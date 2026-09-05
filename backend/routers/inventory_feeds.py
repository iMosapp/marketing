"""Inventory feeds: connect a dealer's HomeNet / vAuto / website catalog feed (URL or SFTP) and pull it automatically."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body
from bson import ObjectId

from routers.database import get_db
from services import inventory_feed as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory-feeds", tags=["inventory-feeds"])

MANAGER_ROLES = ("store_manager", "org_admin", "super_admin", "admin")


async def _manager(db, user_id: str) -> dict:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only store managers and admins can manage inventory feeds")
    return user


def _scope(user: dict, user_id: str) -> dict:
    sid = str(user["store_id"]) if user.get("store_id") else None
    return {"store_id": sid} if sid else {"store_id": None, "created_by": user_id}


async def _feed_or_404(db, user, user_id, feed_id) -> dict:
    if not ObjectId.is_valid(feed_id):
        raise HTTPException(status_code=404, detail="Feed not found")
    feed = await db.inventory_feeds.find_one({"_id": ObjectId(feed_id), **_scope(user, user_id)})
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    return feed


def _clean(payload: dict, existing: dict | None = None) -> dict:
    transport = (payload.get("transport") or (existing or {}).get("transport") or "url").strip().lower()
    if transport not in ("url", "sftp"):
        raise HTTPException(status_code=400, detail="transport must be 'url' or 'sftp'")
    provider = (payload.get("provider") or (existing or {}).get("provider") or "other").strip().lower()
    if provider not in svc.PROVIDERS:
        provider = "other"
    doc = {
        "transport": transport,
        "provider": provider,
        "label": (payload.get("label") or (existing or {}).get("label") or svc.PROVIDERS[provider]["label"]).strip()[:60],
        "mark_missing_sold": bool(payload.get("mark_missing_sold", (existing or {}).get("mark_missing_sold", True))),
        "enabled": bool(payload.get("enabled", (existing or {}).get("enabled", True))),
    }
    if transport == "url":
        url = svc.normalize_feed_url(payload.get("feed_url") or (existing or {}).get("feed_url") or "")
        if not url.lower().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Paste the full feed link (it starts with https://)")
        doc["feed_url"] = url
        doc["feed_auth_user"] = (payload.get("feed_auth_user") or (existing or {}).get("feed_auth_user") or "").strip()
        if payload.get("feed_auth_password"):
            doc["feed_auth_password_enc"] = svc.encrypt_secret(payload["feed_auth_password"])
    else:
        host = (payload.get("sftp_host") or (existing or {}).get("sftp_host") or "").strip()
        username = (payload.get("sftp_username") or (existing or {}).get("sftp_username") or "").strip()
        if not host or not username:
            raise HTTPException(status_code=400, detail="SFTP host and username are required")
        try:
            port = int(payload.get("sftp_port") or (existing or {}).get("sftp_port") or 22)
        except Exception:
            raise HTTPException(status_code=400, detail="Port must be a number")
        doc.update({
            "sftp_host": host, "sftp_port": port, "sftp_username": username,
            "remote_path": (payload.get("remote_path") or (existing or {}).get("remote_path") or "/").strip() or "/",
            "file_pattern": (payload.get("file_pattern") or (existing or {}).get("file_pattern") or "*.csv").strip() or "*.csv",
        })
        if payload.get("sftp_password"):
            doc["sftp_password_enc"] = svc.encrypt_secret(payload["sftp_password"])
        elif not (existing or {}).get("sftp_password_enc"):
            raise HTTPException(status_code=400, detail="SFTP password is required")
    return doc


@router.get("/providers")
async def providers():
    return {"providers": [{"id": k, **v} for k, v in svc.PROVIDERS.items()]}


@router.get("/{user_id}")
async def list_feeds(user_id: str):
    db = get_db()
    user = await _manager(db, user_id)
    feeds = await db.inventory_feeds.find(_scope(user, user_id)).sort("created_at", 1).to_list(50)
    out = []
    for f in feeds:
        runs = await db.inventory_feed_runs.find({"feed_id": str(f["_id"])}).sort("started_at", -1).limit(8).to_list(8)
        pub = svc.feed_public(f)
        pub["runs"] = [_run_public(r) for r in runs]
        pub["live_units"] = await db.inventory.count_documents({"feed_id": str(f["_id"]), "status": "available"})
        out.append(pub)
    return {"success": True, "feeds": out, "store_id": _scope(user, user_id).get("store_id")}


def _run_public(r: dict) -> dict:
    d = {k: v for k, v in r.items() if k != "_id"}
    d["id"] = str(r["_id"])
    for k in ("started_at", "finished_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


@router.post("/{user_id}/test")
async def test_feed(user_id: str, payload: dict = Body(...)):
    """Dry run against un-saved settings (or a saved feed via feed_id) - nothing is written."""
    db = get_db()
    user = await _manager(db, user_id)
    existing = None
    if payload.get("feed_id"):
        existing = await _feed_or_404(db, user, user_id, payload["feed_id"])
    doc = _clean(payload, existing)
    if existing:
        for k in ("sftp_password_enc", "feed_auth_password_enc"):
            if existing.get(k) and k not in doc:
                doc[k] = existing[k]
    return await svc.test_connection(doc)


@router.post("/{user_id}")
async def create_feed(user_id: str, payload: dict = Body(...)):
    db = get_db()
    user = await _manager(db, user_id)
    doc = _clean(payload)
    now = datetime.now(timezone.utc)
    doc.update({**_scope(user, user_id), "created_by": user_id, "created_at": now, "updated_at": now,
                "consecutive_failures": 0, "last_status": None})
    res = await db.inventory_feeds.insert_one(doc)
    doc["_id"] = res.inserted_id
    run = None
    if payload.get("run_now", True):
        run = await svc.sync_feed(db, doc, force=True, triggered_by=f"user:{user_id}")
        doc = await db.inventory_feeds.find_one({"_id": res.inserted_id})
    return {"success": True, "feed": svc.feed_public(doc), "run": _strip_run(run)}


def _strip_run(run):
    if not run:
        return None
    d = dict(run)
    for k in ("started_at", "finished_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


@router.put("/{user_id}/{feed_id}")
async def update_feed(user_id: str, feed_id: str, payload: dict = Body(...)):
    db = get_db()
    user = await _manager(db, user_id)
    feed = await _feed_or_404(db, user, user_id, feed_id)
    doc = _clean(payload, feed)
    doc["updated_at"] = datetime.now(timezone.utc)
    await db.inventory_feeds.update_one({"_id": feed["_id"]}, {"$set": doc})
    fresh = await db.inventory_feeds.find_one({"_id": feed["_id"]})
    return {"success": True, "feed": svc.feed_public(fresh)}


@router.post("/{user_id}/{feed_id}/run")
async def run_feed(user_id: str, feed_id: str):
    db = get_db()
    user = await _manager(db, user_id)
    feed = await _feed_or_404(db, user, user_id, feed_id)
    run = await svc.sync_feed(db, feed, force=True, triggered_by=f"user:{user_id}")
    fresh = await db.inventory_feeds.find_one({"_id": feed["_id"]})
    return {"success": run["status"] == "ok", "run": _strip_run(run), "feed": svc.feed_public(fresh)}


@router.get("/{user_id}/{feed_id}/runs")
async def feed_runs(user_id: str, feed_id: str, limit: int = 20):
    db = get_db()
    user = await _manager(db, user_id)
    await _feed_or_404(db, user, user_id, feed_id)
    runs = await db.inventory_feed_runs.find({"feed_id": feed_id}).sort("started_at", -1).limit(min(limit, 100)).to_list(100)
    return {"success": True, "runs": [_run_public(r) for r in runs]}


@router.delete("/{user_id}/{feed_id}")
async def delete_feed(user_id: str, feed_id: str, remove_vehicles: bool = False):
    db = get_db()
    user = await _manager(db, user_id)
    feed = await _feed_or_404(db, user, user_id, feed_id)
    await db.inventory_feeds.delete_one({"_id": feed["_id"]})
    await db.inventory_feed_runs.delete_many({"feed_id": feed_id})
    removed = 0
    if remove_vehicles:
        res = await db.inventory.delete_many({"feed_id": feed_id})
        removed = res.deleted_count
    else:
        await db.inventory.update_many({"feed_id": feed_id}, {"$unset": {"feed_id": ""}})
    return {"success": True, "removed_vehicles": removed}
