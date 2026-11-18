"""Backtest against the fund's own decisions (case: "Run it against those and tell me how often it disagrees with us.
When it does, tell me whether we were wrong or it was.")

Design choices, written down before running:
- The 12 memos become pseudo-applications: what it does, sector, stage, source, founder assessment, risks.
  REMOVED: the decision line and the whole "Why we invested/passed" paragraph.
- Hold-out: when scoring company X, memo X and every partner-note line naming X are removed from the desk's context, and
  any correction seeded from X is excluded (leave-one-out). Otherwise the test would read its own answer.
- Web research OFF: several of these are real, famous companies; searching would leak what happened (hindsight).
- Honest limit: memos contain the partners' read of the founder AFTER a call; real applications only have a deck. So this
  tests whether the desk's thesis reproduces the fund's judgement, not whether it can see founder behaviour from a deck.
- Mapping: desk "Take the call" = leans invest; desk "Pass..." = leans pass; "Partner judgement - borderline" is counted
  as a disagreement (conservative) and listed separately.
- For every disagreement, a separate hindsight step searches what happened to the company since, and a judge says
  whether the FUND or the DESK looks wrong - or that it is too early / not public."""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import config
import llm
import pipeline
import storage

SHORT = {"The ePlane Company": "ePlane", "Unbox Robotics": "Unbox", "Wint Wealth": "Wint", "Jai Kisan": "Jai Kisan"}


def load_memos():
    with open(os.path.join(config.DATA, "seed", "deal_memos.txt"), encoding="utf-8") as f:
        text = f.read()
    out = []
    for block in re.split(r"(?=Memo \d+: )", text)[1:]:
        head = block.split("\n", 1)[0]
        name = re.sub(r"^Memo \d+: ", "", head).strip()
        meta = re.search(r"Sector: (.*?) \| Stage: (.*?) \| Source: (.*?) \| Decision: (\w+)", block)
        body = block[block.index(meta.group(0)) + len(meta.group(0)):] if meta else block
        body = re.split(r"Why we (invested|passed)\.", body)[0].strip()
        out.append({"name": name, "num": int(re.match(r"Memo (\d+)", head).group(1)), "sector": meta.group(1),
                    "stage": meta.group(2), "source_channel": meta.group(3), "decision": meta.group(4),
                    "why": re.split(r"Why we (?:invested|passed)\.", block)[1].strip() if "Why we" in block else ""})
        out[-1]["form_text"] = (f"Company name {name}\nSector {meta.group(1)}\nStage {meta.group(2)}\nHow did you hear about us? "
                                f"{meta.group(3)}\n\n{body}")
    return out


def lean(rec):
    r = rec or ""
    if r.startswith("Take the call"):
        return "invest"
    if r.startswith("Pass"):
        return "pass"
    if r.startswith("HOLD"):
        return "hold"
    return "borderline"


HINDSIGHT = {"type": "object", "properties": {
    "who_looks_wrong": {"type": "string", "enum": ["fund", "desk", "neither_too_early", "not_public"]},
    "driving_criterion": {"type": "string", "description": "Which desk criterion caused the disagreement"},
    "explanation": {"type": "string"},
    "source_numbers": {"type": "array", "items": {"type": "integer"}},
}, "required": ["who_looks_wrong", "driving_criterion", "explanation", "source_numbers"]}


def hindsight(m, read):
    try:
        text, sources = llm.ask_search(
            f"Search the web now (do not answer from memory). What has happened to the Indian startup {m['name']} "
            f"({m['sector']}) since its early funding round: later rounds, revenue, shutdown, acquisition? Name each page.")
    except Exception as e:  # noqa: BLE001
        text, sources = f"search failed: {e}", []
    listing = "\n".join(f"{i+1}. {s['title']} {s['url']}" for i, s in enumerate(sources))
    crit = "; ".join(f'{c["key"]}={c["score"]} ({c["reason"][:120]})' for c in read.get("criteria", []))
    j = llm.ask_json(
        f"A VC fund decided {m['decision']} on {m['name']} for this reason: {m['why']}\n"
        f"An AI triage desk instead recommended '{read.get('recommendation')}' (score {read.get('score_revealed')}/100). "
        f"Desk criteria: {crit}\n\nWhat happened since (web search):\n{text[:3000]}\nSources:\n{listing or '(none)'}\n\n"
        "Who looks wrong in hindsight? 'not_public' if the search found nothing about THIS company (many may be "
        "illustrative). Name the desk criterion that drove the disagreement. Use only the sources for facts.", HINDSIGHT)
    used = [sources[n - 1] for n in j.get("source_numbers", []) if 0 < n <= len(sources)]
    if not used and j["who_looks_wrong"] in ("fund", "desk"):
        j["explanation"] += " (No source tied to this verdict - judged on reasoning only.)"
    return {**j, "sources": used}


def run():
    memos = load_memos()
    storage.event(None, "backtest_start", {"n": len(memos)})

    def one(m):
        rec = {"id": "memo-" + re.sub(r"[^a-z0-9]+", "-", m["name"].lower()).strip("-"), "name": m["name"],
               "batch": "backtest", "form_text": m["form_text"], "deck_text": "", "source": m["source_channel"]}
        read = pipeline.run_one(rec, exclude_corrections=(rec["id"],), do_research=False, persist=False,
                                holdout=SHORT.get(m["name"], m["name"]))
        desk = lean(read.get("recommendation"))
        fund = "invest" if m["decision"].upper().startswith("INVEST") else "pass"
        row = {"memo": m["num"], "company": m["name"], "sector": m["sector"], "fund": m["decision"],
               "desk": read.get("recommendation"), "merit": read.get("merit_recommendation"), "score": read.get("score_revealed"),
               "score_written": read.get("score_written"), "agree": desk == fund,
               "criteria": {c["key"]: c["score"] for c in read.get("criteria", [])}, "flags": [f["key"] for f in read.get("flags", [])],
               "two_lines": read.get("two_lines"), "error": read.get("error")}
        if not row["agree"]:
            row["hindsight"] = hindsight(m, read)
        return row

    with ThreadPoolExecutor(4) as ex:
        rows = sorted(ex.map(one, memos), key=lambda r: r["memo"])
    agree = sum(r["agree"] for r in rows)
    result = {"rows": rows, "agree": agree, "n": len(rows), "gate": config.BACKTEST_MIN_AGREEMENT,
              "passes_gate": agree >= config.BACKTEST_MIN_AGREEMENT,
              "written_vs_revealed": {
                  "revealed_agree": agree,
                  "note": "Scores against the written thesis are kept per row (score_written) to show the drift Riya raised in M5."}}
    storage.save_backtest(result)
    os.makedirs("reports", exist_ok=True)
    with open("reports/backtest.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False, default=str)
    return result


if __name__ == "__main__":
    r = run()
    for x in r["rows"]:
        print(f'{x["memo"]:>2} {x["company"]:<20} fund={x["fund"]:<8} desk={x["desk"]:<48} {x["score"]}/{x["score_written"]} '
              f'{"AGREE" if x["agree"] else "DISAGREE -> " + x.get("hindsight", {}).get("who_looks_wrong", "")} {x.get("error") or ""}')
    print(f'\nAgreement {r["agree"]}/{r["n"]} (gate {r["gate"]}) -> {"PASS" if r["passes_gate"] else "FAIL: do not go live"}')
    sys.exit(0)
