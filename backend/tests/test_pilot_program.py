"""Founding Partner Pilot acceptance tests against the live preview API + Mongo + the owner's Stripe TEST sandbox.
Creates "QA FP Pilot *" customers and removes them (incl. any Stripe test customer) at the end.
Covers: pilot creation without any Stripe object, clock starts at owner activation and never resets, founder row fields
(days left / potential vs actual MRR / engagement), reminders once per milestone per channel (30/60/75/90), no automatic
conversion at expiry, extend / end / resume with audit, API-wide access block of an ended pilot, early conversion with a
Stripe trial that first invoices the day the pilot ends (verified live with trial_end=now), guards for roles / legacy / paid."""
import asyncio
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest

from services import billing, pilot_program
from tests._http import API, UA
from tests.live_auth import ORG_B, Session, anon, oid
from tests.wipe_pilot_customers import wipe
from tests import qa_creds

PREFIX = "QA FP Pilot"
OWNER_PASSWORD = qa_creds.password_for("qa-pilot-owner-ui@invalid.imonsocial.test")
PAID_ORG = "6acbea92a284f605698a9743"  # QA Accept Motors: paid through Stripe (founder acceptance run)

loop = asyncio.new_event_loop()


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


def _phone():
    return f"+1500555{secrets.randbelow(9000) + 1000}"


def _cust(mongo, org_id):
    return mongo.organizations.find_one({"_id": oid(org_id)})["customer"]


def _event(typ, obj):
    return {"id": f"evt_test_{secrets.token_hex(8)}", "object": "event", "type": typ, "livemode": False, "created": int(time.time()), "data": {"object": obj}}


def _backdate(mongo, org_id, days_ago: int):
    started = datetime.now(timezone.utc) - timedelta(days=days_ago)
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.pilot_program.started_at": started.isoformat(), "customer.pilot_program.ends_at": (started + timedelta(days=90)).isoformat()}})


@pytest.fixture(scope="module")
def customer(super_admin, mongo):
    suffix = secrets.token_hex(3)
    body = {
        "business_name": f"{PREFIX} Motors {suffix}", "city": "Lehi", "state": "UT", "zip": "84043", "industry": "Automotive / Dealership",
        "contact_name": f"Fran Founding{suffix}", "contact_email": f"qa-fp-owner-{suffix}@invalid.imonsocial.test", "contact_phone": _phone(),
        "plan_key": "pilot_store_monthly", "seats_extra": 1, "pilot": True, "billing_mode": "founding_pilot",
    }
    status, res = super_admin.post("/api/setup-wizard/new-account", body)
    assert status == 200, res
    yield {**res, "body": body}
    wipe(mongo, PREFIX, dry_run=False)


# ── 1. creation: pilot, no Stripe, no card ───────────────────────────────────

def test_founding_pilot_customer_is_created_without_stripe(customer, mongo, super_admin):
    org_id = customer["organization_id"]
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "pilot" and c["pilot_program"]["state"] == "pending" and c["pilot_program"]["days"] == 90
    assert c["pilot_program"]["started_at"] is None and c["pilot_program"]["ends_at"] is None and c["pilot_program"]["reminders_sent"] == []
    assert "stripe_customer_id" not in c and "stripe_subscription_id" not in c and "checkout_url" not in c
    assert c["amount"] == 375.0 and c["seat_price"] == 75.0 and c["seats_extra"] == 1  # agreed pricing recorded up front
    actions = [a["action"] for a in mongo.customer_audit_log.find({"organization_id": org_id})]
    assert actions.count("customer_created") == 1 and actions.count("pilot_granted") == 1
    status, row = super_admin.get(f"/api/customers/{org_id}")
    assert status == 200
    assert row["pilot_program"]["state"] == "pending" and row["pilot_program"]["days_left"] is None
    assert row["mrr"] == {"amount": 450.0, "kind": "potential", "first_charge_on": None}
    assert row["engagement"]["people"]["total"] == 1 and row["engagement"]["contacts"]["total"] == 0
    # the owner is still dormant: Stage 1 contract intact
    owner = mongo.users.find_one({"_id": oid(customer["user_id"])})
    assert owner["is_active"] is False and owner["dormant"] is True


def test_paid_from_day_one_still_creates_an_unpaid_customer(super_admin, org_admin, mongo):
    body = {"business_name": f"{PREFIX} Paid {secrets.token_hex(2)}", "contact_name": "Pay Upfront", "contact_phone": _phone(), "plan_key": "pilot_individual_monthly", "billing_mode": "paid"}
    status, res = super_admin.post("/api/setup-wizard/new-account", body)
    assert status == 200, res
    c = _cust(mongo, res["organization_id"])
    assert c["billing_status"] == "unpaid" and "pilot_program" not in c
    assert super_admin.post("/api/setup-wizard/new-account", {**body, "business_name": f"{PREFIX} Bad mode", "billing_mode": "free_forever"})[0] == 400
    # omitting billing_mode keeps the Stage 1 contract (unpaid); only a super admin may grant the complimentary pilot
    status, res3 = super_admin.post("/api/setup-wizard/new-account", {**{k: v for k, v in body.items() if k != "billing_mode"}, "business_name": f"{PREFIX} Default {secrets.token_hex(2)}"})
    assert status == 200 and _cust(mongo, res3["organization_id"])["billing_status"] == "unpaid"
    assert org_admin.post("/api/setup-wizard/new-account", {**body, "business_name": f"{PREFIX} Partner", "billing_mode": "founding_pilot"})[0] == 403
    # an unpaid customer can be moved onto the pilot from the customer page
    status, res2 = super_admin.post(f"/api/customers/{res['organization_id']}/pilot/start")
    assert status == 200 and res2["pilot_program"]["state"] == "pending"
    assert _cust(mongo, res["organization_id"])["billing_status"] == "pilot"
    assert super_admin.post(f"/api/customers/{res['organization_id']}/pilot/start")[0] == 409  # already on the pilot


# ── 2. clock starts at owner activation, never resets ────────────────────────

def test_activate_without_payment_then_owner_activation_starts_the_clock(customer, super_admin, mongo):
    org_id = customer["organization_id"]
    status, body = super_admin.post(f"/api/customers/{org_id}/activate")
    assert status == 200 and body.get("activated") is True, body  # no payment, no exception needed
    assert _cust(mongo, org_id)["pilot_program"]["state"] == "pending"  # founder activation does NOT start the clock
    assert super_admin.post(f"/api/customers/{org_id}/invite-owner")[0] == 200
    tok = mongo.password_reset_tokens.find_one({"user_id": customer["user_id"], "purpose": "activate_link", "used": False})
    status, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    assert status == 200, swap
    status, done = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": OWNER_PASSWORD})
    assert status == 200, done
    for _ in range(20):
        p = _cust(mongo, org_id)["pilot_program"]
        if p.get("state") == "active":
            break
        time.sleep(0.5)
    assert p["state"] == "active" and p["started_at"] and p["ends_at"]
    started, ends = datetime.fromisoformat(p["started_at"]), datetime.fromisoformat(p["ends_at"])
    assert abs((ends - started).days - 90) == 0 and abs((datetime.now(timezone.utc) - started).total_seconds()) < 120
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_started"}) == 1
    note = mongo.notifications.find_one({"user_id": super_admin.user_id, "type": "customer_owner_activated", "link": f"/admin/customers/{org_id}"})
    assert note and "90-day" in (note.get("message") or note.get("body") or json.dumps(note))

    # later sign-ins and session refreshes never move the clock
    email = customer["body"]["contact_email"]
    for _ in range(2):
        status, me = anon("POST", "/api/auth/login", {"email": email, "password": OWNER_PASSWORD})
        assert status == 200
        assert me["user"]["pilot"] is True and me["user"]["pilot_billing_status"] == "pilot"
        assert me["user"]["pilot_program"]["state"] == "active" and me["user"]["pilot_program"]["days_left"] in (89, 90)
    owner = Session(email, OWNER_PASSWORD)
    assert owner.get("/api/billing/me")[0] == 200
    p2 = _cust(mongo, org_id)["pilot_program"]
    assert p2["started_at"] == p["started_at"] and p2["ends_at"] == p["ends_at"]
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_started"}) == 1


def test_founder_hub_row_and_owner_billing_view(customer, super_admin, mongo):
    org_id = customer["organization_id"]
    status, rows = super_admin.get("/api/customers")
    row = next(r for r in rows if r["organization_id"] == org_id)
    assert row["pilot_program"]["state"] == "active" and row["pilot_program"]["days_left"] in (89, 90) and row["pilot_program"]["day"] == 1
    assert row["mrr"]["kind"] == "potential" and row["mrr"]["amount"] == 450.0
    assert row["attention"] == []  # 90 days out: nothing to flag
    assert set(row["engagement"]) == {"contacts", "shares", "memos", "texts", "people"}
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    status, me = owner.get("/api/billing/me")
    assert status == 200 and me["billing_status"] == "pilot" and me["pilot"]["state"] == "active" and me["pilot"]["can_continue"] is True
    assert me["monthly_total"] == 450.0 and me["checkout_url"] is None and me["portal_available"] is False
    assert me["pilot"]["first_charge_on"][:10] == me["pilot"]["ends_at"][:10]


# ── 3. reminders: once per milestone, per channel ─────────────────────────────

def test_reminders_fire_once_per_milestone_and_expiry_never_converts(customer, super_admin, store_manager, mongo):
    org_id = customer["organization_id"]
    # route the founder channel to the QA manager (@invalid address): push + Alert + email are recorded, nobody real is mailed
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.created_by": store_manager.user_id}})
    expected = []
    for days_ago, milestone in ((31, 30), (61, 60), (76, 75), (91, 90)):
        _backdate(mongo, org_id, days_ago)
        res = run(pilot_program.tick(adb()))
        mine = [s for s in res["sent"] if s["organization_id"] == org_id]
        assert [s["milestone"] for s in mine] == [milestone], res
        assert mine[0]["push_alert"] is True
        expected.append(milestone)
        again = run(pilot_program.tick(adb()))
        assert not [s for s in again["sent"] if s["organization_id"] == org_id]  # nothing repeats
        assert mongo.notifications.count_documents({"user_id": store_manager.user_id, "type": f"customer_pilot_day_{milestone}", "link": f"/admin/customers/{org_id}"}) == 1
    p = _cust(mongo, org_id)["pilot_program"]
    assert p["reminders_sent"] == [30, 60, 75, 90] and len(p["reminder_log"]) == 4
    assert all(e["push_alert"] is True and "email" in e for e in p["reminder_log"])
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_reminder_sent"}) == 4
    # day 91: the pilot is completed, access is on, nothing was charged, nothing exists in Stripe
    assert p["state"] == "completed" and mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_completed"}) == 1
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "pilot" and "stripe_customer_id" not in c and "stripe_subscription_id" not in c
    assert billing.client().v1.customers.list({"email": customer["body"]["contact_email"]}).data == []
    status, row = super_admin.get(f"/api/customers/{org_id}")
    assert row["pilot_program"]["state"] == "completed" and row["pilot_program"]["days_left"] == 0
    assert any(a.startswith("Pilot period over") for a in row["attention"]), row["attention"]
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    status, me = owner.get("/api/billing/me")
    assert status == 200 and me["pilot"]["state"] == "completed" and me["pilot"]["can_continue"] is True  # access continues
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.created_by": super_admin.user_id}})


def test_cron_route_is_secret_protected_and_idempotent():
    secret = os.environ.get("WEBHOOK_CRON_SECRET")
    assert anon("POST", "/api/cron/pilot-reminders", {})[0] == 401
    if not secret:
        pytest.skip("WEBHOOK_CRON_SECRET not set in this environment")
    import urllib.request
    rid = f"qa-{secrets.token_hex(4)}"

    def hit():
        req = urllib.request.Request(API + "/api/cron/pilot-reminders", method="POST", data=b"{}", headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}", "X-Webhook-Id": rid, **UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    first, second = hit(), hit()
    assert first.get("accepted") is True and second.get("duplicate") is True


# ── 4. extend / end / resume with audit; ended pilot blocks every API call ───

def test_extend_end_and_resume_are_audited_and_block_access(customer, super_admin, mongo):
    org_id = customer["organization_id"]
    email = customer["body"]["contact_email"]
    assert super_admin.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "no"})[0] == 400
    status, ext = super_admin.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "Owner asked for a month to decide"})
    assert status == 200, ext
    p = _cust(mongo, org_id)["pilot_program"]
    assert p["state"] == "active" and 29 <= (datetime.fromisoformat(p["ends_at"]) - datetime.now(timezone.utc)).days <= 30
    assert p["extensions"][0]["days"] == 30 and p["extensions"][0]["ends_at_after"] == p["ends_at"]
    assert mongo.customer_audit_log.find_one({"organization_id": org_id, "action": "pilot_extended", "details.days": 30})
    assert p["reminders_sent"] == [30, 60, 75, 90]  # extension never re-sends milestones

    owner = Session(email, OWNER_PASSWORD)
    contacts_before = mongo.contacts.count_documents({"user_id": customer["user_id"]})
    assert owner.get("/api/billing/me")[0] == 200
    assert super_admin.post(f"/api/customers/{org_id}/pilot/end", {"reason": "QA: ending the pilot"})[0] == 200
    org = mongo.organizations.find_one({"_id": oid(org_id)})
    assert org["active"] is False and org["customer"]["pilot_program"]["state"] == "ended" and org["customer"]["pilot_program"]["ended_reason"] == "QA: ending the pilot"
    assert mongo.users.count_documents({"organization_id": org_id, "access_blocked.reason": "pilot_ended"}) == mongo.users.count_documents({"organization_id": org_id}) >= 1
    # the existing session is dead on every authenticated route, not only at sign-in
    for path in ("/api/billing/me", f"/api/contacts/{customer['user_id']}", "/api/pilot/checklist", "/api/notifications-center/unread-count"):
        status, body = owner.get(path)
        assert status == 401, (path, status, body)
    status, body = anon("POST", "/api/auth/login", {"email": email, "password": OWNER_PASSWORD})
    assert status == 403 and "has ended" in str(body)
    # data untouched
    assert mongo.contacts.count_documents({"user_id": customer["user_id"]}) == contacts_before
    assert mongo.users.count_documents({"organization_id": org_id}) >= 1 and mongo.stores.count_documents({"organization_id": org_id}) == 1
    status, row = super_admin.get(f"/api/customers/{org_id}")
    assert row["pilot_program"]["state"] == "ended" and row["mrr"]["kind"] == "none" and any(a.startswith("Pilot ended") for a in row["attention"])
    assert super_admin.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "cannot extend an ended pilot"})[0] == 409
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_ended"}) == 1

    # founder-controlled reactivation
    assert super_admin.post(f"/api/customers/{org_id}/pilot/resume", {"reason": "QA: owner called back"})[0] == 200
    org = mongo.organizations.find_one({"_id": oid(org_id)})
    assert org["active"] is True and org["customer"]["pilot_program"]["state"] == "active"
    assert mongo.users.count_documents({"organization_id": org_id, "access_blocked": {"$exists": True}}) == 0
    status, me = anon("POST", "/api/auth/login", {"email": email, "password": OWNER_PASSWORD})
    assert status == 200 and me["user"]["pilot_program"]["state"] == "active"
    assert Session(email, OWNER_PASSWORD).get("/api/billing/me")[0] == 200
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_resumed"}) == 1


# ── 5. early conversion: card saved now, first invoice the day the pilot ends ─

def test_owner_continue_creates_checkout_with_trial_until_pilot_end(customer, mongo, rep, store_manager):
    org_id = customer["organization_id"]
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    status, res = owner.post("/api/billing/checkout")
    assert status == 200, res
    assert res["url"].startswith("https://checkout.stripe.com/") and res["first_charge_on"]
    p = _cust(mongo, org_id)["pilot_program"]
    assert res["first_charge_on"][:10] == p["ends_at"][:10]
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "pilot" and c["checkout_session_id"] == res["session_id"] and c.get("stripe_customer_id")  # still a pilot until Stripe confirms
    assert mongo.customer_audit_log.find_one({"organization_id": org_id, "action": "owner_checkout_opened"})
    status, again = owner.post("/api/billing/checkout")
    assert status == 200 and again["session_id"] == res["session_id"]  # open session reused
    status, me = owner.get("/api/billing/me")
    assert me["checkout_url"] is None and me["pilot"]["can_continue"] is True  # the owner authorizes through the terms screen, never a bare link
    assert rep.post("/api/billing/checkout")[0] == 403          # not a store manager
    assert store_manager.post("/api/billing/checkout")[0] == 404  # legacy store: billing handled by the representative


def test_trial_subscription_converts_the_pilot_and_first_invoices_at_trial_end(customer, mongo, super_admin):
    org_id = customer["organization_id"]
    sc = billing.client()
    c = _cust(mongo, org_id)
    prices = {k: v["price_id"] for k, v in billing.ensure_catalog_sync(sc).items()}
    trial_end = int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp())
    sc.v1.customers.update(c["stripe_customer_id"], {"source": "tok_visa"})
    sub = sc.v1.subscriptions.create({"customer": c["stripe_customer_id"], "trial_end": trial_end,
                                      "items": [{"price": prices["pilot_store_monthly"]}, {"price": prices["pilot_seat_monthly"], "quantity": 1}],
                                      "metadata": {"organization_id": org_id, "source": "customer_launch", "plan_key": "pilot_store_monthly", "pilot_conversion": "1"}})
    assert sub.status == "trialing" and sub.trial_end == trial_end
    # Stripe's $0 trial invoice is not a payment
    inv = sc.v1.invoices.list({"subscription": sub.id, "limit": 1}).data[0]
    assert inv.amount_paid == 0 and inv.status == "paid"
    res = run(billing.handle_event(adb(), _event("invoice.paid", json.loads(json.dumps(inv)))))
    assert res["result"] == "trial_invoice"
    res = run(billing.handle_event(adb(), _event("customer.subscription.created", json.loads(json.dumps(sub)))))
    assert res["result"] == "trialing"
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "trialing" and c["stripe_subscription_id"] == sub.id and c.get("last_payment_amount") is None and c.get("paid_at") is None
    assert c["pilot_program"]["state"] == "converted" and c["pilot_program"]["converted_at"]
    assert c["current_period_end"][:10] == datetime.fromtimestamp(trial_end, tz=timezone.utc).isoformat()[:10]
    assert mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_converted"}) == 1
    assert mongo.notifications.find_one({"user_id": super_admin.user_id, "type": "customer_pilot_converted", "link": f"/admin/customers/{org_id}"})
    status, row = super_admin.get(f"/api/customers/{org_id}")
    assert row["mrr"]["kind"] == "scheduled" and row["mrr"]["amount"] == 450.0 and row["mrr"]["first_charge_on"] == c["current_period_end"]
    assert row["pilot_program"]["state"] == "converted"
    # a converted customer is billing, not a pilot: extend / end no longer apply
    assert super_admin.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "already converted"})[0] == 409
    assert super_admin.post(f"/api/customers/{org_id}/pilot/end", {"reason": "already converted"})[0] == 409

    # the trial ends (Stripe does this on the pilot end date; here forced with trial_end=now): first invoice is created and charged
    sub2 = sc.v1.subscriptions.update(sub.id, {"trial_end": "now"})
    for _ in range(20):
        sub2 = sc.v1.subscriptions.retrieve(sub.id)
        if sub2.status == "active":
            break
        time.sleep(1)
    assert sub2.status == "active"
    paid = [i for i in sc.v1.invoices.list({"subscription": sub.id, "limit": 5}).data if i.amount_paid > 0]
    assert paid and paid[0].amount_paid == 45000 and paid[0].status == "paid"
    run(billing.handle_event(adb(), _event("customer.subscription.updated", json.loads(json.dumps(sub2)))))
    run(billing.handle_event(adb(), _event("invoice.paid", json.loads(json.dumps(paid[0])))))
    c = _cust(mongo, org_id)
    assert c["billing_status"] == "active" and c["last_payment_amount"] == 450.0 and c["paid_at"]
    status, row = super_admin.get(f"/api/customers/{org_id}")
    assert row["mrr"] == {"amount": 450.0, "kind": "actual", "first_charge_on": None}
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    status, me = owner.get("/api/billing/me")
    assert me["billing_status"] == "active" and me["portal_available"] is True and me["pilot"]["state"] == "converted" and me["pilot"]["can_continue"] is False


# ── 6. guards ─────────────────────────────────────────────────────────────────

def test_pilot_routes_are_super_admin_only_and_never_touch_legacy_or_paid(customer, rep, store_manager, org_admin, super_admin):
    org_id = customer["organization_id"]
    for who in (rep, store_manager, org_admin):
        assert who.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "not allowed"})[0] == 403
        assert who.post(f"/api/customers/{org_id}/pilot/end", {"reason": "not allowed"})[0] == 403
    assert super_admin.post(f"/api/customers/{ORG_B}/pilot/start")[0] == 404   # legacy org: not a customer
    assert super_admin.post(f"/api/customers/{PAID_ORG}/pilot/start")[0] == 409  # paying customer stays paying
    assert super_admin.post(f"/api/customers/{PAID_ORG}/pilot/end", {"reason": "paying customers are not pilots"})[0] == 409
