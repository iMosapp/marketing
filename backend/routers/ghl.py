"""GoHighLevel connection per store: connect with a Private Integration Token, pull tags/pipelines, push contacts,
and receive GHL workflow webhooks into a lead source (speed to lead)."""
import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import ghl
from services import dialer as eng
from services.lead_flows import user_store_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ghl", tags=["GoHighLevel"], dependencies=[Depends(require_user)])
public = APIRouter(prefix="/ghl", tags=["GoHighLevel"])


class ConnectBody(BaseModel):
    location_id: str
    token: Optional[str] = None
    lead_source_id: Optional[str] = None
    store_id: Optional[str] = None


class PushBody(BaseModel):
    tags: list = []


async def _me(request: Request) -> dict:
    me = await _resolve(request)
    if not eng.is_manager(me):
        raise HTTPException(status_code=403, detail="Managers connect GoHighLevel")
    if not await eng.available(get_db(), me):
        raise HTTPException(status_code=403, detail="GoHighLevel is not released yet")
    return me


def _key(me: dict, store_id: Optional[str]) -> tuple:
    sid = store_id if (store_id and me.get("role") in ("super_admin", "org_admin")) else user_store_id(me)
    return ghl.scope_key(sid, str(me["_id"])), sid


async def _conn(db, me: dict, store_id: Optional[str]) -> dict:
    key, _ = _key(me, store_id)
    conn = await ghl.connection(db, key)
    if not conn:
        raise HTTPException(status_code=404, detail="GoHighLevel is not connected yet")
    return conn


@router.get("/connection")
async def get_connection(request: Request, store_id: Optional[str] = None):
    db = get_db()
    me = await _me(request)
    key, sid = _key(me, store_id)
    conn = await ghl.connection(db, key)
    sources = await db.lead_sources.find({"store_id": sid} if sid else {"store_id": {"$in": [None, ""]}}, {"name": 1, "is_active": 1}).to_list(100)
    return {**ghl.serialize(conn, eng._app_url()), "store_id": sid, "lead_sources": [{"id": str(s["_id"]), "name": s.get("name"), "active": s.get("is_active", True)} for s in sources]}


@router.put("/connection")
async def put_connection(body: ConnectBody, request: Request):
    db = get_db()
    me = await _me(request)
    key, sid = _key(me, body.store_id)
    existing = await ghl.connection(db, key)
    token = (body.token or "").strip() or (existing or {}).get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Paste the Private Integration Token")
    location_id = body.location_id.strip()
    if len(location_id) < 8:
        raise HTTPException(status_code=400, detail="That does not look like a GoHighLevel Location ID (Settings > Business Profile)")
    if body.lead_source_id and not ObjectId.is_valid(body.lead_source_id):
        raise HTTPException(status_code=400, detail="Bad lead source")
    try:
        conn = await ghl.save_connection(db, key, sid, me, location_id, token, body.lead_source_id if body.lead_source_id is not None else None)
    except ghl.GhlError as e:
        raise HTTPException(status_code=400, detail=f"GoHighLevel rejected that: {e.message}. Check the Location ID and that the token has locations.readonly + contacts scopes.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach GoHighLevel: {str(e)[:120]}")
    return ghl.serialize(conn, eng._app_url())


@router.post("/connection/test")
async def test_connection(request: Request, store_id: Optional[str] = None):
    db = get_db()
    conn = await _conn(db, await _me(request), store_id)
    try:
        info = await ghl.test_token(conn["location_id"], conn["token"])
        await db[ghl.COLL].update_one({"_id": conn["_id"]}, {"$set": {"ok": True, "error": None, "last_test_at": ghl._now(), "location_name": info["name"] or conn.get("location_name")}})
        return {"ok": True, "location": info}
    except ghl.GhlError as e:
        await db[ghl.COLL].update_one({"_id": conn["_id"]}, {"$set": {"ok": False, "error": e.message[:200], "last_test_at": ghl._now()}})
        return {"ok": False, "error": e.message}


@router.delete("/connection")
async def delete_connection(request: Request, store_id: Optional[str] = None):
    db = get_db()
    conn = await _conn(db, await _me(request), store_id)
    await db[ghl.COLL].delete_one({"_id": conn["_id"]})
    return {"connected": False}


@router.get("/tags")
async def list_tags(request: Request, store_id: Optional[str] = None):
    conn = await _conn(get_db(), await _me(request), store_id)
    try:
        return {"tags": await ghl.tags(conn)}
    except ghl.GhlError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/pipelines")
async def list_pipelines(request: Request, store_id: Optional[str] = None):
    conn = await _conn(get_db(), await _me(request), store_id)
    try:
        return {"pipelines": await ghl.pipelines(conn)}
    except ghl.GhlError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/contacts/{contact_id}/push")
async def push_contact(contact_id: str, body: PushBody, request: Request, store_id: Optional[str] = None):
    """Send one of our contacts to GoHighLevel (any signed-in user with a connected store)."""
    db = get_db()
    me = await _resolve(request)
    if not await eng.available(db, me):
        raise HTTPException(status_code=403, detail="GoHighLevel is not released yet")
    key, _ = _key(me, store_id)
    conn = await ghl.connection(db, key)
    if not conn:
        raise HTTPException(status_code=404, detail="GoHighLevel is not connected for your store")
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=400, detail="Bad contact id")
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if not eng.is_manager(me) and str(contact.get("user_id")) != str(me["_id"]):
        raise HTTPException(status_code=403, detail="Not your contact")
    try:
        cid = await ghl.push_contact(db, conn, contact, [str(t)[:40] for t in body.tags][:10])
    except ghl.GhlError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ghl_contact_id": cid}


# ── public webhook: GHL workflow "Webhook" action -> our lead intake ──────────
@public.post("/webhook/{connection_id}")
async def inbound_webhook(connection_id: str, request: Request, key: str = ""):
    db = get_db()
    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=404, detail="Unknown connection")
    conn = await db[ghl.COLL].find_one({"_id": ObjectId(connection_id)})
    if not conn or not key or key != conn.get("webhook_key"):
        raise HTTPException(status_code=401, detail="Bad webhook key")
    if not conn.get("lead_source_id"):
        raise HTTPException(status_code=400, detail="Pick a lead source on the GoHighLevel screen first")
    source = await db.lead_sources.find_one({"_id": ObjectId(conn["lead_source_id"])})
    if not source:
        raise HTTPException(status_code=400, detail="That lead source no longer exists")
    body = await request.body()
    try:
        import json
        raw = json.loads(body.decode("utf-8", errors="replace") or "{}")
    except Exception:
        import urllib.parse
        raw = {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True).items()}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    normalized = ghl.normalize_webhook(raw)
    if not normalized.get("phone") and not normalized.get("email"):
        raise HTTPException(status_code=422, detail="Lead has no phone or email")
    from routers.lead_intake import process_inbound_lead
    result = await process_inbound_lead(normalized, source, db, raw_body=body.decode("utf-8", errors="replace")[:20000])
    await db[ghl.COLL].update_one({"_id": conn["_id"]}, {"$inc": {"received": 1}, "$set": {"last_webhook_at": ghl._now()}})
    return {"success": True, **{k: (str(v) if isinstance(v, ObjectId) else v) for k, v in (result or {}).items()}}
