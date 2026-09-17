"""Shop-call guards after a lost Twilio callback: a stuck 'live' shop is checked with Twilio before it blocks a new one, and the
Twilio webhooks never answer with a 5xx ('application error') even when something inside them breaks."""
import os
import types
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from routers import scripts as rs  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services import scripts as scr  # noqa: E402
from services import lead_call_engine as lce  # noqa: E402

pytestmark = pytest.mark.asyncio


def _session(status="live", minutes_ago=5, **extra):
    now = datetime.now(timezone.utc)
    oid = ObjectId()
    return {"_id": oid, "token": "tokguard", "mode": "phone", "kind": "mystery_shop", "status": status, "direction": "outbound", "locale": "en-US",
            "client_id": str(ObjectId()), "script_id": str(ObjectId()), "rep_name": "Sam Seller", "rep_phone": "+1500555" + str(int(str(oid)[-4:], 16) % 10000).zfill(4), "target_id": str(ObjectId()),
            "store_name": "QA Jeep", "department": "sales", "call_sid": "CAguard1", "demo": True, "manual": True, "attempts": 1,
            "persona": {"name": "Casey Morgan", "voice": "female", "opening_line": "Hi there.", "summary": "x", "goals": "y", "objections": []},
            "turns": [], "started_at": now - timedelta(minutes=minutes_ago), "created_at": now - timedelta(minutes=minutes_ago), "updated_at": now - timedelta(minutes=minutes_ago), **extra}


class FakeTwilio:
    def __init__(self, status):
        self.status = status

    def calls(self, sid):
        return types.SimpleNamespace(fetch=lambda: types.SimpleNamespace(status=self.status, sid=sid))


class FakeRequest:
    def __init__(self, **form):
        self._form = form

    async def form(self):
        return self._form


async def test_busy_with_clears_a_stuck_live_shop(monkeypatch):
    """The hang-up callback never landed (deploy/restart): Twilio says the call is over, so the next Shop now goes through."""
    db = get_db()
    s = _session("live", minutes_ago=6)
    await db.roleplay_sessions.insert_one(s)
    monkeypatch.setattr(lce, "_twilio_client", lambda: FakeTwilio("completed"))
    try:
        assert await ms.busy_with(db, {"rep_phone": s["rep_phone"], **ms.mode_q("phone")}) is None
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "unreachable" and doc["outcome"] == "hung_up" and doc["call_status"] == "completed"
    finally:
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_busy_with_keeps_a_real_live_call(monkeypatch):
    db = get_db()
    s = _session("live", minutes_ago=3)
    await db.roleplay_sessions.insert_one(s)
    monkeypatch.setattr(lce, "_twilio_client", lambda: FakeTwilio("in-progress"))
    try:
        busy = await ms.busy_with(db, {"rep_phone": s["rep_phone"], **ms.mode_q("phone")})
        assert busy and busy["status"] == "live"
        assert ms.busy_label(busy, "Sam", "phone") == "Sam is already on a shop call (started 3 min ago)"
        assert "graded" in ms.busy_label({**busy, "status": "grading"}, "Sam", "phone")
        # a fresh call (under 30 s) is never questioned, and when Twilio cannot be asked the stuck row keeps blocking (no accidental double dial)
        fresh = _session("dialing", minutes_ago=0)
        await db.roleplay_sessions.insert_one(fresh)
        monkeypatch.setattr(lce, "_twilio_client", lambda: None)
        assert (await ms.busy_with(db, {"rep_phone": fresh["rep_phone"], **ms.mode_q("phone")}))["_id"] == fresh["_id"]
        assert (await ms.busy_with(db, {"rep_phone": s["rep_phone"], **ms.mode_q("phone")}))["_id"] == s["_id"]
        await db.roleplay_sessions.delete_one({"_id": fresh["_id"]})
    finally:
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_gate_falls_back_to_relay_when_live_shop_check_breaks(monkeypatch):
    db = get_db()
    s = _session("dialing", minutes_ago=0)
    await db.roleplay_sessions.insert_one(s)
    from services import live_shops

    async def boom(db_, sess):
        raise RuntimeError("lab lookup exploded")

    monkeypatch.setattr(live_shops, "enabled", boom)
    try:
        r = await rs.relay_gate(str(s["_id"]), s["token"], FakeRequest(Digits="1"))
        body = r.body.decode()
        assert r.status_code == 200 and "<ConversationRelay" in body and "ring.wav" in body, "classic shopper, no 500"
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["gate_via"] == "dtmf" and doc["status"] == "dialing"
    finally:
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_webhooks_never_answer_500(monkeypatch):
    """Anything unexpected inside /twiml, /gate or /after becomes a spoken sorry + hangup and parks the shop with the reason."""
    db = get_db()
    s = _session("dialing", minutes_ago=0)
    await db.roleplay_sessions.insert_one(s)

    def broken(*a, **k):
        raise KeyError("persona")

    try:
        monkeypatch.setattr(scr, "shop_go_twiml", broken)
        r = await rs.relay_gate(str(s["_id"]), s["token"], FakeRequest(Digits="1"))
        body = r.body.decode()
        assert r.status_code == 200 and "the practice line had a problem" in body and "<Hangup/>" in body
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "unreachable" and doc["fail_reason"] == "The line had a problem (KeyError)", "parked, so the next Shop now is not blocked"

        s2 = _session("dialing", minutes_ago=0)
        await db.roleplay_sessions.insert_one(s2)
        monkeypatch.setattr(scr, "shop_gate_twiml", broken)
        r = await rs.relay_twiml(str(s2["_id"]), s2["token"], FakeRequest())
        assert r.status_code == 200 and "<Hangup/>" in r.body.decode()
        await db.roleplay_sessions.delete_one({"_id": s2["_id"]})

        s3 = _session("dialing", minutes_ago=0)
        await db.roleplay_sessions.insert_one(s3)
        monkeypatch.setattr(scr, "failure_key", broken)
        r = await rs.relay_status(str(s3["_id"]), s3["token"], FakeRequest(CallStatus="busy"))
        assert r.status_code == 204, "status bookkeeping errors are logged, never returned"
        await db.roleplay_sessions.delete_one({"_id": s3["_id"]})
    finally:
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})
