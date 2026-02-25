"""
Integrations router - API keys, webhooks, RMS/DMS connections
Supports: Salesforce, HubSpot, DealerSocket, VinSolutions, Tekion, Pipedrive
DMS: MyKarma, Xtime, CDK, Reynolds & Reynolds, Dealertrack
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List
import secrets
import hashlib
import hmac
import json
import logging
import httpx
from pydantic import BaseModel

from routers.database import get_db

router = APIRouter(prefix="/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)


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

WEBHOOK_EVENTS = {
    "contact.created": "Triggered when a new contact is added",
    "contact.updated": "Triggered when a contact is updated",
    "contact.deleted": "Triggered when a contact is deleted",
    "message.received": "Triggered when an inbound message is received",
    "message.sent": "Triggered when an outbound message is sent",
    "call.completed": "Triggered when a call ends",
    "campaign.enrolled": "Triggered when a contact is enrolled in a campaign",
    "campaign.completed": "Triggered when a contact completes a campaign",
    "deal.created": "Triggered when a deal/opportunity is created",
    "deal.updated": "Triggered when a deal status changes",
    "deal.closed": "Triggered when a deal is marked as closed/won",
    "appointment.created": "Triggered when an appointment is scheduled",
    "appointment.updated": "Triggered when an appointment is modified",
    "review.received": "Triggered when a customer submits a review",
    "task.created": "Triggered when a task is created",
    "task.completed": "Triggered when a task is marked complete",
}


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
        "description": "Connect MVPLine to 5,000+ apps",
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
async def create_api_key(data: APIKeyCreate, store_id: str):
    """Generate a new API key for the store"""
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
async def list_api_keys(store_id: str):
    """List all API keys for a store"""
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
async def revoke_api_key(key_id: str):
    """Revoke an API key"""
    db = get_db()
    
    result = await db.api_keys.update_one(
        {"_id": ObjectId(key_id)},
        {"$set": {"active": False, "revoked_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return {"success": True, "message": "API key revoked"}


# ============= WEBHOOKS =============

@router.post("/webhooks")
async def create_webhook(data: WebhookCreate, store_id: str):
    """Create a new webhook endpoint"""
    db = get_db()
    
    # Generate signing secret if not provided
    secret = data.secret or secrets.token_urlsafe(32)
    
    webhook = {
        "store_id": store_id,
        "name": data.name,
        "url": data.url,
        "events": data.events,
        "secret": secret,
        "active": data.active,
        "created_at": datetime.utcnow(),
        "delivery_count": 0,
        "failure_count": 0,
        "last_triggered_at": None,
    }
    
    result = await db.webhooks.insert_one(webhook)
    
    return {
        "id": str(result.inserted_id),
        "name": data.name,
        "url": data.url,
        "events": data.events,
        "secret": secret,
        "active": data.active,
        "message": "Webhook created successfully"
    }


@router.get("/webhooks")
async def list_webhooks(store_id: str):
    """List all webhooks for a store"""
    db = get_db()
    
    webhooks = await db.webhooks.find({"store_id": store_id}).to_list(100)
    
    return [
        {
            "id": str(w["_id"]),
            "name": w["name"],
            "url": w["url"],
            "events": w["events"],
            "active": w["active"],
            "delivery_count": w.get("delivery_count", 0),
            "failure_count": w.get("failure_count", 0),
            "last_triggered_at": w["last_triggered_at"].isoformat() if w.get("last_triggered_at") else None,
        }
        for w in webhooks
    ]


@router.get("/webhooks/events")
async def list_webhook_events():
    """List all available webhook events"""
    return WEBHOOK_EVENTS


@router.put("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, data: dict):
    """Update a webhook"""
    db = get_db()
    
    allowed_fields = ["name", "url", "events", "active"]
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.webhooks.update_one(
        {"_id": ObjectId(webhook_id)},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"success": True, "message": "Webhook updated"}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Delete a webhook"""
    db = get_db()
    
    result = await db.webhooks.delete_one({"_id": ObjectId(webhook_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"success": True, "message": "Webhook deleted"}


@router.get("/webhooks/{webhook_id}/logs")
async def get_webhook_logs(webhook_id: str, limit: int = 50):
    """Get delivery logs for a webhook"""
    db = get_db()
    
    logs = await db.webhook_logs.find(
        {"webhook_id": webhook_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return [
        {
            "id": str(log["_id"]),
            "event": log["event"],
            "status_code": log.get("status_code"),
            "success": log.get("success", False),
            "response_time_ms": log.get("response_time_ms"),
            "error": log.get("error"),
            "created_at": log["created_at"].isoformat(),
        }
        for log in logs
    ]


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """Send a test payload to the webhook"""
    db = get_db()
    
    webhook = await db.webhooks.find_one({"_id": ObjectId(webhook_id)})
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    test_payload = {
        "event": "test",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "message": "This is a test webhook from MVPLine",
            "webhook_id": webhook_id,
        }
    }
    
    # Sign the payload
    signature = hmac.new(
        webhook["secret"].encode(),
        json.dumps(test_payload).encode(),
        hashlib.sha256
    ).hexdigest()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook["url"],
                json=test_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-MVPLine-Signature": signature,
                    "X-MVPLine-Event": "test",
                }
            )
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "response": response.text[:500] if response.text else None,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


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
    """Get API documentation overview"""
    return {
        "name": "MVPLine API",
        "version": "2.0",
        "base_url": "/api",
        "authentication": {
            "type": "API Key",
            "header": "X-API-Key",
            "description": "Include your API key in the X-API-Key header for all requests",
        },
        "rate_limits": {
            "requests_per_minute": 60,
            "requests_per_day": 10000,
        },
        "endpoints": {
            "contacts": {
                "base": "/api/contacts",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "description": "Manage contacts and customer data",
            },
            "messages": {
                "base": "/api/messages",
                "methods": ["GET", "POST"],
                "description": "Send and receive messages",
            },
            "campaigns": {
                "base": "/api/campaigns",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "description": "Manage nurture campaigns",
            },
            "appointments": {
                "base": "/api/calendar/appointments",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "description": "Schedule and manage appointments",
            },
            "tasks": {
                "base": "/api/tasks",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "description": "Create and manage tasks",
            },
        },
        "webhooks": {
            "description": "Receive real-time notifications for events",
            "events": list(WEBHOOK_EVENTS.keys()),
            "signature_header": "X-MVPLine-Signature",
            "signature_algorithm": "HMAC-SHA256",
        },
    }


@router.get("/docs/contacts")
async def get_contacts_docs():
    """Get contacts API documentation"""
    return {
        "resource": "Contacts",
        "base_path": "/api/contacts/{user_id}",
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/contacts/{user_id}",
                "description": "List all contacts for a user",
                "query_params": [
                    {"name": "search", "type": "string", "description": "Search by name or phone"},
                    {"name": "tags", "type": "string", "description": "Filter by tags (comma-separated)"},
                    {"name": "limit", "type": "integer", "description": "Max results (default 100)"},
                    {"name": "offset", "type": "integer", "description": "Pagination offset"},
                ],
                "response": {
                    "type": "array",
                    "items": {
                        "type": "Contact",
                        "properties": {
                            "_id": "string",
                            "first_name": "string",
                            "last_name": "string",
                            "phone": "string",
                            "email": "string",
                            "tags": "array[string]",
                            "custom_dates": "array[{label, date}]",
                            "created_at": "datetime",
                        }
                    }
                }
            },
            {
                "method": "POST",
                "path": "/api/contacts/{user_id}",
                "description": "Create a new contact",
                "body": {
                    "first_name": {"type": "string", "required": True},
                    "last_name": {"type": "string", "required": False},
                    "phone": {"type": "string", "required": True},
                    "email": {"type": "string", "required": False},
                    "tags": {"type": "array[string]", "required": False},
                    "notes": {"type": "string", "required": False},
                },
                "response": {"type": "Contact"}
            },
            {
                "method": "PUT",
                "path": "/api/contacts/{user_id}/{contact_id}",
                "description": "Update a contact",
                "body": "Partial Contact object",
                "response": {"type": "Contact"}
            },
            {
                "method": "DELETE",
                "path": "/api/contacts/{user_id}/{contact_id}",
                "description": "Delete a contact",
                "response": {"success": True}
            },
        ]
    }


@router.get("/docs/messages")
async def get_messages_docs():
    """Get messages API documentation"""
    return {
        "resource": "Messages",
        "base_path": "/api/messages",
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/messages/conversations/{user_id}",
                "description": "List all conversations for a user",
                "response": {
                    "type": "array",
                    "items": {
                        "type": "Conversation",
                        "properties": {
                            "contact_id": "string",
                            "contact_name": "string",
                            "contact_phone": "string",
                            "last_message": "string",
                            "last_message_at": "datetime",
                            "unread_count": "integer",
                            "ai_handled": "boolean",
                        }
                    }
                }
            },
            {
                "method": "GET",
                "path": "/api/messages/thread/{contact_id}",
                "description": "Get message thread with a contact",
                "response": {
                    "type": "array",
                    "items": {
                        "type": "Message",
                        "properties": {
                            "_id": "string",
                            "direction": "inbound|outbound",
                            "content": "string",
                            "media_urls": "array[string]",
                            "sent_at": "datetime",
                            "delivered": "boolean",
                            "read": "boolean",
                        }
                    }
                }
            },
            {
                "method": "POST",
                "path": "/api/messages/send",
                "description": "Send a message to a contact",
                "body": {
                    "user_id": {"type": "string", "required": True},
                    "contact_id": {"type": "string", "required": True},
                    "content": {"type": "string", "required": True},
                    "media_urls": {"type": "array[string]", "required": False},
                },
                "response": {"type": "Message"}
            },
        ]
    }


@router.get("/docs/webhooks")
async def get_webhooks_docs():
    """Get webhooks documentation"""
    return {
        "overview": "Webhooks allow you to receive real-time HTTP notifications when events occur in MVPLine.",
        "setup": {
            "steps": [
                "1. Create a webhook endpoint in your application",
                "2. Register the webhook URL in MVPLine",
                "3. Select which events to subscribe to",
                "4. Store the signing secret securely",
            ],
        },
        "payload_format": {
            "event": "The event type (e.g., 'contact.created')",
            "timestamp": "ISO 8601 timestamp",
            "data": "Event-specific data object",
            "webhook_id": "Your webhook ID",
        },
        "signature_verification": {
            "header": "X-MVPLine-Signature",
            "algorithm": "HMAC-SHA256",
            "example_python": """
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
""",
        },
        "events": WEBHOOK_EVENTS,
        "retry_policy": {
            "max_retries": 3,
            "retry_delays": ["1 minute", "5 minutes", "30 minutes"],
            "timeout": "10 seconds",
        },
    }
