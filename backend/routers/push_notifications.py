"""
Web Push Notifications Router
Manages push subscriptions and sends milestone notifications.
"""
import os
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
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
    """Send a push notification — handles BOTH native iOS (Expo) and web (VAPID).
    Respects user's notification_mode preference: 'push', 'sms', or 'both'.
    """
    # Check user's notification preference
    try:
        user_doc = await get_db().users.find_one({"_id": ObjectId(user_id)}, {"notification_mode": 1})
        mode = (user_doc or {}).get("notification_mode", "both")
        if mode == "sms":
            return 0  # User wants SMS only — skip push entirely
    except Exception:
        mode = "both"

    # Respect quiet-hours schedule
    try:
        from routers.user_schedule import is_user_available
        if not await is_user_available(user_id):
            logger.info(f"[Push] Skipped for {user_id} — outside scheduled hours")
            return 0
    except Exception as e:
        logger.debug(f"[Push] Schedule check failed (non-fatal): {e}")

    db = get_db()
    sent = 0

    # ── Native iOS/Android via Expo Push API ──────────────────────────────────
    tokens = await db.expo_push_tokens.find({"user_id": user_id}).to_list(10)
    if tokens:
        import httpx
        messages = [{
            "to": t["expo_push_token"],
            "title": title,
            "body": body,
            "data": {"url": url, "icon": icon},
            "sound": "default",
            "badge": 1,
        } for t in tokens if t.get("expo_push_token")]
        if messages:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://exp.host/--/api/v2/push/send",
                        json=messages,
                        headers={"Accept": "application/json", "Content-Type": "application/json"},
                    )
                    result = resp.json()
                    # Clean up invalid tokens
                    if isinstance(result, dict) and "data" in result:
                        for i, item in enumerate(result["data"]):
                            if isinstance(item, dict) and item.get("status") == "error":
                                details = item.get("details", {})
                                if details.get("error") in ("DeviceNotRegistered", "InvalidCredentials"):
                                    if i < len(tokens):
                                        await db.expo_push_tokens.delete_one({"_id": tokens[i]["_id"]})
                    sent += len(messages)
                    logger.info(f"[Push] Expo native sent {len(messages)} notifications to {user_id}")
            except Exception as e:
                logger.warning(f"[Push] Expo native failed for {user_id}: {e}")

    # ── Web push via VAPID ────────────────────────────────────────────────────
    if VAPID_PRIVATE_KEY:
        subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
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
                else:
                    logger.warning(f"[Push] Web push failed for {user_id}: {e}")
            except Exception as e:
                logger.warning(f"[Push] Web push error for {user_id}: {e}")

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
            "message": n["body"],
            "type": "milestone",
            "read": False,
            "created_at": datetime.now(timezone.utc),
        })


@router.post("/subscribe-native/{user_id}")
async def subscribe_native_push(user_id: str, request: Request):
    """Store Expo push token for native iOS/Android push notifications."""
    db = get_db()
    data = await request.json()
    expo_token = data.get("expo_push_token", "")
    platform = data.get("platform", "ios")
    if not expo_token:
        raise HTTPException(status_code=400, detail="expo_push_token required")
    await db.expo_push_tokens.update_one(
        {"user_id": user_id, "expo_push_token": expo_token},
        {"$set": {
            "user_id":         user_id,
            "expo_push_token": expo_token,
            "platform":        platform,
            "updated_at":      datetime.now(timezone.utc),
        }, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    logger.info(f"[Push] ✅ Native Expo token registered for user {user_id} ({platform}): {expo_token[:20]}...")
    return {"success": True, "registered": True}


@router.post("/log-error")
async def log_push_error(request: Request):
    """Log push notification errors from native clients for debugging."""
    db = get_db()
    data = await request.json()
    logger.error(f"[Push] ❌ Client error — user={data.get('user_id')} platform={data.get('platform')}: {data.get('error')}")
    await db.push_errors.insert_one({
        **data,
        "created_at": datetime.now(timezone.utc),
    })
    return {"logged": True}


@router.patch("/preferences/{user_id}")
async def update_notification_preferences(user_id: str, request: Request):
    """Update user's notification delivery preference: 'sms', 'push', or 'both'."""
    from bson import ObjectId as _OId
    db = get_db()
    data = await request.json()
    mode = data.get("notification_mode", "both")
    if mode not in ("sms", "push", "both"):
        raise HTTPException(status_code=400, detail="notification_mode must be 'sms', 'push', or 'both'")
    await db.users.update_one({"_id": _OId(user_id)}, {"$set": {"notification_mode": mode}})
    logger.info(f"[Push] User {user_id} set notification_mode={mode}")
    return {"success": True, "notification_mode": mode}


@router.get("/status/{user_id}")
async def get_push_status(user_id: str):
    """Check push notification registration status for a user."""
    db = get_db()
    tokens = await db.expo_push_tokens.find({"user_id": user_id}, {"_id": 0, "expo_push_token": 1, "platform": 1, "updated_at": 1}).to_list(10)
    web_subs = await db.push_subscriptions.count_documents({"user_id": user_id})
    errors = await db.push_errors.find({"user_id": user_id}).sort("created_at", -1).limit(3).to_list(3)
    return {
        "native_tokens": len(tokens),
        "tokens": [{"platform": t.get("platform"), "token_preview": t.get("expo_push_token", "")[:20] + "...", "updated": str(t.get("updated_at", ""))} for t in tokens],
        "web_subscriptions": web_subs,
        "recent_errors": [{"error": e.get("error"), "time": str(e.get("created_at", ""))} for e in errors],
    }


async def send_push_native(user_id: str, title: str, body: str, data: dict = None):
    """Send push notification to native iOS/Android via Expo Push API."""
    db = get_db()
    tokens = await db.expo_push_tokens.find({"user_id": user_id}).to_list(10)
    if not tokens:
        return 0
    import httpx
    messages = [{"to": t["expo_push_token"], "title": title, "body": body, "data": data or {}, "sound": "default"} for t in tokens]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json=messages,
                headers={"Accept": "application/json", "Accept-Encoding": "gzip, deflate", "Content-Type": "application/json"},
                timeout=10.0,
            )
            logger.info(f"[Push] Expo native push sent to {len(messages)} devices for user {user_id}")
            return len(messages)
    except Exception as e:
        logger.warning(f"[Push] Expo native push failed: {e}")
        return 0


    return len(notifications)



async def send_daily_task_digest():
    """
    Morning push digest — called by scheduler at 2pm UTC (~7am PDT / 9am CDT).
    Sends each active user a push notification with their pending touchpoints for today.
    Only fires if they have push subscriptions and pending tasks.
    """
    db = get_db()
    if not VAPID_PRIVATE_KEY:
        logger.info("[Push Digest] VAPID not configured, skipping")
        return

    from datetime import date
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = today_start.replace(hour=23, minute=59, second=59)

    # Get users who have push subscriptions
    subs = await db.push_subscriptions.find({}, {"user_id": 1}).to_list(500)
    user_ids_with_push = list({s["user_id"] for s in subs})

    sent = 0
    for user_id in user_ids_with_push:
        try:
            # Count pending tasks due today
            count = await db.tasks.count_documents({
                "user_id": user_id,
                "status": {"$in": ["pending", "pending_user_action"]},
                "$or": [
                    {"due_date": {"$gte": today_start.replace(tzinfo=None), "$lte": today_end.replace(tzinfo=None)}},
                    {"due_date": {"$exists": False}},  # undated tasks always show
                ],
            })
            if count == 0:
                continue

            label = "touchpoint" if count == 1 else "touchpoints"
            n = await send_push_to_user(
                user_id,
                f"You have {count} {label} today",
                "Tap to open your Touchpoints and get started.",
                "/touchpoints",
                "checkmark-circle",
            )
            if n > 0:
                sent += 1
        except Exception as e:
            logger.warning(f"[Push Digest] Error for {user_id}: {e}")

    logger.info(f"[Push Digest] Morning digest sent to {sent}/{len(user_ids_with_push)} users")
    return sent


async def send_push_to_users(user_ids: list, title: str, body: str, url: str = "/", icon: str = "flame"):
    """Broadcast a push notification to multiple users at once."""
    sent = 0
    for uid in user_ids:
        sent += await send_push_to_user(uid, title, body, url, icon)
    return sent
