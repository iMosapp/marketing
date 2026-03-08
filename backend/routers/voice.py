"""
Voice-to-Text Router - Audio transcription using OpenAI Whisper
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import os
import tempfile
import logging
from datetime import datetime
from dotenv import load_dotenv

from routers.database import get_db

load_dotenv()

router = APIRouter(prefix="/voice", tags=["Voice"])
logger = logging.getLogger(__name__)

# Import the OpenAI Speech-to-Text integration
try:
    from emergentintegrations.llm.openai import OpenAISpeechToText
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("emergentintegrations not installed - voice transcription disabled")


class TranscriptionResponse(BaseModel):
    text: str
    success: bool
    error: str | None = None


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "en"
):
    """
    Transcribe audio file to text using OpenAI Whisper.
    
    Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm
    Max file size: 25 MB
    """
    if not WHISPER_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Voice transcription service unavailable - missing dependencies"
        )
    
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Voice transcription service not configured"
        )
    
    # Validate file type
    allowed_types = ['audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/wav', 
                     'audio/webm', 'audio/m4a', 'audio/x-m4a', 'video/mp4',
                     'audio/x-wav', 'audio/wave']
    
    content_type = file.content_type or ''
    filename = file.filename or 'audio.wav'
    
    # Check by extension if content type is generic
    valid_extensions = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
    file_ext = os.path.splitext(filename)[1].lower()
    
    if content_type not in allowed_types and file_ext not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Supported: mp3, mp4, mpeg, mpga, m4a, wav, webm"
        )
    
    try:
        # Read the uploaded file
        audio_content = await file.read()
        
        # Check file size (25 MB limit)
        if len(audio_content) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Audio file too large. Maximum size is 25 MB."
            )
        
        # Save to temp file for the API
        suffix = file_ext if file_ext else '.wav'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(audio_content)
            tmp_path = tmp_file.name
        
        try:
            # Initialize Whisper client
            stt = OpenAISpeechToText(api_key=api_key)
            
            # Transcribe
            with open(tmp_path, "rb") as audio_file:
                response = await stt.transcribe(
                    file=audio_file,
                    model="whisper-1",
                    response_format="json",
                    language=language
                )
            
            transcribed_text = response.text.strip()
            
            # Filter out common Whisper hallucinations that occur with silence
            # These are EXACT matches only - short phrases Whisper outputs for silence
            hallucination_phrases = [
                "thank you for watching",
                "thanks for watching", 
                "please subscribe",
                "subscribe to my channel",
                "like and subscribe",
                "see you next time",
                "see you in the next",
                "bye bye",
                "goodbye",
                "you",  # Single word "you" is common hallucination
                "",     # Empty
            ]
            
            # Check if transcription is a hallucination (silence recording)
            # Strip punctuation for comparison
            import re
            lower_text = transcribed_text.lower().strip()
            clean_text = re.sub(r'[^\w\s]', '', lower_text).strip()  # Remove punctuation
            
            # Only filter EXACT matches or very short meaningless text
            is_hallucination = (
                clean_text in hallucination_phrases or  # Exact match only
                len(clean_text) < 3 or  # Too short to be meaningful
                all(c in '.?!,; ' for c in transcribed_text)  # Just punctuation/spaces
            )
            
            if is_hallucination:
                logger.info(f"Filtered hallucination/empty transcription: '{transcribed_text}'")
                return TranscriptionResponse(
                    text="",
                    success=True,  # Not an error, just nothing to transcribe
                    error=None
                )
            
            logger.info(f"Successfully transcribed audio: {len(transcribed_text)} chars")
            
            return TranscriptionResponse(
                text=transcribed_text,
                success=True
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return TranscriptionResponse(
            text="",
            success=False,
            error=f"Transcription failed: {str(e)}"
        )


class TaskParseRequest(BaseModel):
    text: str

class TaskParseResponse(BaseModel):
    title: str
    description: str = ""
    type: str = "other"
    priority: str = "medium"
    due_date: str | None = None
    due_time: str | None = None
    success: bool = True


@router.post("/parse-task", response_model=TaskParseResponse)
async def parse_task_from_voice(data: TaskParseRequest):
    """Use AI to extract task details from transcribed voice input."""
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not emergent_key:
        # Fallback: just use the text as the title
        return TaskParseResponse(title=data.text[:200], description=data.text)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        today = datetime.now().strftime("%A, %B %d, %Y")
        prompt = f"""Extract task details from this voice input. Today is {today}.

Voice input: "{data.text}"

Return ONLY a valid JSON object with these fields:
- "title": A concise task title (max 80 chars)
- "description": Any additional details mentioned
- "type": One of "callback", "follow_up", "appointment", "other"
- "priority": One of "low", "medium", "high"
- "due_date": ISO date string (YYYY-MM-DD) if a date was mentioned, null otherwise
- "due_time": Time in HH:MM 24h format if mentioned, null otherwise

Rules:
- If they say "call back" or "call", type is "callback"
- If they say "follow up" or "check in", type is "follow_up"
- If they say "meeting" or "appointment", type is "appointment"
- If they say "urgent" or "ASAP", priority is "high"
- "tomorrow" means the day after today
- "next Tuesday" means the next occurrence of that day
- If no date mentioned, due_date should be null

Return ONLY the JSON, no explanation."""

        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"task-parse-{datetime.now().isoformat()}",
            system_message="You are a task extraction assistant. Return only valid JSON.",
        ).with_model("openai", "gpt-4o-mini")
        response = await chat.send_message(UserMessage(text=prompt))

        import json
        # Clean response - strip markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)

        return TaskParseResponse(
            title=parsed.get("title", data.text[:200]),
            description=parsed.get("description", ""),
            type=parsed.get("type", "other"),
            priority=parsed.get("priority", "medium"),
            due_date=parsed.get("due_date"),
            due_time=parsed.get("due_time"),
            success=True,
        )
    except Exception as e:
        logger.error(f"Task parse error: {e}")
        return TaskParseResponse(title=data.text[:200], description=data.text, success=True)




@router.get("/status")
async def voice_status():
    """Check if voice transcription is available"""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    
    return {
        "available": WHISPER_AVAILABLE and bool(api_key),
        "whisper_installed": WHISPER_AVAILABLE,
        "api_key_configured": bool(api_key)
    }


# ============= VOICEMAIL ENDPOINTS =============

@router.get("/voicemail/{user_id}")
async def get_voicemail(user_id: str):
    """Get user's voicemail greeting URL"""
    db = get_db()
    
    voicemail = await db.voicemails.find_one({"user_id": user_id})
    
    if not voicemail:
        return {"voicemail_url": None, "has_voicemail": False}
    
    return {
        "voicemail_url": voicemail.get("audio_data"),
        "has_voicemail": True,
        "created_at": voicemail.get("created_at").isoformat() if voicemail.get("created_at") else None,
        "duration_seconds": voicemail.get("duration_seconds")
    }


@router.post("/voicemail/{user_id}")
async def save_voicemail(
    user_id: str,
    file: UploadFile = File(...)
):
    """Save user's voicemail greeting"""
    db = get_db()
    
    try:
        # Read the audio file
        audio_content = await file.read()
        
        # Convert to base64 for storage
        import base64
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        audio_data = f"data:audio/m4a;base64,{audio_base64}"
        
        # Upsert voicemail record
        await db.voicemails.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "audio_data": audio_data,
                "content_type": file.content_type or "audio/m4a",
                "filename": file.filename or "voicemail.m4a",
                "size_bytes": len(audio_content),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        
        logger.info(f"Saved voicemail for user {user_id}: {len(audio_content)} bytes")
        
        return {"success": True, "message": "Voicemail saved successfully"}
        
    except Exception as e:
        logger.error(f"Voicemail save error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save voicemail: {str(e)}")


@router.delete("/voicemail/{user_id}")
async def delete_voicemail(user_id: str):
    """Delete user's voicemail greeting"""
    db = get_db()
    
    result = await db.voicemails.delete_one({"user_id": user_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No voicemail found")
    
    logger.info(f"Deleted voicemail for user {user_id}")
    
    return {"success": True, "message": "Voicemail deleted"}
