"""Owner + heartbeat for long-running in-process work (site crawls, leadership roundtables, AI inspections).
A run stamps `worker_id` and refreshes `heartbeat_at` every BEAT_S while it works. Recovery (at boot and every few minutes on one
replica) only fails runs whose heartbeat is older than STALE_S, so a replica that restarts never fails work another replica is
still doing. Runs started by older code (no heartbeat) are judged by their last update instead."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

BEAT_S = 30
STALE_S = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def stamp() -> dict:
    from services.job_lease import INSTANCE_ID
    return {"worker_id": INSTANCE_ID, "heartbeat_at": _now()}


@asynccontextmanager
async def heartbeat(db, coll: str, _id, every: float = BEAT_S):
    """Keep `heartbeat_at` fresh on db[coll][_id] for as long as the block runs."""
    await db[coll].update_one({"_id": _id}, {"$set": stamp()})

    async def beat():
        while True:
            await asyncio.sleep(every)
            try:
                await db[coll].update_one({"_id": _id}, {"$set": {"heartbeat_at": _now()}})
            except Exception as e:
                logger.warning(f"[Heartbeat] {coll} {_id}: {e}")
    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        task.cancel()


def stale(statuses: list, stale_s: float = STALE_S, legacy_field: str = "updated_at") -> dict:
    """Filter for in-progress runs nobody is working on any more."""
    cut = _now() - timedelta(seconds=stale_s)
    return {"status": {"$in": statuses}, "$or": [{"heartbeat_at": {"$lt": cut}},
                                                  {"heartbeat_at": {"$exists": False}, legacy_field: {"$lt": cut}}]}


async def sweep_all(db) -> dict:
    from services import widget_crawl
    from services.appraisals import inspection
    from services.leadership import orchestrator
    return {"crawls": await widget_crawl.fail_interrupted(db), "roundtables": await orchestrator.fail_interrupted(db),
            "inspections": await inspection.recover_interrupted(db)}
