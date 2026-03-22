"""
Profile router - handles salesperson profile, photo upload, AI bio generation
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from bson import ObjectId
from datetime import datetime
from typing import Optional
import os
import base64
import uuid
import logging
from dotenv import load_dotenv

load_dotenv()

from routers.database import get_db

router = APIRouter(prefix="/profile", tags=["profile"])
logger = logging.getLogger(__name__)


@router.get("/{user_id}")
async def get_profile(user_id: str):
    """Get user's full profile for display"""
    db = get_db()
    
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"password": 0}
        )
    except:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get store info
    store = None
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
    
    # Get their testimonials (reviews with consent)
    testimonials = await db.customer_feedback.find({
        "salesperson_id": user_id,
        "photo_consent": True,
        "rating": {"$gte": 4}
    }).sort("created_at", -1).limit(10).to_list(10)
    
    # Get all their reviews (for portfolio management)
    all_reviews = await db.customer_feedback.find({
        "salesperson_id": user_id
    }).sort("created_at", -1).to_list(50)
    
    from utils.image_urls import resolve_user_photo, resolve_store_logo
    
    return {
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "title": user.get("title", "Sales Professional"),
            "company": user.get("company", ""),
            "website": user.get("website", ""),
            "review_url": user.get("review_url", ""),
            "photo_url": resolve_user_photo(user),
            "bio": user.get("persona", {}).get("bio", ""),
            "hobbies": user.get("persona", {}).get("hobbies", []),
            "family_info": user.get("persona", {}).get("family_info", ""),
            "hometown": user.get("persona", {}).get("hometown", ""),
            "years_experience": user.get("persona", {}).get("years_experience", ""),
            "fun_facts": user.get("persona", {}).get("fun_facts", []),
            "personal_motto": user.get("persona", {}).get("personal_motto", ""),
            "tone_preference": user.get("persona", {}).get("tone_preference", "friendly"),
            "social_links": user.get("social_links", {}),
            "needs_password_change": user.get("needs_password_change", False),
        },
        "store": {
            "id": str(store["_id"]) if store else None,
            "name": store.get("name") if store else None,
            "logo_url": resolve_store_logo(store),
        } if store else None,
        "testimonials": [
            {
                "id": str(t["_id"]),
                "customer_name": t.get("customer_name", "Customer"),
                "rating": t.get("rating", 5),
                "text": t.get("text_review", ""),
                "in_portfolio": t.get("in_portfolio", False),
                "created_at": t.get("created_at").isoformat() if t.get("created_at") else None
            }
            for t in testimonials
        ],
        "all_reviews": [
            {
                "id": str(r["_id"]),
                "customer_name": r.get("customer_name", "Customer"),
                "rating": r.get("rating", 5),
                "text": r.get("text_review", ""),
                "photo_consent": r.get("photo_consent", False),
                "in_portfolio": r.get("in_portfolio", False),
                "created_at": r.get("created_at").isoformat() if r.get("created_at") else None
            }
            for r in all_reviews
        ]
    }


@router.put("/{user_id}")
async def update_profile(user_id: str, data: dict):
    """Update user profile fields"""
    db = get_db()
    
    allowed_fields = [
        'name', 'phone', 'title', 'company', 'website', 'review_url',
        'photo_url', 'social_links', 'onboarding_complete',
        'social_instagram', 'social_facebook', 'social_linkedin',
        'social_twitter', 'social_tiktok'
    ]
    
    # Handle persona fields separately
    persona_fields = [
        'bio', 'hobbies', 'family_info', 'hometown', 
        'years_experience', 'fun_facts', 'personal_motto', 'tone_preference'
    ]
    
    update_dict = {}
    
    # Map social_* flat fields to social_links.* nested fields
    social_map = {
        'social_instagram': 'social_links.instagram',
        'social_facebook': 'social_links.facebook',
        'social_linkedin': 'social_links.linkedin',
        'social_twitter': 'social_links.twitter',
        'social_tiktok': 'social_links.tiktok',
    }
    
    # Update regular fields
    for field in allowed_fields:
        if field in data:
            if field in social_map:
                update_dict[social_map[field]] = data[field]
            else:
                update_dict[field] = data[field]
    
    # Also handle social_links as a nested dict if passed directly
    if 'social_links' in data and isinstance(data['social_links'], dict):
        for k, v in data['social_links'].items():
            update_dict[f"social_links.{k}"] = v
    
    # Update persona fields with dot notation
    for field in persona_fields:
        if field in data:
            update_dict[f"persona.{field}"] = data[field]
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "message": "Profile updated"}


@router.post("/{user_id}/photo")
async def upload_photo(user_id: str, file: UploadFile = File(...)):
    """Upload profile photo - compresses to WebP, generates thumbnails, serves from CDN cache."""
    db = get_db()
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    contents = await file.read()
    
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 10MB")
    
    # Use the optimized image pipeline — compress → WebP → thumbnail → avatar → cache
    from utils.image_storage import upload_image
    result = await upload_image(contents, prefix="profiles", entity_id=user_id)
    if not result:
        raise HTTPException(status_code=500, detail="Image processing failed")
    
    original_url = f"/api/images/{result['original_path']}"
    thumb_url = f"/api/images/{result['thumbnail_path']}"
    avatar_url = f"/api/images/{result['avatar_path']}"
    
    # Store optimized paths (NOT base64)
    update = {
        "photo_url": original_url,
        "photo_path": result["original_path"],
        "photo_thumb_path": result["thumbnail_path"],
        "photo_avatar_path": result["avatar_path"],
        "updated_at": datetime.utcnow(),
        "og_image_path": None,  # Invalidate cached OG image so it regenerates with new photo
    }
    
    r = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update})
    if r.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "success": True,
        "photo_url": original_url,
        "thumbnail_url": thumb_url,
        "avatar_url": avatar_url,
    }


@router.post("/{user_id}/generate-bio")
async def generate_bio(user_id: str, data: dict):
    """Generate a professional bio using AI based on user's personal info"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    db = get_db()
    
    # Get user info
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Extract personal details
    name = data.get("name") or user.get("name", "")
    hobbies = data.get("hobbies", [])
    family_info = data.get("family_info", "")
    hometown = data.get("hometown", "")
    years_experience = data.get("years_experience", "")
    fun_facts = data.get("fun_facts", [])
    personal_motto = data.get("personal_motto", "")
    title = data.get("title") or user.get("title", "Sales Professional")
    
    # Build context for AI
    context_parts = []
    if name:
        context_parts.append(f"Name: {name}")
    if title:
        context_parts.append(f"Role: {title}")
    if years_experience:
        context_parts.append(f"Years of experience: {years_experience}")
    if hometown:
        context_parts.append(f"From: {hometown}")
    if family_info:
        context_parts.append(f"Family: {family_info}")
    if hobbies:
        context_parts.append(f"Hobbies: {', '.join(hobbies)}")
    if fun_facts:
        context_parts.append(f"Fun facts: {', '.join(fun_facts)}")
    if personal_motto:
        context_parts.append(f"Personal motto: {personal_motto}")
    
    if not context_parts:
        raise HTTPException(
            status_code=400, 
            detail="Please provide some personal information to generate a bio"
        )
    
    personal_info = "\n".join(context_parts)
    
    # Create AI prompt
    prompt = f"""Write a warm, professional bio for a salesperson's digital business card. 
The bio should be 2-3 sentences, feel genuine and personable, and help customers connect with them as a real person.
Make it conversational but professional. Don't start with "Hi, I'm" - be more creative.

Personal Information:
{personal_info}

Write ONLY the bio text, nothing else. No quotes around it."""

    try:
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"bio-gen-{user_id}-{uuid.uuid4()}",
            system_message="You are a professional copywriter who writes warm, authentic bios for salespeople. Keep bios concise (2-3 sentences), personable, and professional."
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        generated_bio = response.strip().strip('"').strip("'")
        
        return {
            "success": True,
            "bio": generated_bio
        }
        
    except Exception as e:
        logger.error(f"AI bio generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate bio: {str(e)}")


@router.post("/reviews/{review_id}/portfolio")
async def toggle_portfolio(review_id: str, data: dict):
    """Add or remove a review from the salesperson's portfolio"""
    db = get_db()
    
    in_portfolio = data.get("in_portfolio", True)
    
    result = await db.customer_feedback.update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"in_portfolio": in_portfolio, "updated_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {
        "success": True,
        "in_portfolio": in_portfolio,
        "message": "Added to portfolio" if in_portfolio else "Removed from portfolio"
    }
