"""Security hotfix 4C: account creation / approval must respect the role hierarchy and organization / store scope.
POST /api/admin/users, POST /api/admin/users/create, PUT /api/admin/pending-users/{id}/approve (+ list/count/reject),
POST /api/admin/users/add-team-member, POST /api/setup-wizard/bulk-invite, permission-template apply/create/update,
POST /api/admin/individuals. Live preview API; anonymous, rep, cross-organization manager and authorized callers.
No invite email / SMS is ever triggered: creation tests pass send_invite/send_sms false or an empty phone."""
import secrets
from datetime import datetime

import pytest
from bson import ObjectId

from tests.live_auth import ORG_B, STORE_A, STORE_B, Session, anon, ensure_qa_user

QA_ORG_A = "org_001"
ZERO = "0" * 24
SEEDED = ("templates", "campaigns", "email_templates", "date_trigger_configs", "lead_sources", "review_response_templates", "social_templates", "tags", "activity")


@pytest.fixture(scope="module")
def victim(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix3-victim@invalid.imonsocial.test", "user", QA_ORG_A, STORE_A, "QA Hotfix Victim")
    return Session(email, pw)


@pytest.fixture(scope="module")
def org_a_admin(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix4-orgadmin@invalid.imonsocial.test", "org_admin", QA_ORG_A, STORE_A, "QA Hotfix4 Org Admin")
    return Session(email, pw)


def _email(tag):
    return f"qa-hotfix4c-{tag}-{secrets.token_hex(3)}@invalid.imonsocial.test"


def _phone():
    """A Twilio test-range number; creation tests always pass send_sms=False so nothing is ever texted."""
    return "+1500555" + f"{secrets.randbelow(10000):04d}"


def _bulk_email(tag):
    """bulk-invite validates EmailStr, which rejects the reserved .test TLD; nothing is ever sent to these."""
    return f"qa-hotfix4c-{tag}-{secrets.token_hex(3)}@hotfix4c-qa.imonsocial.com"


def _purge(mongo, email):
    """Remove an account a test created plus everything seeded for it."""
    doc = mongo.users.find_one({"email": email}, {"_id": 1})
    if not doc:
        return
    uid = str(doc["_id"])
    for coll in SEEDED:
        mongo[coll].delete_many({"user_id": uid})
    mongo.contacts.delete_many({"email": email, "source": "user_creation"})
    mongo.users.delete_one({"_id": doc["_id"]})


def _role(mongo, sid):
    return (mongo.users.find_one({"_id": ObjectId(sid)}, {"role": 1}) or {}).get("role")


# ── the reported hole: role grants on creation ──────────────────────────────────────────────────────────────────────────


def test_store_manager_cannot_create_privileged_accounts(store_manager, mongo):
    """Reproduced before the fix: POST /api/admin/users as a store manager with role=super_admin answered 200 and created a
    super admin (preview, Oct 14 2026). Now every role at or above the caller's own is refused and nothing is written."""
    for route in ("/api/admin/users", "/api/admin/users/create"):
        for role in ("super_admin", "org_admin", "store_manager", "account_manager"):
            email = _email("sm")
            body = {"email": email, "password": "x", "name": "Repro", "first_name": "Repro", "last_name": "Account", "phone": "",
                    "role": role, "store_id": STORE_A, "send_invite": False, "send_sms": False}
            st, resp = store_manager.post(route, body)
            assert st == 403, (route, role, st, resp)
            assert mongo.users.find_one({"email": email}) is None, (route, role)


def test_store_manager_can_only_place_people_into_their_own_store(store_manager, mongo):
    for route in ("/api/admin/users", "/api/admin/users/create"):
        base = {"password": "x", "name": "Repro", "first_name": "Repro", "last_name": "Account", "phone": "", "role": "user",
                "send_invite": False, "send_sms": False}
        for extra, expected in (({"store_id": STORE_B}, 403), ({"store_id": STORE_A, "organization_id": ORG_B}, 403),
                                ({}, 400), ({"store_id": ZERO}, (403, 404))):
            email = _email("sm-scope")
            st, resp = store_manager.post(route, {**base, "email": email, **extra})
            assert st in ((expected,) if isinstance(expected, int) else expected), (route, extra, st, resp)
            assert mongo.users.find_one({"email": email}) is None, (route, extra)


def test_org_admin_role_ceiling_and_organization_isolation(org_a_admin, org_admin, mongo):
    cases = [
        (org_a_admin, {"role": "super_admin", "store_id": STORE_A}),
        (org_a_admin, {"role": "org_admin", "store_id": STORE_A}),
        (org_a_admin, {"role": "user", "organization_id": ORG_B}),             # another dealership
        (org_a_admin, {"role": "user", "store_id": STORE_B}),                  # a store of another dealership
        (org_admin, {"role": "user", "organization_id": QA_ORG_A, "store_id": STORE_A}),  # ORG_B admin into STORE_A
        (org_admin, {"role": "user", "store_id": STORE_A}),
    ]
    for route in ("/api/admin/users", "/api/admin/users/create"):
        for who, extra in cases:
            email = _email("oa")
            st, resp = who.post(route, {"email": email, "password": "x", "name": "Repro", "first_name": "Repro", "last_name": "Account",
                                        "phone": "", "send_invite": False, "send_sms": False, **extra})
            assert st == 403, (route, who.email, extra, st, resp)
            assert mongo.users.find_one({"email": email}) is None


def test_reps_and_anonymous_callers_cannot_create_accounts(victim, rep):
    email = _email("rep")
    body = {"email": email, "password": "x", "name": "Repro", "first_name": "Repro", "last_name": "Account", "phone": "", "role": "user",
            "store_id": STORE_A, "send_invite": False, "send_sms": False}
    for who in (victim, rep):
        assert who.post("/api/admin/users", body)[0] == 403
        assert who.post("/api/admin/users/create", body)[0] == 403
        assert who.post("/api/admin/users/add-team-member", {"name": "x", "email": email, "phone": "", "store_id": STORE_A})[0] == 403
        assert who.post("/api/admin/individuals", {"email": email, "name": "x"})[0] == 403
        assert who.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": [{"name": "x", "email": _bulk_email("rep")}]})[0] == 403
    for method, path in (("POST", "/api/admin/users"), ("POST", "/api/admin/users/create"), ("POST", "/api/admin/users/add-team-member"),
                         ("POST", "/api/admin/individuals"), ("POST", "/api/setup-wizard/bulk-invite"),
                         ("PUT", f"/api/admin/pending-users/{ZERO}/approve"), ("GET", "/api/admin/pending-users")):
        assert anon(method, path, {} if method != "GET" else None)[0] == 401, (method, path)


def test_authorized_creation_keeps_working(super_admin, org_a_admin, store_manager, mongo):
    created = []
    try:
        email = _email("ok-sa")
        st, body = super_admin.post("/api/admin/users", {"email": email, "password": secrets.token_urlsafe(12), "name": "QA 4c Org Admin",
                                                         "role": "org_admin", "organization_id": QA_ORG_A, "store_id": STORE_A})
        created.append(email)
        assert st == 200 and body["role"] == "org_admin" and body["organization_id"] == QA_ORG_A, (st, body)

        email = _email("ok-oa")
        st, body = org_a_admin.post("/api/admin/users/create", {"email": email, "first_name": "QA", "last_name": "Manager", "phone": _phone(),
                                                                "role": "store_manager", "store_id": STORE_A, "send_invite": False, "send_sms": False})
        created.append(email)
        assert st == 200, (st, body)
        doc = mongo.users.find_one({"email": email})
        assert doc["role"] == "store_manager" and doc["organization_id"] == QA_ORG_A and doc["store_id"] == STORE_A

        email = _email("ok-sm")
        st, body = store_manager.post("/api/admin/users/create", {"email": email, "first_name": "QA", "last_name": "Rep", "phone": _phone(),
                                                                  "role": "user", "store_id": STORE_A, "send_invite": False, "send_sms": False})
        created.append(email)
        assert st == 200, (st, body)
        doc = mongo.users.find_one({"email": email})
        assert doc["role"] == "user" and doc["store_id"] == STORE_A and doc["organization_id"] == QA_ORG_A
    finally:
        for e in created:
            _purge(mongo, e)


# ── pending-user approval ───────────────────────────────────────────────────────────────────────────────────────────────


def _pending(mongo, org_id, store_id, tag):
    email = _email(tag)
    r = mongo.users.insert_one({"email": email, "name": "QA Pending", "role": "user", "status": "pending", "is_active": True,
                                "organization_id": org_id, "store_id": store_id, "requested_role": "Sales Manager",
                                "password": "x", "created_at": datetime.utcnow()})
    return str(r.inserted_id), email


def test_approval_is_scoped_to_the_approvers_organizations(org_a_admin, org_admin, store_manager, victim, mongo):
    pid, email = _pending(mongo, ORG_B, STORE_B, "pending-b")
    try:
        # an org admin of another dealership can't see, approve or reject this applicant
        st, listed = org_a_admin.get("/api/admin/pending-users")
        assert st == 200 and pid not in {u["_id"] for u in listed}
        assert org_a_admin.put(f"/api/admin/pending-users/{pid}/approve", {"role": "user"})[0] in (403, 404)
        assert org_a_admin.put(f"/api/admin/pending-users/{pid}/reject", {})[0] in (403, 404)
        assert store_manager.put(f"/api/admin/pending-users/{pid}/approve", {"role": "user"})[0] == 403
        assert victim.put(f"/api/admin/pending-users/{pid}/approve", {"role": "user"})[0] == 403
        assert mongo.users.find_one({"_id": ObjectId(pid)})["status"] == "pending"
        # the right org admin sees it, but can't grant their own rank or move it elsewhere
        st, listed = org_admin.get("/api/admin/pending-users")
        assert st == 200 and pid in {u["_id"] for u in listed}
        for body in ({"role": "super_admin"}, {"role": "org_admin"}, {"role": "user", "store_id": STORE_A},
                     {"role": "user", "organization_id": QA_ORG_A}, {"role": "user", "store_ids": [STORE_B, STORE_A]}):
            st, resp = org_admin.put(f"/api/admin/pending-users/{pid}/approve", body)
            assert st == 403, (body, st, resp)
            doc = mongo.users.find_one({"_id": ObjectId(pid)})
            assert doc["status"] == "pending" and doc["role"] == "user" and doc["organization_id"] == ORG_B
        st, resp = org_admin.put(f"/api/admin/pending-users/{pid}/approve", {"role": "store_manager", "store_id": STORE_B})
        assert st == 200, (st, resp)
        doc = mongo.users.find_one({"_id": ObjectId(pid)})
        assert doc["status"] == "active" and doc["role"] == "store_manager" and doc["store_id"] == STORE_B
    finally:
        mongo.users.delete_one({"_id": ObjectId(pid)})


def test_super_admin_approves_anything_and_counts_are_scoped(super_admin, org_a_admin, org_admin, mongo):
    pid, email = _pending(mongo, QA_ORG_A, STORE_A, "pending-a")
    try:
        st, c_a = org_a_admin.get("/api/admin/pending-users/count")
        st2, c_b = org_admin.get("/api/admin/pending-users/count")
        assert st == 200 and st2 == 200
        st_a, list_a = org_a_admin.get("/api/admin/pending-users")
        st_b, list_b = org_admin.get("/api/admin/pending-users")
        assert st_a == 200 and st_b == 200, (st_a, list_a, st_b, list_b)
        assert pid in {u["_id"] for u in list_a}
        assert pid not in {u["_id"] for u in list_b}
        assert c_a["count"] >= 1
        st, resp = super_admin.put(f"/api/admin/pending-users/{pid}/approve", {"role": "org_admin"})
        assert st == 200, (st, resp)
        assert mongo.users.find_one({"_id": ObjectId(pid)})["role"] == "org_admin"
    finally:
        mongo.users.delete_one({"_id": ObjectId(pid)})


# ── equivalent creation routes ──────────────────────────────────────────────────────────────────────────────────────────


def test_add_team_member_trusts_the_session_not_the_body(store_manager, super_admin, mongo):
    email = _email("team")
    forged = {"name": "QA Team", "email": email, "phone": "", "store_id": STORE_B, "role": "user", "added_by": super_admin.user_id}
    st, resp = store_manager.post("/api/admin/users/add-team-member", forged)
    assert st == 403 and mongo.users.find_one({"email": email}) is None, (st, resp)
    st, resp = store_manager.post("/api/admin/users/add-team-member", {**forged, "store_id": STORE_A, "role": "store_manager"})
    assert st == 403 and mongo.users.find_one({"email": email}) is None, (st, resp)
    try:
        st, resp = store_manager.post("/api/admin/users/add-team-member", {**forged, "store_id": STORE_A})
        assert st == 200, (st, resp)
        doc = mongo.users.find_one({"email": email})
        assert doc["role"] == "user" and doc["store_id"] == STORE_A and doc["added_by"] == store_manager.user_id
        assert doc["password"].startswith("$2"), "temporary password must be stored hashed"
    finally:
        _purge(mongo, email)


def test_bulk_invite_grants_roles_strictly_below_the_caller(store_manager, org_a_admin, mongo):
    email = _bulk_email("bulk")
    st, resp = store_manager.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": [{"name": "QA Bulk", "email": email, "role": "store_manager"}]})
    assert st == 403 and mongo.users.find_one({"email": email}) is None, (st, resp)
    assert store_manager.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_B, "members": [{"name": "QA Bulk", "email": email, "role": "user"}]})[0] == 403
    try:
        st, resp = org_a_admin.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": [{"name": "QA Bulk", "email": email, "role": "store_manager"}]})
        assert st == 200 and resp["results"][0]["status"] == "created" if isinstance(resp, dict) and "results" in resp else st == 200, (st, resp)
        assert mongo.users.find_one({"email": email})["role"] == "store_manager"
    finally:
        _purge(mongo, email)


def test_permission_templates_cannot_escalate(store_manager, org_a_admin, org_admin, victim, mongo):
    me = store_manager.user_id
    before = mongo.users.find_one({"_id": ObjectId(victim.user_id)})
    for path in (f"/api/permission-templates/org_admin/apply/{me}", f"/api/permission-templates/sales_manager/apply/{me}",
                 f"/api/permission-templates/org_admin/apply/{victim.user_id}", f"/api/permission-templates/sales_manager/apply/{victim.user_id}"):
        st, resp = store_manager.post(path, {})
        assert st == 403, (path, st, resp)
    assert _role(mongo, me) == "store_manager" and _role(mongo, victim.user_id) == "user"
    for role in ("super_admin", "org_admin", "store_manager"):
        st, resp = store_manager.post("/api/permission-templates/", {"name": f"QA 4c {role}", "role": role})
        assert st == 403, (role, st, resp)
        assert mongo.permission_templates.find_one({"name": f"QA 4c {role}"}) is None
    assert org_a_admin.post(f"/api/permission-templates/org_admin/apply/{victim.user_id}", {})[0] == 403
    assert org_admin.post(f"/api/permission-templates/sales_rep/apply/{victim.user_id}", {})[0] == 403   # other dealership
    assert victim.post(f"/api/permission-templates/sales_manager/apply/{victim.user_id}", {})[0] == 403
    assert anon("POST", f"/api/permission-templates/org_admin/apply/{victim.user_id}", {})[0] == 401
    assert _role(mongo, victim.user_id) == "user"
    try:
        st, resp = org_a_admin.post(f"/api/permission-templates/sales_manager/apply/{victim.user_id}", {})
        assert st == 200 and _role(mongo, victim.user_id) == "store_manager", (st, resp)
    finally:
        restore = {"role": "user"}
        for f in ("feature_permissions", "permission_template"):
            if f in before:
                restore[f] = before[f]
        mongo.users.update_one({"_id": ObjectId(victim.user_id)}, {"$set": restore, "$unset": {k: "" for k in ("feature_permissions", "permission_template", "permissions_updated_at", "permissions_updated_by") if k not in before}})
    assert _role(mongo, victim.user_id) == "user"


def test_individuals_are_super_admin_only(victim, org_a_admin, super_admin, mongo):
    email = _email("indiv")
    assert victim.post("/api/admin/individuals", {"email": email, "name": "QA Indiv"})[0] == 403
    assert org_a_admin.post("/api/admin/individuals", {"email": email, "name": "QA Indiv"})[0] == 403
    assert victim.get("/api/admin/individuals")[0] == 403
    assert mongo.users.find_one({"email": email}) is None
    try:
        st, resp = super_admin.post("/api/admin/individuals", {"email": email, "name": "QA Indiv"})
        assert st == 200 and resp["role"] == "user" and "password" not in resp, (st, resp)
    finally:
        _purge(mongo, email)


# ── operator surfaces ───────────────────────────────────────────────────────────────────────────────────────────────────


def test_webhook_enforcement_report_is_super_admin_only_and_leaks_no_keys(victim, super_admin):
    assert anon("GET", "/api/health/webhook-enforcement")[0] == 401
    assert victim.get("/api/health/webhook-enforcement")[0] == 403
    st, body = super_admin.get("/api/health/webhook-enforcement")
    assert st == 200 and {"shared_inboxes", "adf_sources_with_api_key", "build"} <= set(body), (st, body)
    import json
    blob = json.dumps(body)
    assert "webhook_key" not in blob and '"api_key"' not in blob


def test_smoke_script_expects_the_hotfix4c_build():
    from tests import prod_smoke_hotfix3 as smoke
    assert smoke.DEFAULT_BUILD == "2026-10-14.mms-stage1"
    probes = {(m, p) for m, p, *_ in smoke.CHECKS}
    assert ("POST", "/api/admin/users") in probes and ("POST", "/api/admin/users/create") in probes
