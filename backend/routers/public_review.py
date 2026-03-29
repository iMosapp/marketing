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


def get_safe_logo(doc, fallback_doc=None):
    """Get a logo URL that's safe for API responses.
    Prefers avatar (small) version, falls back to logo_url only if it's a real URL (not base64)."""
    for d in [doc, fallback_doc]:
        if not d:
            continue
        # Prefer small avatar version
        avatar = d.get("logo_avatar_url")
        if avatar:
            return avatar
        # Use logo_url only if it's a real URL (not huge base64)
        logo = d.get("logo_url")
        if logo and not logo.startswith("data:") or (logo and len(logo) < 500):
            return logo
    return ""


@router.get("/page/{store_slug}")
async def get_review_page_data(store_slug: str, sp: str = None, cid: str = None, self_preview: str = None):
    """
    Get store data for the public review page.
    sp = salesperson ID (optional, for tracking)
    cid = contact ID (optional, for accurate tracking — passed by short URL redirect)
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
                # Skip tracking when salesperson previews their own page — prevents
                # "Bridger Ward viewed your page" when Forest clicks his own View button
                if self_preview != "1" and cid:
                    try:
                        from utils.contact_activity import log_customer_activity
                        from datetime import timedelta
                        recent = await db.contact_events.find_one({
                            "contact_id": cid,
                            "event_type": "review_page_viewed",
                            "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)},
                        })
                        if not recent:
                            await log_customer_activity(
                                user_id=sp,
                                contact_id=cid,
                                event_type="review_page_viewed",
                                title="Viewed Review Page",
                                description="Contact opened the review page",
                                icon="eye",
                                color="#FBBC04",
                                category="customer_activity",
                                metadata={"store_slug": store_slug, "salesperson_id": sp, "contact_id": cid},
                            )
                    except Exception as e:
                        print(f"[Review] Failed to log view activity: {e}")
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

    safe_logo = get_safe_logo(store, brand_kit)

    return {
        "store": {
            "id": str(store["_id"]),
            "name": store.get("name", ""),
            "slug": store.get("slug", ""),
            "logo_url": safe_logo,
            "cover_image_url": store.get("cover_image_url") if store.get("cover_image_url") and len(store.get("cover_image_url", "")) < 500 else "",
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
            "logo_url": safe_logo,
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
    
    store = await find_store_by_slug(db, store_slug)
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
    
    # Log activity: customer clicked a review link
    if salesperson_id:
        try:
            from utils.contact_activity import log_activity_for_customer
            customer_name = data.get("customer_name")
            customer_phone = data.get("customer_phone")
            if customer_name or customer_phone:
                await log_activity_for_customer(
                    user_id=salesperson_id,
                    customer_phone=customer_phone,
                    customer_name=customer_name,
                    event_type="review_link_clicked",
                    title="Clicked Review Link",
                    description=f"Clicked {platform.replace('_', ' ').title()} review link",
                    icon="open",
                    color="#FBBC04",
                    category="customer_activity",
                    metadata={"platform": platform, "url": data.get("url", "")},
                )
        except Exception as e:
            print(f"[PublicReview] Failed to log click activity: {e}")
    
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
    
    store = await find_store_by_slug(db, store_slug)
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
        "approved": feedback.get("rating", 5) >= 4,  # Auto-approve 4+ star reviews
        "created_at": datetime.now(timezone.utc),
    }
    
    result = await db.customer_feedback.insert_one(feedback_doc)
    
    # Log activity: customer submitted feedback via review page
    salesperson_id = feedback.get("salesperson_id")
    if salesperson_id:
        try:
            from utils.contact_activity import log_activity_for_customer
            cust_name = feedback.get("customer_name", "")
            cust_phone = feedback.get("customer_phone")
            cust_rating = feedback.get("rating", 5)
            cust_text = feedback.get("text_review", "")
            await log_activity_for_customer(
                user_id=salesperson_id,
                customer_phone=cust_phone,
                customer_name=cust_name,
                event_type="review_submitted",
                title="Submitted a Review",
                description=f"{cust_name or 'Customer'} left a {cust_rating}-star review" + (f': "{cust_text[:60]}"' if cust_text else ""),
                icon="star",
                color="#FFD60A",
                category="customer_activity",
                metadata={"feedback_id": str(result.inserted_id), "rating": cust_rating, "source": feedback.get("source", "review_page")},
            )
        except Exception as e:
            print(f"[PublicReview] Failed to log review feedback activity: {e}")
    
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
    
    store = await find_store_by_slug(db, store_slug)
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
