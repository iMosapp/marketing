"""
Image router  - serves stored images and handles uploads.
All images served through /api/images/{path} endpoints.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db
from utils.image_storage import upload_image, get_object, init_storage

router = APIRouter(prefix="/images", tags=["Images"])
logger = logging.getLogger(__name__)


@router.get("/{path:path}")
async def serve_image(path: str):
    """Serve an image from object storage. Public endpoint for img src."""
    try:
        data, content_type = get_object(path)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        logger.error(f"Failed to serve image {path}: {e}")
        raise HTTPException(status_code=404, detail="Image not found")


@router.post("/upload")
async def upload_image_endpoint(file: UploadFile = File(...), entity_type: str = "general", entity_id: str = "general"):
    """Upload an image file and get back URLs for original, thumbnail, and avatar."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")

    result = await upload_image(data, prefix=entity_type, entity_id=entity_id)
    if not result:
        raise HTTPException(status_code=500, detail="Upload failed")

    base_url = "/api/images"
    return {
        "original_url": f"{base_url}/{result['original_path']}",
        "thumbnail_url": f"{base_url}/{result['thumbnail_path']}",
        "avatar_url": f"{base_url}/{result['avatar_path']}",
        "file_id": result["file_id"],
    }


@router.post("/upload-base64")
async def upload_base64_image(data: dict):
    """Upload a base64 image and get back URLs."""
    image_data = data.get("image")
    entity_type = data.get("entity_type", "general")
    entity_id = data.get("entity_id", "general")

    if not image_data:
        raise HTTPException(status_code=400, detail="No image data provided")

    result = await upload_image(image_data, prefix=entity_type, entity_id=entity_id)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid image data or already a URL")

    base_url = "/api/images"
    return {
        "original_url": f"{base_url}/{result['original_path']}",
        "thumbnail_url": f"{base_url}/{result['thumbnail_path']}",
        "avatar_url": f"{base_url}/{result['avatar_path']}",
        "file_id": result["file_id"],
    }
