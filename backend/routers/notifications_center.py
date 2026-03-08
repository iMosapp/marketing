"""
Notifications Center  - Smart activity hub with prioritized alerts.
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
            contact_id = n.get("contact_id", "")
            conversation_id = n.get("conversation_id", "")
            # Build the best link: prefer contact detail, fallback to thread, then lead tracking
            if contact_id:
                link = f"/contact/{contact_id}"
            elif conversation_id:
                link = f"/thread/{conversation_id}?contact_name={n.get('contact_name', '')}"
            elif n.get("demo_request_id"):
                link = "/admin/lead-tracking"
            else:
                link = None

            # For new lead notifications, show form details in body
            body = n.get("message", "")
            form_details = n.get("form_details", "")
            if form_details and n.get("type") in ("new_lead", "new_demo_request"):
                body = form_details

            notifications.append({
                "id": str(n["_id"]),
                "type": n.get("type", "lead"),
                "category": "leads" if n.get("type") in ("new_lead", "lead_assigned", "jump_ball") else "campaigns",
                "priority": 0 if not n.get("read") else 3,
                "title": n.get("title", "New Lead"),
                "body": body,
                "link": link,
                "contact_name": n.get("contact_name"),
                "contact_id": contact_id,
                "demo_request_id": n.get("demo_request_id", ""),
                "lead_email": n.get("lead_email", ""),
                "lead_phone": n.get("lead_phone", ""),
                "referred_by_name": n.get("referred_by_name", ""),
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
            "completed": {"$ne": True},
            "due_date": {"$lt": now}
        }).sort("due_date", 1).limit(10))
        for t in overdue:
            contact_id = t.get("contact_id", "")
            desc = t.get("description", "")
            title = t.get("title", "Follow up")
            task_id = str(t["_id"])
            import urllib.parse
            prefill = urllib.parse.quote(desc[:500]) if desc else ""
            task_title_enc = urllib.parse.quote(title[:200])
            link = f"/contact/{contact_id}?taskId={task_id}&taskTitle={task_title_enc}&prefill={prefill}" if contact_id else None
            notifications.append({
                "id": f"task_{t['_id']}",
                "type": "task_overdue",
                "category": "tasks",
                "priority": 1,
                "title": "Overdue Task",
                "body": title,
                "link": link,
                "contact_id": contact_id,
                "timestamp": _ts(t.get("due_date")),
                "read": False,
                "source": "tasks",
            })
    except Exception as e:
        logger.debug(f"Overdue tasks: {e}")

    # 3. UPCOMING TASKS (due within 24h)
    try:
        tomorrow = now + timedelta(hours=24)
        upcoming = list(db.tasks.find({
            "user_id": user_id,
            "completed": {"$ne": True},
            "due_date": {"$gte": now, "$lte": tomorrow}
        }).sort("due_date", 1).limit(5))
        for t in upcoming:
            contact_id = t.get("contact_id", "")
            desc = t.get("description", "")
            title = t.get("title", "Follow up")
            task_id = str(t["_id"])
            prefill = urllib.parse.quote(desc[:500]) if desc else ""
            task_title_enc = urllib.parse.quote(title[:200])
            link = f"/contact/{contact_id}?taskId={task_id}&taskTitle={task_title_enc}&prefill={prefill}" if contact_id else None
            notifications.append({
                "id": f"task_soon_{t['_id']}",
                "type": "task_due_soon",
                "category": "tasks",
                "priority": 2,
                "title": "Task Due Soon",
                "body": title,
                "link": link,
                "contact_id": contact_id,
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

    # 7. PENDING CAMPAIGN SENDS (manual mode  - high priority action items)
    try:
        pending_sends = list(db.campaign_pending_sends.find({
            "user_id": user_id,
            "status": "pending",
        }).sort("created_at", -1).limit(10))
        for ps in pending_sends:
            contact_id = ps.get("contact_id", "")
            message_content = ps.get("message", "")
            import urllib.parse
            prefill = urllib.parse.quote(message_content[:500]) if message_content else ""
            link = f"/contact/{contact_id}?prefill={prefill}" if contact_id else None
            notifications.append({
                "id": f"csend_{ps['_id']}",
                "type": "campaign_send",
                "category": "campaigns",
                "priority": 1,
                "title": f"Send: {ps.get('campaign_name', 'Campaign')}",
                "body": f"Step {ps.get('step', 0)} to {ps.get('contact_name', 'contact')} via {ps.get('channel', 'sms').upper()}",
                "link": link,
                "contact_name": ps.get("contact_name"),
                "contact_id": contact_id,
                "timestamp": _ts(ps.get("created_at")),
                "read": False,
                "source": "campaigns",
            })
    except Exception as e:
        logger.debug(f"Pending campaign sends: {e}")

    # 8. ENGAGEMENT SIGNALS — Real-time customer engagement alerts
    try:
        from datetime import timedelta as td
        cutoff = datetime.now(timezone.utc) - td(hours=48)
        eng_signals = list(db.notifications.find({
            "type": "engagement_signal",
            "user_id": user_id,
            "created_at": {"$gte": cutoff},
        }).sort("created_at", -1).limit(20))
        for sig in eng_signals:
            is_return = sig.get("is_return_visit", False)
            view_count = sig.get("view_count", 1)
            contact_id = sig.get("contact_id", "")
            priority = 0 if is_return else 1  # Return visits are highest priority
            if view_count >= 3:
                priority = 0  # Repeat viewers are hot leads
            notifications.append({
                "id": f"eng_{sig['_id']}",
                "type": "engagement_signal",
                "category": "engagement",
                "priority": priority,
                "title": sig.get("title", "Customer engaged"),
                "body": sig.get("message", ""),
                "icon": sig.get("icon", "eye"),
                "color": sig.get("color", "#007AFF"),
                "link": f"/contact/{contact_id}" if contact_id else None,
                "contact_name": sig.get("contact_name"),
                "contact_id": contact_id,
                "is_return_visit": is_return,
                "view_count": view_count,
                "timestamp": _ts(sig.get("created_at")),
                "read": sig.get("read", False),
                "source": "engagement",
            })
    except Exception as e:
        logger.debug(f"Engagement signals: {e}")

    # Count categories before filtering
    category_counts = {}
    for n in notifications:
        cat = n.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Filter by category if specified
    filtered = notifications if category == "all" else [n for n in notifications if n["category"] == category]

    # Sort: priority first, then newest within same priority
    filtered.sort(key=lambda n: (n["priority"], n.get("timestamp", "")))
    # Stable sort by timestamp desc within same priority
    from itertools import groupby
    sorted_notifs = []
    filtered.sort(key=lambda n: n["priority"])
    for _, group in groupby(filtered, key=lambda n: n["priority"]):
        grp = list(group)
        grp.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
        sorted_notifs.extend(grp)

    # Read status overlay from user's notification_reads
    try:
        reads = db.notification_reads.find_one({"user_id": user_id})
        read_ids = set((reads or {}).get("read_ids", []))
        for n in sorted_notifs:
            if n["id"] in read_ids:
                n["read"] = True
    except Exception:
        pass

    unread_count = sum(1 for n in sorted_notifs if not n["read"])

    return {
        "success": True,
        "notifications": sorted_notifs[:limit],
        "unread_count": unread_count,
        "total": len(sorted_notifs),
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
