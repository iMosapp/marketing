"""
Inventory Management Router — user-facing CRUD + CSV import for store inventory.
Feeds the same db.inventory collection as the HomeNet-compatible webhook API
(/api/webhooks/inventory/*), so a live feed can plug in later with zero rework.
"""
import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body, UploadFile, File
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory", tags=["Inventory"])

ATTR_FIELDS = ("year", "make", "model", "trim", "color", "mileage", "stock_number", "vin")


def _serialize(item: dict) -> dict:
    item["_id"] = str(item["_id"])
    for k in ("created_at", "updated_at"):
        if hasattr(item.get(k), "isoformat"):
            item[k] = item[k].isoformat()
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


def _build_item(user_id: str, store_id: str, data: dict, source: str) -> dict:
    attributes = {}
    for f in ATTR_FIELDS:
        v = data.get(f)
        if v not in (None, ""):
            attributes[f] = str(v).strip()
    name = (data.get("name") or "").strip()
    if not name:
        name = " ".join(str(attributes.get(f, "")).strip() for f in ("year", "make", "model", "trim") if attributes.get(f)).strip()
    if not name:
        return None
    price = None
    raw_price = data.get("price")
    if raw_price not in (None, ""):
        try:
            price = float(str(raw_price).replace("$", "").replace(",", "").strip())
        except Exception:
            price = None
    now = datetime.now(timezone.utc)
    return {
        "external_id": f"{source}-{uuid.uuid4().hex[:12]}",
        "name": name,
        "category": "vehicle",
        "status": (data.get("status") or "available").strip().lower() or "available",
        "price": price,
        "currency": "USD",
        "store_id": store_id,
        "created_by_user_id": user_id,
        "description": (data.get("description") or "").strip(),
        "attributes": attributes,
        "tags": [],
        "is_visible": True,
        "source_system": source,
        "created_at": now,
        "updated_at": now,
    }


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


@router.post("/{user_id}/{item_id}/photo")
async def upload_inventory_photo(user_id: str, item_id: str, data: dict = Body(...)):
    """Attach a photo to a vehicle (base64) — Jessi texts it when quoting this car."""
    db = get_db()
    photo = data.get("photo") or data.get("photo_url")
    if not photo:
        raise HTTPException(status_code=400, detail="photo is required")
    scope = await _scope_query(user_id)
    item = await db.inventory.find_one({"$and": [{"_id": ObjectId(item_id)}, scope or {}]}, {"_id": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    from utils.image_storage import upload_image
    result = await upload_image(photo, prefix="inventory", entity_id=item_id)
    if not result:
        raise HTTPException(status_code=500, detail="Photo upload failed")
    photo_url = f"/api/images/{result['thumbnail_path']}"
    await db.inventory.update_one({"_id": ObjectId(item_id)}, {"$set": {
        "photo_url": photo_url,
        "photo_full_path": result["original_path"],
        "updated_at": datetime.now(timezone.utc),
    }})
    return {"success": True, "photo_url": photo_url}


CSV_HEADER_ALIASES = {
    "year": "year", "yr": "year",
    "make": "make", "manufacturer": "make",
    "model": "model",
    "trim": "trim", "series": "trim",
    "color": "color", "colour": "color", "exterior color": "color", "ext color": "color", "exterior": "color",
    "mileage": "mileage", "miles": "mileage", "odometer": "mileage",
    "price": "price", "list price": "price", "selling price": "price", "asking price": "price", "internet price": "price",
    "stock": "stock_number", "stock#": "stock_number", "stock #": "stock_number", "stock number": "stock_number", "stock_number": "stock_number", "stocknumber": "stock_number",
    "vin": "vin",
    "status": "status",
    "name": "name", "title": "name", "vehicle": "name",
    "description": "description", "desc": "description", "notes": "description",
}


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

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    header_map = {}
    for h in reader.fieldnames:
        key = (h or "").strip().lower()
        if key in CSV_HEADER_ALIASES:
            header_map[h] = CSV_HEADER_ALIASES[key]

    if not header_map:
        raise HTTPException(status_code=400, detail="No recognized columns. Expected headers like: year, make, model, price, color, mileage, stock, vin")

    docs, skipped = [], 0
    for row in reader:
        data = {header_map[h]: (row.get(h) or "").strip() for h in header_map}
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
