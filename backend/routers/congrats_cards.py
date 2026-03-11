"""
Unified Cards Router - Creates shareable cards for customers
Handles ALL card types: congrats, birthday, anniversary, thankyou, welcome, holiday.
Features:
- Store-level card templates with customizable messages
- Individual card creation with customer photo and name
- Auto-creation from scheduler/tag triggers (birthday, anniversary, etc.)
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
import re
import io
import logging
from PIL import Image, ImageDraw, ImageFont
from routers.database import get_db
from routers.short_urls import create_short_url, get_short_url_base

router = APIRouter(prefix="/congrats", tags=["congrats-cards"])
logger = logging.getLogger(__name__)


def _sync_upload_bytes(image_bytes: bytes, prefix: str, entity_id: str):
    """
    Synchronous image upload from raw bytes.
    Runs in asyncio.to_thread to avoid blocking the event loop.
    """
    import gc
    from utils.image_storage import (
        _compress_image, generate_thumbnail, put_object,
        ORIGINAL_MAX_WIDTH, WEBP_QUALITY, THUMBNAIL_SIZE, AVATAR_SIZE, APP_NAME,
    )

    file_id = str(uuid.uuid4())
    base_path = f"{APP_NAME}/{prefix}/{entity_id}"

    compressed_data, compressed_ct = _compress_image(image_bytes, ORIGINAL_MAX_WIDTH, WEBP_QUALITY)
    original_path = f"{base_path}/{file_id}.webp"
    put_object(original_path, compressed_data, compressed_ct)

    thumb_data, thumb_ct, thumb_ext = generate_thumbnail(image_bytes, THUMBNAIL_SIZE)
    thumb_path = f"{base_path}/{file_id}_thumb.{thumb_ext}"
    put_object(thumb_path, thumb_data, thumb_ct)

    avatar_data, avatar_ct, avatar_ext = generate_thumbnail(image_bytes, AVATAR_SIZE)
    avatar_path = f"{base_path}/{file_id}_avatar.{avatar_ext}"
    put_object(avatar_path, avatar_data, avatar_ct)

    del compressed_data, thumb_data, avatar_data
    gc.collect()

    return {"original_path": original_path, "thumbnail_path": thumb_path, "avatar_path": avatar_path}

# ===== Card Type Defaults =====
CARD_TYPE_DEFAULTS = {
    "congrats": {
        "headline": "Congratulations!",
        "message": "Thank you for choosing us, {customer_name}! We truly appreciate your business.",
        "accent_color": "#C9A962",
        "background_color": "#1A1A1A",
        "text_color": "#FFFFFF",
    },
    "birthday": {
        "headline": "Happy Birthday!",
        "message": "Wishing you the happiest of birthdays, {customer_name}!",
        "accent_color": "#FF2D55",
        "background_color": "#1A1A1A",
        "text_color": "#FFFFFF",
    },
    "anniversary": {
        "headline": "Happy Anniversary!",
        "message": "Celebrating this special milestone with you, {customer_name}!",
        "accent_color": "#FF6B6B",
        "background_color": "#1A1A1A",
        "text_color": "#FFFFFF",
    },
    "thankyou": {
        "headline": "Thank You!",
        "message": "We truly appreciate your loyalty and trust, {customer_name}!",
        "accent_color": "#34C759",
        "background_color": "#1A1A1A",
        "text_color": "#FFFFFF",
    },
    "welcome": {
        "headline": "Welcome!",
        "message": "We're so excited to have you, {customer_name}! Welcome to the family.",
        "accent_color": "#007AFF",
        "background_color": "#1A1A1A",
        "text_color": "#FFFFFF",
    },
    "holiday": {
        "headline": "Happy Holidays!",
        "message": "Warm wishes this holiday season, {customer_name}! Thank you for being part of our family.",
        "accent_color": "#5AC8FA",
        "background_color": "#1A1A1A",
        "text_color": "#FFFFFF",
    },
}


def _get_type_defaults(card_type: str) -> dict:
    return CARD_TYPE_DEFAULTS.get(card_type, CARD_TYPE_DEFAULTS["congrats"])


async def _get_contact_photo(db, contact) -> Optional[str]:
    """Get the best available photo for a contact - returns optimized URL."""
    from utils.image_urls import resolve_contact_photo
    url = resolve_contact_photo(contact)
    if url:
        return url
    phone = contact.get("phone", "")
    if phone:
        normalized = re.sub(r'\D', '', phone)[-10:]
        card = await db.congrats_cards.find_one(
            {"salesman_id": contact.get("user_id"), "customer_phone": {"$regex": normalized}},
            sort=[("created_at", -1)],
        )
        if card:
            if card.get("photo_path"):
                return f"/api/images/{card['photo_path']}"
            if card.get("customer_photo") and card["customer_photo"].startswith("/api/images/"):
                return card["customer_photo"]
    return None


async def auto_create_card(
    user_id: str,
    contact_id: str,
    card_type: str = "birthday",
    custom_message: Optional[str] = None,
) -> Optional[dict]:
    """
    Auto-create a card for a contact. Called by scheduler or tag trigger.
    Stores in the unified congrats_cards collection.
    Returns card info dict or None if creation fails.
    """
    db = get_db()
    defaults = _get_type_defaults(card_type)

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return None

        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            return None

        # Check if we already created a card for this contact today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        existing = await db.congrats_cards.find_one({
            "salesman_id": user_id,
            "contact_id": contact_id,
            "card_type": card_type,
            "created_at": {"$gte": today_start},
        })
        if existing:
            logger.info(f"[Cards] {card_type} card already exists for contact {contact_id} today")
            return {"card_id": existing["card_id"], "already_exists": True}

        store = None
        store_id = user.get("store_id")
        if store_id:
            store = await db.stores.find_one({"_id": ObjectId(store_id)})

        photo_url = await _get_contact_photo(db, contact)
        customer_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Friend"
        card_id = str(uuid.uuid4())[:12]
        store_accent = store.get("primary_color", defaults["accent_color"]) if store else defaults["accent_color"]

        from utils.image_urls import resolve_user_photo, resolve_store_logo

        card_doc = {
            "card_id": card_id,
            "card_type": card_type,
            "salesman_id": user_id,
            "contact_id": contact_id,
            "salesman_name": user.get("name", ""),
            "salesman_photo": resolve_user_photo(user),
            "salesman_title": user.get("title", "Sales Professional"),
            "salesman_phone": user.get("phone"),
            "salesman_email": user.get("email"),
            "store_id": store_id,
            "store_name": store.get("name") if store else None,
            "store_logo": resolve_store_logo(store),
            "customer_name": customer_name,
            "customer_phone": contact.get("phone"),
            "customer_photo": photo_url,
            "custom_message": custom_message,
            "headline": defaults["headline"],
            "message": defaults["message"],
            "footer_text": "",
            "show_salesman": True,
            "show_store_logo": True,
            "background_color": defaults["background_color"],
            "accent_color": store_accent,
            "text_color": defaults["text_color"],
            "views": 0,
            "downloads": 0,
            "shares": 0,
            "auto_generated": True,
            "showcase_approved": False,
            "created_at": datetime.now(timezone.utc),
        }

        await db.congrats_cards.insert_one(card_doc)

        base_url = get_short_url_base()
        full_url = f"{base_url}/congrats/{card_id}"
        short_result = await create_short_url(
            original_url=full_url,
            link_type=f"{card_type}_card",
            reference_id=card_id,
            user_id=user_id,
            metadata={"customer_name": customer_name, "card_type": card_type},
        )
        await db.congrats_cards.update_one(
            {"card_id": card_id},
            {"$set": {"short_url": short_result["short_url"]}},
        )

        logger.info(f"[Cards] Created {card_type} card {card_id} for {customer_name}")
        return {
            "card_id": card_id,
            "card_url": full_url,
            "short_url": short_result["short_url"],
            "customer_name": customer_name,
        }

    except Exception as e:
        logger.error(f"[Cards] Failed to create {card_type} card: {e}")
        return None


@router.get("/template/{store_id}")
async def get_store_template(store_id: str, card_type: str = "congrats"):
    """Get the card template for a store by card type."""
    db = get_db()
    defaults = _get_type_defaults(card_type)

    template = await db.congrats_templates.find_one({"store_id": store_id, "card_type": card_type})

    is_fallback = False
    if not template:
        # Fall back to store-level generic template
        template = await db.congrats_templates.find_one({"store_id": store_id, "card_type": {"$exists": False}})
        if template:
            is_fallback = True

    if not template:
        return {
            "exists": False,
            "card_type": card_type,
            "template": {
                "headline": defaults["headline"],
                "message": defaults["message"],
                "footer_text": "",
                "show_salesman": True,
                "show_store_logo": True,
                "background_color": defaults["background_color"],
                "accent_color": defaults["accent_color"],
                "text_color": defaults["text_color"],
            }
        }

    return {
        "exists": True,
        "card_type": card_type,
        "template": {
            "id": str(template["_id"]),
            "headline": defaults["headline"] if is_fallback else template.get("headline", defaults["headline"]),
            "message": defaults["message"] if is_fallback else template.get("message", defaults["message"]),
            "footer_text": template.get("footer_text", ""),
            "show_salesman": template.get("show_salesman", True),
            "show_store_logo": template.get("show_store_logo", True),
            "background_color": template.get("background_color", defaults["background_color"]),
            "accent_color": defaults["accent_color"] if is_fallback else template.get("accent_color", defaults["accent_color"]),
            "text_color": template.get("text_color", defaults["text_color"]),
        }
    }


@router.get("/templates/all/{store_id}")
async def get_all_store_templates(store_id: str):
    """Get all card templates for a store (for template management UI)."""
    db = get_db()
    templates = await db.congrats_templates.find({"store_id": store_id}).to_list(50)
    template_map = {t.get("card_type", "congrats"): t for t in templates}

    result = []
    for card_type, defaults in CARD_TYPE_DEFAULTS.items():
        t = template_map.get(card_type)
        result.append({
            "card_type": card_type,
            "customized": t is not None,
            "headline": t.get("headline", defaults["headline"]) if t else defaults["headline"],
            "message": t.get("message", defaults["message"]) if t else defaults["message"],
            "accent_color": t.get("accent_color", defaults["accent_color"]) if t else defaults["accent_color"],
            "background_color": t.get("background_color", defaults["background_color"]) if t else defaults["background_color"],
            "text_color": t.get("text_color", defaults["text_color"]) if t else defaults["text_color"],
            "footer_text": t.get("footer_text", "") if t else "",
        })
    return result


@router.post("/template/{store_id}")
async def save_store_template(store_id: str, data: dict):
    """Save/update a card template for a store (by card_type)."""
    db = get_db()
    card_type = data.get("card_type", "congrats")
    defaults = _get_type_defaults(card_type)

    template_data = {
        "store_id": store_id,
        "card_type": card_type,
        "headline": data.get("headline", defaults["headline"]),
        "message": data.get("message", defaults["message"]),
        "footer_text": data.get("footer_text", ""),
        "show_salesman": data.get("show_salesman", True),
        "show_store_logo": data.get("show_store_logo", True),
        "background_color": data.get("background_color", defaults["background_color"]),
        "accent_color": data.get("accent_color", defaults["accent_color"]),
        "text_color": data.get("text_color", defaults["text_color"]),
        "updated_at": datetime.now(timezone.utc),
    }

    await db.congrats_templates.update_one(
        {"store_id": store_id, "card_type": card_type},
        {"$set": template_data, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True
    )

    return {"success": True, "message": f"{card_type} template saved"}



@router.post("/templates/backfill")
async def backfill_all_store_templates():
    """Create missing card-type templates for all existing stores."""
    db = get_db()
    stores = await db.stores.find({}, {"_id": 1}).to_list(1000)
    created = 0
    for store in stores:
        sid = str(store["_id"])
        for ctype, defaults in CARD_TYPE_DEFAULTS.items():
            exists = await db.congrats_templates.find_one({"store_id": sid, "card_type": ctype})
            if not exists:
                await db.congrats_templates.insert_one({
                    "store_id": sid,
                    "card_type": ctype,
                    "headline": defaults["headline"],
                    "message": defaults["message"],
                    "footer_text": "",
                    "show_salesman": True,
                    "show_store_logo": True,
                    "background_color": defaults["background_color"],
                    "accent_color": defaults["accent_color"],
                    "text_color": defaults["text_color"],
                    "created_at": datetime.now(timezone.utc),
                })
                created += 1
    return {"status": "success", "templates_created": created}


@router.post("/create")
async def create_congrats_card(
    salesman_id: str = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(None),
    custom_message: str = Form(None),
    card_type: str = Form("congrats"),
    tags: str = Form(None),
    skip_campaign: str = Form(None),
    photo: UploadFile = File(...)
):
    """
    Create a new congrats card
    Returns a shareable link
    Also updates the contact's avatar with the photo if contact exists
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
    
    # Get store template (type-specific, then generic fallback)
    template = None
    is_fallback_template = False
    type_defaults = _get_type_defaults(card_type)
    if store_id:
        template = await db.congrats_templates.find_one({"store_id": store_id, "card_type": card_type})
        if not template:
            template = await db.congrats_templates.find_one({"store_id": store_id, "card_type": {"$exists": False}})
            if template:
                is_fallback_template = True
    
    # Process photo — compress to WebP via image pipeline
    contents = await photo.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image must be less than 10MB")
    
    # Generate unique card ID first (needed for image path)
    card_id = str(uuid.uuid4())[:12]
    
    # Upload via optimized pipeline (run in thread to avoid blocking event loop)
    import asyncio
    try:
        img_result = await asyncio.to_thread(
            _sync_upload_bytes, contents, "congrats", card_id
        )
    except Exception as e:
        logger.warning(f"[CongratsCard] Image upload failed, using base64 fallback: {e}")
        img_result = None
    
    if img_result:
        optimized_photo_url = f"/api/images/{img_result['original_path']}"
        photo_thumb_url = f"/api/images/{img_result['thumbnail_path']}"
        photo_path = img_result["original_path"]
        photo_thumb_path = img_result["thumbnail_path"]
    else:
        # Fallback: store as base64 (should be rare)
        base64_data = base64.b64encode(contents).decode('utf-8')
        optimized_photo_url = f"data:{photo.content_type};base64,{base64_data}"
        photo_thumb_url = optimized_photo_url
        photo_path = None
        photo_thumb_path = None
    
    # Update contact's avatar if contact exists (by phone number)
    contact_updated = False
    if customer_phone:
        # Normalize phone number for matching
        normalized_phone = customer_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not normalized_phone.startswith("+"):
            normalized_phone = "+1" + normalized_phone if len(normalized_phone) == 10 else normalized_phone
        
        # Find contact by phone (try multiple formats)
        contact = await db.contacts.find_one({
            "$or": [
                {"phone": customer_phone},
                {"phone": normalized_phone},
                {"phone": {"$regex": normalized_phone[-10:] if len(normalized_phone) >= 10 else normalized_phone}}
            ],
            "user_id": salesman_id
        })
        
        if contact and not contact.get("photo_path"):
            # Use the same optimized image for the contact avatar
            if img_result:
                await db.contacts.update_one(
                    {"_id": contact["_id"]},
                    {"$set": {
                        "photo_path": img_result["original_path"],
                        "photo_thumb_path": img_result["thumbnail_path"],
                        "photo_avatar_path": img_result["avatar_path"],
                        "photo_thumbnail": photo_thumb_url,
                        "photo_url": photo_thumb_url,
                        "photo_source": card_type
                    }}
                )
            contact_updated = True
            print(f"[CongratsCard] Updated contact {contact.get('first_name', '')} {contact.get('last_name', '')} avatar from congrats card photo")
    
    from utils.image_urls import resolve_user_photo, resolve_store_logo
    
    # Build card document
    card_doc = {
        "card_id": card_id,
        "salesman_id": salesman_id,
        "salesman_name": salesman.get("name", ""),
        "salesman_photo": resolve_user_photo(salesman),
        "salesman_title": salesman.get("title", "Sales Professional"),
        "salesman_phone": salesman.get("phone"),
        "salesman_email": salesman.get("email"),
        "store_id": store_id,
        "store_name": store.get("name") if store else None,
        "store_logo": resolve_store_logo(store),
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_photo": optimized_photo_url,
        "photo_path": photo_path,
        "photo_thumb_path": photo_thumb_path,
        "custom_message": custom_message,
        "card_type": card_type,
        # Template settings - use type defaults for headline/message when using a fallback generic template
        "headline": type_defaults["headline"] if (not template or is_fallback_template) else template.get("headline", type_defaults["headline"]),
        "message": template.get("message", type_defaults["message"]) if (template and not is_fallback_template) else type_defaults["message"],
        "footer_text": template.get("footer_text", "") if template else "",
        "show_salesman": template.get("show_salesman", True) if template else True,
        "show_store_logo": template.get("show_store_logo", True) if template else True,
        "background_color": template.get("background_color", type_defaults["background_color"]) if template else type_defaults["background_color"],
        "accent_color": type_defaults["accent_color"] if (not template or is_fallback_template) else template.get("accent_color", type_defaults["accent_color"]),
        "text_color": template.get("text_color", type_defaults["text_color"]) if template else type_defaults["text_color"],
        # Tracking
        "views": 0,
        "downloads": 0,
        "shares": 0,
        "created_at": datetime.now(timezone.utc),
        "contact_photo_updated": contact_updated,
        # Showroom moderation  - requires admin/manager approval before appearing publicly
        "showcase_approved": False,
    }
    
    await db.congrats_cards.insert_one(card_doc)
    
    # Generate short URL for the card
    base_url = get_short_url_base()
    full_card_url = f"{base_url}/congrats/{card_id}"
    
    short_url_result = await create_short_url(
        original_url=full_card_url,
        link_type=f"{card_type}_card",
        reference_id=card_id,
        user_id=salesman_id,
        metadata={"customer_name": customer_name, "card_type": card_type}
    )
    
    # Update card with short URL
    await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$set": {"short_url": short_url_result["short_url"]}}
    )
    
    # Apply tags to contact if provided
    applied_tags = []
    if tags:
        import json as _json
        try:
            tag_list = _json.loads(tags) if isinstance(tags, str) else tags
        except Exception:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        if tag_list and customer_phone:
            # Find the contact
            normalized_phone = customer_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            contact = await db.contacts.find_one({
                "$or": [
                    {"phone": customer_phone},
                    {"phone": {"$regex": normalized_phone[-10:] if len(normalized_phone) >= 10 else normalized_phone}},
                ],
                "user_id": salesman_id,
            })
            
            if contact:
                contact_id = str(contact["_id"])
                for tag_name in tag_list:
                    # Add tag to contact
                    await db.contacts.update_one(
                        {"_id": contact["_id"], "tags": {"$ne": tag_name}},
                        {"$push": {"tags": tag_name}},
                    )
                    applied_tags.append(tag_name)
                
                # Trigger campaign enrollment for applied tags (unless skipped)
                should_skip = skip_campaign and skip_campaign.lower() in ("true", "1", "yes")
                if applied_tags and not should_skip:
                    from routers.tags import auto_enroll_contacts_in_campaign
                    for tag_name in applied_tags:
                        await auto_enroll_contacts_in_campaign(salesman_id, tag_name, [contact_id])
    
    # Auto-apply "Recent" tag to the contact (if contact found by phone)
    recent_tag_applied = False
    if customer_phone:
        try:
            normalized_phone = customer_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            contact = await db.contacts.find_one({
                "$or": [
                    {"phone": customer_phone},
                    {"phone": {"$regex": normalized_phone[-10:] if len(normalized_phone) >= 10 else normalized_phone}},
                ],
                "user_id": salesman_id,
            })
            if contact:
                # Ensure "Recent" tag exists for this org/user
                user_doc = await db.users.find_one({"_id": ObjectId(salesman_id)}, {"organization_id": 1})
                org_id = user_doc.get("organization_id") if user_doc else None
                if org_id:
                    existing_tag = await db.tags.find_one({"org_id": org_id, "name": "Recent"})
                else:
                    existing_tag = await db.tags.find_one({"user_id": salesman_id, "name": "Recent"})
                if not existing_tag:
                    await db.tags.insert_one({
                        "name": "Recent",
                        "color": "#5856D6",
                        "status": "approved",
                        "system_tag": True,
                        "org_id": org_id or "",
                        "user_id": salesman_id,
                        "created_at": datetime.utcnow(),
                    })

                # Apply "Recent" tag if not already present
                res = await db.contacts.update_one(
                    {"_id": contact["_id"], "tags": {"$ne": "Recent"}},
                    {
                        "$push": {"tags": "Recent"},
                        "$set": {"tag_timestamps.Recent": datetime.utcnow()},
                    },
                )
                if res.modified_count > 0:
                    recent_tag_applied = True
                    if "Recent" not in applied_tags:
                        applied_tags.append("Recent")
                else:
                    # Tag already present — refresh the timestamp
                    await db.contacts.update_one(
                        {"_id": contact["_id"]},
                        {"$set": {"tag_timestamps.Recent": datetime.utcnow()}},
                    )
        except Exception as e:
            logger.warning(f"Auto-apply 'Recent' tag failed: {e}")

    return {
        "success": True,
        "card_id": card_id,
        "card_url": full_card_url,
        "short_url": short_url_result["short_url"],
        "message": "Congrats card created!",
        "contact_photo_updated": contact_updated,
        "tags_applied": applied_tags,
        "recent_tag_auto_applied": recent_tag_applied,
    }


@router.get("/card/{card_id}")
async def get_congrats_card(card_id: str):
    """
    Get card data for the public landing page.
    Checks congrats_cards first, then falls back to legacy birthday_cards collection.
    """
    db = get_db()
    
    card = await db.congrats_cards.find_one({"card_id": card_id})
    
    # Fallback: check legacy birthday_cards collection for old cards
    if not card:
        card = await db.birthday_cards.find_one({"card_id": card_id})
        if card:
            # Track views in the legacy collection
            await db.birthday_cards.update_one({"card_id": card_id}, {"$inc": {"views": 1}})
    
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Increment view count (only for congrats_cards - legacy already incremented above)
    if await db.congrats_cards.find_one({"card_id": card_id}, {"_id": 1}):
        await db.congrats_cards.update_one(
            {"card_id": card_id},
            {"$inc": {"views": 1}}
        )
    
    # Log activity: customer viewed their card (specific to card type)
    try:
        from utils.contact_activity import log_activity_for_customer
        salesman_id = card.get("salesman_id")
        customer_phone = card.get("customer_phone")
        customer_name = card.get("customer_name")
        card_type = card.get("card_type", "congrats")
        
        # Use centralized event type resolution
        from utils.event_types import get_card_viewed_info
        viewed_info = get_card_viewed_info(card_type)
        title = viewed_info["label"]
        event_type = viewed_info["event_type"]
        
        if salesman_id:
            await log_activity_for_customer(
                user_id=salesman_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                event_type=event_type,
                title=title,
                description=f"{customer_name or 'Customer'} opened their {card_type} card",
                icon="eye",
                color="#C9A962",
                category="customer_activity",
                metadata={"card_id": card_id, "card_type": card_type, "views": card.get("views", 0) + 1},
            )
    except Exception as e:
        print(f"[CongratsCard] Failed to log card view activity: {e}")

    # Fire engagement signal for real-time notification
    try:
        from routers.engagement_signals import record_signal
        contact_id = card.get("contact_id")
        await record_signal(
            signal_type="card_viewed",
            user_id=card.get("salesman_id", ""),
            contact_id=contact_id,
            contact_name=card.get("customer_name"),
            metadata={"card_id": card_id, "card_type": card.get("card_type", "congrats")},
        )
    except Exception as e:
        logger.debug(f"Engagement signal failed: {e}")
    
    # Format the message with customer name
    message = card.get("message", "")
    if "{customer_name}" in message:
        message = message.replace("{customer_name}", card.get("customer_name", ""))
    if "{salesman_name}" in message:
        message = message.replace("{salesman_name}", card.get("salesman_name", ""))
    
    from utils.image_urls import resolve_card_photo, resolve_user_photo, resolve_store_logo
    
    # Use optimized image URLs
    card_photo = resolve_card_photo(card)
    
    # Fetch store details for website link, review URL, slug
    store_data = None
    salesman_id = card.get("salesman_id")
    if salesman_id:
        try:
            user_doc = await db.users.find_one({"_id": ObjectId(salesman_id)}, {"store_id": 1})
            if user_doc and user_doc.get("store_id"):
                try:
                    store_doc = await db.stores.find_one({"_id": ObjectId(user_doc["store_id"])})
                except Exception:
                    store_doc = None
                if store_doc:
                    review_links = store_doc.get("review_links", {})
                    store_data = {
                        "name": store_doc.get("name") or card.get("store_name"),
                        "logo": card.get("store_logo") if card.get("store_logo", "").startswith("/api/") else resolve_store_logo({"logo_path": None, "logo_url": card.get("store_logo"), "_id": card.get("store_id")}),
                        "website": store_doc.get("website", ""),
                        "google_review_url": review_links.get("google", ""),
                        "slug": store_doc.get("slug", ""),
                    }
        except Exception:
            pass
    
    if not store_data and card.get("show_store_logo") and card.get("store_name"):
        store_data = {
            "name": card.get("store_name"),
            "logo": card.get("store_logo") if card.get("store_logo", "").startswith("/api/") else resolve_store_logo({"logo_path": None, "logo_url": card.get("store_logo"), "_id": card.get("store_id")}),
            "website": "",
            "google_review_url": "",
            "slug": "",
        }

    return {
        "card_id": card_id,
        "salesman_id": card.get("salesman_id"),
        "customer_name": card.get("customer_name"),
        "customer_phone": card.get("customer_phone"),
        "customer_photo": card_photo,
        "headline": card.get("headline", "Thank You!"),
        "message": message,
        "custom_message": card.get("custom_message"),
        "footer_text": card.get("footer_text"),
        "salesman": {
            "name": card.get("salesman_name"),
            "photo": card.get("salesman_photo") if card.get("salesman_photo", "").startswith("/api/") else resolve_user_photo({"photo_path": None, "photo_url": card.get("salesman_photo"), "_id": card.get("salesman_id")}),
            "title": card.get("salesman_title"),
            "phone": card.get("salesman_phone"),
            "email": card.get("salesman_email"),
        } if card.get("show_salesman") else None,
        "store": store_data,
        "short_url": card.get("short_url", ""),
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
    Track downloads and shares (checks both collections for backward compat)
    """
    db = get_db()
    
    action = data.get("action")
    if action not in ["download", "share"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    field = "downloads" if action == "download" else "shares"
    
    # Try congrats_cards first, then legacy birthday_cards
    result = await db.congrats_cards.update_one({"card_id": card_id}, {"$inc": {field: 1}})
    if result.matched_count == 0:
        await db.birthday_cards.update_one({"card_id": card_id}, {"$inc": {field: 1}})
    
    # Log activity: customer downloaded/shared their card
    try:
        card = await db.congrats_cards.find_one({"card_id": card_id}, {"salesman_id": 1, "customer_phone": 1, "customer_name": 1, "card_type": 1})
        if not card:
            card = await db.birthday_cards.find_one({"card_id": card_id}, {"salesman_id": 1, "customer_phone": 1, "customer_name": 1, "card_type": 1})
        if card and card.get("salesman_id"):
            from utils.contact_activity import log_activity_for_customer
            action_label = "Downloaded" if action == "download" else "Shared"
            ct = card.get("card_type", "congrats")
            ct_display = ct.replace("_", " ").title()
            await log_activity_for_customer(
                user_id=card["salesman_id"],
                customer_phone=card.get("customer_phone"),
                customer_name=card.get("customer_name"),
                event_type=f"{ct}_card_{action}",
                title=f"{action_label} {ct_display} Card",
                description=f"{card.get('customer_name', 'Customer')} {action_label.lower()} their {ct} card",
                icon="download" if action == "download" else "share-social",
                color="#34C759" if action == "download" else "#007AFF",
                category="customer_activity",
                metadata={"card_id": card_id, "action": action, "card_type": ct},
            )
    except Exception as e:
        print(f"[CongratsCard] Failed to log {action} activity: {e}")

    # Fire engagement signal
    try:
        from routers.engagement_signals import record_signal
        signal_type = "card_downloaded" if action == "download" else "card_shared"
        if card and card.get("salesman_id"):
            await record_signal(
                signal_type=signal_type,
                user_id=card["salesman_id"],
                contact_id=str(card["_id"]) if card.get("contact_id") else None,
                contact_name=card.get("customer_name"),
                metadata={"card_id": card_id, "action": action},
            )
    except Exception:
        pass
    
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


def create_rounded_rect_mask(width, height, radius):
    """Create a rounded rectangle mask for the photo"""
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, width, height], radius=radius, fill=255)
    return mask


@router.get("/card/{card_id}/image")
async def get_card_image(card_id: str):
    """
    Generate a premium, social-media-ready card image with embedded tracking.
    Includes store logo, QR code with tracked short URL, and branded footer.
    1080x1350 (4:5 portrait — optimal for Instagram/Facebook).
    """
    import qrcode
    import os
    db = get_db()
    app_url = os.environ.get("APP_URL", "https://app.imonsocial.com").rstrip("/")

    card = await db.congrats_cards.find_one({"card_id": card_id})
    if not card:
        card = await db.birthday_cards.find_one({"card_id": card_id})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # ---------- dimensions & colors ----------
    W, H = 1080, 1350
    bg_hex = card.get("background_color", "#111111")
    accent_hex = card.get("accent_color", "#C9A962")
    text_hex = card.get("text_color", "#FFFFFF")
    bg = hex_to_rgb(bg_hex)
    accent = hex_to_rgb(accent_hex)
    txt = hex_to_rgb(text_hex)
    dim_txt = tuple(min(255, c + 60) for c in bg)  # subtle secondary text

    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)

    # ---------- fonts ----------
    def load_font(bold=False, size=40):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
        except Exception:
            return ImageFont.load_default()

    f_logo     = load_font(True, 22)
    f_headline = load_font(True, 58)
    f_name     = load_font(True, 44)
    f_msg      = load_font(False, 28)
    f_sender   = load_font(True, 26)
    f_title    = load_font(False, 22)
    f_url      = load_font(True, 20)
    f_footer   = load_font(False, 18)

    # ---------- accent bar at top ----------
    draw.rectangle([0, 0, W, 8], fill=accent)

    y = 40

    # ---------- store logo ----------
    store_logo_loaded = False
    store_name = card.get("store_name", "")
    salesman_id = card.get("salesman_id")

    if salesman_id:
        try:
            user_doc = await db.users.find_one({"_id": ObjectId(salesman_id)}, {"store_id": 1})
            if user_doc and user_doc.get("store_id"):
                try:
                    store_doc = await db.stores.find_one({"_id": ObjectId(user_doc["store_id"])})
                except Exception:
                    store_doc = await db.stores.find_one({"_id": user_doc["store_id"]})
                if store_doc:
                    store_name = store_doc.get("name", store_name)
                    logo_url = store_doc.get("logo_url", "")
                    if logo_url:
                        try:
                            import httpx
                            full_url = f"{app_url}{logo_url}" if logo_url.startswith("/") else logo_url
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(full_url, timeout=5)
                                if resp.status_code == 200:
                                    logo_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                                    # Scale to max 200w x 60h
                                    lw, lh = logo_img.size
                                    scale = min(200 / lw, 60 / lh, 1.0)
                                    logo_img = logo_img.resize((int(lw * scale), int(lh * scale)), Image.Resampling.LANCZOS)
                                    lw, lh = logo_img.size
                                    lx = (W - lw) // 2
                                    # Paste with alpha
                                    img.paste(logo_img, (lx, y), logo_img if logo_img.mode == 'RGBA' else None)
                                    y += lh + 12
                                    store_logo_loaded = True
                        except Exception:
                            pass
        except Exception:
            pass

    # Store name (if no logo, or always show below logo)
    if store_name:
        bbox = draw.textbbox((0, 0), store_name, font=f_logo)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), store_name, fill=dim_txt, font=f_logo)
        y += 40
    else:
        y += 20

    # ---------- thin accent line ----------
    line_w = 120
    draw.rectangle([(W - line_w) // 2, y, (W + line_w) // 2, y + 3], fill=accent)
    y += 30

    # ---------- headline ----------
    headline = card.get("headline", "Congratulations!")
    bbox = draw.textbbox((0, 0), headline, font=f_headline)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), headline, fill=accent, font=f_headline)
    y += 85

    # ---------- customer photo ----------
    customer_photo_data = card.get("customer_photo", "")
    photo_size = 320
    photo_x = (W - photo_size) // 2

    photo_loaded = False
    if customer_photo_data:
        try:
            if customer_photo_data.startswith("data:"):
                b64 = customer_photo_data.split(",")[1]
                photo_bytes = base64.b64decode(b64)
            elif customer_photo_data.startswith("/api/") or customer_photo_data.startswith("http"):
                import httpx
                full = f"{app_url}{customer_photo_data}" if customer_photo_data.startswith("/") else customer_photo_data
                async with httpx.AsyncClient() as client:
                    resp = await client.get(full, timeout=5)
                    photo_bytes = resp.content if resp.status_code == 200 else None
            else:
                photo_bytes = None

            if photo_bytes:
                cphoto = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
                mn = min(cphoto.size)
                left = (cphoto.width - mn) // 2
                top = (cphoto.height - mn) // 2
                cphoto = cphoto.crop((left, top, left + mn, top + mn))
                cphoto = cphoto.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
                corner_radius = 24
                mask = create_rounded_rect_mask(photo_size, photo_size, corner_radius)
                # accent border (rounded rectangle)
                border_w = 6
                border_size = photo_size + border_w * 2
                bx = (W - border_size) // 2
                draw.rounded_rectangle(
                    [bx, y - border_w, bx + border_size, y + border_size - border_w],
                    radius=corner_radius + 4, fill=accent
                )
                img.paste(cphoto.convert("RGB"), (photo_x, y), mask)
                photo_loaded = True
        except Exception:
            pass

    if not photo_loaded:
        # placeholder rounded rectangle
        draw.rounded_rectangle([photo_x, y, photo_x + photo_size, y + photo_size], radius=24, outline=accent, width=4)
        # initials
        cname = card.get("customer_name", "?")
        initials = "".join(w[0].upper() for w in cname.split()[:2])
        fi = load_font(True, 80)
        bbox = draw.textbbox((0, 0), initials, font=fi)
        iw, ih = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((photo_x + (photo_size - iw) // 2, y + (photo_size - ih) // 2 - 10), initials, fill=accent, font=fi)

    y += photo_size + 30

    # ---------- customer name ----------
    customer_name = card.get("customer_name", "Customer")
    bbox = draw.textbbox((0, 0), customer_name, font=f_name)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), customer_name, fill=txt, font=f_name)
    y += 60

    # ---------- message (word-wrapped) ----------
    message = card.get("message", "Thank you for choosing us!")
    message = message.replace("{customer_name}", customer_name).replace("{name}", customer_name)
    if "{salesman_name}" in message:
        message = message.replace("{salesman_name}", card.get("salesman_name", ""))

    max_tw = W - 160
    lines = []
    cur = ""
    for w in message.split():
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=f_msg)
        if bbox[2] - bbox[0] <= max_tw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lines = lines[:5]

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f_msg)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), line, fill=txt, font=f_msg)
        y += 38
    y += 15

    # ---------- accent divider ----------
    draw.rectangle([(W - 80) // 2, y, (W + 80) // 2, y + 3], fill=accent)
    y += 25

    # ---------- sender info ----------
    if card.get("show_salesman"):
        sname = card.get("salesman_name", "")
        stitle = card.get("salesman_title", "")
        if sname:
            bbox = draw.textbbox((0, 0), sname, font=f_sender)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, y), sname, fill=txt, font=f_sender)
            y += 34
        if stitle:
            bbox = draw.textbbox((0, 0), stitle, font=f_title)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, y), stitle, fill=accent, font=f_title)
            y += 30
        if store_name:
            bbox = draw.textbbox((0, 0), store_name, font=f_title)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, y), store_name, fill=dim_txt, font=f_title)
            y += 30

    # ========== TRACKING FOOTER (QR + short URL) ==========
    short_url = card.get("short_url", "")
    share_url = short_url or f"{app_url}/congrats/{card_id}"

    # Bottom section background
    footer_top = H - 180
    draw.rectangle([0, footer_top, W, H], fill=tuple(max(0, c - 15) for c in bg))
    draw.rectangle([0, footer_top, W, footer_top + 2], fill=accent)

    # QR code (left side)
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=2)
        qr.add_data(share_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#FFFFFF", back_color=bg_hex).convert("RGB")
        qr_size = 130
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        qr_x = 60
        qr_y = footer_top + 25
        img.paste(qr_img, (qr_x, qr_y))
    except Exception:
        qr_size = 0
        qr_x = 60

    # URL text (right of QR)
    url_x = qr_x + qr_size + 30 if qr_size else 60
    url_y = footer_top + 40

    # Display a clean version of the URL
    display_url = share_url.replace("https://", "").replace("http://", "")
    if len(display_url) > 40:
        display_url = display_url[:40] + "..."
    draw.text((url_x, url_y), "Scan or visit:", fill=dim_txt, font=f_footer)
    draw.text((url_x, url_y + 28), display_url, fill=accent, font=f_url)

    # Powered by
    powered = "i'M On Social"
    bbox = draw.textbbox((0, 0), powered, font=f_footer)
    tw = bbox[2] - bbox[0]
    draw.text((url_x, url_y + 65), powered, fill=dim_txt, font=f_footer)

    # Bottom accent bar
    draw.rectangle([0, H - 8, W, H], fill=accent)

    # ---------- save ----------
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG', quality=95)
    img_bytes.seek(0)

    # Track download
    result = await db.congrats_cards.update_one({"card_id": card_id}, {"$inc": {"downloads": 1}})
    if result.matched_count == 0:
        await db.birthday_cards.update_one({"card_id": card_id}, {"$inc": {"downloads": 1}})

    return Response(
        content=img_bytes.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="card-{card_id}.png"',
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.get("/history/{salesman_id}")
async def get_card_history(salesman_id: str, limit: int = 20, card_type: str = None):
    """
    Get card history for a salesman. Merges both collections for full history.
    """
    db = get_db()
    
    query = {"salesman_id": salesman_id}
    if card_type:
        query["card_type"] = card_type
    
    congrats = await db.congrats_cards.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    legacy = await db.birthday_cards.find({"salesman_id": salesman_id}).sort("created_at", -1).limit(limit).to_list(limit)
    
    all_cards = congrats + legacy
    all_cards.sort(key=lambda c: c.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    
    return [{
        "card_id": c["card_id"],
        "card_type": c.get("card_type", "congrats"),
        "customer_name": c.get("customer_name"),
        "customer_phone": c.get("customer_phone"),
        "views": c.get("views", 0),
        "downloads": c.get("downloads", 0),
        "shares": c.get("shares", 0),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
    } for c in all_cards[:limit]]
