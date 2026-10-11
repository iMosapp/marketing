"""Per-request access block (ended pilots): one indexed lookup per authenticated caller, cached briefly so a blocked user is
refused on every API call within TTL seconds on any pod and immediately on the pod that blocked them."""
import time

from bson import ObjectId

TTL = 20.0
_cache: dict[str, tuple[bool, float]] = {}
REFUSAL = {"detail": "Authentication required", "reason": "access_blocked"}


async def is_blocked(db, user_id: str) -> bool:
    hit = _cache.get(user_id)
    now = time.monotonic()
    if hit and hit[1] > now:
        return hit[0]
    blocked = False
    if ObjectId.is_valid(user_id):
        blocked = await db.users.find_one({"_id": ObjectId(user_id), "access_blocked": {"$exists": True}}, {"_id": 1}) is not None
    _cache[user_id] = (blocked, now + TTL)
    return blocked


def invalidate(user_ids) -> None:
    for u in user_ids:
        _cache.pop(str(u), None)
