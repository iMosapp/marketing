"""
Group Inboxes & Bulk Transfer Management
- Shared inboxes (same number assigned to multiple users)
- Bulk customer transfers when users leave
"""
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import logging

from routers.database import get_db

router = APIRouter(prefix="/team", tags=["team"])
logger = logging.getLogger(__name__)


# ============= MODELS =============

class SharedInboxCreate(BaseModel):
    name: str
    phone_number: str
    description: Optional[str] = None
    assigned_users: List[str] = []  # List of user IDs


class SharedInboxUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    assigned_users: Optional[List[str]] = None
    is_active: Optional[bool] = None


class BulkTransferRequest(BaseModel):
    from_user_id: str
    to_user_id: str
    transfer_contacts: bool = True
    transfer_conversations: bool = True
    transfer_tasks: bool = True
    transfer_campaigns: bool = True
    tag_filter: Optional[List[str]] = None  # Only transfer contacts with these tags


# ============= SHARED INBOXES =============

@router.post("/inboxes")
async def create_shared_inbox(data: SharedInboxCreate):
    """Create a shared inbox that multiple users can access"""
    db = get_db()
    
    # Check if phone number already exists
    existing = await db.shared_inboxes.find_one({"phone_number": data.phone_number})
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already has a shared inbox")
    
    inbox = {
        "name": data.name,
        "phone_number": data.phone_number,
        "description": data.description,
        "assigned_users": data.assigned_users,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    result = await db.shared_inboxes.insert_one(inbox)
    
    # Update users to include this inbox
    if data.assigned_users:
        await db.users.update_many(
            {"_id": {"$in": [ObjectId(uid) for uid in data.assigned_users]}},
            {"$addToSet": {"shared_inboxes": str(result.inserted_id)}}
        )
    
    logger.info(f"Shared inbox created: {data.name} ({data.phone_number})")
    
    return {
        "id": str(result.inserted_id),
        "message": "Shared inbox created successfully",
    }


@router.get("/inboxes")
async def list_shared_inboxes(
    user_id: Optional[str] = None,
    is_active: bool = True,
):
    """List all shared inboxes, optionally filtered by user"""
    db = get_db()
    
    query = {"is_active": is_active}
    if user_id:
        query["assigned_users"] = user_id
    
    inboxes = await db.shared_inboxes.find(query).to_list(100)
    
    result = []
    for inbox in inboxes:
        # Get assigned user details
        user_ids = inbox.get("assigned_users", [])
        users = []
        if user_ids:
            user_docs = await db.users.find(
                {"_id": {"$in": [ObjectId(uid) for uid in user_ids]}}
            ).to_list(100)
            users = [
                {"id": str(u["_id"]), "name": u.get("name", u.get("email", "Unknown"))}
                for u in user_docs
            ]
        
        # Count unread messages
        unread_count = await db.messages.count_documents({
            "inbox_id": str(inbox["_id"]),
            "is_read": False,
        })
        
        result.append({
            "id": str(inbox["_id"]),
            "name": inbox["name"],
            "phone_number": inbox["phone_number"],
            "description": inbox.get("description"),
            "assigned_users": users,
            "user_count": len(users),
            "unread_count": unread_count,
            "is_active": inbox.get("is_active", True),
            "created_at": inbox["created_at"].isoformat() if inbox.get("created_at") else None,
        })
    
    return result


@router.get("/inboxes/{inbox_id}")
async def get_shared_inbox(inbox_id: str):
    """Get details of a shared inbox"""
    db = get_db()
    
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    # Get assigned user details
    user_ids = inbox.get("assigned_users", [])
    users = []
    if user_ids:
        user_docs = await db.users.find(
            {"_id": {"$in": [ObjectId(uid) for uid in user_ids]}}
        ).to_list(100)
        users = [
            {
                "id": str(u["_id"]), 
                "name": u.get("name", u.get("email", "Unknown")),
                "email": u.get("email"),
                "role": u.get("role"),
            }
            for u in user_docs
        ]
    
    return {
        "id": str(inbox["_id"]),
        "name": inbox["name"],
        "phone_number": inbox["phone_number"],
        "description": inbox.get("description"),
        "assigned_users": users,
        "is_active": inbox.get("is_active", True),
        "created_at": inbox["created_at"].isoformat() if inbox.get("created_at") else None,
        "updated_at": inbox["updated_at"].isoformat() if inbox.get("updated_at") else None,
    }


@router.put("/inboxes/{inbox_id}")
async def update_shared_inbox(inbox_id: str, data: SharedInboxUpdate):
    """Update a shared inbox"""
    db = get_db()
    
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_data["updated_at"] = datetime.utcnow()
    
    # If updating assigned users, also update user records
    if "assigned_users" in update_data:
        # Get current assigned users
        inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
        if inbox:
            old_users = set(inbox.get("assigned_users", []))
            new_users = set(update_data["assigned_users"])
            
            # Remove inbox from users who were removed
            removed_users = old_users - new_users
            if removed_users:
                await db.users.update_many(
                    {"_id": {"$in": [ObjectId(uid) for uid in removed_users]}},
                    {"$pull": {"shared_inboxes": inbox_id}}
                )
            
            # Add inbox to new users
            added_users = new_users - old_users
            if added_users:
                await db.users.update_many(
                    {"_id": {"$in": [ObjectId(uid) for uid in added_users]}},
                    {"$addToSet": {"shared_inboxes": inbox_id}}
                )
    
    result = await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    return {"success": True, "message": "Shared inbox updated"}


@router.post("/inboxes/{inbox_id}/assign")
async def assign_user_to_inbox(inbox_id: str, user_id: str):
    """Add a user to a shared inbox"""
    db = get_db()
    
    # Update inbox
    result = await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {
            "$addToSet": {"assigned_users": user_id},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Shared inbox not found or user already assigned")
    
    # Update user
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {"shared_inboxes": inbox_id}}
    )
    
    logger.info(f"User {user_id} assigned to inbox {inbox_id}")
    
    return {"success": True, "message": "User assigned to inbox"}


@router.post("/inboxes/{inbox_id}/unassign")
async def unassign_user_from_inbox(inbox_id: str, user_id: str):
    """Remove a user from a shared inbox"""
    db = get_db()
    
    # Update inbox
    result = await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {
            "$pull": {"assigned_users": user_id},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    # Update user
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"shared_inboxes": inbox_id}}
    )
    
    logger.info(f"User {user_id} removed from inbox {inbox_id}")
    
    return {"success": True, "message": "User removed from inbox"}


@router.delete("/inboxes/{inbox_id}")
async def delete_shared_inbox(inbox_id: str):
    """Deactivate a shared inbox"""
    db = get_db()
    
    # Get inbox to find assigned users
    inbox = await db.shared_inboxes.find_one({"_id": ObjectId(inbox_id)})
    if not inbox:
        raise HTTPException(status_code=404, detail="Shared inbox not found")
    
    # Remove inbox from all assigned users
    user_ids = inbox.get("assigned_users", [])
    if user_ids:
        await db.users.update_many(
            {"_id": {"$in": [ObjectId(uid) for uid in user_ids]}},
            {"$pull": {"shared_inboxes": inbox_id}}
        )
    
    # Soft delete
    await db.shared_inboxes.update_one(
        {"_id": ObjectId(inbox_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    return {"success": True, "message": "Shared inbox deactivated"}


# ============= BULK TRANSFERS =============

@router.post("/transfer")
async def bulk_transfer_customers(data: BulkTransferRequest):
    """
    Bulk transfer contacts, conversations, tasks from one user to another.
    Used when a team member leaves or changes roles.
    """
    db = get_db()
    
    # Validate users exist
    from_user = await db.users.find_one({"_id": ObjectId(data.from_user_id)})
    to_user = await db.users.find_one({"_id": ObjectId(data.to_user_id)})
    
    if not from_user:
        raise HTTPException(status_code=404, detail="Source user not found")
    if not to_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    
    transfer_log = {
        "from_user_id": data.from_user_id,
        "from_user_name": from_user.get("name", from_user.get("email")),
        "to_user_id": data.to_user_id,
        "to_user_name": to_user.get("name", to_user.get("email")),
        "tag_filter": data.tag_filter,
        "started_at": datetime.utcnow(),
        "results": {},
    }
    
    # Build contact query - only transfer org/store contacts by default
    # Personal contacts belong to the user, not the store
    contact_query = {"user_id": data.from_user_id}
    if not getattr(data, 'include_personal', False):
        contact_query["ownership_type"] = {"$ne": "personal"}
    if data.tag_filter:
        contact_query["tags"] = {"$in": data.tag_filter}
    
    # Transfer contacts (org contacts only by default)
    contacts_transferred = 0
    personal_kept = 0
    if data.transfer_contacts:
        # Count personal contacts being kept
        personal_kept = await db.contacts.count_documents(
            {"user_id": data.from_user_id, "ownership_type": "personal"}
        )
        
        result = await db.contacts.update_many(
            contact_query,
            {
                "$set": {
                    "user_id": data.to_user_id,
                    "transferred_from": data.from_user_id,
                    "transferred_at": datetime.utcnow(),
                }
            }
        )
        contacts_transferred = result.modified_count
        transfer_log["results"]["contacts"] = contacts_transferred
        transfer_log["results"]["personal_kept"] = personal_kept
        logger.info(f"Transferred {contacts_transferred} org contacts from {data.from_user_id} to {data.to_user_id}. {personal_kept} personal contacts kept with original owner.")
    
    # Get transferred contact IDs for related transfers
    transferred_contacts = await db.contacts.find(
        {"user_id": data.to_user_id, "transferred_from": data.from_user_id}
    ).to_list(500)
    contact_ids = [str(c["_id"]) for c in transferred_contacts]
    
    # Transfer conversations
    conversations_transferred = 0
    if data.transfer_conversations and contact_ids:
        result = await db.conversations.update_many(
            {"contact_id": {"$in": contact_ids}},
            {
                "$set": {
                    "user_id": data.to_user_id,
                    "transferred_from": data.from_user_id,
                    "transferred_at": datetime.utcnow(),
                }
            }
        )
        conversations_transferred = result.modified_count
        transfer_log["results"]["conversations"] = conversations_transferred
    
    # Transfer tasks
    tasks_transferred = 0
    if data.transfer_tasks:
        task_query = {"assigned_to": data.from_user_id}
        if contact_ids:
            task_query["$or"] = [
                {"assigned_to": data.from_user_id},
                {"contact_id": {"$in": contact_ids}}
            ]
        
        result = await db.tasks.update_many(
            task_query,
            {
                "$set": {
                    "assigned_to": data.to_user_id,
                    "transferred_from": data.from_user_id,
                    "transferred_at": datetime.utcnow(),
                }
            }
        )
        tasks_transferred = result.modified_count
        transfer_log["results"]["tasks"] = tasks_transferred
    
    # Transfer campaign enrollments
    campaigns_transferred = 0
    if data.transfer_campaigns and contact_ids:
        result = await db.campaign_enrollments.update_many(
            {"contact_id": {"$in": contact_ids}},
            {
                "$set": {
                    "user_id": data.to_user_id,
                    "transferred_from": data.from_user_id,
                    "transferred_at": datetime.utcnow(),
                }
            }
        )
        campaigns_transferred = result.modified_count
        transfer_log["results"]["campaign_enrollments"] = campaigns_transferred
    
    # Save transfer log
    transfer_log["completed_at"] = datetime.utcnow()
    transfer_log["status"] = "completed"
    await db.transfer_logs.insert_one(transfer_log)
    
    return {
        "success": True,
        "message": f"Bulk transfer completed",
        "summary": {
            "from_user": from_user.get("name", from_user.get("email")),
            "to_user": to_user.get("name", to_user.get("email")),
            "contacts_transferred": contacts_transferred,
            "conversations_transferred": conversations_transferred,
            "tasks_transferred": tasks_transferred,
            "campaign_enrollments_transferred": campaigns_transferred,
        }
    }


@router.get("/transfer/history")
async def get_transfer_history(limit: int = 20):
    """Get history of bulk transfers"""
    db = get_db()
    
    logs = await db.transfer_logs.find().sort("started_at", -1).limit(limit).to_list(limit)
    
    return [
        {
            "id": str(log["_id"]),
            "from_user": log.get("from_user_name"),
            "to_user": log.get("to_user_name"),
            "results": log.get("results", {}),
            "tag_filter": log.get("tag_filter"),
            "status": log.get("status"),
            "started_at": log["started_at"].isoformat() if log.get("started_at") else None,
            "completed_at": log["completed_at"].isoformat() if log.get("completed_at") else None,
        }
        for log in logs
    ]


@router.get("/transfer/preview")
async def preview_transfer(
    from_user_id: str,
    tag_filter: Optional[str] = None,
):
    """Preview what will be transferred before executing"""
    db = get_db()
    
    # Build query
    contact_query = {"user_id": from_user_id}
    if tag_filter:
        tags = tag_filter.split(",")
        contact_query["tags"] = {"$in": tags}
    
    # Count items
    contacts_count = await db.contacts.count_documents(contact_query)
    
    # Get contact IDs for related counts
    contacts = await db.contacts.find(contact_query, {"_id": 1}).to_list(500)
    contact_ids = [str(c["_id"]) for c in contacts]
    
    conversations_count = await db.conversations.count_documents(
        {"contact_id": {"$in": contact_ids}}
    ) if contact_ids else 0
    
    tasks_count = await db.tasks.count_documents(
        {"$or": [
            {"assigned_to": from_user_id},
            {"contact_id": {"$in": contact_ids}}
        ]}
    )
    
    campaigns_count = await db.campaign_enrollments.count_documents(
        {"contact_id": {"$in": contact_ids}}
    ) if contact_ids else 0
    
    return {
        "contacts": contacts_count,
        "conversations": conversations_count,
        "tasks": tasks_count,
        "campaign_enrollments": campaigns_count,
        "tag_filter": tag_filter.split(",") if tag_filter else None,
    }


# ============= USER INBOX ACCESS =============

@router.get("/users/{user_id}/inboxes")
async def get_user_inboxes(user_id: str):
    """Get all inboxes a user has access to (personal + shared)"""
    db = get_db()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    inboxes = []
    
    # Personal inbox (user's own number)
    if user.get("phone_number"):
        inboxes.append({
            "id": f"personal_{user_id}",
            "type": "personal",
            "name": "My Inbox",
            "phone_number": user.get("phone_number"),
            "is_primary": True,
        })
    
    # Shared inboxes
    shared_inbox_ids = user.get("shared_inboxes", [])
    if shared_inbox_ids:
        shared = await db.shared_inboxes.find({
            "_id": {"$in": [ObjectId(sid) for sid in shared_inbox_ids]},
            "is_active": True,
        }).to_list(100)
        
        for inbox in shared:
            inboxes.append({
                "id": str(inbox["_id"]),
                "type": "shared",
                "name": inbox["name"],
                "phone_number": inbox["phone_number"],
                "description": inbox.get("description"),
                "user_count": len(inbox.get("assigned_users", [])),
                "is_primary": False,
            })
    
    return inboxes
