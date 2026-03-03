"""
URL Shortener for i'M On Social
Generates short codes for business cards, congrats cards, and other shareable links.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from bson import ObjectId
from datetime import datetime
from typing import Optional
import os
import random
import string

from .database import get_db

router = APIRouter(prefix="/s", tags=["URL Shortener"])

# Characters for short codes (excluding confusing ones like 0/O, 1/l/I)
SHORT_CODE_CHARS = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"
SHORT_CODE_LENGTH = 6

def generate_short_code(length: int = SHORT_CODE_LENGTH) -> str:
    """Generate a random short code."""
    return ''.join(random.choices(SHORT_CODE_CHARS, k=length))

def get_short_url_base() -> str:
    """Get the base URL for short links."""
    short_domain = os.environ.get('SHORT_URL_DOMAIN')
    if short_domain:
        return short_domain.rstrip('/')
    return os.environ.get("APP_URL", "https://app.imosapp.com")

async def create_short_url(
    original_url: str,
    link_type: str,
    reference_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> dict:
    """
    Create a short URL for any link.
    
    Args:
        original_url: The full URL to shorten
        link_type: Type of link (business_card, congrats_card, referral, etc.)
        reference_id: ID of the related object (card ID, user ID, etc.)
        user_id: ID of the user who created this link
        metadata: Additional data to store
    
    Returns:
        dict with short_code and full short_url
    """
    db = get_db()
    
    # Check if we already have a short URL for this exact original URL
    existing = await db.short_urls.find_one({
        "original_url": original_url,
        "link_type": link_type,
        "reference_id": reference_id
    })
    
    if existing:
        return {
            "short_code": existing["short_code"],
            "short_url": f"{get_short_url_base()}/api/s/{existing['short_code']}",
            "original_url": original_url
        }
    
    # Generate a unique short code
    max_attempts = 10
    for _ in range(max_attempts):
        short_code = generate_short_code()
        # Check if code already exists
        if not await db.short_urls.find_one({"short_code": short_code}):
            break
    else:
        # If we couldn't find a unique code, use a longer one
        short_code = generate_short_code(8)
    
    # Create the short URL record
    short_url_doc = {
        "short_code": short_code,
        "original_url": original_url,
        "link_type": link_type,
        "reference_id": reference_id,
        "user_id": user_id,
        "metadata": metadata or {},
        "click_count": 0,
        "created_at": datetime.utcnow(),
        "last_clicked_at": None,
    }
    
    await db.short_urls.insert_one(short_url_doc)
    
    # Create index for fast lookups
    await db.short_urls.create_index("short_code", unique=True)
    
    return {
        "short_code": short_code,
        "short_url": f"{get_short_url_base()}/api/s/{short_code}",
        "original_url": original_url
    }


async def get_short_url_stats(short_code: str) -> Optional[dict]:
    """Get stats for a short URL."""
    db = get_db()
    doc = await db.short_urls.find_one({"short_code": short_code})
    if not doc:
        return None
    
    return {
        "short_code": doc["short_code"],
        "original_url": doc["original_url"],
        "link_type": doc["link_type"],
        "click_count": doc.get("click_count", 0),
        "created_at": doc["created_at"],
        "last_clicked_at": doc.get("last_clicked_at"),
    }


def _detect_event_type(doc: dict) -> tuple:
    """Determine the event_type, title, icon, color from a short URL doc."""
    link_type = doc.get("link_type", "")
    original_url = doc.get("original_url", "")

    if link_type == "business_card" or "/p/" in original_url:
        return "digital_card_viewed", "Viewed Digital Card", "eye", "#007AFF"
    if "/review/" in original_url:
        return "review_page_viewed", "Viewed Review Page", "eye", "#FBBC04"
    if "/showcase/" in original_url:
        return "showcase_viewed", "Viewed Showcase", "eye", "#C9A962"
    if "/l/" in original_url or "/linkpage/" in original_url:
        return "link_page_viewed", "Viewed Link Page", "eye", "#AF52DE"
    if link_type == "congrats_card" or "/congrats/" in original_url:
        return None, None, None, None  # handled by congrats_cards.py
    return "link_clicked", "Clicked Link", "open", "#007AFF"


async def _log_link_click_event(db, doc: dict, short_code: str):
    """Find the contact who received this short link and log a contact_event."""
    event_type, title, icon, color = _detect_event_type(doc)
    if not event_type:
        return  # skip (e.g., congrats cards handled elsewhere)

    user_id = doc.get("user_id")
    if not user_id:
        return

    # Find a message containing this short code to identify the contact
    msg = await db.messages.find_one(
        {"content": {"$regex": short_code}, "sender": "user", "user_id": user_id},
        {"conversation_id": 1}
    )
    if not msg:
        return

    conv = await db.conversations.find_one(
        {"_id": ObjectId(msg["conversation_id"])},
        {"contact_id": 1}
    )
    if not conv or not conv.get("contact_id"):
        return

    contact_id = str(conv["contact_id"])

    # Avoid duplicate events within a short window (1 hour)
    from datetime import timedelta
    recent = await db.contact_events.find_one({
        "contact_id": contact_id,
        "event_type": event_type,
        "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=1)},
    })
    if recent:
        return

    await db.contact_events.insert_one({
        "contact_id": contact_id,
        "user_id": user_id,
        "event_type": event_type,
        "icon": icon,
        "color": color,
        "title": title,
        "description": f"Contact opened the shared link",
        "category": "customer_activity",
        "metadata": {"short_code": short_code, "link_type": doc.get("link_type", "")},
        "timestamp": datetime.utcnow(),
    })


@router.get("/{short_code}")
async def redirect_short_url(short_code: str, request: Request):
    """
    Redirect a short URL to the original URL.
    Also tracks click analytics.
    """
    db = get_db()
    
    # Find the short URL
    doc = await db.short_urls.find_one({"short_code": short_code})
    
    if not doc:
        # Return a nice error page or redirect to home
        raise HTTPException(status_code=404, detail="Link not found")
    
    # Update click stats
    await db.short_urls.update_one(
        {"short_code": short_code},
        {
            "$inc": {"click_count": 1},
            "$set": {"last_clicked_at": datetime.utcnow()}
        }
    )
    
    # Log the click for analytics
    click_log = {
        "short_code": short_code,
        "link_type": doc.get("link_type"),
        "reference_id": doc.get("reference_id"),
        "user_agent": request.headers.get("user-agent", ""),
        "referer": request.headers.get("referer", ""),
        "ip": request.client.host if request.client else None,
        "clicked_at": datetime.utcnow()
    }
    await db.short_url_clicks.insert_one(click_log)

    # Log a contact_event so the click appears in the activity feed
    try:
        await _log_link_click_event(db, doc, short_code)
    except Exception as e:
        print(f"[ShortURL] Failed to log click event: {e}")

    # Redirect to the original URL
    return RedirectResponse(url=doc["original_url"], status_code=302)


@router.post("/create")
async def create_short_url_endpoint(data: dict):
    """
    API endpoint to create a short URL.
    
    Body:
        original_url: The URL to shorten
        link_type: Type of link
        reference_id: Optional reference ID
        user_id: Optional user ID
    """
    original_url = data.get("original_url")
    if not original_url:
        raise HTTPException(status_code=400, detail="original_url is required")
    
    result = await create_short_url(
        original_url=original_url,
        link_type=data.get("link_type", "custom"),
        reference_id=data.get("reference_id"),
        user_id=data.get("user_id"),
        metadata=data.get("metadata")
    )
    
    return result


@router.get("/stats/{short_code}")
async def get_stats(short_code: str):
    """Get analytics for a short URL."""
    stats = await get_short_url_stats(short_code)
    if not stats:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return stats
