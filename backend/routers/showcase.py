"""
The Showroom  - Public social proof showcase page.
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


async def _build_showcase_entries(db, query_filter: dict, feedback_filter: dict, include_pending: bool = False):
    """Core logic: fetch congrats cards, match with reviews, return entries.
    If include_pending is False (default/public), only show approved entries.
    """

    # For public view, only show approved entries
    card_filter = {**query_filter}
    if not include_pending:
        card_filter["showcase_approved"] = True

    # Fetch congrats cards - exclude massive base64 photo blobs for list performance
    cards = await db.congrats_cards.find(
        card_filter,
        {"customer_photo": 0, "salesman_photo": 0}
    ).sort("created_at", -1).to_list(500)

    # Track which cards have photos AND get their optimized paths if migrated
    card_photo_map = {}  # card_id_str -> photo_url
    if cards:
        card_obj_ids = [c["_id"] for c in cards]
        # Fix: use $nin instead of duplicate $ne keys (Python dict bug)
        photo_check = await db.congrats_cards.find(
            {"_id": {"$in": card_obj_ids}, "customer_photo": {"$exists": True, "$nin": [None, ""]}},
            {"_id": 1, "card_id": 1, "photo_path": 1, "photo_thumb_path": 1}
        ).to_list(500)
        for pc in photo_check:
            cid = str(pc["_id"])
            # Use optimized WebP path if migrated, otherwise fallback to photo endpoint
            if pc.get("photo_path"):
                card_photo_map[cid] = f"/api/images/{pc['photo_path']}"
            else:
                card_photo_map[cid] = f"/api/showcase/photo/{pc.get('card_id', cid)}"

    # Fetch approved reviews (include photo_path for optimized image serving)
    reviews = await db.customer_feedback.find({
        **feedback_filter,
        "approved": True,
    }, {"photo_path": 1, "purchase_photo_url": 1, "customer_phone": 1, "customer_name": 1, "rating": 1, "text_review": 1, "created_at": 1, "salesperson_id": 1}).sort("created_at", -1).to_list(500)

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

        card_id = card.get("card_id", str(card["_id"]))
        card_obj_str = str(card["_id"])
        photo_url = card_photo_map.get(card_obj_str)

        entry = {
            "id": card_id,
            "type": "delivery",
            "customer_name": card.get("customer_name", "Happy Customer"),
            "customer_photo": photo_url,
            "card_id": card_id,
            "salesman_id": card.get("salesman_id"),
            "salesman_name": card.get("salesman_name"),
            "salesman_photo": None,
            "store_name": card.get("store_name"),
            "created_at": card.get("created_at").isoformat() if card.get("created_at") else None,
            "showcase_approved": card.get("showcase_approved", False),
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
            # Use optimized path for feedback photo if migrated
            feedback_photo = None
            if matched_review.get("photo_path"):
                feedback_photo = f"/api/images/{matched_review['photo_path']}"
            elif matched_review.get("purchase_photo_url"):
                feedback_photo = f"/api/showcase/feedback-photo/{str(matched_review['_id'])}"

            entry["review"] = {
                "id": str(matched_review["_id"]),
                "rating": matched_review.get("rating", 5),
                "text": matched_review.get("text_review", ""),
                "customer_name": matched_review.get("customer_name"),
                "photo_url": feedback_photo,
                "created_at": matched_review.get("created_at").isoformat() if matched_review.get("created_at") else None,
            }

        entries.append(entry)

    # Also add unmatched reviews as standalone entries
    for r in reviews:
        rid = str(r["_id"])
        if rid not in matched_review_ids:
            # Use optimized path for feedback photo
            fb_photo = None
            if r.get("photo_path"):
                fb_photo = f"/api/images/{r['photo_path']}"
            elif r.get("purchase_photo_url"):
                fb_photo = f"/api/showcase/feedback-photo/{rid}"

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
                    "photo_url": fb_photo,
                    "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
                },
            })

    return entries


@router.get("/user/{user_id}")
async def get_user_showcase(user_id: str, cid: str = None):
    """Public endpoint: Get showcase data for a salesperson.
    cid = contact ID (optional, for accurate tracking)
    """
    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Log view event — use cid (contact_id) directly if provided
    try:
        from utils.contact_activity import log_customer_activity
        from datetime import timedelta
        contact_id = cid

        if not contact_id:
            msg = await db.messages.find_one(
                {"user_id": user_id, "sender": "user",
                 "$or": [
                     {"content": {"$regex": f"/showcase/", "$options": "i"}},
                     {"content": {"$regex": "showcase", "$options": "i"}},
                 ]},
                {"conversation_id": 1},
                sort=[("created_at", -1)],
            )
            if msg and msg.get("conversation_id"):
                conv = await db.conversations.find_one(
                    {"_id": ObjectId(msg["conversation_id"]) if not isinstance(msg["conversation_id"], ObjectId) else msg["conversation_id"]},
                    {"contact_id": 1},
                )
                if conv and conv.get("contact_id"):
                    contact_id = str(conv["contact_id"])

        if contact_id:
            recent = await db.contact_events.find_one({
                "contact_id": contact_id,
                "event_type": "showcase_viewed",
                "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)},
            })
            if not recent:
                await log_customer_activity(
                    user_id=user_id,
                    contact_id=contact_id,
                    event_type="showcase_viewed",
                    title="Viewed Showcase",
                    description="Contact opened your showcase page",
                    icon="eye",
                    color="#C9A962",
                    category="customer_activity",
                    metadata={"user_id": user_id, "contact_id": contact_id},
                )
    except Exception as e:
        print(f"[Showcase] Failed to log view activity: {e}")

    # Resolve user photo — prefer photo_path (optimized), fall back to photo_url
    if user.get("photo_path"):
        user_photo_url = f"/api/images/{user['photo_path']}"
    elif user.get("photo_url") and not user["photo_url"].startswith("data:"):
        user_photo_url = user["photo_url"]
    else:
        user_photo_url = None

    store = None
    store_logo_url = None
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
        if store:
            if store.get("logo_path"):
                store_logo_url = f"/api/images/{store['logo_path']}"
            elif store.get("logo_url") and not store["logo_url"].startswith("data:"):
                store_logo_url = store["logo_url"]

    entries = await _build_showcase_entries(
        db,
        query_filter={"salesman_id": user_id},
        feedback_filter={"salesperson_id": user_id},
    )

    # Get user's brand kit for public page theming (user → store → org fallback)
    user_brand_kit = user.get("email_brand_kit", {})
    if not user_brand_kit and store:
        user_brand_kit = store.get("email_brand_kit", {})
    if not user_brand_kit and user.get("organization_id"):
        try:
            org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])})
            if org:
                user_brand_kit = org.get("email_brand_kit", {})
        except Exception:
            pass

    return {
        "salesperson": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "title": user.get("title", "Sales Professional"),
            "photo_url": user_photo_url,
            "phone": user.get("phone"),
        },
        "store": {
            "id": str(store["_id"]) if store else None,
            "name": store.get("name", "") if store else None,
            "logo_url": store_logo_url,
            "primary_color": store.get("primary_color", "#C9A962") if store else "#C9A962",
        } if store else None,
        "entries": entries,
        "total_deliveries": sum(1 for e in entries if e["type"] == "delivery"),
        "total_reviews": sum(1 for e in entries if e.get("review")),
        "brand_kit": {
            "page_theme": user_brand_kit.get("page_theme", "dark"),
            "primary_color": user_brand_kit.get("primary_color"),
            "accent_color": user_brand_kit.get("accent_color"),
        },
    }


@router.get("/store/{store_id}")
async def get_store_showcase(store_id: str):
    """Public endpoint: Get showcase data for an entire store."""
    db = get_db()

    # Support both ObjectId and slug lookup
    store = None
    try:
        store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"logo_url": 0})
    except Exception:
        pass
    if not store:
        store = await db.stores.find_one({"slug": store_id})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Use the actual ObjectId for queries below
    actual_store_id = str(store["_id"])

    # Use optimized logo path if migrated
    store_logo_doc = await db.stores.find_one(
        {"_id": ObjectId(actual_store_id), "logo_url": {"$exists": True, "$nin": [None, ""]}},
        {"logo_path": 1}
    )
    if store_logo_doc and store_logo_doc.get("logo_path"):
        store_logo_url = f"/api/images/{store_logo_doc['logo_path']}"
    elif store_logo_doc:
        store_logo_url = f"/api/showcase/store-logo/{actual_store_id}"
    else:
        store_logo_url = None

    # Get all users in this store
    users = await db.users.find({"store_id": actual_store_id}, {"password": 0, "photo_url": 0}).to_list(200)
    user_ids = [str(u["_id"]) for u in users]

    entries = await _build_showcase_entries(
        db,
        query_filter={"salesman_id": {"$in": user_ids}},
        feedback_filter={"$or": [
            {"salesperson_id": {"$in": user_ids}},
            {"store_id": actual_store_id},
        ]},
    )

    return {
        "store": {
            "id": str(store["_id"]),
            "name": store.get("name", ""),
            "logo_url": store_logo_url,
            "primary_color": store.get("primary_color", "#C9A962"),
        },
        "team": [{"id": str(u["_id"]), "name": u.get("name", ""), "photo_url": f"/api/showcase/user-photo/{str(u['_id'])}"} for u in users],
        "entries": entries,
        "total_deliveries": sum(1 for e in entries if e["type"] == "delivery"),
        "total_reviews": sum(1 for e in entries if e.get("review")),
        "brand_kit": {
            "page_theme": store.get("email_brand_kit", {}).get("page_theme", "dark"),
            "primary_color": store.get("email_brand_kit", {}).get("primary_color"),
            "accent_color": store.get("email_brand_kit", {}).get("accent_color"),
        },
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


@router.post("/entry/{card_id}/approve")
async def approve_showcase_entry(card_id: str):
    """Approve a congrats card to appear in the public showroom."""
    db = get_db()
    result = await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$set": {"showcase_approved": True, "approved_at": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True, "message": "Entry approved for showroom"}


@router.post("/entry/{card_id}/reject")
async def reject_showcase_entry(card_id: str):
    """Reject a congrats card from the showroom (hides it)."""
    db = get_db()
    result = await db.congrats_cards.update_one(
        {"card_id": card_id},
        {"$set": {"showcase_approved": False, "hidden": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True, "message": "Entry rejected from showroom"}


@router.get("/pending/{user_id}")
async def get_pending_showcase_entries(user_id: str):
    """Get showcase entries pending approval for a manager/admin."""
    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "role": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store_id = user.get("store_id")
    role = user.get("role", "")

    # Build query: admins/managers see all pending for their store, users see only their own
    query = {"showcase_approved": {"$ne": True}, "hidden": {"$ne": True}}
    if role in ("super_admin", "org_admin", "store_manager") and store_id:
        users_in_store = await db.users.find({"store_id": store_id}, {"_id": 1}).to_list(200)
        user_ids = [str(u["_id"]) for u in users_in_store]
        query["salesman_id"] = {"$in": user_ids}
    else:
        query["salesman_id"] = user_id

    cards = await db.congrats_cards.find(
        query,
        {"customer_photo": 0, "salesman_photo": 0}
    ).sort("created_at", -1).to_list(100)

    # Check which have photos — use optimized paths when available
    card_photo_map = {}
    if cards:
        card_obj_ids = [c["_id"] for c in cards]
        photo_check = await db.congrats_cards.find(
            {"_id": {"$in": card_obj_ids}, "customer_photo": {"$exists": True, "$nin": [None, ""]}},
            {"_id": 1, "card_id": 1, "photo_path": 1}
        ).to_list(100)
        for pc in photo_check:
            cid = str(pc["_id"])
            if pc.get("photo_path"):
                card_photo_map[cid] = f"/api/images/{pc['photo_path']}"
            else:
                card_photo_map[cid] = f"/api/showcase/photo/{pc.get('card_id', cid)}"

    return [{
        "card_id": c.get("card_id", str(c["_id"])),
        "customer_name": c.get("customer_name", "Customer"),
        "customer_phone": c.get("customer_phone"),
        "salesman_name": c.get("salesman_name"),
        "salesman_id": c.get("salesman_id"),
        "customer_photo": card_photo_map.get(str(c["_id"])),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
    } for c in cards]


@router.get("/pending-count/{user_id}")
async def get_pending_showcase_count(user_id: str):
    """Get count of pending showcase entries for badge display."""
    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "role": 1})
    if not user:
        return {"count": 0}

    store_id = user.get("store_id")
    role = user.get("role", "")

    query = {"showcase_approved": {"$ne": True}, "hidden": {"$ne": True}}
    if role in ("super_admin", "org_admin", "store_manager") and store_id:
        users_in_store = await db.users.find({"store_id": store_id}, {"_id": 1}).to_list(200)
        user_ids = [str(u["_id"]) for u in users_in_store]
        query["salesman_id"] = {"$in": user_ids}
    else:
        query["salesman_id"] = user_id

    count = await db.congrats_cards.count_documents(query)
    return {"count": count}


@router.get("/manage/{user_id}")
async def get_manage_showcase(user_id: str):
    """Private endpoint: Get all entries (including hidden) for management."""
    db = get_db()

    cards = await db.congrats_cards.find(
        {"salesman_id": user_id},
        {"customer_photo": 0, "salesman_photo": 0}
    ).sort("created_at", -1).to_list(500)

    # Resolve photos: WebP first, then photo endpoint for un-migrated, null for no-photo cards
    photo_map = {}
    if cards:
        card_ids = [c["_id"] for c in cards]
        photo_check = await db.congrats_cards.find(
            {"_id": {"$in": card_ids}, "$or": [
                {"photo_path": {"$exists": True, "$ne": None}},
                {"customer_photo": {"$exists": True, "$nin": [None, ""]}}
            ]},
            {"_id": 1, "card_id": 1, "photo_path": 1, "photo_thumb_path": 1}
        ).to_list(500)
        for pc in photo_check:
            cid = str(pc["_id"])
            if pc.get("photo_path"):
                photo_map[cid] = f"/api/images/{pc.get('photo_thumb_path') or pc['photo_path']}"
            else:
                photo_map[cid] = f"/api/showcase/photo/{pc.get('card_id', cid)}"

    return [{
        "card_id": c.get("card_id", str(c["_id"])),
        "customer_name": c.get("customer_name"),
        "customer_phone": c.get("customer_phone"),
        "customer_photo": photo_map.get(str(c["_id"])),
        "hidden": c.get("hidden", False),
        "views": c.get("views", 0),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
    } for c in cards]


@router.get("/photo/{card_id}")
async def get_showcase_photo(card_id: str):
    """Serve a congrats card customer photo — optimized with lazy migration to WebP."""
    db = get_db()

    card = await db.congrats_cards.find_one(
        {"card_id": card_id},
        {"customer_photo": 1, "photo_path": 1, "_id": 1}
    )
    if not card:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Fast path: already migrated to object storage
    if card.get("photo_path"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/api/images/{card['photo_path']}",
            status_code=301,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    photo_data = card.get("customer_photo")
    if not photo_data:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Lazy-migrate base64 → WebP in object storage
    if photo_data.startswith("data:") or len(photo_data) > 500:
        try:
            from utils.image_storage import upload_image
            result = await upload_image(photo_data, prefix="congrats", entity_id=card_id)
            if result:
                await db.congrats_cards.update_one(
                    {"_id": card["_id"]},
                    {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                        "photo_avatar_path": result["avatar_path"],
                    }}
                )
                from fastapi.responses import RedirectResponse
                return RedirectResponse(
                    url=f"/api/images/{result['original_path']}",
                    status_code=301,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
        except Exception as e:
            logger.warning(f"Lazy migration failed for card {card_id}: {e}")

    # Fallback: serve raw base64 (should rarely happen)
    if photo_data.startswith("data:"):
        parts = photo_data.split(",", 1)
        if len(parts) == 2:
            mime = parts[0].split(":")[1].split(";")[0] if ":" in parts[0] else "image/png"
            try:
                image_bytes = base64.b64decode(parts[1])
                return Response(content=image_bytes, media_type=mime, headers={
                    "Cache-Control": "public, max-age=3600",
                })
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to decode photo")

    if photo_data.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=photo_data)
    raise HTTPException(status_code=404, detail="Photo not found")


@router.get("/feedback-photo/{feedback_id}")
async def get_feedback_photo(feedback_id: str):
    """Serve a customer feedback photo — optimized with lazy migration."""
    db = get_db()

    try:
        oid = ObjectId(feedback_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid feedback ID")

    feedback = await db.customer_feedback.find_one(
        {"_id": oid},
        {"purchase_photo_url": 1, "photo_path": 1}
    )
    if not feedback:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Fast path: already migrated
    if feedback.get("photo_path"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/api/images/{feedback['photo_path']}",
            status_code=301,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    photo_data = feedback.get("purchase_photo_url")
    if not photo_data:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Lazy-migrate
    if photo_data.startswith("data:") or len(photo_data) > 500:
        try:
            from utils.image_storage import upload_image
            result = await upload_image(photo_data, prefix="feedback", entity_id=feedback_id)
            if result:
                await db.customer_feedback.update_one(
                    {"_id": oid},
                    {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                    }}
                )
                from fastapi.responses import RedirectResponse
                return RedirectResponse(
                    url=f"/api/images/{result['original_path']}",
                    status_code=301,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
        except Exception as e:
            logger.warning(f"Lazy migration failed for feedback {feedback_id}: {e}")

    if photo_data.startswith("data:"):
        parts = photo_data.split(",", 1)
        if len(parts) == 2:
            mime = parts[0].split(":")[1].split(";")[0] if ":" in parts[0] else "image/png"
            try:
                image_bytes = base64.b64decode(parts[1])
                return Response(content=image_bytes, media_type=mime, headers={
                    "Cache-Control": "public, max-age=3600",
                })
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to decode photo")
    if photo_data.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=photo_data)
    raise HTTPException(status_code=404, detail="Photo not found")


@router.get("/user-photo/{user_id}")
async def get_user_photo(user_id: str):
    """Serve a user's profile photo — optimized with lazy migration to WebP."""
    db = get_db()
    user = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"photo_url": 1, "photo_path": 1}
    )
    if not user:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Fast path: already migrated
    if user.get("photo_path"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/api/images/{user['photo_path']}",
            status_code=301,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    photo_data = user.get("photo_url")
    if not photo_data:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Lazy-migrate
    if photo_data.startswith("data:") or len(photo_data) > 500:
        try:
            from utils.image_storage import upload_image
            result = await upload_image(photo_data, prefix="profiles", entity_id=user_id)
            if result:
                await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {
                        "photo_path": result["original_path"],
                        "photo_thumb_path": result["thumbnail_path"],
                        "photo_avatar_path": result["avatar_path"],
                    }}
                )
                from fastapi.responses import RedirectResponse
                return RedirectResponse(
                    url=f"/api/images/{result['original_path']}",
                    status_code=301,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
        except Exception as e:
            logger.warning(f"Lazy migration failed for user {user_id}: {e}")

    if photo_data.startswith("data:"):
        parts = photo_data.split(",", 1)
        if len(parts) == 2:
            mime = parts[0].split(":")[1].split(";")[0] if ":" in parts[0] else "image/png"
            try:
                image_bytes = base64.b64decode(parts[1])
                return Response(content=image_bytes, media_type=mime, headers={
                    "Cache-Control": "public, max-age=3600",
                })
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to decode photo")
    if photo_data.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=photo_data)
    raise HTTPException(status_code=404, detail="Photo not found")


@router.get("/store-logo/{store_id}")
async def get_store_logo(store_id: str):
    """Serve a store's logo — optimized with lazy migration to WebP."""
    db = get_db()
    store = await db.stores.find_one(
        {"_id": ObjectId(store_id)},
        {"logo_url": 1, "logo_path": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="Logo not found")

    # Fast path: already migrated
    if store.get("logo_path"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/api/images/{store['logo_path']}",
            status_code=301,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    photo_data = store.get("logo_url")
    if not photo_data:
        raise HTTPException(status_code=404, detail="Logo not found")

    # Lazy-migrate
    if photo_data.startswith("data:") or len(photo_data) > 500:
        try:
            from utils.image_storage import upload_image
            result = await upload_image(photo_data, prefix="logos", entity_id=store_id)
            if result:
                await db.stores.update_one(
                    {"_id": ObjectId(store_id)},
                    {"$set": {
                        "logo_path": result["original_path"],
                        "logo_thumb_path": result["thumbnail_path"],
                        "logo_avatar_path": result["avatar_path"],
                    }}
                )
                from fastapi.responses import RedirectResponse
                return RedirectResponse(
                    url=f"/api/images/{result['original_path']}",
                    status_code=301,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
        except Exception as e:
            logger.warning(f"Lazy migration failed for store logo {store_id}: {e}")

    if photo_data.startswith("data:"):
        parts = photo_data.split(",", 1)
        if len(parts) == 2:
            mime = parts[0].split(":")[1].split(";")[0] if ":" in parts[0] else "image/png"
            try:
                image_bytes = base64.b64decode(parts[1])
                return Response(content=image_bytes, media_type=mime, headers={
                    "Cache-Control": "public, max-age=3600",
                })
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to decode logo")
    if photo_data.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=photo_data)
    raise HTTPException(status_code=404, detail="Logo not found")
