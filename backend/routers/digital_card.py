"""
Digital Business Card router - shareable card for salespeople
Includes campaign enrollment on card save/download
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import Optional
from routers.database import get_db, get_data_filter
from routers.short_urls import create_short_url, get_short_url_base

def get_safe_logo(doc):
    """Return avatar or short logo URL, never a massive base64."""
    if not doc:
        return None
    avatar = doc.get("logo_avatar_url")
    if avatar:
        return avatar
    logo = doc.get("logo_url")
    if logo and (not logo.startswith("data:") or len(logo) < 500):
        return logo
    return None

router = APIRouter(prefix="/card", tags=["digital-card"])


@router.get("/data/{user_id}")
async def get_card_data(user_id: str):
    """
    Get salesperson's digital card data for public display
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
    
    # Get testimonials/reviews for this salesperson (approved only)
    testimonials = await db.customer_feedback.find({
        "salesperson_id": user_id,
        "approved": True,
        "rating": {"$gte": 4}   # Only show 4+ star reviews
    }).sort("created_at", -1).limit(5).to_list(5)
    
    # Format testimonials
    formatted_testimonials = []
    for t in testimonials:
        formatted_testimonials.append({
            "id": str(t["_id"]),
            "customer_name": t.get("customer_name", "Happy Customer"),
            "rating": t.get("rating", 5),
            "text": t.get("text_review", ""),
            "created_at": t.get("created_at").isoformat() if t.get("created_at") else None
        })
    
    # Add partner branding if available
    partner_branding_data = None
    if store and store.get("partner_id"):
        try:
            partner = await db.white_label_partners.find_one(
                {"_id": ObjectId(store["partner_id"]), "is_active": True},
                {"_id": 0, "created_at": 0, "updated_at": 0}
            )
            if partner:
                partner_branding_data = partner
        except Exception:
            pass

    result = {
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "title": user.get("title", "Sales Professional"),
            "photo_url": user.get("photo_url"),
            "bio": user.get("persona", {}).get("bio", ""),
            "social_links": user.get("social_links", {}),
        },
        "store": {
            "id": str(store["_id"]) if store else None,
            "name": store.get("name", "") if store else None,
            "logo_url": store.get("logo_url") if store else None,
            "primary_color": store.get("primary_color", "#007AFF") if store else "#007AFF",
            "phone": store.get("phone") if store else None,
            "address": store.get("address") if store else None,
            "city": store.get("city") if store else None,
            "state": store.get("state") if store else None,
            "website": store.get("website") if store else None,
        } if store else None,
        "testimonials": formatted_testimonials
    }
    if partner_branding_data:
        result["partner_branding"] = partner_branding_data
    return result


@router.post("/save/{user_id}")
async def track_card_save(
    user_id: str, 
    data: dict
):
    """
    Track when a customer saves the digital card
    Optionally enrolls the contact in a campaign
    """
    db = get_db()
    
    contact_id = data.get("contact_id")
    campaign_id = data.get("campaign_id")
    
    # Log the card save event
    event = {
        "type": "card_save",
        "user_id": user_id,
        "contact_id": contact_id,
        "campaign_id": campaign_id,
        "created_at": datetime.utcnow()
    }
    await db.card_events.insert_one(event)
    
    # If campaign_id provided, enroll the contact
    if campaign_id and contact_id:
        try:
            # Get contact info
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
            if not contact:
                return {"success": True, "enrolled": False, "message": "Contact not found"}
            
            # Get campaign info
            campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
            if not campaign:
                return {"success": True, "enrolled": False, "message": "Campaign not found"}
            
            # Check if already enrolled
            existing = await db.campaign_enrollments.find_one({
                "campaign_id": campaign_id,
                "contact_id": contact_id,
                "status": "active"
            })
            
            if existing:
                return {"success": True, "enrolled": False, "message": "Already enrolled"}
            
            # Create enrollment
            enrollment = {
                "user_id": user_id,
                "campaign_id": campaign_id,
                "contact_id": contact_id,
                "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "contact_phone": contact.get("phone", ""),
                "current_step": 1,
                "status": "active",
                "enrolled_at": datetime.utcnow(),
                "next_send_at": datetime.utcnow(),  # Start immediately
                "messages_sent": [],
                "source": "digital_card"
            }
            
            await db.campaign_enrollments.insert_one(enrollment)
            
            return {
                "success": True, 
                "enrolled": True, 
                "campaign_name": campaign.get("name"),
                "message": f"Enrolled in {campaign.get('name')}"
            }
            
        except Exception as e:
            return {"success": True, "enrolled": False, "message": str(e)}
    
    return {"success": True, "enrolled": False}


@router.get("/vcard/{user_id}")
async def generate_vcard(user_id: str):
    """
    Generate vCard data for the salesperson
    Returns vCard file for download
    """
    from fastapi.responses import Response
    
    db = get_db()
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get store info for organization
    store = None
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
    
    # Build vCard
    name = user.get("name", "")
    name_parts = name.split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    vcard_lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{last_name};{first_name};;;",
        f"FN:{name}",
        f"TEL;TYPE=CELL:{user.get('phone', '')}",
        f"EMAIL:{user.get('email', '')}",
    ]
    
    if user.get("title"):
        vcard_lines.append(f"TITLE:{user.get('title')}")
    
    if store:
        vcard_lines.append(f"ORG:{store.get('name', '')}")
        if store.get("address"):
            addr = f"{store.get('address', '')};{store.get('city', '')};{store.get('state', '')};;;"
            vcard_lines.append(f"ADR;TYPE=WORK:;;{addr}")
        if store.get("website"):
            vcard_lines.append(f"URL:{store.get('website')}")
    
    if user.get("photo_url"):
        vcard_lines.append(f"PHOTO;VALUE=URI:{user.get('photo_url')}")
    
    vcard_lines.append("END:VCARD")
    
    vcard_content = "\n".join(vcard_lines)
    filename = f"{name.replace(' ', '_')}.vcf"
    
    # Return as a downloadable VCF file
    return Response(
        content=vcard_content,
        media_type="text/vcard",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/vcard; charset=utf-8"
        }
    )


@router.get("/campaigns/{user_id}")
async def get_user_campaigns(user_id: str):
    """
    Get list of campaigns for the user to select when sharing card
    """
    db = get_db()
    
    # Use the same role-based filter as campaigns router
    base_filter = await get_data_filter(user_id)
    base_filter["active"] = True
    
    campaigns = await db.campaigns.find(base_filter).to_list(100)
    
    return [
        {
            "id": str(c["_id"]),
            "name": c.get("name", ""),
            "type": c.get("type", "custom")
        }
        for c in campaigns
    ]


@router.get("/short-url/{user_id}")
async def get_card_short_url(user_id: str):
    """
    Get or create a short URL for a user's digital business card.
    This is the link that should be shared in messages, QR codes, etc.
    """
    db = get_db()
    
    # Verify user exists
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate the full URL for the business card public page
    base_url = get_short_url_base()
    full_card_url = f"{base_url}/p/{user_id}"
    
    # Create or get existing short URL
    short_url_result = await create_short_url(
        original_url=full_card_url,
        link_type="business_card",
        reference_id=user_id,
        user_id=user_id,
        metadata={"user_name": user.get("name", "")}
    )
    
    return {
        "user_id": user_id,
        "full_url": full_card_url,
        "short_url": short_url_result["short_url"],
        "short_code": short_url_result["short_code"]
    }


@router.get("/store/{store_slug}")
async def get_store_card_data(store_slug: str):
    """
    Get account-level digital card data for public display.
    This is the dealership/store card that managers send out.
    """
    db = get_db()

    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        # Fallback: try as org slug
        org = await db.organizations.find_one({"slug": store_slug})
        if org:
            store = await db.stores.find_one({"organization_id": str(org["_id"])})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    store_id = str(store["_id"])

    # Get brand kit
    brand_kit = store.get("email_brand_kit", {})

    # Get approved testimonials at the store level
    testimonials = await db.customer_feedback.find({
        "store_id": store_id,
        "approved": True,
        "rating": {"$gte": 4}
    }).sort("created_at", -1).limit(6).to_list(6)

    formatted_testimonials = []
    for t in testimonials:
        formatted_testimonials.append({
            "id": str(t["_id"]),
            "customer_name": t.get("customer_name", "Happy Customer"),
            "rating": t.get("rating", 5),
            "text": t.get("text_review", ""),
            "salesperson_name": t.get("salesperson_name"),
            "created_at": t.get("created_at").isoformat() if t.get("created_at") else None
        })

    # Get team members to display
    team_members = await db.users.find({
        "store_id": store_id,
        "status": "active"
    }, {"password": 0, "_id": 1, "name": 1, "title": 1, "photo_url": 1}).to_list(20)

    formatted_team = [{
        "id": str(m["_id"]),
        "name": m.get("name", ""),
        "title": m.get("title", ""),
        "photo_url": m.get("photo_url"),
    } for m in team_members]

    return {
        "store": {
            "id": store_id,
            "name": store.get("name", ""),
            "slug": store.get("slug", ""),
            "logo_url": brand_kit.get("logo_url") or store.get("logo_url", ""),
            "cover_image_url": store.get("cover_image_url"),
            "primary_color": brand_kit.get("primary_color") or store.get("primary_color", "#007AFF"),
            "phone": store.get("phone"),
            "email": store.get("email"),
            "address": store.get("address"),
            "city": store.get("city"),
            "state": store.get("state"),
            "website": store.get("website"),
            "social_links": store.get("social_links", {}),
            "business_hours": store.get("business_hours", {}),
        },
        "brand_kit": {
            "company_name": brand_kit.get("company_name", store.get("name", "")),
            "tagline": brand_kit.get("tagline", ""),
            "primary_color": brand_kit.get("primary_color", store.get("primary_color", "#007AFF")),
        },
        "testimonials": formatted_testimonials,
        "team": formatted_team,
        "review_links": store.get("review_links", {}),
    }
