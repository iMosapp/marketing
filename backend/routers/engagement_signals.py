"""
Engagement Intelligence — Real-time customer engagement tracking.
Records signals when customers view cards, click links, download content.
Detects "second look" return visits. Powers the Hot Leads dashboard.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter
from bson import ObjectId
from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/engagement", tags=["engagement-intelligence"])

SIGNAL_TYPES = {
    "card_viewed": {"icon": "eye", "color": "#007AFF", "label": "Viewed Your Card"},
    "card_downloaded": {"icon": "download", "color": "#34C759", "label": "Downloaded Your Card"},
    "card_shared": {"icon": "share-social", "color": "#AF52DE", "label": "Shared Your Card"},
    "digital_card_viewed": {"icon": "person-circle", "color": "#007AFF", "label": "Viewed Your Digital Card"},
    "review_link_clicked": {"icon": "star", "color": "#FFD60A", "label": "Clicked Review Link"},
    "showcase_viewed": {"icon": "images", "color": "#C9A962", "label": "Viewed Your Showcase"},
    "link_page_viewed": {"icon": "link", "color": "#AF52DE", "label": "Viewed Your Link Page"},
    "contact_saved": {"icon": "person-add", "color": "#34C759", "label": "Saved Your Contact"},
    "link_clicked": {"icon": "open", "color": "#007AFF", "label": "Clicked Your Link"},
}


async def record_signal(
    signal_type: str,
    user_id: str,
    contact_id: Optional[str] = None,
    contact_name: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """
    Record an engagement signal and create a notification.
    Call this from any tracking endpoint when a customer interacts with content.
    Detects "second look" return visits automatically.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    type_info = SIGNAL_TYPES.get(signal_type, {"icon": "eye", "color": "#007AFF", "label": signal_type})

    # Skip if no user_id
    if not user_id:
        return

    # Resolve contact name if we have contact_id but no name
    if contact_id and not contact_name:
        try:
            c = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
            if c:
                contact_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        except Exception:
            pass

    contact_name = contact_name or "Someone"

    # Check for recent duplicate (within 5 minutes = same session)
    recent = await db.engagement_signals.find_one({
        "user_id": user_id,
        "contact_id": contact_id,
        "signal_type": signal_type,
        "created_at": {"$gte": now - timedelta(minutes=5)},
    })
    if recent:
        return  # Same person, same action, same session — skip

    # Detect "second look" — has this contact viewed anything before?
    is_return_visit = False
    if contact_id:
        previous = await db.engagement_signals.find_one({
            "user_id": user_id,
            "contact_id": contact_id,
            "created_at": {"$lt": now - timedelta(minutes=30)},
        })
        is_return_visit = previous is not None

    # Count total views by this contact (for "looked at your card 3 times" messages)
    view_count = 0
    if contact_id:
        view_count = await db.engagement_signals.count_documents({
            "user_id": user_id,
            "contact_id": contact_id,
        })

    # Store the signal
    signal_doc = {
        "signal_type": signal_type,
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "is_return_visit": is_return_visit,
        "view_count": view_count + 1,
        "metadata": metadata or {},
        "created_at": now,
    }
    await db.engagement_signals.insert_one(signal_doc)

    # Build notification message
    if is_return_visit:
        if view_count >= 3:
            title = f"{contact_name} keeps coming back"
            body = f"Viewed your content {view_count + 1} times. Hot lead!"
        else:
            title = f"{contact_name} looked again"
            body = f"{type_info['label']} — this is a return visit"
    else:
        title = f"{contact_name} just engaged"
        body = type_info["label"]

    # Create notification for the salesperson
    notif_doc = {
        "type": "engagement_signal",
        "signal_type": signal_type,
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "title": title,
        "message": body,
        "icon": type_info["icon"],
        "color": type_info["color"],
        "is_return_visit": is_return_visit,
        "view_count": view_count + 1,
        "read": False,
        "dismissed": False,
        "created_at": now,
    }
    await db.notifications.insert_one(notif_doc)

    logger.info(f"[Engagement] {signal_type}: {contact_name} → {user_id} (return={is_return_visit})")


@router.get("/hot-leads/{user_id}")
async def get_hot_leads(user_id: str, hours: int = 48):
    """
    Get contacts with recent engagement — sorted by most recent activity.
    This is the "Customers Looking At You Right Now" feed.
    """
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    pipeline = [
        {"$match": {"user_id": user_id, "created_at": {"$gte": cutoff}}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": {"$ifNull": ["$contact_id", "$contact_name"]},
            "contact_id": {"$first": "$contact_id"},
            "contact_name": {"$first": "$contact_name"},
            "last_signal": {"$first": "$signal_type"},
            "last_activity": {"$first": "$created_at"},
            "total_signals": {"$sum": 1},
            "is_return_visit": {"$first": "$is_return_visit"},
            "signal_types": {"$addToSet": "$signal_type"},
        }},
        {"$sort": {"last_activity": -1}},
        {"$limit": 30},
    ]

    results = await db.engagement_signals.aggregate(pipeline).to_list(30)

    hot_leads = []
    for r in results:
        contact_id = r.get("contact_id")  # May be None for anonymous views

        # Calculate "heat" score: more signals + return visits = hotter
        heat = r["total_signals"]
        if r.get("is_return_visit"):
            heat *= 2
        if len(r.get("signal_types", [])) > 1:
            heat *= 1.5

        # Time-based urgency
        last = r["last_activity"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        minutes_ago = (datetime.now(timezone.utc) - last).total_seconds() / 60

        # Get contact phone for quick action
        phone = None
        if contact_id:
            try:
                contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"phone": 1})
                if contact:
                    phone = contact.get("phone")
            except Exception:
                pass

        type_info = SIGNAL_TYPES.get(r["last_signal"], {"icon": "eye", "color": "#007AFF", "label": r["last_signal"]})

        hot_leads.append({
            "contact_id": contact_id,
            "contact_name": r["contact_name"] or "Unknown",
            "last_signal": r["last_signal"],
            "last_signal_label": type_info["label"],
            "last_signal_icon": type_info["icon"],
            "last_signal_color": type_info["color"],
            "last_activity": last.isoformat(),
            "minutes_ago": round(minutes_ago),
            "total_signals": r["total_signals"],
            "signal_types": r.get("signal_types", []),
            "is_return_visit": r.get("is_return_visit", False),
            "heat_score": round(heat, 1),
            "phone": phone,
        })

    # Sort by heat score
    hot_leads.sort(key=lambda x: (-x["heat_score"], x["minutes_ago"]))

    return {
        "hot_leads": hot_leads,
        "total": len(hot_leads),
        "period_hours": hours,
    }


@router.get("/signals/{user_id}")
async def get_signals(user_id: str, limit: int = 50):
    """Get recent engagement signals for a user — the raw activity feed."""
    db = get_db()

    signals = await db.engagement_signals.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)

    for s in signals:
        type_info = SIGNAL_TYPES.get(s.get("signal_type", ""), {})
        s["label"] = type_info.get("label", s.get("signal_type", ""))
        s["icon"] = type_info.get("icon", "eye")
        s["color"] = type_info.get("color", "#007AFF")
        if s.get("created_at"):
            s["created_at"] = s["created_at"].isoformat()

    return {"signals": signals, "total": len(signals)}
