"""Web app: the partner review queue. Reading is open; every action (review, correct, book, add) needs EDIT_PASSWORD."""
import os
import re

from flask import Flask, jsonify, request, send_from_directory

import booking
import config
import feedback
import intake
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
                     "booking": (books.get(r["app_id"]) or {}).get("meeting_status")})
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
    storage.set_review(app_id, status, decision, b.get("reviewer") or "Kushal", b.get("note"), b.get("seconds"))
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
        feedback.capture(app_id, r["read"]["facts"], crit["key"], crit["score"], float(b["new"]), b.get("reason"), b.get("reviewer") or "Kushal")
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
    """New application into the pile: pasted form + deck text. Runs the full desk (~2-3 minutes)."""
    if not _auth():
        return _need_auth()
    b = request.get_json(force=True)
    name = (b.get("name") or "").strip()
    if not name or not (b.get("form") or b.get("deck")):
        return jsonify({"error": "Name and at least the form or deck text are needed."}), 400
    rec = {"id": intake.slug(name), "name": name, "batch": b.get("batch") or "manual", "form_text": b.get("form", ""),
           "deck_text": b.get("deck", "")}
    form = rec["form_text"].lower()
    rec["source"] = "warm intro" if re.search(r"warm intro|introduced by|referred by", form) else "public form"
    rec["missing_docs"] = [k for k in ("deck_text", "form_text") if not rec[k].strip()]
    read = pipeline.run_one(rec)
    return jsonify({"ok": True, "id": rec["id"], "recommendation": read.get("recommendation"), "score": read.get("score_revealed")})


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
