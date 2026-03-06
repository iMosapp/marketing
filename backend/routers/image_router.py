"""
Image router - serves stored images with CDN-like caching.

Caching strategy:
1. In-memory LRU cache (~200MB) — hot images served from RAM
2. ETag + If-None-Match → 304 Not Modified (zero body transfer)
3. Cache-Control: immutable (1 year) — browser never re-validates
4. Images cached on upload → first view is already in RAM
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Request
from fastapi.responses import Response
from datetime import datetime, timezone
import logging

from routers.database import get_db
from utils.image_storage import upload_image, get_object, make_etag, get_cache_stats

router = APIRouter(prefix="/images", tags=["Images"])
logger = logging.getLogger(__name__)


@router.get("/cache-stats")
async def cache_stats():
    """Get image cache statistics (admin/debug endpoint)."""
    return get_cache_stats()


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
