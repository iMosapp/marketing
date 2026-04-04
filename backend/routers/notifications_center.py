"""
Notifications Center  - Smart activity hub with prioritized alerts.
Aggregates tasks, unread messages, flags, lead alerts, and system events into a unified feed.
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

# Cache the full notification list per user (30s TTL) — prevents 8 queries on every Hub load
_notifications_cache: TTLCache = TTLCache(maxsize=500, ttl=30)

# Cache unread count separately (30-sec TTL)
_unread_cache: TTLCache = TTLCache(maxsize=1000, ttl=30)
_UNREAD_TTL = timedelta(seconds=15)

# Hard timeout for each DB section — prevents runaway queries from crashing the worker
_SECTION_TIMEOUT = 3.0   # seconds per section
_TOTAL_TIMEOUT   = 10.0  # seconds total for full endpoint


def _ts(val) -> str:
    """Safely convert any timestamp to ISO string."""
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val else datetime.now(timezone.utc).isoformat()


async def _get_user_teams(db, user_id: str) -> list:
    """Get team IDs for a user (shared across endpoints)."""
    user_teams = []
    try:
        teams = await db.teams.find({"members": user_id}, {"_id": 1}).to_list(50)
        user_teams.extend([str(t["_id"]) for t in teams])
        shared_inboxes = await db.shared_inboxes.find({"user_ids": user_id}, {"_id": 1}).to_list(50)
        user_teams.extend([str(si["_id"]) for si in shared_inboxes])
    except Exception:
        pass
    return user_teams


@router.get("/{user_id}")
async def get_notifications(user_id: str, limit: int = 50, category: str = "all"):
    """Get prioritized notifications for a user from all sources.
    
    Cached per user for 30 seconds — prevents 8 sequential DB queries on every Hub page load.
    Each section has a 3-second timeout — a slow query in one section won't crash the worker.
    """
    # Return cached result if available (same user + category)
    cache_key = f"{user_id}:{category}"
    if cache_key in _notifications_cache:
        return _notifications_cache[cache_key]

    try:
        result = await asyncio.wait_for(
            _build_notifications(user_id, limit, category),
            timeout=_TOTAL_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"[NotificationsCenter] Timeout for user {user_id} after {_TOTAL_TIMEOUT}s")
        result = {"success": True, "notifications": [], "unread_count": 0, "total": 0, "category_counts": {}, "timed_out": True}

    _notifications_cache[cache_key] = result
    return result


async def _run_section(coro, section_name: str, fallback=None):
    """Run a DB query with a per-section timeout. Returns fallback on timeout or error."""
    try:
        return await asyncio.wait_for(coro, timeout=_SECTION_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"[NotificationsCenter] Section '{section_name}' timed out after {_SECTION_TIMEOUT}s")
        return fallback if fallback is not None else []
    except Exception as e:
        logger.debug(f"[NotificationsCenter] Section '{section_name}' error: {e}")
        return fallback if fallback is not None else []


async def _build_notifications(user_id: str, limit: int, category: str) -> dict:
    """Build notifications from all sources with per-section timeouts.
    Each section gets _SECTION_TIMEOUT seconds; if any section is slow it's skipped gracefully.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    notifications = []

    user_teams = await _run_section(_get_user_teams(db, user_id), "teams", [])

    # 1. LEAD NOTIFICATIONS
    lead_query = {"$or": [{"user_id": user_id}, {"team_id": {"$in": user_teams}, "user_id": None}], "dismissed": False}
    leads = await _run_section(db.notifications.find(lead_query).sort("created_at", -1).limit(15).to_list(15), "leads")
    for n in leads:
        contact_id = n.get("contact_id", "")
        conversation_id = n.get("conversation_id", "")
        link = f"/contact/{contact_id}" if contact_id else (f"/thread/{conversation_id}?contact_name={n.get('contact_name', '')}" if conversation_id else ("/admin/lead-tracking" if n.get("demo_request_id") else None))
        body = n.get("form_details", n.get("message", "")) if n.get("type") in ("new_lead", "new_demo_request") and n.get("form_details") else n.get("message", "")
        notifications.append({"id": str(n["_id"]), "type": n.get("type", "lead"), "category": "leads" if n.get("type") in ("new_lead", "lead_assigned", "jump_ball") else "campaigns", "priority": 0 if not n.get("read") else 3, "title": n.get("title", "New Lead"), "body": body, "link": link, "contact_name": n.get("contact_name"), "contact_id": contact_id, "demo_request_id": n.get("demo_request_id", ""), "lead_email": n.get("lead_email", ""), "lead_phone": n.get("lead_phone", ""), "referred_by_name": n.get("referred_by_name", ""), "timestamp": _ts(n.get("created_at")), "read": n.get("read", False), "source": "leads"})

    # 2. OVERDUE TASKS
    overdue = await _run_section(db.tasks.find({"user_id": user_id, "completed": {"$ne": True}, "due_date": {"$lt": now}}).sort("due_date", 1).limit(10).to_list(10), "overdue_tasks")
    for t in overdue:
        contact_id = t.get("contact_id", ""); desc = t.get("description", ""); title = t.get("title", "Follow up"); task_id = str(t["_id"])
        prefill = urllib.parse.quote(desc[:500]) if desc else ""
        link = f"/contact/{contact_id}?taskId={task_id}&taskTitle={urllib.parse.quote(title[:200])}&prefill={prefill}" if contact_id else None
        notifications.append({"id": f"task_{task_id}", "type": "task_overdue", "category": "tasks", "priority": 1, "title": "Overdue Task", "body": title, "link": link, "contact_id": contact_id, "timestamp": _ts(t.get("due_date")), "read": False, "source": "tasks"})

    # 3. UPCOMING TASKS (due within 24h)
    tomorrow = now + timedelta(hours=24)
    upcoming = await _run_section(db.tasks.find({"user_id": user_id, "completed": {"$ne": True}, "due_date": {"$gte": now, "$lte": tomorrow}}).sort("due_date", 1).limit(5).to_list(5), "upcoming_tasks")
    for t in upcoming:
        contact_id = t.get("contact_id", ""); desc = t.get("description", ""); title = t.get("title", "Follow up"); task_id = str(t["_id"])
        prefill = urllib.parse.quote(desc[:500]) if desc else ""
        link = f"/contact/{contact_id}?taskId={task_id}&taskTitle={urllib.parse.quote(title[:200])}&prefill={prefill}" if contact_id else None
        notifications.append({"id": f"task_soon_{task_id}", "type": "task_due_soon", "category": "tasks", "priority": 2, "title": "Task Due Soon", "body": title, "link": link, "contact_id": contact_id, "timestamp": _ts(t.get("due_date")), "read": False, "source": "tasks"})

    # 4. UNREAD CONVERSATIONS
    unread = await _run_section(db.conversations.find({"participants": user_id, "unread": True}).sort("updated_at", -1).limit(10).to_list(10), "unread_convos")
    for c in unread:
        contact = c.get("contact", {})
        notifications.append({"id": f"msg_{c['_id']}", "type": "unread_message", "category": "messages", "priority": 3, "title": "Unread Message", "body": f"From {contact.get('name', 'Unknown')}", "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}", "contact_name": contact.get("name"), "timestamp": _ts(c.get("updated_at")), "read": False, "source": "messages"})

    # 5. FLAGGED CONVERSATIONS
    flagged = await _run_section(db.conversations.find({"participants": user_id, "flagged": True}).sort("updated_at", -1).limit(5).to_list(5), "flagged_convos")
    for c in flagged:
        contact = c.get("contact", {})
        notifications.append({"id": f"flag_{c['_id']}", "type": "flagged", "category": "flags", "priority": 4, "title": "Flagged Conversation", "body": contact.get("name", "Unknown"), "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}", "contact_name": contact.get("name"), "timestamp": _ts(c.get("updated_at")), "read": True, "source": "flags"})

    # 6. RECENT ACTIVITY (last 24h — tightened from 48h)
    cutoff = now - timedelta(hours=24)
    recent = await _run_section(db.contact_events.find({"user_id": user_id, "timestamp": {"$gte": cutoff}, "event_type": {"$in": ["link_click", "review_submitted", "new_contact", "digital_card_sent", "review_request_sent", "congrats_card_sent", "email_sent", "sms_sent"]}}).sort("timestamp", -1).limit(15).to_list(15), "recent_activity")
    for ev in recent:
        notifications.append({"id": f"evt_{ev['_id']}", "type": ev.get("event_type", "activity"), "category": "activity", "priority": 5, "title": ev.get("title") or ev.get("event_type", "Activity").replace("_", " ").title(), "body": ev.get("description", ""), "link": f"/contact/{ev.get('contact_id', '')}", "timestamp": _ts(ev.get("timestamp")), "read": True, "source": "activity"})

    # 7. PENDING CAMPAIGN SENDS
    pending_sends = await _run_section(db.campaign_pending_sends.find({"user_id": user_id, "status": "pending"}).sort("created_at", -1).limit(5).to_list(5), "pending_sends")
    for ps in pending_sends:
        contact_id = ps.get("contact_id", ""); message_content = ps.get("message", ""); prefill = urllib.parse.quote(message_content[:500]) if message_content else ""
        notifications.append({"id": f"csend_{ps['_id']}", "type": "campaign_send", "category": "campaigns", "priority": 1, "title": f"Send: {ps.get('campaign_name', 'Campaign')}", "body": f"Step {ps.get('step', 0)} to {ps.get('contact_name', 'contact')} via {ps.get('channel', 'sms').upper()}", "link": f"/contact/{contact_id}?prefill={prefill}" if contact_id else None, "contact_name": ps.get("contact_name"), "contact_id": contact_id, "timestamp": _ts(ps.get("created_at")), "read": False, "source": "campaigns"})

    # 8. ENGAGEMENT SIGNALS (last 24h)
    cutoff24 = datetime.now(timezone.utc) - timedelta(hours=24)
    eng_signals = await _run_section(db.notifications.find({"type": "engagement_signal", "user_id": user_id, "created_at": {"$gte": cutoff24}}).sort("created_at", -1).limit(10).to_list(10), "engagement_signals")
    for sig in eng_signals:
        contact_id = sig.get("contact_id", ""); is_return = sig.get("is_return_visit", False); view_count = sig.get("view_count", 1)
        notifications.append({"id": f"eng_{sig['_id']}", "type": "engagement_signal", "category": "engagement", "priority": 0 if (is_return or view_count >= 3) else 1, "title": sig.get("title", "Customer engaged"), "body": sig.get("message", ""), "icon": sig.get("icon", "eye"), "color": sig.get("color", "#007AFF"), "link": f"/contact/{contact_id}" if contact_id else None, "contact_name": sig.get("contact_name"), "contact_id": contact_id, "is_return_visit": is_return, "view_count": view_count, "timestamp": _ts(sig.get("created_at")), "read": sig.get("read", False), "source": "engagement"})

    # Count + filter + sort
    category_counts = {}
    for n in notifications:
        cat = n.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    filtered = notifications if category == "all" else [n for n in notifications if n["category"] == category]
    filtered.sort(key=lambda n: n["priority"])
    sorted_notifs = []
    for _, group in groupby(filtered, key=lambda n: n["priority"]):
        grp = list(group)
        grp.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
        sorted_notifs.extend(grp)

    # Read status overlay
    reads = await _run_section(db.notification_reads.find_one({"user_id": user_id}), "read_status", None)
    if reads:
        read_ids = set(reads.get("read_ids", []))
        for n in sorted_notifs:
            if n["id"] in read_ids:
                n["read"] = True

    unread_count = sum(1 for n in sorted_notifs if not n["read"])
    return {"success": True, "notifications": sorted_notifs[:limit], "unread_count": unread_count, "total": len(sorted_notifs), "category_counts": category_counts}


@router.get("/{user_id}/unread-count")
async def get_unread_count(user_id: str):
    """Fast unread count for badge display — cached for 15s."""
    now = datetime.now(timezone.utc)
    cached = _unread_cache.get(user_id)
    if cached:
        return cached[1]  # TTLCache handles expiry automatically

    try:
        db = get_db()
        user_teams = await _get_user_teams(db, user_id)

        lead_count = 0
        try:
            lead_query = {
                "$or": [
                    {"user_id": user_id},
                    {"team_id": {"$in": user_teams}, "user_id": None}
                ],
                "dismissed": False,
                "read": {"$ne": True},
            }
            lead_count = await db.notifications.count_documents(lead_query)
        except Exception:
            pass

        overdue_count = 0
        try:
            # Exclude campaign_send tasks from badge — they have their own notification flow
            # and shouldn't double-count in the overdue badge
            overdue_count = await db.tasks.count_documents({
                "user_id": user_id,
                "completed": {"$ne": True},
                "due_date": {"$lt": now},
                "type": {"$nin": ["campaign_send", "campaign_step"]},
            })
        except Exception:
            pass

        unread_msg_count = 0
        try:
            unread_msg_count = await db.messages.count_documents({
                "recipient_id": user_id,
                "read": {"$ne": True},
                "sender_id": {"$ne": user_id},
            })
        except Exception:
            pass

        total_unread = lead_count + overdue_count + unread_msg_count
        try:
            reads = await db.notification_reads.find_one({"user_id": user_id})
            if reads:
                total_unread = max(0, total_unread - len(reads.get("read_ids", [])))
        except Exception:
            pass

        result = {"count": total_unread}
        _unread_cache[user_id] = (now, result)
        return result
    except Exception as e:
        logger.error(f"Unread count error for {user_id}: {e}")
        return {"count": 0}


@router.post("/{user_id}/read")
async def mark_notifications_read(user_id: str, data: dict = {}):
    """Mark specific notifications as read."""
    db = get_db()
    ids = data.get("ids", [])

    for nid in ids:
        if not nid.startswith(("task_", "msg_", "flag_", "evt_", "task_soon_")):
            try:
                await db.notifications.update_one(
                    {"_id": ObjectId(nid)},
                    {"$set": {"read": True}}
                )
            except Exception:
                pass

    if ids:
        await db.notification_reads.update_one(
            {"user_id": user_id},
            {"$addToSet": {"read_ids": {"$each": ids}}},
            upsert=True,
        )

    # Invalidate cache
    _unread_cache.pop(user_id, None)
    return {"success": True, "message": "Marked as read"}


@router.post("/{user_id}/read-all")
async def mark_all_read(user_id: str):
    """Mark all notifications as read AND dismissed — prevents them re-appearing in the count."""
    db = get_db()

    # Single update_many — far faster than looping one-by-one
    result = await db.notifications.update_many(
        {"user_id": user_id, "dismissed": {"$ne": True}},
        {"$set": {"read": True, "dismissed": True}},
    )

    # Also record in notification_reads for virtual notification types (tasks, messages)
    notifs = await get_notifications(user_id, limit=200)
    all_ids = [n["id"] for n in notifs.get("notifications", [])]
    if all_ids:
        await db.notification_reads.update_one(
            {"user_id": user_id},
            {"$set": {"read_ids": all_ids, "last_cleared_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    # Invalidate cache so next poll reflects the cleared state immediately
    _unread_cache.pop(user_id, None)
    return {"success": True, "message": "All marked as read", "count": result.modified_count}
