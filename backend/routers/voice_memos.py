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
    people, suggested = n.get("people") or [], n.get("suggested_contacts") or []
    heard = {s.get("heard") for s in suggested}
    return {"id": str(n["_id"]), "audio_url": n.get("audio_url"), "transcript": n.get("transcript") or "", "summary": n.get("summary") or "",
            "title": n.get("title") or "", "duration": n.get("duration") or 0, "created_at": n["created_at"].isoformat() if n.get("created_at") else "",
            "contact_id": n.get("contact_id"), "contact_name": n.get("contact_name") or "", "kind": n.get("kind") or "memo",
            "attached_at": n["attached_at"].isoformat() if n.get("attached_at") else "", "tags": n.get("tags") or [],
            "people": people, "suggested_contacts": suggested,
            # Names Jessi heard that match nobody in the book: the app offers to create them as new contacts.
            "new_people": [p for p in people if p.get("name") not in heard]}


def _clean_tags(raw) -> list:
    out: list = []
    for t in (raw or []) if isinstance(raw, list) else []:
        s = " ".join(str(t).split())[:40]
        if s and s.lower() not in {x.lower() for x in out}:
            out.append(s)
    return out[:20]


MEMO_PROJECTION = {"audio_url": 1, "transcript": 1, "summary": 1, "title": 1, "duration": 1, "created_at": 1, "contact_id": 1, "contact_name": 1,
                   "people": 1, "suggested_contacts": 1, "tags": 1, "kind": 1, "attached_at": 1, "unattached": 1}
MEMO_OWN = {"$or": [{"unattached": True}, {"attached_at": {"$exists": True}}]}  # notes that came through the memo flow (not notes recorded on a contact directly)


async def _title_and_summary(transcript: str) -> dict:
    """One short call: a 3-6 word title, a two-sentence summary and the people named in the memo (so Jessi can guess who it is about)."""
    empty = {"title": "", "summary": "", "people": []}
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key or len(transcript.strip()) < 40:
        return empty
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=api_key, session_id=f"memo_{uuid.uuid4().hex[:8]}",
                       system_message=("You title and summarize a salesperson's voice memo and list the people it names. Reply with JSON only: "
                                       "{\"title\": \"3 to 6 words\", \"summary\": \"two plain sentences, no em dashes\", "
                                       "\"people\": [{\"name\": \"full name as spoken\", \"company\": \"their company or dealership if said, else empty\"}]}. "
                                       "Only real people who are named (first name alone counts); never the speaker; at most 6.")).with_model(*CUSTOMER_TEXT_MODEL)
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=transcript[:6000])), timeout=30)
        m = re.search(r"\{.*\}", out if isinstance(out, str) else str(out), re.S)
        d = json.loads(m.group(0)) if m else {}
        people = [{"name": " ".join(str(p.get("name") or "").split())[:60], "company": " ".join(str(p.get("company") or "").split())[:60]}
                  for p in (d.get("people") or []) if isinstance(p, dict) and str(p.get("name") or "").strip()][:6]
        return {"title": no_em_dash(str(d.get("title") or ""))[:60], "summary": no_em_dash(str(d.get("summary") or ""))[:600], "people": people}
    except Exception as e:
        logger.warning(f"[VoiceMemo] title/summary skipped: {e}")
        return empty


def _cname(c: dict) -> str:
    return c.get("name") or " ".join(x for x in [c.get("first_name"), c.get("last_name")] if x) or c.get("phone") or "Contact"


async def match_people(db, user_id: str, people: list) -> list:
    """Jessi's guess at who the memo is about: the names she heard, looked up in this rep's book (full name beats last name beats first name)."""
    if not people:
        return []
    from routers.database import get_data_filter
    scope = await get_data_filter(user_id)
    found: dict = {}
    for p in people[:6]:
        tokens = [t for t in re.split(r"[\s,]+", p["name"]) if len(t) >= 2]
        if not tokens:
            continue
        first, last = tokens[0], tokens[-1] if len(tokens) > 1 else ""
        rx = lambda s: {"$regex": f"^{re.escape(s)}", "$options": "i"}
        ors = [{"first_name": rx(first)}, {"name": rx(first)}]
        if last:
            ors += [{"last_name": rx(last)}, {"name": {"$regex": re.escape(last), "$options": "i"}}]
        if p.get("company"):
            co_rx = {"$regex": re.escape(p["company"].split(" ")[0]), "$options": "i"}
            ors += [{"employer": co_rx}, {"organization_name": co_rx}, {"company": co_rx}]
        rows = await db.contacts.find({**scope, "$or": ors}, {"first_name": 1, "last_name": 1, "name": 1, "company": 1, "employer": 1, "organization_name": 1, "phone": 1}).limit(40).to_list(40)
        for c in rows:
            nm = _cname(c).lower()
            c_company = c.get("employer") or c.get("organization_name") or c.get("company") or ""
            f_ok = nm.startswith(first.lower()) or (c.get("first_name") or "").lower().startswith(first.lower())
            l_ok = bool(last) and ((c.get("last_name") or "").lower().startswith(last.lower()) or last.lower() in nm)
            co_ok = bool(p.get("company")) and p["company"].split(" ")[0].lower() in c_company.lower()
            score = (3 if f_ok and l_ok else 0) + (2 if l_ok and not f_ok else 0) + (1 if f_ok and not l_ok else 0) + (1 if co_ok else 0)
            if score == 0 or (score == 1 and f_ok and len(rows) > 3):
                continue
            cid = str(c["_id"])
            why = f"Jessi heard \"{p['name']}\"" + (f" from {p['company']}" if p.get("company") and co_ok else "")
            if cid not in found or found[cid]["score"] < score:
                found[cid] = {"contact_id": cid, "name": _cname(c), "phone": c.get("phone") or "", "company": c_company, "reason": why, "heard": p["name"], "score": score}
    out = sorted(found.values(), key=lambda r: -r["score"])[:3]
    for r in out:
        r.pop("score", None)
    return out


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
    suggested = await match_people(db, user_id, meta["people"])
    now = datetime.now(timezone.utc)
    doc = {"contact_id": None, "unattached": True, "user_id": user_id, "audio_url": f"/api/images/{stored_path}", "audio_path": stored_path,
           "transcript": transcript, "summary": meta["summary"], "title": meta["title"], "people": meta["people"], "suggested_contacts": suggested,
           "kind": "memo", "duration": round(chunk.duration, 1), "created_at": now, "source": "app", "tags": []}
    res = await db.voice_notes.insert_one(doc)
    return {**_public({**doc, "_id": res.inserted_id}), "success": True, "received": chunk.total, "total": chunk.total}


@router.get("/{user_id}")
async def list_memos(user_id: str, request: Request, view: str = "unattached"):
    """view=unattached (default): the to-file pile. view=attached: memos already filed on a contact, newest filing first.
    Also returns the user's day labels ("NADA show day 2") and both counts for the segmented control."""
    _me(request, user_id)
    db = get_db()
    attached = view == "attached"
    q = {"user_id": user_id, "attached_at": {"$exists": True}} if attached else {"user_id": user_id, "unattached": True}
    rows = await db.voice_notes.find(q, MEMO_PROJECTION).sort("attached_at" if attached else "created_at", -1).to_list(300)
    # Jessi re-checks her guesses on every open: a contact added after the memo (e.g. "They are not in my contacts yet") shows up next time.
    for n in rows:
        if not attached and n.get("people") and not n.get("contact_id"):
            fresh = await match_people(db, user_id, n["people"])
            if fresh != (n.get("suggested_contacts") or []):
                n["suggested_contacts"] = fresh
                await db.voice_notes.update_one({"_id": n["_id"]}, {"$set": {"suggested_contacts": fresh}})
    counts = {"unattached": await db.voice_notes.count_documents({"user_id": user_id, "unattached": True}),
              "attached": await db.voice_notes.count_documents({"user_id": user_id, "attached_at": {"$exists": True}})}
    labels = await db.voice_memo_days.find({"user_id": user_id}, {"_id": 0, "day": 1, "label": 1}).to_list(500)
    return {"memos": [_public(n) for n in rows], "counts": counts, "day_labels": {d["day"]: d["label"] for d in labels}}


class DayLabelBody(BaseModel):
    day: str        # YYYY-MM-DD in the rep's local time (the app groups by local day)
    label: str = ""


@router.put("/{user_id}/day-label")
async def set_day_label(user_id: str, body: DayLabelBody, request: Request):
    """Name a recording day ("NADA show day 2"); an empty label removes the name."""
    _me(request, user_id)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", body.day):
        raise HTTPException(status_code=400, detail="Bad day")
    label = no_em_dash(" ".join(body.label.split()))[:60]
    db = get_db()
    if label:
        await db.voice_memo_days.update_one({"user_id": user_id, "day": body.day}, {"$set": {"label": label, "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    else:
        await db.voice_memo_days.delete_one({"user_id": user_id, "day": body.day})
    return {"ok": True, "day": body.day, "label": label}


@router.patch("/{user_id}/{note_id}")
async def rename_memo(user_id: str, note_id: str, data: dict, request: Request):
    """Title and/or tags. Works on the to-file pile and on memos already filed on a contact."""
    _me(request, user_id)
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=404, detail="Memo not found")
    data = data or {}
    upd: dict = {}
    if "title" in data:
        upd["title"] = no_em_dash(str(data.get("title") or "")).strip()[:60]
    if "tags" in data:
        upd["tags"] = _clean_tags(data.get("tags"))
    if not upd:
        raise HTTPException(status_code=400, detail="Nothing to change")
    r = await get_db().voice_notes.update_one({"_id": ObjectId(note_id), "user_id": user_id, **MEMO_OWN}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Memo not found")
    return {"ok": True, **upd}


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
