"""
Webhooks router - handles incoming webhooks from external RMS platforms/systems
Supports user sync, contact sync, and custom event triggers
"""
from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import hashlib
import hmac
import logging
import os

from .database import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

# ============= MODELS =============

class WebhookUserCreate(BaseModel):
    external_id: str  # ID from the external system (e.g., Salesforce ID)
    email: EmailStr
    name: str
    phone: Optional[str] = None
    role: Optional[str] = "Sales Rep"
    store_id: Optional[str] = None
    organization_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class WebhookUserDelete(BaseModel):
    external_id: Optional[str] = None
    email: Optional[EmailStr] = None
    deletion_source: Optional[str] = None  # e.g., "Salesforce", "Manual", "CDK", etc.
    # At least one must be provided to identify the user

class WebhookContactCreate(BaseModel):
    external_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    assigned_to_email: Optional[str] = None
    assigned_to_external_id: Optional[str] = None
    store_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class BulkReassignRequest(BaseModel):
    contact_ids: List[str]
    new_owner_id: str

# ============= WEBHOOK AUTHENTICATION =============

async def verify_webhook_signature(request: Request, x_webhook_secret: str = Header(None)):
    """Verify webhook signature for security"""
    db = get_db()
    
    # Get the organization's webhook secret
    if x_webhook_secret:
        org = await db.organizations.find_one({"webhook_secret": x_webhook_secret})
        if org:
            return org
    
    # Also check for API key auth
    api_key = request.headers.get("X-API-Key")
    if api_key:
        org = await db.organizations.find_one({"api_key": api_key})
        if org:
            return org
    
    # For demo/development, allow unauthenticated webhooks
    # In production, you'd want to enforce authentication
    logger.warning("Webhook received without authentication - allowing for demo mode")
    return None

# ============= USER WEBHOOKS =============

@router.post("/user-created")
async def webhook_user_created(
    user_data: WebhookUserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(None)
):
    """
    Webhook endpoint for when a user is created in an external system.
    Creates or updates the user in our system.
    """
    db = get_db()
    org = await verify_webhook_signature(request, x_webhook_secret)
    
    # Check if user already exists by external_id or email
    existing_user = await db.users.find_one({
        "$or": [
            {"external_id": user_data.external_id},
            {"email": user_data.email}
        ]
    })
    
    if existing_user:
        # Update existing user
        update_data = {
            "external_id": user_data.external_id,
            "name": user_data.name,
            "phone": user_data.phone or existing_user.get("phone"),
            "role": user_data.role,
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "status": "active",
            "external_metadata": user_data.metadata
        }
        
        if user_data.store_id:
            update_data["store_id"] = user_data.store_id
        if user_data.organization_id:
            update_data["organization_id"] = user_data.organization_id
            
        await db.users.update_one(
            {"_id": existing_user["_id"]},
            {"$set": update_data}
        )
        
        logger.info(f"Webhook: Updated existing user {user_data.email}")
        return {
            "status": "updated",
            "user_id": str(existing_user["_id"]),
            "email": user_data.email,
            "message": "User updated successfully"
        }
    else:
        # Create new user
        new_user = {
            "external_id": user_data.external_id,
            "email": user_data.email,
            "name": user_data.name,
            "phone": user_data.phone or "",
            "role": user_data.role,
            "store_id": user_data.store_id,
            "organization_id": user_data.organization_id,
            "password": "",  # External users don't have local passwords
            "auth_type": "external",
            "is_active": True,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "external_metadata": user_data.metadata,
            "stats": {
                "contacts_added": 0,
                "messages_sent": 0,
                "calls_made": 0,
                "deals_closed": 0
            },
            "settings": {
                "leaderboard_visible": False,
                "compare_scope": "state"
            }
        }
        
        result = await db.users.insert_one(new_user)
        
        logger.info(f"Webhook: Created new user {user_data.email}")
        return {
            "status": "created",
            "user_id": str(result.inserted_id),
            "email": user_data.email,
            "message": "User created successfully"
        }

@router.post("/user-deleted")
async def webhook_user_deleted(
    user_data: WebhookUserDelete,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(None)
):
    """
    Webhook endpoint for when a user is deleted in an external system.
    Deactivates the user and moves their contacts to unassigned.
    """
    db = get_db()
    await verify_webhook_signature(request, x_webhook_secret)
    
    if not user_data.external_id and not user_data.email:
        raise HTTPException(status_code=400, detail="Either external_id or email must be provided")
    
    # Find the user
    query = {}
    if user_data.external_id:
        query["external_id"] = user_data.external_id
    if user_data.email:
        query["email"] = user_data.email
    
    user = await db.users.find_one(query)
    
    if not user:
        return {
            "status": "not_found",
            "message": "User not found in system"
        }
    
    user_id = user["_id"]
    store_id = user.get("store_id")
    org_id = user.get("organization_id")
    
    # Determine deletion source
    deletion_source = user_data.deletion_source or "External System (Webhook)"
    
    # Deactivate user (soft delete) with audit trail
    await db.users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "is_active": False,
                "status": "inactive",
                "deleted_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "deletion_source": deletion_source,
                "deletion_reason": f"Deleted by {deletion_source}",
                "previous_status": user.get("status", "active")
            }
        }
    )
    
    # Move all contacts to unassigned
    contacts_result = await db.contacts.update_many(
        {"owner_id": str(user_id)},
        {
            "$set": {
                "owner_id": None,
                "is_unassigned": True,
                "previous_owner_id": str(user_id),
                "previous_owner_name": user.get("name"),
                "unassigned_at": datetime.utcnow(),
                "unassigned_reason": "owner_deleted_via_webhook"
            }
        }
    )
    
    logger.info(f"Webhook: Deleted user {user.get('email')}, moved {contacts_result.modified_count} contacts to unassigned")
    
    return {
        "status": "deleted",
        "user_id": str(user_id),
        "email": user.get("email"),
        "contacts_unassigned": contacts_result.modified_count,
        "message": f"User deactivated and {contacts_result.modified_count} contacts moved to unassigned pool"
    }

# ============= CONTACT WEBHOOKS =============

@router.post("/contact-created")
async def webhook_contact_created(
    contact_data: WebhookContactCreate,
    request: Request,
    x_webhook_secret: str = Header(None)
):
    """
    Webhook endpoint for when a contact is created in an external system.
    """
    db = get_db()
    await verify_webhook_signature(request, x_webhook_secret)
    
    # Find owner if specified
    owner_id = None
    if contact_data.assigned_to_email:
        owner = await db.users.find_one({"email": contact_data.assigned_to_email})
        if owner:
            owner_id = str(owner["_id"])
    elif contact_data.assigned_to_external_id:
        owner = await db.users.find_one({"external_id": contact_data.assigned_to_external_id})
        if owner:
            owner_id = str(owner["_id"])
    
    # Check if contact exists
    existing = await db.contacts.find_one({"external_id": contact_data.external_id})
    
    if existing:
        # Update
        await db.contacts.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "name": contact_data.name,
                    "phone": contact_data.phone,
                    "email": contact_data.email,
                    "owner_id": owner_id,
                    "is_unassigned": owner_id is None,
                    "store_id": contact_data.store_id,
                    "updated_at": datetime.utcnow(),
                    "external_metadata": contact_data.metadata
                }
            }
        )
        return {"status": "updated", "contact_id": str(existing["_id"])}
    else:
        # Create
        new_contact = {
            "external_id": contact_data.external_id,
            "name": contact_data.name,
            "phone": contact_data.phone or "",
            "email": contact_data.email or "",
            "owner_id": owner_id,
            "is_unassigned": owner_id is None,
            "store_id": contact_data.store_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "external_metadata": contact_data.metadata,
            "status": "active",
            "tags": [],
            "notes": []
        }
        result = await db.contacts.insert_one(new_contact)
        return {"status": "created", "contact_id": str(result.inserted_id)}

# ============= UNASSIGNED CONTACTS MANAGEMENT =============

@router.get("/unassigned-contacts")
async def get_unassigned_contacts(
    store_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    """Get all unassigned contacts, optionally filtered by store or organization"""
    db = get_db()
    
    query = {"$or": [{"is_unassigned": True}, {"owner_id": None}]}
    
    if store_id:
        query["store_id"] = store_id
    if organization_id:
        query["organization_id"] = organization_id
    
    contacts = await db.contacts.find(query).skip(skip).limit(limit).to_list(length=limit)
    total = await db.contacts.count_documents(query)
    
    # Convert ObjectIds
    for contact in contacts:
        contact["_id"] = str(contact["_id"])
    
    return {
        "contacts": contacts,
        "total": total,
        "limit": limit,
        "skip": skip
    }

@router.post("/reassign-contacts")
async def reassign_contacts(
    request: BulkReassignRequest,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Bulk reassign contacts to a new owner"""
    db = get_db()
    
    # Verify new owner exists
    new_owner = await db.users.find_one({"_id": ObjectId(request.new_owner_id)})
    if not new_owner:
        raise HTTPException(status_code=404, detail="New owner not found")
    
    # Convert contact IDs to ObjectIds
    contact_oids = [ObjectId(cid) for cid in request.contact_ids]
    
    # Update contacts
    result = await db.contacts.update_many(
        {"_id": {"$in": contact_oids}},
        {
            "$set": {
                "owner_id": request.new_owner_id,
                "is_unassigned": False,
                "assigned_at": datetime.utcnow(),
                "assigned_by": x_user_id
            },
            "$unset": {
                "unassigned_at": "",
                "unassigned_reason": ""
            }
        }
    )
    
    logger.info(f"Reassigned {result.modified_count} contacts to user {request.new_owner_id}")
    
    return {
        "status": "success",
        "contacts_reassigned": result.modified_count,
        "new_owner": {
            "id": request.new_owner_id,
            "name": new_owner.get("name"),
            "email": new_owner.get("email")
        }
    }

# ============= WEBHOOK CONFIGURATION =============

@router.get("/config")
async def get_webhook_config(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get webhook configuration and URLs for integration setup"""
    
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://app.imosapp.com")
    
    return {
        "webhook_endpoints": {
            "user_created": f"{base_url}/api/webhooks/user-created",
            "user_deleted": f"{base_url}/api/webhooks/user-deleted",
            "contact_created": f"{base_url}/api/webhooks/contact-created"
        },
        "authentication": {
            "method": "header",
            "header_name": "X-Webhook-Secret",
            "description": "Include your webhook secret in the X-Webhook-Secret header"
        },
        "example_payloads": {
            "user_created": {
                "external_id": "salesforce_user_123",
                "email": "newuser@company.com",
                "name": "John Doe",
                "phone": "+15551234567",
                "role": "Sales Rep",
                "store_id": "optional_store_id",
                "metadata": {"department": "Sales", "hire_date": "2024-01-15"}
            },
            "user_deleted": {
                "external_id": "salesforce_user_123",
                "email": "deleteduser@company.com"
            },
            "contact_created": {
                "external_id": "salesforce_contact_456",
                "name": "Jane Smith",
                "phone": "+15559876543",
                "email": "jane@example.com",
                "assigned_to_email": "rep@company.com"
            }
        }
    }

# ============= GENERIC WEBHOOK EVENT =============

@router.post("/event")
async def webhook_generic_event(
    request: Request,
    x_webhook_secret: str = Header(None)
):
    """
    Generic webhook endpoint for custom events.
    Stores the event for processing or triggers custom actions.
    """
    db = get_db()
    
    body = await request.json()
    
    event = {
        "type": body.get("type", "custom"),
        "data": body,
        "received_at": datetime.utcnow(),
        "processed": False,
        "source_ip": request.client.host if request.client else None
    }
    
    result = await db.webhook_events.insert_one(event)
    
    logger.info(f"Received generic webhook event: {body.get('type', 'custom')}")
    
    return {
        "status": "received",
        "event_id": str(result.inserted_id),
        "message": "Event recorded for processing"
    }
