"""Operate it and know what it costs (Case 04, tasks 4 and 5).

Every model call goes through llm.py, which reports here. For each call we record: application, run, step, prompt version,
model, tokens, search calls, cost in INR, latency, status, and whether it went through Portkey. Records go to Neon
(`model_calls`, `runs`) so the cost page and the run inspector always work, and - when LANGFUSE keys are set - to Langfuse
as an OpenTelemetry trace (the legacy /api/public/ingestion endpoint was sunset on Langfuse Cloud on 2026-11-16).

Daily limit: before every call, today's spend (IST) is checked against DAILY_COST_LIMIT_INR. Past it, the desk pauses
(every further call raises BudgetPaused, applications become "needs attention: daily cost limit") and one alert email
goes to TO_ADDRESS that day."""
import base64
import contextlib
import datetime as dt
import json
import os
import secrets
import threading
import time

import requests

import config

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_ctx = threading.local()
_lock = threading.Lock()
_spend_cache = {"day": None, "inr": 0.0, "at": 0}
_spans = {}          # run_id -> list of finished spans (for Langfuse export)


class BudgetPaused(RuntimeError):
    """Permanent for today: do not retry."""


# ---------------- context ----------------
def current():
    return {"app_id": getattr(_ctx, "app_id", None), "run_id": getattr(_ctx, "run_id", None),
            "step": getattr(_ctx, "step", None), "span_id": getattr(_ctx, "span_id", None)}


def _set(**kw):
    for k, v in kw.items():
        setattr(_ctx, k, v)


def carry(fn):
    """Wrap a function so it runs with the caller's context inside a thread pool."""
    snap = current()

    def run(*a, **k):
        old = current()
        _set(**snap)
        try:
            return fn(*a, **k)
        finally:
            _set(**old)
    return run


def _now_ns():
    return time.time_ns()


def _hex(n):
    return secrets.token_hex(n)


@contextlib.contextmanager
def run(app_id, kind="triage", meta=None):
    """One application's pass through the desk = one trace."""
    run_id = _hex(16)
    old = current()
    _set(app_id=app_id, run_id=run_id, step=kind, span_id=_hex(8))
    root = {"spanId": _ctx.span_id, "parent": None, "name": f"{kind}:{app_id}", "start": _now_ns(),
            "attrs": {"langfuse.trace.name": f"{kind}:{app_id}", "langfuse.observation.type": "span",
                      "langfuse.trace.metadata.app_id": app_id, **{f"langfuse.trace.metadata.{k}": str(v) for k, v in (meta or {}).items()}}}
    status = "ok"
    _db_run_start(run_id, app_id, kind, meta)
    try:
        yield run_id
    except Exception as e:
        status = f"error: {type(e).__name__}: {e}"[:300]
        raise
    finally:
        root["end"], root["status"] = _now_ns(), status
        _record_span(run_id, root)
        _db_run_end(run_id, status)
        _export(run_id)
        _set(**old)


@contextlib.contextmanager
def step(name, **attrs):
    if not getattr(_ctx, "run_id", None):
        yield
        return
    parent, run_id = _ctx.span_id, _ctx.run_id
    sid = _hex(8)
    old_step, old_span = _ctx.step, _ctx.span_id
    _set(step=name, span_id=sid)
    sp = {"spanId": sid, "parent": parent, "name": name, "start": _now_ns(),
          "attrs": {"langfuse.observation.type": "span", **{f"langfuse.observation.metadata.{k}": str(v) for k, v in attrs.items()}}}
    status = "ok"
    try:
        yield
    except Exception as e:
        status = f"error: {type(e).__name__}: {e}"[:300]
        raise
    finally:
        sp["end"], sp["status"] = _now_ns(), status
        _record_span(run_id, sp)
        _set(step=old_step, span_id=old_span)


# ---------------- cost ----------------
def cost_inr(kind, in_tok, out_tok, searches=0):
    if kind == "embed":
        usd = in_tok / 1e6 * config.PRICE_EMBED_PER_M
    else:
        usd = in_tok / 1e6 * config.PRICE_IN_PER_M + out_tok / 1e6 * config.PRICE_OUT_PER_M
    usd += searches * config.PRICE_SEARCH_PER_CALL
    return round(usd * config.USD_INR, 4)


def spend_today():
    day = dt.datetime.now(IST).date().isoformat()
    with _lock:
        if _spend_cache["day"] == day and time.time() - _spend_cache["at"] < 20:
            return _spend_cache["inr"]
    import storage
    try:
        with storage.db() as c:
            v = c.execute("SELECT coalesce(sum(cost_inr),0) FROM model_calls WHERE (at AT TIME ZONE 'Asia/Kolkata')::date = %s::date",
                          (day,)).fetchone()[0]
    except Exception:  # noqa: BLE001 - if we cannot read spend, do not block work; the record step will show the gap
        return _spend_cache["inr"]
    with _lock:
        _spend_cache.update(day=day, inr=float(v), at=time.time())
    return float(v)


def is_paused():
    return spend_today() >= config.DAILY_COST_LIMIT_INR


def guard():
    """Called before every model call."""
    spent = spend_today()
    if spent >= config.DAILY_COST_LIMIT_INR:
        _alert_once(spent)
        raise BudgetPaused(f"Daily cost limit reached: INR {spent:.0f} of INR {config.DAILY_COST_LIMIT_INR:.0f}. "
                           "The desk is paused until midnight IST or until the limit is raised.")


def _alert_once(spent):
    import storage
    day = dt.datetime.now(IST).date().isoformat()
    try:
        with storage.db() as c:
            if c.execute("SELECT 1 FROM events WHERE kind='cost_alert' AND payload->>'day'=%s", (day,)).fetchone():
                return
            c.execute("INSERT INTO events (kind, payload) VALUES ('cost_alert', %s)", (json.dumps({"day": day, "spent": spent}),))
        if config.RESEND_API_KEY and config.TO_ADDRESS:
            requests.post("https://api.resend.com/emails", timeout=20, headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                          json={"from": config.RESEND_FROM, "to": [config.TO_ADDRESS],
                                "subject": f"[All In Desk] Paused: daily cost limit reached (INR {spent:.0f})",
                                "html": f"<p>The triage desk spent INR {spent:.0f} today, past the limit of INR "
                                        f"{config.DAILY_COST_LIMIT_INR:.0f}. New model calls are paused until midnight IST. "
                                        "Applications waiting are kept in the queue, nothing is lost.</p>"})
    except Exception:  # noqa: BLE001
        pass


# ---------------- record one model call ----------------
def record_call(kind, model, prompt_version, in_tok, out_tok, searches, latency_ms, status, error=None, via="direct",
                input_preview=None, output_preview=None, retries=0):
    c = current()
    inr = cost_inr(kind, in_tok or 0, out_tok or 0, searches or 0)
    row = (c["app_id"], c["run_id"], c["step"], kind, model, prompt_version, in_tok or 0, out_tok or 0, searches or 0, inr,
           int(latency_ms), status, (error or "")[:300], via, retries)
    import storage
    try:
        with storage.db() as db:
            db.execute("""INSERT INTO model_calls (app_id, run_id, step, kind, model, prompt_version, in_tok, out_tok, searches,
                          cost_inr, latency_ms, status, error, via, retries) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", row)
    except Exception:  # noqa: BLE001 - never fail the work because the meter failed
        pass
    with _lock:
        _spend_cache["inr"] += inr
    if c["run_id"]:
        end = _now_ns()
        _record_span(c["run_id"], {
            "spanId": _hex(8), "parent": c["span_id"], "name": f"{kind}:{c['step']}", "start": end - int(latency_ms * 1e6), "end": end,
            "status": "ok" if status == "ok" else f"error: {error}",
            "attrs": {"langfuse.observation.type": "generation", "langfuse.observation.model.name": model,
                      "gen_ai.request.model": model, "gen_ai.usage.input_tokens": in_tok or 0,
                      "gen_ai.usage.output_tokens": out_tok or 0,
                      "langfuse.observation.usage_details": json.dumps({"input": in_tok or 0, "output": out_tok or 0}),
                      "langfuse.observation.cost_details": json.dumps({"total": round(inr / config.USD_INR, 6)}),
                      "langfuse.observation.prompt.version": prompt_version or "", "langfuse.version": prompt_version or "",
                      "langfuse.observation.metadata.via": via, "langfuse.observation.metadata.cost_inr": inr,
                      "langfuse.observation.metadata.searches": searches or 0, "langfuse.observation.metadata.retries": retries,
                      "langfuse.observation.input": (input_preview or "")[:4000],
                      "langfuse.observation.output": (output_preview or "")[:4000]}})
    return inr


# ---------------- run records + Langfuse export ----------------
def _db_run_start(run_id, app_id, kind, meta):
    import storage
    try:
        with storage.db() as c:
            c.execute("INSERT INTO runs (run_id, app_id, kind, meta) VALUES (%s,%s,%s,%s)", (run_id, app_id, kind, json.dumps(meta or {})))
    except Exception:  # noqa: BLE001
        pass


def _db_run_end(run_id, status):
    import storage
    spans = _spans.get(run_id, [])
    try:
        with storage.db() as c:
            c.execute("UPDATE runs SET ended_at=now(), status=%s, spans=%s WHERE run_id=%s",
                      (status, json.dumps([{k: v for k, v in s.items() if k != "attrs"} | {"type": s["attrs"].get("langfuse.observation.type"),
                                            "model": s["attrs"].get("gen_ai.request.model"),
                                            "cost_inr": s["attrs"].get("langfuse.observation.metadata.cost_inr")} for s in spans]), run_id))
    except Exception:  # noqa: BLE001
        pass


def _record_span(run_id, span):
    with _lock:
        _spans.setdefault(run_id, []).append(span)


def _attr(k, v):
    if isinstance(v, bool):
        return {"key": k, "value": {"boolValue": v}}
    if isinstance(v, int):
        return {"key": k, "value": {"intValue": str(v)}}
    if isinstance(v, float):
        return {"key": k, "value": {"doubleValue": v}}
    return {"key": k, "value": {"stringValue": str(v)}}


def _export(run_id):
    with _lock:
        spans = _spans.pop(run_id, [])
    if not (config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY) or not spans:
        return None
    body = {"resourceSpans": [{"resource": {"attributes": [_attr("service.name", "allin-desk")]},
                               "scopeSpans": [{"scope": {"name": "allin-desk.obs"}, "spans": [{
                                   "traceId": run_id, "spanId": s["spanId"], **({"parentSpanId": s["parent"]} if s["parent"] else {}),
                                   "name": s["name"], "kind": 1, "startTimeUnixNano": str(s["start"]), "endTimeUnixNano": str(s["end"]),
                                   "attributes": [_attr(k, v) for k, v in s["attrs"].items()],
                                   "status": {"code": 1 if s.get("status") == "ok" else 2, "message": "" if s.get("status") == "ok" else s.get("status", "")}}
                                   for s in spans]}]}]}
    auth = base64.b64encode(f"{config.LANGFUSE_PUBLIC_KEY}:{config.LANGFUSE_SECRET_KEY}".encode()).decode()
    try:
        r = requests.post(config.LANGFUSE_HOST.rstrip("/") + "/api/public/otel/v1/traces", json=body, timeout=15,
                          headers={"Authorization": f"Basic {auth}", "x-langfuse-ingestion-version": "4"})
        return r.status_code
    except requests.RequestException:
        return None


def langfuse_url(run_id):
    if not config.LANGFUSE_PUBLIC_KEY:
        return None
    return f"{config.LANGFUSE_HOST.rstrip('/')}/trace/{run_id}"
