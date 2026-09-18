"""
Integrations router - API keys, webhooks, RMS/DMS connections
Supports: Salesforce, HubSpot, DealerSocket, VinSolutions, Tekion, Pipedrive
DMS: MyKarma, Xtime, CDK, Reynolds & Reynolds, Dealertrack
"""
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List
import secrets
import hashlib
import logging
from pydantic import BaseModel

from routers.database import get_db
from routers.webhook_subscriptions import EVENT_TYPES, build_event, deliver, delivery_logs, validate_events

router = APIRouter(prefix="/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)

ADMIN_ROLES = ("super_admin", "org_admin", "store_manager", "white_label_partner")


async def require_store_admin(request: Request, store_id: str) -> dict:
    """API keys and webhooks hand out customer data: only a logged-in manager/admin of that store may manage them."""
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    role = user.get("role")
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Manager or admin role required")
    if role == "super_admin" or user.get("store_id") == store_id:
        return user
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)}, {"organization_id": 1}) if ObjectId.is_valid(store_id) else None
    if store and user.get("organization_id") and store.get("organization_id") == user["organization_id"]:
        return user
    raise HTTPException(status_code=403, detail="You do not manage this store")


# ============= MODELS =============

class APIKeyCreate(BaseModel):
    name: str
    scopes: List[str] = ["read", "write"]
    expires_in_days: Optional[int] = 365

class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    active: bool = True

class IntegrationConfig(BaseModel):
    provider: str
    credentials: dict
    sync_settings: dict = {}
    active: bool = True


# ============= WEBHOOK EVENTS =============

WEBHOOK_EVENTS = {k: v for k, v in EVENT_TYPES.items() if k != "ping"}


# ============= CRM PROVIDERS =============

CRM_PROVIDERS = {
    "salesforce": {
        "name": "Salesforce",
        "type": "crm",
        "description": "World's #1 RMS platform",
        "auth_type": "oauth2",
        "supported_objects": ["contacts", "leads", "accounts", "opportunities", "activities"],
        "docs_url": "https://developer.salesforce.com/docs",
        "required_fields": ["client_id", "client_secret", "instance_url"],
    },
    "hubspot": {
        "name": "HubSpot",
        "type": "crm",
        "description": "Inbound marketing, sales, and service software",
        "auth_type": "oauth2",
        "supported_objects": ["contacts", "companies", "deals", "engagements"],
        "docs_url": "https://developers.hubspot.com/docs",
        "required_fields": ["api_key"],
    },
    "dealersocket": {
        "name": "DealerSocket",
        "type": "crm",
        "description": "Automotive RMS and marketing solutions",
        "auth_type": "api_key",
        "supported_objects": ["customers", "vehicles", "opportunities", "activities"],
        "docs_url": "https://www.dealersocket.com/solutions/crm",
        "required_fields": ["api_key", "dealer_id"],
    },
    "vinsolutions": {
        "name": "VinSolutions",
        "type": "crm",
        "description": "Cox Automotive RMS for dealerships",
        "auth_type": "api_key",
        "supported_objects": ["customers", "vehicles", "leads", "activities"],
        "docs_url": "https://www.vinsolutions.com",
        "required_fields": ["api_key", "dealer_code"],
    },
    "tekion": {
        "name": "Tekion",
        "type": "crm",
        "description": "Cloud-native automotive retail platform",
        "auth_type": "oauth2",
        "supported_objects": ["customers", "vehicles", "deals", "service_appointments"],
        "docs_url": "https://tekion.com/platform",
        "required_fields": ["client_id", "client_secret", "tenant_id"],
    },
    "pipedrive": {
        "name": "Pipedrive",
        "type": "crm",
        "description": "Sales RMS & pipeline management",
        "auth_type": "api_key",
        "supported_objects": ["persons", "organizations", "deals", "activities"],
        "docs_url": "https://developers.pipedrive.com/docs",
        "required_fields": ["api_token"],
    },
}


# ============= DMS PROVIDERS =============

DMS_PROVIDERS = {
    "mykarma": {
        "name": "myKarma",
        "type": "dms",
        "description": "Service scheduling and customer communication",
        "auth_type": "api_key",
        "supported_objects": ["appointments", "customers", "vehicles", "service_history"],
        "docs_url": "https://mykarma.com",
        "required_fields": ["api_key", "dealer_id"],
    },
    "xtime": {
        "name": "Xtime",
        "type": "dms",
        "description": "Cox Automotive service scheduling",
        "auth_type": "api_key",
        "supported_objects": ["appointments", "customers", "vehicles", "service_advisors"],
        "docs_url": "https://www.xtime.com",
        "required_fields": ["api_key", "dealer_code"],
    },
    "cdk": {
        "name": "CDK Global",
        "type": "dms",
        "description": "Dealer management system and data services",
        "auth_type": "oauth2",
        "supported_objects": ["customers", "vehicles", "parts", "service_orders", "inventory"],
        "docs_url": "https://www.cdkglobal.com",
        "required_fields": ["client_id", "client_secret", "dealer_id"],
    },
    "reynolds": {
        "name": "Reynolds & Reynolds",
        "type": "dms",
        "description": "ERA-IGNITE dealer management system",
        "auth_type": "api_key",
        "supported_objects": ["customers", "vehicles", "parts", "service", "accounting"],
        "docs_url": "https://www.reyrey.com",
        "required_fields": ["api_key", "dealer_number"],
    },
    "dealertrack": {
        "name": "Dealertrack DMS",
        "type": "dms",
        "description": "Cox Automotive dealer management system",
        "auth_type": "api_key",
        "supported_objects": ["customers", "inventory", "deals", "service"],
        "docs_url": "https://www.dealertrack.com",
        "required_fields": ["api_key", "dealer_id"],
    },
    "autosoft": {
        "name": "Autosoft DMS",
        "type": "dms",
        "description": "Cloud-based dealer management",
        "auth_type": "api_key",
        "supported_objects": ["customers", "vehicles", "parts", "service", "accounting"],
        "docs_url": "https://www.autosoft.com",
        "required_fields": ["api_key", "dealer_code"],
    },
}


# ============= AUTOMATION PROVIDERS =============

AUTOMATION_PROVIDERS = {
    "zapier": {
        "name": "Zapier",
        "type": "automation",
        "description": "Connect I'm On Social to 5,000+ apps",
        "auth_type": "webhook",
        "docs_url": "https://zapier.com",
        "setup_instructions": "Use webhooks to trigger Zaps or receive data from Zapier",
    },
    "make": {
        "name": "Make (Integromat)",
        "type": "automation",
        "description": "Visual automation platform",
        "auth_type": "webhook",
        "docs_url": "https://make.com",
        "setup_instructions": "Use webhooks to connect with Make scenarios",
    },
    "n8n": {
        "name": "n8n",
        "type": "automation",
        "description": "Open-source workflow automation",
        "auth_type": "webhook",
        "docs_url": "https://n8n.io",
        "setup_instructions": "Use webhooks with n8n HTTP nodes",
    },
}


# ============= API KEY MANAGEMENT =============

@router.post("/api-keys")
async def create_api_key(request: Request, data: APIKeyCreate, store_id: str):
    """Generate a new API key for the store"""
    await require_store_admin(request, store_id)
    db = get_db()
    
    # Generate secure key
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]  # For display purposes
    
    api_key = {
        "store_id": store_id,
        "name": data.name,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "scopes": data.scopes,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=data.expires_in_days) if data.expires_in_days else None,
        "last_used_at": None,
        "request_count": 0,
        "active": True,
    }
    
    result = await db.api_keys.insert_one(api_key)
    
    return {
        "id": str(result.inserted_id),
        "name": data.name,
        "key": raw_key,  # Only shown once!
        "key_prefix": key_prefix,
        "scopes": data.scopes,
        "expires_at": api_key["expires_at"].isoformat() if api_key["expires_at"] else None,
        "message": "Store this key securely - it won't be shown again!"
    }


@router.get("/api-keys")
async def list_api_keys(request: Request, store_id: str):
    """List all API keys for a store"""
    await require_store_admin(request, store_id)
    db = get_db()
    
    keys = await db.api_keys.find(
        {"store_id": store_id},
        {"key_hash": 0}  # Don't expose hash
    ).to_list(100)
    
    return [
        {
            "id": str(k["_id"]),
            "name": k["name"],
            "key_prefix": k["key_prefix"],
            "scopes": k["scopes"],
            "created_at": k["created_at"].isoformat(),
            "expires_at": k["expires_at"].isoformat() if k.get("expires_at") else None,
            "last_used_at": k["last_used_at"].isoformat() if k.get("last_used_at") else None,
            "request_count": k.get("request_count", 0),
            "active": k["active"],
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(request: Request, key_id: str):
    """Revoke an API key"""
    db = get_db()
    key = await db.api_keys.find_one({"_id": ObjectId(key_id)}, {"store_id": 1}) if ObjectId.is_valid(key_id) else None
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    await require_store_admin(request, key.get("store_id") or "")
    
    result = await db.api_keys.update_one(
        {"_id": ObjectId(key_id)},
        {"$set": {"active": False, "is_active": False, "revoked_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return {"success": True, "message": "API key revoked"}


# ============= WEBHOOKS =============

@router.post("/webhooks")
async def create_webhook(request: Request, data: WebhookCreate, store_id: str):
    """Register a webhook for the store. Lives in webhook_subscriptions, the one collection the outbox delivers to."""
    user = await require_store_admin(request, store_id)
    db = get_db()
    validate_events(data.events)
    secret = data.secret or secrets.token_urlsafe(32)
    now = datetime.utcnow()
    store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"organization_id": 1}) if ObjectId.is_valid(store_id) else None
    webhook = {
        "store_id": store_id, "organization_id": (store or {}).get("organization_id") or user.get("organization_id"),
        "description": data.name, "url": data.url, "events": data.events, "secret": secret, "is_active": data.active,
        "created_by": str(user["_id"]), "created_at": now, "updated_at": now,
        "delivery_count": 0, "failure_count": 0, "last_triggered": None, "last_status": None,
    }
    result = await db.webhook_subscriptions.insert_one(webhook)
    return {
        "id": str(result.inserted_id),
        "name": data.name,
        "url": data.url,
        "events": data.events,
        "secret": secret,
        "active": data.active,
        "message": "Webhook created successfully"
    }


def _ui_webhook(w: dict) -> dict:
    return {
        "id": str(w["_id"]),
        "name": w.get("description") or w.get("name") or w.get("url"),
        "url": w["url"],
        "events": w.get("events") or [],
        "active": w.get("is_active", w.get("active", True)),
        "delivery_count": w.get("delivery_count", 0),
        "failure_count": w.get("failure_count", 0),
        "last_status": w.get("last_status"),
        "last_triggered_at": w["last_triggered"].isoformat() if isinstance(w.get("last_triggered"), datetime) else None,
    }


@router.get("/webhooks")
async def list_webhooks(request: Request, store_id: str):
    """List all webhooks for a store"""
    await require_store_admin(request, store_id)
    db = get_db()
    webhooks = await db.webhook_subscriptions.find({"store_id": store_id}).to_list(100)
    return [_ui_webhook(w) for w in webhooks]


@router.get("/webhooks/events")
async def list_webhook_events():
    return {k: v for k, v in EVENT_TYPES.items() if k != "ping"}


@router.put("/webhooks/{webhook_id}")
async def update_webhook(request: Request, webhook_id: str, data: dict):
    db = get_db()
    w = await db.webhook_subscriptions.find_one({"_id": ObjectId(webhook_id)}, {"store_id": 1}) if ObjectId.is_valid(webhook_id) else None
    if not w:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await require_store_admin(request, w.get("store_id") or "")
    update_dict = {}
    if "name" in data:
        update_dict["description"] = data["name"]
    if "url" in data:
        update_dict["url"] = data["url"]
    if "events" in data:
        validate_events(data["events"])
        update_dict["events"] = data["events"]
    if "active" in data:
        update_dict["is_active"] = bool(data["active"])
    update_dict["updated_at"] = datetime.utcnow()
    await db.webhook_subscriptions.update_one({"_id": ObjectId(webhook_id)}, {"$set": update_dict})
    return {"success": True, "message": "Webhook updated"}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(request: Request, webhook_id: str):
    db = get_db()
    w = await db.webhook_subscriptions.find_one({"_id": ObjectId(webhook_id)}, {"store_id": 1}) if ObjectId.is_valid(webhook_id) else None
    if not w:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await require_store_admin(request, w.get("store_id") or "")
    await db.webhook_subscriptions.delete_one({"_id": ObjectId(webhook_id)})
    return {"success": True, "message": "Webhook deleted"}


@router.get("/webhooks/{webhook_id}/logs")
async def get_webhook_logs(request: Request, webhook_id: str, limit: int = 50):
    db = get_db()
    w = await db.webhook_subscriptions.find_one({"_id": ObjectId(webhook_id)}, {"store_id": 1}) if ObjectId.is_valid(webhook_id) else None
    if not w:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await require_store_admin(request, w.get("store_id") or "")
    logs = await delivery_logs(webhook_id, limit)
    for l in logs:
        l["created_at"] = l.get("timestamp")
    return logs


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(request: Request, webhook_id: str):
    """Send a signed ping to the URL right now."""
    db = get_db()
    webhook = await db.webhook_subscriptions.find_one({"_id": ObjectId(webhook_id)}) if ObjectId.is_valid(webhook_id) else None
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await require_store_admin(request, webhook.get("store_id") or "")
    event = build_event("ping", {"message": "This is a test webhook from I'm On Social", "webhook_id": webhook_id},
                        {"store_id": webhook.get("store_id"), "organization_id": webhook.get("organization_id")})
    return await deliver(db, webhook, event)


# ============= CRM/DMS INTEGRATIONS =============

@router.get("/providers")
async def list_providers():
    """List all available integration providers"""
    return {
        "crm": CRM_PROVIDERS,
        "dms": DMS_PROVIDERS,
        "automation": AUTOMATION_PROVIDERS,
    }


@router.get("/providers/{provider_id}")
async def get_provider_details(provider_id: str):
    """Get details for a specific provider"""
    all_providers = {**CRM_PROVIDERS, **DMS_PROVIDERS, **AUTOMATION_PROVIDERS}
    
    if provider_id not in all_providers:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return all_providers[provider_id]


@router.post("/connections")
async def create_connection(data: IntegrationConfig, store_id: str):
    """Create a new integration connection"""
    db = get_db()
    
    # Validate provider
    all_providers = {**CRM_PROVIDERS, **DMS_PROVIDERS}
    if data.provider not in all_providers:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    provider = all_providers[data.provider]
    
    # Check required fields
    for field in provider.get("required_fields", []):
        if field not in data.credentials:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required credential: {field}"
            )
    
    connection = {
        "store_id": store_id,
        "provider": data.provider,
        "provider_name": provider["name"],
        "provider_type": provider["type"],
        "credentials": data.credentials,  # In production, encrypt these!
        "sync_settings": data.sync_settings,
        "active": data.active,
        "created_at": datetime.utcnow(),
        "last_sync_at": None,
        "sync_status": "pending",
        "error_message": None,
    }
    
    result = await db.integrations.insert_one(connection)
    
    return {
        "id": str(result.inserted_id),
        "provider": data.provider,
        "provider_name": provider["name"],
        "active": data.active,
        "message": "Integration connected successfully"
    }


@router.get("/connections")
async def list_connections(store_id: str):
    """List all integration connections for a store"""
    db = get_db()
    
    connections = await db.integrations.find(
        {"store_id": store_id},
        {"credentials": 0}  # Don't expose credentials
    ).to_list(100)
    
    return [
        {
            "id": str(c["_id"]),
            "provider": c["provider"],
            "provider_name": c["provider_name"],
            "provider_type": c["provider_type"],
            "active": c["active"],
            "sync_status": c.get("sync_status", "unknown"),
            "last_sync_at": c["last_sync_at"].isoformat() if c.get("last_sync_at") else None,
            "error_message": c.get("error_message"),
        }
        for c in connections
    ]


@router.put("/connections/{connection_id}")
async def update_connection(connection_id: str, data: dict):
    """Update an integration connection"""
    db = get_db()
    
    allowed_fields = ["credentials", "sync_settings", "active"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.integrations.update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return {"success": True, "message": "Connection updated"}


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str):
    """Delete an integration connection"""
    db = get_db()
    
    result = await db.integrations.delete_one({"_id": ObjectId(connection_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return {"success": True, "message": "Connection deleted"}


@router.post("/connections/{connection_id}/sync")
async def trigger_sync(connection_id: str, direction: str = "push"):
    """Manually trigger a sync for an integration"""
    db = get_db()
    
    connection = await db.integrations.find_one({"_id": ObjectId(connection_id)})
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Update sync status
    await db.integrations.update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": {
            "sync_status": "syncing",
            "last_sync_at": datetime.utcnow(),
        }}
    )
    
    # In production, this would trigger an async job
    # For now, we'll simulate a successful sync
    await db.integrations.update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": {
            "sync_status": "success",
            "error_message": None,
        }}
    )
    
    return {
        "success": True,
        "message": f"Sync triggered ({direction})",
        "connection_id": connection_id,
    }


@router.get("/connections/{connection_id}/logs")
async def get_sync_logs(connection_id: str, limit: int = 50):
    """Get sync logs for a connection"""
    db = get_db()
    
    logs = await db.sync_logs.find(
        {"connection_id": connection_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return [
        {
            "id": str(log["_id"]),
            "direction": log.get("direction", "push"),
            "records_processed": log.get("records_processed", 0),
            "records_failed": log.get("records_failed", 0),
            "status": log.get("status", "unknown"),
            "error": log.get("error"),
            "duration_seconds": log.get("duration_seconds"),
            "created_at": log["created_at"].isoformat(),
        }
        for log in logs
    ]


# ============= API DOCUMENTATION =============

@router.get("/docs/overview")
async def get_api_overview():
    """Where the real developer documentation lives. The API-key API is /api/v1; the app's own /api/* routes are session-only."""
    return {
        "name": "I'm On Social Public API",
        "version": "v1",
        "base_url": "/api/v1",
        "authentication": {"type": "API Key", "header": "X-API-Key", "description": "Create keys in Tools -> Integrations -> API Keys. Sent once, stored hashed."},
        "rate_limits": {"requests_per_minute": 120},
        "docs_url": "https://www.imonsocial.com/developers",
        "openapi_url": "/api/public/openapi-v1.json",
        "try_it_url": "/api/public/reference",
        "webhooks": {"events": list(WEBHOOK_EVENTS.keys()), "signature_header": "X-IMOS-Signature", "signature_algorithm": "HMAC-SHA256 over the raw body, prefixed sha256="},
    }
