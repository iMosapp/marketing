"""
Notifications Center — Smart activity hub with prioritized alerts.
Aggregates tasks, unread messages, flags, system events into a unified feed.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/{user_id}")
async def get_notifications(user_id: str, limit: int = 50):
    """Get prioritized notifications for a user."""
    db = get_db()
    now = datetime.now(timezone.utc)
    notifications = []

    # 1. OVERDUE TASKS (highest priority)
    try:
        tasks = await db.tasks.find({
            "user_id": user_id,
            "status": {"$ne": "completed"},
            "due_date": {"$lt": now.isoformat()}
        }).sort("due_date", 1).limit(10).to_list(10)
        for t in tasks:
            notifications.append({
                "id": str(t["_id"]),
                "type": "task_overdue",
                "category": "action",
                "priority": 1,
                "title": "Overdue Task",
                "body": t.get("title", "Follow up"),
                "link": f"/contact/{t.get('contact_id', '')}",
                "timestamp": t.get("due_date", now.isoformat()),
                "read": False,
            })
    except Exception as e:
        logger.debug(f"Tasks query: {e}")

    # 2. UPCOMING TASKS (due within 24h)
    try:
        tomorrow = (now + timedelta(hours=24)).isoformat()
        upcoming = await db.tasks.find({
            "user_id": user_id,
            "status": {"$ne": "completed"},
            "due_date": {"$gte": now.isoformat(), "$lte": tomorrow}
        }).sort("due_date", 1).limit(5).to_list(5)
        for t in upcoming:
            notifications.append({
                "id": str(t["_id"]),
                "type": "task_due_soon",
                "category": "action",
                "priority": 2,
                "title": "Task Due Soon",
                "body": t.get("title", "Follow up"),
                "link": f"/contact/{t.get('contact_id', '')}",
                "timestamp": t.get("due_date", now.isoformat()),
                "read": False,
            })
    except Exception as e:
        logger.debug(f"Upcoming tasks: {e}")

    # 3. UNREAD CONVERSATIONS
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        org_id = (user_doc or {}).get("organization_id") or (user_doc or {}).get("org_id", "")
        unread = await db.conversations.find({
            "participants": user_id,
            "unread": True,
        }).sort("updated_at", -1).limit(10).to_list(10)
        for c in unread:
            contact = c.get("contact", {})
            notifications.append({
                "id": str(c["_id"]),
                "type": "unread_message",
                "category": "action",
                "priority": 3,
                "title": "Unread Message",
                "body": f"From {contact.get('name', 'Unknown')}",
                "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}",
                "timestamp": c.get("updated_at", now).isoformat() if isinstance(c.get("updated_at"), datetime) else str(c.get("updated_at", "")),
                "read": False,
            })
    except Exception as e:
        logger.debug(f"Unread convos: {e}")

    # 4. FLAGGED CONVERSATIONS
    try:
        flagged = await db.conversations.find({
            "participants": user_id,
            "flagged": True,
        }).sort("updated_at", -1).limit(5).to_list(5)
        for c in flagged:
            contact = c.get("contact", {})
            notifications.append({
                "id": f"flag_{c['_id']}",
                "type": "flagged",
                "category": "action",
                "priority": 4,
                "title": "Flagged Conversation",
                "body": contact.get("name", "Unknown"),
                "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}",
                "timestamp": c.get("updated_at", now).isoformat() if isinstance(c.get("updated_at"), datetime) else str(c.get("updated_at", "")),
                "read": False,
            })
    except Exception as e:
        logger.debug(f"Flagged: {e}")

    # 5. RECENT ACTIVITY (last 48h - informational)
    try:
        cutoff = now - timedelta(hours=48)
        recent = await db.contact_events.find({
            "user_id": user_id,
            "timestamp": {"$gte": cutoff},
            "event_type": {"$in": ["link_click", "review_submitted", "new_contact"]}
        }).sort("timestamp", -1).limit(10).to_list(10)
        for e in recent:
            notifications.append({
                "id": str(e["_id"]),
                "type": e.get("event_type", "activity"),
                "category": "activity",
                "priority": 5,
                "title": e.get("title", "Activity"),
                "body": e.get("description", ""),
                "link": f"/contact/{e.get('contact_id', '')}",
                "timestamp": e["timestamp"].isoformat() if isinstance(e.get("timestamp"), datetime) else str(e.get("timestamp", "")),
                "read": True,
            })
    except Exception as e:
        logger.debug(f"Recent activity: {e}")

    # 6. BADGE EARNED (from leaderboard)
    try:
        latest_badge = await db.contact_intel.find_one(
            {"user_id": user_id, "type": "badge_earned"},
            sort=[("created_at", -1)]
        )
        if latest_badge and latest_badge.get("created_at"):
            ts = latest_badge["created_at"]
            notifications.append({
                "id": str(latest_badge["_id"]),
                "type": "badge_earned",
                "category": "system",
                "priority": 6,
                "title": "Badge Earned!",
                "body": latest_badge.get("summary", "You earned a new badge"),
                "link": "/leaderboard",
                "timestamp": ts.isoformat() if isinstance(ts, datetime) else str(ts),
                "read": True,
            })
    except Exception as e:
        logger.debug(f"Badges: {e}")

    # Sort by priority, then by timestamp desc
    notifications.sort(key=lambda n: (n["priority"], n.get("timestamp", "")), reverse=False)

    # Read status from user's notification_reads
    try:
        reads = await db.notification_reads.find_one({"user_id": user_id})
        read_ids = set((reads or {}).get("read_ids", []))
        for n in notifications:
            if n["id"] in read_ids:
                n["read"] = True
    except Exception:
        pass

    unread_count = sum(1 for n in notifications if not n["read"])

    return {
        "notifications": notifications[:limit],
        "unread_count": unread_count,
        "total": len(notifications),
    }


@router.post("/{user_id}/read")
async def mark_notifications_read(user_id: str, data: dict = {}):
    """Mark notifications as read."""
    db = get_db()
    ids = data.get("ids", [])
    if ids:
        await db.notification_reads.update_one(
            {"user_id": user_id},
            {"$addToSet": {"read_ids": {"$each": ids}}},
            upsert=True,
        )
    return {"message": "Marked as read"}


@router.post("/{user_id}/read-all")
async def mark_all_read(user_id: str):
    """Mark all current notifications as read."""
    db = get_db()
    notifs = await get_notifications(user_id, limit=100)
    all_ids = [n["id"] for n in notifs.get("notifications", [])]
    if all_ids:
        await db.notification_reads.update_one(
            {"user_id": user_id},
            {"$set": {"read_ids": all_ids}},
            upsert=True,
        )
    return {"message": "All marked as read", "count": len(all_ids)}
