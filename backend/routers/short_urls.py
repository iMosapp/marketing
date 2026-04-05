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
from PIL import Image, ImageDraw, ImageFont

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

    if link_type == "training_video" or ("youtube.com" in original_url and link_type == "training_video"):
        return "training_video_clicked", "Watched Training Video", "play-circle", "#AF52DE"
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

    # Avoid duplicate events within a short window (30 minutes)
    from datetime import timedelta
    recent = await db.contact_events.find_one({
        "contact_id": contact_id,
        "event_type": event_type,
        "timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=30)},
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
            "training_video": "training_video_clicked",
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


def _load_font(bold=False, size=40):
    """Load DejaVu font with fallback to default."""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        from PIL import ImageFont
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


async def _fetch_image(url: str, app_url: str) -> "Image.Image | None":
    """Fetch an image from a URL (handles relative /api/ paths)."""
    if not url or url.startswith("data:"):
        return None
    full_url = f"{app_url}{url}" if url.startswith("/") else url
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(full_url)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


async def _generate_og_image_bytes(user_doc, store_doc, app_url) -> bytes:
    """Generate a photo-dominant 1200x630 OG image in WebP.

    Layout: salesperson photo fills left ~60% of frame, name/title overlaid
    at the bottom with a gradient scrim. Store logo in the bottom-right.
    """
    from PIL import ImageDraw, ImageFilter
    from utils.image_urls import resolve_user_photo, resolve_store_logo

    user_photo_url = resolve_user_photo(user_doc)
    store_logo_url = resolve_store_logo(store_doc) if store_doc else None
    user_name = user_doc.get("name", "")
    user_title = user_doc.get("title", "")
    store_name = store_doc.get("name", "") if store_doc else ""

    brand_kit = user_doc.get("email_brand_kit") or {}
    if not brand_kit and store_doc:
        brand_kit = store_doc.get("email_brand_kit") or {}
    accent_hex = brand_kit.get("primary_color") or (store_doc.get("primary_color") if store_doc else None) or "#C9A962"
    accent = _hex_to_rgb(accent_hex)

    W, H = 1200, 630
    bg = (17, 17, 17)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # --- Photo: fill the left ~55% of the frame ---
    photo_img = await _fetch_image(user_photo_url, app_url)
    photo_area_w = 660  # left portion for the photo

    if photo_img:
        pw, ph = photo_img.size
        # Crop to fill the photo area (cover fit)
        target_ratio = photo_area_w / H
        source_ratio = pw / ph
        if source_ratio > target_ratio:
            # Source is wider — crop sides
            new_w = int(ph * target_ratio)
            left = (pw - new_w) // 2
            photo_img = photo_img.crop((left, 0, left + new_w, ph))
        else:
            # Source is taller — crop top/bottom
            new_h = int(pw / target_ratio)
            top = (ph - new_h) // 2
            photo_img = photo_img.crop((0, top, pw, top + new_h))
        photo_img = photo_img.resize((photo_area_w, H), Image.LANCZOS)
        img.paste(photo_img.convert("RGB"), (0, 0))

        # Gradient scrim over the photo bottom for text legibility
        gradient = Image.new("RGBA", (photo_area_w, 200), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gradient)
        for y in range(200):
            alpha = int(200 * (y / 200))
            gd.line([(0, y), (photo_area_w, y)], fill=(0, 0, 0, alpha))
        img.paste(Image.alpha_composite(
            img.crop((0, H - 200, photo_area_w, H)).convert("RGBA"), gradient
        ).convert("RGB"), (0, H - 200))

        # Soft fade from photo edge into the dark right panel
        fade_w = 80
        fade_start = photo_area_w - fade_w
        for x_off in range(fade_w):
            alpha = int(255 * (x_off / fade_w))
            draw.line([(fade_start + x_off, 0), (fade_start + x_off, H)], fill=(bg[0], bg[1], bg[2], alpha))
    else:
        # No photo — draw a large circle with initials
        cx, cy = photo_area_w // 2, H // 2
        radius = 200
        draw.ellipse([cx - radius - 4, cy - radius - 4, cx + radius + 4, cy + radius + 4], fill=accent)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(30, 30, 30))
        if user_name:
            initials = "".join(w[0].upper() for w in user_name.split()[:2])
            fi = _load_font(True, 96)
            bbox = draw.textbbox((0, 0), initials, font=fi)
            iw, ih = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - iw // 2, cy - ih // 2 - 8), initials, fill=accent, font=fi)

    # --- Accent stripe at top ---
    draw.rectangle([0, 0, W, 5], fill=accent)

    # --- Right panel: name, title, store name ---
    text_x = photo_area_w + 40
    text_max_w = W - text_x - 40

    # Name (large, bold)
    f_name = _load_font(True, 44)
    name_y = H // 2 - 70
    if user_name:
        display_name = user_name
        bbox = draw.textbbox((0, 0), display_name, font=f_name)
        while bbox[2] - bbox[0] > text_max_w and len(display_name) > 10:
            display_name = display_name[:-2] + "..."
            bbox = draw.textbbox((0, 0), display_name, font=f_name)
        draw.text((text_x, name_y), display_name, fill=(255, 255, 255), font=f_name)

    # Title
    f_title = _load_font(False, 26)
    title_y = name_y + 58
    if user_title:
        title_text = user_title
        bbox = draw.textbbox((0, 0), title_text, font=f_title)
        while bbox[2] - bbox[0] > text_max_w and len(title_text) > 10:
            title_text = title_text[:-2] + "..."
            bbox = draw.textbbox((0, 0), title_text, font=f_title)
        draw.text((text_x, title_y), title_text, fill=accent, font=f_title)

    # Store name
    f_store = _load_font(False, 22)
    store_y = title_y + 40
    if store_name:
        draw.text((text_x, store_y), store_name, fill=(140, 140, 140), font=f_store)

    # Divider
    div_y = store_y + 38
    draw.rectangle([text_x, div_y, text_x + 60, div_y + 3], fill=accent)

    # --- Store logo (bottom-right) ---
    logo_img = await _fetch_image(store_logo_url, app_url)
    if logo_img:
        lw, lh = logo_img.size
        max_logo_w, max_logo_h = 140, 50
        scale = min(max_logo_w / lw, max_logo_h / lh, 1.0)
        logo_img = logo_img.resize((int(lw * scale), int(lh * scale)), Image.LANCZOS)
        lw, lh = logo_img.size
        img.paste(logo_img.convert("RGB"), (W - lw - 30, H - lh - 25),
                  logo_img if logo_img.mode == "RGBA" else None)

    # Bottom accent stripe
    draw.rectangle([0, H - 5, W, H], fill=accent)

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


async def _generate_customer_og_image_bytes(card_doc, store_doc, app_url) -> bytes:
    """Generate a photo-dominant 1200x630 OG image for a customer card.

    The customer's photo fills the left side, their name and card context
    appear on the right. Cached as WebP for fast delivery.
    """
    from PIL import ImageDraw
    from utils.image_urls import resolve_store_logo

    customer_name = (card_doc.get("customer_name") or "").strip().title()
    salesman_name = card_doc.get("salesman_name", "")
    store_name = card_doc.get("store_name", "")
    card_type = card_doc.get("card_type", "congrats")

    store_logo_url = resolve_store_logo(store_doc) if store_doc else None

    brand_kit = (store_doc or {}).get("email_brand_kit") or {}
    accent_hex = brand_kit.get("primary_color") or (store_doc.get("primary_color") if store_doc else None) or "#C9A962"
    accent = _hex_to_rgb(accent_hex)

    # Resolve customer photo
    photo_url = (card_doc.get("photo_url") or card_doc.get("customer_photo") or
                 card_doc.get("optimized_photo_url") or "")
    if photo_url.startswith("data:"):
        photo_url = ""

    W, H = 1200, 630
    bg = (17, 17, 17)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # --- Customer photo: fill left ~55% ---
    photo_area_w = 660
    photo_img = await _fetch_image(photo_url, app_url) if photo_url else None

    if photo_img:
        pw, ph = photo_img.size
        target_ratio = photo_area_w / H
        source_ratio = pw / ph
        if source_ratio > target_ratio:
            new_w = int(ph * target_ratio)
            left = (pw - new_w) // 2
            photo_img = photo_img.crop((left, 0, left + new_w, ph))
        else:
            new_h = int(pw / target_ratio)
            top = (ph - new_h) // 2
            photo_img = photo_img.crop((0, top, pw, top + new_h))
        photo_img = photo_img.resize((photo_area_w, H), Image.LANCZOS)
        img.paste(photo_img.convert("RGB"), (0, 0))

        # Soft fade into dark panel
        fade_w = 80
        for x_off in range(fade_w):
            alpha = int(255 * (x_off / fade_w))
            draw.line([(photo_area_w - fade_w + x_off, 0),
                       (photo_area_w - fade_w + x_off, H)],
                      fill=(bg[0], bg[1], bg[2], alpha))
    else:
        # No photo — large initials
        cx, cy = photo_area_w // 2, H // 2
        radius = 200
        draw.ellipse([cx - radius - 4, cy - radius - 4, cx + radius + 4, cy + radius + 4], fill=accent)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(30, 30, 30))
        if customer_name:
            initials = "".join(w[0].upper() for w in customer_name.split()[:2])
            fi = _load_font(True, 96)
            bbox = draw.textbbox((0, 0), initials, font=fi)
            iw, ih = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - iw // 2, cy - ih // 2 - 8), initials, fill=accent, font=fi)

    # Top accent
    draw.rectangle([0, 0, W, 5], fill=accent)

    # --- Right panel ---
    text_x = photo_area_w + 40
    text_max_w = W - text_x - 40

    # Card type headline
    first_name = customer_name.split()[0] if customer_name else ""
    card_titles = {
        "congrats": f"Congrats\n{customer_name}!" if customer_name else "Congratulations!",
        "birthday": f"Happy Birthday\n{first_name}!" if first_name else "Happy Birthday!",
        "anniversary": f"Happy Anniversary\n{first_name}!" if first_name else "Happy Anniversary!",
        "thankyou": f"Thank You\n{first_name}!" if first_name else "Thank You!",
        "thank_you": f"Thank You\n{first_name}!" if first_name else "Thank You!",
        "welcome": f"Welcome\n{first_name}!" if first_name else "Welcome!",
        "holiday": f"Happy Holidays\n{first_name}!" if first_name else "Happy Holidays!",
    }
    headline = card_titles.get(card_type, f"A Card for\n{customer_name}!" if customer_name else "You've received a card!")

    f_headline = _load_font(True, 40)
    headline_y = H // 2 - 80
    for i, line in enumerate(headline.split("\n")):
        draw.text((text_x, headline_y + i * 52), line, fill=(255, 255, 255), font=f_headline)

    # "From" line
    from_line = ""
    if salesman_name and store_name:
        from_line = f"From {salesman_name}\nat {store_name}"
    elif salesman_name:
        from_line = f"From {salesman_name}"
    elif store_name:
        from_line = f"From {store_name}"

    if from_line:
        f_from = _load_font(False, 22)
        from_y = headline_y + len(headline.split("\n")) * 52 + 20
        for i, line in enumerate(from_line.split("\n")):
            draw.text((text_x, from_y + i * 30), line, fill=(160, 160, 160), font=f_from)

    # Store logo bottom-right
    logo_img = await _fetch_image(store_logo_url, app_url) if store_logo_url else None
    if logo_img:
        lw, lh = logo_img.size
        max_logo_w, max_logo_h = 140, 50
        scale = min(max_logo_w / lw, max_logo_h / lh, 1.0)
        logo_img = logo_img.resize((int(lw * scale), int(lh * scale)), Image.LANCZOS)
        lw, lh = logo_img.size
        img.paste(logo_img.convert("RGB"), (W - lw - 30, H - lh - 25),
                  logo_img if logo_img.mode == "RGBA" else None)

    # Bottom accent
    draw.rectangle([0, H - 5, W, H], fill=accent)

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


@router.get("/og-image/{user_id}")
async def get_og_image(user_id: str):
    """Serve a personalized 1200x630 OG preview image for social sharing.

    Generated once, then stored in object storage and served from the
    in-memory LRU cache on all subsequent requests — same speed as any
    other image on the site.
    """
    db = get_db()

    # --- 1. Try serving from object storage cache ---
    user_doc = None
    try:
        user_doc = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"name": 1, "title": 1, "store_id": 1, "photo_url": 1,
             "photo_path": 1, "photo_avatar_path": 1, "email_brand_kit": 1,
             "og_image_path": 1}
        )
    except Exception:
        pass

    if not user_doc:
        static_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "og-image.png")
        if os.path.exists(static_path):
            with open(static_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png",
                                headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(status_code=404, detail="OG image not found")

    cached_path = user_doc.get("og_image_path")
    if cached_path:
        try:
            from utils.image_storage import get_object
            data, ct = get_object(cached_path)
            return Response(content=data, media_type=ct,
                            headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            # Cache miss or storage error — regenerate below
            pass

    # --- 2. Generate the image ---
    app_url = os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL", "https://app.imonsocial.com")
    app_url = app_url.rstrip("/")

    store_doc = None
    if user_doc.get("store_id"):
        try:
            store_doc = await db.stores.find_one(
                {"_id": ObjectId(user_doc["store_id"])},
                {"name": 1, "logo_url": 1, "logo_avatar_url": 1,
                 "logo_path": 1, "primary_color": 1, "email_brand_kit": 1}
            )
        except Exception:
            pass

    image_bytes = await _generate_og_image_bytes(user_doc, store_doc, app_url)

    # --- 3. Upload to object storage (fire-and-forget to not slow response) ---
    import asyncio
    async def _store_og_image():
        try:
            from utils.image_storage import put_object
            og_path = f"imos/og/{user_id}/og_preview.webp"
            await asyncio.to_thread(put_object, og_path, image_bytes, "image/webp")
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"og_image_path": og_path}}
            )
        except Exception:
            pass

    asyncio.create_task(_store_og_image())

    return Response(
        content=image_bytes,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"}
    )


@router.get("/og-card-image/{card_id}")
async def get_card_og_image(card_id: str):
    """Serve a photo-dominant 1200x630 OG image for customer card links.

    Uses the customer's photo prominently (not the full heavy card image).
    Same caching strategy as the salesperson OG image.
    """
    db = get_db()

    card_doc = await db.congrats_cards.find_one({"card_id": card_id})
    if not card_doc:
        card_doc = await db.birthday_cards.find_one({"card_id": card_id})
    if not card_doc:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check for cached version
    cached_path = card_doc.get("og_image_path")
    if cached_path:
        try:
            from utils.image_storage import get_object
            data, ct = get_object(cached_path)
            return Response(content=data, media_type=ct,
                            headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    app_url = os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL", "https://app.imonsocial.com")
    app_url = app_url.rstrip("/")

    # Get store doc for branding
    store_doc = None
    store_id = card_doc.get("store_id")
    if store_id:
        try:
            store_doc = await db.stores.find_one(
                {"_id": ObjectId(store_id)},
                {"name": 1, "logo_url": 1, "logo_avatar_url": 1,
                 "logo_path": 1, "primary_color": 1, "email_brand_kit": 1}
            )
        except Exception:
            pass

    image_bytes = await _generate_customer_og_image_bytes(card_doc, store_doc, app_url)

    # Cache in object storage (fire-and-forget)
    import asyncio
    collection_name = "congrats_cards" if await db.congrats_cards.find_one({"card_id": card_id}) else "birthday_cards"

    async def _store_card_og():
        try:
            from utils.image_storage import put_object
            og_path = f"imos/og/cards/{card_id}/og_preview.webp"
            await asyncio.to_thread(put_object, og_path, image_bytes, "image/webp")
            await db[collection_name].update_one(
                {"card_id": card_id},
                {"$set": {"og_image_path": og_path}}
            )
        except Exception:
            pass

    asyncio.create_task(_store_card_og())

    return Response(
        content=image_bytes,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"}
    )


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
    
    # ── Bot / prefetch detection ──
    ua = (request.headers.get("user-agent") or "").lower()
    bot_patterns = [
        "facebookexternalhit", "whatsapp", "telegrambot", "twitterbot",
        "linkedinbot", "slackbot", "googlebot", "bingbot", "yandex",
        "baiduspider", "duckduckbot", "applebot", "preview", "crawler",
        "spider", "bot/", "fetch/", "headless", "phantom", "prerender",
    ]
    is_bot = any(p in ua for p in bot_patterns)
    
    # ── IP-based dedup (skip counting if same IP + link within 60 seconds) ──
    client_ip = request.client.host if request.client else "unknown"
    is_duplicate = False
    if not is_bot:
        from datetime import timedelta
        recent_click = await db.short_url_clicks.find_one({
            "short_code": short_code,
            "ip": client_ip,
            "clicked_at": {"$gte": datetime.utcnow() - timedelta(seconds=60)}
        })
        is_duplicate = recent_click is not None
    
    # Only count genuine, non-duplicate human clicks
    if not is_bot and not is_duplicate:
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
            "ip": client_ip,
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
    # Detect ANY card type generically — any link_type ending in "_card" except "business_card"
    is_customer_card = "_card" in link_type and link_type != "business_card"
    ref_id = doc.get("reference_id", "")

    # If no ref_id, try to extract card_id from the original URL
    if is_customer_card and not ref_id:
        import re
        url_match = re.search(r'/([a-f0-9]{8}-[a-f0-9]{3,})', doc.get("original_url", ""))
        if url_match:
            ref_id = url_match.group(1)

    if is_customer_card and ref_id:
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

            # OG Image: use the new photo-dominant card OG image (fast WebP, cached)
            og_image = f"{base_url}/api/s/og-card-image/{ref_id}?v=2"
        else:
            # Card not found in DB, still try the card OG image endpoint
            og_image = f"{base_url}/api/s/og-card-image/{ref_id}?v=2"
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

    elif is_customer_card and user_id:
        # Card type but no ref_id found — use salesperson OG as fallback
        # (This handles test links and edge cases where card data is missing)
        personalized_og = f"{base_url}/api/s/og-image/{user_id}?v=2"
        ct = link_type.replace("_card", "")
        ct_titles = {
            "congrats": "Congratulations!", "birthday": "Happy Birthday!",
            "anniversary": "Happy Anniversary!", "thankyou": "Thank You!",
            "thank_you": "Thank You!", "welcome": "Welcome!",
            "holiday": "Happy Holidays!",
        }
        og_title = ct_titles.get(ct, "You've received a card!")
        og_description = "Open to see your special card"
        og_image = personalized_og

    elif link_type == "training_video":
        # === TRAINING VIDEO: Use YouTube thumbnail + video title ===
        import re as _re
        yt_url = doc.get("original_url", "")
        video_id = ""
        yt_match = _re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)', yt_url)
        if yt_match:
            video_id = yt_match.group(1)
        video_title = (doc.get("metadata") or {}).get("video_title", "")
        og_title = video_title or "Watch this training video"
        og_description = "Tap to watch on YouTube"
        if video_id:
            og_image = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        else:
            og_image = f"{base_url}/og-image.png"

    elif user_id:
        # === NON-CARD LINK: Use store branding ===
        try:
            user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "first_name": 1, "last_name": 1, "name": 1, "photo_url": 1})
            if user_doc and user_doc.get("store_id"):
                store = await db.stores.find_one({"_id": ObjectId(user_doc["store_id"])}, {"name": 1, "logo_url": 1, "logo_avatar_url": 1})
                if store:
                    store_name = store.get("name", "")
                    user_name = f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip() or user_doc.get("name", "")

                    # Helper to resolve a photo URL to absolute
                    def _abs(url):
                        if url and not url.startswith("data:"):
                            return f"{base_url}{url}" if url.startswith("/") else url
                        return ""

                    store_logo = _abs(store.get("logo_url") or store.get("logo_avatar_url"))

                    # Use the personalized OG image generator for personal link types
                    # ?v=2 busts iMessage's aggressive URL-level cache for old OG images
                    personalized_og = f"{base_url}/api/s/og-image/{user_id}?v=2"

                    if link_type == "business_card":
                        og_title = f"{user_name}'s Digital Card" if user_name else "Digital Business Card"
                        og_description = f"Connect with {user_name} at {store_name}" if store_name else f"Connect with {user_name}"
                        og_image = personalized_og
                    elif link_type == "referral":
                        sp_title = doc_metadata.get("salesman_title") or ""
                        if user_name and sp_title:
                            og_title = f"{user_name} — {sp_title}"
                        elif user_name:
                            og_title = f"Check out {user_name}!"
                        else:
                            og_title = "You've been referred!"
                        og_description = f"Connect with {user_name} at {store_name}" if store_name else f"Connect with {user_name}"
                        og_image = personalized_og
                    elif link_type in ("review_request", "review_invite", "review"):
                        og_title = f"Share Your Experience with {store_name}" if store_name else "We'd Love Your Feedback!"
                        og_description = f"{user_name} would love to hear about your experience" if user_name else "Your feedback means the world to us"
                        og_image = personalized_og
                    elif link_type == "showcase":
                        og_title = f"{store_name} — Happy Customers" if store_name else "Our Happy Customers"
                        og_description = f"See what customers are saying about {store_name}" if store_name else "Check out our showcase"
                        og_image = personalized_og
                    elif link_type == "link_page":
                        og_title = f"{user_name}'s Links" if user_name else "Connect With Us"
                        og_description = f"Find all of {user_name}'s links at {store_name}" if store_name else f"Find all of {user_name}'s links"
                        og_image = personalized_og
                    else:
                        og_title = store_name or "Check this out!"
                        og_description = f"Shared by {user_name}" if user_name else ""
                        og_image = personalized_og

                    # Final fallback: use store logo if no image was set
                    if not og_image:
                        og_image = store_logo
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
        elif "/og-image/" in og_image or "/og-card-image/" in og_image:
            img_w, img_h = "1200", "630"
        else:
            img_w, img_h = "800", "800"
        og_image_tags = f"""<meta property="og:image" content="{og_image}" />
<meta property="og:image:width" content="{img_w}" />
<meta property="og:image:height" content="{img_h}" />"""

    # Escape any quotes in titles/descriptions for safe HTML embedding
    safe_title = og_title.replace('"', '&quot;').replace("'", '&#39;')
    safe_desc = og_description.replace('"', '&quot;').replace("'", '&#39;')

    # JSON-LD schema for AEO (Answer Engine Optimization) — makes AI search tools
    # (ChatGPT, Perplexity, Google AI) recognize the salesperson and their business.
    # Only inject for business card and review links (person + business attribution).
    json_ld_block = ""
    if link_type in ("business_card", "review_request") or "/card/" in original_url or "/p/" in original_url:
        try:
            # Try to fetch salesperson info for schema
            sp_user = None
            sp_store = None
            if user_id:
                sp_user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "title": 1, "phone": 1, "email": 1, "seo_slug": 1, "store_id": 1})
                if sp_user and sp_user.get("store_id"):
                    sp_store = await db.stores.find_one({"_id": ObjectId(str(sp_user["store_id"]))}, {"name": 1, "phone": 1, "address": 1, "city": 1, "state": 1, "zip_code": 1})

            import json as _json
            person_schema: dict = {
                "@context": "https://schema.org",
                "@type": "Person",
                "name": (sp_user or {}).get("name", og_title.replace("'s Digital Card", "").replace("'s Business Card", "").strip()),
                "jobTitle": (sp_user or {}).get("title", ""),
                "telephone": (sp_user or {}).get("phone", ""),
                "email": (sp_user or {}).get("email", ""),
                "url": redirect_url,
                "image": og_image or "",
            }
            if sp_store:
                person_schema["worksFor"] = {
                    "@type": "AutoDealer",
                    "name": sp_store.get("name", ""),
                    "telephone": sp_store.get("phone", ""),
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": sp_store.get("address", ""),
                        "addressLocality": sp_store.get("city", ""),
                        "addressRegion": sp_store.get("state", ""),
                        "postalCode": sp_store.get("zip_code", ""),
                    }
                }
            # Remove empty fields
            person_schema = {k: v for k, v in person_schema.items() if v}
            json_ld_block = f'<script type="application/ld+json">{_json.dumps(person_schema)}</script>'
        except Exception:
            pass

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta property="og:title" content="{safe_title}" />
<meta property="og:description" content="{safe_desc}" />
{og_image_tags}
<meta property="og:url" content="{redirect_url}" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{safe_title}" />
<meta name="twitter:description" content="{safe_desc}" />
{json_ld_block}
<style>
body{{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#000;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}}
.wrap{{padding:24px}}
.logo{{font-size:22px;font-weight:700;letter-spacing:-.5px;color:#C9A962;margin-bottom:12px}}
.msg{{font-size:15px;color:#8E8E93;margin-bottom:24px}}
a.btn{{display:inline-block;padding:12px 32px;background:#C9A962;color:#000;text-decoration:none;border-radius:24px;font-weight:600;font-size:15px}}
.spinner{{width:24px;height:24px;border:3px solid #333;border-top-color:#C9A962;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
</head><body>
<div class="wrap" id="content">
<div class="spinner"></div>
<div class="logo">i'M On Social</div>
<p class="msg">Opening...</p>
</div>
<script>
window.location.replace("{redirect_url}");
setTimeout(function(){{
  document.getElementById('content').innerHTML='<div class="logo">i\\'M On Social</div><p class="msg">You can close this tab</p><a class="btn" href="{redirect_url}">Open Again</a>';
}},3000);
</script>
<noscript><meta http-equiv="refresh" content="0;url={redirect_url}" /></noscript>
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


@router.post("/wrap")
async def wrap_url(data: dict):
    """
    Universal URL wrapper — pass any URL, get back a tracked short URL.
    Auto-detects link type (YouTube → training_video, review → review_request, etc.).
    Idempotent: returns existing short URL if already wrapped.
    
    Body:
        url: The URL to wrap with tracking (required)
        user_id: ID of the user creating this link (required)
        context: Optional context string (e.g., "training", "campaign", "message")
        reference_id: Optional reference ID (lesson ID, campaign ID, etc.)
        contact_id: Optional contact ID for per-contact tracking
    
    Returns:
        short_url: The tracked URL to use
        short_code: The code portion
        original_url: The original URL
        link_type: Auto-detected type
    """
    import re

    url = (data.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    # Auto-detect link type
    if "youtube.com" in url or "youtu.be" in url:
        link_type = "training_video"
    elif "review" in url.lower():
        link_type = "review_request"
    else:
        link_type = data.get("context", "custom")

    # Extract YouTube video title for metadata if possible
    metadata = data.get("metadata") or {}
    metadata["source"] = data.get("context", "manual_wrap")
    if data.get("contact_id"):
        metadata["contact_id"] = data["contact_id"]

    result = await create_short_url(
        original_url=url,
        link_type=link_type,
        reference_id=data.get("reference_id"),
        user_id=user_id,
        metadata=metadata,
    )
    result["link_type"] = link_type
    return result


@router.post("/wrap-bulk")
async def wrap_urls_bulk(data: dict):
    """
    Bulk URL wrapper — pass multiple URLs, get back tracked short URLs.
    
    Body:
        urls: List of URLs to wrap (required)
        user_id: ID of the user (required)
        context: Optional context (e.g., "training", "campaign")
        reference_id: Optional reference ID
    
    Returns:
        results: List of {original_url, short_url, short_code, link_type}
    """
    urls = data.get("urls", [])
    user_id = data.get("user_id")
    if not urls:
        raise HTTPException(status_code=400, detail="urls list is required")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    context = data.get("context", "manual_wrap")
    reference_id = data.get("reference_id")
    results = []

    for url in urls:
        url = (url or "").strip()
        if not url:
            continue
        if "youtube.com" in url or "youtu.be" in url:
            link_type = "training_video"
        elif "review" in url.lower():
            link_type = "review_request"
        else:
            link_type = context

        result = await create_short_url(
            original_url=url,
            link_type=link_type,
            reference_id=reference_id,
            user_id=user_id,
            metadata={"source": context},
        )
        result["link_type"] = link_type
        results.append(result)

    return {"results": results, "wrapped_count": len(results)}
