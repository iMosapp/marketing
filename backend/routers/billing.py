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
