"""
Link Page Router — Linktree-style public profile pages for users.
Each user gets a customizable public page at /l/{username}.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
import re

from routers.database import get_db

router = APIRouter(prefix="/linkpage", tags=["linkpage"])


def sanitize_username(name: str) -> str:
    """Convert a name to a URL-safe username."""
    slug = re.sub(r'[^a-z0-9]', '', name.lower().strip())
    return slug


@router.get("/public/{username}")
async def get_public_link_page(username: str):
    """Public endpoint — returns the link page data for display."""
    db = get_db()
    username = username.lower().strip()

    page = await db.link_pages.find_one({"username": username}, {"_id": 0})
    if not page:
        # Try to find by user_id fallback
        page = await db.link_pages.find_one({"user_id": username}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Increment view count
    await db.link_pages.update_one(
        {"username": page["username"]},
        {"$inc": {"views": 1}}
    )

    return page


@router.get("/user/{user_id}")
async def get_user_link_page(user_id: str):
    """Get the link page config for a user (authenticated)."""
    db = get_db()

    page = await db.link_pages.find_one({"user_id": user_id}, {"_id": 0})
    if page:
        return page

    # Auto-create from digital card data
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store = None
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})

    # Build username from name
    name = user.get("name", "")
    base_username = sanitize_username(name) or user_id
    username = base_username

    # Ensure unique
    existing = await db.link_pages.find_one({"username": username})
    counter = 1
    while existing:
        username = f"{base_username}{counter}"
        existing = await db.link_pages.find_one({"username": username})
        counter += 1

    # Build links from digital card data
    links = []
    social_links = user.get("social_links", {})
    if not social_links and store:
        social_links = store.get("social_links", {})

    # Add social links
    social_map = {
        "instagram": {"label": "Instagram", "icon": "logo-instagram", "color": "#E4405F"},
        "facebook": {"label": "Facebook", "icon": "logo-facebook", "color": "#1877F2"},
        "tiktok": {"label": "TikTok", "icon": "logo-tiktok", "color": "#000000"},
        "linkedin": {"label": "LinkedIn", "icon": "logo-linkedin", "color": "#0A66C2"},
        "youtube": {"label": "YouTube", "icon": "logo-youtube", "color": "#FF0000"},
        "twitter": {"label": "X / Twitter", "icon": "logo-twitter", "color": "#000000"},
    }
    for key, meta in social_map.items():
        url = social_links.get(key)
        if url:
            links.append({
                "id": key,
                "label": meta["label"],
                "url": url,
                "icon": meta["icon"],
                "color": meta["color"],
                "visible": True,
            })

    # Add contact links
    if user.get("phone"):
        links.append({"id": "phone", "label": "Call Me", "url": f"tel:{user['phone']}", "icon": "call", "color": "#34C759", "visible": True})
    if user.get("email"):
        links.append({"id": "email", "label": "Email Me", "url": f"mailto:{user['email']}", "icon": "mail", "color": "#007AFF", "visible": True})

    # Add digital card link
    links.append({"id": "digital_card", "label": "My Digital Card", "url": f"/card/{user_id}", "icon": "card", "color": "#C9A962", "visible": True})

    # Add review links from store
    if store:
        review_links = store.get("review_links", {})
        if review_links.get("google"):
            links.append({"id": "google_review", "label": "Leave a Review", "url": review_links["google"], "icon": "star", "color": "#FBBC04", "visible": True})

    page_data = {
        "user_id": user_id,
        "username": username,
        "display_name": name,
        "bio": user.get("persona", {}).get("bio", "") or user.get("title", ""),
        "photo_url": user.get("photo_url", ""),
        "company": store.get("name", "") if store else "",
        "links": links,
        "custom_links": [],
        "theme": "dark",
        "accent_color": "#C9A962",
        "views": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.link_pages.insert_one({**page_data, "_id": ObjectId()})
    return page_data


@router.put("/user/{user_id}")
async def update_link_page(user_id: str, data: dict):
    """Update link page settings."""
    db = get_db()

    allowed = {"display_name", "bio", "photo_url", "links", "custom_links", "theme", "accent_color", "username"}
    update = {k: v for k, v in data.items() if k in allowed}

    if "username" in update:
        new_username = sanitize_username(update["username"])
        if not new_username:
            raise HTTPException(status_code=400, detail="Invalid username")
        existing = await db.link_pages.find_one({"username": new_username, "user_id": {"$ne": user_id}})
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        update["username"] = new_username

    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.link_pages.update_one(
        {"user_id": user_id},
        {"$set": update}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Link page not found")

    return {"status": "updated"}


@router.post("/user/{user_id}/check-username")
async def check_username(user_id: str, data: dict):
    """Check if a username is available."""
    db = get_db()
    username = sanitize_username(data.get("username", ""))
    if not username or len(username) < 3:
        return {"available": False, "reason": "Username must be at least 3 characters"}

    existing = await db.link_pages.find_one({"username": username, "user_id": {"$ne": user_id}})
    return {"available": existing is None, "username": username}


@router.post("/public/{username}/click")
async def track_link_click(username: str, data: dict):
    """Track a link click on a public page."""
    db = get_db()
    link_id = data.get("link_id", "")
    await db.link_pages.update_one(
        {"username": username.lower()},
        {"$inc": {f"clicks.{link_id}": 1}}
    )
    return {"status": "tracked"}
