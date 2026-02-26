"""
Public Review Page router - serves the "link tree" style review page
No authentication required - customers access this directly
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
from routers.database import get_db

router = APIRouter(prefix="/review", tags=["public-review"])


async def find_store_by_slug(db, slug: str):
    """Find a store by slug, falling back to org slug lookup."""
    store = await db.stores.find_one({"slug": slug})
    if not store:
        org = await db.organizations.find_one({"slug": slug})
        if org:
            store = await db.stores.find_one({"organization_id": str(org["_id"])})
    return store


@router.get("/page/{store_slug}")
async def get_review_page_data(store_slug: str, sp: str = None):
    """
    Get store data for the public review page.
    sp = salesperson ID (optional, for tracking)
    """
    db = get_db()
    
    store = await find_store_by_slug(db, store_slug)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    salesperson_name = None
    if sp:
        try:
            user = await db.users.find_one({"_id": ObjectId(sp)})
            if user:
                salesperson_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('name', '')
        except Exception:
            pass
    
    # Get brand kit data (from store or organization)
    brand_kit = store.get("email_brand_kit", {})
    if not brand_kit:
        org_id = store.get("organization_id")
        if org_id:
            try:
                org = await db.organizations.find_one({"_id": ObjectId(org_id)})
                if org:
                    brand_kit = org.get("email_brand_kit", {})
            except Exception:
                pass

    return {
        "store": {
            "id": str(store["_id"]),
            "name": store.get("name", ""),
            "slug": store.get("slug", ""),
            "logo_url": store.get("logo_url") or brand_kit.get("logo_url", ""),
            "cover_image_url": store.get("cover_image_url"),
            "primary_color": brand_kit.get("primary_color") or store.get("primary_color", "#007AFF"),
            "phone": store.get("phone"),
            "address": store.get("address"),
            "city": store.get("city"),
            "state": store.get("state"),
            "website": store.get("website"),
        },
        "brand_kit": {
            "company_name": brand_kit.get("company_name", store.get("name", "")),
            "tagline": brand_kit.get("tagline", ""),
            "logo_url": brand_kit.get("logo_url", store.get("logo_url", "")),
            "primary_color": brand_kit.get("primary_color", store.get("primary_color", "#007AFF")),
        },
        "review_links": store.get("review_links", {}),
        "social_links": store.get("social_links", {}),
        "salesperson": {
            "id": sp,
            "name": salesperson_name
        } if sp else None
    }


@router.post("/track-click/{store_slug}")
async def track_review_click(store_slug: str, data: dict):
    """
    Track when a customer clicks a review link.
    Records click at both store and salesperson level.
    """
    db = get_db()
    
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store_id = str(store["_id"])
    platform = data.get("platform", "unknown")
    salesperson_id = data.get("salesperson_id")
    
    click_doc = {
        "store_id": store_id,
        "store_slug": store_slug,
        "platform": platform,
        "salesperson_id": salesperson_id,
        "url_clicked": data.get("url", ""),
        "created_at": datetime.now(timezone.utc),
    }
    
    await db.review_link_clicks.insert_one(click_doc)
    
    # Increment store-level click count
    await db.stores.update_one(
        {"_id": store["_id"]},
        {"$inc": {
            f"review_click_counts.{platform}": 1,
            "review_click_counts.total": 1,
        }}
    )
    
    # Increment salesperson-level click count if provided
    if salesperson_id:
        try:
            await db.users.update_one(
                {"_id": ObjectId(salesperson_id)},
                {"$inc": {
                    f"review_clicks.{platform}": 1,
                    "review_clicks.total": 1,
                }}
            )
        except Exception:
            pass
    
    return {"success": True}


@router.get("/click-stats/{store_id}")
async def get_click_stats(store_id: str):
    """Get review link click stats for a store (admin use)"""
    db = get_db()
    
    store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"_id": 0, "review_click_counts": 1})
    
    # Get per-salesperson stats
    pipeline = [
        {"$match": {"store_id": store_id}},
        {"$group": {
            "_id": {"salesperson_id": "$salesperson_id", "platform": "$platform"},
            "count": {"$sum": 1}
        }}
    ]
    
    agg_results = await db.review_link_clicks.aggregate(pipeline).to_list(1000)
    
    return {
        "store_totals": store.get("review_click_counts", {}) if store else {},
        "detailed": [
            {
                "salesperson_id": r["_id"]["salesperson_id"],
                "platform": r["_id"]["platform"],
                "count": r["count"]
            }
            for r in agg_results
        ]
    }


@router.post("/submit/{store_slug}")
async def submit_feedback(store_slug: str, feedback: dict):
    """Submit customer feedback/review"""
    db = get_db()
    
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    feedback_doc = {
        "store_id": str(store["_id"]),
        "customer_name": feedback.get("customer_name", "Anonymous"),
        "customer_phone": feedback.get("customer_phone"),
        "customer_email": feedback.get("customer_email"),
        "rating": feedback.get("rating", 5),
        "text_review": feedback.get("text_review"),
        "photo_consent": feedback.get("photo_consent", False),
        "photo_url": feedback.get("photo_url"),
        "review_platform_clicked": feedback.get("platform_clicked"),
        "salesperson_id": feedback.get("salesperson_id"),
        "salesperson_name": feedback.get("salesperson_name"),
        "source": feedback.get("source", "review_page"),
        "approved": False,
        "created_at": datetime.now(timezone.utc),
    }
    
    result = await db.customer_feedback.insert_one(feedback_doc)
    
    return {
        "success": True,
        "feedback_id": str(result.inserted_id),
        "message": "Thank you for your feedback!"
    }


@router.get("/feedback/{store_id}")
async def get_store_feedback(store_id: str, limit: int = 50):
    """Get all feedback for a store (for admin viewing)"""
    db = get_db()
    
    feedback = await db.customer_feedback.find(
        {"store_id": store_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return [{**f, "_id": str(f["_id"])} for f in feedback]


@router.get("/check-hours/{store_slug}")
async def check_store_hours(store_slug: str):
    """Check if store is currently open"""
    db = get_db()
    
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    import pytz
    
    tz = pytz.timezone(store.get("timezone", "America/Denver"))
    now = datetime.now(tz)
    day_name = now.strftime("%A").lower()
    current_time = now.strftime("%H:%M")
    
    hours = store.get("business_hours", {})
    today_hours = hours.get(day_name)
    
    if not today_hours:
        return {
            "is_open": False,
            "message": f"Closed on {day_name.capitalize()}",
            "next_open": None
        }
    
    open_time = today_hours.get("open", "09:00")
    close_time = today_hours.get("close", "18:00")
    
    is_open = open_time <= current_time <= close_time
    
    return {
        "is_open": is_open,
        "current_time": current_time,
        "today_hours": {"open": open_time, "close": close_time},
        "day": day_name,
        "timezone": store.get("timezone")
    }
