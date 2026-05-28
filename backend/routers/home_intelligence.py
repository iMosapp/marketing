"""
Home Screen Intelligence — /api/home/

Powers the addictive daily habit loop:
  - My 3 for Today: AI picks 3 contacts to reach out to, with context + one-tap action
  - Streak: days of consecutive relationship activity
  - Wins Feed: recent dopamine moments (views, replies, clicks)
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter

from routers.database import get_db

router = APIRouter(prefix="/home", tags=["home"])
logger = logging.getLogger(__name__)


# ── Streak calculator ─────────────────────────────────────────────────────────

async def get_streak(user_id: str, db) -> dict:
    """
    Calculate consecutive days of relationship activity.
    Activity = outbound message sent, task completed, or card shared.
    """
    now    = datetime.now(timezone.utc)
    streak = 0
    at_risk = False

    try:
        # Check each day going backwards from today
        for days_ago in range(0, 60):
            day_start = (now - timedelta(days=days_ago)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            activity = await db.contact_events.find_one({
                "user_id":   user_id,
                "timestamp": {"$gte": day_start, "$lt": day_end},
                "category":  {"$in": ["sent", "campaign", "outbound", "touchpoint"]},
            })
            if not activity:
                # Also check messages sent
                activity = await db.messages.find_one({
                    "sender":    {"$in": [user_id, "user", "ai"]},
                    "direction": "outbound",
                    "timestamp": {"$gte": day_start, "$lt": day_end},
                })

            if activity:
                streak += 1
            elif days_ago == 0:
                # Nothing yet today — streak at risk if they had activity yesterday
                at_risk = streak > 0
                break
            else:
                break

        hours_since_last = 0  # noqa — reserved for future "last contact" display
        last_event = await db.contact_events.find_one(
            {"user_id": user_id, "category": {"$in": ["sent","campaign","outbound","touchpoint"]}},
            sort=[("timestamp", -1)]
        )
        if last_event and last_event.get("timestamp"):
            ts = last_event["timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            hours_since_last = (now - ts).total_seconds() / 3600

    except Exception as e:
        logger.warning(f"[Home] Streak calc failed: {e}")

    return {
        "streak":         streak,
        "at_risk":        at_risk,
        "label":          f"{streak} day streak" if streak > 1 else ("1 day streak" if streak == 1 else "Start your streak today"),
        "emoji":          "🔥" if streak >= 3 else ("✨" if streak >= 1 else "💪"),
    }


# ── My 3 for Today ────────────────────────────────────────────────────────────

PRIORITY_REASONS = {
    "card_viewed":     {"label": "Viewed your card",        "action": "Follow Up",     "icon": "eye",           "color": "#FF9500", "priority": 10},
    "campaign_reply":  {"label": "Replied to your message", "action": "Reply Now",      "icon": "chatbubble",    "color": "#34C759", "priority": 10},
    "birthday":        {"label": "Birthday coming up",      "action": "Send Birthday",  "icon": "gift",          "color": "#FF375F", "priority": 9},
    "anniversary":     {"label": "Anniversary this week",   "action": "Send Card",      "icon": "heart",         "color": "#FF375F", "priority": 8},
    "cooling_down":    {"label": "days since last contact", "action": "Check In",       "icon": "time",          "color": "#007AFF", "priority": 5},
    "review_click":    {"label": "Clicked your review link","action": "Send Follow-Up", "icon": "star",          "color": "#C9A962", "priority": 7},
    "warm_lead":       {"label": "Warm lead — active now",  "action": "Reach Out",      "icon": "flash",         "color": "#FF3B30", "priority": 10},
    "purchase_followup":{"label":"Bought recently",         "action": "Say Thank You",  "icon": "bag-check",     "color": "#34C759", "priority": 6},
}


async def get_my_3(user_id: str, db) -> list:
    """
    AI-powered daily contact recommendations.
    Returns up to 3 contacts with reason, context, and a suggested action.
    Scoring:
      - Hot signals (recent card view, warm reply) = 10
      - Birthday/anniversary within 3 days = 9/8
      - Review link click = 7
      - Recent purchase follow-up = 6
      - Days since last contact (overdue) = 5
    """
    now       = datetime.now(timezone.utc)
    scored: list = []
    seen_ids: set = set()

    async def add(contact, reason_key: str, extra_label: str = "", score: int = 0):
        cid = str(contact["_id"])
        if cid in seen_ids:
            return
        seen_ids.add(cid)
        meta = PRIORITY_REASONS.get(reason_key, {})
        scored.append({
            "contact_id":   cid,
            "first_name":   contact.get("first_name", ""),
            "last_name":    contact.get("last_name", ""),
            "phone":        contact.get("phone", ""),
            "email":        contact.get("email", ""),
            "photo_url":    contact.get("photo_url") or contact.get("photo_path") or "",
            "reason_key":   reason_key,
            "reason_label": extra_label or meta.get("label", ""),
            "action_label": meta.get("action", "Reach Out"),
            "icon":         meta.get("icon", "person"),
            "color":        meta.get("color", "#007AFF"),
            "score":        score or meta.get("priority", 5),
        })

    try:
        # 0. OVERDUE TASKS — highest priority, always surface these first
        overdue_tasks = await db.tasks.find({
            "user_id":  user_id,
            "status":   {"$in": ["pending", "active", None]},
            "due_date": {"$lte": now},
        }).sort("due_date", 1).limit(10).to_list(10)

        for task in overdue_tasks:
            if not task.get("contact_id"):
                continue
            try:
                c = await db.contacts.find_one({"_id": ObjectId(task["contact_id"])})
                if not c:
                    continue
                due = task.get("due_date")
                if due:
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    days_late = (now - due).days
                    label = f"Overdue task: {task.get('title','Follow up')}" if days_late == 0 else f"{days_late}d overdue: {task.get('title','Follow up')}"
                else:
                    label = f"Task due: {task.get('title','Follow up')}"
                await add(c, "cooling_down", label, 9)
            except Exception:
                pass

        # Also grab due TODAY tasks (not yet overdue)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end   = today_start + timedelta(days=1)
        today_tasks = await db.tasks.find({
            "user_id":  user_id,
            "status":   {"$in": ["pending", "active", None]},
            "due_date": {"$gte": today_start, "$lt": today_end},
        }).sort("due_date", 1).limit(5).to_list(5)

        for task in today_tasks:
            if not task.get("contact_id"):
                continue
            try:
                c = await db.contacts.find_one({"_id": ObjectId(task["contact_id"])})
                if c:
                    await add(c, "cooling_down", f"Due today: {task.get('title','Follow up')}", 8)
            except Exception:
                pass

        # 1. Viewed your card in the last 48 hours
        cutoff_48h = now - timedelta(hours=48)
        views = await db.contact_events.find({
            "user_id":    user_id,
            "event_type": {"$in": ["card_viewed", "link_clicked", "digital_card_viewed"]},
            "timestamp":  {"$gte": cutoff_48h},
        }).sort("timestamp", -1).limit(10).to_list(10)
        for evt in views:
            if evt.get("contact_id"):
                try:
                    c = await db.contacts.find_one({"_id": ObjectId(evt["contact_id"])})
                    if c:
                        h = int((now - evt["timestamp"].replace(tzinfo=timezone.utc)).total_seconds() / 3600)
                        label = f"Viewed your card {h}h ago" if h > 0 else "Just viewed your card"
                        await add(c, "card_viewed", label, 10)
                except Exception:
                    pass

        # 2. Replied to a campaign (paused enrollments)
        paused = await db.campaign_enrollments.find({
            "user_id": user_id,
            "status":  "paused",
            "paused_reason": "customer_replied",
        }).sort("last_reply_at", -1).limit(5).to_list(5)
        for enroll in paused:
            if enroll.get("contact_id"):
                try:
                    c = await db.contacts.find_one({"_id": ObjectId(enroll["contact_id"])})
                    if c:
                        await add(c, "campaign_reply", score=10)
                except Exception:
                    pass

        # 3. Birthday within 3 days
        today_md  = (now.month, now.day)  # noqa
        bday_contacts = await db.contacts.find({
            "user_id": user_id,
            "birthday": {"$exists": True, "$ne": None},
        }).limit(200).to_list(200)
        for c in bday_contacts:
            try:
                bd = c.get("birthday")
                if isinstance(bd, str) and len(bd) >= 5:
                    parts = bd.replace("/", "-").split("-")
                    if len(parts) >= 2:
                        m, d = int(parts[-2]), int(parts[-1])
                        for offset in range(0, 4):
                            upcoming = now + timedelta(days=offset)
                            if upcoming.month == m and upcoming.day == d:
                                label = "Birthday today! 🎂" if offset == 0 else f"Birthday in {offset} day{'s' if offset > 1 else ''}"
                                await add(c, "birthday", label, 9 - offset)
                                break
            except Exception:
                pass

        # 4. Review link clicked but no review left
        cutoff_7d = now - timedelta(days=7)
        review_clicks = await db.contact_events.find({
            "user_id":    user_id,
            "event_type": {"$in": ["review_link_clicked", "review_request_sent"]},
            "timestamp":  {"$gte": cutoff_7d},
        }).sort("timestamp", -1).limit(5).to_list(5)
        for evt in review_clicks:
            if evt.get("contact_id"):
                try:
                    c = await db.contacts.find_one({"_id": ObjectId(evt["contact_id"])})
                    if c:
                        await add(c, "review_click", score=7)
                except Exception:
                    pass

        # 5. Purchased recently — prime for referral ask
        ref_start = now - timedelta(days=365)
        ref_end   = now - timedelta(days=90)
        sold_contacts = await db.contacts.find({
            "user_id": user_id,
            "tags":    {"$in": ["sold", "purchased", "customer", "Sold"]},
            "updated_at": {"$gte": ref_start, "$lte": ref_end},
        }).limit(20).to_list(20)
        for c in sold_contacts:
            await add(c, "purchase_followup", score=6)

        # 6. Cooling down — contacts with no recent activity (broadened query)
        if len(scored) < 6:
            # Get IDs of contacts touched in last 14 days (any event type)
            cutoff_14d = now - timedelta(days=14)
            recent_events = await db.contact_events.find({
                "user_id":   user_id,
                "timestamp": {"$gte": cutoff_14d},
            }).limit(500).to_list(500)
            recently_active = {str(e["contact_id"]) for e in recent_events if e.get("contact_id")}

            # Get recent task interactions too
            recent_tasks_done = await db.tasks.find({
                "user_id":     user_id,
                "status":      {"$in": ["completed", "done"]},
                "completed_at":{"$gte": cutoff_14d},
            }).limit(200).to_list(200)
            recently_active.update({str(t["contact_id"]) for t in recent_tasks_done if t.get("contact_id")})

            # Find contacts NOT recently active — no status filter so we don't miss anyone
            all_contacts = await db.contacts.find(
                {"user_id": user_id},
            ).sort("created_at", -1).limit(100).to_list(100)

            for c in all_contacts:
                if len(scored) >= 9:
                    break
                cid = str(c["_id"])
                if cid in recently_active or cid in seen_ids:
                    continue
                # Use any date field available
                last = (c.get("last_contacted_at") or
                        c.get("last_activity_at") or
                        c.get("updated_at") or
                        c.get("created_at"))
                if last:
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    days = (now - last).days
                    if days >= 7:  # Lowered from 14 to catch more
                        await add(c, "cooling_down",
                                  f"{days} days since last contact",
                                  max(3, 7 - (days // 14)))

    except Exception as e:
        logger.error(f"[Home] My-3 error: {e}")

    # Sort by score descending, return top 3
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


# ── Wins Feed ────────────────────────────────────────────────────────────────

async def get_wins_feed(user_id: str, db, limit: int = 15) -> list:
    """
    Recent dopamine moments — wins from other people engaging with you.
    Event types matched to what's actually stored in the DB.
    """
    WIN_TYPES = {
        # Card views — most common wins
        "digital_card_viewed":   {"msg": "viewed your digital card",       "icon": "eye",          "color": "#FF9500"},
        "congrats_card_viewed":  {"msg": "opened your congrats card",      "icon": "gift",         "color": "#FF375F"},
        "birthday_card_viewed":  {"msg": "opened your birthday card 🎂",   "icon": "gift",         "color": "#FF375F"},
        "holiday_card_viewed":   {"msg": "opened your holiday card",       "icon": "gift",         "color": "#FF375F"},
        "showcase_viewed":       {"msg": "viewed your showcase",           "icon": "storefront",   "color": "#34C759"},
        "digital_card_shared":   {"msg": "shared your digital card",       "icon": "share",        "color": "#5856D6"},
        # Engagement
        "review_link_clicked":   {"msg": "tapped your review link ⭐",     "icon": "star",         "color": "#FFD700"},
        "review_invite_sent":    {"msg": "received your review request",   "icon": "star-outline", "color": "#C9A962"},
        # Replies / contact saves
        "customer_reply":        {"msg": "replied to your message",        "icon": "chatbubble",   "color": "#34C759"},
        "digital_card_saved":    {"msg": "saved your contact info",        "icon": "person-add",   "color": "#007AFF"},
        "vcard_download":        {"msg": "downloaded your contact card",   "icon": "download",     "color": "#5856D6"},
        # Legacy names
        "card_viewed":           {"msg": "viewed your card",               "icon": "eye",          "color": "#FF9500"},
        "link_clicked":          {"msg": "clicked your link",              "icon": "hand-right",   "color": "#C9A962"},
    }

    wins = []
    try:
        # Get user's own info to filter self-actions
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "email": 1})
        own_name  = (user.get("name") or "").strip().lower() if user else ""
        own_email = (user.get("email") or "").strip().lower() if user else ""
        own_contact_ids: set = set()
        if own_email:
            # Find contacts with the rep's own email — these are self-test contacts
            self_contacts_direct = await db.contacts.find(
                {"user_id": user_id, "email": own_email},
                {"_id": 1}
            ).limit(10).to_list(10)
            own_contact_ids = {str(c["_id"]) for c in self_contacts_direct}
            # Also check via contact_events (legacy path)
            self_events = await db.contact_events.find(
                {"user_id": user_id, "contact_email": own_email},
                {"contact_id": 1}
            ).limit(5).to_list(5)
            own_contact_ids.update({str(c["contact_id"]) for c in self_events if c.get("contact_id")})

        # Use naive UTC to match stored timestamps (stored with datetime.utcnow())
        from datetime import datetime as _dt
        cutoff = _dt.utcnow() - timedelta(days=30)

        events = await db.contact_events.find({
            "user_id":    user_id,
            "event_type": {"$in": list(WIN_TYPES.keys())},
            "timestamp":  {"$gte": cutoff},
        }).sort("timestamp", -1).limit(limit * 3).to_list(limit * 3)

        seen_contact_event: set = set()  # dedupe same contact+event within feed

        for evt in events:
            if len(wins) >= limit:
                break

            meta  = WIN_TYPES.get(evt.get("event_type", ""), {})
            cid   = str(evt.get("contact_id") or "")
            cname = (evt.get("contact_name") or "").strip()

            # Resolve name if missing
            if not cname and cid:
                try:
                    c = await db.contacts.find_one(
                        {"_id": ObjectId(cid)},
                        {"first_name": 1, "last_name": 1}
                    )
                    if c:
                        cname = f"{c.get('first_name','')} {c.get('last_name','')}".strip()
                except Exception:
                    pass

            if not cname:
                cname = "Someone"

            # Skip self-actions: only filter contacts whose email matches the rep's own email
            # (Do NOT filter by name — too easy to accidentally match real customers)
            if cid and cid in own_contact_ids:
                continue

            # Dedupe: same contact + same event type shown max once per feed
            dedup_key = f"{cid}:{evt.get('event_type')}"
            if dedup_key in seen_contact_event:
                continue
            seen_contact_event.add(dedup_key)

            ts = evt.get("timestamp")
            if ts:
                # Make timezone-aware for consistent isoformat output
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

            wins.append({
                "contact_id":   cid or None,
                "contact_name": cname,
                "message":      f"{cname} {meta.get('msg', 'engaged with you')}",
                "icon":         meta.get("icon", "flash"),
                "color":        meta.get("color", "#007AFF"),
                "timestamp":    ts.isoformat() if ts else None,
                "event_type":   evt.get("event_type"),
            })

    except Exception as e:
        logger.warning(f"[Home] Wins feed error: {e}")
    return wins


# ── Combined endpoint ─────────────────────────────────────────────────────────

from cachetools import TTLCache as _TTLCache
_home_cache: _TTLCache = _TTLCache(maxsize=200, ttl=30)  # 30s cache — short enough to feel live

@router.get("/{user_id}")
async def get_home_data(user_id: str):
    """
    Single endpoint for the home screen.
    Cached 30s per user — prevents OOM from rapid refreshes.
    """
    import asyncio

    # Return cached result if fresh
    cached = _home_cache.get(user_id)
    if cached is not None:
        return cached

    db = get_db()

    # Run all three in parallel with a hard 8s timeout
    try:
        streak_data, my3_data, wins_data = await asyncio.wait_for(
            asyncio.gather(
                get_streak(user_id, db),
                get_my_3(user_id, db),
                get_wins_feed(user_id, db),
                return_exceptions=True,
            ),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[Home] Timeout for user {user_id} — returning empty")
        streak_data = {"streak": 0, "at_risk": False, "label": "Start your streak", "emoji": "💪"}
        my3_data    = []
        wins_data   = []

    result = {
        "streak":    streak_data if not isinstance(streak_data, Exception) else {"streak": 0, "at_risk": False, "label": "Start your streak", "emoji": "💪"},
        "my_3":      my3_data    if not isinstance(my3_data,    Exception) else [],
        "wins_feed": wins_data   if not isinstance(wins_data,   Exception) else [],
    }

    # Cache the result
    _home_cache[user_id] = result
    return result


@router.delete("/{user_id}/cache")
async def bust_home_cache(user_id: str):
    """Force-expire the home cache for a user (called after activity events)."""
    _home_cache.pop(user_id, None)
    return {"cleared": True}
