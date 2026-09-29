"""Dead air never lasts: a GPT-Live session that never starts or never speaks is cut within seconds, and a stalled shop rings back."""
import asyncio
import os
import pytest
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import live_shops as ls  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from tests.test_live_shops import FakeUpstream, _session, _wait, _ret  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _noop(*a):
    pass


async def test_no_session_started_is_cut(monkeypatch):
    monkeypatch.setattr(ls, "READY_DEADLINE_S", 1.0)
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    bridge = ls.Bridge(db, s, _noop, _noop, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZstall1", "callSid": "CAstall1"}})
        assert await _wait(lambda: bridge.closed, timeout=6)
        assert bridge.reason == "no_session"
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["live_end_reason"] == "no_session"
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_started_but_silent_is_cut(monkeypatch):
    monkeypatch.setattr(ls, "FIRST_VOICE_S", 1.0)
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    bridge = ls.Bridge(db, s, _noop, _noop, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZstall2", "callSid": "CAstall2"}})
        await up.q.put({"type": "session.started", "session": {"id": "live_silent"}})
        assert await _wait(lambda: bridge.ready)
        assert await _wait(lambda: bridge.closed, timeout=6)
        assert bridge.reason == "no_voice"
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_speaking_session_is_not_cut(monkeypatch):
    monkeypatch.setattr(ls, "FIRST_VOICE_S", 1.0)
    monkeypatch.setattr(ls, "READY_DEADLINE_S", 1.0)
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    bridge = ls.Bridge(db, s, _noop, _noop, connect=lambda: _ret(up))
    try:
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZok", "callSid": "CAok"}})
        await up.q.put({"type": "session.started", "session": {"id": "live_ok"}})
        assert await _wait(lambda: bridge.ready)
        await up.q.put({"type": "session.output_audio.delta", "delta": "AAAA"})
        await asyncio.sleep(2.5)
        assert not bridge.closed
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_stalled_shop_rings_back_then_gives_up(monkeypatch):
    fired = []

    async def fake_ring_later(sid, delay):
        fired.append((sid, delay))
    monkeypatch.setattr(ms, "ring_later", fake_ring_later)
    db = get_db()
    s = {**_session(), "live_end_reason": "no_voice", "status": "ending", "attempts": 1}
    await db.roleplay_sessions.insert_one(s)
    try:
        for n in (1, 2, 3):
            call = await db.roleplay_sessions.find_one({"_id": s["_id"]})
            assert await ms.retry_after_stall(db, {**call, "live_end_reason": "no_voice"}) == 2
            doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
            assert doc["status"] == "scheduled" and doc["stall_retries"] == n and doc["turns"] == [] and doc["ready_only"] is False
            assert timedelta(seconds=100) < (doc["scheduled_for"] - ms._now().replace(tzinfo=None)) <= timedelta(seconds=121)
        assert len(fired) == 3 and fired[0][1] == 120
        call = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert await ms.retry_after_stall(db, {**call, "live_end_reason": "no_voice"}) == 0
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["status"] == "unreachable" and "3 tries" in doc["fail_reason"]
    finally:
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})
