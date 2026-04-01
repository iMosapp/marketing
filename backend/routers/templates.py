"""
Message Templates router - handles user message templates CRUD
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List
import logging
import re

from models import MessageTemplateCreate, MessageTemplateUpdate
from routers.database import get_db

router = APIRouter(prefix="/templates", tags=["Templates"])
logger = logging.getLogger(__name__)

YOUTUBE_URL_RE = re.compile(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+(?:&[\w=]*)*')
ANY_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')


async def _auto_wrap_content_urls(content: str, user_id: str, context: str = "template") -> str:
    """Wrap ALL raw URLs in template content with tracked short URLs."""
    from routers.short_urls import create_short_url
    urls = ANY_URL_RE.findall(content)
    for url in urls:
        if "/api/s/" in url:
            continue  # already tracked
        try:
            link_type = "training_video" if ("youtube.com" in url or "youtu.be" in url) else context
            result = await create_short_url(
                original_url=url,
                link_type=link_type,
                user_id=user_id,
                metadata={"source": context},
            )
            content = content.replace(url, result["short_url"])
        except Exception as e:
            logger.warning(f"[AutoWrap] Failed to wrap {url}: {e}")
    return content

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
    # ── Onboarding Video Templates ──
    {
        "name": "Video: Saving The App",
        "content": "Hey {name}! Here's a quick 2-min video on how to save the app to your phone so it's always one tap away: https://www.youtube.com/watch?v=Vj_JBS5UXrQ",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: Setting Up Your Profile",
        "content": "Hey {name}! Check out this quick video on setting up your profile — your photo, bio, and brand: https://www.youtube.com/watch?v=dT7ybKZembI",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: Home Screen Tour",
        "content": "Hey {name}! Here's a quick walkthrough of your Home screen — touchpoints, quick actions, and more: https://www.youtube.com/watch?v=nsTC9IVEmNY",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: Managing Contacts",
        "content": "Hey {name}! This video shows you how to add, search, and manage your contacts: https://www.youtube.com/watch?v=in5K_-TRKlM",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: Using Your Inbox",
        "content": "Hey {name}! Learn how to use your Inbox to send texts, emails, and stay on top of every conversation: https://www.youtube.com/watch?v=Dccm4yhkapM",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: Best Practices",
        "content": "Hey {name}! Check out these tips and best practices from top performers: https://www.youtube.com/watch?v=KfCXQEzLKTA",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: The 30 Second Workflow",
        "content": "Hey {name}! This is the secret weapon — the 30-second daily workflow that keeps every relationship warm: https://www.youtube.com/watch?v=5YpvvDChBOY",
        "category": "training_video",
        "is_default": True
    },
    {
        "name": "Video: Tags & Campaigns",
        "content": "Hey {name}! Learn how tags and campaigns turn one-time buyers into lifelong customers: https://www.youtube.com/watch?v=Uss8ziGL120",
        "category": "training_video",
        "is_default": True
    },
]


async def _wrap_video_urls(templates: list, user_id: str) -> list:
    """For training_video templates, replace raw YouTube URLs with tracked short URLs."""
    from routers.short_urls import create_short_url
    for t in templates:
        if t.get("category") != "training_video":
            continue
        content = t.get("content", "")
        matches = YOUTUBE_URL_RE.findall(content)
        for yt_url in matches:
            try:
                result = await create_short_url(
                    original_url=yt_url,
                    link_type="training_video",
                    reference_id=None,
                    user_id=user_id,
                    metadata={"video_url": yt_url, "video_title": t.get("name", "Training Video")},
                )
                content = content.replace(yt_url, result["short_url"])
            except Exception as e:
                logger.warning(f"Failed to wrap video URL {yt_url}: {e}")
        t["content"] = content
    return templates


@router.get("/{user_id}")
async def get_templates(user_id: str):
    """Get all templates for a user (including org-level and defaults)"""
    db = get_db()
    
    # Get user's own templates
    user_templates = await db.templates.find(
        {"user_id": user_id}
    ).sort("name", 1).to_list(100)
    
    # Also get org-level templates (created by admin/manager in same org)
    user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"org_id": 1, "store_id": 1})
    org_templates = []
    if user_doc:
        org_id = user_doc.get("org_id")
        store_id = user_doc.get("store_id")
        if org_id:
            # Find templates from other users in the same org that are marked shared or default
            org_users = await db.users.find(
                {"org_id": org_id, "_id": {"$ne": ObjectId(user_id)}},
                {"_id": 1}
            ).to_list(50)
            org_user_ids = [str(u["_id"]) for u in org_users]
            if org_user_ids:
                org_templates = await db.templates.find(
                    {"user_id": {"$in": org_user_ids}, "is_default": True}
                ).sort("name", 1).to_list(100)
        elif store_id:
            # Use store_id to find org templates
            store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"org_id": 1})
            if store and store.get("org_id"):
                org_users = await db.users.find(
                    {"org_id": store["org_id"], "_id": {"$ne": ObjectId(user_id)}},
                    {"_id": 1}
                ).to_list(50)
                org_user_ids = [str(u["_id"]) for u in org_users]
                if org_user_ids:
                    org_templates = await db.templates.find(
                        {"user_id": {"$in": org_user_ids}, "is_default": True}
                    ).sort("name", 1).to_list(100)
    
    # Merge: user's templates first, then org templates (avoid dupes by name)
    user_names = {t.get("name", "").lower() for t in user_templates}
    templates = []
    for t in user_templates:
        t["_id"] = str(t["_id"])
        templates.append(t)
    for t in org_templates:
        if t.get("name", "").lower() not in user_names:
            t["_id"] = str(t["_id"])
            t["is_org_template"] = True
            templates.append(t)
    
    # If user has no templates at all, create ALL defaults
    # Otherwise, check for missing video templates and add them
    if not templates:
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
    else:
        # Auto-add any missing default templates (e.g., new video templates)
        existing_names = {t.get("name", "").lower() for t in templates}
        added = 0
        for default in DEFAULT_TEMPLATES:
            if default["name"].lower() not in existing_names:
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
                added += 1
        if added:
            logger.info(f"Auto-added {added} new default templates for user {user_id}")
    
    # Wrap YouTube URLs in training_video templates with tracked short URLs
    templates = await _wrap_video_urls(templates, user_id)
    
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

    # Auto-wrap any URLs in content with tracking
    wrapped_content = await _auto_wrap_content_urls(template_data.content, user_id, template_data.category or "template")
    
    template = {
        "user_id": user_id,
        "name": template_data.name,
        "content": wrapped_content,
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
        # Auto-wrap any URLs in content with tracking
        category = template_data.category or "template"
        update_dict["content"] = await _auto_wrap_content_urls(template_data.content, user_id, category)
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
    """Delete a template — any template the user owns can be deleted"""
    db = get_db()
    template = await db.templates.find_one({"_id": ObjectId(template_id), "user_id": user_id})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
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
            {"id": "training_video", "name": "Training Video", "icon": "play-circle"},
            {"id": "referral", "name": "Referral Request", "icon": "share"},
            {"id": "sold", "name": "Congratulations - Sold", "icon": "checkmark-circle"},
        ]
    }
