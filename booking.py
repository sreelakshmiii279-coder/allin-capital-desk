"""Booking agent (S6): "once something looks promising, don't make me go back to email and calendars".
Starts ONLY when Kushal marks an application "Take the call" in the review queue (M5: he sees every outcome first).

FRAMEWORK CHOICE (S6 matrix): no framework. The flow is linear with ONE judgement gate (classify the founder's reply);
LangGraph/CrewAI would be over-engineering ("Do not over-engineer").

TOOLS - each description states what it does, when to use it, when NOT to, and the output format (S6 four golden rules).
STATE OBJECT - the only thing the reply classifier sees besides the reply itself; no raw email threads (S6 scratchpad problem).
EDGES:
  approved -> check_calendar -> propose_times (hold 3 Tue/Thu slots) -> send_email(invite) -> [founder reply]
  reply -> classify_reply:
     picks_slot      -> book_meeting -> send_email(confirmation + .ics) -> update_crm(booked)            [done]
     counter/none_fit-> reply_round+1; if <= MAX_REPLY_ROUNDS: propose_times again else escalate(Riya)
     not_interested  -> release holds -> update_crm(declined)                                            [done]
     unclear         -> escalate(Riya)                                                                    [done]
  no reply after 3 working days -> one follow-up (counts as a round) -> then escalate.
RETRY TABLE:
  | Error                                   | Kind      | Downstream need | Policy                                   |
  | Resend 429 / 5xx / timeout              | transient | required        | retry 3x, backoff 3s/6s/12s, then escalate |
  | Resend 4xx (bad address, domain)        | permanent | required        | abort step, escalate to Riya, log          |
  | DB timeout                              | transient | required        | retry 3x then escalate                     |
  | Classifier returns non-JSON             | transient | required        | retry once, then 'unclear' -> escalate     |
  | Slot taken between propose and book     | permanent | required        | do not double-book: re-propose (a round)   |
SAFETY: every email goes to TO_ADDRESS (our own inbox) - never to the founder - so the flow is real end to end
without contacting anyone; the founder's address is shown in the email body for the human who forwards it."""
import base64
import datetime as dt
import time
import uuid

import requests

import config
import llm
import storage

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

TOOLS = {
    "check_calendar": {
        "does": "Lists Kushal's free 30-minute call slots (Tue/Thu afternoons, IST) in the next 14 days.",
        "use_when": "Before proposing times, and again just before booking.",
        "not_when": "Never to read or change any other calendar; never for second calls (Aditya runs deeptech second calls himself).",
        "returns": "list of ISO datetimes that are 'free'; [] if fully booked; 'no_calendar_access' on DB failure."},
    "propose_times": {
        "does": "Holds 3 free slots for this applicant so nobody else is offered them.",
        "use_when": "After approval, or after a counter-reply while reply_round <= MAX_REPLY_ROUNDS.",
        "not_when": "If meeting_status is booked/declined/escalated, or the founder already picked a slot.",
        "returns": "the 3 held slots (ISO); [] if fewer than 1 free -> escalate."},
    "send_email": {
        "does": "Sends one email (optionally with an .ics invite) via Resend to TO_ADDRESS.",
        "use_when": "Invite, follow-up, confirmation.",
        "not_when": "Never to the founder directly from this build; never twice for the same step (check state.emails_sent).",
        "returns": "'sent' | 'failed_transient' | 'failed_permanent' (+ message id)."},
    "book_meeting": {
        "does": "Turns one held slot into a booking and releases the other holds.",
        "use_when": "Only after classify_reply = picks_slot AND check_calendar shows the slot still held for this applicant.",
        "not_when": "Slot not in state.slots_proposed, or meeting already booked.",
        "returns": "'booked' | 'slot_taken'."},
    "update_crm": {
        "does": "Writes the outcome to the desk's record (bookings + events tables).",
        "use_when": "After every state change.",
        "not_when": "Never to change the investment recommendation or review decision.",
        "returns": "'logged'."},
}

NEW_STATE = {"app_id": None, "company": None, "founder_name": None, "attendees": [], "reply_status": "none",
             "slots_proposed": [], "reply_round": 0, "meeting_status": "not_started", "chosen_slot": None,
             "emails_sent": [], "crm_logged": False, "errors": [], "history": []}


# ---------------- tools ----------------
def check_calendar(days=14):
    try:
        taken = storage.taken_slots()
    except Exception:  # noqa: BLE001
        return "no_calendar_access"
    now = dt.datetime.now(IST)
    free = []
    for d in range(1, days + 1):
        day = (now + dt.timedelta(days=d)).date()
        if day.weekday() not in config.CALL_DAYS:
            continue
        for t in config.CALL_SLOTS:
            h, m = map(int, t.split(":"))
            s = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
            if s.astimezone(dt.timezone.utc).isoformat() not in taken and s.isoformat() not in taken:
                free.append(s.isoformat())
    return free


def propose_times(state):
    free = check_calendar()
    if free == "no_calendar_access" or not free:
        return []
    # spread across days first (one per day), then fill
    picks, days = [], set()
    for f in free:
        if f[:10] not in days and len(picks) < config.SLOTS_TO_PROPOSE:
            picks.append(f); days.add(f[:10])
    for f in free:
        if len(picks) >= config.SLOTS_TO_PROPOSE:
            break
        if f not in picks:
            picks.append(f)
    picks.sort()
    for p in picks:
        storage.hold_slot(p, state["app_id"], "held")
    return picks


def _ics(state, slot):
    start = dt.datetime.fromisoformat(slot).astimezone(dt.timezone.utc)
    end = start + dt.timedelta(minutes=config.CALL_MINUTES)
    f = "%Y%m%dT%H%M%SZ"
    who = " + ".join(state["attendees"])
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//All In Capital Desk//EN", "METHOD:REQUEST", "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@allin-desk", f"DTSTAMP:{dt.datetime.now(dt.timezone.utc).strftime(f)}",
        f"DTSTART:{start.strftime(f)}", f"DTEND:{end.strftime(f)}",
        f"SUMMARY:All In Capital x {state['company']} - intro call (30 min)",
        f"DESCRIPTION:First call. Attendees: {who}. Desk read attached in the review queue.",
        "END:VEVENT", "END:VCALENDAR", ""])


def send_email(subject, html, ics=None):
    if not (config.RESEND_API_KEY and config.TO_ADDRESS):
        return "failed_permanent", "Resend not configured"
    payload = {"from": config.RESEND_FROM, "to": [config.TO_ADDRESS], "subject": subject, "html": html}
    if ics:
        payload["attachments"] = [{"filename": "invite.ics", "content": base64.b64encode(ics.encode()).decode()}]
    for attempt in range(config.TRANSIENT_RETRIES):
        try:
            r = requests.post("https://api.resend.com/emails", json=payload, timeout=20,
                              headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"})
            if r.status_code < 300:
                return "sent", r.json().get("id")
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(3 * 2 ** attempt)
                continue
            return "failed_permanent", f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            time.sleep(3 * 2 ** attempt)
            last = str(e)
    return "failed_transient", "retries exhausted"


def book_meeting(state, slot):
    taken = storage.taken_slots()
    holder = taken.get(dt.datetime.fromisoformat(slot).astimezone(dt.timezone.utc).isoformat())
    if holder and holder[0] != state["app_id"]:
        return "slot_taken"
    storage.hold_slot(slot, state["app_id"], "booked")
    storage.release_slots(state["app_id"], keep=slot)
    return "booked"


def update_crm(state):
    storage.save_booking(state["app_id"], state)
    storage.event(state["app_id"], "booking", {"meeting_status": state["meeting_status"], "round": state["reply_round"]})
    state["crm_logged"] = True
    return "logged"


# ---------------- the one judgement gate ----------------
CLASSIFY = {"type": "object", "properties": {
    "reply_status": {"type": "string", "enum": ["picks_slot", "counter", "none_fit", "not_interested", "unclear"]},
    "chosen_slot_index": {"type": "integer", "description": "1-based index into slots_proposed when picks_slot, else 0"},
    "note": {"type": "string"}}, "required": ["reply_status", "chosen_slot_index", "note"]}


def classify_reply(state, reply_text):
    slots = "\n".join(f"{i+1}. {_human(s)}" for i, s in enumerate(state["slots_proposed"]))
    for attempt in range(2):
        try:
            return llm.ask_json(
                "Classify a founder's reply to a meeting invite. State (only what you need):\n"
                f"company={state['company']}; reply_round={state['reply_round']}; slots offered:\n{slots}\n\n"
                f"Founder reply:\n\"\"\"{reply_text[:2000]}\"\"\"\n"
                "picks_slot only if they clearly accept one of the offered slots.", CLASSIFY, temperature=0.0)
        except Exception:  # noqa: BLE001
            continue
    return {"reply_status": "unclear", "chosen_slot_index": 0, "note": "classifier failed twice"}


def _human(iso):
    return dt.datetime.fromisoformat(iso).astimezone(IST).strftime("%a %d %b, %I:%M %p IST")


def _log(state, what):
    state["history"].append({"at": dt.datetime.now(IST).isoformat(timespec="seconds"), "what": what})


def _invite_html(state, read, follow_up=False):
    slots = "".join(f"<li>{_human(s)}</li>" for s in state["slots_proposed"])
    who = " and ".join(state["attendees"])
    lead = "Following up on our note - " if follow_up else ""
    return (f"<p><i>Draft for {state['founder_name']} at {state['company']} - this desk sends to our own inbox only; "
            f"forward to the founder after a glance.</i></p><hr>"
            f"<p>Hi {state['founder_name'].split()[0]},</p><p>{lead}Thanks for applying to All In Capital. We'd like a 30-minute call "
            f"with {who}. Could you pick one of these?</p><ul>{slots}</ul>"
            f"<p>Reply with the one that works, or suggest another Tuesday/Thursday afternoon.</p><p>Best,<br>All In Capital</p>"
            f"<hr><p><b>For Kushal - what to ask on the call (from the desk read):</b></p><ul>"
            + "".join(f"<li>{q}</li>" for q in (read or {}).get("questions_for_call", [])) + "</ul>")


# ---------------- edges ----------------
def start(app_id, read):
    state = storage.get_booking(app_id)
    if state and state["meeting_status"] in ("pending_confirmation", "booked"):
        return state  # idempotent: approving twice does not send twice
    facts = read.get("facts", {})
    founders = facts.get("founders") or [{"name": "Founder"}]
    state = {**NEW_STATE, "app_id": app_id, "company": read.get("company"), "founder_name": founders[0]["name"],
             "attendees": ["Kushal"] + (["Aditya"] if read.get("sector") in config.ADITYA_JOINS_FOR else []),
             "emails_sent": [], "history": [], "errors": []}
    return _propose_and_send(state, read)


def _propose_and_send(state, read, follow_up=False):
    state["slots_proposed"] = propose_times(state)
    if not state["slots_proposed"]:
        state["meeting_status"] = "escalated"
        _log(state, "No free Tue/Thu slot in 14 days - escalated to Riya")
        update_crm(state)
        return state
    _log(state, f"Held {len(state['slots_proposed'])} slots (round {state['reply_round']})")
    status, info = send_email(f"[Desk draft] All In Capital <> {state['company']}: pick a time", _invite_html(state, read, follow_up))
    state["emails_sent"].append({"kind": "follow_up" if follow_up else "invite", "status": status, "info": info})
    if status != "sent":
        state["errors"].append(info)
        state["meeting_status"] = "escalated" if status == "failed_permanent" else "pending_confirmation"
        _log(state, f"Email {status}: {info}")
    else:
        state["meeting_status"] = "pending_confirmation"
        _log(state, "Invite emailed (to our inbox)")
    update_crm(state)
    return state


def on_reply(app_id, reply_text, read):
    state = storage.get_booking(app_id)
    if not state or state["meeting_status"] != "pending_confirmation":
        return state
    c = classify_reply(state, reply_text)
    state["reply_status"] = c["reply_status"]
    _log(state, f"Founder replied -> {c['reply_status']} ({c['note']})")
    if c["reply_status"] == "picks_slot" and 0 < c["chosen_slot_index"] <= len(state["slots_proposed"]):
        slot = state["slots_proposed"][c["chosen_slot_index"] - 1]
        if book_meeting(state, slot) == "booked":
            state["chosen_slot"], state["meeting_status"] = slot, "booked"
            status, info = send_email(f"[Desk] Booked: All In Capital <> {state['company']}, {_human(slot)}",
                                      f"<p>Booked {_human(slot)} with {' and '.join(state['attendees'])}. Calendar invite attached.</p>",
                                      ics=_ics(state, slot))
            state["emails_sent"].append({"kind": "confirmation", "status": status, "info": info})
            _log(state, f"Booked {_human(slot)}; confirmation {status}")
        else:
            state["reply_round"] += 1
            _log(state, "Slot was taken in between - re-proposing")
            return _propose_and_send(state, read)
    elif c["reply_status"] in ("counter", "none_fit"):
        state["reply_round"] += 1
        storage.release_slots(app_id)
        if state["reply_round"] > config.MAX_REPLY_ROUNDS:
            state["meeting_status"] = "escalated"
            _log(state, f"{config.MAX_REPLY_ROUNDS} rounds without a time - escalated to Riya (retry cap)")
        else:
            return _propose_and_send(state, read)
    elif c["reply_status"] == "not_interested":
        storage.release_slots(app_id)
        state["meeting_status"] = "declined"
    else:
        state["meeting_status"] = "escalated"
        _log(state, "Unclear reply - escalated to Riya")
    update_crm(state)
    return state


def no_reply(app_id, read):
    """Called when 3 working days pass with no reply: one follow-up, which counts as a round."""
    state = storage.get_booking(app_id)
    if not state or state["meeting_status"] != "pending_confirmation":
        return state
    state["reply_round"] += 1
    storage.release_slots(app_id)
    if state["reply_round"] > config.MAX_REPLY_ROUNDS:
        state["meeting_status"] = "escalated"
        _log(state, "No reply after follow-up - escalated to Riya")
        update_crm(state)
        return state
    return _propose_and_send(state, read, follow_up=True)
