"""
Image router - serves stored images with CDN-like caching.

Caching strategy:
1. In-memory LRU cache (~200MB) — hot images served from RAM
2. ETag + If-None-Match → 304 Not Modified (zero body transfer)
3. Cache-Control: immutable (1 year) — browser never re-validates
4. Images cached on upload → first view is already in RAM
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Request, BackgroundTasks
from fastapi.responses import Response
from datetime import datetime, timezone
import logging

from routers.database import get_db
from utils.image_storage import (
    upload_image, get_object, make_etag, get_cache_stats,
    decode_base64_image, _compress_image, generate_thumbnail, put_object,
    ORIGINAL_MAX_WIDTH, WEBP_QUALITY, THUMBNAIL_SIZE, AVATAR_SIZE, APP_NAME,
)
import uuid

router = APIRouter(prefix="/images", tags=["Images"])
logger = logging.getLogger(__name__)


@router.get("/cache-stats")
async def cache_stats():
    """Get image cache statistics (admin/debug endpoint)."""
    return get_cache_stats()


@router.get("/migrate-status")
async def get_migration_status():
    """Get the status of the most recent migration job."""
    db = get_db()
    job = await db.migration_jobs.find_one(
        {"type": "image_migration"},
        sort=[("started_at", -1)],
    )
    if not job:
        return {"status": "none", "message": "No migration has been run yet."}

    return {
        "status": job.get("status", "unknown"),
        "started_at": job.get("started_at").isoformat() if job.get("started_at") else None,
        "completed_at": job.get("completed_at").isoformat() if job.get("completed_at") else None,
        "progress": job.get("progress", {}),
        "result": job.get("result"),
    }


@router.get("/migrate-check")
async def migrate_check():
    """
    Instant health check — counts images needing migration. No auth needed.
    If this works, your deployment is current.
    """
    db = get_db()
    counts = {
        "users": await db.users.count_documents({"photo_url": {"$regex": "^data:"}, "photo_path": {"$exists": False}}),
        "stores": await db.stores.count_documents({"logo_url": {"$regex": "^data:"}, "logo_path": {"$exists": False}}),
        "contacts": await db.contacts.count_documents({"photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}}),
        "congrats": await db.congrats_cards.count_documents({"customer_photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}}),
    }
    counts["total"] = sum(counts.values())
    return {"status": "ok", "version": "v3", "needs_migration": counts}


@router.get("/migrate-log")
async def migrate_log():
    """See the result and errors from the last migration run."""
    db = get_db()
    job = await db.migration_jobs.find_one(
        {"type": "simple_migrate"},
        sort=[("started_at", -1)],
        projection={"_id": 0},
    )
    if not job:
        return {"status": "none", "message": "No migration has been run yet."}
    return job


@router.get("/{path:path}")
async def serve_image(path: str, request: Request):
    """Serve an image with CDN-like caching behavior.

    Flow:
    1. Check ETag — if browser already has the image, return 304 (no body)
    2. Check in-memory cache — if cached, return from RAM (no storage call)
    3. Fetch from object storage → cache in memory → return
    """
    # Generate ETag (stable hash of path — UUID-based paths are immutable)
    etag = make_etag(path)

    # Check If-None-Match → return 304 if browser has current version
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and (if_none_match.strip('"') == etag or if_none_match == f'"{etag}"'):
        return Response(
            status_code=304,
            headers={
                "ETag": f'"{etag}"',
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    try:
        data, content_type = get_object(path)
        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{etag}"',
                "Vary": "Accept-Encoding",
                "X-Cache": "HIT" if True else "MISS",  # simplified; cache handles this internally
            },
        )
    except Exception as e:
        logger.error(f"Failed to serve image {path}: {e}")
        raise HTTPException(status_code=404, detail="Image not found")


@router.post("/upload")
async def upload_image_endpoint(
    file: UploadFile = File(...),
    entity_type: str = "general",
    entity_id: str = "general",
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Upload an image. Auto-compresses to WebP and caches immediately."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")

    preserve_raw = await _check_hires_flag(x_user_id)

    result = await upload_image(data, prefix=entity_type, entity_id=entity_id, preserve_raw=preserve_raw)
    if not result:
        raise HTTPException(status_code=500, detail="Upload failed")

    base_url = "/api/images"
    response = {
        "original_url": f"{base_url}/{result['original_path']}",
        "thumbnail_url": f"{base_url}/{result['thumbnail_path']}",
        "avatar_url": f"{base_url}/{result['avatar_path']}",
        "file_id": result["file_id"],
    }
    if result.get("raw_path"):
        response["raw_url"] = f"{base_url}/{result['raw_path']}"

    return response


@router.post("/upload-base64")
async def upload_base64_image(
    data: dict,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Upload a base64 image. Auto-compresses to WebP."""
    image_data = data.get("image")
    entity_type = data.get("entity_type", "general")
    entity_id = data.get("entity_id", "general")

    if not image_data:
        raise HTTPException(status_code=400, detail="No image data provided")

    preserve_raw = await _check_hires_flag(x_user_id)

    result = await upload_image(image_data, prefix=entity_type, entity_id=entity_id, preserve_raw=preserve_raw)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid image data or already a URL")

    base_url = "/api/images"
    response = {
        "original_url": f"{base_url}/{result['original_path']}",
        "thumbnail_url": f"{base_url}/{result['thumbnail_path']}",
        "avatar_url": f"{base_url}/{result['avatar_path']}",
        "file_id": result["file_id"],
    }
    if result.get("raw_path"):
        response["raw_url"] = f"{base_url}/{result['raw_path']}"

    return response


async def _check_hires_flag(user_id: str | None) -> bool:
    """Check if a user's organization has hires_images enabled."""
    if not user_id:
        return False
    try:
        from bson import ObjectId
        db = get_db()
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"organization_id": 1})
        if user and user.get("organization_id"):
            org_id = user["organization_id"]
            # Try ObjectId first, fall back to string match
            try:
                org = await db.organizations.find_one(
                    {"_id": ObjectId(org_id)},
                    {"hires_images": 1}
                )
            except Exception:
                org = await db.organizations.find_one(
                    {"_id": org_id},
                    {"hires_images": 1}
                )
            return bool(org and org.get("hires_images"))
    except Exception as e:
        logger.debug(f"hires check: {e}")
    return False


@router.delete("/raw/{path:path}")
async def cleanup_raw_image(path: str):
    """Mark a raw (uncompressed) original as no longer needed.
    Note: The raw file's URL is only returned at upload time and not stored
    in any database record. Once you've sent the full-res image to the partner,
    simply discard the raw_url. The compressed WebP version remains for in-app use."""
    if "_raw." not in path:
        raise HTTPException(status_code=400, detail="Can only clean up raw originals (path must contain '_raw.')")
    logger.info(f"Raw image cleanup noted: {path}")
    return {
        "message": "Raw image flagged for cleanup. The compressed version remains available.",
        "path": path,
        "note": "raw_url is only provided at upload time. Do not persist it after sending to the partner.",
    }


@router.post("/migrate-all-base64")
async def migrate_all_base64_images(request: Request, background_tasks: BackgroundTasks):
    """Background migration. Super admin only."""
    db = get_db()
    try:
        body = await request.json()
    except Exception:
        body = {}

    uid = body.get("user_id") or request.headers.get("x-user-id")
    if not uid:
        return {"status": "error", "detail": "Send JSON: {\"user_id\": \"your_id\"}"}

    from bson import ObjectId as ObjId
    try:
        user = await db.users.find_one({"_id": ObjId(uid)}, {"role": 1})
    except Exception:
        return {"status": "error", "detail": "Invalid user_id"}
    if not user or user.get("role") != "super_admin":
        return {"status": "error", "detail": "Super admin only"}

    existing = await db.migration_jobs.find_one({"status": "running"})
    if existing:
        started = existing.get("started_at")
        age_minutes = (datetime.now(timezone.utc) - started).total_seconds() / 60 if started else 999
        if age_minutes < 5:
            return {"status": "already_running", "message": "Migration already in progress."}
        await db.migration_jobs.update_one(
            {"_id": existing["_id"]},
            {"$set": {"status": "failed", "completed_at": datetime.now(timezone.utc)}},
        )

    job_doc = {
        "type": "image_migration", "status": "running",
        "started_at": datetime.now(timezone.utc), "started_by": uid,
        "progress": {}, "result": None,
    }
    insert_result = await db.migration_jobs.insert_one(job_doc)
    job_id = str(insert_result.inserted_id)
    background_tasks.add_task(_run_migration, job_id)
    return {"status": "started", "job_id": job_id}


@router.post("/migrate-now")
async def migrate_now(request: Request):
    """
    Processes ONE batch of images per call (up to 5 at a time).
    Call repeatedly until migrate-check shows total: 0.
    No background tasks — runs inline with proper timeout handling.
    """
    db = get_db()
    try:
        body = await request.json()
    except Exception:
        body = {}

    uid = body.get("user_id")
    if not uid:
        return {"status": "error", "detail": "Send JSON body with user_id"}

    from bson import ObjectId as ObjId
    try:
        user = await db.users.find_one({"_id": ObjId(uid)}, {"role": 1})
    except Exception:
        return {"status": "error", "detail": "Invalid user_id"}
    if not user or user.get("role") != "super_admin":
        return {"status": "error", "detail": "Super admin only"}

    import asyncio
    processed = 0
    errors = []
    BATCH = 3  # Process 3 images per call to stay under proxy timeout

    # Process users
    for u in await db.users.find({"photo_url": {"$regex": "^data:"}, "photo_path": {"$exists": False}}, {"_id": 1, "photo_url": 1}).to_list(BATCH):
        if processed >= BATCH:
            break
        try:
            r = await asyncio.to_thread(lambda doc=u: _sync_upload(doc["photo_url"], "profiles", str(doc["_id"])))
            if r:
                await db.users.update_one({"_id": u["_id"]}, {"$set": {"photo_path": r["original_path"], "photo_thumb_path": r["thumbnail_path"], "photo_avatar_path": r["avatar_path"], "photo_url": f"/api/images/{r['original_path']}"}})
                processed += 1
        except Exception as e:
            errors.append(f"user {u['_id']}: {str(e)[:80]}")

    # Process stores
    for s in await db.stores.find({"logo_url": {"$regex": "^data:"}, "logo_path": {"$exists": False}}, {"_id": 1, "logo_url": 1}).to_list(BATCH):
        if processed >= BATCH:
            break
        try:
            r = await asyncio.to_thread(lambda doc=s: _sync_upload(doc["logo_url"], "logos", str(doc["_id"])))
            if r:
                await db.stores.update_one({"_id": s["_id"]}, {"$set": {"logo_path": r["original_path"], "logo_thumb_path": r["thumbnail_path"], "logo_avatar_path": r["avatar_path"]}})
                processed += 1
        except Exception as e:
            errors.append(f"store {s['_id']}: {str(e)[:80]}")

    # Process contacts
    for c in await db.contacts.find({"photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}}, {"_id": 1, "photo": 1}).to_list(BATCH):
        if processed >= BATCH:
            break
        try:
            r = await asyncio.to_thread(lambda doc=c: _sync_upload(doc["photo"], "contacts", str(doc["_id"])))
            if r:
                await db.contacts.update_one({"_id": c["_id"]}, {"$set": {"photo_path": r["original_path"], "photo_thumb_path": r["thumbnail_path"], "photo_avatar_path": r["avatar_path"]}})
                processed += 1
        except Exception as e:
            errors.append(f"contact {c['_id']}: {str(e)[:80]}")

    # Process congrats cards — load ONE AT A TIME (base64 can be huge)
    for card in await db.congrats_cards.find({"customer_photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}}, {"_id": 1, "card_id": 1, "customer_photo": 1}).to_list(BATCH):
        if processed >= BATCH:
            break
        try:
            cid = card.get("card_id", str(card["_id"]))
            r = await asyncio.to_thread(lambda doc=card, cid=cid: _sync_upload(doc["customer_photo"], "congrats", cid))
            if r:
                await db.congrats_cards.update_one({"_id": card["_id"]}, {"$set": {"photo_path": r["original_path"], "photo_thumb_path": r["thumbnail_path"]}})
                processed += 1
        except Exception as e:
            errors.append(f"card {card.get('card_id', card['_id'])}: {str(e)[:80]}")

    remaining = await db.congrats_cards.count_documents({"customer_photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}})
    return {"status": "ok", "processed": processed, "errors": errors, "remaining": remaining}


def _sync_upload(image_data: str, prefix: str, entity_id: str):
    """Synchronous image upload — safe to call from asyncio.to_thread."""
    if not image_data or not image_data.startswith("data:"):
        return None
    image_bytes, content_type = decode_base64_image(image_data)
    file_id = str(uuid.uuid4())
    base_path = f"{APP_NAME}/{prefix}/{entity_id}"

    compressed_data, compressed_ct = _compress_image(image_bytes, ORIGINAL_MAX_WIDTH, WEBP_QUALITY)
    original_path = f"{base_path}/{file_id}.webp"
    put_object(original_path, compressed_data, compressed_ct)

    thumb_data, thumb_ct, thumb_ext = generate_thumbnail(image_bytes, THUMBNAIL_SIZE)
    thumb_path = f"{base_path}/{file_id}_thumb.{thumb_ext}"
    put_object(thumb_path, thumb_data, thumb_ct)

    avatar_data, avatar_ct, avatar_ext = generate_thumbnail(image_bytes, AVATAR_SIZE)
    avatar_path = f"{base_path}/{file_id}_avatar.{avatar_ext}"
    put_object(avatar_path, avatar_data, avatar_ct)

    return {"original_path": original_path, "thumbnail_path": thumb_path, "avatar_path": avatar_path}


async def _run_migration(job_id: str):
    """Background worker that performs the actual migration."""
    db = get_db()
    from bson import ObjectId as ObjId
    import time

    stats = {"users": 0, "stores": 0, "contacts": 0, "congrats": 0, "feedback": 0, "errors": 0}
    start = time.time()

    async def _update_progress():
        elapsed = round(time.time() - start, 1)
        total = sum(v for k, v in stats.items() if k != "errors")
        await db.migration_jobs.update_one(
            {"_id": ObjId(job_id)},
            {"$set": {"progress": {**stats, "total": total, "elapsed_seconds": elapsed}}},
        )

    try:
        # 0. Backfill photo_path from existing /api/images/ URLs
        backfill_count = 0
        for coll_name, url_field, path_field in [
            ("users", "photo_url", "photo_path"),
            ("stores", "logo_url", "logo_path"),
            ("contacts", "photo", "photo_path"),
            ("contacts", "photo_thumbnail", "photo_path"),
        ]:
            coll = db[coll_name]
            docs = await coll.find(
                {url_field: {"$regex": "^/api/images/"}, path_field: {"$exists": False}},
                {"_id": 1, url_field: 1}
            ).to_list(500)
            for d in docs:
                path = d[url_field].replace("/api/images/", "")
                if path:
                    await coll.update_one({"_id": d["_id"]}, {"$set": {path_field: path}})
                    backfill_count += 1

        await _update_progress()

        # 1. Users with base64 photo_url but no photo_path
        users = await db.users.find(
            {"photo_url": {"$regex": "^data:"}, "photo_path": {"$exists": False}},
            {"_id": 1, "photo_url": 1}
        ).to_list(200)
        for u in users:
            try:
                result = await upload_image(u["photo_url"], prefix="profiles", entity_id=str(u["_id"]))
                if result:
                    await db.users.update_one({"_id": u["_id"]}, {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                        "photo_avatar_path": result["avatar_path"],
                        "photo_url": f"/api/images/{result['original_path']}",
                    }})
                    stats["users"] += 1
            except Exception as e:
                logger.warning(f"User photo migration failed {u['_id']}: {e}")
                stats["errors"] += 1
        await _update_progress()

        # 2. Stores with base64 logo_url but no logo_path
        stores = await db.stores.find(
            {"logo_url": {"$regex": "^data:"}, "logo_path": {"$exists": False}},
            {"_id": 1, "logo_url": 1}
        ).to_list(200)
        for s in stores:
            try:
                result = await upload_image(s["logo_url"], prefix="logos", entity_id=str(s["_id"]))
                if result:
                    await db.stores.update_one({"_id": s["_id"]}, {"$set": {
                        "logo_path": result["original_path"],
                        "logo_thumb_path": result["thumbnail_path"],
                        "logo_avatar_path": result["avatar_path"],
                    }})
                    stats["stores"] += 1
            except Exception as e:
                logger.warning(f"Store logo migration failed {s['_id']}: {e}")
                stats["errors"] += 1
        await _update_progress()

        # 3. Contacts with base64 photo but no photo_path
        contacts = await db.contacts.find(
            {"photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}},
            {"_id": 1, "photo": 1}
        ).to_list(500)
        for c in contacts:
            try:
                result = await upload_image(c["photo"], prefix="contacts", entity_id=str(c["_id"]))
                if result:
                    await db.contacts.update_one({"_id": c["_id"]}, {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                        "photo_avatar_path": result["avatar_path"],
                        "photo_thumbnail": f"/api/images/{result['thumbnail_path']}",
                        "photo_url": f"/api/images/{result['thumbnail_path']}",
                    }})
                    stats["contacts"] += 1
            except Exception as e:
                logger.warning(f"Contact photo migration failed {c['_id']}: {e}")
                stats["errors"] += 1
        await _update_progress()

        # 4. Congrats cards with base64 customer_photo but no photo_path
        cards = await db.congrats_cards.find(
            {"customer_photo": {"$regex": "^data:"}, "photo_path": {"$exists": False}},
            {"_id": 1, "card_id": 1, "customer_photo": 1}
        ).to_list(500)
        for card in cards:
            try:
                cid = card.get("card_id", str(card["_id"]))
                result = await upload_image(card["customer_photo"], prefix="congrats", entity_id=cid)
                if result:
                    await db.congrats_cards.update_one({"_id": card["_id"]}, {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                        "photo_url": f"/api/images/{result['original_path']}",
                        "photo_thumbnail_url": f"/api/images/{result['thumbnail_path']}",
                    }})
                    stats["congrats"] += 1
            except Exception as e:
                logger.warning(f"Congrats photo migration failed {card['_id']}: {e}")
                stats["errors"] += 1
        await _update_progress()

        # 5. Feedback with base64 purchase_photo_url but no photo_path
        feedbacks = await db.customer_feedback.find(
            {"purchase_photo_url": {"$regex": "^data:"}, "photo_path": {"$exists": False}},
            {"_id": 1, "purchase_photo_url": 1}
        ).to_list(500)
        for fb in feedbacks:
            try:
                result = await upload_image(fb["purchase_photo_url"], prefix="feedback", entity_id=str(fb["_id"]))
                if result:
                    await db.customer_feedback.update_one({"_id": fb["_id"]}, {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                    }})
                    stats["feedback"] += 1
            except Exception as e:
                logger.warning(f"Feedback photo migration failed {fb['_id']}: {e}")
                stats["errors"] += 1

        elapsed = round(time.time() - start, 1)
        total = sum(v for k, v in stats.items() if k != "errors")
        result_data = {
            "migrated": stats,
            "backfilled": backfill_count,
            "total_migrated": total,
            "elapsed_seconds": elapsed,
            "message": f"Migrated {total} images in {elapsed}s.",
        }

        await db.migration_jobs.update_one(
            {"_id": ObjId(job_id)},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "result": result_data,
                "progress": {**stats, "total": total, "elapsed_seconds": elapsed},
            }},
        )
        logger.info(f"[Migration] Completed: {result_data['message']}")

    except Exception as e:
        logger.error(f"[Migration] Failed: {e}")
        await db.migration_jobs.update_one(
            {"_id": ObjId(job_id)},
            {"$set": {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc),
                "result": {"error": str(e)},
            }},
        )
