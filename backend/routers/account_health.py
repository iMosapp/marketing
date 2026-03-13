"""
Account Health API — Aggregates user/org metrics for retention dashboards.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from routers.database import get_db

router = APIRouter(prefix="/account-health", tags=["Account Health"])
logger = logging.getLogger(__name__)


def _health_score(metrics: dict) -> dict:
    """Calculate overall health score from metrics. Returns score (0-100), grade, color."""
    score = 0
    # Activity (40 points max)
    days_since_login = metrics.get("days_since_login", 999)
    if days_since_login <= 1:
        score += 40
    elif days_since_login <= 3:
        score += 30
    elif days_since_login <= 7:
        score += 20
    elif days_since_login <= 14:
        score += 10
    elif days_since_login <= 30:
        score += 5

    # Contacts (20 points max)
    contacts = metrics.get("total_contacts", 0)
    if contacts >= 50:
        score += 20
    elif contacts >= 20:
        score += 15
    elif contacts >= 5:
        score += 10
    elif contacts >= 1:
        score += 5

    # Messages (20 points max)
    msgs_30d = metrics.get("messages_30d", 0)
    if msgs_30d >= 50:
        score += 20
    elif msgs_30d >= 20:
        score += 15
    elif msgs_30d >= 5:
        score += 10
    elif msgs_30d >= 1:
        score += 5

    # Campaigns & Touchpoints (20 points max)
    campaigns = metrics.get("active_campaigns", 0)
    touchpoints = metrics.get("touchpoints_30d", 0)
    if campaigns >= 3 and touchpoints >= 10:
        score += 20
    elif campaigns >= 1 and touchpoints >= 5:
        score += 15
    elif campaigns >= 1 or touchpoints >= 3:
        score += 10
    elif touchpoints >= 1:
        score += 5

    if score >= 70:
        return {"score": score, "grade": "Healthy", "color": "#34C759"}
    elif score >= 40:
        return {"score": score, "grade": "At Risk", "color": "#FF9500"}
    else:
        return {"score": score, "grade": "Critical", "color": "#FF3B30"}


async def _get_user_metrics(db, user_id: str, days: int = 30) -> dict:
    """Aggregate all metrics for a single user."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    uid = user_id

    # Contacts
    total_contacts = await db.contacts.count_documents({"user_id": uid})
    new_contacts = await db.contacts.count_documents({"user_id": uid, "created_at": {"$gte": cutoff}})

    # Messages
    total_messages = await db.messages.count_documents({"user_id": uid})
    messages_period = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})

    # Tasks
    total_tasks = await db.tasks.count_documents({"user_id": uid})
    completed_tasks = await db.tasks.count_documents({"user_id": uid, "completed": True})

    # Campaigns
    active_campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})
    total_campaigns = await db.campaigns.count_documents({"user_id": uid})
    enrollments = await db.campaign_enrollments.count_documents({"user_id": uid})
    enrollments_period = await db.campaign_enrollments.count_documents({"user_id": uid, "enrolled_at": {"$gte": cutoff}})

    # Contact events (touchpoints)
    total_events = await db.contact_events.count_documents({"user_id": uid})
    events_period = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})

    # Event breakdown
    event_pipeline = [
        {"$match": {"user_id": uid, "timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
    ]
    event_breakdown = {}
    async for doc in db.contact_events.aggregate(event_pipeline):
        event_breakdown[doc["_id"]] = doc["count"]

    # Short URL clicks
    short_urls = await db.short_urls.count_documents({"user_id": uid})
    link_clicks = await db.short_url_clicks.count_documents({"clicked_at": {"$gte": cutoff}})

    # Congrats cards
    cards_shared = await db.congrats_cards.count_documents({"user_id": uid})

    # User info
    user = await db.users.find_one({"_id": ObjectId(uid)}, {"password": 0, "_id": 0})
    last_login = user.get("last_login") if user else None
    days_since_login = (datetime.utcnow() - last_login).days if last_login else 999

    return {
        "total_contacts": total_contacts,
        "new_contacts": new_contacts,
        "total_messages": total_messages,
        "messages_30d": messages_period,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "active_campaigns": active_campaigns,
        "total_campaigns": total_campaigns,
        "enrollments": enrollments,
        "enrollments_30d": enrollments_period,
        "total_touchpoints": total_events,
        "touchpoints_30d": events_period,
        "event_breakdown": event_breakdown,
        "short_urls_created": short_urls,
        "link_clicks_30d": link_clicks,
        "cards_shared": cards_shared,
        "days_since_login": days_since_login,
        "last_login": last_login.isoformat() if last_login else None,
    }


@router.get("/overview")
async def get_accounts_overview(period: int = 30):
    """List all user accounts with health scores for the dashboard."""
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=period)

    users = await db.users.find(
        {"role": {"$nin": ["super_admin"]}, "is_active": {"$ne": False}},
        {"password": 0}
    ).sort("last_login", -1).limit(500).to_list(500)

    accounts = []
    for u in users:
        uid = str(u["_id"])
        # Fast counts (no full aggregation for overview)
        contacts = await db.contacts.count_documents({"user_id": uid})
        messages = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        events = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})

        last_login = u.get("last_login")
        days_since = (datetime.utcnow() - last_login).days if last_login else 999

        health = _health_score({
            "days_since_login": days_since,
            "total_contacts": contacts,
            "messages_30d": messages,
            "active_campaigns": campaigns,
            "touchpoints_30d": events,
        })

        # Get org/store names
        org_name = ""
        store_name = ""
        if u.get("organization_id"):
            try:
                org = await db.organizations.find_one({"_id": ObjectId(u["organization_id"])}, {"name": 1})
                org_name = org.get("name", "") if org else ""
            except:
                pass
        if u.get("store_id"):
            try:
                store = await db.stores.find_one({"_id": ObjectId(u["store_id"])}, {"name": 1})
                store_name = store.get("name", "") if store else ""
            except:
                pass

        accounts.append({
            "user_id": uid,
            "name": u.get("name", u.get("email", "")),
            "email": u.get("email", ""),
            "role": u.get("role", "user"),
            "organization": org_name,
            "store": store_name,
            "photo_url": u.get("photo_url", ""),
            "contacts": contacts,
            "messages_30d": messages,
            "touchpoints_30d": events,
            "active_campaigns": campaigns,
            "days_since_login": days_since,
            "last_login": last_login.isoformat() if isinstance(last_login, datetime) else str(last_login or ""),
            "health": health,
            "created_at": u.get("created_at").isoformat() if isinstance(u.get("created_at"), datetime) else str(u.get("created_at", "")),
            "tos_accepted": u.get("tos_accepted", False),
        })

    # Sort by health score ascending (worst first)
    accounts.sort(key=lambda x: x["health"]["score"])
    return accounts


@router.get("/user/{user_id}")
async def get_user_health(user_id: str, period: int = 30):
    """Detailed health report for a single user."""
    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(404, "User not found")

    metrics = await _get_user_metrics(db, user_id, period)
    health = _health_score(metrics)

    # Get org/store info
    org_name = ""
    store_name = ""
    if user.get("organization_id"):
        try:
            org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])}, {"name": 1})
            org_name = org.get("name", "") if org else ""
        except:
            pass
    if user.get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(user["store_id"])}, {"name": 1})
            store_name = store.get("name", "") if store else ""
        except:
            pass

    # Recent activity timeline (last 10 events)
    recent_events = []
    async for ev in db.contact_events.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("timestamp", -1).limit(10):
        if "timestamp" in ev and ev["timestamp"]:
            ev["timestamp"] = ev["timestamp"].isoformat()
        recent_events.append(ev)

    user_id_str = str(user["_id"])
    del user["_id"]

    return {
        "user": {**user, "id": user_id_str, "created_at": user.get("created_at").isoformat() if isinstance(user.get("created_at"), datetime) else str(user.get("created_at", "")), "last_login": user.get("last_login").isoformat() if isinstance(user.get("last_login"), datetime) else str(user.get("last_login", ""))},
        "organization": org_name,
        "store": store_name,
        "metrics": metrics,
        "health": health,
        "recent_events": recent_events,
        "period_days": period,
    }


@router.get("/org/{org_id}")
async def get_org_health(org_id: str, period: int = 30):
    """Aggregate health report for an entire organization."""
    db = get_db()

    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(404, "Organization not found")

    # Get all users in this org
    users = await db.users.find(
        {"organization_id": org_id, "is_active": {"$ne": False}},
        {"password": 0}
    ).to_list(500)

    user_reports = []
    agg = {"contacts": 0, "messages_30d": 0, "touchpoints_30d": 0, "active_campaigns": 0, "total_users": len(users), "active_users_7d": 0}

    cutoff = datetime.utcnow() - timedelta(days=period)
    for u in users:
        uid = str(u["_id"])
        contacts = await db.contacts.count_documents({"user_id": uid})
        messages = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        events = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})

        last_login = u.get("last_login")
        days_since = (datetime.utcnow() - last_login).days if last_login else 999
        if days_since <= 7:
            agg["active_users_7d"] += 1

        health = _health_score({"days_since_login": days_since, "total_contacts": contacts, "messages_30d": messages, "active_campaigns": campaigns, "touchpoints_30d": events})

        agg["contacts"] += contacts
        agg["messages_30d"] += messages
        agg["touchpoints_30d"] += events
        agg["active_campaigns"] += campaigns

        user_reports.append({
            "user_id": uid,
            "name": u.get("name", u.get("email", "")),
            "role": u.get("role", ""),
            "contacts": contacts,
            "messages_30d": messages,
            "touchpoints_30d": events,
            "days_since_login": days_since,
            "health": health,
        })

    # Org-level health
    avg_score = sum(r["health"]["score"] for r in user_reports) / len(user_reports) if user_reports else 0
    if avg_score >= 70:
        org_health = {"score": round(avg_score), "grade": "Healthy", "color": "#34C759"}
    elif avg_score >= 40:
        org_health = {"score": round(avg_score), "grade": "At Risk", "color": "#FF9500"}
    else:
        org_health = {"score": round(avg_score), "grade": "Critical", "color": "#FF3B30"}

    org_id_str = str(org["_id"])
    del org["_id"]

    return {
        "organization": {**org, "id": org_id_str},
        "health": org_health,
        "aggregate": agg,
        "users": sorted(user_reports, key=lambda x: x["health"]["score"]),
        "period_days": period,
    }
