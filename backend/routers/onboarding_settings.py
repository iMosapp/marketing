"""
Onboarding Settings Router
Manages branding, welcome messages, and onboarding configuration for stores/organizations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

from routers.database import get_db

router = APIRouter(prefix="/onboarding-settings", tags=["Onboarding Settings"])


# ============= MODELS =============

class OnboardingMessages(BaseModel):
    welcome_sms: str = "Welcome to the team! 🎉 Click here to start your training: {training_link}"
    training_complete_sms: str = "Congrats on completing your training! 🎓 You're ready to start closing deals. Now share this link with your team: {team_invite_link}"
    team_invite_sms: str = "You've been invited to join the team! 📱 Download the app and get started: {app_link}"
    team_welcome_sms: str = "Welcome aboard! 🚀 Complete your training to unlock all features: {training_link}"


class AppLinks(BaseModel):
    app_store_url: str = ""
    google_play_url: str = ""
    web_app_url: str = ""


class BrandingSettings(BaseModel):
    logo_url: Optional[str] = None
    primary_color: str = "#C9A962"
    secondary_color: str = "#1A1A2E"
    accent_color: str = "#34C759"
    company_name: Optional[str] = None


class OnboardingSettingsModel(BaseModel):
    messages: OnboardingMessages = OnboardingMessages()
    app_links: AppLinks = AppLinks()
    branding: BrandingSettings = BrandingSettings()
    training_required: bool = True
    auto_send_welcome_sms: bool = True
    auto_send_team_invite: bool = True


class OnboardingSettingsUpdate(BaseModel):
    messages: Optional[dict] = None
    app_links: Optional[dict] = None
    branding: Optional[dict] = None
    training_required: Optional[bool] = None
    auto_send_welcome_sms: Optional[bool] = None
    auto_send_team_invite: Optional[bool] = None


# ============= DEFAULT SETTINGS =============

DEFAULT_SETTINGS = {
    "messages": {
        "welcome_sms": "Welcome to the team! 🎉 Click here to start your training: {training_link}",
        "training_complete_sms": "Congrats on completing your training! 🎓 You're ready to start closing deals. Now share this link with your team: {team_invite_link}",
        "team_invite_sms": "You've been invited to join the team! 📱 Download the app and get started: {app_link}",
        "team_welcome_sms": "Welcome aboard! 🚀 Complete your training to unlock all features: {training_link}",
    },
    "app_links": {
        "app_store_url": "",
        "google_play_url": "",
        "web_app_url": "",
    },
    "branding": {
        "logo_url": None,
        "primary_color": "#C9A962",
        "secondary_color": "#1A1A2E",
        "accent_color": "#34C759",
        "company_name": None,
    },
    "training_required": True,
    "auto_send_welcome_sms": True,
    "auto_send_team_invite": True,
}


# ============= ENDPOINTS =============

@router.get("/store/{store_id}")
async def get_store_onboarding_settings(store_id: str):
    """Get onboarding settings for a specific store"""
    db = get_db()
    
    # First check if store exists
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Check for store-specific settings
    settings = await db.onboarding_settings.find_one({"store_id": store_id})
    
    if settings:
        settings["_id"] = str(settings["_id"])
        return settings
    
    # Check for organization-level settings
    if store.get("organization_id"):
        org_settings = await db.onboarding_settings.find_one({
            "organization_id": store["organization_id"],
            "store_id": None
        })
        if org_settings:
            org_settings["_id"] = str(org_settings["_id"])
            org_settings["inherited_from"] = "organization"
            return org_settings
    
    # Return defaults with store info
    return {
        **DEFAULT_SETTINGS,
        "store_id": store_id,
        "inherited_from": "defaults",
    }


@router.put("/store/{store_id}")
async def update_store_onboarding_settings(store_id: str, settings: OnboardingSettingsUpdate):
    """Update onboarding settings for a specific store"""
    db = get_db()
    
    # Verify store exists
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get existing settings or create new
    existing = await db.onboarding_settings.find_one({"store_id": store_id})
    
    update_data = settings.dict(exclude_none=True)
    update_data["updated_at"] = datetime.utcnow()
    
    if existing:
        # Merge with existing settings
        for key, value in update_data.items():
            if isinstance(value, dict) and key in existing:
                existing[key] = {**existing.get(key, {}), **value}
            else:
                existing[key] = value
        
        await db.onboarding_settings.update_one(
            {"_id": existing["_id"]},
            {"$set": existing}
        )
        existing["_id"] = str(existing["_id"])
        return existing
    else:
        # Create new settings
        new_settings = {
            **DEFAULT_SETTINGS,
            **update_data,
            "store_id": store_id,
            "organization_id": store.get("organization_id"),
            "created_at": datetime.utcnow(),
        }
        result = await db.onboarding_settings.insert_one(new_settings)
        new_settings["_id"] = str(result.inserted_id)
        return new_settings


@router.get("/organization/{org_id}")
async def get_organization_onboarding_settings(org_id: str):
    """Get onboarding settings for an organization (applies to all stores unless overridden)"""
    db = get_db()
    
    # Verify org exists
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check for org-level settings
    settings = await db.onboarding_settings.find_one({
        "organization_id": org_id,
        "store_id": None
    })
    
    if settings:
        settings["_id"] = str(settings["_id"])
        return settings
    
    # Return defaults
    return {
        **DEFAULT_SETTINGS,
        "organization_id": org_id,
        "inherited_from": "defaults",
    }


@router.put("/organization/{org_id}")
async def update_organization_onboarding_settings(org_id: str, settings: OnboardingSettingsUpdate):
    """Update onboarding settings for an organization"""
    db = get_db()
    
    # Verify org exists
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get existing settings or create new
    existing = await db.onboarding_settings.find_one({
        "organization_id": org_id,
        "store_id": None
    })
    
    update_data = settings.dict(exclude_none=True)
    update_data["updated_at"] = datetime.utcnow()
    
    if existing:
        # Merge with existing settings
        for key, value in update_data.items():
            if isinstance(value, dict) and key in existing:
                existing[key] = {**existing.get(key, {}), **value}
            else:
                existing[key] = value
        
        await db.onboarding_settings.update_one(
            {"_id": existing["_id"]},
            {"$set": existing}
        )
        existing["_id"] = str(existing["_id"])
        return existing
    else:
        # Create new settings
        new_settings = {
            **DEFAULT_SETTINGS,
            **update_data,
            "organization_id": org_id,
            "store_id": None,
            "created_at": datetime.utcnow(),
        }
        result = await db.onboarding_settings.insert_one(new_settings)
        new_settings["_id"] = str(result.inserted_id)
        return new_settings


@router.get("/global")
async def get_global_onboarding_settings():
    """Get global/platform-wide onboarding settings (super admin only)"""
    db = get_db()
    
    settings = await db.onboarding_settings.find_one({
        "organization_id": None,
        "store_id": None,
        "is_global": True
    })
    
    if settings:
        settings["_id"] = str(settings["_id"])
        return settings
    
    return {
        **DEFAULT_SETTINGS,
        "is_global": True,
        "inherited_from": "defaults",
    }


@router.put("/global")
async def update_global_onboarding_settings(settings: OnboardingSettingsUpdate):
    """Update global/platform-wide onboarding settings (super admin only)"""
    db = get_db()
    
    existing = await db.onboarding_settings.find_one({
        "organization_id": None,
        "store_id": None,
        "is_global": True
    })
    
    update_data = settings.dict(exclude_none=True)
    update_data["updated_at"] = datetime.utcnow()
    
    if existing:
        # Merge with defaults first to ensure all keys exist
        merged = {**DEFAULT_SETTINGS}
        for key in DEFAULT_SETTINGS:
            if key in existing:
                if isinstance(existing[key], dict):
                    merged[key] = {**DEFAULT_SETTINGS.get(key, {}), **existing[key]}
                else:
                    merged[key] = existing[key]
        
        # Then apply updates
        for key, value in update_data.items():
            if isinstance(value, dict) and key in merged:
                merged[key] = {**merged.get(key, {}), **value}
            else:
                merged[key] = value
        
        merged["_id"] = existing["_id"]
        merged["is_global"] = True
        
        await db.onboarding_settings.update_one(
            {"_id": existing["_id"]},
            {"$set": merged}
        )
        merged["_id"] = str(merged["_id"])
        return merged
    else:
        new_settings = {
            **DEFAULT_SETTINGS,
            **update_data,
            "organization_id": None,
            "store_id": None,
            "is_global": True,
            "created_at": datetime.utcnow(),
        }
        result = await db.onboarding_settings.insert_one(new_settings)
        new_settings["_id"] = str(result.inserted_id)
        return new_settings


# ============= MESSAGE PREVIEW =============

@router.post("/preview-message")
async def preview_message(data: dict):
    """
    Preview a message with placeholder values filled in.
    Useful for showing admins what messages will look like.
    """
    message_template = data.get("template", "")
    
    # Sample placeholder values
    placeholders = {
        "{training_link}": "https://app.mvpline.com/train/abc123",
        "{team_invite_link}": "https://app.mvpline.com/join/xyz789",
        "{app_link}": "https://app.mvpline.com/download",
        "{user_name}": "John Smith",
        "{store_name}": "Premier Auto Group",
        "{admin_name}": "Forest Johnson",
    }
    
    # Replace placeholders
    preview = message_template
    for placeholder, value in placeholders.items():
        preview = preview.replace(placeholder, value)
    
    return {
        "original": message_template,
        "preview": preview,
        "placeholders_used": [p for p in placeholders.keys() if p in message_template]
    }


# ============= AVAILABLE PLACEHOLDERS =============

@router.get("/placeholders")
async def get_available_placeholders():
    """Get list of available placeholders for message templates"""
    return {
        "placeholders": [
            {"key": "{training_link}", "description": "Link to the user's training portal"},
            {"key": "{team_invite_link}", "description": "Link for inviting team members"},
            {"key": "{app_link}", "description": "Link to download the mobile app"},
            {"key": "{user_name}", "description": "The recipient's name"},
            {"key": "{store_name}", "description": "The store/dealership name"},
            {"key": "{admin_name}", "description": "The admin who created the account"},
            {"key": "{company_name}", "description": "The organization/company name"},
        ]
    }
