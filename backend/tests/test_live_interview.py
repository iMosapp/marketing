"""Onboarding interview on GPT-Live: the InterviewBridge (fake Twilio socket + fake GPT-Live upstream, real Mongo), the
TwiML gate (Test Lab flag `live_interview`, live by default) and the steering whisper after each rep answer."""
import asyncio
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import interview as iv  # noqa: E402
from services import lab  # noqa: E402
from services import live_interview as li  # noqa: E402
from services import live_shops as ls  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(__file__))
from test_live_shops import FakeUpstream, _ret, _wait  # noqa: E402

pytestmark = pytest.mark.asyncio


def _session(locale="en-US", **extra):
    now = datetime.now(timezone.utc)
    return {"_id": ObjectId(), "user_id": str(ObjectId()), "token": "tok" + str(ObjectId())[-6:], "rep_name": "Forest Ward", "rep_phone": "+15005550100", "from_number": "+15005550001",
            "store_name": "LHM Jeep", "role_title": "Sales Consultant", "locale": locale, "industry": "automotive", "status": "dialing", "turns": [], "covered": [], "created_at": now, "updated_at": now, **extra}


async def test_gate_and_twiml(monkeypatch):
    db = get_db()
    assert lab._default(li.LAB_KEY) == "live"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    s = _session()
    await db[iv.COLL].insert_one(s)
    try:
        on, why = await li.decide(db, s)
        assert on is True and why == "on for every English interview"
        on, why = await li.decide(db, {**s, "locale": "nl-NL"})
        assert on is False and "Dutch" in why
        xml = await li.twiml_for(db, s)
        assert '<Stream url="wss://' in xml and f'/api/interview/stream/{s["_id"]}/{s["token"]}" />' in xml and f'/api/interview/call/after/{s["_id"]}?t={s["token"]}' in xml
        assert "ConversationRelay" not in xml
        monkeypatch.setenv("OPENAI_API_KEY", "")
        on, why = await li.decide(db, s)
        assert on is False and why == ls.NO_KEY
        xml = await li.twiml_for(db, s)
        assert "ConversationRelay" in xml, "no key -> classic relay"
        row = await db[iv.COLL].find_one({"_id": s["_id"]})
        assert row["live_transport"] == "relay" and row["live_skip_reason"] == ls.NO_KEY
        assert iv.serialize(row)["live_skip_reason"] == ls.NO_KEY
    finally:
        await db[iv.COLL].delete_one({"_id": s["_id"]})


async def test_instructions():
    text = li.instructions(_session())
    assert "interviewing Forest, Sales Consultant at LHM Jeep" in text and "Hey Forest, it's Jessi from I'm On Social" in text
    assert "nickname:" in text and "texting:" in text and "Delegate to the backend exactly once" in text and "never coach" in text


async def test_bridge_interview_call(monkeypatch):
    db = get_db()
    s = _session()
    await db[iv.COLL].insert_one(s)
    up = FakeUpstream()
    twilio_out, closed = [], {"v": False}

    async def twilio_send(msg):
        twilio_out.append(msg)

    async def twilio_close():
        closed["v"] = True

    reads = []

    async def fake_llm_json(system, user, timeout=0, **k):
        reads.append(user)
        return {"covered": ["nickname"]}

    async def over(turns):
        return True

    monkeypatch.setattr(li, "_llm_json", fake_llm_json)
    monkeypatch.setattr(li, "STEER_DEBOUNCE_S", 0.05)
    monkeypatch.setattr(ls, "call_over", over)
    bridge = li.InterviewBridge(db, s, twilio_send, twilio_close, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZint1", "callSid": "CAint1"}})
        start = up.sent[0]
        assert start["type"] == "session.start" and start["session"]["model"] == "gpt-live-1" and start["session"]["audio"]["format"] == {"type": "audio/pcmu", "rate": 8000}
        assert "interviewing Forest" in start["session"]["instructions"]
        doc = await db[iv.COLL].find_one({"_id": s["_id"]})
        assert doc["status"] == "live" and doc["call_sid"] == "CAint1" and doc["live_transport"] == "gpt-live" and doc["live_voice"] == start["session"]["audio"]["output"]["voice"]

        await up.q.put({"type": "session.started", "session": {"id": "live_int_1"}})
        assert await _wait(lambda: "session.commentary.append" in up.types())
        opening = [e for e in up.sent if e["type"] == "session.instructions.append"][0]
        assert "Speak first, now" in opening["content"] and "Hey Forest, it's Jessi" in opening["content"]

        await up.q.put({"type": "session.output_audio.delta", "delta": "QUJD"})
        assert await _wait(lambda: any(m.get("event") == "media" for m in twilio_out))
        await bridge.on_twilio({"event": "media", "media": {"payload": "dGVzdA=="}})
        assert up.sent[-1] == {"type": "session.input_audio.append", "audio": "dGVzdA=="}

        # Jessi asks, the rep answers -> turns land as jessi/rep and a steering whisper follows the rep's answer
        await up.q.put({"type": "session.output_transcript.delta", "delta": "What do customers call you?", "start_ms": 1000, "end_ms": 2000})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "Everyone calls me Woody, I run the truck side.", "start_ms": 4000, "end_ms": 6000})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Woody, love it. How long have you been at it?", "start_ms": 8000, "end_ms": 9500})
        assert await _wait(lambda: any(str(e.get("event_id", "")).startswith("steer_") for e in up.sent), timeout=6)
        steer = [e for e in up.sent if str(e.get("event_id", "")).startswith("steer_")][-1]
        assert steer["type"] == "session.thinking.append" and steer["delegation_id"] is None
        assert "covered so far: nickname" in steer["content"] and "Still to cover:" in steer["content"] and "How long they have done this work" in steer["content"]
        assert reads and "Woody" in reads[0]
        doc = await db[iv.COLL].find_one({"_id": s["_id"]})
        assert [t["role"] for t in doc["turns"]] == ["jessi", "rep"] and doc["covered"] == ["nickname"]
        assert "mood" not in doc["turns"][0], "interview turns stay plain (no shop grader fields)"

        # a stray delegation before the goodbye is refused, the call keeps going
        monkeypatch.setattr(ls, "call_over", _not_over)
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_mid", "target": "client"}})
        assert await _wait(lambda: any(e.get("event_id") == "stay_item_mid" for e in up.sent))
        assert not bridge.closed and "Keep interviewing" in [e for e in up.sent if e.get("event_id") == "stay_item_mid"][0]["content"]

        # goodbye -> delegation -> hang up
        monkeypatch.setattr(ls, "call_over", over)
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Thanks Woody, your card is on its way. Bye!", "start_ms": 20000, "end_ms": 22000})
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_bye", "target": "client"}})
        await asyncio.wait_for(bridge.done.wait(), 15)
        bye = [e for e in up.sent if e.get("event_id") == "bye_item_bye"]
        assert bye and "disconnecting" in bye[0]["content"] and "session.close" in up.types() and closed["v"]
        doc = await db[iv.COLL].find_one({"_id": s["_id"]})
        assert doc["status"] == "ending" and doc["live_end_reason"] == "customer_ended" and doc["live_seconds"] == 61
        assert [t["role"] for t in doc["turns"]] == ["jessi", "rep", "jessi", "jessi"]
    finally:
        await bridge.close("test_cleanup")
        await db[iv.COLL].delete_one({"_id": s["_id"]})


async def _not_over(turns):
    return False


async def test_bridge_time_up_wraps(monkeypatch):
    db = get_db()
    s = _session()
    await db[iv.COLL].insert_one(s)
    up = FakeUpstream()

    async def noop(*a):
        pass

    monkeypatch.setattr(iv, "MAX_MINUTES", 0)
    monkeypatch.setattr(ls, "WRAP_GRACE_S", 1)
    bridge = li.InterviewBridge(db, s, noop, noop, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZint2", "callSid": "CAint2"}})
        await up.q.put({"type": "session.started", "session": {"id": "live_int_2"}})
        assert await _wait(lambda: any(e.get("event_id") == "wrap_1" for e in up.sent), timeout=5)
        assert "TIME IS UP" in [e for e in up.sent if e.get("event_id") == "wrap_1"][0]["content"]
        await asyncio.wait_for(bridge.done.wait(), 10)
        assert bridge.reason == "out_of_time"
        doc = await db[iv.COLL].find_one({"_id": s["_id"]})
        assert doc["status"] == "ending" and doc["live_end_reason"] == "out_of_time"
    finally:
        await bridge.close("test_cleanup")
        await db[iv.COLL].delete_one({"_id": s["_id"]})
