"""
Public Landing Page router - serves the salesperson's digital business card landing page
This is the public-facing page that anyone can access via QR code or direct link.
Includes: Profile, social links, reviews, leave a review, refer a friend
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import base64
import os
from routers.database import get_db

router = APIRouter(prefix="/p", tags=["public-landing"])


@router.get("/data/{user_id}")
async def get_landing_page_data(user_id: str):
    """
    Get all data needed for the public landing page
    """
    db = get_db()
    
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"password": 0}  # Exclude password
        )
    except:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's store info
    store = None
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
    
    # Get APPROVED testimonials/reviews for this salesperson
    testimonials = await db.customer_feedback.find({
        "salesperson_id": user_id,
        "approved": True,
        "rating": {"$gte": 4}
    }).sort("created_at", -1).limit(10).to_list(10)
    
    # Format testimonials
    formatted_testimonials = []
    for t in testimonials:
        formatted_testimonials.append({
            "id": str(t["_id"]),
            "customer_name": t.get("customer_name", "Happy Customer"),
            "rating": t.get("rating", 5),
            "text": t.get("text_review", ""),
            "photo_url": t.get("purchase_photo_url"),
            "created_at": t.get("created_at").isoformat() if t.get("created_at") else None
        })
    
    # Get persona data
    persona = user.get("persona", {})
    
    return {
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "title": user.get("title", "Sales Professional"),
            "photo_url": user.get("photo_url"),
            "bio": persona.get("bio", ""),
            "hobbies": persona.get("hobbies", []),
            "family_info": persona.get("family_info", ""),
            "hometown": persona.get("hometown", ""),
            "years_experience": persona.get("years_experience", ""),
            "fun_facts": persona.get("fun_facts", []),
            "personal_motto": persona.get("personal_motto", ""),
            "social_links": user.get("social_links", {}),
        },
        "store": {
            "id": str(store["_id"]) if store else None,
            "name": store.get("name", "") if store else None,
            "logo_url": store.get("logo_url") if store else None,
            "primary_color": store.get("primary_color", "#C9A962") if store else "#C9A962",
            "phone": store.get("phone") if store else None,
            "address": store.get("address") if store else None,
            "city": store.get("city") if store else None,
            "state": store.get("state") if store else None,
            "website": store.get("website") if store else None,
            "review_links": store.get("review_links", {}) if store else {},
        } if store else None,
        "testimonials": formatted_testimonials
    }


@router.post("/review/{user_id}")
async def submit_review(
    user_id: str,
    customer_name: str = Form(...),
    rating: int = Form(...),
    text_review: str = Form(None),
    customer_phone: str = Form(None),
    customer_email: str = Form(None),
    photo: UploadFile = File(None)
):
    """
    Submit a review for a salesperson
    Reviews must be approved before appearing on the landing page
    """
    db = get_db()
    
    # Validate user exists
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Process photo if uploaded
    purchase_photo_url = None
    if photo:
        contents = await photo.read()
        # Limit file size (5MB)
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image must be less than 5MB")
        
        # Convert to base64 data URL
        base64_data = base64.b64encode(contents).decode('utf-8')
        purchase_photo_url = f"data:{photo.content_type};base64,{base64_data}"
    
    # Create feedback record
    feedback_doc = {
        "salesperson_id": user_id,
        "store_id": user.get("store_id"),
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "rating": rating,
        "text_review": text_review,
        "purchase_photo_url": purchase_photo_url,
        "photo_consent": True,
        "approved": False,  # Requires approval
        "source": "landing_page",
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.customer_feedback.insert_one(feedback_doc)
    
    # Log activity: customer submitted a review/feedback
    try:
        from utils.contact_activity import log_activity_for_customer
        await log_activity_for_customer(
            user_id=user_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            event_type="review_submitted",
            title="Submitted a Review",
            description=f"{customer_name} left a {rating}-star review" + (f': "{text_review[:60]}..."' if text_review and len(text_review) > 60 else f': "{text_review}"' if text_review else ""),
            icon="star",
            color="#FFD60A",
            category="customer_activity",
            metadata={"feedback_id": str(result.inserted_id), "rating": rating, "has_photo": purchase_photo_url is not None},
        )
    except Exception as e:
        print(f"[PublicLanding] Failed to log review activity: {e}")
    
    return {
        "success": True,
        "feedback_id": str(result.inserted_id),
        "message": "Thank you for your review! It will be visible after approval."
    }


@router.get("/reviews/pending/{user_id}")
async def get_pending_reviews(user_id: str):
    """
    Get pending reviews for approval  - includes both
    salesperson-level and account-level (store) reviews.
    """
    db = get_db()
    
    # Get user's store_id for account-level reviews
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "role": 1})
    store_id = user.get("store_id") if user else None
    
    # Build filter: salesperson reviews OR store-level reviews (for managers/admins)
    query_filter = {"approved": {"$ne": True}}
    if store_id and user.get("role") in ("super_admin", "org_admin", "store_manager"):
        query_filter["$or"] = [
            {"salesperson_id": user_id},
            {"store_id": store_id}
        ]
    else:
        query_filter["salesperson_id"] = user_id
    
    reviews = await db.customer_feedback.find(query_filter).sort("created_at", -1).to_list(50)
    
    return [{
        "id": str(r["_id"]),
        "customer_name": r.get("customer_name", "Customer"),
        "customer_phone": r.get("customer_phone"),
        "customer_email": r.get("customer_email"),
        "rating": r.get("rating", 5),
        "text": r.get("text_review", ""),
        "photo_url": r.get("purchase_photo_url"),
        "created_at": r.get("created_at").isoformat() if r.get("created_at") else None
    } for r in reviews]


@router.post("/reviews/approve/{review_id}")
async def approve_review(review_id: str):
    """
    Approve a review to be displayed on landing page
    """
    db = get_db()
    
    result = await db.customer_feedback.update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"approved": True, "approved_at": datetime.now(timezone.utc)}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {"success": True, "message": "Review approved"}


@router.post("/reviews/reject/{review_id}")
async def reject_review(review_id: str):
    """
    Reject/delete a review
    """
    db = get_db()
    
    result = await db.customer_feedback.delete_one({"_id": ObjectId(review_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {"success": True, "message": "Review removed"}


@router.post("/refer/{user_id}")
async def create_referral(user_id: str, data: dict):
    """
    Create a referral from the landing page
    """
    db = get_db()
    
    # Get the salesperson
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    referrer_name = data.get("referrer_name", "")
    referrer_phone = data.get("referrer_phone", "")
    referred_name = data.get("referred_name", "")
    referred_phone = data.get("referred_phone", "")
    referred_email = data.get("referred_email", "")
    notes = data.get("notes", "")
    
    # Create the referral record
    referral_doc = {
        "salesperson_id": user_id,
        "store_id": user.get("store_id"),
        "referrer_name": referrer_name,
        "referrer_phone": referrer_phone,
        "referred_name": referred_name,
        "referred_phone": referred_phone,
        "referred_email": referred_email,
        "notes": notes,
        "source": "landing_page",
        "status": "new",
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.referrals.insert_one(referral_doc)
    
    # Also create a contact if phone is provided
    if referred_phone:
        existing_contact = await db.contacts.find_one({
            "user_id": user_id,
            "phone": referred_phone
        })
        
        if not existing_contact:
            contact_doc = {
                "user_id": user_id,
                "store_id": user.get("store_id"),
                "first_name": referred_name.split()[0] if referred_name else "",
                "last_name": " ".join(referred_name.split()[1:]) if referred_name and len(referred_name.split()) > 1 else "",
                "phone": referred_phone,
                "email": referred_email,
                "source": "referral",
                "referred_by": referrer_name,
                "notes": notes,
                "tags": ["Referral"],
                "created_at": datetime.now(timezone.utc)
            }
            await db.contacts.insert_one(contact_doc)
    
    return {
        "success": True,
        "referral_id": str(result.inserted_id),
        "message": "Thank you for the referral!"
    }


@router.get("/referrals/{user_id}")
async def get_referrals(user_id: str, status: str = None):
    """
    Get referrals for a user
    """
    db = get_db()
    
    query = {"salesperson_id": user_id}
    if status:
        query["status"] = status
    
    referrals = await db.referrals.find(query).sort("created_at", -1).to_list(100)
    
    return [{
        "id": str(r["_id"]),
        "referrer_name": r.get("referrer_name"),
        "referred_name": r.get("referred_name"),
        "referred_phone": r.get("referred_phone"),
        "referred_email": r.get("referred_email"),
        "notes": r.get("notes"),
        "status": r.get("status", "new"),
        "created_at": r.get("created_at").isoformat() if r.get("created_at") else None
    } for r in referrals]
