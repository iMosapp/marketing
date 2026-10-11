"""Stage 1 acceptance tests: founder customer launch workflow against the live preview API.
Covers creation (dormant owner, no credentials in responses), role boundaries, tenant isolation, activation security
(dormant guard + single-use expiring link), billing exception rules, seat limits on every creation path, legacy orgs untouched."""
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest

from tests.live_auth import ORG_B, STORE_A, STORE_B, Session, anon, oid
from tests.wipe_pilot_customers import wipe

PREFIX = "QA Pilot Co"
OWNER_PASSWORD = "PilotOwner123!"


def _phone():
    return f"+1500555{secrets.randbelow(9000) + 1000}"


@pytest.fixture(scope="module")
def baseline(mongo):
    legacy_orgs = mongo.organizations.count_documents({"customer": {"$exists": False}})
    manager_perms = mongo.users.find_one({"email": "qa-manager@invalid.imonsocial.test"}, {"feature_permissions": 1}).get("feature_permissions")
    return {"legacy_orgs": legacy_orgs, "manager_perms": manager_perms}


@pytest.fixture(scope="module")
def customer(super_admin, mongo, baseline):
    suffix = secrets.token_hex(3)
    body = {
        "business_name": f"{PREFIX} Co {suffix}", "city": "Sandy", "state": "UT", "zip": "84070", "industry": "Automotive / Dealership",
        "contact_name": f"Pat Pilot{suffix}", "contact_email": f"qa-pilot-owner-{suffix}@invalid.imonsocial.test", "contact_phone": _phone(),
        "plan_key": "pilot_store_monthly", "seats_extra": 0, "pilot": True,
    }
    status, res = super_admin.post("/api/setup-wizard/new-account", body)
    assert status == 200, res
    yield {**res, "body": body}
    wipe(mongo, PREFIX, dry_run=False)


# ── A1 creation ───────────────────────────────────────────────────────────────

def test_creation_is_dormant_and_returns_no_credentials(customer, mongo):
    assert "temp_password" not in customer and "password" not in str(customer).lower().replace("passwordless", "")
    org = mongo.organizations.find_one({"_id": oid(customer["organization_id"])})
    c = org["customer"]
    assert org["active"] is False
    assert c["pilot"] is True and c["plan_key"] == "pilot_store_monthly" and c["seats_included"] == 5 and c["seats_extra"] == 0
    assert c["billing_status"] == "unpaid" and c["onboarding_status"] == "created" and c["owner_user_id"] == customer["user_id"]
    owner = mongo.users.find_one({"_id": oid(customer["user_id"])})
    assert owner["is_active"] is False and owner["dormant"] is True and owner["activation_pending"] is True
    assert owner["role"] == "store_manager" and owner["organization_id"] == customer["organization_id"]
    assert owner["feature_permissions"]["campaigns"]["_enabled"] is False
    assert owner["feature_permissions"]["manage"]["_enabled"] is False
    assert owner["feature_permissions"]["admin"]["invite_team"] is True
    assert mongo.stores.count_documents({"organization_id": customer["organization_id"]}) == 1
    assert mongo.customer_audit_log.count_documents({"organization_id": customer["organization_id"], "action": "customer_created"}) == 1


def test_dormant_owner_cannot_sign_in_or_request_activation(customer):
    email, phone = customer["body"]["contact_email"], customer["body"]["contact_phone"]
    assert anon("POST", "/api/auth/login", {"email": email, "password": OWNER_PASSWORD})[0] == 401
    status, body = anon("POST", "/api/auth/activate/request", {"phone": phone})
    assert status == 403 and "not been activated" in str(body)
    assert anon("POST", "/api/auth/forgot-password/request", {"email": email})[0] in (403, 404)


def test_unknown_plan_and_bad_seats_are_refused(super_admin):
    base = {"business_name": f"{PREFIX} Bad", "contact_name": "x", "contact_phone": _phone()}
    assert super_admin.post("/api/setup-wizard/new-account", {**base, "plan_key": "enterprise"})[0] == 400
    assert super_admin.post("/api/setup-wizard/new-account", {**base, "plan_key": "pilot_individual_monthly", "seats_extra": 2})[0] == 400


# ── A2 roles + tenant isolation ───────────────────────────────────────────────

def test_roles_cannot_reach_customer_routes(customer, rep, store_manager, org_admin):
    oid_ = customer["organization_id"]
    for who in (rep, store_manager):
        assert who.get("/api/customers")[0] == 403
        assert who.get("/api/customers/plans")[0] == 403
        assert who.post("/api/setup-wizard/new-account", {"business_name": "x", "contact_name": "x", "contact_phone": _phone()})[0] == 403
    # qa-orgadmin sits in a PARTNER org: may list customers (scoped to the partner's orgs) but never another tenant's row
    status, rows = org_admin.get("/api/customers")
    assert status == 200 and oid_ not in {r["organization_id"] for r in rows}
    for who in (rep, store_manager, org_admin):
        assert who.get(f"/api/customers/{oid_}")[0] == 403
        assert who.post(f"/api/customers/{oid_}/activate")[0] == 403
        assert who.post(f"/api/customers/{oid_}/invite-owner")[0] == 403
        assert who.post(f"/api/customers/{oid_}/billing-exception", {"reason": "because I said so", "expires_at": "2030-01-01"})[0] == 403
        assert who.patch(f"/api/customers/{oid_}", {"notes": "x"})[0] == 403
    for method, path in (("GET", "/api/customers"), ("GET", f"/api/customers/{oid_}"), ("POST", f"/api/customers/{oid_}/activate"), ("POST", f"/api/customers/{oid_}/invite-owner"), ("PATCH", f"/api/customers/{oid_}")):
        assert anon(method, path, {} if method != "GET" else None)[0] == 401, (method, path)


def test_legacy_org_is_not_a_customer(super_admin):
    assert super_admin.get(f"/api/customers/{ORG_B}")[0] == 404
    status, rows = super_admin.get("/api/customers")
    assert status == 200 and ORG_B not in {r["organization_id"] for r in rows}
    assert super_admin.post(f"/api/customers/{ORG_B}/activate")[0] == 404


# ── A3 billing exception + activation order ──────────────────────────────────

def test_activate_and_invite_refused_before_payment_or_exception(customer, super_admin):
    oid_ = customer["organization_id"]
    status, body = super_admin.post(f"/api/customers/{oid_}/activate")
    assert status == 409 and "exception" in str(body)
    status, body = super_admin.post(f"/api/customers/{oid_}/invite-owner")
    assert status == 409 and "Activate" in str(body)


def test_exception_requires_reason_and_valid_expiry(customer, super_admin):
    oid_ = customer["organization_id"]
    far = (datetime.now(timezone.utc) + timedelta(days=400)).strftime("%Y-%m-%d")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    ok = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    assert super_admin.post(f"/api/customers/{oid_}/billing-exception", {"reason": "abc", "expires_at": ok})[0] == 400
    assert super_admin.post(f"/api/customers/{oid_}/billing-exception", {"reason": "paid by check #1041", "expires_at": past})[0] == 400
    assert super_admin.post(f"/api/customers/{oid_}/billing-exception", {"reason": "paid by check #1041", "expires_at": far})[0] == 400
    assert super_admin.post(f"/api/customers/{oid_}/billing-exception", {"reason": "paid by check #1041"})[0] == 422


def test_exception_then_activate_is_audited_and_never_a_payment(customer, super_admin, mongo):
    oid_ = customer["organization_id"]
    ok = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    status, body = super_admin.post(f"/api/customers/{oid_}/billing-exception", {"reason": "Pilot courtesy, paid by check #1041", "expires_at": ok})
    assert status == 200, body
    c = mongo.organizations.find_one({"_id": oid(oid_)})["customer"]
    assert c["billing_status"] == "exception" and c["billing_exception"]["reason"].startswith("Pilot courtesy")
    assert c["billing_exception"]["granted_by"] == super_admin.user_id and "stripe" not in str(c).lower()

    status, body = super_admin.post(f"/api/customers/{oid_}/activate")
    assert status == 200 and body.get("activated") is True, body
    org = mongo.organizations.find_one({"_id": oid(oid_)})
    assert org["active"] is True and org["customer"]["onboarding_status"] == "activated" and org["customer"]["activated_by"] == super_admin.user_id
    owner = mongo.users.find_one({"_id": oid(customer["user_id"])})
    assert owner["is_active"] is True and "dormant" not in owner and owner["activation_pending"] is True
    actions = [a["action"] for a in mongo.customer_audit_log.find({"organization_id": oid_})]
    assert "billing_exception_granted" in actions and "account_activated" in actions
    assert super_admin.post(f"/api/customers/{oid_}/activate")[1].get("already_active") is True

    status, row = super_admin.get(f"/api/customers/{oid_}")
    assert status == 200 and row["customer"]["billing_status"] == "exception" and row["owner"]["dormant"] is False
    assert "password" not in str(row).lower()


# ── A4 invitation + activation security ──────────────────────────────────────

def test_invite_mints_single_use_expiring_link_and_resend_supersedes(customer, super_admin, mongo):
    oid_ = customer["organization_id"]
    status, body = super_admin.post(f"/api/customers/{oid_}/invite-owner")
    assert status == 200 and set(body) >= {"sms_sent", "email_sent", "expires_at"}, body
    tok = mongo.password_reset_tokens.find_one({"user_id": customer["user_id"], "purpose": "activate_link", "used": False})
    assert tok and tok["source"] == "customer_launch"
    assert 71 * 3600 < tok["expires_at"] - tok["created_at"] <= 72 * 3600
    c = mongo.organizations.find_one({"_id": oid(oid_)})["customer"]
    assert c["onboarding_status"] == "owner_invited" and c["invite_count"] == 1

    assert super_admin.post(f"/api/customers/{oid_}/invite-owner")[0] == 200
    assert mongo.password_reset_tokens.find_one({"_id": tok["_id"]})["used"] is True
    assert mongo.password_reset_tokens.count_documents({"user_id": customer["user_id"], "purpose": "activate_link", "used": False}) == 1
    assert anon("POST", "/api/auth/activate/link", {"token": tok["token"]})[0] == 400  # superseded link is dead


def test_owner_activates_through_link_and_founder_is_told(customer, super_admin, mongo):
    oid_ = customer["organization_id"]
    tok = mongo.password_reset_tokens.find_one({"user_id": customer["user_id"], "purpose": "activate_link", "used": False})
    status, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    assert status == 200 and swap.get("code") and swap.get("identifier"), swap
    status, done = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": OWNER_PASSWORD})
    assert status == 200, done
    assert anon("POST", "/api/auth/activate/link", {"token": tok["token"]})[0] == 400  # single use

    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    status, me = anon("POST", "/api/auth/login", {"email": customer["body"]["contact_email"], "password": OWNER_PASSWORD})
    assert status == 200 and me["user"]["role"] == "store_manager"
    assert me["user"]["feature_permissions"]["campaigns"]["_enabled"] is False
    assert me["user"]["feature_permissions"]["admin"]["invite_team"] is True

    for _ in range(10):
        c = mongo.organizations.find_one({"_id": oid(oid_)})["customer"]
        if c.get("owner_activated_at"):
            break
        time.sleep(0.5)
    assert c["onboarding_status"] == "owner_active" and c.get("owner_activated_at")
    assert mongo.notifications.find_one({"user_id": super_admin.user_id, "type": "customer_owner_activated", "link": f"/admin/customers/{oid_}"})
    assert mongo.customer_audit_log.count_documents({"organization_id": oid_, "action": "owner_activated"}) == 1
    status, body = super_admin.post(f"/api/customers/{oid_}/invite-owner")
    assert status == 409  # nothing left to invite


def test_owner_cannot_see_other_tenants(customer):
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    assert owner.get("/api/customers")[0] == 403
    assert owner.get(f"/api/team-invite/store/{STORE_A}")[0] == 403
    assert owner.get(f"/api/team-invite/store/{STORE_B}")[0] == 403
    assert owner.get(f"/api/onboarding-settings/store/{STORE_A}")[0] == 403
    assert owner.get(f"/api/setup-wizard/progress/{ORG_B}")[0] == 403
    assert owner.get("/api/setup-wizard/clients")[0] == 403
    assert owner.get(f"/api/team-invite/store/{customer['store_id']}")[0] == 200


# ── A5 seat limits on every creation path ────────────────────────────────────

def _rep_body(store_id, org_id):
    s = secrets.token_hex(3)
    return {"first_name": "Rep", "last_name": f"Pilot{s}", "email": f"qa-pilot-rep-{s}@invalid.imonsocial.test", "phone": _phone(),
            "role": "user", "store_id": store_id, "organization_id": org_id, "send_invite": False, "send_sms": False}


def test_seat_limit_blocks_every_creation_path(customer, super_admin, mongo):
    oid_, sid = customer["organization_id"], customer["store_id"]
    owner = Session(customer["body"]["contact_email"], OWNER_PASSWORD)
    now = datetime.now(timezone.utc).isoformat()
    filler = [{"name": f"Filler {i}", "email": f"qa-pilot-filler-{i}-{secrets.token_hex(2)}@invalid.imonsocial.test", "role": "user", "organization_id": oid_,
               "store_id": sid, "store_ids": [sid], "status": "active", "is_active": True, "created_at": now} for i in range(4)]
    mongo.users.insert_many(filler)  # owner + 4 = 5 seats in use
    status, row = super_admin.get(f"/api/customers/{oid_}")
    assert row["seats"] == {"included": 5, "extra": 0, "limit": 5, "used": 5}

    status, body = owner.post("/api/admin/users/create", _rep_body(sid, oid_))
    assert status == 400 and "5 seats" in str(body), body
    status, body = super_admin.post("/api/admin/users/create", _rep_body(sid, oid_))
    assert status == 400, body  # super admins are not exempt; add a seat instead
    status, body = super_admin.post("/api/admin/users", {"email": f"qa-pilot-x-{secrets.token_hex(2)}@invalid.imonsocial.test", "name": "x", "role": "user", "store_id": sid, "organization_id": oid_, "password": "Passw0rd!"})
    assert status == 400, body
    status, body = owner.post("/api/setup-wizard/bulk-invite", {"store_id": sid, "members": [{"name": "Bulk", "email": f"qa-pilot-bulk-{secrets.token_hex(2)}@example.com"}]})  # EmailStr rejects .test
    assert status == 200 and body["created"] == 0 and "seat" in body["results"][0]["reason"], body
    status, inv = owner.post("/api/team-invite/create", {"store_id": sid})
    assert status == 200, inv
    status, body = anon("POST", "/api/team-invite/join", {"invite_code": inv["invite_code"], "name": "Joiner", "phone": _phone()[2:], "email": f"qa-pilot-join-{secrets.token_hex(2)}@invalid.imonsocial.test"})
    assert status == 400 and "seat" in str(body), body
    assert mongo.users.count_documents({"organization_id": oid_}) == 5

    status, body = super_admin.patch(f"/api/customers/{oid_}", {"seats_extra": 1})
    assert status == 200 and body["seats"]["limit"] == 6, body
    status, body = owner.post("/api/admin/users/create", _rep_body(sid, oid_))
    assert status == 200, body
    assert "temp_password" in body  # legacy team-member flow unchanged for existing customers
    assert mongo.users.count_documents({"organization_id": oid_}) == 6
    status, body = anon("POST", "/api/team-invite/join", {"invite_code": inv["invite_code"], "name": "Joiner", "phone": _phone()[2:], "email": f"qa-pilot-join-{secrets.token_hex(2)}@invalid.imonsocial.test"})
    assert status == 400
    assert super_admin.patch(f"/api/customers/{oid_}", {"seats_extra": 0})[0] == 400  # cannot shrink below use
    mongo.team_invites.delete_many({"store_id": sid})


def test_legacy_org_creation_is_never_limited(super_admin, mongo):
    body = _rep_body(STORE_B, ORG_B)
    status, res = super_admin.post("/api/admin/users/create", body)
    try:
        assert status == 200, res
    finally:
        mongo.users.delete_one({"email": body["email"]})
        mongo.contacts.delete_many({"email": body["email"], "source": "user_creation"})
        for coll in ("templates", "email_templates", "campaigns", "date_trigger_configs", "tags", "review_response_templates", "social_templates"):
            mongo[coll].delete_many({"user_id": res.get("user_id", "none")}) if isinstance(res, dict) else None


# ── A6 legacy data untouched ──────────────────────────────────────────────────

def test_legacy_orgs_and_manager_permissions_untouched(mongo, baseline, customer):
    assert mongo.organizations.count_documents({"customer": {"$exists": False}}) == baseline["legacy_orgs"]
    assert mongo.users.find_one({"email": "qa-manager@invalid.imonsocial.test"}, {"feature_permissions": 1}).get("feature_permissions") == baseline["manager_perms"]
    assert mongo.organizations.count_documents({"_id": oid(ORG_B), "customer": {"$exists": True}}) == 0
