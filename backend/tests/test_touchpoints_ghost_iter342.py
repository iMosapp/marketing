"""
Iter 342: Touchpoints ghost-task fix + Sold wizard scheduled sends + Wallet guards.
Covers:
 - GET /api/tasks/{user_id}?filter=today does NOT create task for automated Direct Send
 - Self-heal: inserted stale campaign_send task auto-completes with completed_via
 - GET /api/messages/scheduled/{uid}/{cid} auth (200 self, 403 other user, 401 anon)
 - Wallet guards: status false/false, download-token 503, google-save-url 503
"""
import os
import time
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ACT_USER_ID = "6a978d68b8673c29063aa8b9"
ACT_CONTACT_ID = "6aa413008f0d53e3f2261853"
ACT_EMAIL = "activation-tester@invalid.imonsocial.test"
ACT_PASSWORD = "NewPass123!"
OTHER_EMAIL = "mjeast1985@gmail.com"
OTHER_PASSWORD = "NavyBean1!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text[:300]}"
    j = r.json()
    return j["token"], j["user"]["_id"]


@pytest.fixture(scope="module")
def act_token():
    tok, uid = _login(ACT_EMAIL, ACT_PASSWORD)
    assert uid == ACT_USER_ID, f"Expected user id {ACT_USER_ID} got {uid}"
    return tok


@pytest.fixture(scope="module")
def other_token():
    tok, _ = _login(OTHER_EMAIL, OTHER_PASSWORD)
    return tok


@pytest.fixture(scope="module")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ── Test 1: automated direct send does NOT create a task ─────────────────────
@pytest.mark.asyncio
async def test_automated_direct_send_no_ghost_task(act_token, db):
    # Queue an automated direct send (delay_seconds=0)
    r = requests.post(
        f"{BASE_URL}/api/messages/schedule-delayed",
        headers=_headers(act_token),
        json={
            "user_id": ACT_USER_ID,
            "to": "+15005550042",
            "body": "QA_T Hi ghost check",
            "delay_seconds": 0,
            "contact_id": ACT_CONTACT_ID,
            "contact_name": "Sarah Tester",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    pending_id = r.json()["pending_send_id"]
    print(f"[T1] queued pending_send_id={pending_id}")

    try:
        # Call tasks?filter=today
        r2 = requests.get(f"{BASE_URL}/api/tasks/{ACT_USER_ID}?filter=today",
                          headers=_headers(act_token), timeout=30)
        assert r2.status_code == 200, r2.text
        # Give catchup a beat to run (it's already awaited synchronously, but be safe)
        await asyncio.sleep(1)

        cnt = await db.tasks.count_documents({"pending_send_id": pending_id})
        assert cnt == 0, f"Ghost task created for automated send! count={cnt}"
        print("[T1] PASS: no ghost task for automated direct send")
    finally:
        await db.campaign_pending_sends.delete_one({"_id": ObjectId(pending_id)})


# ── Test 2: Self-heal existing ghost task (auto_sent + send_cancelled) ─────
@pytest.mark.asyncio
async def test_selfheal_ghost_tasks(act_token, db):
    now = datetime.now(timezone.utc)

    # Case A: auto_sent — pending send with delivery_mode=automated, status=sent
    send_a = {
        "user_id": ACT_USER_ID,
        "contact_id": ACT_CONTACT_ID,
        "contact_name": "Sarah Tester",
        "contact_phone": "+15005550042",
        "message_template": "QA auto sent",
        "channel": "sms",
        "delivery_mode": "automated",
        "status": "sent",
        "type": "direct_scheduled",
        "send_at": now.replace(tzinfo=None) - timedelta(minutes=5),
        "created_at": now,
        "processed_at": now,
    }
    send_a_id = (await db.campaign_pending_sends.insert_one(send_a)).inserted_id

    task_a = {
        "user_id": ACT_USER_ID,
        "type": "campaign_send",
        "status": "pending",
        "completed": False,
        "pending_send_id": str(send_a_id),
        "title": "QA ghost autosent",
        "due_date": now,
        "created_at": now,
        "idempotency_key": f"qa_ghost_a_{uuid.uuid4().hex}",
    }
    task_a_id = (await db.tasks.insert_one(task_a)).inserted_id

    # Case B: send_cancelled — manual send, status=cancelled
    send_b = {
        "user_id": ACT_USER_ID,
        "contact_id": ACT_CONTACT_ID,
        "contact_name": "Sarah Tester",
        "contact_phone": "+15005550042",
        "message_template": "QA cancelled",
        "channel": "sms",
        "delivery_mode": "manual",
        "status": "cancelled",
        "type": "direct_scheduled",
        "send_at": now.replace(tzinfo=None) - timedelta(minutes=5),
        "created_at": now,
    }
    send_b_id = (await db.campaign_pending_sends.insert_one(send_b)).inserted_id

    task_b = {
        "user_id": ACT_USER_ID,
        "type": "campaign_send",
        "status": "pending",
        "completed": False,
        "pending_send_id": str(send_b_id),
        "title": "QA ghost cancelled",
        "due_date": now,
        "created_at": now,
        "idempotency_key": f"qa_ghost_b_{uuid.uuid4().hex}",
    }
    task_b_id = (await db.tasks.insert_one(task_b)).inserted_id

    # Bypass 90s throttle from prior test — clear the memo
    try:
        from routers.tasks import _catchup_last_run  # type: ignore
        _catchup_last_run.pop(ACT_USER_ID, None)
    except Exception:
        pass
    # The backend runs in a separate process, so clearing local memo does nothing.
    # Wait past the 90s throttle window.
    print("[T2] waiting 95s for catchup throttle to expire...")
    await asyncio.sleep(95)

    try:
        r = requests.get(f"{BASE_URL}/api/tasks/{ACT_USER_ID}?filter=today",
                         headers=_headers(act_token), timeout=30)
        assert r.status_code == 200, r.text
        await asyncio.sleep(1.5)

        ta = await db.tasks.find_one({"_id": task_a_id})
        tb = await db.tasks.find_one({"_id": task_b_id})
        print(f"[T2a] task_a status={ta.get('status')} completed_via={ta.get('completed_via')}")
        print(f"[T2b] task_b status={tb.get('status')} completed_via={tb.get('completed_via')}")

        assert ta.get("status") == "completed"
        assert ta.get("completed_via") == "auto_sent"
        assert tb.get("status") == "completed"
        assert tb.get("completed_via") == "send_cancelled"
    finally:
        await db.tasks.delete_many({"_id": {"$in": [task_a_id, task_b_id]}})
        await db.campaign_pending_sends.delete_many({"_id": {"$in": [send_a_id, send_b_id]}})


# ── Test 3: scheduled messages endpoint auth ────────────────────────────────
@pytest.mark.asyncio
async def test_scheduled_messages_endpoint(act_token, other_token, db):
    # Queue a pending send with delay 600s so it stays pending
    r = requests.post(
        f"{BASE_URL}/api/messages/schedule-delayed",
        headers=_headers(act_token),
        json={
            "user_id": ACT_USER_ID,
            "to": "+15005550042",
            "body": "QA_T scheduled row test",
            "delay_seconds": 600,
            "contact_id": ACT_CONTACT_ID,
            "contact_name": "Sarah Tester",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    pending_id = r.json()["pending_send_id"]

    try:
        # Self — 200
        r_self = requests.get(
            f"{BASE_URL}/api/messages/scheduled/{ACT_USER_ID}/{ACT_CONTACT_ID}",
            headers=_headers(act_token), timeout=30,
        )
        assert r_self.status_code == 200, r_self.text
        rows = r_self.json()
        assert isinstance(rows, list)
        assert any(row.get("id") == pending_id for row in rows), f"Queued send not in list: {rows}"
        row = next(r for r in rows if r["id"] == pending_id)
        for k in ("id", "body", "status", "send_at", "sent_at", "event_type", "has_media", "error"):
            assert k in row, f"Missing key {k} in row {row}"
        assert row["status"] == "pending"
        assert row["body"].startswith("QA_T")
        print(f"[T3] self row keys ok, status={row['status']}")

        # Other user — 403
        r_other = requests.get(
            f"{BASE_URL}/api/messages/scheduled/{ACT_USER_ID}/{ACT_CONTACT_ID}",
            headers=_headers(other_token), timeout=30,
        )
        assert r_other.status_code == 403, f"Expected 403 got {r_other.status_code} {r_other.text[:200]}"

        # Unauth — 401
        r_anon = requests.get(
            f"{BASE_URL}/api/messages/scheduled/{ACT_USER_ID}/{ACT_CONTACT_ID}", timeout=30,
        )
        assert r_anon.status_code == 401, f"Expected 401 got {r_anon.status_code}"
        print("[T3] PASS: 200/403/401 auth ok")
    finally:
        await db.campaign_pending_sends.delete_one({"_id": ObjectId(pending_id)})


# ── Test 4: wallet guards ────────────────────────────────────────────────────
def test_wallet_guards(act_token):
    h = _headers(act_token)
    r_status = requests.get(f"{BASE_URL}/api/wallet/{ACT_USER_ID}/status", headers=h, timeout=30)
    assert r_status.status_code == 200, r_status.text
    body = r_status.json()
    assert body.get("apple") is False, f"apple should be False: {body}"
    assert body.get("google") is False, f"google should be False: {body}"

    r_tok = requests.post(f"{BASE_URL}/api/wallet/{ACT_USER_ID}/download-token", headers=h, timeout=30)
    assert r_tok.status_code == 503, f"download-token expected 503 got {r_tok.status_code} {r_tok.text[:200]}"

    r_gsu = requests.get(f"{BASE_URL}/api/wallet/{ACT_USER_ID}/google-save-url", headers=h, timeout=30)
    assert r_gsu.status_code == 503, f"google-save-url expected 503 got {r_gsu.status_code} {r_gsu.text[:200]}"
    print("[T4] PASS wallet guards")
