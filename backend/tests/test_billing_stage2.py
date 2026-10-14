"""Stage 2 acceptance tests: Stripe recurring billing for launch customers, against the live preview API + the owner's test-mode sandbox.
Creates real test-mode objects (customer, checkout session, subscription, prorations) under "QA Pilot Billing *" and removes them at the end.
Webhook delivery itself is exercised through the service writer (handle_event) with synthetic events; the HTTP route is checked for
signature enforcement (503 until STRIPE_BILLING_WEBHOOK_SECRET is set, then 400 unsigned / 400 forged / 200 self-signed)."""
import asyncio
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import stripe

from services import billing
from tests._http import API, UA
from tests.live_auth import Session, anon, oid
from tests.wipe_pilot_customers import wipe
from tests import qa_creds

PREFIX = "QA Pilot Billing"
OWNER_PASSWORD = qa_creds.password_for("qa-pilot-owner-ui@invalid.imonsocial.test")
WEBHOOK = "/api/billing/stripe/webhook"

loop = asyncio.new_event_loop()


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


def _phone():
    return f"+1500555{secrets.randbelow(9000) + 1000}"


def _event(typ: str, obj: dict, eid: str | None = None) -> dict:
    return {"id": eid or f"evt_test_{secrets.token_hex(8)}", "object": "event", "type": typ, "livemode": False, "created": int(time.time()), "data": {"object": obj}}


def _post_raw(path: str, payload: bytes, headers: dict):
    req = urllib.request.Request(API + path, method="POST", data=payload, headers={"Content-Type": "application/json", **UA, **headers})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


@pytest.fixture(scope="module")
def sc():
    return billing.client()


@pytest.fixture(scope="module")
def customer(super_admin, mongo):
    suffix = secrets.token_hex(3)
    body = {
        "business_name": f"{PREFIX} Co {suffix}", "city": "Sandy", "state": "UT", "zip": "84070", "industry": "Automotive / Dealership",
        "contact_name": f"Billie Pilot{suffix}", "contact_email": f"qa-pilot-billing-{suffix}@invalid.imonsocial.test", "contact_phone": _phone(),
        "plan_key": "pilot_store_monthly", "seats_extra": 1, "pilot": True,
    }
    status, res = super_admin.post("/api/setup-wizard/new-account", body)
    assert status == 200, res
    yield {**res, "body": body}
    wipe(mongo, PREFIX, dry_run=False)


def _cust(mongo, org_id):
    return mongo.organizations.find_one({"_id": oid(org_id)})["customer"]


# ── B1 catalog ────────────────────────────────────────────────────────────────

def test_catalog_is_idempotent_and_priced_as_approved(sc):
    first = billing.ensure_catalog_sync(sc)
    second = billing.ensure_catalog_sync(sc)
    assert set(first) == {"pilot_store_monthly", "pilot_seat_monthly", "pilot_individual_monthly"}
    assert all(v["created"] is False for v in second.values()), second
    assert {k: v["unit_amount"] for k, v in second.items()} == {"pilot_store_monthly": 37500, "pilot_seat_monthly": 7500, "pilot_individual_monthly": 10000}
    assert {k: v["price_id"] for k, v in first.items()} == {k: v["price_id"] for k, v in second.items()}
    assert sc.v1.balance.retrieve().livemode is False


# ── B2 checkout link ──────────────────────────────────────────────────────────

def test_payment_link_creates_subscription_checkout(customer, super_admin, mongo, sc):
    org_id = customer["organization_id"]
    status, res = super_admin.post(f"/api/customers/{org_id}/payment-link", {"send": False})
    assert status == 200, res
    assert res["url"].startswith("https://checkout.stripe.com/") and res["session_id"].startswith("cs_test_") and "sent" not in res
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "awaiting_payment" and c["onboarding_status"] == "payment_link_sent"
    assert c["stripe_customer_id"].startswith("cus_") and c["checkout_session_id"] == res["session_id"] and c["checkout_url"] == res["url"]
    session = sc.v1.checkout.sessions.retrieve(res["session_id"])
    assert session.mode == "subscription" and session.client_reference_id == org_id and session.metadata["source"] == "customer_launch"
    items = sc.v1.checkout.sessions.line_items.list(res["session_id"]).data
    assert sorted((i.price.lookup_key, i.quantity) for i in items) == [("pilot_seat_monthly", 1), ("pilot_store_monthly", 1)]
    assert sum(i.amount_total for i in items) == 45000
    stripe_customer = sc.v1.customers.retrieve(c["stripe_customer_id"])
    assert stripe_customer.metadata["organization_id"] == org_id and stripe_customer.email == customer["body"]["contact_email"]
    # second call reuses the open session instead of minting another
    status, again = super_admin.post(f"/api/customers/{org_id}/payment-link", {"send": False})
    assert status == 200 and again["session_id"] == res["session_id"]
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "payment_link_created"}) == 1


def test_billing_routes_are_super_admin_only(customer, rep, store_manager, org_admin):
    org_id = customer["organization_id"]
    for who in (rep, store_manager, org_admin):
        assert who.post(f"/api/customers/{org_id}/payment-link", {"send": False})[0] == 403
        assert who.post(f"/api/customers/{org_id}/sync-billing")[0] == 403
        assert who.post(f"/api/customers/{org_id}/portal-link")[0] == 403
        assert who.post(f"/api/customers/{org_id}/cancel", {"cancel": True})[0] == 403
    assert anon("POST", f"/api/customers/{org_id}/payment-link", {"send": False})[0] == 401


def test_checkout_confirm_is_anonymous_but_trusts_only_stripe(customer, mongo):
    org_id = customer["organization_id"]
    c = _cust(mongo, org_id)
    assert anon("POST", "/api/billing/checkout/confirm", {"session_id": "nonsense"})[0] == 400
    assert anon("POST", "/api/billing/checkout/confirm", {"session_id": "cs_test_doesnotexist"})[0] in (404, 502)
    status, body = anon("POST", "/api/billing/checkout/confirm", {"session_id": c["checkout_session_id"]})
    assert status == 200 and body["payment_status"] == "unpaid" and body["billing_status"] == "awaiting_payment" and body["activated"] is False
    assert set(body) == {"business_name", "payment_status", "billing_status", "plan_name", "activated"}  # no ids, no card data
    assert _cust(mongo, org_id)["billing_status"] == "awaiting_payment"  # an unpaid return changes nothing


# ── B3 webhook route (signature enforcement) ─────────────────────────────────

def test_webhook_rejects_unsigned_and_forged_payloads():
    payload = json.dumps(_event("invoice.payment_failed", {"id": "in_x"})).encode()
    secret = os.environ.get("STRIPE_BILLING_WEBHOOK_SECRET", "")
    if not secret:
        assert _post_raw(WEBHOOK, payload, {})[0] == 503
        assert _post_raw(WEBHOOK, payload, {"Stripe-Signature": "t=1,v1=abc"})[0] == 503
        pytest.skip("STRIPE_BILLING_WEBHOOK_SECRET not set yet: route correctly refuses everything with 503")
    assert _post_raw(WEBHOOK, payload, {})[0] == 400
    assert _post_raw(WEBHOOK, payload, {"Stripe-Signature": "t=1,v1=deadbeef"})[0] == 400
    ts = int(time.time())
    good = stripe.WebhookSignature._compute_signature(f"{ts}.{payload.decode()}", secret)
    stale = stripe.WebhookSignature._compute_signature(f"{ts - 3600}.{payload.decode()}", secret)
    assert _post_raw(WEBHOOK, payload, {"Stripe-Signature": f"t={ts - 3600},v1={stale}"})[0] == 400  # outside tolerance
    status, body = _post_raw(WEBHOOK, payload, {"Stripe-Signature": f"t={ts},v1={good}"})
    assert status == 200 and body["received"] is True and body.get("result") == "no_customer"  # signed but unrelated invoice: acknowledged, ignored


# ── B4 paid subscription -> activation -> owner access ───────────────────────

def test_completed_subscription_marks_customer_paid(customer, super_admin, mongo, sc):
    org_id = customer["organization_id"]
    c = _cust(mongo, org_id)
    prices = {k: v["price_id"] for k, v in billing.ensure_catalog_sync(sc).items()}
    sc.v1.customers.update(c["stripe_customer_id"], {"source": "tok_visa"})
    sub = sc.v1.subscriptions.create({"customer": c["stripe_customer_id"], "items": [{"price": prices["pilot_store_monthly"]}, {"price": prices["pilot_seat_monthly"], "quantity": 1}],
                                      "metadata": {"organization_id": org_id, "source": "customer_launch", "plan_key": "pilot_store_monthly"}})
    assert sub.status == "active"
    event = _event("customer.subscription.created", json.loads(json.dumps(sub)))
    res = run(billing.handle_event(adb(), event))
    assert res["result"] == "active" and res["organization_id"] == org_id
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "active" and c["subscription_status"] == "active" and c["stripe_subscription_id"] == sub.id
    assert c["onboarding_status"] == "paid" and c["paid_at"] and c["current_period_end"] and c["seat_item_id"] and c["base_item_id"]
    assert c["seats_extra"] == 1 and c["grace_until"] is None
    # same event again: acknowledged, nothing rewritten
    assert run(billing.handle_event(adb(), event)) == {"received": True, "duplicate": True}
    assert mongo.stripe_events.count_documents({"_id": event["id"]}) == 1
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "subscription_active"}) == 1
    # pull-sync agrees with Stripe
    status, body = super_admin.post(f"/api/customers/{org_id}/sync-billing")
    assert status == 200 and body["billing_status"] == "active" and body["customer"]["customer"]["billing_status"] == "active"
    # unknown event types are acknowledged and ignored
    assert run(billing.handle_event(adb(), _event("charge.refunded", {"id": "ch_x"})))["ignored"] is True
    # live delivery: with the endpoint registered, Stripe itself must have posted the real events for this subscription
    if os.environ.get("STRIPE_BILLING_WEBHOOK_SECRET"):
        for _ in range(30):
            live = {e["type"] for e in mongo.stripe_events.find({"_id": {"$regex": "^evt_1"}, "organization_id": org_id, "processed": True})}
            if {"customer.subscription.created", "invoice.paid"} <= live:
                break
            time.sleep(1)
        assert {"customer.subscription.created", "invoice.paid"} <= live, live
        assert _cust(mongo, org_id)["last_payment_amount"] == 450.0  # written by Stripe's own invoice.paid, not by this test
        assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "subscription_active"}) == 1  # replayed by the live event: still one write


def test_paid_customer_can_be_activated_and_owner_sees_billing(customer, super_admin, mongo, store_manager, rep):
    org_id = customer["organization_id"]
    assert super_admin.post(f"/api/customers/{org_id}/activate")[0] == 200
    assert mongo.organizations.find_one({"_id": oid(org_id)})["active"] is True
    assert super_admin.post(f"/api/customers/{org_id}/invite-owner")[0] == 200
    tok = mongo.password_reset_tokens.find_one({"user_id": customer["user_id"], "purpose": "activate_link", "used": False})
    status, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    assert status == 200, swap
    assert anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": OWNER_PASSWORD})[0] == 200
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    status, me = owner.get("/api/billing/me")
    assert status == 200, me
    assert me["plan_name"] == "Pilot Store" and me["monthly_total"] == 450.0 and me["billing_status"] == "active" and me["portal_available"] is True
    assert me["checkout_url"] is None and not any(k.startswith("stripe_") for k in me) and "card" not in json.dumps(me).lower()
    status, portal = owner.post("/api/billing/portal")
    assert status == 200 and portal["url"].startswith("https://billing.stripe.com/"), portal
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "portal_opened"}) == 1
    # legacy manager: no launch customer record -> told billing is handled for them; rep: no role; anonymous: 401
    assert store_manager.get("/api/billing/me")[0] == 404
    assert rep.get("/api/billing/me")[0] == 403
    assert anon("GET", "/api/billing/me")[0] == 401
    status, link = super_admin.post(f"/api/customers/{org_id}/portal-link")
    assert status == 200 and link["url"].startswith("https://billing.stripe.com/")


# ── B5 failed payment -> grace, recovery ─────────────────────────────────────

def test_failed_payment_keeps_access_and_tells_founder(customer, mongo):
    org_id = customer["organization_id"]
    c = _cust(mongo, org_id)
    inv = {"id": "in_test_fail", "object": "invoice", "customer": c["stripe_customer_id"], "amount_due": 45000, "amount_paid": 0,
           "parent": {"subscription_details": {"subscription": c["stripe_subscription_id"]}}, "billing_reason": "subscription_cycle"}
    res = run(billing.handle_event(adb(), _event("invoice.payment_failed", inv)))
    assert res["result"] == "past_due"
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "past_due" and c["failed_attempts"] == 1
    grace_days = (datetime.fromisoformat(c["grace_until"]) - datetime.now(timezone.utc)).days
    assert 13 <= grace_days <= 14
    assert mongo.organizations.find_one({"_id": oid(org_id)})["active"] is True  # no automatic suspension
    assert mongo.users.find_one({"_id": oid(customer["user_id"])})["is_active"] is True
    note = mongo.notifications.find_one({"type": "customer_payment_failed", "link": f"/admin/customers/{org_id}"})
    assert note and note["user_id"] == c["created_by"] and "$450.00" in note["message"]
    # a second failure keeps the original grace date
    run(billing.handle_event(adb(), _event("invoice.payment_failed", {**inv, "id": "in_test_fail2"})))
    c2 = _cust(mongo, org_id)
    assert c2["grace_until"] == c["grace_until"] and c2["failed_attempts"] == 2
    # the retry succeeds
    paid = {**inv, "id": "in_test_paid", "amount_paid": 45000, "status_transitions": {"paid_at": int(time.time())}}
    assert run(billing.handle_event(adb(), _event("invoice.paid", paid)))["result"] == "paid"
    c3 = _cust(mongo, org_id)
    assert c3["billing_status"] == "active" and c3["grace_until"] is None and c3["failed_attempts"] == 0 and c3["last_payment_amount"] == 450.0
    assert mongo.notifications.count_documents({"type": "customer_payment_recovered", "link": f"/admin/customers/{org_id}"}) == 1
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "payment_failed"}) == 2
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "payment_succeeded"}) >= 1  # + Stripe's own invoice.paid when live


# ── B6 seats stay in step with Stripe ─────────────────────────────────────────

def test_seat_changes_sync_to_stripe_and_limits_follow(customer, super_admin, mongo, sc):
    org_id = customer["organization_id"]
    c = _cust(mongo, org_id)
    status, body = super_admin.patch(f"/api/customers/{org_id}", {"seats_extra": 3})
    assert status == 200 and body["seats"]["extra"] == 3 and body["seats"]["limit"] == 8
    sub = sc.v1.subscriptions.retrieve(c["stripe_subscription_id"])
    seat = next(i for i in sub["items"]["data"] if i.price.lookup_key == "pilot_seat_monthly")
    assert seat.quantity == 3 and seat.id == c["seat_item_id"]
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "seats_synced_to_stripe"}) == 1
    # Stripe-side change (portal / dashboard) flows back through the webhook writer
    sc.v1.subscription_items.update(seat.id, {"quantity": 2, "proration_behavior": "none"})
    sub = sc.v1.subscriptions.retrieve(c["stripe_subscription_id"])
    run(billing.handle_event(adb(), _event("customer.subscription.updated", json.loads(json.dumps(sub)))))
    c = _cust(mongo, org_id)
    assert c["seats_extra"] == 2
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "seats_synced_from_stripe"}) == 1
    # back to zero removes the seat item entirely
    status, body = super_admin.patch(f"/api/customers/{org_id}", {"seats_extra": 0})
    assert status == 200 and body["seats"]["extra"] == 0
    sub = sc.v1.subscriptions.retrieve(c["stripe_subscription_id"])
    assert [i.price.lookup_key for i in sub["items"]["data"]] == ["pilot_store_monthly"]
    assert _cust(mongo, org_id)["seat_item_id"] is None
    # plan swap on a live subscription is refused (Stripe is the place to do that)
    assert super_admin.patch(f"/api/customers/{org_id}", {"plan_key": "pilot_individual_monthly"})[0] == 409
    # seat guard still applies: 1 owner in use, 5 included -> a 6th person is refused
    def rep_body():
        s = secrets.token_hex(3)
        return {"first_name": "Seat", "last_name": f"Pilot{s}", "email": f"qa-pilot-billing-seat-{s}@invalid.imonsocial.test", "phone": _phone(),
                "role": "user", "store_id": customer["store_id"], "organization_id": org_id, "send_invite": False, "send_sms": False}
    for _ in range(4):
        status, body = super_admin.post("/api/admin/users/create", rep_body())
        assert status == 200, body
    status, body = super_admin.post("/api/admin/users/create", rep_body())
    assert status == 400 and "seat" in str(body).lower()


# ── B7 cancel, resume, end, restart ──────────────────────────────────────────

def test_cancel_resume_and_restart(customer, super_admin, mongo, sc):
    org_id = customer["organization_id"]
    c = _cust(mongo, org_id)
    status, body = super_admin.post(f"/api/customers/{org_id}/cancel", {"cancel": True})
    assert status == 200 and body["cancel_at_period_end"] is True
    assert sc.v1.subscriptions.retrieve(c["stripe_subscription_id"]).cancel_at_period_end is True
    assert _cust(mongo, org_id)["cancel_at_period_end"] is True and _cust(mongo, org_id)["billing_status"] == "active"
    status, body = super_admin.post(f"/api/customers/{org_id}/cancel", {"cancel": False})
    assert status == 200 and body["cancel_at_period_end"] is False
    assert sc.v1.subscriptions.retrieve(c["stripe_subscription_id"]).cancel_at_period_end is False
    # the subscription ends (portal or dashboard): status canceled, access untouched, founder told, new link allowed
    ended = sc.v1.subscriptions.cancel(c["stripe_subscription_id"])
    assert ended.status == "canceled"
    run(billing.handle_event(adb(), _event("customer.subscription.deleted", json.loads(json.dumps(ended)))))
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "canceled" and c["canceled_at"]
    assert mongo.organizations.find_one({"_id": oid(org_id)})["active"] is True
    assert mongo.notifications.count_documents({"type": "customer_subscription_canceled", "link": f"/admin/customers/{org_id}"}) == 1
    assert super_admin.post(f"/api/customers/{org_id}/cancel", {"cancel": True})[0] == 409
    status, res = super_admin.post(f"/api/customers/{org_id}/payment-link", {"send": False})
    assert status == 200 and res["session_id"] != c["checkout_session_id"]
    assert _cust(mongo, org_id)["billing_status"] == "awaiting_payment"
    # a sync while the new link is out keeps "awaiting"; a late event for the OLD subscription is ignored as stale
    assert super_admin.post(f"/api/customers/{org_id}/sync-billing")[1]["billing_status"] == "awaiting_payment"
    assert run(billing.handle_event(adb(), _event("customer.subscription.deleted", json.loads(json.dumps(ended)))))["result"] == "awaiting_payment"
    assert _cust(mongo, org_id)["billing_status"] == "awaiting_payment"
    # exception path from Stage 1 still works alongside Stripe
    ends = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%Y-%m-%d")
    assert super_admin.post(f"/api/customers/{org_id}/billing-exception", {"reason": "pilot courtesy month", "expires_at": ends})[0] == 200
    assert _cust(mongo, org_id)["billing_status"] == "exception"


# ── B8 legacy flows untouched ─────────────────────────────────────────────────

def test_legacy_stripe_surfaces_unchanged():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ms = open(os.path.join(root, "routers", "mystery_shops.py")).read()
    srv = open(os.path.join(root, "server.py")).read()
    assert "STRIPE_BILLING" not in ms and "STRIPE_WEBHOOK_SECRET" in ms and "/stripe/webhook" in ms
    assert "/webhook/stripe" in srv and "STRIPE_BILLING" not in srv
    assert not (stripe.api_key or "").startswith("rk_")  # the billing client never leaks into the module global
