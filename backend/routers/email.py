"""
Email router - handles email sending via Resend, email templates, and email campaigns
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
import logging
import asyncio
import os
import resend

from pydantic import BaseModel, EmailStr
from routers.database import get_db, get_data_filter, get_user_by_id

router = APIRouter(prefix="/email", tags=["Email"])
logger = logging.getLogger(__name__)

# Initialize Resend
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# ============= PYDANTIC MODELS =============

class SendEmailRequest(BaseModel):
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    subject: str
    html_content: str
    contact_id: Optional[str] = None

class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    html_content: str
    category: str = "general"
    description: Optional[str] = None

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    html_content: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

class EmailCampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template_id: Optional[str] = None
    subject: str
    html_content: str
    trigger_type: str = "manual"  # manual, birthday, anniversary, custom_date

class BrandKitUpdate(BaseModel):
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    footer_text: Optional[str] = None
    social_links: Optional[dict] = None

# ============= DEFAULT EMAIL TEMPLATES =============

DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Welcome Email",
        "subject": "Welcome to {company_name}!",
        "html_content": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #333;">Welcome, {name}!</h1>
    <p style="color: #666; line-height: 1.6;">Thank you for connecting with us. We're excited to have you!</p>
    <p style="color: #666; line-height: 1.6;">If you have any questions, don't hesitate to reach out.</p>
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px;">Powered by iMos</p>
    </div>
</div>
""",
        "category": "greeting",
        "is_default": True
    },
    {
        "name": "Digital Business Card",
        "subject": "{sender_name}'s Digital Business Card",
        "html_content": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">Here's my digital business card</h2>
    <p style="color: #666; line-height: 1.6;">Hi {name},</p>
    <p style="color: #666; line-height: 1.6;">Here's my digital business card with all my contact information:</p>
    <div style="text-align: center; margin: 30px 0;">
        <a href="{card_link}" style="background-color: #007AFF; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">View My Card</a>
    </div>
    <p style="color: #666; line-height: 1.6;">Looking forward to connecting!</p>
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px;">Powered by iMos</p>
    </div>
</div>
""",
        "category": "digital_card",
        "is_default": True
    },
    {
        "name": "Review Request",
        "subject": "We'd love your feedback, {name}!",
        "html_content": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">How was your experience?</h2>
    <p style="color: #666; line-height: 1.6;">Hi {name},</p>
    <p style="color: #666; line-height: 1.6;">We hope you had a great experience! Your feedback means the world to us and helps others make informed decisions.</p>
    <div style="text-align: center; margin: 30px 0;">
        <a href="{review_link}" style="background-color: #34C759; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">Leave a Review</a>
    </div>
    <p style="color: #666; line-height: 1.6;">Thank you for your time!</p>
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px;">Powered by iMos</p>
    </div>
</div>
""",
        "category": "review_request",
        "is_default": True
    },
    {
        "name": "Photo Share",
        "subject": "Photos from {sender_name}",
        "html_content": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">Here are your photos!</h2>
    <p style="color: #666; line-height: 1.6;">Hi {name},</p>
    <p style="color: #666; line-height: 1.6;">As promised, here are the photos from our meeting:</p>
    <div style="margin: 20px 0;">
        {photos}
    </div>
    <p style="color: #666; line-height: 1.6;">Let me know if you need anything else!</p>
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px;">Powered by iMos</p>
    </div>
</div>
""",
        "category": "photo_share",
        "is_default": True
    },
    {
        "name": "Follow Up",
        "subject": "Following up - {subject_line}",
        "html_content": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <p style="color: #666; line-height: 1.6;">Hi {name},</p>
    <p style="color: #666; line-height: 1.6;">I wanted to follow up on our conversation. Do you have any questions I can help answer?</p>
    <p style="color: #666; line-height: 1.6;">I'm here to help whenever you're ready!</p>
    <p style="color: #666; line-height: 1.6;">Best regards,<br>{sender_name}</p>
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px;">Powered by iMos</p>
    </div>
</div>
""",
        "category": "follow_up",
        "is_default": True
    },
]

# ============= HELPER FUNCTIONS =============

def get_brand_wrapper(brand_kit: dict = None) -> tuple:
    """Returns header and footer HTML based on brand kit"""
    if not brand_kit:
        brand_kit = {}
    
    logo_url = brand_kit.get("logo_url", "")
    primary_color = brand_kit.get("primary_color", "#007AFF")
    company_name = brand_kit.get("company_name", "")
    tagline = brand_kit.get("tagline", "")
    footer_text = brand_kit.get("footer_text", "Powered by iMos")
    
    header = f"""
<div style="background-color: {primary_color}; padding: 20px; text-align: center;">
    {f'<img src="{logo_url}" alt="{company_name}" style="max-height: 60px; margin-bottom: 10px;">' if logo_url else ''}
    {f'<h1 style="color: white; margin: 0;">{company_name}</h1>' if company_name else ''}
    {f'<p style="color: rgba(255,255,255,0.8); margin: 5px 0 0 0;">{tagline}</p>' if tagline else ''}
</div>
"""
    
    footer = f"""
<div style="margin-top: 30px; padding: 20px; background-color: #f5f5f5; text-align: center;">
    <p style="color: #999; font-size: 12px; margin: 0;">{footer_text}</p>
</div>
"""
    return header, footer

async def wrap_email_with_brand(html_content: str, user_id: str = None, store_id: str = None, org_id: str = None) -> str:
    """Wrap email content with brand header and footer"""
    db = get_db()
    brand_kit = None
    
    # Try to get brand kit from store, then org, then user
    if store_id:
        store = await db.stores.find_one({"_id": ObjectId(store_id)})
        if store:
            brand_kit = store.get("email_brand_kit")
    
    if not brand_kit and org_id:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})
        if org:
            brand_kit = org.get("email_brand_kit")
    
    if not brand_kit and user_id:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            brand_kit = user.get("email_brand_kit")
    
    header, footer = get_brand_wrapper(brand_kit)
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white;">
        {header}
        {html_content}
        {footer}
    </div>
</body>
</html>
"""

# ============= SEND EMAIL ENDPOINT =============

@router.post("/send")
async def send_email(request: SendEmailRequest, user_id: str):
    """Send an email via Resend"""
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Wrap content with branding
    wrapped_html = await wrap_email_with_brand(
        request.html_content,
        user_id=user_id,
        store_id=user.get("store_id"),
        org_id=user.get("organization_id")
    )
    
    params = {
        "from": SENDER_EMAIL,
        "to": [request.recipient_email],
        "subject": request.subject,
        "html": wrapped_html,
    }
    
    try:
        email_result = await asyncio.to_thread(resend.Emails.send, params)
        
        # Log email in database
        await db.email_logs.insert_one({
            "user_id": user_id,
            "contact_id": request.contact_id,
            "recipient_email": request.recipient_email,
            "recipient_name": request.recipient_name,
            "subject": request.subject,
            "status": "sent",
            "resend_id": email_result.get("id"),
            "sent_at": datetime.utcnow(),
        })
        
        return {
            "status": "success",
            "message": f"Email sent to {request.recipient_email}",
            "email_id": email_result.get("id")
        }
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        
        # Log failed attempt
        await db.email_logs.insert_one({
            "user_id": user_id,
            "contact_id": request.contact_id,
            "recipient_email": request.recipient_email,
            "subject": request.subject,
            "status": "failed",
            "error": str(e),
            "attempted_at": datetime.utcnow(),
        })
        
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# ============= EMAIL TEMPLATES CRUD =============

@router.get("/templates/{user_id}")
async def get_email_templates(user_id: str):
    """Get all email templates for a user"""
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's custom templates
    templates = await db.email_templates.find({
        "$or": [
            {"user_id": user_id},
            {"store_id": user.get("store_id")},
            {"organization_id": user.get("organization_id")},
            {"is_default": True}
        ]
    }).to_list(100)
    
    # If no templates, seed defaults
    if not templates:
        for template in DEFAULT_EMAIL_TEMPLATES:
            template_doc = {**template, "user_id": user_id, "created_at": datetime.utcnow()}
            await db.email_templates.insert_one(template_doc)
        templates = await db.email_templates.find({"user_id": user_id}).to_list(100)
    
    return [{**t, "_id": str(t["_id"])} for t in templates]

@router.post("/templates/{user_id}")
async def create_email_template(user_id: str, template: EmailTemplateCreate):
    """Create a new email template"""
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    template_doc = {
        **template.dict(),
        "user_id": user_id,
        "store_id": user.get("store_id"),
        "organization_id": user.get("organization_id"),
        "is_default": False,
        "usage_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    result = await db.email_templates.insert_one(template_doc)
    template_doc["_id"] = str(result.inserted_id)
    
    return template_doc

@router.put("/templates/{user_id}/{template_id}")
async def update_email_template(user_id: str, template_id: str, update: EmailTemplateUpdate):
    """Update an email template"""
    db = get_db()
    
    update_dict = {k: v for k, v in update.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.email_templates.update_one(
        {"_id": ObjectId(template_id), "user_id": user_id},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"message": "Template updated"}

@router.delete("/templates/{user_id}/{template_id}")
async def delete_email_template(user_id: str, template_id: str):
    """Delete an email template"""
    db = get_db()
    
    # Don't allow deleting default templates
    template = await db.email_templates.find_one({"_id": ObjectId(template_id)})
    if template and template.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete default templates")
    
    result = await db.email_templates.delete_one(
        {"_id": ObjectId(template_id), "user_id": user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"message": "Template deleted"}

# ============= EMAIL CAMPAIGNS CRUD =============

@router.get("/campaigns/{user_id}")
async def get_email_campaigns(user_id: str):
    """Get all email campaigns for a user"""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    
    campaigns = await db.email_campaigns.find(base_filter).to_list(100)
    return [{**c, "_id": str(c["_id"])} for c in campaigns]

@router.post("/campaigns/{user_id}")
async def create_email_campaign(user_id: str, campaign: EmailCampaignCreate):
    """Create a new email campaign"""
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    campaign_doc = {
        **campaign.dict(),
        "user_id": user_id,
        "store_id": user.get("store_id"),
        "organization_id": user.get("organization_id"),
        "active": True,
        "sent_count": 0,
        "open_count": 0,
        "click_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    result = await db.email_campaigns.insert_one(campaign_doc)
    campaign_doc["_id"] = str(result.inserted_id)
    
    return campaign_doc

@router.put("/campaigns/{user_id}/{campaign_id}")
async def update_email_campaign(user_id: str, campaign_id: str, updates: dict):
    """Update an email campaign"""
    db = get_db()
    
    updates["updated_at"] = datetime.utcnow()
    
    result = await db.email_campaigns.update_one(
        {"_id": ObjectId(campaign_id), "user_id": user_id},
        {"$set": updates}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"message": "Campaign updated"}

@router.delete("/campaigns/{user_id}/{campaign_id}")
async def delete_email_campaign(user_id: str, campaign_id: str):
    """Delete an email campaign"""
    db = get_db()
    
    result = await db.email_campaigns.delete_one(
        {"_id": ObjectId(campaign_id), "user_id": user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"message": "Campaign deleted"}

# ============= BRAND KIT ENDPOINTS =============

@router.get("/brand-kit/{entity_type}/{entity_id}")
async def get_brand_kit(entity_type: str, entity_id: str):
    """Get brand kit for user, store, or organization"""
    db = get_db()
    
    collection_map = {
        "user": "users",
        "store": "stores",
        "organization": "organizations"
    }
    
    if entity_type not in collection_map:
        raise HTTPException(status_code=400, detail="Invalid entity type")
    
    collection = collection_map[entity_type]
    entity = await db[collection].find_one({"_id": ObjectId(entity_id)})
    
    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.title()} not found")
    
    return entity.get("email_brand_kit", {})

@router.put("/brand-kit/{entity_type}/{entity_id}")
async def update_brand_kit(entity_type: str, entity_id: str, brand_kit: BrandKitUpdate):
    """Update brand kit for user, store, or organization"""
    db = get_db()
    
    collection_map = {
        "user": "users",
        "store": "stores",
        "organization": "organizations"
    }
    
    if entity_type not in collection_map:
        raise HTTPException(status_code=400, detail="Invalid entity type")
    
    collection = collection_map[entity_type]
    update_dict = {f"email_brand_kit.{k}": v for k, v in brand_kit.dict().items() if v is not None}
    
    result = await db[collection].update_one(
        {"_id": ObjectId(entity_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"{entity_type.title()} not found")
    
    return {"message": "Brand kit updated"}

# ============= USER PREFERENCES =============

@router.get("/preferences/{user_id}")
async def get_email_preferences(user_id: str):
    """Get user's email/SMS mode preferences"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user.get("messaging_preferences", {
        "default_mode": "sms",
        "toggle_style": "pill",  # pill, fab, tabs, segmented
    })

@router.put("/preferences/{user_id}")
async def update_email_preferences(user_id: str, preferences: dict):
    """Update user's email/SMS mode preferences"""
    db = get_db()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"messaging_preferences": preferences}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Preferences updated"}

# ============= EMAIL LOGS =============

@router.get("/logs/{user_id}")
async def get_email_logs(user_id: str, limit: int = 50):
    """Get email sending logs for a user"""
    db = get_db()
    
    logs = await db.email_logs.find(
        {"user_id": user_id}
    ).sort("sent_at", -1).limit(limit).to_list(limit)
    
    return [{**log, "_id": str(log["_id"])} for log in logs]
