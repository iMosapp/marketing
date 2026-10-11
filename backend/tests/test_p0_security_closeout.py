"""P0 security close-out regression: authentication, authorization, cross-tenant isolation,
invitation creation and the legitimate public onboarding flows. Runs against the live preview API."""
import secrets

import pytest

from tests.live_auth import ORG_B, STORE_A, STORE_B, anon, oid

FOREST = "69a0b7095fddcede09591667"
ZERO = "000000000000000000000000"

SECURED = [
    ("GET", "/api/setup-wizard/clients"),
    ("POST", "/api/setup-wizard/clients"),
    ("GET", f"/api/setup-wizard/progress/{ORG_B}"),
    ("POST", f"/api/setup-wizard/progress/{ORG_B}"),
    ("POST", f"/api/setup-wizard/complete/{ORG_B}"),
    ("POST", "/api/setup-wizard/bulk-invite"),
    ("POST", "/api/setup-wizard/new-account"),
    ("POST", "/api/team-invite/create"),
    ("GET", f"/api/team-invite/store/{STORE_A}"),
    ("DELETE", f"/api/team-invite/{ZERO}"),
    ("GET", f"/api/team-invite/user/{FOREST}/invite-link"),
    ("POST", "/api/team-invite/share-via-sms"),
    ("GET", f"/api/team-invite/shares/{FOREST}"),
    ("GET", f"/api/team-invite/analytics/store/{STORE_A}"),
    ("POST", "/api/team-invite/send-email-invite"),
    ("GET", f"/api/onboarding-settings/store/{STORE_A}"),
    ("PUT", f"/api/onboarding-settings/store/{STORE_A}"),
    ("GET", f"/api/onboarding-settings/organization/{ORG_B}"),
    ("GET", "/api/onboarding-settings/global"),
    ("PUT", "/api/onboarding-settings/global"),
    ("POST", "/api/onboarding-settings/preview-message"),
    ("GET", "/api/onboarding-settings/placeholders"),
    ("GET", "/api/scheduler/status"),
    ("POST", "/api/scheduler/trigger/date-triggers"),
    ("POST", f"/api/email/send?user_id={FOREST}"),
    ("GET", f"/api/email/templates/{FOREST}"),
    ("POST", f"/api/email/templates/{FOREST}"),
    ("GET", f"/api/email/campaigns/{FOREST}"),
    ("GET", f"/api/email/brand-kit/user/{FOREST}"),
    ("GET", f"/api/email/brand-kit/store/{STORE_A}"),
    ("GET", f"/api/email/preferences/{FOREST}"),
    ("GET", f"/api/email/logs/{FOREST}"),
    ("GET", f"/api/email/analytics/{FOREST}"),
    ("GET", "/api/subscriptions/my-subscription?email=someone@example.com"),
    ("GET", "/api/subscriptions/cancellation-status?email=someone@example.com"),
    ("POST", "/api/subscriptions/cancel"),
    ("GET", "/api/subscriptions/quotes"),
    ("POST", "/api/subscriptions/quotes"),
    ("GET", f"/api/subscriptions/quotes/{ZERO}"),
    ("GET", "/api/subscriptions/discount-codes"),
    ("POST", "/api/subscriptions/discount-codes"),
    ("GET", "/api/subscriptions/partner/accounts?partner_id=x"),
]

PUBLIC = [
    ("GET", "/api/team-invite/validate/zzzzzzzz", 404),
    ("GET", "/api/team-invite/validate-email/zzzzzzzz", 404),
    ("POST", "/api/team-invite/join", 404),
    ("POST", "/api/team-invite/accept", 404),
    ("GET", "/api/subscriptions/plans", 200),
    ("GET", "/api/subscriptions/discount-codes/validate/NOPE", 200),
]


@pytest.mark.parametrize("method,path", SECURED)
def test_unauthenticated_is_rejected(method, path):
    status, _ = anon(method, path, {} if method in ("POST", "PUT") else None)
    assert status == 401, (method, path, status)


@pytest.mark.parametrize("method,path,expected", PUBLIC)
def test_public_token_flows_stay_public(method, path, expected):
    body = {"invite_code": "zzzzzzzz", "name": "x", "phone": "5005550001", "email": "nobody@example.com", "password": "Passw0rd!"} if method == "POST" else None
    status, _ = anon(method, path, body)
    assert status == expected, (method, path, status)


# ── role boundaries ────────────────────────────────────────────────────────────

def test_rep_cannot_reach_admin_surfaces(rep):
    assert rep.get("/api/setup-wizard/clients")[0] == 403
    assert rep.get("/api/scheduler/status")[0] == 403
    assert rep.get("/api/onboarding-settings/global")[0] == 403
    assert rep.get(f"/api/onboarding-settings/store/{STORE_A}")[0] == 403
    assert rep.get(f"/api/team-invite/store/{STORE_A}")[0] == 403
    assert rep.post("/api/team-invite/create", {"store_id": STORE_A})[0] == 403
    assert rep.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": []})[0] == 403
    assert rep.post("/api/setup-wizard/new-account", {"business_name": "x", "contact_name": "x", "contact_phone": "5005550002"})[0] == 403
    assert rep.get("/api/subscriptions/quotes")[0] == 403
    assert rep.get("/api/subscriptions/discount-codes")[0] == 403
    assert rep.get("/api/subscriptions/partner/accounts?partner_id=x")[0] == 403


def test_rep_sees_only_their_own_records(rep, store_manager):
    assert rep.get(f"/api/email/templates/{rep.user_id}")[0] == 200
    assert rep.get(f"/api/email/templates/{store_manager.user_id}")[0] == 403
    assert rep.get(f"/api/email/templates/{FOREST}")[0] == 403
    assert rep.get(f"/api/email/brand-kit/user/{rep.user_id}")[0] == 200
    assert rep.get(f"/api/email/brand-kit/user/{FOREST}")[0] == 403
    assert rep.get(f"/api/email/brand-kit/store/{STORE_A}")[0] == 403
    assert rep.get(f"/api/email/preferences/{FOREST}")[0] == 403
    assert rep.get(f"/api/team-invite/shares/{FOREST}")[0] == 403
    status, _ = rep.get(f"/api/team-invite/user/{rep.user_id}/invite-link")
    assert status in (200, 400)  # own link (400 = not assigned to a store), never 401/403
    assert rep.get(f"/api/team-invite/user/{FOREST}/invite-link")[0] == 403
    assert rep.get(f"/api/subscriptions/my-subscription?email={rep.email}")[0] == 200
    assert rep.get("/api/subscriptions/my-subscription?email=forest@imosapp.com")[0] == 403
    assert rep.get("/api/subscriptions/cancellation-status?email=forest@imosapp.com")[0] == 403
    assert rep.post("/api/subscriptions/cancel", {"email": "forest@imosapp.com"})[0] == 403


def test_store_manager_is_scoped_to_their_store(store_manager):
    assert store_manager.get(f"/api/team-invite/store/{STORE_A}")[0] == 200
    assert store_manager.get(f"/api/team-invite/store/{STORE_B}")[0] == 403
    assert store_manager.get(f"/api/team-invite/analytics/store/{STORE_A}")[0] == 200
    assert store_manager.get(f"/api/team-invite/analytics/store/{STORE_B}")[0] == 403
    assert store_manager.get(f"/api/onboarding-settings/store/{STORE_A}")[0] == 200
    assert store_manager.get(f"/api/onboarding-settings/store/{STORE_B}")[0] == 403
    assert store_manager.get(f"/api/onboarding-settings/organization/{ORG_B}")[0] == 403
    assert store_manager.get("/api/onboarding-settings/global")[0] == 403
    assert store_manager.get("/api/onboarding-settings/placeholders")[0] == 200
    assert store_manager.post("/api/onboarding-settings/preview-message", {"template": "Hi {user_name}"})[0] == 200
    assert store_manager.get(f"/api/email/brand-kit/store/{STORE_A}")[0] == 200
    assert store_manager.get(f"/api/email/brand-kit/store/{STORE_B}")[0] == 403
    assert store_manager.get("/api/setup-wizard/clients")[0] == 403
    assert store_manager.get(f"/api/setup-wizard/progress/{ORG_B}")[0] == 403
    assert store_manager.post("/api/team-invite/create", {"store_id": STORE_B})[0] == 403
    assert store_manager.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_B, "members": []})[0] == 403
    assert store_manager.get("/api/scheduler/status")[0] == 403
    assert store_manager.post("/api/setup-wizard/new-account", {"business_name": "x", "contact_name": "x", "contact_phone": "5005550003"})[0] == 403


def test_org_admin_is_scoped_to_their_org(org_admin):
    assert org_admin.get(f"/api/setup-wizard/progress/{ORG_B}")[0] == 200
    assert org_admin.get("/api/setup-wizard/progress/org_001")[0] == 403          # store A's org
    assert org_admin.get(f"/api/onboarding-settings/organization/{ORG_B}")[0] == 200
    assert org_admin.get("/api/onboarding-settings/organization/org_001")[0] == 403
    assert org_admin.get(f"/api/team-invite/store/{STORE_B}")[0] == 200
    assert org_admin.get(f"/api/team-invite/store/{STORE_A}")[0] == 403
    assert org_admin.get(f"/api/email/brand-kit/organization/{ORG_B}")[0] == 200
    assert org_admin.get("/api/email/brand-kit/organization/org_001")[0] == 404  # not an ObjectId, hidden
    assert org_admin.get("/api/setup-wizard/clients")[0] == 403
    assert org_admin.get("/api/onboarding-settings/global")[0] == 403
    assert org_admin.get("/api/subscriptions/quotes")[0] == 403
    assert org_admin.get("/api/subscriptions/partner/accounts?partner_id=69a10678b8e991776ed5df19")[0] == 403


def test_super_admin_keeps_full_access(super_admin):
    assert super_admin.get("/api/setup-wizard/clients")[0] == 200
    assert super_admin.get("/api/scheduler/status")[0] == 200
    assert super_admin.get("/api/onboarding-settings/global")[0] == 200
    assert super_admin.get(f"/api/onboarding-settings/store/{STORE_B}")[0] == 200
    assert super_admin.get(f"/api/team-invite/store/{STORE_B}")[0] == 200
    assert super_admin.get(f"/api/email/templates/{FOREST}")[0] == 200
    assert super_admin.get("/api/subscriptions/quotes")[0] == 200
    assert super_admin.get("/api/subscriptions/discount-codes")[0] == 200
    assert super_admin.get("/api/subscriptions/partner/accounts?partner_id=69a10678b8e991776ed5df19")[0] == 200
    assert super_admin.get("/api/subscriptions/my-subscription?email=someone@example.com")[0] == 200


# ── invitation creation + legitimate public onboarding ────────────────────────

def _cleanup_user(mongo, user_id):
    mongo.users.delete_one({"_id": oid(user_id)})


def test_link_invite_is_attributed_to_caller_and_joinable(store_manager, mongo):
    status, inv = store_manager.post("/api/team-invite/create", {"store_id": STORE_A, "created_by": FOREST, "expires_days": 365})
    assert status == 200, inv
    code = inv["invite_code"]
    created_user = None
    try:
        doc = mongo.team_invites.find_one({"invite_code": code})
        assert doc["created_by"] == store_manager.user_id          # body created_by ignored
        assert (doc["expires_at"] - doc["created_at"]).days <= 90   # capped

        status, v = anon("GET", f"/api/team-invite/validate/{code}")
        assert status == 200 and v["valid"] is True and v["store_id"] == STORE_A

        suffix = secrets.token_hex(3)
        status, joined = anon("POST", "/api/team-invite/join", {
            "invite_code": code, "name": f"P0 Join {suffix}", "phone": f"500555{secrets.randbelow(9000) + 1000}",
            "email": f"p0-join-{suffix}@qa.imonsocial.com"})
        assert status == 200, joined
        created_user = joined["user"]["_id"]
        assert joined["user"]["role"] == "user" and joined["user"]["store_id"] == STORE_A
        assert "password" not in joined["user"]

        status, _ = store_manager.delete(f"/api/team-invite/{doc['_id']}")
        assert status == 200
        assert anon("GET", f"/api/team-invite/validate/{code}")[0] == 404  # revoked
    finally:
        if created_user:
            _cleanup_user(mongo, created_user)
        mongo.team_invites.delete_one({"invite_code": code})


def test_other_tenants_cannot_revoke_an_invite(store_manager, org_admin, mongo):
    status, inv = store_manager.post("/api/team-invite/create", {"store_id": STORE_A})
    assert status == 200
    try:
        doc = mongo.team_invites.find_one({"invite_code": inv["invite_code"]})
        assert org_admin.delete(f"/api/team-invite/{doc['_id']}")[0] == 403
        assert mongo.team_invites.find_one({"_id": doc["_id"]})["is_active"] is True
    finally:
        mongo.team_invites.delete_one({"invite_code": inv["invite_code"]})


def test_email_invite_is_bound_to_its_recipient(mongo):
    from datetime import datetime, timedelta
    code = "p0" + secrets.token_hex(5)
    recipient = f"p0-accept-{secrets.token_hex(3)}@qa.imonsocial.com"
    mongo.team_invites.insert_one({
        "invite_code": code, "store_id": STORE_A, "organization_id": "org_001", "created_by": FOREST,
        "created_at": datetime.utcnow(), "expires_at": datetime.utcnow() + timedelta(days=7),
        "is_active": True, "uses_count": 0, "invite_type": "email", "recipient_email": recipient, "recipient_name": "P0 Accept",
    })
    created_user = None
    try:
        wrong = {"invite_code": code, "name": "Someone Else", "email": f"other-{secrets.token_hex(3)}@qa.imonsocial.com", "password": "TestPass123!"}
        assert anon("POST", "/api/team-invite/accept", wrong)[0] == 403

        status, ok = anon("POST", "/api/team-invite/accept", {**wrong, "name": "P0 Accept", "email": recipient})
        assert status == 200, ok
        created_user = ok["user"]["_id"]
        assert mongo.team_invites.find_one({"invite_code": code})["is_active"] is False  # single use
        assert anon("GET", f"/api/team-invite/validate-email/{code}")[0] == 404
    finally:
        if created_user:
            _cleanup_user(mongo, created_user)
        mongo.team_invites.delete_one({"invite_code": code})


def test_bulk_invite_cannot_mint_admins(store_manager, mongo):
    members = [{"name": "P0 Escalation", "email": f"p0-esc-{secrets.token_hex(3)}@qa.imonsocial.com", "role": "super_admin"}]
    status, body = store_manager.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": members})
    assert status == 400, body
    assert mongo.users.find_one({"email": members[0]["email"]}) is None

    ok_members = [{"name": "P0 Rep", "email": f"p0-rep-{secrets.token_hex(3)}@qa.imonsocial.com", "phone": f"500555{secrets.randbelow(9000) + 1000}", "role": "user"}]
    status, body = store_manager.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": ok_members})
    try:
        assert status == 200 and body["created"] == 1, body
        created = mongo.users.find_one({"email": ok_members[0]["email"]}, {"role": 1, "store_id": 1})
        assert created["role"] == "user" and created["store_id"] == STORE_A
    finally:
        mongo.users.delete_one({"email": ok_members[0]["email"]})
