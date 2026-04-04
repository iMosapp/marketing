"""
Public Review Page router - serves the "link tree" style review page
No authentication required - customers access this directly
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
import logging
from routers.database import get_db

router = APIRouter(prefix="/review", tags=["public-review"])
logger = logging.getLogger(__name__)


async def find_store_by_slug(db, slug: str):
    """Find a store by slug, falling back to org slug lookup."""
    store = await db.stores.find_one({"slug": slug})
    if not store:
        org = await db.organizations.find_one({"slug": slug})
        if org:
            store = await db.stores.find_one({"organization_id": str(org["_id"])})
    return store


def get_safe_logo(doc, fallback_doc=None):
    """Get the sharpest available logo URL. Priority: full logo_url → full logo_path → thumbnail → avatar."""
    for d in [doc, fallback_doc]:
        if not d:
            continue
        # 1. Full-size logo URL (best quality)
        logo = d.get("logo_url")
        if logo and not logo.startswith("data:") and len(logo) < 2000:
            return logo
        # 2. Construct URL from logo_path (full-size stored image)
        logo_path = d.get("logo_path")
        if logo_path:
            return f"/api/images/{logo_path}"
        # 3. Thumbnail (medium quality)
        thumb = d.get("logo_thumbnail_url")
        if thumb and not thumb.startswith("data:"):
            return thumb
        # 4. Avatar as last resort (smallest)
        avatar = d.get("logo_avatar_url")
        if avatar and not avatar.startswith("data:"):
            return avatar
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
    
    # Notify the salesperson immediately when someone clicks their review link
    if salesperson_id:
        try:
            customer_name = data.get("customer_name", "Someone")
            customer_phone = data.get("customer_phone")
            platform_display = platform.replace("_", " ").title()

            # Contact activity log
            from utils.contact_activity import log_activity_for_customer
            if customer_name != "Someone" or customer_phone:
                await log_activity_for_customer(
                    user_id=salesperson_id,
                    customer_phone=customer_phone,
                    customer_name=customer_name if customer_name != "Someone" else None,
                    event_type="review_link_clicked",
                    title="Clicked Your Review Link",
                    description=f"Clicked your {platform_display} review link — they may have left a review!",
                    icon="open", color="#FBBC04", category="customer_activity",
                    metadata={"platform": platform, "url": data.get("url", "")},
                )

            # Real-time notification
            await db.notifications.insert_one({
                "type": "review_click",
                "title": f"Review Link Clicked — {platform_display}",
                "message": f"{customer_name} clicked your {platform_display} review link! They may have just left you a review.",
                "user_id": salesperson_id,
                "contact_name": customer_name,
                "contact_phone": customer_phone,
                "platform": platform,
                "action_required": False,
                "read": False,
                "dismissed": False,
                "priority": "normal",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"[ReviewClick] Failed to notify salesperson {salesperson_id}: {e}")
    
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


@router.post("/submit-by-user/{salesperson_id}")
async def submit_feedback_by_user(salesperson_id: str, feedback: dict):
    """Submit feedback directly by salesperson user_id — used by digital card page
    when no store slug is available (independent users, missing slug, etc.)"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(salesperson_id)}, {"store_id": 1})
    store_id = str(user["store_id"]) if user and user.get("store_id") else ""
    # Inject salesperson_id and delegate to the main submit logic
    feedback["salesperson_id"] = salesperson_id
    feedback["source"] = "digital_card"
    
    cust_rating = feedback.get("rating", 5)
    feedback_doc = {
        "store_id": store_id,
        "customer_name": feedback.get("customer_name", "Anonymous"),
        "customer_phone": feedback.get("customer_phone"),
        "customer_email": feedback.get("customer_email"),
        "rating": cust_rating,
        "text_review": feedback.get("text_review"),
        "salesperson_id": salesperson_id,
        "salesperson_name": feedback.get("salesperson_name"),
        "source": "digital_card",
        "approved": cust_rating >= 4,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.customer_feedback.insert_one(feedback_doc)
    feedback_id = str(result.inserted_id)

    # Reuse notification logic
    cust_name = feedback.get("customer_name", "Someone")
    cust_phone = feedback.get("customer_phone")
    cust_text = feedback.get("text_review", "")
    stars = "⭐" * int(cust_rating)

    try:
        from utils.contact_activity import log_activity_for_customer
        await log_activity_for_customer(
            user_id=salesperson_id, customer_phone=cust_phone, customer_name=cust_name,
            event_type="review_submitted", title="Left You a Review",
            description=f"{cust_name} left a {cust_rating}-star review" + (f': "{cust_text[:60]}"' if cust_text else ""),
            icon="star", color="#FFD60A", category="customer_activity",
            metadata={"feedback_id": feedback_id, "rating": cust_rating, "source": "digital_card"},
        )
    except Exception as e:
        logger.warning(f"[Card] Failed to log review activity: {e}")

    try:
        contact_id = None
        if cust_phone:
            clean = "".join(c for c in cust_phone if c.isdigit())
            contact = await db.contacts.find_one({"user_id": salesperson_id, "phone": {"$regex": clean[-10:] + "$"}}, {"_id": 1})
            if contact:
                contact_id = str(contact["_id"])
        await db.notifications.insert_one({
            "type": "new_review", "title": f"{stars} New Review from {cust_name}",
            "message": cust_text[:120] if cust_text else f"{cust_name} left you a {cust_rating}-star review from your digital card!",
            "user_id": salesperson_id, "contact_id": contact_id, "contact_name": cust_name,
            "contact_phone": cust_phone, "feedback_id": feedback_id, "rating": cust_rating,
            "action_required": True, "action_label": "Send Thank You",
            "read": False, "dismissed": False, "priority": "high",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[Card] Failed to create review notification: {e}")

    return {"success": True, "feedback_id": feedback_id, "message": "Thank you for your feedback!"}


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
    feedback_id = str(result.inserted_id)
    
    # Log activity + send notification to the salesperson
    salesperson_id = feedback.get("salesperson_id")
    if salesperson_id:
        cust_name = feedback.get("customer_name", "Someone")
        cust_phone = feedback.get("customer_phone")
        cust_rating = feedback.get("rating", 5)
        cust_text = feedback.get("text_review", "")
        stars = "⭐" * int(cust_rating)
        short_text = f': "{cust_text[:80]}"' if cust_text else ""

        # 1. Log contact activity
        try:
            from utils.contact_activity import log_activity_for_customer
            await log_activity_for_customer(
                user_id=salesperson_id,
                customer_phone=cust_phone,
                customer_name=cust_name,
                event_type="review_submitted",
                title="Left You a Review",
                description=f"{cust_name} left a {cust_rating}-star review{short_text}",
                icon="star",
                color="#FFD60A",
                category="customer_activity",
                metadata={"feedback_id": feedback_id, "rating": cust_rating, "source": feedback.get("source", "review_page")},
            )
        except Exception as e:
            logger.warning(f"[PublicReview] Failed to log review activity: {e}")

        # 2. Create actionable notification so salesperson is alerted immediately
        try:
            # Find the contact by phone to get contact_id for deep link
            contact_id = None
            contact_name = cust_name
            if cust_phone:
                clean_phone = "".join(c for c in cust_phone if c.isdigit())
                contact = await db.contacts.find_one(
                    {"user_id": salesperson_id, "phone": {"$regex": clean_phone[-10:] + "$"}},
                    {"_id": 1, "first_name": 1, "last_name": 1}
                )
                if contact:
                    contact_id = str(contact["_id"])
                    contact_name = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() or cust_name

            await db.notifications.insert_one({
                "type": "new_review",
                "title": f"{stars} New Review from {contact_name}",
                "message": cust_text[:120] if cust_text else f"{contact_name} left you a {cust_rating}-star review. Tap to send a thank you!",
                "user_id": salesperson_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "contact_phone": cust_phone,
                "feedback_id": feedback_id,
                "rating": cust_rating,
                "action_required": True,
                "action_label": "Send Thank You",
                "read": False,
                "dismissed": False,
                "priority": "high",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"[PublicReview] Notification sent to salesperson {salesperson_id} for review from {cust_name}")
        except Exception as e:
            logger.warning(f"[PublicReview] Failed to create review notification: {e}")
    
    return {
        "success": True,
        "feedback_id": feedback_id,
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


@router.post("/track-click-by-user/{salesperson_id}")
async def track_review_click_by_user(salesperson_id: str, data: dict):
    """Track review link click attributed to a salesperson (no store slug needed)."""
    db = get_db()
    platform = data.get("platform", "unknown")
    now = datetime.now(timezone.utc)

    click_doc = {
        "salesperson_id": salesperson_id,
        "platform": platform,
        "url_clicked": data.get("url", ""),
        "customer_name": data.get("customer_name"),
        "customer_phone": data.get("customer_phone"),
        "source": data.get("source", "card"),
        "created_at": now,
    }
    await db.review_link_clicks.insert_one(click_doc)

    # Update salesperson click counter
    try:
        await db.users.update_one(
            {"_id": ObjectId(salesperson_id)},
            {"$inc": {f"review_clicks.{platform}": 1, "review_clicks.total": 1}}
        )
    except Exception:
        pass

    # Notify salesperson
    try:
        customer_name = data.get("customer_name", "Someone")
        platform_display = platform.replace("_", " ").title()
        await db.notifications.insert_one({
            "type": "review_click",
            "title": f"Review Link Clicked — {platform_display}",
            "message": f"{customer_name} clicked your {platform_display} review link! They may have left you a review.",
            "user_id": salesperson_id,
            "contact_name": customer_name,
            "contact_phone": data.get("customer_phone"),
            "platform": platform,
            "action_required": False,
            "read": False, "dismissed": False, "priority": "normal",
            "created_at": now.isoformat(),
        })
    except Exception as e:
        logger.warning(f"[ReviewClickUser] Notification failed: {e}")

    return {"success": True}


@router.get("/attribution/{user_id}")
async def get_review_attribution(user_id: str):
    """Get comprehensive review attribution for a salesperson — internal reviews + online click log."""
    db = get_db()
    
    # Internal reviews (all statuses)
    all_feedback = await db.customer_feedback.find(
        {"salesperson_id": user_id}
    ).sort("created_at", -1).limit(100).to_list(100)

    # Online review link clicks
    clicks = await db.review_link_clicks.find(
        {"salesperson_id": user_id}
    ).sort("created_at", -1).limit(100).to_list(100)

    def fmt(doc):
        d = {k: v for k, v in doc.items() if k != "_id"}
        d["id"] = str(doc["_id"])
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        return d

    return {
        "internal_reviews": [fmt(f) for f in all_feedback],
        "online_clicks": [fmt(c) for c in clicks],
        "summary": {
            "total_internal": len(all_feedback),
            "pending": sum(1 for f in all_feedback if not f.get("approved")),
            "approved": sum(1 for f in all_feedback if f.get("approved")),
            "total_clicks": len(clicks),
            "clicks_by_platform": {},
        }
    }


@router.patch("/reviews/{review_id}/publish")
async def update_review_publish(review_id: str, data: dict):
    """Update which pages a review is published on."""
    db = get_db()
    pages = data.get("pages", ["digital_card", "landing_page"])
    result = await db.customer_feedback.update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"approved": True, "publish_to": pages, "approved_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"success": True, "publish_to": pages}
