"""
Message Templates router - handles user message templates CRUD
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List
import logging

from models import MessageTemplateCreate, MessageTemplateUpdate
from routers.database import get_db

router = APIRouter(prefix="/templates", tags=["Templates"])
logger = logging.getLogger(__name__)

# Default templates that all users get
DEFAULT_TEMPLATES = [
    {
        "name": "Greeting",
        "content": "Hi {name}! Thanks for reaching out. How can I help you today?",
        "category": "greeting",
        "is_default": True
    },
    {
        "name": "Follow Up",
        "content": "Hi {name}, I wanted to follow up on our conversation. Do you have any questions?",
        "category": "follow_up",
        "is_default": True
    },
    {
        "name": "Appointment",
        "content": "Hi {name}, I'd love to schedule a time to chat. What works best for you?",
        "category": "appointment",
        "is_default": True
    },
    {
        "name": "Thank You",
        "content": "Thank you so much for your time today, {name}! Please let me know if you need anything else.",
        "category": "thank_you",
        "is_default": True
    },
    {
        "name": "Review Request",
        "content": "Hi {name}! If you had a great experience, we'd really appreciate a review. Here's the link: ",
        "category": "review",
        "is_default": True
    },
    {
        "name": "Referral Request",
        "content": "Hi {name}! If you know anyone who could benefit from our services, I'd love an introduction. Referrals mean the world to us!",
        "category": "referral",
        "is_default": True
    },
    {
        "name": "Congratulations - Sold!",
        "content": "Congratulations on your new purchase, {name}! Thank you for trusting us. Please reach out if you have any questions!",
        "category": "sold",
        "is_default": True
    },
]


@router.get("/{user_id}")
async def get_templates(user_id: str):
    """Get all templates for a user (including defaults)"""
    db = get_db()
    
    # Get user's custom templates
    user_templates = await db.templates.find(
        {"user_id": user_id}
    ).sort("name", 1).to_list(100)
    
    # Convert ObjectIds
    templates = []
    for t in user_templates:
        t["_id"] = str(t["_id"])
        templates.append(t)
    
    # If user has no templates, return defaults
    if not templates:
        # Create default templates for this user
        for default in DEFAULT_TEMPLATES:
            template = {
                "user_id": user_id,
                **default,
                "usage_count": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.templates.insert_one(template)
            template["_id"] = str(result.inserted_id)
            templates.append(template)
    
    return templates


@router.get("/{user_id}/{template_id}")
async def get_template(user_id: str, template_id: str):
    """Get a specific template"""
    db = get_db()
    
    template = await db.templates.find_one({
        "_id": ObjectId(template_id),
        "user_id": user_id
    })
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template["_id"] = str(template["_id"])
    return template


@router.post("/{user_id}")
async def create_template(user_id: str, template_data: MessageTemplateCreate):
    """Create a new custom template"""
    db = get_db()
    
    # Check for duplicate name
    existing = await db.templates.find_one({
        "user_id": user_id,
        "name": template_data.name
    })
    if existing:
        raise HTTPException(status_code=400, detail="Template with this name already exists")
    
    template = {
        "user_id": user_id,
        "name": template_data.name,
        "content": template_data.content,
        "category": template_data.category,
        "is_default": False,
        "usage_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.templates.insert_one(template)
    template["_id"] = str(result.inserted_id)
    
    return template


@router.put("/{user_id}/{template_id}")
async def update_template(user_id: str, template_id: str, template_data: MessageTemplateUpdate):
    """Update an existing template"""
    db = get_db()
    
    # Build update dict
    update_dict = {"updated_at": datetime.utcnow()}
    if template_data.name is not None:
        update_dict["name"] = template_data.name
    if template_data.content is not None:
        update_dict["content"] = template_data.content
    if template_data.category is not None:
        update_dict["category"] = template_data.category
    
    result = await db.templates.update_one(
        {"_id": ObjectId(template_id), "user_id": user_id},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Return updated template
    template = await db.templates.find_one({"_id": ObjectId(template_id)})
    template["_id"] = str(template["_id"])
    return template


@router.delete("/{user_id}/{template_id}")
async def delete_template(user_id: str, template_id: str):
    """Delete a template"""
    db = get_db()
    
    # Check if it's a default template
    template = await db.templates.find_one({
        "_id": ObjectId(template_id),
        "user_id": user_id
    })
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete default templates")
    
    await db.templates.delete_one({"_id": ObjectId(template_id)})
    
    return {"message": "Template deleted"}


@router.post("/{user_id}/{template_id}/use")
async def track_template_usage(user_id: str, template_id: str):
    """Track when a template is used (increment usage counter)"""
    db = get_db()
    
    result = await db.templates.update_one(
        {"_id": ObjectId(template_id), "user_id": user_id},
        {"$inc": {"usage_count": 1}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"message": "Usage tracked"}


@router.get("/{user_id}/categories/list")
async def get_template_categories(user_id: str):
    """Get list of available template categories"""
    return {
        "categories": [
            {"id": "general", "name": "General", "icon": "document-text"},
            {"id": "greeting", "name": "Greeting", "icon": "hand-right"},
            {"id": "follow_up", "name": "Follow Up", "icon": "refresh"},
            {"id": "appointment", "name": "Appointment", "icon": "calendar"},
            {"id": "thank_you", "name": "Thank You", "icon": "heart"},
            {"id": "review", "name": "Review Request", "icon": "star"},
            {"id": "referral", "name": "Referral Request", "icon": "share"},
            {"id": "sold", "name": "Congratulations - Sold", "icon": "checkmark-circle"},
        ]
    }
