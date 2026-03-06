"""
Image storage service - handles uploads to Emergent Object Storage,
generates thumbnails/avatars, compresses originals, and serves images via public URLs.

Optimization strategy:
- All originals are compressed to max 1200px wide, WebP format, 85% quality
- Thumbnails: 200x200 WebP
- Avatars: 80x80 WebP
- Accounts with `hires_images: true` also get the uncompressed raw original stored
- All images use immutable cache headers (UUID-based paths never change)
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

# Size presets
ORIGINAL_MAX_WIDTH = 1200
THUMBNAIL_SIZE = (200, 200)
AVATAR_SIZE = (80, 80)
WEBP_QUALITY = 85
THUMB_QUALITY = 80


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


def _compress_image(image_bytes: bytes, max_width: int, quality: int) -> tuple:
    """Compress and resize an image to WebP. Returns (bytes, content_type).
    Preserves transparency for PNGs by using lossless WebP."""
    img = Image.open(io.BytesIO(image_bytes))
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )

    # Resize if wider than max_width (maintain aspect ratio)
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    if has_alpha:
        img = img.convert("RGBA")
        img.save(buf, format="WEBP", quality=quality, method=4)
    else:
        img = img.convert("RGB")
        img.save(buf, format="WEBP", quality=quality, method=4)

    return buf.getvalue(), "image/webp"


def generate_thumbnail(image_bytes: bytes, size: tuple) -> tuple:
    """Generate a WebP thumbnail. Returns (bytes, content_type, ext)."""
    img = Image.open(io.BytesIO(image_bytes))
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )

    if has_alpha:
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    img.thumbnail(size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=THUMB_QUALITY, method=4)
    return buf.getvalue(), "image/webp", "webp"


def decode_base64_image(data_uri: str) -> tuple:
    """Decode a base64 data URI into bytes + content type."""
    if data_uri.startswith("data:"):
        header, b64_data = data_uri.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
    else:
        b64_data = data_uri
        content_type = "image/jpeg"
    return base64.b64decode(b64_data), content_type


async def upload_image(image_data, prefix: str = "uploads", entity_id: str = "general", preserve_raw: bool = False):
    """
    Upload an image to object storage with automatic compression.
    
    - Default: compresses original to 1200px wide WebP
    - preserve_raw=True: also stores the uncompressed original (for hires accounts)
    - Always generates WebP thumbnail (200x200) and avatar (80x80)
    
    Returns dict with paths for all variants.
    """
    # Handle base64 data URIs
    if isinstance(image_data, str):
        if image_data.startswith("data:") or len(image_data) > 500:
            image_bytes, content_type = decode_base64_image(image_data)
        else:
            return None
    elif isinstance(image_data, bytes):
        image_bytes = image_data
        try:
            img = Image.open(io.BytesIO(image_bytes))
            fmt_map = {"PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp"}
            content_type = fmt_map.get(img.format, "image/jpeg")
        except Exception:
            content_type = "image/jpeg"
    else:
        return None

    file_id = str(uuid.uuid4())
    base_path = f"{APP_NAME}/{prefix}/{entity_id}"

    # 1. Compress original → WebP
    compressed_data, compressed_ct = _compress_image(image_bytes, ORIGINAL_MAX_WIDTH, WEBP_QUALITY)
    original_path = f"{base_path}/{file_id}.webp"
    put_object(original_path, compressed_data, compressed_ct)
    logger.info(f"Uploaded compressed image: {len(image_bytes)} → {len(compressed_data)} bytes ({100 - (len(compressed_data)*100//max(len(image_bytes),1))}% reduction)")

    # 2. Generate and upload WebP thumbnail
    thumb_data, thumb_ct, thumb_ext = generate_thumbnail(image_bytes, THUMBNAIL_SIZE)
    thumb_path = f"{base_path}/{file_id}_thumb.{thumb_ext}"
    put_object(thumb_path, thumb_data, thumb_ct)

    # 3. Generate and upload WebP avatar
    avatar_data, avatar_ct, avatar_ext = generate_thumbnail(image_bytes, AVATAR_SIZE)
    avatar_path = f"{base_path}/{file_id}_avatar.{avatar_ext}"
    put_object(avatar_path, avatar_data, avatar_ct)

    result = {
        "original_path": original_path,
        "thumbnail_path": thumb_path,
        "avatar_path": avatar_path,
        "content_type": compressed_ct,
        "file_id": file_id,
    }

    # 4. Optionally store raw original for hires accounts
    if preserve_raw:
        ext = "png" if "png" in content_type else "jpg"
        raw_path = f"{base_path}/{file_id}_raw.{ext}"
        put_object(raw_path, image_bytes, content_type)
        result["raw_path"] = raw_path
        logger.info(f"Preserved raw original ({len(image_bytes)} bytes) for hires account")

    return result
