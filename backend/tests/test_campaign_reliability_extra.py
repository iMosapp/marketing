"""Extra Phase 0-1 campaign reliability cases (adds to test_campaign_reliability_harness.py). Same in-process harness:
fake SMS provider, fake AI writer, throwaway Mongo DB, controlled clock. Nothing real is sent."""
import asyncio
import os
import uuid
from datetime import timedelta

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from tests.test_campaign_reliability_harness import Clock, go, naive  # noqa: F401
from services import campaign_reliability as rel


# ── switch: env overrides db.settings, db.settings is the fallback ──
@pytest.mark.parametrize("env,db_val,expect", [
    ("on", False, True), ("ON ", None, True), ("true", None, True), ("1", False, True),
    ("off", True, False), ("0", True, False), ("no", True, False),
    (None, True, True), (None, False, False), (None, None, False),
])
def test_switch_env_and_db_fallback(monkeypatch, env, db_val, expect):
    async def main():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[f"harness_switch_{uuid.uuid4().hex[:8]}"]
        try:
            if env is None:
                monkeypatch.delenv(rel.FLAG, raising=False)
            else:
                monkeypatch.setenv(rel.FLAG, env)
            if db_val is not None:
                await db.settings.insert_one({"key": rel.SETTINGS_KEY, "enabled": db_val})
            assert await rel.enabled(db) is expect
        finally:
            await client.drop_database(db.name)
            client.close()
    asyncio.run(main())


def test_env_off_overrides_db_on_runs_legacy_path(monkeypatch):
    """db.settings says on, env says off -> legacy: paused plan still sends (unchanged behaviour)."""
    async def body(h):
        await h.db.settings.insert_one({"key": rel.SETTINGS_KEY, "enabled": True})
        s = await h.seed(active=False)
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "sent" and len(h.calls) == 1 and "events" not in r
    go(monkeypatch, False, body)


# ── late check-in boundary ──
@pytest.mark.parametrize("late,status", [(timedelta(days=3), "sent"), (timedelta(days=3, minutes=1), "expired")])
def test_v2_checkin_3_day_boundary(monkeypatch, late, status):
    async def body(h):
        s = await h.seed(late=late)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == status
        assert len(h.calls) == (1 if status == "sent" else 0)
    go(monkeypatch, True, body)


# ── dated occasions: expired + ONE task, idempotent ──
@pytest.mark.parametrize("ctype", ["birthday", "anniversary", "sold_date", "holiday"])
def test_v2_dated_one_day_late_expires_with_one_task(monkeypatch, ctype):
    async def body(h):
        s = await h.seed(ctype=ctype, late=timedelta(days=1))
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "expired" and r["skip_reason"] == "too_late" and not h.calls
        await h.run()
        await h.run()
        tasks = await h.db.tasks.find({"pending_send_id": str(s["rows"][0])}).to_list(10)
        assert len(tasks) == 1 and tasks[0]["source"] == "campaign_expired"
    go(monkeypatch, True, body)


@pytest.mark.parametrize("ctype", ["anniversary", "sold_date", "holiday"])
def test_v2_dated_same_day_sends(monkeypatch, ctype):
    async def body(h):
        s = await h.seed(ctype=ctype, late=timedelta(hours=3))
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent" and len(h.calls) == 1
    go(monkeypatch, True, body)


def test_v2_holiday_card_type_on_custom_campaign_is_dated(monkeypatch):
    async def body(h):
        s = await h.seed(late=timedelta(days=1))
        await h.db.campaign_pending_sends.update_one({"_id": s["rows"][0]}, {"$set": {"card_type": "holiday"}})
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "expired" and not h.calls
    go(monkeypatch, True, body)


@pytest.mark.parametrize("late,status", [(timedelta(hours=11), "sent"), (timedelta(hours=13), "expired")])
def test_v2_dated_uses_rep_local_day_not_utc(monkeypatch, late, status):
    """now = 12:00 Denver (18:00Z). 13h late = 23:00 Denver yesterday (same UTC day) -> expired; 11h late = 01:00 today -> sent."""
    async def body(h):
        s = await h.seed(ctype="birthday", late=late)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == status
    go(monkeypatch, True, body)


# ── AI writing ──
def test_v2_ai_succeeds_on_second_retry(monkeypatch):
    async def body(h):
        s = await h.seed(ai=True)
        cid = (await h.row(s["rows"][0]))["contact_id"]
        h.llm_script[cid] = ["fail", "fail", "ok"]
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent"
        assert len(h.llm_calls) == 3 and len(h.calls) == 1 and h.calls[0]["body"].startswith("AI text")
        assert not await h.db.tasks.count_documents({})
    go(monkeypatch, True, body)


def test_v2_ai_held_task_idempotent_and_never_resent(monkeypatch):
    async def body(h):
        s = await h.seed(ai=True)
        cid = (await h.row(s["rows"][0]))["contact_id"]
        h.llm_script[cid] = ["fail"] * 9
        await h.run()
        await h.run()
        Clock.t += timedelta(hours=1)
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "held" and not h.calls and len(h.llm_calls) == 3
        assert await h.db.tasks.count_documents({"source": "campaign_held"}) == 1
    go(monkeypatch, True, body)


def test_v2_ai_held_direct_call_twice_one_task(monkeypatch):
    async def body(h):
        s = await h.seed()
        doc = await h.row(s["rows"][0])
        await rel.hold_for_rep(h.db, doc, naive(Clock.t), "ai_failed", "x", "goal")
        await rel.hold_for_rep(h.db, doc, naive(Clock.t), "ai_failed", "x", "goal")
        await rel.expire(h.db, doc, naive(Clock.t), "late", "goal")
        await rel.expire(h.db, doc, naive(Clock.t), "late", "goal")
        assert await h.db.tasks.count_documents({"source": "campaign_held"}) == 1
        assert await h.db.tasks.count_documents({"source": "campaign_expired"}) == 1
    go(monkeypatch, True, body)


# ── paused / cancelled / stale ──
def test_v2_paused_plan_many_rows_nothing_sends(monkeypatch):
    async def body(h):
        s = await h.seed(n=3, steps=2, active=False, late=timedelta(minutes=5))
        await h.run()
        await h.run()
        assert not h.calls
        first_steps = [await h.row(r) for r in s["rows"][::2]]
        assert all(r["status"] == "paused" for r in first_steps)
    go(monkeypatch, True, body)


@pytest.mark.parametrize("st", ["stopped", "removed"])
def test_v2_stopped_removed_enrollment_skipped(monkeypatch, st):
    async def body(h):
        s = await h.seed(enrollment_status=st)
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "skipped" and r["skip_reason"] == f"enrollment_{st}" and not h.calls
    go(monkeypatch, True, body)


def test_v2_stale_processing_third_time_fails(monkeypatch):
    async def body(h):
        s = await h.seed()
        await h.db.campaign_pending_sends.update_one({"_id": s["rows"][0]}, {"$set": {
            "status": "processing", "attempts": 2, "locked_at": naive(Clock.t - timedelta(minutes=45))}})
        n = await rel.recover_stale(h.db, naive(Clock.t))
        r = await h.row(s["rows"][0])
        assert n == 1 and r["status"] == "failed" and r["attempts"] == 3
    go(monkeypatch, True, body)


def test_v2_fresh_processing_not_recovered(monkeypatch):
    async def body(h):
        s = await h.seed()
        await h.db.campaign_pending_sends.update_one({"_id": s["rows"][0]}, {"$set": {
            "status": "processing", "locked_at": naive(Clock.t - timedelta(minutes=5))}})
        assert await rel.recover_stale(h.db, naive(Clock.t)) == 0
        assert (await h.row(s["rows"][0]))["status"] == "processing"
    go(monkeypatch, True, body)
