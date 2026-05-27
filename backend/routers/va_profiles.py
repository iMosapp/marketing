"""
VA Profile Library — named, reusable Virtual Assistant personas.
Each profile has a name, bio, specialties, tone, and optional full custom prompt.
Profiles can be assigned to lead sources so each intake channel has its own personality.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId
import logging

from routers.database import get_db

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/va-profiles", tags=["va-profiles"])

AVATAR_COLORS = ["#007AFF","#34C759","#FF9500","#AF52DE","#FF3B30","#C9A962","#5856D6","#FF2D55"]


class VAProfileCreate(BaseModel):
    name:            str
    tagline:         Optional[str]  = ""         # Short description, e.g. "Truck & off-road specialist"
    bio:             Optional[str]  = ""         # Who this VA is — used in system prompt
    specialties:     Optional[str]  = ""         # What they focus on
    tone:            Optional[str]  = "friendly" # Communication style
    never_say:       Optional[str]  = ""         # Forbidden phrases/topics
    custom_prompt:   Optional[str]  = ""         # Full override (replaces everything if set)
    avatar_color:    Optional[str]  = "#007AFF"


class VAProfileUpdate(VAProfileCreate):
    pass


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    for f in ("created_at", "updated_at"):
        if isinstance(doc.get(f), datetime):
            doc[f] = doc[f].isoformat()
    return doc


@router.get("")
async def list_va_profiles(x_user_id: str = Header(None, alias="X-User-ID")):
    """List all VA profiles visible to this user."""
    db = get_db()
    profiles = await db.ai_va_profiles.find(
        {"$or": [{"user_id": x_user_id}, {"scope": "global"}]}
    ).sort("created_at", -1).to_list(200)
    return {"profiles": [_serialize(p) for p in profiles]}


@router.post("")
async def create_va_profile(
    data: VAProfileCreate,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Create a new VA profile."""
    db  = get_db()
    now = datetime.utcnow()
    doc = {
        "user_id":      x_user_id,
        "name":         data.name.strip(),
        "tagline":      data.tagline or "",
        "bio":          data.bio or "",
        "specialties":  data.specialties or "",
        "tone":         data.tone or "friendly",
        "never_say":    data.never_say or "",
        "custom_prompt":data.custom_prompt or "",
        "avatar_color": data.avatar_color or AVATAR_COLORS[0],
        "created_at":   now,
        "updated_at":   now,
    }
    result = await db.ai_va_profiles.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return {"success": True, "profile": _serialize(doc)}


@router.put("/{profile_id}")
async def update_va_profile(
    profile_id: str,
    data: VAProfileUpdate,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    db = get_db()
    profile = await db.ai_va_profiles.find_one({"_id": ObjectId(profile_id)})
    if not profile:
        raise HTTPException(status_code=404, detail="VA profile not found")
    update = {
        "name":          data.name.strip(),
        "tagline":       data.tagline or "",
        "bio":           data.bio or "",
        "specialties":   data.specialties or "",
        "tone":          data.tone or "friendly",
        "never_say":     data.never_say or "",
        "custom_prompt": data.custom_prompt or "",
        "avatar_color":  data.avatar_color or AVATAR_COLORS[0],
        "updated_at":    datetime.utcnow(),
    }
    await db.ai_va_profiles.update_one({"_id": ObjectId(profile_id)}, {"$set": update})
    updated = await db.ai_va_profiles.find_one({"_id": ObjectId(profile_id)})
    return {"success": True, "profile": _serialize(updated)}


@router.delete("/{profile_id}")
async def delete_va_profile(profile_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    db = get_db()
    await db.ai_va_profiles.delete_one({"_id": ObjectId(profile_id), "user_id": x_user_id})
    return {"success": True}


@router.get("/{profile_id}/preview")
async def preview_va_profile(profile_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Generate a sample message from this VA profile for preview."""
    import os, asyncio as _aio
    db = get_db()
    profile = await db.ai_va_profiles.find_one({"_id": ObjectId(profile_id)})
    if not profile:
        raise HTTPException(status_code=404, detail="VA profile not found")

    try:
        from routers.ai_campaigns import build_clone_system_prompt
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid as _uuid

        # Build system prompt from this profile's data
        if profile.get("custom_prompt"):
            system_prompt = profile["custom_prompt"]
        else:
            # Build from fields
            bio = profile.get("bio", "")
            specialties = profile.get("specialties", "")
            tone = profile.get("tone", "friendly")
            never_say = profile.get("never_say", "")
            system_prompt = (
                f"You are a {tone} sales professional.\n"
                + (f"About you: {bio}\n" if bio else "")
                + (f"Your specialties: {specialties}\n" if specialties else "")
                + (f"Never say: {never_say}\n" if never_say else "")
                + "\nKeep your reply to 1-2 sentences. Be warm and natural."
            )

        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"va-preview-{_uuid.uuid4().hex[:10]}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")

        result = await _aio.wait_for(
            chat.send_message(UserMessage(text='A customer just texted: "Hey, I saw you had a truck available — what can you tell me about it?"')),
            timeout=10.0,
        )
        sample = (result.strip() if isinstance(result, str) else result.text.strip() if hasattr(result, "text") else "").strip('"\'')
        return {"sample_reply": sample}
    except Exception as e:
        return {"sample_reply": f"Preview failed: {e}"}
