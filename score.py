"""Step 4 - Make the case and show the work.
The model proposes a 0-5 score per criterion WITH evidence; CODE then
  - throws out any evidence it cannot trace (deck/form quote not in the document, URL not returned by the research step,
    memo number that doesn't exist) and turns an untraceable criterion into UNKNOWN (which drags, M1);
  - caps traction at 2 when the key number for the business model is absent (M1);
  - computes the overall score (revealed AND written thesis) - the model never gives a bare "7/10";
  - applies the gates and the recommendation rules, which are plain readable code below, not model judgement.
Nothing is decided here: the recommendation is the desk's case for Kushal, who sees every one (M5)."""
import re

import config
import extract
import feedback
import llm
import thesis

S = {"type": "string"}
EVID = {"type": "array", "items": {"type": "object", "properties": {
    "claim": S,
    "source_type": {"type": "string", "enum": ["deck", "form", "web", "memo", "notes", "correction", "absence"]},
    "ref": {"type": "string", "description": "deck/form: exact short quote; web: the URL; memo: 'Memo N'; notes: 'M1'..'M5'; "
                                             "correction: 'correction #id'; absence: what was looked for"},
}, "required": ["claim", "source_type", "ref"]}}

CRIT = {"type": "object", "properties": {
    "score": {"type": "integer", "description": "0-5, or -1 if there is no evidence either way"},
    "written_score": {"type": "integer", "description": "0-5 against the WRITTEN-thesis lens, -1 if unknown"},
    "reason": S, "evidence": EVID,
    "unknowns": {"type": "array", "items": S, "description": "What we could not find out that would change this score"},
}, "required": ["score", "written_score", "reason", "evidence", "unknowns"]}

SCHEMA = {"type": "object", "properties": {
    **{c["key"]: CRIT for c in thesis.CRITERIA},
    "key_number_present": {"type": "boolean", "description": "Is the key number for this business model (below) actually given?"},
    "depends_on_regulatory_change": {"type": "boolean"}, "regulatory_dependence_why": S,
    "capital_density_model": {"type": "boolean", "description": "Needs heavy capex or density far beyond a pre-seed cheque before it works"},
    "precedents": {"type": "array", "items": {"type": "object", "properties": {
        "memo": S, "decision": S, "lesson": S}, "required": ["memo", "decision", "lesson"]},
        "description": "The 1-2 closest past memos and the lesson that carries over"},
    "two_lines": {"type": "string", "description": "Riya's two lines for the partners: what it is, and the crux"},
    "questions_for_call": {"type": "array", "items": S, "description": "3 questions that would resolve the biggest unknowns"},
}, "required": [c["key"] for c in thesis.CRITERIA] + ["key_number_present", "depends_on_regulatory_change",
                                                     "capital_density_model", "precedents", "two_lines", "questions_for_call"]}

PROMPT = """You are the first-pass analyst for All In Capital, a Mumbai pre-seed fund. You do not decide; you make the case
and show your work. Score the applicant on each criterion 0-5 using the anchors. Rules:
- Every evidence item must cite a source: a SHORT exact quote from the deck or form, a URL from the research findings
  below (only those URLs), a memo number, a partner-meeting number, or a correction id. If you looked for something and it
  is not there, add an 'absence' item - absence is evidence.
- Score evidence, not pedigree. Founder claims in the deck that the form contradicts count against candour and founder.
- Founder self-description is not verification. If research could not confirm the founder, say so in unknowns.
- If there is genuinely no evidence for a criterion, score -1.
- The key question for this business model: {key_q}

=== THE FUND'S CRITERIA (reconstructed; revealed thesis = what the memos show) ===
{criteria}

=== WRITTEN THESIS (public record) - use only for written_score ===
{written}

=== PAST DECISIONS (12 memos) AND PARTNER NOTES ===
{seed}

=== {corrections}

=== APPLICANT: structured facts extracted from deck and form ===
{facts}

=== RESEARCH FINDINGS FROM THE WEB (status per variable; only these URLs may be cited) ===
{research}

=== PORTFOLIO OVERLAPS FOUND ===
{conflicts}

=== RAW FORM ===
{form}

=== RAW DECK ===
{deck}
"""


def _seed_text(holdout=None):
    """Memos + partner notes. holdout=<company> (backtest only) removes that company's memo and every note line that
    mentions it, so the desk cannot read the answer it is being tested on."""
    import os
    with open(os.path.join(config.DATA, "seed", "deal_memos.txt"), encoding="utf-8") as h:
        memos = h.read()
    with open(os.path.join(config.DATA, "seed", "partner_meeting_notes.txt"), encoding="utf-8") as h:
        notes = h.read()
    if holdout:
        h = holdout.lower()
        parts = re.split(r"(?=Memo \d+: )", memos)
        memos = "".join(p for p in parts if h not in p.split("\n")[0].lower())
        notes = "\n".join(l for l in notes.split("\n") if h not in l.lower())
    return memos + "\n\n" + notes


def _research_text(research):
    lines = []
    for k, v in research.items():
        if k.startswith("_"):
            continue
        urls = ", ".join(s["url"] for s in v.get("sources", []))
        lines.append(f'- {k}{" (" + v["who"] + ")" if v.get("who") else ""}{" claim: " + v["claim"] if v.get("claim") else ""}: '
                     f'{v["status"]} - {v["finding"]} [{urls or "no sources"}]')
    return "\n".join(lines) or "(none)"


def raise_in_cr(facts):
    v = ((facts.get("raise_amount") or {}).get("value") or "").replace(",", "")
    m = re.search(r"([\d.]+)\s*(cr|crore|l|lakh|lac|m|mn|million)?", v, re.I)
    if not m:
        return None
    n, unit = float(m.group(1)), (m.group(2) or "").lower()
    if unit in ("l", "lakh", "lac"):
        return n / 100
    if unit in ("m", "mn", "million"):
        return n * 8.5 if "$" in v or "usd" in v.lower() else n / 10
    return n


def _verify_evidence(items, rec, research_urls, valid_corrections):
    kept, dropped = [], []
    for e in items:
        t, ref = e.get("source_type"), (e.get("ref") or "").strip()
        ok = True
        if t in ("deck", "form"):
            ok = extract.quote_found(ref, rec, t)
        elif t == "web":
            ok = any(ref and (ref in u or u in ref) for u in research_urls)
        elif t == "memo":
            ok = bool(re.search(r"\b([1-9]|1[0-2])\b", ref))
        elif t == "notes":
            ok = bool(re.search(r"M[1-5]", ref))
        elif t == "correction":
            ok = any(f"#{i}" in ref for i in valid_corrections)
        (kept if ok else dropped).append({**e, "traced": ok})
    return kept, dropped


def score(rec, facts, research, conflicts, exclude_corrections=(), holdout=None):
    blob = " ".join([facts.get("business_model", ""), facts.get("sub_sector", "") or "", facts.get("one_liner", ""), facts.get("sector", "")])
    kq = thesis.key_question_for(blob)
    hits = feedback.retrieve(facts, exclude_app_ids=exclude_corrections)
    import json
    slim = {k: v for k, v in facts.items() if k not in ("unverified_quotes",)}
    prompt = PROMPT.format(
        key_q="; ".join(f'{k["question"]} (precedent: {k["precedent"]})' for k in kq),
        criteria=thesis.as_prompt(), written="\n".join("- " + w for w in thesis.WRITTEN), seed=_seed_text(holdout),
        corrections=feedback.as_prompt(hits), facts=json.dumps(slim, ensure_ascii=False)[:9000],
        research=_research_text(research),
        conflicts="\n".join(f'- {c["level"]}: {c["portfolio_company"]} - {c["why"]}' for c in conflicts) or "(none)",
        form=rec.get("form_text", "")[:12000], deck=rec.get("deck_text", "")[:12000])
    raw = llm.ask_json(prompt, SCHEMA, temperature=config.SCORE_TEMPERATURE)

    research_urls = [s["url"] for k, v in research.items() if not k.startswith("_") for s in v.get("sources", [])]
    crit_out, total_claims, untraced = [], 0, 0
    for c in thesis.CRITERIA:
        r = raw[c["key"]]
        kept, dropped = _verify_evidence(r.get("evidence", []), rec, research_urls, [h["id"] for h in hits])
        total_claims += len(kept) + len(dropped)
        untraced += len(dropped)
        s, ws = r.get("score", -1), r.get("written_score", -1)
        notes = []
        if not kept and s >= 0:
            notes.append("No traceable evidence survived checking -> scored as unknown.")
            s = -1
        if c["key"] == "traction" and not raw.get("key_number_present") and s > 2:
            notes.append(f"Key number for this model is missing -> capped at 2 (M1). Model said {s}.")
            s = 2
        unknown = s < 0
        eff = config.UNKNOWN_SCORE if unknown else max(0, min(5, s))
        weff = config.UNKNOWN_SCORE if ws < 0 else max(0, min(5, ws))
        crit_out.append({"key": c["key"], "name": c["name"], "score": None if unknown else eff, "effective": eff,
                         "written_score": None if ws < 0 else weff, "written_effective": weff,
                         "weight": c["weight_revealed"], "weight_written": c["weight_written"],
                         "reason": r.get("reason"), "evidence": kept, "untraced_evidence": dropped,
                         "unknowns": r.get("unknowns", []), "system_notes": notes, "definition_sources": c["sources"]})

    revealed = round(sum(x["effective"] * x["weight"] for x in crit_out) / 5)
    written = round(sum(x["written_effective"] * x["weight_written"] for x in crit_out) / 5)
    by = {x["key"]: x for x in crit_out}

    # ---- gates (readable rules) ----
    flags = []
    direct = [c for c in conflicts if c["level"] == "direct"]
    if direct:
        flags.append({"key": "portfolio_conflict", "hard": True,
                      "why": "Direct overlap with " + ", ".join(c["portfolio_company"] for c in direct) + " (M4: default is no; hold until the portfolio founder is told)."})
    elif conflicts:
        flags.append({"key": "portfolio_adjacent", "hard": False,
                      "why": "Adjacent to " + ", ".join(c["portfolio_company"] for c in conflicts) + " - Kushal to judge."})
    rc = raise_in_cr(facts)
    stage = (facts.get("stage") or "").lower()
    if (rc and rc > thesis.MAX_ROUND_CR) or re.search(r"series\s*[a-z]", stage):
        flags.append({"key": "stage_mismatch", "hard": True, "why": f"Raising ~INR {rc} Cr at stage '{facts.get('stage')}'. " + thesis.ANTI_THESIS[1]["why"]})
    if raw.get("depends_on_regulatory_change"):
        flags.append({"key": "regulation_bet", "hard": True, "why": (raw.get("regulatory_dependence_why") or "") + " " + thesis.ANTI_THESIS[0]["why"]})
    if raw.get("capital_density_model"):
        flags.append({"key": "capital_density", "hard": False, "why": thesis.ANTI_THESIS[2]["why"]})
    if facts.get("sector") in ("other",):
        flags.append({"key": "outside_sectors", "hard": False, "why": thesis.ANTI_THESIS[3]["why"]})
    if facts.get("inconsistencies"):
        flags.append({"key": "deck_form_mismatch", "hard": False,
                      "why": "; ".join(f'{i["field"]}: deck "{i["deck_says"]}" vs form "{i["form_says"]}"' for i in facts["inconsistencies"])})

    # ---- recommendation (readable rules) ----
    hard = [f for f in flags if f["hard"] and f["key"] != "portfolio_conflict"]
    if hard:
        merit = "Pass - outside the fund's game (partner to confirm)"
    elif revealed >= config.CALL_THRESHOLD and by["founder"]["effective"] >= config.MIN_FOUNDER_FOR_CALL             and by["path"]["effective"] >= config.MIN_PATH_FOR_CALL:
        merit = "Take the call"
    elif revealed < config.PASS_THRESHOLD:
        merit = "Pass"
    else:
        merit = "Partner judgement - borderline"
    # A direct portfolio overlap overrides everything until Kushal has spoken to the portfolio founder (M4),
    # but the merit read is kept so he knows what he is holding.
    rec_ = "HOLD - portfolio conflict" if any(f["key"] == "portfolio_conflict" for f in flags) else merit

    unknown_crit = [x["name"] for x in crit_out if x["score"] is None]
    return {
        "company": facts.get("company"), "sector": facts.get("sector"), "one_liner": facts.get("one_liner"),
        "recommendation": rec_, "merit_recommendation": merit, "score_revealed": revealed, "score_written": written,
        "drift": abs(revealed - written) >= 15,
        "scored_against": "Revealed thesis (what the 12 memos and partner notes show the fund actually does); the written-thesis score is shown beside it.",
        "criteria": crit_out, "flags": flags, "conflicts": conflicts,
        "key_questions": kq, "precedents": raw.get("precedents", []), "two_lines": raw.get("two_lines"),
        "questions_for_call": raw.get("questions_for_call", []), "corrections_applied": hits,
        "unknown_criteria": unknown_crit,
        "claims_total": total_claims, "claims_untraced": untraced,
        "untraced_share": round(untraced / total_claims, 3) if total_claims else 0,
        "deeptech_second_call": "Aditya does the second call himself (M3)" if facts.get("sector") == "deeptech" else None,
    }
