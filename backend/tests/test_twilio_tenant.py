"""Multi-tenant Twilio: org record + subaccount (dry run), phone_numbers registry lifecycle, inbound resolver,
signature validation, HELP keyword, usage counters, migration report, audit log. No Twilio network calls (mode dry_run).
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_twilio_tenant.py -q"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx
import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import phone_numbers as pn  # noqa: E402
from services import twilio_tenant as tenant  # noqa: E402
from services import twilio_signature as sig  # noqa: E402

TAG = "QA Tenant"
ADMIN = {"_id": ObjectId(), "name": "QA Super", "email": "qa-super@invalid.imonsocial.test", "role": "super_admin"}
LOCAL = "http://localhost:8001"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _seed(db):
    now = datetime.now(timezone.utc)
    org = {"name": f"{TAG} Motors", "slug": "qa-tenant-motors", "admin_email": "owner@invalid.imonsocial.test", "admin_phone": "+18015550100", "active": True, "created_at": now, "qa_tag": TAG}
    org_id = (await db.organizations.insert_one(org)).inserted_id
    store = {"name": f"{TAG} Salt Lake", "organization_id": str(org_id), "phone": "+13855550100", "city": "Salt Lake City", "state": "UT", "country": "US", "created_at": now, "qa_tag": TAG}
    store_id = (await db.stores.insert_one(store)).inserted_id
    rep = {"name": "QA Rep Tenant", "email": "qa-rep-tenant@invalid.imonsocial.test", "role": "user", "organization_id": str(org_id), "store_id": str(store_id), "phone": "+14355550100", "status": "active", "created_at": now, "qa_tag": TAG}
    rep_id = (await db.users.insert_one(rep)).inserted_id
    mgr = {"name": "QA Manager Tenant", "email": "qa-mgr-tenant@invalid.imonsocial.test", "role": "store_manager", "organization_id": str(org_id), "store_id": str(store_id), "status": "active", "created_at": now, "qa_tag": TAG}
    mgr_id = (await db.users.insert_one(mgr)).inserted_id
    return {**org, "_id": org_id}, {**store, "_id": store_id}, {**rep, "_id": rep_id}, {**mgr, "_id": mgr_id}


async def _wipe(db):
    orgs = [o["_id"] async for o in db.organizations.find({"qa_tag": TAG}, {"_id": 1})]
    org_ids = [str(o) for o in orgs]
    await db.phone_number_pool.delete_many({"organization_id": {"$in": org_ids}})
    async for n in db[pn.COLL].find({"organization_id": {"$in": org_ids}}):
        await db.phone_number_pool.delete_many({"twilio_sid": n["twilio_phone_number_sid"]})
    await db[pn.COLL].delete_many({"organization_id": {"$in": org_ids}})
    await db[pn.USAGE].delete_many({"organization_id": {"$in": org_ids}})
    await db[tenant.AUDIT].delete_many({"organization_id": {"$in": org_ids}})
    uids = [str(u["_id"]) async for u in db.users.find({"qa_tag": TAG}, {"_id": 1})]
    convs = [str(c["_id"]) async for c in db.conversations.find({"user_id": {"$in": uids}}, {"_id": 1})]
    await db.messages.delete_many({"conversation_id": {"$in": convs}})
    await db.conversations.delete_many({"user_id": {"$in": uids}})
    await db.contacts.delete_many({"user_id": {"$in": uids}})
    await db.inbound_message_dedup.delete_many({"message_sid": {"$regex": "^SMqa_tenant"}})
    await db.users.delete_many({"qa_tag": TAG})
    await db.stores.delete_many({"qa_tag": TAG})
    await db.organizations.delete_many({"qa_tag": TAG})


@pytest.fixture(scope="module")
def loop():
    lp = asyncio.new_event_loop()
    yield lp
    lp.close()


@pytest.fixture(scope="module")
def world(loop):
    db = _db()
    loop.run_until_complete(_wipe(db))
    org, store, rep, mgr = loop.run_until_complete(_seed(db))
    yield {"db": db, "org": org, "store": store, "rep": rep, "mgr": mgr}
    loop.run_until_complete(_wipe(db))


def test_dry_run_and_secrets(loop, world):
    db = world["db"]
    assert loop.run_until_complete(tenant.dry_run(db)) is True, "preview must stay in dry_run for these tests"
    enc = tenant.encrypt("secret-token")
    assert enc != "secret-token" and tenant.decrypt(enc) == "secret-token" and tenant.decrypt("garbage") == ""


def test_provision_subaccount_idempotent_and_statuses(loop, world):
    db, org = world["db"], world["org"]
    rec1 = loop.run_until_complete(tenant.provision(db, org, ADMIN))
    assert rec1["subaccount_sid"].startswith("ACdry") and rec1["enabled"] is True
    assert rec1["provisioning_status"] == "INFORMATION_REQUIRED" and "compliance form" in rec1["provisioning_error"].lower()
    org2 = loop.run_until_complete(tenant.org_by_id(db, org["_id"]))
    rec2 = loop.run_until_complete(tenant.provision(db, org2, ADMIN))
    assert rec2["subaccount_sid"] == rec1["subaccount_sid"], "second Provision must not create another subaccount"
    assert loop.run_until_complete(db[tenant.AUDIT].count_documents({"organization_id": str(org["_id"]), "action": "subaccount_dry_run"})) == 1
    view = loop.run_until_complete(tenant.view(db, org2, full=True))
    st = view["statuses"]
    assert st["subaccount"]["status"] == "APPROVED" and st["compliance_profile"]["status"] == "NOT_STARTED" and st["phone_numbers"]["status"] == "NOT_STARTED"
    assert view["messaging_ready"] is False and "subaccount_auth_token_enc" not in view["record"] and view["record"]["has_subaccount_token"] is True
    limited = loop.run_until_complete(tenant.view(db, org2, full=False))
    assert "subaccount_sid" not in limited["record"] and "sid" not in limited["statuses"]["subaccount"] and limited["webhooks"] is None
    # creds for the org resolve to the parent while the subaccount is a dry-run one
    assert tenant.creds_for_org(org2)[0] == tenant.parent_sid()


def test_number_lifecycle(loop, world):
    db, org, store, rep, mgr = world["db"], world["org"], world["store"], world["rep"], world["mgr"]
    org = loop.run_until_complete(tenant.org_by_id(db, org["_id"]))
    sugg = loop.run_until_complete(pn.suggest_area_codes(db, org, store, rep))
    assert [s["area_code"] for s in sugg][:3] == ["435", "385", "801"], sugg
    found = loop.run_until_complete(pn.search(db, org, area_code="435"))
    assert found["dry_run"] and found["numbers"][0]["phone_number"].startswith("+1435")
    phone = found["numbers"][0]["phone_number"]
    num = loop.run_until_complete(pn.purchase(db, org=org, phone_number=phone, number_type="USER", assigned_user_id=str(rep["_id"]), actor=ADMIN))
    assert num["status"] == "ASSIGNED" and num["organization_id"] == str(org["_id"]) and num["location_id"] == str(store["_id"]) and num["dry_run"]
    assert num["incoming_sms_webhook"].endswith("/api/webhooks/twilio/sms")
    u = loop.run_until_complete(db.users.find_one({"_id": rep["_id"]}))
    assert u["twilio_number"] == phone and u["twilio_number_sid"] == num["twilio_phone_number_sid"], "legacy mirror keeps send paths working"
    pool = loop.run_until_complete(db.phone_number_pool.find_one({"twilio_sid": num["twilio_phone_number_sid"]}))
    assert pool and pool["status"] == "assigned"
    with pytest.raises(ValueError):
        loop.run_until_complete(pn.purchase(db, org=org, phone_number=phone, actor=ADMIN))
    # store_numbers (compliance) sees it
    from services.twilio_compliance import store_numbers
    assert any(n["sid"] == num["twilio_phone_number_sid"] for n in loop.run_until_complete(store_numbers(db, str(store["_id"]))))
    # inbound resolver: number -> org -> store -> user
    hit = loop.run_until_complete(pn.resolve_inbound(db, phone))
    assert hit and str(hit["org"]["_id"]) == str(org["_id"]) and str(hit["store"]["_id"]) == str(store["_id"]) and str(hit["user"]["_id"]) == str(rep["_id"])
    # reassign to the manager
    doc = loop.run_until_complete(pn.get(db, num["id"]))
    out = loop.run_until_complete(pn.assign(db, doc, str(mgr["_id"]), ADMIN))
    assert out["assigned_user_id"] == str(mgr["_id"])
    assert loop.run_until_complete(db.users.find_one({"_id": rep["_id"]})).get("twilio_number") is None
    assert loop.run_until_complete(db.users.find_one({"_id": mgr["_id"]}))["twilio_number"] == phone
    # cross-org guard
    other = loop.run_until_complete(db.users.find_one({"role": "super_admin"}))
    other_org_user = loop.run_until_complete(db.users.find_one({"organization_id": {"$nin": [None, "", str(org["_id"])]}, "status": {"$ne": "deactivated"}}))
    if other_org_user:
        with pytest.raises(ValueError):
            loop.run_until_complete(pn.assign(db, out, str(other_org_user["_id"]), ADMIN))
    # suspend -> inbound goes to the location manager, not the user
    out = loop.run_until_complete(pn.suspend(db, out, ADMIN, "test"))
    assert out["status"] == "SUSPENDED" and loop.run_until_complete(db.users.find_one({"_id": mgr["_id"]})).get("twilio_number") is None
    hit = loop.run_until_complete(pn.resolve_inbound(db, phone))
    assert hit["user"] is None and hit["store"]
    out = loop.run_until_complete(pn.reactivate(db, out, ADMIN))
    assert out["status"] == "ASSIGNED" and loop.run_until_complete(db.users.find_one({"_id": mgr["_id"]}))["twilio_number"] == phone
    # unassign on user departure
    n = loop.run_until_complete(pn.unassign_user(db, str(mgr["_id"]), ADMIN, "left"))
    assert n == 1 and loop.run_until_complete(pn.get(db, num["id"]))["status"] == "AVAILABLE"
    # release (dry run: no Twilio call)
    out = loop.run_until_complete(pn.release(db, loop.run_until_complete(pn.get(db, num["id"])), ADMIN, "test"))
    assert out["status"] == "RELEASED" and loop.run_until_complete(pn.by_phone(db, phone)) is None
    actions = [a["action"] for a in loop.run_until_complete(tenant.audit_list(db, org["_id"], limit=50))]
    for a in ("number_purchased", "number_reassigned", "number_suspended", "number_reactivated", "number_unassigned", "number_released"):
        assert a in actions, actions
    world["phone"] = phone


def test_org_view_after_numbers_and_usage(loop, world):
    db, org, rep = world["db"], world["org"], world["rep"]
    org = loop.run_until_complete(tenant.org_by_id(db, org["_id"]))
    num = loop.run_until_complete(pn.purchase(db, org=org, phone_number="+14355550199", number_type="STORE", location_id=str(world["store"]["_id"]), actor=ADMIN))
    loop.run_until_complete(pn.record_usage(db, direction="outbound", phone_number="+14355550199", segments=2))
    loop.run_until_complete(pn.record_usage(db, direction="inbound", phone_number="+14355550199", mms=True))
    usage = loop.run_until_complete(pn.usage_summary(db, str(org["_id"])))
    assert usage["totals"]["sms_out"] == 1 and usage["totals"]["segments_out"] == 2 and usage["totals"]["mms_in"] == 1 and usage["numbers_active"] == 1
    view = loop.run_until_complete(tenant.view(db, org, full=True))
    assert view["statuses"]["phone_numbers"]["status"] == "PENDING", view["statuses"]["phone_numbers"]
    assert view["provisioning"]["status"] == "INFORMATION_REQUIRED"
    assert any(n["id"] == num["id"] for n in view["numbers"])
    # a "not ready" org blocks sends only when the flag is on
    assert loop.run_until_complete(tenant.send_block_reason(db, "+14355550199")) == ""
    loop.run_until_complete(tenant.set_flags(db, {"enforce_ready": True}, ADMIN))
    try:
        why = loop.run_until_complete(tenant.send_block_reason(db, "+14355550199"))
        assert "not active yet" in why and "Motors" in why, why
        assert loop.run_until_complete(tenant.send_block_reason(db, "+19995550000")) == "", "numbers outside the registry are never blocked"
    finally:
        loop.run_until_complete(tenant.set_flags(db, {"enforce_ready": False}, ADMIN))


def test_signature_validation_modes(loop, world):
    from twilio.request_validator import RequestValidator
    from starlette.requests import Request as _R
    db = world["db"]
    token = tenant.parent_token()
    assert token, "preview has TWILIO_AUTH_TOKEN"
    url = "https://app.imonsocial.com/api/webhooks/twilio/sms"
    form = {"From": "+15005550006", "To": "+14355550199", "Body": "hi", "AccountSid": tenant.parent_sid(), "MessageSid": "SMqa_tenant_sig"}
    good = RequestValidator(token).compute_signature(url, form)

    def req(sig_value, host="app.imonsocial.com", scheme="http"):
        scope = {"type": "http", "method": "POST", "scheme": scheme, "path": "/api/webhooks/twilio/sms", "query_string": b"", "server": ("10.0.0.1", 8001),
                 "headers": [(b"host", host.encode()), (b"x-twilio-signature", sig_value.encode())]}
        return _R(scope)

    os.environ["PUBLIC_FACING_URL"] = "https://app.imonsocial.com"
    assert loop.run_until_complete(sig.check(req(good), form, db)) == (True, "ok"), "public URL shape validates even when the ingress hands us http://"
    ok, why = loop.run_until_complete(sig.check(req("bad"), form, db))
    assert not ok and why == "signature mismatch"
    os.environ["TWILIO_WEBHOOK_VALIDATION"] = "log"
    assert loop.run_until_complete(sig.guard(req("bad"), form, db, "test")) is None, "log mode never blocks"
    os.environ["TWILIO_WEBHOOK_VALIDATION"] = "enforce"
    resp = loop.run_until_complete(sig.guard(req("bad"), form, db, "test"))
    assert resp is not None and resp.status_code == 403
    assert loop.run_until_complete(sig.guard(req(good), form, db, "test")) is None
    os.environ["TWILIO_WEBHOOK_VALIDATION"] = "log"


def test_inbound_webhook_routes_registry_number_and_help(loop, world):
    """Real webhook on the running backend: a text to the STORE number lands on the store manager; HELP gets the compliant reply."""
    db, org, store, mgr = world["db"], world["org"], world["store"], world["mgr"]
    base = LOCAL
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{base}/api/webhooks/twilio/sms", data={"From": "+15005550031", "To": "+14355550199", "Body": "Hi, is the Tahoe still there?", "MessageSid": "SMqa_tenant_1", "NumMedia": "0", "AccountSid": tenant.parent_sid()})
        assert r.status_code == 200, r.text
    conv = loop.run_until_complete(db.conversations.find_one({"rep_phone": "+14355550199", "contact_phone": "+15005550031"}))
    assert conv and conv["user_id"] == str(mgr["_id"]), "store number with no assigned user routes to the location's manager"
    msg = loop.run_until_complete(db.messages.find_one({"twilio_sid": "SMqa_tenant_1"}))
    assert msg["direction"] == "inbound" and msg["organization_id"] == str(org["_id"]) and msg["location_id"] == str(store["_id"])
    usage = loop.run_until_complete(pn.usage_summary(db, str(org["_id"])))
    assert usage["totals"]["sms_in"] >= 1
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{base}/api/webhooks/twilio/incoming", data={"From": "+15005550031", "To": "+14355550199", "Body": "HELP", "MessageSid": "SMqa_tenant_2", "NumMedia": "0", "AccountSid": tenant.parent_sid()})
        assert r.status_code == 200 and "<Message>" in r.text and "STOP" in r.text and "QA Tenant Salt Lake" in r.text, r.text
        r = c.post(f"{base}/api/webhooks/twilio/incoming", data={"From": "+15005550031", "To": "+14355550199", "Body": "STOP", "MessageSid": "SMqa_tenant_3", "NumMedia": "0", "AccountSid": tenant.parent_sid()})
        assert r.status_code == 200 and "unsubscribed" in r.text
    contact = loop.run_until_complete(db.contacts.find_one({"user_id": str(mgr["_id"]), "phone": {"$regex": "5550031"}}))
    assert contact and contact.get("opted_out") is True and contact.get("sms_opt_out") is True, "both opt-out fields set"


def test_migration_report_and_import(loop, world):
    db, org, rep = world["db"], world["org"], world["rep"]
    loop.run_until_complete(db.users.update_one({"_id": rep["_id"]}, {"$set": {"twilio_number": "+14355550177", "mvpline_number": "+14355550177", "twilio_number_sid": "PNqa_tenant_legacy"}}))
    rep_report = loop.run_until_complete(pn.migration_report(db))
    row = next(r for r in rep_report["rows"] if r["phone_number"] == "+14355550177")
    assert "users.twilio_number" in row["sources"] and row["organization_id"] == str(org["_id"]) and row["user_id"] == str(rep["_id"]) and row["number_type"] == "USER"
    assert not row["in_registry"]
    out = loop.run_until_complete(pn.import_report(db, ADMIN, phones=["+14355550177"]))
    assert out["count"] == 1
    reg = loop.run_until_complete(pn.by_phone(db, "+14355550177"))
    assert reg and reg["status"] == "ASSIGNED" and reg["assigned_user_id"] == str(rep["_id"]) and reg["twilio_phone_number_sid"] == "PNqa_tenant_legacy"
    again = loop.run_until_complete(pn.import_report(db, ADMIN, phones=["+14355550177"]))
    assert again["count"] == 1 and loop.run_until_complete(db[pn.COLL].count_documents({"phone_number": "+14355550177"})) == 1, "import is idempotent"
    ov = loop.run_until_complete(tenant.overview(db))
    mine = next(o for o in ov if o["id"] == str(org["_id"]))
    assert mine["numbers"] == 2 and mine["has_subaccount"] and mine["provisioning_status"] == "INFORMATION_REQUIRED"
