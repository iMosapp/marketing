"""
Birthday Cards Router - Creates shareable birthday cards for customers
Mirrors the congrats card system with birthday-specific theming.
Auto-triggers from:
  1. Daily scheduler when contact's birthday field matches today
  2. When a "birthday" tag is applied to a contact
"""
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import base64
import uuid
import io
import re
import logging
from PIL import Image, ImageDraw, ImageFont
from routers.database import get_db
from routers.short_urls import create_short_url, get_short_url_base

router = APIRouter(prefix="/birthday", tags=["birthday-cards"])
logger = logging.getLogger(__name__)

BIRTHDAY_DEFAULTS = {
    "headline": "Happy Birthday!",
    "message": "Wishing you a wonderful birthday, {customer_name}! Thank you for being part of our family.",
    "footer_text": "From all of us",
    "background_color": "#1A1A1A",
    "accent_color": "#FF6B8A",
    "text_color": "#FFFFFF",
}


def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_circular_mask(size):
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size, size], fill=255)
    return mask


async def _get_contact_photo(db, contact) -> Optional[str]:
    """Get the best available photo for a contact."""
    # Priority: photo_thumbnail > photo_url > congrats card photo
    if contact.get("photo_thumbnail"):
        return contact["photo_thumbnail"]
    if contact.get("photo_url"):
        return contact["photo_url"]

    # Check for a congrats card photo
    user_id = contact.get("user_id")
    phone = contact.get("phone", "")
    if phone:
        normalized = re.sub(r'\D', '', phone)[-10:]
        card = await db.congrats_cards.find_one(
            {"salesman_id": user_id, "customer_phone": {"$regex": normalized}},
            sort=[("created_at", -1)],
        )
        if card and card.get("customer_photo"):
            return card["customer_photo"]

    # Check contact_photos collection
    contact_photo = await db.contact_photos.find_one({"contact_id": str(contact["_id"])})
    if contact_photo and contact_photo.get("photo_full"):
        return contact_photo["photo_full"]

    return None


async def auto_create_birthday_card(
    user_id: str,
    contact_id: str,
    custom_message: Optional[str] = None,
) -> Optional[dict]:
    """
    Auto-create a birthday card for a contact. Called by scheduler or tag trigger.
    Returns card info dict or None if creation fails.
    """
    db = get_db()

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return None

        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            return None

        # Check if we already sent a birthday card to this contact today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        existing = await db.birthday_cards.find_one({
            "salesman_id": user_id,
            "contact_id": contact_id,
            "created_at": {"$gte": today_start},
        })
        if existing:
            logger.info(f"[Birthday] Card already exists for contact {contact_id} today")
            return {"card_id": existing["card_id"], "already_exists": True}

        # Get store
        store = None
        store_id = user.get("store_id")
        if store_id:
            store = await db.stores.find_one({"_id": ObjectId(store_id)})

        # Get customer photo
        photo_url = await _get_contact_photo(db, contact)

        customer_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Friend"

        card_id = str(uuid.uuid4())[:12]

        # Get store accent color for branding consistency
        store_accent = store.get("primary_color", BIRTHDAY_DEFAULTS["accent_color"]) if store else BIRTHDAY_DEFAULTS["accent_color"]

        card_doc = {
            "card_id": card_id,
            "card_type": "birthday",
            "salesman_id": user_id,
            "contact_id": contact_id,
            "salesman_name": user.get("name", ""),
            "salesman_photo": user.get("photo_url"),
            "salesman_title": user.get("title", "Sales Professional"),
            "salesman_phone": user.get("phone"),
            "salesman_email": user.get("email"),
            "store_id": store_id,
            "store_name": store.get("name") if store else None,
            "store_logo": store.get("logo_url") if store else None,
            "customer_name": customer_name,
            "customer_phone": contact.get("phone"),
            "customer_photo": photo_url,
            "custom_message": custom_message,
            "headline": BIRTHDAY_DEFAULTS["headline"],
            "message": BIRTHDAY_DEFAULTS["message"],
            "footer_text": BIRTHDAY_DEFAULTS["footer_text"],
            "show_salesman": True,
            "show_store_logo": True,
            "background_color": BIRTHDAY_DEFAULTS["background_color"],
            "accent_color": store_accent,
            "text_color": BIRTHDAY_DEFAULTS["text_color"],
            "views": 0,
            "downloads": 0,
            "shares": 0,
            "auto_generated": True,
            "created_at": datetime.now(timezone.utc),
        }

        await db.birthday_cards.insert_one(card_doc)

        # Generate short URL
        base_url = get_short_url_base()
        full_url = f"{base_url}/birthday/{card_id}"
        short_result = await create_short_url(
            original_url=full_url,
            link_type="birthday_card",
            reference_id=card_id,
            user_id=user_id,
            metadata={"customer_name": customer_name},
        )
        await db.birthday_cards.update_one(
            {"card_id": card_id},
            {"$set": {"short_url": short_result["short_url"]}},
        )

        logger.info(f"[Birthday] Created card {card_id} for {customer_name}")
        return {
            "card_id": card_id,
            "card_url": full_url,
            "short_url": short_result["short_url"],
            "customer_name": customer_name,
        }

    except Exception as e:
        logger.error(f"[Birthday] Failed to create card: {e}")
        return None


@router.post("/create")
async def create_birthday_card(
    salesman_id: str = Form(...),
    contact_id: str = Form(...),
    custom_message: str = Form(None),
):
    """Manually create a birthday card for a contact."""
    result = await auto_create_birthday_card(salesman_id, contact_id, custom_message)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create birthday card")
    return {"success": True, **result}


@router.get("/card/{card_id}")
async def get_birthday_card(card_id: str):
    """Get birthday card data for the public landing page."""
    db = get_db()
    card = await db.birthday_cards.find_one({"card_id": card_id})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await db.birthday_cards.update_one({"card_id": card_id}, {"$inc": {"views": 1}})

    message = card.get("message", "")
    message = message.replace("{customer_name}", card.get("customer_name", ""))
    message = message.replace("{salesman_name}", card.get("salesman_name", ""))

    return {
        "card_id": card_id,
        "card_type": "birthday",
        "salesman_id": card.get("salesman_id"),
        "customer_name": card.get("customer_name"),
        "customer_photo": card.get("customer_photo"),
        "headline": card.get("headline", BIRTHDAY_DEFAULTS["headline"]),
        "message": message,
        "custom_message": card.get("custom_message"),
        "footer_text": card.get("footer_text"),
        "salesman": {
            "name": card.get("salesman_name"),
            "photo": card.get("salesman_photo"),
            "title": card.get("salesman_title"),
            "phone": card.get("salesman_phone"),
            "email": card.get("salesman_email"),
        } if card.get("show_salesman") else None,
        "store": {
            "name": card.get("store_name"),
            "logo": card.get("store_logo"),
        } if card.get("show_store_logo") and card.get("store_name") else None,
        "style": {
            "background_color": card.get("background_color", BIRTHDAY_DEFAULTS["background_color"]),
            "accent_color": card.get("accent_color", BIRTHDAY_DEFAULTS["accent_color"]),
            "text_color": card.get("text_color", BIRTHDAY_DEFAULTS["text_color"]),
        },
        "created_at": card.get("created_at").isoformat() if card.get("created_at") else None,
    }


@router.post("/card/{card_id}/track")
async def track_card_action(card_id: str, data: dict):
    db = get_db()
    action = data.get("action")
    if action not in ("download", "share"):
        raise HTTPException(status_code=400, detail="Invalid action")
    await db.birthday_cards.update_one(
        {"card_id": card_id}, {"$inc": {"downloads" if action == "download" else "shares": 1}}
    )
    return {"success": True}


@router.get("/card/{card_id}/image")
async def get_card_image(card_id: str):
    """Generate a downloadable birthday card image."""
    db = get_db()
    card = await db.birthday_cards.find_one({"card_id": card_id})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    width, height = 1080, 1920
    bg = hex_to_rgb(card.get("background_color", BIRTHDAY_DEFAULTS["background_color"]))
    accent = hex_to_rgb(card.get("accent_color", BIRTHDAY_DEFAULTS["accent_color"]))
    text_c = hex_to_rgb(card.get("text_color", BIRTHDAY_DEFAULTS["text_color"]))

    img = Image.new('RGB', (width, height), bg)
    draw = ImageDraw.Draw(img)

    try:
        fnt_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        fnt_n = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        fnt_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        fnt_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        fnt_sp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except Exception:
        fnt_h = fnt_n = fnt_m = fnt_s = fnt_sp = ImageFont.load_default()

    y = 80

    # Birthday decorative top — confetti dots
    import random
    random.seed(card_id)  # deterministic per card
    confetti_colors = [
        hex_to_rgb("#FF6B8A"), hex_to_rgb("#FFD700"), hex_to_rgb("#00CED1"),
        hex_to_rgb("#FF8C00"), hex_to_rgb("#9370DB"), hex_to_rgb("#32CD32"),
    ]
    for _ in range(30):
        cx = random.randint(40, width - 40)
        cy = random.randint(20, 100)
        r = random.randint(4, 10)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=random.choice(confetti_colors))

    y = 120

    # Headline
    headline = card.get("headline", BIRTHDAY_DEFAULTS["headline"])
    bb = draw.textbbox((0, 0), headline, font=fnt_h)
    tw = bb[2] - bb[0]
    draw.text(((width - tw) // 2, y), headline, fill=accent, font=fnt_h)
    y += 120

    # Birthday cake emoji line (decorative dots)
    cake_line = "~ ~ ~"
    bb = draw.textbbox((0, 0), cake_line, font=fnt_m)
    tw = bb[2] - bb[0]
    draw.text(((width - tw) // 2, y), cake_line, fill=accent, font=fnt_m)
    y += 60

    # Customer photo
    photo_data = card.get("customer_photo", "")
    photo_size = 320
    photo_x = (width - photo_size) // 2

    if photo_data and (photo_data.startswith("data:") or photo_data.startswith("http")):
        try:
            if photo_data.startswith("data:"):
                b64 = photo_data.split(",")[1]
                photo_bytes = base64.b64decode(b64)
            else:
                import urllib.request
                with urllib.request.urlopen(photo_data, timeout=5) as resp:
                    photo_bytes = resp.read()

            cust_img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
            d = min(cust_img.size)
            l = (cust_img.width - d) // 2
            t = (cust_img.height - d) // 2
            cust_img = cust_img.crop((l, t, l + d, t + d)).resize((photo_size, photo_size), Image.Resampling.LANCZOS)

            mask = create_circular_mask(photo_size)
            ring = photo_size + 20
            rx = (width - ring) // 2
            draw.ellipse([rx, y - 10, rx + ring, y + ring - 10], fill=accent)
            img.paste(cust_img.convert("RGB"), (photo_x, y), mask)
        except Exception:
            draw.ellipse([photo_x, y, photo_x + photo_size, y + photo_size], outline=accent, width=8)
    else:
        draw.ellipse([photo_x, y, photo_x + photo_size, y + photo_size], outline=accent, width=8)
        # Draw initials
        initials = "".join(w[0] for w in card.get("customer_name", "?").split()[:2]).upper()
        bb = draw.textbbox((0, 0), initials, font=fnt_n)
        iw, ih = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((photo_x + (photo_size - iw) // 2, y + (photo_size - ih) // 2), initials, fill=accent, font=fnt_n)

    y += photo_size + 50

    # Customer name
    name = card.get("customer_name", "Friend")
    bb = draw.textbbox((0, 0), name, font=fnt_n)
    draw.text(((width - (bb[2] - bb[0])) // 2, y), name, fill=text_c, font=fnt_n)
    y += 80

    # Message (word-wrapped)
    message = card.get("message", BIRTHDAY_DEFAULTS["message"])
    message = message.replace("{customer_name}", name).replace("{salesman_name}", card.get("salesman_name", ""))
    max_w = width - 120
    lines = []
    cur = ""
    for w in message.split():
        test = f"{cur} {w}".strip()
        if (draw.textbbox((0, 0), test, font=fnt_m)[2] - draw.textbbox((0, 0), test, font=fnt_m)[0]) <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fnt_m)
        draw.text(((width - (bb[2] - bb[0])) // 2, y), line, fill=text_c, font=fnt_m)
        y += 50
    y += 20

    # Custom message
    cm = card.get("custom_message")
    if cm:
        ct = f'"{cm}"'
        lines = []
        cur = ""
        for w in ct.split():
            test = f"{cur} {w}".strip()
            if (draw.textbbox((0, 0), test, font=fnt_s)[2] - draw.textbbox((0, 0), test, font=fnt_s)[0]) <= max_w:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        light = tuple(min(255, c + 40) for c in text_c)
        for line in lines:
            bb = draw.textbbox((0, 0), line, font=fnt_s)
            draw.text(((width - (bb[2] - bb[0])) // 2, y), line, fill=light, font=fnt_s)
            y += 40
        y += 30

    # Divider
    dw = 100
    dx = (width - dw) // 2
    draw.rounded_rectangle([dx, y, dx + dw, y + 6], radius=3, fill=accent)
    y += 60

    # Salesman info
    if card.get("show_salesman"):
        for text, font, color in [
            (card.get("salesman_name", ""), fnt_sp, text_c),
            (card.get("salesman_title", ""), fnt_s, accent),
            (card.get("store_name", ""), fnt_s, (142, 142, 147)),
        ]:
            if text:
                bb = draw.textbbox((0, 0), text, font=font)
                draw.text(((width - (bb[2] - bb[0])) // 2, y), text, fill=color, font=font)
                y += 45

    # Footer
    ft = card.get("footer_text")
    if ft:
        bb = draw.textbbox((0, 0), ft, font=fnt_s)
        draw.text(((width - (bb[2] - bb[0])) // 2, height - 100), ft, fill=(142, 142, 147), font=fnt_s)

    # Bottom confetti
    for _ in range(20):
        cx = random.randint(40, width - 40)
        cy = random.randint(height - 100, height - 20)
        r = random.randint(3, 8)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=random.choice(confetti_colors))

    buf = io.BytesIO()
    img.save(buf, format='PNG', quality=95)
    buf.seek(0)

    await db.birthday_cards.update_one({"card_id": card_id}, {"$inc": {"downloads": 1}})

    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="birthday-card-{card_id}.png"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/history/{salesman_id}")
async def get_card_history(salesman_id: str, limit: int = 50):
    db = get_db()
    cards = await db.birthday_cards.find(
        {"salesman_id": salesman_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    return [{
        "card_id": c["card_id"],
        "customer_name": c.get("customer_name"),
        "customer_phone": c.get("customer_phone"),
        "auto_generated": c.get("auto_generated", False),
        "views": c.get("views", 0),
        "shares": c.get("shares", 0),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
    } for c in cards]


@router.get("/photo/{card_id}")
async def get_birthday_photo(card_id: str):
    """Serve a birthday card customer photo as an actual image."""
    db = get_db()
    card = await db.birthday_cards.find_one({"card_id": card_id}, {"customer_photo": 1})
    if not card or not card.get("customer_photo"):
        raise HTTPException(status_code=404, detail="Photo not found")

    photo_data = card["customer_photo"]
    if photo_data.startswith("data:"):
        parts = photo_data.split(",", 1)
        if len(parts) == 2:
            header = parts[0]
            b64_data = parts[1]
            mime = header.split(":")[1].split(";")[0] if ":" in header else "image/png"
            try:
                image_bytes = base64.b64decode(b64_data)
                return Response(content=image_bytes, media_type=mime, headers={
                    "Cache-Control": "public, max-age=86400",
                })
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to decode photo")
    if photo_data.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=photo_data)
    raise HTTPException(status_code=404, detail="Photo not found")
