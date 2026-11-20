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
import obs
import research
import score
import storage
import thesis


def prescreen(facts):
    """Cheap short circuit BEFORE research spend (S4): stage/round far outside a pre-seed cheque."""
    rc = score.raise_in_cr(facts)
    return bool((rc and rc > thesis.MAX_ROUND_CR) or re.search(r"series\s*[a-z]", (facts.get("stage") or "").lower()))


def run_one(rec, exclude_corrections=(), do_research=True, persist=True, holdout=None):
    """One application = one trace (obs.run) with a span per step. Errors carry a reason; a paused budget is reported
    as paused (the queue puts the job back), never as a silent zero."""
    t0 = time.time()
    steps = {}
    key = input_key(rec, holdout, do_research)
    if config.CACHE_READS and persist and not holdout:
        hit = cached_read(rec["id"], key)
        if hit:
            hit = dict(hit)
            hit.update({"cached": True, "cache_note": "Same application, same prompt versions, no new corrections: stored read "
                                                      "reused (no model calls, no cost).", "batch": rec.get("batch")})
            storage.save_application({k: v for k, v in rec.items()})
            storage.save_read(rec["id"], hit)
            storage.event(rec["id"], "read_cached", {"key": key[:16]})
            return hit
    with obs.run(rec["id"], kind="triage", meta={"batch": rec.get("batch"), "name": rec.get("name")}) as run_id:
        try:
            with obs.step("extract"):
                facts = extract.extract(rec)
            steps["extract"] = round(time.time() - t0, 1)
            with obs.step("conflicts"):
                confl = conflicts.check(facts, holdout=holdout)
            steps["conflicts"] = round(time.time() - t0, 1)
            short = prescreen(facts)
            with obs.step("research", short_circuit=short):
                res = research.research(rec, facts, hard_flag=short) if do_research else {"_skipped": "research off (backtest without hindsight)"}
            steps["research"] = round(time.time() - t0, 1)
            with obs.step("score"):
                read = score.score(rec, facts, res, confl, exclude_corrections=exclude_corrections, holdout=holdout)
            read.update({"facts": facts, "research": res, "timing_s": steps, "seconds": round(time.time() - t0, 1),
                         "source": rec.get("source"), "batch": rec.get("batch"), "missing_docs": rec.get("missing_docs")})
            if read["untraced_share"] > config.UNSOURCED_CLAIMS_KILL:
                read["withheld_reason"] = (f'{read["untraced_share"]:.0%} of claims could not be traced to a source '
                                           f'(kill criterion > {config.UNSOURCED_CLAIMS_KILL:.0%}): untraced claims were removed; check before trusting.')
        except obs.BudgetPaused as e:
            read = {"company": rec["name"], "recommendation": "Needs attention - paused (daily cost limit)", "paused": True,
                    "error": str(e), "score_revealed": None, "criteria": [], "flags": [], "seconds": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            read = {"company": rec["name"], "recommendation": "Needs attention - desk failed", "error": f"{type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-1500:], "score_revealed": None, "criteria": [], "flags": [],
                    "seconds": round(time.time() - t0, 1)}
        read["run_id"] = run_id
        read["cost_inr"] = run_cost(run_id)
        read["input_key"] = key
    if persist and not read.get("paused"):
        storage.save_application({k: v for k, v in rec.items()})
        storage.save_read(rec["id"], read)
        storage.event(rec["id"], "read", {"recommendation": read["recommendation"], "score": read.get("score_revealed")})
    return read


def input_key(rec, holdout=None, do_research=True):
    """Cache key: the application's text + every prompt version + model + the newest correction id.
    A new partner correction changes the key, so the feedback loop is never bypassed by the cache."""
    import hashlib
    import conflicts as _c
    try:
        newest = max((c["id"] for c in storage.all_corrections()), default=0)
    except Exception:  # noqa: BLE001
        newest = "?"
    parts = [rec.get("form_text", ""), rec.get("deck_text", ""), extract.PROMPT_VERSION, _c.PROMPT_VERSION, score.PROMPT_VERSION,
             "research-judge-v2", "search-v1", config.MODEL, str(config.SCORE_SAMPLES), str(newest), str(holdout), str(do_research)]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def cached_read(app_id, key, max_age_days=7):
    try:
        with storage.db() as c:
            r = c.execute("""SELECT read FROM reads WHERE app_id=%s AND read->>'input_key'=%s AND read->>'error' IS NULL
                             AND created_at > now() - (%s || ' days')::interval ORDER BY id DESC LIMIT 1""",
                          (app_id, key, str(max_age_days))).fetchone()
        return r[0] if r else None
    except Exception:  # noqa: BLE001
        return None


def run_cost(run_id):
    try:
        with storage.db() as c:
            return round(float(c.execute("SELECT coalesce(sum(cost_inr),0) FROM model_calls WHERE run_id=%s", (run_id,)).fetchone()[0]), 2)
    except Exception:  # noqa: BLE001
        return None


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
