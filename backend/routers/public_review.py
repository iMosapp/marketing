"""
Public Review Page router - serves the "link tree" style review page
No authentication required - customers access this directly
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from bson import ObjectId
from datetime import datetime
from routers.database import get_db

router = APIRouter(prefix="/review", tags=["public-review"])


@router.get("/page/{store_slug}")
async def get_review_page_data(store_slug: str, sp: str = None):
    """
    Get store data for the public review page
    sp = salesperson ID (optional, for tracking)
    """
    db = get_db()
    
    # Find store by slug
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get salesperson name if provided
    salesperson_name = None
    if sp:
        try:
            user = await db.users.find_one({"_id": ObjectId(sp)})
            if user:
                salesperson_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        except:
            pass
    
    return {
        "store": {
            "id": str(store["_id"]),
            "name": store.get("name", ""),
            "logo_url": store.get("logo_url"),
            "cover_image_url": store.get("cover_image_url"),
            "primary_color": store.get("primary_color", "#007AFF"),
            "phone": store.get("phone"),
            "address": store.get("address"),
            "city": store.get("city"),
            "state": store.get("state"),
            "website": store.get("website"),
            "business_hours": store.get("business_hours", {}),
            "timezone": store.get("timezone", "America/Denver"),
        },
        "review_links": store.get("review_links", {}),
        "social_links": store.get("social_links", {}),
        "salesperson": {
            "id": sp,
            "name": salesperson_name
        } if sp else None
    }


@router.post("/submit/{store_slug}")
async def submit_feedback(store_slug: str, feedback: dict):
    """
    Submit customer feedback/review
    """
    db = get_db()
    
    # Find store
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Create feedback record
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
        "created_at": datetime.utcnow()
    }
    
    result = await db.customer_feedback.insert_one(feedback_doc)
    
    return {
        "success": True,
        "feedback_id": str(result.inserted_id),
        "message": "Thank you for your feedback!"
    }


@router.get("/feedback/{store_id}")
async def get_store_feedback(store_id: str, limit: int = 50):
    """
    Get all feedback for a store (for admin viewing)
    """
    db = get_db()
    
    feedback = await db.customer_feedback.find(
        {"store_id": store_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return [{**f, "_id": str(f["_id"])} for f in feedback]


@router.get("/check-hours/{store_slug}")
async def check_store_hours(store_slug: str):
    """
    Check if store is currently open
    Used by AI to avoid scheduling during closed hours
    """
    db = get_db()
    
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get current time in store's timezone
    import pytz
    from datetime import datetime
    
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
            "next_open": None  # Could calculate next open time
        }
    
    open_time = today_hours.get("open", "09:00")
    close_time = today_hours.get("close", "18:00")
    
    is_open = open_time <= current_time <= close_time
    
    return {
        "is_open": is_open,
        "current_time": current_time,
        "today_hours": {
            "open": open_time,
            "close": close_time
        },
        "day": day_name,
        "timezone": store.get("timezone")
    }
