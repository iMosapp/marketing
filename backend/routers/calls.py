"""
Calls router - handles call logs and dialer functionality
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

from models import Call, CallCreate
from routers.database import get_db, get_data_filter, increment_user_stat

router = APIRouter(prefix="/calls", tags=["Calls"])
logger = logging.getLogger(__name__)

@router.post("/{user_id}", response_model=Call)
async def create_call_log(user_id: str, call_data: CallCreate):
    """Log a call"""
    call_dict = call_data.dict()
    call_dict['user_id'] = user_id
    call_dict['timestamp'] = datetime.utcnow()
    
    result = await get_db().calls.insert_one(call_dict)
    call_dict['_id'] = result.inserted_id
    
    # Track stat
    await increment_user_stat(user_id, "calls_made")
    
    # If missed call, send auto-text (mocked)
    if call_data.type == "missed":
        try:
            contact = await get_db().contacts.find_one({"_id": ObjectId(call_data.contact_id)})
        except:
            contact = await get_db().contacts.find_one({"_id": call_data.contact_id})
        
        if contact:
            logger.info(f"[MOCK] Auto-text sent to {contact['first_name']}: Hey, I just missed your call!")
            call_dict['auto_text_sent'] = True
            await get_db().calls.update_one(
                {"_id": result.inserted_id},
                {"$set": {"auto_text_sent": True}}
            )
    
    return Call(**call_dict)

@router.get("/{user_id}")
async def get_call_logs(user_id: str, call_type: Optional[str] = None):
    """Get call logs with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    if call_type:
        query = {"$and": [base_filter, {"type": call_type}]}
    else:
        query = base_filter
    
    calls = await get_db().calls.find(query).sort("timestamp", -1).limit(500).to_list(500)
    
    # Enrich with contact info
    result = []
    for call in calls:
        call['_id'] = str(call['_id'])
        try:
            contact = await get_db().contacts.find_one({"_id": ObjectId(call['contact_id'])})
        except:
            contact = await get_db().contacts.find_one({"_id": call['contact_id']})
        
        if contact:
            call['contact'] = {
                "name": f"{contact['first_name']} {contact.get('last_name', '')}".strip(),
                "phone": contact['phone']
            }
        result.append(call)
    
    return result

@router.post("/{user_id}/initiate")
async def initiate_call(user_id: str, data: dict):
    """Initiate an outgoing call (mocked - Twilio pending)"""
    phone_number = data.get('phone_number')
    contact_id = data.get('contact_id')
    
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number is required")
    
    # In production, this would initiate a Twilio call
    logger.info(f"[MOCK] Initiating call to {phone_number}")
    
    # Log the call
    call_dict = {
        "user_id": user_id,
        "contact_id": contact_id,
        "phone_number": phone_number,
        "type": "outgoing",
        "duration": 0,
        "status": "initiated",
        "timestamp": datetime.utcnow()
    }
    
    result = await get_db().calls.insert_one(call_dict)
    call_dict['_id'] = str(result.inserted_id)
    
    return {
        "message": "Call initiated (mocked)",
        "call_id": call_dict['_id'],
        "status": "initiated"
    }


@router.get("/{user_id}/contact/{contact_id}")
async def get_contact_calls(user_id: str, contact_id: str):
    """Get all call logs + recordings for a specific contact."""
    db = get_db()
    # Get regular call logs
    call_logs = await db.calls.find(
        {"contact_id": contact_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50).to_list(50)

    # Get recorded call logs (from twilio recordings)
    recorded = await db.call_logs.find(
        {"contact_id": contact_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50).to_list(50)

    # Get call notes (from voicemail/recording analysis)
    notes = await db.notes.find(
        {"contact_id": contact_id, "type": "call_log"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(20).to_list(20)

    # Serialize dates
    for item in call_logs + recorded + notes:
        for k in ["timestamp", "created_at"]:
            if isinstance(item.get(k), datetime):
                item[k] = item[k].isoformat()

    return {
        "calls":     call_logs,
        "recordings": recorded,
        "notes":     notes,
        "total":     len(call_logs) + len(recorded),
    }



@router.post("/retry-transcription/{call_sid}")
async def retry_transcription(call_sid: str, x_user_id: str = None):
    """
    Re-run Whisper transcription + GPT summary for a call log that failed.
    Used to recover past calls where transcription silently failed.
    """
    import os, asyncio
    db = get_db()
    
    log = await db.call_logs.find_one({"call_sid": call_sid})
    if not log:
        raise HTTPException(status_code=404, detail="Call log not found for this call_sid")
    
    if log.get("transcript"):
        return {"status": "already_transcribed", "transcript_length": len(log["transcript"])}
    
    recording_url = log.get("recording_url", "")
    if not recording_url:
        raise HTTPException(status_code=400, detail="No recording URL on this call log")
    
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    
    if not emergent_key or not tw_sid:
        raise HTTPException(status_code=500, detail="Missing EMERGENT_LLM_KEY or Twilio credentials")
    
    try:
        import requests as _req, uuid as _uuid
        mp3_url = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"
        resp = _req.get(mp3_url, auth=(tw_sid, tw_token), timeout=30)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Recording download failed: HTTP {resp.status_code}")
        
        tmp_path = f"/tmp/retry_{_uuid.uuid4().hex}.mp3"
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
        
        from emergentintegrations.llm.openai import OpenAISpeechToText
        stt = OpenAISpeechToText(api_key=emergent_key)
        with open(tmp_path, "rb") as audio_file:
            result = await asyncio.wait_for(stt.transcribe(audio_file, language="en"), timeout=90.0)
        
        transcript = ""
        if hasattr(result, "text"):
            transcript = result.text.strip()
        elif isinstance(result, str):
            transcript = result.strip()
        
        try: os.remove(tmp_path)
        except: pass
        
        if not transcript:
            return {"status": "empty_transcript", "message": "Whisper returned empty — call may have been silent"}
        
        # Generate GPT summary
        ai_summary = ""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"retry-call-{_uuid.uuid4().hex[:12]}",
                system_message=(
                    "You are a CRM assistant analyzing a sales call transcript.\n"
                    "Extract these if mentioned — be brief and use bullet points:\n"
                    "- What they're looking for\n- Timeline or urgency\n- Objections or concerns\n"
                    "- Next steps or commitments\nMax 120 words."
                ),
            ).with_model("openai", "gpt-5.2")
            resp2 = await asyncio.wait_for(
                chat.send_message(UserMessage(text=f"Transcript:\n{transcript}")),
                timeout=15.0
            )
            ai_summary = (resp2.strip() if isinstance(resp2, str) else resp2.text.strip() if hasattr(resp2, "text") else "").strip()
        except Exception:
            pass
        
        # Update call_log + contact_event
        await db.call_logs.update_one(
            {"call_sid": call_sid},
            {"$set": {"transcript": transcript, "ai_summary": ai_summary}}
        )
        await db.contact_events.update_one(
            {"call_sid": call_sid},
            {"$set": {"has_recording": True, "ai_summary": ai_summary, "transcript": transcript[:200]}}
        )
        
        logger.info(f"[Calls] Retry transcription succeeded for {call_sid}: {len(transcript)} chars")
        return {
            "status": "success",
            "transcript_length": len(transcript),
            "has_summary": bool(ai_summary),
            "transcript_preview": transcript[:200],
            "ai_summary": ai_summary,
        }
    
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Whisper transcription timed out (90s)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
