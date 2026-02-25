"""
Team Chat Router - Internal messaging system for organizations
Supports channels, DMs, @mentions, and broadcasts
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from routers.database import get_db

router = APIRouter(prefix="/team-chat", tags=["team-chat"])

# ============ MODELS ============

class CreateChannelRequest(BaseModel):
    name: str
    description: Optional[str] = None
    channel_type: str  # 'org', 'store', 'custom', 'dm'
    organization_id: Optional[str] = None
    store_id: Optional[str] = None
    member_ids: Optional[List[str]] = None  # For custom groups
    created_by: str

class SendMessageRequest(BaseModel):
    channel_id: str
    sender_id: str
    content: str
    mentions: Optional[List[str]] = None  # User IDs mentioned
    is_broadcast: bool = False

class AddMembersRequest(BaseModel):
    channel_id: str
    member_ids: List[str]
    added_by: str

# ============ CHANNELS ============

@router.post("/channels")
async def create_channel(request: CreateChannelRequest):
    """Create a new channel (org-wide, store, or custom group)"""
    db = get_db()
    
    # Validate creator exists
    try:
        creator = await db.users.find_one({"_id": ObjectId(request.created_by)})
    except:
        creator = None
    
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    
    # Build member list based on channel type
    members = []
    
    if request.channel_type == 'org':
        # Org-wide: all users in the organization
        if not request.organization_id:
            raise HTTPException(status_code=400, detail="Organization ID required for org channels")
        
        org_users = await db.users.find({
            "organization_id": request.organization_id,
            "is_active": {"$ne": False}
        }).to_list(1000)
        members = [str(u["_id"]) for u in org_users]
        
    elif request.channel_type == 'store':
        # Store channel: all users in that store
        if not request.store_id:
            raise HTTPException(status_code=400, detail="Store ID required for store channels")
        
        store_users = await db.users.find({
            "store_id": request.store_id,
            "is_active": {"$ne": False}
        }).to_list(1000)
        members = [str(u["_id"]) for u in store_users]
        
    elif request.channel_type == 'custom':
        # Custom group: manually selected members
        if not request.member_ids:
            raise HTTPException(status_code=400, detail="Member IDs required for custom channels")
        members = request.member_ids
        
    elif request.channel_type == 'dm':
        # Direct message: exactly 2 members
        if not request.member_ids or len(request.member_ids) != 2:
            raise HTTPException(status_code=400, detail="DM requires exactly 2 members")
        
        # Check if DM already exists between these users
        existing_dm = await db.team_channels.find_one({
            "channel_type": "dm",
            "members": {"$all": request.member_ids, "$size": 2}
        })
        
        if existing_dm:
            return {
                "success": True,
                "channel_id": str(existing_dm["_id"]),
                "existing": True
            }
        
        members = request.member_ids
    
    # Ensure creator is in members
    if request.created_by not in members:
        members.append(request.created_by)
    
    # Create channel document
    channel_doc = {
        "name": request.name,
        "description": request.description,
        "channel_type": request.channel_type,
        "organization_id": request.organization_id,
        "store_id": request.store_id,
        "members": members,
        "created_by": request.created_by,
        "created_at": datetime.now(timezone.utc),
        "last_message_at": None,
        "is_active": True
    }
    
    result = await db.team_channels.insert_one(channel_doc)
    
    return {
        "success": True,
        "channel_id": str(result.inserted_id),
        "member_count": len(members)
    }


@router.get("/channels")
async def get_user_channels(user_id: str):
    """Get all channels a user is a member of"""
    db = get_db()
    
    # Get user info
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        user = None
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find all channels user is a member of
    channels = await db.team_channels.find({
        "members": user_id,
        "is_active": True
    }).sort("last_message_at", -1).to_list(100)
    
    result = []
    for channel in channels:
        # Get last message preview
        last_message = await db.team_messages.find_one(
            {"channel_id": str(channel["_id"])},
            sort=[("created_at", -1)]
        )
        
        # Get unread count
        user_read = await db.team_read_status.find_one({
            "channel_id": str(channel["_id"]),
            "user_id": user_id
        })
        last_read = user_read.get("last_read_at") if user_read else None
        
        unread_query = {"channel_id": str(channel["_id"])}
        if last_read:
            unread_query["created_at"] = {"$gt": last_read}
        unread_count = await db.team_messages.count_documents(unread_query)
        
        # For DMs, get the other person's info
        channel_name = channel["name"]
        channel_avatar = None
        if channel["channel_type"] == "dm":
            other_id = [m for m in channel["members"] if m != user_id]
            if other_id:
                other_user = await db.users.find_one({"_id": ObjectId(other_id[0])})
                if other_user:
                    channel_name = other_user.get("name", "Unknown")
                    channel_avatar = other_user.get("photo_url")
        
        result.append({
            "id": str(channel["_id"]),
            "name": channel_name,
            "description": channel.get("description"),
            "channel_type": channel["channel_type"],
            "member_count": len(channel["members"]),
            "avatar": channel_avatar,
            "last_message": {
                "content": last_message.get("content", "")[:50] if last_message else None,
                "sender_name": last_message.get("sender_name") if last_message else None,
                "created_at": last_message.get("created_at").isoformat() if last_message and last_message.get("created_at") else None
            } if last_message else None,
            "unread_count": unread_count,
            "last_message_at": channel.get("last_message_at").isoformat() if channel.get("last_message_at") else None
        })
    
    return {"success": True, "channels": result}


@router.get("/channels/{channel_id}")
async def get_channel_details(channel_id: str):
    """Get channel details including members"""
    db = get_db()
    
    try:
        channel = await db.team_channels.find_one({"_id": ObjectId(channel_id)})
    except:
        channel = None
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get member details
    members = []
    for member_id in channel.get("members", []):
        try:
            user = await db.users.find_one({"_id": ObjectId(member_id)})
            if user:
                members.append({
                    "id": str(user["_id"]),
                    "name": user.get("name", "Unknown"),
                    "role": user.get("role", "user"),
                    "photo_url": user.get("photo_url"),
                    "is_online": False  # Could implement presence later
                })
        except:
            continue
    
    return {
        "success": True,
        "channel": {
            "id": str(channel["_id"]),
            "name": channel["name"],
            "description": channel.get("description"),
            "channel_type": channel["channel_type"],
            "members": members,
            "created_at": channel["created_at"].isoformat() if channel.get("created_at") else None
        }
    }


@router.post("/channels/{channel_id}/members")
async def add_channel_members(channel_id: str, request: AddMembersRequest):
    """Add members to a channel"""
    db = get_db()
    
    try:
        channel = await db.team_channels.find_one({"_id": ObjectId(channel_id)})
    except:
        channel = None
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Add new members
    current_members = set(channel.get("members", []))
    new_members = set(request.member_ids)
    updated_members = list(current_members | new_members)
    
    await db.team_channels.update_one(
        {"_id": ObjectId(channel_id)},
        {"$set": {"members": updated_members}}
    )
    
    return {
        "success": True,
        "added_count": len(new_members - current_members),
        "total_members": len(updated_members)
    }


# ============ MESSAGES ============

@router.post("/messages")
async def send_message(request: SendMessageRequest):
    """Send a message to a channel"""
    db = get_db()
    
    # Validate channel
    try:
        channel = await db.team_channels.find_one({"_id": ObjectId(request.channel_id)})
    except:
        channel = None
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Validate sender is a member
    if request.sender_id not in channel.get("members", []):
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    
    # Get sender info
    try:
        sender = await db.users.find_one({"_id": ObjectId(request.sender_id)})
    except:
        sender = None
    
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    
    # Create message
    message_doc = {
        "channel_id": request.channel_id,
        "sender_id": request.sender_id,
        "sender_name": sender.get("name", "Unknown"),
        "sender_photo": sender.get("photo_url"),
        "content": request.content,
        "mentions": request.mentions or [],
        "is_broadcast": request.is_broadcast,
        "created_at": datetime.now(timezone.utc),
        "edited_at": None,
        "is_deleted": False
    }
    
    result = await db.team_messages.insert_one(message_doc)
    
    # Update channel last_message_at
    await db.team_channels.update_one(
        {"_id": ObjectId(request.channel_id)},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    # Create notifications for mentioned users
    if request.mentions:
        for mentioned_id in request.mentions:
            if mentioned_id != request.sender_id:
                notification_doc = {
                    "user_id": mentioned_id,
                    "type": "team_mention",
                    "title": f"{sender.get('name', 'Someone')} mentioned you",
                    "body": request.content[:100],
                    "channel_id": request.channel_id,
                    "message_id": str(result.inserted_id),
                    "created_at": datetime.now(timezone.utc),
                    "read": False
                }
                await db.notifications.insert_one(notification_doc)
    
    # If broadcast, notify all members
    if request.is_broadcast:
        for member_id in channel.get("members", []):
            if member_id != request.sender_id:
                notification_doc = {
                    "user_id": member_id,
                    "type": "team_broadcast",
                    "title": f"📢 {sender.get('name', 'Someone')} sent a broadcast",
                    "body": request.content[:100],
                    "channel_id": request.channel_id,
                    "message_id": str(result.inserted_id),
                    "created_at": datetime.now(timezone.utc),
                    "read": False
                }
                await db.notifications.insert_one(notification_doc)
    
    return {
        "success": True,
        "message_id": str(result.inserted_id),
        "created_at": message_doc["created_at"].isoformat()
    }


@router.get("/messages/{channel_id}")
async def get_channel_messages(
    channel_id: str,
    user_id: str,
    limit: int = Query(50, le=100),
    before: Optional[str] = None
):
    """Get messages from a channel"""
    db = get_db()
    
    # Validate channel and membership
    try:
        channel = await db.team_channels.find_one({"_id": ObjectId(channel_id)})
    except:
        channel = None
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if user_id not in channel.get("members", []):
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    
    # Build query
    query = {"channel_id": channel_id, "is_deleted": False}
    if before:
        try:
            before_date = datetime.fromisoformat(before.replace('Z', '+00:00'))
            query["created_at"] = {"$lt": before_date}
        except:
            pass
    
    # Get messages
    messages = await db.team_messages.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Update read status
    await db.team_read_status.update_one(
        {"channel_id": channel_id, "user_id": user_id},
        {"$set": {"last_read_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    result = []
    for msg in reversed(messages):  # Reverse to get chronological order
        result.append({
            "id": str(msg["_id"]),
            "sender_id": msg["sender_id"],
            "sender_name": msg.get("sender_name", "Unknown"),
            "sender_photo": msg.get("sender_photo"),
            "content": msg["content"],
            "mentions": msg.get("mentions", []),
            "is_broadcast": msg.get("is_broadcast", False),
            "created_at": msg["created_at"].isoformat() if msg.get("created_at") else None
        })
    
    return {"success": True, "messages": result}


# ============ MEMBERS SEARCH ============

@router.get("/members/search")
async def search_members(
    user_id: str,
    query: str = "",
    role_filter: Optional[str] = None
):
    """Search for users to add to channels or mention"""
    db = get_db()
    
    # Get requesting user's org
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        user = None
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build search query
    search_query = {"is_active": {"$ne": False}}
    
    # Filter by organization
    if user.get("organization_id"):
        search_query["organization_id"] = user["organization_id"]
    
    # Filter by role if specified
    if role_filter:
        search_query["role"] = role_filter
    
    # Text search on name/email
    if query:
        search_query["$or"] = [
            {"name": {"$regex": query, "$options": "i"}},
            {"email": {"$regex": query, "$options": "i"}}
        ]
    
    users = await db.users.find(search_query).limit(50).to_list(50)
    
    result = []
    for u in users:
        result.append({
            "id": str(u["_id"]),
            "name": u.get("name", "Unknown"),
            "email": u.get("email"),
            "role": u.get("role", "user"),
            "store_id": u.get("store_id"),
            "photo_url": u.get("photo_url")
        })
    
    return {"success": True, "members": result}


# ============ QUICK ACTIONS ============

@router.post("/broadcast")
async def send_broadcast(
    sender_id: str,
    content: str,
    recipient_type: str,  # 'org', 'store', 'role', 'custom'
    organization_id: Optional[str] = None,
    store_id: Optional[str] = None,
    role_filter: Optional[str] = None,
    recipient_ids: Optional[List[str]] = None
):
    """Send a broadcast message to multiple users"""
    db = get_db()
    
    # Get sender
    try:
        sender = await db.users.find_one({"_id": ObjectId(sender_id)})
    except:
        sender = None
    
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    
    # Build recipient list based on type
    recipients = []
    
    if recipient_type == 'org' and organization_id:
        org_users = await db.users.find({
            "organization_id": organization_id,
            "is_active": {"$ne": False}
        }).to_list(1000)
        recipients = [str(u["_id"]) for u in org_users]
        
    elif recipient_type == 'store' and store_id:
        store_users = await db.users.find({
            "store_id": store_id,
            "is_active": {"$ne": False}
        }).to_list(500)
        recipients = [str(u["_id"]) for u in store_users]
        
    elif recipient_type == 'role' and role_filter:
        role_users = await db.users.find({
            "role": role_filter,
            "is_active": {"$ne": False}
        }).to_list(500)
        if organization_id:
            role_users = [u for u in role_users if u.get("organization_id") == organization_id]
        recipients = [str(u["_id"]) for u in role_users]
        
    elif recipient_type == 'custom' and recipient_ids:
        recipients = recipient_ids
    
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients found")
    
    # Create notifications for all recipients
    notifications_created = 0
    for recipient_id in recipients:
        if recipient_id != sender_id:
            notification_doc = {
                "user_id": recipient_id,
                "type": "team_broadcast",
                "title": f"📢 Broadcast from {sender.get('name', 'Unknown')}",
                "body": content[:200],
                "sender_id": sender_id,
                "created_at": datetime.now(timezone.utc),
                "read": False
            }
            await db.notifications.insert_one(notification_doc)
            notifications_created += 1
    
    return {
        "success": True,
        "recipients_count": len(recipients),
        "notifications_sent": notifications_created
    }



# ============ DELETE / CLEAR HISTORY ============

@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str, user_id: str):
    """Delete a channel and all its messages. Only channel creator or admins can delete."""
    db = get_db()

    try:
        channel = await db.team_channels.find_one({"_id": ObjectId(channel_id)})
    except:
        channel = None

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check permission: creator or admin
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_creator = channel.get("created_by") == user_id
    is_admin = user.get("role") in ("super_admin", "org_admin", "store_manager")

    if not is_creator and not is_admin:
        raise HTTPException(status_code=403, detail="Only the channel creator or an admin can delete this channel")

    # Delete all messages in the channel
    msg_result = await db.team_messages.delete_many({"channel_id": channel_id})
    # Delete read status records
    await db.team_read_status.delete_many({"channel_id": channel_id})
    # Delete the channel itself
    await db.team_channels.delete_one({"_id": ObjectId(channel_id)})

    return {
        "success": True,
        "messages_deleted": msg_result.deleted_count,
        "message": "Channel and all messages deleted"
    }


@router.delete("/channels/{channel_id}/messages")
async def clear_channel_history(channel_id: str, user_id: str):
    """Clear all message history in a channel. Only creator or admins can clear."""
    db = get_db()

    try:
        channel = await db.team_channels.find_one({"_id": ObjectId(channel_id)})
    except:
        channel = None

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_creator = channel.get("created_by") == user_id
    is_admin = user.get("role") in ("super_admin", "org_admin", "store_manager")

    if not is_creator and not is_admin:
        raise HTTPException(status_code=403, detail="Only the channel creator or an admin can clear history")

    result = await db.team_messages.delete_many({"channel_id": channel_id})

    return {
        "success": True,
        "messages_deleted": result.deleted_count,
        "message": "Chat history cleared"
    }
