"""
Broadcast Router - One-time mass messaging system
Allows sending messages to filtered contact lists with scheduling, staggering, and Jessi AI replies
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging
import os

from routers.database import get_db

router = APIRouter(prefix="/broadcast", tags=["broadcast"])
logger = logging.getLogger(__name__)


# Pydantic Models
class BroadcastFilter(BaseModel):
    tags: Optional[List[str]] = []
    exclude_tags: Optional[List[str]] = []
    purchase_month: Optional[int] = None
    purchase_year: Optional[int] = None
    days_since_purchase: Optional[int] = None
    days_since_contact: Optional[int] = None
    custom_date_start: Optional[str] = None
    custom_date_end: Optional[str] = None
    contact_ids: Optional[List[str]] = []
    sold_months_min: Optional[int] = None   # lower bound: sold at least N months ago
    sold_months_max: Optional[int] = None   # upper bound: sold at most N months ago
    purchase_title_contains: Optional[str] = None  # search purchase_history[].title
    purchase_category: Optional[str] = None         # vehicle / real_estate / insurance / other
    purchase_history_year: Optional[int] = None     # year within purchase_history[].date


class BroadcastCreate(BaseModel):
    name: str
    message: str
    filters: BroadcastFilter
    scheduled_at: Optional[str] = None
    media_urls: Optional[List[str]] = []
    jessi_replies: Optional[bool] = False   # Enable Jessi AI for all replies
    stagger_seconds: Optional[int] = 10    # Seconds between each send (A2P safety)


class BroadcastUpdate(BaseModel):
    name: Optional[str] = None
    message: Optional[str] = None
    filters: Optional[BroadcastFilter] = None
    scheduled_at: Optional[str] = None
    media_urls: Optional[List[str]] = None
    jessi_replies: Optional[bool] = None


def serialize_broadcast(broadcast: dict) -> dict:
    if not broadcast:
        return None
    return {
        "id": str(broadcast["_id"]),
        "name": broadcast.get("name", ""),
        "message": broadcast.get("message", ""),
        "filters": broadcast.get("filters", {}),
        "media_urls": broadcast.get("media_urls", []),
        "status": broadcast.get("status", "draft"),
        "scheduled_at": broadcast.get("scheduled_at"),
        "sent_at": broadcast.get("sent_at"),
        "created_at": broadcast.get("created_at"),
        "updated_at": broadcast.get("updated_at"),
        "created_by": broadcast.get("created_by"),
        "recipient_count": broadcast.get("recipient_count", 0),
        "sent_count": broadcast.get("sent_count", 0),
        "failed_count": broadcast.get("failed_count", 0),
        "delivered_count": broadcast.get("delivered_count", 0),
        "undelivered_count": broadcast.get("undelivered_count", 0),
        "jessi_replies": broadcast.get("jessi_replies", False),
        "recipients": broadcast.get("recipients", []),
    }


async def get_filtered_contacts(filters: dict, user_id: str) -> List[dict]:
    """Get contacts matching the filter criteria. Uses user_id (not owner_id).
    Hand-picked contact_ids are UNIONED with other filters (or used alone if no other filters)."""
    db = get_db()
    query: dict = {"user_id": user_id}

    picked_ids = filters.get("contact_ids") or []
    other_filter_keys = (
        "tags", "exclude_tags", "purchase_month", "purchase_year", "days_since_purchase",
        "days_since_contact", "custom_date_start", "custom_date_end",
        "purchase_title_contains", "purchase_category", "purchase_history_year",
    )
    has_other_filters = any(filters.get(k) for k in other_filter_keys)

    # Tag include/exclude
    if filters.get("tags"):
        query["tags"] = {"$in": filters["tags"]}
    if filters.get("exclude_tags"):
        if "tags" in query:
            query["tags"]["$nin"] = filters["exclude_tags"]
        else:
            query["tags"] = {"$nin": filters["exclude_tags"]}

    # Specific contact IDs — if ONLY ids picked (no other filters), restrict to them here;
    # if combined with other filters, they are unioned in after the main query below.
    picked_oids = []
    if picked_ids:
        for cid in picked_ids:
            try:
                picked_oids.append(ObjectId(cid))
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid contact id: {cid}")
    if picked_oids and not has_other_filters:
        query["_id"] = {"$in": picked_oids}

    # Purchase date filters
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if filters.get("days_since_purchase"):
        cutoff = now - timedelta(days=filters["days_since_purchase"])
        query["date_sold"] = {"$lte": cutoff}
    elif filters.get("purchase_year"):
        yr = filters["purchase_year"]
        date_q: dict = {
            "$gte": datetime(yr, 1, 1),
            "$lt": datetime(yr + 1, 1, 1),
        }
        if filters.get("purchase_month"):
            m = filters["purchase_month"]
            import calendar
            _, last_day = calendar.monthrange(yr, m)
            date_q = {"$gte": datetime(yr, m, 1), "$lte": datetime(yr, m, last_day)}
        query["date_sold"] = date_q

    # Days since last contact
    if filters.get("days_since_contact"):
        cutoff = now - timedelta(days=filters["days_since_contact"])
        query["last_activity_at"] = {"$lte": cutoff}

    # Custom date range on date_sold
    if filters.get("custom_date_start") or filters.get("custom_date_end"):
        date_q = {}
        if filters.get("custom_date_start"):
            date_q["$gte"] = datetime.fromisoformat(filters["custom_date_start"].replace("Z", "+00:00")).replace(tzinfo=None)
        if filters.get("custom_date_end"):
            date_q["$lte"] = datetime.fromisoformat(filters["custom_date_end"].replace("Z", "+00:00")).replace(tzinfo=None)
        query["date_sold"] = date_q

    # Purchase history filters — search across purchase_history[] array
    if filters.get("purchase_title_contains"):
        import re as _re
        pattern = _re.escape(filters["purchase_title_contains"].strip())
        query["$or"] = query.get("$or", []) + [
            {"purchase_history": {"$elemMatch": {"title": {"$regex": pattern, "$options": "i"}}}},
            {"vehicle": {"$regex": pattern, "$options": "i"}},  # legacy fallback
        ]

    if filters.get("purchase_category"):
        query["purchase_history"] = {
            "$elemMatch": {
                **query.get("purchase_history", {}).get("$elemMatch", {}),
                "category": filters["purchase_category"],
            }
        }

    if filters.get("purchase_history_year"):
        yr = str(filters["purchase_history_year"])
        query["$or"] = query.get("$or", []) + [
            {"purchase_history": {"$elemMatch": {"date": {"$regex": f"^{yr}"}}}},
        ]

    # Exclude hidden/deleted
    query["status"] = {"$nin": ["hidden", "merged", "deleted"]}

    contacts = await db.contacts.find(
        query,
        {"_id": 1, "phone": 1, "first_name": 1, "last_name": 1, "email": 1, "tags": 1}
    ).to_list(5000)

    # Union hand-picked contacts with the filtered set
    if picked_oids and has_other_filters:
        seen = {str(c["_id"]) for c in contacts}
        extra_ids = [oid for oid in picked_oids if str(oid) not in seen]
        if extra_ids:
            extra = await db.contacts.find(
                {"_id": {"$in": extra_ids}, "user_id": user_id, "status": {"$nin": ["hidden", "merged", "deleted"]}},
                {"_id": 1, "phone": 1, "first_name": 1, "last_name": 1, "email": 1, "tags": 1}
            ).to_list(1000)
            contacts.extend(extra)

    # Only contacts with a phone number
    return [c for c in contacts if c.get("phone")]


@router.get("")
async def list_broadcasts(user_id: str, status: Optional[str] = None, limit: int = 50):
    """List all broadcasts for a user"""
    db = get_db()
    query = {"created_by": user_id}
    if status:
        query["status"] = status
    broadcasts = await db.broadcasts.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    return {"success": True, "broadcasts": [serialize_broadcast(b) for b in broadcasts]}


@router.get("/stats")
async def get_broadcast_stats(user_id: str):
    db = get_db()
    pipeline = [
        {"$match": {"created_by": user_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1},
                    "total_sent": {"$sum": "$sent_count"}, "total_failed": {"$sum": "$failed_count"}}}
    ]
    stats = await db.broadcasts.aggregate(pipeline).to_list(10)
    result = {"draft": 0, "scheduled": 0, "sending": 0, "sent": 0, "failed": 0,
              "total_messages_sent": 0, "total_messages_failed": 0}
    for stat in stats:
        s = stat["_id"]
        if s in result:
            result[s] = stat["count"]
        result["total_messages_sent"] += stat.get("total_sent", 0)
        result["total_messages_failed"] += stat.get("total_failed", 0)
    return {"success": True, "stats": result}


@router.get("/preview")
async def preview_broadcast_recipients(
    user_id: str,
    tags: Optional[str] = None,
    exclude_tags: Optional[str] = None,
    purchase_month: Optional[int] = None,
    purchase_year: Optional[int] = None,
    days_since_purchase: Optional[int] = None,
    days_since_contact: Optional[int] = None,
    custom_date_start: Optional[str] = None,
    custom_date_end: Optional[str] = None,
    purchase_title_contains: Optional[str] = None,
    purchase_category: Optional[str] = None,
    purchase_history_year: Optional[int] = None,
    contact_ids: Optional[str] = None,
):
    """Preview how many contacts match the filter criteria"""
    filters = {
        "tags": tags.split(",") if tags else [],
        "exclude_tags": exclude_tags.split(",") if exclude_tags else [],
        "contact_ids": contact_ids.split(",") if contact_ids else [],
        "purchase_month": purchase_month,
        "purchase_year": purchase_year,
        "days_since_purchase": days_since_purchase,
        "days_since_contact": days_since_contact,
        "custom_date_start": custom_date_start,
        "custom_date_end": custom_date_end,
        "purchase_title_contains": purchase_title_contains,
        "purchase_category": purchase_category,
        "purchase_history_year": purchase_history_year,
    }
    
    contacts = await get_filtered_contacts(filters, user_id)
    
    return {
        "success": True,
        "count": len(contacts),
        "sample": [
            {
                "id": str(c["_id"]),
                "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "phone": c.get("phone", "")
            }
            for c in contacts[:10]  # Return sample of 10
        ]
    }


@router.post("")
async def create_broadcast(data: BroadcastCreate, user_id: str):
    """Create a new broadcast"""
    db = get_db()
    contacts = await get_filtered_contacts(data.filters.dict(), user_id)
    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts with phone numbers match the selected filters")
    status = "scheduled" if data.scheduled_at else "draft"
    broadcast = {
        "name": data.name,
        "message": data.message,
        "filters": data.filters.dict(),
        "media_urls": data.media_urls or [],
        "status": status,
        "scheduled_at": data.scheduled_at,
        "jessi_replies": data.jessi_replies or False,
        "stagger_seconds": data.stagger_seconds or 10,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user_id,
        "recipient_count": len(contacts),
        "sent_count": 0,
        "failed_count": 0,
        "recipients": [str(c["_id"]) for c in contacts],
    }
    result = await db.broadcasts.insert_one(broadcast)
    broadcast["_id"] = result.inserted_id
    return {"success": True, "broadcast": serialize_broadcast(broadcast)}


@router.get("/{broadcast_id}")
async def get_broadcast(broadcast_id: str, user_id: str):
    db = get_db()
    try:
        broadcast = await db.broadcasts.find_one({"_id": ObjectId(broadcast_id), "created_by": user_id})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return {"success": True, "broadcast": serialize_broadcast(broadcast)}


@router.get("/{broadcast_id}/recipients")
async def get_broadcast_recipients(broadcast_id: str, user_id: str):
    """Per-recipient delivery results for a broadcast (sent/failed/queued + error reason)."""
    db = get_db()
    try:
        broadcast = await db.broadcasts.find_one({"_id": ObjectId(broadcast_id), "created_by": user_id}, {"_id": 1})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    docs = await db.campaign_pending_sends.find(
        {"broadcast_id": broadcast_id},
        {"contact_id": 1, "contact_name": 1, "contact_phone": 1, "status": 1,
         "error": 1, "send_at": 1, "processed_at": 1, "deferred_reason": 1,
         "delivery_status": 1, "delivery_error": 1, "delivered_at": 1}
    ).sort("send_at", 1).to_list(5000)

    status_map = {
        "sent": "sent",
        "failed": "failed",
        "pending": "queued",
        "processing": "queued",
        "pending_user_action": "unconfirmed",
    }
    recipients = []
    for d in docs:
        status = status_map.get(d.get("status", ""), "queued")
        delivery = d.get("delivery_status") or ""
        if status == "sent" and delivery == "delivered":
            status = "delivered"
        elif status == "sent" and delivery == "undelivered":
            status = "undelivered"
        recipients.append({
            "contact_id": d.get("contact_id", ""),
            "name": d.get("contact_name", "Unknown"),
            "phone": d.get("contact_phone", ""),
            "status": status,
            "error": d.get("error", "") or (d.get("delivery_error", "") if status == "undelivered" else ""),
            "deferred_reason": d.get("deferred_reason", ""),
            "send_at": d.get("send_at").isoformat() if d.get("send_at") else "",
            "processed_at": d.get("processed_at").isoformat() if d.get("processed_at") else "",
            "delivered_at": d.get("delivered_at").isoformat() if d.get("delivered_at") else "",
        })
    counts: dict = {}
    for r in recipients:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    # "3 of 4 delivered": delivered vs everything Twilio accepted (sent + delivered + undelivered)
    accepted = counts.get("sent", 0) + counts.get("delivered", 0) + counts.get("undelivered", 0)
    return {"recipients": recipients, "counts": counts, "total": len(recipients),
            "summary": {"delivered": counts.get("delivered", 0), "accepted": accepted,
                        "undelivered": counts.get("undelivered", 0), "awaiting_receipt": counts.get("sent", 0)}}


@router.put("/{broadcast_id}")
async def update_broadcast(broadcast_id: str, data: BroadcastUpdate, user_id: str):
    """Update a broadcast (only if not yet sent)"""
    try:
        broadcast = await get_db().broadcasts.find_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    
    if broadcast.get("status") in ["sending", "sent"]:
        raise HTTPException(status_code=400, detail="Cannot update a broadcast that has been sent")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.name is not None:
        update_data["name"] = data.name
    if data.message is not None:
        update_data["message"] = data.message
    if data.media_urls is not None:
        update_data["media_urls"] = data.media_urls
    if data.scheduled_at is not None:
        update_data["scheduled_at"] = data.scheduled_at
        update_data["status"] = "scheduled" if data.scheduled_at else "draft"
    
    if data.filters is not None:
        update_data["filters"] = data.filters.dict()
        # Recalculate recipients
        contacts = await get_filtered_contacts(data.filters.dict(), user_id)
        update_data["recipient_count"] = len(contacts)
        update_data["recipients"] = [str(c["_id"]) for c in contacts]
    
    await get_db().broadcasts.update_one(
        {"_id": ObjectId(broadcast_id)},
        {"$set": update_data}
    )
    
    updated = await get_db().broadcasts.find_one({"_id": ObjectId(broadcast_id)})
    
    return {
        "success": True,
        "broadcast": serialize_broadcast(updated)
    }


@router.delete("/{broadcast_id}")
async def delete_broadcast(broadcast_id: str, user_id: str):
    """Delete a broadcast"""
    try:
        result = await get_db().broadcasts.delete_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id,
            "status": {"$nin": ["sending", "sent"]}  # Can't delete sent broadcasts
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Broadcast not found or cannot be deleted")
    
    return {"success": True, "message": "Broadcast deleted"}


@router.post("/{broadcast_id}/send")
async def send_broadcast(broadcast_id: str, user_id: str):
    """Send a broadcast via Twilio with staggered delivery and optional Jessi AI on replies."""
    db = get_db()
    try:
        broadcast = await db.broadcasts.find_one({"_id": ObjectId(broadcast_id), "created_by": user_id})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    if broadcast.get("status") in ["sending", "sent"]:
        raise HTTPException(status_code=400, detail="Broadcast has already been sent")

    # Get rep's Twilio number
    from services.twilio_service import get_rep_twilio_number
    rep_twilio_number = await get_rep_twilio_number(user_id)

    now = datetime.now(timezone.utc)
    stagger = int(broadcast.get("stagger_seconds", 10))  # seconds between each send
    jessi_on = broadcast.get("jessi_replies", False)
    message_template = broadcast.get("message", "")

    # Sanitize media URLs — Twilio MMS requires PUBLIC https URLs.
    # Local device paths (file://) or data URIs can never be fetched by Twilio (error 21620).
    public_base = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    media_urls = []
    for u in (broadcast.get("media_urls") or []):
        if not isinstance(u, str):
            continue
        if u.startswith("http://") or u.startswith("https://"):
            media_urls.append(u)
        elif u.startswith("/api/"):
            media_urls.append(f"{public_base}{u}")
        else:
            logger.warning(f"[Broadcast] Dropping invalid media URL (not publicly fetchable): {u[:100]}")

    recipient_ids = broadcast.get("recipients", [])
    contacts = await db.contacts.find(
        {"_id": {"$in": [ObjectId(rid) for rid in recipient_ids]}},
        {"_id": 1, "phone": 1, "first_name": 1, "last_name": 1}
    ).to_list(5000)

    # Pre-schedule all sends into campaign_pending_sends with staggered send_at
    pending_docs = []
    for i, contact in enumerate(contacts):
        phone = contact.get("phone", "")
        if not phone:
            continue
        first_name = contact.get("first_name", "there")
        # Personalise {first_name} / {name} variables
        personalised = message_template.replace("{first_name}", first_name).replace("{name}", first_name)
        contact_id = str(contact["_id"])
        send_at = (now + timedelta(seconds=i * stagger)).replace(tzinfo=None)
        pending_docs.append({
            "user_id": user_id,
            "contact_id": contact_id,
            "contact_name": f"{contact.get('first_name','')} {contact.get('last_name','')}".strip(),
            "contact_phone": phone,
            "rep_phone": rep_twilio_number,
            "message_template": personalised,
            "media_urls": media_urls,
            "channel": "sms",
            "delivery_mode": "auto",
            "send_at": send_at,
            "status": "pending",
            "step": 0,
            "enrollment_id": "",
            "campaign_id": "",
            "campaign_name": broadcast.get("name", "Broadcast"),
            "broadcast_id": broadcast_id,
            "type": "broadcast",
            "created_at": now.replace(tzinfo=None),
        })

    queued = 0
    if pending_docs:
        result = await db.campaign_pending_sends.insert_many(pending_docs)
        queued = len(result.inserted_ids)

    # Enable Jessi for all recipient conversations (if requested)
    jessi_enabled_count = 0
    if jessi_on:
        for contact in contacts:
            if not contact.get("phone"):
                continue
            contact_id = str(contact["_id"])
            phone = contact["phone"]
            # Find or create conversation
            conv = await db.conversations.find_one({
                "$or": [
                    {"rep_phone": rep_twilio_number, "contact_phone": phone},
                    {"user_id": user_id, "contact_id": contact_id},
                ]
            })
            if not conv:
                conv_doc = {
                    "user_id": user_id,
                    "rep_phone": rep_twilio_number,
                    "contact_id": contact_id,
                    "contact_phone": phone,
                    "contact_name": f"{contact.get('first_name','')} {contact.get('last_name','')}".strip(),
                    "status": "active",
                    "ai_enabled": True,
                    "ai_mode": "auto",
                    "created_at": now,
                    "last_message_at": now,
                }
                await db.conversations.insert_one(conv_doc)
            else:
                await db.conversations.update_one(
                    {"_id": conv["_id"]},
                    {"$set": {"ai_enabled": True, "ai_mode": "auto"}}
                )
            jessi_enabled_count += 1

    # Mark broadcast as sending (scheduler will update to sent as messages go out)
    last_send_at = (now + timedelta(seconds=len(pending_docs) * stagger)).isoformat()
    await db.broadcasts.update_one(
        {"_id": ObjectId(broadcast_id)},
        {"$set": {
            "status": "sending",
            "sent_at": now.isoformat(),
            "queued_count": queued,
            "estimated_completion": last_send_at,
        }}
    )
    logger.info(f"[Broadcast] Queued {queued} messages for '{broadcast.get('name')}', stagger={stagger}s, jessi={jessi_on}")
    return {
        "success": True,
        "message": f"Broadcast queued — {queued} messages will go out over ~{round(queued * stagger / 60, 1)} minutes",
        "queued": queued,
        "jessi_enabled": jessi_enabled_count,
        "estimated_completion": last_send_at,
    }


@router.post("/{broadcast_id}/duplicate")
async def duplicate_broadcast(broadcast_id: str, user_id: str):
    """Duplicate a broadcast"""
    try:
        original = await get_db().broadcasts.find_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    
    if not original:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    
    # Create a copy
    new_broadcast = {
        "name": f"{original.get('name', 'Broadcast')} (Copy)",
        "message": original.get("message", ""),
        "filters": original.get("filters", {}),
        "media_urls": original.get("media_urls", []),
        "status": "draft",
        "scheduled_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user_id,
        "recipient_count": original.get("recipient_count", 0),
        "sent_count": 0,
        "failed_count": 0,
        "recipients": original.get("recipients", [])
    }
    
    result = await get_db().broadcasts.insert_one(new_broadcast)
    new_broadcast["_id"] = result.inserted_id
    
    return {
        "success": True,
        "broadcast": serialize_broadcast(new_broadcast)
    }
