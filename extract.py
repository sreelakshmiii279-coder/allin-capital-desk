"""Step 2 - Extract structured facts from the founder's own documents.
Every fact carries a verbatim quote and which document it came from; code then checks the quote really is in
that document. A fact whose quote cannot be found is marked unverified (the model may have paraphrased or invented)."""
import re

import config
import llm

S = {"type": "string"}
QUOTED = {"type": "object", "properties": {"value": S, "quote": S, "doc": {"type": "string", "enum": ["deck", "form"]}},
          "required": ["value", "quote", "doc"]}

SCHEMA = {
    "type": "object",
    "properties": {
        "company": S, "one_liner": S, "website": S, "location": S, "incorporated": S,
        "sector_selected": S,
        "sector": {"type": "string", "enum": ["fintech", "deeptech", "consumer_tech", "consumer_brand", "b2b_software", "other"],
                   "description": "What the business actually is, regardless of the box the founder ticked"},
        "sub_sector": S,
        "business_model": {"type": "string", "description": "e.g. lending, payments, SaaS seats, D2C brand, marketplace, hardware, quick-commerce"},
        "stage": S, "team_size": S, "source_channel": S,
        "founders": {"type": "array", "items": {"type": "object", "properties": {
            "name": S, "role": S, "background": S, "links": {"type": "array", "items": S},
            "full_time": S, "prior_startups": S}, "required": ["name", "role", "background"]}},
        "metrics": {"type": "array", "items": {"type": "object", "properties": {
            "name": S, "value": S, "quote": S, "doc": {"type": "string", "enum": ["deck", "form"]}},
            "required": ["name", "value", "quote", "doc"]}},
        "raise_amount": QUOTED, "valuation": QUOTED, "existing_investors": S,
        "founder_stated_risks": {"type": "array", "items": S},
        "competition_claimed": S,
        "inconsistencies": {"type": "array", "items": {"type": "object", "properties": {
            "field": S, "deck_says": S, "form_says": S}, "required": ["field", "deck_says", "form_says"]},
            "description": "Any number or fact that differs between deck and form"},
        "claims_to_verify": {"type": "array", "items": {"type": "object", "properties": {
            "claim": S, "quote": S, "doc": {"type": "string", "enum": ["deck", "form"]}}, "required": ["claim", "quote", "doc"]},
            "description": "Claims an outsider could check on the public web: customers named, partnerships, awards, founder employers, licences"},
        "absent_numbers": {"type": "array", "items": S,
            "description": "Numbers an early-stage investor would expect for THIS business model that are not given anywhere "
                           "(e.g. repeat rate/cohorts for a brand, default rate for lending, retention for consumer apps, "
                           "pilot conversion for hardware, contribution margin for delivery)"},
    },
    "required": ["company", "one_liner", "sector", "business_model", "founders", "metrics", "inconsistencies",
                 "claims_to_verify", "absent_numbers"],
}

PROMPT_VERSION = "extract-v1"

PROMPT = """You extract facts from a startup's application to a pre-seed VC fund. Use ONLY the two documents below.
Rules:
- Every quote must be copied character-for-character from the named document (short, under 25 words).
- Do not infer numbers that are not written. If something is not stated, leave it out (or list it in absent_numbers).
- "sector" is what the business actually is, even if the founder ticked a different box.
- List every place where the deck and the form disagree (numbers, dates, team size, customers).

=== FORM RESPONSE ===
{form}

=== DECK TEXT ===
{deck}
"""


def _norm(s):
    return re.sub(r"[^a-z0-9%.]+", " ", (s or "").lower()).strip()


def quote_found(quote, rec, doc):
    src = _norm(rec.get(f"{doc}_text", ""))
    q = _norm(quote)
    if not q:
        return False
    if q in src:
        return True
    # tolerate PDF line-break artefacts: accept if 80% of the quote's words appear in order-insensitive window
    words = q.split()
    return len(words) >= 3 and sum(w in src for w in words) / len(words) >= 0.9


def extract(rec):
    facts = llm.ask_json(PROMPT.format(form=rec["form_text"][:20000], deck=rec["deck_text"][:20000]), SCHEMA,
                         temperature=config.EXTRACT_TEMPERATURE, prompt_version=PROMPT_VERSION)
    unverified = 0
    for m in facts.get("metrics", []) + facts.get("claims_to_verify", []):
        m["quote_verified"] = quote_found(m.get("quote"), rec, m.get("doc", "form"))
        unverified += not m["quote_verified"]
    for k in ("raise_amount", "valuation"):
        if isinstance(facts.get(k), dict):
            facts[k]["quote_verified"] = quote_found(facts[k].get("quote"), rec, facts[k].get("doc", "form"))
    facts["unverified_quotes"] = unverified
    return facts
