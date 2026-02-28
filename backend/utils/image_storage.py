"""
Image storage service — handles uploads to Emergent Object Storage,
generates thumbnails/avatars, and serves images via public URLs.
"""
import os
import io
import uuid
import base64
import logging
import requests
from PIL import Image

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "imos"

storage_key = None

THUMBNAIL_SIZE = (200, 200)
AVATAR_SIZE = (80, 80)


def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(
        f"{STORAGE_URL}/init",
        json={"emergent_key": EMERGENT_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    logger.info("Object storage initialized")
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def generate_thumbnail(image_bytes: bytes, size: tuple, preserve_alpha: bool = False) -> tuple:
    """Generate a thumbnail. Returns (bytes, format_str, content_type, ext)."""
    img = Image.open(io.BytesIO(image_bytes))
    if preserve_alpha and img.mode in ("RGBA", "LA", "PA"):
        img = img.convert("RGBA")
        img.thumbnail(size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "PNG", "image/png", "png"
    else:
        img = img.convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        return buf.getvalue(), "JPEG", "image/jpeg", "jpg"


def decode_base64_image(data_uri: str) -> tuple:
    """Decode a base64 data URI into bytes + content type."""
    if data_uri.startswith("data:"):
        header, b64_data = data_uri.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
    else:
        b64_data = data_uri
        content_type = "image/jpeg"
    return base64.b64decode(b64_data), content_type


async def upload_image(image_data, prefix: str = "uploads", entity_id: str = "general"):
    """
    Upload an image (base64 string or bytes) to object storage.
    Returns dict with original_url, thumbnail_url, avatar_url storage paths.
    """
    # Handle base64 data URIs
    if isinstance(image_data, str):
        if image_data.startswith("data:") or len(image_data) > 500:
            image_bytes, content_type = decode_base64_image(image_data)
        else:
            # It's already a URL, not base64 — nothing to upload
            return None
    elif isinstance(image_data, bytes):
        image_bytes = image_data
        content_type = "image/jpeg"
    else:
        return None

    file_id = str(uuid.uuid4())
    ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]

    # Upload original
    original_path = f"{APP_NAME}/{prefix}/{entity_id}/{file_id}.{ext}"
    put_object(original_path, image_bytes, content_type)

    # Generate and upload thumbnail
    thumb_bytes = generate_thumbnail(image_bytes, THUMBNAIL_SIZE)
    thumb_path = f"{APP_NAME}/{prefix}/{entity_id}/{file_id}_thumb.jpg"
    put_object(thumb_path, thumb_bytes, "image/jpeg")

    # Generate and upload avatar
    avatar_bytes = generate_thumbnail(image_bytes, AVATAR_SIZE)
    avatar_path = f"{APP_NAME}/{prefix}/{entity_id}/{file_id}_avatar.jpg"
    put_object(avatar_path, avatar_bytes, "image/jpeg")

    return {
        "original_path": original_path,
        "thumbnail_path": thumb_path,
        "avatar_path": avatar_path,
        "content_type": content_type,
        "file_id": file_id,
    }
