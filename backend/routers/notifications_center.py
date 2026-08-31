"""
Notifications Center — "For You / Activity" split feed.
For You = only what needs the rep: urgent, leads, replies, appointments/tasks.
Activity = everything else (sent confirmations, link clicks, campaign chores, system events).
"""
import logging
import urllib.parse
import asyncio
from datetime import datetime, timezone, timedelta
from itertools import groupby
from fastapi import APIRouter
from bson import ObjectId
from cachetools import TTLCache

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notification-center", tags=["notification-center"])

# Cache the FULL built feed per user (30s TTL) — filtered per request
_notifications_cache: TTLCache = TTLCache(maxsize=500, ttl=30)

_SECTION_TIMEOUT = 3.0   # seconds per DB section
_TOTAL_TIMEOUT   = 10.0  # seconds total

# db.notifications types that belong in For You: type -> (category, priority)
FOR_YOU_TYPES = {
    "you_are_needed":            ("urgent", -1),
    "slow_lead":                 ("urgent", 0),
    "jump_ball":                 ("leads", 0),
    "new_lead":                  ("leads", 1),
    "lead_assigned":             ("leads", 1),
    "new_demo_request":          ("leads", 1),
    "engagement_signal":         ("leads", 1),
    "keyword_alert":             ("leads", 1),
    "customer_reply":            ("replies", 2),
    "customer_reply_ai_handling": ("replies", 2),
    "appointment_extracted":     ("appts", 2),
    "task_reminder":             ("appts", 2),
}

FOR_YOU_CATEGORIES = ("urgent", "leads", "replies", "appts")


def _ts(val) -> str:
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val else datetime.now(timezone.utc).isoformat()


async def _get_user_teams(db, user_id: str) -> list:
    user_teams = []
    try:
        teams = await db.teams.find({"members": user_id}, {"_id": 1}).to_list(50)
        user_teams.extend([str(t["_id"]) for t in teams])
        shared_inboxes = await db.shared_inboxes.find({"user_ids": user_id}, {"_id": 1}).to_list(50)
        user_teams.extend([str(si["_id"]) for si in shared_inboxes])
    except Exception:
        pass
    return user_teams


async def _run_section(coro, section_name: str, fallback=None):
    try:
        return await asyncio.wait_for(coro, timeout=_SECTION_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"[NotificationsCenter] Section '{section_name}' timed out")
        return fallback if fallback is not None else []
    except Exception as e:
        logger.debug(f"[NotificationsCenter] Section '{section_name}' error: {e}")
        return fallback if fallback is not None else []


def _notif_link(n: dict) -> str | None:
    """Build the tap-through link for a db.notifications doc."""
    conversation_id = n.get("conversation_id", "")
    contact_id = n.get("contact_id", "")
    ntype = n.get("type", "")
    if ntype in ("you_are_needed", "customer_reply", "customer_reply_ai_handling", "slow_lead") and conversation_id:
        return f"/thread/{conversation_id}"
    if ntype in ("appointment_extracted", "task_reminder"):
        return f"/contact/{contact_id}" if contact_id else "/dates-calendar"
    if contact_id:
        return f"/contact/{contact_id}"
    if conversation_id:
        return f"/thread/{conversation_id}?contact_name={n.get('contact_name', '')}"
    if n.get("demo_request_id"):
        return "/admin/lead-tracking"
    return None


async def _get_full_feed(user_id: str) -> dict:
    """Return the full built feed for a user, from cache or fresh."""
    if user_id in _notifications_cache:
        return _notifications_cache[user_id]
    try:
        built = await asyncio.wait_for(_build_feed(user_id), timeout=_TOTAL_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"[NotificationsCenter] Timeout for user {user_id}")
        built = {"items": [], "unread_count": 0, "category_counts": {}, "activity_count": 0, "timed_out": True}
    _notifications_cache[user_id] = built
    return built


async def _build_feed(user_id: str) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)
    items = []

    user_teams = await _run_section(_get_user_teams(db, user_id), "teams", [])

    # 1. ALL db.notifications for this user/team — classified into For You vs Activity
    notif_query = {"$or": [{"user_id": user_id}, {"team_id": {"$in": user_teams}, "user_id": None}], "dismissed": False}
    notifs = await _run_section(db.notifications.find(notif_query).sort("created_at", -1).limit(40).to_list(40), "notifications")
    for n in notifs:
        ntype = n.get("type", "activity")
        cat_prio = FOR_YOU_TYPES.get(ntype)
        contact_id = n.get("contact_id", "")
        body = n.get("form_details") or n.get("message", "")
        base = {
            "id": str(n["_id"]),
            "type": ntype,
            "title": n.get("title", ntype.replace("_", " ").title()),
            "body": body,
            "link": _notif_link(n),
            "contact_name": n.get("contact_name"),
            "contact_id": contact_id,
            "conversation_id": n.get("conversation_id", ""),
            "demo_request_id": n.get("demo_request_id", ""),
            "timestamp": _ts(n.get("created_at")),
            "read": n.get("read", False),
        }
        if cat_prio:
            cat, prio = cat_prio
            # hot engagement (return visit / 3+ views) bumps priority
            if ntype == "engagement_signal" and (n.get("is_return_visit") or n.get("view_count", 1) >= 3):
                prio = 0
            items.append({**base, "feed": "for_you", "category": cat, "priority": prio,
                          "source": "leads" if cat == "leads" else cat,
                          "reply_count": n.get("reply_count")})
        else:
            items.append({**base, "feed": "activity", "category": "activity", "priority": 6, "source": "activity"})

    # 2. OVERDUE TASKS (For You / appts) — campaign chores excluded
    task_filter = {"user_id": user_id, "completed": {"$ne": True}, "type": {"$nin": ["campaign_send", "campaign_step"]}}
    overdue = await _run_section(db.tasks.find({**task_filter, "due_date": {"$lt": now}}).sort("due_date", 1).limit(10).to_list(10), "overdue_tasks")
    for t in overdue:
        contact_id = t.get("contact_id", ""); desc = t.get("description", ""); title = t.get("title", "Follow up"); task_id = str(t["_id"])
        prefill = urllib.parse.quote(desc[:500]) if desc else ""
        link = f"/contact/{contact_id}?taskId={task_id}&taskTitle={urllib.parse.quote(title[:200])}&prefill={prefill}" if contact_id else "/dates-calendar"
        items.append({"id": f"task_{task_id}", "type": "task_overdue", "feed": "for_you", "category": "appts", "priority": 1,
                      "title": "Overdue", "body": title, "link": link, "contact_id": contact_id,
                      "timestamp": _ts(t.get("due_date")), "read": False, "source": "tasks"})

    # 3. DUE WITHIN 24H (For You / appts)
    tomorrow = now + timedelta(hours=24)
    upcoming = await _run_section(db.tasks.find({**task_filter, "due_date": {"$gte": now, "$lte": tomorrow}}).sort("due_date", 1).limit(5).to_list(5), "upcoming_tasks")
    for t in upcoming:
        contact_id = t.get("contact_id", ""); desc = t.get("description", ""); title = t.get("title", "Follow up"); task_id = str(t["_id"])
        prefill = urllib.parse.quote(desc[:500]) if desc else ""
        link = f"/contact/{contact_id}?taskId={task_id}&taskTitle={urllib.parse.quote(title[:200])}&prefill={prefill}" if contact_id else "/dates-calendar"
        items.append({"id": f"task_soon_{task_id}", "type": "task_due_soon", "feed": "for_you", "category": "appts", "priority": 3,
                      "title": "Due Soon", "body": title, "link": link, "contact_id": contact_id,
                      "timestamp": _ts(t.get("due_date")), "read": False, "source": "tasks"})

    # 4. UNREAD CONVERSATIONS (For You / replies)
    unread = await _run_section(db.conversations.find({"participants": user_id, "unread": True}).sort("updated_at", -1).limit(10).to_list(10), "unread_convos")
    for c in unread:
        contact = c.get("contact", {})
        items.append({"id": f"msg_{c['_id']}", "type": "unread_message", "feed": "for_you", "category": "replies", "priority": 2,
                      "title": "Unread Message", "body": f"From {contact.get('name', 'Unknown')}",
                      "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}",
                      "contact_name": contact.get("name"), "timestamp": _ts(c.get("updated_at")), "read": False, "source": "messages"})

    # 5. FLAGGED CONVERSATIONS (Activity)
    flagged = await _run_section(db.conversations.find({"participants": user_id, "flagged": True}).sort("updated_at", -1).limit(5).to_list(5), "flagged_convos")
    for c in flagged:
        contact = c.get("contact", {})
        items.append({"id": f"flag_{c['_id']}", "type": "flagged", "feed": "activity", "category": "activity", "priority": 6,
                      "title": "Flagged Conversation", "body": contact.get("name", "Unknown"),
                      "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}",
                      "contact_name": contact.get("name"), "timestamp": _ts(c.get("updated_at")), "read": True, "source": "flags"})

    # 6. RECENT CONTACT EVENTS (Activity, last 24h)
    cutoff = now - timedelta(hours=24)
    recent = await _run_section(db.contact_events.find({"user_id": user_id, "timestamp": {"$gte": cutoff}, "event_type": {"$in": ["link_click", "review_submitted", "new_contact", "digital_card_sent", "review_request_sent", "congrats_card_sent", "email_sent", "sms_sent"]}}).sort("timestamp", -1).limit(15).to_list(15), "recent_activity")
    for ev in recent:
        items.append({"id": f"evt_{ev['_id']}", "type": ev.get("event_type", "activity"), "feed": "activity", "category": "activity", "priority": 6,
                      "title": ev.get("title") or ev.get("event_type", "Activity").replace("_", " ").title(),
                      "body": ev.get("description", ""), "link": f"/contact/{ev.get('contact_id', '')}",
                      "timestamp": _ts(ev.get("timestamp")), "read": True, "source": "activity"})

    # 7. PENDING CAMPAIGN SENDS (Activity)
    pending_sends = await _run_section(db.campaign_pending_sends.find({"user_id": user_id, "status": "pending"}).sort("created_at", -1).limit(5).to_list(5), "pending_sends")
    for ps in pending_sends:
        contact_id = ps.get("contact_id", ""); message_content = ps.get("message", ""); prefill = urllib.parse.quote(message_content[:500]) if message_content else ""
        items.append({"id": f"csend_{ps['_id']}", "type": "campaign_send", "feed": "activity", "category": "activity", "priority": 5,
                      "title": f"Send: {ps.get('campaign_name', 'Campaign')}",
                      "body": f"Step {ps.get('step', 0)} to {ps.get('contact_name', 'contact')} via {ps.get('channel', 'sms').upper()}",
                      "link": f"/contact/{contact_id}?prefill={prefill}" if contact_id else None,
                      "contact_name": ps.get("contact_name"), "contact_id": contact_id,
                      "timestamp": _ts(ps.get("created_at")), "read": False, "source": "campaigns"})

    # Read overlay (virtual items: tasks, messages, events)
    reads = await _run_section(db.notification_reads.find_one({"user_id": user_id}), "read_status", None)
    if reads:
        read_ids = set(reads.get("read_ids", []))
        for n in items:
            if n["id"] in read_ids:
                n["read"] = True

    # Sort: priority asc, then newest first within each priority
    items.sort(key=lambda n: n["priority"])
    sorted_items = []
    for _, group in groupby(items, key=lambda n: n["priority"]):
        grp = list(group)
        grp.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
        sorted_items.extend(grp)

    for_you = [n for n in sorted_items if n["feed"] == "for_you"]
    category_counts = {c: 0 for c in FOR_YOU_CATEGORIES}
    for n in for_you:
        category_counts[n["category"]] = category_counts.get(n["category"], 0) + 1
    unread_count = sum(1 for n in for_you if not n["read"])
    activity_count = sum(1 for n in sorted_items if n["feed"] == "activity")

    return {
        "items": sorted_items,
        "unread_count": unread_count,
        "category_counts": category_counts,
        "activity_count": activity_count,
    }


@router.get("/{user_id}")
async def get_notifications(user_id: str, limit: int = 50, category: str = "all", feed: str = "for_you"):
    """Filtered feed. feed=for_you (default) or activity; category applies to for_you only."""
    built = await _get_full_feed(user_id)
    if feed == "activity":
        filtered = [n for n in built["items"] if n["feed"] == "activity"]
        filtered.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
    else:
        filtered = [n for n in built["items"] if n["feed"] == "for_you"]
        if category not in ("all", ""):
            filtered = [n for n in filtered if n["category"] == category]
    return {
        "success": True,
        "notifications": filtered[:limit],
        "unread_count": built["unread_count"],
        "total": len(filtered),
        "category_counts": built["category_counts"],
        "activity_count": built["activity_count"],
        "timed_out": built.get("timed_out", False),
    }


@router.get("/{user_id}/unread-count")
async def get_unread_count(user_id: str):
    """Badge count = unread items in the For You feed — always matches what the user sees."""
    try:
        built = await _get_full_feed(user_id)
        return {"count": built["unread_count"]}
    except Exception as e:
        logger.error(f"Unread count error for {user_id}: {e}")
        return {"count": 0}


@router.post("/{user_id}/read")
async def mark_notifications_read(user_id: str, data: dict = None):
    """Mark specific notifications as read."""
    db = get_db()
    data = data or {}
    ids = data.get("ids", [])

    for nid in ids:
        if not nid.startswith(("task_", "msg_", "flag_", "evt_", "task_soon_", "csend_")):
            try:
                await db.notifications.update_one({"_id": ObjectId(nid)}, {"$set": {"read": True}})
            except Exception:
                pass

    if ids:
        await db.notification_reads.update_one(
            {"user_id": user_id},
            {"$addToSet": {"read_ids": {"$each": ids}}},
            upsert=True,
        )

    _notifications_cache.pop(user_id, None)
    return {"success": True, "message": "Marked as read"}


@router.post("/{user_id}/read-all")
async def mark_all_read(user_id: str):
    """Mark everything read (items stay visible, just no longer count as unread)."""
    db = get_db()
    result = await db.notifications.update_many(
        {"user_id": user_id, "read": {"$ne": True}},
        {"$set": {"read": True}},
    )

    # Record virtual ids (tasks, messages, events) in the read overlay
    built = await _get_full_feed(user_id)
    all_ids = [n["id"] for n in built["items"]]
    if all_ids:
        await db.notification_reads.update_one(
            {"user_id": user_id},
            {"$set": {"read_ids": all_ids, "last_cleared_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    _notifications_cache.pop(user_id, None)
    return {"success": True, "message": "All marked as read", "count": result.modified_count}
