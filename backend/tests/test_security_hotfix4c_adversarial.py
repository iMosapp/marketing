"""Security hotfix 4C adversarial probes - targeting bypasses that the main test file may miss.

Focus: X-User-ID spoof headers, extra/weird body fields (role as list/object, extra account_id/is_owner/status),
nonexistent store IDs, mismatched store+org, cross-dealership pending-user approval of ACTIVE users,
custom template cross-org, /hierarchy/users/{user_id}/role bypass, PUT /api/admin/users/{id} role elevation,
POST /api/setup-wizard/new-account, routers/webhooks.py user-created role clamp (admin-only).

No invite emails/SMS trigger; .test TLD rejected by EmailStr; cleanup every doc we create."""
import secrets
from datetime import datetime

import pytest
from bson import ObjectId

from tests._http import call
from tests.live_auth import ORG_B, STORE_A, STORE_B, Session, anon, ensure_qa_user

QA_ORG_A = "org_001"
ZERO = "0" * 24
SEEDED = ("templates", "campaigns", "email_templates", "date_trigger_configs",
          "lead_sources", "review_response_templates", "social_templates", "tags", "activity")


@pytest.fixture(scope="module")
def victim(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix3-victim@invalid.imonsocial.test", "user", QA_ORG_A, STORE_A, "QA Hotfix Victim")
    return Session(email, pw)


@pytest.fixture(scope="module")
def org_a_admin(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix4-orgadmin@invalid.imonsocial.test", "org_admin", QA_ORG_A, STORE_A, "QA Hotfix4 Org Admin")
    return Session(email, pw)


def _email(tag):
    return f"qa-hotfix4c-adv-{tag}-{secrets.token_hex(3)}@invalid.imonsocial.test"


def _purge(mongo, email):
    doc = mongo.users.find_one({"email": email}, {"_id": 1})
    if not doc:
        return
    uid = str(doc["_id"])
    for coll in SEEDED:
        mongo[coll].delete_many({"user_id": uid})
    mongo.contacts.delete_many({"email": email, "source": "user_creation"})
    mongo.users.delete_one({"_id": doc["_id"]})


# ───────────────────────────── X-User-ID spoof probes ──────────────────────────────────────────
def test_x_user_id_header_spoof_does_not_grant_super_admin(store_manager, super_admin, mongo):
    """Store manager puts super_admin's _id in X-User-ID while posting a super_admin role creation.
    Expectation: identity comes from JWT only; the request is refused and nothing is written."""
    spoofed = {**store_manager.headers, "X-User-ID": super_admin.user_id}
    for route in ("/api/admin/users", "/api/admin/users/create"):
        email = _email("spoof")
        body = {"email": email, "password": "x", "name": "Spoof", "first_name": "S", "last_name": "P",
                "phone": "", "role": "super_admin", "store_id": STORE_A, "send_invite": False, "send_sms": False}
        st, resp = call("POST", route, body, spoofed)
        assert st in (401, 403), (route, st, resp)
        assert mongo.users.find_one({"email": email}) is None, (route, resp)


# ───────────────────────────── weird body shapes ───────────────────────────────────────────────
def test_role_as_list_or_object_is_rejected(store_manager, mongo):
    for bad_role in (["super_admin"], {"name": "super_admin"}, "owner", "SUPER_ADMIN"):
        email = _email("badrole")
        body = {"email": email, "password": "x", "name": "Repro", "first_name": "R", "last_name": "A",
                "phone": "", "role": bad_role, "store_id": STORE_A, "send_invite": False, "send_sms": False}
        st, resp = store_manager.post("/api/admin/users", body)
        # Must not create a user. 400/403/422 are all refusals.
        assert st in (400, 403, 422), (bad_role, st, resp)
        assert mongo.users.find_one({"email": email}) is None


def test_organization_id_as_list_or_object_is_rejected(store_manager, mongo):
    for bad_org in ([ORG_B], {"$ne": None}, ORG_B):
        email = _email("badorg")
        body = {"email": email, "password": "x", "name": "Repro", "first_name": "R", "last_name": "A",
                "phone": "", "role": "user", "store_id": STORE_A, "organization_id": bad_org,
                "send_invite": False, "send_sms": False}
        st, resp = store_manager.post("/api/admin/users", body)
        assert st in (400, 403, 422), (bad_org, st, resp)
        assert mongo.users.find_one({"email": email}) is None


def test_mismatched_store_and_org_rejected(org_a_admin, mongo):
    """store_id STORE_A but organization_id ORG_B — the store must belong to the stated org."""
    email = _email("mismatch")
    body = {"email": email, "password": "x", "name": "Repro", "first_name": "R", "last_name": "A",
            "phone": "", "role": "user", "store_id": STORE_A, "organization_id": ORG_B,
            "send_invite": False, "send_sms": False}
    st, resp = org_a_admin.post("/api/admin/users", body)
    assert st in (400, 403), (st, resp)
    assert mongo.users.find_one({"email": email}) is None


def test_extra_body_fields_are_ignored_not_trusted(store_manager, super_admin, mongo):
    """Even if the request succeeds, extra escalation-flavored body fields (account_id, partner_id, is_owner, status)
    must not grant anything the caller doesn't already have. We assert on the stored document."""
    email = _email("extras")
    body = {"email": email, "password": "pw", "name": "Repro", "first_name": "R", "last_name": "A",
            "phone": "", "role": "user", "store_id": STORE_A, "send_invite": False, "send_sms": False,
            "account_id": super_admin.user_id, "partner_id": "deadbeef", "is_owner": True, "status": "owner"}
    st, resp = store_manager.post("/api/admin/users/create", body)
    try:
        if st == 200:
            doc = mongo.users.find_one({"email": email})
            assert doc is not None
            # account_id must inherit from the creator (store_manager's own account_id or _id), not from the body
            assert doc.get("account_id") != super_admin.user_id, doc
            # role must stay 'user'
            assert doc.get("role") == "user", doc
        else:
            assert st in (400, 403, 422), (st, resp)
    finally:
        _purge(mongo, email)


# ───────────────────────────── pending-user edge cases ────────────────────────────────────────
def test_approving_an_active_user_via_pending_route_refused(org_admin, mongo):
    """FINDING: PUT /api/admin/pending-users/{id}/approve lacks a status=='pending' filter in its mongo lookup
    (_pending_scope only filters by organization_id), so an org admin can mutate an ACTIVE user's role through the
    approve route — not a privilege-ceiling escalation (role is bounded by assert_placement), but a route-scope bug:
    /approve must only act on status=='pending' documents (the sibling /reject already does this). Fixed in 4C."""
    email = _email("active")
    r = mongo.users.insert_one({"email": email, "name": "QA Active", "role": "user", "status": "active",
                                "is_active": True, "organization_id": ORG_B, "store_id": STORE_B,
                                "password": "x", "created_at": datetime.utcnow()})
    pid = str(r.inserted_id)
    try:
        st, resp = org_admin.put(f"/api/admin/pending-users/{pid}/approve", {"role": "store_manager", "store_id": STORE_B})
        doc = mongo.users.find_one({"_id": r.inserted_id})
        # Fixed in 4C: the approve route only acts on status=='pending' documents (404 otherwise, role untouched).
        assert st == 404, (st, resp)
        assert doc["role"] == "user", doc
    finally:
        mongo.users.delete_one({"_id": r.inserted_id})


def test_pending_users_list_hides_other_orgs_applicants(org_a_admin, org_admin, mongo):
    """Insert pending in ORG_B — org_001 admin must NOT see it, and the count must be scoped."""
    email = _email("hide")
    r = mongo.users.insert_one({"email": email, "name": "QA Hide", "role": "user", "status": "pending",
                                "is_active": True, "organization_id": ORG_B, "store_id": STORE_B,
                                "password": "x", "created_at": datetime.utcnow()})
    pid = str(r.inserted_id)
    try:
        st, lst = org_a_admin.get("/api/admin/pending-users")
        assert st == 200
        assert pid not in {u["_id"] for u in lst}, "cross-org applicant leaked to org_a_admin"
        st, lst = org_admin.get("/api/admin/pending-users")
        assert st == 200 and pid in {u["_id"] for u in lst}
    finally:
        mongo.users.delete_one({"_id": r.inserted_id})


# ───────────────────────────── permission templates: cross-org custom template ────────────────
def test_cross_org_custom_template_cannot_be_applied(org_a_admin, victim, mongo):
    """Create a custom template owned by ORG_B directly in mongo; org_001 admin tries to apply it to a STORE_A rep.
    Must be refused (404 — the handler scopes template lookup by org)."""
    tpl = mongo.permission_templates.insert_one({
        "name": "QA 4c cross-org tpl", "role": "store_manager", "feature_permissions": {},
        "org_id": ORG_B, "organization_id": ORG_B, "created_at": datetime.utcnow(),
    })
    tid = str(tpl.inserted_id)
    before_role = (mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1}) or {}).get("role")
    try:
        st, resp = org_a_admin.post(f"/api/permission-templates/{tid}/apply/{victim.user_id}", {})
        assert st in (403, 404), (st, resp)
        now = (mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1}) or {}).get("role")
        assert now == before_role, (before_role, now)
    finally:
        mongo.permission_templates.delete_one({"_id": tpl.inserted_id})


def test_store_manager_cannot_create_custom_template_with_privileged_role_then_apply(store_manager, mongo):
    """A store manager must not be able to create a template whose role >= their own and then apply it."""
    for role in ("super_admin", "org_admin", "store_manager"):
        st, resp = store_manager.post("/api/permission-templates/", {"name": f"QA 4c adv {role}", "role": role, "feature_permissions": {}})
        assert st in (400, 403), (role, st, resp)
        assert mongo.permission_templates.find_one({"name": f"QA 4c adv {role}"}) is None


def test_update_template_role_to_privileged_rejected(store_manager, mongo):
    """Create a benign template (role=user) as super admin (via direct mongo insert owned by caller's org),
    then store_manager tries PUT to change role to org_admin. Must be refused and role unchanged."""
    tpl = mongo.permission_templates.insert_one({
        "name": "QA 4c upd probe", "role": "user", "feature_permissions": {},
        "org_id": QA_ORG_A, "organization_id": QA_ORG_A,
        "created_by": store_manager.user_id, "created_at": datetime.utcnow(),
    })
    tid = str(tpl.inserted_id)
    try:
        st, resp = store_manager.put(f"/api/permission-templates/{tid}", {"name": "QA 4c upd probe", "role": "org_admin"})
        assert st in (400, 403, 404), (st, resp)
        doc = mongo.permission_templates.find_one({"_id": tpl.inserted_id})
        assert doc["role"] == "user", doc
    finally:
        mongo.permission_templates.delete_one({"_id": tpl.inserted_id})


# ───────────────────────────── other role-mutating routes ─────────────────────────────────────
def test_hierarchy_role_endpoint_rejects_privileged_grant(store_manager, victim, mongo):
    """PUT /api/admin/hierarchy/users/{id}/role — store manager must not grant org_admin/super_admin/store_manager."""
    before = (mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1}) or {}).get("role")
    for role in ("super_admin", "org_admin", "store_manager"):
        st, resp = store_manager.put(f"/api/admin/hierarchy/users/{victim.user_id}/role", {"role": role})
        assert st in (400, 403, 404), (role, st, resp)
        now = (mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1}) or {}).get("role")
        assert now == before, (role, before, now)


def test_hierarchy_role_endpoint_rejects_cross_org_target(org_a_admin, mongo):
    """Org_001 admin tries to change role of a user that belongs to ORG_B. Must be refused."""
    # Create a disposable target in ORG_B directly in mongo
    email = _email("cross-target")
    r = mongo.users.insert_one({"email": email, "name": "QA X", "role": "user", "status": "active",
                                "is_active": True, "organization_id": ORG_B, "store_id": STORE_B,
                                "password": "x", "created_at": datetime.utcnow()})
    tid = str(r.inserted_id)
    try:
        st, resp = org_a_admin.put(f"/api/admin/hierarchy/users/{tid}/role", {"role": "store_manager"})
        assert st in (400, 403, 404), (st, resp)
        doc = mongo.users.find_one({"_id": r.inserted_id})
        assert doc["role"] == "user", doc
    finally:
        mongo.users.delete_one({"_id": r.inserted_id})


def test_admin_users_put_cannot_elevate_role(store_manager, victim, mongo):
    """PUT /api/admin/users/{id} is a role-mutating path. Store manager must not elevate the victim's role."""
    before = (mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1}) or {}).get("role")
    for role in ("super_admin", "org_admin", "store_manager"):
        st, resp = store_manager.put(f"/api/admin/users/{victim.user_id}", {"role": role})
        assert st in (400, 403, 404), (role, st, resp)
        now = (mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1}) or {}).get("role")
        assert now == before, (role, before, now)


def test_setup_wizard_new_account_requires_super_admin(store_manager, org_a_admin, victim, rep):
    """POST /api/setup-wizard/new-account mints a store_manager; must be super-admin-only.
    Accept 422 as refusal (body validation runs after auth-dep in FastAPI only sometimes; we only care
    that no low-rank caller gets 200 or minted a user)."""
    body = {"account_name": "QA 4c adv", "business_name": "QA 4c adv", "owner_email": _email("acct"),
            "owner_name": "X Y", "store_name": "Store QA",
            "subdomain": f"qa-4c-adv-{secrets.token_hex(2)}"}
    for who in (store_manager, org_a_admin, victim, rep):
        st, resp = who.post("/api/setup-wizard/new-account", body)
        assert st in (400, 401, 403, 404, 422), (who.email, st, resp)
        assert "owner_email" not in str(resp) or "created" not in str(resp).lower()
    assert anon("POST", "/api/setup-wizard/new-account", body)[0] in (401, 403, 404, 422)


# ───────────────────────────── operator surface regression ────────────────────────────────────
def test_webhook_enforcement_health_scoped_and_no_key_leak(victim, super_admin):
    assert anon("GET", "/api/health/webhook-enforcement")[0] == 401
    assert victim.get("/api/health/webhook-enforcement")[0] == 403
    st, body = super_admin.get("/api/health/webhook-enforcement")
    assert st == 200
    import json as _json
    blob = _json.dumps(body)
    assert "webhook_key" not in blob and '"api_key"' not in blob
