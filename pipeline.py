"""The whole desk for one weekly batch. Each step is its own file (components map, DESIGN.md section 3).
    intake -> extract -> [A] conflict check -> pre-screen -> [C] research loop -> score (+ [D] corrections) -> review queue
Failures carry a reason and become 'needs human', never a silent zero (S6: permanent vs transient errors)."""
import re
import time
import traceback

import conflicts
import config
import extract
import intake
import research
import score
import storage
import thesis


def prescreen(facts):
    """Cheap short circuit BEFORE research spend (S4): stage/round far outside a pre-seed cheque."""
    rc = score.raise_in_cr(facts)
    return bool((rc and rc > thesis.MAX_ROUND_CR) or re.search(r"series\s*[a-z]", (facts.get("stage") or "").lower()))


def run_one(rec, exclude_corrections=(), do_research=True, persist=True, holdout=None):
    t0 = time.time()
    steps = {}
    try:
        facts = extract.extract(rec); steps["extract"] = round(time.time() - t0, 1)
        confl = conflicts.check(facts, holdout=holdout); steps["conflicts"] = round(time.time() - t0, 1)
        short = prescreen(facts)
        res = research.research(rec, facts, hard_flag=short) if do_research else {"_skipped": "research off (backtest without hindsight)"}
        steps["research"] = round(time.time() - t0, 1)
        read = score.score(rec, facts, res, confl, exclude_corrections=exclude_corrections, holdout=holdout)
        read.update({"facts": facts, "research": res, "timing_s": steps, "seconds": round(time.time() - t0, 1),
                     "source": rec.get("source"), "batch": rec.get("batch"), "missing_docs": rec.get("missing_docs")})
        if read["untraced_share"] > config.UNSOURCED_CLAIMS_KILL:
            read["withheld_reason"] = (f'{read["untraced_share"]:.0%} of claims could not be traced to a source '
                                       f'(kill criterion > {config.UNSOURCED_CLAIMS_KILL:.0%}): untraced claims were removed; check before trusting.')
    except Exception as e:  # noqa: BLE001
        read = {"company": rec["name"], "recommendation": "Needs human - desk failed", "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-1500:], "score_revealed": None, "criteria": [], "flags": [], "seconds": round(time.time() - t0, 1)}
    if persist:
        storage.save_application({k: v for k, v in rec.items()})
        storage.save_read(rec["id"], read)
        storage.event(rec["id"], "read", {"recommendation": read["recommendation"], "score": read.get("score_revealed")})
    return read


def apply_ceiling(reads):
    """Capability ceiling (S1): never more 'Take the call' than Kushal's Tue/Thu slots allow."""
    calls = sorted([r for r in reads if r.get("recommendation") == "Take the call"], key=lambda r: -(r.get("score_revealed") or 0))
    for i, r in enumerate(calls):
        r["call_rank"] = i + 1
        if i >= config.CALL_CAP_PER_WEEK:
            r["recommendation"] = "Take the call - over this week's capacity"
    return reads


def run_batch(folder=None, batch="2026-W47", only=None, workers=4):
    from concurrent.futures import ThreadPoolExecutor
    recs = [r for r in intake.load_batch(folder, batch) if not only or r["id"] in only]
    with ThreadPoolExecutor(workers) as ex:
        reads = list(ex.map(lambda r: run_one(r, persist=False), recs))
    reads = apply_ceiling(reads)
    for rec, read in zip(recs, reads):
        storage.save_application(rec)
        storage.save_read(rec["id"], read)
        storage.event(rec["id"], "read", {"recommendation": read["recommendation"], "score": read.get("score_revealed")})
    return reads
