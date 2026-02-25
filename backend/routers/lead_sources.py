"""
Lead Sources Router - Manages lead sources, webhooks, and routing logic
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timezone
from bson import ObjectId
import secrets
import logging
import os
from pymongo import MongoClient
from routers.notifications import create_notification, create_team_notifications

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lead-sources", tags=["Lead Sources"])

# MongoDB connection - uses environment variable, no localhost fallback
def get_db():
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise Exception("MONGO_URL not configured")
    client = MongoClient(mongo_url)
    return client[os.environ.get("DB_NAME", "test_database")]

# Models
class LeadSourceCreate(BaseModel):
    name: str = Field(..., description="Name of the lead source (e.g., 'Facebook Ads', 'Website Form')")
    description: Optional[str] = None
    team_id: str = Field(..., description="Team ID that handles leads from this source")
    assignment_method: Literal["jump_ball", "round_robin", "weighted_round_robin"] = "jump_ball"
    is_active: bool = True

class LeadSourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[str] = None
    assignment_method: Optional[Literal["jump_ball", "round_robin", "weighted_round_robin"]] = None
    is_active: Optional[bool] = None

class InboundLead(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None  # Alternative to first_name/last_name
    phone: str = Field(..., description="Phone number (required)")
    email: Optional[str] = None
    notes: Optional[str] = None
    vehicle_interest: Optional[str] = None
    custom_fields: Optional[dict] = None

def serialize_lead_source(source: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    return {
        "id": str(source["_id"]),
        "name": source.get("name"),
        "description": source.get("description"),
        "store_id": source.get("store_id"),
        "organization_id": source.get("organization_id"),
        "team_id": source.get("team_id"),
        "assignment_method": source.get("assignment_method", "jump_ball"),
        "webhook_url": source.get("webhook_url"),
        "api_key": source.get("api_key"),
        "is_active": source.get("is_active", True),
        "lead_count": source.get("lead_count", 0),
        "created_at": source.get("created_at"),
        "updated_at": source.get("updated_at"),
    }

# ============ LEAD SOURCE MANAGEMENT ============

@router.post("")
async def create_lead_source(source: LeadSourceCreate, store_id: str, organization_id: Optional[str] = None):
    """Create a new lead source for a store"""
    db = get_db()
    
    # Generate unique webhook URL and API key
    source_id = str(ObjectId())
    api_key = secrets.token_urlsafe(32)
    
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    webhook_url = f"{base_url}/api/lead-sources/inbound/{source_id}"
    
    lead_source = {
        "_id": ObjectId(source_id),
        "name": source.name,
        "description": source.description,
        "store_id": store_id,
        "organization_id": organization_id,
        "team_id": source.team_id,
        "assignment_method": source.assignment_method,
        "webhook_url": webhook_url,
        "api_key": api_key,
        "is_active": source.is_active,
        "lead_count": 0,
        "round_robin_index": 0,  # For round robin tracking
        "member_lead_counts": {},  # For weighted round robin: {user_id: count}
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    db.lead_sources.insert_one(lead_source)
    
    return {
        "success": True,
        "lead_source": serialize_lead_source(lead_source),
        "message": f"Lead source created. Webhook URL: {webhook_url}"
    }

@router.get("")
async def list_lead_sources(store_id: str):
    """List all lead sources for a store"""
    db = get_db()
    
    sources = list(db.lead_sources.find({"store_id": store_id}))
    
    return {
        "success": True,
        "lead_sources": [serialize_lead_source(s) for s in sources]
    }

@router.get("/{source_id}")
async def get_lead_source(source_id: str):
    """Get a specific lead source"""
    db = get_db()
    
    source = db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    return {
        "success": True,
        "lead_source": serialize_lead_source(source)
    }

@router.patch("/{source_id}")
async def update_lead_source(source_id: str, updates: LeadSourceUpdate):
    """Update a lead source"""
    db = get_db()
    
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = db.lead_sources.update_one(
        {"_id": ObjectId(source_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    source = db.lead_sources.find_one({"_id": ObjectId(source_id)})
    return {
        "success": True,
        "lead_source": serialize_lead_source(source)
    }

@router.delete("/{source_id}")
async def delete_lead_source(source_id: str):
    """Delete a lead source"""
    db = get_db()
    
    result = db.lead_sources.delete_one({"_id": ObjectId(source_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    return {"success": True, "message": "Lead source deleted"}

# ============ LEAD ASSIGNMENT LOGIC ============

def get_jump_ball_assignee(db, team_id: str) -> Optional[str]:
    """Jump Ball: Returns None - lead goes to team inbox, first responder claims it"""
    return None

def get_round_robin_assignee(db, source: dict, team_id: str) -> Optional[str]:
    """Round Robin: Assign to next team member in rotation"""
    # Get team members
    team = db.teams.find_one({"_id": ObjectId(team_id)})
    if not team or not team.get("members"):
        return None
    
    members = team.get("members", [])
    if not members:
        return None
    
    # Get current index and select next member
    current_index = source.get("round_robin_index", 0)
    assignee_id = members[current_index % len(members)]
    
    # Update index for next assignment
    db.lead_sources.update_one(
        {"_id": source["_id"]},
        {"$set": {"round_robin_index": (current_index + 1) % len(members)}}
    )
    
    return assignee_id

def get_weighted_round_robin_assignee(db, source: dict, team_id: str) -> Optional[str]:
    """Weighted Round Robin: Assign to team member with fewest leads"""
    # Get team members
    team = db.teams.find_one({"_id": ObjectId(team_id)})
    if not team or not team.get("members"):
        return None
    
    members = team.get("members", [])
    if not members:
        return None
    
    # Get lead counts per member
    member_counts = source.get("member_lead_counts", {})
    
    # Initialize counts for new members
    for member_id in members:
        if member_id not in member_counts:
            member_counts[member_id] = 0
    
    # Find member with lowest count
    min_count = float('inf')
    assignee_id = members[0]
    for member_id in members:
        count = member_counts.get(member_id, 0)
        if count < min_count:
            min_count = count
            assignee_id = member_id
    
    # Increment count for assigned member
    member_counts[assignee_id] = member_counts.get(assignee_id, 0) + 1
    db.lead_sources.update_one(
        {"_id": source["_id"]},
        {"$set": {"member_lead_counts": member_counts}}
    )
    
    return assignee_id

def assign_lead(db, source: dict) -> Optional[str]:
    """Determine who to assign the lead to based on source's assignment method"""
    team_id = source.get("team_id")
    method = source.get("assignment_method", "jump_ball")
    
    if method == "jump_ball":
        return get_jump_ball_assignee(db, team_id)
    elif method == "round_robin":
        return get_round_robin_assignee(db, source, team_id)
    elif method == "weighted_round_robin":
        return get_weighted_round_robin_assignee(db, source, team_id)
    else:
        return None

# ============ INBOUND LEAD WEBHOOK ============

@router.post("/inbound/{source_id}")
async def receive_inbound_lead(source_id: str, lead: InboundLead, request: Request):
    """
    Webhook endpoint to receive inbound leads from external systems.
    Requires API key in header: X-API-Key
    """
    db = get_db()
    
    # Validate source exists
    source = db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    # Validate API key
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != source.get("api_key"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not source.get("is_active", True):
        raise HTTPException(status_code=400, detail="Lead source is inactive")
    
    # Parse lead name
    if lead.name:
        name_parts = lead.name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
    else:
        first_name = lead.first_name or "Unknown"
        last_name = lead.last_name or ""
    
    # Normalize phone number
    phone = lead.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        phone = "+1" + phone if len(phone) == 10 else "+" + phone
    
    # Check if contact already exists
    existing_contact = db.contacts.find_one({
        "phone": phone,
        "user_id": {"$in": [source.get("store_id"), source.get("organization_id")]}
    })
    
    if existing_contact:
        contact_id = str(existing_contact["_id"])
    else:
        # Create new contact
        new_contact = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": lead.email,
            "notes": lead.notes,
            "vehicle_interest": lead.vehicle_interest,
            "tags": ["lead", f"source:{source.get('name')}"],
            "lead_source_id": source_id,
            "lead_source_name": source.get("name"),
            "custom_fields": lead.custom_fields or {},
            "store_id": source.get("store_id"),
            "organization_id": source.get("organization_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = db.contacts.insert_one(new_contact)
        contact_id = str(result.inserted_id)
    
    # Determine assignment
    assigned_to = assign_lead(db, source)
    team_id = source.get("team_id")
    
    # Create conversation/thread
    conversation = {
        "contact_id": contact_id,
        "contact_phone": phone,
        "contact_name": f"{first_name} {last_name}".strip(),
        "lead_source_id": source_id,
        "lead_source_name": source.get("name"),
        "team_id": team_id,
        "assigned_to": assigned_to,  # None for jump_ball
        "assignment_method": source.get("assignment_method"),
        "status": "new",
        "claimed": assigned_to is not None,
        "claimed_by": assigned_to,
        "claimed_at": datetime.now(timezone.utc).isoformat() if assigned_to else None,
        "store_id": source.get("store_id"),
        "organization_id": source.get("organization_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_message_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add initial message if notes provided
    if lead.notes:
        conversation["messages"] = [{
            "content": f"New lead from {source.get('name')}: {lead.notes}",
            "sender": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    
    result = db.conversations.insert_one(conversation)
    conversation_id = str(result.inserted_id)
    
    # Update lead source stats
    db.lead_sources.update_one(
        {"_id": ObjectId(source_id)},
        {"$inc": {"lead_count": 1}}
    )
    
    # ============ CREATE NOTIFICATIONS ============
    contact_full_name = f"{first_name} {last_name}".strip()
    source_name = source.get("name", "Unknown Source")
    assignment_method = source.get("assignment_method", "jump_ball")
    
    if assignment_method == "jump_ball":
        # Notify ALL team members - first to respond claims the lead
        create_team_notifications(
            team_id=team_id,
            notification_type="jump_ball",
            title="New Lead Available!",
            message=f"New lead from {source_name}: {contact_full_name}. First to respond gets it!",
            conversation_id=conversation_id,
            contact_id=contact_id,
            contact_name=contact_full_name,
            contact_phone=phone,
            contact_email=lead.email,
            lead_source_name=source_name
        )
        logger.info(f"Jump ball notifications sent to team {team_id}")
    else:
        # Round Robin or Weighted - notify only the assigned user
        if assigned_to:
            create_notification(
                notification_type="lead_assigned",
                title="New Lead Assigned to You!",
                message=f"You've been assigned a new lead from {source_name}: {contact_full_name}",
                user_id=assigned_to,
                team_id=team_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                contact_name=contact_full_name,
                contact_phone=phone,
                contact_email=lead.email,
                lead_source_name=source_name,
                action_required=True,
                priority="high"
            )
            logger.info(f"Lead assigned notification sent to user {assigned_to}")
    
    # Log the lead
    logger.info(f"New lead received from {source.get('name')}: {phone} -> Team {team_id}, Assigned: {assigned_to}")
    
    return {
        "success": True,
        "message": "Lead received successfully",
        "contact_id": contact_id,
        "conversation_id": conversation_id,
        "assigned_to": assigned_to,
        "team_id": team_id,
        "assignment_method": source.get("assignment_method")
    }

# ============ CLAIM LEAD (for Jump Ball) ============

@router.post("/claim/{conversation_id}")
async def claim_lead(conversation_id: str, user_id: str):
    """Claim an unclaimed lead (for jump ball assignment)"""
    db = get_db()
    
    conversation = db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.get("claimed"):
        raise HTTPException(status_code=400, detail=f"Lead already claimed by {conversation.get('claimed_by')}")
    
    # Claim the lead
    result = db.conversations.update_one(
        {"_id": ObjectId(conversation_id), "claimed": {"$ne": True}},
        {"$set": {
            "claimed": True,
            "claimed_by": user_id,
            "assigned_to": user_id,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Could not claim lead - may already be claimed")
    
    # Also update the contact to be owned by this user so it appears in their contacts
    if conversation.get("contact_id"):
        db.contacts.update_one(
            {"_id": ObjectId(conversation["contact_id"])},
            {"$set": {
                "user_id": user_id,
                "claimed_by": user_id,
                "claimed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
    
    # Update lead source weighted counts if applicable
    if conversation.get("lead_source_id"):
        source = db.lead_sources.find_one({"_id": ObjectId(conversation["lead_source_id"])})
        if source and source.get("assignment_method") == "weighted_round_robin":
            member_counts = source.get("member_lead_counts", {})
            member_counts[user_id] = member_counts.get(user_id, 0) + 1
            db.lead_sources.update_one(
                {"_id": source["_id"]},
                {"$set": {"member_lead_counts": member_counts}}
            )
    
    return {
        "success": True,
        "message": "Lead claimed successfully",
        "claimed_by": user_id
    }

# ============ TEAM INBOX QUERIES ============

@router.get("/team-inbox/{team_id}")
async def get_team_inbox(team_id: str, include_claimed: bool = False):
    """Get all conversations for a team inbox"""
    db = get_db()
    
    query = {"team_id": team_id}
    if not include_claimed:
        query["$or"] = [{"claimed": False}, {"claimed": {"$exists": False}}]
    
    conversations = list(db.conversations.find(query).sort("last_message_at", -1))
    
    result = []
    for c in conversations:
        conv_data = {
            "id": str(c["_id"]),
            "contact_id": c.get("contact_id"),
            "contact_phone": c.get("contact_phone"),
            "contact_name": c.get("contact_name"),
            "contact_photo": None,
            "lead_source_name": c.get("lead_source_name"),
            "status": c.get("status"),
            "claimed": c.get("claimed", False),
            "claimed_by": c.get("claimed_by"),
            "assigned_to": c.get("assigned_to"),
            "last_message_at": c.get("last_message_at"),
            "created_at": c.get("created_at"),
        }
        # Try to get contact photo
        if c.get("contact_id"):
            try:
                contact = db.contacts.find_one({"_id": ObjectId(c["contact_id"])}, {"photo": 0})
                if contact:
                    conv_data["contact_photo"] = contact.get("photo_thumbnail") or contact.get("photo_url")
            except:
                pass
        result.append(conv_data)
    
    return {
        "success": True,
        "conversations": result
    }

@router.get("/user-inbox/{user_id}")
async def get_user_inbox(user_id: str):
    """Get all conversations assigned to a specific user"""
    db = get_db()
    
    conversations = list(db.conversations.find({
        "$or": [
            {"assigned_to": user_id},
            {"claimed_by": user_id}
        ]
    }).sort("last_message_at", -1))
    
    result = []
    for c in conversations:
        conv_data = {
            "id": str(c["_id"]),
            "contact_id": c.get("contact_id"),
            "contact_phone": c.get("contact_phone"),
            "contact_name": c.get("contact_name"),
            "contact_photo": None,
            "lead_source_name": c.get("lead_source_name"),
            "status": c.get("status"),
            "claimed": c.get("claimed", False),
            "last_message_at": c.get("last_message_at"),
            "created_at": c.get("created_at"),
        }
        # Try to get contact photo
        if c.get("contact_id"):
            try:
                contact = db.contacts.find_one({"_id": ObjectId(c["contact_id"])}, {"photo": 0})
                if contact:
                    conv_data["contact_photo"] = contact.get("photo_thumbnail") or contact.get("photo_url")
            except:
                pass
        result.append(conv_data)
    
    return {
        "success": True,
        "conversations": result
    }

# ============ STATS ============

@router.get("/stats/{source_id}")
async def get_lead_source_stats(source_id: str):
    """Get statistics for a lead source"""
    db = get_db()
    
    source = db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    # Count conversations by status
    pipeline = [
        {"$match": {"lead_source_id": source_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    status_counts = {doc["_id"]: doc["count"] for doc in db.conversations.aggregate(pipeline)}
    
    return {
        "success": True,
        "stats": {
            "total_leads": source.get("lead_count", 0),
            "by_status": status_counts,
            "member_lead_counts": source.get("member_lead_counts", {}),
            "assignment_method": source.get("assignment_method"),
        }
    }
