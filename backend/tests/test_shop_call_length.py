"""Practice shops run long enough: no fragment-count cut-off, a 20-minute ceiling, no early goodbye before SHOP_MIN_MINUTES
unless the rep ends it, and the out-of-time hang-up lets the goodbye finish (fake GPT-Live upstream, real Mongo)."""
import asyncio
import os
import pytest
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import live_shops as ls  # noqa: E402
from services import scripts as scr  # noqa: E402
from tests.test_live_shops import FakeUpstream, _session, _wait, _ret  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _noop(*a):
    pass


async def _live_bridge(db, s, up, monkeypatch, over=False):
    async def call_over(turns):
        return over
    monkeypatch.setattr(ls, "call_over", call_over)
    bridge = ls.Bridge(db, s, _noop, _noop, connect=lambda: _ret(up))
    await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZlen", "callSid": "CAlen"}})
    await up.q.put({"type": "session.started", "session": {"id": "live_len"}})
    await _wait(lambda: bridge.ready)
    return bridge


async def test_ceilings():
    assert scr.PHONE_MAX_MINUTES == 20
    assert scr.CALL_TIME_LIMIT_S == 23 * 60
    assert ls.SHOP_MIN_MINUTES == 10
    assert ls.WRAP_GRACE_S >= 40


async def test_many_fragments_do_not_end_the_call(monkeypatch):
    """GPT-Live counts every speech fragment as a turn; 60 of them used to trigger the out-of-time wrap at ~5 minutes."""
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    bridge = await _live_bridge(db, s, up, monkeypatch)
    try:
        bridge.turns = 200
        await asyncio.sleep(2.2)
        assert not bridge.wrapping and not any(e.get("event_id") == "wrap_1" for e in up.sent)
        assert not bridge.closed
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_early_goodbye_is_refused_until_rep_ends_it(monkeypatch):
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    bridge = await _live_bridge(db, s, up, monkeypatch, over=True)
    try:
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$push": {"turns": {"$each": [
            {"role": "customer", "text": "So what's the out-the-door price?"}, {"role": "rep", "text": "It lands around thirty-one five with everything."}]}}})
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_early", "target": "client"}})
        assert await _wait(lambda: any(e.get("event_id") == "early_item_early" for e in up.sent)), "minute 0, rep still talking: keep asking"
        assert not bridge.closed
        # the rep says goodbye: the shopper may hang up even though it is early
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$push": {"turns": {"role": "rep", "text": "Perfect, see you Saturday at ten. Bye now."}}})
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_bye", "target": "client"}})
        assert await _wait(lambda: bridge.closed, timeout=10)
        assert bridge.reason == "customer_ended"
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_goodbye_allowed_after_min_minutes(monkeypatch):
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    bridge = await _live_bridge(db, s, up, monkeypatch, over=True)
    try:
        bridge.started_at = ls._now() - timedelta(minutes=ls.SHOP_MIN_MINUTES + 1)
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$push": {"turns": {"role": "rep", "text": "So that's the plan, anything else?"}}})
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "item_late", "target": "client"}})
        assert await _wait(lambda: bridge.closed, timeout=10)
        assert bridge.reason == "customer_ended"
        assert not any(str(e.get("event_id", "")).startswith("early_") for e in up.sent)
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})


async def test_out_of_time_wraps_then_drains(monkeypatch):
    db = get_db()
    s = _session()
    await db.roleplay_sessions.insert_one(s)
    up = FakeUpstream()
    monkeypatch.setattr(ls, "WRAP_GRACE_S", 0.5)
    bridge = await _live_bridge(db, s, up, monkeypatch)
    try:
        bridge.started_at = ls._now() - timedelta(minutes=scr.PHONE_MAX_MINUTES + 1)
        assert await _wait(lambda: any(e.get("event_id") == "wrap_1" for e in up.sent), timeout=4)
        assert await _wait(lambda: bridge.closed, timeout=10)
        assert bridge.reason == "out_of_time"
        doc = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert doc["live_end_reason"] == "out_of_time" and doc["status"] == "ending"
    finally:
        await bridge.close("test_cleanup")
        await db.roleplay_sessions.delete_one({"_id": s["_id"]})
