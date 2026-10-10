"""Living Relationship Intelligence: settings and feature flags.
Defaults live here; a store may override windows on stores.intelligence. Flags come from the environment so production stays off until Phase 1B."""
import os

DEFAULTS = {
    "intent_window_days": 45,
    "intent_fresh_days": 14,
    "not_shopping_days": 90,
    "intent_windows": {"service": 30, "finance": 30, "appraisal": 30, "trade": 45, "purchase": 45},
    "stale_after_days": {"contact_pref": 365, "work": 365, "buying_status": 90, "vehicle_interest": 45, "preference": 540, "identity": 730, "note": 365, "trade": 180, "service": 180, "finance": 180, "relationship": 365},
    "recent_days": 14,
}


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def ingest_enabled() -> bool:
    return _flag("INTEL_FACTS_INGEST")


def projection_enabled() -> bool:
    return _flag("INTEL_LEGACY_PROJECTION")


def backfill_execute_enabled() -> bool:
    return _flag("INTEL_BACKFILL_EXECUTE")


def flags() -> dict:
    return {"ingest": ingest_enabled(), "legacy_projection": projection_enabled(), "backfill_execute": backfill_execute_enabled(), "nudges": _flag("INTEL_NUDGES")}


async def settings(db, store_id: str | None) -> dict:
    """Store override merged over the defaults; unknown store -> defaults."""
    out = {**DEFAULTS, "intent_windows": dict(DEFAULTS["intent_windows"]), "stale_after_days": dict(DEFAULTS["stale_after_days"])}
    if not store_id:
        return out
    from bson import ObjectId
    if not ObjectId.is_valid(str(store_id)):
        return out
    store = await db.stores.find_one({"_id": ObjectId(str(store_id))}, {"intelligence": 1})
    over = (store or {}).get("intelligence") or {}
    for k in ("intent_window_days", "intent_fresh_days", "not_shopping_days", "recent_days"):
        if isinstance(over.get(k), (int, float)) and over[k] > 0:
            out[k] = int(over[k])
    for k in ("intent_windows", "stale_after_days"):
        if isinstance(over.get(k), dict):
            out[k].update({a: int(b) for a, b in over[k].items() if isinstance(b, (int, float))})
    return out
