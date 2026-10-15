"""Cross-replica job leases (services/job_lease.py), against the preview Mongo. Every key starts with qa_lease_ and is removed afterwards.
Run alone: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_job_lease.py -q"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pymongo.errors import AutoReconnect

from routers import database
from services import job_lease as jl


def _run(coro):
    database._client, database._db = None, None  # one Motor client per event loop
    return asyncio.run(coro)


def _key(name):
    return f"qa_lease_{name}_{uuid.uuid4().hex[:6]}"


async def _cleanup():
    await database.get_db()[jl.COLL].delete_many({"_id": {"$regex": "^(startup:)?qa_lease_"}})


def _as_replica(monkeypatch, name):
    monkeypatch.setattr(jl, "INSTANCE_ID", f"replica-{name}")


@pytest.fixture(autouse=True)
def _wipe():
    yield
    _run(_cleanup())


def test_only_one_of_many_concurrent_claims_wins():
    key = _key("claim")

    async def go():
        db = database.get_db()
        return await asyncio.gather(*[jl.claim(db, key, 30) for _ in range(20)])
    assert sum(_run(go())) == 1


def test_two_replicas_firing_the_same_tick_run_it_once(monkeypatch):
    key, calls = _key("tick"), []

    async def job():
        calls.append(jl.INSTANCE_ID)
        await asyncio.sleep(0.2)

    async def go():
        a, b = jl.guard(key, job, gap_s=5), jl.guard(key, job, gap_s=5)
        _as_replica(monkeypatch, "a")
        ta = asyncio.create_task(a())
        await asyncio.sleep(0)
        _as_replica(monkeypatch, "b")
        tb = asyncio.create_task(b())
        await asyncio.gather(ta, tb)
        await b()  # the other replica's next tick inside the gap is skipped too
    _run(go())
    assert len(calls) == 1


def test_next_period_runs_again_after_the_gap():
    key, calls = _key("gap"), []

    async def job():
        calls.append(1)

    async def go():
        g = jl.guard(key, job, gap_s=0.5)
        await g()
        await g()
        await asyncio.sleep(0.6)
        await g()
    _run(go())
    assert len(calls) == 2


def test_dead_replica_lease_expires_and_the_other_takes_over(monkeypatch):
    key, calls = _key("takeover"), []
    monkeypatch.setattr(jl, "HOLD_S", 1)

    async def job():
        calls.append(jl.INSTANCE_ID)

    async def go():
        db = database.get_db()
        _as_replica(monkeypatch, "dead")
        assert await jl.claim(db, key, jl.HOLD_S)  # claimed, then the replica died: no renew, no finish
        _as_replica(monkeypatch, "alive")
        g = jl.guard(key, job, gap_s=0)
        await g()
        assert calls == []
        await asyncio.sleep(1.2)
        await g()
        doc = await db[jl.COLL].find_one({"_id": key})
        return doc
    doc = _run(go())
    assert calls == ["replica-alive"] and doc["owner"] == "replica-alive" and doc["running"] is False


def test_long_running_job_keeps_its_lease(monkeypatch):
    key, calls = _key("renew"), []
    monkeypatch.setattr(jl, "HOLD_S", 1)
    monkeypatch.setattr(jl, "RENEW_S", 0.3)

    async def slow():
        calls.append("slow")
        await asyncio.sleep(2.0)

    async def quick():
        calls.append("steal")

    async def go():
        _as_replica(monkeypatch, "a")
        t = asyncio.create_task(jl.guard(key, slow, gap_s=0)())
        await asyncio.sleep(1.5)  # past the 1 s hold: only renewal keeps it
        _as_replica(monkeypatch, "b")
        await jl.guard(key, quick, gap_s=0)()
        _as_replica(monkeypatch, "a")
        await t
    _run(go())
    assert calls == ["slow"]


def test_mongo_error_runs_the_tick_like_before_leases(monkeypatch):
    calls = []

    async def broken(*a, **k):
        raise AutoReconnect("down")

    async def job():
        calls.append(1)
    monkeypatch.setattr(jl, "claim", broken)
    _run(jl.guard(_key("failopen"), job, gap_s=10)())
    assert calls == [1]


def test_job_exceptions_still_release_the_lease():
    key = _key("raises")

    async def boom():
        raise RuntimeError("x")

    async def go():
        with pytest.raises(RuntimeError):
            await jl.guard(key, boom, gap_s=0)()
        return await database.get_db()[jl.COLL].find_one({"_id": key})
    doc = _run(go())
    assert doc["running"] is False


def test_guard_jobs_wraps_shared_jobs_and_leaves_local_ones(monkeypatch):
    async def noop():
        return None

    async def go():
        s = AsyncIOScheduler()
        s.add_job(noop, IntervalTrigger(minutes=1), id="qa_interval")
        s.add_job(noop, IntervalTrigger(seconds=15), id="qa_fast")
        s.add_job(noop, CronTrigger(hour=8, minute=0), id="qa_daily")
        s.add_job(noop, CronTrigger(minute=5), id="qa_hourly")
        s.add_job(noop, IntervalTrigger(minutes=5), id="memory_gc")
        n = jl.guard_jobs(s)
        gaps = {j.id: getattr(j.func, "lease_gap_s", None) for j in s.get_jobs()}
        monkeypatch.setenv("JOB_LEASES", "off")
        s2 = AsyncIOScheduler()
        s2.add_job(noop, IntervalTrigger(minutes=1), id="qa_off")
        n_off = jl.guard_jobs(s2)
        return n, gaps, n_off
    n, gaps, n_off = _run(go())
    assert n == 4 and n_off == 0
    assert gaps == {"qa_interval": 48.0, "qa_fast": 12.0, "qa_daily": 300, "qa_hourly": 300, "memory_gc": None}


def test_every_real_scheduler_job_is_guarded_except_memory_gc(monkeypatch):
    """Registers the real 56 jobs on a private scheduler (never started) and checks each gets a lease and a sane gap."""
    import scheduler as sched_mod

    async def go():
        private = AsyncIOScheduler()
        monkeypatch.setattr(sched_mod, "scheduler", private)
        monkeypatch.setattr(private, "start", lambda *a, **k: None)
        sched_mod.start_scheduler()
        return {j.id: (getattr(j.func, "lease_gap_s", None), j.trigger) for j in private.get_jobs()}
    jobs = _run(go())
    assert len(jobs) >= 50
    assert jobs["memory_gc"][0] is None
    for jid, (gap, trig) in jobs.items():
        if jid == "memory_gc":
            continue
        assert gap is not None, jid
        if isinstance(trig, IntervalTrigger):
            assert gap == pytest.approx(trig.interval.total_seconds() * 0.8), jid
        else:
            assert 0 < gap <= jl.CRON_GAP_CAP_S, jid


def test_boot_cleanup_runs_on_one_replica_per_rollout(monkeypatch):
    key, calls = _key("boot"), []

    async def cleanup():
        calls.append(jl.INSTANCE_ID)

    async def go():
        _as_replica(monkeypatch, "pod1")
        t1 = asyncio.create_task(jl.run_once(key, cleanup, window_s=2))
        await asyncio.sleep(0)
        _as_replica(monkeypatch, "pod2")
        t2 = asyncio.create_task(jl.run_once(key, cleanup, window_s=2))
        await asyncio.gather(t1, t2)
        await asyncio.sleep(2.1)
        _as_replica(monkeypatch, "pod3")  # a later restart, outside the rollout window, runs it again
        await jl.run_once(key, cleanup, window_s=2)
    _run(go())
    assert len(calls) == 2 and calls[-1] == "replica-pod3"


def test_lease_docs_carry_owner_and_times():
    key = _key("doc")

    async def job():
        return "ok"

    async def go():
        out = await jl.guard(key, job, gap_s=1)()
        return out, await database.get_db()[jl.COLL].find_one({"_id": key})
    out, doc = _run(go())
    assert out == "ok" and doc["owner"] == jl.INSTANCE_ID and doc["runs"] == 1
    assert doc["until"].replace(tzinfo=timezone.utc) >= doc["claimed_at"].replace(tzinfo=timezone.utc)
    assert doc["finished_at"].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)


def test_two_replicas_running_the_real_job_list_share_it_without_double_runs(monkeypatch):
    """Production topology in one process: two schedulers register the real 56 jobs (bodies swapped for recorders, every trigger
    sped up to 1 s), run side by side for 5 s, then replica A shuts down and B must keep every job going on its own."""
    import time
    import scheduler as sched_mod
    monkeypatch.setattr(jl, "COLL", "job_leases_qa")  # never touch the live preview leases
    real_guard_jobs = jl.guard_jobs
    runs, active, overlaps = [], {}, []

    def recorder(job_id, replica):
        async def body():
            if job_id in active and job_id not in jl.LOCAL_JOBS:
                overlaps.append((job_id, active[job_id], replica))
            active[job_id] = replica
            runs.append((job_id, replica, time.monotonic()))
            await asyncio.sleep(0.05)
            active.pop(job_id, None)
        return body

    async def replica(name):
        s = AsyncIOScheduler()
        monkeypatch.setattr(sched_mod, "scheduler", s)
        monkeypatch.setattr(jl, "guard_jobs", lambda *a, **k: 0)
        sched_mod.start_scheduler()
        monkeypatch.setattr(jl, "guard_jobs", real_guard_jobs)
        for job in s.get_jobs():
            job.modify(func=recorder(job.id, name), misfire_grace_time=5, coalesce=True)
            job.reschedule(IntervalTrigger(seconds=1))
        real_guard_jobs(s, owner=name)
        return s

    async def go():
        a = await replica("A")
        b = await replica("B")
        await asyncio.sleep(5.2)
        a.shutdown(wait=False)
        killed_at = time.monotonic()
        await asyncio.sleep(2.5)
        b.shutdown(wait=False)
        await asyncio.sleep(0.2)
        await database.get_db()["job_leases_qa"].drop()
        return killed_at

    killed_at = _run(go())
    jobs = {j for j, _, _ in runs}
    assert len(jobs) >= 50 and not overlaps, overlaps[:5]
    for jid in jobs - jl.LOCAL_JOBS:
        starts = sorted(t for j, _, t in runs if j == jid)
        both = [t for t in starts if t < killed_at]
        assert 3 <= len(both) <= 7, (jid, len(both))  # ~once per second across BOTH replicas, not twice
        assert all(b2 - b1 > 0.7 for b1, b2 in zip(starts, starts[1:])), jid  # never two runs inside one tick
        assert any(t > killed_at + 0.5 and r == "B" for j, r, t in runs if j == jid), jid  # B took over after A stopped
    gc = [r for j, r, t in runs if j == "memory_gc" and t < killed_at]
    assert {"A", "B"} <= set(gc)  # local jobs keep running on every replica
