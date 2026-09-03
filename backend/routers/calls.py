"""
Calls router - handles call logs and dialer functionality
"""
from fastapi import APIRouter, HTTPException, Request, Response
from bson import ObjectId
from datetime import datetime, timezone
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
        except Exception:
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
        except Exception:
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


CADENCE_MANAGER_ROLES = ("super_admin", "admin", "manager", "store_manager", "org_admin")


@router.get("/{user_id}/retry-cadence")
async def get_retry_cadence(user_id: str):
    """Per-rep voicemail retry timing (personal -> store -> org default) + a live preview of what a miss right now would schedule."""
    from services.call_followup import resolve_cadence, preview_schedule, _tz_for, DEFAULT_CADENCE, CADENCE_LIMITS
    res = await resolve_cadence(user_id)
    tz = await _tz_for(user_id)
    db = get_db()
    u = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1}) if ObjectId.is_valid(user_id) else None
    return {**res, "defaults": DEFAULT_CADENCE, "limits": {k: list(v) for k, v in CADENCE_LIMITS.items()},
            "timezone": str(tz), "preview": preview_schedule(res["cadence"], tz),
            "is_manager": bool(u and u.get("role") in CADENCE_MANAGER_ROLES), "has_store": bool(u and u.get("store_id"))}


@router.put("/{user_id}/retry-cadence")
async def save_retry_cadence(user_id: str, data: dict):
    """Personal override for this rep."""
    from services.call_followup import normalize_cadence, preview_schedule, _tz_for
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user")
    cadence = normalize_cadence(data or {})
    db = get_db()
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"call_retry_cadence": cadence}})
    tz = await _tz_for(user_id)
    return {"success": True, "cadence": cadence, "source": "personal", "preview": preview_schedule(cadence, tz)}


@router.delete("/{user_id}/retry-cadence")
async def clear_retry_cadence(user_id: str):
    """Drop the personal override so the rep inherits the store / org default again."""
    from services.call_followup import resolve_cadence, preview_schedule, _tz_for
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user")
    db = get_db()
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$unset": {"call_retry_cadence": ""}})
    res = await resolve_cadence(user_id)
    tz = await _tz_for(user_id)
    return {"success": True, **res, "preview": preview_schedule(res["cadence"], tz)}


async def _cadence_scope(db, user_id: str):
    """Managers edit their store's default; store-less super/org admins edit the org-wide default."""
    u = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1}) if ObjectId.is_valid(user_id) else None
    if not u or u.get("role") not in CADENCE_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Managers only")
    sid = str(u.get("store_id") or "")
    if ObjectId.is_valid(sid):
        return {"scope": "store", "store_id": sid, "rep_filter": {"$or": [{"store_id": sid}, {"store_id": ObjectId(sid)}], "active": {"$ne": False}}}
    if u.get("role") in ("super_admin", "org_admin"):
        return {"scope": "global", "store_id": None, "rep_filter": {"active": {"$ne": False}}}
    raise HTTPException(status_code=400, detail="Your account isn't linked to a store yet")


@router.get("/{user_id}/retry-cadence/store")
async def get_store_retry_cadence(user_id: str):
    from services.call_followup import normalize_cadence, preview_schedule, _tz_for, DEFAULT_CADENCE
    db = get_db()
    scope = await _cadence_scope(db, user_id)
    if scope["scope"] == "store":
        st = await db.stores.find_one({"_id": ObjectId(scope["store_id"])}, {"call_retry_cadence": 1, "name": 1})
        raw, name = (st or {}).get("call_retry_cadence"), (st or {}).get("name") or "your store"
    else:
        g = await db.settings.find_one({"key": "call_retry_cadence_default"}, {"value": 1})
        raw, name = (g or {}).get("value"), "the whole organization"
    reps_total = await db.users.count_documents(scope["rep_filter"])
    reps_custom = await db.users.count_documents({**scope["rep_filter"], "call_retry_cadence": {"$exists": True}})
    cadence = normalize_cadence(raw) if raw else dict(DEFAULT_CADENCE)
    tz = await _tz_for(user_id)
    return {"scope": scope["scope"], "scope_name": name, "is_set": bool(raw), "cadence": cadence, "preview": preview_schedule(cadence, tz),
            "reps_total": reps_total, "reps_with_override": reps_custom}


@router.put("/{user_id}/retry-cadence/store")
async def save_store_retry_cadence(user_id: str, data: dict):
    """Body = cadence fields (+ apply_to_all: true to wipe every rep's personal override so they inherit now)."""
    from services.call_followup import normalize_cadence, preview_schedule, _tz_for
    db = get_db()
    scope = await _cadence_scope(db, user_id)
    cadence = normalize_cadence(data or {})
    now = datetime.now(timezone.utc)
    if scope["scope"] == "store":
        await db.stores.update_one({"_id": ObjectId(scope["store_id"])}, {"$set": {"call_retry_cadence": cadence, "call_retry_cadence_updated_at": now, "call_retry_cadence_updated_by": user_id}})
    else:
        await db.settings.update_one({"key": "call_retry_cadence_default"}, {"$set": {"value": cadence, "updated_at": now, "updated_by": user_id}}, upsert=True)
    cleared = 0
    if data.get("apply_to_all"):
        r = await db.users.update_many({**scope["rep_filter"], "call_retry_cadence": {"$exists": True}}, {"$unset": {"call_retry_cadence": ""}})
        cleared = r.modified_count
    tz = await _tz_for(user_id)
    return {"success": True, "scope": scope["scope"], "cadence": cadence, "preview": preview_schedule(cadence, tz), "overrides_cleared": cleared}


@router.post("/{user_id}/just-tried/{task_id}")
async def just_tried_text(user_id: str, task_id: str):
    """One-tap 'just tried you' SMS from a voicemail retry task; respects the texting window (queues if closed)."""
    from services.call_followup import send_just_tried_text
    res = await send_just_tried_text(user_id, task_id)
    if not res.get("ok"):
        err = res.get("error", "Could not send")
        raise HTTPException(status_code=404 if "not found" in err.lower() else 400, detail=err)
    return res


@router.get("/{user_id}/just-tried-preview/{task_id}")
async def just_tried_preview(user_id: str, task_id: str):
    """What the one-tap text will say (for the button label / confirmation)."""
    from services.call_followup import just_tried_template
    db = get_db()
    task = await db.tasks.find_one({"_id": ObjectId(task_id), "user_id": user_id}) if ObjectId.is_valid(task_id) else None
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    conv = None
    if task.get("conversation_id") and ObjectId.is_valid(str(task["conversation_id"])):
        conv = await db.conversations.find_one({"_id": ObjectId(str(task["conversation_id"]))}, {"lead_source_id": 1})
    template, source = await just_tried_template(db, user_id, conv)
    first = (task.get("contact_name") or "there").split(" ")[0]
    return {"template": template, "source": source, "preview": template.replace("{first_name}", first)}


@router.post("/{user_id}/outcome")
async def log_call_outcome(user_id: str, data: dict):
    """Native-dialer calls: rep picks Talked / Voicemail / No answer / Busy -> same follow-up engine as Twilio calls."""
    outcome = (data.get("outcome") or "").strip()
    if outcome not in ("connected", "voicemail", "no_answer", "busy"):
        raise HTTPException(status_code=400, detail="outcome must be connected, voicemail, no_answer or busy")
    contact_id = str(data.get("contact_id") or "")
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=400, detail="contact_id required")
    from services.call_followup import record_manual_outcome
    return await record_manual_outcome(user_id, contact_id, outcome, int(data.get("duration") or 0),
                                       str(data.get("conversation_id") or ""), str(data.get("task_id") or ""))


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
        except Exception: pass
        
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
                    "You are an expert sales CRM assistant. Analyze this sales call transcript and produce a structured summary.\n\n"
                    "Format your response EXACTLY like this:\n\n"
                    "**CALL SUMMARY**\n"
                    "2-3 sentences capturing what the call was about and the overall outcome.\n\n"
                    "**KEY DETAILS**\n"
                    "• Vehicle/product interest: [what they want]\n"
                    "• Budget: [if mentioned]\n"
                    "• Timeline: [urgency or timeframe]\n"
                    "• Objections: [concerns raised]\n"
                    "• Personal notes: [anything personal — spouse, kids, job, etc.]\n\n"
                    "**FOLLOW-UP ACTIONS**\n"
                    "List 2-4 specific, actionable next steps the rep should take. Be concrete — not 'follow up' but 'Text John about the F-150 availability'.\n\n"
                    "Skip any section where nothing was mentioned. Keep total response under 200 words."
                ),
            ).with_model("openai", "gpt-5.2")
            resp2 = await asyncio.wait_for(
                chat.send_message(UserMessage(text=f"Transcript:\n{transcript}")),
                timeout=20.0
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

        # Auto-extract scheduled appointments from the recovered transcript
        try:
            from routers.tasks import extract_appointment_from_call
            asyncio.create_task(extract_appointment_from_call(
                log.get("user_id") or "", log.get("contact_id") or "",
                log.get("contact_name") or "", transcript, call_sid
            ))
        except Exception:
            pass
        
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


@router.get("/recording/{call_sid}")
async def stream_recording(call_sid: str, request: Request):
    """Stream a call recording through the backend (Twilio auth server-side).
    Supports HTTP Range so iOS/web players can seek and change speed smoothly."""
    import os as _os
    import re as _re
    import httpx as _httpx

    db = get_db()
    log = await db.call_logs.find_one({"call_sid": call_sid}, {"recording_url": 1, "recording_sid": 1})
    if not log or not log.get("recording_url"):
        raise HTTPException(status_code=404, detail="Recording not found")

    tw_sid = _os.environ.get("TWILIO_ACCOUNT_SID")
    tw_token = _os.environ.get("TWILIO_AUTH_TOKEN")
    if not tw_sid or not tw_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not configured")

    cache_key = (log.get("recording_sid") or call_sid).replace("/", "_")
    cache_path = f"/tmp/rec_cache_{cache_key}.mp3"

    if not _os.path.exists(cache_path):
        url = log["recording_url"]
        mp3_url = url if url.endswith(".mp3") else f"{url}.mp3"
        async with _httpx.AsyncClient() as client:
            resp = await client.get(mp3_url, auth=(tw_sid, tw_token), follow_redirects=True, timeout=60.0)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Recording fetch failed: HTTP {resp.status_code}")
        tmp = cache_path + ".part"
        with open(tmp, "wb") as f:
            f.write(resp.content)
        _os.replace(tmp, cache_path)

    file_size = _os.path.getsize(cache_path)
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}

    range_header = request.headers.get("range")
    if range_header:
        m = _re.match(r"bytes=(\d*)-(\d*)", range_header)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            raise HTTPException(status_code=416, detail="Invalid range")
        with open(cache_path, "rb") as f:
            f.seek(start)
            data = f.read(end - start + 1)
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        return Response(content=data, status_code=206, headers=headers, media_type="audio/mpeg")

    with open(cache_path, "rb") as f:
        data = f.read()
    return Response(content=data, headers=headers, media_type="audio/mpeg")
