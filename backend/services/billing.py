"""Stage 2: Stripe recurring billing for launch customers (organizations that carry `customer`).
Isolated `stripe.StripeClient` on STRIPE_BILLING_SECRET_KEY: never touches `stripe.api_key` / `stripe.api_base`, so the
Mystery Shops invoices (STRIPE_SECRET_KEY) and the legacy emergentintegrations flows (STRIPE_API_KEY) are unaffected.
Policy: a failed renewal never suspends access by itself; the customer goes `past_due` with a GRACE_DAYS window and the founder is told."""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import stripe
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from services import customers as cust

logger = logging.getLogger(__name__)

SEAT_KEY = "pilot_seat_monthly"
CATALOG = {
    "pilot_store_monthly": {"product": "i'M On Social Pilot Store", "desc": "Pilot Store plan, 5 seats included", "unit_amount": int(cust.PILOT_PLANS["pilot_store_monthly"]["amount"] * 100)},
    SEAT_KEY: {"product": "i'M On Social Additional Seat", "desc": "One additional seat on the Pilot Store plan", "unit_amount": int(cust.PILOT_PLANS["pilot_store_monthly"]["seat_price"] * 100)},
    "pilot_individual_monthly": {"product": "i'M On Social Pilot Individual", "desc": "Pilot Individual plan, 1 seat", "unit_amount": int(cust.PILOT_PLANS["pilot_individual_monthly"]["amount"] * 100)},
}
GRACE_DAYS = 14
HANDLED_EVENTS = ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated",
                  "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed")
STATUS_MAP = {"active": "active", "trialing": "trialing", "past_due": "past_due", "unpaid": "past_due", "paused": "past_due",
              "canceled": "canceled", "incomplete": "awaiting_payment", "incomplete_expired": "unpaid"}
RESUBSCRIBE_OK = {"unpaid", "awaiting_payment", "canceled", "exception"}

_client: stripe.StripeClient | None = None
_prices: dict[str, str] = {}


def configured() -> bool:
    return bool(os.environ.get("STRIPE_BILLING_SECRET_KEY"))


def client() -> stripe.StripeClient:
    global _client
    key = os.environ.get("STRIPE_BILLING_SECRET_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Billing is not configured on this server")
    if _client is None:
        _client = stripe.StripeClient(key, max_network_retries=2)
    return _client


async def _run(fn, *args, **kwargs):
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except stripe.StripeError as e:
        logger.warning(f"[Billing] Stripe {type(e).__name__}: {getattr(e, 'user_message', None) or e.code or 'request failed'}")
        raise HTTPException(status_code=502, detail=f"Stripe: {getattr(e, 'user_message', None) or 'request failed, try again'}")


def _iso(ts) -> str | None:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat() if ts else None


def _d(obj) -> dict:
    return json.loads(json.dumps(obj)) if not isinstance(obj, dict) or hasattr(obj, "to_dict") else obj


# ── catalog ───────────────────────────────────────────────────────────────────

def ensure_catalog_sync(sc: stripe.StripeClient, dry_run: bool = False) -> dict:
    """Idempotent: one product + one monthly price per lookup key. Second run creates nothing."""
    out = {}
    for key, spec in CATALOG.items():
        found = sc.v1.prices.list({"lookup_keys": [key], "active": True, "limit": 1})
        if found.data:
            p = found.data[0]
            out[key] = {"price_id": p.id, "unit_amount": p.unit_amount, "created": False}
            continue
        if dry_run:
            out[key] = {"price_id": None, "unit_amount": spec["unit_amount"], "created": "would create"}
            continue
        product = sc.v1.products.create({"name": spec["product"], "description": spec["desc"], "metadata": {"catalog_key": key, "app": "imonsocial"}},
                                        {"idempotency_key": f"imos-product-{key}-v1"})
        price = sc.v1.prices.create({"product": product.id, "currency": "usd", "unit_amount": spec["unit_amount"], "recurring": {"interval": "month"},
                                     "lookup_key": key, "metadata": {"catalog_key": key, "app": "imonsocial"}},
                                    {"idempotency_key": f"imos-price-{key}-v1"})
        out[key] = {"price_id": price.id, "unit_amount": price.unit_amount, "created": True}
    return out


async def price_ids() -> dict[str, str]:
    if len(_prices) < len(CATALOG):
        cat = await _run(ensure_catalog_sync, client())
        _prices.update({k: v["price_id"] for k, v in cat.items()})
    return _prices


# ── helpers ───────────────────────────────────────────────────────────────────

async def _owner(db, c: dict) -> dict:
    if ObjectId.is_valid(c.get("owner_user_id") or ""):
        return await db.users.find_one({"_id": ObjectId(c["owner_user_id"])}, {"name": 1, "first_name": 1, "email": 1, "phone": 1}) or {}
    return {}


def _owner_email(owner: dict) -> str | None:
    email = (owner.get("email") or "").lower()
    return None if not email or email.endswith(cust.PLACEHOLDER_EMAIL_SUFFIX) else email


async def _notify_founder(db, org: dict, ntype: str, title: str, body: str) -> None:
    founder = (org.get("customer") or {}).get("created_by")
    if not founder:
        return
    link = f"/admin/customers/{org['_id']}"
    try:
        from routers.push_notifications import send_push_to_user
        await send_push_to_user(founder, title, body, link, "card")
    except Exception as e:
        logger.warning(f"[Billing] founder push failed: {e}")
    try:
        from routers.notifications import create_notification
        await create_notification(ntype, title, body, user_id=founder, link=link)
    except Exception as e:
        logger.debug(f"[Billing] founder notification skipped: {e}")


async def _org_for(db, org_id: str | None = None, subscription_id: str | None = None, customer_id: str | None = None) -> dict | None:
    org = await cust.customer_org(db, org_id) if org_id else None
    if not org and subscription_id:
        org = await db.organizations.find_one({"customer.stripe_subscription_id": subscription_id})
    if not org and customer_id:
        org = await db.organizations.find_one({"customer.stripe_customer_id": customer_id})
    return org


def _invoice_subscription_id(inv: dict) -> str | None:
    sub = inv.get("subscription") or (((inv.get("parent") or {}).get("subscription_details") or {}).get("subscription"))
    return sub.get("id") if isinstance(sub, dict) else sub


# ── Stripe customer + checkout ────────────────────────────────────────────────

async def _ensure_stripe_customer(db, org: dict) -> str:
    c = org["customer"]
    if c.get("stripe_customer_id"):
        return c["stripe_customer_id"]
    owner = await _owner(db, c)
    params = {"name": org.get("name"), "metadata": {"organization_id": str(org["_id"]), "source": "customer_launch"}}
    if _owner_email(owner):
        params["email"] = _owner_email(owner)
    if owner.get("phone"):
        params["phone"] = owner["phone"]
    created = await _run(client().v1.customers.create, params, {"idempotency_key": f"imos-customer-{org['_id']}-v1"})
    await cust._set(db, str(org["_id"]), stripe_customer_id=created.id)
    return created.id


async def create_checkout(db, org: dict, actor: dict, base_url: str) -> dict:
    """Stripe-hosted Checkout in subscription mode: base plan x1 (+ seat price x seats_extra). Nothing is charged here."""
    c = org["customer"]
    org_id = str(org["_id"])
    if c.get("stripe_subscription_id") and c.get("billing_status") in ("active", "trialing", "past_due"):
        raise HTTPException(status_code=409, detail="This customer already has a subscription. Use the billing portal to change payment details.")
    prices = await price_ids()
    customer_id = await _ensure_stripe_customer(db, org)
    line_items = [{"price": prices[c["plan_key"]], "quantity": 1}]
    if c.get("seat_price") and int(c.get("seats_extra") or 0) > 0:
        line_items.append({"price": prices[SEAT_KEY], "quantity": int(c["seats_extra"])})
    meta = {"organization_id": org_id, "source": "customer_launch", "plan_key": c["plan_key"]}
    session = await _run(client().v1.checkout.sessions.create, {
        "mode": "subscription", "customer": customer_id, "client_reference_id": org_id, "line_items": line_items,
        "success_url": f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}", "cancel_url": f"{base_url}/billing/cancel",
        "metadata": meta, "subscription_data": {"metadata": meta, "description": f"{c['plan_name']} - {org.get('name', '')}"[:500]},
        "billing_address_collection": "auto", "customer_update": {"name": "auto", "address": "auto"},
    })
    fields = {"checkout_session_id": session.id, "checkout_url": session.url, "checkout_created_at": cust.now_iso(), "checkout_expires_at": _iso(session.expires_at)}
    if c.get("billing_status") in ("unpaid", "canceled", "awaiting_payment"):
        fields["billing_status"] = "awaiting_payment"
    if c.get("onboarding_status") == "created":
        fields["onboarding_status"] = "payment_link_sent"
    await cust._set(db, org_id, **fields)
    await cust.audit(db, org_id, "payment_link_created", actor, amount=c.get("amount"), seats_extra=c.get("seats_extra", 0))
    return {"url": session.url, "session_id": session.id, "expires_at": fields["checkout_expires_at"]}


async def send_payment_link(db, org: dict, actor: dict, url: str) -> dict:
    """Text + email the Checkout link to the owner (500-555 numbers and @invalid addresses stay harmless in QA)."""
    c = org["customer"]
    owner = await _owner(db, c)
    first = owner.get("first_name") or (owner.get("name") or "").split(" ")[0] or "there"
    plan_line = f"{c['plan_name']} ${int(c['amount'] + (c.get('seat_price') or 0) * (c.get('seats_extra') or 0))}/month"
    sms_sent = email_sent = False
    if owner.get("phone"):
        try:
            from services.twilio_service import send_sms
            res = await send_sms(owner["phone"], f"Hi {first}, here is the secure payment link for {org.get('name', 'your')} on I'm On Social ({plan_line}). "
                                                 f"Card details go to Stripe, never to us: {url}")
            sms_sent = bool(res.get("success"))
        except Exception as e:
            logger.warning(f"[Billing] payment link text failed for {org['_id']}: {e}")
    email = _owner_email(owner)
    if email:
        try:
            import resend
            resend.api_key = os.environ.get("RESEND_API_KEY")
            sender = os.environ.get("SENDER_EMAIL", "notifications@imonsocial.com")
            html = (f"<p>Hi {first},</p><p>Here is the secure payment link for <strong>{org.get('name', '')}</strong> on I'm On Social: {plan_line}.</p>"
                    f"<p><a href=\"{url}\" style=\"background:#C9A962;color:#111;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:700\">Set up payment</a></p>"
                    f"<p style=\"color:#666;font-size:13px\">Payments are handled by Stripe. Your card details never reach I'm On Social.</p>")
            r = await asyncio.to_thread(resend.Emails.send, {"from": f"I'm On Social <{sender}>", "to": [email], "subject": f"Payment link for {org.get('name', 'your account')}",
                                                             "html": html, "text": f"Hi {first}, here is the secure payment link for {org.get('name', '')} ({plan_line}): {url}"})
            email_sent = bool((r or {}).get("id"))
        except Exception as e:
            logger.warning(f"[Billing] payment link email failed for {org['_id']}: {e}")
    await cust._set(db, str(org["_id"]), payment_link_sent_at=cust.now_iso())
    await cust.audit(db, str(org["_id"]), "payment_link_sent", actor, sms_sent=sms_sent, email_sent=email_sent)
    return {"sms_sent": sms_sent, "email_sent": email_sent}


# ── subscription state (single writer for pull + webhook) ─────────────────────

async def apply_subscription(db, org: dict, sub: dict, source: str, actor: dict | None = None) -> dict:
    """Map a Stripe Subscription onto organizations.customer. Stripe is the source of truth for status and seat quantity."""
    sub = _d(sub)
    c = org["customer"]
    org_id = str(org["_id"])
    items = ((sub.get("items") or {}).get("data")) or []
    seat_item = next((it for it in items if (it.get("price") or {}).get("lookup_key") == SEAT_KEY), None)
    base_item = next((it for it in items if (it.get("price") or {}).get("lookup_key") in cust.PILOT_PLANS), None)
    period_end = sub.get("current_period_end") or (items[0].get("current_period_end") if items else None)
    new_status = STATUS_MAP.get(sub.get("status"), c.get("billing_status"))
    fields = {
        "stripe_customer_id": sub.get("customer") if isinstance(sub.get("customer"), str) else (sub.get("customer") or {}).get("id"),
        "stripe_subscription_id": sub.get("id"), "subscription_status": sub.get("status"), "billing_status": new_status,
        "current_period_end": _iso(period_end), "cancel_at_period_end": bool(sub.get("cancel_at_period_end")), "canceled_at": _iso(sub.get("canceled_at")),
        "seat_item_id": (seat_item or {}).get("id"), "base_item_id": (base_item or {}).get("id"), "billing_synced_at": cust.now_iso(), "billing_source": source,
    }
    if seat_item is not None or c.get("seat_price"):
        fields["seats_extra"] = int((seat_item or {}).get("quantity") or 0)
    if new_status in ("active", "trialing"):
        fields["grace_until"] = None
        fields["paid_at"] = c.get("paid_at") or cust.now_iso()
        if c.get("onboarding_status") in ("created", "payment_link_sent"):
            fields["onboarding_status"] = "paid"
    await cust._set(db, org_id, **fields)
    if new_status != c.get("billing_status"):
        await cust.audit(db, org_id, f"subscription_{new_status}", actor, source=source, stripe_status=sub.get("status"))
    if fields.get("seats_extra") is not None and fields["seats_extra"] != int(c.get("seats_extra") or 0):
        await cust.audit(db, org_id, "seats_synced_from_stripe", actor, before=c.get("seats_extra", 0), after=fields["seats_extra"], source=source)
    return fields


async def sync_from_stripe(db, org: dict, actor: dict | None = None) -> dict:
    """Pull the truth: subscription by id, else the pending Checkout session. Safe to call any time."""
    c = org["customer"]
    sc = client()
    if c.get("stripe_subscription_id"):
        sub = await _run(sc.v1.subscriptions.retrieve, c["stripe_subscription_id"])
        return await apply_subscription(db, org, sub, "pull", actor)
    if c.get("checkout_session_id"):
        session = await _run(sc.v1.checkout.sessions.retrieve, c["checkout_session_id"], {"expand": ["subscription"]})
        if session.get("subscription") and session.get("payment_status") in ("paid", "no_payment_required"):
            return await apply_subscription(db, org, session["subscription"], "pull", actor)
        if session.get("status") == "expired" and c.get("billing_status") == "awaiting_payment":
            await cust._set(db, str(org["_id"]), billing_status="unpaid", checkout_url=None)
            return {"billing_status": "unpaid", "checkout_expired": True}
        return {"billing_status": c.get("billing_status"), "payment_status": session.get("payment_status")}
    return {"billing_status": c.get("billing_status")}


async def confirm_checkout(db, session_id: str) -> dict:
    """Return-URL handler (anonymous): Stripe is asked directly, the browser is never trusted. Returns only safe display fields."""
    if not session_id or not session_id.startswith("cs_"):
        raise HTTPException(status_code=400, detail="Invalid session")
    session = await _run(client().v1.checkout.sessions.retrieve, session_id, {"expand": ["subscription"]})
    org_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("organization_id")
    org = await cust.customer_org(db, org_id)
    if not org or session.get("mode") != "subscription":
        raise HTTPException(status_code=404, detail="Unknown checkout")
    if session.get("subscription") and session.get("payment_status") in ("paid", "no_payment_required"):
        await apply_subscription(db, org, session["subscription"], "checkout_return")
        org = await cust.customer_org(db, org_id)
    c = org["customer"]
    return {"business_name": org.get("name"), "payment_status": session.get("payment_status"), "billing_status": c.get("billing_status"),
            "plan_name": c.get("plan_name"), "activated": bool(c.get("activated_at"))}


# ── seats, portal, cancel / resume ────────────────────────────────────────────

async def sync_seats_to_stripe(db, org: dict, seats_extra: int, actor: dict) -> None:
    """Keep the seat item quantity equal to seats_extra. Prorations are invoiced right away."""
    c = org["customer"]
    if not c.get("stripe_subscription_id") or c.get("billing_status") in ("canceled", "unpaid"):
        return
    sc = client()
    seat_item = c.get("seat_item_id")
    if seat_item and seats_extra == 0:
        await _run(sc.v1.subscription_items.delete, seat_item, {"proration_behavior": "always_invoice"})
        await cust._set(db, str(org["_id"]), seat_item_id=None)
    elif seat_item:
        await _run(sc.v1.subscription_items.update, seat_item, {"quantity": seats_extra, "proration_behavior": "always_invoice"})
    elif seats_extra > 0:
        prices = await price_ids()
        item = await _run(sc.v1.subscription_items.create, {"subscription": c["stripe_subscription_id"], "price": prices[SEAT_KEY], "quantity": seats_extra, "proration_behavior": "always_invoice"})
        await cust._set(db, str(org["_id"]), seat_item_id=item.id)
    await cust.audit(db, str(org["_id"]), "seats_synced_to_stripe", actor, before=c.get("seats_extra", 0), after=seats_extra)


async def _portal_configuration(db, base_url: str) -> str:
    row = await db.billing_settings.find_one({"_id": "stripe_portal"})
    if row and row.get("configuration_id"):
        return row["configuration_id"]
    sc = client()
    existing = await _run(sc.v1.billing_portal.configurations.list, {"limit": 20})
    cfg = next((x for x in existing.data if (x.metadata or {}).get("app") == "imonsocial"), None)
    if not cfg:
        cfg = await _run(sc.v1.billing_portal.configurations.create, {
            "business_profile": {"headline": "I'm On Social billing"}, "default_return_url": f"{base_url}/settings/billing",
            "features": {"customer_update": {"enabled": True, "allowed_updates": ["email", "phone", "address", "name"]}, "invoice_history": {"enabled": True},
                         "payment_method_update": {"enabled": True}, "subscription_cancel": {"enabled": True, "mode": "at_period_end", "proration_behavior": "none"}},
            "metadata": {"app": "imonsocial", "version": "v1"},
        }, {"idempotency_key": "imos-portal-config-v1"})
    await db.billing_settings.update_one({"_id": "stripe_portal"}, {"$set": {"configuration_id": cfg.id, "created_at": cust.now_iso()}}, upsert=True)
    return cfg.id


async def portal_url(db, org: dict, base_url: str, return_path: str = "/settings/billing") -> str:
    c = org["customer"]
    if not c.get("stripe_customer_id"):
        raise HTTPException(status_code=409, detail="No Stripe customer yet. Send the payment link first.")
    cfg = await _portal_configuration(db, base_url)
    session = await _run(client().v1.billing_portal.sessions.create, {"customer": c["stripe_customer_id"], "return_url": f"{base_url}{return_path}", "configuration": cfg})
    return session.url


async def set_cancel_at_period_end(db, org: dict, actor: dict, cancel: bool) -> dict:
    c = org["customer"]
    if not c.get("stripe_subscription_id") or c.get("billing_status") in ("canceled", "unpaid"):
        raise HTTPException(status_code=409, detail="No active subscription to change.")
    sub = await _run(client().v1.subscriptions.update, c["stripe_subscription_id"], {"cancel_at_period_end": cancel})
    fields = await apply_subscription(db, org, sub, "founder", actor)
    await cust.audit(db, str(org["_id"]), "cancel_scheduled" if cancel else "cancel_reverted", actor, period_end=fields.get("current_period_end"))
    return {"cancel_at_period_end": fields["cancel_at_period_end"], "current_period_end": fields.get("current_period_end")}


# ── webhook ───────────────────────────────────────────────────────────────────

async def handle_event(db, event: dict) -> dict:
    """Idempotent by Stripe event id (unique _id in stripe_events). Unknown or unrelated events are acknowledged and ignored."""
    eid, typ = event.get("id"), event.get("type")
    try:
        await db.stripe_events.insert_one({"_id": eid, "type": typ, "livemode": event.get("livemode"), "received_at": cust.now_iso(), "processed": False})
    except DuplicateKeyError:
        return {"received": True, "duplicate": True}
    if typ not in HANDLED_EVENTS:
        await db.stripe_events.update_one({"_id": eid}, {"$set": {"processed": True, "ignored": True}})
        return {"received": True, "ignored": True}
    obj = (event.get("data") or {}).get("object") or {}
    try:
        result = await _dispatch(db, typ, obj)
        await db.stripe_events.update_one({"_id": eid}, {"$set": {"processed": True, "organization_id": result.get("organization_id"), "result": result.get("result")}})
        return {"received": True, **result}
    except Exception:
        await db.stripe_events.delete_one({"_id": eid})
        raise


async def _dispatch(db, typ: str, obj: dict) -> dict:
    if typ == "checkout.session.completed":
        if obj.get("mode") != "subscription" or not obj.get("subscription"):
            return {"result": "ignored"}
        org = await _org_for(db, obj.get("client_reference_id") or (obj.get("metadata") or {}).get("organization_id"), customer_id=obj.get("customer"))
        if not org:
            return {"result": "no_customer"}
        sub = await _run(client().v1.subscriptions.retrieve, obj["subscription"])
        fields = await apply_subscription(db, org, sub, "webhook")
        return {"organization_id": str(org["_id"]), "result": fields["billing_status"]}

    if typ.startswith("customer.subscription."):
        org = await _org_for(db, (obj.get("metadata") or {}).get("organization_id"), subscription_id=obj.get("id"), customer_id=obj.get("customer"))
        if not org:
            return {"result": "no_customer"}
        before = org["customer"].get("billing_status")
        fields = await apply_subscription(db, org, obj, "webhook")
        if typ == "customer.subscription.deleted":
            await _notify_founder(db, org, "customer_subscription_canceled", f"{org.get('name')} subscription ended",
                                  "The Stripe subscription is canceled. Access stays on until you decide; open the customer to resend a payment link or turn the account off.")
        elif obj.get("cancel_at_period_end") and not org["customer"].get("cancel_at_period_end"):
            await _notify_founder(db, org, "customer_cancel_scheduled", f"{org.get('name')} scheduled a cancellation",
                                  f"Access continues until {(fields.get('current_period_end') or '')[:10]}. Reach out before then.")
        elif before == "past_due" and fields["billing_status"] in ("active", "trialing"):
            await _notify_founder(db, org, "customer_payment_recovered", f"{org.get('name')} is paid up again", "The failed payment went through. Nothing to do.")
        return {"organization_id": str(org["_id"]), "result": fields["billing_status"]}

    sub_id = _invoice_subscription_id(obj)
    org = await _org_for(db, None, subscription_id=sub_id, customer_id=obj.get("customer") if isinstance(obj.get("customer"), str) else None)
    if not org:
        return {"result": "no_customer"}
    org_id = str(org["_id"])
    amount = (obj.get("amount_paid") if typ == "invoice.paid" else obj.get("amount_due")) or 0
    if typ == "invoice.paid":
        before = org["customer"].get("billing_status")
        fields = {"last_payment_at": _iso(obj.get("status_transitions", {}).get("paid_at")) or cust.now_iso(), "last_payment_amount": amount / 100, "last_invoice_id": obj.get("id"),
                  "grace_until": None, "failed_attempts": 0}
        if sub_id:
            sub = await _run(client().v1.subscriptions.retrieve, sub_id)
            await apply_subscription(db, org, sub, "webhook")
        await cust._set(db, org_id, **fields)
        await cust.audit(db, org_id, "payment_succeeded", None, amount=amount / 100, invoice=obj.get("id"), billing_reason=obj.get("billing_reason"))
        if before == "past_due":
            await _notify_founder(db, org, "customer_payment_recovered", f"{org.get('name')} is paid up again", f"${amount / 100:,.2f} came through. Nothing to do.")
        return {"organization_id": org_id, "result": "paid"}

    c = org["customer"]
    grace_until = c.get("grace_until") or (datetime.now(timezone.utc) + timedelta(days=GRACE_DAYS)).isoformat()
    await cust._set(db, org_id, billing_status="past_due", grace_until=grace_until, payment_failed_at=cust.now_iso(), failed_attempts=int(c.get("failed_attempts") or 0) + 1,
                    last_invoice_id=obj.get("id"))
    await cust.audit(db, org_id, "payment_failed", None, amount=amount / 100, invoice=obj.get("id"), grace_until=grace_until, attempt=int(c.get("failed_attempts") or 0) + 1)
    await _notify_founder(db, org, "customer_payment_failed", f"Payment failed for {org.get('name')}",
                          f"${amount / 100:,.2f} did not go through. Stripe retries automatically; access stays on until {grace_until[:10]}. Ask them to update their card in Billing.")
    return {"organization_id": org_id, "result": "past_due"}


def owner_summary(org: dict) -> dict:
    """What the paying owner may see about their own billing. No Stripe ids, no card data."""
    c = org.get("customer") or {}
    return {
        "business_name": org.get("name"), "plan_name": c.get("plan_name"), "amount": c.get("amount"), "seat_price": c.get("seat_price"),
        "seats_included": c.get("seats_included"), "seats_extra": c.get("seats_extra", 0),
        "monthly_total": float(c.get("amount") or 0) + float(c.get("seat_price") or 0) * int(c.get("seats_extra") or 0),
        "billing_status": c.get("billing_status"), "current_period_end": c.get("current_period_end"), "cancel_at_period_end": bool(c.get("cancel_at_period_end")),
        "grace_until": c.get("grace_until"), "last_payment_at": c.get("last_payment_at"), "last_payment_amount": c.get("last_payment_amount"),
        "portal_available": bool(c.get("stripe_customer_id")) and configured(),
        "checkout_url": c.get("checkout_url") if c.get("billing_status") in ("unpaid", "awaiting_payment", "canceled") else None,
        "exception": bool(c.get("billing_status") == "exception"), "exception_ends": (c.get("billing_exception") or {}).get("expires_at") if c.get("billing_status") == "exception" else None,
    }
