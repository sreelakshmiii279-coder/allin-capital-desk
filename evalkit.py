"""Server side of the evals: each decision the desk makes, callable with a FIXED input over HTTP (L7: fixed scenario).
The harness (evals/harness.py) only ever talks to these endpoints; it never imports this code.
Nothing here writes to the real queue, sends a real email or touches the real slot table."""
import copy
import datetime as dt

import booking
import conflicts
import extract
import feedback
import research
import score
import thesis

IST = booking.IST


# ---------------- booking: a fake world with switchable failures ----------------
class FakeWorld:
    """behaviour = {"calendar": ok|timeout_once|down, "email": sent|bad_address|transient|transient_once,
                    "book": ok|permanent_error, "crm": ok|fail_after_booking, "approved": true|false,
                    "start": ISO datetime (IST) the scenario begins}"""
    def __init__(self, behaviour):
        self.b = {"calendar": "ok", "email": "sent", "book": "ok", "crm": "ok", "approved": True, **(behaviour or {})}
        self.slots, self.bookings, self.events = {}, {}, []
        self.calls = {"taken_slots": 0, "post_email": 0, "book_attempts": 0, "save_booking": 0, "sleep": 0}
        self.clock = dt.datetime.fromisoformat(self.b.get("start", "2026-11-16T10:00:00+05:30"))
        self.emails = []

    # store
    def taken_slots(self):
        self.calls["taken_slots"] += 1
        if self.b["calendar"] == "down" or (self.b["calendar"] == "timeout_once" and self.calls["taken_slots"] == 1):
            raise TimeoutError("calendar timeout")
        return {k: v for k, v in self.slots.items()}

    def _key(self, iso):
        return dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).isoformat()

    def hold_slot(self, iso, app_id, status):
        if status == "booked":
            self.calls["book_attempts"] += 1
            if self.b["book"] == "permanent_error":
                raise PermissionError("calendar permissions revoked")
        k = self._key(iso)
        if k in self.slots and self.slots[k][0] != app_id:
            return
        self.slots[k] = (app_id, status)

    def release_slots(self, app_id, keep=None):
        keep_k = self._key(keep) if keep else None
        self.slots = {k: v for k, v in self.slots.items() if v[0] != app_id or k == keep_k}

    def get_booking(self, app_id):
        return copy.deepcopy(self.bookings.get(app_id))

    def save_booking(self, app_id, state):
        self.calls["save_booking"] += 1
        if self.b["crm"] == "fail_after_booking" and state.get("meeting_status") == "booked":
            raise ConnectionError("CRM write failed")
        self.bookings[app_id] = copy.deepcopy(state)

    def event(self, app_id, kind, payload):
        self.events.append({"app_id": app_id, "kind": kind, **(payload or {})})

    # email
    def email_ready(self):
        return True

    def post_email(self, payload):
        self.calls["post_email"] += 1
        e = self.b["email"]
        if e == "bad_address":
            return 422, "invalid recipient"
        if e == "transient" or (e == "transient_once" and self.calls["post_email"] == 1):
            return 503, "unavailable"
        self.emails.append(payload["subject"])
        return 200, {"id": f"fake-{self.calls['post_email']}"}

    # clock
    def now(self):
        return self.clock

    def sleep(self, s):
        self.calls["sleep"] += 1

    # drafting (template - evals test the agent's edges, not the copywriting)
    def draft_email(self, state, read):
        return booking._template(state)

    def judge_edit(self, draft, final, note):
        same = (draft.get("subject"), draft.get("body")) == (final.get("subject"), final.get("body"))
        return {"meaningful": not same, "summary": "fixture edit", "note": note}

    def store_email_correction(self, app_id, read, edit, editor):
        self.events.append({"app_id": app_id, "kind": "email_correction", "summary": edit.get("summary")})

    # approval (K7)
    def approved(self, app_id):
        return bool(self.b.get("approved", True))


def run_booking_scenario(body):
    """body = {behaviour, apps: [{app_id, company, sector, founder}], steps: [{app_id, do: start|reply|advance_hours|tick|no_reply,
               text?, forced?: {reply_status, chosen_slot_index}, hours?}]}"""
    w = FakeWorld(body.get("behaviour"))
    reads = {a["app_id"]: {"company": a.get("company", a["app_id"]), "sector": a.get("sector", "fintech"),
                           "facts": {"founders": [{"name": a.get("founder", "Asha Rao")}]}, "questions_for_call": []}
             for a in body.get("apps", [{"app_id": "app-1"}])}
    trace, error = [], None
    with booking.use_world(w):
        for st in body.get("steps", []):
            a = st.get("app_id", next(iter(reads)))
            try:
                if st["do"] == "start":
                    booking.start(a, reads[a])
                elif st["do"] == "send":
                    s0 = w.bookings.get(a) or {}
                    d = s0.get("draft") or {}
                    booking.send_draft(a, st.get("subject", d.get("subject", "")), st.get("body", d.get("body", "")),
                                       note=st.get("note"), read=reads[a])
                elif st["do"] == "reply":
                    booking.on_reply(a, st.get("text", ""), reads[a], forced=st.get("forced"))
                elif st["do"] == "advance_hours":
                    w.clock += dt.timedelta(hours=st["hours"])
                elif st["do"] == "tick":
                    if not hasattr(booking, "tick"):
                        raise NotImplementedError("booking has no automatic reply-window check (tick)")
                    booking.tick(a, reads[a])
                elif st["do"] == "no_reply":
                    booking.no_reply(a, reads[a])
                s = w.bookings.get(a) or {}
                trace.append({"step": st["do"], "app_id": a, "meeting_status": s.get("meeting_status"), "round": s.get("reply_round")})
            except Exception as e:  # noqa: BLE001 - a crash is a result the harness must see, not hide
                error = f"{type(e).__name__}: {e}"
                trace.append({"step": st["do"], "app_id": a, "crashed": error})
                break
    states = w.bookings
    first = states.get(next(iter(reads))) or {}
    booked_slots = [k for k, v in w.slots.items() if v[1] == "booked"]
    return {"state": first, "states": states, "calls": w.calls, "emails": w.emails, "trace": trace, "error": error,
            "invites_sent": sum(1 for s in states.values() for e in s.get("emails_sent", []) if e["kind"] in ("invite", "follow_up") and e["status"] == "sent"),
            "booked_slots": booked_slots, "double_booked": len(booked_slots) != len(set(booked_slots)),
            "events": w.events}


# ---------------- other decisions ----------------
def eval_quote(b):
    rec = {"form_text": b.get("form", ""), "deck_text": b.get("deck", "")}
    return {"found": extract.quote_found(b["quote"], rec, b.get("doc", "form"))}


def eval_extract(b):
    rec = {"form_text": b.get("form", ""), "deck_text": b.get("deck", "")}
    return extract.extract(rec)


def eval_conflict(b):
    facts = {k: b.get(k) for k in ("company", "one_liner", "business_model", "sector")}
    out = conflicts.check(facts)
    levels = {o["portfolio_company"]: o["level"] for o in out}
    return {"overlaps": out, "levels": levels, "direct": sorted(k for k, v in levels.items() if v == "direct")}


def eval_research_judge(b):
    return research.judge_sources(b["question"], b["identity_rule"], b.get("search_text", ""), b.get("sources", []))


def eval_budget(b):
    bud = research.Budget()
    bud.used = int(b["used"])
    allowed = bud.take()
    return {"allowed": allowed, "used_after": bud.used, "cap": research.config.MAX_SEARCHES_PER_APP}


def eval_finalize(b):
    rec = {"form_text": b.get("form", ""), "deck_text": b.get("deck", "")}
    raw = b["raw"]
    for c in thesis.CRITERIA:   # fill criteria the case does not mention with a neutral, traceable 3
        raw.setdefault(c["key"], {"score": 3, "written_score": 3, "reason": "fixture",
                                  "evidence": [{"claim": "fixture", "source_type": "memo", "ref": "Memo 3"}], "unknowns": []})
    raw.setdefault("key_number_present", True)
    raw.setdefault("depends_on_regulatory_change", False)
    raw.setdefault("capital_density_model", False)
    out = score.finalize(raw, rec, b.get("facts", {}), b.get("research", {}), b.get("conflicts", []), b.get("hits", []))
    out["by"] = {c["key"]: {"score": c["score"], "effective": c["effective"], "evidence": len(c["evidence"]),
                            "untraced": len(c["untraced_evidence"])} for c in out["criteria"]}
    out["flag_keys"] = [f["key"] for f in out["flags"]]
    return out


def eval_retrieve(b):
    cands = []
    for i, c in enumerate(b["corrections"]):
        tags = feedback.context_tags(c["facts"])
        tags["embedding"] = feedback._embed(f'{tags["one_liner"]} | {tags["business_model"]} | {c["criterion"]}: {c["reason"]}')
        cands.append({"id": c.get("id", i + 1), "app_id": c.get("app_id", f"fx-{i}"), "criterion": c["criterion"],
                      "old": c["old"], "new": c["new"], "reason": c["reason"], "tags": tags,
                      "reviewer": c.get("reviewer", "Riya"), "at": c.get("at", "2026-11-01T10:00:00")})
    hits = feedback.retrieve(b["facts"], candidates=cands)
    return {"hits": hits, "ids": [h["id"] for h in hits], "prompt": feedback.as_prompt(hits)}


def eval_capture(b):
    ok, why = feedback.validate(b.get("old"), b.get("new"), b.get("reason"))
    return {"store": ok, "why": why}


def eval_classify(b):
    state = {"company": b.get("company", "Acme"), "reply_round": b.get("round", 0), "slots_proposed": b["slots"]}
    return booking.classify_reply(state, b["reply"])


def eval_score(b):
    """Full scoring with the model (no web research, nothing stored)."""
    import pipeline
    rec = {"id": "eval-" + b.get("name", "x").lower(), "name": b.get("name", "Eval"), "batch": "eval",
           "form_text": b.get("form", ""), "deck_text": b.get("deck", ""), "source": "public form"}
    read = pipeline.run_one(rec, do_research=False, persist=False)
    read["by"] = {c["key"]: c["score"] for c in read.get("criteria", [])}
    read["flag_keys"] = [f["key"] for f in read.get("flags", [])]
    return read


def eval_cost(b):
    import obs
    return {"inr": obs.cost_inr(b.get("kind", "json"), b.get("in_tok", 0), b.get("out_tok", 0), b.get("searches", 0))}


def eval_redact(b):
    facts = {"founders": [{"name": n} for n in b.get("founders", [])]}
    return {"text": score.redact(b["text"], facts)}


def eval_memos(b):
    text = score._seed_text(None, b["facts"])
    return {"memos": [l.split(": ", 1)[1].strip() for l in text.split("\n") if l.startswith("Memo ")], "chars": len(text)}


def eval_chat(b):
    import chat
    return chat.answer(b["question"], b.get("history"), b.get("app_id"))


HANDLERS = {"quote": eval_quote, "extract": eval_extract, "conflict": eval_conflict, "research_judge": eval_research_judge,
            "budget": eval_budget, "finalize": eval_finalize, "retrieve": eval_retrieve, "capture": eval_capture,
            "classify": eval_classify, "cost": eval_cost, "chat": eval_chat, "redact": eval_redact, "memos": eval_memos, "booking": run_booking_scenario, "score": eval_score}
