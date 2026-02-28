"""
Notifications Center — Smart activity hub with prioritized alerts.
Aggregates tasks, unread messages, flags, lead alerts, and system events into a unified feed.
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from bson import ObjectId
from pymongo import MongoClient
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notification-center", tags=["notification-center"])


def get_db():
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise Exception("MONGO_URL not configured")
    client = MongoClient(mongo_url)
    return client[os.environ.get("DB_NAME", "test_database")]


def _ts(val) -> str:
    """Safely convert any timestamp to ISO string."""
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val else datetime.now(timezone.utc).isoformat()


@router.get("/{user_id}")
async def get_notifications(user_id: str, limit: int = 50, category: str = "all"):
    """Get prioritized notifications for a user from all sources."""
    db = get_db()
    now = datetime.now(timezone.utc)
    notifications = []

    # 1. LEAD NOTIFICATIONS from existing notifications collection (highest priority)
    try:
        user_teams = []
        teams = list(db.teams.find({"members": user_id}))
        user_teams.extend([str(t["_id"]) for t in teams])
        shared_inboxes = list(db.shared_inboxes.find({"user_ids": user_id}))
        user_teams.extend([str(si["_id"]) for si in shared_inboxes])

        lead_query = {
            "$or": [
                {"user_id": user_id},
                {"team_id": {"$in": user_teams}, "user_id": None}
            ],
            "dismissed": False,
        }
        leads = list(db.notifications.find(lead_query).sort("created_at", -1).limit(15))
        for n in leads:
            notifications.append({
                "id": str(n["_id"]),
                "type": n.get("type", "lead"),
                "category": "leads",
                "priority": 0 if not n.get("read") else 3,
                "title": n.get("title", "New Lead"),
                "body": n.get("message", ""),
                "link": f"/thread/{n.get('conversation_id', '')}?contact_name={n.get('contact_name', '')}" if n.get("conversation_id") else None,
                "contact_name": n.get("contact_name"),
                "timestamp": _ts(n.get("created_at")),
                "read": n.get("read", False),
                "source": "leads",
            })
    except Exception as e:
        logger.debug(f"Lead notifications: {e}")

    # 2. OVERDUE TASKS
    try:
        overdue = list(db.tasks.find({
            "user_id": user_id,
            "status": {"$ne": "completed"},
            "due_date": {"$lt": now.isoformat()}
        }).sort("due_date", 1).limit(10))
        for t in overdue:
            notifications.append({
                "id": f"task_{t['_id']}",
                "type": "task_overdue",
                "category": "tasks",
                "priority": 1,
                "title": "Overdue Task",
                "body": t.get("title", "Follow up"),
                "link": f"/contact/{t.get('contact_id', '')}",
                "timestamp": _ts(t.get("due_date")),
                "read": False,
                "source": "tasks",
            })
    except Exception as e:
        logger.debug(f"Overdue tasks: {e}")

    # 3. UPCOMING TASKS (due within 24h)
    try:
        tomorrow = (now + timedelta(hours=24)).isoformat()
        upcoming = list(db.tasks.find({
            "user_id": user_id,
            "status": {"$ne": "completed"},
            "due_date": {"$gte": now.isoformat(), "$lte": tomorrow}
        }).sort("due_date", 1).limit(5))
        for t in upcoming:
            notifications.append({
                "id": f"task_soon_{t['_id']}",
                "type": "task_due_soon",
                "category": "tasks",
                "priority": 2,
                "title": "Task Due Soon",
                "body": t.get("title", "Follow up"),
                "link": f"/contact/{t.get('contact_id', '')}",
                "timestamp": _ts(t.get("due_date")),
                "read": False,
                "source": "tasks",
            })
    except Exception as e:
        logger.debug(f"Upcoming tasks: {e}")

    # 4. UNREAD CONVERSATIONS
    try:
        unread = list(db.conversations.find({
            "participants": user_id,
            "unread": True,
        }).sort("updated_at", -1).limit(10))
        for c in unread:
            contact = c.get("contact", {})
            notifications.append({
                "id": f"msg_{c['_id']}",
                "type": "unread_message",
                "category": "messages",
                "priority": 3,
                "title": "Unread Message",
                "body": f"From {contact.get('name', 'Unknown')}",
                "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}",
                "contact_name": contact.get("name"),
                "timestamp": _ts(c.get("updated_at")),
                "read": False,
                "source": "messages",
            })
    except Exception as e:
        logger.debug(f"Unread convos: {e}")

    # 5. FLAGGED CONVERSATIONS
    try:
        flagged = list(db.conversations.find({
            "participants": user_id,
            "flagged": True,
        }).sort("updated_at", -1).limit(5))
        for c in flagged:
            contact = c.get("contact", {})
            notifications.append({
                "id": f"flag_{c['_id']}",
                "type": "flagged",
                "category": "flags",
                "priority": 4,
                "title": "Flagged Conversation",
                "body": contact.get("name", "Unknown"),
                "link": f"/thread/{c['_id']}?contact_name={contact.get('name', '')}",
                "contact_name": contact.get("name"),
                "timestamp": _ts(c.get("updated_at")),
                "read": True,
                "source": "flags",
            })
    except Exception as e:
        logger.debug(f"Flagged: {e}")

    # 6. RECENT ACTIVITY (last 48h - informational)
    try:
        cutoff = now - timedelta(hours=48)
        recent = list(db.contact_events.find({
            "user_id": user_id,
            "timestamp": {"$gte": cutoff},
            "event_type": {"$in": [
                "link_click", "review_submitted", "new_contact",
                "digital_card_sent", "review_request_sent", "congrats_card_sent",
                "email_sent", "sms_sent",
            ]}
        }).sort("timestamp", -1).limit(15))
        for ev in recent:
            notifications.append({
                "id": f"evt_{ev['_id']}",
                "type": ev.get("event_type", "activity"),
                "category": "activity",
                "priority": 5,
                "title": ev.get("title") or ev.get("event_type", "Activity").replace("_", " ").title(),
                "body": ev.get("description", ""),
                "link": f"/contact/{ev.get('contact_id', '')}",
                "timestamp": _ts(ev.get("timestamp")),
                "read": True,
                "source": "activity",
            })
    except Exception as e:
        logger.debug(f"Recent activity: {e}")

    # Filter by category if specified
    if category != "all":
        notifications = [n for n in notifications if n["category"] == category]

    # Sort by priority, then by timestamp desc
    notifications.sort(key=lambda n: (n["priority"], ""), reverse=False)
    # Secondary sort: within same priority, newest first
    notifications.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
    notifications.sort(key=lambda n: n["priority"])

    # Read status overlay from user's notification_reads
    try:
        reads = db.notification_reads.find_one({"user_id": user_id})
        read_ids = set((reads or {}).get("read_ids", []))
        for n in notifications:
            if n["id"] in read_ids:
                n["read"] = True
    except Exception:
        pass

    unread_count = sum(1 for n in notifications if not n["read"])
    category_counts = {}
    for n in notifications:
        cat = n.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "success": True,
        "notifications": notifications[:limit],
        "unread_count": unread_count,
        "total": len(notifications),
        "category_counts": category_counts,
    }


@router.get("/{user_id}/unread-count")
async def get_unread_count(user_id: str):
    """Fast unread count for badge display."""
    result = await get_notifications(user_id, limit=100)
    return {"count": result["unread_count"]}


@router.post("/{user_id}/read")
async def mark_notifications_read(user_id: str, data: dict = {}):
    """Mark specific notifications as read."""
    db = get_db()
    ids = data.get("ids", [])

    # For lead notifications, also mark in the notifications collection
    for nid in ids:
        if not nid.startswith(("task_", "msg_", "flag_", "evt_", "task_soon_")):
            try:
                db.notifications.update_one(
                    {"_id": ObjectId(nid)},
                    {"$set": {"read": True}}
                )
            except Exception:
                pass

    if ids:
        db.notification_reads.update_one(
            {"user_id": user_id},
            {"$addToSet": {"read_ids": {"$each": ids}}},
            upsert=True,
        )
    return {"success": True, "message": "Marked as read"}


@router.post("/{user_id}/read-all")
async def mark_all_read(user_id: str):
    """Mark all current notifications as read."""
    db = get_db()
    notifs = await get_notifications(user_id, limit=200)
    all_ids = [n["id"] for n in notifs.get("notifications", [])]

    # Also mark lead notifications as read in the notifications collection
    for nid in all_ids:
        if not nid.startswith(("task_", "msg_", "flag_", "evt_", "task_soon_")):
            try:
                db.notifications.update_one(
                    {"_id": ObjectId(nid)},
                    {"$set": {"read": True}}
                )
            except Exception:
                pass

    if all_ids:
        db.notification_reads.update_one(
            {"user_id": user_id},
            {"$set": {"read_ids": all_ids}},
            upsert=True,
        )
    return {"success": True, "message": "All marked as read", "count": len(all_ids)}
