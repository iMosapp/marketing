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


async def _transcribe_audio(audio_bytes: bytes, filename: str, kind: str = "memo") -> str:
    """Transcribe audio using OpenAI Whisper via Emergent integrations."""
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            logger.warning("No EMERGENT_LLM_KEY  - skipping transcription")
            return ""

        stt = OpenAISpeechToText(api_key=api_key)

        # Whisper needs a file-like object with a name attribute
        audio_file = io.BytesIO(audio_bytes)
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


async def _process_voice_note(db, user_id: str, contact_id: str, audio_bytes: bytes, content_type: str, duration: float, kind: str) -> dict:
    """Store, transcribe, summarize (conversations), log the touchpoint, extract personal details."""
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

    transcript = await _transcribe_audio(audio_bytes, filename, kind)
    is_convo = kind == "conversation"

    now = datetime.now(timezone.utc)
    note_doc = {
        "contact_id": contact_id, "user_id": user_id, "audio_url": audio_url, "audio_path": stored_path,
        "transcript": transcript, "summary": "", "kind": kind, "duration": round(duration, 1), "created_at": now,
    }
    result = await db.voice_notes.insert_one(note_doc)
    note_id = str(result.inserted_id)

    # Recorded conversations: summary + every commitment becomes a task on the rep's list
    summary, highlights, new_tasks = "", [], []
    if is_convo and transcript and len(transcript.strip()) >= 40:
        from services.recording_highlights import process_recorded_conversation
        hl = await process_recorded_conversation(db, user_id, contact_id, note_id, transcript)
        summary, highlights, new_tasks = hl["summary"], hl["highlights"], hl["tasks"]

    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "org_id": 1, "name": 1})
        await db.contact_events.insert_one({
            "event_type": "conversation_recorded" if is_convo else "voice_note",
            "title": "In-person conversation recorded" if is_convo else "Voice Note Recorded",
            "description": (summary or transcript)[:200] if (summary or transcript) else ("Conversation recorded" if is_convo else "Audio memo recorded"),
            "contact_id": contact_id, "user_id": user_id, "org_id": (user_doc or {}).get("org_id", ""),
            "channel": "voice_note", "category": "voice_note", "icon": "people" if is_convo else "mic", "color": "#C9A962" if is_convo else "#34C759",
            "content": summary or transcript or "",
            "metadata": {"voice_note_id": note_id, "duration": round(duration, 1), "kind": kind},
            "timestamp": now, "created_at": now,
        })
    except Exception as e:
        logger.error(f"Failed to log voice note event: {e}")

    if transcript and len(transcript.strip()) >= 10:
        try:
            from services.voice_intel import process_voice_note_intelligence
            asyncio.create_task(process_voice_note_intelligence(user_id, contact_id, transcript, note_id))
        except Exception as e:
            logger.warning(f"Voice intelligence extraction trigger failed: {e}")

    return {"id": note_id, "audio_url": audio_url, "transcript": transcript, "summary": summary, "kind": kind,
            "highlights": highlights, "tasks": new_tasks,
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
):
    """Upload a voice memo (or a recorded in-person conversation) for a contact. Stores audio, transcribes, logs event."""
    db = get_db()
    kind = "conversation" if kind == "conversation" else "memo"
    _check_duration(duration, kind)
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    return await _process_voice_note(db, user_id, contact_id, audio_bytes, audio.content_type or "audio/webm", duration, kind)


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


@router.get("/{user_id}/{contact_id}")
async def get_voice_notes(user_id: str, contact_id: str):
    """Get all voice notes for a contact, newest first."""
    db = get_db()
    notes = await db.voice_notes.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 1, "audio_url": 1, "transcript": 1, "summary": 1, "kind": 1, "duration": 1, "created_at": 1, "contact_id": 1, "user_id": 1, "highlights": 1},
    ).sort("created_at", -1).to_list(100)

    def _hl(h: dict) -> dict:
        d = h.get("due_date")
        return {**h, "due_date": d.isoformat() if hasattr(d, "isoformat") else d}

    return [
        {
            "id": str(n["_id"]),
            "contact_id": n["contact_id"],
            "user_id": n["user_id"],
            "audio_url": n["audio_url"],
            "transcript": n.get("transcript", ""),
            "summary": n.get("summary", ""),
            "kind": n.get("kind", "memo"),
            "duration": n.get("duration", 0),
            "highlights": [_hl(h) for h in (n.get("highlights") or [])],
            "created_at": n["created_at"].isoformat() if n.get("created_at") else "",
        }
        for n in notes
    ]


@router.delete("/{user_id}/{contact_id}/{note_id}")
async def delete_voice_note(user_id: str, contact_id: str, note_id: str):
    """Delete a voice note."""
    db = get_db()
    try:
        result = await db.voice_notes.delete_one({"_id": ObjectId(note_id), "user_id": user_id})
    except Exception:
        result = await db.voice_notes.delete_one({"_id": note_id, "user_id": user_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Voice note not found")

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
                title=f"Capture {first_name}'s story while it's fresh",
                body=f"Spouse, kids, pets, hobbies — 60 seconds now saves the relationship forever.",
                data={
                    "url": f"/contact/{contact_id}?capture=true",
                    "contact_id": contact_id,
                    "action": "voice_capture",
                }
            )
            logger.info(f"[VoiceCapture] Sent capture reminder for contact {contact_id}")
        except Exception as e:
            logger.warning(f"[VoiceCapture] Failed to send reminder: {e}")

    asyncio.create_task(_send_after_delay())
    return {"success": True, "message": f"Reminder scheduled in {delay_seconds}s"}
