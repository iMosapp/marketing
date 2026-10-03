"""Public read-only aggregate usage counts for the /mybaby platform deck."""
import asyncio
import time
from fastapi import APIRouter

from routers.database import get_db

router = APIRouter(tags=["platform-stats"])

_CACHE_TTL_S = 600
_cache: dict = {"at": 0.0, "data": None}


async def _compute() -> dict:
    db = get_db()
    users, orgs, contacts, messages, calls_graded, calls_transcribed, shops, lead_shops, sends, enrollments, date_triggers = await asyncio.gather(
        db.users.count_documents({"role": {"$ne": "super_admin"}}),
        db.organizations.count_documents({"active": {"$ne": False}}),
        db.contacts.count_documents({"status": {"$nin": ["hidden", "merged", "deleted"]}}),
        db.messages.count_documents({"direction": {"$in": ["inbound", "outbound"]}, "channel": {"$ne": "system"}}),
        db.call_evaluations.count_documents({}),
        db.call_logs.count_documents({"transcript": {"$exists": True, "$ne": ""}}),
        db.mystery_shops.count_documents({"status": "completed"}),
        db.lead_shops.count_documents({"status": "completed"}),
        db.campaign_pending_sends.count_documents({"status": {"$in": ["sent", "done"]}}),
        db.campaign_enrollments.count_documents({"status": "completed"}),
        db.date_trigger_log.count_documents({}),
    )
    return {
        "users": users,
        "organizations": orgs,
        "contacts": contacts,
        "messages": messages,
        "ai_calls": calls_graded + calls_transcribed + shops + lead_shops,
        "automations": sends + enrollments + date_triggers,
    }


@router.get("/public/platform-stats")
async def platform_stats():
    now = time.time()
    if _cache["data"] is None or now - _cache["at"] > _CACHE_TTL_S:
        _cache["data"] = await _compute()
        _cache["at"] = now
    return {**_cache["data"], "cached_at": int(_cache["at"])}
