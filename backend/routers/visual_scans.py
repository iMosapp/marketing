"""Scan with Jessi: upload + read a card / photo / PDF before a contact exists, review possible existing contacts, then save it to a new or
existing contact with only the details the rep ticks. Owner-only until saved; follows the Photo Intelligence rollout and Pause All."""
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db, get_data_filter
from routers.lead_sources import require_user
from services import contact_files as cf
from services import visual_intel as vi

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["scan-with-jessi"], dependencies=[Depends(require_user)])


class ScanChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    name: str = ""
    content_type: str = "application/octet-stream"
    capture: Optional[str] = None


class SaveBody(BaseModel):
    contact_id: str
    fields: list = []
    values: dict = {}


def _me(request: Request, user_id: str) -> dict:
    u = request.state.user
    if str(u.get("_id")) != user_id:
        raise HTTPException(status_code=403, detail="Not your scan")
    return u


async def _scan(db, user_id: str, scan_id: str) -> dict:
    doc = await vi.pending(db, user_id, scan_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Scan not found")
    return doc


@router.get("/{user_id}/status")
async def scan_status(user_id: str, request: Request):
    _me(request, user_id)
    return await vi.status(get_db(), user_id)


@router.post("/{user_id}/chunk")
async def upload_chunk(user_id: str, chunk: ScanChunk, request: Request):
    """Base64 pieces (same as Files). On the last piece the image is stored owner-only and read once; returns the review + possible matches."""
    me = _me(request, user_id)
    db = get_db()
    if not (await vi.status(db, user_id))["enabled"]:
        raise HTTPException(status_code=403, detail="Scan with Jessi is not on for your account yet")
    if chunk.total < 1 or chunk.total > 120 or not (0 <= chunk.index < chunk.total) or len(chunk.data) > 900_000:
        raise HTTPException(status_code=400, detail="Bad chunk")
    upload_id = re.sub(r"[^A-Za-z0-9_-]", "", chunk.upload_id)[:64]
    if not upload_id:
        raise HTTPException(status_code=400, detail="Bad upload id")
    key = f"scan_{upload_id}"
    await db.voice_upload_chunks.update_one({"user_id": user_id, "upload_id": key, "index": chunk.index},
                                            {"$set": {"data": chunk.data, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    have = await db.voice_upload_chunks.count_documents({"user_id": user_id, "upload_id": key})
    if have < chunk.total:
        return {"success": True, "received": have, "total": chunk.total}
    parts = await db.voice_upload_chunks.find({"user_id": user_id, "upload_id": key}).sort("index", 1).to_list(chunk.total)
    await db.voice_upload_chunks.delete_many({"user_id": user_id, "upload_id": key})
    try:
        data = base64.b64decode("".join(p["data"] for p in parts))
    except Exception:
        raise HTTPException(status_code=400, detail="That photo came through damaged. Please try again.")
    capture = chunk.capture if chunk.capture in ("camera", "library", "document") else "library"
    try:
        doc = await cf.save_file(db, user_id=user_id, contact_id="", name=chunk.name or "Scan", content_type=chunk.content_type, data=data,
                                 hint="business_card", source="scan", capture=capture)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Scan] save failed: {e}")
        raise HTTPException(status_code=500, detail="Could not store that photo")
    v = vi.view(doc, user_id)
    return {"success": True, "received": chunk.total, "total": chunk.total, "scan": v, "matches": await vi.matches(db, me, v["fields"]) if v["is_card"] else []}


@router.get("/{user_id}/{scan_id}")
async def get_scan(user_id: str, scan_id: str, request: Request):
    me = _me(request, user_id)
    db = get_db()
    v = vi.view(await _scan(db, user_id, scan_id), user_id)
    return {"scan": v, "matches": await vi.matches(db, me, v["fields"]) if v["is_card"] and not v["contact_id"] else []}


@router.post("/{user_id}/{scan_id}/save")
async def save_scan(user_id: str, scan_id: str, body: SaveBody, request: Request):
    """Save to a new or existing contact the rep can see. Writes only `fields` (ticked), using the rep's edited `values`."""
    _me(request, user_id)
    db = get_db()
    doc = await _scan(db, user_id, scan_id)
    if doc.get("contact_id") and doc["contact_id"] != body.contact_id:
        raise HTTPException(status_code=409, detail="This scan is already saved to another contact")
    if doc.get("contact_id"):   # a retry / double tap: already saved here, nothing is logged twice
        return {"ok": True, "applied": {}, "labels": {}, "contact_id": doc["contact_id"], "file_id": str(doc["_id"]), "already_saved": True}
    if not ObjectId.is_valid(body.contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    contact = await db.contacts.find_one({"_id": ObjectId(body.contact_id), **(await get_data_filter(user_id))})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True, **await vi.save_to_contact(db, user_id, doc, contact, body.fields, body.values or {})}


@router.delete("/{user_id}/{scan_id}")
async def discard_scan(user_id: str, scan_id: str, request: Request):
    _me(request, user_id)
    db = get_db()
    doc = await _scan(db, user_id, scan_id)
    if doc.get("contact_id"):
        raise HTTPException(status_code=409, detail="Already saved to a contact; delete it from their Files")
    await cf.destroy_file(db, doc, "scan_discarded")
    return {"ok": True}
