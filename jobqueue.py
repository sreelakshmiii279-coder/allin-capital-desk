"""The intake queue (Case 04 task 2): on announcement day ~100 applications arrive at once. Each one becomes a job in Neon.
Workers claim jobs with FOR UPDATE SKIP LOCKED, so two workers never take the same job, and the extras wait their turn.

Every job ends in exactly one visible state - nothing disappears:
  queued           waiting its turn (or put back: paused by the daily cost limit / a transient failure)
  running          being processed (reclaimed if stuck longer than JOB_STUCK_MINUTES)
  done             read is in the review queue
  needs_attention  with a reason (bad input, failed twice, stuck twice) - Riya sees it in the queue"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import config
import intake
import pipeline
import storage


def _validate(app):
    name = (app.get("name") or "").strip()
    form, deck = (app.get("form") or "").strip(), (app.get("deck") or "").strip()
    if not name:
        return "No company name."
    if len(form) + len(deck) < 200:
        return "Form and deck together are under 200 characters - nothing to assess."
    if len(form) + len(deck) > 400_000:
        return "Form + deck over 400,000 characters - likely a bad export; please re-upload."
    return None


def enqueue(apps, batch):
    """apps: [{name, form, deck, source?}]. Returns the job ids. Invalid inputs are queued as needs_attention immediately
    (with the reason) so they still show up - they do not vanish."""
    ids = []
    with storage.db() as c:
        for a in apps:
            app_id = intake.slug(a.get("name") or f"unnamed-{time.time_ns()}")
            problem = _validate(a)
            status = "needs_attention" if problem else "queued"
            r = c.execute("""INSERT INTO jobs (app_id, name, batch, payload, status, reason) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                          (app_id, a.get("name") or "(no name)", batch, json.dumps(a), status, problem)).fetchone()
            ids.append(r[0])
    return ids


def reclaim_stuck():
    with storage.db() as c:
        c.execute("""UPDATE jobs SET status = CASE WHEN attempts >= %s THEN 'needs_attention' ELSE 'queued' END,
                       reason = CASE WHEN attempts >= %s THEN 'Stuck while running twice (timeout) - check the run trace'
                                     ELSE 'Reclaimed after a stuck run' END
                     WHERE status='running' AND started_at < now() - (%s || ' minutes')::interval""",
                  (config.JOB_MAX_ATTEMPTS, config.JOB_MAX_ATTEMPTS, str(config.JOB_STUCK_MINUTES)))


def claim(n):
    with storage.db() as c:
        rows = c.execute("""UPDATE jobs SET status='running', started_at=now(), attempts=attempts+1
                            WHERE id IN (SELECT id FROM jobs WHERE status='queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT %s)
                            RETURNING id, app_id, name, batch, payload, attempts""", (n,)).fetchall()
    return [{"id": r[0], "app_id": r[1], "name": r[2], "batch": r[3], "payload": r[4], "attempts": r[5]} for r in rows]


def _finish(job_id, status, reason=None, run_id=None):
    with storage.db() as c:
        c.execute("UPDATE jobs SET status=%s, reason=%s, run_id=%s, finished_at=CASE WHEN %s IN ('done','needs_attention') THEN now() END WHERE id=%s",
                  (status, reason, run_id, status, job_id))


def process(job):
    p = job["payload"]
    rec = {"id": job["app_id"], "name": job["name"], "batch": job["batch"], "form_text": p.get("form", ""),
           "deck_text": p.get("deck", ""), "source": p.get("source") or "public form"}
    rec["missing_docs"] = [k for k in ("deck_text", "form_text") if not rec[k].strip()]
    try:
        read = pipeline.run_one(rec)
    except Exception as e:  # noqa: BLE001 - run_one already catches; this is the last line of defence
        read = {"error": f"{type(e).__name__}: {e}"}
    if read.get("paused"):
        _finish(job["id"], "queued", "Paused: daily cost limit reached - will resume", read.get("run_id"))
        with storage.db() as c:
            c.execute("UPDATE jobs SET attempts=attempts-1 WHERE id=%s", (job["id"],))   # a pause is not a failed attempt
        return "paused"
    if read.get("error"):
        if job["attempts"] < config.JOB_MAX_ATTEMPTS:
            _finish(job["id"], "queued", f"Retrying after: {read['error'][:200]}", read.get("run_id"))
            return "retry"
        _finish(job["id"], "needs_attention", f"Failed twice: {read['error'][:250]}", read.get("run_id"))
        return "needs_attention"
    _finish(job["id"], "done", None, read.get("run_id"))
    return "done"


def work(deadline_s=240, workers=None):
    """Process queued jobs until the queue is empty or the deadline passes (Vercel functions stop at 300 s).
    Starts a new job only if it can plausibly finish before the deadline."""
    workers = workers or config.QUEUE_WORKERS
    reclaim_stuck()
    t0, results = time.time(), []
    with ThreadPoolExecutor(workers) as ex:
        while time.time() - t0 < deadline_s - 170:   # a triage takes ~150 s; don't start one we can't finish
            jobs = claim(workers)
            if not jobs:
                break
            results += list(ex.map(process, jobs))
    return {"processed": len(results), "outcomes": {k: results.count(k) for k in set(results)}, "seconds": round(time.time() - t0)}


def counts(batch=None):
    with storage.db() as c:
        q = "SELECT status, count(*) FROM jobs" + (" WHERE batch=%s" if batch else "") + " GROUP BY status"
        rows = c.execute(q, (batch,) if batch else ()).fetchall()
    return {r[0]: r[1] for r in rows}


def jobs(batch=None, limit=200):
    with storage.db() as c:
        q = ("SELECT id, app_id, name, batch, status, attempts, reason, run_id, queued_at, started_at, finished_at FROM jobs"
             + (" WHERE batch=%s" if batch else "") + " ORDER BY id DESC LIMIT %s")
        rows = c.execute(q, ((batch, limit) if batch else (limit,))).fetchall()
    keys = ["id", "app_id", "name", "batch", "status", "attempts", "reason", "run_id", "queued_at", "started_at", "finished_at"]
    return [dict(zip(keys, [x.isoformat() if hasattr(x, "isoformat") else x for x in r])) for r in rows]


if __name__ == "__main__":
    # local worker: python jobqueue.py  (loops until the queue is empty)
    while True:
        r = work(deadline_s=10_000)
        print(r, counts())
        if not r["processed"]:
            break
