"""Consent capture + opt-out visibility for contacts, the contact-driven opt-in page, and the controlled consent migration."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db
from services import consent as svc
from services import disclosure, suppression
from services.contact_scope import owned_contact

router = APIRouter(prefix="/consent", tags=["Consent"], dependencies=[Depends(require_user)])
public_router = APIRouter(prefix="/public/consent", tags=["Consent (public)"])
LINKS = "consent_links"
LINK_DAYS = 7
MANAGERS = ("super_admin", "org_admin", "store_manager")


class CaptureBody(BaseModel):
    scopes: list[str]
    method: str = "verbal_in_person"
    source: str = "app"
    evidence: Optional[dict] = None
    statement_version: str = svc.STATEMENT_VERSION


class RevokeBody(BaseModel):
    scopes: list[str]
    reason: str = ""


class LinkBody(BaseModel):
    scopes: list[str] = ["marketing"]


class PublicBody(BaseModel):
    scopes: list[str]
    agree: bool
    confirm_last4: str


async def _business(db, org_id: Optional[str], location_id: Optional[str]) -> str:
    if location_id and ObjectId.is_valid(location_id):
        st = await db.stores.find_one({"_id": ObjectId(location_id)}, {"name": 1})
        if st and st.get("name"):
            return st["name"]
    if org_id and ObjectId.is_valid(org_id):
        o = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
        return (o or {}).get("name") or ""
    return ""


async def _target(request: Request, contact_id: str) -> tuple[dict, dict, str, Optional[str], str]:
    db = get_db()
    me = request.state.user
    c = await owned_contact(db, str(me["_id"]), contact_id, {"phone": 1, "user_id": 1, "first_name": 1, "last_name": 1}, shared_thread=True)
    org_id, location_id = await svc.org_for_contact(db, c)
    org_id = org_id or (str(me.get("organization_id")) if me.get("organization_id") else None) or svc.solo_scope(str(c.get("user_id") or me["_id"]))
    phone = svc.e164(c.get("phone") or "")
    if not phone:
        raise HTTPException(status_code=400, detail="This contact has no phone number yet.")
    return me, c, org_id, location_id, phone


@router.get("/statements")
async def statements(request: Request, contact_id: Optional[str] = None):
    db = get_db()
    me = request.state.user
    org_id, loc = (str(me.get("organization_id")) if me.get("organization_id") else None), (str(me.get("store_id")) if me.get("store_id") else None)
    if contact_id:
        _, _, org_id, loc, _ = await _target(request, contact_id)
    return svc.statements(await _business(db, org_id, loc))


@router.get("/contact/{contact_id}")
async def contact_consent(contact_id: str, request: Request):
    db = get_db()
    _, c, org_id, loc, phone = await _target(request, contact_id)
    last = await svc.last_inbound(db, org_id, phone)
    hit = await suppression.active(db, phone, org_id)
    return {"contact_id": contact_id, "phone_last4": phone[-4:], "organization_id": org_id, "location_id": loc,
            "state": await svc.state(db, org_id, phone), "opted_out": bool(hit), "opt_out": hit and {"source": hit.get("source"), "since": hit["since"].isoformat() if isinstance(hit.get("since"), datetime) else None},
            "last_customer_text_at": last.isoformat() if last else None, "reply_window_days": (await svc.policy(db))["reply_window_days"],
            "history": await svc.history(db, org_id, phone, 50), "opt_out_history": await suppression.history(db, phone, org_id),
            "disclosures": await disclosure.status_for(db, org_id, phone), "statements": svc.statements(await _business(db, org_id, loc))}


@router.post("/contact/{contact_id}")
async def capture(contact_id: str, body: CaptureBody, request: Request):
    db = get_db()
    me, _, org_id, loc, phone = await _target(request, contact_id)
    try:
        recs = await svc.record(db, org_id=org_id, phone=phone, scopes=body.scopes, method=body.method, source=(body.source or "app")[:40],
                                location_id=loc, contact_id=contact_id, captured_by=me, evidence=body.evidence, business=await _business(db, org_id, loc),
                                ip=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip(), user_agent=request.headers.get("user-agent") or "",
                                statement_version=body.statement_version)
    except svc.ConsentError as e:
        raise HTTPException(status_code=409 if e.code == "opted_out" else 400, detail={"code": e.code, "message": str(e)})
    return {"recorded": recs, "state": await svc.state(db, org_id, phone)}


class PhoneCaptureBody(CaptureBody):
    phone: str


@router.post("/phone")
async def capture_by_phone(body: PhoneCaptureBody, request: Request):
    """Consent for a number with no saved contact yet (the composer's inline capture), in the caller's own organization."""
    db = get_db()
    me = request.state.user
    org_id, loc = (str(me.get("organization_id")) if me.get("organization_id") else None), (str(me.get("store_id")) if me.get("store_id") else None)
    org_id = org_id or svc.solo_scope(str(me["_id"]))
    try:
        recs = await svc.record(db, org_id=org_id, phone=body.phone, scopes=body.scopes, method=body.method, source=(body.source or "app")[:40],
                                location_id=loc, captured_by=me, evidence=body.evidence, business=await _business(db, org_id, loc),
                                ip=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip(), user_agent=request.headers.get("user-agent") or "",
                                statement_version=body.statement_version)
    except svc.ConsentError as e:
        raise HTTPException(status_code=409 if e.code == "opted_out" else 400, detail={"code": e.code, "message": str(e)})
    return {"recorded": recs, "state": await svc.state(db, org_id, body.phone)}


@router.post("/contact/{contact_id}/revoke")
async def revoke(contact_id: str, body: RevokeBody, request: Request):
    db = get_db()
    me, _, org_id, _, phone = await _target(request, contact_id)
    n = await svc.revoke(db, org_id=org_id, phone=phone, scopes=body.scopes, source="app", by=me, reason=body.reason, contact_id=contact_id)
    return {"revoked": n, "state": await svc.state(db, org_id, phone)}


@router.post("/contact/{contact_id}/opt-in-link")
async def opt_in_link(contact_id: str, body: LinkBody, request: Request):
    """A single-use page the contact completes on their own phone (digital opt-in, the only way a team member can collect marketing consent in person)."""
    db = get_db()
    me, _, org_id, loc, phone = await _target(request, contact_id)
    scopes = [s for s in body.scopes if s in svc.SCOPES] or ["marketing"]
    if await suppression.active(db, phone, org_id):
        raise HTTPException(status_code=409, detail={"code": "opted_out", "message": "This contact texted STOP. Only they can turn texts back on, by texting START to your number."})
    token = secrets.token_urlsafe(18)
    now = datetime.now(timezone.utc)
    await db[LINKS].insert_one({"_id": token, "org_id": org_id, "location_id": loc, "contact_id": contact_id, "phone": phone, "scopes": scopes,
                                "created_by": {"user_id": str(me["_id"]), "name": me.get("name") or ""}, "created_at": now, "expires_at": now + timedelta(days=LINK_DAYS)})
    from routers.billing import public_base
    return {"token": token, "url": f"{public_base(request)}/consent/{token}", "expires_at": (now + timedelta(days=LINK_DAYS)).isoformat(), "scopes": scopes}


async def _link(token: str) -> dict:
    doc = await get_db()[LINKS].find_one({"_id": token})
    if not doc:
        raise HTTPException(status_code=404, detail="This link is not valid.")
    exp = doc["expires_at"].replace(tzinfo=timezone.utc) if doc["expires_at"].tzinfo is None else doc["expires_at"]
    if exp <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This link has expired. Ask for a new one.")
    return doc


@public_router.get("/{token}")
async def public_view(token: str):
    db = get_db()
    doc = await _link(token)
    business = await _business(db, doc["org_id"], doc.get("location_id"))
    st = svc.statements(business)
    return {"business": business or "This business", "phone_last4": doc["phone"][-4:], "used": bool(doc.get("used_at")),
            "scopes": [{"scope": s, **st["scopes"][s]} for s in doc["scopes"]], "version": st["version"],
            "opted_out": bool(await suppression.active(db, doc["phone"], doc["org_id"]))}


@public_router.post("/{token}")
async def public_submit(token: str, body: PublicBody, request: Request):
    db = get_db()
    doc = await _link(token)
    if doc.get("used_at"):
        raise HTTPException(status_code=409, detail="This opt-in was already completed.")
    if not body.agree:
        raise HTTPException(status_code=400, detail="Check the box to agree.")
    if (body.confirm_last4 or "").strip()[-4:] != doc["phone"][-4:]:
        raise HTTPException(status_code=400, detail="Those digits do not match the phone number this link was made for.")
    scopes = [s for s in body.scopes if s in doc["scopes"]]
    try:
        recs = await svc.record(db, org_id=doc["org_id"], phone=doc["phone"], scopes=scopes, method="web_form", source="opt_in_page",
                                location_id=doc.get("location_id"), contact_id=doc.get("contact_id"), business=await _business(db, doc["org_id"], doc.get("location_id")),
                                evidence={"token": token, "link_created_by": doc.get("created_by"), "confirmed_last4": True},
                                ip=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip(), user_agent=request.headers.get("user-agent") or "")
    except svc.ConsentError as e:
        raise HTTPException(status_code=409 if e.code == "opted_out" else 400,
                            detail="You opted out of texts earlier. To turn them back on, text START to the business's number." if e.code == "opted_out" else str(e))
    await db[LINKS].update_one({"_id": token}, {"$set": {"used_at": datetime.now(timezone.utc), "used_scopes": scopes}})
    return {"ok": True, "recorded": [r["scope"] for r in recs]}


# ── controlled migration + policy (managers for their own organization, super admin for any) ──
def _manager_org(me: dict, org_id: Optional[str]) -> str:
    if me.get("role") not in MANAGERS:
        raise HTTPException(status_code=403, detail="Managers only")
    if me.get("role") == "super_admin":
        if not org_id:
            raise HTTPException(status_code=400, detail="org_id is required")
        return org_id
    own = str(me.get("organization_id") or "")
    if org_id and org_id != own:
        raise HTTPException(status_code=403, detail="Another organization's data")
    return own


@router.get("/admin/migration-report")
async def migration_report(request: Request, org_id: Optional[str] = None):
    me = request.state.user
    if me.get("role") == "super_admin" and not org_id:
        return await svc.migration_report(get_db())
    return await svc.migration_report(get_db(), _manager_org(me, org_id))


class MigrateBody(BaseModel):
    org_id: Optional[str] = None
    step: str
    apply: bool = False


@router.post("/admin/migrate")
async def migrate(body: MigrateBody, request: Request):
    me = request.state.user
    org = _manager_org(me, body.org_id)
    if body.step == "lead_forms":
        return await svc.migrate_legacy_form_opt_ins(get_db(), org, me, apply=body.apply)
    if body.step == "inbound":
        return await svc.backfill_inbound(get_db(), org, apply=body.apply)
    raise HTTPException(status_code=400, detail="step must be lead_forms or inbound")


class PolicyBody(BaseModel):
    reply_window_days: Optional[int] = None
    disclosure: Optional[dict] = None


@router.get("/admin/policy")
async def get_policy(request: Request):
    me = request.state.user
    if me.get("role") not in MANAGERS:
        raise HTTPException(status_code=403, detail="Managers only")
    org = await get_db().organizations.find_one({"_id": ObjectId(me["organization_id"])}, {"messaging_disclosure": 1, "name": 1}) if ObjectId.is_valid(str(me.get("organization_id") or "")) else None
    from services.outbound_gate import consent_mode, sender_mode
    return {"consent": await svc.policy(get_db()), "disclosure": await disclosure.effective_policy(get_db(), org), "sender_policy_mode": sender_mode(), "consent_mode": consent_mode()}


@router.put("/admin/policy")
async def put_policy(body: PolicyBody, request: Request):
    me = request.state.user
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    db = get_db()
    if body.reply_window_days is not None:
        if not 1 <= body.reply_window_days <= 365:
            raise HTTPException(status_code=400, detail="reply_window_days must be 1-365")
        await db.settings.update_one({"key": "consent_policy"}, {"$set": {"key": "consent_policy", "reply_window_days": body.reply_window_days}}, upsert=True)
    if body.disclosure is not None:
        allowed = {k: v for k, v in body.disclosure.items() if k in ("programs", "jurisdictions", "templates", "version")}
        await db.settings.update_one({"key": "disclosure_policy"}, {"$set": {"key": "disclosure_policy", **allowed}}, upsert=True)
    return await get_policy(request)
