"""
Shared Inboxes & Bulk Customer Transfers Router

Features:
1. Shared Inboxes - Assign multiple users to a single phone number/inbox
2. Bulk Customer Transfers - Transfer all contacts/conversations from one user to another
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/admin/team", tags=["Shared Inboxes & Transfers"])
logger = logging.getLogger(__name__)


# ============= PYDANTIC MODELS =============

class SharedInboxCreate(BaseModel):
    name: str
    phone_number: str
    description: Optional[str] = None
    assigned_user_ids: List[str] = []


class SharedInboxUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    description: Optional[str] = None
    assigned_user_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    va_profile_id: Optional[str] = None    # VA persona from VA Library
    va_prompt_override: Optional[str] = None  # Custom prompt for this inbox
    receives_demo_requests: Optional[bool] = None  # Route website leads to this inbox


class BulkTransferRequest(BaseModel):
    from_user_id: str
    to_user_id: str
    transfer_contacts: bool = True
    transfer_conversations: bool = True
    transfer_tasks: bool = True
    transfer_campaigns: bool = True
    reason: Optional[str] = None


# ============= SHARED INBOX ENDPOINTS =============

@router.post("/shared-inboxes")
async def create_shared_inbox(inbox: SharedInboxCreate, user_id: str):
    """Create a new shared inbox that multiple users can access"""
    db = get_db()
    
    # Verify user is admin
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if phone number already exists
    existing = await db.shared_inboxes.find_one({"phone_number": inbox.phone_number})
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already assigned to an inbox")
    
    # Create the shared inbox
    inbox_doc = {
        "name": inbox.name,
        "phone_number": inbox.phone_number,
        "description": inbox.description,
        "assigned_user_ids": inbox.assigned_user_ids,
        "organization_id": user.get('organization_id'),
        "store_id": user.get('store_id'),
        "account_id": user.get('account_id') or str(user['_id']),  # Account-level scoping
        "created_by": user_id,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.shared_inboxes.insert_one(inbox_doc)
    
    # Update assigned users to have this inbox reference
    if inbox.assigned_user_ids:
        await db.users.update_many(
            {"_id": {"$in": [ObjectId(uid) for uid in inbox.assigned_user_ids]}},
            {"$addToSet": {"shared_inbox_ids": str(result.inserted_id)}}
        )
    
    return {
        "id": str(result.inserted_id),
        "message": f"Shared inbox '{inbox.name}' created with {len(inbox.assigned_user_ids)} assigned users"
    }


@router.get("/shared-inboxes")
async def list_shared_inboxes(user_id: str):
    """List all shared inboxes accessible to the user"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build filter based on role — always exclude deleted/inactive inboxes
    role = user.get('role', 'user')
    base_filter = {"is_active": {"$ne": False}}   # exclude soft-deleted

    if role == 'super_admin':
        query = {**base_filter}
    elif role == 'org_admin':
        query = {"organization_id": user.get('organization_id'), **base_filter}
    elif role == 'store_manager':
        query = {"store_id": user.get('store_id'), **base_filter}
    else:
        # Regular users see inboxes they're assigned to
        query = {"assigned_user_ids": user_id, **base_filter}
    
    inboxes = await db.shared_inboxes.find(query).to_list(100)
    
    result = []
    for inbox in inboxes:
        # Get assigned user names
        assigned_users = []
        for uid in inbox.get('assigned_user_ids', []):
            u = await get_user_by_id(uid)
            if u:
                assigned_users.append({
                    "id": uid,
                    "name": u.get('name', 'Unknown'),
                    "email": u.get('email', '')
                })
        
        result.append({
            "id": str(inbox['_id']),
            "name": inbox.get('name'),
            "phone_number": inbox.get('phone_number'),
            "description": inbox.get('description'),
            "assigned_users": assigned_users,
            "is_active": inbox.get('is_active', True),
            "va_profile_id": inbox.get('va_profile_id', ''),
            "va_prompt_override": inbox.get('va_prompt_override', ''),
            "receives_demo_requests": inbox.get('receives_demo_requests', False),
            "created_at": inbox.get('created_at').isoformat() if inbox.get('created_at') else None
        })
    
    return result


@router.get("/shared-inboxes/{inbox_id}")
async def get_shared_inbox(inbox_id: str, user_id: str):
    """Get details of a specific shared inbox"""
    db = get_db()
    
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    # Get assigned user details
    assigned_users = []
    for uid in inbox.get('assigned_user_ids', []):
        u = await get_user_by_id(uid)
        if u:
            assigned_users.append({
                "id": uid,
                "name": u.get('name', 'Unknown'),
                "email": u.get('email', ''),
                "role": u.get('role', 'user')
            })
    
    # Get conversation count for this inbox
    conv_count = await db.conversations.count_documents({
        "shared_inbox_id": inbox_id
    })
    
    return {
        "id": str(inbox['_id']),
        "name": inbox.get('name'),
        "phone_number": inbox.get('phone_number'),
        "description": inbox.get('description'),
        "assigned_users": assigned_users,
        "conversation_count": conv_count,
        "is_active": inbox.get('is_active', True),
        "created_at": inbox.get('created_at').isoformat() if inbox.get('created_at') else None,
        "updated_at": inbox.get('updated_at').isoformat() if inbox.get('updated_at') else None
    }


@router.put("/shared-inboxes/{inbox_id}")
async def update_shared_inbox(inbox_id: str, update: SharedInboxUpdate, user_id: str):
    """Update a shared inbox - add/remove users, change settings"""
    db = get_db()
    
    # Verify admin access
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    update_dict = {"updated_at": datetime.utcnow()}
    
    if update.name is not None:
        update_dict['name'] = update.name
    if update.phone_number is not None:
        update_dict['phone_number'] = update.phone_number
    if update.description is not None:
        update_dict['description'] = update.description
    if update.is_active is not None:
        update_dict['is_active'] = update.is_active
    if update.va_profile_id is not None:
        update_dict['va_profile_id'] = update.va_profile_id
    if update.va_prompt_override is not None:
        update_dict['va_prompt_override'] = update.va_prompt_override
    if update.receives_demo_requests is not None:
        # Only one inbox can be the website lead receiver — clear others first
        if update.receives_demo_requests:
            await db.shared_inboxes.update_many(
                {"_id": {"$ne": ObjectId(inbox_id)}},
                {"$set": {"receives_demo_requests": False}}
            )
        update_dict['receives_demo_requests'] = update.receives_demo_requests
    
    # Handle user assignment changes
    if update.assigned_user_ids is not None:
        old_users = set(inbox.get('assigned_user_ids', []))
        new_users = set(update.assigned_user_ids)
        
        # Users to remove
        removed = old_users - new_users
        if removed:
            await db.users.update_many(
                {"_id": {"$in": [ObjectId(uid) for uid in removed]}},
                {"$pull": {"shared_inbox_ids": inbox_id}}
            )
        
        # Users to add
        added = new_users - old_users
        if added:
            await db.users.update_many(
                {"_id": {"$in": [ObjectId(uid) for uid in added]}},
                {"$addToSet": {"shared_inbox_ids": inbox_id}}
            )
        
        update_dict['assigned_user_ids'] = update.assigned_user_ids
    
    await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {"$set": update_dict}
    )
    
    return {"message": "Shared inbox updated successfully"}


@router.post("/shared-inboxes/{inbox_id}/webhook")
async def inbox_webhook(inbox_id: str, request: Request):
    """
    Webhook endpoint for receiving leads from external sources (website forms, etc).
    Include this URL in your web form or CRM integration.
    Accepts JSON: { first_name, last_name, phone, email, message, vehicle, source }
    """
    import asyncio as _aio
    db = get_db()

    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox or inbox.get('is_active') is False:
        raise HTTPException(status_code=404, detail="Inbox not found or inactive")

    try:
        data = await request.json()
    except Exception:
        data = {}

    first_name  = data.get('first_name', '')
    last_name   = data.get('last_name', '')
    phone       = data.get('phone') or data.get('phone_number') or ''
    email       = data.get('email', '')
    message     = data.get('message', '')
    vehicle     = data.get('vehicle') or data.get('vehicle_interest', '')
    source_name = data.get('source') or inbox.get('name', 'Inbox Lead')

    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")

    full_name = f"{first_name} {last_name}".strip() or "New Lead"

    # Route to the lead intake system
    from routers.lead_intake import process_inbound_lead as _pil
    from routers.lead_sources import hydrate_intake_text

    # Find or create the matching lead source
    source = {
        "_id":          inbox["_id"],
        "name":         inbox.get("name"),
        "phone_number": inbox.get("phone_number"),
        "intake_text":  inbox.get("intake_text", ""),
        "workflow_user_ids": inbox.get("assigned_user_ids", []),
        "notify_all_on_intake": True,
        "auto_call_on_claim": inbox.get("auto_call_on_claim", False),
        "va_enabled":   True,
        "va_prompt_override": inbox.get("va_prompt_override"),
    }

    normalized = {
        "first_name":     first_name,
        "last_name":      last_name,
        "full_name":      full_name,
        "phone":          phone,
        "email":          email,
        "vehicle_interest": vehicle,
        "comments":       message,
    }

    try:
        result = await _pil(
            normalized=normalized,
            source=source,
            raw_data=data,
        )
        logger.info(f"[InboxWebhook] Lead {full_name} routed to {inbox.get('name')}")
        return {"success": True, "lead_id": str(result.get('_id', '')), "message": "Lead received"}
    except Exception as e:
        logger.error(f"[InboxWebhook] Failed: {e}")
        # Fallback: create contact + conversation manually
        try:
            from datetime import datetime as _dt
            from routers.twilio_webhooks import normalize_phone
            phone_e164 = normalize_phone(phone)
            # Create contact
            contact = await db.contacts.find_one({"phone": phone_e164})
            if not contact:
                res = await db.contacts.insert_one({
                    "phone": phone_e164, "first_name": first_name, "last_name": last_name,
                    "name": full_name, "email": email, "source": source_name,
                    "tags": ["Inbound Lead"], "status": "active",
                    "created_at": _dt.utcnow(),
                })
                contact_id = str(res.inserted_id)
            else:
                contact_id = str(contact["_id"])
            # Notify assigned users
            from routers.lead_sources import hydrate_intake_text
            intake_text = inbox.get("intake_text", "")
            for uid in inbox.get("assigned_user_ids", []):
                await db.notifications.insert_one({
                    "user_id": uid, "type": "new_lead", "priority": "urgent",
                    "title": f"New Lead: {full_name}", "message": vehicle or source_name,
                    "contact_id": contact_id, "read": False, "created_at": _dt.utcnow(),
                })
            return {"success": True, "contact_id": contact_id, "message": "Lead received (fallback)"}
        except Exception as fb_err:
            raise HTTPException(status_code=500, detail=f"Lead intake failed: {fb_err}")


@router.get("/shared-inboxes/{inbox_id}/webhook-info")
async def get_webhook_info(inbox_id: str, user_id: str):
    """Return the webhook URL and example payload for this inbox."""
    db = get_db()
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    import os
    base = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    webhook_url = f"{base}/api/admin/team/shared-inboxes/{inbox_id}/webhook"
    return {
        "webhook_url": webhook_url,
        "method": "POST",
        "content_type": "application/json",
        "example_payload": {
            "first_name": "John",
            "last_name": "Smith",
            "phone": "+18015551234",
            "email": "john@email.com",
            "vehicle": "2024 Ford F-150",
            "message": "Interested in this truck",
            "source": inbox.get("name", "Website"),
        }
    }


@router.delete("/shared-inboxes/{inbox_id}")
async def delete_shared_inbox(inbox_id: str, user_id: str):
    """Delete (deactivate) a shared inbox"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    # Remove inbox reference from all assigned users
    await db.users.update_many(
        {"shared_inbox_ids": inbox_id},
        {"$pull": {"shared_inbox_ids": inbox_id}}
    )

    # Hard delete — user expects it to disappear immediately
    await db.shared_inboxes.delete_one({"_id": ObjectId(inbox_id)})

    return {"message": "Shared inbox deleted", "id": inbox_id}


@router.post("/shared-inboxes/{inbox_id}/assign")
async def assign_user_to_inbox(inbox_id: str, target_user_id: str, user_id: str):
    """Assign a single user to a shared inbox"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Verify inbox exists
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    # Verify target user exists
    target_user = await get_user_by_id(target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    
    # Add user to inbox
    await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {"$addToSet": {"assigned_user_ids": target_user_id}}
    )
    
    # Add inbox to user
    await db.users.update_one(
        {"_id": ObjectId(target_user_id)},
        {"$addToSet": {"shared_inbox_ids": inbox_id}}
    )
    
    return {
        "message": f"{target_user.get('name')} assigned to {inbox.get('name')}"
    }


@router.post("/shared-inboxes/{inbox_id}/unassign")
async def unassign_user_from_inbox(inbox_id: str, target_user_id: str, user_id: str):
    """Remove a user from a shared inbox"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Remove user from inbox
    await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {"$pull": {"assigned_user_ids": target_user_id}}
    )
    
    # Remove inbox from user
    await db.users.update_one(
        {"_id": ObjectId(target_user_id)},
        {"$pull": {"shared_inbox_ids": inbox_id}}
    )
    
    return {"message": "User removed from shared inbox"}


# ============= BULK CUSTOMER TRANSFER ENDPOINTS =============

@router.post("/bulk-transfer")
async def initiate_bulk_transfer(transfer: BulkTransferRequest, user_id: str):
    """
    Transfer all customer data from one user to another.
    Used when an employee leaves or changes roles.
    """
    db = get_db()
    
    # Verify admin access
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Verify both users exist
    from_user = await get_user_by_id(transfer.from_user_id)
    to_user = await get_user_by_id(transfer.to_user_id)
    
    if not from_user:
        raise HTTPException(status_code=404, detail="Source user not found")
    if not to_user:
        raise HTTPException(status_code=404, detail="Destination user not found")
    
    # Track what we're transferring
    transfer_log = {
        "from_user_id": transfer.from_user_id,
        "from_user_name": from_user.get('name'),
        "to_user_id": transfer.to_user_id,
        "to_user_name": to_user.get('name'),
        "initiated_by": user_id,
        "initiated_by_name": user.get('name'),
        "reason": transfer.reason,
        "started_at": datetime.utcnow(),
        "status": "in_progress",
        "transfers": {}
    }
    
    # Transfer contacts
    if transfer.transfer_contacts:
        result = await db.contacts.update_many(
            {"user_id": transfer.from_user_id},
            {"$set": {
                "user_id": transfer.to_user_id,
                "transferred_from": transfer.from_user_id,
                "transferred_at": datetime.utcnow()
            }}
        )
        transfer_log['transfers']['contacts'] = result.modified_count
    
    # Transfer conversations
    if transfer.transfer_conversations:
        result = await db.conversations.update_many(
            {"user_id": transfer.from_user_id},
            {"$set": {
                "user_id": transfer.to_user_id,
                "transferred_from": transfer.from_user_id,
                "transferred_at": datetime.utcnow()
            }}
        )
        transfer_log['transfers']['conversations'] = result.modified_count
    
    # Transfer tasks
    if transfer.transfer_tasks:
        result = await db.tasks.update_many(
            {"user_id": transfer.from_user_id},
            {"$set": {
                "user_id": transfer.to_user_id,
                "transferred_from": transfer.from_user_id,
                "transferred_at": datetime.utcnow()
            }}
        )
        transfer_log['transfers']['tasks'] = result.modified_count
    
    # Transfer campaign enrollments
    if transfer.transfer_campaigns:
        result = await db.campaign_enrollments.update_many(
            {"user_id": transfer.from_user_id},
            {"$set": {
                "user_id": transfer.to_user_id,
                "transferred_from": transfer.from_user_id,
                "transferred_at": datetime.utcnow()
            }}
        )
        transfer_log['transfers']['campaign_enrollments'] = result.modified_count
    
    # Mark transfer as completed
    transfer_log['status'] = "completed"
    transfer_log['completed_at'] = datetime.utcnow()
    
    # Save transfer log
    await db.bulk_transfers.insert_one(transfer_log)
    
    # Update user stats
    total_transferred = sum(transfer_log['transfers'].values())
    
    return {
        "message": f"Successfully transferred {total_transferred} items from {from_user.get('name')} to {to_user.get('name')}",
        "details": transfer_log['transfers'],
        "from_user": from_user.get('name'),
        "to_user": to_user.get('name')
    }


@router.get("/bulk-transfer/history")
async def get_transfer_history(user_id: str, limit: int = 20):
    """Get history of bulk transfers"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    transfers = await db.bulk_transfers.find({}).sort("started_at", -1).limit(limit).to_list(limit)
    
    result = []
    for t in transfers:
        result.append({
            "id": str(t['_id']),
            "from_user": t.get('from_user_name'),
            "to_user": t.get('to_user_name'),
            "initiated_by": t.get('initiated_by_name'),
            "reason": t.get('reason'),
            "transfers": t.get('transfers', {}),
            "status": t.get('status'),
            "started_at": t.get('started_at').isoformat() if t.get('started_at') else None,
            "completed_at": t.get('completed_at').isoformat() if t.get('completed_at') else None
        })
    
    return result


@router.get("/bulk-transfer/preview")
async def preview_bulk_transfer(from_user_id: str, user_id: str):
    """Preview what would be transferred without actually doing it"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from_user = await get_user_by_id(from_user_id)
    if not from_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Count items that would be transferred
    contacts_count = await db.contacts.count_documents({"user_id": from_user_id})
    conversations_count = await db.conversations.count_documents({"user_id": from_user_id})
    tasks_count = await db.tasks.count_documents({"user_id": from_user_id})
    enrollments_count = await db.campaign_enrollments.count_documents({"user_id": from_user_id})
    
    return {
        "from_user": {
            "id": from_user_id,
            "name": from_user.get('name'),
            "email": from_user.get('email')
        },
        "items_to_transfer": {
            "contacts": contacts_count,
            "conversations": conversations_count,
            "tasks": tasks_count,
            "campaign_enrollments": enrollments_count
        },
        "total": contacts_count + conversations_count + tasks_count + enrollments_count
    }


# ============= USER LISTING FOR ASSIGNMENT =============

@router.get("/users")
async def list_users_for_assignment(user_id: str, search: Optional[str] = None):
    """List users available for inbox assignment or transfer"""
    db = get_db()
    
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build filter — primary: account_id; fallback: org/store for legacy data
    role     = user.get('role', 'user')
    acct_id  = user.get('account_id') or str(user['_id'])
    org_id   = user.get('organization_id')
    store_id = user.get('store_id')
    # Note: do NOT exclude self — admins should be able to add themselves to inboxes
    query    = {}

    if role not in ('super_admin', 'org_admin', 'store_manager'):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Prefer account_id scope; fall back to org/store for legacy users
    query['$or'] = [
        {"account_id": acct_id},
        *(
            [{"organization_id": org_id}] if org_id else
            [{"store_id": store_id}] if store_id else
            [{"organization_id": {"$in": [None, ""]}, "account_id": {"$exists": False}}]
        ),
    ]

    # Only show active users
    query['status'] = {'$ne': 'deactivated'}
    
    # Add search filter
    if search:
        query['$or'] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    users = await db.users.find(query, {"password": 0}).limit(50).to_list(50)
    
    result = []
    for u in users:
        result.append({
            "id": str(u['_id']),
            "name": u.get('name', 'Unknown'),
            "email": u.get('email', ''),
            "role": u.get('role', 'user'),
            "phone": u.get('phone', ''),
            "shared_inbox_ids": u.get('shared_inbox_ids', [])
        })
    
    return result
