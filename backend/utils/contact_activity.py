"""
Utility to log customer-initiated activity to their contact's activity feed.
Used by public-facing endpoints (congrats card views, review submissions, link clicks)
to create contact_events that appear in the salesperson's contact detail page.
"""
import re
import logging
from datetime import datetime, timezone
from bson import ObjectId
from routers.database import get_db

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits


async def find_contact_by_phone_or_name(user_id: str, phone: str = None, name: str = None):
    """Find a contact belonging to a salesperson by phone (last 10 digits) or name."""
    db = get_db()
    contact = None

    if phone:
        norm = normalize_phone(phone)
        if norm:
            contact = await db.contacts.find_one({
                "user_id": user_id,
                "phone": {"$regex": norm},
                "status": {"$ne": "deleted"},
            })

    if not contact and name:
        parts = name.strip().split()
        if len(parts) >= 2:
            contact = await db.contacts.find_one({
                "user_id": user_id,
                "first_name": {"$regex": f"^{re.escape(parts[0])}$", "$options": "i"},
                "last_name": {"$regex": f"^{re.escape(parts[1])}$", "$options": "i"},
                "status": {"$ne": "deleted"},
            })
        elif parts:
            contact = await db.contacts.find_one({
                "user_id": user_id,
                "first_name": {"$regex": f"^{re.escape(parts[0])}$", "$options": "i"},
                "status": {"$ne": "deleted"},
            })

    return contact


async def log_customer_activity(
    user_id: str,
    contact_id: str,
    event_type: str,
    title: str,
    description: str = "",
    icon: str = "flag",
    color: str = "#007AFF",
    category: str = "customer_activity",
    metadata: dict = None,
):
    """Log a customer-initiated event to the contact_events collection."""
    # Validate contact_id is a valid ObjectId before storing
    if contact_id:
        try:
            ObjectId(contact_id)
        except Exception:
            logger.warning(f"[CustomerActivity] Invalid contact_id '{contact_id}' — skipping event {event_type}")
            return None
    db = get_db()

    event = {
        "contact_id": contact_id,
        "user_id": user_id,
        "event_type": event_type,
        "icon": icon,
        "color": color,
        "title": title,
        "description": description,
        "category": category,
        "timestamp": datetime.now(timezone.utc),
    }
    if metadata:
        event["metadata"] = metadata

    await db.contact_events.insert_one(event)
    event.pop("_id", None)
    logger.info(f"[CustomerActivity] Logged {event_type} for contact {contact_id} (user {user_id})")
    return event


async def log_activity_for_customer(
    user_id: str,
    customer_phone: str = None,
    customer_name: str = None,
    event_type: str = "custom",
    title: str = "Customer Activity",
    description: str = "",
    icon: str = "flag",
    color: str = "#007AFF",
    category: str = "customer_activity",
    metadata: dict = None,
):
    """
    Find a contact by phone/name under a salesperson, then log the event.
    Returns the logged event or None if contact wasn't found.
    """
    contact = await find_contact_by_phone_or_name(user_id, customer_phone, customer_name)
    if not contact:
        return None

    return await log_customer_activity(
        user_id=user_id,
        contact_id=str(contact["_id"]),
        event_type=event_type,
        title=title,
        description=description,
        icon=icon,
        color=color,
        category=category,
        metadata=metadata,
    )


# ── NEW: centralized event logger that also bumps last_activity_at ──────────

async def log_contact_event(db, contact_id: str, event: dict) -> str:
    """
    Insert a contact event AND bump last_activity_at on the contact.
    Powers the 'sort by recent' O(log n) indexed query.
    """
    event.setdefault("contact_id", contact_id)
    event.setdefault("timestamp", datetime.now(timezone.utc))

    result = await db.contact_events.insert_one(event)

    try:
        if contact_id and len(str(contact_id)) == 24:
            await db.contacts.update_one(
                {"_id": ObjectId(contact_id)},
                {"$set": {"last_activity_at": event["timestamp"]}},
            )
    except Exception as e:
        logger.debug(f"last_activity_at bump failed for {contact_id}: {e}")

    return str(result.inserted_id)


async def backfill_last_activity_at(db) -> dict:
    """
    One-time backfill: set last_activity_at on contacts from contact_events.
    Call POST /admin/backfill-last-activity once after deploying.
    """
    pipeline = [
        {"$group": {"_id": "$contact_id", "last": {"$max": "$timestamp"}}},
    ]
    results = await db.contact_events.aggregate(pipeline).to_list(50000)

    updated = 0
    for r in results:
        cid = r["_id"]
        if not cid or len(cid) != 24:
            continue
        try:
            res = await db.contacts.update_one(
                {"_id": ObjectId(cid), "last_activity_at": {"$exists": False}},
                {"$set": {"last_activity_at": r["last"]}},
            )
            updated += res.modified_count
        except Exception:
            pass

    return {"backfilled": updated, "total_contacts_with_events": len(results)}
