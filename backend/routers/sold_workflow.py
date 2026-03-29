"""
Sold Workflow System
Event-driven, partner-configurable sold workflow that activates only when
a "Sold" tag is applied to a contact under a partner with sold_workflow_enabled.

Zero impact on standard platform behavior.
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import logging
import hashlib
import httpx

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/sold-workflow", tags=["Sold Workflow"])
logger = logging.getLogger(__name__)

# Guard flag — prevents concurrent runs of the delivery processor
_delivery_running: bool = False


# ─── Canonical Sold Tag Detection ───────────────────────────────────────────

def is_sold_tag(tag: str) -> bool:
    """Check if a tag is the canonical 'Sold' tag. Normalized: lowercase + trimmed."""
    return tag.strip().lower() == "sold"


def sold_tag_just_added(old_tags: list, new_tags: list) -> bool:
    """Return True if 'Sold' was NOT in old_tags but IS in new_tags."""
    old_has = any(is_sold_tag(t) for t in (old_tags or []))
    new_has = any(is_sold_tag(t) for t in (new_tags or []))
    return new_has and not old_has


# ─── Partner Resolution ─────────────────────────────────────────────────────

async def _resolve_partner_config(user_id: str) -> tuple:
    """
    Resolve the partner config for a user.
    Returns (partner_doc, store_doc) or (None, None) if no partner or workflow disabled.
    """
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return None, None

    store_id = user.get("store_id")
    org_id = user.get("organization_id") or user.get("org_id")
    partner_id = None

    # Check org-level partner first
    if org_id:
        try:
            org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"partner_id": 1})
            if org and org.get("partner_id"):
                partner_id = org["partner_id"]
        except Exception:
            pass

    # Check store-level partner
    if not partner_id and store_id:
        try:
            store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"partner_id": 1})
            if store and store.get("partner_id"):
                partner_id = store["partner_id"]
        except Exception:
            pass

    if not partner_id:
        return None, None

    # Fetch partner
    try:
        partner = await db.white_label_partners.find_one({"_id": ObjectId(partner_id), "is_active": True})
    except Exception:
        return None, None

    if not partner or not partner.get("sold_workflow_enabled"):
        return None, None

    # Fetch store (account)
    store_doc = None
    if store_id:
        try:
            store_doc = await db.stores.find_one({"_id": ObjectId(store_id)})
        except Exception:
            pass

    return partner, store_doc


# ─── Validation ──────────────────────────────────────────────────────────────

def _validate_sold_fields(contact: dict, partner: dict, store: dict) -> list:
    """
    Validate required fields based on partner config.
    Returns list of missing field identifiers.
    """
    required = partner.get("sold_required_fields", [])
    missing = []

    for field in required:
        if field == "customer_name":
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            if not name:
                missing.append("customer_name")

        elif field == "phone_number":
            if not contact.get("phone", "").strip():
                missing.append("phone_number")

        elif field == "full_size_image":
            if not contact.get("full_size_image_url", "").strip():
                missing.append("full_size_image")

        elif field == "deal_or_stock_number":
            mode = (store or {}).get("deal_or_stock_mode", "stock_number")
            if mode == "deal_number":
                if not contact.get("deal_number", "").strip():
                    missing.append("deal_number")
            else:
                if not contact.get("stock_number", "").strip():
                    missing.append("stock_number")

    # Check external_account_id if required by partner
    if partner.get("external_account_id_required"):
        if not (store or {}).get("external_account_id", "").strip():
            missing.append("external_account_id")

    return missing


# ─── Core Workflow ───────────────────────────────────────────────────────────

async def process_sold_workflow(
    user_id: str,
    contact_id: str,
    contact_data: dict,
    old_tags: list,
    trigger_source: str = "update",
) -> Optional[dict]:
    """
    Main entry point. Called after tag save in contacts.py.
    Returns a dict with workflow result if sold workflow applies, None otherwise.

    This function NEVER blocks the tag save. Tags and date_sold are already persisted
    before this runs.
    """
    new_tags = contact_data.get("tags", [])

    if not sold_tag_just_added(old_tags, new_tags):
        return None

    db = get_db()
    now = datetime.now(timezone.utc)

    # Set date_sold if empty
    existing_contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"date_sold": 1})
    if existing_contact and not existing_contact.get("date_sold"):
        await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {"date_sold": now, "sold_tag_applied_at": now}}
        )
    elif existing_contact:
        await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {"sold_tag_applied_at": now}}
        )

    # Resolve partner
    partner, store = await _resolve_partner_config(user_id)
    if not partner:
        return None  # No partner or workflow disabled — standard flow

    partner_id = str(partner["_id"])
    store_id = str(store["_id"]) if store else ""

    logger.info(f"[SoldWorkflow] Triggered for contact {contact_id} by user {user_id}, partner={partner.get('name')}")

    # Idempotency check — don't create duplicate events
    active_statuses = ["validated", "delivery_pending", "delivery_success"]
    existing_event = await db.sold_event_logs.find_one({
        "contact_id": contact_id,
        "validation_status": "passed",
        "delivery_status": {"$in": ["queued", "sent", "retrying"]},
    })
    if existing_event:
        logger.info(f"[SoldWorkflow] Active sold event already exists for contact {contact_id}, skipping")
        return {"status": "already_processed", "event_id": str(existing_event["_id"])}

    # Refresh contact data from DB for validation
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        return None
    contact["_id"] = str(contact["_id"])

    # Validate required fields
    missing = _validate_sold_fields(contact, partner, store)

    # Build idempotency key
    idem_key = f"{contact_id}_sold_{hashlib.md5(now.isoformat().encode()).hexdigest()[:12]}"

    # Create sold event log
    event_log = {
        "contact_id": contact_id,
        "user_id": user_id,
        "account_id": store_id,
        "partner_id": partner_id,
        "external_account_id": (store or {}).get("external_account_id", ""),
        "event_type": "sold",
        "trigger_source": trigger_source,
        "idempotency_key": idem_key,
        "validation_status": "failed" if missing else "passed",
        "missing_fields": missing,
        "payload_snapshot": {},
        "delivery_status": "not_sent",
        "delivery_attempt_count": 0,
        "last_delivery_response_code": None,
        "error_message": "",
        "request_payload": {},
        "response_payload": "",
        "delivered_at": None,
        "next_retry_at": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.sold_event_logs.insert_one(event_log)
    event_id = str(result.inserted_id)

    if missing:
        # Validation failed — update contact status
        await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {
                "sold_workflow_status": "validation_failed",
                "sold_workflow_event_id": event_id,
                "sold_workflow_last_error": f"Missing fields: {', '.join(missing)}",
                "sold_validation_missing_fields": missing,
                "updated_at": now,
            }}
        )
        logger.info(f"[SoldWorkflow] Validation failed for contact {contact_id}: missing {missing}")
        return {
            "status": "validation_failed",
            "event_id": event_id,
            "missing_fields": missing,
            "deal_or_stock_mode": (store or {}).get("deal_or_stock_mode", "stock_number"),
        }

    # Validation passed — build payload and queue delivery
    payload = _build_payload(contact, partner, store)
    await db.sold_event_logs.update_one(
        {"_id": ObjectId(event_id)},
        {"$set": {
            "payload_snapshot": payload,
            "request_payload": payload,
            "delivery_status": "queued",
            "updated_at": now,
        }}
    )

    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {
            "sold_workflow_status": "delivery_pending",
            "sold_workflow_event_id": event_id,
            "sold_workflow_processed_at": now,
            "sold_workflow_last_error": None,
            "sold_validation_missing_fields": [],
            "updated_at": now,
        }}
    )

    logger.info(f"[SoldWorkflow] Validated and queued delivery for contact {contact_id}, event={event_id}")

    return {
        "status": "queued",
        "event_id": event_id,
        "missing_fields": [],
    }


def _build_payload(contact: dict, partner: dict, store: dict) -> dict:
    """Build the external delivery payload from contact/store/partner data."""
    mode = (store or {}).get("deal_or_stock_mode", "stock_number")
    payload = {
        "event": "sold",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "account_id": str((store or {}).get("_id", "")),
        "external_account_id": (store or {}).get("external_account_id", ""),
        "customer_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
        "phone_number": contact.get("phone", ""),
        "full_size_image_url": contact.get("full_size_image_url", ""),
    }
    if mode == "deal_number":
        payload["deal_number"] = contact.get("deal_number", "")
    else:
        payload["stock_number"] = contact.get("stock_number", "")
    return payload


# ─── Re-validate (after user fixes missing fields) ──────────────────────────

async def revalidate_sold_workflow(contact_id: str, user_id: str) -> Optional[dict]:
    """
    Re-run validation for a contact whose sold workflow previously failed.
    Called when user submits missing fields from the modal.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # Find the most recent failed event for this contact
    event = await db.sold_event_logs.find_one(
        {"contact_id": contact_id, "validation_status": "failed"},
        sort=[("created_at", -1)],
    )
    if not event:
        return None

    partner, store = await _resolve_partner_config(user_id)
    if not partner:
        return None

    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        return None
    contact["_id"] = str(contact["_id"])

    missing = _validate_sold_fields(contact, partner, store)
    event_id = str(event["_id"])

    if missing:
        await db.sold_event_logs.update_one(
            {"_id": event["_id"]},
            {"$set": {
                "missing_fields": missing,
                "updated_at": now,
            }}
        )
        await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {
                "sold_validation_missing_fields": missing,
                "sold_workflow_last_error": f"Missing fields: {', '.join(missing)}",
                "updated_at": now,
            }}
        )
        return {
            "status": "validation_failed",
            "event_id": event_id,
            "missing_fields": missing,
            "deal_or_stock_mode": (store or {}).get("deal_or_stock_mode", "stock_number"),
        }

    # Passed — build payload and queue
    payload = _build_payload(contact, partner, store)
    await db.sold_event_logs.update_one(
        {"_id": event["_id"]},
        {"$set": {
            "validation_status": "passed",
            "missing_fields": [],
            "payload_snapshot": payload,
            "request_payload": payload,
            "delivery_status": "queued",
            "trigger_source": "manual_retry",
            "updated_at": now,
        }}
    )
    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {
            "sold_workflow_status": "delivery_pending",
            "sold_workflow_processed_at": now,
            "sold_workflow_last_error": None,
            "sold_validation_missing_fields": [],
            "updated_at": now,
        }}
    )

    logger.info(f"[SoldWorkflow] Revalidated and queued delivery for contact {contact_id}")
    return {"status": "queued", "event_id": event_id, "missing_fields": []}


# ─── Delivery Engine ─────────────────────────────────────────────────────────

async def deliver_sold_event(event_id: str) -> dict:
    """
    Attempt to deliver a sold event payload to the partner's endpoint.
    Called by background scheduler or manual retry.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    event = await db.sold_event_logs.find_one({"_id": ObjectId(event_id)})
    if not event:
        return {"success": False, "error": "Event not found"}

    partner_id = event.get("partner_id")
    if not partner_id:
        return {"success": False, "error": "No partner_id on event"}

    try:
        partner = await db.white_label_partners.find_one({"_id": ObjectId(partner_id)})
    except Exception:
        partner = None

    if not partner:
        return {"success": False, "error": "Partner not found"}

    delivery_config = partner.get("event_delivery", {})
    if not delivery_config.get("enabled"):
        # Endpoint not enabled — mark as not_sent (not an error)
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"delivery_status": "not_sent", "error_message": "Endpoint not enabled", "updated_at": now}}
        )
        await db.contacts.update_one(
            {"_id": ObjectId(event.get("contact_id"))},
            {"$set": {"sold_workflow_status": "delivery_success", "updated_at": now}}
        )
        return {"success": True, "status": "endpoint_not_enabled"}

    endpoint_url = delivery_config.get("endpoint_url", "").strip()
    if not endpoint_url:
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"delivery_status": "failed", "error_message": "No endpoint URL configured", "updated_at": now}}
        )
        return {"success": False, "error": "No endpoint URL"}

    # Build headers
    headers = {"Content-Type": "application/json"}
    auth_type = delivery_config.get("auth_type", "none")
    auth_value = delivery_config.get("auth_value_encrypted", "")
    if auth_type == "bearer" and auth_value:
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "api_key" and auth_value:
        headers["X-API-Key"] = auth_value

    payload = event.get("request_payload", event.get("payload_snapshot", {}))
    attempt = event.get("delivery_attempt_count", 0) + 1

    # Verify image accessibility if present
    image_url = payload.get("full_size_image_url", "")
    image_accessible = True
    if image_url:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                head_resp = await client.head(image_url)
                image_accessible = head_resp.status_code < 400
        except Exception:
            image_accessible = False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint_url, json=payload, headers=headers)
            status_code = resp.status_code
            response_body = resp.text[:2000]  # truncate

        success = 200 <= status_code < 300
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "delivery_status": "sent" if success else "failed",
                "delivery_attempt_count": attempt,
                "last_delivery_response_code": status_code,
                "response_payload": response_body,
                "error_message": "" if success else f"HTTP {status_code}",
                "delivered_at": now if success else None,
                "image_accessible_at_delivery": image_accessible,
                "updated_at": now,
            }}
        )

        contact_status = "delivery_success" if success else "delivery_failed"
        await db.contacts.update_one(
            {"_id": ObjectId(event.get("contact_id"))},
            {"$set": {
                "sold_workflow_status": contact_status,
                "sold_workflow_last_error": None if success else f"HTTP {status_code}",
                "updated_at": now,
            }}
        )

        logger.info(f"[SoldWorkflow] Delivery {'succeeded' if success else 'failed'} for event {event_id}: HTTP {status_code}")
        return {"success": success, "status_code": status_code}

    except Exception as e:
        error_msg = str(e)[:500]
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "delivery_status": "failed",
                "delivery_attempt_count": attempt,
                "error_message": error_msg,
                "updated_at": now,
            }}
        )
        await db.contacts.update_one(
            {"_id": ObjectId(event.get("contact_id"))},
            {"$set": {
                "sold_workflow_status": "delivery_failed",
                "sold_workflow_last_error": error_msg,
                "updated_at": now,
            }}
        )
        logger.error(f"[SoldWorkflow] Delivery exception for event {event_id}: {error_msg}")
        return {"success": False, "error": error_msg}


# ─── Background Job ──────────────────────────────────────────────────────────

async def process_queued_sold_deliveries():
    """Background job: process queued sold event deliveries with retries.
    
    Safety limits:
    - Max 10 events per run (prevents 50×30s httpx calls from flooding the server)
    - Single shared httpx client for all deliveries in this run
    - Guard against concurrent runs via a module-level flag
    """
    global _delivery_running
    if _delivery_running:
        logger.debug("[SoldWorkflow] Skipping — previous delivery run still active")
        return
    _delivery_running = True

    db = get_db()
    now = datetime.now(timezone.utc)
    processed = 0

    try:
        queued = await db.sold_event_logs.find({
            "delivery_status": {"$in": ["queued", "retrying"]},
            "validation_status": "passed",
            "delivery_attempt_count": {"$lt": 3},
        }).to_list(10)  # reduced from 50 — prevents event loop flooding

        # Reuse a single httpx client for all events in this batch
        async with httpx.AsyncClient(timeout=15) as client:
            for event in queued:
                event_id = str(event["_id"])
                try:
                    result = await _deliver_with_client(client, db, event_id, event, now)
                    if not result.get("success") and event.get("delivery_attempt_count", 0) < 2:
                        from datetime import timedelta
                        retry_at = now + timedelta(minutes=15 * (event.get("delivery_attempt_count", 0) + 1))
                        await db.sold_event_logs.update_one(
                            {"_id": event["_id"]},
                            {"$set": {"delivery_status": "retrying", "next_retry_at": retry_at, "updated_at": now}}
                        )
                    processed += 1
                except Exception as e:
                    logger.error(f"[SoldWorkflow] Error processing delivery for event {event_id}: {e}")
    finally:
        _delivery_running = False

    if processed:
        logger.info(f"[SoldWorkflow] Processed {processed} queued deliveries")


async def _deliver_with_client(client: httpx.AsyncClient, db, event_id: str, event: dict, now) -> dict:
    """Deliver a single sold event using a shared httpx client."""
    partner_id = event.get("partner_id")
    if not partner_id:
        return {"success": False, "error": "No partner_id on event"}

    try:
        partner = await db.white_label_partners.find_one({"_id": ObjectId(partner_id)})
    except Exception:
        partner = None

    if not partner:
        return {"success": False, "error": "Partner not found"}

    delivery_config = partner.get("event_delivery", {})
    if not delivery_config.get("enabled"):
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"delivery_status": "not_sent", "error_message": "Endpoint not enabled", "updated_at": now}}
        )
        await db.contacts.update_one(
            {"_id": ObjectId(event.get("contact_id"))},
            {"$set": {"sold_workflow_status": "delivery_success", "updated_at": now}}
        )
        return {"success": True, "status": "endpoint_not_enabled"}

    endpoint_url = delivery_config.get("endpoint_url", "").strip()
    if not endpoint_url:
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"delivery_status": "failed", "error_message": "No endpoint URL configured", "updated_at": now}}
        )
        return {"success": False, "error": "No endpoint URL"}

    headers = {"Content-Type": "application/json"}
    auth_type = delivery_config.get("auth_type", "none")
    auth_value = delivery_config.get("auth_value_encrypted", "")
    if auth_type == "bearer" and auth_value:
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "api_key" and auth_value:
        headers["X-API-Key"] = auth_value

    payload = event.get("request_payload", event.get("payload_snapshot", {}))
    attempt = event.get("delivery_attempt_count", 0) + 1

    try:
        resp = await client.post(endpoint_url, json=payload, headers=headers)
        success = 200 <= resp.status_code < 300
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "delivery_status": "sent" if success else "failed",
                "delivery_attempt_count": attempt,
                "last_delivery_response_code": resp.status_code,
                "response_payload": resp.text[:2000],
                "error_message": "" if success else f"HTTP {resp.status_code}",
                "delivered_at": now if success else None,
                "updated_at": now,
            }}
        )
        await db.contacts.update_one(
            {"_id": ObjectId(event.get("contact_id"))},
            {"$set": {"sold_workflow_status": "delivery_success" if success else "delivery_failed", "updated_at": now}}
        )
        return {"success": success, "status_code": resp.status_code}
    except Exception as e:
        error_msg = str(e)[:500]
        await db.sold_event_logs.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"delivery_status": "failed", "delivery_attempt_count": attempt, "error_message": error_msg, "updated_at": now}}
        )
        await db.contacts.update_one(
            {"_id": ObjectId(event.get("contact_id"))},
            {"$set": {"sold_workflow_status": "delivery_failed", "sold_workflow_last_error": error_msg, "updated_at": now}}
        )
        logger.error(f"[SoldWorkflow] Delivery exception for event {event_id}: {error_msg}")
        return {"success": False, "error": error_msg}


# ─── API Endpoints ───────────────────────────────────────────────────────────

@router.post("/revalidate/{contact_id}")
async def api_revalidate(contact_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Re-validate sold workflow after user fixes missing fields."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID")
    result = await revalidate_sold_workflow(contact_id, x_user_id)
    if not result:
        raise HTTPException(status_code=404, detail="No failed sold event found for this contact")
    return result


@router.post("/retry/{log_id}")
async def api_retry_delivery(log_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Admin manual retry for a failed delivery."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID")
    db = get_db()

    # Reset delivery status to queued
    event = await db.sold_event_logs.find_one({"_id": ObjectId(log_id)})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.get("delivery_status") not in ("failed", "not_sent"):
        raise HTTPException(status_code=400, detail=f"Cannot retry event in status: {event.get('delivery_status')}")

    now = datetime.now(timezone.utc)
    await db.sold_event_logs.update_one(
        {"_id": ObjectId(log_id)},
        {"$set": {
            "delivery_status": "queued",
            "trigger_source": "manual_retry",
            "delivery_attempt_count": 0,
            "updated_at": now,
        }}
    )
    result = await deliver_sold_event(log_id)
    return result


@router.get("/contact/{contact_id}")
async def get_contact_sold_status(contact_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get sold workflow status and event history for a contact."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID")
    db = get_db()

    events = await db.sold_event_logs.find(
        {"contact_id": contact_id},
        {"_id": 1, "validation_status": 1, "missing_fields": 1, "delivery_status": 1,
         "delivery_attempt_count": 1, "last_delivery_response_code": 1, "error_message": 1,
         "trigger_source": 1, "created_at": 1, "delivered_at": 1}
    ).sort("created_at", -1).to_list(20)

    for e in events:
        e["_id"] = str(e["_id"])
        for k in ("created_at", "delivered_at"):
            if isinstance(e.get(k), datetime):
                e[k] = e[k].isoformat()

    # Get partner config for this user (to know deal_or_stock_mode)
    partner, store = await _resolve_partner_config(x_user_id)
    deal_or_stock_mode = (store or {}).get("deal_or_stock_mode", "stock_number") if store else None

    return {
        "events": events,
        "deal_or_stock_mode": deal_or_stock_mode,
        "partner_name": partner.get("name") if partner else None,
        "has_partner": partner is not None,
    }


@router.get("/partner/{partner_id}/events")
async def get_partner_sold_events(partner_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Admin view: all sold events for a partner."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID")
    db = get_db()

    events = await db.sold_event_logs.find(
        {"partner_id": partner_id},
        {"_id": 1, "contact_id": 1, "account_id": 1, "external_account_id": 1,
         "validation_status": 1, "delivery_status": 1, "missing_fields": 1,
         "error_message": 1, "trigger_source": 1, "created_at": 1, "delivered_at": 1}
    ).sort("created_at", -1).to_list(100)

    for e in events:
        e["_id"] = str(e["_id"])
        for k in ("created_at", "delivered_at"):
            if isinstance(e.get(k), datetime):
                e[k] = e[k].isoformat()

    return events
