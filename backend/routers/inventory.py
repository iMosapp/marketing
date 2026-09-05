"""
Inventory Management Router — user-facing CRUD + CSV import for store inventory.
Feeds the same db.inventory collection as the HomeNet-compatible webhook API
(/api/webhooks/inventory/*), so a live feed can plug in later with zero rework.
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Body, UploadFile, File
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory", tags=["Inventory"])

from services.inventory_feed import ATTR_FIELDS, build_item as _build_item, parse_inventory_csv  # shared with automatic feeds


def _serialize(item: dict) -> dict:
    item["_id"] = str(item["_id"])
    for k in ("created_at", "updated_at"):
        if hasattr(item.get(k), "isoformat"):
            item[k] = item[k].isoformat()
    item["photos"] = _gallery(item)
    return item


async def _scope_query(user_id: str) -> dict:
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "role": 1})
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    sid = user.get("store_id")
    if sid:
        return {"store_id": str(sid)}
    if user.get("role") == "super_admin":
        return {}
    return {"$or": [{"created_by_user_id": user_id}, {"assigned_to_user_id": user_id}]}


@router.get("/{user_id}/hot")
async def hot_vehicles(user_id: str, days: int = 7, limit: int = 8):
    """Vehicles shoppers are opening (tracked lot links) and asking Jessi about most this week, store-wide.
    Reps use it to know what to push. Score = 2 x link opens + asks."""
    db = get_db()
    scope = await _scope_query(user_id)
    days = max(1, min(days, 30))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    items = await db.inventory.find(scope, {"name": 1, "price": 1, "status": 1, "attributes": 1, "primary_image": 1, "photo_url": 1,
                                             "photos": 1, "listing_url": 1, "created_at": 1}).limit(2000).to_list(2000)
    if not items:
        return {"success": True, "days": days, "vehicles": [], "total_shoppers": 0}
    by_id = {str(it["_id"]): it for it in items}
    ids = list(by_id.keys())

    stats: dict = {}

    def bump(iid, kind, contact_id, ts, when="cur"):
        s = stats.setdefault(iid, {"clicks": 0, "asks": 0, "prev": 0, "contacts": {}, "last": None})
        if when == "prev":
            s["prev"] += 1
            return
        s[kind] += 1
        if contact_id:
            c = s["contacts"].setdefault(str(contact_id), {"clicks": 0, "asks": 0, "last": None})
            c[kind] += 1
            if ts and (c["last"] is None or ts > c["last"]):
                c["last"] = ts
        if ts and (s["last"] is None or ts > s["last"]):
            s["last"] = ts

    def _ts(v):
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    clicks = await db.contact_events.find(
        {"event_type": "vehicle_link_clicked", "metadata.inventory_id": {"$in": ids}, "timestamp": {"$gte": prev_since}},
        {"metadata": 1, "contact_id": 1, "timestamp": 1}).limit(5000).to_list(5000)
    for ev in clicks:
        ts = _ts(ev.get("timestamp"))
        bump(ev["metadata"]["inventory_id"], "clicks", ev.get("contact_id"), ts, "cur" if (ts and ts >= since) else "prev")
    asks = await db.inventory_interest.find(
        {"inventory_id": {"$in": ids}, "timestamp": {"$gte": prev_since}},
        {"inventory_id": 1, "contact_id": 1, "timestamp": 1}).limit(5000).to_list(5000)
    for ev in asks:
        ts = _ts(ev.get("timestamp"))
        bump(ev["inventory_id"], "asks", ev.get("contact_id"), ts, "cur" if (ts and ts >= since) else "prev")

    ranked = [(iid, s) for iid, s in stats.items() if s["clicks"] + s["asks"] > 0]
    ranked.sort(key=lambda kv: (kv[1]["clicks"] * 2 + kv[1]["asks"], kv[1]["last"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    ranked = ranked[:limit]

    contact_ids = {cid for _, s in ranked for cid in s["contacts"] if ObjectId.is_valid(cid)}
    contacts = {}
    if contact_ids:
        docs = await db.contacts.find({"_id": {"$in": [ObjectId(c) for c in contact_ids]}},
                                      {"first_name": 1, "last_name": 1, "user_id": 1, "phone": 1}).to_list(500)
        contacts = {str(c["_id"]): c for c in docs}
    rep_ids = {str(c.get("user_id")) for c in contacts.values() if c.get("user_id") and ObjectId.is_valid(str(c.get("user_id")))}
    reps = {}
    if rep_ids:
        rdocs = await db.users.find({"_id": {"$in": [ObjectId(r) for r in rep_ids]}}, {"name": 1, "first_name": 1}).to_list(200)
        reps = {str(r["_id"]): (r.get("first_name") or (r.get("name") or "").split(" ")[0] or "Rep") for r in rdocs}

    out = []
    all_shoppers = set()
    for iid, s in ranked:
        it = by_id[iid]
        a = it.get("attributes") or {}
        shoppers = []
        for cid, c in sorted(s["contacts"].items(), key=lambda kv: kv[1]["last"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            all_shoppers.add(cid)
            doc = contacts.get(cid) or {}
            name = f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip() or "Shopper"
            shoppers.append({"contact_id": cid, "name": name, "clicks": c["clicks"], "asks": c["asks"],
                             "rep": reps.get(str(doc.get("user_id")), ""), "mine": str(doc.get("user_id")) == user_id,
                             "last": c["last"].isoformat() if c["last"] else None})
        photo = None
        gallery = _gallery(it)
        if gallery:
            photo = gallery[0].get("url") or gallery[0].get("thumb_url")
        score = s["clicks"] * 2 + s["asks"]
        out.append({
            "inventory_id": iid, "name": it.get("name", ""), "price": it.get("price"), "status": it.get("status", "available"),
            "stock_number": a.get("stock_number", ""), "color": a.get("color", ""), "mileage": a.get("mileage", ""),
            "photo": photo, "primary_image": it.get("primary_image"), "listing_url": it.get("listing_url"),
            "clicks": s["clicks"], "asks": s["asks"], "shoppers": shoppers, "shopper_count": len(shoppers),
            "score": score, "prev_score": s["prev"], "trend": "new" if s["prev"] == 0 else ("up" if score > s["prev"] else ("down" if score < s["prev"] else "flat")),
            "last_activity": s["last"].isoformat() if s["last"] else None,
        })
    return {"success": True, "days": days, "vehicles": out, "total_shoppers": len(all_shoppers)}


@router.get("/{user_id}")
async def list_inventory(user_id: str, search: str = None, status: str = None, limit: int = 200):
    db = get_db()
    scope = await _scope_query(user_id)
    clauses = [scope] if scope else []
    clauses.append({"is_visible": {"$ne": False}})
    if status and status != "all":
        clauses.append({"status": status})
    if search:
        rx = {"$regex": search, "$options": "i"}
        clauses.append({"$or": [
            {"name": rx}, {"description": rx},
            {"attributes.make": rx}, {"attributes.model": rx}, {"attributes.color": rx},
            {"attributes.stock_number": rx}, {"attributes.vin": rx},
        ]})
    query = {"$and": clauses}
    items = await db.inventory.find(query).sort("updated_at", -1).to_list(min(limit, 500))
    counts = {
        "available": await db.inventory.count_documents({**scope, "status": "available", "is_visible": {"$ne": False}}),
        "sold": await db.inventory.count_documents({**scope, "status": "sold", "is_visible": {"$ne": False}}),
        "missing_photos": await db.inventory.count_documents({
            **scope, "status": "available", "is_visible": {"$ne": False},
            "$or": [{"photo_url": {"$exists": False}}, {"photo_url": {"$in": [None, ""]}}],
        }),
    }
    return {"items": [_serialize(i) for i in items], "total": len(items), "counts": counts}


async def send_missing_photo_reminders() -> dict:
    """Daily nudge: push + in-app notification to store admins when in-stock
    vehicles are missing photos (photos ride along on the first lead text)."""
    db = get_db()
    query = {
        "status": "available", "is_visible": {"$ne": False},
        "$or": [{"photo_url": {"$exists": False}}, {"photo_url": {"$in": [None, ""]}}],
    }
    items = await db.inventory.find(query, {"store_id": 1, "created_by_user_id": 1}).to_list(3000)
    if not items:
        return {"notified": 0, "reason": "no_missing_photos"}

    by_scope: dict = {}
    for it in items:
        key = str(it.get("store_id") or "") or f"user:{it.get('created_by_user_id', '')}"
        by_scope[key] = by_scope.get(key, 0) + 1

    from routers.push_notifications import send_push_to_user
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notified = 0

    for key, count in by_scope.items():
        if key.startswith("user:"):
            uids = [key[5:]] if key[5:] else []
        else:
            store_vals = [key, ObjectId(key)] if ObjectId.is_valid(key) else [key]
            admins = await db.users.find(
                {"store_id": {"$in": store_vals}, "role": {"$in": ["store_manager", "org_admin"]}},
                {"_id": 1},
            ).to_list(20)
            uids = [str(a["_id"]) for a in admins]

        title = f"{count} vehicle{'s' if count != 1 else ''} missing photos"
        body = "In-stock vehicles without photos can't ride along on lead texts. Add pictures in Inventory."

        for uid in uids:
            idem = f"photo_reminder_{uid}_{today}"
            r = await db.notifications.update_one(
                {"idempotency_key": idem},
                {"$setOnInsert": {
                    "user_id": uid,
                    "type": "photo_reminder",
                    "title": title,
                    "message": body,
                    "link": "/inventory",
                    "idempotency_key": idem,
                    "read": False,
                    "dismissed": False,
                    "created_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            if r.upserted_id:
                try:
                    await send_push_to_user(uid, f"📸 {title}", body, "/inventory", "camera")
                except Exception as e:
                    logger.debug(f"[PhotoReminder] push to {uid} failed: {e}")
                notified += 1

    logger.info(f"[PhotoReminder] {notified} admins notified across {len(by_scope)} scopes")
    return {"notified": notified, "scopes": len(by_scope)}


@router.post("/{user_id}")
async def add_inventory_item(user_id: str, data: dict = Body(...)):
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    store_id = str(user["store_id"]) if user.get("store_id") else None
    item = _build_item(user_id, store_id, data, "manual")
    if not item:
        raise HTTPException(status_code=400, detail="Provide a name, or year/make/model")
    result = await db.inventory.insert_one(item)
    item["_id"] = result.inserted_id
    return {"success": True, "item": _serialize(item)}


@router.put("/{user_id}/{item_id}")
async def update_inventory_item(user_id: str, item_id: str, data: dict = Body(...)):
    db = get_db()
    updates = {}
    for f in ("name", "status", "description"):
        if f in data:
            updates[f] = data[f]
    if "price" in data:
        try:
            updates["price"] = float(str(data["price"]).replace("$", "").replace(",", "")) if data["price"] not in (None, "") else None
        except Exception:
            pass
    if isinstance(data.get("attributes"), dict):
        for f in ATTR_FIELDS:
            if f in data["attributes"]:
                updates[f"attributes.{f}"] = str(data["attributes"][f]).strip()
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)
    scope = await _scope_query(user_id)
    result = await db.inventory.update_one({"$and": [{"_id": ObjectId(item_id)}, scope or {}]}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


@router.delete("/{user_id}/{item_id}")
async def delete_inventory_item(user_id: str, item_id: str):
    db = get_db()
    scope = await _scope_query(user_id)
    result = await db.inventory.delete_one({"$and": [{"_id": ObjectId(item_id)}, scope or {}]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


MAX_PHOTOS = 6


def _gallery(item: dict) -> list:
    """Photo gallery, folding in the legacy single cover photo."""
    photos = list(item.get("photos") or [])
    if not photos and item.get("photo_full_path"):
        photos = [{"full_path": item["photo_full_path"], "thumb_url": item.get("photo_url") or f"/api/images/{item['photo_full_path']}"}]
    return photos


def _gallery_set(photos: list) -> dict:
    cover = photos[0] if photos else None
    return {
        "photos": photos,
        "photo_url": cover["thumb_url"] if cover else None,
        "photo_full_path": cover["full_path"] if cover else None,
        "updated_at": datetime.now(timezone.utc),
    }


@router.post("/{user_id}/{item_id}/photo")
async def upload_inventory_photo(user_id: str, item_id: str, data: dict = Body(...)):
    """Add a photo to a vehicle (base64). Up to MAX_PHOTOS; Jessi texts the first three when quoting this car."""
    db = get_db()
    photo = data.get("photo") or data.get("photo_url")
    if not photo:
        raise HTTPException(status_code=400, detail="photo is required")
    scope = await _scope_query(user_id)
    item = await db.inventory.find_one({"$and": [{"_id": ObjectId(item_id)}, scope or {}]}, {"photos": 1, "photo_url": 1, "photo_full_path": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    photos = _gallery(item)
    if len(photos) >= MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Up to {MAX_PHOTOS} photos per vehicle")
    from utils.image_storage import upload_image
    result = await upload_image(photo, prefix="inventory", entity_id=item_id)
    if not result:
        raise HTTPException(status_code=500, detail="Photo upload failed")
    photos.append({"full_path": result["original_path"], "thumb_url": f"/api/images/{result['thumbnail_path']}"})
    await db.inventory.update_one({"_id": ObjectId(item_id)}, {"$set": _gallery_set(photos)})
    return {"success": True, "photo_url": photos[0]["thumb_url"], "photos": photos}


@router.delete("/{user_id}/{item_id}/photo/{index}")
async def delete_inventory_photo(user_id: str, item_id: str, index: int):
    """Remove one photo from the vehicle's gallery; the first remaining photo becomes the cover."""
    db = get_db()
    scope = await _scope_query(user_id)
    item = await db.inventory.find_one({"$and": [{"_id": ObjectId(item_id)}, scope or {}]}, {"photos": 1, "photo_url": 1, "photo_full_path": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    photos = _gallery(item)
    if not 0 <= index < len(photos):
        raise HTTPException(status_code=404, detail="Photo not found")
    photos.pop(index)
    await db.inventory.update_one({"_id": ObjectId(item_id)}, {"$set": _gallery_set(photos)})
    return {"success": True, "photos": photos}


@router.put("/{user_id}/{item_id}/photo/{index}/cover")
async def set_inventory_cover(user_id: str, item_id: str, index: int):
    """Move a photo to the front so it is the cover and the first one Jessi sends."""
    db = get_db()
    scope = await _scope_query(user_id)
    item = await db.inventory.find_one({"$and": [{"_id": ObjectId(item_id)}, scope or {}]}, {"photos": 1, "photo_url": 1, "photo_full_path": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    photos = _gallery(item)
    if not 0 <= index < len(photos):
        raise HTTPException(status_code=404, detail="Photo not found")
    photos.insert(0, photos.pop(index))
    await db.inventory.update_one({"_id": ObjectId(item_id)}, {"$set": _gallery_set(photos)})
    return {"success": True, "photos": photos}


@router.post("/{user_id}/csv")
async def import_inventory_csv(user_id: str, file: UploadFile = File(...)):
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    store_id = str(user["store_id"]) if user.get("store_id") else None

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("latin-1", errors="ignore")

    rows, fields, _ = parse_inventory_csv(text)
    if not fields:
        raise HTTPException(status_code=400, detail="No recognized columns. Expected headers like: year, make, model, price, color, mileage, stock, vin")

    docs, skipped = [], 0
    for data in rows:
        item = _build_item(user_id, store_id, data, "csv")
        if item:
            docs.append(item)
        else:
            skipped += 1
        if len(docs) >= 2000:
            break

    if docs:
        await db.inventory.insert_many(docs)
    return {"success": True, "imported": len(docs), "skipped": skipped}
