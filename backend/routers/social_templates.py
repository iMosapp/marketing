"""
Social Content Templates router - CRUD for social content starter templates
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
import logging

from routers.database import get_db

router = APIRouter(prefix="/social-templates", tags=["Social Templates"])
logger = logging.getLogger(__name__)


@router.get("/{user_id}")
async def get_social_templates(user_id: str):
    """Get all social content templates for a user"""
    db = get_db()
    templates = await db.social_templates.find(
        {"user_id": user_id}
    ).sort("category", 1).to_list(50)
    for t in templates:
        t["_id"] = str(t["_id"])
    return templates


@router.get("/{user_id}/{template_id}")
async def get_social_template(user_id: str, template_id: str):
    """Get a specific social content template"""
    db = get_db()
    template = await db.social_templates.find_one(
        {"_id": ObjectId(template_id), "user_id": user_id}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template["_id"] = str(template["_id"])
    return template


@router.post("/{user_id}")
async def create_social_template(user_id: str, data: dict):
    """Create a new social content template"""
    db = get_db()
    doc = {
        "user_id": user_id,
        "name": data.get("name", ""),
        "category": data.get("category", ""),
        "content": data.get("content", ""),
        "is_default": False,
        "created_at": datetime.utcnow(),
    }
    result = await db.social_templates.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.put("/{user_id}/{template_id}")
async def update_social_template(user_id: str, template_id: str, data: dict):
    """Update a social content template"""
    db = get_db()
    allowed = {"name", "category", "content"}
    update_dict = {k: v for k, v in data.items() if k in allowed}
    update_dict["updated_at"] = datetime.utcnow()
    result = await db.social_templates.update_one(
        {"_id": ObjectId(template_id), "user_id": user_id},
        {"$set": update_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    updated = await db.social_templates.find_one({"_id": ObjectId(template_id)})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{user_id}/{template_id}")
async def delete_social_template(user_id: str, template_id: str):
    """Delete a social content template"""
    db = get_db()
    result = await db.social_templates.delete_one(
        {"_id": ObjectId(template_id), "user_id": user_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}
