"""
Tags router - handles contact tag management
Supports organization-level tags with approval workflow
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
import logging

from routers.database import get_db, get_data_filter, get_user_by_id

router = APIRouter(prefix="/tags", tags=["Tags"])
logger = logging.getLogger(__name__)

# Default tag colors
DEFAULT_COLORS = [
    "#FF3B30",  # Red
    "#FF9500",  # Orange
    "#FFCC00",  # Yellow
    "#34C759",  # Green
    "#007AFF",  # Blue
    "#5856D6",  # Purple
    "#AF52DE",  # Magenta
    "#FF2D55",  # Pink
    "#00C7BE",  # Teal
    "#8E8E93",  # Gray
]

# Default tags for new users/orgs
DEFAULT_TAGS = [
    {"name": "Hot Lead", "color": "#FF3B30", "icon": "flame"},
    {"name": "VIP", "color": "#FFD60A", "icon": "star"},
    {"name": "New Customer", "color": "#34C759", "icon": "person-add"},
    {"name": "Follow Up", "color": "#007AFF", "icon": "refresh"},
    {"name": "Service Due", "color": "#FF9500", "icon": "construct"},
]


async def get_tag_scope(user_id: str):
    """Determine if tags should be user-level or org-level"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return None, None, False
    
    org_id = user.get("org_id")
    role = user.get("role", "user")
    is_admin = role in ["super_admin", "org_admin", "admin"]
    
    return org_id, role, is_admin


@router.get("/{user_id}")
async def get_tags(user_id: str):
    """Get all tags for a user (org-level if in org, user-level otherwise)"""
    db = get_db()
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if org_id:
        # Organization-level tags - get approved tags for the org
        query = {"org_id": org_id, "status": "approved"}
        tags = await db.tags.find(query).sort("name", 1).to_list(200)
    else:
        # User-level tags
        tags = await db.tags.find({"user_id": user_id}).sort("name", 1).to_list(100)
    
    # If no tags exist, create defaults
    if not tags:
        for default in DEFAULT_TAGS:
            tag = {
                **default,
                "contact_count": 0,
                "created_at": datetime.utcnow(),
                "status": "approved",
            }
            if org_id:
                tag["org_id"] = org_id
                tag["created_by"] = user_id
            else:
                tag["user_id"] = user_id
            
            result = await db.tags.insert_one(tag)
            tag["_id"] = str(result.inserted_id)
            tags.append(tag)
    else:
        for tag in tags:
            tag["_id"] = str(tag["_id"])
    
    # Update contact counts
    for tag in tags:
        if org_id:
            # Count across org users
            org_users = await db.users.find({"org_id": org_id}, {"_id": 1}).limit(500).to_list(500)
            org_user_ids = [str(u["_id"]) for u in org_users]
            count = await db.contacts.count_documents({
                "user_id": {"$in": org_user_ids},
                "tags": tag["name"]
            })
        else:
            count = await db.contacts.count_documents({
                "user_id": user_id,
                "tags": tag["name"]
            })
        tag["contact_count"] = count
    
    return tags


@router.get("/{user_id}/pending")
async def get_pending_tags(user_id: str):
    """Get pending tags awaiting approval (org admins only)"""
    db = get_db()
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if not org_id:
        return []  # No pending tags for individual users
    
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can view pending tags")
    
    tags = await db.tags.find({
        "org_id": org_id,
        "status": "pending"
    }).sort("created_at", -1).to_list(100)
    
    # Add creator info
    for tag in tags:
        tag["_id"] = str(tag["_id"])
        if tag.get("created_by"):
            creator = await db.users.find_one({"_id": ObjectId(tag["created_by"])}, {"name": 1})
            tag["creator_name"] = creator.get("name", "Unknown") if creator else "Unknown"
    
    return tags


@router.post("/{user_id}")
async def create_tag(user_id: str, tag_data: dict):
    """Create a new tag (requires approval in orgs)"""
    db = get_db()
    
    name = tag_data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name is required")
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if org_id:
        # Organization tag - check for duplicates across org
        existing = await db.tags.find_one({
            "org_id": org_id,
            "name": {"$regex": f"^{name}$", "$options": "i"},
            "status": {"$in": ["approved", "pending"]}
        })
        if existing:
            if existing["status"] == "pending":
                raise HTTPException(status_code=400, detail="A tag with this name is already pending approval")
            raise HTTPException(status_code=400, detail="Tag with this name already exists")
        
        # Determine status - admins auto-approve, others go to pending
        status = "approved" if is_admin else "pending"
        
        tag = {
            "org_id": org_id,
            "name": name,
            "color": tag_data.get("color", DEFAULT_COLORS[0]),
            "icon": tag_data.get("icon", "pricetag"),
            "status": status,
            "created_by": user_id,
            "created_at": datetime.utcnow(),
        }
    else:
        # Individual user tag - no approval needed
        existing = await db.tags.find_one({"user_id": user_id, "name": name})
        if existing:
            raise HTTPException(status_code=400, detail="Tag with this name already exists")
        
        tag = {
            "user_id": user_id,
            "name": name,
            "color": tag_data.get("color", DEFAULT_COLORS[0]),
            "icon": tag_data.get("icon", "pricetag"),
            "status": "approved",
            "created_at": datetime.utcnow(),
        }
    
    result = await db.tags.insert_one(tag)
    tag["_id"] = str(result.inserted_id)
    tag["contact_count"] = 0
    
    return tag


@router.post("/{user_id}/approve/{tag_id}")
async def approve_tag(user_id: str, tag_id: str):
    """Approve a pending tag (org admins only)"""
    db = get_db()
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if not org_id or not is_admin:
        raise HTTPException(status_code=403, detail="Only org admins can approve tags")
    
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "org_id": org_id,
        "status": "pending"
    })
    
    if not tag:
        raise HTTPException(status_code=404, detail="Pending tag not found")
    
    await db.tags.update_one(
        {"_id": ObjectId(tag_id)},
        {"$set": {
            "status": "approved",
            "approved_by": user_id,
            "approved_at": datetime.utcnow()
        }}
    )
    
    logger.info(f"Tag '{tag['name']}' approved by {user_id}")
    return {"message": f"Tag '{tag['name']}' approved"}


@router.post("/{user_id}/reject/{tag_id}")
async def reject_tag(user_id: str, tag_id: str):
    """Reject a pending tag (org admins only)"""
    db = get_db()
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if not org_id or not is_admin:
        raise HTTPException(status_code=403, detail="Only org admins can reject tags")
    
    tag = await db.tags.find_one({
        "_id": ObjectId(tag_id),
        "org_id": org_id,
        "status": "pending"
    })
    
    if not tag:
        raise HTTPException(status_code=404, detail="Pending tag not found")
    
    # Delete the rejected tag
    await db.tags.delete_one({"_id": ObjectId(tag_id)})
    
    logger.info(f"Tag '{tag['name']}' rejected by {user_id}")
    return {"message": f"Tag '{tag['name']}' rejected"}


@router.put("/{user_id}/{tag_id}")
async def update_tag(user_id: str, tag_id: str, tag_data: dict):
    """Update a tag (org admins only for org tags)"""
    db = get_db()
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if org_id:
        # Org tag - admin only
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only admins can edit tags")
        
        old_tag = await db.tags.find_one({"_id": ObjectId(tag_id), "org_id": org_id})
    else:
        old_tag = await db.tags.find_one({"_id": ObjectId(tag_id), "user_id": user_id})
    
    if not old_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    old_name = old_tag["name"]
    new_name = tag_data.get("name", old_name).strip()
    
    # Update tag
    update_dict = {
        "name": new_name,
        "color": tag_data.get("color", old_tag.get("color")),
        "icon": tag_data.get("icon", old_tag.get("icon")),
        "updated_at": datetime.utcnow(),
    }
    
    await db.tags.update_one(
        {"_id": ObjectId(tag_id)},
        {"$set": update_dict}
    )
    
    # If name changed, update all contacts with this tag
    if old_name != new_name:
        if org_id:
            org_users = await db.users.find({"org_id": org_id}, {"_id": 1}).limit(500).to_list(500)
            org_user_ids = [str(u["_id"]) for u in org_users]
            await db.contacts.update_many(
                {"user_id": {"$in": org_user_ids}, "tags": old_name},
                {"$set": {"tags.$": new_name}}
            )
        else:
            await db.contacts.update_many(
                {"user_id": user_id, "tags": old_name},
                {"$set": {"tags.$": new_name}}
            )
    
    # Return updated tag
    tag = await db.tags.find_one({"_id": ObjectId(tag_id)})
    tag["_id"] = str(tag["_id"])
    tag["contact_count"] = 0  # Will be calculated by frontend
    
    return tag


@router.delete("/{user_id}/{tag_id}")
async def delete_tag(user_id: str, tag_id: str, remove_from_contacts: bool = True):
    """Delete a tag (org admins only for org tags)"""
    db = get_db()
    
    org_id, role, is_admin = await get_tag_scope(user_id)
    
    if org_id:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only admins can delete tags")
        
        tag = await db.tags.find_one({"_id": ObjectId(tag_id), "org_id": org_id})
    else:
        tag = await db.tags.find_one({"_id": ObjectId(tag_id), "user_id": user_id})
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    tag_name = tag["name"]
    
    # Remove tag from all contacts if requested
    if remove_from_contacts:
        if org_id:
            org_users = await db.users.find({"org_id": org_id}, {"_id": 1}).limit(500).to_list(500)
            org_user_ids = [str(u["_id"]) for u in org_users]
            await db.contacts.update_many(
                {"user_id": {"$in": org_user_ids}, "tags": tag_name},
                {"$pull": {"tags": tag_name}}
            )
        else:
            await db.contacts.update_many(
                {"user_id": user_id, "tags": tag_name},
                {"$pull": {"tags": tag_name}}
            )
    
    await db.tags.delete_one({"_id": ObjectId(tag_id)})
    
    return {"message": f"Tag '{tag_name}' deleted"}


@router.get("/{user_id}/colors")
async def get_tag_colors(user_id: str):
    """Get available tag colors"""
    return {"colors": DEFAULT_COLORS}


@router.post("/{user_id}/assign")
async def assign_tag_to_contacts(user_id: str, data: dict):
    """Assign a tag to multiple contacts"""
    db = get_db()
    
    tag_name = data.get("tag_name")
    contact_ids = data.get("contact_ids", [])
    
    if not tag_name:
        raise HTTPException(status_code=400, detail="tag_name is required")
    
    if not contact_ids:
        raise HTTPException(status_code=400, detail="contact_ids is required")
    
    org_id, _, _ = await get_tag_scope(user_id)
    
    # Verify tag exists and is approved
    if org_id:
        tag = await db.tags.find_one({"org_id": org_id, "name": tag_name, "status": "approved"})
    else:
        tag = await db.tags.find_one({"user_id": user_id, "name": tag_name})
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Add tag to contacts
    result = await db.contacts.update_many(
        {
            "_id": {"$in": [ObjectId(cid) for cid in contact_ids]},
            "tags": {"$ne": tag_name}
        },
        {"$push": {"tags": tag_name}}
    )
    
    return {"message": f"Tag assigned to {result.modified_count} contacts"}


@router.post("/{user_id}/remove")
async def remove_tag_from_contacts(user_id: str, data: dict):
    """Remove a tag from multiple contacts"""
    db = get_db()
    
    tag_name = data.get("tag_name")
    contact_ids = data.get("contact_ids", [])
    
    if not tag_name:
        raise HTTPException(status_code=400, detail="tag_name is required")
    
    if not contact_ids:
        raise HTTPException(status_code=400, detail="contact_ids is required")
    
    result = await db.contacts.update_many(
        {"_id": {"$in": [ObjectId(cid) for cid in contact_ids]}},
        {"$pull": {"tags": tag_name}}
    )
    
    return {"message": f"Tag removed from {result.modified_count} contacts"}


@router.get("/{user_id}/contacts/{tag_name}")
async def get_contacts_by_tag(user_id: str, tag_name: str):
    """Get all contacts with a specific tag"""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    
    contacts = await db.contacts.find({
        "$and": [base_filter, {"tags": tag_name}]
    }).sort("first_name", 1).limit(500).to_list(500)
    
    for contact in contacts:
        contact["_id"] = str(contact["_id"])
    
    return contacts
