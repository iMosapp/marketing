"""Files & photos on a contact. Chunked upload (same base64 pieces as voice memos), list, detail, rename/retype, apply Jessi's fields
to the contact, delete. Sensitive files are served through short-lived signed links; everything else through the immutable /api/images path."""
import base64
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from routers.database import get_db, get_data_filter
from routers.lead_sources import require_user
from services import contact_files as cf
from services import doc_reminders as dr
from utils.image_storage import get_object
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contact-files", tags=["contact-files"], dependencies=[Depends(require_user)])
open_router = APIRouter(prefix="/contact-files/open", tags=["contact-files"])


class FileChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    name: str = ""
    content_type: str = "application/octet-stream"
    contact_id: str
    hint: Optional[str] = None


class ApplyBody(BaseModel):
    fields: list


class ReminderBody(BaseModel):
    key: str
    decision: str = "create"   # create | dismiss


def _caller(request: Request) -> dict:
    return request.state.user


def _me(request: Request, user_id: str):
    u = _caller(request)
    if str(u.get("_id")) != user_id and u.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Not your files")


async def _contact(db, caller_id: str, contact_id: str) -> dict:
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    c = await db.contacts.find_one({"_id": ObjectId(contact_id), **(await get_data_filter(caller_id))})
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c


async def _file(db, caller_id: str, file_id: str) -> dict:
    if not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=404, detail="File not found")
    rows = await db.contact_files.find({"_id": ObjectId(file_id), "deleted": {"$ne": True}}).to_list(1)
    if not rows:
        raise HTTPException(status_code=404, detail="File not found")
    await _contact(db, caller_id, rows[0]["contact_id"])
    if rows[0].get("sensitive") and str(rows[0].get("user_id")) != str(caller_id):
        raise HTTPException(status_code=404, detail="File not found")
    return rows[0]


@router.post("/{user_id}/chunk")
async def upload_chunk(user_id: str, chunk: FileChunk, request: Request):
    """Base64 pieces, assembled on the last one, then stored and read by Jessi (5 to 20 s). Returns {file} on the last piece."""
    _me(request, user_id)
    db = get_db()
    if chunk.total < 1 or chunk.total > 120 or not (0 <= chunk.index < chunk.total) or len(chunk.data) > 900_000:
        raise HTTPException(status_code=400, detail="Bad chunk")
    upload_id = re.sub(r"[^A-Za-z0-9_-]", "", chunk.upload_id)[:64]
    if not upload_id:
        raise HTTPException(status_code=400, detail="Bad upload id")
    await _contact(db, str(_caller(request)["_id"]), chunk.contact_id)
    await db.voice_upload_chunks.update_one({"user_id": user_id, "upload_id": upload_id, "index": chunk.index},
                                            {"$set": {"data": chunk.data, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    have = await db.voice_upload_chunks.count_documents({"user_id": user_id, "upload_id": upload_id})
    if have < chunk.total:
        return {"success": True, "received": have, "total": chunk.total}
    parts = await db.voice_upload_chunks.find({"user_id": user_id, "upload_id": upload_id}).sort("index", 1).to_list(chunk.total)
    await db.voice_upload_chunks.delete_many({"user_id": user_id, "upload_id": upload_id})
    try:
        data = base64.b64decode("".join(p["data"] for p in parts))
    except Exception:
        raise HTTPException(status_code=400, detail="That file came through damaged. Please try again.")
    hint = chunk.hint if chunk.hint in cf.SCAN_TYPES else None
    try:
        doc = await cf.save_file(db, user_id=user_id, contact_id=chunk.contact_id, name=chunk.name, content_type=chunk.content_type, data=data, hint=hint)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ContactFiles] save failed: {e}")
        raise HTTPException(status_code=500, detail="Could not store that file")
    return {"success": True, "received": chunk.total, "total": chunk.total, "file": cf.public(doc, user_id)}


@router.get("/{user_id}/contact/{contact_id}")
async def list_files(user_id: str, contact_id: str, request: Request):
    _me(request, user_id)
    db = get_db()
    caller_id = str(_caller(request)["_id"])
    await _contact(db, caller_id, contact_id)
    rows = await db.contact_files.find({"contact_id": contact_id, "deleted": {"$ne": True}}, {"text": 0}).sort("created_at", -1).to_list(300)
    rows = [r for r in rows if not r.get("sensitive") or str(r.get("user_id")) == caller_id]
    return {"files": [cf.public(r, caller_id) for r in rows], "scan_types": cf.SCAN_TYPES, "sensitive_types": sorted(cf.SENSITIVE_TYPES), "ttl_days": cf.SENSITIVE_TTL_DAYS}


@router.get("/{user_id}/{file_id}")
async def file_detail(user_id: str, file_id: str, request: Request):
    _me(request, user_id)
    caller_id = str(_caller(request)["_id"])
    doc = await _file(get_db(), caller_id, file_id)
    return cf.public(doc, caller_id)


@router.patch("/{user_id}/{file_id}")
async def update_file(user_id: str, file_id: str, data: dict, request: Request):
    """Rename, retype (a sensitive type locks it down and starts the 30 day clock), or toggle sensitive by hand."""
    _me(request, user_id)
    db = get_db()
    caller_id = str(_caller(request)["_id"])
    doc = await _file(db, caller_id, file_id)
    data = data or {}
    upd: dict = {}
    if "name" in data:
        upd["name"] = no_em_dash(str(data.get("name") or "")).strip()[:120] or doc["name"]
    if "title" in data:
        upd["title"] = no_em_dash(str(data.get("title") or "")).strip()[:60]
    if "scan_type" in data:
        if data["scan_type"] not in cf.SCAN_TYPES:
            raise HTTPException(status_code=400, detail="Unknown type")
        upd["scan_type"] = data["scan_type"]
        if data["scan_type"] in cf.SENSITIVE_TYPES:
            upd["sensitive"] = True
    if "sensitive" in data:
        upd["sensitive"] = bool(data["sensitive"])
    if not upd:
        raise HTTPException(status_code=400, detail="Nothing to change")
    unset = {}
    if upd.get("sensitive") and not doc.get("sensitive"):
        upd["expires_at"] = datetime.now(timezone.utc) + timedelta(days=cf.SENSITIVE_TTL_DAYS)
    elif "sensitive" in upd and not upd["sensitive"]:
        if (upd.get("scan_type") or doc.get("scan_type")) in cf.SENSITIVE_TYPES:
            raise HTTPException(status_code=400, detail="IDs, insurance cards and credit applications always stay sensitive")
        unset["expires_at"] = ""
    ops = {"$set": upd}
    if unset:
        ops["$unset"] = unset
    await db.contact_files.update_one({"_id": doc["_id"]}, ops)
    doc = await db.contact_files.find_one({"_id": doc["_id"]})
    return cf.public(doc, caller_id)


@router.post("/{user_id}/{file_id}/apply")
async def apply_to_contact(user_id: str, file_id: str, body: ApplyBody, request: Request):
    """Write the chosen fields Jessi read (name, company, phone, address, VIN...) onto the contact."""
    _me(request, user_id)
    db = get_db()
    caller_id = str(_caller(request)["_id"])
    doc = await _file(db, caller_id, file_id)
    contact = await _contact(db, caller_id, doc["contact_id"])
    wanted = [k for k in body.fields if isinstance(k, str) and k in cf.FIELD_LABELS]
    if not wanted:
        raise HTTPException(status_code=400, detail="Pick at least one detail")
    res = await cf.apply_fields(db, doc, contact, wanted)
    if res["applied"]:
        now = datetime.now(timezone.utc)
        await db.contact_events.insert_one({"event_type": "file_applied", "title": "Details added from a file", "description": ", ".join(f"{cf.FIELD_LABELS[k]}: {v}" for k, v in res["applied"].items())[:200],
                                            "contact_id": doc["contact_id"], "user_id": user_id, "category": "file", "icon": "checkmark-done", "color": "#34C759",
                                            "metadata": {"file_id": str(doc["_id"]), "fields": list(res["applied"])}, "timestamp": now, "created_at": now})
    return {"ok": True, **res, "labels": {k: cf.FIELD_LABELS[k] for k in res["applied"]}}


@router.post("/{user_id}/{file_id}/reminders")
async def decide_reminder(user_id: str, file_id: str, body: ReminderBody, request: Request):
    """Create (or dismiss) one reminder Jessi suggested from a document's dates. A task for the rep only; nothing is sent."""
    _me(request, user_id)
    db = get_db()
    caller_id = str(_caller(request)["_id"])
    doc = await _file(db, caller_id, file_id)
    contact = await _contact(db, caller_id, doc["contact_id"])
    try:
        r = await dr.decide(db, user_id, doc, contact, body.key, "dismiss" if body.decision == "dismiss" else "create")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "reminder": r, "file": cf.public(await db.contact_files.find_one({"_id": doc["_id"]}), caller_id)}


@router.delete("/{user_id}/{file_id}")
async def delete_file(user_id: str, file_id: str, request: Request):
    _me(request, user_id)
    db = get_db()
    caller_id = str(_caller(request)["_id"])
    doc = await _file(db, caller_id, file_id)
    if str(doc.get("user_id")) != caller_id and _caller(request).get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only the rep who filed it or a manager can delete it")
    await cf.destroy_file(db, doc)
    return {"ok": True}


@open_router.get("/{token}")
async def open_file(token: str, thumb: int = 0):
    """Signed, short-lived link for sensitive files (the only way their bytes leave the server)."""
    fid = cf.verify_open_token(token)
    if not fid or not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="Link expired")
    doc = await get_db().contact_files.find_one({"_id": ObjectId(fid), "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    path = doc.get("thumb_path") if thumb and doc.get("thumb_path") else doc["path"]
    try:
        data, ct = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=data, media_type=ct or doc.get("content_type"), headers={"Cache-Control": "private, no-store", "Content-Disposition": f"inline; filename=\"{doc.get('name') or 'file'}\""})
