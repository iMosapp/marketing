"""
Voice Notes router  - record, transcribe, store, and play back voice memos on contacts.
Audio stored in object storage. Transcription via OpenAI Whisper.
"""
import os
import io
import uuid
import base64
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel
from bson import ObjectId

from routers.database import get_db
from services.contact_scope import owned_contact
from utils.image_storage import put_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-notes", tags=["voice-notes"])

MAX_DURATION_SECONDS = 180  # 3 minute cap for a memo
MAX_CONVERSATION_SECONDS = 45 * 60  # recorded walk-around / desk conversation


def _convert_webm_to_m4a(webm_bytes: bytes) -> bytes:
    """Transcode webm (web recordings) to m4a/AAC so iPhones can play it."""
    import subprocess
    import tempfile
    from imageio_ffmpeg import get_ffmpeg_exe
    ffmpeg = get_ffmpeg_exe()
    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(webm_bytes)
            in_path = f.name
        out_path = in_path[:-5] + ".m4a"
        subprocess.run(
            [ffmpeg, "-y", "-i", in_path, "-vn", "-c:a", "aac", "-b:a", "64k", out_path],
            check=True, capture_output=True, timeout=120,
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p in (in_path, out_path):
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass


async def run_webm_conversion() -> dict:
    """Convert already-stored .webm voice notes to .m4a so they play on iOS.
    Idempotent — only touches notes whose audio_path still ends in .webm."""
    from utils.image_storage import get_object, put_object as _put
    db = get_db()
    notes = await db.voice_notes.find({"audio_path": {"$regex": r"\.webm$"}}).to_list(500)
    converted = failed = 0
    for n in notes:
        try:
            data, _ct = get_object(n["audio_path"])
            m4a = await asyncio.to_thread(_convert_webm_to_m4a, data)
            new_path = n["audio_path"][:-5] + ".m4a"
            await asyncio.to_thread(_put, new_path, m4a, "audio/mp4")
            await db.voice_notes.update_one(
                {"_id": n["_id"]},
                {"$set": {"audio_path": new_path, "audio_url": f"/api/images/{new_path}"}}
            )
            converted += 1
        except Exception as e:
            failed += 1
            logger.warning(f"[WebmConvert] failed for note {n.get('_id')}: {e}")
    if converted or failed:
        logger.info(f"[WebmConvert] converted={converted} failed={failed} of {len(notes)}")
    return {"converted": converted, "failed": failed, "scanned": len(notes)}


@router.post("/admin/backfill-audio-urls")
async def backfill_audio_urls(request: Request):
    """Re-link voice notes whose audio_url was never saved (storage response bug).
    Matches DB notes to storage files per contact by upload timestamp. Super admin only."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    from routers.auth import verify_jwt_token
    payload = verify_jwt_token(auth[7:])
    caller_id = payload.get("sub") if payload else None
    if not caller_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    try:
        caller = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1})
    except Exception:
        caller = None
    if not caller or caller.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return await run_audio_backfill()


async def run_audio_backfill() -> dict:
    """Core backfill: re-link voice notes with empty audio_url to their storage files."""
    import asyncio
    from utils.image_storage import list_objects

    db = get_db()
    notes = await db.voice_notes.find({
        "$or": [{"audio_url": {"$in": [None, ""]}}, {"audio_url": {"$exists": False}}]
    }).to_list(2000)
    if not notes:
        return {"fixed": 0, "unmatched": 0, "notes_scanned": 0}

    def _lm(o):
        try:
            return datetime.fromisoformat(o.get("last_modified", "").replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    by_contact: dict = {}
    for n in notes:
        by_contact.setdefault(n["contact_id"], []).append(n)

    fixed = unmatched = 0
    for cid, cnotes in by_contact.items():
        try:
            objs = await asyncio.to_thread(list_objects, f"voice-notes/{cid}/")
        except Exception as e:
            logger.warning(f"[VoiceBackfill] list failed for {cid}: {e}")
            unmatched += len(cnotes)
            continue
        used: set = set()
        for n in sorted(cnotes, key=lambda x: x.get("created_at") or datetime.min):
            n_ts = n.get("created_at")
            if n_ts and n_ts.tzinfo is None:
                n_ts = n_ts.replace(tzinfo=timezone.utc)
            best, best_diff = None, None
            for o in objs:
                if o["path"] in used:
                    continue
                diff = abs((_lm(o) - n_ts).total_seconds()) if n_ts else 0
                if best is None or diff < best_diff:
                    best, best_diff = o, diff
            if best:
                used.add(best["path"])
                await db.voice_notes.update_one(
                    {"_id": n["_id"]},
                    {"$set": {"audio_path": best["path"], "audio_url": f"/api/images/{best['path']}"}}
                )
                fixed += 1
            else:
                unmatched += 1

    logger.info(f"[VoiceBackfill] fixed={fixed} unmatched={unmatched} of {len(notes)}")
    return {"fixed": fixed, "unmatched": unmatched, "notes_scanned": len(notes)}


class VoiceNoteOut(BaseModel):
    id: str
    contact_id: str
    user_id: str
    audio_url: str
    transcript: Optional[str] = None
    duration: float  # seconds
    created_at: str


async def _whisper(audio_bytes: bytes, filename: str, kind: str = "memo") -> str:
    """One Whisper call (OpenAI via Emergent integrations). Raises on failure; "" means no words were heard."""
    from emergentintegrations.llm.openai import OpenAISpeechToText
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY missing")
    stt = OpenAISpeechToText(api_key=api_key)
    audio_file = io.BytesIO(audio_bytes)   # Whisper needs a file-like object with a name attribute
    audio_file.name = filename
    response = await stt.transcribe(
        file=audio_file,
        model="whisper-1",
        language="en",
        response_format="json",
        prompt=("A recorded in-person conversation at a car dealership between a salesperson and a customer. Names, vehicle models, trade-in, payments, appointment times."
                if kind == "conversation" else
                "Sales conversation notes about a customer. May include names, car models, family details, dates."),
    )
    return response.text.strip() if response and response.text else ""


async def _transcribe_audio(audio_bytes: bytes, filename: str, kind: str = "memo") -> str:
    """Transcribe audio, "" on any failure (callers that must not lose a memo use services.transcript_retry instead)."""
    try:
        return await _whisper(audio_bytes, filename, kind)
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return ""


def _ext_for(content_type: str) -> str:
    ct = (content_type or "audio/webm").lower()
    if "mp4" in ct or "m4a" in ct:
        return "m4a"
    if "wav" in ct:
        return "wav"
    if "mp3" in ct or "mpeg" in ct:
        return "mp3"
    return "webm"


async def _process_voice_note(db, user_id: str, contact_id: str, audio_bytes: bytes, content_type: str, duration: float, kind: str, transcript: str = "") -> dict:
    """Store, transcribe, summarize (conversations), log the touchpoint, extract personal details.
    transcript: already transcribed on this recording (the new-contact screen shows it before Save), so it is not paid for twice."""
    ext = _ext_for(content_type)
    filename = f"voice_note_{uuid.uuid4().hex[:8]}.{ext}"
    if ext == "webm":
        try:
            audio_bytes = await asyncio.to_thread(_convert_webm_to_m4a, audio_bytes)
            ext, content_type = "m4a", "audio/mp4"
            filename = f"voice_note_{uuid.uuid4().hex[:8]}.m4a"
        except Exception as e:
            logger.warning(f"webm→m4a conversion failed, storing original webm: {e}")

    storage_path = f"voice-notes/{contact_id}/{filename}"
    try:
        result = put_object(storage_path, audio_bytes, content_type)
        stored_path = result.get("path") or storage_path
        audio_url = f"/api/images/{stored_path}"
    except Exception as e:
        logger.error(f"Voice note upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store audio")

    transcript, error = (transcript or "").strip()[:20000], ""
    if not transcript:
        from services.transcript_retry import transcribe_now
        transcript, error = await transcribe_now(audio_bytes, filename, kind)
    return await _store_note(db, user_id, contact_id, transcript, kind, duration, audio_url, stored_path, audio_bytes, transcript_error=error)


async def create_text_memo(db, user_id: str, contact_id: str, text: str, source: str = "jessi", followup: bool = True) -> dict:
    """A memo dictated to Jessi (or typed): no audio, otherwise the exact voice-note pipeline (timeline event, personal-detail extraction).
    followup=False when the caller handles the follow-up itself (Jessi's new-contact flow offers a dated reminder)."""
    return await _store_note(db, user_id, contact_id, (text or "").strip(), "memo", 0.0, None, None, None, source=source, followup=followup)


async def _store_note(db, user_id: str, contact_id: str, transcript: str, kind: str, duration: float, audio_url, stored_path, audio_bytes, source: str = "app", followup: bool = True,
                      transcript_error: str = "") -> dict:
    from services.transcript_retry import fields_after_upload
    is_convo = kind == "conversation"

    now = datetime.now(timezone.utc)
    note_doc = {
        "contact_id": contact_id, "user_id": user_id, "audio_url": audio_url, "audio_path": stored_path,
        "transcript": transcript, "summary": "", "kind": kind, "duration": round(duration, 1), "created_at": now, "source": source,
        "followup": followup, **fields_after_upload(transcript, transcript_error, now, bool(stored_path)),
    }
    result = await db.voice_notes.insert_one(note_doc)
    note_id = str(result.inserted_id)

    async def _voice_check():
        from services import voice_id
        try:
            v = await voice_id.verify_user(db, user_id, audio_bytes)
        except Exception as e:
            logger.debug(f"[VoiceID] voice note check skipped: {e}")
            return
        if v:
            await db.voice_notes.update_one({"_id": result.inserted_id}, {"$set": {"voice_id": v}})
    if audio_bytes:
        asyncio.create_task(_voice_check())

    # Recorded conversations: summary + every commitment becomes a task on the rep's list
    summary, title, highlights, new_tasks = "", "", [], []
    if is_convo and transcript and len(transcript.strip()) >= 40:
        from services.recording_highlights import process_recorded_conversation
        hl = await process_recorded_conversation(db, user_id, contact_id, note_id, transcript)
        summary, title, highlights, new_tasks = hl["summary"], hl["title"], hl["highlights"], hl["tasks"]

    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "org_id": 1, "name": 1})
        await db.contact_events.insert_one({
            "event_type": "conversation_recorded" if is_convo else "voice_note",
            "title": "In-person conversation recorded" if is_convo else ("Note dictated to Jessi" if source == "jessi" else "Voice Note Recorded"),
            "description": (summary or transcript)[:200] if (summary or transcript) else ("Conversation recorded" if is_convo else "Audio memo recorded"),
            "contact_id": contact_id, "user_id": user_id, "org_id": (user_doc or {}).get("org_id", ""),
            "channel": "voice_note", "category": "voice_note", "icon": "people" if is_convo else "mic", "color": "#C9A962" if is_convo else "#34C759",
            "content": summary or transcript or "",
            "metadata": {"voice_note_id": note_id, "duration": round(duration, 1), "kind": kind, "source": source},
            "timestamp": now, "created_at": now,
        })
    except Exception as e:
        logger.error(f"Failed to log voice note event: {e}")

    if transcript and len(transcript.strip()) >= 10:
        try:
            from services.voice_intel import process_voice_note_intelligence
            asyncio.create_task(process_voice_note_intelligence(user_id, contact_id, transcript, note_id, auto_followup=followup))
        except Exception as e:
            logger.warning(f"Voice intelligence extraction trigger failed: {e}")

    return {"id": note_id, "audio_url": audio_url, "transcript": transcript, "summary": summary, "title": title, "kind": kind,
            "highlights": highlights, "tasks": new_tasks, "transcript_status": note_doc["transcript_status"],
            "duration": round(duration, 1), "created_at": now.isoformat()}


def _check_duration(duration: float, kind: str):
    cap = MAX_CONVERSATION_SECONDS if kind == "conversation" else MAX_DURATION_SECONDS
    if duration > cap:
        raise HTTPException(status_code=400, detail=f"Recording exceeds the {cap // 60} minute limit")


@router.post("/{user_id}/{contact_id}")
async def create_voice_note(
    user_id: str,
    contact_id: str,
    audio: UploadFile = File(...),
    duration: float = Form(0),
    kind: str = Form("memo"),
    transcript: str = Form(""),
):
    """Upload a voice memo (or a recorded in-person conversation) for a contact. Stores audio, transcribes, logs event."""
    db = get_db()
    await owned_contact(db, user_id, contact_id, {"_id": 1})
    kind = "conversation" if kind == "conversation" else "memo"
    _check_duration(duration, kind)
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    return await _process_voice_note(db, user_id, contact_id, audio_bytes, audio.content_type or "audio/webm", duration, kind, transcript)


class AudioChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    content_type: str = "audio/mp4"
    duration: float = 0
    kind: str = "conversation"


@router.post("/{user_id}/{contact_id}/chunk")
async def upload_voice_chunk(user_id: str, contact_id: str, chunk: AudioChunk):
    """Long recordings arrive as base64 pieces (<= ~600KB each) so proxies never see one huge request; assembled on the last piece."""
    import re as _re
    db = get_db()
    await owned_contact(db, user_id, contact_id, {"_id": 1})
    if chunk.total < 1 or chunk.total > 200 or not (0 <= chunk.index < chunk.total) or len(chunk.data) > 900_000:
        raise HTTPException(status_code=400, detail="Bad chunk")
    upload_id = _re.sub(r"[^A-Za-z0-9_-]", "", chunk.upload_id)[:64]
    if not upload_id:
        raise HTTPException(status_code=400, detail="Bad upload id")
    kind = "conversation" if chunk.kind == "conversation" else "memo"
    _check_duration(chunk.duration, kind)
    await db.voice_upload_chunks.update_one(
        {"user_id": user_id, "upload_id": upload_id, "index": chunk.index},
        {"$set": {"data": chunk.data, "created_at": datetime.utcnow()}}, upsert=True)
    have = await db.voice_upload_chunks.count_documents({"user_id": user_id, "upload_id": upload_id})
    if have < chunk.total:
        return {"success": True, "received": have, "total": chunk.total}
    parts = await db.voice_upload_chunks.find({"user_id": user_id, "upload_id": upload_id}).sort("index", 1).to_list(chunk.total)
    await db.voice_upload_chunks.delete_many({"user_id": user_id, "upload_id": upload_id})
    try:
        audio_bytes = base64.b64decode("".join(p["data"] for p in parts))
    except Exception:
        raise HTTPException(status_code=400, detail="That recording came through damaged. Please try again.")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    out = await _process_voice_note(db, user_id, contact_id, audio_bytes, chunk.content_type, chunk.duration, kind)
    out.update({"success": True, "received": chunk.total, "total": chunk.total})
    return out


async def _can_change(db, user_id: str, note: dict) -> bool:
    """The rep who recorded a memo, or a manager over this contact, may rename or delete it."""
    if str(note.get("user_id")) == str(user_id):
        return True
    from services.inboxes import is_manager
    me = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1}) if ObjectId.is_valid(str(user_id)) else None
    return is_manager(me or {})


async def _scoped_note(db, user_id: str, contact_id: str, note_id: str) -> dict:
    """A note on a contact this user can open (reassigned contacts keep every memo, whoever recorded it)."""
    if not ObjectId.is_valid(str(note_id)):
        raise HTTPException(status_code=404, detail="Voice note not found")
    await owned_contact(db, user_id, contact_id, {"_id": 1})
    n = await db.voice_notes.find_one({"_id": ObjectId(note_id), "contact_id": contact_id})
    if not n:
        raise HTTPException(status_code=404, detail="Voice note not found")
    return n


@router.get("/{user_id}/{contact_id}")
async def get_voice_notes(user_id: str, contact_id: str):
    """Every voice note on a contact the user can open, newest first, labelled with who recorded it."""
    from services.transcript_retry import status_of
    db = get_db()
    await owned_contact(db, user_id, contact_id, {"_id": 1})
    notes = await db.voice_notes.find(
        {"contact_id": contact_id},
        {"_id": 1, "audio_url": 1, "audio_path": 1, "transcript": 1, "transcript_status": 1, "summary": 1, "title": 1, "kind": 1, "duration": 1, "created_at": 1,
         "contact_id": 1, "user_id": 1, "highlights": 1, "voice_id.verified": 1},
    ).sort("created_at", -1).to_list(100)
    authors = {str(n.get("user_id")) for n in notes if n.get("user_id")}
    names = {str(u["_id"]): (u.get("first_name") or (u.get("name") or "").split(" ")[0] or "a teammate")
             async for u in db.users.find({"_id": {"$in": [ObjectId(a) for a in authors if ObjectId.is_valid(a)]}}, {"name": 1, "first_name": 1})} if authors else {}
    from services.inboxes import is_manager
    me = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1}) if ObjectId.is_valid(user_id) else None
    manager = is_manager(me or {})

    def _hl(h: dict) -> dict:
        d = h.get("due_date")
        return {**h, "due_date": d.isoformat() if hasattr(d, "isoformat") else d}

    return [
        {
            "id": str(n["_id"]),
            "contact_id": n["contact_id"],
            "user_id": n.get("user_id"),
            "audio_url": n.get("audio_url"),
            "transcript": n.get("transcript", ""),
            "transcript_status": status_of(n),
            "summary": n.get("summary", ""),
            "title": n.get("title") or "",
            "kind": n.get("kind", "memo"),
            "duration": n.get("duration", 0),
            "highlights": [_hl(h) for h in (n.get("highlights") or [])],
            "voice_verified": (n.get("voice_id") or {}).get("verified"),
            "mine": str(n.get("user_id")) == user_id,
            "recorded_by": names.get(str(n.get("user_id")), "a teammate"),
            "can_delete": manager or str(n.get("user_id")) == user_id,
            "created_at": n["created_at"].isoformat() if n.get("created_at") else "",
        }
        for n in notes
    ]


@router.get("/{user_id}/{contact_id}/{note_id}")
async def get_voice_note(user_id: str, contact_id: str, note_id: str):
    """One note with what Jessi learned from it (the app polls this right after a memo is saved)."""
    from services.transcript_retry import status_of
    n = await _scoped_note(get_db(), user_id, contact_id, note_id)
    transcript = n.get("transcript") or ""
    status = status_of(n)
    return {
        "id": note_id, "audio_url": n.get("audio_url"), "transcript": transcript, "summary": n.get("summary", ""), "title": n.get("title") or "",
        "kind": n.get("kind", "memo"), "duration": n.get("duration", 0), "transcript_status": status,
        "intelligence_done": bool(n.get("intelligence_done")) or (status != "retrying" and len(transcript.strip()) < 10),
        "extracted_details": n.get("extracted_details") or {}, "followup_task": n.get("followup_task"),
        "created_at": n["created_at"].isoformat() if n.get("created_at") else "",
    }


@router.post("/{user_id}/{contact_id}/{note_id}/retry-transcript")
async def retry_voice_note_transcript(user_id: str, contact_id: str, note_id: str):
    """Retry button: one more transcription from the saved audio, right now (no extra reminder if it still fails)."""
    from services.transcript_retry import retry_one, status_of
    db = get_db()
    n = await _scoped_note(db, user_id, contact_id, note_id)
    if status_of(n) == "done":
        return {"id": note_id, "transcript_status": "done", "transcript": n.get("transcript") or ""}
    out = await retry_one(db, n, manual=True)
    return {"id": note_id, **out}


@router.patch("/{user_id}/{contact_id}/{note_id}")
async def rename_voice_note(user_id: str, contact_id: str, note_id: str, data: dict = None):
    """Give a recording a short name ("Tahoe walk-around"). Empty title falls back to the default label."""
    from utils.text_sanitize import no_em_dash
    db = get_db()
    title = no_em_dash(str((data or {}).get("title") or "")).strip()[:60]
    n = await _scoped_note(db, user_id, contact_id, note_id)
    if not await _can_change(db, user_id, n):
        raise HTTPException(status_code=403, detail="Only the person who recorded this, or a manager, can rename it")
    await db.voice_notes.update_one({"_id": n["_id"]}, {"$set": {"title": title}})
    return {"id": note_id, "title": title}


@router.delete("/{user_id}/{contact_id}/{note_id}")
async def delete_voice_note(user_id: str, contact_id: str, note_id: str):
    """Delete a voice note or recorded conversation (timeline entry goes too; tasks it created stay on the rep's list).
    Only the rep who recorded it, or a manager over the contact."""
    db = get_db()
    n = await _scoped_note(db, user_id, contact_id, note_id)
    if not await _can_change(db, user_id, n):
        raise HTTPException(status_code=403, detail="Only the person who recorded this, or a manager, can delete it")
    await db.voice_notes.delete_one({"_id": n["_id"]})
    await db.contact_events.delete_many({"contact_id": contact_id, "metadata.voice_note_id": note_id, "event_type": {"$in": ["voice_note", "conversation_recorded"]}})
    return {"message": "Voice note deleted"}


@router.post("/{user_id}/{contact_id}/capture-reminder")
async def schedule_capture_reminder(user_id: str, contact_id: str, data: dict = None):
    """
    Schedule a push notification ~5 minutes after a sale to prompt the rep
    to record a relationship voice note about the customer while memory is fresh.
    Called by the SOLD wizard after success.
    """
    import asyncio
    db = get_db()
    await owned_contact(db, user_id, contact_id, {"_id": 1})
    data = data or {}
    contact_name = data.get("contact_name", "your customer")
    first_name = contact_name.split()[0] if contact_name else "your customer"
    delay_seconds = data.get("delay_seconds", 300)  # 5 minutes default

    async def _send_after_delay():
        await asyncio.sleep(delay_seconds)
        try:
            from routers.push_notifications import send_push_native
            await send_push_native(
                user_id=user_id,
                title=f"Tell me about {first_name} while it's fresh",
                body=f"Tap, hit Start recording, and talk for a minute: spouse, kids, pets, work, hobbies, why they bought. I'll save it to {first_name}'s profile.",
                data={
                    "url": f"/contact/{contact_id}?capture=sold",
                    "contact_id": contact_id,
                    "action": "voice_capture",
                }
            )
            logger.info(f"[VoiceCapture] Sent capture reminder for contact {contact_id}")
        except Exception as e:
            logger.warning(f"[VoiceCapture] Failed to send reminder: {e}")

    asyncio.create_task(_send_after_delay())
    return {"success": True, "message": f"Reminder scheduled in {delay_seconds}s"}
