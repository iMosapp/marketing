"""Per-recipient send ledger: at most one provider call per idempotency key, on any replica, including retries after a crash.
A key is claimed (status `sending`) before the provider is called and closed with the provider's answer. A crash between the
provider accepting a text and the answer being recorded leaves the row in `sending`; the sweep moves it to `unknown_outcome`
and it is never re-sent automatically (at-most-once: a missed text is preferable to a duplicate). Rows stay for review."""
import logging
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

COLL = "send_ledger"
STALE_S = 900


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def claim(db, key: str, **meta) -> bool:
    from services.job_lease import INSTANCE_ID
    try:
        await db[COLL].insert_one({"_id": key, "status": "sending", "owner": INSTANCE_ID, "claimed_at": _now(), **meta})
        return True
    except DuplicateKeyError:
        return False


async def done(db, key: str, result: dict) -> None:
    ok = bool(result.get("success"))
    await db[COLL].update_one({"_id": key}, {"$set": {"status": "sent" if ok else "failed", "message_sid": result.get("message_sid"),
                                                     "error_code": None if ok else str(result.get("error_code") or result.get("error") or "")[:120], "finished_at": _now()}})


async def release(db, key: str) -> None:
    """The send never reached the provider (blocked before the call): free the key so a later, allowed attempt may use it."""
    await db[COLL].delete_one({"_id": key, "status": "sending"})


async def sweep(db, stale_s: int = STALE_S) -> int:
    r = await db[COLL].update_many({"status": "sending", "claimed_at": {"$lt": _now() - timedelta(seconds=stale_s)}},
                                   {"$set": {"status": "unknown_outcome", "swept_at": _now()}})
    if r.modified_count:
        logger.warning(f"[SendLedger] {r.modified_count} send(s) crashed mid-call: outcome unknown, not re-sent (review send_ledger)")
    return r.modified_count
