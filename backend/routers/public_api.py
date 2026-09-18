"""Public API v1: API-key access for CRMs and automation tools.
Every request is scoped to the store (or organization) that issued the key. Keys are created in-app
(Tools -> Integrations -> API Keys) and stored hashed; the plaintext is shown once.
Docs: https://www.imonsocial.com/developers  |  OpenAPI: GET /api/public/openapi-v1.json"""
import csv
import hashlib
import io
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from services.contact_match import NOT_MERGED, find_existing_contact, phone_clause, store_user_ids
from services.twilio_service import normalize_phone

from .database import get_db
from .webhook_subscriptions import EVENT_TYPES, build_event, deliver, delivery_logs, public_subscription, validate_events

router = APIRouter(prefix="/v1", tags=["Public API v1"])
logger = logging.getLogger(__name__)

RATE_LIMIT_PER_MINUTE = 120
_buckets: dict = {}

CONTACT_WRITE_FIELDS = {
    "first_name", "last_name", "phone", "email", "email_work", "phones", "emails", "organization_name", "occupation", "employer",
    "vehicle", "vehicle_interest", "notes", "tags", "source", "external_id", "external_ids", "birthday", "anniversary",
    "address_street", "address_city", "address_state", "address_zip", "personal_details", "photo_url", "customer_number",
}
CONTACT_HIDE = {"photo": 0, "photo_thumbnail": 0}
USER_FIELDS = {"first_name": 1, "last_name": 1, "name": 1, "email": 1, "phone": 1, "role": 1, "title": 1, "status": 1,
               "store_id": 1, "organization_id": 1, "twilio_number": 1, "created_at": 1}


def serialize(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            out["id" if k == "_id" else k] = serialize(v)
        return out
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return (doc if doc.tzinfo else doc.replace(tzinfo=timezone.utc)).isoformat()
    return doc


def _oid(value: str, what: str = "Record") -> ObjectId:
    if not value or not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(value)


def _aware(d):
    return d if not isinstance(d, datetime) or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _parse_dt(value: Optional[str], name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} must be an ISO-8601 timestamp, e.g. 2026-09-01T00:00:00Z")
    return _aware(d)


# ============= AUTH =============

async def verify_api_key(request: Request, x_api_key: str = Header(None, alias="X-API-Key")):
    """Resolve the key (hashed or legacy plaintext), enforce active/expiry + rate limit, attach the tenant scope."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    db = get_db()
    now = datetime.now(timezone.utc)
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    doc = await db.api_keys.find_one({"key_hash": key_hash}) or await db.api_keys.find_one({"key": x_api_key})
    org = None
    if not doc:
        org = await db.organizations.find_one({"api_key": x_api_key}, {"name": 1})
        if not org:
            raise HTTPException(status_code=401, detail="Invalid API key")
    if doc:
        if doc.get("active") is False or doc.get("is_active") is False:
            raise HTTPException(status_code=401, detail="API key revoked")
        exp = _aware(doc.get("expires_at"))
        if exp and exp < now:
            raise HTTPException(status_code=401, detail="API key expired")

    bucket_id = str(doc["_id"]) if doc else f"org:{org['_id']}"
    q = _buckets.setdefault(bucket_id, deque())
    t = time.monotonic()
    while q and t - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail=f"Rate limit is {RATE_LIMIT_PER_MINUTE} requests per minute per key", headers={"Retry-After": "60"})
    q.append(t)

    if doc:
        await db.api_keys.update_one({"_id": doc["_id"]}, {"$set": {"last_used_at": now, "last_used": now}, "$inc": {"request_count": 1, "usage_count": 1}})
        scopes = doc.get("scopes") or (["read"] if doc.get("scope") == "read_only" else ["read", "write"])
        auth = {"key_id": bucket_id, "name": doc.get("name"), "scopes": scopes, "store_id": doc.get("store_id"),
                "org_id": doc.get("organization_id"), "user_id": doc.get("created_by")}
    else:
        auth = {"key_id": bucket_id, "name": org.get("name"), "scopes": ["read", "write"], "store_id": None, "org_id": str(org["_id"]), "user_id": None}
    auth["tenant"] = await _tenant(db, auth)
    request.state.api_auth = auth
    return auth


async def _tenant(db, auth: dict) -> dict:
    """The users and stores this key may see. Store keys see one store; org keys see every store in the org."""
    org_id, store_ids, user_ids = auth.get("org_id"), [], []
    if auth.get("store_id"):
        store = await db.stores.find_one({"_id": _oid(auth["store_id"], "Store")}, {"organization_id": 1, "name": 1})
        if store:
            org_id = org_id or store.get("organization_id")
        store_ids = [auth["store_id"]]
        user_ids = await store_user_ids(db, auth["store_id"])
    elif org_id:
        store_ids = [str(s["_id"]) async for s in db.stores.find({"organization_id": org_id}, {"_id": 1})]
        user_ids = [str(u["_id"]) async for u in db.users.find({"organization_id": org_id}, {"_id": 1})]
    elif auth.get("user_id"):
        user_ids = [auth["user_id"]]
    return {"org_id": org_id, "store_ids": store_ids, "user_ids": user_ids}


def _require_write(auth: dict):
    if "write" not in (auth.get("scopes") or []):
        raise HTTPException(status_code=403, detail="This API key is read-only")


def _contact_scope(auth: dict) -> dict:
    t = auth["tenant"]
    if not t["user_ids"] and not t["store_ids"]:
        return {"_id": None}
    return {"$or": [{"user_id": {"$in": t["user_ids"]}}, {"store_id": {"$in": t["store_ids"]}}], "status": NOT_MERGED}


def _owner_scope(auth: dict) -> dict:
    t = auth["tenant"]
    ors = []
    if t["user_ids"]:
        ors.append({"user_id": {"$in": t["user_ids"]}})
    if t["store_ids"]:
        ors.append({"store_id": {"$in": t["store_ids"]}})
    return {"$or": ors} if ors else {"_id": None}


def _in_tenant_user(auth: dict, user_id: Optional[str]) -> bool:
    return bool(user_id) and user_id in auth["tenant"]["user_ids"]


async def _contact(db, auth: dict, contact_id: str) -> dict:
    c = await db.contacts.find_one({"_id": _oid(contact_id, "Contact"), **_contact_scope(auth)}, CONTACT_HIDE)
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c


async def _default_owner(db, auth: dict) -> Optional[str]:
    """Who owns an API-created contact when the caller does not say: the key's creator, else the store manager, else any rep."""
    t = auth["tenant"]
    if _in_tenant_user(auth, auth.get("user_id")):
        return auth["user_id"]
    if not t["user_ids"]:
        return None
    oids = [ObjectId(u) for u in t["user_ids"] if ObjectId.is_valid(u)]
    mgr = await db.users.find_one({"_id": {"$in": oids}, "role": {"$in": ["store_manager", "org_admin"]}, "status": {"$nin": ["deactivated", "inactive"]}}, {"_id": 1})
    if mgr:
        return str(mgr["_id"])
    any_user = await db.users.find_one({"_id": {"$in": oids}, "status": {"$nin": ["deactivated", "inactive"]}}, {"_id": 1})
    return str(any_user["_id"]) if any_user else t["user_ids"][0]


def _clean_contact_fields(data: dict) -> dict:
    out = {k: v for k, v in data.items() if k in CONTACT_WRITE_FIELDS}
    if out.get("phone"):
        out["phone"] = normalize_phone(str(out["phone"]))
    if "tags" in out and not isinstance(out["tags"], list):
        raise HTTPException(status_code=400, detail="tags must be a list of strings")
    if "external_ids" in out and not isinstance(out["external_ids"], dict):
        raise HTTPException(status_code=400, detail="external_ids must be an object like {\"hubspot\": \"12345\"}")
    return out


# ============= ME =============

@router.get("/me")
async def api_me(auth: dict = Depends(verify_api_key)):
    """Who am I? Confirms the key works and shows exactly what it can see."""
    db = get_db()
    t = auth["tenant"]
    store = await db.stores.find_one({"_id": ObjectId(t["store_ids"][0])}, {"name": 1}) if len(t["store_ids"]) == 1 and ObjectId.is_valid(t["store_ids"][0]) else None
    org = await db.organizations.find_one({"_id": ObjectId(t["org_id"])}, {"name": 1}) if t.get("org_id") and ObjectId.is_valid(t["org_id"]) else None
    return {
        "key_name": auth.get("name"), "scopes": auth["scopes"],
        "store": {"id": t["store_ids"][0], "name": store.get("name") if store else None} if len(t["store_ids"]) == 1 else None,
        "organization": {"id": t["org_id"], "name": org.get("name") if org else None} if t.get("org_id") else None,
        "stores_visible": len(t["store_ids"]), "users_visible": len(t["user_ids"]),
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE, "docs": "https://www.imonsocial.com/developers",
    }


# ============= CONTACTS =============

@router.get("/contacts")
async def api_list_contacts(
    auth: dict = Depends(verify_api_key),
    search: Optional[str] = Query(None, description="Matches first name, last name, phone or email"),
    phone: Optional[str] = Query(None, description="Exact phone match (any format)"),
    email: Optional[str] = None,
    external_id: Optional[str] = Query(None, description="Your CRM's record id (matches external_id or any external_ids value)"),
    tag: Optional[str] = None,
    source: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    updated_since: Optional[str] = Query(None, description="ISO-8601; only contacts changed after this moment (use for incremental sync)"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    db = get_db()
    query = _contact_scope(auth)
    ands = []
    if search:
        ands.append({"$or": [{"first_name": {"$regex": search, "$options": "i"}}, {"last_name": {"$regex": search, "$options": "i"}},
                             {"phone": {"$regex": search, "$options": "i"}}, {"email": {"$regex": search, "$options": "i"}}]})
    if phone:
        ands.append(phone_clause(phone) or {"_id": None})
    if email:
        ands.append({"$or": [{"email": {"$regex": f"^{email}$", "$options": "i"}}, {"email_work": {"$regex": f"^{email}$", "$options": "i"}}]})
    if external_id:
        ands.append({"$or": [{"external_id": external_id}, {"crm_id": external_id}, {"$expr": {"$in": [external_id, {"$map": {"input": {"$objectToArray": {"$ifNull": ["$external_ids", {}]}}, "as": "e", "in": "$$e.v"}}]}}]})
    if tag:
        query["tags"] = tag
    if source:
        query["source"] = source
    if owner_user_id:
        query["user_id"] = owner_user_id
    since = _parse_dt(updated_since, "updated_since")
    if since:
        query["updated_at"] = {"$gt": since}
    if ands:
        query["$and"] = ands
    total = await db.contacts.count_documents(query)
    rows = await db.contacts.find(query, CONTACT_HIDE).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"contacts": serialize(rows), "total": total, "limit": limit, "offset": offset}


@router.get("/contacts/{contact_id}")
async def api_get_contact(contact_id: str, auth: dict = Depends(verify_api_key)):
    db = get_db()
    return serialize(await _contact(db, auth, contact_id))


@router.post("/contacts")
async def api_upsert_contact(data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    """Create or update. Matches an existing contact by external_id, then phone, then email; never creates duplicates."""
    _require_write(auth)
    db = get_db()
    fields = _clean_contact_fields(data)
    if not (fields.get("phone") or fields.get("email") or fields.get("external_id")):
        raise HTTPException(status_code=400, detail="phone, email or external_id is required")
    owner = data.get("owner_user_id")
    if owner and not _in_tenant_user(auth, owner):
        raise HTTPException(status_code=400, detail="owner_user_id is not a rep in this store")
    if not owner and data.get("owner_email"):
        u = await db.users.find_one({"email": {"$regex": f"^{data['owner_email']}$", "$options": "i"}}, {"_id": 1})
        if u and _in_tenant_user(auth, str(u["_id"])):
            owner = str(u["_id"])
    now = datetime.now(timezone.utc)
    t = auth["tenant"]

    existing = None
    if fields.get("external_id"):
        existing = await db.contacts.find_one({**_contact_scope(auth), "$or": [{"external_id": fields["external_id"]}, {"crm_id": fields["external_id"]}]}, CONTACT_HIDE)
    if not existing and fields.get("external_ids"):
        for sys_name, ext in fields["external_ids"].items():
            existing = await db.contacts.find_one({**_contact_scope(auth), f"external_ids.{sys_name}": str(ext)}, CONTACT_HIDE)
            if existing:
                break
    if not existing:
        store_id = t["store_ids"][0] if len(t["store_ids"]) == 1 else None
        existing, _how, _conflict = await find_existing_contact(db, fields.get("phone") or "", fields.get("email") or "", fields.get("first_name") or "",
                                                                fields.get("last_name") or "", store_id or "", extra_owner_ids=t["user_ids"])

    if existing:
        upd = {k: v for k, v in fields.items() if k not in ("tags", "external_ids", "notes")}
        upd["updated_at"] = now
        ops = {"$set": upd}
        if fields.get("tags"):
            ops["$addToSet"] = {"tags": {"$each": fields["tags"]}}
        if fields.get("external_ids"):
            for sys_name, ext in fields["external_ids"].items():
                upd[f"external_ids.{sys_name}"] = str(ext)
        if fields.get("notes") and fields["notes"] not in (existing.get("notes") or ""):
            upd["notes"] = ((existing.get("notes") or "").rstrip() + "\n\n" + fields["notes"]).strip()
        if owner:
            upd["user_id"] = owner
        await db.contacts.update_one({"_id": existing["_id"]}, ops)
        return {"id": str(existing["_id"]), "created": False, "message": "Existing contact updated"}

    owner = owner or await _default_owner(db, auth)
    if not owner:
        raise HTTPException(status_code=400, detail="This key has no reps to assign the contact to")
    doc = {**fields, "user_id": owner, "store_id": t["store_ids"][0] if len(t["store_ids"]) == 1 else None,
           "source": fields.get("source") or "api", "ownership_type": "org", "status": "active", "tags": fields.get("tags") or [],
           "created_at": now, "updated_at": now}
    if doc.get("external_ids"):
        doc["external_ids"] = {k: str(v) for k, v in doc["external_ids"].items()}
    result = await db.contacts.insert_one(doc)
    return {"id": str(result.inserted_id), "created": True, "message": "Contact created"}


@router.put("/contacts/{contact_id}")
async def api_update_contact(contact_id: str, data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    fields = _clean_contact_fields(data)
    if data.get("owner_user_id"):
        if not _in_tenant_user(auth, data["owner_user_id"]):
            raise HTTPException(status_code=400, detail="owner_user_id is not a rep in this store")
        fields["user_id"] = data["owner_user_id"]
    if not fields:
        raise HTTPException(status_code=400, detail="No writable fields in body")
    if "external_ids" in fields:
        merged = {**(c.get("external_ids") or {}), **{k: str(v) for k, v in fields.pop("external_ids").items()}}
        fields["external_ids"] = merged
    fields["updated_at"] = datetime.now(timezone.utc)
    await db.contacts.update_one({"_id": c["_id"]}, {"$set": fields})
    return {"id": contact_id, "message": "Contact updated"}


@router.delete("/contacts/{contact_id}")
async def api_delete_contact(contact_id: str, auth: dict = Depends(verify_api_key)):
    """Soft delete: the contact is hidden from the rep and excluded from lists, history is kept."""
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    now = datetime.now(timezone.utc)
    await db.contacts.update_one({"_id": c["_id"]}, {"$set": {"status": "hidden", "hidden_at": now, "updated_at": now}})
    return {"id": contact_id, "message": "Contact hidden"}


@router.post("/contacts/{contact_id}/tags")
async def api_add_tag(contact_id: str, data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    tag = (data.get("tag") or "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="tag is required")
    await db.contacts.update_one({"_id": c["_id"]}, {"$addToSet": {"tags": tag}, "$set": {"updated_at": datetime.now(timezone.utc)}})
    return {"id": contact_id, "tags": sorted(set((c.get("tags") or []) + [tag]))}


@router.delete("/contacts/{contact_id}/tags/{tag}")
async def api_remove_tag(contact_id: str, tag: str, auth: dict = Depends(verify_api_key)):
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    await db.contacts.update_one({"_id": c["_id"]}, {"$pull": {"tags": tag}, "$set": {"updated_at": datetime.now(timezone.utc)}})
    return {"id": contact_id, "tags": [x for x in (c.get("tags") or []) if x != tag]}


@router.get("/contacts/{contact_id}/notes")
async def api_get_notes(contact_id: str, auth: dict = Depends(verify_api_key)):
    db = get_db()
    c = await _contact(db, auth, contact_id)
    return {"id": contact_id, "notes": c.get("notes") or ""}


@router.post("/contacts/{contact_id}/notes")
async def api_add_note(contact_id: str, data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    """Appends to the rep's notes (never overwrites) and logs a note_added event on the timeline."""
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    note = (data.get("note") or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="note is required")
    now = datetime.now(timezone.utc)
    label = (data.get("source") or "API").strip()
    entry = f"[{now.strftime('%b %d, %Y')} via {label}] {note}"
    notes = ((c.get("notes") or "").rstrip() + "\n\n" + entry).strip()
    await db.contacts.update_one({"_id": c["_id"]}, {"$set": {"notes": notes, "updated_at": now}})
    await db.contact_events.insert_one({"contact_id": contact_id, "user_id": c.get("user_id"), "event_type": "note_added", "title": f"Note added via {label}",
                                        "description": note[:1000], "source": "api", "icon": "document-text", "color": "#5856D6", "timestamp": now})
    return {"id": contact_id, "notes": notes}


@router.get("/contacts/{contact_id}/events")
async def api_get_contact_events(contact_id: str, auth: dict = Depends(verify_api_key), limit: int = Query(default=100, le=500), offset: int = 0):
    """The contact's activity timeline: texts, calls, cards, review requests, notes, sales, tasks."""
    db = get_db()
    await _contact(db, auth, contact_id)
    rows = await db.contact_events.find({"contact_id": contact_id}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
    return {"events": serialize(rows), "limit": limit, "offset": offset}


@router.post("/contacts/{contact_id}/events")
async def api_log_contact_event(contact_id: str, data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    """Log something that happened in your system onto the contact's timeline (e.g. 'Appraisal completed in DealerCRM')."""
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    event = {"contact_id": contact_id, "user_id": c.get("user_id"), "event_type": (data.get("event_type") or "custom")[:60],
             "title": (data.get("title") or data.get("description") or "External event")[:200], "description": (data.get("description") or "")[:2000],
             "metadata": data.get("metadata") or {}, "source": "api", "icon": "git-network", "color": "#FF9500", "timestamp": datetime.now(timezone.utc)}
    result = await db.contact_events.insert_one(event)
    return {"event_id": str(result.inserted_id), "message": "Event logged"}


@router.get("/contacts/{contact_id}/messages")
async def api_contact_messages(contact_id: str, auth: dict = Depends(verify_api_key), limit: int = Query(default=100, le=500), offset: int = 0):
    """Every text/email exchanged with this contact across all of the rep's conversations, newest first."""
    db = get_db()
    await _contact(db, auth, contact_id)
    conv_ids = [str(cv["_id"]) async for cv in db.conversations.find({"contact_id": contact_id}, {"_id": 1})]
    q = {"conversation_id": {"$in": conv_ids}} if conv_ids else {"_id": None}
    total = await db.messages.count_documents(q)
    rows = await db.messages.find(q).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
    return {"messages": serialize(rows), "total": total, "limit": limit, "offset": offset}


@router.post("/contacts/{contact_id}/messages")
async def api_send_to_contact(contact_id: str, data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    """Send a real text from the rep's number (or email). Goes through the same pipeline as the app: conversation, Twilio, timeline."""
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    content = (data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    user_id = data.get("user_id") or c.get("user_id")
    if not _in_tenant_user(auth, user_id):
        raise HTTPException(status_code=400, detail="user_id must be a rep in this store")
    from .messages import send_message_simple
    result = await send_message_simple(user_id, {"contact_id": contact_id, "content": content, "channel": data.get("channel") or "sms"})
    return serialize(result)


@router.get("/contacts/{contact_id}/calls")
async def api_contact_calls(contact_id: str, auth: dict = Depends(verify_api_key), limit: int = Query(default=50, le=200)):
    """Call logs with duration, outcome, recording URL, transcript and AI summary when available."""
    db = get_db()
    await _contact(db, auth, contact_id)
    rows = await db.call_logs.find({"contact_id": contact_id}, {"transcript_segments": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"calls": serialize(rows)}


@router.get("/contacts/{contact_id}/purchases")
async def api_contact_purchases(contact_id: str, auth: dict = Depends(verify_api_key)):
    """Sold records (purchase history) for the contact."""
    db = get_db()
    c = await _contact(db, auth, contact_id)
    return {"id": contact_id, "purchases": c.get("purchase_history") or [], "date_sold": c.get("date_sold"), "vehicle": c.get("vehicle"), "sold_count": c.get("sold_count")}


@router.post("/contacts/{contact_id}/purchases")
async def api_add_purchase(contact_id: str, data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    """Record a sale. Same rules as the Sold wizard: merges with a matching record instead of duplicating, tags the contact sold."""
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, contact_id)
    title = (data.get("title") or data.get("vehicle") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title (what they bought) is required")
    from services import sales
    purchase = await sales.add_purchase(db, contact_id, title, data.get("category") or "vehicle", data.get("date"), data.get("notes") or "")
    now = datetime.now(timezone.utc)
    await db.contacts.update_one({"_id": c["_id"]}, {"$addToSet": {"tags": "sold"}, "$set": {"updated_at": now}})
    await db.contact_events.insert_one({"contact_id": contact_id, "user_id": c.get("user_id"), "event_type": "purchase_added", "title": f"Purchase recorded: {title}",
                                        "description": f"Date: {purchase.get('date') or 'unknown'}", "icon": "bag-handle", "color": "#C9A962",
                                        "timestamp": now, "category": "sale", "source": "api"})
    return {"id": contact_id, "purchase": purchase}


# ============= TASKS =============

@router.get("/tasks")
async def api_list_tasks(auth: dict = Depends(verify_api_key), status: Optional[str] = None, user_id: Optional[str] = None,
                         contact_id: Optional[str] = None, due_before: Optional[str] = None, due_after: Optional[str] = None,
                         limit: int = Query(default=100, le=500), offset: int = 0):
    db = get_db()
    q = {"user_id": {"$in": auth["tenant"]["user_ids"]}} if auth["tenant"]["user_ids"] else {"_id": None}
    if status:
        q["status"] = status
    if user_id:
        q["user_id"] = user_id if _in_tenant_user(auth, user_id) else "-"
    if contact_id:
        q["contact_id"] = contact_id
    due = {}
    if due_after:
        due["$gte"] = _parse_dt(due_after, "due_after")
    if due_before:
        due["$lte"] = _parse_dt(due_before, "due_before")
    if due:
        q["due_date"] = due
    total = await db.tasks.count_documents(q)
    rows = await db.tasks.find(q).sort("due_date", 1).skip(offset).limit(limit).to_list(limit)
    return {"tasks": serialize(rows), "total": total, "limit": limit, "offset": offset}


@router.post("/tasks")
async def api_create_task(data: dict = Body(...), auth: dict = Depends(verify_api_key)):
    """Put a follow-up on a rep's Today list. Idempotent when you send idempotency_key."""
    _require_write(auth)
    db = get_db()
    c = await _contact(db, auth, data.get("contact_id") or "")
    user_id = data.get("user_id") or c.get("user_id")
    if not _in_tenant_user(auth, user_id):
        raise HTTPException(status_code=400, detail="user_id must be a rep in this store")
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    now = datetime.now(timezone.utc)
    due = _parse_dt(data.get("due_date"), "due_date") or now
    if data.get("idempotency_key"):
        dup = await db.tasks.find_one({"idempotency_key": data["idempotency_key"], "user_id": user_id})
        if dup:
            return {"id": str(dup["_id"]), "created": False}
    task = {"user_id": user_id, "contact_id": str(c["_id"]), "type": data.get("type") or "follow_up", "title": title, "description": data.get("description") or "",
            "due_date": due, "priority": data.get("priority") or "medium", "status": "pending", "source": "api", "idempotency_key": data.get("idempotency_key"),
            "created_at": now, "updated_at": now}
    result = await db.tasks.insert_one(task)
    return {"id": str(result.inserted_id), "created": True}


# ============= USERS / STORES =============

@router.get("/users")
async def api_list_users(auth: dict = Depends(verify_api_key), role: Optional[str] = None, status: Optional[str] = None,
                         limit: int = Query(default=50, le=200), offset: int = 0):
    """Reps and managers this key can see (never includes passwords or tokens)."""
    db = get_db()
    ids = [ObjectId(u) for u in auth["tenant"]["user_ids"] if ObjectId.is_valid(u)]
    q: dict = {"_id": {"$in": ids}}
    if role:
        q["role"] = role
    if status:
        q["status"] = status
    total = await db.users.count_documents(q)
    rows = await db.users.find(q, USER_FIELDS).sort("last_name", 1).skip(offset).limit(limit).to_list(limit)
    return {"users": serialize(rows), "total": total, "limit": limit, "offset": offset}


@router.get("/users/{user_id}")
async def api_get_user(user_id: str, auth: dict = Depends(verify_api_key)):
    db = get_db()
    if not _in_tenant_user(auth, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    u = await db.users.find_one({"_id": _oid(user_id, "User")}, USER_FIELDS)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize(u)


@router.get("/stores")
async def api_list_stores(auth: dict = Depends(verify_api_key)):
    db = get_db()
    ids = [ObjectId(s) for s in auth["tenant"]["store_ids"] if ObjectId.is_valid(s)]
    rows = await db.stores.find({"_id": {"$in": ids}}, {"name": 1, "organization_id": 1, "address": 1, "city": 1, "state": 1, "phone": 1, "website": 1, "timezone": 1}).to_list(200)
    return {"stores": serialize(rows)}


@router.get("/organizations")
async def api_list_organizations(auth: dict = Depends(verify_api_key)):
    db = get_db()
    org_id = auth["tenant"].get("org_id")
    rows = await db.organizations.find({"_id": ObjectId(org_id)}, {"name": 1, "industry": 1, "created_at": 1}).to_list(1) if org_id and ObjectId.is_valid(org_id) else []
    return {"organizations": serialize(rows)}


# ============= CONVERSATIONS =============

@router.get("/conversations")
async def api_list_conversations(auth: dict = Depends(verify_api_key), user_id: Optional[str] = None, contact_id: Optional[str] = None,
                                 updated_since: Optional[str] = None, limit: int = Query(default=50, le=200), offset: int = 0):
    db = get_db()
    q = {"user_id": {"$in": auth["tenant"]["user_ids"]}} if auth["tenant"]["user_ids"] else {"_id": None}
    if user_id:
        q["user_id"] = user_id if _in_tenant_user(auth, user_id) else "-"
    if contact_id:
        q["contact_id"] = contact_id
    since = _parse_dt(updated_since, "updated_since")
    if since:
        q["last_message_at"] = {"$gt": since}
    total = await db.conversations.count_documents(q)
    rows = await db.conversations.find(q).sort("last_message_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"conversations": serialize(rows), "total": total, "limit": limit, "offset": offset}


@router.get("/conversations/{conversation_id}/messages")
async def api_conversation_messages(conversation_id: str, auth: dict = Depends(verify_api_key), limit: int = Query(default=100, le=500), offset: int = 0):
    db = get_db()
    cv = await db.conversations.find_one({"_id": _oid(conversation_id, "Conversation")})
    if not cv or not _in_tenant_user(auth, cv.get("user_id")):
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = await db.messages.find({"conversation_id": conversation_id}).sort("timestamp", 1).skip(offset).limit(limit).to_list(limit)
    return {"conversation": serialize(cv), "messages": serialize(rows), "limit": limit, "offset": offset}


# ============= EXPORT =============

@router.get("/export/contacts")
async def api_export_contacts(auth: dict = Depends(verify_api_key), format: str = Query("json", pattern="^(json|csv)$"), limit: int = Query(default=5000, le=20000)):
    """Full pull for an initial CRM load. Use GET /contacts?updated_since=... afterwards."""
    db = get_db()
    rows = await db.contacts.find(_contact_scope(auth), CONTACT_HIDE).sort("created_at", -1).limit(limit).to_list(limit)
    if format == "csv":
        cols = ["id", "first_name", "last_name", "phone", "email", "tags", "source", "external_id", "vehicle", "vehicle_interest", "date_sold", "user_id", "store_id", "notes", "created_at", "updated_at"]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in serialize(rows):
            r["tags"] = ";".join(r.get("tags") or [])
            w.writerow({k: r.get(k, "") for k in cols})
        return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contacts.csv"})
    return {"contacts": serialize(rows), "total": len(rows), "exported_at": datetime.now(timezone.utc).isoformat()}


# ============= WEBHOOKS =============

class WebhookIn(BaseModel):
    url: str
    events: list
    secret: Optional[str] = None
    description: Optional[str] = None


def _webhook_scope(auth: dict) -> dict:
    t = auth["tenant"]
    if len(t["store_ids"]) == 1 and auth.get("store_id"):
        return {"store_id": auth["store_id"]}
    if t.get("org_id"):
        return {"organization_id": t["org_id"]}
    return {"_id": None}


@router.get("/webhooks/events")
async def api_webhook_events():
    """Everything you can subscribe to, with a one-line meaning for each."""
    return {"event_types": [k for k in EVENT_TYPES if k != "ping"], "descriptions": EVENT_TYPES}


@router.get("/webhooks")
async def api_list_webhooks(auth: dict = Depends(verify_api_key)):
    db = get_db()
    rows = await db.webhook_subscriptions.find(_webhook_scope(auth)).to_list(100)
    return {"webhooks": [public_subscription(s) for s in rows]}


@router.post("/webhooks")
async def api_create_webhook(body: WebhookIn, auth: dict = Depends(verify_api_key)):
    """Register a URL. Events arrive within about a minute, signed with your secret (X-IMOS-Signature)."""
    _require_write(auth)
    db = get_db()
    validate_events(body.events)
    if not body.url.lower().startswith("https://"):
        raise HTTPException(status_code=400, detail="url must be https")
    scope = _webhook_scope(auth)
    if scope.get("_id", 1) is None:
        raise HTTPException(status_code=400, detail="This key is not tied to a store or organization")
    now = datetime.now(timezone.utc)
    doc = {"url": body.url, "events": body.events, "secret": body.secret, "description": body.description, "is_active": True,
           "created_by": f"api:{auth['key_id']}", "store_id": auth.get("store_id") if scope.get("store_id") else None,
           "organization_id": auth["tenant"].get("org_id"), "created_at": now, "updated_at": now, "failure_count": 0, "delivery_count": 0,
           "last_triggered": None, "last_status": None}
    result = await db.webhook_subscriptions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return public_subscription(doc)


@router.delete("/webhooks/{webhook_id}")
async def api_delete_webhook(webhook_id: str, auth: dict = Depends(verify_api_key)):
    _require_write(auth)
    db = get_db()
    result = await db.webhook_subscriptions.delete_one({"_id": _oid(webhook_id, "Webhook"), **_webhook_scope(auth)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"id": webhook_id, "message": "Webhook deleted"}


@router.get("/webhooks/{webhook_id}/deliveries")
async def api_webhook_deliveries(webhook_id: str, auth: dict = Depends(verify_api_key), limit: int = Query(default=50, le=200)):
    db = get_db()
    if not await db.webhook_subscriptions.find_one({"_id": _oid(webhook_id, "Webhook"), **_webhook_scope(auth)}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deliveries": await delivery_logs(webhook_id, limit)}


@router.post("/webhooks/{webhook_id}/test")
async def api_test_webhook(webhook_id: str, auth: dict = Depends(verify_api_key)):
    """Sends a signed `ping` event to the URL right now and returns what your server answered."""
    db = get_db()
    sub = await db.webhook_subscriptions.find_one({"_id": _oid(webhook_id, "Webhook"), **_webhook_scope(auth)})
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")
    event = build_event("ping", {"message": "Hello from I'm On Social", "webhook_id": webhook_id}, {"store_id": sub.get("store_id"), "organization_id": sub.get("organization_id")})
    return await deliver(db, sub, event)
