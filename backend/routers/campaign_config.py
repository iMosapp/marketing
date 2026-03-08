"""
Campaign Configuration Router
Store-level (account-level) campaign configuration with org override.
Controls whether campaigns use AI-suggested messages or hard-coded templates,
and how sequences are built.
"""
from fastapi import APIRouter, HTTPException, Body
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db

router = APIRouter(prefix="/campaign-config", tags=["Campaign Config"])
logger = logging.getLogger(__name__)

# Default config if none is set
DEFAULT_CONFIG = {
    "message_mode": "ai_suggested",  # ai_suggested | template | hybrid
    "sequence_mode": "preset_timing",  # preset_timing (use set dates) | ai_full (AI decides everything)
    "auto_enroll_on_tag": True,  # auto-enroll in campaigns when tag is applied
    "review_before_send": True,  # salesperson must review before sending (manual deploy)
    "auto_send": False,  # fully automatic (requires Twilio)
    "default_channel": "sms",  # sms | email | both
    "ai_tone": "casual",  # casual | professional | warm
    "include_personal_details": True,  # Use voice memo intel in AI messages
    "include_engagement_signals": True,  # Use engagement data in AI messages
}


async def get_effective_config(user_id: str = None, store_id: str = None, org_id: str = None) -> dict:
    """
    Get the effective campaign configuration.
    Priority: user override > store config > org config > defaults

    Most configs live at the store (account) level.
    Org can set a baseline. Users can override if permitted.
    """
    db = get_db()
    config = {**DEFAULT_CONFIG}

    # 1. Org-level config (baseline)
    if org_id:
        org_config = await db.campaign_configs.find_one(
            {"level": "org", "entity_id": org_id},
            {"_id": 0, "config": 1}
        )
        if org_config and org_config.get("config"):
            config.update(org_config["config"])

    # 2. Store-level config (primary)
    if store_id:
        store_config = await db.campaign_configs.find_one(
            {"level": "store", "entity_id": store_id},
            {"_id": 0, "config": 1}
        )
        if store_config and store_config.get("config"):
            config.update(store_config["config"])

    # 3. User-level override (if permitted)
    if user_id:
        user_config = await db.campaign_configs.find_one(
            {"level": "user", "entity_id": user_id},
            {"_id": 0, "config": 1}
        )
        if user_config and user_config.get("config"):
            # Only apply user overrides if the store/org allows it
            if config.get("allow_user_override", True):
                config.update(user_config["config"])

    return config


@router.get("/effective/{user_id}")
async def get_user_effective_config(user_id: str):
    """Get the resolved campaign config for a user (accounts for org/store/user hierarchy)."""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "organization_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    config = await get_effective_config(
        user_id=user_id,
        store_id=user.get("store_id"),
        org_id=user.get("organization_id"),
    )

    return {
        "config": config,
        "level_applied": "effective",
        "user_id": user_id,
        "store_id": user.get("store_id"),
        "org_id": user.get("organization_id"),
    }


@router.get("/{level}/{entity_id}")
async def get_config(level: str, entity_id: str):
    """Get the campaign configuration for a specific level (org, store, or user)."""
    if level not in ("org", "store", "user"):
        raise HTTPException(status_code=400, detail="Level must be org, store, or user")

    db = get_db()
    doc = await db.campaign_configs.find_one(
        {"level": level, "entity_id": entity_id},
        {"_id": 0}
    )

    if not doc:
        return {"config": DEFAULT_CONFIG, "level": level, "entity_id": entity_id, "is_default": True}

    return {"config": doc.get("config", DEFAULT_CONFIG), "level": level, "entity_id": entity_id, "is_default": False}


@router.put("/{level}/{entity_id}")
async def set_config(level: str, entity_id: str, data: dict = Body(...)):
    """Set campaign configuration at a specific level."""
    if level not in ("org", "store", "user"):
        raise HTTPException(status_code=400, detail="Level must be org, store, or user")

    config = data.get("config", {})
    valid_keys = set(DEFAULT_CONFIG.keys()) | {"allow_user_override"}

    # Only allow known keys
    clean_config = {k: v for k, v in config.items() if k in valid_keys}

    db = get_db()
    now = datetime.now(timezone.utc)

    await db.campaign_configs.update_one(
        {"level": level, "entity_id": entity_id},
        {"$set": {
            "level": level,
            "entity_id": entity_id,
            "config": clean_config,
            "updated_at": now,
        },
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    logger.info(f"Campaign config updated: level={level}, entity={entity_id}, keys={list(clean_config.keys())}")
    return {"message": "Configuration saved", "config": clean_config}


@router.delete("/{level}/{entity_id}")
async def reset_config(level: str, entity_id: str):
    """Reset a level's config back to defaults (removes the override)."""
    db = get_db()
    result = await db.campaign_configs.delete_one({"level": level, "entity_id": entity_id})
    if result.deleted_count == 0:
        return {"message": "No custom config found (already using defaults)"}
    return {"message": f"Config reset to defaults for {level}/{entity_id}"}
