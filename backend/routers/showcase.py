"""
The Showroom — Public social proof showcase page.
Displays delivery photos (congrats cards) paired with customer reviews.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timezone
import re
import logging
import base64

from routers.database import get_db

router = APIRouter(prefix="/showcase", tags=["showcase"])
logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Strip to last 10 digits for matching."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits


def name_match(a: str, b: str) -> bool:
    """Fuzzy first-name match (case-insensitive, ignores extra whitespace)."""
    if not a or not b:
        return False
    a_parts = a.strip().lower().split()
    b_parts = b.strip().lower().split()
    if not a_parts or not b_parts:
        return False
    # Match if first names are the same, or full names are the same
    return a_parts[0] == b_parts[0] or a.strip().lower() == b.strip().lower()


async def _build_showcase_entries(db, query_filter: dict, feedback_filter: dict):
    """Core logic: fetch congrats cards, match with reviews, return entries."""

    # Fetch congrats cards
    cards = await db.congrats_cards.find(query_filter).sort("created_at", -1).to_list(500)

    # Fetch approved reviews
    reviews = await db.customer_feedback.find({
        **feedback_filter,
        "approved": True,
    }).sort("created_at", -1).to_list(500)

    # Build lookup maps for reviews by normalized phone and by name
    reviews_by_phone = {}
    reviews_by_name = {}
    for r in reviews:
        phone = normalize_phone(r.get("customer_phone", ""))
        if phone:
            reviews_by_phone.setdefault(phone, []).append(r)
        name = (r.get("customer_name") or "").strip().lower()
        if name:
            reviews_by_name.setdefault(name, []).append(r)

    # Match cards with reviews
    matched_review_ids = set()
    entries = []

    for card in cards:
        if card.get("hidden"):
            continue

        entry = {
            "id": card.get("card_id", str(card["_id"])),
            "type": "delivery",
            "customer_name": card.get("customer_name", "Happy Customer"),
            "customer_photo": card.get("customer_photo"),
            "card_id": card.get("card_id"),
            "salesman_id": card.get("salesman_id"),
            "salesman_name": card.get("salesman_name"),
            "salesman_photo": card.get("salesman_photo"),
            "store_name": card.get("store_name"),
            "created_at": card.get("created_at").isoformat() if card.get("created_at") else None,
            "review": None,
        }

        # Try to match a review
        card_phone = normalize_phone(card.get("customer_phone", ""))
        card_name = (card.get("customer_name") or "").strip().lower()
        matched_review = None

        # Priority 1: phone match
        if card_phone and card_phone in reviews_by_phone:
            for r in reviews_by_phone[card_phone]:
                rid = str(r["_id"])
                if rid not in matched_review_ids:
                    matched_review = r
                    matched_review_ids.add(rid)
                    break

        # Priority 2: name match
        if not matched_review and card_name in reviews_by_name:
            for r in reviews_by_name[card_name]:
                rid = str(r["_id"])
                if rid not in matched_review_ids:
                    matched_review = r
                    matched_review_ids.add(rid)
                    break

        if matched_review:
            entry["review"] = {
                "id": str(matched_review["_id"]),
                "rating": matched_review.get("rating", 5),
                "text": matched_review.get("text_review", ""),
                "customer_name": matched_review.get("customer_name"),
                "created_at": matched_review.get("created_at").isoformat() if matched_review.get("created_at") else None,
            }

        entries.append(entry)

    # Also add unmatched reviews as standalone entries
    for r in reviews:
        rid = str(r["_id"])
        if rid not in matched_review_ids:
            entries.append({
                "id": rid,
                "type": "review_only",
                "customer_name": r.get("customer_name", "Happy Customer"),
                "customer_photo": None,
                "card_id": None,
                "salesman_id": r.get("salesperson_id"),
                "salesman_name": None,
                "salesman_photo": None,
                "store_name": None,
                "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
                "review": {
                    "id": rid,
                    "rating": r.get("rating", 5),
                    "text": r.get("text_review", ""),
                    "customer_name": r.get("customer_name"),
                    "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
                },
            })

    return entries


@router.get("/user/{user_id}")
async def get_user_showcase(user_id: str):
    """Public endpoint: Get showcase data for a salesperson."""
    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store = None
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})

    entries = await _build_showcase_entries(
        db,
        query_filter={"salesman_id": user_id},
        feedback_filter={"salesperson_id": user_id},
    )

    return {
        "salesperson": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "title": user.get("title", "Sales Professional"),
            "photo_url": user.get("photo_url"),
            "phone": user.get("phone"),
        },
        "store": {
            "name": store.get("name", "") if store else None,
            "logo_url": store.get("logo_url") if store else None,
            "primary_color": store.get("primary_color", "#C9A962") if store else "#C9A962",
        } if store else None,
        "entries": entries,
        "total_deliveries": sum(1 for e in entries if e["type"] == "delivery"),
        "total_reviews": sum(1 for e in entries if e.get("review")),
    }


@router.get("/store/{store_id}")
async def get_store_showcase(store_id: str):
    """Public endpoint: Get showcase data for an entire store."""
    db = get_db()

    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Get all users in this store
    users = await db.users.find({"store_id": store_id}, {"password": 0}).to_list(200)
    user_ids = [str(u["_id"]) for u in users]

    entries = await _build_showcase_entries(
        db,
        query_filter={"salesman_id": {"$in": user_ids}},
        feedback_filter={"$or": [
            {"salesperson_id": {"$in": user_ids}},
            {"store_id": store_id},
        ]},
    )

    return {
        "store": {
            "id": str(store["_id"]),
            "name": store.get("name", ""),
            "logo_url": store.get("logo_url"),
            "primary_color": store.get("primary_color", "#C9A962"),
        },
        "team": [{"id": str(u["_id"]), "name": u.get("name", ""), "photo_url": u.get("photo_url")} for u in users],
        "entries": entries,
        "total_deliveries": sum(1 for e in entries if e["type"] == "delivery"),
        "total_reviews": sum(1 for e in entries if e.get("review")),
    }


@router.get("/org/{org_id}")
async def get_org_showcase(org_id: str):
    """Public endpoint: Get showcase data for an entire organization."""
    db = get_db()

    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    stores = await db.stores.find({"organization_id": org_id}).to_list(100)
    store_ids = [str(s["_id"]) for s in stores]

    users = await db.users.find({"store_id": {"$in": store_ids}}, {"password": 0}).to_list(500)
    user_ids = [str(u["_id"]) for u in users]

    entries = await _build_showcase_entries(
        db,
        query_filter={"salesman_id": {"$in": user_ids}},
        feedback_filter={"$or": [
            {"salesperson_id": {"$in": user_ids}},
            {"store_id": {"$in": store_ids}},
        ]},
    )

    return {
        "organization": {
            "id": str(org["_id"]),
            "name": org.get("name", ""),
            "logo_url": org.get("logo_url"),
        },
        "stores": [{"id": str(s["_id"]), "name": s.get("name", "")} for s in stores],
        "entries": entries,
        "total_deliveries": sum(1 for e in entries if e["type"] == "delivery"),
        "total_reviews": sum(1 for e in entries if e.get("review")),
    }


@router.put("/entry/{card_id}/hide")
async def hide_showcase_entry(card_id: str):
    """Hide a congrats card from the showcase."""
    db = get_db()
    result = await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$set": {"hidden": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True, "message": "Entry hidden from showcase"}


@router.put("/entry/{card_id}/show")
async def show_showcase_entry(card_id: str):
    """Unhide a congrats card on the showcase."""
    db = get_db()
    result = await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$unset": {"hidden": ""}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True, "message": "Entry restored to showcase"}


@router.get("/manage/{user_id}")
async def get_manage_showcase(user_id: str):
    """Private endpoint: Get all entries (including hidden) for management."""
    db = get_db()

    cards = await db.congrats_cards.find(
        {"salesman_id": user_id}
    ).sort("created_at", -1).to_list(500)

    return [{
        "card_id": c.get("card_id", str(c["_id"])),
        "customer_name": c.get("customer_name"),
        "customer_phone": c.get("customer_phone"),
        "customer_photo": c.get("customer_photo"),
        "hidden": c.get("hidden", False),
        "views": c.get("views", 0),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
    } for c in cards]
