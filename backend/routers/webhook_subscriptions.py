"""
Outgoing Webhook System - Fires events to registered 3rd party endpoints
when actions happen in iMOs (contact created, message sent, deal closed, etc.)
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import httpx
import logging
import asyncio

from .database import get_db

router = APIRouter(prefix="/webhook-subscriptions", tags=["Webhook Subscriptions"])
logger = logging.getLogger(__name__)

# ============= MODELS =============

EVENT_TYPES = [
    "contact.created", "contact.updated", "contact.deleted", "contact.tagged",
    "message.sent", "message.received",
    "campaign.enrolled", "campaign.completed", "campaign.step_sent",
    "review.submitted", "review.approved",
    "congrats.sent",
    "user.created", "user.deactivated", "user.reactivated",
    "deal.closed",
    "call.logged",
    "note.added",
    "tag.added", "tag.removed",
    "appointment.created",
]

class WebhookSubscription(BaseModel):
    url: str
    events: List[str]  # List of event types to subscribe to, or ["*"] for all
    secret: Optional[str] = None  # Shared secret for HMAC verification
    description: Optional[str] = None
    is_active: bool = True

class WebhookSubscriptionUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ============= SUBSCRIPTION MANAGEMENT =============

@router.get("/events")
async def list_event_types():
    """List all available webhook event types"""
    return {"event_types": EVENT_TYPES}

@router.post("/")
async def create_subscription(
    sub: WebhookSubscription,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Register a new webhook subscription"""
    db = get_db()
    
    # Validate event types
    for event in sub.events:
        if event != "*" and event not in EVENT_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event}")
    
    # Get user's org context
    user = await db.users.find_one({"_id": ObjectId(x_user_id)}) if x_user_id else None
    
    doc = {
        "url": sub.url,
        "events": sub.events,
        "secret": sub.secret,
        "description": sub.description,
        "is_active": sub.is_active,
        "created_by": x_user_id,
        "organization_id": user.get("organization_id") if user else None,
        "store_id": user.get("store_id") if user else None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "failure_count": 0,
        "last_triggered": None,
        "last_status": None,
    }
    
    result = await db.webhook_subscriptions.insert_one(doc)
    return {"id": str(result.inserted_id), "message": "Webhook subscription created"}

@router.get("/")
async def list_subscriptions(x_user_id: str = Header(None, alias="X-User-ID")):
    """List all webhook subscriptions for the user's org"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(x_user_id)}) if x_user_id else None
    
    query = {}
    if user and user.get("organization_id"):
        query["organization_id"] = user["organization_id"]
    elif x_user_id:
        query["created_by"] = x_user_id
    
    subs = await db.webhook_subscriptions.find(query, {"secret": 0}).to_list(100)
    for s in subs:
        s["_id"] = str(s["_id"])
    return {"subscriptions": subs}

@router.put("/{sub_id}")
async def update_subscription(sub_id: str, update: WebhookSubscriptionUpdate):
    """Update a webhook subscription"""
    db = get_db()
    update_dict = {k: v for k, v in update.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.webhook_subscriptions.update_one(
        {"_id": ObjectId(sub_id)},
        {"$set": update_dict}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription updated"}

@router.delete("/{sub_id}")
async def delete_subscription(sub_id: str):
    """Delete a webhook subscription"""
    db = get_db()
    result = await db.webhook_subscriptions.delete_one({"_id": ObjectId(sub_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription deleted"}

@router.get("/{sub_id}/logs")
async def get_subscription_logs(sub_id: str, limit: int = 50):
    """Get recent delivery logs for a webhook subscription"""
    db = get_db()
    logs = await db.webhook_logs.find(
        {"subscription_id": sub_id}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    for l in logs:
        l["_id"] = str(l["_id"])
    return {"logs": logs}


# ============= EVENT DISPATCHER =============

async def fire_webhook_event(event_type: str, payload: dict, org_id: str = None, store_id: str = None):
    """
    Fire a webhook event to all matching subscriptions.
    Called from other routers when events occur.
    """
    db = get_db()
    if db is None:
        return
    
    try:
        # Find matching active subscriptions
        query = {
            "is_active": True,
            "$or": [
                {"events": event_type},
                {"events": "*"},
            ]
        }
        if org_id:
            query["$or"] = [
                {"organization_id": org_id},
                {"organization_id": None},
                {"organization_id": {"$exists": False}},
            ]
        
        subs = await db.webhook_subscriptions.find(query).to_list(50)
        
        if not subs:
            return
        
        event_data = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }
        
        # Fire all webhooks concurrently
        tasks = [_deliver_webhook(db, sub, event_data) for sub in subs]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except Exception as e:
        logger.error(f"Webhook dispatch error for {event_type}: {e}")


async def _deliver_webhook(db, subscription: dict, event_data: dict):
    """Deliver a single webhook with retry and logging"""
    sub_id = str(subscription["_id"])
    url = subscription["url"]
    
    headers = {"Content-Type": "application/json", "X-iMOs-Event": event_data["event"]}
    
    # Add HMAC signature if secret is configured
    if subscription.get("secret"):
        import hashlib, hmac, json
        body = json.dumps(event_data, default=str).encode()
        sig = hmac.new(subscription["secret"].encode(), body, hashlib.sha256).hexdigest()
        headers["X-iMOs-Signature"] = f"sha256={sig}"
    
    status_code = None
    error_msg = None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=event_data, headers=headers)
            status_code = resp.status_code
            
            if resp.status_code >= 400:
                error_msg = resp.text[:500]
                # Increment failure count
                await db.webhook_subscriptions.update_one(
                    {"_id": subscription["_id"]},
                    {"$inc": {"failure_count": 1}, "$set": {"last_status": status_code, "last_triggered": datetime.utcnow()}}
                )
            else:
                # Reset failure count on success
                await db.webhook_subscriptions.update_one(
                    {"_id": subscription["_id"]},
                    {"$set": {"failure_count": 0, "last_status": status_code, "last_triggered": datetime.utcnow()}}
                )
    except Exception as e:
        error_msg = str(e)[:500]
        await db.webhook_subscriptions.update_one(
            {"_id": subscription["_id"]},
            {"$inc": {"failure_count": 1}, "$set": {"last_status": "error", "last_triggered": datetime.utcnow()}}
        )
    
    # Log delivery attempt
    await db.webhook_logs.insert_one({
        "subscription_id": sub_id,
        "event": event_data["event"],
        "url": url,
        "status_code": status_code,
        "error": error_msg,
        "timestamp": datetime.utcnow(),
    })
