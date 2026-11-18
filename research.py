"""Step 3 - Go find what the founder did not put in the deck (S4 evidence map + agentic loop).

EVIDENCE MAP (S4). One row per variable. The loop works down the rows, each capped, the whole app capped.
| Variable            | Data that answers it                          | Where it lives                         | Sufficient when                                         | Max tries | Short circuit |
|---------------------|-----------------------------------------------|----------------------------------------|---------------------------------------------------------|-----------|---------------|
| company_presence    | live site, matches the deck's product         | company website (request, cleaned)      | site fetched and describes the same product, OR 1 independent mention | 2 | site unreachable twice -> unknown, continue |
| founder_<n>         | employer/role/years claimed in the form       | search results (LinkedIn only via search snippets - no scraping: ToS, hiQ v LinkedIn), press, company pages | 1 independent source naming the SAME person (name + company or employer) | 2 per founder | none |
| traction_claims     | named customers, partners, awards, licences   | press, customer sites, registries       | 1 independent mention per claim                         | 1 per claim, 2 claims | none |
| competition         | who else does this in India, how funded       | search, news                            | 2 named competitors with sources                        | 1         | none |
| regulation          | the rule this model depends on and its status | regulator sites, news (only for regulated models) | the governing rule named with a source           | 1         | none |
Global cap: config.MAX_SEARCHES_PER_APP. Anti-thesis short circuit: if the screen flags a hard exclusion, only
company_presence runs (we still send the read to Kushal - nobody is auto-rejected - but we don't spend research on it).

Every finding keeps its source URLs. A search that returns no sources is treated as "not found" (the model answered from
memory, which we never use). A finding about a namesake is rejected (CEO-vs-CTO lesson from S5: similar is not same)."""
import re

import requests
from bs4 import BeautifulSoup

import config
import llm

REGULATED = re.compile(r"lend|credit|loan|bnpl|nbfc|payment|insur|wealth|invest|bond|crypto|drone|uav|evtol|aviation|"
                       r"health|clinic|medic|pharma|telecom|call[- ]record|food|fssai|education|edtech|real estate|rent", re.I)

JUDGE = {"type": "object", "properties": {
    "status": {"type": "string", "enum": ["confirmed", "contradicted", "partial", "not_found", "namesake_only"]},
    "finding": {"type": "string", "description": "One or two sentences, only what the sources say"},
    "source_numbers": {"type": "array", "items": {"type": "integer"}, "description": "1-based indexes of the sources used"},
}, "required": ["status", "finding", "source_numbers"]}


def _clean_html(html):
    """S4 hybrid extraction: rules strip the noise first, only clean text goes to the model."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "form", "iframe"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return text[: config.MAX_PAGE_CHARS]


def fetch_site(url):
    """Request-based fetch (cheap). Returns (text, error). Permanent errors (DNS, 404) are not retried."""
    if not url:
        return "", "no website given"
    if not url.startswith("http"):
        url = "https://" + url.strip().lstrip("/")
    if re.search(r"\.example(/|$)", url):
        return "", "placeholder domain (.example) - not a real website"
    try:
        r = requests.get(url, timeout=config.FETCH_TIMEOUT_S, headers={"User-Agent": config.USER_AGENT})
        if r.status_code >= 400:
            return "", f"HTTP {r.status_code}"
        return _clean_html(r.text), ""
    except requests.RequestException as e:
        return "", f"unreachable ({type(e).__name__})"


import threading
_LOCK = threading.Lock()


class Budget:
    def __init__(self):
        self.used = 0

    def ok(self):
        return self.used < config.MAX_SEARCHES_PER_APP

    def take(self):
        with _LOCK:
            if self.used >= config.MAX_SEARCHES_PER_APP:
                return False
            self.used += 1
            return True


def _search_and_judge(question, must_match, budget, log):
    """One search + one judgement. Returns a finding dict (always with sources, maybe empty)."""
    if not budget.take():
        return {"status": "not_found", "finding": "Search budget for this application used up (cap).", "sources": []}
    try:
        text, sources = llm.ask_search(
            "Search the web now (do not answer from memory). " + question +
            " Report only what the pages say, and name the page each fact comes from.")
    except Exception as e:  # noqa: BLE001
        log.append({"q": question, "error": str(e)[:200]})
        return {"status": "not_found", "finding": f"search failed: {str(e)[:120]}", "sources": []}
    if not sources:
        log.append({"q": question, "sources": 0})
        return {"status": "not_found", "finding": "No web sources returned.", "sources": []}
    listing = "\n".join(f"{i+1}. {s['title']} {s['url']}" for i, s in enumerate(sources))
    j = llm.ask_json(
        f"Question: {question}\nIdentity rule: {must_match}\n\nSearch answer:\n{text[:4000]}\n\nSources:\n{listing}\n\n"
        "Judge strictly. 'namesake_only' if sources are about a different person/company with the same name. "
        "'not_found' if nothing relevant. Do not use your own knowledge.", JUDGE, temperature=0.0)
    used = [sources[n - 1] for n in j.get("source_numbers", []) if 0 < n <= len(sources)]
    if j["status"] in ("confirmed", "contradicted", "partial") and not used:
        j["status"] = "not_found"
        j["finding"] += " (no source could be tied to this; treated as not found)"
    log.append({"q": question, "status": j["status"], "sources": len(used)})
    return {"status": j["status"], "finding": j["finding"], "sources": used}


def research(rec, facts, hard_flag=False):
    budget, log, out = Budget(), [], {}

    # company_presence: website first (cheap request), then search
    site_text, err = fetch_site(facts.get("website") or "")
    if site_text:
        out["company_presence"] = {"status": "confirmed", "finding": f"Website fetched ({len(site_text)} chars of clean text).",
                                   "sources": [{"title": "Company website", "url": facts.get("website")}], "site_excerpt": site_text[:800]}
    else:
        tries, res = 0, None
        while tries < config.MAX_TRIES_PER_VARIABLE and budget.ok():
            tries += 1
            q = (f'Find any independent web mention of the Indian startup "{facts.get("company")}" '
                 f'({facts.get("one_liner", "")}, {facts.get("location", "")}).') if tries == 1 else \
                (f'"{facts.get("company")}" startup {facts.get("location", "")} founders '
                 + " ".join(f["name"] for f in facts.get("founders", [])))
            res = _search_and_judge(q, f'Must be the same company: {facts.get("company")}, {facts.get("one_liner", "")}', budget, log)
            if res["status"] in ("confirmed", "partial", "contradicted"):
                break
        res = res or {"status": "not_found", "finding": "", "sources": []}
        res["finding"] = f"Website: {err}. " + res["finding"]
        out["company_presence"] = res

    if hard_flag:
        out["_short_circuit"] = "Anti-thesis flag: deep research skipped to save cost; read still goes to Kushal."
        out["_searches"] = budget.used
        out["_log"] = log
        return out

    company = facts.get("company")
    tasks = []

    def founder_task(i, f):
        res, tries = None, 0
        while tries < config.MAX_TRIES_PER_VARIABLE and budget.ok():
            tries += 1
            if tries == 1:
                q = (f'Professional background of {f["name"]}, {f.get("role", "")} of {company} '
                     f'(India). The application says: "{f.get("background", "")}". Look for LinkedIn, press, talks, past employers.')
            else:
                q = f'{f["name"]} {f.get("background", "")[:80]} LinkedIn OR interview OR profile'
            res = _search_and_judge(q, f'Same person: {f["name"]} AND (company {company} OR the employer/role stated: {f.get("background", "")[:100]})', budget, log)
            if res["status"] in ("confirmed", "partial", "contradicted"):
                break
        return f"founder_{i+1}", {"who": f["name"], **(res or {"status": "not_found", "finding": "search budget exhausted", "sources": []})}

    for i, f in enumerate(facts.get("founders", [])[:3]):
        tasks.append(lambda i=i, f=f: founder_task(i, f))
    # traction claims (max 2) - skip claims that are just founder bios (already covered above)
    names = [f["name"].split()[0].lower() for f in facts.get("founders", [])]
    claims = [c for c in facts.get("claims_to_verify", []) if not any(n in c["claim"].lower() for n in names)][:2]
    for i, c in enumerate(claims):
        tasks.append(lambda i=i, c=c: (f"claim_{i+1}", {"claim": c["claim"], **_search_and_judge(
            f'Is this claim by the startup {company} independently confirmed anywhere: "{c["claim"]}"?',
            f'Must be about {company} specifically', budget, log)}))
    tasks.append(lambda: ("competition", _search_and_judge(
        f'Which Indian startups or companies already do this: {facts.get("one_liner", "")}? Name them and their funding.',
        "Any real company doing the same thing in India counts", budget, log)))
    model_text = " ".join([facts.get("business_model", ""), facts.get("sub_sector", "") or "", facts.get("one_liner", "")])
    if REGULATED.search(model_text):
        tasks.append(lambda: ("regulation", _search_and_judge(
            f'What Indian regulation governs this business model and what is its current status: {facts.get("one_liner", "")} '
            f'({facts.get("business_model", "")})? Name the regulator and the rule.',
            "Must be an Indian regulator or law relevant to this model", budget, log)))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(5) as ex:
        for key, val in ex.map(lambda t: t(), tasks):
            out[key] = val

    out["_searches"] = budget.used
    out["_log"] = log
    return out
