"""Twilio final status + SipResponseCode 603/607/608 -> 'carrier spam filter declined' instead of 'busy' (practice + mystery shop), toll-free hint."""
import asyncio
import os
import uuid
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import scripts as scr

API = os.environ.get("TEST_API_URL", "http://localhost:8001").rstrip("/")


def test_helpers():
    assert scr.failure_key("busy", "603") == "declined"
    assert scr.failure_key("failed", "607") == "carrier_declined"
    assert scr.failure_key("busy", "608") == "carrier_declined"
    assert scr.failure_key("busy", None) == "busy"
    assert scr.failure_key("no-answer", "486") == "no-answer"
    assert scr.toll_free("+18445550100") and scr.toll_free("(800) 555-0100") and scr.toll_free("18885550100")
    assert not scr.toll_free("+14352203414") and not scr.toll_free("+18015550100") and not scr.toll_free("")
    assert scr.fail_label("busy", "+18445550100") == "Your phone was busy"
    assert "toll-free" in scr.fail_label("carrier_declined", "+18445550100") and "toll-free" not in scr.fail_label("carrier_declined", "+14355550100")


async def _seed(db, **extra):
    now = datetime.now(timezone.utc)
    doc = {"user_id": "qa", "rep_name": "QA Rep", "rep_phone": "+15005550006", "from_number": "+18445550100", "mode": "phone", "status": "dialing", "token": uuid.uuid4().hex,
           "call_sid": "CA_test_" + uuid.uuid4().hex[:8], "turns": [], "started_at": now, "updated_at": now, "script_id": str(ObjectId()), "qa_carrier_decline": True, **extra}
    res = await db.roleplay_sessions.insert_one(doc)
    return await db.roleplay_sessions.find_one({"_id": res.inserted_id})


async def _status(s, **form):
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API}/api/scripts/roleplay/status/{s['_id']}", params={"t": s["token"]}, data={"CallSid": s["call_sid"], **form})
    assert r.status_code == 204, r.text


def test_status_webhook_maps_sip_codes():
    asyncio.run(_run_webhook_cases())


async def _run_webhook_cases():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    try:
        practice = await _seed(db)
        await _status(practice, CallStatus="busy", SipResponseCode="603")
        p = await db.roleplay_sessions.find_one({"_id": practice["_id"]})
        assert p["status"] == "failed" and p["sip_code"] == "603"
        assert p["fail_reason"].startswith("Declined before it rang") and "toll-free" in p["fail_reason"], p["fail_reason"]

        control = await _seed(db, from_number="+14355550100")
        await _status(control, CallStatus="busy")
        c = await db.roleplay_sessions.find_one({"_id": control["_id"]})
        assert c["status"] == "failed" and c["fail_reason"] == "Your phone was busy" and c.get("sip_code") is None

        shop = await _seed(db, kind="mystery_shop", client_id=str(ObjectId()), manual=True, attempts=1)
        await _status(shop, CallStatus="failed", SipResponseCode="607", ErrorCode="31607")
        m = await db.roleplay_sessions.find_one({"_id": shop["_id"]})
        assert m["status"] == "unreachable" and m["outcome"] == "carrier_declined", m
        assert m["fail_reason"].startswith("Carrier spam filter declined the call") and "toll-free" in m["fail_reason"], m["fail_reason"]
        assert m["attempt_history"][-1]["outcome"] == "carrier_declined" and m["attempt_history"][-1]["sip_code"] == "607"
    finally:
        await db.roleplay_sessions.delete_many({"qa_carrier_decline": True})
