"""
Public API v1 - Full RESTful API for 3rd party CRM integrations
All endpoints require API key authentication via X-API-Key header
Exposes every data point: contacts, users, messages, campaigns, reviews, tags, etc.
"""
from fastapi import APIRouter, HTTPException, Header, Query, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging
import secrets

from .database import get_db

router = APIRouter(prefix="/v1", tags=["Public API v1"])
logger = logging.getLogger(__name__)


# ============= API KEY AUTH =============

async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key and return the associated org/user context"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    
    db = get_db()
    
    # Check api_keys collection
    key_doc = await db.api_keys.find_one({"key": x_api_key, "is_active": True})
    if not key_doc:
        # Also check org-level api_key
        org = await db.organizations.find_one({"api_key": x_api_key})
        if not org:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return {"org_id": str(org["_id"]), "scope": "organization", "org_name": org.get("name")}
    
    # Update last used
    await db.api_keys.update_one({"_id": key_doc["_id"]}, {"$set": {"last_used": datetime.utcnow()}, "$inc": {"usage_count": 1}})
    
    return {
        "org_id": key_doc.get("organization_id"),
        "store_id": key_doc.get("store_id"),
        "user_id": key_doc.get("created_by"),
        "scope": key_doc.get("scope", "full"),
        "name": key_doc.get("name"),
    }


def serialize(doc):
    """Convert MongoDB doc to JSON-safe dict"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, dict):
                result[k] = serialize(v)
            elif isinstance(v, list):
                result[k] = [serialize(i) if isinstance(i, (dict, ObjectId)) else i for i in v]
            else:
                result[k] = v
        return result
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc


# ============= API KEY MANAGEMENT =============

class ApiKeyCreate(BaseModel):
    name: str
    scope: str = "full"  # full, read_only, contacts_only, messages_only

@router.post("/api-keys")
async def create_api_key(
    data: ApiKeyCreate,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Generate a new API key for 3rd party integrations"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(x_user_id)}) if x_user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    key = f"imos_{secrets.token_urlsafe(32)}"
    
    doc = {
        "key": key,
        "name": data.name,
        "scope": data.scope,
        "created_by": x_user_id,
        "organization_id": user.get("organization_id"),
        "store_id": user.get("store_id"),
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_used": None,
        "usage_count": 0,
    }
    
    await db.api_keys.insert_one(doc)
    return {"api_key": key, "name": data.name, "scope": data.scope, "message": "Store this key securely — it won't be shown again"}

@router.get("/api-keys")
async def list_api_keys(x_user_id: str = Header(None, alias="X-User-ID")):
    """List all API keys (key value masked)"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(x_user_id)}) if x_user_id else None
    query = {"organization_id": user.get("organization_id")} if user else {"created_by": x_user_id}
    
    keys = await db.api_keys.find(query).to_list(50)
    result = []
    for k in keys:
        result.append({
            "id": str(k["_id"]),
            "name": k.get("name"),
            "scope": k.get("scope"),
            "key_preview": k["key"][:10] + "...",
            "is_active": k.get("is_active", True),
            "created_at": k.get("created_at", "").isoformat() if isinstance(k.get("created_at"), datetime) else "",
            "last_used": k.get("last_used", "").isoformat() if isinstance(k.get("last_used"), datetime) else None,
            "usage_count": k.get("usage_count", 0),
        })
    return {"api_keys": result}

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Revoke an API key"""
    db = get_db()
    result = await db.api_keys.update_one({"_id": ObjectId(key_id)}, {"$set": {"is_active": False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key revoked"}


# ============= CONTACTS =============

@router.get("/contacts")
async def api_list_contacts(
    auth: dict = Depends(verify_api_key),
    search: Optional[str] = None,
    tag: Optional[str] = None,
    source: Optional[str] = None,
    ownership_type: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    """List contacts with filtering, search, and pagination"""
    db = get_db()
    query: dict = {"status": {"$ne": "hidden"}}
    
    if auth.get("org_id"):
        # Get all stores in org
        stores = await db.stores.find({"organization_id": auth["org_id"]}).to_list(100)
        store_ids = [str(s["_id"]) for s in stores]
        users = await db.users.find({"organization_id": auth["org_id"]}).to_list(500)
        user_ids = [str(u["_id"]) for u in users]
        query["$or"] = [{"user_id": {"$in": user_ids}}, {"store_id": {"$in": store_ids}}]
    
    if search:
        query["$and"] = query.get("$and", []) + [{"$or": [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]}]
    if tag:
        query["tags"] = tag
    if source:
        query["source"] = source
    if ownership_type:
        query["ownership_type"] = ownership_type
    
    total = await db.contacts.count_documents(query)
    contacts = await db.contacts.find(query, {"photo": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    return {"contacts": serialize(contacts), "total": total, "limit": limit, "offset": offset}

@router.get("/contacts/{contact_id}")
async def api_get_contact(contact_id: str, auth: dict = Depends(verify_api_key)):
    """Get a single contact with all details"""
    db = get_db()
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"photo": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return serialize(contact)

@router.post("/contacts")
async def api_create_contact(data: dict, auth: dict = Depends(verify_api_key)):
    """Create a new contact via API"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    data["source"] = data.get("source", "api")
    data["ownership_type"] = data.get("ownership_type", "org")
    data["status"] = "active"
    data["tags"] = data.get("tags", [])
    
    result = await db.contacts.insert_one(data)
    contact_id = str(result.inserted_id)
    
    # Fire webhook
    await fire_webhook_event("contact.created", {"contact_id": contact_id, **{k: v for k, v in data.items() if k != "_id"}}, org_id=auth.get("org_id"))
    
    return {"id": contact_id, "message": "Contact created"}

@router.put("/contacts/{contact_id}")
async def api_update_contact(contact_id: str, data: dict, auth: dict = Depends(verify_api_key)):
    """Update a contact"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    data["updated_at"] = datetime.utcnow()
    data.pop("_id", None)
    
    result = await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$set": data})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    await fire_webhook_event("contact.updated", {"contact_id": contact_id, "changes": data}, org_id=auth.get("org_id"))
    return {"message": "Contact updated"}

@router.delete("/contacts/{contact_id}")
async def api_delete_contact(contact_id: str, auth: dict = Depends(verify_api_key)):
    """Soft-delete a contact"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    result = await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$set": {"status": "hidden", "hidden_at": datetime.utcnow()}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    await fire_webhook_event("contact.deleted", {"contact_id": contact_id}, org_id=auth.get("org_id"))
    return {"message": "Contact deleted"}


# ============= USERS =============

@router.get("/users")
async def api_list_users(
    auth: dict = Depends(verify_api_key),
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List users in the org"""
    db = get_db()
    query: dict = {}
    if auth.get("org_id"):
        query["organization_id"] = auth["org_id"]
    if role:
        query["role"] = role
    if status:
        query["status"] = status
    
    total = await db.users.count_documents(query)
    users = await db.users.find(query, {"password": 0}).sort("name", 1).skip(offset).limit(limit).to_list(limit)
    
    return {"users": serialize(users), "total": total, "limit": limit, "offset": offset}

@router.get("/users/{user_id}")
async def api_get_user(user_id: str, auth: dict = Depends(verify_api_key)):
    """Get a single user with all details (password excluded)"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize(user)

@router.get("/users/{user_id}/contacts")
async def api_get_user_contacts(user_id: str, auth: dict = Depends(verify_api_key), limit: int = 100, offset: int = 0):
    """Get all contacts belonging to a specific user"""
    db = get_db()
    query = {"user_id": user_id, "status": {"$ne": "hidden"}}
    total = await db.contacts.count_documents(query)
    contacts = await db.contacts.find(query, {"photo": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"contacts": serialize(contacts), "total": total}

@router.get("/users/{user_id}/stats")
async def api_get_user_stats(user_id: str, auth: dict = Depends(verify_api_key)):
    """Get user activity stats"""
    db = get_db()
    contacts = await db.contacts.count_documents({"user_id": user_id, "status": {"$ne": "hidden"}})
    messages = await db.messages.count_documents({"user_id": user_id})
    campaigns = await db.campaign_enrollments.count_documents({"user_id": user_id})
    
    return {"user_id": user_id, "contacts": contacts, "messages_sent": messages, "campaigns_active": campaigns}


# ============= MESSAGES / CONVERSATIONS =============

@router.get("/conversations")
async def api_list_conversations(
    auth: dict = Depends(verify_api_key),
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List conversations"""
    db = get_db()
    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    if status:
        query["status"] = status
    
    total = await db.conversations.count_documents(query)
    convos = await db.conversations.find(query).sort("last_message_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"conversations": serialize(convos), "total": total}

@router.get("/conversations/{convo_id}/messages")
async def api_get_conversation_messages(convo_id: str, auth: dict = Depends(verify_api_key), limit: int = 100):
    """Get all messages in a conversation"""
    db = get_db()
    messages = await db.messages.find({"conversation_id": convo_id}).sort("timestamp", 1).limit(limit).to_list(limit)
    return {"messages": serialize(messages)}

@router.post("/messages")
async def api_send_message(data: dict, auth: dict = Depends(verify_api_key)):
    """Send a message (SMS or email) via API"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    required = ["to", "content", "user_id"]
    for field in required:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    msg = {
        "user_id": data["user_id"],
        "to": data["to"],
        "content": data["content"],
        "sender": "user",
        "mode": data.get("mode", "sms"),
        "timestamp": datetime.utcnow(),
        "status": "queued",
        "source": "api",
    }
    
    result = await db.messages.insert_one(msg)
    await fire_webhook_event("message.sent", {"message_id": str(result.inserted_id), "to": data["to"]}, org_id=auth.get("org_id"))
    
    return {"message_id": str(result.inserted_id), "status": "queued"}


# ============= CAMPAIGNS =============

@router.get("/campaigns")
async def api_list_campaigns(auth: dict = Depends(verify_api_key), limit: int = 50, offset: int = 0):
    """List all campaign templates"""
    db = get_db()
    total = await db.campaigns.count_documents({})
    campaigns = await db.campaigns.find({}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"campaigns": serialize(campaigns), "total": total}

@router.get("/campaigns/{campaign_id}")
async def api_get_campaign(campaign_id: str, auth: dict = Depends(verify_api_key)):
    """Get campaign details including enrollment stats"""
    db = get_db()
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    enrolled = await db.campaign_enrollments.count_documents({"campaign_id": campaign_id})
    completed = await db.campaign_enrollments.count_documents({"campaign_id": campaign_id, "status": "completed"})
    
    result = serialize(campaign)
    result["stats"] = {"enrolled": enrolled, "completed": completed}
    return result

@router.get("/campaigns/{campaign_id}/enrollments")
async def api_get_campaign_enrollments(campaign_id: str, auth: dict = Depends(verify_api_key), limit: int = 100):
    """Get all enrollments for a campaign"""
    db = get_db()
    enrollments = await db.campaign_enrollments.find({"campaign_id": campaign_id}).to_list(limit)
    return {"enrollments": serialize(enrollments)}


# ============= REVIEWS =============

@router.get("/reviews")
async def api_list_reviews(
    auth: dict = Depends(verify_api_key),
    status: Optional[str] = None,
    store_id: Optional[str] = None,
    limit: int = 50, offset: int = 0,
):
    """List reviews with filtering"""
    db = get_db()
    query: dict = {}
    if status:
        query["status"] = status
    if store_id:
        query["store_id"] = store_id
    
    total = await db.reviews.count_documents(query)
    reviews = await db.reviews.find(query).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"reviews": serialize(reviews), "total": total}


# ============= TAGS =============

@router.get("/tags")
async def api_list_tags(auth: dict = Depends(verify_api_key)):
    """List all tags"""
    db = get_db()
    tags = await db.tags.find({}).to_list(500)
    return {"tags": serialize(tags)}

@router.post("/contacts/{contact_id}/tags")
async def api_add_tag(contact_id: str, data: dict, auth: dict = Depends(verify_api_key)):
    """Add a tag to a contact"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    tag = data.get("tag")
    if not tag:
        raise HTTPException(status_code=400, detail="tag field required")
    
    result = await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$addToSet": {"tags": tag}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found or tag already exists")
    
    await fire_webhook_event("tag.added", {"contact_id": contact_id, "tag": tag}, org_id=auth.get("org_id"))
    return {"message": f"Tag '{tag}' added"}

@router.delete("/contacts/{contact_id}/tags/{tag}")
async def api_remove_tag(contact_id: str, tag: str, auth: dict = Depends(verify_api_key)):
    """Remove a tag from a contact"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$pull": {"tags": tag}})
    await fire_webhook_event("tag.removed", {"contact_id": contact_id, "tag": tag}, org_id=auth.get("org_id"))
    return {"message": f"Tag '{tag}' removed"}


# ============= ORGANIZATIONS & STORES =============

@router.get("/organizations")
async def api_list_organizations(auth: dict = Depends(verify_api_key)):
    """List organizations"""
    db = get_db()
    query = {"_id": ObjectId(auth["org_id"])} if auth.get("org_id") else {}
    orgs = await db.organizations.find(query, {"logo_url": 0}).to_list(100)
    return {"organizations": serialize(orgs)}

@router.get("/stores")
async def api_list_stores(auth: dict = Depends(verify_api_key)):
    """List stores, optionally filtered by org"""
    db = get_db()
    query = {}
    if auth.get("org_id"):
        query["organization_id"] = auth["org_id"]
    stores = await db.stores.find(query, {"logo_url": 0, "brand_kit.logo_url": 0}).to_list(100)
    return {"stores": serialize(stores)}


# ============= ACTIVITY / EVENTS =============

@router.get("/contacts/{contact_id}/events")
async def api_get_contact_events(contact_id: str, auth: dict = Depends(verify_api_key), limit: int = 100):
    """Get activity timeline for a contact"""
    db = get_db()
    events = await db.contact_events.find({"contact_id": contact_id}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"events": serialize(events)}

@router.post("/contacts/{contact_id}/events")
async def api_log_contact_event(contact_id: str, data: dict, auth: dict = Depends(verify_api_key)):
    """Log a custom event to a contact's timeline"""
    db = get_db()
    
    event = {
        "contact_id": contact_id,
        "event_type": data.get("event_type", "custom"),
        "description": data.get("description", ""),
        "metadata": data.get("metadata", {}),
        "source": "api",
        "timestamp": datetime.utcnow(),
    }
    
    result = await db.contact_events.insert_one(event)
    return {"event_id": str(result.inserted_id), "message": "Event logged"}


# ============= NOTES =============

@router.post("/contacts/{contact_id}/notes")
async def api_add_note(contact_id: str, data: dict, auth: dict = Depends(verify_api_key)):
    """Add a note to a contact"""
    db = get_db()
    from .webhook_subscriptions import fire_webhook_event
    
    note = data.get("note", "")
    result = await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"notes": note, "updated_at": datetime.utcnow()}}
    )
    
    await fire_webhook_event("note.added", {"contact_id": contact_id}, org_id=auth.get("org_id"))
    return {"message": "Note added"}


# ============= BULK OPERATIONS =============

@router.post("/contacts/bulk-tag")
async def api_bulk_tag(data: dict, auth: dict = Depends(verify_api_key)):
    """Add a tag to multiple contacts at once"""
    db = get_db()
    contact_ids = data.get("contact_ids", [])
    tag = data.get("tag")
    if not contact_ids or not tag:
        raise HTTPException(status_code=400, detail="contact_ids and tag required")
    
    oids = [ObjectId(cid) for cid in contact_ids]
    result = await db.contacts.update_many({"_id": {"$in": oids}}, {"$addToSet": {"tags": tag}})
    return {"tagged": result.modified_count}

@router.post("/contacts/bulk-assign")
async def api_bulk_assign(data: dict, auth: dict = Depends(verify_api_key)):
    """Reassign multiple contacts to a new user"""
    db = get_db()
    contact_ids = data.get("contact_ids", [])
    user_id = data.get("user_id")
    if not contact_ids or not user_id:
        raise HTTPException(status_code=400, detail="contact_ids and user_id required")
    
    oids = [ObjectId(cid) for cid in contact_ids]
    result = await db.contacts.update_many({"_id": {"$in": oids}}, {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}})
    return {"assigned": result.modified_count}


# ============= EXPORT =============

@router.get("/export/contacts")
async def api_export_contacts(auth: dict = Depends(verify_api_key), format: str = "json"):
    """Export all contacts (for CRM migration/sync)"""
    db = get_db()
    query: dict = {"status": {"$ne": "hidden"}}
    if auth.get("org_id"):
        stores = await db.stores.find({"organization_id": auth["org_id"]}).to_list(100)
        store_ids = [str(s["_id"]) for s in stores]
        users = await db.users.find({"organization_id": auth["org_id"]}).to_list(500)
        user_ids = [str(u["_id"]) for u in users]
        query["$or"] = [{"user_id": {"$in": user_ids}}, {"store_id": {"$in": store_ids}}]
    
    contacts = await db.contacts.find(query, {"photo": 0}).to_list(10000)
    return {"contacts": serialize(contacts), "total": len(contacts), "exported_at": datetime.utcnow().isoformat()}
