"""
Link Page Router  - Linktree-style public profile pages for users.
Each user gets a customizable public page at /l/{username}.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
import re

from routers.database import get_db

router = APIRouter(prefix="/linkpage", tags=["linkpage"])

# All social platforms with URL prefixes  - users only enter their username
SOCIAL_PLATFORMS = [
    {"key": "facebook", "label": "Facebook", "icon": "logo-facebook", "color": "#1877F2", "prefix": "https://facebook.com/"},
    {"key": "instagram", "label": "Instagram", "icon": "logo-instagram", "color": "#E4405F", "prefix": "https://instagram.com/"},
    {"key": "linkedin", "label": "LinkedIn", "icon": "logo-linkedin", "color": "#0A66C2", "prefix": "https://linkedin.com/in/"},
    {"key": "twitter", "label": "X / Twitter", "icon": "logo-twitter", "color": "#1DA1F2", "prefix": "https://x.com/"},
    {"key": "tiktok", "label": "TikTok", "icon": "logo-tiktok", "color": "#000000", "prefix": "https://tiktok.com/@"},
    {"key": "youtube", "label": "YouTube", "icon": "logo-youtube", "color": "#FF0000", "prefix": "https://youtube.com/@"},
]


def sanitize_username(name: str) -> str:
    """Convert a name to a URL-safe username."""
    slug = re.sub(r'[^a-z0-9]', '', name.lower().strip())
    return slug


def extract_username_from_url(url: str, prefix_patterns: list[str]) -> str:
    """Extract just the username from a full social media URL."""
    if not url:
        return ""
    url = url.strip().rstrip("/")
    for pattern in prefix_patterns:
        if pattern in url.lower():
            parts = url.lower().split(pattern)
            if len(parts) > 1:
                return parts[-1].strip("/").split("?")[0].split("/")[0]
    # If it's already just a username (no URL structure), return as-is
    if "/" not in url and "." not in url:
        return url.lstrip("@")
    return url


def build_default_social_links(user_social_links: dict) -> dict:
    """Build the social_links dict with all platforms, pulling usernames from user profile."""
    result = {}
    for platform in SOCIAL_PLATFORMS:
        key = platform["key"]
        raw_value = user_social_links.get(key, "")
        # Extract username from whatever is stored (could be full URL or just username)
        username = extract_username_from_url(raw_value, [
            "facebook.com/", "instagram.com/", "linkedin.com/in/",
            "x.com/", "twitter.com/", "tiktok.com/@", "tiktok.com/",
            "youtube.com/@", "youtube.com/",
        ])
        result[key] = {"username": username, "visible": bool(username)}
    return result


@router.get("/public/{username}")
async def get_public_link_page(username: str):
    """Public endpoint  - returns the link page data for display."""
    db = get_db()
    username = username.lower().strip()

    page = await db.link_pages.find_one({"username": username}, {"_id": 0})
    if not page:
        page = await db.link_pages.find_one({"user_id": username}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Increment view count
    await db.link_pages.update_one(
        {"username": page["username"]},
        {"$inc": {"views": 1}}
    )

    # Log view event for the most recent contact who was sent this link
    try:
        user_id = page.get("user_id")
        if user_id:
            from utils.contact_activity import log_customer_activity
            from datetime import timedelta
            # Find the most recent message from this user that contained a link page URL
            msg = await db.messages.find_one(
                {"user_id": user_id, "sender": "user",
                 "$or": [
                     {"content": {"$regex": f"/l/{username}", "$options": "i"}},
                     {"content": {"$regex": "link_page_shared|linkpage", "$options": "i"}},
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
                    # Dedupe: skip if already logged in the last hour
                    recent = await db.contact_events.find_one({
                        "contact_id": contact_id,
                        "event_type": "link_page_viewed",
                        "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)},
                    })
                    if not recent:
                        await log_customer_activity(
                            user_id=user_id,
                            contact_id=contact_id,
                            event_type="link_page_viewed",
                            title="Viewed Link Page",
                            description="Contact opened your link page",
                            icon="eye",
                            color="#AF52DE",
                            category="customer_activity",
                            metadata={"username": username, "views": page.get("views", 0) + 1},
                        )
    except Exception as e:
        print(f"[LinkPage] Failed to log view activity: {e}")

    # Build full social link URLs for public display
    social_links_raw = page.get("social_links", {})
    built_social_links = []
    for platform in SOCIAL_PLATFORMS:
        key = platform["key"]
        entry = social_links_raw.get(key, {})
        uname = entry.get("username", "") if isinstance(entry, dict) else ""
        visible = entry.get("visible", True) if isinstance(entry, dict) else True
        if uname and visible:
            built_social_links.append({
                "id": key,
                "label": platform["label"],
                "url": platform["prefix"] + uname,
                "icon": platform["icon"],
                "color": platform["color"],
                "visible": True,
            })

    # Contact links (phone, email, card, review)
    contact_links = [l for l in page.get("links", []) if l.get("visible", True)]

    page["built_social_links"] = built_social_links
    page["contact_links"] = contact_links
    return page


@router.get("/user/{user_id}")
async def get_user_link_page(user_id: str):
    """Get the link page config for a user (authenticated)."""
    db = get_db()

    page = await db.link_pages.find_one({"user_id": user_id}, {"_id": 0})
    if page:
        # Ensure all platforms exist in social_links (migration for old data)
        social_links = page.get("social_links", {})
        updated = False
        for platform in SOCIAL_PLATFORMS:
            if platform["key"] not in social_links:
                social_links[platform["key"]] = {"username": "", "visible": False}
                updated = True

        # Auto-sync: if ALL social usernames are empty, re-pull from user profile
        all_empty = all(
            not entry.get("username", "") for entry in social_links.values()
            if isinstance(entry, dict)
        )
        if all_empty:
            user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
            if user:
                store = None
                if user.get("store_id"):
                    store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
                user_social = user.get("social_links", {})
                if not user_social and store:
                    user_social = store.get("social_links", {})
                if any(v for v in user_social.values()):
                    social_links = build_default_social_links(user_social)
                    updated = True

        if updated or "social_links" not in page:
            page["social_links"] = social_links
            await db.link_pages.update_one(
                {"user_id": user_id},
                {"$set": {"social_links": social_links}}
            )
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

    # Build social links from user/store profile data
    user_social = user.get("social_links", {})
    if not user_social and store:
        user_social = store.get("social_links", {})
    social_links = build_default_social_links(user_social)

    # Build contact links
    links = []
    if user.get("phone"):
        links.append({"id": "phone", "label": "Call Me", "url": f"tel:{user['phone']}", "icon": "call", "color": "#34C759", "visible": True})
    if user.get("email"):
        links.append({"id": "email", "label": "Email Me", "url": f"mailto:{user['email']}", "icon": "mail", "color": "#007AFF", "visible": True})
    links.append({"id": "digital_card", "label": "My Digital Card", "url": f"/card/{user_id}", "icon": "card", "color": "#C9A962", "visible": True})
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
        "social_links": social_links,
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

    allowed = {"display_name", "bio", "photo_url", "links", "custom_links",
               "theme", "accent_color", "username", "social_links"}
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
