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
from services.appraisals import inspection
from services.appraisals import market
from services.appraisals import market_providers as mp
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


class FindingBody(BaseModel):
    category: Optional[str] = None
    subtype: Optional[str] = None
    location: Optional[str] = None
    location_label: Optional[str] = None
    severity: Optional[str] = None
    explanation: Optional[str] = None
    frame_ids: Optional[list] = None


class DecisionBody(BaseModel):
    decision: str


class OverrideBody(BaseModel):
    overall: Optional[str] = None
    reason: str = ""


class MarketRefreshBody(BaseModel):
    zip: Optional[str] = None
    radius: Optional[int] = None
    force: bool = False


class BookValueBody(BaseModel):
    source: Optional[str] = None
    source_label: Optional[str] = None
    value_type: Optional[str] = None
    value: Optional[int] = None
    note: Optional[str] = None


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
    return {"modes": core.MODES, "sources": core.SOURCES, "roles": core.ROLES, "identity": identity_options(), "steps": core.STEPS,
            "market_provider": {"name": mp.active().name, "label": mp.active().label, "live": mp.active().live, "badge": mp.active().badge}}


@router.get("/providers")
async def providers(request: Request):
    """Which market data provider is live vs mock, plus this month's usage. Managers and admins only; keys are never returned."""
    me = _me(request)
    if me.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Managers and admins only")
    db = get_db()
    return {"market": mp.provider_options(), "usage": await market.usage(db, mp.active()), "identity": identity_options(),
            "monthly_cap": market.MONTHLY_CAP_DEFAULT, "cache_hours": market.CACHE_HOURS}


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
    out["inspection"] = await inspection.summary(db, a)
    out["market"] = await market.summary(db, a)
    out["book_values"] = market.public_book_values(a)
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


@router.delete("/{appraisal_id}/media/{media_id}")
async def delete_media(appraisal_id: str, media_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        await core.delete_media(db, a, me, media_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "media": await core.list_media(db, a)}


# ---------- AI Vehicle Inspection ----------
@router.get("/{appraisal_id}/inspection")
async def get_inspection(appraisal_id: str, request: Request):
    """Status, frames, findings, coverage and the condition report. Same shape while Jessi is still working (poll on status)."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    out = await inspection.read(db, a)
    out["media"] = await core.list_media(db, a)
    areas = {}
    for f in out["frames"]:
        for ar in f.get("areas") or []:
            areas.setdefault(f["media_id"], [])
            if ar not in areas[f["media_id"]]:
                areas[f["media_id"]].append(ar)
    for m in out["media"]:
        m["areas"] = areas.get(m["id"], [])
    out["appraisal_status"] = a.get("status")
    return out


@router.post("/{appraisal_id}/inspection/run")
async def run_inspection(appraisal_id: str, request: Request):
    """Start (or retry) the pipeline over everything on the appraisal. Frames already extracted are reused; findings are matched, not duplicated."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        ins = await inspection.start_run(db, a, me)
    except ValueError as e:
        raise HTTPException(status_code=409 if "already" in str(e) else 400, detail=str(e))
    return {"status": ins.get("status"), "stage": ins.get("stage"), "run_count": ins.get("run_count")}


@router.post("/{appraisal_id}/inspection/findings")
async def add_finding(appraisal_id: str, body: FindingBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    ins = await inspection.get_or_create(db, a)
    try:
        d = await inspection.add_finding(db, ins, a, me, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    frames = {str(f["_id"]): f for f in await inspection.frames_for(db, ins)}
    return {"finding": inspection.public_finding(d, frames)}


@router.patch("/{appraisal_id}/inspection/findings/{finding_id}")
async def edit_finding(appraisal_id: str, finding_id: str, body: FindingBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    ins = await inspection.get_or_create(db, a)
    try:
        d = await inspection.edit_finding(db, ins, a, me, finding_id, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    frames = {str(f["_id"]): f for f in await inspection.frames_for(db, ins)}
    return {"finding": inspection.public_finding(d, frames)}


@router.post("/{appraisal_id}/inspection/findings/{finding_id}/decision")
async def decide_finding(appraisal_id: str, finding_id: str, body: DecisionBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    ins = await inspection.get_or_create(db, a)
    try:
        d = await inspection.decide(db, ins, a, me, finding_id, body.decision)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    frames = {str(f["_id"]): f for f in await inspection.frames_for(db, ins)}
    return {"finding": inspection.public_finding(d, frames)}


@router.post("/{appraisal_id}/inspection/override")
async def override_condition(appraisal_id: str, body: OverrideBody, request: Request):
    """Manager/rep sets the final overall condition (overall=null clears it). Reason and author are kept."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    ins = await inspection.get_or_create(db, a)
    try:
        await inspection.override(db, ins, a, me, body.overall, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await inspection.read(db, a)


# ---------- Market analysis (MVP3) ----------
def _market_error(e: Exception) -> HTTPException:
    if isinstance(e, mp.MarketRateLimited):
        return HTTPException(status_code=429, detail=str(e), headers={"Retry-After": str(int(e.retry_after) + 1)})
    if isinstance(e, mp.MarketQuotaExceeded):
        return HTTPException(status_code=429, detail=str(e), headers={"Retry-After": str(e.retry_after or 3600), "X-Quota-Monthly": "1" if e.monthly else "0"})
    if isinstance(e, mp.MarketUnavailable):
        return HTTPException(status_code=503, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


@router.get("/{appraisal_id}/market")
async def get_market(appraisal_id: str, request: Request):
    """Latest snapshot + comparables + book values + which provider is answering (live vs DEVELOPMENT DATA). Scoped through the appraisal."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return await market.read(db, a, me)


@router.post("/{appraisal_id}/market/refresh")
async def refresh_market(appraisal_id: str, body: MarketRefreshBody, request: Request):
    """Fetch market data (reused for 24h unless force). Every fetch is a new snapshot; nothing is overwritten. 429 = rate limit / quota, 503 = provider down."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        res = await market.refresh(db, a, me, zip_code=body.zip, radius=body.radius, force=body.force)
    except (ValueError, mp.MarketUnavailable, mp.MarketRateLimited) as e:
        raise _market_error(e)
    out = await market.read(db, await _appr(db, me, appraisal_id), me)
    out["cached"] = res["cached"]
    return out


@router.post("/{appraisal_id}/book-values")
async def add_book_value(appraisal_id: str, body: BookValueBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await market.add_book_value(db, a, me, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"book_values": market.public_book_values(doc), "appraisal": core.public_appraisal(doc)}


@router.patch("/{appraisal_id}/book-values/{book_id}")
async def edit_book_value(appraisal_id: str, book_id: str, body: BookValueBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await market.edit_book_value(db, a, me, book_id, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    return {"book_values": market.public_book_values(doc), "appraisal": core.public_appraisal(doc)}


@router.delete("/{appraisal_id}/book-values/{book_id}")
async def remove_book_value(appraisal_id: str, book_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await market.remove_book_value(db, a, me, book_id)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    return {"book_values": market.public_book_values(doc), "appraisal": core.public_appraisal(doc)}
