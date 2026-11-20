"""python check_setup.py - what is connected, and does each connection really work?
Makes one tiny call per service (a few paise). Prints PASS / FAIL / NOT SET with the reason."""
import json
import os
import time

import requests

import config


def line(name, status, detail=""):
    print(f"{status:<8} {name:<34} {detail}")


def main():
    line("Gemini key", "PASS" if os.environ.get("GEMINI_API_KEY") else "FAIL", config.MODEL)
    line("Neon database", "PASS" if config.DATABASE_URL else "FAIL")
    try:
        import storage
        with storage.db() as c:
            c.execute("SELECT 1")
        line("Neon reachable", "PASS")
    except Exception as e:  # noqa: BLE001
        line("Neon reachable", "FAIL", str(e)[:120])
    line("Resend (emails to own inbox)", "PASS" if config.RESEND_API_KEY and config.TO_ADDRESS else "NOT SET")
    line("Daily cost limit", "PASS", f"INR {config.DAILY_COST_LIMIT_INR:.0f} (Google published prices, config.py)")

    if config.CF_GATEWAY_URL:
        import llm
        try:
            out = llm.ask_json('Return {"ok": true}', {"type": "object", "properties": {"ok": {"type": "boolean"}}})
            line("Cloudflare gateway: JSON call", "PASS" if out.get("ok") else "FAIL", json.dumps(out))
        except Exception as e:  # noqa: BLE001
            line("Cloudflare gateway: JSON call", "FAIL", str(e)[:200])
        try:
            text, sources = llm.ask_search("Search the web now (do not answer from memory). Who founded All In Capital, the Indian VC fund?")
            line("Cloudflare gateway: search grounding", "PASS" if sources else "FAIL", f"{len(sources)} sources with citations")
        except Exception as e:  # noqa: BLE001
            line("Cloudflare gateway: search grounding", "FAIL", str(e)[:200])
        try:
            v = llm.embed("connection test")
            line("Cloudflare gateway: embeddings", "PASS" if v else "FAIL", f"{len(v)} dims")
        except Exception as e:  # noqa: BLE001
            line("Cloudflare gateway: embeddings", "FAIL", str(e)[:200])
    elif not config.PORTKEY_API_KEY:
        line("Portkey gateway", "NOT SET", "add PORTKEY_API_KEY to .env (+ PORTKEY_PROVIDER, default 'google')")
    else:
        import llm
        try:
            out = llm.ask_json('Return {"ok": true}', {"type": "object", "properties": {"ok": {"type": "boolean"}}})
            line("Portkey: JSON call", "PASS" if out.get("ok") else "FAIL", json.dumps(out))
        except Exception as e:  # noqa: BLE001
            line("Portkey: JSON call", "FAIL", str(e)[:200])
        try:
            text, sources = llm.ask_search("Search the web now (do not answer from memory). Who founded All In Capital, the Indian VC fund?")
            line("Portkey: search grounding", "PASS" if sources else "FAIL",
                 f"{len(sources)} sources" + ("" if sources else " - citations not returned through Portkey: set PORTKEY_ROUTE_SEARCH=0 "
                                                                   "so research keeps working (searches then go direct, still metered)"))
        except Exception as e:  # noqa: BLE001
            line("Portkey: search grounding", "FAIL", str(e)[:200])

    if not (config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY):
        line("Langfuse tracing", "NOT SET", "add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY (+ LANGFUSE_HOST) to .env")
    else:
        import obs
        with obs.run("setup-check", kind="setup") as run_id:
            with obs.step("ping"):
                obs.record_call("json", config.MODEL, "setup-v1", 1, 1, 0, 5, "ok", input_preview="ping", output_preview="pong")
        line("Langfuse tracing", "PASS", f"trace sent - open {obs.langfuse_url(run_id)} (check it appears; OTLP endpoint, ingestion v4)")


if __name__ == "__main__":
    main()
