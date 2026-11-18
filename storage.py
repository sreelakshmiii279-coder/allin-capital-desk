"""Neon Postgres. Every table keeps history: nothing is overwritten except the 'current' pointers."""
import json
import threading

import psycopg

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
  id text PRIMARY KEY, name text NOT NULL, batch text NOT NULL, source text, record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS reads (
  id serial PRIMARY KEY, app_id text NOT NULL, read jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS reviews (
  app_id text PRIMARY KEY, status text NOT NULL, decision text, reviewer text, note text,
  review_seconds int, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS corrections (
  id serial PRIMARY KEY, app_id text NOT NULL, criterion text NOT NULL, old_score real, new_score real,
  reason text NOT NULL, tags jsonb NOT NULL, reviewer text, active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS bookings (
  app_id text PRIMARY KEY, state jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS slots (
  slot_start timestamptz PRIMARY KEY, app_id text NOT NULL, status text NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  id serial PRIMARY KEY, app_id text, kind text NOT NULL, payload jsonb, at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS backtests (
  id serial PRIMARY KEY, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
"""

_ready = False
_local = threading.local()


class _Reuse:
    """`with db() as c:` keeps working, but the connection is reused per thread instead of a new TLS handshake to Neon
    on every query (that made the queue take ~6 s)."""
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *a):
        return False


def db():
    global _ready
    import time
    conn = getattr(_local, "conn", None)
    if conn is not None and time.time() - getattr(_local, "used", 0) > 60:
        try:
            conn.execute("SELECT 1")   # Neon drops idle connections; check once after a quiet minute
        except Exception:  # noqa: BLE001
            conn = None
    _local.used = time.time()
    if conn is None or conn.closed or conn.broken:
        conn = psycopg.connect(config.DATABASE_URL, autocommit=True)
        _local.conn = conn
    if not _ready:
        conn.execute(SCHEMA)
        _ready = True
    return _Reuse(conn)


def j(x):
    return json.dumps(x, ensure_ascii=False, default=str)


def event(app_id, kind, payload=None):
    with db() as c:
        c.execute("INSERT INTO events (app_id, kind, payload) VALUES (%s,%s,%s)", (app_id, kind, j(payload or {})))


def save_application(rec):
    with db() as c:
        c.execute("""INSERT INTO applications (id, name, batch, source, record) VALUES (%s,%s,%s,%s,%s)
                     ON CONFLICT (id) DO UPDATE SET record=EXCLUDED.record, batch=EXCLUDED.batch""",
                  (rec["id"], rec["name"], rec["batch"], rec.get("source"), j(rec)))


def save_read(app_id, read):
    with db() as c:
        c.execute("INSERT INTO reads (app_id, read) VALUES (%s,%s)", (app_id, j(read)))
        c.execute("""INSERT INTO reviews (app_id, status) VALUES (%s,'pending')
                     ON CONFLICT (app_id) DO UPDATE SET status='pending', decision=NULL, updated_at=now()""", (app_id,))


def latest_reads():
    with db() as c:
        rows = c.execute("""SELECT DISTINCT ON (r.app_id) r.app_id, r.read, r.created_at, v.status, v.decision, v.reviewer,
                              v.note, a.record
                            FROM reads r JOIN applications a ON a.id=r.app_id LEFT JOIN reviews v ON v.app_id=r.app_id
                            ORDER BY r.app_id, r.id DESC""").fetchall()
    return [{"app_id": r[0], "read": r[1], "at": r[2].isoformat(), "status": r[3], "decision": r[4],
             "reviewer": r[5], "note": r[6], "record": r[7]} for r in rows]


def get_read(app_id):
    for r in latest_reads():
        if r["app_id"] == app_id:
            return r
    return None


def set_review(app_id, status, decision, reviewer, note, seconds=None):
    with db() as c:
        c.execute("""INSERT INTO reviews (app_id, status, decision, reviewer, note, review_seconds) VALUES (%s,%s,%s,%s,%s,%s)
                     ON CONFLICT (app_id) DO UPDATE SET status=EXCLUDED.status, decision=EXCLUDED.decision,
                     reviewer=EXCLUDED.reviewer, note=EXCLUDED.note, review_seconds=EXCLUDED.review_seconds, updated_at=now()""",
                  (app_id, status, decision, reviewer, note, seconds))


def add_correction(app_id, criterion, old, new, reason, tags, reviewer):
    with db() as c:
        c.execute("""INSERT INTO corrections (app_id, criterion, old_score, new_score, reason, tags, reviewer)
                     VALUES (%s,%s,%s,%s,%s,%s,%s)""", (app_id, criterion, old, new, reason, j(tags), reviewer))


def all_corrections(active_only=True):
    with db() as c:
        rows = c.execute("SELECT id, app_id, criterion, old_score, new_score, reason, tags, reviewer, created_at, active "
                         "FROM corrections " + ("WHERE active " if active_only else "") + "ORDER BY id").fetchall()
    return [{"id": r[0], "app_id": r[1], "criterion": r[2], "old": r[3], "new": r[4], "reason": r[5], "tags": r[6],
             "reviewer": r[7], "at": r[8].isoformat(), "active": r[9]} for r in rows]


def get_booking(app_id):
    with db() as c:
        r = c.execute("SELECT state FROM bookings WHERE app_id=%s", (app_id,)).fetchone()
    return r[0] if r else None


def save_booking(app_id, state):
    with db() as c:
        c.execute("""INSERT INTO bookings (app_id, state) VALUES (%s,%s)
                     ON CONFLICT (app_id) DO UPDATE SET state=EXCLUDED.state, updated_at=now()""", (app_id, j(state)))


def taken_slots():
    with db() as c:
        return {r[0].isoformat(): (r[1], r[2]) for r in c.execute("SELECT slot_start, app_id, status FROM slots")}


def hold_slot(iso, app_id, status):
    with db() as c:
        c.execute("""INSERT INTO slots (slot_start, app_id, status) VALUES (%s,%s,%s)
                     ON CONFLICT (slot_start) DO UPDATE SET status=EXCLUDED.status WHERE slots.app_id=EXCLUDED.app_id""",
                  (iso, app_id, status))


def release_slots(app_id, keep=None):
    with db() as c:
        if keep:
            c.execute("DELETE FROM slots WHERE app_id=%s AND slot_start<>%s", (app_id, keep))
        else:
            c.execute("DELETE FROM slots WHERE app_id=%s", (app_id,))


def save_backtest(result):
    with db() as c:
        c.execute("INSERT INTO backtests (result) VALUES (%s)", (j(result),))


def latest_backtest():
    with db() as c:
        r = c.execute("SELECT result, created_at FROM backtests ORDER BY id DESC LIMIT 1").fetchone()
    return {"result": r[0], "at": r[1].isoformat()} if r else None


def review_stats():
    with db() as c:
        rows = c.execute("SELECT status, decision, review_seconds FROM reviews").fetchall()
    return rows


def all_bookings():
    with db() as c:
        return {r[0]: r[1] for r in c.execute("SELECT app_id, state FROM bookings")}
