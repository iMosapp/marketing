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

MAX_AUTO_RETRIES = 4
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


def _at(d: datetime, hour: int) -> datetime:
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def _next_business_morning(local: datetime) -> datetime:
    d = _at(local + timedelta(days=1), 10)
    while d.weekday() == 6:  # dealers work Saturdays; skip Sundays only
        d += timedelta(days=1)
    return d


def next_retry_due(attempt: int, now_utc: datetime, tz: ZoneInfo) -> datetime:
    local = now_utc.astimezone(tz)
    if attempt == 1:
        due = local + timedelta(minutes=30)
        if due.hour >= 20 or due.hour < 8:
            due = _next_business_morning(local)
    elif attempt == 2:
        due = local + timedelta(hours=3)
        if due.hour >= 19 or due.hour < 8:
            due = _next_business_morning(local)
    elif attempt == 3:
        due = _next_business_morning(local)
    elif attempt == 4:
        due = _at(local + timedelta(days=2), 10)
        while due.weekday() == 6:
            due += timedelta(days=1)
    else:
        due = _next_business_morning(local)
    return due.astimezone(timezone.utc)


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
    state = contact.get("call_retry") or {}
    last_at = state.get("last_at")
    if isinstance(last_at, datetime) and last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    attempt = (int(state.get("attempts") or 0) + 1) if (isinstance(last_at, datetime) and now - last_at < timedelta(days=7)) else 1
    verb = OUTCOME_LABEL.get(outcome, "didn't answer")
    stamp = now.astimezone(tz).strftime("%-I:%M %p")
    conversation_id = pending.get("conversation_id") or None

    task_id, due_utc, label = None, None, ""
    if attempt <= MAX_AUTO_RETRIES:
        due_utc = next_retry_due(attempt, now, tz)
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
    elif attempt == MAX_AUTO_RETRIES + 1:
        due_utc = next_retry_due(attempt, now, tz)
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
        "description": (f"Retry set for {label} (miss #{attempt})" if task_id and attempt <= MAX_AUTO_RETRIES
                        else f"Miss #{attempt}. Auto-retries stopped." if attempt > MAX_AUTO_RETRIES else f"Miss #{attempt}"),
        "category": "call", "icon": "call", "color": "#FF9F0A", "call_sid": call_sid, "source": source,
        "timestamp": now, "created_at": now,
    })
    if task_id:
        push_title = f"{first} {verb}"
        push_body = (f"Try again {label} · miss #{attempt}" if attempt <= MAX_AUTO_RETRIES
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


async def record_manual_outcome(user_id: str, contact_id: str, outcome: str, duration_s: int = 0,
                                conversation_id: str = "", task_id: str = "") -> dict:
    """Native-dialer calls: the rep tells us how it went."""
    stub = {"rep_user_id": user_id, "contact_id": contact_id, "conversation_id": conversation_id or None,
            "task_id": task_id or None, "call_sid": f"manual-{int(datetime.now(timezone.utc).timestamp())}"}
    return await apply_call_outcome(stub, outcome, duration_s, source="manual")
