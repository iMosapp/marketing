"""Lead Shops API (super admin / admin, same gate as Mystery Shops)."""
import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.mystery_shops import require_admin, _client
from services import lead_shops as ls

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lead-shops", tags=["Lead Shops"])


class SetupBody(BaseModel):
    lead_email: Optional[str] = None
    lead_website: Optional[str] = None
    lead_process: Optional[dict] = None


class CreateBody(BaseModel):
    client_id: str
    department: Optional[str] = "sales"
    method: Optional[str] = "adf"
    window_hours: Optional[int] = 72
    offering: Optional[str] = ""
    source_name: Optional[str] = ""
    script_id: Optional[str] = None
    notes: Optional[str] = ""


class BuyBody(BaseModel):
    area_code: Optional[str] = None


def _oid(v: str) -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=400, detail="Bad id")
    return ObjectId(str(v))


async def _shop(db, sid: str) -> dict:
    s = await db[ls.COLL].find_one({"_id": _oid(sid)})
    if not s:
        raise HTTPException(status_code=404, detail="Lead shop not found")
    return dict(s)


@router.get("/setup/{cid}")
async def get_setup(cid: str, request: Request):
    await require_admin(request)
    c = await _client(get_db(), cid)
    return {"lead_email": c.get("lead_email") or "", "lead_website": c.get("lead_website") or "", "lead_process": ls.clean_process(c.get("lead_process")), "defaults": ls.DEFAULT_PROCESS,
            "windows": [{"hours": h, "label": l} for h, l in ls.WINDOWS.items()], "email_ready": bool(ls.inbound_domain()), "pool": await ls.pool_state(get_db())}


@router.put("/setup/{cid}")
async def put_setup(cid: str, body: SetupBody, request: Request):
    await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    upd = {}
    if body.lead_email is not None:
        v = body.lead_email.strip().lower()
        if v and ("@" not in v or "." not in v.split("@")[-1]):
            raise HTTPException(status_code=400, detail="That is not an email address")
        upd["lead_email"] = v
    if body.lead_website is not None:
        upd["lead_website"] = body.lead_website.strip()[:200]
    if body.lead_process is not None:
        upd["lead_process"] = ls.clean_process(body.lead_process)
    if upd:
        await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {**upd, "updated_at": ls._now()}})
    return await get_setup(cid, request)


@router.get("")
async def list_shops(request: Request, client_id: str, limit: int = 50):
    await require_admin(request)
    db = get_db()
    await _client(db, client_id)
    rows = await db[ls.COLL].find({"client_id": client_id}).sort("created_at", -1).limit(max(1, min(limit, 200))).to_list(200)
    return {"shops": [await ls.serialize(db, s) for s in rows]}


@router.post("")
async def create_shop(body: CreateBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    c = await _client(db, body.client_id)
    try:
        shop = await ls.create(db, c, me, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await ls.serialize(db, shop, with_sessions=True)


@router.get("/numbers")
async def numbers(request: Request):
    await require_admin(request)
    return await ls.pool_state(get_db())


@router.post("/numbers/buy")
async def buy(body: BuyBody, request: Request):
    me = await require_admin(request)
    try:
        await ls.buy_number(get_db(), me, body.area_code)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Twilio would not sell a number: {str(e)[:160]}")
    return await ls.pool_state(get_db())


@router.get("/{sid}")
async def get_shop(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await _shop(db, sid)
    return {**(await ls.serialize(db, s, with_sessions=True)), "identity_card": ls.identity_card(s) if s.get("method") == "manual" else None, "adf_preview": ls.adf_xml(s, await _client(db, s["client_id"])) if s.get("method") == "adf" else None}


@router.post("/{sid}/delivered")
async def delivered(sid: str, request: Request):
    """Manual method: the admin submitted the store's web form with the identity card, the clock starts now."""
    await require_admin(request)
    db = get_db()
    s = await _shop(db, sid)
    if s.get("status") != "pending_delivery":
        raise HTTPException(status_code=409, detail="This shop is already running")
    await ls.mark_delivered(db, s)
    return await ls.serialize(db, await _shop(db, sid), with_sessions=True)


@router.post("/{sid}/close")
async def close_shop(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await _shop(db, sid)
    if s.get("status") not in ("live", "pending_delivery"):
        raise HTTPException(status_code=409, detail="This shop is not running")
    await ls.close(db, s, "closed_by_admin")
    return await ls.serialize(db, await _shop(db, sid), with_sessions=True)


@router.post("/{sid}/rescore")
async def rescore(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await _shop(db, sid)
    if s.get("status") not in ("completed", "closing"):
        raise HTTPException(status_code=409, detail="Close the shop first")
    score = await ls.compute_score(db, s)
    await db[ls.COLL].update_one({"_id": s["_id"]}, {"$set": {"score": score, "status": "completed", "updated_at": ls._now()}})
    return await ls.serialize(db, await _shop(db, sid), with_sessions=True)


@router.delete("/{sid}")
async def delete_shop(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await _shop(db, sid)
    if s.get("status") in ("live", "closing"):
        raise HTTPException(status_code=409, detail="Close the shop before deleting it")
    await ls.release_number(db, s)
    await db[ls.COLL].delete_one({"_id": s["_id"]})
    return {"deleted": True}
