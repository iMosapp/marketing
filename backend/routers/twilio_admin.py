"""
Twilio Admin Router
Full accounting + management for all purchased phone numbers.
Covers: inventory, activity, search, purchase, assign, release, pool management.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from routers.database import get_db
from routers.rbac import require_role

router = APIRouter(prefix="/admin/twilio", tags=["twilio-admin"],
                   dependencies=[Depends(require_role("super_admin"))])
logger = logging.getLogger(__name__)

APP_URL = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
WEBHOOK_URL = f"{APP_URL}/api/webhooks/twilio/incoming"
NUMBER_MONTHLY_COST = 1.15  # USD — standard Twilio local number rate


def _get_twilio_client():
    from twilio.rest import Client
    sid   = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise HTTPException(status_code=503, detail="Twilio credentials not configured")
    return Client(sid, token)


async def _twilio_call(fn, *args, timeout: float = 15.0, **kwargs):
    """Run a synchronous Twilio API call in a thread with a timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(fn, *args, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Twilio API timed out — check your Account SID and Auth Token are correct.")


async def _me(request: Request) -> dict:
    from routers.scripts import _resolve
    return await _resolve(request) or {}


async def _registry_number(db, number_sid: str) -> dict:
    """The registry row for a Twilio SID; legacy numbers bought before the registry existed are adopted on first touch."""
    from services import phone_numbers as pn
    num = await pn.by_sid(db, number_sid)
    if num:
        return num
    client = _get_twilio_client()
    tn = await _twilio_call(client.incoming_phone_numbers(number_sid).fetch)
    holder = await db.users.find_one({"$or": [{"mvpline_number": tn.phone_number}, {"twilio_number": tn.phone_number}]}, {"organization_id": 1, "store_id": 1})
    return await pn.adopt(db, phone_number=tn.phone_number, sid=tn.sid, account_sid=tn.account_sid, org_id=(holder or {}).get("organization_id"),
                          location_id=(holder or {}).get("store_id"), assigned_user_id=str(holder["_id"]) if holder else None, number_type="USER" if holder else "STORE",
                          friendly_name=tn.friendly_name or "", sms_url=tn.sms_url or "", voice_url=tn.voice_url or "", actor="system", note="adopted from legacy admin action")


# ── Inventory ─────────────────────────────────────────────────────────────────

@router.get("/numbers")
async def list_numbers():
    """
    Full inventory: every purchased number on the Twilio account,
    enriched with DB data (owner, last activity, contact count, cost).
    """
    db = get_db()

    # Fetch from Twilio
    try:
        client = _get_twilio_client()
        twilio_numbers = await _twilio_call(client.incoming_phone_numbers.list)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"[TwilioAdmin] numbers list failed: {e}")
        raise HTTPException(status_code=502, detail=f"Could not connect to Twilio. Verify your Account SID and Auth Token are correct in Settings. ({type(e).__name__})")

    result = []
    for tn in twilio_numbers:
        phone = tn.phone_number

        # Find assigned user (check both mvpline_number and twilio_number)
        user = await db.users.find_one(
            {"$or": [{"mvpline_number": phone}, {"twilio_number": phone}]},
            {"name": 1, "email": 1, "photo_url": 1, "role": 1, "store_id": 1, "status": 1}
        )
        user_id = str(user["_id"]) if user else None

        # Check pool for previous owner info (for unassigned/pool numbers)
        pool_entry = None
        if not user:
            pool_entry = await db.phone_number_pool.find_one({"phone_number": phone})

        # Find store
        store = None
        if user and user.get("store_id"):
            try:
                store = await db.stores.find_one(
                    {"_id": ObjectId(user["store_id"])}, {"name": 1}
                )
            except Exception:
                pass

        # Last activity (last message sent or received from this number)
        last_msg = await db.messages.find_one(
            {"$or": [
                {"from_number": phone},
                {"to_number": phone},
                {"twilio_from": phone},
            ]},
            sort=[("timestamp", -1)]
        )
        last_activity = None
        last_activity_type = None
        if last_msg:
            ts = last_msg.get("timestamp") or last_msg.get("created_at")
            if ts:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                last_activity = ts.isoformat()
                last_activity_type = last_msg.get("direction", "unknown")

        # Contact count (contacts with this user)
        contact_count = 0
        if user_id:
            contact_count = await db.contacts.count_documents({"user_id": user_id})

        # Message volume this month
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        msgs_this_month = await db.messages.count_documents({
            "$or": [{"from_number": phone}, {"to_number": phone}],
            "timestamp": {"$gte": month_start.replace(tzinfo=None)},
        })

        # Webhook status
        webhook_configured = bool(tn.sms_url and "demo.twilio.com" not in (tn.sms_url or ""))
        webhook_correct = tn.sms_url == WEBHOOK_URL if tn.sms_url else False

        result.append({
            "sid":                 tn.sid,
            "phone_number":        phone,
            "friendly_name":       tn.friendly_name or phone,
            "date_purchased":      tn.date_created.isoformat() if tn.date_created else None,
            "capabilities": {
                "sms":   tn.capabilities.get("sms", False),
                "mms":   tn.capabilities.get("mms", False),
                "voice": tn.capabilities.get("voice", False),
            },
            "webhook_url":         tn.sms_url,
            "webhook_configured":  webhook_configured,
            "webhook_correct":     webhook_correct,
            "monthly_cost_usd":    NUMBER_MONTHLY_COST,
            # DB-enriched data
            "assigned_to": {
                "user_id":   user_id,
                "name":      user.get("name") if user else None,
                "email":     user.get("email") if user else None,
                "photo_url": user.get("photo_url") if user else None,
                "role":      user.get("role") if user else None,
                "active":    (user.get("status") or "active") == "active" if user else False,
            } if user else None,
            "store_name":          store.get("name") if store else None,
            "status":              "assigned" if user else "pool",
            "previous_owner": {
                "name":       pool_entry.get("previous_user_name") if pool_entry else None,
                "email":      pool_entry.get("previous_user_email") if pool_entry else None,
                "store_id":   pool_entry.get("previous_store_id") if pool_entry else None,
                "released_at": pool_entry["released_at"].isoformat() if pool_entry and pool_entry.get("released_at") else None,
            } if pool_entry and pool_entry.get("previous_user_name") else None,
            "last_activity":       last_activity,
            "last_activity_type":  last_activity_type,
            "contact_count":       contact_count,
            "messages_this_month": msgs_this_month,
        })

    # Sort: assigned first, then pool; within each group newest first
    result.sort(key=lambda x: (0 if x["assigned_to"] else 1, x["date_purchased"] or ""))
    return {"numbers": result, "total": len(result)}


@router.get("/stats")
async def get_twilio_stats():
    """Summary stats for the accounting dashboard header."""
    try:
        client = _get_twilio_client()
        numbers = await _twilio_call(client.incoming_phone_numbers.list)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    db = get_db()
    total = len(numbers)
    monthly_cost = total * NUMBER_MONTHLY_COST

    # Count assigned vs pool
    assigned = 0
    for n in numbers:
        user = await db.users.find_one(
            {"$or": [{"mvpline_number": n.phone_number}, {"twilio_number": n.phone_number}]},
            {"_id": 1}
        )
        if user:
            assigned += 1

    # Messages this month across all numbers
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    msgs_month = await db.messages.count_documents({
        "timestamp": {"$gte": month_start.replace(tzinfo=None)},
        "channel": {"$in": ["sms", "sms_personal", "mms"]},
    })

    return {
        "total_numbers":       total,
        "assigned":            assigned,
        "in_pool":             total - assigned,
        "monthly_cost_usd":    round(monthly_cost, 2),
        "messages_this_month": msgs_month,
        "messaging_service_sid": os.environ.get("TWILIO_MESSAGING_SERVICE_SID"),
        "account_sid":         (os.environ.get("TWILIO_ACCOUNT_SID") or "")[:8] + "...",
    }


@router.get("/status")
async def get_twilio_live_status():
    """Full Twilio configuration status — LIVE vs MOCK, compliance checks."""
    from services.twilio_service import TWILIO_ENABLED, USE_MESSAGING_SERVICE, TWILIO_PHONE_NUMBER, TWILIO_MESSAGING_SERVICE_SID
    db = get_db()

    # Count push subscriptions
    push_subs = await db.push_subscriptions.count_documents({})
    # Recent SMS (last 24h)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_sms = await db.messages.count_documents({
        "timestamp": {"$gte": cutoff.replace(tzinfo=None)},
        "channel": {"$in": ["sms", "mms"]},
    })
    # Count mock vs live
    mock_sms = await db.messages.count_documents({
        "status": "sent_mock",
        "timestamp": {"$gte": cutoff.replace(tzinfo=None)},
    })

    return {
        "twilio_sms": {
            "status": "LIVE" if TWILIO_ENABLED else "MOCK",
            "enabled": TWILIO_ENABLED,
            "sender": "Messaging Service (A2P 10DLC)" if USE_MESSAGING_SERVICE else "Direct Phone Number",
            "phone_number": TWILIO_PHONE_NUMBER,
            "messaging_service_sid": TWILIO_MESSAGING_SERVICE_SID,
            "a2p_compliant": USE_MESSAGING_SERVICE,
        },
        "sms_stats_24h": {
            "total": recent_sms,
            "mock": mock_sms,
            "live": recent_sms - mock_sms,
        },
        "push_notifications": {
            "vapid_configured": bool(os.environ.get("VAPID_PRIVATE_KEY")),
            "active_subscriptions": push_subs,
        },
    }


@router.post("/test-sms")
async def send_test_sms(request: Request):
    """Send a test SMS to verify Twilio is live. Admin only."""
    data = await request.json()
    to_phone = data.get("to_phone", "").strip()
    if not to_phone:
        raise HTTPException(status_code=400, detail="to_phone required")
    from services.twilio_service import send_sms
    result = await send_sms(to_phone, "I'm On Social test SMS — Twilio is live and working!")
    return {
        "success": result.get("success"),
        "mock": result.get("mock", False),
        "message_sid": result.get("message_sid"),
        "error": result.get("error"),
    }



@router.get("/numbers/search")
async def search_available_numbers(
    area_code: Optional[str] = None,
    contains: Optional[str] = None,
    country: str = "US",
    limit: int = 10,
):
    """Search Twilio for available numbers by area code or pattern."""
    try:
        client = _get_twilio_client()
        params = {"limit": limit, "sms_enabled": True, "mms_enabled": True}
        if area_code:
            params["area_code"] = area_code
        if contains:
            params["contains"] = contains

        available = await _twilio_call(lambda: client.available_phone_numbers(country).local.list(**params))

        return {"numbers": [
            {
                "phone_number":    n.phone_number,
                "friendly_name":   n.friendly_name,
                "region":          n.region,
                "locality":        n.locality,
                "capabilities": {
                    "sms":   n.capabilities.get("SMS", False),
                    "mms":   n.capabilities.get("MMS", False),
                    "voice": n.capabilities.get("voice", False),
                },
                "monthly_cost_usd": NUMBER_MONTHLY_COST,
            }
            for n in available
        ]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Twilio search failed: {e}")


@router.post("/numbers/purchase")
async def purchase_number(request: Request):
    """
    Purchase a number from Twilio, configure the inbound webhook,
    add to the Messaging Service, register it and optionally assign it to a user.
    (Legacy entry point: routes through services.phone_numbers so the registry stays the source of truth.)
    """
    db   = get_db()
    data = await request.json()
    phone_number = data.get("phone_number")
    assign_user_id = data.get("user_id")

    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number required")

    from services import phone_numbers as pn
    from services import twilio_tenant as tenant
    me = await _me(request)
    org = None
    if assign_user_id and ObjectId.is_valid(str(assign_user_id)):
        u = await db.users.find_one({"_id": ObjectId(assign_user_id)}, {"organization_id": 1})
        org = await tenant.org_by_id(db, (u or {}).get("organization_id"))
    if not org and data.get("organization_id"):
        org = await tenant.org_by_id(db, data["organization_id"])
    try:
        out = await pn.purchase(db, org=org, phone_number=phone_number, number_type=(data.get("number_type") or ("USER" if assign_user_id else "STORE")),
                                location_id=data.get("location_id"), assigned_user_id=assign_user_id, actor=me, friendly_name=data.get("friendly_name") or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Purchase failed: {e}")
    return {"success": True, "phone_number": out["phone_number"], "sid": out["twilio_phone_number_sid"], "assigned_to": assign_user_id,
            "webhook_set": out["incoming_sms_webhook"], "number_id": out["id"], "dry_run": out.get("dry_run", False)}


@router.get("/pool")
async def get_number_pool():
    """List all numbers currently in the pool (unassigned, previously used by terminated reps)."""
    db = get_db()
    pool_entries = await db.phone_number_pool.find(
        {"status": "pool"}
    ).sort("released_at", -1).to_list(100)

    result = []
    for entry in pool_entries:
        # Resolve store name
        store_name = None
        if entry.get("previous_store_id"):
            try:
                store = await db.stores.find_one(
                    {"_id": ObjectId(entry["previous_store_id"])}, {"name": 1}
                )
                if store:
                    store_name = store.get("name")
            except Exception:
                pass

        released_at = entry.get("released_at")
        result.append({
            "phone_number":        entry.get("phone_number"),
            "twilio_sid":          entry.get("twilio_sid"),
            "previous_user_name":  entry.get("previous_user_name"),
            "previous_user_email": entry.get("previous_user_email"),
            "previous_store_id":   entry.get("previous_store_id"),
            "previous_store_name": store_name,
            "released_at":         released_at.isoformat() if released_at else None,
            "released_by":         entry.get("released_by"),
        })

    return {"pool": result, "count": len(result)}


# ── Assign / Pool / Release ───────────────────────────────────────────────────

@router.post("/numbers/{number_sid}/assign")
async def assign_number(number_sid: str, request: Request):
    """Assign a number to a user (or move to pool if no user_id given). Legacy entry point, goes through the registry."""
    db   = get_db()
    data = await request.json()
    user_id = data.get("user_id")
    from services import phone_numbers as pn
    me = await _me(request)
    try:
        num = await _registry_number(db, number_sid)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Number not found: {e}")
    try:
        out = await pn.assign(db, num, user_id, me) if user_id else await pn.unassign(db, num, me, "moved to pool")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "phone_number": out["phone_number"], "status": "assigned" if user_id else "pool", "assigned_to": user_id, "number_id": str(out["_id"])}


@router.post("/numbers/{number_sid}/fix-webhook")
async def fix_webhook(number_sid: str):
    """Set the correct inbound webhook on a number (fixes demo/missing webhooks)."""
    try:
        client = _get_twilio_client()
        updated = await _twilio_call(client.incoming_phone_numbers(number_sid).update,
            sms_url=WEBHOOK_URL,
            sms_method="POST",
        )
        return {"success": True, "phone_number": updated.phone_number, "webhook_url": WEBHOOK_URL}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/numbers/{number_sid}")
async def release_number(number_sid: str, request: Request):
    """Release a number back to Twilio (permanent — stops billing). Legacy entry point, goes through the registry."""
    db = get_db()
    from services import phone_numbers as pn
    me = await _me(request)
    try:
        num = await _registry_number(db, number_sid)
        out = await pn.release(db, num, me, "released from Phone Numbers screen")
        logger.info(f"[Twilio] Released {out['phone_number']}")
        return {"success": True, "phone_number": out["phone_number"], "message": "Number released and billing stopped."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Multi-tenant: organizations overview, migration report, flags, audit ──────

@router.get("/orgs")
async def orgs_overview():
    """Every organization with its Twilio readiness in one line (Admin -> Organizations badges)."""
    from services import twilio_tenant as tenant
    return {"organizations": await tenant.overview(get_db())}


@router.get("/migration-report")
async def migration_report():
    """Read-only mapping of every number IMOS / Twilio knows about. Nothing is moved or released."""
    from services import phone_numbers as pn
    return await pn.migration_report(get_db())


@router.post("/migration-report/import")
async def migration_import(request: Request):
    """Register the importable rows (or the given phone_numbers) in the phone_numbers registry. No Twilio writes."""
    from services import phone_numbers as pn
    data = await request.json() if (request.headers.get("content-type") or "").startswith("application/json") else {}
    return await pn.import_report(get_db(), actor=await _me(request), phones=data.get("phone_numbers"))


@router.get("/registry")
async def registry(include_released: bool = False):
    from services import phone_numbers as pn
    return {"numbers": await pn.list_all(get_db(), include_released)}


@router.get("/flags")
async def get_flags():
    from services import twilio_tenant as tenant
    from services.twilio_signature import mode as sig_mode
    return {**(await tenant.flags(get_db())), "webhook_validation": sig_mode()}


@router.put("/flags")
async def put_flags(request: Request):
    from services import twilio_tenant as tenant
    from services.twilio_signature import mode as sig_mode
    data = await request.json()
    me = await _me(request)
    out = await tenant.set_flags(get_db(), data, me)
    await tenant.audit(get_db(), action="flags_changed", actor=me, details={k: data[k] for k in ("enforce_ready", "auto_provision") if k in data})
    return {**out, "webhook_validation": sig_mode()}


@router.get("/audit")
async def audit_all(limit: int = 200, organization_id: Optional[str] = None):
    from services import twilio_tenant as tenant
    return {"entries": await tenant.audit_list(get_db(), organization_id, limit=min(limit, 500), full=True)}
