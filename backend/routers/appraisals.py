"""Trade Appraisal (MVP1): drafts, customer, capture mode, vehicle identity (VIN photo / typed / reappraise), mileage, customer expectation,
media with provenance, audit trail, vehicles on a contact. Scoped by the platform's accessible-user rule."""
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from permissions import is_feature_enabled, merge_permissions
from routers.database import get_db, get_data_filter
from routers.lead_sources import require_user
from services.appraisals import core
from services.appraisals.providers import ProviderUnavailable, identity_options, IDENTITY
from services.appraisals import readers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/appraisals", tags=["appraisals"], dependencies=[Depends(require_user)])


class CreateBody(BaseModel):
    contact_id: str
    mode: str = "vehicle_here"
    vehicle_id: Optional[str] = None


class ModeBody(BaseModel):
    mode: str


class VinBody(BaseModel):
    vin: str


class VehicleBody(BaseModel):
    vin: Optional[str] = None
    manual: Optional[dict] = None
    method: str = "manual_vin"


class MileageBody(BaseModel):
    confirmed: int
    detected: Optional[int] = None
    source: str = "manual"


class ExpectationBody(BaseModel):
    asked: bool
    value: Optional[int] = None


class MediaChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    name: str = ""
    content_type: str = "application/octet-stream"
    role: str
    source: str


def _me(request: Request) -> dict:
    return request.state.user


def can_appraise(me: dict) -> bool:
    """Managers and admins always; reps only when my_tools.trade_appraisal was switched on for them (manager-enabled per store)."""
    if me.get("role") in ("super_admin", "org_admin", "store_manager"):
        return True
    return is_feature_enabled(merge_permissions(me.get("feature_permissions"), me.get("role") or "user"), "my_tools", "trade_appraisal")


def _allowed(me: dict):
    if not can_appraise(me):
        raise HTTPException(status_code=403, detail="Trade Appraisal is not switched on for you yet. Ask your manager.")


async def _appr(db, me: dict, appraisal_id: str) -> dict:
    a = await core.get_appraisal(db, me, appraisal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Appraisal not found")
    return a


async def _contact(db, me: dict, contact_id: str) -> dict:
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    c = await db.contacts.find_one({"_id": ObjectId(contact_id), **(await get_data_filter(str(me["_id"])))})
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c


def _dt(s: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


@router.get("/meta")
async def meta(request: Request):
    me = _me(request)
    _allowed(me)
    return {"modes": core.MODES, "sources": core.SOURCES, "roles": core.ROLES, "identity": identity_options(), "steps": core.STEPS}


@router.get("")
async def list_appraisals(request: Request, group: Optional[str] = None, q: str = "", date_from: Optional[str] = None, date_to: Optional[str] = None):
    me = _me(request)
    _allowed(me)
    return await core.list_appraisals(get_db(), me, group, q, _dt(date_from), _dt(date_to))


@router.post("")
async def create(body: CreateBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    contact = await _contact(db, me, body.contact_id)
    try:
        doc = await core.create(db, me, contact, body.mode, body.vehicle_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"appraisal": core.public_appraisal(doc)}


@router.get("/vehicles/{contact_id}")
async def contact_vehicles(contact_id: str, request: Request):
    """Vehicles on a contact with their appraisal history (also used by the contact's Vehicles section and REAPPRAISE)."""
    me = _me(request)
    db = get_db()
    await _contact(db, me, contact_id)
    vehicles = await core.contact_vehicles(db, me, contact_id)
    for v in vehicles:
        v["appraisals"] = await core.vehicle_appraisals(db, me, v["id"])
    return {"vehicles": vehicles, "can_appraise": can_appraise(me)}


@router.post("/vin/decode")
async def decode_vin(body: VinBody, request: Request):
    """Validate + decode a typed VIN (no appraisal needed). Returns validation errors instead of 400 so the UI can coach."""
    _allowed(_me(request))
    try:
        res = await core.identify(get_db(), "vin", vin=body.vin)
    except ProviderUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return res


@router.get("/{appraisal_id}")
async def detail(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    out = core.public_appraisal(a)
    out["media"] = await core.list_media(db, a)
    out["activity"] = await core.activity(db, a)
    if a.get("vehicle_id"):
        veh = await core.get_vehicle(db, me, a["vehicle_id"])
        out["vehicle_record"] = core.public_vehicle(veh) if veh else None
        out["history"] = await core.vehicle_appraisals(db, me, a["vehicle_id"])
    return out


@router.patch("/{appraisal_id}")
async def patch(appraisal_id: str, data: dict, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return {"appraisal": core.public_appraisal(await core.patch(db, a, me, data or {}))}


@router.delete("/{appraisal_id}")
async def delete(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        await core.delete_draft(db, a, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@router.post("/{appraisal_id}/mode")
async def set_mode(appraisal_id: str, body: ModeBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        return {"appraisal": core.public_appraisal(await core.set_mode(db, a, me, body.mode))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appraisal_id}/vehicle")
async def set_vehicle(appraisal_id: str, body: VehicleBody, request: Request):
    """Confirmed VIN (scanned, uploaded or typed) and/or manual vehicle fields -> vehicles doc + snapshot on the appraisal."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await core.set_vehicle(db, a, me, vin=body.vin, manual=body.manual, method=body.method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    out = core.public_appraisal(doc)
    veh = await core.get_vehicle(db, me, doc["vehicle_id"])
    out["vehicle_record"] = core.public_vehicle(veh) if veh else None
    return {"appraisal": out}


@router.post("/{appraisal_id}/mileage")
async def set_mileage(appraisal_id: str, body: MileageBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        return {"appraisal": core.public_appraisal(await core.set_mileage(db, a, me, body.confirmed, body.detected, body.source))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appraisal_id}/expectation")
async def set_expectation(appraisal_id: str, body: ExpectationBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        return {"appraisal": core.public_appraisal(await core.set_expectation(db, a, me, body.asked, body.value))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appraisal_id}/media/chunk")
async def media_chunk(appraisal_id: str, chunk: MediaChunk, request: Request):
    """Base64 pieces (same protocol as contact files); on the last piece the media is stored with its provenance and, for VIN and odometer
    photos, read by Jessi. Returns {media} on the last piece."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    if chunk.total < 1 or chunk.total > 400 or not (0 <= chunk.index < chunk.total) or len(chunk.data) > 900_000:
        raise HTTPException(status_code=400, detail="Bad chunk")
    upload_id = re.sub(r"[^A-Za-z0-9_-]", "", chunk.upload_id)[:64]
    if not upload_id:
        raise HTTPException(status_code=400, detail="Bad upload id")
    if chunk.role not in core.ROLES or chunk.source not in core.SOURCES:
        raise HTTPException(status_code=400, detail="Bad media role or source")
    key = {"user_id": str(me["_id"]), "upload_id": f"appr_{upload_id}"}
    await db.voice_upload_chunks.update_one({**key, "index": chunk.index}, {"$set": {"data": chunk.data, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    have = await db.voice_upload_chunks.count_documents(key)
    if have < chunk.total:
        return {"success": True, "received": have, "total": chunk.total}
    parts = await db.voice_upload_chunks.find(key).sort("index", 1).to_list(chunk.total)
    await db.voice_upload_chunks.delete_many(key)
    try:
        data = base64.b64decode("".join(p["data"] for p in parts))
    except Exception:
        raise HTTPException(status_code=400, detail="That file came through damaged. Please try again.")
    try:
        doc = await core.save_media(db, a, me, role=chunk.role, source=chunk.source, data=data, content_type=chunk.content_type, name=chunk.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Appraisal] media save failed: {e}")
        raise HTTPException(status_code=500, detail="Could not store that file")
    return {"success": True, "received": chunk.total, "total": chunk.total, "media": core.public_media(doc)}


@router.get("/{appraisal_id}/media")
async def media(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return {"media": await core.list_media(db, a)}
