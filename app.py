"""Web app: the partner review queue. Reading is open; every action (review, correct, book, add) needs EDIT_PASSWORD."""
import os
import re

from flask import Flask, jsonify, request, send_from_directory

import booking
import config
import feedback
import intake
import jobqueue
import obs
import pipeline
import score
import storage

app = Flask(__name__, static_folder=None)
WEB = os.path.join(config.HERE, "web")


def _auth():
    return config.EDIT_PASSWORD and request.headers.get("X-Desk-Password", "") == config.EDIT_PASSWORD


def _need_auth():
    return jsonify({"error": "Password needed for this action."}), 401


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/api/queue")
def queue():
    rows, books = [], storage.all_bookings()
    for r in storage.latest_reads():
        d = r["read"]
        rows.append({"id": r["app_id"], "company": r["record"]["name"], "one_liner": d.get("one_liner"), "sector": d.get("sector"),
                     "source": d.get("source"), "recommendation": d.get("recommendation"), "merit": d.get("merit_recommendation"),
                     "score": d.get("score_revealed"), "score_written": d.get("score_written"), "drift": d.get("drift"),
                     "flags": [{"key": f["key"], "hard": f["hard"]} for f in d.get("flags", [])],
                     "two_lines": d.get("two_lines"), "status": r["status"], "decision": r["decision"],
                     "unknowns": len(d.get("unknown_criteria", [])), "untraced": d.get("claims_untraced"),
                     "claims": d.get("claims_total"), "batch": d.get("batch"), "at": r["at"], "error": d.get("error"),
                     "booking": (books.get(r["app_id"]) or {}).get("meeting_status"), "cost_inr": d.get("cost_inr"),
                     "run_id": d.get("run_id")})
    # capability ceiling, per batch: only CALL_CAP_PER_WEEK "Take the call" rows; the rest are marked over capacity
    by_batch = {}
    for row in rows:
        if (row["recommendation"] or "") == "Take the call":
            by_batch.setdefault(row["batch"], []).append(row)
    for calls in by_batch.values():
        for i, row in enumerate(sorted(calls, key=lambda x: -(x["score"] or 0))):
            if i >= config.CALL_CAP_PER_WEEK:
                row["recommendation"] = "Take the call - over this week's capacity"
    return jsonify(rows)


@app.get("/api/app/<app_id>")
def one(app_id):
    r = storage.get_read(app_id)
    if not r:
        return jsonify({"error": "not found"}), 404
    r["booking"] = storage.get_booking(app_id)
    r["corrections_on_this"] = [c for c in storage.all_corrections(active_only=False) if c["app_id"] == app_id]
    r["tools"] = booking.TOOLS
    return jsonify(r)


@app.post("/api/review/<app_id>")
def review(app_id):
    if not _auth():
        return _need_auth()
    b = request.get_json(force=True)
    decision = b.get("decision")
    if decision not in ("take_call", "pass", "hold", "accept"):
        return jsonify({"error": "bad decision"}), 400
    r = storage.get_read(app_id)
    rec = r["read"].get("recommendation", "")
    if decision == "accept":
        decision = "take_call" if rec.startswith("Take the call") else "hold" if rec.startswith("HOLD") else "pass" \
            if rec.startswith("Pass") else None
        if not decision:
            return jsonify({"error": "The desk said 'borderline' - pick Take the call, Pass or Hold yourself."}), 400
        status = "accepted"
    else:
        desk_dec = "take_call" if rec.startswith("Take the call") else "hold" if rec.startswith("HOLD") else "pass" if rec.startswith("Pass") else "borderline"
        status = "accepted" if desk_dec == decision else "overridden"
        if status == "overridden" and len((b.get("note") or "").strip()) < 8:
            return jsonify({"error": "Overriding the desk needs a one-line reason (M5)."}), 400
    storage.set_review(app_id, status, decision, b.get("reviewer") or "Riya", b.get("note"), b.get("seconds"))
    storage.event(app_id, "review", {"decision": decision, "status": status, "note": b.get("note"), "by": b.get("reviewer")})
    out = {"ok": True, "status": status}
    if decision == "take_call":
        out["booking"] = booking.start(app_id, r["read"])
    return jsonify(out)


@app.post("/api/correct/<app_id>")
def correct(app_id):
    if not _auth():
        return _need_auth()
    b = request.get_json(force=True)
    r = storage.get_read(app_id)
    crit = next((c for c in r["read"]["criteria"] if c["key"] == b.get("criterion")), None)
    if not crit:
        return jsonify({"error": "unknown criterion"}), 400
    try:
        feedback.capture(app_id, r["read"]["facts"], crit["key"], crit["score"], float(b["new"]), b.get("reason"), b.get("reviewer") or "Riya")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@app.post("/api/rescore/<app_id>")
def rescore(app_id):
    """Re-run ONLY the scoring step (facts + research cached) so the effect of new corrections is visible in ~30s."""
    if not _auth():
        return _need_auth()
    r = storage.get_read(app_id)
    old = r["read"]
    rec = r["record"]
    new = score.score(rec, old["facts"], old["research"], old.get("conflicts", []))
    for k in ("facts", "research", "source", "batch", "missing_docs", "timing_s", "seconds"):
        new[k] = old.get(k)
    new["previous_score"] = old.get("score_revealed")
    new["previous_recommendation"] = old.get("recommendation")
    storage.save_read(app_id, new)
    storage.event(app_id, "rescore", {"from": old.get("score_revealed"), "to": new["score_revealed"]})
    return jsonify({"ok": True, "from": old.get("score_revealed"), "to": new["score_revealed"], "recommendation": new["recommendation"]})


@app.post("/api/booking/<app_id>/send")
def send(app_id):
    """Riya edits the drafted founder email and sends it from the dashboard (Case 04)."""
    if not _auth():
        return _need_auth()
    b = request.get_json(force=True)
    r = storage.get_read(app_id)
    return jsonify(booking.send_draft(app_id, b.get("subject", ""), b.get("body", ""), b.get("editor") or "Riya",
                                      b.get("note"), r["read"] if r else {}))


@app.get("/api/news")
def news_pulse():
    """What's happening: Google News for the fund's focus sectors + Indian startup funding (cached 12 h, no model cost)."""
    import news
    return jsonify({"topics": news.pulse(), "source": "Google News (India edition), last 7 days"})


@app.post("/api/applicant/<app_id>/erase")
def erase(app_id):
    """DPDP / GDPR erasure request: delete everything about one applicant. Needs the ADMIN password (Kushal), not the
    everyday desk password - least privilege for an irreversible action."""
    if not (config.ADMIN_PASSWORD and request.headers.get("X-Admin-Password", "") == config.ADMIN_PASSWORD):
        return jsonify({"error": "Erasure needs the admin password."}), 401
    b = request.get_json(silent=True) or {}
    if b.get("confirm") != app_id:
        return jsonify({"error": "Confirm by sending the application id."}), 400
    return jsonify({"ok": True, "deleted": storage.erase_applicant(app_id)})


@app.post("/api/chat")
def chat_endpoint():
    """Desk assistant: read-only answers grounded in the desk's data (chat.py). Password-gated: each question costs a call."""
    if not _auth():
        return _need_auth()
    import chat
    b = request.get_json(force=True)
    try:
        return jsonify(chat.answer(b.get("question"), b.get("history"), b.get("app_id")))
    except obs.BudgetPaused as e:
        return jsonify({"answer": str(e), "sources": [], "not_in_data": False, "refused_action": False})


@app.post("/api/intake")
def intake_batch():
    """The pile arrives: [{name, form, deck}] -> one queued job each. Returns at once; workers process in turn."""
    if not _auth():
        return _need_auth()
    b = request.get_json(force=True)
    apps = b.get("applications") or []
    if not apps:
        return jsonify({"error": "No applications."}), 400
    # L8: an open form is an open door - limits per request and per minute; extras are told to retry, never silently dropped
    if len(apps) > config.INTAKE_MAX_PER_REQUEST:
        return jsonify({"error": f"At most {config.INTAKE_MAX_PER_REQUEST} applications per request - split the upload."}), 413
    with storage.db() as c:
        last_min = c.execute("SELECT count(*) FROM jobs WHERE queued_at > now() - interval '1 minute'").fetchone()[0]
    if last_min + len(apps) > config.INTAKE_MAX_PER_MINUTE:
        return jsonify({"error": f"Intake limit: {config.INTAKE_MAX_PER_MINUTE} applications a minute "
                                 f"({last_min} already this minute). Nothing was queued - retry in a minute."}), 429, {"Retry-After": "60"}
    ids = jobqueue.enqueue(apps, b.get("batch") or "intake")
    return jsonify({"ok": True, "job_ids": ids, "counts": jobqueue.counts(b.get("batch") or "intake")})


@app.post("/api/worker/tick")
def worker_tick():
    """Process the queue for up to ~4 minutes, then check booking reply windows. Called by the dashboard's
    'Process queue' button, a cron (Authorization: Bearer CRON_SECRET), or `python jobqueue.py` locally."""
    secret = os.environ.get("CRON_SECRET")
    cron_ok = bool(secret) and request.headers.get("Authorization") == f"Bearer {secret}"
    if not (_auth() or cron_ok):
        return _need_auth()
    out = jobqueue.work(deadline_s=int(request.args.get("deadline", 250)))
    ticked = []
    for app_id, st in storage.all_bookings().items():
        if st.get("meeting_status") == "pending_confirmation":
            r = storage.get_read(app_id)
            new = booking.tick(app_id, r["read"] if r else {})
            if new and new.get("reply_round") != st.get("reply_round"):
                ticked.append(app_id)
    out["booking_followups"] = ticked
    out["purged_after_retention"] = storage.purge_expired(config.RETENTION_DAYS)
    out["counts"] = jobqueue.counts()
    out["paused"] = obs.is_paused()
    return jsonify(out)


@app.get("/api/jobs")
def jobs_list():
    batch = request.args.get("batch")
    return jsonify({"counts": jobqueue.counts(batch), "jobs": jobqueue.jobs(batch)})


@app.get("/api/cost")
def cost():
    """Cost of every model call, totalled by application, day, week and month (Case 04 task 5)."""
    ist = "(at AT TIME ZONE 'Asia/Kolkata')"
    with storage.db() as c:
        def q(sql):
            return c.execute(sql).fetchall()
        by_day = q(f"SELECT {ist}::date d, sum(cost_inr), count(*), sum(searches) FROM model_calls GROUP BY 1 ORDER BY 1 DESC LIMIT 31")
        by_week = q(f"SELECT date_trunc('week', {ist})::date w, sum(cost_inr), count(*) FROM model_calls GROUP BY 1 ORDER BY 1 DESC LIMIT 12")
        by_month = q(f"SELECT to_char({ist}, 'YYYY-MM') m, sum(cost_inr), count(*) FROM model_calls GROUP BY 1 ORDER BY 1 DESC LIMIT 12")
        by_app = q("SELECT app_id, sum(cost_inr), count(*), count(DISTINCT run_id), max(at) FROM model_calls WHERE app_id IS NOT NULL "
                   "GROUP BY 1 ORDER BY 5 DESC LIMIT 200")
        by_step = q("SELECT coalesce(step,'-'), kind, sum(cost_inr), count(*), avg(latency_ms) FROM model_calls GROUP BY 1,2 ORDER BY 3 DESC")
        per_run = q("SELECT avg(t) FROM (SELECT run_id, sum(cost_inr) t FROM model_calls WHERE run_id IS NOT NULL "
                    "GROUP BY run_id HAVING count(*) > 3) x")[0][0]
        via = q("SELECT via, count(*), sum(retries) FROM model_calls GROUP BY 1")

    def f(v):
        return round(float(v or 0), 2)
    today = obs.spend_today()
    return jsonify({
        "today_inr": f(today), "limit_inr": config.DAILY_COST_LIMIT_INR, "paused": today >= config.DAILY_COST_LIMIT_INR,
        "avg_per_application_inr": f(per_run), "projection_100_apps_inr": f((per_run or 0) * 100),
        "prices": {"in_per_m_usd": config.PRICE_IN_PER_M, "out_per_m_usd": config.PRICE_OUT_PER_M,
                   "search_per_call_usd": config.PRICE_SEARCH_PER_CALL, "usd_inr": config.USD_INR,
                   "note": "Google Gemini API published prices, read 20 Nov 2026 (aistudio.google.com/docs/pricing). 3.5 Flash is no longer listed, so it is priced conservatively at 3.8 Flash rates; search is per query, 5,000 free a month not deducted."},
        "by_day": [{"day": str(r[0]), "inr": f(r[1]), "calls": r[2], "searches": r[3]} for r in by_day],
        "by_week": [{"week": str(r[0]), "inr": f(r[1]), "calls": r[2]} for r in by_week],
        "by_month": [{"month": r[0], "inr": f(r[1]), "calls": r[2]} for r in by_month],
        "by_application": [{"app_id": r[0], "inr": f(r[1]), "calls": r[2], "runs": r[3], "last": r[4].isoformat()} for r in by_app],
        "by_step": [{"step": r[0], "kind": r[1], "inr": f(r[2]), "calls": r[3], "avg_ms": int(r[4] or 0)} for r in by_step],
        "via": [{"via": r[0], "calls": r[1], "retries": int(r[2] or 0)} for r in via]})


@app.get("/api/run/<run_id>")
def run_trace(run_id):
    """Open one application's run: every step and model call, with prompt version, tokens, cost and errors."""
    with storage.db() as c:
        r = c.execute("SELECT run_id, app_id, kind, meta, status, spans, started_at, ended_at FROM runs WHERE run_id=%s",
                      (run_id,)).fetchone()
        calls = c.execute("SELECT at, step, kind, model, prompt_version, in_tok, out_tok, searches, cost_inr, latency_ms, status, "
                          "error, via, retries FROM model_calls WHERE run_id=%s ORDER BY at", (run_id,)).fetchall()
    if not r:
        return jsonify({"error": "not found"}), 404
    keys = ["at", "step", "kind", "model", "prompt_version", "in_tok", "out_tok", "searches", "cost_inr", "latency_ms",
            "status", "error", "via", "retries"]
    return jsonify({"run_id": r[0], "app_id": r[1], "kind": r[2], "meta": r[3], "status": r[4], "spans": r[5],
                    "started_at": r[6].isoformat(), "ended_at": r[7].isoformat() if r[7] else None,
                    "calls": [dict(zip(keys, [x.isoformat() if hasattr(x, "isoformat") else x for x in row])) for row in calls],
                    "total_inr": round(sum(float(x[8] or 0) for x in calls), 2), "langfuse_url": obs.langfuse_url(r[0])})


@app.get("/api/setup")
def setup():
    return jsonify({"env": config.DESK_ENV, "gateway": "cloudflare" if config.CF_GATEWAY_URL else
                    ("portkey" if config.PORTKEY_API_KEY else "direct"), "portkey": bool(config.PORTKEY_API_KEY), "langfuse": bool(config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY),
                    "langfuse_host": config.LANGFUSE_HOST, "resend": bool(config.RESEND_API_KEY), "model": config.MODEL,
                    "daily_limit_inr": config.DAILY_COST_LIMIT_INR, "workers": config.QUEUE_WORKERS})


@app.post("/api/booking/<app_id>/reply")
def reply(app_id):
    if not _auth():
        return _need_auth()
    r = storage.get_read(app_id)
    return jsonify(booking.on_reply(app_id, request.get_json(force=True).get("text", ""), r["read"]))


@app.post("/api/booking/<app_id>/noreply")
def noreply(app_id):
    if not _auth():
        return _need_auth()
    r = storage.get_read(app_id)
    return jsonify(booking.no_reply(app_id, r["read"]))


@app.post("/api/add")
def add():
    """One pasted application goes into the same queue as everything else."""
    if not _auth():
        return _need_auth()
    b = request.get_json(force=True)
    ids = jobqueue.enqueue([{"name": b.get("name"), "form": b.get("form", ""), "deck": b.get("deck", "")}], b.get("batch") or "manual")
    return jsonify({"ok": True, "job_ids": ids, "counts": jobqueue.counts()})


@app.get("/api/backtest")
def backtest():
    return jsonify(storage.latest_backtest() or {})


@app.get("/api/feedback")
def fb():
    return jsonify(storage.all_corrections(active_only=False))


@app.get("/api/stats")
def stats():
    rows = storage.review_stats()
    reviewed = [r for r in rows if r[0] in ("accepted", "overridden")]
    overrides = [r for r in rows if r[0] == "overridden"]
    secs = [r[2] for r in reviewed if r[2]]
    corr = storage.all_corrections()
    reads = storage.latest_reads()
    claims = sum((r["read"].get("claims_total") or 0) for r in reads)
    untr = sum((r["read"].get("claims_untraced") or 0) for r in reads)
    with storage.db() as c:
        booked = c.execute("SELECT count(*) FROM slots WHERE status='booked'").fetchone()[0]
    return jsonify({
        "applications": len(rows), "reviewed": len(reviewed), "overridden": len(overrides),
        "override_rate": round(len(overrides) / len(reviewed), 2) if reviewed else None,
        "avg_review_min": round(sum(secs) / len(secs) / 60, 1) if secs else None,
        "corrections": len(corr), "mean_abs_delta": round(sum(abs((c["new"] or 0) - (c["old"] or 0)) for c in corr) / len(corr), 2) if corr else None,
        "untraced_share": round(untr / claims, 3) if claims else None, "calls_booked": booked,
        "kill": {"override_rate": config.OVERRIDE_RATE_KILL, "untraced": config.UNSOURCED_CLAIMS_KILL,
                 "review_min": config.REVIEW_MINUTES_KILL, "backtest_min": config.BACKTEST_MIN_AGREEMENT},
        "capacity": config.CALL_CAP_PER_WEEK, "baseline_min_per_app": 30})


@app.post("/api/eval/<name>")
def eval_endpoint(name):
    """Fixed-input access to each decision, for the eval harness (L7). Password-gated: these calls cost model tokens.
    Nothing here writes to the real queue, sends a real email or books a real slot."""
    if config.IS_LIVE:
        # least privilege + test/live separation (L8): the test surface does not exist on the live site
        return jsonify({"error": "Eval endpoints are disabled on the live site. Run evals against the test environment."}), 404
    if not _auth():
        return _need_auth()
    import evalkit
    fn = evalkit.HANDLERS.get(name)
    if not fn:
        return jsonify({"error": f"unknown eval '{name}'"}), 404
    try:
        return jsonify(fn(request.get_json(force=True)))
    except Exception as e:  # noqa: BLE001 - the harness must see the failure, with its type
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@app.get("/api/doc/<name>")
def doc(name):
    files = {"design": "DESIGN.md", "trust": "reports/trust_contract.md", "thesis": "data/research/thesis_research.md",
             "backtest": "reports/backtest.md", "run": "reports/batch_report.md"}
    if name not in files or not os.path.exists(os.path.join(config.HERE, files[name])):
        return jsonify({"error": "not found"}), 404
    with open(os.path.join(config.HERE, files[name]), encoding="utf-8") as f:
        return jsonify({"markdown": f.read()})


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5057)), debug=False, threaded=True)
