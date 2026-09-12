"""Lead flow: (1) "text first, ring later" honours ring_delay_seconds; (2) a returning customer with no sale and nothing
happening for N days is reopened to the team instead of routed straight to their rep.
Run: cd /app/backend && python -m pytest tests/test_returning_reopen_ring_delay.py -q"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
REP_ID = "6a978d68b8673c29063aa8b9"  # activation-tester
LOOP = asyncio.new_event_loop()


def _run(coro):
    return LOOP.run_until_complete(coro)


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def test_verdict_rules():
    from routers.lead_intake import returning_owner_verdict
    now = datetime.now(timezone.utc)

    async def run():
        db = _db()
        base = {"first_name": "Quiet", "last_name": "Customer", "phone": "+15005550199", "user_id": REP_ID, "store_id": "x", "created_at": now - timedelta(days=80), "vt_test": True}
        c_quiet = await db.contacts.insert_one({**base})
        c_sold = await db.contacts.insert_one({**base, "tags": ["Sold"]})
        c_fresh = await db.contacts.insert_one({**base, "created_at": now - timedelta(days=3)})
        c_texted = await db.contacts.insert_one({**base})
        conv = await db.conversations.insert_one({"user_id": REP_ID, "contact_id": str(c_texted.inserted_id), "status": "active", "created_at": now - timedelta(days=70), "last_message_at": now - timedelta(days=70), "vt_test": True})
        msg = await db.messages.insert_one({"conversation_id": str(conv.inserted_id), "sender": "user", "content": "hi", "timestamp": now - timedelta(days=12), "vt_test": True})
        try:
            quiet = await returning_owner_verdict(db, await db.contacts.find_one({"_id": c_quiet.inserted_id}), REP_ID, 30, now)
            assert quiet["reopen"] is True and quiet["reason"] == "quiet" and quiet["quiet_days"] == 80
            sold = await returning_owner_verdict(db, await db.contacts.find_one({"_id": c_sold.inserted_id}), REP_ID, 30, now)
            assert sold == {"reopen": False, "reason": "sold", "quiet_days": None}
            fresh = await returning_owner_verdict(db, await db.contacts.find_one({"_id": c_fresh.inserted_id}), REP_ID, 30, now)
            assert fresh["reopen"] is False and fresh["reason"] == "engaged" and fresh["quiet_days"] == 3
            texted = await returning_owner_verdict(db, await db.contacts.find_one({"_id": c_texted.inserted_id}), REP_ID, 30, now)
            assert texted["reopen"] is False and texted["quiet_days"] == 12
            # a 7-day rule would reopen that same texted customer
            assert (await returning_owner_verdict(db, await db.contacts.find_one({"_id": c_texted.inserted_id}), REP_ID, 7, now))["reopen"] is True
        finally:
            await db.contacts.delete_many({"vt_test": True})
            await db.conversations.delete_many({"vt_test": True})
            await db.messages.delete_many({"vt_test": True})
    _run(run())


def test_ring_delay_job_waits_for_scheduler():
    from services import lead_call_engine as eng

    async def run():
        db = _db()
        source = {"_id": ObjectId(), "name": "Delay Test", "contact_mode": "text_and_call", "ring_delay_seconds": 30,
                  "call_attempts": [{"user_ids": [REP_ID], "delay_seconds": 0, "delivery": "call"}], "workflow_user_ids": [REP_ID]}
        conv_id = str(ObjectId())
        try:
            job_id = await eng.start_call_workflow(source, conv_id, str(ObjectId()), "+15005550177", {"name": "Delay Test"})
            job = await db.lead_call_jobs.find_one({"_id": ObjectId(job_id)})
            assert job["status"] == "active" and job["attempt_index"] == 0 and job["ring_delay_seconds"] == 30 and not job["deferred"]
            wait = (job["next_attempt_at"].replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
            assert 20 < wait <= 31 and job["calls"] == []  # nothing dialed yet; the 15s tick fires it after the delay
            # without a delay the job is created with the 30s double-ring guard and attempt 1 is dispatched immediately (calls populated async)
            src2 = {**source, "_id": ObjectId(), "ring_delay_seconds": 0}
            conv2 = str(ObjectId())
            job2_id = await eng.start_call_workflow(src2, conv2, str(ObjectId()), "+15005550177", {"name": "Instant"})
            await asyncio.sleep(2.5)
            job2 = await db.lead_call_jobs.find_one({"_id": ObjectId(job2_id)})
            assert "ring_delay_seconds" not in job2 and (job2["attempt_index"] == 1 or job2["calls"])
        finally:
            await db.lead_call_jobs.delete_many({"conversation_id": {"$in": [conv_id, locals().get("conv2", "")]}})
    _run(run())


def test_flow_settings_roundtrip_and_summary():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER, timeout=20)
    hdr = {"Authorization": f"Bearer {r.json()['token']}"}
    body = {"name": "Reopen test flow", "contact_mode": "text_and_call", "call_attempts": [{"user_ids": [REP_ID], "delay_seconds": 0, "delivery": "call"}],
            "ring_delay_seconds": 30, "returning_stale_days": 45, "intake_text": "Hi {{first_name}}"}
    created = requests.post(f"{BASE_URL}/api/lead-flows", json=body, headers=hdr, timeout=20)
    assert created.status_code in (200, 201), created.text
    flow = created.json()
    fid = flow["id"]
    try:
        assert flow["ring_delay_seconds"] == 30 and flow["returning_stale_days"] == 45
        texts = " | ".join(r["text"] for r in flow["summary"])
        assert "ring 30s later" in texts and "quiet 45+ days" in texts
        upd = requests.put(f"{BASE_URL}/api/lead-flows/{fid}", json={"ring_delay_seconds": 999, "returning_stale_days": 0}, headers=hdr, timeout=20).json()
        assert upd["ring_delay_seconds"] == 300 and upd["returning_stale_days"] == 0
        assert "always straight to their rep" in " | ".join(r["text"] for r in upd["summary"])
    finally:
        requests.delete(f"{BASE_URL}/api/lead-flows/{fid}?force=true", headers=hdr, timeout=20)
