"""
Lead Sources Router - Manages lead sources, webhooks, and routing logic
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timezone
from bson import ObjectId
import os
import re
import secrets
import logging

from routers.database import get_db
from routers.notifications import create_notification, create_team_notifications

logger = logging.getLogger(__name__)

MANAGER_ROLES = {"super_admin", "admin", "org_admin", "store_manager", "manager"}


async def require_user(request: Request) -> dict:
    """Every lead-source route needs a logged-in user, except the API-key protected /inbound webhook."""
    if "/lead-sources/inbound/" in request.url.path:
        return {}
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user = user
    return user


async def require_manager(request: Request) -> dict:
    user = await require_user(request)
    if user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Manager or admin role required")
    return user


def _assert_self_or_manager(user: dict, user_id: str):
    if str(user.get("_id")) != str(user_id) and user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="You can only claim leads as yourself")


router = APIRouter(prefix="/lead-sources", tags=["Lead Sources"], dependencies=[Depends(require_user)])

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
    monthly_cost: Optional[float] = None

class InboundLead(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None  # Alternative to first_name/last_name
    phone: str = Field(..., description="Phone number (required)")
    email: Optional[str] = None
    notes: Optional[str] = None
    vehicle_interest: Optional[str] = None
    custom_fields: Optional[dict] = None

class CallAttempt(BaseModel):
    """One rung of the rep escalation ladder: who rings, and how long after the previous attempt."""
    user_ids: List[str] = []
    delay_seconds: int = 60


class WorkflowConfig(BaseModel):
    """Configuration for automated lead response workflow."""
    intake_text: str = ""                       # Template with {{first_name}}, {{vehicle}}, etc.
    intake_delay_seconds: int = 0               # 0 = instant
    va_enabled: bool = True                     # Enable AI auto-reply
    va_profile_id: Optional[str] = None         # VA Library profile to use
    va_prompt_override: Optional[str] = None    # Custom VA prompt for this source
    workflow_user_ids: List[str] = []           # Reps to notify & call on new lead
    auto_call_on_claim: bool = False            # Auto-dial customer when rep claims
    claim_timeout_minutes: int = 5             # Before escalating to next rep
    notify_all_on_intake: bool = True           # Blast all workflow reps with push
    contact_mode: Literal["text_only", "text_and_call"] = "text_only"
    call_attempts: List[CallAttempt] = []       # Up to 4 attempts (CallDrip-style rep dialing)
    website_default: bool = False               # Catch-all for marketing "Book a Demo" forms
    website_pages: List[str] = []               # Specific marketing pages routed here
    after_hours_mode: Literal["text_and_ai", "ring_anyway"] = "text_and_ai"   # store closed: text + Jessi, ladder at opening
    text_window_start: str = "09:00"            # business-initiated texts/calls, customer-local time
    text_window_end: str = "20:00"
    timer_green_minutes: int = 5                # queue "Waiting" timer turns amber after this
    timer_amber_minutes: int = 15               # ...and red after this
    returning_alert_minutes: int = 10           # returning customer routed to owner: alert managers if no reply
    returning_release_minutes: int = 30         # ...then release back to the shared queue
    digest_hour: int = 18                       # managers' daily red-leads report (store local hour)


_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# Marketing pages that post Book a Demo forms (source like "pricing_hero" -> page "pricing")
WEBSITE_PAGES = [
    "homepage", "pricing", "features", "relationship_os", "why_imonsocial", "presentation",
    "calendar_systems", "calendar_systems_dealers", "insurance", "tiktok", "outreach",
    "appdirectory", "training", "sms_terms", "ad_showcase", "ad_autopilot", "dealers",
    "organizations", "individuals", "digital_card", "showcase", "seo", "store_reviews",
]

MERGE_FIELDS = ["first_name", "last_name", "full_name", "vehicle", "year", "make", "model", "lead_source", "phone", "rep_name"]

def hydrate_intake_text(template: str, lead_data: dict, source_name: str = "", rep_name: str = "") -> str:
    """Replace {{field}} placeholders with actual lead data."""
    text = template
    vehicle = lead_data.get("vehicle_interest") or " ".join(filter(None, [
        lead_data.get("vehicle_year"), lead_data.get("vehicle_make"), lead_data.get("vehicle_model")
    ]))
    replacements = {
        "first_name":   lead_data.get("first_name", "there"),
        "last_name":    lead_data.get("last_name", ""),
        "full_name":    lead_data.get("full_name") or f"{lead_data.get('first_name','')} {lead_data.get('last_name','')}".strip() or "there",
        "vehicle":      vehicle or "vehicle",
        "year":         lead_data.get("vehicle_year", ""),
        "make":         lead_data.get("vehicle_make", ""),
        "model":        lead_data.get("vehicle_model", ""),
        "lead_source":  source_name,
        "phone":        lead_data.get("phone", ""),
        "rep_name":     rep_name or "the team",
    }
    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
        text = text.replace(f"{{{key}}}", str(value))  # single-brace {first_name} works too
    return text.strip()

def serialize_lead_source(source: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    _base = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")
    _sid = str(source["_id"])
    _wh = source.get("webhook_url") or f"/api/lead-sources/inbound/{_sid}"
    if _wh.startswith("/"):
        _wh = f"{_base}{_wh}"
    return {
        "id": _sid,
        "name": source.get("name"),
        "description": source.get("description"),
        "store_id": source.get("store_id"),
        "organization_id": source.get("organization_id"),
        "team_id": source.get("team_id"),
        "assignment_method": source.get("assignment_method", "jump_ball"),
        "webhook_url": _wh,
        "adf_url": f"{_base}/api/leads/adf?source_id={_sid}",
        "email_inbound_url": f"{_base}/api/leads/email-inbound?source_id={_sid}",
        "monthly_cost": source.get("monthly_cost"),
        "api_key": source.get("api_key"),
        "is_active": source.get("is_active", True),
        "lead_count": source.get("lead_count", 0),
        "created_at": source.get("created_at"),
        "updated_at": source.get("updated_at"),
        # Workflow config
        "workflow": {
            "intake_text":             source.get("intake_text", ""),
            "intake_delay_seconds":    source.get("intake_delay_seconds", 0),
            "va_enabled":              source.get("va_enabled", True),
            "va_profile_id":           source.get("va_profile_id"),
            "va_prompt_override":      source.get("va_prompt_override"),
            "workflow_user_ids":       source.get("workflow_user_ids", []),
            "auto_call_on_claim":      source.get("auto_call_on_claim", False),
            "claim_timeout_minutes":   source.get("claim_timeout_minutes", 5),
            "notify_all_on_intake":    source.get("notify_all_on_intake", True),
            "contact_mode":            source.get("contact_mode", "text_only"),
            "call_attempts":           source.get("call_attempts", []),
            "website_default":         source.get("website_default", False),
            "website_pages":           source.get("website_pages", []),
            "after_hours_mode":        source.get("after_hours_mode", "text_and_ai"),
            "text_window_start":       source.get("text_window_start", "09:00"),
            "text_window_end":         source.get("text_window_end", "20:00"),
            "timer_green_minutes":     source.get("timer_green_minutes", 5),
            "timer_amber_minutes":     source.get("timer_amber_minutes", 15),
            "returning_alert_minutes": source.get("returning_alert_minutes", 10),
            "returning_release_minutes": source.get("returning_release_minutes", 30),
            "digest_hour":             source.get("digest_hour", 18),
        },
    }

# ============ LEAD SOURCE MANAGEMENT ============

@router.post("")
async def create_lead_source(source: LeadSourceCreate, store_id: str, organization_id: Optional[str] = None, _m: dict = Depends(require_manager)):
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
    
    await db.lead_sources.insert_one(lead_source)
    
    return {
        "success": True,
        "lead_source": serialize_lead_source(lead_source),
        "message": f"Lead source created. Webhook URL: {webhook_url}"
    }

@router.get("")
async def list_lead_sources(store_id: str):
    """List all lead sources for a store"""
    db = get_db()
    
    sources = await db.lead_sources.find({"store_id": store_id}).to_list(500)
    
    return {
        "success": True,
        "lead_sources": [serialize_lead_source(s) for s in sources]
    }

@router.get("/team-inbox/{team_id}")
async def get_team_inbox(team_id: str, include_claimed: bool = False):
    """Get all conversations for a team inbox"""
    db = get_db()
    
    query = {"team_id": team_id}
    if not include_claimed:
        query["$or"] = [{"claimed": False}, {"claimed": {"$exists": False}}]
    
    conversations = await db.conversations.find(query).sort("last_message_at", -1).to_list(200)
    
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
        if c.get("contact_id"):
            try:
                contact = await db.contacts.find_one({"_id": ObjectId(c["contact_id"])}, {"photo": 0})
                if contact:
                    conv_data["contact_photo"] = contact.get("photo_thumbnail") or contact.get("photo_url")
            except Exception:
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
    
    conversations = await db.conversations.find({
        "$or": [
            {"assigned_to": user_id},
            {"claimed_by": user_id}
        ]
    }).sort("last_message_at", -1).to_list(200)
    
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
        if c.get("contact_id"):
            try:
                contact = await db.contacts.find_one({"_id": ObjectId(c["contact_id"])}, {"photo": 0})
                if contact:
                    conv_data["contact_photo"] = contact.get("photo_thumbnail") or contact.get("photo_url")
            except Exception:
                pass
        result.append(conv_data)
    
    return {
        "success": True,
        "conversations": result
    }

@router.get("/stats/{source_id}")
async def get_lead_source_stats(source_id: str):
    """Get statistics for a lead source"""
    db = get_db()
    
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    pipeline = [
        {"$match": {"lead_source_id": source_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    status_counts = {doc["_id"]: doc["count"] async for doc in db.conversations.aggregate(pipeline)}
    
    return {
        "success": True,
        "stats": {
            "total_leads": source.get("lead_count", 0),
            "by_status": status_counts,
            "member_lead_counts": source.get("member_lead_counts", {}),
            "assignment_method": source.get("assignment_method"),
        }
    }

@router.get("/website-pages")
async def list_website_pages():
    """Known marketing pages (static list + anything seen in demo requests) for the routing UI."""
    db = get_db()
    seen = await db.demo_requests.distinct("source_page")
    pages = list(dict.fromkeys(WEBSITE_PAGES + [p for p in seen if p and p != "unknown"]))
    routed = {}
    async for src in db.lead_sources.find({"$or": [{"website_default": True}, {"website_pages.0": {"$exists": True}}]}, {"name": 1, "website_default": 1, "website_pages": 1}):
        for p in src.get("website_pages", []):
            routed[p] = {"id": str(src["_id"]), "name": src.get("name")}
        if src.get("website_default"):
            routed["__default__"] = {"id": str(src["_id"]), "name": src.get("name")}
    return {"pages": pages, "routed": routed}


@router.get("/{source_id}")
async def get_lead_source(source_id: str):
    """Get a specific lead source"""
    db = get_db()
    
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    return {
        "success": True,
        "lead_source": serialize_lead_source(source)
    }

@router.patch("/{source_id}")
async def update_lead_source(source_id: str, updates: LeadSourceUpdate, _m: dict = Depends(require_manager)):
    """Update a lead source"""
    db = get_db()
    
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.lead_sources.update_one(
        {"_id": ObjectId(source_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    return {
        "success": True,
        "lead_source": serialize_lead_source(source)
    }

@router.delete("/{source_id}")
async def delete_lead_source(source_id: str, _m: dict = Depends(require_manager)):
    """Delete a lead source"""
    db = get_db()
    
    result = await db.lead_sources.delete_one({"_id": ObjectId(source_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead source not found")
    
    return {"success": True, "message": "Lead source deleted"}

# ============ LEAD ASSIGNMENT LOGIC ============

def get_jump_ball_assignee(db, team_id: str) -> Optional[str]:
    """Jump Ball: Returns None - lead goes to team inbox, first responder claims it"""
    return None

async def get_round_robin_assignee(db, source: dict, team_id: str) -> Optional[str]:
    """Round Robin: Assign to next team member in rotation"""
    # Get team members
    team = await db.teams.find_one({"_id": ObjectId(team_id)})
    if not team or not team.get("members"):
        return None
    
    members = team.get("members", [])
    if not members:
        return None
    
    # Get current index and select next member
    current_index = source.get("round_robin_index", 0)
    assignee_id = members[current_index % len(members)]
    
    # Update index for next assignment
    await db.lead_sources.update_one(
        {"_id": source["_id"]},
        {"$set": {"round_robin_index": (current_index + 1) % len(members)}}
    )
    
    return assignee_id

async def get_weighted_round_robin_assignee(db, source: dict, team_id: str) -> Optional[str]:
    """Weighted Round Robin: Assign to team member with fewest leads"""
    # Get team members
    team = await db.teams.find_one({"_id": ObjectId(team_id)})
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
    await db.lead_sources.update_one(
        {"_id": source["_id"]},
        {"$set": {"member_lead_counts": member_counts}}
    )
    
    return assignee_id

async def assign_lead(db, source: dict) -> Optional[str]:
    """Determine who to assign the lead to based on source's assignment method"""
    team_id = source.get("team_id")
    method = source.get("assignment_method", "jump_ball")
    
    if method == "jump_ball":
        return get_jump_ball_assignee(db, team_id)
    elif method == "round_robin":
        return await get_round_robin_assignee(db, source, team_id)
    elif method == "weighted_round_robin":
        return await get_weighted_round_robin_assignee(db, source, team_id)
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
    
    # Validate source_id format
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=400, detail="Invalid source ID format")
    
    # Validate source exists
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
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
    existing_contact = await db.contacts.find_one({
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
        result = await db.contacts.insert_one(new_contact)
        contact_id = str(result.inserted_id)
    
    # Determine assignment
    assigned_to = await assign_lead(db, source)
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
    
    result = await db.conversations.insert_one(conversation)
    conversation_id = str(result.inserted_id)
    
    # Update lead source stats
    await db.lead_sources.update_one(
        {"_id": ObjectId(source_id)},
        {"$inc": {"lead_count": 1}}
    )
    
    # ============ CREATE NOTIFICATIONS ============
    contact_full_name = f"{first_name} {last_name}".strip()
    source_name = source.get("name", "Unknown Source")
    assignment_method = source.get("assignment_method", "jump_ball")
    
    if assignment_method == "jump_ball":
        # Notify ALL team members - first to respond claims the lead
        await create_team_notifications(
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
            await create_notification(
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
async def claim_lead(conversation_id: str, user_id: str, request: Request):
    """Claim an unclaimed lead (for jump ball assignment)"""
    _assert_self_or_manager(request.state.user, user_id)
    db = get_db()
    
    conversation = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.get("claimed"):
        raise HTTPException(status_code=400, detail=f"Lead already claimed by {conversation.get('claimed_by')}")

    # Only reps on this source's workflow (or managers) can claim from the shared queue
    source = None
    if conversation.get("lead_source_id") and ObjectId.is_valid(str(conversation["lead_source_id"])):
        source = await db.lead_sources.find_one({"_id": ObjectId(conversation["lead_source_id"])})
    requester = request.state.user or {}
    is_mgr = requester.get("role") in ("super_admin", "admin", "manager", "store_manager", "org_admin")
    if source and not is_mgr:
        from routers.lead_queue import source_member_ids
        if user_id not in source_member_ids(source):
            raise HTTPException(status_code=403, detail=f"You're not on the {source.get('name', 'lead source')} workflow")
    
    # Claim the lead
    result = await db.conversations.update_one(
        {"_id": ObjectId(conversation_id), "claimed": {"$ne": True}},
        {"$set": {
            "claimed": True,
            "claimed_by": user_id,
            "assigned_to": user_id,
            "user_id": user_id,
            "claim_source": "app",
            "routing_kind": "claimed",
            "owner_alert_at": None,
            "release_at": None,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Could not claim lead - may already be claimed")

    # Stop the phone dialing ladder, if one is running for this lead
    from services.lead_call_engine import mark_claimed
    await mark_claimed(conversation_id, user_id, via="app")
    
    # Also update the contact to be owned by this user so it appears in their contacts
    if conversation.get("contact_id"):
        await db.contacts.update_one(
            {"_id": ObjectId(conversation["contact_id"])},
            {"$set": {
                "user_id": user_id,
                "claimed_by": user_id,
                "claimed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
    
    # Update lead source weighted counts if applicable
    if source and source.get("assignment_method") == "weighted_round_robin":
        member_counts = source.get("member_lead_counts", {})
        member_counts[user_id] = member_counts.get(user_id, 0) + 1
        await db.lead_sources.update_one(
            {"_id": source["_id"]},
            {"$set": {"member_lead_counts": member_counts}}
        )

    # Quiet in-app notice (no push) to the other workflow reps so the card's disappearance makes sense
    try:
        from routers.lead_queue import source_member_ids
        claimer = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})
        who = ((claimer or {}).get("name") or "A teammate").split()[0]
        others = [m for m in source_member_ids(source or {}) if m != user_id]
        if others:
            await db.notifications.insert_many([{
                "user_id": uid, "type": "lead_claimed", "priority": "low",
                "title": f"{who} claimed {conversation.get('contact_name') or 'a lead'}",
                "message": f"{(source or {}).get('name', 'Lead')} · no action needed",
                "conversation_id": conversation_id, "contact_id": conversation.get("contact_id"),
                "read": False, "dismissed": False, "created_at": datetime.now(timezone.utc),
            } for uid in others])
    except Exception as e:
        logger.debug(f"[Claim] quiet notice failed: {e}")
    
    return {
        "success": True,
        "message": "Lead claimed successfully",
        "claimed_by": user_id
    }



@router.get("/{source_id}/workflow")
async def get_workflow_config(source_id: str):
    """Get the workflow automation config for a lead source (plus the store's hours for the after-hours rule)."""
    db = get_db()
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    cfg = serialize_lead_source(source).get("workflow", {})
    store = {}
    if source.get("store_id") and ObjectId.is_valid(str(source["store_id"])):
        store = await db.stores.find_one({"_id": ObjectId(source["store_id"])}, {"business_hours": 1, "timezone": 1, "name": 1}) or {}
    from services.lead_timing import store_hours_status
    st = store_hours_status(store)
    cfg["store_hours"] = {
        "store_name": store.get("name"),
        "timezone": st["tz"],
        "configured": st["configured"],
        "open_now": st["open"],
        "opens_at": st["opens_at"].isoformat() if st.get("opens_at") else None,
        "hours": store.get("business_hours") or {},
    }
    return cfg


@router.put("/{source_id}/workflow")
async def save_workflow_config(source_id: str, config: WorkflowConfig, _m: dict = Depends(require_manager)):
    """Save the workflow automation config for a lead source."""
    db = get_db()
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    # Only touch fields the client actually sent (a partial save must not reset the VA or wipe the ladder)
    updates = config.dict(exclude_unset=True)
    for k in ("text_window_start", "text_window_end"):
        if k in updates and not _HHMM.match(updates[k] or ""):
            raise HTTPException(status_code=400, detail=f"{k} must be HH:MM (24h)")
    if "call_attempts" in updates:
        updates["call_attempts"] = [
            {"user_ids": a.get("user_ids", []), "delay_seconds": max(30, int(60 if a.get("delay_seconds") is None else a["delay_seconds"]))}
            for a in updates["call_attempts"][:4]
        ]
    for k, lo, hi in (("timer_green_minutes", 1, 120), ("timer_amber_minutes", 2, 240),
                      ("returning_alert_minutes", 1, 240), ("returning_release_minutes", 2, 720), ("digest_hour", 0, 23)):
        if k in updates:
            updates[k] = max(lo, min(hi, int(updates[k])))
    if "timer_green_minutes" in updates or "timer_amber_minutes" in updates:
        g = updates.get("timer_green_minutes", source.get("timer_green_minutes", 5))
        a = updates.get("timer_amber_minutes", source.get("timer_amber_minutes", 15))
        if a <= g:
            raise HTTPException(status_code=400, detail="Amber must be later than green")
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.lead_sources.update_one({"_id": ObjectId(source_id)}, {"$set": updates})
    if config.website_default:
        # Only one catch-all for website forms
        await db.lead_sources.update_many(
            {"_id": {"$ne": ObjectId(source_id)}, "website_default": True},
            {"$set": {"website_default": False}},
        )
    return {"success": True, "message": "Workflow config saved"}


@router.get("/call-timeline/{conversation_id}")
async def call_timeline(conversation_id: str, request: Request):
    """Every ring, pass and claim for a lead's call ladder, plus how its intake was timed."""
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    db = get_db()
    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)}, {"user_id": 1, "assigned_to": 1, "claimed_by": 1, "store_id": 1, "is_internet_lead": 1})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user = request.state.user
    uid = str(user.get("_id"))
    if user.get("role") not in MANAGER_ROLES and uid not in {str(conv.get("user_id")), str(conv.get("assigned_to")), str(conv.get("claimed_by"))}:
        job = await db.lead_call_jobs.find_one({"conversation_id": conversation_id, "attempts.user_ids": uid}, {"_id": 1})
        if not job:
            raise HTTPException(status_code=403, detail="Not your lead")
    from services.lead_call_engine import timeline_for_conversation
    return await timeline_for_conversation(conversation_id)


class TestLead(BaseModel):
    phone: str
    first_name: str = "Test"
    last_name: str = "Lead"
    include_ladder: bool = True
    comments: str = "Test lead sent from the Lead Source screen"


@router.post("/{source_id}/test-lead")
async def send_test_lead(source_id: str, body: TestLead, request: Request, _m: dict = Depends(require_manager)):
    """Run a fake website lead through this source's REAL workflow (intake text, rep push,
    ladder, after-hours rule) so routing can be verified without touching the public site."""
    db = get_db()
    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    digits = re.sub(r"\D", "", body.phone or "")
    if len(digits) not in (10, 11):
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit phone number")
    if not body.include_ladder:
        source = {**source, "contact_mode": "text_only"}
    user = request.state.user
    normalized = {
        "first_name": body.first_name.strip() or "Test",
        "last_name": body.last_name.strip() or "Lead",
        "full_name": f"{body.first_name.strip() or 'Test'} {body.last_name.strip() or 'Lead'}",
        "phone": body.phone,
        "email": "",
        "company": "Test Company",
        "industry": "",
        "vehicle_interest": "Demo request",
        "comments": body.comments,
        "source_name": source.get("name", "Website"),
        "is_test": True,
        "sms_opt_in": True,
        "attribution": {
            "kind": "test",
            "source": "lead_source_test_button",
            "page": "test",
            "source_label": "a test lead",
            "sent_by": str(user.get("_id")),
        },
    }
    from routers.lead_intake import process_inbound_lead
    result = await process_inbound_lead(normalized, source, db)
    plan = result.get("plan") or {}
    return {
        "success": True,
        "conversation_id": result.get("conversation_id"),
        "contact_id": result.get("contact_id"),
        "plan": plan,
        "intake_text_configured": bool((source.get("intake_text") or "").strip()),
        "ladder_configured": source.get("contact_mode") == "text_and_call" and bool(source.get("call_attempts") or source.get("workflow_user_ids")),
        "reps_notified": len(source.get("workflow_user_ids") or []) if source.get("notify_all_on_intake", True) else 0,
    }




@router.post("/claim-and-call/{conversation_id}")
async def claim_and_call(conversation_id: str, user_id: str, request: Request):
    """
    Claim a lead AND immediately call the customer.
    Called when a rep taps 'Claim & Call' on a Jump Ball lead.
    """
    import os, asyncio as _aio
    _assert_self_or_manager(request.state.user, user_id)
    db = get_db()

    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Claim the conversation
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"claimed": True, "claimed_by": user_id, "assigned_to": user_id, "user_id": user_id, "routing_kind": "claimed",
                  "owner_alert_at": None, "release_at": None,
                  "claimed_at": datetime.now(timezone.utc), "claim_source": "app"}}
    )
    if conv.get("contact_id") and ObjectId.is_valid(str(conv["contact_id"])):
        await db.contacts.update_one({"_id": ObjectId(conv["contact_id"])},
                                     {"$set": {"user_id": user_id, "claimed_by": user_id, "updated_at": datetime.now(timezone.utc).isoformat()}})
    from services.lead_call_engine import mark_claimed
    await mark_claimed(conversation_id, user_id, via="app")

    # Get lead source workflow config for auto_call setting
    source_id = conv.get("lead_source_id")
    auto_call = False
    if source_id:
        source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
        auto_call = (source or {}).get("auto_call_on_claim", False)

    call_result = None
    if auto_call:
        rep = await db.users.find_one({"_id": ObjectId(user_id)})
        rep_phone   = (rep or {}).get("phone", "").strip()
        rep_twilio  = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number", "")
        customer_phone = conv.get("contact_phone", "")

        if rep_phone and rep_twilio and customer_phone:
            try:
                from twilio.rest import Client as _TC
                tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
                if tw_sid and tw_token:
                    app_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                    # Store pending call for bridge
                    from datetime import datetime as _dt
                    pending_doc = {
                        "customer_phone":    customer_phone,
                        "rep_twilio_number": rep_twilio,
                        "rep_name":          (rep or {}).get("name", ""),
                        "user_id":           user_id,
                        "rep_user_id":       user_id,
                        "contact_id":        conv.get("contact_id"),
                        "created_at":        _dt.now(),
                    }
                    client = _TC(tw_sid, tw_token)
                    from normalize_phone import normalize_phone as _np
                    try:
                        from routers.twilio_webhooks import normalize_phone as _np
                    except Exception:
                        _np = lambda x: x
                    call = await _aio.to_thread(
                        client.calls.create,
                        to=_np(rep_phone),
                        from_=rep_twilio,
                        url=f"{app_url}/api/webhooks/twilio/call-bridge",
                    )
                    pending_doc["call_sid"] = call.sid
                    await db.pending_calls.insert_one(pending_doc)
                    call_result = {"call_sid": call.sid, "status": call.status}
            except Exception as e:
                logger.warning(f"[LeadSource] Auto-call failed: {e}")
                call_result = {"error": str(e)}

    return {
        "success": True,
        "claimed": True,
        "claimed_by": user_id,
        "auto_call_placed": call_result is not None and "error" not in (call_result or {}),
        "call_result": call_result,
    }
