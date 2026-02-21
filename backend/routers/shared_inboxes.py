"""
Shared Inboxes & Bulk Customer Transfers Router

Features:
1. Shared Inboxes - Assign multiple users to a single phone number/inbox
2. Bulk Customer Transfers - Transfer all contacts/conversations from one user to another
"""
from fastapi import APIRouter, HTTPException
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
    description: Optional[str] = None
    assigned_user_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None


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
    
    # Build filter based on role
    role = user.get('role', 'user')
    if role == 'super_admin':
        query = {}
    elif role == 'org_admin':
        query = {"organization_id": user.get('organization_id')}
    elif role == 'store_manager':
        query = {"store_id": user.get('store_id')}
    else:
        # Regular users see inboxes they're assigned to
        query = {"assigned_user_ids": user_id}
    
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
    if update.description is not None:
        update_dict['description'] = update.description
    if update.is_active is not None:
        update_dict['is_active'] = update.is_active
    
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
    
    # Soft delete - mark as inactive
    await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {"$set": {"is_active": False, "deleted_at": datetime.utcnow()}}
    )
    
    return {"message": "Shared inbox deactivated"}


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
    
    # Build filter based on role
    role = user.get('role', 'user')
    query = {"_id": {"$ne": ObjectId(user_id)}}  # Exclude self
    
    if role == 'org_admin':
        query['organization_id'] = user.get('organization_id')
    elif role == 'store_manager':
        query['store_id'] = user.get('store_id')
    elif role != 'super_admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
