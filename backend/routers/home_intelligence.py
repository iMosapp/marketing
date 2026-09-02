"""
Home Screen Intelligence — /api/home/

Powers the addictive daily habit loop:
  - My 3 for Today: AI picks 3 contacts to reach out to, with context + one-tap action
  - Streak: days of consecutive relationship activity
  - Wins Feed: recent dopamine moments (views, replies, clicks)
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Query

from routers.database import get_db
from utils.photo_url import abs_photo_url, contact_photo_url

router = APIRouter(prefix="/home", tags=["home"])
logger = logging.getLogger(__name__)


@router.get("/weekly-wins/{user_id}")
async def weekly_wins(user_id: str):
    """Last week's (Mon-Sun) wins for the Monday recap card."""
    db = get_db()
    now = datetime.now(timezone.utc)
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    start = this_monday - timedelta(days=7)
    end = this_monday
    sold = await db.contacts.count_documents({"user_id": user_id, "date_sold": {"$gte": start, "$lt": end}})
    texts = await db.messages.count_documents({"user_id": user_id, "sender": "user", "timestamp": {"$gte": start, "$lt": end}})
    scans = await db.card_scans.count_documents({"user_id": user_id, "scanned_at": {"$gte": start, "$lt": end}})
    new_contacts = await db.contacts.count_documents({"user_id": user_id, "created_at": {"$gte": start, "$lt": end}})
    waiting_cleared = await db.waiting_clear_log.count_documents({"user_id": user_id, "cleared_at": {"$gte": start, "$lt": end}})
    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "sold": sold,
        "texts": texts,
        "scans": scans,
        "new_contacts": new_contacts,
        "waiting_cleared": waiting_cleared,
    }


def _abs_photo(u: str) -> str:
    return abs_photo_url(u)


@router.get("/weekly-wins/{user_id}/list")
async def weekly_wins_list(user_id: str, type: str = "sold"):
    """
    Drill-down list behind each Last Week's Wins tile.
    type: sold | texts | scans | contacts
    Returns people/events for the same Mon-Sun window as /weekly-wins.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    start = this_monday - timedelta(days=7)
    end = this_monday

    def _name(c: dict) -> str:
        return f"{c.get('first_name','')} {c.get('last_name','')}".strip() or c.get('company', '') or 'Unknown'

    items: list = []
    title = "Last Week"

    if type == "sold":
        title = "Sold Last Week"
        docs = await db.contacts.find(
            {"user_id": user_id, "date_sold": {"$gte": start, "$lt": end},
             "status": {"$nin": ["hidden", "merged", "deleted"]}},
            {"first_name": 1, "last_name": 1, "company": 1, "vehicle": 1, "date_sold": 1, "photo_thumbnail": 1}
        ).sort("date_sold", -1).to_list(500)
        items = [{
            "id": str(c["_id"]), "contact_id": str(c["_id"]), "name": _name(c),
            "subtitle": c.get("vehicle", ""), "photo_thumbnail": _abs_photo(c.get("photo_thumbnail", "")),
            "date": c["date_sold"].isoformat() if c.get("date_sold") else "",
        } for c in docs]

    elif type == "contacts":
        title = "New Contacts Last Week"
        docs = await db.contacts.find(
            {"user_id": user_id, "created_at": {"$gte": start, "$lt": end},
             "status": {"$nin": ["hidden", "merged", "deleted"]}},
            {"first_name": 1, "last_name": 1, "company": 1, "phone": 1, "source": 1, "created_at": 1, "photo_thumbnail": 1}
        ).sort("created_at", -1).to_list(500)
        items = [{
            "id": str(c["_id"]), "contact_id": str(c["_id"]), "name": _name(c),
            "subtitle": c.get("source", "") or c.get("phone", ""),
            "photo_thumbnail": _abs_photo(c.get("photo_thumbnail", "")),
            "date": c["created_at"].isoformat() if c.get("created_at") else "",
        } for c in docs]

    elif type == "texts":
        title = "Texted Last Week"
        # Distinct conversations the user sent a message in, most-recent first
        pipeline = [
            {"$match": {"user_id": user_id, "sender": "user", "timestamp": {"$gte": start, "$lt": end}}},
            {"$group": {"_id": "$conversation_id", "last": {"$max": "$timestamp"}, "count": {"$sum": 1}}},
            {"$sort": {"last": -1}},
            {"$limit": 500},
        ]
        groups = await db.messages.aggregate(pipeline).to_list(500)
        for g in groups:
            conv_id = g["_id"]
            conv = None
            try:
                conv = await db.conversations.find_one({"_id": ObjectId(str(conv_id))})
            except Exception:
                conv = None
            contact = None
            phone = (conv or {}).get("contact_phone", "")
            cid = (conv or {}).get("contact_id")
            if cid:
                try:
                    contact = await db.contacts.find_one(
                        {"_id": ObjectId(str(cid))},
                        {"first_name": 1, "last_name": 1, "company": 1, "phone": 1, "photo_thumbnail": 1}
                    )
                except Exception:
                    contact = None
            nsent = g.get("count", 0)
            items.append({
                "id": str(conv_id),
                "contact_id": str(cid) if cid else "",
                "name": _name(contact) if contact else (phone or "Unknown"),
                "subtitle": f"{nsent} message{'s' if nsent != 1 else ''} sent",
                "photo_thumbnail": _abs_photo((contact or {}).get("photo_thumbnail", "")),
                "date": g["last"].isoformat() if g.get("last") else "",
            })

    elif type == "scans":
        title = "QR Scans Last Week"
        docs = await db.card_scans.find(
            {"user_id": user_id, "scanned_at": {"$gte": start, "$lt": end}}
        ).sort("scanned_at", -1).to_list(500)
        items = [{
            "id": str(d["_id"]), "contact_id": "",
            "name": "Card scan",
            "subtitle": "Someone scanned your QR / card link",
            "photo_thumbnail": "",
            "date": d["scanned_at"].isoformat() if d.get("scanned_at") else "",
        } for d in docs]

    return {
        "type": type,
        "title": title,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "count": len(items),
        "items": items,
    }


@router.get("/reply-health/{user_id}")
async def reply_health(user_id: str):
    """AI replies that failed to send in the last 24h — powers the Home warning card."""
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    q = {
        "$or": [{"assigned_user_id": user_id}, {"user_id": user_id}],
        "status": "failed",
        "created_at": {"$gte": cutoff},
    }
    failed = await db.ai_reply_queue.count_documents(q)
    last = await db.ai_reply_queue.find_one(q, sort=[("created_at", -1)]) if failed else None
    return {
        "failed": failed,
        "conversation_id": (last or {}).get("conversation_id"),
        "error": (last or {}).get("error"),
    }


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


def _personal_hook(contact: dict) -> str:
    """A short, human tidbit from extracted personal_details to make reasons feel personal."""
    pd = contact.get("personal_details") or {}
    if not isinstance(pd, dict):
        return ""
    interests = pd.get("interests") or []
    kids = pd.get("kids") or []
    if isinstance(interests, list) and interests:
        return f"Loves {interests[0]}"
    if pd.get("spouse"):
        return f"Spouse: {pd['spouse']}"
    if isinstance(kids, list) and kids:
        return f"Kids: {', '.join(str(k) for k in kids[:2])}"
    if pd.get("referral_potential"):
        return "Possible referral source"
    notes = pd.get("personal_notes")
    if notes:
        return str(notes)[:60]
    return ""


async def get_my_3(user_id: str, db, top_n: int = 3) -> list:
    """
    AI-powered daily contact recommendations.
    Returns up to top_n contacts with reason, context, and a suggested action.
    Optimised: batch contact lookups, lean projections — no N+1 queries, no photo blobs.
    """
    cap = max(9, top_n + 3)
    now       = datetime.now(timezone.utc)
    scored: list = []
    seen_ids: set = set()

    # Minimal projection — never load the heavy photo/photo_data blob
    CONTACT_PROJ = {
        "_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1,
        "photo_url": 1, "photo_thumbnail": 1, "photo_path": 1,
        "tags": 1, "vehicle": 1, "birthday": 1, "anniversary": 1, "personal_details": 1,
        "last_contacted_at": 1, "last_activity_at": 1, "updated_at": 1, "created_at": 1,
    }

    async def batch_contacts(ids: list) -> dict:
        """Fetch multiple contacts by ID in one query. Returns {str_id: doc}."""
        if not ids:
            return {}
        oids = []
        for cid in ids:
            try:
                oids.append(ObjectId(cid))
            except Exception:
                pass
        if not oids:
            return {}
        docs = await db.contacts.find({"_id": {"$in": oids}}, CONTACT_PROJ).to_list(len(oids))
        return {str(d["_id"]): d for d in docs}

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
            "photo_url":    contact_photo_url(contact),
            "reason_key":   reason_key,
            "reason_label": extra_label or meta.get("label", ""),
            "hook":         _personal_hook(contact),
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
        }, {"contact_id": 1, "title": 1, "due_date": 1}).sort("due_date", 1).limit(10).to_list(10)

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end   = today_start + timedelta(days=1)
        today_tasks = await db.tasks.find({
            "user_id":  user_id,
            "status":   {"$in": ["pending", "active", None]},
            "due_date": {"$gte": today_start, "$lt": today_end},
        }, {"contact_id": 1, "title": 1}).sort("due_date", 1).limit(5).to_list(5)

        # Batch fetch contacts for tasks
        task_contact_ids = list({t["contact_id"] for t in overdue_tasks + today_tasks if t.get("contact_id")})
        task_contacts = await batch_contacts(task_contact_ids)

        for task in overdue_tasks:
            c = task_contacts.get(str(task.get("contact_id", "")))
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

        for task in today_tasks:
            c = task_contacts.get(str(task.get("contact_id", "")))
            if c:
                await add(c, "cooling_down", f"Due today: {task.get('title','Follow up')}", 8)

        # 1. Viewed your card in the last 48 hours
        cutoff_48h = now - timedelta(hours=48)
        views = await db.contact_events.find({
            "user_id":    user_id,
            "event_type": {"$in": ["card_viewed", "link_clicked", "digital_card_viewed"]},
            "timestamp":  {"$gte": cutoff_48h},
        }, {"contact_id": 1, "timestamp": 1}).sort("timestamp", -1).limit(10).to_list(10)

        view_contact_ids = list({str(e["contact_id"]) for e in views if e.get("contact_id")})
        view_contacts = await batch_contacts(view_contact_ids)
        for evt in views:
            c = view_contacts.get(str(evt.get("contact_id", "")))
            if c:
                ts = evt.get("timestamp")
                h = int((now - ts.replace(tzinfo=timezone.utc)).total_seconds() / 3600) if ts else 0
                label = f"Viewed your card {h}h ago" if h > 0 else "Just viewed your card"
                await add(c, "card_viewed", label, 10)

        # 2. Replied to a campaign (paused enrollments)
        paused = await db.campaign_enrollments.find({
            "user_id": user_id,
            "status":  "paused",
            "paused_reason": "customer_replied",
        }, {"contact_id": 1}).sort("last_reply_at", -1).limit(5).to_list(5)

        paused_contact_ids = list({str(e["contact_id"]) for e in paused if e.get("contact_id")})
        paused_contacts = await batch_contacts(paused_contact_ids)
        for enroll in paused:
            c = paused_contacts.get(str(enroll.get("contact_id", "")))
            if c:
                await add(c, "campaign_reply", score=10)

        # 3. Birthday within 3 days — lean projection, tight limit
        bday_contacts = await db.contacts.find({
            "user_id": user_id,
            "birthday": {"$exists": True, "$ne": None},
        }, CONTACT_PROJ).limit(50).to_list(50)

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
        }, {"contact_id": 1}).sort("timestamp", -1).limit(5).to_list(5)

        review_contact_ids = list({str(e["contact_id"]) for e in review_clicks if e.get("contact_id")})
        review_contacts = await batch_contacts(review_contact_ids)
        for evt in review_clicks:
            c = review_contacts.get(str(evt.get("contact_id", "")))
            if c:
                await add(c, "review_click", score=7)

        # 5. Purchased recently — prime for referral ask
        ref_start = now - timedelta(days=365)
        ref_end   = now - timedelta(days=90)
        sold_contacts = await db.contacts.find({
            "user_id": user_id,
            "tags":    {"$in": ["sold", "purchased", "customer", "Sold"]},
            "updated_at": {"$gte": ref_start, "$lte": ref_end},
        }, CONTACT_PROJ).limit(20).to_list(20)
        for c in sold_contacts:
            await add(c, "purchase_followup", score=6)

        # 6. Cooling down — contacts with no recent activity
        if len(scored) < cap:
            # Fetch only contact_ids from events (no full docs) — 100 events max
            cutoff_14d = now - timedelta(days=14)
            recent_events = await db.contact_events.find({
                "user_id":   user_id,
                "timestamp": {"$gte": cutoff_14d},
            }, {"contact_id": 1}).limit(100).to_list(100)
            recently_active = {str(e["contact_id"]) for e in recent_events if e.get("contact_id")}

            recent_tasks_done = await db.tasks.find({
                "user_id":      user_id,
                "status":       {"$in": ["completed", "done"]},
                "completed_at": {"$gte": cutoff_14d},
            }, {"contact_id": 1}).limit(50).to_list(50)
            recently_active.update({str(t["contact_id"]) for t in recent_tasks_done if t.get("contact_id")})

            # Lean contact fetch — always exclude photo blob
            all_contacts = await db.contacts.find(
                {"user_id": user_id},
                CONTACT_PROJ,
            ).sort("created_at", -1).limit(max(50, cap * 6)).to_list(max(50, cap * 6))

            for c in all_contacts:
                if len(scored) >= cap:
                    break
                cid = str(c["_id"])
                if cid in recently_active or cid in seen_ids:
                    continue
                last = (c.get("last_contacted_at") or
                        c.get("last_activity_at") or
                        c.get("updated_at") or
                        c.get("created_at"))
                if last:
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    days = (now - last).days
                    if days >= 7:
                        await add(c, "cooling_down",
                                  f"{days} days since last contact",
                                  max(3, 7 - (days // 14)))

    except Exception as e:
        logger.error(f"[Home] My-3 error: {e}")

    # Sort by score descending, return top_n
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


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
        }, {"contact_id": 1, "contact_name": 1, "event_type": 1, "timestamp": 1}).sort("timestamp", -1).limit(limit * 3).to_list(limit * 3)

        # Batch fetch all missing contact names in one query
        missing_name_ids = [str(e["contact_id"]) for e in events if not (e.get("contact_name") or "").strip() and e.get("contact_id")]
        name_map: dict = {}
        if missing_name_ids:
            oids = []
            for cid in missing_name_ids:
                try:
                    oids.append(ObjectId(cid))
                except Exception:
                    pass
            if oids:
                docs = await db.contacts.find({"_id": {"$in": oids}}, {"_id": 1, "first_name": 1, "last_name": 1}).to_list(len(oids))
                for d in docs:
                    name_map[str(d["_id"])] = f"{d.get('first_name','')} {d.get('last_name','')}".strip()

        seen_contact_event: set = set()  # dedupe same contact+event within feed

        for evt in events:
            if len(wins) >= limit:
                break

            meta  = WIN_TYPES.get(evt.get("event_type", ""), {})
            cid   = str(evt.get("contact_id") or "")
            cname = (evt.get("contact_name") or "").strip()

            # Resolve name from batch map if missing
            if not cname and cid:
                cname = name_map.get(cid, "")

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


# ── One-tap message draft — powers the "What to send" sheet on Home ──────────

DRAFT_BRIEFS = {
    "card_viewed":       "They just viewed my digital business card. Write a friendly follow-up that opens a conversation.",
    "campaign_reply":    "They replied to a recent message of mine. Write a warm response that re-opens the conversation.",
    "birthday":          "Their birthday is coming up. Write a warm, personal birthday wish.",
    "anniversary":       "Their purchase anniversary is this week. Write a warm note marking the occasion.",
    "cooling_down":      "It has been a while since we last talked. Write a casual, no-pressure check-in.",
    "review_click":      "They clicked my review link but may not have finished the review. Write a gentle, appreciative nudge.",
    "warm_lead":         "This is a warm lead actively showing interest. Write a helpful, low-pressure reach-out offering to answer questions.",
    "purchase_followup": "They bought from me recently. Write a thank-you check-in asking how everything is going.",
    "touchpoint":        "I have a scheduled follow-up touchpoint due for them. Write a friendly message that fits the task.",
}

DRAFT_FALLBACKS = {
    "card_viewed":       "Hey {first}! Saw you checked out my card. Anything I can help you with? Happy to answer any questions.",
    "campaign_reply":    "Hey {first}! Thanks for getting back to me. What can I help you with?",
    "birthday":          "Happy early birthday, {first}! 🎉 Hope you have an amazing one. Let me know if there's anything I can do for you.",
    "anniversary":       "Hey {first}! Can't believe it's already been a year. Happy anniversary! Hope everything's still treating you great.",
    "cooling_down":      "Hey {first}! It's been a minute, just checking in to see how everything's going. Anything I can help with?",
    "review_click":      "Hey {first}! Thanks for taking a look at that review link. If you get a sec to finish it, it'd mean the world to me!",
    "warm_lead":         "Hey {first}! Just wanted to reach out, I'm here if you have any questions at all. No pressure!",
    "purchase_followup": "Hey {first}! Just checking in, how's everything going with your purchase? Let me know if you need anything at all.",
    "touchpoint":        "Hey {first}! You crossed my mind today, just wanted to check in and see how everything's going. Anything I can help with?",
}

DRAFT_SYSTEM_PROMPT = """You write ONE short, casual, ready-to-send text message from a salesperson to their customer.
Rules:
- 1-3 sentences max, warm and conversational — like texting a friend
- Sound human, never salesy or robotic
- Use the customer's first name once
- At most one emoji, or none
- NEVER use em dashes (—) or en dashes (–) anywhere. Use a comma or a period instead.
- Output ONLY the message text. No quotes, no preamble, no options."""


@router.get("/draft/{user_id}/{contact_id}")
async def draft_message(user_id: str, contact_id: str, reason: str = "", context: str = ""):
    """Generate one ready-to-send text message for a contact, tailored to why they're being recommended."""
    import asyncio
    db = get_db()
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    except Exception:
        contact = None
    if not contact:
        return {"message": "Hey! Just checking in — how's everything going?"}

    first = contact.get("first_name", "") or "there"
    fallback = DRAFT_FALLBACKS.get(reason, DRAFT_FALLBACKS["cooling_down"]).format(first=first)

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return {"message": fallback}

    parts = [f"Customer first name: {first}"]
    if contact.get("vehicle"):
        parts.append(f"Their purchase/vehicle: {contact['vehicle']}")
    if contact.get("spouse_name"):
        parts.append(f"Spouse: {contact['spouse_name']}")
    if contact.get("occupation") or contact.get("employer"):
        parts.append(f"Work: {contact.get('occupation', '')} {contact.get('employer', '')}".strip())
    if contact.get("tags"):
        parts.append(f"Tags: {', '.join(contact['tags'][:5])}")
    last = contact.get("last_contacted_at") or contact.get("last_activity_at")
    if isinstance(last, datetime):
        days = (datetime.now(timezone.utc) - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))).days
        parts.append(f"Days since last contact: {days}")
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "persona.banned_words": 1})
    if user and user.get("name"):
        parts.append(f"Salesperson name: {user['name'].split()[0]}")
    banned = ((user or {}).get("persona") or {}).get("banned_words", "")
    brief = DRAFT_BRIEFS.get(reason, DRAFT_BRIEFS["cooling_down"])
    if context:
        parts.append(f"The task/occasion: {context[:200]}")
    if banned:
        parts.append(f"NEVER use these words or phrases: {banned}")
    prompt = f"Situation: {brief}\n\n" + "\n".join(parts)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import secrets as _secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"homedraft_{user_id}_{_secrets.token_hex(4)}",
            system_message=DRAFT_SYSTEM_PROMPT,
        ).with_model("openai", "gpt-5.2")
        text = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=12.0)
        text = (text or "").strip().strip('"').strip()
        from utils.text_sanitize import clean_ai_text
        text = await clean_ai_text(text, user_id)
        if not text or len(text) > 500:
            text = fallback
        return {"message": text}
    except Exception as e:
        logger.warning(f"[HomeDraft] LLM failed, using fallback: {e}")
        return {"message": fallback}


# ── People to Talk To Today (full feed) ──────────────────────────────────────

@router.get("/people-to-engage/{user_id}")
async def people_to_engage(user_id: str, limit: int = Query(25, ge=1, le=50)):
    """
    The full 'People You Should Talk To Today' feed — same scoring engine as
    'My 3 for Today', just uncapped. Each item carries the reason + suggested action.
    """
    db = get_db()
    people = await get_my_3(user_id, db, top_n=limit)
    return {"count": len(people), "people": people}


# ── Touch Mix (Transactional / Promotional / Relationship) ───────────────────

_PROMO_WORDS = (
    "sale", "deal", "offer", "discount", "special", "% off", "save", "trade",
    "buy your", "cash offer", "we'd like to buy", "we would like to buy", "limited time",
    "clearance", "financing", "apr", "lease special", "event",
)
_TRANSACT_WORDS = (
    "oil change", "service", "maintenance", "appointment", "scheduled", "reminder",
    "due for", "recall", "warranty", "confirm", "confirmation", "your order",
    "ready for pickup", "invoice", "payment", "paperwork", "documents",
)


def _classify_touch(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in _PROMO_WORDS):
        return "promotional"
    if any(w in t for w in _TRANSACT_WORDS):
        return "transactional"
    return "relationship"


@router.get("/touch-mix/{user_id}")
async def touch_mix(user_id: str, days: int = Query(7, ge=1, le=365)):
    """
    Classifies the rep's outbound messages over the last N days into
    Transactional / Promotional / Relationship so they can see if they're
    actually building relationships or just pushing marketing.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    # Mixed-schema safe: outbound = direction 'outbound' OR sender 'user',
    # and explicitly exclude anything marked inbound.
    msgs = await db.messages.find(
        {
            "user_id": user_id,
            "timestamp": {"$gte": start},
            "$or": [{"direction": "outbound"}, {"sender": "user"}],
            "direction": {"$ne": "inbound"},
            "sender": {"$ne": "contact"},
        },
        {"content": 1},
    ).limit(3000).to_list(3000)

    counts = {"relationship": 0, "transactional": 0, "promotional": 0}
    for m in msgs:
        counts[_classify_touch(m.get("content", ""))] += 1
    total = sum(counts.values())
    rel_pct = round((counts["relationship"] / total) * 100) if total else 0
    return {
        "days": days,
        "total": total,
        "counts": counts,
        "relationship_pct": rel_pct,
    }


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
