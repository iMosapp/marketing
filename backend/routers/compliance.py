"""Admin API for per-store Twilio texting compliance (A2P 10DLC + CNAM) and the Trust Hub status callback."""
import logging
import os
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import twilio_compliance as tc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/compliance", tags=["Compliance"], dependencies=[Depends(require_user)])
webhook_router = APIRouter(prefix="/webhooks/twilio", tags=["Compliance"])


async def _admin(request: Request, store: Optional[dict] = None, org_ok: bool = False) -> dict:
    """Super admins always; org admins for their own stores (or store-less reads when org_ok)."""
    me = await _resolve(request)
    role = (me or {}).get("role")
    if role == "super_admin":
        return me
    if role == "org_admin" and me.get("organization_id"):
        if org_ok and store is None:
            return me
        if store and str(store.get("organization_id") or "") == str(me.get("organization_id") or ""):
            return me
    raise HTTPException(status_code=403, detail="Admin only")


async def _store(store_id: str) -> dict:
    s = await get_db().stores.find_one({"_id": ObjectId(store_id)}) if ObjectId.is_valid(store_id) else None
    if not s:
        raise HTTPException(status_code=404, detail="Store not found")
    return s


class SettingsIn(BaseModel):
    mode: Optional[str] = None
    notify_email: Optional[str] = None


class RecordIn(BaseModel):
    business: Optional[dict] = None
    rep: Optional[dict] = None
    campaign: Optional[dict] = None
    cnam: Optional[dict] = None


@router.get("")
async def overview(request: Request):
    """Every store with its compliance stage, plus the mode switch."""
    me = await _admin(request, org_ok=True)
    db = get_db()
    q: dict = {} if me.get("role") == "super_admin" else {"organization_id": str(me.get("organization_id") or "")}
    q["country"] = {"$in": ["US", "USA", None, ""]}
    stores = [tc.summary(s) async for s in db.stores.find(q, {"name": 1, "compliance": 1, "country": 1}).sort("name", 1)]
    return {"settings": await tc.get_settings(db), "stores": stores, "stages": list(tc.STAGES), "stage_labels": tc.STAGE_LABEL}


@router.put("/settings")
async def put_settings(body: SettingsIn, request: Request):
    me = await _admin(request)
    if body.mode and body.mode not in tc.MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {tc.MODES}")
    return await tc.set_settings(get_db(), body.model_dump(exclude_none=True), me)


@router.get("/options")
async def options(request: Request):
    await _admin(request, org_ok=True)
    return {"business_types": list(tc.BUSINESS_TYPES), "job_positions": list(tc.JOB_POSITIONS), "use_cases": tc.USE_CASES, "modes": list(tc.MODES)}


@router.get("/{store_id}")
async def get_record(store_id: str, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    db = get_db()
    rec = store.get("compliance") or tc.defaults(store)
    rec["numbers"] = await tc.store_numbers(db, store_id)
    return {"store": {"id": store_id, "name": store.get("name"), "country": store.get("country")}, "record": tc.public(rec), "missing": tc.missing_fields(rec), "summary": tc.summary({**store, "compliance": rec}), "settings": await tc.get_settings(db)}


@router.put("/{store_id}")
async def put_record(store_id: str, body: RecordIn, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    rec = tc.merge_patch(store.get("compliance") or {}, body.model_dump(exclude_none=True), store)
    if rec.get("stage") not in (None, "draft") and rec.get("status") not in ("rejected", "error"):
        # mid-review: Twilio will not take edits; keep them for the resubmit
        rec["pending_edit"] = True
    await get_db().stores.update_one({"_id": store["_id"]}, {"$set": {"compliance": {**rec, "updated_at": tc._now()}}})
    return {"record": tc.public(rec), "missing": tc.missing_fields(rec)}


@router.post("/{store_id}/submit")
async def submit(store_id: str, request: Request):
    store = await _store(store_id)
    me = await _admin(request, store)
    rec = store.get("compliance") or {}
    try:
        if rec.get("stage") not in (None, "draft"):
            out = await tc.resubmit(get_db(), store, me)
        else:
            out = await tc.start(get_db(), store, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"record": tc.public(out), "summary": tc.summary({**store, "compliance": out})}


@router.post("/{store_id}/check")
async def check_now(store_id: str, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    out = await tc.advance(get_db(), store_id)
    return {"record": tc.public(out), "summary": tc.summary({**store, "compliance": out})}


@router.post("/{store_id}/reset")
async def reset(store_id: str, request: Request):
    """Back to draft (keeps the form data, drops SIDs). Super admin only; Twilio resources are left as they are."""
    store = await _store(store_id)
    me = await _admin(request)
    rec = store.get("compliance") or tc.defaults(store)
    rec.update({"stage": "draft", "status": "not_started", "error": "", "sids": {}, "statuses": {}, "history": tc._hist(rec, "draft", "reset", f"by {me.get('email')}")})
    await get_db().stores.update_one({"_id": store["_id"]}, {"$set": {"compliance": rec}})
    return {"record": tc.public(rec)}


@webhook_router.post("/trusthub-status")
async def trusthub_status(request: Request):
    form = dict(await request.form())
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if token:
        try:
            from twilio.request_validator import RequestValidator
            sig = request.headers.get("X-Twilio-Signature", "")
            url = str(request.url).replace("http://", "https://", 1) if request.headers.get("x-forwarded-proto") == "https" else str(request.url)
            if not RequestValidator(token).validate(url, form, sig):
                logger.warning("[Compliance] trusthub-status: bad Twilio signature")
                return PlainTextResponse("forbidden", status_code=403)
        except ImportError:
            pass
    sid = await tc.on_status_callback(get_db(), form)
    logger.info(f"[Compliance] trusthub-status {form.get('BundleSid')} -> {form.get('Status')} store={sid}")
    return PlainTextResponse("ok")
