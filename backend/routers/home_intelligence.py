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
        today_md  = (now.month, now.day)  # noqa — kept for readable reference
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

        # 5. Purchased recently (6-12 months ago) — prime for referral ask
        ref_start = now - timedelta(days=365)
        ref_end   = now - timedelta(days=150)
        sold_tags_contacts = await db.contacts.find({
            "user_id": user_id,
            "tags":    {"$in": ["sold", "purchased", "customer"]},
            "updated_at": {"$gte": ref_start, "$lte": ref_end},
        }).limit(20).to_list(20)
        for c in sold_tags_contacts:
            await add(c, "purchase_followup", score=6)

        # 6. Cooling down — no contact in 14+ days (overdue follow-up)
        cutoff_14d = now - timedelta(days=14)
        if len(scored) < 6:
            recent_contacted = set()
            recent_events = await db.contact_events.find({
                "user_id":   user_id,
                "timestamp": {"$gte": cutoff_14d},
                "category":  {"$in": ["sent", "outbound", "touchpoint"]},
            }).to_list(500)
            for e in recent_events:
                if e.get("contact_id"):
                    recent_contacted.add(str(e["contact_id"]))

            old_contacts = await db.contacts.find({
                "user_id": user_id,
                "status":  "active",
            }).sort("updated_at", -1).skip(5).limit(30).to_list(30)

            for c in old_contacts:
                cid = str(c["_id"])
                if cid not in recent_contacted:
                    last = c.get("last_contacted_at") or c.get("updated_at")
                    if last:
                        if last.tzinfo is None:
                            last = last.replace(tzinfo=timezone.utc)
                        days = (now - last).days
                        if days >= 14:
                            await add(c, "cooling_down", f"{days} days since last contact", max(3, 7 - (days // 7)))

    except Exception as e:
        logger.error(f"[Home] My-3 error: {e}")

    # Sort by score descending, return top 3
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


# ── Wins Feed ────────────────────────────────────────────────────────────────

async def get_wins_feed(user_id: str, db, limit: int = 15) -> list:
    """
    Recent dopamine moments — card views, replies, review clicks.
    Filtered to only the rewarding events, not boring system events.
    """
    WIN_TYPES = {
        "card_viewed":           {"msg": "viewed your digital card",       "icon": "eye",          "color": "#FF9500"},
        "digital_card_viewed":   {"msg": "viewed your digital card",       "icon": "eye",          "color": "#FF9500"},
        "link_clicked":          {"msg": "clicked your link",              "icon": "hand-right",   "color": "#C9A962"},
        "customer_reply":        {"msg": "replied to your message",        "icon": "chatbubble",   "color": "#34C759"},
        "review_link_clicked":   {"msg": "tapped your review link",        "icon": "star",         "color": "#FFD700"},
        "digital_card_saved":    {"msg": "saved your contact info",        "icon": "person-add",   "color": "#007AFF"},
        "vcard_download":        {"msg": "downloaded your contact card",   "icon": "download",     "color": "#5856D6"},
        "congrats_card_viewed":  {"msg": "opened your card",               "icon": "gift",         "color": "#FF375F"},
    }
    wins = []
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        events = await db.contact_events.find({
            "user_id":    user_id,
            "event_type": {"$in": list(WIN_TYPES.keys())},
            "timestamp":  {"$gte": cutoff},
        }).sort("timestamp", -1).limit(limit).to_list(limit)

        for evt in events:
            meta    = WIN_TYPES.get(evt.get("event_type", ""), {})
            cid     = evt.get("contact_id")
            cname   = evt.get("contact_name") or "Someone"
            if cid and cname == "Someone":
                try:
                    c = await db.contacts.find_one({"_id": ObjectId(cid)}, {"first_name": 1, "last_name": 1})
                    if c:
                        cname = f"{c.get('first_name','')} {c.get('last_name','')}".strip() or "Someone"
                except Exception:
                    pass
            ts = evt.get("timestamp")
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            wins.append({
                "contact_id":   cid,
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

@router.get("/{user_id}")
async def get_home_data(user_id: str):
    """
    Single endpoint powers the entire new home screen.
    Returns: streak, my_3, wins_feed.
    Lightweight — all data fetched in parallel.
    """
    import asyncio
    db = get_db()

    streak_data, my3_data, wins_data = await asyncio.gather(
        get_streak(user_id, db),
        get_my_3(user_id, db),
        get_wins_feed(user_id, db),
        return_exceptions=True,
    )

    return {
        "streak":    streak_data if not isinstance(streak_data, Exception) else {"streak": 0, "at_risk": False, "label": "Start your streak", "emoji": "💪"},
        "my_3":      my3_data    if not isinstance(my3_data,    Exception) else [],
        "wins_feed": wins_data   if not isinstance(wins_data,   Exception) else [],
    }
