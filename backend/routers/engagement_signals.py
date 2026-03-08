"""
Engagement Intelligence — Real-time customer engagement tracking.
Records signals when customers view cards, click links, download content.
Detects "second look" return visits. Powers the Hot Leads dashboard.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
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


# ────────────────── MANAGER / TEAM ENDPOINTS ──────────────────


async def _get_team_user_ids(manager_id: str) -> list[str]:
    """Get user IDs for everyone on the manager's team (same store/org)."""
    db = get_db()
    manager = await db.users.find_one({"_id": ObjectId(manager_id)}, {"store_id": 1, "store_ids": 1, "organization_id": 1, "role": 1})
    if not manager:
        return []

    query: dict = {}
    role = manager.get("role", "user")

    if role in ("super_admin", "org_admin"):
        org_id = manager.get("organization_id")
        if org_id:
            query = {"organization_id": org_id if isinstance(org_id, str) else str(org_id)}
    elif role == "store_manager":
        store_ids = manager.get("store_ids", [])
        if not store_ids:
            sid = manager.get("store_id")
            store_ids = [sid] if sid else []
        if store_ids:
            query = {"$or": [{"store_id": {"$in": store_ids}}, {"store_ids": {"$elemMatch": {"$in": store_ids}}}]}
    else:
        return [manager_id]

    if not query:
        return [manager_id]

    users = await db.users.find(query, {"_id": 1}).to_list(200)
    return [str(u["_id"]) for u in users]


@router.get("/team-hot-leads/{manager_id}")
async def get_team_hot_leads(manager_id: str, hours: int = 48):
    """
    Manager view: hot leads across all team members.
    Returns leads grouped by rep with engagement scores.
    """
    db = get_db()
    team_ids = await _get_team_user_ids(manager_id)
    if not team_ids:
        return {"hot_leads": [], "team_stats": [], "total": 0, "alert_leads": []}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # ── Hot leads aggregation (across all team members) ──
    pipeline = [
        {"$match": {"user_id": {"$in": team_ids}, "created_at": {"$gte": cutoff}}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": {"contact": "$contact_id", "user": "$user_id"},
            "contact_id": {"$first": "$contact_id"},
            "contact_name": {"$first": "$contact_name"},
            "user_id": {"$first": "$user_id"},
            "last_signal": {"$first": "$signal_type"},
            "last_activity": {"$first": "$created_at"},
            "total_signals": {"$sum": 1},
            "is_return_visit": {"$first": "$is_return_visit"},
            "signal_types": {"$addToSet": "$signal_type"},
        }},
        {"$sort": {"last_activity": -1}},
        {"$limit": 50},
    ]
    results = await db.engagement_signals.aggregate(pipeline).to_list(50)

    # Build user name lookup
    user_docs = await db.users.find({"_id": {"$in": [ObjectId(uid) for uid in team_ids]}}, {"_id": 1, "name": 1}).to_list(200)
    user_names = {str(u["_id"]): u.get("name", "Unknown") for u in user_docs}

    hot_leads = []
    alert_leads = []
    for r in results:
        contact_id = r.get("contact_id")
        heat = r["total_signals"]
        if r.get("is_return_visit"):
            heat *= 2
        if len(r.get("signal_types", [])) > 1:
            heat *= 1.5

        last = r["last_activity"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        minutes_ago = (datetime.now(timezone.utc) - last).total_seconds() / 60

        # Get contact info for reassignment eligibility
        ownership_type = None
        phone = None
        if contact_id:
            try:
                contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"phone": 1, "ownership_type": 1})
                if contact:
                    phone = contact.get("phone")
                    ownership_type = contact.get("ownership_type")
            except Exception:
                pass

        type_info = SIGNAL_TYPES.get(r["last_signal"], {"icon": "eye", "color": "#007AFF", "label": r["last_signal"]})

        lead = {
            "contact_id": contact_id,
            "contact_name": r["contact_name"] or "Unknown",
            "user_id": r["user_id"],
            "rep_name": user_names.get(r["user_id"], "Unknown"),
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
            "can_reassign": ownership_type == "org",
        }
        hot_leads.append(lead)

        # 3+ interactions in this period = alert lead
        if r["total_signals"] >= 3:
            alert_leads.append(lead)

    hot_leads.sort(key=lambda x: (-x["heat_score"], x["minutes_ago"]))
    alert_leads.sort(key=lambda x: -x["heat_score"])

    # ── Team activity stats ──
    events_cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    team_stats = []
    for uid in team_ids:
        event_pipeline = [
            {"$match": {"user_id": uid, "created_at": {"$gte": events_cutoff}}},
            {"$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
            }},
        ]
        events = await db.contact_events.aggregate(event_pipeline).to_list(20)
        event_map = {e["_id"]: e["count"] for e in events}

        signal_count = await db.engagement_signals.count_documents({"user_id": uid, "created_at": {"$gte": cutoff}})

        team_stats.append({
            "user_id": uid,
            "name": user_names.get(uid, "Unknown"),
            "calls": event_map.get("call_placed", 0),
            "texts": event_map.get("sms_sent", 0) + event_map.get("sms_personal", 0),
            "emails": event_map.get("email_sent", 0),
            "cards": event_map.get("card_shared", 0) + event_map.get("card_sent", 0) + event_map.get("digital_card_shared", 0),
            "engagement_signals": signal_count,
            "total_activity": sum(event_map.values()),
        })
    team_stats.sort(key=lambda x: -x["total_activity"])

    return {
        "hot_leads": hot_leads,
        "team_stats": team_stats,
        "alert_leads": alert_leads,
        "total": len(hot_leads),
        "period_hours": hours,
    }


@router.post("/reassign-lead")
async def reassign_lead(
    body: dict,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Reassign an org-owned lead to a different user.
    Only works for contacts with ownership_type == 'org'.
    """
    db = get_db()
    contact_id = body.get("contact_id")
    new_user_id = body.get("new_user_id")

    if not contact_id or not new_user_id:
        raise HTTPException(status_code=400, detail="contact_id and new_user_id are required")

    # Verify requester is a manager
    requester = await db.users.find_one({"_id": ObjectId(x_user_id)}, {"role": 1, "name": 1})
    if not requester or requester.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only managers can reassign leads")

    # Verify contact exists and is org-owned
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"ownership_type": 1, "user_id": 1, "first_name": 1, "last_name": 1})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if contact.get("ownership_type") != "org":
        raise HTTPException(status_code=403, detail="Only organization-created leads can be reassigned")

    old_user_id = contact.get("user_id")

    # Verify target user exists
    target_user = await db.users.find_one({"_id": ObjectId(new_user_id)}, {"name": 1})
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Reassign
    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"user_id": new_user_id, "updated_at": datetime.now(timezone.utc)}},
    )

    contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Unknown"

    # Log the reassignment as a contact event
    await db.contact_events.insert_one({
        "event_type": "lead_reassigned",
        "contact_id": contact_id,
        "user_id": new_user_id,
        "org_id": requester.get("organization_id"),
        "content": f"Lead reassigned from {old_user_id} to {target_user.get('name', new_user_id)} by {requester.get('name', x_user_id)}",
        "metadata": {
            "previous_user_id": old_user_id,
            "reassigned_by": x_user_id,
            "reassigned_by_name": requester.get("name", ""),
        },
        "channel": "system",
        "created_at": datetime.now(timezone.utc),
    })

    logger.info(f"Lead {contact_name} ({contact_id}) reassigned to {target_user.get('name')} by {requester.get('name')}")

    return {
        "message": f"Lead reassigned to {target_user.get('name', 'user')}",
        "contact_id": contact_id,
        "new_user_id": new_user_id,
        "new_user_name": target_user.get("name", ""),
    }
