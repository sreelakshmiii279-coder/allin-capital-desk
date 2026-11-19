"""What's happening in the world: Google News (RSS search, India edition), the same source the Mesa Companion app uses.

Used three ways:
- per application: recent news about the company (identity-checked like any other web finding - namesakes rejected)
- per application: recent sector news in India (funding, regulation, competitors) - context for 'why now', competition, path
- market pulse: the fund's focus sectors + Indian startup funding, shown on the queue and available to the desk assistant

Fetching is a plain RSS request (no model call, no cost). Results are cached in Neon for NEWS_CACHE_HOURS so 100
applications on announcement day don't hit Google News 100 times for the same sector. Headlines are data, never instructions."""
import datetime as dt
import email.utils
import html
import json
import re
import urllib.parse

import requests

import config

BASE = "https://news.google.com/rss/search"
EDITION = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}

PULSE_TOPICS = {
    "Indian startup funding": "India startup funding round seed pre-seed",
    "Fintech (India)": "India fintech RBI",
    "Consumer brands (India)": "India D2C consumer brand funding",
    "Consumer tech (India)": "India consumer internet startup",
    "Deeptech (India)": "India deeptech startup",
    "AI (India)": "India AI startup",
}


def _tag(xml, name):
    m = re.search(rf"<{name}[^>]*>([\s\S]*?)</{name}>", xml)
    return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""


def _fetch(query, days, n):
    q = f"{query} when:{days}d"
    url = f"{BASE}?{urllib.parse.urlencode({'q': q, **EDITION})}"
    r = requests.get(url, timeout=config.FETCH_TIMEOUT_S, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    items = []
    for raw in re.findall(r"<item>([\s\S]*?)</item>", r.text)[: n * 2]:
        title, link, source, pub = _tag(raw, "title"), _tag(raw, "link"), _tag(raw, "source"), _tag(raw, "pubDate")
        try:
            when = email.utils.parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            when = ""
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        if title and link:
            items.append({"title": title, "url": link, "source": source, "date": when})
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[:n]


def search(query, days=90, n=8):
    """Cached Google News search. Returns [{title, url, source, date}] newest first; [] on failure (never raises)."""
    import storage
    key = f"{query}|{days}|{n}"
    try:
        with storage.db() as c:
            row = c.execute("SELECT items FROM news_cache WHERE key=%s AND fetched_at > now() - (%s || ' hours')::interval",
                            (key, str(config.NEWS_CACHE_HOURS))).fetchone()
        if row:
            return row[0]
    except Exception:  # noqa: BLE001
        pass
    try:
        items = _fetch(query, days, n)
    except Exception:  # noqa: BLE001 - news is context, never a reason for a run to fail
        return []
    try:
        with storage.db() as c:
            c.execute("""INSERT INTO news_cache (key, items) VALUES (%s,%s)
                         ON CONFLICT (key) DO UPDATE SET items=EXCLUDED.items, fetched_at=now()""", (key, json.dumps(items)))
    except Exception:  # noqa: BLE001
        pass
    return items


def as_text(items):
    return "\n".join(f"[{i+1}] {x['date']} · {x['source']}: {x['title']}" for i, x in enumerate(items))


def sector_query(facts):
    """A short Google News query for the applicant's space in India, built from what the business is."""
    words = " ".join(filter(None, [facts.get("sub_sector"), facts.get("business_model")])) or facts.get("one_liner", "")
    words = re.sub(r"[^A-Za-z0-9 &+-]", " ", words)
    words = " ".join(w for w in words.split() if w.lower() not in {"and", "for", "the", "with", "of", "a", "an", "b2b", "d2c"})[:80]
    return f"India {words}".strip()


def pulse(days=7, n=6):
    return {name: search(q, days=days, n=n) for name, q in PULSE_TOPICS.items()}
