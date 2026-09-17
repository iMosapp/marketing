"""Mystery-shop calls on GPT-Live: the Twilio Media Streams <-> GPT-Live bridge with a fake Twilio socket and a fake
GPT-Live upstream (no OpenAI, no Twilio, real Mongo). Also the `live_calls` client override vs the Test Lab flag."""
import asyncio
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import lab  # noqa: E402
from services import live_shops as ls  # noqa: E402
from services import scripts as scr  # noqa: E402

pytestmark = pytest.mark.asyncio


def _session(client_id=None, direction="outbound", locale="en-US", **extra):
    return {"_id": ObjectId(), "token": "tok" + ObjectId().__str__()[-6:], "mode": "phone", "kind": "mystery_shop", "status": "dialing", "direction": direction,
            "locale": locale, "client_id": client_id, "script_id": str(ObjectId()), "rep_name": "Sam Seller", "store_name": "QA Jeep", "department": "sales",
            "persona": {"name": "Casey Morgan", "voice": "female", "opening_line": "Hi, I'm calling about the Wrangler you have online.", "summary": "Busy nurse, wants a Wrangler.",
                        "goals": "Out-the-door price and a test drive Saturday.", "objections": ["I saw it cheaper elsewhere"]},
            "turns": [], "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc), **extra}


class FakeUpstream:
    """Stands in for the GPT-Live websocket: records what the bridge sends, feeds it whatever the test queues."""

    def __init__(self):
        self.sent = []
        self.q: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send(self, ev):
        self.sent.append(ev)
        if ev.get("type") == "session.close":
            await self.q.put({"type": "session.closed", "reason": "close_requested", "usage": {"seconds": 61}})

    def __aiter__(self):
        return self

    async def __anext__(self):
        ev = await self.q.get()
        if ev is None:
            raise StopAsyncIteration
        return ev

    async def close(self):
        self.closed = True
        await self.q.put(None)

    def types(self):
        return [e.get("type") for e in self.sent]


async def _wait(cond, timeout=8.0):
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if cond():
            return True
        await asyncio.sleep(0.05)
    return False


async def test_enabled_client_override_and_lab_flag(monkeypatch):
    db = get_db()
    cid = (await db.shop_clients.insert_one({"name": "QA Live Shop Client", "live_calls": True, "created_at": datetime.now(timezone.utc)})).inserted_id
    try:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        assert await ls.enabled(db, _session(str(cid))) is True
        assert await ls.enabled(db, _session(str(cid), locale="nl-NL")) is False, "Dutch stays on ConversationRelay"
        await db.shop_clients.update_one({"_id": cid}, {"$set": {"live_calls": False}})
        assert await ls.enabled(db, _session(str(cid))) is False
        await db.shop_clients.update_one({"_id": cid}, {"$set": {"live_calls": None}})
        assert await ls.enabled(db, _session(str(cid))) == await lab.is_live(db, ls.LAB_KEY), "no override -> Test Lab flag decides"
        assert lab._default(ls.LAB_KEY) == "live", "GPT-Live is the default for English shops once the key is there"
        saved = ((await lab.statuses(db)).get(ls.LAB_KEY) or {}).get("status")
        try:
            await db.settings.update_one({"key": lab.SETTINGS_KEY}, {"$unset": {f"value.{ls.LAB_KEY}": ""}})
            on, why = await ls.decide(db, _session(str(cid)))
            assert on is True and why == "on for every English shop"
            st = await ls.status(db)
            assert st["on"] is True and st["configured"] is True and st["reason"] is None
        finally:
            if saved:
                await db.settings.update_one({"key": lab.SETTINGS_KEY}, {"$set": {f"value.{ls.LAB_KEY}.status": saved}}, upsert=True)
        monkeypatch.setenv("OPENAI_API_KEY", "")
        await db.shop_clients.update_one({"_id": cid}, {"$set": {"live_calls": True}})
        on, why = await ls.decide(db, _session(str(cid)))
        assert on is False and why == ls.NO_KEY, "no key -> never"
        st = await ls.status(db)
        assert st["on"] is False and st["reason"] == ls.NO_KEY
        s = _session(str(cid))
        await db.roleplay_sessions.insert_one(s)
        try:
            await ls.mark_relay(db, s, why)
            row = await db.roleplay_sessions.find_one({"_id": s["_id"]})
            assert row["live_transport"] == "relay" and row["live_skip_reason"] == ls.NO_KEY
        finally:
            await db.roleplay_sessions.delete_one({"_id": s["_id"]})
    finally:
        await db.shop_clients.delete_one({"_id": cid})


async def test_twiml_and_voice():
    s = _session()
    xml = ls.stream_twiml(s)
    assert xml.startswith('<?xml') and f'/api/scripts/roleplay/after/{s["_id"]}?t={s["token"]}' in xml
    assert f'<Stream url="wss://' in xml and f'/api/scripts/roleplay/stream/{s["_id"]}/{s["token"]}" />' in xml
    go = ls.shop_go_twiml(s)
    assert go.index("<Say") < go.index("<Play") < go.index("<Connect"), "heads-up, ring, then the live shopper"
    assert ls.voice_for(s) in ls.FEMININE
    assert ls.voice_for({**s, "persona": {**s["persona"], "voice": "male"}}) in ls.MASCULINE
    assert ls.voice_for({**s, "locale": "en-GB"}) in ls.UK_VOICES["female"]
    text = ls.instructions({"title": "Inbound sales", "purpose": "Set the appointment"}, s)
    assert "Casey Morgan" in text and "Sam" in text and "never admit you are an AI" in text and "Delegate to the backend exactly once" in text


async def test_bridge_full_call(monkeypatch):
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    twilio_out, closed = [], {"v": False}

    async def twilio_send(msg):
        twilio_out.append(msg)

    async def twilio_close():
        closed["v"] = True

    async def fake_over(turns):
        return True

    monkeypatch.setattr(ls, "call_over", fake_over)
    bridge = ls.Bridge(db, s, twilio_send, twilio_close, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZtest1", "callSid": "CAtest1"}})
        start = up.sent[0]
        assert start["type"] == "session.start" and start["session"]["model"] == "gpt-live-1"
        assert start["session"]["audio"] == {"format": {"type": "audio/pcmu", "rate": 8000}, "output": {"voice": ls.voice_for(s)}}
        assert start["session"]["delegation"] == {"type": "client"} and "Casey Morgan" in start["session"]["instructions"]
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "live" and doc["call_sid"] == "CAtest1" and doc["live_transport"] == "gpt-live"

        # audio before session.started is dropped
        await bridge.on_twilio({"event": "media", "media": {"payload": "early"}})
        assert "session.input_audio.append" not in up.types()

        await up.q.put({"type": "session.started", "session": {"id": "live_fake_1"}})
        assert await _wait(lambda: "session.commentary.append" in up.types())
        opening = [e for e in up.sent if e["type"] == "session.instructions.append"][0]
        assert "Wrangler" in opening["content"] and opening["delegation_id"] is None, "outbound: the shopper speaks first"
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["openai_session_id"] == "live_fake_1"

        await bridge.on_twilio({"event": "media", "media": {"payload": "dGVzdA=="}})
        assert up.sent[-1] == {"type": "session.input_audio.append", "audio": "dGVzdA=="}

        await up.q.put({"type": "session.output_audio.delta", "delta": "QUJD"})
        assert await _wait(lambda: any(m.get("event") == "media" for m in twilio_out))
        assert twilio_out[-1] == {"event": "media", "streamSid": "MZtest1", "media": {"payload": "QUJD"}}

        # transcript -> turns (same speaker within 1.5 s merges, a new speaker flushes)
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Hi, I'm calling about", "start_ms": 1000, "end_ms": 1800})
        await up.q.put({"type": "session.output_transcript.delta", "delta": " the Wrangler.", "start_ms": 1800, "end_ms": 2400})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "Sure, it's still here.", "start_ms": 4000, "end_ms": 5200})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Great, can I come Saturday?", "start_ms": 6000, "end_ms": 7200})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "Ten works. See you then.", "start_ms": 9000, "end_ms": 10200})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Perfect, bye.", "start_ms": 11000, "end_ms": 11800})
        await up.q.put({"type": "session.usage.updated", "usage": {"seconds": 40}})
        assert await _wait(lambda: bridge.seconds == 40)
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert [t["role"] for t in doc["turns"]] == ["customer", "rep", "customer", "rep"], "the last customer turn is still open"
        assert doc["turns"][0]["text"] == "Hi, I'm calling about the Wrangler." and doc["turns"][0]["mood"] == "neutral"

        # goodbye -> delegation -> hang up: thinking note, session.close, Twilio closed, status ending
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_bye", "target": "client"}})
        await asyncio.wait_for(bridge.done.wait(), 15)
        bye = [e for e in up.sent if e["type"] == "session.thinking.append"]
        assert bye and bye[0]["delegation_id"] == "item_bye" and "disconnecting" in bye[0]["content"]
        assert "session.close" in up.types() and up.closed and closed["v"]
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "ending" and doc["live_end_reason"] == "customer_ended"
        assert doc["live_seconds"] == 61 and doc["live_cost_usd"] == round(61 / 60 * 0.05, 4), "final usage comes from session.closed"
        assert [t["role"] for t in doc["turns"]] == ["customer", "rep", "customer", "rep", "customer"] and doc["turns"][-1]["text"] == "Perfect, bye."

        # the router's finally -> finalize_session grades once (rep spoke)
        graded = {}

        async def fake_grade(db_, sess):
            graded["id"] = str(sess["_id"])
            return {"ok": True}

        monkeypatch.setattr(scr, "grade_session", fake_grade)
        await scr.finalize_session(db, str(s["_id"]), "websocket_closed")
        assert graded.get("id") == str(s["_id"])
        assert await scr.finalize_session(db, str(s["_id"]), "call_completed") is None, "second finalize is a no-op"
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "grading" and doc["end_reason"] == "websocket_closed"
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_bridge_inbound_nudge_and_no_delegation_before_goodbye(monkeypatch):
    """Inbound (rep called the shopper back): no scripted first line, the rep speaks first; a stray delegation mid-call is refused."""
    db = get_db()
    s = _session(direction="inbound")
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()

    async def noop(*a):
        pass

    async def not_over(turns):
        return False

    monkeypatch.setattr(ls, "call_over", not_over)
    monkeypatch.setattr(ls, "INBOUND_NUDGE_S", 1)
    bridge = ls.Bridge(db, s, noop, noop, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZtest2", "callSid": "CAtest2"}})
        await up.q.put({"type": "session.started", "session": {"id": "live_fake_2"}})
        await asyncio.sleep(0.3)
        assert "session.commentary.append" not in up.types(), "inbound waits for the rep to answer"
        assert await _wait(lambda: any(e.get("event_id") == "nudge_1" for e in up.sent), timeout=4), "nobody spoke: nudge with the opening line"
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_mid", "target": "client"}})
        assert await _wait(lambda: any(e.get("event_id") == "stay_item_mid" for e in up.sent))
        assert not bridge.closed
        await bridge.on_twilio({"event": "stop"})
        assert bridge.closed and bridge.reason == "twilio_stop"
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "live", "Twilio stop is not the shopper ending: finalize_session decides"
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_bridge_upstream_failure():
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    closed = {"v": False}

    async def noop(*a):
        pass

    async def twilio_close():
        closed["v"] = True

    async def boom():
        raise RuntimeError("401 invalid api key")

    bridge = ls.Bridge(db, s, noop, twilio_close, connect=boom)
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZtest3", "callSid": "CAtest3"}})
        assert bridge.closed and bridge.reason == "upstream_failed" and closed["v"]
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert "401" in doc["live_error"] and doc["live_end_reason"] == "upstream_failed"
    finally:
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def _ret(x):
    return x
