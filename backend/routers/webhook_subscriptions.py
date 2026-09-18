"""Outgoing webhooks: tenant-scoped subscriptions + signed delivery.
Events are produced by services/webhook_outbox.py (change feed, every 60s) and by explicit test pings.
Collection: webhook_subscriptions {url, events[], secret, description, is_active, store_id, organization_id, created_by}."""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
import hashlib
import hmac
import json
import logging
import uuid
import httpx

from .database import get_db

router = APIRouter(prefix="/webhook-subscriptions", tags=["Webhook Subscriptions"])
logger = logging.getLogger(__name__)

# Single source of truth for the event catalog (public API, Integrations screen and docs all read this).
EVENT_TYPES = {
    "contact.created": "A contact was added: in the app, by CSV import, from a lead source, or through the API",
    "contact.updated": "Contact fields, tags, vehicle, notes or owner changed (payload is the full contact)",
    "contact.deleted": "A contact was removed or hidden",
    "message.sent": "A rep, a campaign or Jessi sent a text or email to a customer",
    "message.received": "A customer texted or emailed back",
    "call.logged": "A call ended; includes duration, outcome, transcript and AI summary when available",
    "note.added": "A note was added to a contact",
    "deal.closed": "A sale was recorded (Sold wizard, Purchase History or API purchase)",
    "task.created": "A follow-up task was created for a rep",
    "task.completed": "A rep completed a task",
    "activity.logged": "Any other touchpoint on the contact timeline (card sent, review request, congrats card, link click...)",
    "appointment.created": "An appointment was scheduled",
    "review.submitted": "A customer submitted a review",
    "campaign.enrolled": "A contact entered an automated campaign",
    "campaign.completed": "A contact finished an automated campaign",
    "user.created": "A rep account was created",
    "user.deactivated": "A rep account was deactivated",
    "ping": "Test event sent from the Integrations screen or POST /api/v1/webhooks/{id}/test",
    # Legacy names still accepted on existing subscriptions
    "contact.tagged": "Legacy alias of contact.updated",
    "tag.added": "Legacy alias of contact.updated",
    "tag.removed": "Legacy alias of contact.updated",
    "campaign.step_sent": "Legacy alias of message.sent",
    "review.approved": "A review was approved for display",
    "congrats.sent": "Legacy alias of activity.logged",
    "user.reactivated": "A rep account was reactivated",
}


class WebhookSubscription(BaseModel):
    url: str
    events: List[str]  # event names, or ["*"] for everything
    secret: Optional[str] = None  # shared secret for the X-IMOS-Signature HMAC
    description: Optional[str] = None
    is_active: bool = True


class WebhookSubscriptionUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def validate_events(events: List[str]):
    bad = [e for e in events if e != "*" and e not in EVENT_TYPES]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown event type(s): {', '.join(bad)}. See GET /api/v1/webhooks/events")


def subscription_matches(sub: dict, event_type: str) -> bool:
    evs = sub.get("events") or []
    return "*" in evs or event_type in evs


def public_subscription(sub: dict) -> dict:
    return {
        "id": str(sub["_id"]),
        "url": sub.get("url"),
        "events": sub.get("events") or [],
        "description": sub.get("description"),
        "is_active": sub.get("is_active", True),
        "has_secret": bool(sub.get("secret")),
        "store_id": sub.get("store_id"),
        "organization_id": sub.get("organization_id"),
        "created_at": sub.get("created_at").isoformat() if isinstance(sub.get("created_at"), datetime) else sub.get("created_at"),
        "last_triggered": sub.get("last_triggered").isoformat() if isinstance(sub.get("last_triggered"), datetime) else sub.get("last_triggered"),
        "last_status": sub.get("last_status"),
        "failure_count": sub.get("failure_count", 0),
        "delivery_count": sub.get("delivery_count", 0),
    }


async def _user(x_user_id: Optional[str]):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await get_db().users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _tenant_query(user: dict) -> dict:
    if user.get("role") == "super_admin":
        return {}
    if user.get("organization_id"):
        return {"organization_id": user["organization_id"]}
    if user.get("store_id"):
        return {"store_id": user["store_id"]}
    return {"created_by": str(user["_id"])}


@router.get("/events")
async def list_event_types():
    return {"event_types": [k for k in EVENT_TYPES if k != "ping"], "descriptions": EVENT_TYPES}


@router.post("/")
async def create_subscription(sub: WebhookSubscription, x_user_id: str = Header(None, alias="X-User-ID")):
    user = await _user(x_user_id)
    validate_events(sub.events)
    now = datetime.now(timezone.utc)
    doc = {
        "url": sub.url, "events": sub.events, "secret": sub.secret, "description": sub.description,
        "is_active": sub.is_active, "created_by": str(user["_id"]),
        "organization_id": user.get("organization_id"), "store_id": user.get("store_id"),
        "created_at": now, "updated_at": now, "failure_count": 0, "delivery_count": 0, "last_triggered": None, "last_status": None,
    }
    result = await get_db().webhook_subscriptions.insert_one(doc)
    return {"id": str(result.inserted_id), "message": "Webhook subscription created"}


@router.get("/")
async def list_subscriptions(x_user_id: str = Header(None, alias="X-User-ID")):
    user = await _user(x_user_id)
    subs = await get_db().webhook_subscriptions.find(_tenant_query(user)).to_list(100)
    return {"subscriptions": [public_subscription(s) for s in subs]}


@router.put("/{sub_id}")
async def update_subscription(sub_id: str, update: WebhookSubscriptionUpdate, x_user_id: str = Header(None, alias="X-User-ID")):
    user = await _user(x_user_id)
    update_dict = {k: v for k, v in update.dict().items() if v is not None}
    if "events" in update_dict:
        validate_events(update_dict["events"])
    update_dict["updated_at"] = datetime.now(timezone.utc)
    result = await get_db().webhook_subscriptions.update_one({"_id": ObjectId(sub_id), **_tenant_query(user)}, {"$set": update_dict})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription updated"}


@router.delete("/{sub_id}")
async def delete_subscription(sub_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    user = await _user(x_user_id)
    result = await get_db().webhook_subscriptions.delete_one({"_id": ObjectId(sub_id), **_tenant_query(user)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription deleted"}


@router.get("/{sub_id}/logs")
async def get_subscription_logs(sub_id: str, limit: int = 50, x_user_id: str = Header(None, alias="X-User-ID")):
    user = await _user(x_user_id)
    if not await get_db().webhook_subscriptions.find_one({"_id": ObjectId(sub_id), **_tenant_query(user)}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"logs": await delivery_logs(sub_id, limit)}


async def delivery_logs(sub_id: str, limit: int = 50) -> list:
    logs = await get_db().webhook_logs.find({"subscription_id": sub_id}).sort("timestamp", -1).limit(limit).to_list(limit)
    out = []
    for l in logs:
        out.append({"id": str(l["_id"]), "event": l.get("event"), "delivery_id": l.get("delivery_id"), "status_code": l.get("status_code"),
                    "success": l.get("success", False), "error": l.get("error"), "response_time_ms": l.get("response_time_ms"),
                    "timestamp": l["timestamp"].isoformat() if isinstance(l.get("timestamp"), datetime) else l.get("timestamp")})
    return out


# ============= DELIVERY =============

def build_event(event_type: str, data: dict, tenant: Optional[dict] = None) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex[:20]}",
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "store_id": (tenant or {}).get("store_id"),
        "organization_id": (tenant or {}).get("organization_id"),
        "data": data,
    }


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver(db, sub: dict, event: dict) -> dict:
    """POST one event to one subscription, sign it, log it, update the subscription counters."""
    sub_id = str(sub["_id"])
    body = json.dumps(event, default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ImOnSocial-Webhooks/1.0",
        "X-IMOS-Event": event["event"],
        "X-IMOS-Delivery": event.get("id") or f"evt_{uuid.uuid4().hex[:20]}",
    }
    if sub.get("secret"):
        headers["X-IMOS-Signature"] = sign(sub["secret"], body)
    status_code, error, ok = None, None, False
    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(sub["url"], content=body, headers=headers)
            status_code = resp.status_code
            ok = resp.status_code < 400
            if not ok:
                error = resp.text[:500]
    except Exception as e:
        error = str(e)[:500]
    ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    now = datetime.now(timezone.utc)
    upd = {"$set": {"last_status": status_code or "error", "last_triggered": now, "last_triggered_at": now}, "$inc": {"delivery_count": 1}}
    if ok:
        upd["$set"]["failure_count"] = 0
    else:
        upd["$inc"]["failure_count"] = 1
    await db.webhook_subscriptions.update_one({"_id": sub["_id"]}, upd)
    await db.webhook_logs.insert_one({"subscription_id": sub_id, "webhook_id": sub_id, "event": event["event"], "delivery_id": headers["X-IMOS-Delivery"],
                                      "url": sub["url"], "status_code": status_code, "success": ok, "error": error, "response_time_ms": ms,
                                      "timestamp": now, "created_at": now})
    return {"success": ok, "status_code": status_code, "error": error, "delivery_id": headers["X-IMOS-Delivery"], "response_time_ms": ms}


def tenant_or(org_id: Optional[str], store_id: Optional[str]) -> list:
    """Subscriptions that should hear about something that happened in this store/org."""
    ors = []
    if store_id:
        ors.append({"store_id": store_id})
    if org_id:
        ors.append({"organization_id": org_id, "$or": [{"store_id": None}, {"store_id": ""}, {"store_id": {"$exists": False}}]})
    return ors


async def fire_webhook_event(event_type: str, payload: dict, org_id: str = None, store_id: str = None):
    """Deliver one event right now to every matching subscription of that tenant (used for explicit, immediate events)."""
    db = get_db()
    if db is None:
        return
    ors = tenant_or(org_id, store_id)
    if not ors:
        return
    try:
        subs = await db.webhook_subscriptions.find({"is_active": True, "$and": [{"$or": [{"events": event_type}, {"events": "*"}]}, {"$or": ors}]}).to_list(50)
        if not subs:
            return
        event = build_event(event_type, payload, {"store_id": store_id, "organization_id": org_id})
        import asyncio
        await asyncio.gather(*[deliver(db, s, event) for s in subs], return_exceptions=True)
    except Exception as e:
        logger.error(f"Webhook dispatch error for {event_type}: {e}")
