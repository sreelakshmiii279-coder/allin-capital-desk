"""One place that talks to Gemini. Always asks for JSON and checks it really is JSON."""
import json
import os
import re
import time

from google import genai
from google.genai import types

import config

import threading

_local = threading.local()


def _get_client(fresh=False):
    """One client per thread: a shared client gets closed under concurrent use ("client has been closed")."""
    if fresh or getattr(_local, "client", None) is None:
        _local.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _local.client


def ask_json(prompt, schema, temperature=0.0, retries=2):
    """Returns a dict matching `schema`. Transient errors (rate limit, timeout) retry with backoff;
    anything else is raised so the caller logs it instead of silently carrying on."""
    for attempt in range(retries + 1):
        try:
            res = _get_client().models.generate_content(
                model=config.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return json.loads(res.text)
        except json.JSONDecodeError as e:
            if attempt == retries:
                raise ValueError(f"Model did not return valid JSON: {e}") from e
        except Exception as e:  # noqa: BLE001 - classified below, re-raised if permanent
            transient = any(s in str(e) for s in ("429", "503", "500", "timeout", "Timeout", "UNAVAILABLE", "closed", "Disconnected"))
            if "closed" in str(e):
                _get_client(fresh=True)
            if not transient or attempt == retries:
                raise
            time.sleep(2 ** attempt * 3)
    raise RuntimeError("unreachable")


def ask_search(prompt):
    """Gemini with Google Search grounding, for facts company websites rarely state (funding, headcount).
    Returns (answer text, list of {title, url} sources). No sources means the model answered from memory,
    and callers must not use the answer."""
    for attempt in range(3):
        try:
            res = _get_client().models.generate_content(
                model=config.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
            )
            break
        except Exception as e:  # noqa: BLE001 - transient: retry with backoff; permanent: raise (S6 retry table)
            if attempt == 2 or not any(s in str(e) for s in ("429", "503", "500", "timeout", "UNAVAILABLE", "closed")):
                raise
            if "closed" in str(e):
                _get_client(fresh=True)
            time.sleep(2 ** attempt * 3)
    sources = []
    meta = res.candidates[0].grounding_metadata if res.candidates else None
    for ch in (getattr(meta, "grounding_chunks", None) or []):
        if getattr(ch, "web", None):
            sources.append({"title": ch.web.title or "", "url": ch.web.uri or ""})
    return res.text or "", sources
