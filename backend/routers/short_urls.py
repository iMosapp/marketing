"""
URL Shortener for MVPLine
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
    """Get the base URL for short links. Easy to change for rebranding."""
    # Check for custom short domain first
    short_domain = os.environ.get('SHORT_URL_DOMAIN')
    if short_domain:
        return short_domain.rstrip('/')
    
    # Use the preview URL base
    # This will be set to the final domain (mvpline.com) in production
    base_url = os.environ.get('BASE_URL', 'https://imos-auth-ui.preview.emergentagent.com')
    return base_url.rstrip('/')

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
