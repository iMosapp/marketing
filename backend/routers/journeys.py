"""Journey campaigns API (same admin gate as Mystery Shops / Lead Shops)."""
import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.mystery_shops import require_admin, _client
from services import lead_shops as ls
from services.journey import campaigns as jc
from services.journey import identities as ids

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/journeys", tags=["Journey Campaigns"])


class CreateBody(BaseModel):
    client_id: str
    name: Optional[str] = ""
    department: Optional[str] = "sales"
    offering: Optional[str] = ""
    script_id: Optional[str] = None
    notes: Optional[str] = ""
    method: Optional[str] = "manual"
    source_name: Optional[str] = "Website"
    window_hours: Optional[int] = 72
    modes: Optional[dict] = None
    live_voice_enabled: Optional[bool] = False
    submission_limit: Optional[int] = ids.MAX_IDENTITIES
    count: Optional[int] = 3


class PatchBody(BaseModel):
    name: Optional[str] = None
    modes: Optional[dict] = None
    live_voice_enabled: Optional[bool] = None
    window_hours: Optional[int] = None
    method: Optional[str] = None
    source_name: Optional[str] = None
    offering: Optional[str] = None
    notes: Optional[str] = None
    submission_limit: Optional[int] = None


class GenerateBody(BaseModel):
    count: Optional[int] = 1


class IdentityBody(BaseModel):
    first: Optional[str] = None
    last: Optional[str] = None
    interest: Optional[str] = None
    goals: Optional[str] = None
    timeline: Optional[str] = None
    personality: Optional[str] = None
    channel_prefs: Optional[list] = None
    questions: Optional[list] = None
    objections: Optional[list] = None
    ai_instructions: Optional[str] = None


class ArmBody(BaseModel):
    confirm: bool = False
    website_url: Optional[str] = ""
    note: Optional[str] = ""


class StopBody(BaseModel):
    reason: Optional[str] = ""


def _oid(v: str) -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=400, detail="Bad id")
    return ObjectId(str(v))


async def _camp(db, jid: str) -> dict:
    c = await db[jc.COLL].find_one({"_id": _oid(jid)})
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return dict(c)


async def _identity(db, camp: dict, sid: str) -> dict:
    s = await db[ls.COLL].find_one({"_id": _oid(sid), "campaign_id": str(camp["_id"])})
    if not s:
        raise HTTPException(status_code=404, detail="Identity not found in this campaign")
    return dict(s)


def _bad(e: Exception):
    raise HTTPException(status_code=400, detail=str(e)[:300])


@router.get("/options")
async def options(request: Request):
    await require_admin(request)
    return {"windows": [{"hours": h, "label": l} for h, l in jc.WINDOWS.items()], "modes": list(jc.MODES), "voice_modes": list(jc.VOICE_MODES), "default_modes": jc.DEFAULT_MODES,
            "max_identities": ids.MAX_IDENTITIES, "timelines": ids.TIMELINES, "personalities": ids.PERSONALITIES, "email_ready": bool(ls.inbound_domain()), "pool": await ls.pool_state(get_db())}


@router.get("")
async def list_campaigns(request: Request, client_id: str, limit: int = 50):
    await require_admin(request)
    db = get_db()
    await _client(db, client_id)
    rows = await db[jc.COLL].find({"client_id": client_id}).sort("created_at", -1).limit(max(1, min(limit, 200))).to_list(200)
    return {"campaigns": [await jc.serialize(db, c) for c in rows]}


@router.post("")
async def create_campaign(body: CreateBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    c = await _client(db, body.client_id)
    try:
        camp = await jc.create(db, c, me, body.model_dump())
    except ValueError as e:
        _bad(e)
    return await jc.serialize(db, camp, with_identities=True)


@router.get("/{jid}")
async def get_campaign(jid: str, request: Request):
    await require_admin(request)
    db = get_db()
    return await jc.serialize(db, await _camp(db, jid), with_identities=True)


@router.patch("/{jid}")
async def patch_campaign(jid: str, body: PatchBody, request: Request):
    await require_admin(request)
    db = get_db()
    try:
        camp = await jc.update(db, await _camp(db, jid), body.model_dump(exclude_none=True))
    except ValueError as e:
        _bad(e)
    return await jc.serialize(db, camp, with_identities=True)


@router.delete("/{jid}")
async def delete_campaign(jid: str, request: Request):
    await require_admin(request)
    db = get_db()
    try:
        await jc.remove(db, await _camp(db, jid))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"deleted": True}


@router.post("/{jid}/identities/generate")
async def generate_identities(jid: str, body: GenerateBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    camp = await _camp(db, jid)
    if camp.get("status") != "draft":
        raise HTTPException(status_code=409, detail="Identities are added while the campaign is a draft")
    try:
        await ids.generate(db, camp, await _client(db, camp["client_id"]), me, body.count or 1)
    except ValueError as e:
        _bad(e)
    return await jc.serialize(db, camp, with_identities=True)


@router.patch("/{jid}/identities/{sid}")
async def patch_identity(jid: str, sid: str, body: IdentityBody, request: Request):
    await require_admin(request)
    db = get_db()
    camp = await _camp(db, jid)
    try:
        shop = await ids.update(db, await _identity(db, camp, sid), body.model_dump(exclude_none=True))
    except ValueError as e:
        _bad(e)
    return await ls.serialize(db, shop)


@router.delete("/{jid}/identities/{sid}")
async def delete_identity(jid: str, sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    camp = await _camp(db, jid)
    try:
        await ids.remove(db, await _identity(db, camp, sid))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return await jc.serialize(db, camp, with_identities=True)


@router.post("/{jid}/arm")
async def arm_campaign(jid: str, body: ArmBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    camp = await _camp(db, jid)
    try:
        camp = await jc.arm(db, camp, await _client(db, camp["client_id"]), me, body.model_dump())
    except ValueError as e:
        _bad(e)
    return await jc.serialize(db, camp, with_identities=True)


@router.post("/{jid}/stop")
async def stop_campaign(jid: str, body: StopBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    try:
        camp = await jc.stop(db, await _camp(db, jid), me, body.reason or "")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return await jc.serialize(db, camp, with_identities=True)


@router.post("/{jid}/close")
async def close_campaign(jid: str, request: Request):
    await require_admin(request)
    db = get_db()
    try:
        camp = await jc.close(db, await _camp(db, jid))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return await jc.serialize(db, camp, with_identities=True)
