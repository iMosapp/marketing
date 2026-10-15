"""Stage 2 billing surface: signed Stripe webhook, anonymous Checkout return, and the paying owner's own billing view.
Founder-side billing actions live on /api/customers/{org_id}/... (super admin only)."""
import json
import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.rbac import require_role
from services import billing as svc
from services import customers as cust

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])


def public_base(request: Request) -> str:
    """Return URLs follow the host that made the request (preview stays on preview, production on production)."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    if host and "localhost" not in host and not host.startswith("127."):
        return f"https://{host.split(',')[0].strip()}"
    from routers.admin_helpers import APP_URL
    return APP_URL


class ConfirmBody(BaseModel):
    session_id: str


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    secret = os.environ.get("STRIPE_BILLING_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Billing webhook is not configured")
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    try:
        stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError):
        logger.warning("[Billing] webhook rejected: bad signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = json.loads(payload)
    return await svc.handle_event(get_db(), event)


@router.post("/checkout/confirm")
async def confirm_checkout(body: ConfirmBody):
    return await svc.confirm_checkout(get_db(), body.session_id.strip())


async def _my_customer_org(me: dict) -> dict:
    org = await cust.customer_org(get_db(), me.get("organization_id"))
    if not org:
        raise HTTPException(status_code=404, detail="Billing for this account is handled by your I'm On Social representative.")
    return org


@router.get("/me")
async def my_billing(me: dict = Depends(require_role("store_manager"))):
    return svc.owner_summary(await _my_customer_org(me))


@router.post("/checkout")
async def my_checkout(request: Request, me: dict = Depends(require_role("store_manager"))):
    """The owner chooses to continue after the pilot (or to pay an unpaid plan): hosted Stripe Checkout, card saved on Stripe's page."""
    org = await _my_customer_org(me)
    c = org["customer"]
    if c.get("stripe_subscription_id") and c.get("billing_status") in ("active", "trialing", "past_due"):
        raise HTTPException(status_code=409, detail="Your subscription is already set up. Use Payment method, invoices and plan.")
    if c.get("billing_status") not in svc.RESUBSCRIBE_OK:
        raise HTTPException(status_code=409, detail="Nothing to pay right now.")
    res = await svc.checkout_link(get_db(), org, me, public_base(request))
    await cust.audit(get_db(), str(org["_id"]), "owner_checkout_opened", me, first_charge_on=res.get("first_charge_on"))
    return res


@router.post("/portal")
async def my_portal(request: Request, me: dict = Depends(require_role("store_manager"))):
    org = await _my_customer_org(me)
    url = await svc.portal_url(get_db(), org, public_base(request))
    await cust.audit(get_db(), str(org["_id"]), "portal_opened", me)
    return {"url": url}


@router.get("/access")
async def my_access(request: Request):
    """Subscription access for the signed-in person (open while locked): drives the access-paused screen."""
    from routers.rbac import get_current_user
    from services import billing_lock
    me = await get_current_user(request)
    st = await billing_lock.for_user(get_db(), me)
    if st.get("locked") and st.get("owner"):
        org = await cust.customer_org(get_db(), me.get("organization_id"))
        st["billing"] = svc.owner_summary(org) if org else None
    return st


class LegacyBody(BaseModel):
    review_by: str | None = None
    expires_at: str | None = None
    note: str | None = None


@router.get("/admin/access")
async def access_overview(me: dict = Depends(require_role("super_admin"))):
    """Every organization's subscription access state (super admin)."""
    from services import billing_lock
    from services.sender_policy import internal_org_ids
    db = get_db()
    internal = await internal_org_ids(db)
    out = []
    async for o in db.organizations.find({}, {"name": 1, "customer": 1, "billing_legacy": 1, "internal": 1}).limit(2000):
        st = billing_lock.evaluate(o, internal=str(o["_id"]) in internal)
        c = o.get("customer") or {}
        out.append({"id": str(o["_id"]), "name": o.get("name"), **st, "billing_status": c.get("billing_status"), "subscription_status": c.get("subscription_status"),
                    "legacy": o.get("billing_legacy")})
    return {"organizations": sorted(out, key=lambda r: (not r["locked"], r["state"], r.get("name") or "")),
            "locked": sum(1 for r in out if r["locked"])}


@router.post("/admin/access/classify-legacy")
async def classify_legacy(apply: bool = False, me: dict = Depends(require_role("super_admin"))):
    from services import billing_lock
    return await billing_lock.classify_legacy(get_db(), me, apply=apply)


@router.patch("/admin/access/{org_id}/legacy")
async def update_legacy(org_id: str, body: LegacyBody, me: dict = Depends(require_role("super_admin"))):
    """Admin-controlled legacy exception: a review date (reminder only) and, set on purpose, an expiration date."""
    from bson import ObjectId
    from services import billing_lock
    db = get_db()
    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=400, detail="Bad organization id")
    sets = {}
    for k in ("review_by", "expires_at"):
        v = getattr(body, k)
        if v is not None:
            if v and not billing_lock._dt(v):
                raise HTTPException(status_code=400, detail=f"{k} must be a date (YYYY-MM-DD)")
            sets[f"billing_legacy.{k}"] = billing_lock._dt(v).isoformat() if v else None
    if body.note is not None:
        sets["billing_legacy.note"] = body.note[:300]
    sets["billing_legacy.updated_by"] = str(me["_id"])
    r = await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": sets})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Organization not found")
    await cust.audit(db, org_id, "billing_legacy_updated", me, **{k.split(".")[-1]: v for k, v in sets.items()})
    billing_lock.invalidate()
    return (await db.organizations.find_one({"_id": ObjectId(org_id)}, {"billing_legacy": 1, "_id": 0})) or {}
