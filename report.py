"""Writes reports/batch_report.md and reports/backtest.md from what is stored (python report.py)."""
import os

import storage


def batch():
    reads = storage.latest_reads()
    reads = [r for r in reads if r["record"].get("batch") != "backtest"]
    order = lambda r: (0 if r["read"]["recommendation"].startswith("Take the call") else 1 if r["read"]["recommendation"].startswith("HOLD")
                       else 2 if r["read"]["recommendation"].startswith("Partner") else 3, -(r["read"].get("score_revealed") or 0))
    reads.sort(key=order)
    L = ["# This week's batch: the desk's read", "",
         "Scored against the **revealed** thesis (written-thesis score beside it). Nothing here is a decision: every row waits for Kushal.", "",
         "| Company | Desk's case | On merit | Revealed | Written | Flags | Unknown criteria | Claims traced | Searches | Time |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in reads:
        d = r["read"]
        L.append(f'| {r["record"]["name"]} | {d["recommendation"]} | {d.get("merit_recommendation", "")} | {d.get("score_revealed")} | '
                 f'{d.get("score_written")} | {", ".join(f["key"] for f in d.get("flags", []))} | {len(d.get("unknown_criteria", []))} | '
                 f'{(d.get("claims_total") or 0) - (d.get("claims_untraced") or 0)}/{d.get("claims_total")} | '
                 f'{(d.get("research") or {}).get("_searches", "")} | {d.get("seconds")}s |')
    L += ["", "## Two lines each", ""]
    for r in reads:
        d = r["read"]
        L.append(f'**{r["record"]["name"]}** ({d["recommendation"]}, {d.get("score_revealed")}/100). {d.get("two_lines", "")}')
        crit = "; ".join(f'{c["key"]} {c["score"] if c["score"] is not None else "unknown"}' for c in d.get("criteria", []))
        L.append(f'<br><sub>{crit}. Could not find out: ' + "; ".join(u for c in d.get("criteria", []) for u in c.get("unknowns", [])[:1]) + "</sub>")
        L.append("")
    return "\n".join(L)


def backtest():
    bt = storage.latest_backtest()
    if not bt:
        return "No backtest run yet."
    b = bt["result"]
    rows = b["rows"]

    def lean(rec, score):
        return rec
    inv = [r for r in rows if r["fund"].startswith("INVEST")]
    pas = [r for r in rows if not r["fund"].startswith("INVEST")]
    avg = lambda xs: sum(xs) / len(xs) if xs else 0
    wi, wp = avg([r["score_written"] or 0 for r in inv]), avg([r["score_written"] or 0 for r in pas])
    ri, rp = avg([r["score"] or 0 for r in inv]), avg([r["score"] or 0 for r in pas])
    pet_w = next((r["score_written"] for r in rows if r["company"] == "Petalry"), "?")
    w_agree = sum(1 for r in rows if ((r["score_written"] or 0) >= 60) == r["fund"].startswith("INVEST"))
    r_agree_simple = sum(1 for r in rows if ((r["score"] or 0) >= 60) == r["fund"].startswith("INVEST"))
    L = [f"# Backtest: the desk vs the fund's own decisions", "",
         f"Run {bt['at'][:16]} UTC. **Agreement: {b['agree']}/{b['n']}** against the pre-agreed gate of {b['gate']}/12 → "
         f"**{'PASS' if b['passes_gate'] else 'FAIL'}**.", "",
         "How it was run: each memo became a pseudo-application with the decision and the 'why' paragraph removed; its own memo, every "
         "partner-note line naming it, and any correction seeded from it were hidden (leave-one-out); web research was off so hindsight "
         "could not leak in. Desk 'Take the call' = leans invest; 'Pass…' = leans pass; 'borderline' counts as a disagreement.", "",
         "| # | Company | Fund | Desk | Revealed | Written | Agree |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f'| {r["memo"]} | {r["company"]} | {r["fund"]} | {r["desk"]} | {r["score"]} | {r["score_written"]} | {"yes" if r["agree"] else "**no**"} |')
    L += ["", "## Where it disagrees, and who looks wrong", ""]
    for r in rows:
        if r["agree"]:
            continue
        h = r.get("hindsight", {})
        src = ", ".join(f'[{s.get("title", "source")[:40]}]({s["url"]})' for s in h.get("sources", [])[:3])
        L.append(f'**{r["company"]}** — fund {r["fund"]}, desk "{r["desk"]}" ({r["score"]}/100). Driving criterion: *{h.get("driving_criterion")}*. '
                 f'Verdict: **{h.get("who_looks_wrong", "").replace("_", " ")}**. {h.get("explanation", "")} {src}')
        L.append("")
    L += ["## Written vs revealed thesis (Riya's drift question, M5)", "",
          f"With one 60-point line, the written-thesis score matches the fund's invest/pass call on **{w_agree}/12** and the revealed "
          f"score on **{r_agree_simple}/12** - the same count. The difference is separation: under the **written** thesis the fund's "
          f"passes average **{wp:.0f}** and its investments **{wi:.0f}** (gap {wi-wp:.0f} points; passes sit just under or over the line, "
          f"e.g. Petalry {pet_w}). Under the **revealed** thesis passes average **{rp:.0f}** and investments **{ri:.0f}** (gap {ri-rp:.0f}). "
          "The public wording barely tells this fund's yeses from its nos; what the memos show it actually weighs does. That supports "
          "Riya's drift observation (M5) without settling Aditya's alternative (a changed applicant mix) - 12 memos cannot.", "",
          "## Honest limits", "",
          "- 12 memos is a small sample: one flipped call moves agreement by 8 points.",
          "- Memos contain the partners' read of the founder *after* a call; real applications only have a deck, so live founder scores will be less certain than here.",
          "- Ledgerly (M5, 'Kushal still thinks that was a miss') is not in the pack and has no public trace, so the one known false-pass cannot be tested.",
          "- The thesis criteria were written from these same memos. Leave-one-out removes each company's own memo, but the general lessons still come from the set: this measures consistency with the fund's reasoning, not predictive accuracy on new companies. The quarterly re-run on fresh decisions is the real test.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)
    with open("reports/batch_report.md", "w", encoding="utf-8") as f:
        f.write(batch())
    with open("reports/backtest.md", "w", encoding="utf-8") as f:
        f.write(backtest())
    print("written reports/")
