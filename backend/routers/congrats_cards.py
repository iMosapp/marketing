"""
Congrats Cards Router - Creates shareable thank you/congrats cards for customers
Features:
- Store-level card templates with customizable messages
- Individual card creation with customer photo and name
- Public shareable landing page with download and social sharing
- Image generation for easy saving/sharing
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import base64
import uuid
import io
from PIL import Image, ImageDraw, ImageFont
from routers.database import get_db
from routers.short_urls import create_short_url, get_short_url_base

router = APIRouter(prefix="/congrats", tags=["congrats-cards"])


@router.get("/template/{store_id}")
async def get_store_template(store_id: str):
    """
    Get the congrats card template for a store
    """
    db = get_db()
    
    template = await db.congrats_templates.find_one({"store_id": store_id})
    
    if not template:
        # Return default template
        return {
            "exists": False,
            "template": {
                "headline": "Thank You!",
                "message": "Thank you for choosing us, {customer_name}! We truly appreciate your business and look forward to serving you again.",
                "footer_text": "Your satisfaction is our priority",
                "show_salesman": True,
                "show_store_logo": True,
                "background_color": "#1A1A1A",
                "accent_color": "#C9A962",
                "text_color": "#FFFFFF",
            }
        }
    
    return {
        "exists": True,
        "template": {
            "id": str(template["_id"]),
            "headline": template.get("headline", "Thank You!"),
            "message": template.get("message", "Thank you for choosing us, {customer_name}!"),
            "footer_text": template.get("footer_text", ""),
            "show_salesman": template.get("show_salesman", True),
            "show_store_logo": template.get("show_store_logo", True),
            "background_color": template.get("background_color", "#1A1A1A"),
            "accent_color": template.get("accent_color", "#C9A962"),
            "text_color": template.get("text_color", "#FFFFFF"),
        }
    }


@router.post("/template/{store_id}")
async def save_store_template(store_id: str, data: dict):
    """
    Save/update the congrats card template for a store
    """
    db = get_db()
    
    template_data = {
        "store_id": store_id,
        "headline": data.get("headline", "Thank You!"),
        "message": data.get("message", "Thank you for choosing us, {customer_name}!"),
        "footer_text": data.get("footer_text", ""),
        "show_salesman": data.get("show_salesman", True),
        "show_store_logo": data.get("show_store_logo", True),
        "background_color": data.get("background_color", "#1A1A1A"),
        "accent_color": data.get("accent_color", "#C9A962"),
        "text_color": data.get("text_color", "#FFFFFF"),
        "updated_at": datetime.now(timezone.utc),
    }
    
    await db.congrats_templates.update_one(
        {"store_id": store_id},
        {"$set": template_data, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    return {"success": True, "message": "Template saved"}


@router.post("/create")
async def create_congrats_card(
    salesman_id: str = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(None),
    custom_message: str = Form(None),
    photo: UploadFile = File(...)
):
    """
    Create a new congrats card
    Returns a shareable link
    """
    db = get_db()
    
    # Get salesman info
    try:
        salesman = await db.users.find_one({"_id": ObjectId(salesman_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Salesman not found")
    
    if not salesman:
        raise HTTPException(status_code=404, detail="Salesman not found")
    
    # Get store info
    store = None
    store_id = salesman.get("store_id")
    if store_id:
        store = await db.stores.find_one({"_id": ObjectId(store_id)})
    
    # Get store template
    template = None
    if store_id:
        template = await db.congrats_templates.find_one({"store_id": store_id})
    
    # Process photo
    contents = await photo.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image must be less than 10MB")
    
    base64_data = base64.b64encode(contents).decode('utf-8')
    photo_url = f"data:{photo.content_type};base64,{base64_data}"
    
    # Generate unique card ID
    card_id = str(uuid.uuid4())[:12]
    
    # Build card document
    card_doc = {
        "card_id": card_id,
        "salesman_id": salesman_id,
        "salesman_name": salesman.get("name", ""),
        "salesman_photo": salesman.get("photo_url"),
        "salesman_title": salesman.get("title", "Sales Professional"),
        "salesman_phone": salesman.get("phone"),
        "salesman_email": salesman.get("email"),
        "store_id": store_id,
        "store_name": store.get("name") if store else None,
        "store_logo": store.get("logo_url") if store else None,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_photo": photo_url,
        "custom_message": custom_message,
        # Template settings
        "headline": template.get("headline", "Thank You!") if template else "Thank You!",
        "message": template.get("message", "Thank you for choosing us, {customer_name}!") if template else "Thank you for choosing us, {customer_name}!",
        "footer_text": template.get("footer_text", "") if template else "",
        "show_salesman": template.get("show_salesman", True) if template else True,
        "show_store_logo": template.get("show_store_logo", True) if template else True,
        "background_color": template.get("background_color", "#1A1A1A") if template else "#1A1A1A",
        "accent_color": template.get("accent_color", "#C9A962") if template else "#C9A962",
        "text_color": template.get("text_color", "#FFFFFF") if template else "#FFFFFF",
        # Tracking
        "views": 0,
        "downloads": 0,
        "shares": 0,
        "created_at": datetime.now(timezone.utc),
    }
    
    await db.congrats_cards.insert_one(card_doc)
    
    # Generate short URL for the card
    base_url = get_short_url_base()
    full_card_url = f"{base_url}/congrats/{card_id}"
    
    short_url_result = await create_short_url(
        original_url=full_card_url,
        link_type="congrats_card",
        reference_id=card_id,
        user_id=salesman_id,
        metadata={"customer_name": customer_name}
    )
    
    # Update card with short URL
    await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$set": {"short_url": short_url_result["short_url"]}}
    )
    
    return {
        "success": True,
        "card_id": card_id,
        "card_url": full_card_url,
        "short_url": short_url_result["short_url"],
        "message": "Congrats card created!"
    }


@router.get("/card/{card_id}")
async def get_congrats_card(card_id: str):
    """
    Get congrats card data for the public landing page
    """
    db = get_db()
    
    card = await db.congrats_cards.find_one({"card_id": card_id})
    
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Increment view count
    await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$inc": {"views": 1}}
    )
    
    # Format the message with customer name
    message = card.get("message", "")
    if "{customer_name}" in message:
        message = message.replace("{customer_name}", card.get("customer_name", ""))
    if "{salesman_name}" in message:
        message = message.replace("{salesman_name}", card.get("salesman_name", ""))
    
    return {
        "card_id": card_id,
        "salesman_id": card.get("salesman_id"),
        "customer_name": card.get("customer_name"),
        "customer_photo": card.get("customer_photo"),
        "headline": card.get("headline", "Thank You!"),
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
            "background_color": card.get("background_color", "#1A1A1A"),
            "accent_color": card.get("accent_color", "#C9A962"),
            "text_color": card.get("text_color", "#FFFFFF"),
        },
        "created_at": card.get("created_at").isoformat() if card.get("created_at") else None,
    }


@router.post("/card/{card_id}/track")
async def track_card_action(card_id: str, data: dict):
    """
    Track downloads and shares
    """
    db = get_db()
    
    action = data.get("action")
    if action not in ["download", "share"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    field = "downloads" if action == "download" else "shares"
    
    await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$inc": {field: 1}}
    )
    
    return {"success": True}


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def draw_rounded_rectangle(draw, xy, radius, fill):
    """Draw a rounded rectangle"""
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + 2*radius, y0 + 2*radius], fill=fill)
    draw.ellipse([x1 - 2*radius, y0, x1, y0 + 2*radius], fill=fill)
    draw.ellipse([x0, y1 - 2*radius, x0 + 2*radius, y1], fill=fill)
    draw.ellipse([x1 - 2*radius, y1 - 2*radius, x1, y1], fill=fill)


def create_circular_mask(size):
    """Create a circular mask for the photo"""
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size, size], fill=255)
    return mask


@router.get("/card/{card_id}/image")
async def get_card_image(card_id: str):
    """
    Generate a downloadable image of the congrats card
    Perfect for saving and sharing on social media
    """
    db = get_db()
    
    card = await db.congrats_cards.find_one({"card_id": card_id})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Card dimensions (phone-friendly 9:16 aspect ratio)
    width = 1080
    height = 1920
    
    # Get colors
    bg_color = hex_to_rgb(card.get("background_color", "#1A1A1A"))
    accent_color = hex_to_rgb(card.get("accent_color", "#C9A962"))
    text_color = hex_to_rgb(card.get("text_color", "#FFFFFF"))
    
    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts (fall back to default if not available)
    try:
        font_headline = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_message = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_salesman = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except Exception:
        font_headline = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_message = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_salesman = ImageFont.load_default()
    
    y_offset = 120
    
    # Draw headline
    headline = card.get("headline", "Thank You!")
    bbox = draw.textbbox((0, 0), headline, font=font_headline)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, y_offset), headline, fill=accent_color, font=font_headline)
    y_offset += 120
    
    # Draw customer photo
    customer_photo_data = card.get("customer_photo", "")
    photo_size = 320
    photo_x = (width - photo_size) // 2
    
    if customer_photo_data and customer_photo_data.startswith("data:"):
        try:
            # Extract base64 data
            base64_str = customer_photo_data.split(",")[1]
            photo_bytes = base64.b64decode(base64_str)
            customer_photo = Image.open(io.BytesIO(photo_bytes))
            
            # Resize and crop to square
            customer_photo = customer_photo.convert("RGBA")
            min_dim = min(customer_photo.size)
            left = (customer_photo.width - min_dim) // 2
            top = (customer_photo.height - min_dim) // 2
            customer_photo = customer_photo.crop((left, top, left + min_dim, top + min_dim))
            customer_photo = customer_photo.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
            
            # Create circular photo
            mask = create_circular_mask(photo_size)
            
            # Draw gold ring behind photo
            ring_size = photo_size + 20
            ring_x = (width - ring_size) // 2
            draw.ellipse([ring_x, y_offset - 10, ring_x + ring_size, y_offset + ring_size - 10], 
                        fill=accent_color)
            
            # Paste photo with circular mask
            img.paste(customer_photo.convert("RGB"), (photo_x, y_offset), mask)
            
        except Exception as e:
            # Draw placeholder circle if photo fails
            draw.ellipse([photo_x, y_offset, photo_x + photo_size, y_offset + photo_size], 
                        fill=accent_color, outline=accent_color, width=8)
    else:
        # Draw placeholder circle
        draw.ellipse([photo_x, y_offset, photo_x + photo_size, y_offset + photo_size], 
                    outline=accent_color, width=8)
    
    y_offset += photo_size + 50
    
    # Draw customer name
    customer_name = card.get("customer_name", "Customer")
    bbox = draw.textbbox((0, 0), customer_name, font=font_name)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, y_offset), customer_name, fill=text_color, font=font_name)
    y_offset += 80
    
    # Draw main message
    message = card.get("message", "Thank you for choosing us!")
    if "{customer_name}" in message:
        message = message.replace("{customer_name}", customer_name)
    if "{salesman_name}" in message:
        message = message.replace("{salesman_name}", card.get("salesman_name", ""))
    
    # Word wrap message
    max_width = width - 120
    words = message.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font_message)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_message)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, y_offset), line, fill=text_color, font=font_message)
        y_offset += 50
    
    y_offset += 20
    
    # Draw custom message if present
    custom_message = card.get("custom_message")
    if custom_message:
        custom_text = f'"{custom_message}"'
        # Word wrap
        words = custom_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font_small)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_small)
            text_width = bbox[2] - bbox[0]
            # Lighter color for custom message
            light_text = tuple(min(255, c + 40) for c in text_color)
            draw.text(((width - text_width) // 2, y_offset), line, fill=light_text, font=font_small)
            y_offset += 40
        y_offset += 30
    
    # Draw divider line
    divider_width = 100
    divider_x = (width - divider_width) // 2
    draw.rounded_rectangle([divider_x, y_offset, divider_x + divider_width, y_offset + 6], 
                          radius=3, fill=accent_color)
    y_offset += 60
    
    # Draw salesman info
    if card.get("show_salesman"):
        salesman_name = card.get("salesman_name", "")
        salesman_title = card.get("salesman_title", "")
        store_name = card.get("store_name", "")
        
        if salesman_name:
            bbox = draw.textbbox((0, 0), salesman_name, font=font_salesman)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, y_offset), salesman_name, fill=text_color, font=font_salesman)
            y_offset += 45
        
        if salesman_title:
            bbox = draw.textbbox((0, 0), salesman_title, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, y_offset), salesman_title, fill=accent_color, font=font_small)
            y_offset += 40
        
        if store_name:
            bbox = draw.textbbox((0, 0), store_name, font=font_small)
            text_width = bbox[2] - bbox[0]
            gray_color = (142, 142, 147)
            draw.text(((width - text_width) // 2, y_offset), store_name, fill=gray_color, font=font_small)
            y_offset += 40
    
    # Draw footer text
    footer_text = card.get("footer_text")
    if footer_text:
        y_offset = height - 100
        bbox = draw.textbbox((0, 0), footer_text, font=font_small)
        text_width = bbox[2] - bbox[0]
        gray_color = (142, 142, 147)
        draw.text(((width - text_width) // 2, y_offset), footer_text, fill=gray_color, font=font_small)
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG', quality=95)
    img_bytes.seek(0)
    
    # Track download
    await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$inc": {"downloads": 1}}
    )
    
    # Return as inline image (not attachment) so it displays in browser and can be long-pressed
    return Response(
        content=img_bytes.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="congrats-card-{card_id}.png"',
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.get("/history/{salesman_id}")
async def get_card_history(salesman_id: str, limit: int = 20):
    """
    Get congrats card history for a salesman
    """
    db = get_db()
    
    cards = await db.congrats_cards.find(
        {"salesman_id": salesman_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return [{
        "card_id": c["card_id"],
        "customer_name": c.get("customer_name"),
        "customer_phone": c.get("customer_phone"),
        "views": c.get("views", 0),
        "downloads": c.get("downloads", 0),
        "shares": c.get("shares", 0),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
    } for c in cards]
