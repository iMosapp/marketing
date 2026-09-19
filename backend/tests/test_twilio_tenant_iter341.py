"""Iteration 341: multi-tenant Twilio provisioning HTTP-API tests.
Runs against REACT_APP_BACKEND_URL (preview). Mode stays at dry_run.
Cleans up any numbers created against org 69a907033b77512d1d8d8a08 and restores flags.

Run:
  cd /app/backend && set -a && . ./.env && set +a && \\
  python -m pytest tests/test_twilio_tenant_iter341.py -q
"""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ORG = "69a907033b77512d1d8d8a08"
OTHER_ORG = "69a9071244e985a2b4184d4b"

SUPER = {"email": "forest@imosapp.com", "password": "Admin123!"}
ORG_ADMIN = {"email": "qa-orgadmin@invalid.imonsocial.test", "password": "OrgAdmin123!"}
MGR = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}


# ─── auth helpers ──────────────────────────────────────────────────────────
def _login(creds):
    r = requests.post(f"{BASE}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.text}"
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def super_h():
    return _login(SUPER)


@pytest.fixture(scope="module")
def org_admin_h():
    return _login(ORG_ADMIN)


@pytest.fixture(scope="module")
def mgr_h():
    return _login(MGR)


@pytest.fixture(scope="module")
def org_users(super_h):
    """A user in ORG (must have store_id set to one of ORG's stores) and a user in a different org."""
    import asyncio

    from motor.motor_asyncio import AsyncIOMotorClient
    async def _load():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        stores = await db.stores.find({"organization_id": ORG}, {"_id": 1}).to_list(20)
        store_ids = [str(s["_id"]) for s in stores]
        user = await db.users.find_one({"organization_id": ORG, "store_id": {"$in": store_ids}, "role": {"$in": ["user", "store_manager", "org_admin"]}})
        other = await db.users.find_one({"organization_id": {"$nin": [None, "", ORG]}, "status": {"$ne": "deactivated"}})
        return user, other, store_ids
    loop = asyncio.new_event_loop()
    try:
        user, other, store_ids = loop.run_until_complete(_load())
    finally:
        loop.close()
    assert user, "need at least one user with a valid store on the QA org"
    assert other, "need a user in another org"
    return {"user_id": str(user["_id"]), "store_id": str(user.get("store_id")),
            "other_user_id": str(other["_id"]), "store_ids": store_ids}


# ─── cleanup ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def cleanup_after(super_h):
    yield
    # release any dry-run numbers we created on ORG
    try:
        v = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio", headers=super_h, timeout=30).json()
        for n in v.get("numbers") or []:
            if n.get("dry_run"):
                requests.delete(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{n['id']}?confirm=true&reason=iter341+cleanup",
                                headers=super_h, timeout=30)
    except Exception:
        pass
    # reset flags to false/false
    try:
        requests.put(f"{BASE}/admin/twilio/flags", headers=super_h,
                     json={"enforce_ready": False, "auto_provision": False}, timeout=30)
    except Exception:
        pass


# ─── SECURITY ─────────────────────────────────────────────────────────────
class TestSecurity:
    def test_admin_endpoints_require_auth(self):
        for path in ("/admin/twilio/numbers", "/admin/twilio/pool", "/admin/twilio/numbers/search?area_code=801"):
            r = requests.get(f"{BASE}{path}", timeout=30)
            assert r.status_code == 401, f"{path} without token → {r.status_code}"

    def test_admin_endpoints_forbid_store_manager(self, mgr_h):
        for path in ("/admin/twilio/numbers", "/admin/twilio/pool", "/admin/twilio/numbers/search?area_code=801"):
            r = requests.get(f"{BASE}{path}", headers=mgr_h, timeout=30)
            assert r.status_code == 403, f"{path} as store_manager → {r.status_code}"

    def test_admin_endpoints_allow_super(self, super_h):
        for path in ("/admin/twilio/numbers", "/admin/twilio/pool", "/admin/twilio/numbers/search?area_code=801"):
            r = requests.get(f"{BASE}{path}", headers=super_h, timeout=30)
            assert r.status_code == 200, f"{path} as super → {r.status_code} {r.text[:200]}"


# ─── ORG TWILIO VIEW ──────────────────────────────────────────────────────
class TestOrgTwilioView:
    def test_super_full_view_shape(self, super_h):
        r = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio", headers=super_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["full"] is True
        SEVEN = {"NOT_STARTED", "IN_PROGRESS", "PENDING", "APPROVED", "REJECTED", "SUSPENDED", "INFORMATION_REQUIRED"}
        for k in ("subaccount", "compliance_profile", "a2p_brand", "a2p_campaign", "messaging_service", "phone_numbers"):
            s = d["statuses"][k]
            assert s["status"] in SEVEN, (k, s)
            assert "label" in s and "detail" in s, (k, s)
        assert isinstance(d["messaging_ready"], bool)
        prov = d["provisioning"]
        for f in ("status", "label", "next_action", "history"):
            assert f in prov, prov
        assert isinstance(d["numbers"], list) and isinstance(d["people"], list) and isinstance(d["locations"], list)
        assert "totals" in d["usage"]
        assert isinstance(d["audit"], list)
        assert d["settings"]["mode"] == "dry_run", "CRITICAL: must remain in dry_run"
        assert d["webhooks"] and all(k in d["webhooks"] for k in ("sms", "voice", "status"))
        assert "subaccount_auth_token_enc" not in d["record"], "raw token must never be exposed"

    def test_org_admin_limited_view(self, org_admin_h):
        r = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio", headers=org_admin_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["full"] is False
        assert "subaccount_sid" not in d["record"]
        assert "messaging_service_sid" not in d["record"]
        assert not d.get("provisioning", {}).get("history"), "org admin must not see provisioning history"
        assert d.get("webhooks") is None

    def test_org_admin_cross_org_denied(self, org_admin_h):
        r = requests.get(f"{BASE}/admin/organizations/{OTHER_ORG}/twilio", headers=org_admin_h, timeout=30)
        assert r.status_code == 403

    def test_provision_role_gates(self, org_admin_h, mgr_h):
        assert requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/provision", headers=org_admin_h, timeout=30).status_code == 403
        assert requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/provision", headers=mgr_h, timeout=30).status_code == 403


# ─── PROVISION ────────────────────────────────────────────────────────────
class TestProvision:
    def test_provision_dry_run_and_idempotent(self, super_h):
        r1 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/provision", headers=super_h, timeout=30)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        sid1 = d1["record"]["subaccount_sid"]
        assert sid1.startswith("ACdry"), sid1
        assert d1["statuses"]["subaccount"]["status"] == "APPROVED"
        assert d1["provisioning"]["status"] == "INFORMATION_REQUIRED"
        assert "compliance" in (d1["provisioning"]["next_action"] or "").lower()

        r2 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/provision", headers=super_h, timeout=30)
        assert r2.status_code == 200
        sid2 = r2.json()["record"]["subaccount_sid"]
        assert sid2 == sid1, "must be idempotent"

        # exactly one subaccount_dry_run audit entry for the org
        au = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/audit?limit=300",
                          headers=super_h, timeout=30).json().get("entries") or []
        dry = [a for a in au if a.get("action") == "subaccount_dry_run"]
        assert len(dry) == 1, f"expected exactly 1 subaccount_dry_run, got {len(dry)}"


# ─── SUGGEST/SEARCH/PURCHASE ──────────────────────────────────────────────
class TestNumbers:
    def test_suggest_and_search(self, super_h, org_users):
        r = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/suggest?user_id={org_users['user_id']}",
                         headers=super_h, timeout=30)
        assert r.status_code == 200, r.text
        sug = r.json().get("suggestions") or []
        assert sug and all("area_code" in s and "reason" in s for s in sug)

        r2 = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/search?area_code=801",
                          headers=super_h, timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["dry_run"] is True
        nums = d.get("numbers") or []
        assert nums and all(n["phone_number"].startswith("+1801555") for n in nums)

    def test_purchase_full_lifecycle(self, super_h, org_users):
        # search
        d = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/search?area_code=801",
                        headers=super_h, timeout=30).json()
        phone = d["numbers"][0]["phone_number"]
        # purchase
        r = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers", headers=super_h,
                         json={"phone_number": phone, "number_type": "USER",
                               "assigned_user_id": org_users["user_id"]}, timeout=30)
        assert r.status_code == 200, r.text
        num = r.json()
        assert num["status"] == "ASSIGNED"
        assert num["organization_id"] == ORG
        assert num["location_id"] == org_users["store_id"]
        assert num["dry_run"] is True
        assert num["incoming_sms_webhook"].endswith("/api/webhooks/twilio/sms")
        num_id = num["id"]
        sid = num["twilio_phone_number_sid"]

        # user document mirrors twilio_number/twilio_number_sid
        import asyncio

        from bson import ObjectId
        from motor.motor_asyncio import AsyncIOMotorClient
        async def _check_user_and_pool():
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            u = await db.users.find_one({"_id": ObjectId(org_users["user_id"])})
            pool = await db.phone_number_pool.find_one({"twilio_sid": sid})
            return u, pool
        lp = asyncio.new_event_loop()
        try:
            u, pool = lp.run_until_complete(_check_user_and_pool())
        finally:
            lp.close()
        assert u.get("twilio_number") == phone and u.get("twilio_number_sid") == sid
        assert pool and pool["status"] == "assigned"

        # buying same number → 400
        r2 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers", headers=super_h,
                          json={"phone_number": phone, "number_type": "USER",
                                "assigned_user_id": org_users["user_id"]}, timeout=30)
        assert r2.status_code == 400 and "already" in r2.text.lower()

        # buying with a cross-org user → 400
        r3 = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/search?area_code=801",
                         headers=super_h, timeout=30).json()
        phone2 = r3["numbers"][1]["phone_number"] if len(r3["numbers"]) > 1 else r3["numbers"][0]["phone_number"]
        r4 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers", headers=super_h,
                          json={"phone_number": phone2, "number_type": "USER",
                                "assigned_user_id": org_users["other_user_id"]}, timeout=30)
        assert r4.status_code == 400, r4.text

        # reassign to another user of same org
        # find another user in same org
        async def _other_same_org():
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            u = await db.users.find_one({"organization_id": ORG, "_id": {"$ne": ObjectId(org_users["user_id"])},
                                          "role": {"$in": ["user", "store_manager", "org_admin"]}})
            return u
        lp = asyncio.new_event_loop()
        try:
            other_same = lp.run_until_complete(_other_same_org())
        finally:
            lp.close()
        if other_same:
            r5 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}/assign",
                              headers=super_h, json={"user_id": str(other_same["_id"])}, timeout=30)
            assert r5.status_code == 200, r5.text
            assert r5.json()["assigned_user_id"] == str(other_same["_id"])
            au = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/audit?limit=50",
                             headers=super_h, timeout=30).json().get("entries") or []
            assert any(a.get("action") == "number_reassigned" for a in au)

        # unassign
        r6 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}/unassign",
                           headers=super_h, json={"reason": "iter341"}, timeout=30)
        assert r6.status_code == 200 and r6.json()["status"] == "AVAILABLE"

        # suspend as org_admin → 403
        oa = _login(ORG_ADMIN)
        r_sus_403 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}/suspend",
                                   headers=oa, json={"reason": "no"}, timeout=30)
        assert r_sus_403.status_code == 403

        # suspend as super
        r7 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}/suspend",
                           headers=super_h, json={"reason": "iter341"}, timeout=30)
        assert r7.status_code == 200 and r7.json()["status"] == "SUSPENDED"

        # reactivate
        r8 = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}/reactivate",
                          headers=super_h, timeout=30)
        assert r8.status_code == 200 and r8.json()["status"] in ("ASSIGNED", "AVAILABLE")

        # delete without confirm → 400
        rd0 = requests.delete(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}",
                             headers=super_h, timeout=30)
        assert rd0.status_code == 400

        # delete with confirm → RELEASED, and not in view
        rd = requests.delete(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}?confirm=true&reason=iter341",
                            headers=super_h, timeout=30)
        assert rd.status_code == 200 and rd.json()["status"] == "RELEASED"
        v = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio", headers=super_h, timeout=30).json()
        assert not any(n["id"] == num_id for n in v.get("numbers") or [])


# ─── INBOUND WEBHOOK ──────────────────────────────────────────────────────
class TestInboundWebhook:
    def test_store_number_routes_and_help_stop(self, super_h, org_users):
        # buy a STORE-type number (no assigned user) on org's store
        d = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/search?area_code=801",
                       headers=super_h, timeout=30).json()
        phone = d["numbers"][2]["phone_number"] if len(d["numbers"]) > 2 else d["numbers"][0]["phone_number"]
        r = requests.post(f"{BASE}/admin/organizations/{ORG}/twilio/numbers", headers=super_h,
                        json={"phone_number": phone, "number_type": "STORE",
                              "location_id": org_users["store_id"]}, timeout=30)
        assert r.status_code == 200, r.text
        num_id = r.json()["id"]

        run_tag = uuid.uuid4().hex[:8]

        # inbound hello
        rr = requests.post(f"{BASE}/webhooks/twilio/sms",
                          data={"From": "+15005550041", "To": phone, "Body": "hello",
                                "MessageSid": f"SMiter341_{run_tag}_1", "NumMedia": "0", "AccountSid": "ACfoo"},
                          timeout=30)
        assert rr.status_code == 200, rr.text

        # verify conversation + message + usage
        import asyncio

        from motor.motor_asyncio import AsyncIOMotorClient
        async def _check():
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            conv = await db.conversations.find_one({"rep_phone": phone, "contact_phone": "+15005550041"})
            msg = await db.messages.find_one({"twilio_sid": f"SMiter341_{run_tag}_1"})
            # verify routing user is org_admin/store_manager of org
            u = None
            if conv:
                from bson import ObjectId
                u = await db.users.find_one({"_id": ObjectId(conv["user_id"])})
            return conv, msg, u
        lp = asyncio.new_event_loop()
        try:
            conv, msg, u = lp.run_until_complete(_check())
        finally:
            lp.close()
        assert conv, "conversation was not created"
        assert u and u.get("role") in ("store_manager", "org_admin"), f"routed user role={u and u.get('role')}"
        assert msg and msg["direction"] == "inbound"
        assert msg["organization_id"] == ORG
        assert msg["location_id"] == org_users["store_id"]

        usage = requests.get(f"{BASE}/admin/organizations/{ORG}/twilio/usage",
                            headers=super_h, timeout=30).json()
        assert usage.get("totals", {}).get("sms_in", 0) >= 1

        # HELP
        rh = requests.post(f"{BASE}/webhooks/twilio/sms",
                          data={"From": "+15005550041", "To": phone, "Body": "HELP",
                                "MessageSid": f"SMiter341_{run_tag}_2", "NumMedia": "0", "AccountSid": "ACfoo"},
                          timeout=30)
        assert rh.status_code == 200
        assert "<Message>" in rh.text and "STOP" in rh.text

        # STOP
        rs = requests.post(f"{BASE}/webhooks/twilio/sms",
                          data={"From": "+15005550041", "To": phone, "Body": "STOP",
                                "MessageSid": f"SMiter341_{run_tag}_3", "NumMedia": "0", "AccountSid": "ACfoo"},
                          timeout=30)
        assert rs.status_code == 200
        assert "unsubscribed" in rs.text.lower() or "<Message>" in rs.text

        # contact opt-out
        async def _check_optout():
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            return await db.contacts.find_one({"phone": {"$regex": "5550041"}, "user_id": conv["user_id"]})
        lp = asyncio.new_event_loop()
        try:
            c = lp.run_until_complete(_check_optout())
        finally:
            lp.close()
        assert c and c.get("opted_out") is True and c.get("sms_opt_out") is True

        # /incoming alias behaves the same (unique sid)
        ri = requests.post(f"{BASE}/webhooks/twilio/incoming",
                          data={"From": "+15005550042", "To": phone, "Body": "hi again",
                                "MessageSid": f"SMiter341_{run_tag}_4", "NumMedia": "0", "AccountSid": "ACfoo"},
                          timeout=30)
        assert ri.status_code == 200

        # cleanup number
        requests.delete(f"{BASE}/admin/organizations/{ORG}/twilio/numbers/{num_id}?confirm=true&reason=iter341",
                        headers=super_h, timeout=30)

    def test_missing_signature_accepted_in_log_mode(self):
        # webhook without X-Twilio-Signature is still 200 (log mode default)
        r = requests.post(f"{BASE}/webhooks/twilio/sms",
                        data={"From": "+15005550099", "To": "+14355550199",
                              "Body": "log-mode-ok", "MessageSid": f"SMiter341_logmode_{uuid.uuid4().hex[:8]}",
                              "NumMedia": "0", "AccountSid": "ACfoo"},
                        timeout=30)
        assert r.status_code == 200


# ─── MIGRATION / REGISTRY / ORGS ──────────────────────────────────────────
class TestMigrationAndAdmin:
    def test_migration_report_shape(self, super_h):
        r = requests.get(f"{BASE}/admin/twilio/migration-report", headers=super_h, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("rows"), list)
        assert "twilio_reachable" in d
        s = d.get("summary") or {}
        for k in ("total", "in_twilio", "in_registry", "importable", "needs_review", "webhook_wrong", "no_org"):
            assert k in s, f"summary missing {k}"
        allowed = {"import", "review", "already registered"}
        for row in d["rows"][:20]:
            assert row.get("proposed_action") in allowed, row

    def test_import_empty_selection(self, super_h):
        r = requests.post(f"{BASE}/admin/twilio/migration-report/import",
                        headers=super_h, json={"phone_numbers": []}, timeout=60)
        assert r.status_code == 200
        assert r.json().get("count", 0) == 0

    def test_import_importable_is_idempotent(self, super_h):
        rep = requests.get(f"{BASE}/admin/twilio/migration-report", headers=super_h, timeout=60).json()
        importable = [r for r in rep.get("rows") or [] if r.get("proposed_action") == "import"]
        if not importable:
            pytest.skip("no importable rows in current migration report")
        phone = importable[0]["phone_number"]
        r1 = requests.post(f"{BASE}/admin/twilio/migration-report/import",
                        headers=super_h, json={"phone_numbers": [phone]}, timeout=60)
        assert r1.status_code == 200
        c1 = r1.json().get("count", 0)
        assert c1 == 1
        r2 = requests.post(f"{BASE}/admin/twilio/migration-report/import",
                        headers=super_h, json={"phone_numbers": [phone]}, timeout=60)
        assert r2.status_code == 200
        # registry count for this phone must remain 1
        reg = requests.get(f"{BASE}/admin/twilio/registry", headers=super_h, timeout=30).json()
        count = sum(1 for n in reg.get("numbers", []) if n.get("phone_number") == phone)
        assert count == 1, f"phone {phone} appears {count} times in registry"

    def test_registry_and_orgs(self, super_h):
        r = requests.get(f"{BASE}/admin/twilio/registry", headers=super_h, timeout=30)
        assert r.status_code == 200 and "numbers" in r.json()
        r2 = requests.get(f"{BASE}/admin/twilio/orgs", headers=super_h, timeout=30)
        assert r2.status_code == 200
        orgs = r2.json().get("organizations")
        assert isinstance(orgs, list) and orgs
        for o in orgs[:5]:
            assert "provisioning_status" in o and "numbers" in o and "messaging_ready" in o


class TestFlags:
    def test_flags_roundtrip(self, super_h):
        r = requests.get(f"{BASE}/admin/twilio/flags", headers=super_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("enforce_ready") is False
        assert d.get("auto_provision") is False
        assert d.get("webhook_validation") == "log"

        # toggle enforce_ready on
        r2 = requests.put(f"{BASE}/admin/twilio/flags", headers=super_h,
                          json={"enforce_ready": True}, timeout=30)
        assert r2.status_code == 200
        d2 = requests.get(f"{BASE}/admin/twilio/flags", headers=super_h, timeout=30).json()
        assert d2.get("enforce_ready") is True

        # restore
        r3 = requests.put(f"{BASE}/admin/twilio/flags", headers=super_h,
                         json={"enforce_ready": False, "auto_provision": False}, timeout=30)
        assert r3.status_code == 200
        d3 = requests.get(f"{BASE}/admin/twilio/flags", headers=super_h, timeout=30).json()
        assert d3.get("enforce_ready") is False and d3.get("auto_provision") is False
