"""Recorded conversation -> plain summary + every commitment made on the lot -> tasks on the rep's list, so nothing promised slips."""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from bson import ObjectId

from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MODEL = ("openai", "gpt-5.2")
MAX_TASKS = 5
ACTION_TYPE = {"call": "call", "text": "text", "email": "email", "appointment": "appointment", "task": "manual"}
TASK_TYPE = {"call": "call", "appointment": "appointment"}


def _json(raw: str) -> dict:
    t = (raw or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except Exception:
            return {}


def _prompt(contact_name: str, rep_first: str, now_local: datetime, tz: str, existing: list) -> str:
    existing_block = ("\n\nEXISTING OPEN TASKS for this customer (id: title):\n" + "\n".join(f"- {t['id']}: {t['title']}" for t in existing)
                      + "\nIf a commitment is already covered by one of these, set \"existing_task_id\" to that id instead of proposing a new task.") if existing else ""
    return (
        f"You review a recorded in-person dealership conversation between salesperson {rep_first} and customer {contact_name}. "
        f"Right now it is {now_local.strftime('%A, %B %-d %Y, %-I:%M %p')} in {tz}.\n\n"
        "Return ONLY valid JSON:\n"
        "{\"title\": \"2 to 5 word label for this conversation, like a rep would name it: vehicle or topic + setting (e.g. Tahoe walk-around, Trade talk on the Explorer, Delivery day)\",\n"
        " \"summary\": \"3 or 4 plain sentences: what the customer wants, objections or concerns, what was agreed, next steps\",\n"
        " \"commitments\": [{\"title\": \"short action for the salesperson, imperative, under 60 characters\", "
        "\"detail\": \"one sentence with the exact promise or the customer's words\", "
        "\"due_at\": \"ISO 8601 datetime with timezone offset when a day or time was said or clearly implied, else null\", "
        "\"has_time\": true when a clock time was said or implied (e.g. 'around ten', 'after lunch'), false when only a day is known, "
        "\"action\": \"call|text|email|appointment|task\", \"existing_task_id\": \"id of an existing open task that already covers this, else null\"}]}\n\n"
        "RULES:\n"
        f"- Capture every promise {rep_first} made (numbers to send, calls to make, cars to locate, paperwork) AND everything the customer said they would do, "
        "phrased as a check-in for the salesperson (e.g. 'Confirm Mike sent his insurance card').\n"
        "- Skip pleasantries and vague talk. Most important first. At most 5.\n"
        "- Resolve relative dates ('Saturday', 'tomorrow', 'next week', 'end of the month') against today's date and timezone. When only a day is known, use 10:00 that day.\n"
        "- Appointments the customer agreed to come in for are action 'appointment' with the agreed time.\n"
        "- Plain dealership language. Never use em dashes or en dashes."
        + existing_block
    )


async def analyze_conversation(transcript: str, contact_name: str, rep_first: str, tz: str, existing: list | None = None) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key or len((transcript or "").strip()) < 40:
        return {"title": "", "summary": "", "commitments": []}
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    now_local = datetime.now(ZoneInfo(tz))
    chat = LlmChat(api_key=api_key, session_id=f"convo-hl-{uuid.uuid4().hex[:8]}", system_message=_prompt(contact_name, rep_first, now_local, tz, existing or [])).with_model(*MODEL)
    resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"TRANSCRIPT:\n{transcript[:24000]}")), timeout=75)
    data = _json(resp if isinstance(resp, str) else getattr(resp, "text", "") or "")
    out = []
    for c in (data.get("commitments") or [])[:MAX_TASKS]:
        title = no_em_dash(str(c.get("title") or "")).strip().rstrip(".")[:80]
        if len(title) < 4:
            continue
        out.append({"title": title, "detail": no_em_dash(str(c.get("detail") or "")).strip()[:300], "due_at": c.get("due_at") or None,
                    "has_time": bool(c.get("has_time")), "action": c.get("action") if c.get("action") in ACTION_TYPE else "task",
                    "existing_task_id": str(c.get("existing_task_id") or "") or None})
    return {"title": no_em_dash(str(data.get("title") or "")).strip().strip('"').rstrip(".")[:40],
            "summary": no_em_dash(str(data.get("summary") or "")).strip()[:1500], "commitments": out}


def _due(raw, has_time: bool, tz: str) -> tuple[datetime, bool]:
    """Commitment time in UTC; falls back to tomorrow 10:00 local when the model gave nothing usable."""
    now = datetime.now(timezone.utc)
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
        if d and not d.tzinfo:
            d = d.replace(tzinfo=ZoneInfo(tz))
    except Exception:
        d = None
    if d and d > now - timedelta(hours=1):
        return d.astimezone(timezone.utc), has_time
    local = now.astimezone(ZoneInfo(tz))
    return (local + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).astimezone(timezone.utc), False


async def process_recorded_conversation(db, user_id: str, contact_id: str, note_id: str, transcript: str) -> dict:
    """Summarize, then turn each commitment into a pending task (deduped by title) and stamp the highlights on the voice note."""
    from routers.user_schedule import resolve_user_tz
    tz = await resolve_user_tz(user_id)
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"name": 1, "first_name": 1, "last_name": 1, "phone": 1}) if ObjectId.is_valid(contact_id) else None
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"first_name": 1, "name": 1}) if ObjectId.is_valid(user_id) else None
    contact_name = (contact or {}).get("name") or f"{(contact or {}).get('first_name', '')} {(contact or {}).get('last_name', '')}".strip() or "the customer"
    rep_first = (user or {}).get("first_name") or ((user or {}).get("name") or "the salesperson").split(" ")[0]
    open_q = {"user_id": user_id, "contact_id": contact_id, "completed": {"$ne": True}, "status": {"$in": ["pending", "snoozed", None]}}
    existing = [{"id": str(t["_id"]), "title": t.get("title") or ""} for t in await db.tasks.find(open_q, {"title": 1}).sort("due_date", 1).limit(20).to_list(20)]
    existing_ids = {t["id"] for t in existing}
    try:
        analysis = await analyze_conversation(transcript, contact_name, rep_first, tz, existing)
    except Exception as e:
        logger.warning(f"[RecordingHighlights] analysis failed for note {note_id}: {e}")
        analysis = {"title": "", "summary": "", "commitments": []}

    now = datetime.now(timezone.utc)
    when = now.astimezone(ZoneInfo(tz)).strftime("%b %-d")
    tasks, highlights = [], []
    for c in analysis["commitments"]:
        due, has_time = _due(c["due_at"], c["has_time"], tz)
        norm = re.sub(r"\W+", " ", c["title"].lower()).strip()
        dup = {"_id": ObjectId(c["existing_task_id"])} if c["existing_task_id"] in existing_ids else await db.tasks.find_one({**open_q, "title_norm": norm})
        hl = {"title": c["title"], "detail": c["detail"], "due_date": due, "has_time": has_time, "action": c["action"], "task_id": str(dup["_id"]) if dup else None}
        if not dup:
            doc = {"user_id": user_id, "contact_id": contact_id, "contact_name": contact_name, "contact_phone": (contact or {}).get("phone", ""),
                   "type": TASK_TYPE.get(c["action"], "follow_up"), "source": "recorded_conversation", "auto_kind": "recording_highlight", "voice_note_id": note_id,
                   "title": c["title"], "title_norm": norm, "description": f"Promised in your recorded conversation on {when}: {c['detail']}" if c["detail"] else f"From your recorded conversation on {when}",
                   "suggested_message": "", "action_type": ACTION_TYPE[c["action"]], "priority": "high", "priority_order": 1, "status": "pending", "completed": False,
                   "due_date": due, "has_time": has_time, "appointment_type": c["action"] if c["action"] in ("call", "appointment") else "task",
                   "reminded_15": False, "reminded_due": False, "completed_at": None, "snoozed_until": None, "campaign_id": None, "campaign_name": None,
                   "pending_send_id": None, "channel": "", "created_at": now}
            res = await db.tasks.insert_one(doc)
            hl["task_id"] = str(res.inserted_id)
            tasks.append({"id": hl["task_id"], "title": c["title"], "due_date": due.isoformat(), "has_time": has_time, "action": c["action"]})
        highlights.append(hl)

    await db.voice_notes.update_one({"_id": ObjectId(note_id)}, {"$set": {"summary": analysis["summary"], "highlights": highlights, "highlights_at": now}})
    if analysis["title"]:
        await db.voice_notes.update_one({"_id": ObjectId(note_id), "title": {"$in": [None, ""]}}, {"$set": {"title": analysis["title"]}})  # never overwrite a rep's own name
    if tasks:
        await db.contact_events.insert_one({
            "contact_id": contact_id, "user_id": user_id, "event_type": "recording_highlights", "channel": "system", "category": "task",
            "title": f"{len(tasks)} follow-up{'s' if len(tasks) != 1 else ''} pulled from your recorded conversation",
            "description": "; ".join(t["title"] for t in tasks)[:300], "icon": "checkbox", "color": "#C9A962",
            "metadata": {"voice_note_id": note_id, "task_ids": [t["id"] for t in tasks]}, "timestamp": now, "created_at": now})
    logger.info(f"[RecordingHighlights] note {note_id}: {len(highlights)} commitments, {len(tasks)} new tasks")
    return {"title": analysis["title"], "summary": analysis["summary"], "highlights": [{**h, "due_date": h["due_date"].isoformat()} for h in highlights], "tasks": tasks}


# ---------------------------------------------------------------- Highlight Nudge: the moment a recorded promise comes due
NUDGE_WINDOW_HOURS = 6


def _fallback_draft(first: str, title: str, action: str) -> str:
    t = title[:1].lower() + title[1:] if title else "what we talked about"
    if action == "appointment":
        return f"Hi {first}, looking forward to seeing you today. Everything is set on my end, text me if anything changes."
    return f"Hi {first}, following up on what we talked about: {t}. Quick update coming your way, let me know if anything has changed on your side."


async def draft_nudge_text(task: dict, first: str, rep_first: str, tz: str) -> str:
    """The text the rep sends to keep the promise (gpt-5.2, plain fallback)."""
    title, detail, action = task.get("title") or "", task.get("description") or "", task.get("action_type") or "text"
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return _fallback_draft(first, title, action)
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        due = task.get("due_date")
        if due and not due.tzinfo:
            due = due.replace(tzinfo=timezone.utc)
        when = due.astimezone(ZoneInfo(tz)).strftime("%A %-I:%M %p") if due else "now"
        chat = LlmChat(api_key=api_key, session_id=f"nudge-{uuid.uuid4().hex[:8]}",
                       system_message=(f"You write the one text message car salesperson {rep_first} sends customer {first} right now to keep a promise made in person. "
                                       "The promise is due right now, so the text delivers it or moves it forward today (never repeat the original deadline like 'by tomorrow', never say 'keeping my promise'). "
                                       "Under 300 characters, warm and plain, first name once, specific to the promise. If a number or detail is not known, say you are pulling it together now and ask what you need, "
                                       "never invent figures and never use placeholders in brackets. No greeting longer than 'Hi {first},', no sign-off, no em dashes or en dashes. Return only the text.")).with_model(*MODEL)
        resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"Promise: {title}\nWhat was said: {detail}\nKind: {action}\nDue: {when}")), timeout=40)
        text = no_em_dash((resp if isinstance(resp, str) else getattr(resp, "text", "") or "").strip().strip('"'))
        text = re.sub(r"\[[^\]]*\]", "", text).strip()
        return text[:320] if len(text) > 15 else _fallback_draft(first, title, action)
    except Exception as e:
        logger.warning(f"[HighlightNudge] draft failed for task {task.get('_id')}: {e}")
        return _fallback_draft(first, title, action)


async def send_highlight_nudges(db) -> int:
    """Every minute: recorded-conversation promises that just came due -> push + alert with a one-tap draft text to the customer."""
    from routers.push_notifications import send_push_to_user
    from routers.user_schedule import resolve_user_tz
    from urllib.parse import quote
    now = datetime.now(timezone.utc)
    due = await db.tasks.find({"auto_kind": "recording_highlight", "completed": {"$ne": True}, "status": {"$nin": ["completed", "dismissed", "cancelled"]},
                               "nudged_at": {"$exists": False}, "due_date": {"$lte": now, "$gte": now - timedelta(hours=NUDGE_WINDOW_HOURS)}}).limit(25).to_list(25)
    sent = 0
    for t in due:
        user_id, contact_id = str(t.get("user_id") or ""), str(t.get("contact_id") or "")
        if not user_id or not contact_id:
            continue
        # claim first so two workers never nudge twice
        claimed = await db.tasks.update_one({"_id": t["_id"], "nudged_at": {"$exists": False}}, {"$set": {"nudged_at": now, "reminded_due": True}})
        if not claimed.modified_count:
            continue
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "name": 1, "last_name": 1}) if ObjectId.is_valid(contact_id) else None
            user = await db.users.find_one({"_id": ObjectId(user_id)}, {"first_name": 1, "name": 1}) if ObjectId.is_valid(user_id) else None
            name = (t.get("contact_name") or (contact or {}).get("name") or f"{(contact or {}).get('first_name', '')} {(contact or {}).get('last_name', '')}").strip() or "your customer"
            first = (contact or {}).get("first_name") or name.split(" ")[0]
            rep_first = (user or {}).get("first_name") or ((user or {}).get("name") or "").split(" ")[0] or "your salesperson"
            tz = await resolve_user_tz(user_id)
            draft = await draft_nudge_text(t, first, rep_first, tz)
            conv = await db.conversations.find_one({"user_id": user_id, "contact_id": contact_id}, sort=[("last_message_at", -1)])
            q = f"prefill={quote(draft)}&taskId={t['_id']}"
            link = f"/thread/{conv['_id']}?{q}" if conv else f"/contact/{contact_id}?{q}"
            title = f"Promised to {first}: {t.get('title') or 'follow up'}"
            await db.notifications.insert_one({
                "user_id": user_id, "type": "highlight_due", "title": title, "message": draft, "draft": draft,
                "contact_id": contact_id, "contact_name": name, "conversation_id": str(conv["_id"]) if conv else "",
                "task_id": str(t["_id"]), "voice_note_id": t.get("voice_note_id"), "link": link,
                "read": False, "dismissed": False, "created_at": now,
            })
            try:
                from routers.notifications_center import invalidate_feed
                invalidate_feed(user_id)
            except Exception:
                pass
            await send_push_to_user(user_id, title, f"Tap to send: {draft[:110]}{'…' if len(draft) > 110 else ''}", link, "chatbubble")
            sent += 1
        except Exception as e:
            logger.warning(f"[HighlightNudge] failed for task {t.get('_id')}: {e}")
    if sent:
        logger.info(f"[HighlightNudge] nudged {sent} due promise(s)")
    return sent
