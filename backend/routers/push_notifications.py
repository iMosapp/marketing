"""
Web Push Notifications Router
Manages push subscriptions and sends milestone notifications.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from pywebpush import webpush, WebPushException
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["Push Notifications"])

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_MAILTO = os.environ.get("VAPID_MAILTO", "mailto:notifications@imonsocial.com")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
_push_log_indexed = False


async def _log_push(user_id: str, title: str, channel: str, outcome: str, details: dict = None):
    """Keep a 14-day trail of every push attempt so 'why didn't I get that?' is answerable."""
    global _push_log_indexed
    try:
        db = get_db()
        if not _push_log_indexed:
            await db.push_log.create_index("created_at", expireAfterSeconds=14 * 24 * 3600)
            _push_log_indexed = True
        await db.push_log.insert_one({
            "user_id": user_id, "title": title, "channel": channel, "outcome": outcome,
            "details": details or {}, "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"[Push] log failed (non-fatal): {e}")


async def _send_expo(tokens: list, title: str, body: str, data: dict, sound: str = "default", channel_id: str = None) -> list:
    """POST to Expo, return one ticket per token. Logs every error and prunes dead tokens."""
    import httpx
    db = get_db()
    tokens = [t for t in tokens if t.get("expo_push_token")]
    if not tokens:
        return []
    messages = [{
        "to": t["expo_push_token"], "title": title, "body": body,
        "data": data, "sound": sound or "default", "badge": 1,
        **({"channelId": channel_id} if channel_id else {}),
    } for t in tokens]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(EXPO_PUSH_URL, json=messages,
                                     headers={"Accept": "application/json", "Content-Type": "application/json"})
            result = resp.json()
    except Exception as e:
        logger.warning(f"[Push] Expo request failed: {e}")
        return [{"status": "error", "message": str(e), "details": {"error": "RequestFailed"}} for _ in tokens]

    tickets = result.get("data") if isinstance(result, dict) else None
    if not isinstance(tickets, list):
        logger.warning(f"[Push] Expo unexpected response: {str(result)[:300]}")
        return [{"status": "error", "message": str(result)[:200], "details": {"error": "BadResponse"}} for _ in tokens]

    for i, ticket in enumerate(tickets):
        if not isinstance(ticket, dict) or ticket.get("status") == "ok":
            continue
        err = (ticket.get("details") or {}).get("error")
        logger.warning(f"[Push] Expo ticket error for token {tokens[i]['expo_push_token'][:22]}...: {err} - {ticket.get('message')}")
        if err in ("DeviceNotRegistered", "InvalidCredentials") and i < len(tokens):
            await db.expo_push_tokens.delete_one({"_id": tokens[i]["_id"]})
    ok = sum(1 for t in tickets if isinstance(t, dict) and t.get("status") == "ok")
    logger.info(f"[Push] Expo accepted {ok}/{len(tokens)} native notifications")
    return tickets


async def _fetch_expo_receipts(ticket_ids: list) -> dict:
    """APNs/FCM-level delivery results (DeviceNotRegistered, InvalidCredentials...) only show up here."""
    import httpx
    ids = [i for i in ticket_ids if i]
    if not ids:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(EXPO_RECEIPTS_URL, json={"ids": ids},
                                     headers={"Accept": "application/json", "Content-Type": "application/json"})
            return (resp.json() or {}).get("data") or {}
    except Exception as e:
        logger.warning(f"[Push] Expo receipts failed: {e}")
        return {}


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



LEAD_SOUND = "lead_chime.wav"      # bundled via app.json expo-notifications sounds; iOS falls back to default if missing
LEAD_CHANNEL = "leads"             # Android channel registered by the app at startup


async def _mirror_to_alerts(db, user_id: str, title: str, body: str, url: str, icon: str):
    """Every push also lands in Alerts so it can be revisited (banner gone, phone missed it, etc.).
    Skipped when the sender already wrote a matching notification in the last few minutes."""
    try:
        now = datetime.now(timezone.utc)
        dup = await db.notifications.find_one(
            {"user_id": user_id, "created_at": {"$gte": now - timedelta(minutes=3)},
             "$or": [{"title": title}, {"message": body}]}, {"_id": 1})
        if dup:
            return
        await db.notifications.insert_one({
            "type": "push", "user_id": user_id, "title": title, "message": body, "link": url or "/notifications",
            "icon": icon or "notifications", "read": False, "dismissed": False, "created_at": now,
        })
        from routers.notifications_center import invalidate_feed
        invalidate_feed(user_id)
    except Exception as e:
        logger.debug(f"[Push] alerts mirror failed (non-fatal): {e}")


async def send_push_to_user(user_id: str, title: str, body: str, url: str = "/touchpoints/performance", icon: str = "flame",
                            sound: str = "default", channel_id: str = None):
    """Send a push notification — handles BOTH native iOS (Expo) and web (VAPID).
    Respects user's notification_mode preference: 'push', 'sms', or 'both'.
    sound/channel_id let lead alerts use the distinct chime (LEAD_SOUND / LEAD_CHANNEL).
    """
    # Check user's notification preference
    try:
        user_doc = await get_db().users.find_one({"_id": ObjectId(user_id)}, {"notification_mode": 1})
        mode = (user_doc or {}).get("notification_mode", "both")
        if mode == "sms":
            await _log_push(user_id, title, "none", "skipped_sms_only_mode")
            return 0  # User wants SMS only — skip push entirely
    except Exception:
        mode = "both"

    await _mirror_to_alerts(get_db(), user_id, title, body, url, icon)

    # Quiet hours: HOLD the push for a morning summary instead of dropping it
    try:
        from routers.user_schedule import is_quiet_now
        if await is_quiet_now(user_id):
            from datetime import datetime as _dt, timezone as _tz
            db_q = get_db()
            held_count = await db_q.held_pushes.count_documents({"user_id": user_id, "delivered": False})
            if held_count < 50:
                await db_q.held_pushes.insert_one({
                    "user_id": user_id, "title": title, "body": body, "url": url, "icon": icon,
                    "delivered": False, "created_at": _dt.now(_tz.utc),
                })
            logger.info(f"[Push] Held for {user_id} — quiet hours (will summarize when they end)")
            await _log_push(user_id, title, "none", "held_quiet_hours")
            return 0
    except Exception as e:
        logger.debug(f"[Push] Quiet-hours check failed (non-fatal): {e}")

    db = get_db()
    sent = 0

    # ── Native iOS/Android via Expo Push API ──────────────────────────────────
    tokens = await db.expo_push_tokens.find({"user_id": user_id}).to_list(10)
    if tokens:
        tickets = await _send_expo(tokens, title, body, {"url": url, "icon": icon, "sound": sound or "default"}, sound=sound, channel_id=channel_id)
        ok = [t for t in tickets if t.get("status") == "ok"]
        sent += len(ok)
        await _log_push(user_id, title, "expo", "sent" if ok else "expo_error", {
            "tickets": [{"status": t.get("status"), "id": t.get("id"), "error": (t.get("details") or {}).get("error"), "message": t.get("message")} for t in tickets]
        })

    # ── Web push via VAPID ────────────────────────────────────────────────────
    if VAPID_PRIVATE_KEY:
        subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
        for sub_doc in subs:
            subscription_info = sub_doc.get("subscription", {})
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps({"title": title, "body": body, "url": url, "icon": icon, "sound": sound or "default"}),
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


@router.get("/diagnose/{user_id}")
async def diagnose_push(user_id: str):
    """Everything that decides whether a push reaches this user, in one call."""
    from routers.user_schedule import quiet_status
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"notification_mode": 1, "timezone": 1}) or {}
    tokens = await db.expo_push_tokens.find({"user_id": user_id}).sort("updated_at", -1).to_list(10)
    web_subs = await db.push_subscriptions.count_documents({"user_id": user_id})
    held = await db.held_pushes.count_documents({"user_id": user_id, "delivered": False})
    recent = await db.push_log.find({"user_id": user_id}).sort("created_at", -1).limit(10).to_list(10)
    quiet = await quiet_status(user_id)
    return {
        "notification_mode": user.get("notification_mode", "both"),
        "user_timezone": user.get("timezone"),
        "native_tokens": [{
            "platform": t.get("platform"),
            "token_preview": (t.get("expo_push_token") or "")[:24] + "...",
            "updated_at": str(t.get("updated_at") or ""),
        } for t in tokens],
        "web_subscriptions": web_subs,
        "quiet": quiet,
        "held_pushes": held,
        "recent": [{
            "title": r.get("title"), "channel": r.get("channel"), "outcome": r.get("outcome"),
            "at": str(r.get("created_at") or ""), "details": r.get("details") or {},
        } for r in recent],
    }


@router.post("/diagnose/{user_id}/test")
async def diagnose_push_test(user_id: str):
    """Send a real test push straight to the device, bypassing quiet hours and SMS-only mode,
    then pull Expo receipts so APNs-level failures (bad credentials, dead token) are visible."""
    import asyncio
    db = get_db()
    tokens = await db.expo_push_tokens.find({"user_id": user_id}).to_list(10)
    if not tokens:
        await _log_push(user_id, "Test push", "expo", "no_native_token")
        return {"ok": False, "reason": "no_native_token",
                "hint": "This phone hasn't registered for push. Open the app, allow notifications, then try again."}

    tickets = await _send_expo(tokens, "Test push from i'M On Social",
                               "If you can read this, alerts are reaching your phone.", {"url": "/notifications", "icon": "checkmark.circle"})
    ticket_ids = [t.get("id") for t in tickets if isinstance(t, dict) and t.get("status") == "ok"]
    await asyncio.sleep(3)
    receipts = await _fetch_expo_receipts(ticket_ids)
    for tid, rc in receipts.items():
        err = (rc.get("details") or {}).get("error")
        if err in ("DeviceNotRegistered", "InvalidCredentials"):
            logger.warning(f"[Push] Receipt error {err} for user {user_id}: {rc.get('message')}")
    results = []
    for i, t in enumerate(tickets):
        rc = receipts.get(t.get("id")) if isinstance(t, dict) else None
        results.append({
            "platform": tokens[i].get("platform") if i < len(tokens) else None,
            "ticket": t.get("status") if isinstance(t, dict) else "error",
            "ticket_error": (t.get("details") or {}).get("error") if isinstance(t, dict) else None,
            "receipt": (rc or {}).get("status") if rc else "pending",
            "receipt_error": ((rc or {}).get("details") or {}).get("error") if rc else None,
            "message": (rc or {}).get("message") if rc else (t.get("message") if isinstance(t, dict) else None),
        })
    ok = any(r["ticket"] == "ok" and r["receipt"] in ("ok", "pending") for r in results)
    await _log_push(user_id, "Test push", "expo", "sent" if ok else "expo_error", {"results": results})
    return {"ok": ok, "results": results}


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



async def _compose_morning_brief(db, u: dict, tzinfo):
    """(title, body) for a user's Morning Task Brief, or None when nothing is due."""
    from routers.tasks import get_user_day_bounds
    uid = str(u["_id"])
    today_start, today_end = await get_user_day_bounds(uid, "today")
    docs = await db.tasks.find({
        "user_id": uid,
        "status": {"$in": ["pending", "snoozed", None]},
        "completed": {"$ne": True},
        "type": {"$nin": ["campaign_send", "campaign_step"]},
        "$nor": [{"source": "system", "type": "follow_up"}],
        "due_date": {"$lt": today_end},
    }, {"title": 1, "contact_name": 1, "due_date": 1, "has_time": 1}).sort("due_date", 1).to_list(200)
    if not docs:
        return None
    overdue = [t for t in docs if t.get("due_date") and t["due_date"].replace(tzinfo=timezone.utc) < today_start]
    today = [t for t in docs if t not in overdue]
    n_today, n_over = len(today), len(overdue)
    first = (u.get("name") or "").split()[0] if u.get("name") else ""
    parts = []
    for t in (today or overdue)[:3]:
        label = t.get("title", "Task")
        if t.get("contact_name") and t["contact_name"].split()[0].lower() not in label.lower():
            label += f" ({t['contact_name'].split()[0]})"
        if t.get("has_time") and t.get("due_date"):
            lt = t["due_date"].replace(tzinfo=timezone.utc).astimezone(tzinfo)
            label += f" {lt.strftime('%-I:%M %p')}"
        parts.append(label)
    extra = max(0, (n_today if today else n_over) - 3)
    summary = " · ".join(parts) + (f" +{extra} more" if extra else "")
    greet = f"Good morning{', ' + first if first else ''}"
    if n_today:
        title = f"{greet} - {n_today} task{'s' if n_today != 1 else ''} today"
        if n_over:
            summary += f" · {n_over} overdue"
    else:
        title = f"{greet} - {n_over} overdue task{'s' if n_over != 1 else ''}"
    return title, summary


async def _user_tzinfo(db, u: dict, store_tz_cache: dict):
    from zoneinfo import ZoneInfo
    tz_name = u.get("timezone")
    if (not tz_name or tz_name == "UTC") and u.get("store_id"):
        sid = str(u["store_id"])
        if sid not in store_tz_cache:
            st = await db.stores.find_one({"_id": ObjectId(sid)}, {"timezone": 1}) if ObjectId.is_valid(sid) else None
            store_tz_cache[sid] = (st or {}).get("timezone")
        tz_name = store_tz_cache[sid] or tz_name
    try:
        return ZoneInfo(tz_name if tz_name and tz_name != "UTC" else "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


async def send_daily_task_digest():
    """
    Morning Task Brief. Scheduler calls this every 15 minutes; each active user gets ONE push per day
    in the 07:00-07:15 window of THEIR local time (user tz -> store tz -> America/Denver), listing
    today's tasks with customer names. Users with nothing due today are skipped.
    """
    db = get_db()
    now_utc = datetime.now(timezone.utc)
    users = await db.users.find(
        {"active": {"$ne": False}, "status": {"$ne": "deactivated"}, "morning_brief_enabled": {"$ne": False}},
        {"name": 1, "timezone": 1, "store_id": 1, "morning_brief_sent_on": 1},
    ).to_list(2000)
    store_tz_cache: dict = {}
    sent = 0
    for u in users:
        uid = str(u["_id"])
        try:
            tzinfo = await _user_tzinfo(db, u, store_tz_cache)
            local = now_utc.astimezone(tzinfo)
            if not (local.hour == 7 and local.minute < 15):
                continue
            today_key = local.strftime("%Y-%m-%d")
            if u.get("morning_brief_sent_on") == today_key:
                continue
            brief = await _compose_morning_brief(db, u, tzinfo)
            if not brief:
                continue
            n = await send_push_to_user(uid, brief[0], brief[1], "/touchpoints", "sunny")
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"morning_brief_sent_on": today_key}})
            if n > 0:
                sent += 1
        except Exception as e:
            logger.warning(f"[Morning Brief] Error for {uid}: {e}")
    if sent:
        logger.info(f"[Morning Brief] Sent to {sent} users")
    return sent


@router.post("/morning-brief/{user_id}/send-now")
async def send_morning_brief_now(user_id: str):
    """Preview: build and push this user's Morning Task Brief right now (ignores the 7 AM window)."""
    db = get_db()
    u = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "timezone": 1, "store_id": 1})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    tzinfo = await _user_tzinfo(db, u, {})
    brief = await _compose_morning_brief(db, u, tzinfo)
    if not brief:
        return {"sent": False, "reason": "Nothing due today", "title": None, "body": None}
    n = await send_push_to_user(user_id, brief[0], brief[1], "/touchpoints", "sunny")
    return {"sent": n > 0, "devices": n, "title": brief[0], "body": brief[1]}


async def send_push_to_users(user_ids: list, title: str, body: str, url: str = "/", icon: str = "flame"):
    """Broadcast a push notification to multiple users at once."""
    sent = 0
    for uid in user_ids:
        sent += await send_push_to_user(uid, title, body, url, icon)
    return sent
