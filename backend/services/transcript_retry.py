"""Missed transcripts: Whisper is tried twice on upload, then again about 2 minutes, 10 minutes and 1 hour after the recording,
from the saved audio. A transcript that finally arrives runs the normal pipeline (details, How we met, follow-ups, conversation
summary). If every try fails the memo says "couldn't transcribe" with a Retry button and the rep gets one reminder to listen."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

RETRY_AFTER = (timedelta(minutes=2), timedelta(minutes=10), timedelta(hours=1))   # measured from the recording
LEASE = timedelta(minutes=5)
BATCH = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: Optional[datetime]) -> datetime:
    if not isinstance(d, datetime):
        return _now()
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def status_of(n: dict) -> str:
    """done | retrying | failed. Older notes with audio and no words (before retries existed) read as failed so the rep can retry them."""
    if (n.get("transcript") or "").strip():
        return "done"
    s = n.get("transcript_status")
    if s in ("retrying", "failed"):
        return s
    return "failed" if n.get("audio_path") else "done"


async def transcribe_now(audio_bytes: bytes, filename: str, kind: str) -> tuple:
    """(text, error) after one try plus one quick retry. No words heard counts as a miss too."""
    from routers.voice_notes import _whisper
    err = ""
    for attempt in range(2):
        try:
            text = await _whisper(audio_bytes, filename, kind)
            if text:
                return text, ""
            err = "no words heard"
        except Exception as e:
            err = str(e)[:200] or e.__class__.__name__
            logger.warning(f"[Transcript] whisper try {attempt + 1} failed: {err}")
        if attempt == 0:
            await asyncio.sleep(1.5)
    return "", err


def fields_after_upload(transcript: str, error: str, now: datetime, has_audio: bool) -> dict:
    if transcript or not has_audio:
        return {"transcript_status": "done", "transcript_attempts": 1 if has_audio else 0}
    return {"transcript_status": "retrying", "transcript_attempts": 1, "transcript_next_at": now + RETRY_AFTER[0], "transcript_error": error}


def _task_key(note_id: str) -> str:
    return f"transcript_failed_{note_id}"


async def _contact_name(db, contact_id: Optional[str]) -> tuple:
    if not contact_id or not ObjectId.is_valid(str(contact_id)):
        return "", "", ""
    c = await db.contacts.find_one({"_id": ObjectId(str(contact_id))}, {"first_name": 1, "last_name": 1, "phone": 1}) or {}
    first = c.get("first_name") or ""
    return first, f"{first} {c.get('last_name') or ''}".strip(), c.get("phone") or ""


async def _failure_task(db, note: dict) -> None:
    """One reminder per memo (idempotent) for the rep who recorded it."""
    nid, now = str(note["_id"]), _now()
    first, name, phone = await _contact_name(db, note.get("contact_id"))
    when = _aware(note.get("created_at")).strftime("%b %d")
    what = "recorded conversation" if note.get("kind") == "conversation" else "voice memo"
    title = f"Listen to your {what} about {first} and add a note" if first else f"Listen to your unfiled {what} from {when} and add a note"
    where = f"Play it on {name}'s profile (History, Memos)" if name else "Play it under Voice memos"
    await db.tasks.update_one({"idempotency_key": _task_key(nid)}, {"$setOnInsert": {
        "user_id": note.get("user_id"), "contact_id": note.get("contact_id") or "", "contact_name": name, "contact_phone": phone,
        "type": "follow_up", "source": "transcript_failed", "title": title[:120],
        "description": f"Jessi could not transcribe the {what} you recorded {when}, even after retrying. {where} and add what matters as a note, or tap Retry.",
        "suggested_message": "", "action_type": "manual", "priority": "medium", "priority_order": 2, "status": "pending", "completed": False,
        "due_date": now, "has_time": False, "voice_note_id": nid, "channel": "", "created_at": now,
    }}, upsert=True)


async def _close_failure_task(db, nid: str) -> None:
    await db.tasks.update_one({"idempotency_key": _task_key(nid), "completed": False},
                              {"$set": {"completed": True, "status": "completed", "completed_at": _now(), "completed_reason": "transcript_recovered"}})


async def apply_transcript(db, note: dict, text: str) -> None:
    """A late transcript goes through everything an on-time one would have."""
    nid, now = str(note["_id"]), _now()
    await db.voice_notes.update_one({"_id": note["_id"]}, {"$set": {"transcript": text, "transcript_status": "done", "transcript_recovered_at": now},
                                                           "$unset": {"transcript_next_at": "", "transcript_error": ""}})
    await _close_failure_task(db, nid)
    cid, uid = note.get("contact_id"), str(note.get("user_id") or "")
    if not cid:   # unattached memo: title, summary and who it might be about
        from routers.voice_memos import _title_and_summary, match_people
        meta = await _title_and_summary(text)
        sets = {"summary": meta["summary"], "people": meta["people"], "suggested_contacts": await match_people(db, uid, meta["people"])}
        if not note.get("title"):
            sets["title"] = meta["title"]
        await db.voice_notes.update_one({"_id": note["_id"]}, {"$set": sets})
        return
    summary = ""
    if note.get("kind") == "conversation" and len(text) >= 40:
        from services.recording_highlights import process_recorded_conversation
        summary = (await process_recorded_conversation(db, uid, cid, nid, text)).get("summary") or ""
    await db.contact_events.update_many({"contact_id": cid, "metadata.voice_note_id": nid},
                                        {"$set": {"description": (summary or text)[:200], "content": summary or text}})
    if len(text) >= 10:
        from services.voice_intel import process_voice_note_intelligence
        await process_voice_note_intelligence(uid, cid, text, nid, auto_followup=note.get("followup", True))


async def retry_one(db, note: dict, manual: bool = False) -> dict:
    """One more go from the saved audio. Scheduled tries walk RETRY_AFTER; a manual Retry never schedules more or adds a 2nd reminder."""
    from utils.image_storage import get_object
    nid = str(note["_id"])
    text, err = "", "audio not found"
    if note.get("audio_path"):
        try:
            data, _ct = await asyncio.to_thread(get_object, note["audio_path"])
            text, err = await transcribe_now(data, note["audio_path"].rsplit("/", 1)[-1], note.get("kind") or "memo")
        except Exception as e:
            err = f"audio read failed: {str(e)[:160]}"
    if text:
        await apply_transcript(db, note, text)
        logger.info(f"[Transcript] recovered note {nid} ({'manual' if manual else 'scheduled'})")
        return {"transcript_status": "done", "transcript": text}
    attempts = int(note.get("transcript_attempts") or 1) + 1
    if not manual and attempts <= len(RETRY_AFTER):
        nxt = max(_aware(note.get("created_at")) + RETRY_AFTER[attempts - 1], _now() + timedelta(seconds=30))
        await db.voice_notes.update_one({"_id": note["_id"]}, {"$set": {"transcript_status": "retrying", "transcript_attempts": attempts, "transcript_next_at": nxt, "transcript_error": err}})
        return {"transcript_status": "retrying", "transcript": ""}
    await db.voice_notes.update_one({"_id": note["_id"]}, {"$set": {"transcript_status": "failed", "transcript_attempts": attempts, "transcript_error": err, "transcript_failed_at": _now()},
                                                           "$unset": {"transcript_next_at": ""}})
    if not manual:
        await _failure_task(db, note)
    logger.warning(f"[Transcript] note {nid} still has no transcript after {attempts} attempts: {err}")
    return {"transcript_status": "failed", "transcript": ""}


async def sweep(db) -> int:
    """Scheduler: claim due notes one at a time (lease) so two workers never retry the same memo."""
    done = 0
    for _ in range(BATCH):
        now = _now()
        note = await db.voice_notes.find_one_and_update(
            {"transcript_status": "retrying", "transcript_next_at": {"$lte": now}},
            {"$set": {"transcript_next_at": now + LEASE}}, sort=[("transcript_next_at", 1)])
        if not note:
            break
        try:
            await retry_one(db, note)
        except Exception as e:
            logger.exception(f"[Transcript] retry crashed for {note.get('_id')}: {e}")
        done += 1
    return done
