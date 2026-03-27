"""
Notifications Router

Handles real-time notifications for:
- New lead assignments
- Jump ball lead alerts (team-wide)
- Lead claimed notifications
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
import logging

from routers.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    type: str
    title: str
    message: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    conversation_id: Optional[str] = None
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    lead_source_name: Optional[str] = None
    action_required: bool = True
    priority: str = "high"


# ============ CREATE NOTIFICATION ============

async def create_notification(
    notification_type: str,
    title: str,
    message: str,
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    contact_email: Optional[str] = None,
    lead_source_name: Optional[str] = None,
    action_required: bool = True,
    priority: str = "high"
) -> str:
    """Create a notification in the database"""
    db = get_db()

    notification = {
        "type": notification_type,
        "title": title,
        "message": message,
        "user_id": user_id,
        "team_id": team_id,
        "conversation_id": conversation_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "contact_email": contact_email,
        "lead_source_name": lead_source_name,
        "action_required": action_required,
        "priority": priority,
        "read": False,
        "dismissed": False,
        "action_taken": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    result = await db.notifications.insert_one(notification)
    logger.info(f"Created notification: {notification_type} for user={user_id} team={team_id}")
    return str(result.inserted_id)


async def create_team_notifications(
    team_id: str,
    notification_type: str,
    title: str,
    message: str,
    conversation_id: str,
    contact_id: str,
    contact_name: str,
    contact_phone: str,
    contact_email: Optional[str] = None,
    lead_source_name: Optional[str] = None
) -> List[str]:
    """Create notifications for all team members"""
    db = get_db()
    notification_ids = []

    team = await db.teams.find_one({"_id": ObjectId(team_id)}) if ObjectId.is_valid(team_id) else None

    if not team:
        team = await db.shared_inboxes.find_one({"_id": ObjectId(team_id)}) if ObjectId.is_valid(team_id) else None

    if not team:
        logger.warning(f"Team {team_id} not found for notifications")
        return []

    members = team.get("members", []) or team.get("user_ids", []) or team.get("assigned_user_ids", [])

    if not members:
        logger.warning(f"Team {team_id} has no members")
        return []

    for member_id in members:
        notif_id = await create_notification(
            notification_type=notification_type,
            title=title,
            message=message,
            user_id=member_id,
            team_id=team_id,
            conversation_id=conversation_id,
            contact_id=contact_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
            lead_source_name=lead_source_name,
            action_required=True,
            priority="high"
        )
        notification_ids.append(notif_id)

    logger.info(f"Created {len(notification_ids)} team notifications for team {team_id}")
    return notification_ids


async def _get_user_teams(db, user_id: str) -> list:
    user_teams = []
    teams = await db.teams.find({"members": user_id}, {"_id": 1}).to_list(50)
    user_teams.extend([str(t["_id"]) for t in teams])
    shared_inboxes = await db.shared_inboxes.find({"user_ids": user_id}, {"_id": 1}).to_list(50)
    user_teams.extend([str(si["_id"]) for si in shared_inboxes])
    return user_teams


# ============ GET NOTIFICATIONS ============

@router.get("/")
async def get_notifications_list(
    user_id: str = Query(...),
    unread_only: bool = Query(False),
    limit: int = Query(50)
):
    """Get notifications for a user (includes team notifications)"""
    db = get_db()
    user_teams = await _get_user_teams(db, user_id)

    query = {
        "$or": [
            {"user_id": user_id},
            {"team_id": {"$in": user_teams}, "user_id": None}
        ],
        "dismissed": False
    }

    if unread_only:
        query["read"] = False

    notifications = await db.notifications.find(query).sort("created_at", -1).limit(limit).to_list(limit)

    for n in notifications:
        n["id"] = str(n.pop("_id"))

    unread_count = await db.notifications.count_documents({**query, "read": False})

    return {
        "success": True,
        "notifications": notifications,
        "count": len(notifications),
        "unread_count": unread_count
    }


@router.get("/unread-count")
async def get_unread_count(user_id: str = Query(...)):
    """Get count of unread notifications for badge display"""
    db = get_db()
    user_teams = await _get_user_teams(db, user_id)

    count = await db.notifications.count_documents({
        "$or": [
            {"user_id": user_id},
            {"team_id": {"$in": user_teams}, "user_id": None}
        ],
        "read": False,
        "dismissed": False
    })

    return {"count": count}


@router.get("/pending-action")
async def get_pending_action_notification(user_id: str = Query(...)):
    """Get the most recent notification requiring action (for popup)"""
    db = get_db()
    user_teams = await _get_user_teams(db, user_id)

    notification = await db.notifications.find_one(
        {
            "$or": [
                {"user_id": user_id},
                {"team_id": {"$in": user_teams}, "user_id": None}
            ],
            "action_required": True,
            "action_taken": None,
            "dismissed": False
        },
        sort=[("created_at", -1)]
    )

    if notification:
        notification["id"] = str(notification.pop("_id"))
        return {"success": True, "notification": notification}

    return {"success": True, "notification": None}


# ============ UPDATE NOTIFICATIONS ============

@router.post("/mark-all-read")
async def mark_all_as_read(user_id: str = Query(...)):
    """Mark all notifications as read for a user"""
    db = get_db()
    user_teams = await _get_user_teams(db, user_id)

    result = await db.notifications.update_many(
        {
            "$or": [
                {"user_id": user_id},
                {"team_id": {"$in": user_teams}, "user_id": None}
            ],
            "read": False,
            "dismissed": False
        },
        {"$set": {"read": True}}
    )

    return {"success": True, "marked_count": result.modified_count}


@router.post("/{notification_id}/read")
async def mark_as_read(notification_id: str):
    """Mark a notification as read"""
    db = get_db()
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": {"read": True}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"success": True}


@router.post("/{notification_id}/action")
async def record_action(
    notification_id: str,
    action: str = Query(..., description="Action taken: call, text, email, dismissed"),
    user_id: str = Query(...)
):
    """Record that a user took action on a notification"""
    db = get_db()

    if action not in ["call", "text", "email", "dismissed"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    notification = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    update_data = {
        "action_taken": action,
        "action_taken_by": user_id,
        "action_taken_at": datetime.now(timezone.utc).isoformat(),
        "read": True,
        "dismissed": action == "dismissed"
    }

    await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": update_data}
    )

    if notification.get("type") == "jump_ball" and action != "dismissed":
        conversation_id = notification.get("conversation_id")
        if conversation_id:
            await db.notifications.update_many(
                {
                    "conversation_id": conversation_id,
                    "_id": {"$ne": ObjectId(notification_id)},
                    "action_taken": None
                },
                {"$set": {
                    "dismissed": True,
                    "action_taken": "claimed_by_other",
                    "action_taken_at": datetime.now(timezone.utc).isoformat()
                }}
            )

            await db.conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {
                    "claimed": True,
                    "claimed_by": user_id,
                    "claimed_at": datetime.now(timezone.utc).isoformat(),
                    "assigned_to": user_id
                }}
            )

    return {
        "success": True,
        "action": action,
        "conversation_id": notification.get("conversation_id"),
        "contact_phone": notification.get("contact_phone"),
        "contact_email": notification.get("contact_email"),
        "contact_name": notification.get("contact_name")
    }


@router.post("/{notification_id}/dismiss")
async def dismiss_notification(notification_id: str):
    """Dismiss a notification"""
    db = get_db()

    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": {
            "dismissed": True,
            "action_taken": "dismissed",
            "action_taken_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"success": True}


@router.delete("/clear-all")
async def clear_all_notifications(user_id: str = Query(...)):
    """Clear all notifications for a user"""
    db = get_db()
    user_teams = await _get_user_teams(db, user_id)

    result = await db.notifications.update_many(
        {
            "$or": [
                {"user_id": user_id},
                {"team_id": {"$in": user_teams}}
            ]
        },
        {"$set": {"dismissed": True}}
    )

    return {"success": True, "cleared_count": result.modified_count}
