"""
Tracked Media Router
Upload photos/videos, get a tracked viewing link. When the recipient opens it,
the view is logged as a contact_event with full analytics.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import HTMLResponse, Response
from bson import ObjectId
from datetime import datetime, timezone
import logging
import os
import uuid

from routers.database import get_db

router = APIRouter(prefix="/media", tags=["Tracked Media"])
logger = logging.getLogger(__name__)


def _get_base_url() -> str:
    return (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


@router.post("/upload-tracked")
async def upload_tracked_media(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    contact_id: str = Form(default=""),
    contact_name: str = Form(default=""),
    caption: str = Form(default=""),
):
    """
    Upload a photo or video and get back a tracked short URL.
    When the recipient opens the link, the view is logged.

    Returns:
        tracked_url: The short URL to send to the customer
        media_url: The direct media URL (for inline display)
        media_id: The tracked media record ID
    """
    from utils.image_storage import upload_image, put_object
    from routers.short_urls import create_short_url

    db = get_db()
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    is_video = content_type.startswith("video/")
    is_image = content_type.startswith("image/")

    if not is_video and not is_image:
        raise HTTPException(status_code=400, detail="File must be an image or video")

    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be under 50MB")

    file_id = str(uuid.uuid4())
    base_url = _get_base_url()

    if is_image:
        result = await upload_image(content, prefix="tracked", entity_id=file_id)
        if not result:
            raise HTTPException(status_code=500, detail="Upload failed")
        media_path = result["original_path"]
        thumb_path = result.get("thumbnail_path", media_path)
        media_url = f"/api/images/{media_path}"
    else:
        # Video: store raw in object storage
        ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "mp4"
        media_path = f"imos/tracked/{file_id}/video.{ext}"
        thumb_path = ""
        import asyncio
        await asyncio.to_thread(put_object, media_path, content, content_type)
        media_url = f"/api/images/{media_path}"

    # Create tracked_media record
    media_doc = {
        "media_id": file_id,
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "caption": caption,
        "media_type": "video" if is_video else "image",
        "content_type": content_type,
        "media_path": media_path,
        "thumb_path": thumb_path,
        "media_url": media_url,
        "view_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    await db.tracked_media.insert_one(media_doc)

    # Create viewing page URL and wrap it in a tracked short URL
    view_page_url = f"{base_url}/api/media/view/{file_id}"
    short_result = await create_short_url(
        original_url=view_page_url,
        link_type="tracked_media",
        reference_id=file_id,
        user_id=user_id,
        metadata={
            "contact_id": contact_id,
            "contact_name": contact_name,
            "media_type": "video" if is_video else "image",
            "source": "composer",
        },
    )

    return {
        "tracked_url": short_result["short_url"],
        "short_code": short_result["short_code"],
        "media_url": media_url,
        "media_id": file_id,
        "media_type": "video" if is_video else "image",
    }


@router.get("/view/{media_id}")
async def view_tracked_media(media_id: str):
    """
    Branded media viewing page. Logs the view and shows the photo/video
    in a beautiful full-screen layout.
    """
    db = get_db()
    doc = await db.tracked_media.find_one({"media_id": media_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Media not found")

    # Increment view count
    await db.tracked_media.update_one(
        {"media_id": media_id},
        {"$inc": {"view_count": 1}, "$set": {"last_viewed_at": datetime.now(timezone.utc)}}
    )

    # Log contact_event for the view
    user_id = doc.get("user_id", "")
    contact_id = doc.get("contact_id", "")
    contact_name = doc.get("contact_name", "")
    media_type = doc.get("media_type", "image")

    if user_id and contact_id:
        # Deduplicate: only log once per 5 minutes
        from datetime import timedelta
        recent = await db.contact_events.find_one({
            "contact_id": contact_id,
            "event_type": "media_viewed",
            "metadata.media_id": media_id,
            "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(minutes=5)},
        })
        if not recent:
            await db.contact_events.insert_one({
                "contact_id": contact_id,
                "user_id": user_id,
                "event_type": "media_viewed",
                "icon": "videocam" if media_type == "video" else "image",
                "color": "#FF2D55",
                "title": f"Viewed {media_type.title()}",
                "description": f"{contact_name or 'Contact'} opened the {media_type} you sent",
                "category": "customer_activity",
                "metadata": {"media_id": media_id, "media_type": media_type},
                "timestamp": datetime.now(timezone.utc),
            })

        # Fire engagement signal
        try:
            from routers.engagement_signals import record_signal
            await record_signal(
                signal_type="media_viewed",
                user_id=user_id,
                contact_id=contact_id,
                contact_name=contact_name,
                metadata={"media_id": media_id, "media_type": media_type},
            )
        except Exception:
            pass

    # Build the viewing page
    base_url = _get_base_url()
    full_media_url = f"{base_url}{doc['media_url']}"
    caption = doc.get("caption", "")

    # Get salesperson info for branding
    salesman_name = ""
    store_name = ""
    accent = "#C9A962"
    if user_id:
        try:
            user_doc = await db.users.find_one(
                {"_id": ObjectId(user_id)},
                {"name": 1, "first_name": 1, "last_name": 1, "store_id": 1}
            )
            if user_doc:
                salesman_name = user_doc.get("name") or f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip()
                if user_doc.get("store_id"):
                    store = await db.stores.find_one(
                        {"_id": ObjectId(user_doc["store_id"])},
                        {"name": 1, "primary_color": 1, "email_brand_kit": 1}
                    )
                    if store:
                        store_name = store.get("name", "")
                        brand = store.get("email_brand_kit") or {}
                        accent = brand.get("primary_color") or store.get("primary_color") or "#C9A962"
        except Exception:
            pass

    safe_caption = (caption or "").replace('"', '&quot;').replace("'", "&#39;").replace("<", "&lt;")
    from_line = ""
    if salesman_name and store_name:
        from_line = f"Shared by {salesman_name} at {store_name}"
    elif salesman_name:
        from_line = f"Shared by {salesman_name}"

    if media_type == "video":
        media_html = f'<video controls playsinline autoplay muted style="max-width:100%;max-height:70vh;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.5)"><source src="{full_media_url}" type="{doc.get("content_type","video/mp4")}">Your browser does not support video.</video>'
    else:
        media_html = f'<img src="{full_media_url}" alt="Shared media" style="max-width:100%;max-height:70vh;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.5);object-fit:contain" />'

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta property="og:title" content="{safe_caption or ('A video for you' if media_type == 'video' else 'A photo for you')}"/>
<meta property="og:description" content="{from_line}"/>
<meta property="og:image" content="{full_media_url}"/>
<meta property="og:type" content="website"/>
<title>{safe_caption or 'View Media'}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,system-ui,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px}}
.accent-bar{{position:fixed;top:0;left:0;right:0;height:3px;background:{accent}}}
.container{{max-width:600px;width:100%;text-align:center}}
.media-wrap{{margin:16px 0;line-height:0}}
.caption{{font-size:16px;color:#e0e0e0;margin:16px 0 8px;line-height:1.5}}
.from{{font-size:13px;color:#888;margin-bottom:20px}}
.brand{{font-size:13px;font-weight:600;letter-spacing:-.3px;color:{accent};margin-top:24px}}
</style>
</head><body>
<div class="accent-bar"></div>
<div class="container">
<div class="media-wrap">{media_html}</div>
{"<p class='caption'>" + safe_caption + "</p>" if safe_caption else ""}
{"<p class='from'>" + from_line + "</p>" if from_line else ""}
<p class="brand">i'M On Social</p>
</div>
</body></html>"""

    return HTMLResponse(content=html)


@router.get("/stats/{media_id}")
async def tracked_media_stats(media_id: str):
    """Get view stats for a tracked media item."""
    db = get_db()
    doc = await db.tracked_media.find_one({"media_id": media_id}, {"_id": 0, "media_id": 1, "view_count": 1, "last_viewed_at": 1, "media_type": 1, "created_at": 1, "contact_name": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Tracked media not found")
    return doc
