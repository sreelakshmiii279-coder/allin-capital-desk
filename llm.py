"""The ONE place that talks to a model. Every call is:
  guarded   - paused if today's spend is past DAILY_COST_LIMIT_INR (obs.guard)
  routed    - through the Portkey gateway with automatic retries when PORTKEY_API_KEY is set, else direct to Gemini
              (Case 04 task 3); our own retry loop stays only for the direct route
  metered   - tokens, searches, cost in INR, latency, prompt version, step and application recorded (obs.record_call)
  traced    - as a generation span inside the application's trace (Langfuse when keys are set; Neon always)."""
import json
import os
import random
import re
import threading
import time

import requests
from google import genai
from google.genai import types

import config
import obs

_local = threading.local()
TRANSIENT = ("429", "503", "500", "502", "504", "timeout", "Timeout", "UNAVAILABLE", "closed", "Disconnected")


def _get_client(fresh=False):
    """One client per thread: a shared client gets closed under concurrent use ("client has been closed")."""
    if fresh or getattr(_local, "client", None) is None:
        _local.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _local.client


def model_for(prompt_version):
    """L8 cost lever: cheaper model for simple steps (config.STEP_MODELS), main model for judgement."""
    return config.STEP_MODELS.get(prompt_version or "", config.MODEL)


def backoff(attempt):
    """L8: wait 1 s, 2 s, 4 s ... plus a small random wobble so 20 retries don't hit the provider in lockstep."""
    time.sleep(2 ** attempt + random.uniform(0, 0.5))


def via():
    return "portkey" if config.PORTKEY_API_KEY else "direct"


# ---------------- Portkey (OpenAI-compatible gateway) ----------------
def _portkey(messages, temperature, json_schema=None, search=False, model=None):
    headers = {"x-portkey-api-key": config.PORTKEY_API_KEY, "Content-Type": "application/json",
               "x-portkey-config": json.dumps({"retry": {"attempts": config.PORTKEY_RETRY_ATTEMPTS,
                                                         "on_status_codes": [429, 500, 502, 503, 504]}})}
    model = model or config.MODEL
    if config.PORTKEY_PROVIDER.startswith("@"):
        model = f"{config.PORTKEY_PROVIDER}/{model}"          # Model Catalog route
    else:
        headers["x-portkey-provider"] = config.PORTKEY_PROVIDER      # direct route: our Gemini key travels per request
        headers["Authorization"] = f"Bearer {os.environ['GEMINI_API_KEY']}"
    body = {"model": model, "messages": messages, "temperature": temperature}
    if json_schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": json_schema}}
    if search:
        body["tools"] = [{"type": "function", "function": {"name": "google_search"}}]
    r = requests.post("https://api.portkey.ai/v1/chat/completions", json=body, headers=headers, timeout=180)
    retries = int(r.headers.get("x-portkey-retry-attempt-count", "0") or 0)
    if r.status_code >= 400:
        raise RuntimeError(f"Portkey HTTP {r.status_code}: {r.text[:300]}")
    j = r.json()
    msg = j["choices"][0]["message"]
    usage = j.get("usage") or {}
    return msg, usage, max(retries, 0), j


def _strip_fences(t):
    return re.sub(r"^```(?:json)?|```$", "", (t or "").strip(), flags=re.M).strip()


# ---------------- public calls ----------------
def ask_json(prompt, schema, temperature=0.0, retries=None, prompt_version=None):
    """Returns a dict matching `schema`. Permanent errors are raised so the caller logs them instead of carrying on."""
    obs.guard()
    retries = config.RETRY_ATTEMPTS - 1 if retries is None else retries
    model = model_for(prompt_version)
    t0 = time.time()
    if config.PORTKEY_API_KEY:
        try:
            msg, usage, n_retry, _ = _portkey([{"role": "user", "content": prompt}], temperature, json_schema=schema, model=model)
            out = json.loads(_strip_fences(msg.get("content")))
            obs.record_call("json", model, prompt_version, usage.get("prompt_tokens"), usage.get("completion_tokens"), 0,
                            (time.time() - t0) * 1000, "ok", via="portkey", retries=n_retry,
                            input_preview=prompt[-1500:], output_preview=json.dumps(out)[:1500])
            return out
        except Exception as e:
            obs.record_call("json", model, prompt_version, 0, 0, 0, (time.time() - t0) * 1000, "error", str(e), via="portkey")
            raise
    last = None
    for attempt in range(retries + 1):
        try:
            res = _get_client().models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json",
                                                   response_schema=schema))
            u = res.usage_metadata
            out = json.loads(res.text)
            obs.record_call("json", model, prompt_version, getattr(u, "prompt_token_count", 0),
                            (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0), 0,
                            (time.time() - t0) * 1000, "ok", retries=attempt,
                            input_preview=prompt[-1500:], output_preview=res.text[:1500])
            return out
        except json.JSONDecodeError as e:
            last = e
            if attempt == retries:
                obs.record_call("json", model, prompt_version, 0, 0, 0, (time.time() - t0) * 1000, "error", f"bad JSON: {e}")
                raise ValueError(f"Model did not return valid JSON: {e}") from e
        except Exception as e:  # noqa: BLE001 - classified: transient retries, permanent raises
            last = e
            if "closed" in str(e):
                _get_client(fresh=True)
            if not any(s in str(e) for s in TRANSIENT) or attempt == retries:
                obs.record_call("json", model, prompt_version, 0, 0, 0, (time.time() - t0) * 1000, "error", str(e), retries=attempt)
                raise
            backoff(attempt)
    raise RuntimeError(f"unreachable: {last}")


def ask_search(prompt, prompt_version=None):
    """Gemini with Google Search grounding. Returns (answer text, [{title, url}]). No sources = the model answered from
    memory, and callers must not use the answer."""
    obs.guard()
    t0 = time.time()
    if config.PORTKEY_API_KEY and config.PORTKEY_ROUTE_SEARCH:
        try:
            msg, usage, n_retry, raw = _portkey([{"role": "user", "content": prompt}], 0.0, search=True)
            sources = _portkey_sources(msg, raw)
            obs.record_call("search", config.MODEL, prompt_version, usage.get("prompt_tokens"), usage.get("completion_tokens"), 1,
                            (time.time() - t0) * 1000, "ok", via="portkey", retries=n_retry,
                            input_preview=prompt, output_preview=(msg.get("content") or "")[:1500])
            return msg.get("content") or "", sources
        except Exception as e:
            obs.record_call("search", config.MODEL, prompt_version, 0, 0, 1, (time.time() - t0) * 1000, "error", str(e), via="portkey")
            raise
    res = None
    for attempt in range(config.RETRY_ATTEMPTS):
        try:
            res = _get_client().models.generate_content(
                model=config.MODEL, contents=prompt,
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
            break
        except Exception as e:  # noqa: BLE001 - transient: retry with backoff; permanent: raise (S6 retry table)
            if "closed" in str(e):
                _get_client(fresh=True)
            if attempt == config.RETRY_ATTEMPTS - 1 or not any(s in str(e) for s in TRANSIENT):
                obs.record_call("search", config.MODEL, prompt_version, 0, 0, 1, (time.time() - t0) * 1000, "error", str(e), retries=attempt)
                raise
            backoff(attempt)
    sources = []
    meta = res.candidates[0].grounding_metadata if res.candidates else None
    for ch in (getattr(meta, "grounding_chunks", None) or []):
        if getattr(ch, "web", None):
            sources.append({"title": ch.web.title or "", "url": ch.web.uri or ""})
    u = res.usage_metadata
    obs.record_call("search", config.MODEL, prompt_version, getattr(u, "prompt_token_count", 0),
                    (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0), 1,
                    (time.time() - t0) * 1000, "ok", input_preview=prompt, output_preview=(res.text or "")[:1500])
    return res.text or "", sources


def _portkey_sources(msg, raw):
    """Portkey's docs do not state where grounding citations appear; look in the places Gemini/OpenAI shapes use.
    If none are found the search is treated as 'no sources' (never trusted) - check_setup.py reports this."""
    found = []
    for key in ("citations", "annotations", "groundingMetadata", "grounding_metadata"):
        v = msg.get(key) or raw.get(key) or (raw.get("choices") or [{}])[0].get(key)
        if isinstance(v, dict):
            v = v.get("groundingChunks") or v.get("grounding_chunks") or []
        for x in v or []:
            web = x.get("web") if isinstance(x, dict) else None
            url = (web or {}).get("uri") or (x.get("url") if isinstance(x, dict) else None) or \
                  ((x.get("url_citation") or {}).get("url") if isinstance(x, dict) else None)
            if url:
                found.append({"title": (web or {}).get("title") or x.get("title", ""), "url": url})
    return found


def embed(text, prompt_version="embed-v1"):
    obs.guard()
    t0 = time.time()
    r = _get_client().models.embed_content(model="gemini-embedding-001", contents=text[:2000])
    obs.record_call("embed", "gemini-embedding-001", prompt_version, max(1, len(text) // 4), 0, 0, (time.time() - t0) * 1000, "ok")
    return list(r.embeddings[0].values)
