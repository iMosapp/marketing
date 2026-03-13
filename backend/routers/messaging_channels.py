"""
Messaging Channels API — Configures which share channels are available per organization.
"""
from fastapi import APIRouter, HTTPException, Body
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import BaseModel
from typing import List, Optional
import logging

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/messaging-channels", tags=["messaging-channels"])

# All available channels with metadata
AVAILABLE_CHANNELS = [
    {"id": "sms", "name": "SMS / iMessage", "icon": "chatbubble-ellipses", "color": "#34C759",
     "description": "Native text messaging via phone's SMS app",
     "url_scheme": "sms:{phone}?body={message}", "requires_phone": True},
    {"id": "whatsapp", "name": "WhatsApp", "icon": "logo-whatsapp", "color": "#25D366",
     "description": "Send via WhatsApp — most popular messaging app worldwide",
     "url_scheme": "https://wa.me/{phone_clean}?text={message}", "requires_phone": True},
    {"id": "messenger", "name": "Facebook Messenger", "icon": "logo-facebook", "color": "#0084FF",
     "description": "Send via Facebook Messenger",
     "url_scheme": "fb-messenger://share/?link={link}", "requires_phone": False},
    {"id": "telegram", "name": "Telegram", "icon": "paper-plane", "color": "#0088CC",
     "description": "Send via Telegram messaging",
     "url_scheme": "https://t.me/share/url?url={link}&text={message}", "requires_phone": False},
    {"id": "linkedin", "name": "LinkedIn", "icon": "logo-linkedin", "color": "#0A66C2",
     "description": "Share via LinkedIn messaging",
     "url_scheme": "https://www.linkedin.com/messaging/compose?body={message}", "requires_phone": False},
    {"id": "email", "name": "Email", "icon": "mail", "color": "#FF9500",
     "description": "Send via email (already built-in)",
     "url_scheme": "mailto:{email}?body={message}", "requires_phone": False},
    {"id": "clipboard", "name": "Copy to Clipboard", "icon": "copy", "color": "#8E8E93",
     "description": "Copy message to paste anywhere",
     "url_scheme": "clipboard", "requires_phone": False},
]


@router.get("/available")
async def get_available_channels():
    """Return all available messaging channels."""
    return AVAILABLE_CHANNELS


@router.get("/org/{org_id}")
async def get_org_channels(org_id: str):
    """Get the enabled messaging channels for an organization."""
    db = get_db()
    try:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"settings": 1})
    except Exception:
        raise HTTPException(400, "Invalid organization ID")
    if not org:
        raise HTTPException(404, "Organization not found")

    settings = org.get("settings", {})
    enabled = settings.get("messaging_channels", ["sms"])
    return {"org_id": org_id, "enabled_channels": enabled, "available": AVAILABLE_CHANNELS}


@router.put("/org/{org_id}")
async def update_org_channels(org_id: str, data: dict = Body(...)):
    """Update the enabled messaging channels for an organization."""
    db = get_db()
    channels = data.get("channels", [])
    valid_ids = {c["id"] for c in AVAILABLE_CHANNELS}
    invalid = [c for c in channels if c not in valid_ids]
    if invalid:
        raise HTTPException(400, f"Invalid channel IDs: {invalid}")

    try:
        result = await db.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {"$set": {"settings.messaging_channels": channels, "settings.messaging_channels_updated_at": datetime.now(timezone.utc)}}
        )
    except Exception:
        raise HTTPException(400, "Invalid organization ID")
    if result.matched_count == 0:
        raise HTTPException(404, "Organization not found")
    return {"status": "updated", "enabled_channels": channels}


@router.get("/user/{user_id}")
async def get_user_channels(user_id: str):
    """Get the messaging channels for a user's organization (falls back to defaults)."""
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"organization_id": 1, "settings": 1})
    except Exception:
        raise HTTPException(400, "Invalid user ID")
    if not user:
        raise HTTPException(404, "User not found")

    # Check org-level config
    org_id = user.get("organization_id")
    enabled = ["sms"]  # default

    if org_id:
        try:
            org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"settings.messaging_channels": 1})
            if org and org.get("settings", {}).get("messaging_channels"):
                enabled = org["settings"]["messaging_channels"]
        except Exception:
            pass

    # Return only the enabled channel metadata
    channel_map = {c["id"]: c for c in AVAILABLE_CHANNELS}
    enabled_details = [channel_map[ch] for ch in enabled if ch in channel_map]
    return {"user_id": user_id, "org_id": org_id, "enabled_channels": enabled, "channels": enabled_details}
