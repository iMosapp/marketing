"""Reschedule-from-reply: a customer with an upcoming appointment texts "can we do 3 instead" / "can't make it".
Jessi works out the new time against the existing appointment and the REP approves with one tap
(the app never lets AI lock in a time on the dealer's behalf). Approval moves the task and fires the
calendar update text; a cancel takes it off the books and tells the customer."""
import os
import re
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from zoneinfo import ZoneInfo

from routers.database import get_db
from services.calendar_invite import (INVITE_TYPES, load_context, user_tz, when_label, send_calendar_invite,
                                      _text_customer, _utc)

logger = logging.getLogger(__name__)

CHANGE_HINT = re.compile(
    r"\binstead\b|\bmove\b|\bpush\b|\bbump\b|\bchange\b|\bswitch\b|\blater\b|\bearlier\b|\brunning\b|\blate\b|\bbehind\b"
    r"|\bcan'?t make\b|\bcannot make\b|\bwon'?t make\b|\bnot (gonna|going to) make\b|\bcancel\b|\breschedul"
    r"|\b(different|another|new|other) (time|day)\b|\bmake it\b|\bdo \d{1,2}\b|\bat \d{1,2}\b|\bsomething came up\b"
    r"|\bpostpone\b|\bstill on\b|\bconflict\b|\bmeeting ran\b|\bstuck (at|in)\b",
    re.I,
)

_PROMPT = (
    "A customer has an existing appointment with their sales rep and just sent ONE text. Decide if they are asking to "
    "change it. Return ONLY strict JSON: {\"action\": \"reschedule|cancel|none\", \"local_datetime\": \"YYYY-MM-DDTHH:MM\" or null, "
    "\"confidence\": 0-1, \"summary\": short plain English}. "
    "Rules: resolve times RELATIVE to the existing appointment. 'can we do 3 instead' -> same day 15:00 (pick AM/PM so the new time "
    "is a normal business hour, 8:00-19:00, closest to the existing time). 'push it to Friday' or 'tomorrow' with no time -> same clock time on that day. "
    "'an hour later' / 'running 20 min late' -> shift the existing time. 'can't make it', 'need to cancel', 'something came up, have to bail' -> cancel. "
    "'can we do another day?' with no specific day -> action reschedule with local_datetime null. "
    "'are we still on for 2?', 'see you at 2', confirmations, unrelated chatter, or questions about inventory -> none. "
    "Never invent a time that is not implied. If the named day already passed, use the next occurrence."
)


def _fmt(dt_utc: datetime, tz: ZoneInfo) -> str:
    return dt_utc.astimezone(tz).strftime("%a, %b %-d at %-I:%M %p")


async def _upcoming_appointment(db, user_id: str, contact_id: str) -> dict | None:
    now = datetime.now(timezone.utc)
    return await db.tasks.find_one({
        "user_id": user_id, "contact_id": str(contact_id), "appointment_type": {"$in": list(INVITE_TYPES)},
        "has_time": True, "completed": {"$ne": True}, "status": {"$nin": ["completed", "dismissed"]},
        "due_date": {"$gte": now - timedelta(hours=1), "$lte": now + timedelta(days=45)},
    }, sort=[("due_date", 1)])


async def detect_appointment_change(user_id: str, contact_id: str, conversation_id: str, text: str, message_id: str = "") -> dict | None:
    """Returns the created change request, or None when the text is not about the appointment."""
    text = (text or "").strip()
    if not text or len(text) > 600 or not user_id or not contact_id:
        return None
    db = get_db()
    task = await _upcoming_appointment(db, user_id, contact_id)
    if not task:
        return None
    from routers.tasks import text_has_schedule_hint
    if not (CHANGE_HINT.search(text) or text_has_schedule_hint(text)):
        return None
    if message_id and await db.appointment_changes.find_one({"message_id": message_id}, {"_id": 1}):
        return None

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"timezone": 1, "store_id": 1, "name": 1})
    tz = await user_tz(db, user or {})
    now_local = datetime.now(tz)
    appt_local = _utc(task["due_date"]).astimezone(tz)
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY", ""), session_id=f"resched-{uuid.uuid4().hex[:12]}",
                       system_message=_PROMPT).with_model("openai", "gpt-5.2")
        resp = await asyncio.wait_for(chat.send_message(UserMessage(text=(
            f"Current local datetime: {now_local.strftime('%A %Y-%m-%dT%H:%M')}\n"
            f"Existing appointment: {appt_local.strftime('%A %Y-%m-%dT%H:%M')}\n"
            f"Customer text: {text}"
        ))), timeout=25.0)
        out = resp if isinstance(resp, str) else getattr(resp, "text", str(resp))
        data = json.loads(out[out.find("{"):out.rfind("}") + 1])
    except Exception as e:
        logger.warning(f"[Reschedule] LLM failed for msg {message_id}: {e}")
        return None

    action = (data.get("action") or "none").lower()
    if action not in ("reschedule", "cancel") or float(data.get("confidence") or 0) < 0.5:
        return None
    new_due = None
    if action == "reschedule" and data.get("local_datetime"):
        try:
            naive = datetime.fromisoformat(str(data["local_datetime"])[:16])
            new_due = naive.replace(tzinfo=tz).astimezone(timezone.utc)
        except Exception:
            new_due = None
        if new_due and new_due < datetime.now(timezone.utc):
            return None
        if new_due and abs((new_due - _utc(task["due_date"])).total_seconds()) < 60:
            return None

    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1, "name": 1})
    first = ((contact or {}).get("first_name") or ((contact or {}).get("name") or "").split(" ")[0] or "Customer").strip()
    old_label = _fmt(_utc(task["due_date"]), tz)
    new_label = _fmt(new_due, tz) if new_due else None
    if action == "cancel":
        title, body = f"{first} can't make {old_label}", "Tap to take it off the books and let them know, or reply yourself."
    elif new_due:
        title, body = f"{first} wants to move {old_label} to {new_label}", "Tap to approve and send the calendar update."
    else:
        title, body = f"{first} wants a different time for {old_label}", "No specific time given. Tap to reply with options."

    change = {
        "task_id": str(task["_id"]), "user_id": user_id, "contact_id": str(contact_id), "conversation_id": conversation_id,
        "message_id": message_id, "action": action, "old_due": _utc(task["due_date"]), "new_due": new_due,
        "old_label": old_label, "new_label": new_label, "customer_text": text[:300], "summary": (data.get("summary") or "")[:200],
        "contact_first": first, "status": "pending", "created_at": datetime.now(timezone.utc),
    }
    change["_id"] = (await db.appointment_changes.insert_one(change)).inserted_id
    await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"pending_change_id": str(change["_id"])}})
    if ObjectId.is_valid(conversation_id):
        await db.conversations.update_one({"_id": ObjectId(conversation_id)},
                                          {"$set": {"needs_assistance": True, "you_are_needed_at": datetime.utcnow()}})
    await db.notifications.insert_one({
        "user_id": user_id, "type": "appointment_change", "priority": "urgent", "title": title, "message": body,
        "contact_id": str(contact_id), "conversation_id": conversation_id, "change_id": str(change["_id"]),
        "read": False, "dismissed": False, "created_at": datetime.utcnow(),
    })
    try:
        from routers.push_notifications import send_push_to_user
        asyncio.create_task(send_push_to_user(user_id, title, body, f"/thread/{conversation_id}", "calendar"))
    except Exception as e:
        logger.warning(f"[Reschedule] push failed: {e}")
    logger.info(f"[Reschedule] {action} request for task {task['_id']}: {old_label} -> {new_label}")
    return serialize_change(change)


def serialize_change(c: dict) -> dict:
    out = {k: v for k, v in c.items() if k != "_id"}
    out["id"] = str(c["_id"])
    for k in ("old_due", "new_due", "created_at", "resolved_at"):
        if isinstance(out.get(k), datetime):
            out[k] = _utc(out[k]).isoformat()
    return out


async def _drop_held_drafts(db, conversation_id: str, user_id: str):
    """The calendar update IS the reply; kill Jessi's held draft so the customer doesn't get two texts."""
    await db.ai_reply_queue.update_many(
        {"conversation_id": conversation_id, "status": {"$in": ["pending", "approved"]}},
        {"$set": {"status": "cancelled", "cancel_reason": "appointment_change_approved", "updated_at": datetime.utcnow()}})
    await db.notifications.update_many(
        {"conversation_id": conversation_id, "type": {"$in": ["you_are_needed", "appointment_change"]}, "dismissed": {"$ne": True}},
        {"$set": {"dismissed": True, "read": True}})
    if ObjectId.is_valid(conversation_id):
        await db.conversations.update_one({"_id": ObjectId(conversation_id)}, {"$set": {"needs_assistance": False}})


async def approve_change(change_id: str, user_id: str, new_due_iso: str | None = None) -> dict:
    db = get_db()
    change = await db.appointment_changes.find_one({"_id": ObjectId(change_id), "user_id": user_id})
    if not change:
        raise ValueError("Change request not found")
    if change.get("status") != "pending":
        raise ValueError("This request was already handled")
    task = await db.tasks.find_one({"_id": ObjectId(change["task_id"])})
    if not task:
        raise ValueError("That appointment no longer exists")
    ctx = await load_context(db, task)
    result = {"sent": False}

    if change["action"] == "cancel":
        body = None
        if ctx:
            body = (f"No problem {ctx['first']}, I've taken {when_label(ctx)} off the books. "
                    f"Text me when you'd like to grab another time.")
        await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"status": "dismissed", "dismissed_at": datetime.utcnow(),
                                                              "dismiss_reason": "customer_cancelled"}, "$unset": {"pending_change_id": ""}})
        if ctx and body:
            res = await _text_customer(db, ctx, body, "appointment_cancelled")
            result = {"sent": bool(res.get("success")), "text": body}
    else:
        new_due = None
        if new_due_iso:
            new_due = datetime.fromisoformat(new_due_iso.replace("Z", "+00:00"))
            new_due = new_due.astimezone(timezone.utc) if new_due.tzinfo else new_due.replace(tzinfo=timezone.utc)
        new_due = new_due or (change.get("new_due") and _utc(change["new_due"]))
        if not new_due:
            raise ValueError("Pick the new time first")
        await db.tasks.update_one({"_id": task["_id"]}, {
            "$set": {"due_date": new_due, "has_time": True, "reminded_15": False, "reminded_due": False, "updated_at": datetime.utcnow()},
            "$unset": {"pending_change_id": "", "customer_reminder_sent_at": "", "customer_reminder_skipped": "", "customer_reminder_status": ""}})
        inv = await send_calendar_invite(str(task["_id"]), reason="updated", force=True)
        result = {"sent": bool(inv.get("sent")), "channels": inv.get("channels", []), "when": inv.get("when")}
        change["new_due"] = new_due

    await _drop_held_drafts(db, change["conversation_id"], user_id)
    await db.appointment_changes.update_one({"_id": change["_id"]}, {"$set": {
        "status": "approved", "resolved_at": datetime.now(timezone.utc), "new_due": change.get("new_due"), "result": result}})
    return {"success": True, "action": change["action"], **result}


async def decline_change(change_id: str, user_id: str) -> dict:
    db = get_db()
    change = await db.appointment_changes.find_one({"_id": ObjectId(change_id), "user_id": user_id})
    if not change:
        raise ValueError("Change request not found")
    await db.appointment_changes.update_one({"_id": change["_id"]}, {"$set": {"status": "declined", "resolved_at": datetime.now(timezone.utc)}})
    await db.tasks.update_one({"_id": ObjectId(change["task_id"])}, {"$unset": {"pending_change_id": ""}})
    await db.notifications.update_many({"change_id": change_id, "dismissed": {"$ne": True}}, {"$set": {"dismissed": True, "read": True}})
    return {"success": True}


async def list_changes(user_id: str, *, conversation_id: str | None = None, contact_id: str | None = None,
                       status: str = "pending", limit: int = 20) -> list:
    db = get_db()
    q: dict = {"user_id": user_id, "status": status}
    if conversation_id:
        q["conversation_id"] = conversation_id
    if contact_id:
        q["contact_id"] = str(contact_id)
    rows = await db.appointment_changes.find(q).sort("created_at", -1).limit(limit).to_list(limit)
    return [serialize_change(r) for r in rows]
