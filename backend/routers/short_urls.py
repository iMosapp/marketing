"""
URL Shortener for i'M On Social
Generates short codes for business cards, congrats cards, and other shareable links.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from bson import ObjectId
from datetime import datetime
from typing import Optional
import os
import random
import string
import httpx
from io import BytesIO
from PIL import Image

from .database import get_db

router = APIRouter(prefix="/s", tags=["URL Shortener"])

# Characters for short codes (excluding confusing ones like 0/O, 1/l/I)
SHORT_CODE_CHARS = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"
SHORT_CODE_LENGTH = 6

def generate_short_code(length: int = SHORT_CODE_LENGTH) -> str:
    """Generate a random short code."""
    return ''.join(random.choices(SHORT_CODE_CHARS, k=length))

def get_short_url_base() -> str:
    """Get the base URL for short links. Prioritizes PUBLIC_FACING_URL to avoid
    deployment platforms overriding APP_URL with the staging/deploy domain."""
    short_domain = os.environ.get('SHORT_URL_DOMAIN')
    if short_domain:
        return short_domain.rstrip('/')
    public_url = os.environ.get("PUBLIC_FACING_URL")
    if public_url:
        return public_url.rstrip('/')
    return os.environ.get("APP_URL", "https://app.imonsocial.com")

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
    """Determine the event_type, title, icon, color from a short URL doc.
    Uses centralized event type module.
    """
    from utils.event_types import get_card_viewed_info, LINK_TYPE_TO_EVENT, EVENT_TYPE_LABELS
    link_type = doc.get("link_type", "")
    original_url = doc.get("original_url", "")

    if link_type == "review_request" or "/review/" in original_url:
        return "review_link_clicked", "Clicked Review Link", "star", "#FFD60A"
    if link_type == "business_card" or "/p/" in original_url or "/card/" in original_url:
        return "digital_card_viewed", "Viewed Digital Card", "eye", "#007AFF"
    if "/showcase/" in original_url or link_type == "showcase":
        return "showcase_viewed", "Viewed Showcase", "eye", "#C9A962"
    if "/l/" in original_url or "/linkpage/" in original_url or link_type == "link_page":
        return "link_page_viewed", "Viewed Link Page", "eye", "#AF52DE"
    # ALL card types (congrats, birthday, thank_you, etc.) are handled by congrats_cards.py
    card_link_types = {"congrats_card", "birthday_card", "thank_you_card", "thankyou_card",
                       "holiday_card", "welcome_card", "anniversary_card"}
    card_url_patterns = ["/congrats/", "/birthday/", "/thankyou/", "/holiday/", "/welcome/", "/anniversary/"]
    if link_type in card_link_types or any(p in original_url for p in card_url_patterns):
        return None, None, None, None  # handled by congrats_cards.py view tracking
    return "link_clicked", "Clicked Link", "open", "#007AFF"


async def _log_link_click_event(db, doc: dict, short_code: str):
    """Find the contact who received this short link and log a contact_event."""
    event_type, title, icon, color = _detect_event_type(doc)
    if not event_type:
        return  # skip (e.g., congrats cards handled elsewhere)

    user_id = doc.get("user_id")
    if not user_id:
        return

    # First, check if contact_id is stored directly in metadata (most reliable)
    contact_id = (doc.get("metadata") or {}).get("contact_id")

    # Fallback: search messages for the short code to identify the contact
    if not contact_id:
        msg = await db.messages.find_one(
            {"content": {"$regex": short_code}, "sender": "user", "user_id": user_id},
            {"conversation_id": 1}
        )
        if msg:
            conv = await db.conversations.find_one(
                {"_id": ObjectId(msg["conversation_id"])},
                {"contact_id": 1}
            )
            if conv and conv.get("contact_id"):
                contact_id = str(conv["contact_id"])

    if not contact_id:
        return

    # Avoid duplicate events within a short window (5 minutes)
    from datetime import timedelta
    recent = await db.contact_events.find_one({
        "contact_id": contact_id,
        "event_type": event_type,
        "timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=5)},
    })
    if recent:
        return

    contact_name = ""
    try:
        c = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
        if c:
            contact_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
    except Exception:
        pass

    await db.contact_events.insert_one({
        "contact_id": contact_id,
        "user_id": user_id,
        "event_type": event_type,
        "icon": icon,
        "color": color,
        "title": title,
        "description": f"{contact_name or 'Contact'} opened the shared link",
        "category": "customer_activity",
        "metadata": {"short_code": short_code, "link_type": doc.get("link_type", "")},
        "timestamp": datetime.utcnow(),
    })

    # Smart auto-complete: if customer clicked a review link, complete their review campaign
    if event_type == "review_link_clicked" and contact_id:
        try:
            review_campaigns = await db.campaigns.find(
                {"trigger_tag": "review_sent", "active": True}
            ).to_list(50)
            review_campaign_ids = [str(c["_id"]) for c in review_campaigns]
            if review_campaign_ids:
                result = await db.campaign_enrollments.update_many(
                    {
                        "contact_id": contact_id,
                        "campaign_id": {"$in": review_campaign_ids},
                        "status": "active",
                    },
                    {
                        "$set": {
                            "status": "completed",
                            "completed_at": datetime.utcnow(),
                            "completed_reason": "review_link_clicked",
                        }
                    },
                )
                if result.modified_count > 0:
                    # Also remove any pending sends for this contact's review campaigns
                    await db.campaign_pending_sends.delete_many({
                        "contact_id": contact_id,
                        "campaign_id": {"$in": review_campaign_ids},
                        "status": "pending",
                    })
                    # Mark related tasks as complete
                    await db.tasks.update_many({
                        "contact_id": contact_id,
                        "type": "campaign_send",
                        "status": {"$ne": "completed"},
                        "campaign_id": {"$in": review_campaign_ids},
                    }, {"$set": {"status": "completed", "completed_at": datetime.utcnow(), "auto_completed_reason": "customer_clicked_review_link"}})
                    import logging
                    logging.getLogger(__name__).info(f"[Smart Complete] Auto-completed {result.modified_count} review campaign(s) for contact {contact_id} — customer clicked review link")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Smart Complete] Review campaign auto-complete failed: {e}")

    # Fire engagement signal for real-time notification
    try:
        from routers.engagement_signals import record_signal
        link_type = doc.get("link_type", "link")
        signal_map = {
            "review": "review_link_clicked",
            "review_invite": "review_link_clicked",
            "digital_card": "digital_card_viewed",
            "showcase": "showcase_viewed",
            "link_page": "link_page_viewed",
        }
        signal_type = signal_map.get(link_type, "link_clicked")
        await record_signal(
            signal_type=signal_type,
            user_id=user_id,
            contact_id=contact_id,
            contact_name=contact_name,
            metadata={"short_code": short_code, "link_type": link_type},
        )
    except Exception:
        pass


@router.get("/og-image/{user_id}")
async def get_og_image(user_id: str):
    """Serve a store logo composited onto a white background for OG previews."""
    db = get_db()
    og_image_url = None
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
        if user_doc and user_doc.get("store_id"):
            store = await db.stores.find_one({"_id": ObjectId(user_doc["store_id"])}, {"logo_url": 1, "logo_avatar_url": 1})
            if store:
                og_image_url = store.get("logo_url") or store.get("logo_avatar_url")
    except Exception:
        pass

    if not og_image_url or og_image_url.startswith("data:"):
        static_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "og-image.png")
        if os.path.exists(static_path):
            with open(static_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(status_code=404, detail="OG image not found")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(og_image_url)
            resp.raise_for_status()
        logo = Image.open(BytesIO(resp.content)).convert("RGBA")
        size = (512, 512)
        white_bg = Image.new("RGB", size, (255, 255, 255))
        logo.thumbnail(size, Image.LANCZOS)
        x = (size[0] - logo.width) // 2
        y = (size[1] - logo.height) // 2
        white_bg.paste(logo, (x, y), logo)
        buf = BytesIO()
        white_bg.save(buf, format="PNG", quality=95)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        static_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "og-image.png")
        if os.path.exists(static_path):
            with open(static_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(status_code=500, detail="Failed to generate OG image")



@router.get("/{short_code}")
async def redirect_short_url(short_code: str, request: Request):
    """
    Redirect a short URL to the original URL.
    Serves dynamic OG meta tags for link previewers (iMessage, Facebook, etc.)
    so shared links show the store's logo instead of the default.
    """
    db = get_db()
    
    # Find the short URL
    doc = await db.short_urls.find_one({"short_code": short_code})
    
    if not doc:
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

    original_url = doc["original_url"]

    # Get contact_id from metadata for tracking
    doc_metadata = doc.get("metadata") or {}
    # For card links, reference_id is the card_id (NOT a contact_id).
    # Only use metadata.contact_id for tracking; never fall back to reference_id for cards.
    link_type = doc.get("link_type", "")
    if "_card" in link_type:
        cid = doc_metadata.get("contact_id")
    else:
        cid = doc_metadata.get("contact_id") or doc.get("reference_id")

    # Build the redirect URL with contact_id for tracking
    redirect_url = original_url
    if cid and f"cid={cid}" not in redirect_url:
        separator = "&" if "?" in redirect_url else "?"
        redirect_url = f"{redirect_url}{separator}cid={cid}"

    # Always serve HTML with OG meta tags + JS redirect.
    # This ensures link previewers (iMessage, Facebook, etc.) get rich previews
    # regardless of their user-agent, while normal browsers redirect instantly via JS.
    og_title = "Check this out!"
    og_description = ""
    og_image = ""
    link_type = doc.get("link_type", "")
    user_id = doc.get("user_id")
    # Use APP_URL for OG images — request.base_url returns internal cluster URLs behind proxies
    base_url = os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL", "https://app.imonsocial.com")
    base_url = base_url.rstrip("/")

    # Detect if this is ANY type of card link
    card_link_types = {"congrats_card", "birthday_card", "thank_you_card", "thankyou_card",
                       "holiday_card", "welcome_card", "anniversary_card"}
    ref_id = doc.get("reference_id", "")

    if link_type in card_link_types and ref_id:
        # === CARD LINK: Use customer photo + contextual title ===
        card_doc = await db.congrats_cards.find_one({"card_id": ref_id})
        if not card_doc:
            card_doc = await db.birthday_cards.find_one({"card_id": ref_id})
        if card_doc:
            customer_name = card_doc.get("customer_name", "")
            # Capitalize name properly
            customer_name = customer_name.strip().title() if customer_name else ""
            first_name = customer_name.split()[0] if customer_name else ""
            card_type = doc_metadata.get("card_type") or link_type.replace("_card", "")
            store_name = card_doc.get("store_name", "")
            salesman_name = card_doc.get("salesman_name", "")

            # Contextual titles per card type
            card_titles = {
                "congrats": f"Congrats {customer_name}!" if customer_name else "Congratulations!",
                "birthday": f"Happy Birthday {first_name}!" if first_name else "Happy Birthday!",
                "anniversary": f"Happy Anniversary {first_name}!" if first_name else "Happy Anniversary!",
                "thankyou": f"Thank You {first_name}!" if first_name else "Thank You!",
                "thank_you": f"Thank You {first_name}!" if first_name else "Thank You!",
                "welcome": f"Welcome {first_name}!" if first_name else "Welcome!",
                "holiday": f"Happy Holidays {first_name}!" if first_name else "Happy Holidays!",
            }
            og_title = card_titles.get(card_type, f"A special card for {customer_name}!" if customer_name else "You've received a card!")

            # Contextual description
            if salesman_name and store_name:
                og_description = f"From {salesman_name} at {store_name}"
            elif store_name:
                og_description = f"From {store_name}"
            elif salesman_name:
                og_description = f"From {salesman_name}"

            # OG Image priority: customer photo (object storage) > generated card image > store logo
            photo_url = card_doc.get("photo_url") or card_doc.get("customer_photo") or card_doc.get("optimized_photo_url")
            if photo_url and not photo_url.startswith("data:"):
                # Resolve relative URLs to absolute
                if photo_url.startswith("/"):
                    og_image = f"{base_url}{photo_url}"
                else:
                    og_image = photo_url
            else:
                # Use the generated card image (includes customer photo, QR code, branding)
                og_image = f"{base_url}/api/congrats/card/{ref_id}/image"
        else:
            # Card not found in DB, still try the image endpoint
            og_image = f"{base_url}/api/congrats/card/{ref_id}/image"
            meta_name = doc_metadata.get("customer_name", "")
            if meta_name:
                ct = link_type.replace("_card", "")
                meta_name = meta_name.strip().title()
                fn = meta_name.split()[0] if meta_name else ""
                ct_titles = {
                    "congrats": f"Congrats {meta_name}!",
                    "birthday": f"Happy Birthday {fn}!",
                    "anniversary": f"Happy Anniversary {fn}!",
                    "thankyou": f"Thank You {fn}!",
                    "thank_you": f"Thank You {fn}!",
                    "welcome": f"Welcome {fn}!",
                    "holiday": f"Happy Holidays {fn}!",
                }
                og_title = ct_titles.get(ct, f"A special card for {meta_name}!")
            else:
                og_title = "You've received a card!"

    elif user_id:
        # === NON-CARD LINK: Use store branding ===
        try:
            user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "first_name": 1, "last_name": 1, "photo_url": 1})
            if user_doc and user_doc.get("store_id"):
                store = await db.stores.find_one({"_id": ObjectId(user_doc["store_id"])}, {"name": 1, "logo_url": 1, "logo_avatar_url": 1})
                if store:
                    store_name = store.get("name", "")
                    user_name = f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip()
                    if link_type == "business_card":
                        og_title = f"{user_name}'s Digital Card" if user_name else "Digital Business Card"
                        og_description = f"Connect with {user_name} at {store_name}" if store_name else f"Connect with {user_name}"
                        sp_photo = user_doc.get("photo_url")
                        if sp_photo and not sp_photo.startswith("data:") and sp_photo.startswith("/"):
                            og_image = f"{base_url}{sp_photo}"
                        elif sp_photo and not sp_photo.startswith("data:"):
                            og_image = sp_photo
                    elif link_type == "referral":
                        sp_title = doc_metadata.get("salesman_title") or ""
                        if user_name and sp_title:
                            og_title = f"{user_name} — {sp_title}"
                        elif user_name:
                            og_title = f"Check out {user_name}!"
                        else:
                            og_title = "You've been referred!"
                        og_description = f"Connect with {user_name} at {store_name}" if store_name else f"Connect with {user_name}"
                        sp_photo = doc_metadata.get("photo_url") or user_doc.get("photo_url")
                        if sp_photo and not sp_photo.startswith("data:") and sp_photo.startswith("/"):
                            og_image = f"{base_url}{sp_photo}"
                        elif sp_photo and not sp_photo.startswith("data:"):
                            og_image = sp_photo
                    elif link_type in ("review_request", "review_invite", "review"):
                        og_title = f"Share Your Experience with {store_name}" if store_name else "We'd Love Your Feedback!"
                        og_description = f"{user_name} would love to hear about your experience" if user_name else "Your feedback means the world to us"
                    elif link_type == "showcase":
                        og_title = f"{store_name} — Happy Customers" if store_name else "Our Happy Customers"
                        og_description = f"See what customers are saying about {store_name}" if store_name else "Check out our showcase"
                        # Use salesperson's photo for personal touch (same as business card)
                        sp_photo = user_doc.get("photo_url")
                        if sp_photo and not sp_photo.startswith("data:") and sp_photo.startswith("/"):
                            og_image = f"{base_url}{sp_photo}"
                        elif sp_photo and not sp_photo.startswith("data:"):
                            og_image = sp_photo
                    elif link_type == "link_page":
                        og_title = f"{user_name}" if user_name else "Connect With Us"
                        og_description = f"Find all of {user_name}'s links" if user_name else ""
                    else:
                        og_title = store_name or "Check this out!"
                        og_description = f"Shared by {user_name}" if user_name else ""

                    if not og_image:
                        og_image = f"{base_url}/api/s/og-image/{user_id}"
        except Exception:
            pass

    # Fallback: use the static OG image
    if not og_image:
        og_image = f"{base_url}/og-image.png"

    from fastapi.responses import HTMLResponse
    og_image_tags = ""
    if og_image:
        if "/congrats/card/" in og_image and "/image" in og_image:
            img_w, img_h = "1080", "1350"
        else:
            img_w, img_h = "800", "800"
        og_image_tags = f"""<meta property="og:image" content="{og_image}" />
<meta property="og:image:width" content="{img_w}" />
<meta property="og:image:height" content="{img_h}" />"""

    # Escape any quotes in titles/descriptions for safe HTML embedding
    safe_title = og_title.replace('"', '&quot;').replace("'", '&#39;')
    safe_desc = og_description.replace('"', '&quot;').replace("'", '&#39;')

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8" />
<meta property="og:title" content="{safe_title}" />
<meta property="og:description" content="{safe_desc}" />
{og_image_tags}
<meta property="og:url" content="{redirect_url}" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{safe_title}" />
<meta name="twitter:description" content="{safe_desc}" />
</head><body>
<script>window.location.replace("{redirect_url}");</script>
<noscript><meta http-equiv="refresh" content="0;url={redirect_url}" /></noscript>
<p><a href="{redirect_url}">Continue</a></p>
</body></html>"""
    return HTMLResponse(content=html)


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
