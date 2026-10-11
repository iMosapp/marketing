"""Founder customer launch (Stage 1): list / inspect / activate / invite customers created through the Onboarding Hub.
Separate from legacy organization administration on purpose. Creation stays on POST /setup-wizard/new-account."""
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.billing import public_base
from routers.database import get_db
from routers.rbac import get_scoped_organization_ids, require_account_creator, require_role
from services import billing
from services import customers as svc

router = APIRouter(prefix="/customers", tags=["Customers"])

SUPER = Depends(require_role("super_admin"))


class ExceptionBody(BaseModel):
    reason: str
    expires_at: str


class PatchBody(BaseModel):
    notes: Optional[str] = None
    seats_extra: Optional[int] = None
    plan_key: Optional[str] = None


async def _org(org_id: str, me: dict) -> dict:
    db = get_db()
    org = await svc.customer_org(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Customer not found")
    if me.get("role") != "super_admin" and org_id not in await get_scoped_organization_ids(me):
        raise HTTPException(status_code=403, detail="Access denied to this customer")
    return org


@router.get("/plans")
async def list_plans(me: dict = Depends(require_account_creator)):
    return list(svc.PILOT_PLANS.values())


@router.get("")
async def list_customers(me: dict = Depends(require_account_creator)):
    db = get_db()
    query: dict = {"customer": {"$exists": True}}
    if me.get("role") != "super_admin":
        ids = [ObjectId(o) for o in await get_scoped_organization_ids(me) if ObjectId.is_valid(o)]
        query["_id"] = {"$in": ids}
    orgs = await db.organizations.find(query).sort("created_at", -1).to_list(500)
    return [await svc.row(db, o) for o in orgs]


@router.get("/{org_id}")
async def get_customer(org_id: str, me: dict = Depends(require_account_creator)):
    db = get_db()
    org = await _org(org_id, me)
    log = await db.customer_audit_log.find({"organization_id": org_id}, {"_id": 0}).sort("at", -1).to_list(50)
    return {**await svc.row(db, org), "audit": log}


@router.patch("/{org_id}")
async def patch_customer(org_id: str, body: PatchBody, me: dict = SUPER):
    db = get_db()
    org = await _org(org_id, me)
    c = org["customer"]
    changes = {}
    if body.notes is not None:
        changes["notes"] = body.notes.strip()[:2000]
    plan_key = body.plan_key or c["plan_key"]
    if body.plan_key is not None or body.seats_extra is not None:
        p = svc.plan(plan_key)
        seats_extra = c.get("seats_extra", 0) if body.seats_extra is None else int(body.seats_extra)
        if seats_extra < 0 or seats_extra > 500:
            raise HTTPException(status_code=400, detail="Extra seats must be between 0 and 500")
        if p["seat_price"] is None and seats_extra:
            raise HTTPException(status_code=400, detail="This plan has no extra seats")
        used = await svc.seats_used(db, org_id)
        if p["seats_included"] + seats_extra < used:
            raise HTTPException(status_code=400, detail=f"{used} seats are already in use. Deactivate people before shrinking the plan.")
        changes.update(plan_key=plan_key, plan_name=p["name"], amount=p["amount"], seat_price=p["seat_price"], seats_included=p["seats_included"], seats_extra=seats_extra)
        if body.plan_key is not None and plan_key != c["plan_key"] and c.get("stripe_subscription_id") and c.get("billing_status") not in ("canceled", "unpaid"):
            raise HTTPException(status_code=409, detail="This customer has a live subscription. Change the plan from Stripe, then sync.")
        if seats_extra != int(c.get("seats_extra") or 0):
            await billing.sync_seats_to_stripe(db, org, seats_extra, me)
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to change")
    await svc._set(db, org_id, **changes)
    await svc.audit(db, org_id, "customer_updated", me, **changes)
    return await svc.row(db, await svc.customer_org(db, org_id))


# ── Stage 2: Stripe billing (super admin) ─────────────────────────────────────

class SendBody(BaseModel):
    send: bool = True


class CancelBody(BaseModel):
    cancel: bool = True


@router.post("/{org_id}/payment-link")
async def payment_link(org_id: str, body: SendBody, request: Request, me: dict = SUPER):
    """Create (or reuse) the Stripe Checkout link for this customer and optionally text + email it to the owner."""
    db = get_db()
    org = await _org(org_id, me)
    c = org["customer"]
    reusable = c.get("checkout_url") and c.get("billing_status") == "awaiting_payment" and (c.get("checkout_expires_at") or "") > svc.now_iso()
    res = {"url": c["checkout_url"], "session_id": c.get("checkout_session_id"), "expires_at": c.get("checkout_expires_at")} if reusable \
        else await billing.create_checkout(db, org, me, public_base(request))
    if body.send:
        res["sent"] = await billing.send_payment_link(db, await svc.customer_org(db, org_id), me, res["url"])
    return res


@router.post("/{org_id}/sync-billing")
async def sync_billing(org_id: str, me: dict = SUPER):
    db = get_db()
    org = await _org(org_id, me)
    result = await billing.sync_from_stripe(db, org, me)
    return {"billing_status": result.get("billing_status"), "customer": await svc.row(db, await svc.customer_org(db, org_id))}


@router.post("/{org_id}/portal-link")
async def portal_link(org_id: str, request: Request, me: dict = SUPER):
    org = await _org(org_id, me)
    url = await billing.portal_url(get_db(), org, public_base(request), f"/admin/customers/{org_id}")
    await svc.audit(get_db(), org_id, "portal_link_created", me)
    return {"url": url}


@router.post("/{org_id}/cancel")
async def cancel_subscription(org_id: str, body: CancelBody, me: dict = SUPER):
    org = await _org(org_id, me)
    return await billing.set_cancel_at_period_end(get_db(), org, me, body.cancel)


@router.post("/{org_id}/billing-exception")
async def billing_exception(org_id: str, body: ExceptionBody, me: dict = SUPER):
    org = await _org(org_id, me)
    exc = await svc.grant_exception(get_db(), org, me, body.reason, body.expires_at)
    return {"success": True, "billing_exception": exc}


@router.post("/{org_id}/activate")
async def activate_customer(org_id: str, me: dict = SUPER):
    org = await _org(org_id, me)
    return await svc.activate(get_db(), org, me)


@router.post("/{org_id}/invite-owner")
async def invite_owner(org_id: str, me: dict = SUPER):
    org = await _org(org_id, me)
    return await svc.invite_owner(get_db(), org, me)
