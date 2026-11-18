"""Gate A - Portfolio conflict check against the FULL portfolio list, not the ones someone remembers
(Partner notes M4: "We only found it because Riya happens to know the portfolio"; Kushal: "rather get a flag on a false
alarm than miss a real conflict"). Biased toward flagging. A direct overlap sets the recommendation to HOLD until Kushal
has spoken to the portfolio founder (M4: "Default is no ... only if the founder knows and the portfolio founder is told")."""
import json
import os
import re

import config
import llm

PORTFOLIO_FILE = os.path.join(config.DATA, "research", "portfolio.json")

SCHEMA = {"type": "object", "properties": {"overlaps": {"type": "array", "items": {"type": "object", "properties": {
    "portfolio_company": {"type": "string"},
    "level": {"type": "string", "enum": ["direct", "adjacent"]},
    "why": {"type": "string", "description": "Which customer or product the two would compete for, in one sentence"},
}, "required": ["portfolio_company", "level", "why"]}}}, "required": ["overlaps"]}


def portfolio():
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def check(facts, holdout=None, passes=2):
    """Runs the comparison twice and keeps the STRICTER level per portfolio company: one run said StockSathi/SuperK was
    direct, the next said adjacent. A gate must not flip between runs, and M4 prefers the false alarm."""
    merged = {}
    for _ in range(passes):
        for o in _check_once(facts, holdout):
            k = o["portfolio_company"]
            if k not in merged or (o["level"] == "direct" and merged[k]["level"] != "direct"):
                merged[k] = o
    return sorted(merged.values(), key=lambda o: o["level"] != "direct")


def _check_once(facts, holdout=None):
    me = (holdout or facts.get("company") or "").lower().split(" (")[0]
    # The applicant itself is never its own conflict (a portfolio company re-applying, or the backtest).
    pf = [p for p in portfolio() if not (me and (me in p["name"].lower() or p["name"].lower().split(" (")[0] in me))]
    listing = "\n".join(f'- {p["name"]} ({p.get("sector", "")}): {p.get("what_it_does", "")}' for p in pf)
    app = f'{facts.get("company")}: {facts.get("one_liner")} | model: {facts.get("business_model")} | sector: {facts.get("sector")}'
    res = llm.ask_json(
        "A VC fund must not back a startup that competes with a company it already owns without telling that founder.\n"
        f"Applicant: {app}\n\nPortfolio:\n{listing}\n\n"
        "DIRECT = the same buyer, for the same job, with a substitutable product: a customer would choose one OR the other "
        "(e.g. two AI call-summary tools for sales teams; two networks supplying the same small-town kirana stores). Sharing a "
        "broad category is NOT direct (two different D2C food brands, two different SME fintechs with different products are "
        "adjacent). ADJACENT = same buyer or category, different job, or a plausible expansion path. Err on the side of flagging "
        "adjacent - a false alarm is cheap, a missed conflict is not. Return an empty list only if nothing is even adjacent.", SCHEMA, temperature=0.0)
    by_name = {p["name"].lower(): p for p in pf}
    out = []
    for o in res["overlaps"]:
        p = by_name.get(o["portfolio_company"].lower()) or next(
            (v for k, v in by_name.items() if o["portfolio_company"].lower().split(" (")[0] in k), None)
        if not p:
            continue  # model named something not on the list: ignore (no invented portfolio companies)
        o = {**o, "portfolio_company": p["name"], "portfolio_source": p.get("source_url"),
             "portfolio_confirmed": p.get("confirmed", False)}
        if o["level"] == "direct" and re.search(r"not described|unknown", p.get("what_it_does", ""), re.I):
            o["level"] = "adjacent"
            o["why"] += " (We have no description of what this portfolio company does - check by hand.)"
        if o["level"] == "direct" and not o["portfolio_confirmed"]:
            o["level"] = "adjacent"
            o["why"] += " (Portfolio membership only on an aggregator site - not confirmed, so flagged, not held.)"
        out.append(o)
    return out
