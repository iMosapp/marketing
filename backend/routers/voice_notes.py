"""
Voice Notes router — record, transcribe, store, and play back voice memos on contacts.
Audio stored in object storage. Transcription via OpenAI Whisper.
"""
import os
import io
import uuid
import base64
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from bson import ObjectId

from database import get_db
from utils.image_storage import put_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-notes", tags=["voice-notes"])

MAX_DURATION_SECONDS = 120  # 2 minute cap


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
            logger.warning("No EMERGENT_LLM_KEY — skipping transcription")
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

    # 1. Upload to object storage
    storage_path = f"voice-notes/{contact_id}/{filename}"
    try:
        result = put_object(storage_path, audio_bytes, content_type)
        audio_url = result.get("url", "")
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
            "content": transcript or "",
            "metadata": {"voice_note_id": note_id, "duration": round(duration, 1)},
            "timestamp": now,
            "created_at": now,
        }
        await db.contact_events.insert_one(event_doc)
    except Exception as e:
        logger.error(f"Failed to log voice note event: {e}")

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
