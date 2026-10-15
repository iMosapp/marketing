"""Cross-replica job ownership. Production runs 2 replicas and each one runs its own APScheduler and its own boot clean-ups.
Every replica keeps its scheduler running; each tick of a shared job first claims a lease in `job_leases` (_id = job id).
The winner renews the lease while it works; when it finishes the lease is kept until `min_gap` has passed since the start,
so the other replica's tick for the same period is skipped. A replica that dies stops renewing and its lease expires after
HOLD_S, so the next tick on any surviving replica takes over. If Mongo can't be reached the tick runs (the pre-lease behaviour).
JOB_LEASES=off turns the guard off without a code change."""
import asyncio
import inspect
import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.triggers.interval import IntervalTrigger
from pymongo.errors import DuplicateKeyError, PyMongoError

logger = logging.getLogger(__name__)

COLL = "job_leases"
INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
HOLD_S = 90  # a running tick's lease; renewed every RENEW_S, so a dead replica frees its jobs within 90 s
RENEW_S = 30
CRON_GAP_CAP_S = 300  # cron ticks fire at the same instant on both replicas; 5 min covers clock skew and late starts
LOCAL_JOBS = {"memory_gc"}  # act on this process's own memory, so every replica runs them
BOOT_WINDOW_S = 180  # replicas of one rollout boot within ~1-2 min of each other


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enabled() -> bool:
    return (os.environ.get("JOB_LEASES") or "").strip().lower() != "off"


async def claim(db, key: str, hold_s: float, owner: str = None) -> bool:
    """True when this replica now owns `key` (free, expired, or never claimed). Atomic: the upsert's unique _id makes a race lose cleanly."""
    now = _now()
    try:
        await db[COLL].update_one(
            {"_id": key, "until": {"$lte": now}},
            {"$set": {"owner": owner or INSTANCE_ID, "until": now + timedelta(seconds=hold_s), "claimed_at": now, "running": True}, "$inc": {"runs": 1}},
            upsert=True,
        )
        return True
    except DuplicateKeyError:
        return False


async def _renew(db, key: str, owner: str):
    while True:
        await asyncio.sleep(RENEW_S)
        try:
            await db[COLL].update_one({"_id": key, "owner": owner}, {"$set": {"until": _now() + timedelta(seconds=HOLD_S)}})
        except PyMongoError as e:
            logger.warning(f"[JobLease] {key}: renew failed ({type(e).__name__})")


async def _finish(db, key: str, owner: str, started: datetime, min_gap_s: float):
    now = _now()
    await db[COLL].update_one({"_id": key, "owner": owner},
                              {"$set": {"until": max(now, started + timedelta(seconds=min_gap_s)), "running": False, "finished_at": now}})


def min_gap(trigger) -> float:
    if isinstance(trigger, IntervalTrigger):
        return trigger.interval.total_seconds() * 0.8
    now = _now()
    t1 = trigger.get_next_fire_time(None, now)
    t2 = trigger.get_next_fire_time(t1, t1 + timedelta(seconds=1)) if t1 else None
    return min(CRON_GAP_CAP_S, (t2 - t1).total_seconds() * 0.8) if t1 and t2 else CRON_GAP_CAP_S


def guard(job_id: str, func, gap_s: float, owner: str = None):
    async def run(*args, **kwargs):
        from routers.database import get_db
        db = get_db()
        me = owner or INSTANCE_ID
        started = _now()
        try:
            won = await claim(db, job_id, HOLD_S, me)
        except PyMongoError as e:
            logger.warning(f"[JobLease] {job_id}: lease check failed ({type(e).__name__}), running this tick unguarded")
            won = None
        if won is False:
            return None
        renewer = asyncio.create_task(_renew(db, job_id, me)) if won else None
        try:
            out = func(*args, **kwargs)
            return await out if inspect.isawaitable(out) else out
        finally:
            if renewer:
                renewer.cancel()
                try:
                    await _finish(db, job_id, me, started, gap_s)
                except PyMongoError as e:
                    logger.warning(f"[JobLease] {job_id}: release failed ({type(e).__name__}); the lease expires on its own")
    run.__name__ = getattr(func, "__name__", job_id)
    run.lease_gap_s = gap_s
    return run


def guard_jobs(scheduler, owner: str = None) -> int:
    """Wrap every registered (pending) job except LOCAL_JOBS. Call after the add_job calls, before scheduler.start()."""
    if not enabled():
        logger.warning("[JobLease] JOB_LEASES=off: every replica runs every job")
        return 0
    n = 0
    for job in scheduler.get_jobs():
        if job.id in LOCAL_JOBS:
            continue
        job.modify(func=guard(job.id, job.func, min_gap(job.trigger), owner))
        n += 1
    logger.info(f"[JobLease] {n} shared jobs run on one replica per tick (this replica: {owner or INSTANCE_ID})")
    return n


async def run_once(key: str, fn, window_s: float = BOOT_WINDOW_S):
    """Boot clean-up: the first replica of a rollout runs it, a replica booting within `window_s` skips it."""
    from routers.database import get_db
    if enabled():
        try:
            if not await claim(get_db(), f"startup:{key}", window_s):
                logger.info(f"[JobLease] startup {key}: already ran on a replica in the last {int(window_s)} s, skipped")
                return
        except PyMongoError as e:
            logger.warning(f"[JobLease] startup {key}: lease check failed ({type(e).__name__}), running anyway")
    await fn()
