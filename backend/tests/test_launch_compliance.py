"""Launch compliance (preview only, nothing is sent): consent scopes, STOP/START, customer-initiated replies, the central send gate's
order, disclosure tracking, subscription locks, the send ledger and one-time broadcast queueing. Uses disposable "QA Launch *"
records in preview Mongo and removes them at the end."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from services import billing_lock, broadcast_queue, consent, disclosure, outbound_gate, send_ledger, suppression

loop = asyncio.get_event_loop_policy().get_event_loop()  # shared with the other launch suites: get_db() caches one Motor client per process
if loop.is_closed():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
ORG = str(ObjectId())
PHONE = "+18015559" + str(ObjectId())[-3:].translate(str.maketrans("abcdef", "123456"))
CREATED = {"orgs": [], "users": [], "contacts": [], "broadcasts": []}


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db = adb()
    for coll in ("consent_records", "consent_state", "sms_suppressions", "sms_optout_events", "sms_disclosure_state", "sms_disclosure_events", "sms_inbound_index"):
        run(db[coll].delete_many({"$or": [{"org_id": ORG}, {"phone": PHONE}]}))
    run(db.send_ledger.delete_many({"_id": {"$regex": "^qa-launch:"}}))
    run(db.users.delete_many({"_id": {"$in": CREATED["users"]}}))
    run(db.contacts.delete_many({"_id": {"$in": CREATED["contacts"]}}))
    run(db.organizations.delete_many({"_id": {"$in": CREATED["orgs"]}}))
    for b in CREATED["broadcasts"]:
        run(db.campaign_pending_sends.delete_many({"broadcast_id": str(b)}))
    run(db.broadcasts.delete_many({"_id": {"$in": CREATED["broadcasts"]}}))


# ── consent rules ─────────────────────────────────────────────────────────────

def test_verbal_never_authorizes_marketing():
    with pytest.raises(consent.ConsentError) as e:
        consent.validate(["marketing"], "verbal_in_person", None)
    assert e.value.code == "marketing_needs_written"
    assert consent.validate(["requested_info", "transactional"], "verbal_in_person", None) == ["requested_info", "transactional"]


def test_written_form_needs_evidence():
    with pytest.raises(consent.ConsentError) as e:
        consent.validate(["marketing"], "written_signature", {})
    assert e.value.code == "evidence_required"
    assert consent.validate(["marketing"], "written_signature", {"reference": "Form 12"}) == ["marketing"]


def test_unknown_by_default_and_scoped_grants():
    db = adb()
    st = run(consent.state(db, ORG, PHONE))
    assert all(v["status"] == "unknown" for v in st.values())
    assert not run(consent.eligible(db, ORG, PHONE, "conversational"))["ok"]
    run(consent.record(db, org_id=ORG, phone=PHONE, scopes=["requested_info"], method="verbal_in_person", source="qa"))
    assert run(consent.eligible(db, ORG, PHONE, "requested_info"))["ok"]
    assert run(consent.eligible(db, ORG, PHONE, "conversational"))["ok"]
    assert not run(consent.eligible(db, ORG, PHONE, "transactional"))["ok"]
    assert not run(consent.eligible(db, ORG, PHONE, "marketing"))["ok"]
    assert run(db.consent_records.count_documents({"org_id": ORG, "phone": PHONE, "action": "granted"})) == 1


def test_consent_is_per_organization():
    assert not run(consent.eligible(adb(), str(ObjectId()), PHONE, "requested_info"))["ok"]


def test_customer_text_allows_replies_never_marketing():
    db = adb()
    other = "+18015550" + PHONE[-3:]
    run(consent.note_inbound(db, ORG, other, "+18015550000", "SMqa"))
    assert run(consent.eligible(db, ORG, other, "transactional"))["basis"] == "customer_initiated"
    assert not run(consent.eligible(db, ORG, other, "marketing"))["ok"]
    run(db.sms_inbound_index.delete_many({"_id": f"{ORG}:{other}"}))


# ── STOP / START ──────────────────────────────────────────────────────────────

def test_keyword_classification():
    assert suppression.classify("STOP") == "stop" and suppression.classify("stop.") == "stop"
    assert suppression.classify("Unsubscribe") == "stop" and suppression.classify("START") == "start"
    assert suppression.classify("please stop texting me") == "stop_request"
    assert suppression.classify("Can you stop by Tuesday?") is None


def test_stop_blocks_even_with_consent_and_only_start_lifts_it():
    db = adb()
    run(consent.record(db, org_id=ORG, phone=PHONE, scopes=["transactional"], method="verbal_in_person", source="qa"))
    run(suppression.opt_out(db, PHONE, ORG, source="keyword", keyword="STOP"))
    d = run(outbound_gate.evaluate(db, to_phone=PHONE, from_phone=None, purpose="transactional", org_id=ORG))
    assert not d["allowed"] and d["code"] == "opted_out"
    with pytest.raises(consent.ConsentError) as e:
        run(consent.record(db, org_id=ORG, phone=PHONE, scopes=["requested_info"], method="verbal_in_person", source="qa"))
    assert e.value.code == "opted_out"
    assert run(suppression.opt_in(db, PHONE, ORG, keyword="START"))
    assert run(suppression.active(db, PHONE, ORG)) is None


# ── the gate's order ──────────────────────────────────────────────────────────

def test_gate_refuses_unknown_consent_before_sender_checks():
    db = adb()
    fresh = "+18015551" + PHONE[-3:]
    d = run(outbound_gate.evaluate(db, to_phone=fresh, from_phone=None, purpose="conversational", org_id=ORG))
    assert not d["allowed"] and d["code"] == "consent_required" and set(d["needs"]) == {"requested_info", "transactional"}
    m = run(outbound_gate.evaluate(db, to_phone=fresh, from_phone=None, purpose="marketing", org_id=ORG))
    assert m["code"] == "marketing_consent_required"


def test_unclassified_and_bad_purposes_fail_closed():
    db = adb()
    assert run(outbound_gate.evaluate(db, to_phone=PHONE, from_phone=None, purpose="system", system_kind="nope"))["code"] == "unclassified_system"
    assert run(outbound_gate.evaluate(db, to_phone=PHONE, from_phone=None, purpose="promo"))["code"] == "bad_purpose"


def test_system_team_alert_only_to_team_members():
    d = run(outbound_gate.evaluate(adb(), to_phone="+18015552" + PHONE[-3:], from_phone=None, purpose="system", system_kind="team_alert"))
    assert not d["allowed"] and d["code"] == "not_team_member"


# ── subscription lock ─────────────────────────────────────────────────────────

NOW = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _org(**c):
    return {"_id": ObjectId(), "customer": {"stripe_subscription_id": "sub_qa", **c}}


@pytest.mark.parametrize("cust,locked,state", [
    ({"subscription_status": "active"}, False, "active"),
    ({"subscription_status": "trialing"}, False, "trialing"),
    ({"subscription_status": "past_due", "payment_failed_at": (NOW - timedelta(days=3)).isoformat()}, False, "grace"),
    ({"subscription_status": "past_due", "payment_failed_at": (NOW - timedelta(days=15)).isoformat()}, True, "locked"),
    ({"subscription_status": "unpaid"}, True, "locked"),
    ({"subscription_status": "incomplete_expired"}, True, "locked"),
    ({"subscription_status": "canceled", "current_period_end": (NOW + timedelta(days=5)).isoformat()}, False, "canceling"),
    ({"subscription_status": "canceled", "current_period_end": (NOW - timedelta(days=1)).isoformat()}, True, "locked"),
])
def test_lock_follows_subscription_status(cust, locked, state):
    st = billing_lock.evaluate(_org(**cust), now=NOW)
    assert st["locked"] is locked and st["state"] == state


def test_never_locked_exceptions():
    assert not billing_lock.evaluate({"customer": {"billing_status": "pilot", "subscription_status": "unpaid", "stripe_subscription_id": "x"}}, now=NOW)["locked"]
    assert not billing_lock.evaluate({"customer": {"billing_status": "exception", "subscription_status": "unpaid", "stripe_subscription_id": "x"}}, now=NOW)["locked"]
    assert not billing_lock.evaluate(_org(subscription_status="unpaid"), internal=True, now=NOW)["locked"]
    st = billing_lock.evaluate({"customer": {"billing_status": "active"}}, now=NOW)
    assert st["state"] == "no_subscription" and not st["locked"]
    assert billing_lock.evaluate({"name": "old org"}, now=NOW)["state"] == "legacy_unclassified"


def test_locked_org_blocks_outbound_and_api_paths():
    db = adb()
    oid = ObjectId()
    CREATED["orgs"].append(oid)
    run(db.organizations.insert_one({"_id": oid, "name": "QA Launch Locked", "customer": {"stripe_subscription_id": "sub_qa", "subscription_status": "unpaid"}}))
    billing_lock.invalidate()
    d = run(outbound_gate.evaluate(db, to_phone=PHONE, from_phone=None, purpose="transactional", org_id=str(oid)))
    assert d["code"] == "billing_locked"
    otp = run(outbound_gate.evaluate(db, to_phone=PHONE, from_phone=None, purpose="system", system_kind="otp", org_id=str(oid)))
    assert otp["code"] != "billing_locked"
    assert billing_lock.path_allowed("/api/auth/me", {"owner": False}) and not billing_lock.path_allowed("/api/contacts/x", {"owner": False})
    assert billing_lock.path_allowed("/api/billing/portal", {"owner": True}) and not billing_lock.path_allowed("/api/billing/portal", {"owner": False})


# ── disclosure ────────────────────────────────────────────────────────────────

def test_first_text_discloses_then_stays_natural_marketing_always():
    db = adb()
    org = {"_id": ObjectId(ORG), "name": "QA Launch Co"}
    p1 = run(disclosure.plan(db, org=org, purpose="conversational", from_number="+18015550000", phone=PHONE, body="Hi there"))
    assert p1["reason"] == "first_message" and "STOP" in p1["append"] and "QA Launch Co" in p1["append"]
    run(disclosure.record(db, p1, phone=PHONE, contact_id=None, message_sid="SMqa1", text=disclosure.apply("Hi there", p1)))
    p2 = run(disclosure.plan(db, org=org, purpose="conversational", from_number="+18015550000", phone=PHONE, body="See you at 3"))
    assert p2["append"] is None and not p2["included"]
    p3 = run(disclosure.plan(db, org=org, purpose="marketing", from_number="+18015550000", phone=PHONE, body="Sale this week", campaign_key="qa"))
    assert p3["append"] and "HELP" in p3["append"]
    p4 = run(disclosure.plan(db, org=org, purpose="conversational", from_number="+18015550001", phone=PHONE, body="Reply STOP to opt out. Hi"))
    assert p4["already_in_body"] and p4["append"] is None


# ── duplicate-send protection ─────────────────────────────────────────────────

def test_send_ledger_claims_once():
    db = adb()
    assert run(send_ledger.claim(db, "qa-launch:1", to=PHONE))
    assert not run(send_ledger.claim(db, "qa-launch:1", to=PHONE))
    run(send_ledger.release(db, "qa-launch:1"))
    assert run(send_ledger.claim(db, "qa-launch:1", to=PHONE))


def test_broadcast_queues_each_recipient_once_across_replicas():
    db = adb()
    uid, cid, bid = ObjectId(), ObjectId(), ObjectId()
    CREATED["users"].append(uid)
    CREATED["contacts"].append(cid)
    CREATED["broadcasts"].append(bid)
    run(db.users.insert_one({"_id": uid, "name": "QA Launch Rep"}))
    run(db.contacts.insert_one({"_id": cid, "user_id": str(uid), "first_name": "QA", "phone": PHONE}))
    run(db.broadcasts.insert_one({"_id": bid, "created_by": str(uid), "status": "scheduled", "message": "Hi {first_name}", "recipients": [str(cid)]}))

    async def both():
        return await asyncio.gather(broadcast_queue.queue(db, str(bid), ("scheduled",)), broadcast_queue.queue(db, str(bid), ("scheduled",)))
    a, b = run(both())
    assert [a["claimed"], b["claimed"]].count(True) == 1
    assert run(db.campaign_pending_sends.count_documents({"broadcast_id": str(bid)})) == 1
    run(db.broadcasts.update_one({"_id": bid}, {"$set": {"status": "scheduled"}}))
    run(broadcast_queue.queue(db, str(bid), ("scheduled",)))
    assert run(db.campaign_pending_sends.count_documents({"broadcast_id": str(bid)})) == 1
    row = run(db.campaign_pending_sends.find_one({"broadcast_id": str(bid)}))
    assert row["purpose"] == "marketing" and row["message_template"] == "Hi QA"
