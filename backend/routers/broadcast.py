"""
Broadcast Router - One-time mass messaging system
Allows sending messages to filtered contact lists with scheduling and media attachments
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging

from routers.database import get_db

router = APIRouter(prefix="/broadcast", tags=["broadcast"])
logger = logging.getLogger(__name__)

# Get database reference
db = None

def get_database():
    global db
    if db is None:
        db = get_db()
    return db


# Pydantic Models
class BroadcastFilter(BaseModel):
    """Filter criteria for selecting broadcast recipients"""
    tags: Optional[List[str]] = []  # Contact tags to include
    exclude_tags: Optional[List[str]] = []  # Contact tags to exclude
    purchase_month: Optional[int] = None  # 1-12 for month filter
    purchase_year: Optional[int] = None  # Year filter
    days_since_purchase: Optional[int] = None  # e.g., 1095 for 3 years
    days_since_contact: Optional[int] = None  # Days since last contact
    custom_date_start: Optional[str] = None  # ISO date string
    custom_date_end: Optional[str] = None  # ISO date string
    contact_ids: Optional[List[str]] = []  # Specific contact IDs


class BroadcastCreate(BaseModel):
    """Request model for creating a broadcast"""
    name: str
    message: str
    filters: BroadcastFilter
    scheduled_at: Optional[str] = None  # ISO datetime, None = send immediately
    media_urls: Optional[List[str]] = []  # URLs of attached media


class BroadcastUpdate(BaseModel):
    """Request model for updating a broadcast"""
    name: Optional[str] = None
    message: Optional[str] = None
    filters: Optional[BroadcastFilter] = None
    scheduled_at: Optional[str] = None
    media_urls: Optional[List[str]] = None


def serialize_broadcast(broadcast: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
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
        "recipients": broadcast.get("recipients", []),
    }


async def get_filtered_contacts(filters: dict, user_id: str) -> List[dict]:
    """Get contacts matching the filter criteria"""
    query = {"owner_id": user_id}
    
    # Tag filters
    if filters.get("tags"):
        query["tags"] = {"$in": filters["tags"]}
    
    if filters.get("exclude_tags"):
        query["tags"] = {"$nin": filters["exclude_tags"]}
    
    # Specific contact IDs
    if filters.get("contact_ids"):
        query["_id"] = {"$in": [ObjectId(cid) for cid in filters["contact_ids"]]}
    
    # Purchase date filters
    if filters.get("purchase_month") or filters.get("purchase_year"):
        date_query = {}
        if filters.get("purchase_year"):
            start_year = datetime(filters["purchase_year"], 1, 1)
            end_year = datetime(filters["purchase_year"] + 1, 1, 1)
            date_query["$gte"] = start_year
            date_query["$lt"] = end_year
        if filters.get("purchase_month"):
            # This is a simplification - for month filtering across years
            pass
        if date_query:
            query["purchase_date"] = date_query
    
    # Days since purchase
    if filters.get("days_since_purchase"):
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None)
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=filters["days_since_purchase"])
        query["purchase_date"] = {"$lte": cutoff_date}
    
    # Days since last contact
    if filters.get("days_since_contact"):
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff_date = cutoff_date - timedelta(days=filters["days_since_contact"])
        query["last_contact_date"] = {"$lte": cutoff_date}
    
    # Custom date range
    if filters.get("custom_date_start") or filters.get("custom_date_end"):
        date_query = {}
        if filters.get("custom_date_start"):
            date_query["$gte"] = datetime.fromisoformat(filters["custom_date_start"].replace("Z", "+00:00"))
        if filters.get("custom_date_end"):
            date_query["$lte"] = datetime.fromisoformat(filters["custom_date_end"].replace("Z", "+00:00"))
        if date_query:
            query["purchase_date"] = date_query
    
    # Get contacts
    contacts = await get_database().contacts.find(query, {"_id": 1, "phone": 1, "first_name": 1, "last_name": 1, "email": 1}).to_list(10000)
    return contacts


@router.get("")
async def list_broadcasts(user_id: str, status: Optional[str] = None, limit: int = 50):
    """List all broadcasts for a user"""
    query = {"created_by": user_id}
    if status:
        query["status"] = status
    
    broadcasts = await get_database().broadcasts.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    return {
        "success": True,
        "broadcasts": [serialize_broadcast(b) for b in broadcasts]
    }


@router.get("/stats")
async def get_broadcast_stats(user_id: str):
    """Get broadcast statistics for a user"""
    pipeline = [
        {"$match": {"created_by": user_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_sent": {"$sum": "$sent_count"},
            "total_failed": {"$sum": "$failed_count"}
        }}
    ]
    
    stats = await get_database().broadcasts.aggregate(pipeline).to_list(10)
    
    result = {
        "draft": 0,
        "scheduled": 0,
        "sending": 0,
        "sent": 0,
        "failed": 0,
        "total_messages_sent": 0,
        "total_messages_failed": 0
    }
    
    for stat in stats:
        status = stat["_id"]
        if status in result:
            result[status] = stat["count"]
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
    custom_date_end: Optional[str] = None
):
    """Preview how many contacts match the filter criteria"""
    filters = {
        "tags": tags.split(",") if tags else [],
        "exclude_tags": exclude_tags.split(",") if exclude_tags else [],
        "purchase_month": purchase_month,
        "purchase_year": purchase_year,
        "days_since_purchase": days_since_purchase,
        "days_since_contact": days_since_contact,
        "custom_date_start": custom_date_start,
        "custom_date_end": custom_date_end
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
    # Get matching contacts
    contacts = await get_filtered_contacts(data.filters.dict(), user_id)
    
    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts match the selected filters")
    
    # Determine status based on scheduling
    status = "scheduled" if data.scheduled_at else "draft"
    
    broadcast = {
        "name": data.name,
        "message": data.message,
        "filters": data.filters.dict(),
        "media_urls": data.media_urls or [],
        "status": status,
        "scheduled_at": data.scheduled_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user_id,
        "recipient_count": len(contacts),
        "sent_count": 0,
        "failed_count": 0,
        "recipients": [str(c["_id"]) for c in contacts]
    }
    
    result = await get_database().broadcasts.insert_one(broadcast)
    broadcast["_id"] = result.inserted_id
    
    return {
        "success": True,
        "broadcast": serialize_broadcast(broadcast)
    }


@router.get("/{broadcast_id}")
async def get_broadcast(broadcast_id: str, user_id: str):
    """Get a specific broadcast"""
    try:
        broadcast = await get_database().broadcasts.find_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id
        })
    except:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    
    return {
        "success": True,
        "broadcast": serialize_broadcast(broadcast)
    }


@router.put("/{broadcast_id}")
async def update_broadcast(broadcast_id: str, data: BroadcastUpdate, user_id: str):
    """Update a broadcast (only if not yet sent)"""
    try:
        broadcast = await get_database().broadcasts.find_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id
        })
    except:
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
    
    await get_database().broadcasts.update_one(
        {"_id": ObjectId(broadcast_id)},
        {"$set": update_data}
    )
    
    updated = await get_database().broadcasts.find_one({"_id": ObjectId(broadcast_id)})
    
    return {
        "success": True,
        "broadcast": serialize_broadcast(updated)
    }


@router.delete("/{broadcast_id}")
async def delete_broadcast(broadcast_id: str, user_id: str):
    """Delete a broadcast"""
    try:
        result = await get_database().broadcasts.delete_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id,
            "status": {"$nin": ["sending", "sent"]}  # Can't delete sent broadcasts
        })
    except:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Broadcast not found or cannot be deleted")
    
    return {"success": True, "message": "Broadcast deleted"}


@router.post("/{broadcast_id}/send")
async def send_broadcast(broadcast_id: str, user_id: str):
    """Send a broadcast immediately"""
    try:
        broadcast = await get_database().broadcasts.find_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id
        })
    except:
        raise HTTPException(status_code=400, detail="Invalid broadcast ID")
    
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    
    if broadcast.get("status") in ["sending", "sent"]:
        raise HTTPException(status_code=400, detail="Broadcast has already been sent")
    
    # Update status to sending
    await get_database().broadcasts.update_one(
        {"_id": ObjectId(broadcast_id)},
        {"$set": {
            "status": "sending",
            "sent_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Get recipient contacts
    recipient_ids = broadcast.get("recipients", [])
    contacts = await get_database().contacts.find(
        {"_id": {"$in": [ObjectId(rid) for rid in recipient_ids]}},
        {"_id": 1, "phone": 1, "first_name": 1}
    ).to_list(10000)
    
    sent_count = 0
    failed_count = 0
    
    # Send messages (this would integrate with your SMS service)
    for contact in contacts:
        try:
            # TODO: Integrate with actual SMS service (Twilio)
            # For now, we'll simulate sending
            phone = contact.get("phone")
            if phone:
                # Create a message record
                message_record = {
                    "contact_id": str(contact["_id"]),
                    "phone": phone,
                    "content": broadcast.get("message"),
                    "media_urls": broadcast.get("media_urls", []),
                    "direction": "outbound",
                    "status": "sent",  # Would be "pending" until confirmed
                    "broadcast_id": broadcast_id,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "user_id": user_id
                }
                await get_database().broadcast_messages.insert_one(message_record)
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast message to {contact.get('_id')}: {e}")
            failed_count += 1
    
    # Update broadcast with results
    final_status = "sent" if failed_count == 0 else "sent"  # Still mark as sent even with some failures
    await get_database().broadcasts.update_one(
        {"_id": ObjectId(broadcast_id)},
        {"$set": {
            "status": final_status,
            "sent_count": sent_count,
            "failed_count": failed_count
        }}
    )
    
    return {
        "success": True,
        "message": f"Broadcast sent to {sent_count} recipients",
        "sent_count": sent_count,
        "failed_count": failed_count
    }


@router.post("/{broadcast_id}/duplicate")
async def duplicate_broadcast(broadcast_id: str, user_id: str):
    """Duplicate a broadcast"""
    try:
        original = await get_database().broadcasts.find_one({
            "_id": ObjectId(broadcast_id),
            "created_by": user_id
        })
    except:
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
    
    result = await get_database().broadcasts.insert_one(new_broadcast)
    new_broadcast["_id"] = result.inserted_id
    
    return {
        "success": True,
        "broadcast": serialize_broadcast(new_broadcast)
    }
