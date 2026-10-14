"""Stage 3 acceptance tests: simplified pilot onboarding against the live preview API.
Covers the pilot session flags, the five-step checklist auto-completing from real activity (and never regressing a stamp),
feedback categories with server-side account context, founder progress / activity / issue signals, legacy accounts untouched."""
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from tests.live_auth import ORG_ADMIN, REP, STORE_MANAGER, Session, anon, oid
from tests.wipe_pilot_customers import wipe
from tests import qa_creds

PREFIX = "QA Pilot S3"
OWNER_PASSWORD = qa_creds.password_for("qa-pilot-owner-ui@invalid.imonsocial.test")
STEP_KEYS = ["profile", "card", "contact", "share", "memo"]


def _phone():
    return f"+1500555{secrets.randbelow(9000) + 1000}"


@pytest.fixture(scope="module")
def customer(super_admin, mongo):
    """A pilot customer with an activated, signed-in owner (billing exception so no Stripe traffic)."""
    suffix = secrets.token_hex(3)
    body = {
        "business_name": f"{PREFIX} Co {suffix}", "city": "Sandy", "state": "UT", "zip": "84070", "industry": "Automotive / Dealership",
        "contact_name": f"Sam Stagethree{suffix}", "contact_email": f"qa-pilot-s3-{suffix}@invalid.imonsocial.test", "contact_phone": _phone(),
        "plan_key": "pilot_store_monthly", "seats_extra": 0, "pilot": True,
    }
    status, res = super_admin.post("/api/setup-wizard/new-account", body)
    assert status == 200, res
    org_id = res["organization_id"]
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    assert super_admin.post(f"/api/customers/{org_id}/billing-exception", {"reason": "Stage 3 QA", "expires_at": expires})[0] == 200
    assert super_admin.post(f"/api/customers/{org_id}/activate")[0] == 200
    assert super_admin.post(f"/api/customers/{org_id}/invite-owner")[0] == 200
    tok = mongo.password_reset_tokens.find_one({"user_id": res["user_id"], "purpose": "activate_link", "used": False})
    status, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    assert status == 200, swap
    status, done = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": OWNER_PASSWORD})
    assert status == 200, done
    for _ in range(10):
        if mongo.organizations.find_one({"_id": oid(org_id)})["customer"].get("owner_activated_at"):
            break
        time.sleep(0.5)
    owner = Session(body["contact_email"], OWNER_PASSWORD)
    yield {**res, "body": body, "owner": owner}
    wipe(mongo, PREFIX, dry_run=False)


# ── session flags ─────────────────────────────────────────────────────────────

def test_pilot_flags_ride_on_login(customer):
    status, me = anon("POST", "/api/auth/login", {"email": customer["body"]["contact_email"], "password": OWNER_PASSWORD})
    assert status == 200
    u = me["user"]
    assert u["pilot"] is True and u["pilot_owner"] is True and u["pilot_billing_status"] == "exception"
    assert u["role"] == "store_manager" and "temp_password" not in me


def test_legacy_accounts_carry_no_pilot_flags(store_manager, rep, org_admin):
    for who, creds in ((store_manager, STORE_MANAGER), (rep, REP), (org_admin, ORG_ADMIN)):
        status, me = anon("POST", "/api/auth/login", {"email": creds[0], "password": creds[1]})
        assert status == 200, who.email
        assert "pilot" not in me["user"] and "pilot_owner" not in me["user"], who.email
        assert who.get("/api/pilot/checklist")[0] == 404


# ── checklist ─────────────────────────────────────────────────────────────────

def test_checklist_starts_empty_with_five_steps(customer):
    status, body = customer["owner"].get("/api/pilot/checklist")
    assert status == 200, body
    assert [s["key"] for s in body["steps"]] == STEP_KEYS
    assert body["done"] == 0 and body["total"] == 5 and body["complete"] is False
    assert all(s["done"] is False and s["done_at"] is None for s in body["steps"])
    assert body["business_name"] == customer["body"]["business_name"]
    assert all(s["route"] for s in body["steps"]) and all(s["title"] and s["hint"] for s in body["steps"])


def test_steps_complete_from_real_activity_and_stamps_persist(customer, mongo):
    owner = customer["owner"]
    uid = customer["user_id"]

    # contact: through the real contacts API
    status, created = owner.post(f"/api/contacts/{uid}", {"first_name": "Casey", "last_name": "Checklist", "phone": _phone()})
    assert status in (200, 201), created
    body = owner.get("/api/pilot/checklist")[1]
    steps = {s["key"]: s for s in body["steps"]}
    assert steps["contact"]["done"] is True and steps["contact"]["done_at"]
    assert body["done"] == 1

    # share: the card share event the share sheet logs
    status, shared = owner.post(f"/api/contacts/{uid}/find-or-create-and-log", {"phone": _phone(), "name": "Shay Shared", "event_type": "digital_card_shared", "event_title": "Share My Card", "event_channel": "sms"})
    assert status == 200, shared
    steps = {s["key"]: s for s in owner.get("/api/pilot/checklist")[1]["steps"]}
    assert steps["share"]["done"] is True

    # memo: any voice note owned by the user (recorded through the voice-memos flow)
    mongo.voice_notes.insert_one({"user_id": uid, "kind": "memo", "transcript": "QA Stage 3 memo", "created_at": datetime.now(timezone.utc), "qa_stage3": True})
    steps = {s["key"]: s for s in owner.get("/api/pilot/checklist")[1]["steps"]}
    assert steps["memo"]["done"] is True

    # profile + card: photo, name, title, bio on the user record (what My Profile saves)
    mongo.users.update_one({"_id": oid(uid)}, {"$set": {"photo_url": "https://example.invalid/qa.jpg", "title": "Owner", "persona.bio": "QA bio"}})
    body = owner.get("/api/pilot/checklist")[1]
    assert body["done"] == 5 and body["complete"] is True
    stamps = mongo.users.find_one({"_id": oid(uid)}, {"pilot_checklist": 1})["pilot_checklist"]
    assert set(stamps) == set(STEP_KEYS) and all(stamps.values())

    # first-completion stamps never move once written
    first_contact_at = stamps["contact"]
    owner.post(f"/api/contacts/{uid}", {"first_name": "Second", "last_name": "Contact", "phone": _phone()})
    assert mongo.users.find_one({"_id": oid(uid)}, {"pilot_checklist": 1})["pilot_checklist"]["contact"] == first_contact_at


# ── feedback ──────────────────────────────────────────────────────────────────

def test_feedback_categories_and_server_side_context(customer, mongo):
    owner = customer["owner"]
    uid = customer["user_id"]
    for cat in ("question", "problem", "suggestion"):
        status, body = owner.post(f"/api/bug-reports/{uid}", {"category": cat, "description": f"QA Stage 3 {cat}", "platform": "pytest", "screen": "home"})
        assert status == 200, body
    status, body = owner.post(f"/api/bug-reports/{uid}", {"category": "<script>alert(1)</script>", "description": "QA Stage 3 weird category"})
    assert status == 200
    assert owner.post(f"/api/bug-reports/{uid}", {"category": "question", "description": "   "})[0] == 400
    rows = list(mongo.bug_reports.find({"user_id": uid}))
    assert sorted(r["category"] for r in rows) == ["other", "problem", "question", "suggestion"]
    for r in rows:
        assert r["pilot"] is True and r["organization_id"] == customer["organization_id"] and r["organization_name"] == customer["body"]["business_name"]
        assert r["status"] == "open" and r["user_name"] == customer["body"]["contact_name"]
    assert next(r for r in rows if r["category"] == "question")["screen"] == "home"


# ── founder view ──────────────────────────────────────────────────────────────

def test_founder_sees_progress_activity_and_issues(customer, super_admin, mongo):
    org_id = customer["organization_id"]
    status, row = super_admin.get(f"/api/customers/{org_id}")
    assert status == 200, row
    assert row["progress"]["done"] == 5 and row["progress"]["complete"] is True
    assert set(row["progress"]["steps"]) == set(STEP_KEYS) and all(v["done"] for v in row["progress"]["steps"].values())
    assert row["last_activity"]
    assert row["issues_open"] == 4
    assert len(row["issues"]) == 4 and {i["category"] for i in row["issues"]} == {"question", "problem", "suggestion", "other"}
    assert all(i["user_name"] and i["created_at"] and i["status"] == "open" for i in row["issues"])
    assert "4 open issues" in row["attention"]

    # the list carries the same signals (without the issue rows)
    status, rows = super_admin.get("/api/customers")
    mine = next(r for r in rows if r["organization_id"] == org_id)
    assert mine["progress"]["done"] == 5 and mine["issues_open"] == 4 and "issues" not in mine

    # resolving the issues clears the flag
    mongo.bug_reports.update_many({"user_id": customer["user_id"]}, {"$set": {"status": "resolved"}})
    row = super_admin.get(f"/api/customers/{org_id}")[1]
    assert row["issues_open"] == 0 and not any("open issue" in a for a in row["attention"])


def test_attention_flags_from_customer_state(super_admin, mongo):
    from services.pilot import attention
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=5)).isoformat()
    assert "Payment failed" in attention({"billing_status": "past_due"}, None, None, None, 0)
    assert "Payment link unpaid 3+ days" in attention({"billing_status": "awaiting_payment", "payment_link_sent_at": old}, None, None, None, 0)
    assert "Billing exception expired" in attention({"billing_status": "exception", "billing_exception": {"expires_at": (now - timedelta(days=1)).strftime("%Y-%m-%d")}}, None, None, None, 0)
    assert "Billing exception ends within a week" in attention({"billing_status": "exception", "billing_exception": {"expires_at": (now + timedelta(days=3)).strftime("%Y-%m-%d")}}, None, None, None, 0)
    assert "Owner has not activated (2+ days)" in attention({"owner_invited_at": old}, None, None, None, 0)
    assert "Owner not invited yet" in attention({"activated_at": old}, None, None, None, 0)
    stalled = attention({"owner_activated_at": old}, None, {"complete": False, "done": 2, "total": 5}, (now - timedelta(days=4)).isoformat(), 0)
    assert "Setup stalled at 2/5" in stalled
    quiet = attention({"owner_activated_at": (now - timedelta(days=20)).isoformat()}, None, {"complete": True}, (now - timedelta(days=9)).isoformat(), 0)
    assert "No activity for a week" in quiet
    assert attention({"billing_status": "active", "owner_activated_at": now.isoformat()}, None, {"complete": True}, now.isoformat(), 0) == []


def test_progress_hidden_until_owner_signs_in(super_admin, mongo):
    """A customer whose owner is still dormant shows no checklist progress (nothing to measure yet)."""
    status, rows = super_admin.get("/api/customers")
    assert status == 200
    dormant = [r for r in rows if r.get("owner") and r["owner"].get("dormant")]
    for r in dormant:
        assert r["progress"] is None, r["name"]


def test_legacy_org_rows_unchanged(super_admin, mongo):
    legacy = mongo.organizations.count_documents({"customer": {"$exists": False}})
    assert legacy > 0
    status, rows = super_admin.get("/api/customers")
    assert status == 200 and all("customer" in r and r["customer"] for r in rows)
