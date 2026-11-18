"""Feedback loop (S5): Act -> Signal -> Capture -> Store -> Retrieve -> Apply.

ACT      score.py produces a per-criterion read.
SIGNAL   Kushal or Riya changes a criterion score in the review queue (or changes the recommendation).
CAPTURE  the delta (old -> new), WHO, and a one-line WHY - mandatory (Partner notes M5: "When a score is corrected, Riya
         should say why in a line so the correction can be reused"). A number alone carries no meaning (S5: Raghav's
         750 -> 700 kg) - so a correction without a reason is refused.
STORE    the delta stays linked to its context tags: sector, business model, sub-sector, one-liner, the model's key
         question, criterion (S5: "never store an edit in isolation").
RETRIEVE on the next application: STRICT tag filter first (same sector or same business-model family), then rank by
         semantic similarity (Gemini embeddings) + keyword overlap. Pure semantic search alone would match "lending to
         students" with "lending to farmers" and carry the wrong lesson (S5: CEO vs CTO ~78% similar).
APPLY    the retrieved corrections are injected into the scoring prompt for that criterion, and shown on the read as
         "correction applied", so Kushal can see when an old correction is steering a new score.
Disagreement score (S5) = share of reads where a partner changed anything + mean |delta| per criterion; see report.py."""
import math
import os
import re

from google import genai

import config
import storage

_client = None
EMBED_MODEL = "gemini-embedding-001"

MODEL_FAMILIES = {
    "lending": r"lend|credit|loan|bnpl|nbfc|wage|financ",
    "payments": r"payment|upi|card|invoice|rent|settle",
    "brand": r"d2c|brand|skincare|food|jewel|beauty|millet|fmcg",
    "hardware": r"hardware|robot|drone|sensor|iot|evtol|aircraft",
    "saas": r"saas|software|seat|crm|gst|b2b",
    "density": r"delivery|quick|dark store|clinic|store|retail|kirana",
    "consumer_app": r"app|content|exam|edtech|travel|creator",
    "crypto": r"crypto|web3|token|exchange|wallet",
}


def families(text):
    return {k for k, rx in MODEL_FAMILIES.items() if re.search(rx, text or "", re.I)}


def _embed(text):
    try:
        import llm
        r = llm._get_client().models.embed_content(model=EMBED_MODEL, contents=text[:2000])
        return list(r.embeddings[0].values)
    except Exception:  # noqa: BLE001 - retrieval still works on tags + keywords
        return None


def _cos(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1)


def _words(t):
    return {w for w in re.findall(r"[a-z]{4,}", (t or "").lower())}


def context_tags(facts):
    blob = " ".join([facts.get("business_model", ""), facts.get("sub_sector", "") or "", facts.get("one_liner", "")])
    return {"sector": facts.get("sector"), "business_model": facts.get("business_model"), "sub_sector": facts.get("sub_sector"),
            "one_liner": facts.get("one_liner"), "families": sorted(families(blob)), "company": facts.get("company")}


# --- CAPTURE + STORE ---
def capture(app_id, facts, criterion, old, new, reason, reviewer):
    reason = (reason or "").strip()
    if len(reason) < 8:
        raise ValueError("A correction needs a one-line reason (M5) - otherwise it cannot be reused.")
    tags = context_tags(facts)
    tags["embedding"] = _embed(f'{tags["one_liner"]} | {tags["business_model"]} | {criterion}: {reason}')
    storage.add_correction(app_id, criterion, old, new, reason, tags, reviewer)
    storage.event(app_id, "correction", {"criterion": criterion, "old": old, "new": new, "reason": reason, "by": reviewer})


# --- RETRIEVE ---
def retrieve(facts, exclude_app_ids=(), k=4):
    tags = context_tags(facts)
    fam = set(tags["families"])
    query = f'{tags["one_liner"]} | {tags["business_model"]}'
    qvec, qwords = None, _words(query)
    hits = []
    for c in storage.all_corrections():
        if c["app_id"] in exclude_app_ids:
            continue  # leave-one-out: in the backtest a company never learns from its own correction
        ct = c["tags"] or {}
        same_sector = ct.get("sector") == tags["sector"]
        shared_fam = fam & set(ct.get("families") or [])
        if not (same_sector or shared_fam or c["criterion"] == "gate"):
            continue  # strict tag filter BEFORE similarity
        if qvec is None:
            qvec = _embed(query) or []
        sem = _cos(qvec, ct.get("embedding"))
        kw = len(qwords & _words(f'{ct.get("one_liner")} {ct.get("business_model")} {c["reason"]}')) / (len(qwords) or 1)
        score = 0.5 * sem + 0.3 * min(kw * 3, 1) + 0.2 * bool(shared_fam)
        why = []
        if same_sector:
            why.append(f'same sector ({tags["sector"]})')
        if shared_fam:
            why.append("same model family: " + ", ".join(sorted(shared_fam)))
        hits.append({**{x: c[x] for x in ("id", "app_id", "criterion", "old", "new", "reason", "reviewer", "at")},
                     "about": ct.get("company"), "match_score": round(score, 2), "matched_on": "; ".join(why) or "process rule"})
    hits.sort(key=lambda h: -h["match_score"])
    return hits[:k]


# --- APPLY ---
def as_prompt(hits):
    if not hits:
        return "No past partner corrections match this company."
    lines = ["Past partner corrections on similar companies. Apply the LESSON where it genuinely fits this company; "
             "say in the evidence when you applied one (cite it as 'correction #id'):"]
    for h in hits:
        lines.append(f'- correction #{h["id"]} ({h["reviewer"]}, on {h["about"]}; matched on {h["matched_on"]}): '
                     f'{h["criterion"]} {h["old"]} -> {h["new"]} because "{h["reason"]}"')
    return "\n".join(lines)


# Historical corrections already in the partner notes - the loop starts with them instead of empty.
SEED = [
    {"app_id": "memo-petalry", "criterion": "traction", "old": 3, "new": 1, "reviewer": "Kushal (Partner notes M1)",
     "reason": "Repeat rate missing: a missing key number should drag the score, not be skipped (Riya's 6.5 overall was too high).",
     "facts": {"company": "Petalry", "sector": "consumer_brand", "business_model": "D2C brand",
               "sub_sector": "skincare", "one_liner": "Direct-to-consumer skincare brand selling on its own site and marketplaces"}},
    {"app_id": "memo-aerodrop", "criterion": "founder", "old": 5, "new": 3, "reviewer": "Kushal (Partner notes M3)",
     "reason": "Credentials are not a business: score the evidence, not the pedigree (Riya's 7.5 leaned on the PhD).",
     "facts": {"company": "AeroDrop", "sector": "deeptech", "business_model": "hardware drone delivery",
               "sub_sector": "drones", "one_liner": "Autonomous drone delivery of medical supplies"}},
    {"app_id": "memo-aerodrop", "criterion": "path", "old": 3, "new": 1, "reviewer": "Kushal/Aditya (Partner notes M3)",
     "reason": "No signed customer and no regulator plan or milestone sequence; 'solved once the tech works' is not a path.",
     "facts": {"company": "AeroDrop", "sector": "deeptech", "business_model": "hardware drone delivery",
               "sub_sector": "drones", "one_liner": "Autonomous drone delivery of medical supplies"}},
    {"app_id": "notes-meeting-summary-co", "criterion": "gate", "old": 4, "new": 0, "reviewer": "Kushal (Partner notes M4)",
     "reason": "Overlaps portfolio company MeetRecord - check every application against the full portfolio list; hold until the portfolio founder is told.",
     "facts": {"company": "Meeting-notes startup (unnamed)", "sector": "b2b_software", "business_model": "SaaS seats",
               "sub_sector": "meeting notes / call summaries", "one_liner": "Meeting notes and call summaries"}},
]


def seed():
    if any(c["reviewer"].endswith(("M1)", "M3)", "M4)")) for c in storage.all_corrections(active_only=False)):
        return 0
    for s in SEED:
        capture(s["app_id"], s["facts"], s["criterion"], s["old"], s["new"], s["reason"], s["reviewer"])
    return len(SEED)
