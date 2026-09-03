"""Voicemail / no-answer follow-up.

Outcome detection: Twilio <Dial> result (busy / no-answer / failed) + the call transcript we already make
(voicemail greetings are unmistakable; anything unclear goes to a tiny LLM classification).
Retry cadence (per Forest): miss #1 -> try again in 30 min; #2 -> later the same day; #3 -> next business
morning 10 AM (+ text tip); #4 -> two days later; #5 -> one final "text or park" task, then auto-retries stop.
A connected call completes the retry task and resets the streak.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)

DEFAULT_CADENCE = {
    "enabled": True,
    "first_minutes": 30,     # miss #1 -> try again in N minutes
    "second_hours": 3,       # miss #2 -> later the same day
    "morning_hour": 10,      # "next morning" time for miss #3 and evening rollovers
    "fourth_days": 2,        # miss #4 -> N days later at morning_hour
    "evening_cutoff": 19,    # a retry landing at/after this local hour rolls to next morning
    "max_auto": 4,           # misses that get an auto retry; the next one is the final "text or park" task
}
CADENCE_LIMITS = {
    "first_minutes": (5, 240), "second_hours": (1, 8), "morning_hour": (7, 12),
    "fourth_days": (1, 7), "evening_cutoff": (16, 22), "max_auto": (1, 6),
}
MAX_AUTO_RETRIES = DEFAULT_CADENCE["max_auto"]
DEFAULT_JUST_TRIED = "Hey {first_name}, it's {sender_name}. Just tried to give you a call, no rush at all. Call or text me back whenever works for you."
VOICEMAIL_HINTS = (
    "leave a message", "leave your message", "leave me a message", "after the tone", "at the tone", "after the beep",
    "record your message", "voicemail", "voice mail", "mailbox", "not available", "can't take your call",
    "cannot take your call", "unable to take your call", "unavailable right now", "i'll get back to you",
    "get back to you as soon as", "has a voice mailbox", "is not available", "the person you are trying to reach",
    "the number you have dialed", "press pound", "when you have finished recording", "to leave a callback number",
)
OUTCOME_LABEL = {"voicemail": "went to voicemail", "no_answer": "didn't answer", "busy": "was busy", "connected": "connected"}


def classify_transcript(transcript: str, duration_s: int) -> str:
    """Cheap first pass: 'voicemail' | 'connected' | 'unclear'."""
    t = re.sub(r"\s+", " ", (transcript or "").lower()).strip()
    if not t:
        return "no_answer" if duration_s < 8 else "unclear"
    head = t[:600]
    if any(h in head for h in VOICEMAIL_HINTS):
        return "voicemail"
    words = len(t.split())
    if duration_s >= 90 and words >= 120:
        return "connected"
    return "unclear"


async def classify_outcome_llm(transcript: str) -> str:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"call-outcome-{uuid.uuid4().hex[:10]}",
            system_message=(
                "You classify phone-call transcripts from a car salesperson's outbound call. Reply with exactly one word:\n"
                "connected = a live person answered and there was a two-way conversation\n"
                "voicemail = an answering machine / voicemail greeting, or the salesperson left a one-way message\n"
                "unclear = cannot tell"
            ),
        ).with_model("openai", "gpt-5.2")
        resp = await chat.send_message(UserMessage(text=(transcript or "")[:3000]))
        word = (resp if isinstance(resp, str) else str(resp)).strip().lower()
        for k in ("connected", "voicemail", "unclear"):
            if k in word:
                return k
    except Exception as e:
        logger.warning(f"[CallFollowup] LLM outcome classification failed: {e}")
    return "unclear"


async def detect_outcome(transcript: str, duration_s: int) -> str:
    out = classify_transcript(transcript, duration_s)
    if out == "unclear" and transcript:
        out = await classify_outcome_llm(transcript)
    if out == "unclear":
        out = "connected" if duration_s >= 60 else "voicemail"
    return out


async def _tz_for(user_id: str) -> ZoneInfo:
    try:
        from routers.user_schedule import resolve_user_tz
        return ZoneInfo(await resolve_user_tz(user_id))
    except Exception:
        return ZoneInfo("America/Denver")


def normalize_cadence(raw: dict | None) -> dict:
    """Fill defaults + clamp to sane ranges. Unknown keys dropped."""
    out = dict(DEFAULT_CADENCE)
    for k, (lo, hi) in CADENCE_LIMITS.items():
        v = (raw or {}).get(k)
        if v is None:
            continue
        try:
            out[k] = max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            pass
    if raw is not None and "enabled" in raw:
        out["enabled"] = bool(raw.get("enabled"))
    jt = (raw or {}).get("just_tried_text")
    if isinstance(jt, str) and jt.strip():
        out["just_tried_text"] = jt.strip()[:320]
    return out


async def resolve_cadence(user_id: str) -> dict:
    """personal override -> store default -> org-wide default (settings) -> built-in. Returns {cadence, source, store_cadence, global_cadence}."""
    db = get_db()
    u = await db.users.find_one({"_id": ObjectId(user_id)}, {"call_retry_cadence": 1, "store_id": 1}) if ObjectId.is_valid(user_id) else None
    u = u or {}
    store_raw = None
    sid = str(u.get("store_id") or "")
    if ObjectId.is_valid(sid):
        st = await db.stores.find_one({"_id": ObjectId(sid)}, {"call_retry_cadence": 1})
        store_raw = (st or {}).get("call_retry_cadence")
    g = await db.settings.find_one({"key": "call_retry_cadence_default"}, {"value": 1})
    global_raw = (g or {}).get("value")
    if u.get("call_retry_cadence"):
        cadence, source = normalize_cadence(u["call_retry_cadence"]), "personal"
    elif store_raw:
        cadence, source = normalize_cadence(store_raw), "store"
    elif global_raw:
        cadence, source = normalize_cadence(global_raw), "global"
    else:
        cadence, source = dict(DEFAULT_CADENCE), "default"
    return {"cadence": cadence, "source": source,
            "store_cadence": normalize_cadence(store_raw) if store_raw else None,
            "global_cadence": normalize_cadence(global_raw) if global_raw else None}


async def cadence_for(user_id: str) -> dict:
    return (await resolve_cadence(user_id))["cadence"]


def _at(d: datetime, hour: int) -> datetime:
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def _next_business_morning(local: datetime, hour: int = 10) -> datetime:
    d = _at(local + timedelta(days=1), hour)
    while d.weekday() == 6:  # dealers work Saturdays; skip Sundays only
        d += timedelta(days=1)
    return d


def next_retry_due(attempt: int, now_utc: datetime, tz: ZoneInfo, cadence: dict | None = None) -> datetime:
    c = normalize_cadence(cadence)
    local = now_utc.astimezone(tz)
    morning = c["morning_hour"]
    cutoff = c["evening_cutoff"]
    if attempt > c["max_auto"]:
        return _next_business_morning(local, morning).astimezone(timezone.utc)
    if attempt == 1:
        due = local + timedelta(minutes=c["first_minutes"])
        if due.hour >= cutoff + 1 or due.hour < 8:
            due = _next_business_morning(local, morning)
    elif attempt == 2:
        due = local + timedelta(hours=c["second_hours"])
        if due.hour >= cutoff or due.hour < 8:
            due = _next_business_morning(local, morning)
    elif attempt == 3:
        due = _next_business_morning(local, morning)
    elif attempt == 4:
        due = _at(local + timedelta(days=c["fourth_days"]), morning)
        while due.weekday() == 6:
            due += timedelta(days=1)
    else:
        due = _next_business_morning(local, morning)
    return due.astimezone(timezone.utc)


def preview_schedule(cadence: dict, tz: ZoneInfo, now_utc: datetime | None = None) -> list:
    """What the reminders would look like if a call went to voicemail right now."""
    c = normalize_cadence(cadence)
    now = now_utc or datetime.now(timezone.utc)
    out = []
    for attempt in range(1, c["max_auto"] + 2):
        due = next_retry_due(attempt, now, tz, c)
        out.append({"attempt": attempt, "final": attempt > c["max_auto"], "due": due.isoformat(), "label": _due_label(due, now, tz)})
    return out


def _due_label(due_utc: datetime, now_utc: datetime, tz: ZoneInfo) -> str:
    d, n = due_utc.astimezone(tz), now_utc.astimezone(tz)
    t = d.strftime("%-I:%M %p")
    if d.date() == n.date():
        return f"today {t}"
    if d.date() == (n + timedelta(days=1)).date():
        return f"tomorrow {t}"
    return d.strftime("%a %b %-d") + f" {t}"


async def _claim_pending(db, pending: dict) -> bool:
    """One outcome per Twilio call: first writer wins."""
    if not pending.get("_id"):
        return True
    r = await db.pending_calls.update_one({"_id": pending["_id"], "outcome_applied": {"$ne": True}},
                                          {"$set": {"outcome_applied": True}})
    return r.modified_count == 1


async def apply_call_outcome(pending: dict, outcome: str, duration_s: int = 0, source: str = "transcript") -> dict:
    """pending: pending_calls doc (or a manual stub with rep_user_id/contact_id/conversation_id/task_id)."""
    db = get_db()
    user_id = str(pending.get("rep_user_id") or pending.get("user_id") or "")
    contact_id = str(pending.get("contact_id") or "")
    if not user_id or not ObjectId.is_valid(contact_id):
        return {"applied": False, "reason": "no contact"}
    if not await _claim_pending(db, pending):
        return {"applied": False, "reason": "already applied"}
    now = datetime.now(timezone.utc)
    call_sid = pending.get("call_sid") or ""
    if pending.get("_id"):
        await db.pending_calls.update_one({"_id": pending["_id"]}, {"$set": {
            "customer_outcome": outcome, "outcome_source": source, "outcome_at": now, "customer_duration_s": duration_s}})
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "name": 1, "phone": 1, "call_retry": 1})
    if not contact:
        return {"applied": False, "reason": "contact missing"}
    first = (contact.get("first_name") or (contact.get("name") or "").split(" ")[0] or "them").strip()

    if outcome == "connected":
        return await _on_connected(db, user_id, contact, pending, call_sid, duration_s, now)
    return await _on_missed(db, user_id, contact, first, pending, outcome, source, call_sid, now)


async def _on_connected(db, user_id, contact, pending, call_sid, duration_s, now) -> dict:
    contact_id = str(contact["_id"])
    completed = 0
    if pending.get("task_id"):
        from routers.tasks import complete_task_from_call
        if await complete_task_from_call(user_id, str(pending["task_id"]), call_sid, duration_s):
            completed += 1
    r = await db.tasks.update_many(
        {"user_id": user_id, "contact_id": contact_id, "auto_kind": {"$in": ["call_retry", "call_retry_final"]}, "completed": {"$ne": True}},
        {"$set": {"status": "completed", "completed": True, "completed_at": now, "completed_via": "call_connected", "completed_call_sid": call_sid}})
    completed += r.modified_count
    await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"call_retry": None, "last_connected_call_at": now}})
    logger.info(f"[CallFollowup] connected with {contact_id}: closed {completed} task(s)")
    return {"applied": True, "outcome": "connected", "tasks_completed": completed}


async def _on_missed(db, user_id, contact, first, pending, outcome, source, call_sid, now) -> dict:
    contact_id = str(contact["_id"])
    tz = await _tz_for(user_id)
    cadence = await cadence_for(user_id)
    max_auto = cadence["max_auto"]
    state = contact.get("call_retry") or {}
    last_at = state.get("last_at")
    if isinstance(last_at, datetime) and last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    attempt = (int(state.get("attempts") or 0) + 1) if (isinstance(last_at, datetime) and now - last_at < timedelta(days=7)) else 1
    verb = OUTCOME_LABEL.get(outcome, "didn't answer")
    stamp = now.astimezone(tz).strftime("%-I:%M %p")
    conversation_id = pending.get("conversation_id") or None

    task_id, due_utc, label = None, None, ""
    if not cadence["enabled"]:
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"call_retry": {
            "attempts": attempt, "last_at": now, "last_outcome": outcome, "next_due": None, "task_id": None}}})
        await db.contact_events.insert_one({
            "event_type": f"call_{outcome}", "title": "Left voicemail" if outcome == "voicemail" else ("Line busy" if outcome == "busy" else "No answer"),
            "user_id": user_id, "contact_id": contact_id, "description": f"Miss #{attempt}. Auto-retries are off in your settings.",
            "category": "call", "icon": "call", "color": "#FF9F0A", "call_sid": call_sid, "source": source, "timestamp": now, "created_at": now})
        return {"applied": True, "outcome": outcome, "attempt": attempt, "task_id": None, "due": None, "label": "", "disabled": True}
    if attempt <= max_auto:
        due_utc = next_retry_due(attempt, now, tz, cadence)
        label = _due_label(due_utc, now, tz)
        tip = " Tip: shoot a quick \"just tried you\" text too." if attempt >= 3 else ""
        line = f"{first} {verb} at {stamp} (miss #{attempt}). Try again {label}.{tip}"
        existing = await db.tasks.find_one({"user_id": user_id, "contact_id": contact_id, "completed": {"$ne": True},
                                            "auto_kind": {"$in": ["call_retry", "call_retry_final"]}})
        if not existing and pending.get("task_id") and ObjectId.is_valid(str(pending["task_id"])):
            existing = await db.tasks.find_one({"_id": ObjectId(str(pending["task_id"])), "user_id": user_id, "completed": {"$ne": True}})
        if existing:
            desc = (existing.get("description") or "").strip()
            await db.tasks.update_one({"_id": existing["_id"]}, {"$set": {
                "due_date": due_utc, "has_time": True, "snoozed_until": None, "reminded_15": False, "reminded_due": False,
                "auto_kind": "call_retry", "retry_attempt": attempt, "priority": "high", "priority_order": 1,
                "description": (line + ("\n" + desc if desc else ""))[:600], "updated_at": now,
            }})
            task_id = str(existing["_id"])
        else:
            res = await db.tasks.insert_one({
                "user_id": user_id, "contact_id": contact_id, "contact_name": contact.get("name") or first,
                "contact_phone": contact.get("phone") or pending.get("customer_phone") or "",
                "type": "call", "source": "voicemail_followup", "call_sid": call_sid, "auto_kind": "call_retry", "retry_attempt": attempt,
                "title": f"Try {first} again", "description": line, "suggested_message": "",
                "action_type": "call", "priority": "high", "priority_order": 1, "status": "pending", "completed": False,
                "due_date": due_utc, "has_time": True, "appointment_type": "call", "reminded_15": False, "reminded_due": False,
                "completed_at": None, "snoozed_until": None, "campaign_id": None, "campaign_name": None, "pending_send_id": None,
                "channel": "", "conversation_id": conversation_id, "created_at": now,
            })
            task_id = str(res.inserted_id)
    elif attempt == max_auto + 1:
        due_utc = next_retry_due(attempt, now, tz, cadence)
        label = _due_label(due_utc, now, tz)
        res = await db.tasks.insert_one({
            "user_id": user_id, "contact_id": contact_id, "contact_name": contact.get("name") or first,
            "contact_phone": contact.get("phone") or "", "type": "task", "source": "voicemail_followup", "auto_kind": "call_retry_final",
            "retry_attempt": attempt, "title": f"{first}: {attempt} tries, no connection", "suggested_message": "",
            "description": f"{first} {verb} again at {stamp}. That's {attempt} misses in a row. Send a text or park this one; auto-retries have stopped.",
            "action_type": "manual", "priority": "medium", "priority_order": 2, "status": "pending", "completed": False,
            "due_date": due_utc, "has_time": True, "appointment_type": "task", "reminded_15": False, "reminded_due": False,
            "completed_at": None, "snoozed_until": None, "campaign_id": None, "campaign_name": None, "pending_send_id": None,
            "channel": "", "conversation_id": conversation_id, "created_at": now,
        })
        task_id = str(res.inserted_id)

    await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"call_retry": {
        "attempts": attempt, "last_at": now, "last_outcome": outcome, "next_due": due_utc, "task_id": task_id}}})

    title = "Left voicemail" if outcome == "voicemail" else ("Line busy" if outcome == "busy" else "No answer")
    await db.contact_events.insert_one({
        "event_type": f"call_{outcome}", "title": title, "user_id": user_id, "contact_id": contact_id,
        "description": (f"Retry set for {label} (miss #{attempt})" if task_id and attempt <= max_auto
                        else f"Miss #{attempt}. Auto-retries stopped." if attempt > max_auto else f"Miss #{attempt}"),
        "category": "call", "icon": "call", "color": "#FF9F0A", "call_sid": call_sid, "source": source,
        "timestamp": now, "created_at": now,
    })
    if task_id:
        push_title = f"{first} {verb}"
        push_body = (f"Try again {label} · miss #{attempt}" if attempt <= max_auto
                     else f"{attempt} misses. Text or park? Task added for {label}.")
        try:
            from routers.push_notifications import send_push_to_user
            asyncio.create_task(send_push_to_user(user_id, push_title, push_body, f"/contact/{contact_id}?taskId={task_id}", "call"))
        except Exception:
            pass
        await db.notifications.insert_one({
            "user_id": user_id, "type": "call_retry_scheduled", "title": push_title, "message": push_body,
            "contact_id": contact_id, "task_id": task_id, "conversation_id": conversation_id,
            "read": False, "dismissed": False, "created_at": now})
    logger.info(f"[CallFollowup] {contact_id} {outcome} (miss #{attempt}, {source}) -> task {task_id} due {due_utc}")
    return {"applied": True, "outcome": outcome, "attempt": attempt, "task_id": task_id, "due": due_utc.isoformat() if due_utc else None, "label": label}


async def on_customer_replied(user_id: str, contact_id: str, conversation_id: str | None, body: str) -> dict:
    """Customer texted back while a retry task was open: close the retry, drop any queued "just tried" text, ping the rep."""
    db = get_db()
    if not user_id or not ObjectId.is_valid(contact_id):
        return {"closed": 0}
    open_tasks = await db.tasks.find({"user_id": user_id, "contact_id": contact_id, "completed": {"$ne": True},
                                      "auto_kind": {"$in": ["call_retry", "call_retry_final"]}}).to_list(10)
    if not open_tasks:
        return {"closed": 0}
    now = datetime.now(timezone.utc)
    ids = [t["_id"] for t in open_tasks]
    preview = (body or "").strip().replace("\n", " ")[:100]
    await db.tasks.update_many({"_id": {"$in": ids}}, {"$set": {
        "status": "completed", "completed": True, "completed_at": now, "completed_via": "customer_replied",
        "completed_reply": preview, "updated_at": now}})
    cancelled = await db.campaign_pending_sends.update_many(
        {"task_id": {"$in": [str(i) for i in ids]}, "type": "direct_scheduled", "status": "pending"},
        {"$set": {"status": "cancelled", "cancel_reason": "customer_replied", "cancelled_at": now}})
    await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$set": {"call_retry": None}})
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "name": 1}) or {}
    first = (contact.get("first_name") or (contact.get("name") or "").split(" ")[0] or "They").strip()
    just_tried = any(t.get("just_tried_sent_at") for t in open_tasks)
    title = f"{first} replied to your just-tried text" if just_tried else f"{first} texted back after your voicemail"
    push_body = (f"\"{preview}\" · retry task closed" if preview else "Retry task closed, reply in the thread")
    link = f"/thread/{conversation_id}" if conversation_id else f"/contact/{contact_id}"
    await db.contact_events.insert_one({
        "event_type": "call_retry_replied", "title": title, "user_id": user_id, "contact_id": contact_id,
        "description": f"Closed {len(ids)} retry task(s)" + (f", cancelled {cancelled.modified_count} queued text" if cancelled.modified_count else "") + ". Keep it going by text.",
        "category": "call", "icon": "chatbubble-ellipses", "color": "#34C759", "timestamp": now, "created_at": now})
    await db.notifications.insert_one({
        "user_id": user_id, "type": "call_retry_replied", "title": title, "message": push_body, "contact_id": contact_id,
        "contact_name": contact.get("name") or first, "conversation_id": conversation_id or "", "task_id": str(ids[0]),
        "read": False, "dismissed": False, "created_at": now})
    try:
        from routers.push_notifications import send_push_to_user
        asyncio.create_task(send_push_to_user(user_id, title, push_body, link, "chatbubble-ellipses"))
    except Exception:
        pass
    logger.info(f"[CallFollowup] {contact_id} texted back: closed {len(ids)} retry task(s), cancelled {cancelled.modified_count} queued text(s)")
    return {"closed": len(ids), "cancelled_texts": cancelled.modified_count, "just_tried": just_tried}


async def record_manual_outcome(user_id: str, contact_id: str, outcome: str, duration_s: int = 0,
                                conversation_id: str = "", task_id: str = "") -> dict:
    """Native-dialer calls: the rep tells us how it went."""
    stub = {"rep_user_id": user_id, "contact_id": contact_id, "conversation_id": conversation_id or None,
            "task_id": task_id or None, "call_sid": f"manual-{int(datetime.now(timezone.utc).timestamp())}"}
    return await apply_call_outcome(stub, outcome, duration_s, source="manual")


async def just_tried_template(db, user_id: str, conversation: dict | None) -> tuple[str, str]:
    """Lead-source workflow text -> rep/team cadence text -> built-in. Returns (template, source_label)."""
    sid = str((conversation or {}).get("lead_source_id") or "")
    if ObjectId.is_valid(sid):
        src = await db.lead_sources.find_one({"_id": ObjectId(sid)}, {"just_tried_text": 1, "name": 1})
        if src and (src.get("just_tried_text") or "").strip():
            return src["just_tried_text"].strip(), f"{src.get('name') or 'lead source'} workflow"
    cad = await cadence_for(user_id)
    if cad.get("just_tried_text"):
        return cad["just_tried_text"], "your retry settings"
    return DEFAULT_JUST_TRIED, "default"


async def send_just_tried_text(user_id: str, task_id: str) -> dict:
    """One tap from a retry task: text the customer now if inside texting hours, else queue it for when the window opens."""
    from services.lead_timing import window_status, customer_timezone, store_timezone
    db = get_db()
    if not ObjectId.is_valid(task_id):
        return {"ok": False, "error": "Bad task id"}
    task = await db.tasks.find_one({"_id": ObjectId(task_id), "user_id": user_id})
    if not task:
        return {"ok": False, "error": "Task not found"}
    contact_id = str(task.get("contact_id") or "")
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}) if ObjectId.is_valid(contact_id) else None
    if not contact:
        return {"ok": False, "error": "Contact not found"}
    phone = contact.get("phone") or task.get("contact_phone")
    if not phone:
        return {"ok": False, "error": "No phone number on file"}
    if contact.get("opted_out") or contact.get("sms_consent_status") == "opted_out" or contact.get("do_not_text"):
        return {"ok": False, "error": "This contact opted out of texts"}

    conv = None
    if task.get("conversation_id") and ObjectId.is_valid(str(task["conversation_id"])):
        conv = await db.conversations.find_one({"_id": ObjectId(str(task["conversation_id"]))})
    if not conv:
        conv = await db.conversations.find_one({"contact_id": contact_id, "user_id": user_id}) or \
               await db.conversations.find_one({"contact_id": contact_id})
    template, template_source = await just_tried_template(db, user_id, conv)

    # texting hours: the lead source window if there is one, else the default window, in the customer's local time
    src = None
    sid = str((conv or {}).get("lead_source_id") or "")
    if ObjectId.is_valid(sid):
        src = await db.lead_sources.find_one({"_id": ObjectId(sid)}, {"text_window_start": 1, "text_window_end": 1})
    store = None
    store_sid = str(contact.get("store_id") or (conv or {}).get("store_id") or "")
    if ObjectId.is_valid(store_sid):
        store = await db.stores.find_one({"_id": ObjectId(store_sid)}, {"timezone": 1})
    tz_name = customer_timezone(phone, store_timezone(store or {}))
    win = window_status(src or {}, tz_name)
    now = datetime.now(timezone.utc)
    first = (contact.get("first_name") or (contact.get("name") or "").split(" ")[0] or "there").strip()

    if win["inside"]:
        from routers.messages import send_message_simple
        payload = {"content": template, "contact_id": contact_id, "channel": "sms"}
        if conv and str(conv.get("user_id")) == user_id:
            payload["conversation_id"] = str(conv["_id"])
        try:
            res = await send_message_simple(user_id, payload)
        except Exception as e:  # HTTPException or Twilio failure
            detail = getattr(e, "detail", None) or str(e)
            return {"ok": False, "error": f"Could not send: {detail}"}
        if (res or {}).get("status") == "failed":
            return {"ok": False, "error": f"Text failed: {(res or {}).get('error') or 'carrier rejected the number'}"}
        await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"just_tried_sent_at": now, "just_tried_text": template}})
        await db.contact_events.insert_one({
            "event_type": "just_tried_text", "title": "\"Just tried you\" text sent", "user_id": user_id, "contact_id": contact_id,
            "description": f"After voicemail: {template[:120]}", "category": "sms", "icon": "chatbubble", "color": "#34C759",
            "timestamp": now, "created_at": now})
        return {"ok": True, "sent": True, "scheduled_for": None, "template_source": template_source,
                "message_id": (res or {}).get("message_id") or (res or {}).get("_id"), "preview": template.replace("{first_name}", first)}

    # outside the window: queue for when it opens (scheduler drains campaign_pending_sends every few minutes)
    opens = win["opens_at"]
    rep = await db.users.find_one({"_id": ObjectId(user_id)}, {"twilio_number": 1, "mvpline_number": 1, "name": 1})
    try:
        from routers.messages import substitute_template_vars
        template = await substitute_template_vars(template, user_id, contact_id)   # {sender_name}/{company} resolved now; scheduler handles the rest
    except Exception:
        pass
    await db.campaign_pending_sends.insert_one({
        "user_id": user_id, "contact_id": contact_id, "contact_name": contact.get("name") or first, "contact_phone": phone,
        "rep_phone": (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number"),
        "message_template": template, "channel": "sms", "delivery_mode": "automated",
        "send_at": opens.replace(tzinfo=None), "status": "pending", "step": 0, "enrollment_id": "", "campaign_id": "",
        "campaign_name": "Just tried you", "media_urls": [], "event_type": "just_tried_text", "created_at": now,
        "type": "direct_scheduled", "task_id": task_id,
    })
    await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"just_tried_scheduled_for": opens, "just_tried_text": template}})
    from zoneinfo import ZoneInfo
    local = opens.astimezone(ZoneInfo(tz_name))
    label = local.strftime("%-I:%M %p") + ("" if local.date() == now.astimezone(ZoneInfo(tz_name)).date() else local.strftime(" %a"))
    await db.contact_events.insert_one({
        "event_type": "just_tried_text", "title": "\"Just tried you\" text scheduled", "user_id": user_id, "contact_id": contact_id,
        "description": f"Outside texting hours ({win['start']}-{win['end']} their time). Sends at {label}.", "category": "sms",
        "icon": "time", "color": "#FF9F0A", "timestamp": now, "created_at": now})
    return {"ok": True, "sent": False, "scheduled_for": opens.isoformat(), "scheduled_label": label, "template_source": template_source,
            "window": f"{win['start']}-{win['end']}", "preview": template.replace("{first_name}", first)}
