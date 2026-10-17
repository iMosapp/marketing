"""Phase 0 campaign harness: deterministic tests of the campaign sender (scheduler.process_pending_campaign_steps) with a controlled
clock, a fake SMS provider (real send-ledger semantics), a fake AI writer, and a throwaway Mongo database. Nothing is sent and no
app data is touched. Covers the CAMPAIGN_RELIABILITY_V2 switch both ways: OFF reproduces the audited defects, ON fixes them."""
import asyncio
import os
import uuid
from datetime import datetime as real_dt, timedelta, timezone

import pytest
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import scheduler  # noqa: E402
import routers.database as rdb  # noqa: E402
import routers.ai_campaigns as ai_campaigns  # noqa: E402
import routers.campaign_config as campaign_config  # noqa: E402
import services.inboxes as inboxes  # noqa: E402
import services.relationship_intel as relationship_intel  # noqa: E402
import services.twilio_service as twilio_service  # noqa: E402
from services import campaign_reliability as rel, send_ledger  # noqa: E402

T0 = real_dt(2026, 10, 14, 18, 0, tzinfo=timezone.utc)   # 12:00 in Denver (MDT): inside quiet hours window


class _Meta(type):
    def __instancecheck__(cls, obj):
        return isinstance(obj, real_dt)


class Clock:
    t = T0


class FakeDT(real_dt, metaclass=_Meta):
    @classmethod
    def now(cls, tz=None):
        return Clock.t.astimezone(tz) if tz else Clock.t.replace(tzinfo=None)

    @classmethod
    def utcnow(cls):
        return Clock.t.replace(tzinfo=None)


def naive(dt):
    return dt.replace(tzinfo=None)


class BrokenCollection:
    def __init__(self, col):
        self._col = col

    async def find_one(self, *a, **k):
        raise RuntimeError("simulated database error")

    def __getattr__(self, name):
        return getattr(self._col, name)


class FlakyDB:
    """The real test database, with chosen collections whose find_one raises."""
    def __init__(self, db, broken):
        self._db, self._broken = db, set(broken)

    def __getattr__(self, name):
        col = getattr(self._db, name)
        return BrokenCollection(col) if name in self._broken else col

    def __getitem__(self, name):
        return self.__getattr__(name)


class Harness:
    def __init__(self, mp, v2):
        self.mp, self.v2 = mp, v2
        self.calls, self.llm_calls, self.sleeps = [], [], []
        self.provider_script, self.llm_script = {}, {}
        self.broken = set()

    async def __aenter__(self):
        Clock.t = T0
        self.client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        self.db = self.client[f"harness_campaigns_{uuid.uuid4().hex[:10]}"]
        mp = self.mp
        if self.v2 is None:
            mp.delenv(rel.FLAG, raising=False)
        else:
            mp.setenv(rel.FLAG, "on" if self.v2 else "off")
        mp.setattr(rdb, "get_db", lambda: FlakyDB(self.db, self.broken) if self.broken else self.db)
        mp.setattr(scheduler, "datetime", FakeDT)
        mp.setattr(twilio_service, "send_sms", self._send_sms)
        mp.setattr(ai_campaigns, "generate_campaign_message", self._llm)
        mp.setattr(relationship_intel, "build_relationship_brief", self._brief)
        mp.setattr(campaign_config, "get_effective_config", self._config)
        mp.setattr(inboxes, "resolve_from_number", self._from_number)
        mp.setattr(scheduler, "resolve_template_variables", self._resolve)
        mp.setattr(scheduler, "_update_broadcast_progress", self._noop)
        mp.setattr(rel, "_sleep", self._sleep)
        scheduler._user_cache.clear()
        return self

    async def __aexit__(self, *exc):
        await self.client.drop_database(self.db.name)
        self.client.close()

    # ── fakes ──
    async def _send_sms(self, to, body, media_urls=None, from_phone=None, purpose=None, user_id=None, contact_id=None, campaign_key=None, idempotency_key=None, **kw):
        if idempotency_key and not await send_ledger.claim(self.db, idempotency_key, to=to):
            return {"success": False, "duplicate": True, "ledger_status": await send_ledger.status(self.db, idempotency_key), "error_code": "duplicate"}
        script = self.provider_script.get(to) or []
        res = script.pop(0) if script else {"success": True, "message_sid": f"SM{uuid.uuid4().hex[:12]}"}
        self.calls.append({"to": to, "body": body, "key": idempotency_key})
        if idempotency_key:
            await send_ledger.done(self.db, idempotency_key, res)
        return res

    async def _llm(self, user_id, contact_id, data):
        self.llm_calls.append(contact_id)
        script = self.llm_script.get(contact_id) or []
        step = script.pop(0) if script else "ok"
        if step == "fail":
            raise RuntimeError("model unavailable")
        return {"success": True, "message": f"AI text for {contact_id[-4:]}: {data.get('step_context')}"}

    async def _brief(self, *a, **k):
        return {"human_summary": ""}

    async def _config(self, **k):
        return {"message_mode": "ai_suggested"}

    async def _from_number(self, *a, **k):
        return "+15005550006"

    async def _resolve(self, db, message, contact, user_id):
        return message

    async def _noop(self, *a, **k):
        return None

    async def _sleep(self, s):
        self.sleeps.append(s)

    # ── seeding ──
    async def seed(self, n=1, *, ai=False, active=True, delivery="auto", ctype="custom", late=timedelta(minutes=5), enrollment_status="active",
                   row_status="pending", steps=1, opted_out=False):
        uid = ObjectId()
        await self.db.users.insert_one({"_id": uid, "timezone": "America/Denver", "role": "user", "first_name": "Rep"})
        cid = ObjectId()
        camp = {"_id": cid, "name": "Sold follow-up", "type": ctype, "active": active, "ai_enabled": ai, "delivery_mode": delivery,
                "sequences": [{"step_context": f"check-in {i + 1}", "message_template": f"Hey, how is the truck? ({i + 1})"} for i in range(steps)]}
        if ctype in rel.DATED_TYPES:
            camp["date_type"] = ctype
        await self.db.campaigns.insert_one(camp)
        rows = []
        for i in range(n):
            ct = ObjectId()
            phone = f"+1500555{i:04d}"
            await self.db.contacts.insert_one({"_id": ct, "first_name": f"Cust{i}", "phone": phone, "user_id": str(uid), "opted_out": opted_out})
            eid = ObjectId()
            due = naive(Clock.t - late)
            await self.db.campaign_enrollments.insert_one({"_id": eid, "campaign_id": str(cid), "contact_id": str(ct), "user_id": str(uid),
                                                           "status": enrollment_status, "current_step": 1, "next_send_at": due, "enrolled_at": due})
            for s in range(steps):
                r = await self.db.campaign_pending_sends.insert_one({
                    "user_id": str(uid), "campaign_id": str(cid), "campaign_name": camp["name"], "contact_id": str(ct), "contact_name": f"Cust{i}",
                    "contact_phone": phone, "enrollment_id": str(eid), "step": s + 1, "message_template": camp["sequences"][s]["message_template"],
                    "channel": "sms", "delivery_mode": delivery, "ai_enabled": ai, "send_at": due + timedelta(days=30 * s), "status": row_status,
                    "created_at": due})
                rows.append(r.inserted_id)
        return {"user_id": str(uid), "campaign_id": str(cid), "rows": rows}

    async def run(self):
        await scheduler.process_pending_campaign_steps()

    async def row(self, rid):
        return await self.db.campaign_pending_sends.find_one({"_id": rid})


def go(mp, v2, body):
    async def main():
        async with Harness(mp, v2) as h:
            await body(h)
    asyncio.run(main())


# ───────────────────────── baseline ─────────────────────────

@pytest.mark.parametrize("v2", [False, True])
def test_due_touch_sends_once_and_completes_enrollment(monkeypatch, v2):
    async def body(h):
        s = await h.seed()
        await h.run()
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "sent" and len(h.calls) == 1
        enr = await h.db.campaign_enrollments.find_one({"_id": ObjectId(r["enrollment_id"])})
        assert enr["status"] == "completed"
        if v2:
            assert r["events"][-1]["state"] == "sent"
    go(monkeypatch, v2, body)


@pytest.mark.parametrize("v2", [False, True])
def test_opted_out_contact_is_skipped(monkeypatch, v2):
    async def body(h):
        s = await h.seed(opted_out=True)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "skipped" and not h.calls
    go(monkeypatch, v2, body)


def test_switch_from_database_setting(monkeypatch):
    async def body(h):
        assert not await rel.enabled(h.db)
        await h.db.settings.insert_one({"key": rel.SETTINGS_KEY, "enabled": True})
        assert await rel.enabled(h.db)
        s = await h.seed(active=False)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "paused" and not h.calls
    go(monkeypatch, None, body)


# ───────────────────────── R1: pausing a plan ─────────────────────────

def test_legacy_paused_plan_still_sends(monkeypatch):
    async def body(h):
        s = await h.seed(active=False)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent" and len(h.calls) == 1   # the audited defect
    go(monkeypatch, False, body)


def test_v2_paused_plan_holds_then_resumes(monkeypatch):
    async def body(h):
        s = await h.seed(active=False)
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "paused" and r["paused_reason"] == "campaign_paused" and not h.calls
        await h.db.campaigns.update_one({"_id": ObjectId(s["campaign_id"])}, {"$set": {"active": True}})
        assert await rel.resume_campaign(h.db, s["campaign_id"]) == 1
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent" and len(h.calls) == 1
    go(monkeypatch, True, body)


@pytest.mark.parametrize("st,expect", [("cancelled", "skipped"), ("paused", "paused")])
def test_v2_stopped_enrollment_sends_nothing(monkeypatch, st, expect):
    async def body(h):
        s = await h.seed(enrollment_status=st)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == expect and not h.calls
    go(monkeypatch, True, body)


# ───────────────────────── R2: crashed workers ─────────────────────────

async def _stale(h, s):
    await h.db.campaign_pending_sends.update_one({"_id": s["rows"][0]}, {"$set": {"status": "processing", "locked_at": naive(Clock.t - timedelta(minutes=45))}})


def test_legacy_stale_processing_is_lost(monkeypatch):
    async def body(h):
        s = await h.seed()
        await _stale(h, s)
        await h.db.campaign_enrollments.update_many({}, {"$set": {"next_send_at": None}})
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "processing" and not h.calls   # never recovered
    go(monkeypatch, False, body)


def test_v2_stale_processing_requeued_and_sent_once(monkeypatch):
    async def body(h):
        s = await h.seed()
        await _stale(h, s)
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "sent" and len(h.calls) == 1 and r["attempts"] == 1
        assert any(e["state"] == "pending" and "worker stopped" in e["reason"] for e in r["events"])
    go(monkeypatch, True, body)


def test_v2_stale_after_provider_call_never_resent_or_recreated(monkeypatch):
    async def body(h):
        s = await h.seed()
        await _stale(h, s)
        await h.db.send_ledger.insert_one({"_id": f"pending:{s['rows'][0]}", "status": "sending", "claimed_at": Clock.t - timedelta(minutes=45)})
        await h.run()
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "unknown_outcome" and not h.calls
        assert await h.db.campaign_pending_sends.count_documents({}) == 1   # the legacy migration must not re-create the step
    go(monkeypatch, True, body)


@pytest.mark.parametrize("v2,rows_after", [(False, 2), (True, 1)])
def test_failed_last_step_recreated_only_in_legacy(monkeypatch, v2, rows_after):
    async def body(h):
        s = await h.seed()
        h.provider_script["+15005550000"] = [{"success": False, "error_code": 21211, "error": "Invalid To number"}]
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "failed"
        await h.run()
        assert await h.db.campaign_pending_sends.count_documents({}) == rows_after
    go(monkeypatch, v2, body)


# ───────────────────────── R6: late touches ─────────────────────────

def test_legacy_very_late_checkin_still_sends(monkeypatch):
    async def body(h):
        s = await h.seed(late=timedelta(days=40))
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent"
    go(monkeypatch, False, body)


@pytest.mark.parametrize("late,status", [(timedelta(days=2), "sent"), (timedelta(days=5), "expired")])
def test_v2_checkin_window_is_3_days(monkeypatch, late, status):
    async def body(h):
        s = await h.seed(late=late)
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == status
        if status == "expired":
            assert not h.calls
            task = await h.db.tasks.find_one({"pending_send_id": str(s["rows"][0])})
            assert task and task["source"] == "campaign_expired" and "check-in 1" in task["description"]
            enr = await h.db.campaign_enrollments.find_one({"_id": ObjectId(r["enrollment_id"])})
            assert enr["status"] == "completed"
            await h.run()
            assert await h.db.tasks.count_documents({"pending_send_id": str(s["rows"][0])}) == 1
    go(monkeypatch, True, body)


@pytest.mark.parametrize("late,status", [(timedelta(hours=2), "sent"), (timedelta(hours=26), "expired")])
def test_v2_birthday_sends_same_local_day_only(monkeypatch, late, status):
    async def body(h):
        s = await h.seed(ctype="birthday", late=late)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == status
    go(monkeypatch, True, body)


# ───────────────────────── R3: guard errors ─────────────────────────

def test_legacy_guard_error_sends_anyway(monkeypatch):
    async def body(h):
        s = await h.seed()
        h.broken = {"messages"}
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent"
    go(monkeypatch, False, body)


def test_v2_guard_error_holds_then_fails_after_three(monkeypatch):
    async def body(h):
        s = await h.seed()
        h.broken = {"messages"}
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "pending" and r["held_reason"] == "guard_error" and r["guard_errors"] == 1 and not h.calls
        for _ in range(2):
            Clock.t += timedelta(minutes=31)
            await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "failed" and r["guard_errors"] == 3 and not h.calls
    go(monkeypatch, True, body)


# ───────────────────────── R4: AI failures ─────────────────────────

def test_legacy_ai_failure_sends_template(monkeypatch):
    async def body(h):
        s = await h.seed(ai=True)
        cid = (await h.row(s["rows"][0]))["contact_id"]
        h.llm_script[cid] = ["fail"]
        await h.run()
        assert h.calls and h.calls[0]["body"].startswith("Hey, how is the truck?")
    go(monkeypatch, False, body)


def test_v2_ai_failure_retries_twice_then_holds_for_rep(monkeypatch):
    async def body(h):
        s = await h.seed(ai=True)
        cid = (await h.row(s["rows"][0]))["contact_id"]
        h.llm_script[cid] = ["fail", "fail", "fail"]
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "held" and r["held_reason"] == "ai_failed" and not h.calls
        assert len(h.llm_calls) == 3 and h.sleeps == list(rel.AI_BACKOFF_S)
        task = await h.db.tasks.find_one({"pending_send_id": str(s["rows"][0])})
        assert task and task["source"] == "campaign_held" and "Nothing was sent" in task["description"]
    go(monkeypatch, True, body)


def test_v2_ai_recovers_on_retry(monkeypatch):
    async def body(h):
        s = await h.seed(ai=True)
        cid = (await h.row(s["rows"][0]))["contact_id"]
        h.llm_script[cid] = ["fail", "ok"]
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent" and h.calls[0]["body"].startswith("AI text")
    go(monkeypatch, True, body)


def test_v2_empty_static_message_is_held_not_generic(monkeypatch):
    async def body(h):
        s = await h.seed()
        await h.db.campaign_pending_sends.update_one({"_id": s["rows"][0]}, {"$set": {"message_template": ""}})
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "held" and r["held_reason"] == "empty_message" and not h.calls
    go(monkeypatch, True, body)


# ───────────────────────── R8: provider failures ─────────────────────────

def test_v2_rate_limit_retries_with_backoff_and_fresh_key(monkeypatch):
    async def body(h):
        s = await h.seed()
        h.provider_script["+15005550000"] = [{"success": False, "error_code": 20429, "error": "Too Many Requests"}]
        await h.run()
        r = await h.row(s["rows"][0])
        assert r["status"] == "pending" and r["provider_retries"] == 1 and r["ledger_key"].endswith(":r1")
        await h.run()
        assert len(h.calls) == 1   # not due yet
        Clock.t += timedelta(minutes=6)
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent"
        assert [c["key"] for c in h.calls] == [f"pending:{s['rows'][0]}", f"pending:{s['rows'][0]}:r1"]
    go(monkeypatch, True, body)


def test_v2_permanent_refusal_fails_without_retry(monkeypatch):
    async def body(h):
        s = await h.seed()
        h.provider_script["+15005550000"] = [{"success": False, "error_code": 21211, "error": "Invalid To number"}]
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "failed" and len(h.calls) == 1
    go(monkeypatch, True, body)


# ───────────────────────── duplicates + concurrency ─────────────────────────

def test_v2_duplicate_touch_rows_send_once(monkeypatch):
    async def body(h):
        s = await h.seed()
        doc = await h.row(s["rows"][0])
        doc.pop("_id")
        await h.db.campaign_pending_sends.insert_one(doc)
        await h.run()
        states = sorted([d["status"] async for d in h.db.campaign_pending_sends.find({})])
        assert states == ["sent", "skipped"] and len(h.calls) == 1
    go(monkeypatch, True, body)


@pytest.mark.parametrize("v2", [False, True])
def test_concurrent_workers_never_double_send(monkeypatch, v2):
    async def body(h):
        await h.seed(n=60)
        await asyncio.gather(h.run(), h.run(), h.run())
        sent = await h.db.campaign_pending_sends.count_documents({"status": "sent"})
        assert sent == 60 and len(h.calls) == 60 and len({c["to"] for c in h.calls}) == 60
    go(monkeypatch, v2, body)


def test_v2_broadcast_rows_ignore_plan_status(monkeypatch):
    async def body(h):
        s = await h.seed(active=False)
        await h.db.campaign_pending_sends.update_one({"_id": s["rows"][0]}, {"$set": {"broadcast_id": "b1", "type": "broadcast", "enrollment_id": ""}})
        await h.run()
        assert (await h.row(s["rows"][0]))["status"] == "sent"
    go(monkeypatch, True, body)
