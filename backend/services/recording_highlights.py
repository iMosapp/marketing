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
        "{\"summary\": \"3 or 4 plain sentences: what the customer wants, objections or concerns, what was agreed, next steps\",\n"
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
        return {"summary": "", "commitments": []}
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
    return {"summary": no_em_dash(str(data.get("summary") or "")).strip()[:1500], "commitments": out}


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
        analysis = {"summary": "", "commitments": []}

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
    if tasks:
        await db.contact_events.insert_one({
            "contact_id": contact_id, "user_id": user_id, "event_type": "recording_highlights", "channel": "system", "category": "task",
            "title": f"{len(tasks)} follow-up{'s' if len(tasks) != 1 else ''} pulled from your recorded conversation",
            "description": "; ".join(t["title"] for t in tasks)[:300], "icon": "checkbox", "color": "#C9A962",
            "metadata": {"voice_note_id": note_id, "task_ids": [t["id"] for t in tasks]}, "timestamp": now, "created_at": now})
    logger.info(f"[RecordingHighlights] note {note_id}: {len(highlights)} commitments, {len(tasks)} new tasks")
    return {"summary": analysis["summary"], "highlights": [{**h, "due_date": h["due_date"].isoformat()} for h in highlights], "tasks": tasks}
