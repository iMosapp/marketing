"""Admin API for per-store Twilio texting compliance (A2P 10DLC + CNAM), the client onboarding form (public, tokenized),
pre-flight review, the numbers exit path (release / port-out) and the Trust Hub status callback."""
import copy
import logging
import os
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import compliance_onboarding as ob
from services import compliance_preflight as pf
from services import twilio_compliance as tc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/compliance", tags=["Compliance"], dependencies=[Depends(require_user)])
webhook_router = APIRouter(prefix="/webhooks/twilio", tags=["Compliance"])
public_router = APIRouter(prefix="/public", tags=["Compliance"])


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
    auto_invite: Optional[bool] = None
    digest: Optional[bool] = None
    digest_hour: Optional[int] = None
    reminder_days: Optional[list] = None
    portout_pin: Optional[str] = None
    portout_service_address: Optional[str] = None


class RecordIn(BaseModel):
    business: Optional[dict] = None
    rep: Optional[dict] = None
    campaign: Optional[dict] = None
    cnam: Optional[dict] = None


class SendIn(BaseModel):
    email: Optional[str] = ""
    phone: Optional[str] = ""
    channel: Optional[str] = "both"
    note: Optional[str] = ""


class ReviewIn(BaseModel):
    status: str
    notes: Optional[str] = ""


class NumberStatusIn(BaseModel):
    status: str
    note: Optional[str] = ""


class ClientSaveIn(BaseModel):
    business: Optional[dict] = None
    rep: Optional[dict] = None
    campaign: Optional[dict] = None
    cnam: Optional[dict] = None
    contact: Optional[dict] = None


def _full(store: dict, rec: dict) -> dict:
    return {"store": {"id": str(store["_id"]), "name": store.get("name"), "country": store.get("country")}, "record": tc.public(rec), "missing": tc.missing_fields(rec), "summary": tc.summary({**store, "compliance": rec})}


@router.get("")
async def overview(request: Request):
    """Every store with its compliance stage + onboarding status, plus the settings."""
    me = await _admin(request, org_ok=True)
    db = get_db()
    q: dict = {} if me.get("role") == "super_admin" else {"organization_id": str(me.get("organization_id") or "")}
    q["country"] = {"$in": ["US", "USA", None, ""]}
    stores = [tc.summary(s) async for s in db.stores.find(q, {"name": 1, "compliance": 1, "country": 1}).sort("name", 1)]
    return {"settings": await ob.settings(db), "stores": stores, "stages": list(tc.STAGES), "stage_labels": tc.STAGE_LABEL, "onboarding_labels": ob.ONBOARDING_STATUS_LABEL}


@router.put("/settings")
async def put_settings(body: SettingsIn, request: Request):
    me = await _admin(request)
    if body.mode and body.mode not in tc.MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {tc.MODES}")
    db = get_db()
    patch = body.model_dump(exclude_none=True)
    await tc.set_settings(db, {k: v for k, v in patch.items() if k in ("mode", "notify_email")}, me)
    return await ob.save_settings(db, patch, me)


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
    if not (rec.get("onboarding") or {}).get("token") or not (rec.get("portout") or {}).get("token"):
        ob.ensure_tokens(rec)
        await tc._save(db, store_id, rec)
    rec["numbers"] = await tc.store_numbers(db, store_id)
    out = _full(store, rec)
    out["settings"] = await ob.settings(db)
    out["onboarding"] = ob.public_onboarding(rec)
    out["form_url"] = ob.form_url(rec)
    out["numbers_view"] = await ob.numbers_view(db, {**store, "compliance": rec})
    out["events"] = (rec.get("events") or [])[-30:]
    return out


@router.put("/{store_id}")
async def put_record(store_id: str, body: RecordIn, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    before = store.get("compliance") or tc.defaults(store)
    rec = tc.merge_patch(copy.deepcopy(before), body.model_dump(exclude_none=True), store)
    changed = any((before.get(b) or {}) != (rec.get(b) or {}) for b in ("business", "rep", "campaign", "cnam"))
    if changed and rec.get("stage") not in (None, "draft") and rec.get("status") not in ("rejected", "error"):
        # mid-review: Twilio will not take edits; keep them for the resubmit
        rec["pending_edit"] = True
    if changed and rec.get("preflight"):
        rec["preflight"]["stale"] = True
    if changed and (rec.get("review") or {}).get("status") == "reviewed":
        rec["review"] = {**rec["review"], "status": "returned"}
    await get_db().stores.update_one({"_id": store["_id"]}, {"$set": {"compliance": {**rec, "updated_at": tc._now()}}})
    return {"record": tc.public(rec), "missing": tc.missing_fields(rec)}


# ── client onboarding form ────────────────────────────────────────────────────
@router.post("/{store_id}/send-form")
async def send_form(store_id: str, body: SendIn, request: Request):
    """Text + email the client their onboarding form (first send or a re-send)."""
    store = await _store(store_id)
    me = await _admin(request, store)
    try:
        return await ob.send_to_client(get_db(), store, "invite", body.email or "", body.phone or "", body.channel or "both", me, body.note or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{store_id}/remind")
async def remind(store_id: str, body: SendIn, request: Request):
    """Manual nudge: a reminder, or the 'still needed' list when the form came back with gaps."""
    store = await _store(store_id)
    me = await _admin(request, store)
    rec = store.get("compliance") or {}
    kind = "missing" if (rec.get("onboarding") or {}).get("returned_missing") else "reminder"
    try:
        return await ob.send_to_client(get_db(), store, kind, body.email or "", body.phone or "", body.channel or "both", me, body.note or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{store_id}/form-link")
async def form_link(store_id: str, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    rec = ob.ensure_tokens(store.get("compliance") or tc.defaults(store))
    await tc._save(get_db(), store_id, rec)
    return {"url": ob.form_url(rec), "portout_url": ob.portout_url(rec)}


# ── pre-flight + review ───────────────────────────────────────────────────────
@router.post("/{store_id}/preflight")
async def preflight(store_id: str, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    db = get_db()
    rec = store.get("compliance") or tc.defaults(store)
    numbers = await tc.store_numbers(db, store_id)
    result = await pf.run(rec, numbers, store)
    rec["preflight"] = result
    if result["blockers"] and (rec.get("review") or {}).get("status") == "reviewed":
        rec["review"] = {**rec["review"], "status": "returned"}
    rec["history"] = tc._hist(rec, rec.get("stage") or "draft", "preflight", f"{result['score']}/100, {result['blockers']} blockers, {result['warnings']} warnings")
    await tc._save(db, store_id, rec)
    if result["blockers"]:
        await ob.notify_team(db, store, rec, "preflight", f"{store.get('name')}: pre-flight {result['score']}/100, {result['blockers']} blocker{'s' if result['blockers'] != 1 else ''}",
                             "; ".join(f"{c['label']}: {c['detail']}" for c in result["checks"] if c["level"] == "block")[:600], email=False)
    return {"preflight": result, "record": tc.public(rec)}


@router.post("/{store_id}/review")
async def review(store_id: str, body: ReviewIn, request: Request):
    """Team sign-off before submit: reviewed | needs_client (sends the client the gaps) | reopen."""
    store = await _store(store_id)
    me = await _admin(request, store)
    if body.status not in ("reviewed", "needs_client", "reopen"):
        raise HTTPException(status_code=400, detail="status must be reviewed, needs_client or reopen")
    db = get_db()
    rec = ob.ensure_tokens(store.get("compliance") or tc.defaults(store))
    if body.status == "reviewed":
        if (rec.get("preflight") or {}).get("blockers") and me.get("role") != "super_admin":
            raise HTTPException(status_code=400, detail="Pre-flight still has blockers")
        rec["review"] = {"status": "reviewed", "reviewed_at": tc._now(), "reviewed_by": me.get("email"), "notes": (body.notes or "")[:500]}
    elif body.status == "reopen":
        rec["review"] = {"status": "returned" if (rec.get("onboarding") or {}).get("returned_at") else "awaiting_client", "notes": (body.notes or "")[:500]}
    else:
        rec["review"] = {"status": "needs_client", "notes": (body.notes or "")[:500], "at": tc._now(), "by": me.get("email")}
        rec["onboarding"]["returned_at"] = None
        rec["onboarding"]["flagged_at"] = None
        rec["onboarding"]["reminders_sent"] = 0
        rec["onboarding"]["first_sent_at"] = tc._now()
    rec["history"] = tc._hist(rec, rec.get("stage") or "draft", f"review_{body.status}", f"{me.get('email')} {body.notes or ''}".strip())
    await tc._save(db, store_id, rec)
    if body.status == "needs_client":
        try:
            await ob.send_to_client(db, {**store, "compliance": rec}, "missing" if tc.missing_fields(rec) else "reminder", channel="both", me=me, note=body.notes or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"record": tc.public(rec), "summary": tc.summary({**store, "compliance": rec})}


# ── Twilio submission ─────────────────────────────────────────────────────────
@router.post("/{store_id}/submit")
async def submit(store_id: str, request: Request, force: bool = False):
    """Gate: pre-flight run + no blockers (super admin may force). Then create / resubmit the Trust Hub profile."""
    store = await _store(store_id)
    me = await _admin(request, store)
    rec = store.get("compliance") or {}
    pre = rec.get("preflight") or {}
    fresh = rec.get("stage") in (None, "draft")
    if fresh and not (force and me.get("role") == "super_admin"):
        if not pre.get("at") or pre.get("stale"):
            raise HTTPException(status_code=400, detail="Run pre-flight first (the form changed since the last run)." if pre.get("at") else "Run pre-flight first.")
        if pre.get("blockers"):
            raise HTTPException(status_code=400, detail=f"Pre-flight has {pre['blockers']} blocker{'s' if pre['blockers'] != 1 else ''}. Fix them, or a super admin can force the submit.")
        if (rec.get("review") or {}).get("status") != "reviewed":
            raise HTTPException(status_code=400, detail="Mark the packet reviewed first.")
    try:
        if not fresh:
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


# ── numbers: release / port out ───────────────────────────────────────────────
@router.get("/{store_id}/numbers")
async def numbers(store_id: str, request: Request):
    store = await _store(store_id)
    await _admin(request, store)
    return await ob.numbers_view(get_db(), store)


@router.post("/{store_id}/numbers/{sid}/release")
async def release(store_id: str, sid: str, request: Request):
    store = await _store(store_id)
    me = await _admin(request, store)
    try:
        rec = await ob.release_number(get_db(), store, sid, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"numbers_view": await ob.numbers_view(get_db(), {**store, "compliance": rec})}


@router.post("/{store_id}/numbers/{sid}/status")
async def number_status(store_id: str, sid: str, body: NumberStatusIn, request: Request):
    store = await _store(store_id)
    me = await _admin(request, store)
    try:
        rec = await ob.set_number_status(get_db(), store, sid, body.status, me, body.note or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"numbers_view": await ob.numbers_view(get_db(), {**store, "compliance": rec})}


@router.post("/{store_id}/portout/send")
async def portout_send(store_id: str, body: SendIn, request: Request):
    store = await _store(store_id)
    me = await _admin(request, store)
    try:
        return await ob.send_portout(get_db(), store, me, body.email or "", body.phone or "", body.channel or "both")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── public: the client's form + the port-out packet ───────────────────────────
@public_router.get("/a2p-onboarding/{token}")
async def public_form(token: str):
    db = get_db()
    store = await ob.store_by_token(db, token)
    if not store:
        raise HTTPException(status_code=404, detail="This registration link is not valid")
    rec = await ob.client_opened(db, store)
    return ob.client_view(store, rec or tc.defaults(store))


@public_router.put("/a2p-onboarding/{token}")
async def public_save(token: str, body: ClientSaveIn):
    db = get_db()
    store = await ob.store_by_token(db, token)
    if not store:
        raise HTTPException(status_code=404, detail="This registration link is not valid")
    try:
        rec = await ob.client_save(db, store, body.model_dump(exclude_none=True), submit=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ob.client_view(store, rec)


@public_router.post("/a2p-onboarding/{token}/submit")
async def public_submit(token: str, body: ClientSaveIn):
    db = get_db()
    store = await ob.store_by_token(db, token)
    if not store:
        raise HTTPException(status_code=404, detail="This registration link is not valid")
    try:
        rec = await ob.client_save(db, store, body.model_dump(exclude_none=True), submit=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ob.client_view(store, rec)


@public_router.get("/port-out/{token}")
async def public_portout(token: str):
    db = get_db()
    store = await ob.store_by_token(db, token, "portout")
    if not store:
        raise HTTPException(status_code=404, detail="This link is not valid")
    view = await ob.numbers_view(db, store)
    return ob.portout_packet(store, store.get("compliance") or {}, await ob.settings(db), view["numbers"])


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
