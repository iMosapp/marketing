"""
Jessie AI Assistant Router
API endpoints for the voice-enabled AI assistant
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io

router = APIRouter(prefix="/jessie", tags=["Jessie AI Assistant"])


class ChatMessage(BaseModel):
    user_id: str
    message: str
    include_voice: bool = False
    current_page: str = ""


class VoiceMessage(BaseModel):
    user_id: str
    text: str  # Transcribed voice input


@router.post("/chat")
async def chat_with_jessie(data: ChatMessage):
    """
    Send a text message to Jessie and get a response.
    Optionally includes voice audio in the response.
    """
    from services.jessie_service import chat_with_jessie as jessie_chat, generate_voice_response_base64
    
    try:
        # Get Jessie's text response
        result = await jessie_chat(data.user_id, data.message, current_page=data.current_page)
        
        response = {
            "text": result["text"],
            "session_id": result["session_id"],
        }
        
        # Generate voice if requested
        if data.include_voice:
            try:
                audio_base64 = await generate_voice_response_base64(result["text"])
                response["audio_base64"] = audio_base64
                response["audio_format"] = "mp3"
            except Exception as e:
                print(f"Voice generation failed: {e}")
                response["voice_error"] = str(e)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice-chat")
async def voice_chat_with_jessie(data: VoiceMessage):
    """
    Handle voice input (already transcribed) and return voice response.
    """
    from services.jessie_service import chat_with_jessie as jessie_chat, generate_voice_response_base64
    
    try:
        # Get Jessie's text response
        result = await jessie_chat(data.user_id, data.text)
        
        # Generate voice response
        audio_base64 = await generate_voice_response_base64(result["text"])
        
        return {
            "text": result["text"],
            "audio_base64": audio_base64,
            "audio_format": "mp3",
            "session_id": result["session_id"],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{user_id}")
async def get_chat_history(user_id: str, limit: int = 50):
    """Get chat history for a user"""
    from services.jessie_service import get_chat_history as get_history
    
    try:
        messages = await get_history(user_id, limit=limit)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{user_id}")
async def clear_chat_history(user_id: str):
    """Clear chat history and start fresh"""
    from services.jessie_service import clear_chat_history as clear_history
    
    try:
        result = await clear_history(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(data: dict):
    """
    Generate voice audio from text.
    Used for playing individual messages.
    """
    from services.jessie_service import generate_voice_response
    
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    if len(text) > 4096:
        raise HTTPException(status_code=400, detail="Text too long (max 4096 characters)")
    
    try:
        audio_bytes = await generate_voice_response(text)
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=jessie_response.mp3"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{user_id}")
async def get_session(user_id: str):
    """Get or create a chat session for the user"""
    from services.jessie_service import get_or_create_chat_session
    
    try:
        session = await get_or_create_chat_session(user_id)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ProfileExtractRequest(BaseModel):
    user_id: str
    text: str
    context: str = "intro"  # intro, hobbies, family, expertise


@router.post("/extract-profile")
async def extract_profile_from_voice(data: ProfileExtractRequest):
    """
    Extract structured profile information from voice transcription.
    Uses AI to parse natural speech into profile fields.
    """
    from services.jessie_service import extract_profile_info
    
    try:
        extracted = await extract_profile_info(data.text, data.context)
        return {
            "success": True,
            "extracted": extracted,
            "context": data.context
        }
    except Exception as e:
        print(f"Profile extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
