"""
Web Push Notifications Router
Manages push subscriptions and sends milestone notifications.
"""
import os
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pywebpush import webpush, WebPushException

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["Push Notifications"])

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_MAILTO = os.environ.get("VAPID_MAILTO", "mailto:notifications@imonsocial.com")


@router.get("/vapid-key")
async def get_vapid_key():
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/subscribe/{user_id}")
async def subscribe(user_id: str, data: dict):
    """Store a push subscription for a user."""
    db = get_db()
    subscription = data.get("subscription")
    if not subscription or not subscription.get("endpoint"):
        raise HTTPException(status_code=400, detail="Invalid subscription")

    await db.push_subscriptions.update_one(
        {"user_id": user_id, "endpoint": subscription["endpoint"]},
        {
            "$set": {
                "user_id": user_id,
                "subscription": subscription,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    return {"status": "subscribed"}


@router.delete("/unsubscribe/{user_id}")
async def unsubscribe(user_id: str, data: dict):
    """Remove a push subscription."""
    db = get_db()
    endpoint = data.get("endpoint", "")
    await db.push_subscriptions.delete_one({"user_id": user_id, "endpoint": endpoint})
    return {"status": "unsubscribed"}



@router.post("/test/{user_id}")
async def test_push(user_id: str):
    """Send a test push notification to verify the full push pipeline."""
    sent = await send_push_to_user(
        user_id,
        "Push Notifications Active!",
        "You'll now receive real-time alerts for leads, engagement, and milestones.",
        "/touchpoints/performance",
        "checkmark.circle"
    )
    return {"status": "sent" if sent > 0 else "no_subscriptions", "sent_to": sent}



async def send_push_to_user(user_id: str, title: str, body: str, url: str = "/touchpoints/performance", icon: str = "flame"):
    """Send a push notification to all subscriptions for a user."""
    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not set — skipping push")
        return 0

    db = get_db()
    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
    sent = 0
    for sub_doc in subs:
        subscription_info = sub_doc.get("subscription", {})
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps({"title": title, "body": body, "url": url, "icon": icon}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_MAILTO},
            )
            sent += 1
        except WebPushException as e:
            if "410" in str(e) or "404" in str(e):
                await db.push_subscriptions.delete_one({"_id": sub_doc["_id"]})
                logger.info(f"Removed expired subscription for user {user_id}")
            else:
                logger.warning(f"Push failed for user {user_id}: {e}")
        except Exception as e:
            logger.warning(f"Push error for user {user_id}: {e}")
    return sent


async def check_and_notify_milestones(user_id: str, streak: int, level_title: str, today_count: int, best_day: int):
    """Check if user hit a milestone and send push notification."""
    db = get_db()

    # Get last notified milestones
    milestones = await db.user_milestones.find_one({"user_id": user_id}) or {}

    notifications = []

    # Streak milestones: 7, 14, 21, 30, 60, 90
    streak_milestones = [7, 14, 21, 30, 60, 90]
    last_streak_notified = milestones.get("last_streak_notified", 0)
    for m in streak_milestones:
        if streak >= m and last_streak_notified < m:
            notifications.append({
                "title": f"{m}-Day Streak!",
                "body": f"You've hit {m} consecutive days of 5+ touchpoints. You're on fire!",
                "milestone_key": "last_streak_notified",
                "milestone_value": m,
            })

    # Level up
    last_level = milestones.get("last_level_notified", "Rookie")
    level_order = ["Rookie", "Hustler", "Closer", "All-Star", "Legend"]
    if level_title in level_order and last_level in level_order:
        if level_order.index(level_title) > level_order.index(last_level):
            notifications.append({
                "title": f"Level Up: {level_title}!",
                "body": f"You've been promoted to {level_title}. Keep crushing it!",
                "milestone_key": "last_level_notified",
                "milestone_value": level_title,
            })

    # New personal best day
    last_best_day = milestones.get("last_best_day_notified", 0)
    if today_count > best_day and today_count > last_best_day and today_count >= 10:
        notifications.append({
            "title": "New Personal Best!",
            "body": f"{today_count} touchpoints today — that's your best day ever!",
            "milestone_key": "last_best_day_notified",
            "milestone_value": today_count,
        })

    # Send all notifications
    for n in notifications:
        await send_push_to_user(user_id, n["title"], n["body"])
        await db.user_milestones.update_one(
            {"user_id": user_id},
            {
                "$set": {n["milestone_key"]: n["milestone_value"], "updated_at": datetime.now(timezone.utc)},
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
        # Also store in notification history
        await db.notifications.insert_one({
            "user_id": user_id,
            "title": n["title"],
            "body": n["body"],
            "type": "milestone",
            "read": False,
            "created_at": datetime.now(timezone.utc),
        })
        logger.info(f"[Push] Sent milestone notification to {user_id}: {n['title']}")

    return len(notifications)
