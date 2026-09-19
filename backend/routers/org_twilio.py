"""Admin -> Organizations -> [Organization] -> Communications -> Twilio.
Super admins see everything (SIDs, history, provisioning); org admins get the simplified Communications view of their own
organization: numbers, assignments, compliance status, messaging status. Auth tokens and the parent account never leave the server."""
import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import phone_numbers as pn
from services import twilio_tenant as tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/organizations/{org_id}/twilio", tags=["Twilio tenant"], dependencies=[Depends(require_user)])


async def _ctx(request: Request, org_id: str, super_only: bool = False) -> tuple[dict, dict, bool]:
    me = await _resolve(request)
    role = (me or {}).get("role")
    org = await tenant.org_by_id(get_db(), org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if role == "super_admin":
        return me, org, True
    if not super_only and role == "org_admin" and str(me.get("organization_id") or "") == str(org["_id"]):
        return me, org, False
    raise HTTPException(status_code=403, detail="Super admin only" if super_only else "Admin of this organization only")


async def _number(org: dict, number_id: str) -> dict:
    num = await pn.get(get_db(), number_id)
    if not num or str(num.get("organization_id") or "") != str(org["_id"]):
        raise HTTPException(status_code=404, detail="Number not found on this organization")
    return num


class PurchaseIn(BaseModel):
    phone_number: str
    number_type: Optional[str] = "USER"
    location_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    friendly_name: Optional[str] = ""
    voice_enabled: Optional[bool] = True


class AssignIn(BaseModel):
    user_id: str


class ReasonIn(BaseModel):
    reason: Optional[str] = ""


class SubaccountIn(BaseModel):
    status: str


@router.get("")
async def get_view(request: Request, org_id: str):
    me, org, full = await _ctx(request, org_id)
    return await tenant.view(get_db(), org, full)


@router.post("/provision")
async def provision(request: Request, org_id: str):
    me, org, _ = await _ctx(request, org_id, super_only=True)
    db = get_db()
    await tenant.provision(db, org, me)
    return await tenant.view(db, await tenant.org_by_id(db, org_id), True)


@router.post("/sync")
async def sync(request: Request, org_id: str):
    me, org, full = await _ctx(request, org_id)
    db = get_db()
    await tenant.sync(db, org, me)
    return await tenant.view(db, await tenant.org_by_id(db, org_id), full)


@router.post("/subaccount")
async def subaccount_status(request: Request, org_id: str, body: SubaccountIn):
    me, org, _ = await _ctx(request, org_id, super_only=True)
    db = get_db()
    try:
        await tenant.set_subaccount_status(db, org, body.status, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await tenant.sync(db, await tenant.org_by_id(db, org_id), me)
    return await tenant.view(db, await tenant.org_by_id(db, org_id), True)


@router.get("/numbers/suggest")
async def suggest(request: Request, org_id: str, user_id: Optional[str] = None, store_id: Optional[str] = None):
    me, org, _ = await _ctx(request, org_id)
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id), "organization_id": str(org["_id"])}) if user_id and ObjectId.is_valid(user_id) else None
    store = await db.stores.find_one({"_id": ObjectId(store_id), "organization_id": str(org["_id"])}) if store_id and ObjectId.is_valid(store_id) else None
    return {"suggestions": await pn.suggest_area_codes(db, org, store, user)}


@router.get("/numbers/search")
async def search(request: Request, org_id: str, area_code: str = "", contains: str = "", sms: bool = True, mms: bool = True, voice: bool = True,
                 locality: str = "", region: str = "", limit: int = 10):
    me, org, _ = await _ctx(request, org_id)
    try:
        return await pn.search(get_db(), org, area_code=area_code, contains=contains, sms=sms, mms=mms, voice=voice, locality=locality, region=region, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Twilio search failed: {tenant._friendly(e)}")


@router.post("/numbers")
async def purchase(request: Request, org_id: str, body: PurchaseIn):
    me, org, _ = await _ctx(request, org_id)
    db = get_db()
    try:
        out = await pn.purchase(db, org=org, phone_number=body.phone_number, number_type=body.number_type or "USER", location_id=body.location_id,
                                assigned_user_id=body.assigned_user_id, actor=me, friendly_name=body.friendly_name or "", voice_enabled=body.voice_enabled is not False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await tenant.audit(db, action="number_purchase_failed", actor=me, org_id=org["_id"], target={"phone_number": body.phone_number}, ok=False, error=str(e))
        raise HTTPException(status_code=502, detail=f"Twilio could not sell that number: {tenant._friendly(e)}")
    await tenant.sync(db, await tenant.org_by_id(db, org_id), me)
    return out


@router.post("/numbers/{number_id}/assign")
async def assign(request: Request, org_id: str, number_id: str, body: AssignIn):
    me, org, _ = await _ctx(request, org_id)
    num = await _number(org, number_id)
    try:
        out = await pn.assign(get_db(), num, body.user_id, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return pn.public(out)


@router.post("/numbers/{number_id}/unassign")
async def unassign(request: Request, org_id: str, number_id: str, body: Optional[ReasonIn] = None):
    me, org, _ = await _ctx(request, org_id)
    num = await _number(org, number_id)
    try:
        out = await pn.unassign(get_db(), num, me, (body or ReasonIn()).reason or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return pn.public(out)


@router.post("/numbers/{number_id}/suspend")
async def suspend(request: Request, org_id: str, number_id: str, body: Optional[ReasonIn] = None):
    me, org, _ = await _ctx(request, org_id, super_only=True)
    num = await _number(org, number_id)
    try:
        out = await pn.suspend(get_db(), num, me, (body or ReasonIn()).reason or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return pn.public(out)


@router.post("/numbers/{number_id}/reactivate")
async def reactivate(request: Request, org_id: str, number_id: str):
    me, org, _ = await _ctx(request, org_id, super_only=True)
    num = await _number(org, number_id)
    try:
        out = await pn.reactivate(get_db(), num, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return pn.public(out)


@router.delete("/numbers/{number_id}")
async def release(request: Request, org_id: str, number_id: str, confirm: bool = False, reason: str = ""):
    me, org, _ = await _ctx(request, org_id, super_only=True)
    if not confirm:
        raise HTTPException(status_code=400, detail="Releasing a number is permanent. Call again with confirm=true.")
    num = await _number(org, number_id)
    db = get_db()
    try:
        out = await pn.release(db, num, me, reason)
    except Exception as e:
        await tenant.audit(db, action="number_release_failed", actor=me, org_id=org["_id"], target={"phone_number": num["phone_number"]}, ok=False, error=str(e))
        raise HTTPException(status_code=502, detail=f"Twilio did not release the number: {tenant._friendly(e)}")
    await tenant.sync(db, await tenant.org_by_id(db, org_id), me)
    return pn.public(out)


@router.get("/audit")
async def audit(request: Request, org_id: str, limit: int = 100):
    me, org, full = await _ctx(request, org_id)
    return {"entries": await tenant.audit_list(get_db(), org["_id"], limit=min(limit, 300), full=full)}


@router.get("/usage")
async def usage(request: Request, org_id: str, month: Optional[str] = None):
    me, org, _ = await _ctx(request, org_id)
    return await pn.usage_summary(get_db(), str(org["_id"]), month)
