"""
Image router - serves stored images and handles uploads.
All images served through /api/images/{path} endpoints.

Optimization:
- Immutable cache headers (1 year) since paths use UUIDs
- Checks org `hires_images` flag to preserve raw originals
- Supports WebP output for all compressed images
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Header
from fastapi.responses import Response
from datetime import datetime, timezone
import logging

from routers.database import get_db
from utils.image_storage import upload_image, get_object

router = APIRouter(prefix="/images", tags=["Images"])
logger = logging.getLogger(__name__)

# Immutable cache: UUID-based paths never change, cache for 1 year
CACHE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "Vary": "Accept-Encoding",
}


@router.get("/{path:path}")
async def serve_image(path: str):
    """Serve an image from object storage with aggressive caching."""
    try:
        data, content_type = get_object(path)
        return Response(
            content=data,
            media_type=content_type,
            headers=CACHE_HEADERS,
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
    """Upload an image file. Automatically compresses to WebP.
    If the user's org has `hires_images: true`, also stores the raw original."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")

    # Check if user's org has hires_images enabled
    preserve_raw = False
    if x_user_id:
        try:
            db = get_db()
            user = await db.users.find_one({"_id": __import__("bson").ObjectId(x_user_id)}, {"organization_id": 1})
            if user and user.get("organization_id"):
                org = await db.organizations.find_one(
                    {"_id": __import__("bson").ObjectId(user["organization_id"])},
                    {"hires_images": 1}
                )
                preserve_raw = bool(org and org.get("hires_images"))
        except Exception as e:
            logger.debug(f"Could not check hires_images flag: {e}")

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
    """Upload a base64 image. Automatically compresses to WebP."""
    image_data = data.get("image")
    entity_type = data.get("entity_type", "general")
    entity_id = data.get("entity_id", "general")

    if not image_data:
        raise HTTPException(status_code=400, detail="No image data provided")

    # Check hires flag
    preserve_raw = False
    if x_user_id:
        try:
            db = get_db()
            user = await db.users.find_one({"_id": __import__("bson").ObjectId(x_user_id)}, {"organization_id": 1})
            if user and user.get("organization_id"):
                org = await db.organizations.find_one(
                    {"_id": __import__("bson").ObjectId(user["organization_id"])},
                    {"hires_images": 1}
                )
                preserve_raw = bool(org and org.get("hires_images"))
        except Exception as e:
            logger.debug(f"Could not check hires_images flag: {e}")

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
