"""Dealership texting guard (services/sender_policy.py): the pure decision table plus the resolver against preview Mongo with
disposable "QA Sender Policy *" orgs, users and registry numbers (removed at the end). No Twilio calls, nothing is sent."""
import asyncio
import os
import secrets
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from services import sender_policy as sp

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
PARENT = os.environ.get("TWILIO_ACCOUNT_SID") or "ACparent000"
SUB = "AC" + "5" * 32
MS = "MG" + "7" * 32


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


def _ready_org(**tw):
    return {"_id": ObjectId(), "name": "Dealer", "customer": {"billing_status": "active"},
            "twilio": {"subaccount_sid": SUB, "messaging_ready": True, "messaging_service_sid": MS, **tw}}


def _num(org, user_id, **kw):
    return {"phone_number": "+18015550101", "organization_id": str(org["_id"]), "assigned_user_id": user_id, "number_type": "USER",
            "twilio_account_sid": SUB, "messaging_service_sid": MS, "status": "ASSIGNED", **kw}


def d(**kw):
    base = {"platform": False, "paused": False, "internal_org": False, "user_id": "u1", "from_phone": "+18015550101",
            "internal_number": False, "parent_sid": PARENT}
    base.update(kw)
    return sp.decide(**base)


# ── pure decision table ───────────────────────────────────────────────────────

def test_ready_dealership_number_is_allowed():
    org = _ready_org()
    assert d(org=org, number=_num(org, "u1")) == (True, "dealership_ready")


@pytest.mark.parametrize("case,expect", [
    ("no_number", "no_number"), ("unregistered", "unregistered_number"), ("released", "unregistered_number"),
    ("other_org", "wrong_org"), ("other_rep", "not_your_number"), ("parent_account", "no_subaccount"),
    ("dry_subaccount", "no_subaccount"), ("number_in_parent", "wrong_account"), ("not_ready", "not_ready"),
    ("no_service", "not_associated"), ("other_service", "not_associated"), ("paused", "paused"),
])
def test_dealership_fails_closed(case, expect):
    org = _ready_org()
    num = _num(org, "u1")
    kw = {}
    if case == "no_number":
        kw["from_phone"] = None
    elif case == "unregistered":
        num = None
    elif case == "released":
        num["status"] = "RELEASED"
    elif case == "other_org":
        num["organization_id"] = str(ObjectId())
    elif case == "other_rep":
        num["assigned_user_id"] = "u2"
    elif case == "parent_account":
        org["twilio"]["subaccount_sid"] = PARENT
    elif case == "dry_subaccount":
        org["twilio"]["subaccount_sid"] = "ACdry123"
    elif case == "number_in_parent":
        num["twilio_account_sid"] = PARENT
    elif case == "not_ready":
        org["twilio"]["messaging_ready"] = False
    elif case == "no_service":
        org["twilio"]["messaging_service_sid"] = ""
    elif case == "other_service":
        num["messaging_service_sid"] = "MGother"
    elif case == "paused":
        kw["paused"] = True
    allowed, code = d(org=org, number=num, **kw)
    assert (allowed, code) == (False, expect)
    assert sp.REASONS[code]


def test_shared_number_of_same_org_is_allowed_for_any_member():
    org = _ready_org()
    assert d(org=org, number=_num(org, None, number_type="SHARED"), user_id="u9") == (True, "dealership_ready")


def test_platform_notifications_and_internal_org():
    org = _ready_org()
    assert d(org=org, number=None, platform=True, from_phone=None) == (True, "platform")
    assert d(org=org, number=None, platform=True, from_phone=None, paused=True) == (True, "platform")
    assert d(org=org, number=None, platform=True, from_phone="+18015550101") == (False, "unregistered_number")
    assert d(org={"_id": ObjectId(), "name": "IMOS"}, internal_org=True, number=None, from_phone=None) == (True, "internal")


def test_kill_switch_never_lets_dealership_traffic_through():
    org = _ready_org()
    assert d(org=org, number=_num(org, "u1"), paused=True) == (False, "paused")
    assert d(org=org, number=_num(org, "u1"), paused=False) == (True, "dealership_ready")


def test_uncertain_sender_fails_closed():
    assert d(org=None, number=None, user_id=None, from_phone="+18015550199") == (False, "unknown_sender")
    assert d(org=None, number=None, user_id=None, from_phone=None) == (False, "unattributed")
    assert d(org=None, number=None, user_id=None, from_phone="+18015550199", internal_number=True) == (True, "internal")


def test_legacy_org_without_customer_block_is_still_a_dealership():
    legacy = {"_id": ObjectId(), "name": "Legacy Demo Motors"}
    assert d(org=legacy, number=None, from_phone=None) == (False, "no_number")


# ── resolver against preview Mongo ────────────────────────────────────────────

@pytest.fixture(scope="module")
def world():
    db = adb()
    tag = secrets.token_hex(3)
    now = datetime.now(timezone.utc)
    org = {**_ready_org(), "name": f"QA Sender Policy {tag}"}
    org_pending = {"_id": ObjectId(), "name": f"QA Sender Policy Pending {tag}", "customer": {"billing_status": "active"},
                   "twilio": {"subaccount_sid": SUB, "messaging_ready": False, "messaging_service_sid": ""}}
    rep, rep2, rep3 = ObjectId(), ObjectId(), ObjectId()
    phones = {k: f"+1500555{secrets.randbelow(9000) + 1000}" for k in ("ready", "pending", "nobody")}
    users = [{"_id": rep, "email": f"qa-sp-rep-{tag}@invalid.imonsocial.test", "organization_id": str(org["_id"]), "role": "user", "twilio_number": phones["ready"], "created_at": now},
             {"_id": rep2, "email": f"qa-sp-rep2-{tag}@invalid.imonsocial.test", "organization_id": str(org["_id"]), "role": "user", "created_at": now},
             {"_id": rep3, "email": f"qa-sp-rep3-{tag}@invalid.imonsocial.test", "organization_id": str(org_pending["_id"]), "role": "user", "twilio_number": phones["pending"], "created_at": now}]
    nums = [{**_num(org, str(rep)), "phone_number": phones["ready"], "updated_at": now},
            {**_num(org_pending, str(rep3), messaging_service_sid=""), "phone_number": phones["pending"], "updated_at": now}]
    run(db.organizations.insert_many([org, org_pending]))
    run(db.users.insert_many(users))
    run(db.phone_numbers.insert_many(nums))
    yield {"db": db, "org": org, "rep": str(rep), "rep2": str(rep2), "rep3": str(rep3), "phones": phones}
    run(db.phone_numbers.delete_many({"organization_id": {"$in": [str(org["_id"]), str(org_pending["_id"])]}}))
    run(db.users.delete_many({"_id": {"$in": [rep, rep2, rep3]}}))
    run(db.organizations.delete_many({"_id": {"$in": [org["_id"], org_pending["_id"]]}}))
    run(db[sp.LOG].delete_many({"org_id": {"$in": [str(org["_id"]), str(org_pending["_id"])]}}))


def test_resolver_ready_rep(world):
    r = run(sp.check(world["db"], from_phone=world["phones"]["ready"], user_id=world["rep"]))
    assert (r["allowed"], r["code"], r["dealership"]) == (True, "dealership_ready", True)


def test_resolver_finds_sender_from_number_alone(world):
    r = run(sp.check(world["db"], from_phone=world["phones"]["ready"]))
    assert r["allowed"] and r["user_id"] == world["rep"]


def test_resolver_rep_without_number_is_blocked(world):
    r = run(sp.check(world["db"], from_phone=None, user_id=world["rep2"]))
    assert (r["allowed"], r["code"]) == (False, "no_number")
    assert "No texting number" in r["reason"]


def test_resolver_rep_using_teammates_number_is_blocked(world):
    r = run(sp.check(world["db"], from_phone=world["phones"]["ready"], user_id=world["rep2"]))
    assert (r["allowed"], r["code"]) == (False, "not_your_number")


def test_resolver_pending_registration_is_blocked(world):
    r = run(sp.check(world["db"], from_phone=world["phones"]["pending"], user_id=world["rep3"]))
    assert (r["allowed"], r["code"]) == (False, "not_ready")


def test_resolver_unknown_number_fails_closed(world):
    r = run(sp.check(world["db"], from_phone=world["phones"]["nobody"]))
    assert (r["allowed"], r["code"]) == (False, "unknown_sender")


def test_resolver_internal_owner_org_unchanged():
    db = adb()
    owner = run(db.users.find_one({"email": (os.environ.get("OWNER_EMAIL") or "").lower()}, {"organization_id": 1}))
    if not owner or not owner.get("organization_id"):
        pytest.skip("OWNER_EMAIL user has no organization in this database")
    r = run(sp.check(db, from_phone=None, user_id=str(owner["_id"])))
    assert (r["allowed"], r["code"], r["dealership"]) == (True, "internal", False)


def test_resolver_platform_notification_to_dealership_user(world):
    r = run(sp.check(world["db"], from_phone=None, user_id=world["rep2"], platform=True))
    assert (r["allowed"], r["code"]) == (True, "platform")


def test_log_attempt_records_sender_and_account(world):
    db = world["db"]
    r = run(sp.check(db, from_phone=world["phones"]["ready"], user_id=world["rep"]))
    run(sp.log_attempt(db, r, to_phone="+15005550006", from_phone=world["phones"]["ready"], account_sid=SUB, messaging_service_sid=MS,
                       platform=False, result={"success": True, "message_sid": "SMqa1"}))
    row = run(db[sp.LOG].find_one({"message_sid": "SMqa1", "org_id": str(world["org"]["_id"])}))
    assert row and row["from_number"] == world["phones"]["ready"] and row["account_sid"] == SUB and row["messaging_service_sid"] == MS and row["allowed"]
