"""
White Label Partners router — manages partner branding that cascades 
to all their organizations, accounts, and users.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import logging

from routers.database import get_db

router = APIRouter(prefix="/admin/partners", tags=["White Label Partners"])
logger = logging.getLogger(__name__)


def serialize_partner(p: dict) -> dict:
    """Convert a partner doc to JSON-safe dict."""
    p["_id"] = str(p["_id"])
    if p.get("created_at") and hasattr(p["created_at"], "isoformat"):
        p["created_at"] = p["created_at"].isoformat()
    if p.get("updated_at") and hasattr(p["updated_at"], "isoformat"):
        p["updated_at"] = p["updated_at"].isoformat()
    return p


@router.get("")
async def list_partners():
    db = get_db()
    partners = await db.white_label_partners.find({}, {"_id": 1, "name": 1, "slug": 1, "logo": 1, "primary_color": 1, "is_active": 1}).to_list(100)
    for p in partners:
        p["_id"] = str(p["_id"])
    return partners


@router.get("/{partner_id}")
async def get_partner(partner_id: str):
    db = get_db()
    p = await db.white_label_partners.find_one({"_id": ObjectId(partner_id)})
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    return serialize_partner(p)


@router.post("")
async def create_partner(data: dict):
    db = get_db()
    now = datetime.now(timezone.utc)
    partner = {
        "name": data.get("name", ""),
        "slug": data.get("slug", ""),
        "logo": data.get("logo"),
        "logo_icon": data.get("logo_icon"),
        "primary_color": data.get("primary_color", "#E87722"),
        "secondary_color": data.get("secondary_color", "#008B8B"),
        "accent_color": data.get("accent_color", "#1A1A2E"),
        "text_color": data.get("text_color", "#FFFFFF"),
        "powered_by_text": data.get("powered_by_text", "Powered by i'M On Social App"),
        "company_name": data.get("company_name", ""),
        "company_address": data.get("company_address", ""),
        "company_phone": data.get("company_phone", ""),
        "company_email": data.get("company_email", ""),
        "company_website": data.get("company_website", ""),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.white_label_partners.insert_one(partner)
    partner["_id"] = str(result.inserted_id)
    partner["created_at"] = now.isoformat()
    partner["updated_at"] = now.isoformat()
    return partner


@router.put("/{partner_id}")
async def update_partner(partner_id: str, data: dict):
    db = get_db()
    data.pop("_id", None)
    data.pop("created_at", None)
    data["updated_at"] = datetime.now(timezone.utc)
    result = await db.white_label_partners.find_one_and_update(
        {"_id": ObjectId(partner_id)},
        {"$set": data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Partner not found")
    return serialize_partner(result)


@router.delete("/{partner_id}")
async def delete_partner(partner_id: str):
    db = get_db()
    await db.white_label_partners.delete_one({"_id": ObjectId(partner_id)})
    # Unlink orgs
    await db.organizations.update_many(
        {"partner_id": partner_id},
        {"$unset": {"partner_id": ""}}
    )
    return {"status": "deleted"}


@router.post("/{partner_id}/assign-org/{org_id}")
async def assign_org_to_partner(partner_id: str, org_id: str):
    db = get_db()
    partner = await db.white_label_partners.find_one({"_id": ObjectId(partner_id)}, {"_id": 1})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"partner_id": partner_id}}
    )
    return {"status": "assigned"}


@router.post("/{partner_id}/unassign-org/{org_id}")
async def unassign_org_from_partner(partner_id: str, org_id: str):
    db = get_db()
    await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$unset": {"partner_id": ""}}
    )
    return {"status": "unassigned"}


@router.get("/{partner_id}/orgs")
async def get_partner_orgs(partner_id: str):
    db = get_db()
    orgs = await db.organizations.find(
        {"partner_id": partner_id},
        {"_id": 1, "name": 1, "slug": 1}
    ).to_list(200)
    for o in orgs:
        o["_id"] = str(o["_id"])
    return orgs


@router.get("/by-slug/{slug}")
async def get_partner_by_slug(slug: str):
    """Public endpoint to get partner branding by slug."""
    db = get_db()
    p = await db.white_label_partners.find_one({"slug": slug, "is_active": True})
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    return serialize_partner(p)
