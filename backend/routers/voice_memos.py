"""Voice memos that are not about anyone yet: record a talk, a walk-around or a thought from the + menu, then attach it to a contact
later and it becomes a normal voice note (or recorded conversation) on that record with the full Jessi treatment."""
import asyncio
import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.lead_sources import require_user
from routers.voice_notes import MAX_CONVERSATION_SECONDS, _convert_webm_to_m4a, _ext_for, _transcribe_audio, put_object
from services.llm_models import CUSTOMER_TEXT_MODEL
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice-memos", tags=["voice-memos"], dependencies=[Depends(require_user)])


class AudioChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    content_type: str = "audio/mp4"
    duration: float = 0


class AttachBody(BaseModel):
    contact_id: str
    as_kind: str = "memo"       # memo | conversation


def _me(request: Request, user_id: str):
    if str(request.state.user.get("_id")) != user_id and request.state.user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Not your memos")


def _public(n: dict) -> dict:
    return {"id": str(n["_id"]), "audio_url": n.get("audio_url"), "transcript": n.get("transcript") or "", "summary": n.get("summary") or "",
            "title": n.get("title") or "", "duration": n.get("duration") or 0, "created_at": n["created_at"].isoformat() if n.get("created_at") else "",
            "contact_id": n.get("contact_id"), "contact_name": n.get("contact_name") or ""}


async def _title_and_summary(transcript: str) -> dict:
    """One short call: a 3-6 word title and a two-sentence summary so the memo list is browsable without replaying anything."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key or len(transcript.strip()) < 40:
        return {"title": "", "summary": ""}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=api_key, session_id=f"memo_{uuid.uuid4().hex[:8]}",
                       system_message="You title and summarize a salesperson's voice memo. Reply with JSON only: {\"title\": \"3 to 6 words\", \"summary\": \"two plain sentences, no em dashes\"}.").with_model(*CUSTOMER_TEXT_MODEL)
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=transcript[:6000])), timeout=30)
        m = re.search(r"\{.*\}", out if isinstance(out, str) else str(out), re.S)
        d = json.loads(m.group(0)) if m else {}
        return {"title": no_em_dash(str(d.get("title") or ""))[:60], "summary": no_em_dash(str(d.get("summary") or ""))[:600]}
    except Exception as e:
        logger.warning(f"[VoiceMemo] title/summary skipped: {e}")
        return {"title": "", "summary": ""}


@router.post("/{user_id}/chunk")
async def upload_memo_chunk(user_id: str, chunk: AudioChunk, request: Request):
    """Same chunked upload as recorded conversations (base64 pieces, assembled on the last one); up to 45 minutes."""
    _me(request, user_id)
    db = get_db()
    if chunk.total < 1 or chunk.total > 200 or not (0 <= chunk.index < chunk.total) or len(chunk.data) > 900_000:
        raise HTTPException(status_code=400, detail="Bad chunk")
    upload_id = re.sub(r"[^A-Za-z0-9_-]", "", chunk.upload_id)[:64]
    if not upload_id:
        raise HTTPException(status_code=400, detail="Bad upload id")
    if chunk.duration > MAX_CONVERSATION_SECONDS:
        raise HTTPException(status_code=400, detail=f"Recording exceeds the {MAX_CONVERSATION_SECONDS // 60} minute limit")
    await db.voice_upload_chunks.update_one({"user_id": user_id, "upload_id": upload_id, "index": chunk.index},
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

    ext, content_type = _ext_for(chunk.content_type), chunk.content_type
    if ext == "webm":
        try:
            audio_bytes = await asyncio.to_thread(_convert_webm_to_m4a, audio_bytes)
            ext, content_type = "m4a", "audio/mp4"
        except Exception as e:
            logger.warning(f"[VoiceMemo] webm to m4a failed, keeping webm: {e}")
    filename = f"memo_{uuid.uuid4().hex[:8]}.{ext}"
    storage_path = f"voice-notes/unattached/{user_id}/{filename}"
    try:
        stored = put_object(storage_path, audio_bytes, content_type)
        stored_path = stored.get("path") or storage_path
    except Exception as e:
        logger.error(f"[VoiceMemo] upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to store audio")

    transcript = await _transcribe_audio(audio_bytes, filename, "memo")
    meta = await _title_and_summary(transcript)
    now = datetime.now(timezone.utc)
    doc = {"contact_id": None, "unattached": True, "user_id": user_id, "audio_url": f"/api/images/{stored_path}", "audio_path": stored_path,
           "transcript": transcript, "summary": meta["summary"], "title": meta["title"], "kind": "memo", "duration": round(chunk.duration, 1),
           "created_at": now, "source": "app"}
    res = await db.voice_notes.insert_one(doc)
    return {**_public({**doc, "_id": res.inserted_id}), "success": True, "received": chunk.total, "total": chunk.total}


@router.get("/{user_id}")
async def list_memos(user_id: str, request: Request, include_attached: bool = False):
    _me(request, user_id)
    db = get_db()
    q = {"user_id": user_id, "unattached": True} if not include_attached else {"user_id": user_id, "$or": [{"unattached": True}, {"attached_at": {"$exists": True}}]}
    rows = await db.voice_notes.find(q, {"audio_url": 1, "transcript": 1, "summary": 1, "title": 1, "duration": 1, "created_at": 1, "contact_id": 1, "contact_name": 1}).sort("created_at", -1).to_list(200)
    return {"memos": [_public(n) for n in rows]}


@router.patch("/{user_id}/{note_id}")
async def rename_memo(user_id: str, note_id: str, data: dict, request: Request):
    _me(request, user_id)
    title = no_em_dash(str((data or {}).get("title") or "")).strip()[:60]
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=404, detail="Memo not found")
    r = await get_db().voice_notes.update_one({"_id": ObjectId(note_id), "user_id": user_id, "unattached": True}, {"$set": {"title": title}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Memo not found")
    return {"ok": True, "title": title}


@router.delete("/{user_id}/{note_id}")
async def delete_memo(user_id: str, note_id: str, request: Request):
    _me(request, user_id)
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=404, detail="Memo not found")
    r = await get_db().voice_notes.delete_one({"_id": ObjectId(note_id), "user_id": user_id, "unattached": True})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Memo not found")
    return {"ok": True}


@router.post("/{user_id}/{note_id}/attach")
async def attach_memo(user_id: str, note_id: str, body: AttachBody, request: Request):
    """Pin the memo to a contact. From here on it is a regular voice note (or a recorded conversation with summary + tasks) on that record."""
    _me(request, user_id)
    db = get_db()
    if not ObjectId.is_valid(note_id) or not ObjectId.is_valid(body.contact_id):
        raise HTTPException(status_code=404, detail="Memo or contact not found")
    note = await db.voice_notes.find_one({"_id": ObjectId(note_id), "user_id": user_id, "unattached": True})
    if not note:
        raise HTTPException(status_code=404, detail="Memo not found (it may already be attached)")
    from routers.database import get_data_filter
    contact = await db.contacts.find_one({"_id": ObjectId(body.contact_id), **(await get_data_filter(user_id))}, {"name": 1, "first_name": 1, "last_name": 1, "user_id": 1})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact_id = str(contact["_id"])
    contact_name = contact.get("name") or " ".join(x for x in [contact.get("first_name"), contact.get("last_name")] if x) or "Contact"
    as_convo = body.as_kind == "conversation"
    transcript = note.get("transcript") or ""
    now = datetime.now(timezone.utc)

    summary, title, highlights, tasks = note.get("summary") or "", note.get("title") or "", [], []
    if as_convo and len(transcript.strip()) >= 40:
        from services.recording_highlights import process_recorded_conversation
        hl = await process_recorded_conversation(db, user_id, contact_id, note_id, transcript)
        summary, title, highlights, tasks = hl["summary"] or summary, hl["title"] or title, hl["highlights"], hl["tasks"]

    await db.voice_notes.update_one({"_id": note["_id"]}, {"$set": {"contact_id": contact_id, "contact_name": contact_name, "kind": "conversation" if as_convo else "memo",
                                                                    "summary": summary, "title": title, "attached_at": now}, "$unset": {"unattached": ""}})
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "org_id": 1})
        await db.contact_events.insert_one({
            "event_type": "conversation_recorded" if as_convo else "voice_note",
            "title": "In-person conversation recorded" if as_convo else "Voice memo attached",
            "description": (summary or transcript)[:200] if (summary or transcript) else "Audio memo attached",
            "contact_id": contact_id, "user_id": user_id, "org_id": (user_doc or {}).get("org_id", ""),
            "channel": "voice_note", "category": "voice_note", "icon": "people" if as_convo else "mic", "color": "#C9A962" if as_convo else "#34C759",
            "content": summary or transcript or "",
            "metadata": {"voice_note_id": note_id, "duration": note.get("duration") or 0, "kind": "conversation" if as_convo else "memo", "source": "memo_attach", "recorded_at": note.get("created_at")},
            "timestamp": now, "created_at": now,
        })
    except Exception as e:
        logger.error(f"[VoiceMemo] event log failed: {e}")
    if len(transcript.strip()) >= 10:
        try:
            from services.voice_intel import process_voice_note_intelligence
            asyncio.create_task(process_voice_note_intelligence(user_id, contact_id, transcript, note_id))
        except Exception as e:
            logger.warning(f"[VoiceMemo] intelligence trigger failed: {e}")
    return {"ok": True, "contact_id": contact_id, "contact_name": contact_name, "kind": "conversation" if as_convo else "memo",
            "summary": summary, "title": title, "highlights": highlights, "tasks": tasks}
