"""
Internal User Lifecycle & Auto-Tagging System
Tags users based on tenure, role changes, activity, and status.
Sends automated messages from iMOs for milestones and retention.
"Eat our own dog food" — use iMOs to manage iMOs users.
"""
from fastapi import APIRouter, Header
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
import logging

from .database import get_db

router = APIRouter(prefix="/lifecycle", tags=["User Lifecycle"])
logger = logging.getLogger(__name__)

# ============= TAG DEFINITIONS =============

# Tenure tags — applied based on user created_at
TENURE_MILESTONES = [
    (30, "tenure_30_days", "30 Days with iMOs!"),
    (90, "tenure_90_days", "90 Days with iMOs!"),
    (180, "tenure_6_months", "6 Months with iMOs!"),
    (365, "tenure_1_year", "1 Year Anniversary with iMOs!"),
    (730, "tenure_2_years", "2 Year Anniversary with iMOs!"),
    (1095, "tenure_3_years", "3 Year Anniversary with iMOs!"),
]

# Role tags — applied on role changes
ROLE_TAGS = {
    "user": "role_user",
    "store_manager": "role_manager",
    "org_admin": "role_admin",
    "super_admin": "role_super_admin",
}

# Activity tags — applied based on usage patterns
ACTIVITY_THRESHOLDS = {
    "power_user": {"messages_sent": 100, "contacts_added": 50},
    "active_user": {"messages_sent": 20, "contacts_added": 10},
    "getting_started": {"messages_sent": 1, "contacts_added": 1},
}

# Status tags
STATUS_TAGS = {
    "active": "status_active",
    "deactivated": "status_deactivated",
    "suspended": "status_suspended",
}

# Inactivity thresholds
INACTIVE_DAYS = 30  # No login in 30 days = at_risk
DORMANT_DAYS = 60   # No login in 60 days = dormant


# ============= AUTO-TAG ENGINE =============

async def apply_user_tag(user_id: str, tag: str, reason: str = None):
    """Add a tag to a user's internal tags list"""
    db = get_db()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$addToSet": {"internal_tags": tag},
            "$push": {"tag_history": {
                "tag": tag,
                "action": "added",
                "reason": reason or "auto",
                "timestamp": datetime.utcnow(),
            }}
        }
    )

async def remove_user_tag(user_id: str, tag: str, reason: str = None):
    """Remove a tag from a user"""
    db = get_db()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$pull": {"internal_tags": tag},
            "$push": {"tag_history": {
                "tag": tag,
                "action": "removed",
                "reason": reason or "auto",
                "timestamp": datetime.utcnow(),
            }}
        }
    )

async def log_lifecycle_event(user_id: str, event_type: str, description: str, metadata: dict = None):
    """Log a lifecycle event for a user"""
    db = get_db()
    await db.user_lifecycle_events.insert_one({
        "user_id": user_id,
        "event_type": event_type,
        "description": description,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow(),
    })


# ============= LIFECYCLE HOOKS =============
# Call these from other routers when events happen

async def on_user_created(user_id: str, user_data: dict):
    """Called when a new user is created"""
    role = user_data.get("role", "user")
    role_tag = ROLE_TAGS.get(role, "role_user")
    
    await apply_user_tag(user_id, "status_active", "account created")
    await apply_user_tag(user_id, role_tag, "initial role assignment")
    await apply_user_tag(user_id, "getting_started", "new user")
    await log_lifecycle_event(user_id, "user_created", f"Welcome! Account created as {role}")

async def on_role_change(user_id: str, old_role: str, new_role: str, changed_by: str = None):
    """Called when a user's role changes (promotion/demotion)"""
    db = get_db()
    
    # Remove old role tag, add new one
    old_tag = ROLE_TAGS.get(old_role)
    new_tag = ROLE_TAGS.get(new_role)
    
    if old_tag:
        await remove_user_tag(user_id, old_tag, f"role changed from {old_role}")
    if new_tag:
        await apply_user_tag(user_id, new_tag, f"role changed to {new_role}")
    
    # Track promotion/demotion
    role_levels = {"user": 1, "store_manager": 2, "org_admin": 3, "super_admin": 4}
    old_level = role_levels.get(old_role, 0)
    new_level = role_levels.get(new_role, 0)
    
    if new_level > old_level:
        promo_tag = f"promoted_to_{new_role}"
        await apply_user_tag(user_id, promo_tag, f"promoted from {old_role}")
        await apply_user_tag(user_id, "promoted", "role promotion")
        
        # Store promotion date for anniversary tracking
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {f"promotion_dates.{new_role}": datetime.utcnow()}}
        )
        
        await log_lifecycle_event(user_id, "promotion", f"Promoted from {old_role} to {new_role}", {
            "old_role": old_role, "new_role": new_role, "changed_by": changed_by
        })
    elif new_level < old_level:
        await log_lifecycle_event(user_id, "role_change", f"Role changed from {old_role} to {new_role}", {
            "old_role": old_role, "new_role": new_role, "changed_by": changed_by
        })

async def on_user_deactivated(user_id: str, deactivated_by: str = None):
    """Called when a user is deactivated"""
    await remove_user_tag(user_id, "status_active", "deactivated")
    await apply_user_tag(user_id, "status_deactivated", f"deactivated by {deactivated_by or 'system'}")
    await apply_user_tag(user_id, "churned", "user deactivated")
    await log_lifecycle_event(user_id, "deactivated", "Account deactivated", {"deactivated_by": deactivated_by})

async def on_user_reactivated(user_id: str, reactivated_by: str = None):
    """Called when a user is reactivated"""
    await remove_user_tag(user_id, "status_deactivated", "reactivated")
    await remove_user_tag(user_id, "churned", "reactivated")
    await remove_user_tag(user_id, "at_risk", "reactivated")
    await remove_user_tag(user_id, "dormant", "reactivated")
    await apply_user_tag(user_id, "status_active", "account reactivated")
    await apply_user_tag(user_id, "win_back", "returned after deactivation")
    await log_lifecycle_event(user_id, "reactivated", "Welcome back! Account reactivated", {"reactivated_by": reactivated_by})

async def on_user_login(user_id: str):
    """Called on each user login — updates activity tags"""
    db = get_db()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    # Remove inactivity tags on login
    await remove_user_tag(user_id, "at_risk", "user logged in")
    await remove_user_tag(user_id, "dormant", "user logged in")


# ============= SCHEDULED SCAN ENDPOINT =============
# Run this daily via cron or scheduler to process all users

@router.post("/scan")
async def run_lifecycle_scan(x_user_id: str = Header(None, alias="X-User-ID")):
    """
    Daily scan: process all users for tenure milestones, inactivity,
    activity levels, and queue milestone messages.
    """
    db = get_db()
    now = datetime.utcnow()
    
    results = {
        "tenure_tags_applied": 0,
        "inactivity_tags_applied": 0,
        "activity_tags_applied": 0,
        "milestone_messages_queued": 0,
        "users_processed": 0,
    }
    
    users = await db.users.find({"status": {"$ne": "deleted"}}).to_list(10000)
    
    for user in users:
        uid = str(user["_id"])
        internal_tags = set(user.get("internal_tags", []))
        created_at = user.get("created_at", now)
        days_since_created = (now - created_at).days
        last_login = user.get("last_login")
        
        # --- TENURE MILESTONES ---
        for days, tag, message in TENURE_MILESTONES:
            if days_since_created >= days and tag not in internal_tags:
                await apply_user_tag(uid, tag, f"{days}-day tenure milestone")
                await log_lifecycle_event(uid, "tenure_milestone", message, {"days": days})
                
                # Queue a milestone message
                await db.lifecycle_messages.insert_one({
                    "user_id": uid,
                    "type": "tenure_milestone",
                    "tag": tag,
                    "message": message,
                    "follow_up": "What can we do to make your experience better?",
                    "status": "queued",
                    "created_at": now,
                })
                results["tenure_tags_applied"] += 1
                results["milestone_messages_queued"] += 1
        
        # --- PROMOTION ANNIVERSARIES ---
        promotion_dates = user.get("promotion_dates", {})
        for role, promo_date in promotion_dates.items():
            if isinstance(promo_date, datetime):
                days_since = (now - promo_date).days
                for year in [1, 2, 3, 5]:
                    anniversary_tag = f"promo_anniversary_{role}_{year}yr"
                    if days_since >= (year * 365) and anniversary_tag not in internal_tags:
                        await apply_user_tag(uid, anniversary_tag, f"{year}-year promotion anniversary for {role}")
                        await db.lifecycle_messages.insert_one({
                            "user_id": uid,
                            "type": "promotion_anniversary",
                            "tag": anniversary_tag,
                            "message": f"Congrats on {year} year{'s' if year > 1 else ''} as {role}!",
                            "follow_up": "Your leadership makes a difference.",
                            "status": "queued",
                            "created_at": now,
                        })
                        results["milestone_messages_queued"] += 1
        
        # --- INACTIVITY DETECTION ---
        if user.get("status") == "active" and last_login:
            days_inactive = (now - last_login).days
            
            if days_inactive >= DORMANT_DAYS and "dormant" not in internal_tags:
                await apply_user_tag(uid, "dormant", f"no login for {days_inactive} days")
                await log_lifecycle_event(uid, "inactivity", f"Dormant — {days_inactive} days without login")
                await db.lifecycle_messages.insert_one({
                    "user_id": uid,
                    "type": "inactivity_warning",
                    "tag": "dormant",
                    "message": "We miss you! Your contacts and campaigns are waiting.",
                    "follow_up": "Need help getting back on track? Reply and we'll set up a quick call.",
                    "status": "queued",
                    "created_at": now,
                })
                results["inactivity_tags_applied"] += 1
                results["milestone_messages_queued"] += 1
                
            elif days_inactive >= INACTIVE_DAYS and "at_risk" not in internal_tags:
                await apply_user_tag(uid, "at_risk", f"no login for {days_inactive} days")
                await log_lifecycle_event(uid, "inactivity", f"At risk — {days_inactive} days without login")
                results["inactivity_tags_applied"] += 1
        
        # --- ACTIVITY LEVEL TAGS ---
        stats = user.get("stats", {})
        msgs = stats.get("messages_sent", 0)
        contacts = stats.get("contacts_added", 0)
        
        if msgs >= ACTIVITY_THRESHOLDS["power_user"]["messages_sent"] and "power_user" not in internal_tags:
            await apply_user_tag(uid, "power_user", f"high activity: {msgs} messages, {contacts} contacts")
            results["activity_tags_applied"] += 1
        elif msgs >= ACTIVITY_THRESHOLDS["active_user"]["messages_sent"] and "active_user" not in internal_tags:
            await apply_user_tag(uid, "active_user", f"regular activity: {msgs} messages")
            results["activity_tags_applied"] += 1
        
        results["users_processed"] += 1
    
    logger.info(f"Lifecycle scan complete: {results}")
    return results


# ============= QUERY ENDPOINTS =============

@router.get("/users/by-tag/{tag}")
async def get_users_by_tag(tag: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get all users with a specific internal tag"""
    db = get_db()
    users = await db.users.find(
        {"internal_tags": tag},
        {"password": 0, "photo": 0}
    ).to_list(1000)
    for u in users:
        u["_id"] = str(u["_id"])
    return {"tag": tag, "count": len(users), "users": users}

@router.get("/users/{user_id}/tags")
async def get_user_tags(user_id: str):
    """Get all internal tags and tag history for a user"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"internal_tags": 1, "tag_history": 1, "promotion_dates": 1})
    if not user:
        return {"tags": [], "history": []}
    return {
        "tags": user.get("internal_tags", []),
        "history": [{**h, "timestamp": h["timestamp"].isoformat()} for h in user.get("tag_history", [])[-50:]],
        "promotion_dates": {k: v.isoformat() for k, v in user.get("promotion_dates", {}).items() if isinstance(v, datetime)},
    }

@router.get("/users/{user_id}/events")
async def get_user_lifecycle_events(user_id: str, limit: int = 50):
    """Get lifecycle events for a user"""
    db = get_db()
    events = await db.user_lifecycle_events.find({"user_id": user_id}).sort("timestamp", -1).limit(limit).to_list(limit)
    for e in events:
        e["_id"] = str(e["_id"])
        e["timestamp"] = e["timestamp"].isoformat()
    return {"events": events}

@router.get("/messages/queued")
async def get_queued_messages(limit: int = 100):
    """Get queued lifecycle messages ready to send"""
    db = get_db()
    messages = await db.lifecycle_messages.find({"status": "queued"}).sort("created_at", -1).limit(limit).to_list(limit)
    for m in messages:
        m["_id"] = str(m["_id"])
        m["created_at"] = m["created_at"].isoformat()
    return {"messages": messages, "count": len(messages)}

@router.post("/messages/{message_id}/sent")
async def mark_message_sent(message_id: str):
    """Mark a lifecycle message as sent"""
    db = get_db()
    await db.lifecycle_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"status": "sent", "sent_at": datetime.utcnow()}}
    )
    return {"message": "Marked as sent"}

@router.get("/dashboard")
async def lifecycle_dashboard(x_user_id: str = Header(None, alias="X-User-ID")):
    """Overview dashboard of user lifecycle metrics"""
    db = get_db()
    
    total = await db.users.count_documents({})
    active = await db.users.count_documents({"status": "active"})
    deactivated = await db.users.count_documents({"status": "deactivated"})
    at_risk = await db.users.count_documents({"internal_tags": "at_risk"})
    dormant = await db.users.count_documents({"internal_tags": "dormant"})
    power_users = await db.users.count_documents({"internal_tags": "power_user"})
    churned = await db.users.count_documents({"internal_tags": "churned"})
    win_backs = await db.users.count_documents({"internal_tags": "win_back"})
    queued_msgs = await db.lifecycle_messages.count_documents({"status": "queued"})
    
    return {
        "total_users": total,
        "active": active,
        "deactivated": deactivated,
        "at_risk": at_risk,
        "dormant": dormant,
        "power_users": power_users,
        "churned": churned,
        "win_backs": win_backs,
        "queued_messages": queued_msgs,
    }
