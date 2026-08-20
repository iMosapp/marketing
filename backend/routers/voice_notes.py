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

MAX_DURATION_SECONDS = 180  # 3 minute cap


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


async def _transcribe_audio(audio_bytes: bytes, filename: str) -> str:
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
            prompt="Sales conversation notes about a customer. May include names, car models, family details, dates.",
        )
        return response.text.strip() if response and response.text else ""
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return ""


@router.post("/{user_id}/{contact_id}")
async def create_voice_note(
    user_id: str,
    contact_id: str,
    audio: UploadFile = File(...),
    duration: float = Form(0),
):
    """Upload a voice note for a contact. Stores audio, transcribes, logs event."""
    db = get_db()

    if duration > MAX_DURATION_SECONDS:
        raise HTTPException(status_code=400, detail=f"Recording exceeds {MAX_DURATION_SECONDS}s limit")

    # Read audio bytes
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Determine content type and extension
    content_type = audio.content_type or "audio/webm"
    ext = "webm"
    if "mp4" in content_type or "m4a" in content_type:
        ext = "m4a"
    elif "wav" in content_type:
        ext = "wav"
    elif "mp3" in content_type or "mpeg" in content_type:
        ext = "mp3"

    filename = f"voice_note_{uuid.uuid4().hex[:8]}.{ext}"

    # Web recordings arrive as webm — iPhones can't play webm, transcode to m4a (AAC)
    if ext == "webm":
        try:
            audio_bytes = await asyncio.to_thread(_convert_webm_to_m4a, audio_bytes)
            ext, content_type = "m4a", "audio/mp4"
            filename = f"voice_note_{uuid.uuid4().hex[:8]}.m4a"
        except Exception as e:
            logger.warning(f"webm→m4a conversion failed, storing original webm: {e}")

    # 1. Upload to object storage
    storage_path = f"voice-notes/{contact_id}/{filename}"
    try:
        result = put_object(storage_path, audio_bytes, content_type)
        stored_path = result.get("path") or storage_path
        audio_url = f"/api/images/{stored_path}"
    except Exception as e:
        logger.error(f"Voice note upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store audio")

    # 2. Transcribe with Whisper (async, non-blocking for the response)
    transcript = await _transcribe_audio(audio_bytes, filename)

    # 3. Save to database
    now = datetime.now(timezone.utc)
    note_doc = {
        "contact_id": contact_id,
        "user_id": user_id,
        "audio_url": audio_url,
        "audio_path": stored_path,
        "transcript": transcript,
        "duration": round(duration, 1),
        "created_at": now,
    }
    result = await db.voice_notes.insert_one(note_doc)
    note_id = str(result.inserted_id)

    # 4. Log as contact_event for the activity feed
    try:
        # Get user info for the event
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "org_id": 1, "name": 1})
        org_id = user_doc.get("org_id", "") if user_doc else ""

        event_doc = {
            "event_type": "voice_note",
            "title": "Voice Note Recorded",
            "description": transcript[:200] if transcript else "Audio memo recorded",
            "contact_id": contact_id,
            "user_id": user_id,
            "org_id": org_id,
            "channel": "voice_note",
            "category": "voice_note",  # For frontend icon lookup
            "icon": "mic",
            "color": "#34C759",
            "content": transcript or "",
            "metadata": {"voice_note_id": note_id, "duration": round(duration, 1)},
            "timestamp": now,
            "created_at": now,
        }
        await db.contact_events.insert_one(event_doc)
    except Exception as e:
        logger.error(f"Failed to log voice note event: {e}")

    # 5. Auto-extract personal details from transcript using AI (fire-and-forget)
    if transcript and len(transcript.strip()) >= 10:
        import asyncio
        try:
            from services.voice_intel import process_voice_note_intelligence
            asyncio.create_task(process_voice_note_intelligence(user_id, contact_id, transcript, note_id))
        except Exception as e:
            logger.warning(f"Voice intelligence extraction trigger failed: {e}")

    return {
        "id": note_id,
        "audio_url": audio_url,
        "transcript": transcript,
        "duration": round(duration, 1),
        "created_at": now.isoformat(),
    }


@router.get("/{user_id}/{contact_id}")
async def get_voice_notes(user_id: str, contact_id: str):
    """Get all voice notes for a contact, newest first."""
    db = get_db()
    notes = await db.voice_notes.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 1, "audio_url": 1, "transcript": 1, "duration": 1, "created_at": 1, "contact_id": 1, "user_id": 1},
    ).sort("created_at", -1).to_list(100)

    return [
        {
            "id": str(n["_id"]),
            "contact_id": n["contact_id"],
            "user_id": n["user_id"],
            "audio_url": n["audio_url"],
            "transcript": n.get("transcript", ""),
            "duration": n.get("duration", 0),
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
