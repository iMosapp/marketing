"""
Media Release / Showcase Opt-In API
Handles customer consent for featuring on showcase pages and social media.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db

router = APIRouter(prefix="/opt-in", tags=["opt-in"])
logger = logging.getLogger(__name__)


@router.get("/card/{card_id}")
async def get_opt_in_context(card_id: str):
    """Fetch card + salesperson context for the opt-in page."""
    db = get_db()

    card = await db.congrats_cards.find_one(
        {"card_id": card_id},
        {"customer_photo": 0}  # exclude blob
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    salesman_id = card.get("salesman_id")
    salesman = None
    store = None
    if salesman_id:
        user = await db.users.find_one({"_id": ObjectId(salesman_id)}, {"_id": 0, "first_name": 1, "last_name": 1, "title": 1, "photo_url": 1})
        if user:
            salesman = {
                "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                "title": user.get("title", ""),
                "photo_url": user.get("photo_url"),
            }
        store_doc = await db.stores.find_one({"_id": ObjectId(card.get("store_id"))}, {"_id": 0, "name": 1, "logo_url": 1, "primary_color": 1}) if card.get("store_id") else None
        if store_doc:
            store = {
                "name": store_doc.get("name"),
                "logo_url": store_doc.get("logo_url"),
                "primary_color": store_doc.get("primary_color", "#C9A962"),
            }

    # Check existing consent
    existing = await db.showcase_consents.find_one({"card_id": card_id}, {"_id": 0})

    has_photo = bool(card.get("customer_photo") or card.get("photo_path"))
    photo_url = f"/api/showcase/photo/{card_id}" if has_photo else None

    return {
        "card_id": card_id,
        "customer_name": card.get("customer_name", ""),
        "photo_url": photo_url,
        "salesman": salesman,
        "store": store,
        "existing_consent": {
            "showcase": existing.get("showcase", False),
            "social_media": existing.get("social_media", False),
            "include_photo": existing.get("include_photo", False),
            "submitted_at": existing.get("submitted_at"),
        } if existing else None,
    }


@router.post("/submit/{card_id}")
async def submit_consent(card_id: str, data: dict):
    """Save or update the customer's media release consent."""
    db = get_db()

    card = await db.congrats_cards.find_one({"card_id": card_id}, {"_id": 1, "salesman_id": 1, "store_id": 1, "customer_name": 1})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    showcase = data.get("showcase", False)
    social_media = data.get("social_media", False)
    include_photo = data.get("include_photo", False)
    customer_name = data.get("customer_name", card.get("customer_name", ""))

    consent_doc = {
        "card_id": card_id,
        "card_obj_id": str(card["_id"]),
        "salesman_id": card.get("salesman_id"),
        "store_id": card.get("store_id"),
        "customer_name": customer_name,
        "showcase": showcase,
        "social_media": social_media,
        "include_photo": include_photo,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "ip_address": data.get("ip_address"),
    }

    # Upsert — one consent per card
    await db.showcase_consents.update_one(
        {"card_id": card_id},
        {"$set": consent_doc},
        upsert=True,
    )

    # If customer opted into showcase, auto-approve the card for showcase display
    if showcase:
        await db.congrats_cards.update_one(
            {"card_id": card_id},
            {"$set": {
                "showcase_approved": True,
                "customer_consent": True,
                "consent_date": datetime.now(timezone.utc).isoformat(),
                "consent_social_media": social_media,
                "consent_include_photo": include_photo,
            }}
        )

    return {"status": "ok", "message": "Consent saved successfully"}
