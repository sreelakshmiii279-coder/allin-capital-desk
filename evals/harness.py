"""Eval harness (L7): Feed input -> Run agent -> Check assertion -> Log pass/fail -> Report by severity.

It talks to the desk ONLY over HTTP (BASE_URL). It does not import the desk's code.
  python evals/harness.py                     run every case twice, write evals/reports/latest.md
  python evals/harness.py --only C1,BK3       a subset
  python evals/harness.py --break             sabotage the captured outputs: the harness must catch it
  python evals/harness.py --audit-compare evals/audit/sample-XXXX.csv   compare your blind human verdicts with the judge
Env: BASE_URL (default http://localhost:5057), EVAL_PASSWORD (falls back to EDIT_PASSWORD in ../.env),
     judge: ANTHROPIC_API_KEY (preferred) or OPENAI_API_KEY; else Gemini, reported as SAME FAMILY as the agent."""
import argparse
import csv
import datetime as dt
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _dotenv():
    vals = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                vals[k] = v.strip().strip('"')
    return vals


ENV = {**_dotenv(), **os.environ}
BASE = ENV.get("BASE_URL", "http://localhost:5057").rstrip("/")
PW = ENV.get("EVAL_PASSWORD") or ENV.get("EDIT_PASSWORD", "")


# ---------------- judge (a different model family when possible) ----------------
class Judge:
    def __init__(self):
        if ENV.get("ANTHROPIC_API_KEY"):
            self.provider, self.model, self.same_family = "anthropic", ENV.get("JUDGE_MODEL", "claude-sonnet-5-5"), False
        elif ENV.get("OPENAI_API_KEY"):
            self.provider, self.model, self.same_family = "openai", ENV.get("JUDGE_MODEL", "gpt-4.1"), False
        else:
            self.provider, self.model, self.same_family = "gemini", ENV.get("JUDGE_MODEL", ENV.get("GEMINI_MODEL", "gemini-3.5-flash")), True

    def describe(self):
        s = f"{self.provider}:{self.model}"
        return s + (" - SAME FAMILY as the agent (Gemini): shares its blind spots; set ANTHROPIC_API_KEY or OPENAI_API_KEY"
                    if self.same_family else " - different family from the agent (Gemini)")

    def ask(self, prompt):
        if self.provider == "anthropic":
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=120, headers={
                "x-api-key": ENV["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 800, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"])
        if self.provider == "openai":
            r = requests.post("https://api.openai.com/v1/chat/completions", timeout=120,
                              headers={"Authorization": f"Bearer {ENV['OPENAI_API_KEY']}"},
                              json={"model": self.model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent", timeout=120,
                          headers={"x-goog-api-key": ENV["GEMINI_API_KEY"]},
                          json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def grade(self, case, shown, rubric):
        prompt = ("You are a strict QA judge. Grade an AI system's output against a checklist. Every item must hold for a pass. "
                  "Use only the output shown; do not assume anything that is not there.\n\n"
                  f"Scenario: {case['partition']} ({case['decision']})\nExpected behaviour: {case['expected']}\n\n"
                  f"Output shown:\n{json.dumps(shown, ensure_ascii=False)[:6000]}\n\nChecklist:\n"
                  + "\n".join(f"{i+1}. {r}" for i, r in enumerate(rubric)) +
                  '\n\nReply with JSON only: {"items": [{"n": 1, "pass": true, "why": "..."}], "pass": true}')
        for attempt in range(2):
            try:
                txt = self.ask(prompt)
                return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            except Exception as e:  # noqa: BLE001
                err = str(e)
        return {"pass": False, "items": [], "why": f"judge failed: {err[:150]}"}


# ---------------- assertions ----------------
def get_path(obj, path):
    """'a.b', 'a[*].b', '[*]' -> value or list."""
    parts = [p for p in re.split(r"\.(?![^\[]*\])", path) if p] if path else []
    cur = [obj]
    multi = False
    for p in parts:
        m = re.match(r"^([^\[]*)(\[\*\])?$", p)
        key, star = m.group(1), m.group(2)
        nxt = []
        for c in cur:
            v = c.get(key) if (key and isinstance(c, dict)) else (c if not key else None)
            if star:
                multi = True
                nxt.extend(v or [])
            else:
                nxt.append(v)
        cur = nxt
    return cur if multi else (cur[0] if cur else None)


def check_hard(a, out):
    v, op, want = get_path(out, a["path"]), a["op"], a.get("value")
    lst = v if isinstance(v, list) else ([] if v is None else [v])
    s = lambda x: str(x)
    ok = {
        "eq": lambda: v == want, "ne": lambda: v != want, "in": lambda: v in want,
        "lte": lambda: v is not None and v <= want, "gte": lambda: v is not None and v >= want,
        "lt": lambda: v is not None and v < want, "gt": lambda: v is not None and v > want,
        "is_null": lambda: v is None, "starts_with": lambda: isinstance(v, str) and v.startswith(want),
        "contains": lambda: want in lst, "not_contains": lambda: want not in lst,
        "any_contains": lambda: any(want in s(x) for x in lst), "none_contains": lambda: not any(want in s(x) for x in lst),
        "any_contains_ci": lambda: any(want.lower() in s(x).lower() for x in lst),
        "none_contains_ci": lambda: not any(want.lower() in s(x).lower() for x in lst),
        "len_eq": lambda: len(lst) == want, "len_gte": lambda: len(lst) >= want, "len_lte": lambda: len(lst) <= want,
        "all_in": lambda: all(x in want for x in lst),
        "none_where": lambda: not any(isinstance(x, dict) and x.get("status") == want["status"] and x.get("decision") is not None
                                      for x in lst),
    }[op]()
    return ok, f'{a["path"]} {op} {json.dumps(want) if want is not None else ""} -> got {json.dumps(v, ensure_ascii=False)[:160]}'


# ---------------- run ----------------
def call(case):
    url = BASE + case["endpoint"]
    body = case["input"]
    if body and ("form_file" in body or "deck_file" in body):
        body = dict(body)
        for k in ("form", "deck"):
            f = body.pop(f"{k}_file", None)
            if f:
                body[k] = open(os.path.join(ROOT, f), encoding="utf-8").read()
        body["deck"] = body.get("deck", "") + body.pop("extra_deck", "")
    t0 = time.time()
    try:
        if case["method"] == "GET":
            r = requests.get(url, timeout=300)
        else:
            r = requests.post(url, json=body, timeout=600, headers={"X-Desk-Password": PW})
        out = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": r.text[:300]}
        status = r.status_code
    except Exception as e:  # noqa: BLE001
        out, status = {"error": f"{type(e).__name__}: {e}"}, 0
    return out, status, round(time.time() - t0, 1)


SABOTAGE = {bool: lambda v: not v, int: lambda v: v + 7, float: lambda v: v + 7.0, str: lambda v: "SABOTAGED"}


def sabotage(o):
    if isinstance(o, dict):
        return {k: sabotage(v) for k, v in o.items()}
    if isinstance(o, list):
        return [] if o else ["SABOTAGED"]
    f = SABOTAGE.get(type(o))
    return f(o) if f else "SABOTAGED"


def evaluate(case, out, status, judge, broken=False):
    if broken:
        out = sabotage(out)
    results = []
    if status != 200 and not broken:
        results.append({"kind": "transport", "pass": False, "detail": f"HTTP {status}: {str(out.get('error', out))[:200]}"})
    else:
        for a in case["assertions"]:
            if a["kind"] == "hard":
                try:
                    ok, detail = check_hard(a, out)
                except Exception as e:  # noqa: BLE001
                    ok, detail = False, f"assertion error {type(e).__name__}: {e}"
                results.append({"kind": "hard", "pass": bool(ok), "detail": detail})
            else:
                shown = {p: get_path(out, p) for p in a["show"]}
                g = judge.grade(case, shown, a["rubric"]) if not broken else {"pass": False, "items": []}
                results.append({"kind": "soft", "pass": bool(g.get("pass")), "detail": json.dumps(g.get("items") or g.get("why"))[:400],
                                "rubric": a["rubric"], "shown": shown})
    return all(r["pass"] for r in results), results


def run(cases, runs, workers, judge, broken=False):
    allres = []
    for n in range(runs):
        with ThreadPoolExecutor(workers) as ex:
            outs = list(ex.map(call, cases))
        for c, (out, status, secs) in zip(cases, outs):
            ok, res = evaluate(c, out, status, judge, broken)
            allres.append({"run": n + 1, "id": c["id"], "pass": ok, "results": res, "seconds": secs,
                           "prompt_version": out.get("prompt_version") if isinstance(out, dict) else None,
                           "output": out if not broken else None})
        print(f"run {n+1}: {sum(r['pass'] for r in allres if r['run'] == n+1)}/{len(cases)} passed", flush=True)
    return allres


def report(cases, allres, judge, runs, started):
    by_id = {c["id"]: c for c in cases}
    last = {r["id"]: r for r in allres if r["run"] == runs}
    flips = sorted({r["id"] for r in allres if any(x["id"] == r["id"] and x["pass"] != r["pass"] for x in allres)})
    canary_passed = last.get("CANARY", {}).get("pass")
    real = [c for c in cases if c["id"] != "CANARY"]
    fails = [c for c in real if not last[c["id"]]["pass"]]
    sev = lambda s: [c for c in real if c["severity"] == s]
    crit_fail = [c for c in fails if c["severity"] == "critical"]
    kills = sorted({c["kill"] for c in crit_fail if c["kill"]} | ({"K13"} if any(by_id[i]["severity"] == "critical" for i in flips) else set()))
    high = sev("high")
    high_rate = sum(last[c["id"]]["pass"] for c in high) / len(high) if high else 1
    ship = not crit_fail and not kills and canary_passed is False and high_rate >= 0.9
    L = [f"# Eval run - {started:%Y-%m-%d %H:%M} IST", "",
         f"**Verdict: {'SHIP to Riya' if ship else 'DO NOT SHIP'}** - "
         f"{len(real) - len(fails)}/{len(real)} passed · critical {len(sev('critical')) - len(crit_fail)}/{len(sev('critical'))} · "
         f"high {round(high_rate*100)}% (bar 90%) · low {sum(last[c['id']]['pass'] for c in sev('low'))}/{len(sev('low'))}", "",
         f"- Runs: {runs} (same input, same verdict?) - **{len(flips)} case(s) flipped**: {', '.join(flips) or 'none'}",
         f"- Canary (must fail): **{'failed as it should - harness is checking' if canary_passed is False else 'PASSED - THE HARNESS IS NOT CHECKING ANYTHING'}**",
         f"- Kill criteria fired: **{', '.join(kills) or 'none'}**",
         f"- Judge: {judge.describe()}",
         f"- Prompt versions seen: {', '.join(sorted({str(r['prompt_version']) for r in allres if r['prompt_version']})) or 'n/a'}",
         f"- Target: {BASE}", "", "## Failures (last run), most severe first", "",
         "| Case | Severity | Kill | Decision | Partition | Diagnosis |", "|---|---|---|---|---|---|"]
    order = {"critical": 0, "high": 1, "low": 2}
    for c in sorted(fails, key=lambda c: order[c["severity"]]):
        bad = [r for r in last[c["id"]]["results"] if not r["pass"]]
        diag = "; ".join(r["detail"] for r in bad)[:300].replace("|", "/")
        L.append(f'| {c["id"]} | {c["severity"]} | {c["kill"] or ""} | {c["decision"]} | {c["partition"]} | {diag} |')
    L += ["", "## By decision", "", "| Decision | Passed | Cases |", "|---|---|---|"]
    decs = {}
    for c in real:
        decs.setdefault(c["decision"], []).append(c)
    for d, cs in decs.items():
        L.append(f'| {d} | {sum(last[c["id"]]["pass"] for c in cs)}/{len(cs)} | {", ".join(c["id"] + ("" if last[c["id"]]["pass"] else "✗") for c in cs)} |')
    return "\n".join(L), ship


def write_audit(cases, allres, started):
    """5-10% of soft-judged cases for a blind human check (L7): the judge's verdict is NOT in the file."""
    soft = [r for r in allres if r["run"] == 1 and any(x["kind"] == "soft" for x in r["results"])]
    if not soft:
        return None
    k = max(1, round(len(soft) * 0.1))
    pick = random.Random(started.toordinal()).sample(soft, min(k, len(soft)))
    os.makedirs(os.path.join(HERE, "audit"), exist_ok=True)
    path = os.path.join(HERE, "audit", f"sample-{started:%Y%m%d-%H%M}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "rubric", "output_shown", "human_verdict (pass/fail)", "human_note"])
        for r in pick:
            for x in r["results"]:
                if x["kind"] == "soft":
                    w.writerow([r["id"], " | ".join(x["rubric"]), json.dumps(x["shown"], ensure_ascii=False)[:2000], "", ""])
    return path


def audit_compare(path):
    runs = sorted(f for f in os.listdir(os.path.join(HERE, "results")) if f.endswith(".json"))
    data = json.load(open(os.path.join(HERE, "results", runs[-1]), encoding="utf-8"))
    judge_v = {r["id"]: next((x["pass"] for x in r["results"] if x["kind"] == "soft"), None) for r in data["results"] if r["run"] == 1}
    agree = n = 0
    with open(os.path.join(HERE, "audit", "disagreements.jsonl"), "a", encoding="utf-8") as out:
        for row in csv.DictReader(open(path, encoding="utf-8")):
            hv = (row.get("human_verdict (pass/fail)") or "").strip().lower()
            if hv not in ("pass", "fail"):
                continue
            n += 1
            j = judge_v.get(row["case"])
            if (hv == "pass") == j:
                agree += 1
            else:
                out.write(json.dumps({"case": row["case"], "human": hv, "judge": j, "note": row.get("human_note"),
                                      "at": dt.datetime.now().isoformat(timespec="seconds")}) + "\n")
    print(f"human vs judge: {agree}/{n} agree; disagreements logged to evals/audit/disagreements.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--break", dest="broken", action="store_true")
    ap.add_argument("--audit-compare", default="")
    a = ap.parse_args()
    if a.audit_compare:
        return audit_compare(a.audit_compare)
    cases = json.load(open(os.path.join(HERE, "cases.json"), encoding="utf-8"))
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in keep or c["id"] == "CANARY"]
    try:
        env = requests.get(BASE + "/api/setup", timeout=30).json().get("env")
    except Exception:  # noqa: BLE001
        env = None
    if env != "test":
        print(f"Refusing to run: {BASE} reports env={env!r}. Evals run only against the TEST environment (L8: test and live "
              "are separate). Start the local desk with DESK_ENV=test.")
        return 2
    judge = Judge()
    started =dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    print(f"{len(cases)} cases x {a.runs} run(s) against {BASE}; judge {judge.describe()}", flush=True)
    allres = run(cases, 1 if a.broken else a.runs, a.workers, judge, a.broken)
    if a.broken:
        caught = sum(not r["pass"] for r in allres)
        print(f"BREAK-ON-PURPOSE: harness caught {caught}/{len(allres)} sabotaged outputs "
              f"({'OK' if caught >= len(allres) - 1 else 'HARNESS MISSES SABOTAGE'})")
        return
    md, ship = report(cases, allres, judge, a.runs, started)
    if a.only:
        ship = False
        md = md.replace("**Verdict: SHIP to Riya**", "**Subset run - not a ship decision (only a full run decides)**").replace(
            "**Verdict: DO NOT SHIP**", "**Subset run - DO NOT SHIP (failures below)**")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    stamp = f"{started:%Y%m%d-%H%M}"
    json.dump({"started": started.isoformat(), "judge": judge.describe(), "ship": ship, "results": allres},
              open(os.path.join(HERE, "results", f"run-{stamp}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
    audit = write_audit(cases, allres, started)
    if audit:
        md += f"\n\nBlind human audit sample (10% of soft cases, judge verdict hidden): `{os.path.relpath(audit, ROOT)}`"
    open(os.path.join(HERE, "reports", f"run-{stamp}.md"), "w", encoding="utf-8").write(md)
    open(os.path.join(HERE, "reports", "latest.md"), "w", encoding="utf-8").write(md)
    print(md.split("## By decision")[0].encode("ascii", "replace").decode())


if __name__ == "__main__":
    sys.exit(main())
