"""
AI-Powered Outreach Router
Endpoints for viewing, accepting, and dismissing AI-generated follow-up suggestions.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db

router = APIRouter(prefix="/ai-outreach", tags=["AI Outreach"])
logger = logging.getLogger(__name__)


@router.get("/suggestions/{user_id}")
async def get_suggestions(user_id: str, status: str = "pending"):
    """Get AI outreach suggestions for a user. status: pending, accepted, dismissed, all"""
    db = get_db()
    query = {"user_id": user_id}
    if status != "all":
        query["status"] = status

    records = await db.ai_outreach.find(query).sort("created_at", -1).limit(50).to_list(50)

    result = []
    for r in records:
        r["_id"] = str(r["_id"])
        if isinstance(r.get("scheduled_for"), datetime):
            r["scheduled_for"] = r["scheduled_for"].isoformat()
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("updated_at"), datetime):
            r["updated_at"] = r["updated_at"].isoformat()
        result.append(r)

    return {"suggestions": result, "total": len(result)}


@router.post("/suggestions/{record_id}/accept")
async def accept_suggestion(record_id: str, data: dict):
    """Accept a suggestion and create a scheduled task."""
    suggestion_index = data.get("suggestion_index", 0)

    from services.ai_outreach_service import accept_suggestion as do_accept
    try:
        result = do_accept(record_id, suggestion_index)
        # Handle if it's a coroutine
        import asyncio
        if asyncio.iscoroutine(result):
            result = await result
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error accepting suggestion: {e}")
        raise HTTPException(status_code=500, detail="Failed to accept suggestion")


@router.post("/suggestions/{record_id}/dismiss")
async def dismiss_suggestion(record_id: str):
    """Dismiss an AI outreach suggestion."""
    db = get_db()
    record = await db.ai_outreach.find_one({"_id": ObjectId(record_id)})
    if not record:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if record["status"] != "pending":
        raise HTTPException(status_code=400, detail="Already actioned")

    await db.ai_outreach.update_one(
        {"_id": ObjectId(record_id)},
        {"$set": {"status": "dismissed", "updated_at": datetime.now(timezone.utc)}}
    )

    return {"message": "Suggestion dismissed"}


@router.post("/generate/{user_id}/{contact_id}")
async def manually_generate(user_id: str, contact_id: str):
    """Manually trigger AI outreach generation for a contact."""
    db = get_db()

    # Verify contact exists
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Unknown"

    from services.ai_outreach_service import create_outreach_record
    try:
        record_id = await create_outreach_record(user_id, contact_id, contact_name)
        return {"record_id": record_id, "message": f"AI suggestions generated for {contact_name}"}
    except Exception as e:
        logger.error(f"Error generating outreach: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@router.get("/stats/{user_id}")
async def get_outreach_stats(user_id: str):
    """Get AI outreach statistics for a user."""
    db = get_db()
    pending = await db.ai_outreach.count_documents({"user_id": user_id, "status": "pending"})
    accepted = await db.ai_outreach.count_documents({"user_id": user_id, "status": "accepted"})
    dismissed = await db.ai_outreach.count_documents({"user_id": user_id, "status": "dismissed"})

    return {
        "pending": pending,
        "accepted": accepted,
        "dismissed": dismissed,
        "total": pending + accepted + dismissed,
    }


@router.get("/relationship-brief/{user_id}/{contact_id}")
async def get_relationship_brief(user_id: str, contact_id: str):
    """Get the full relationship intelligence brief for a contact."""
    from services.relationship_intel import build_relationship_brief
    try:
        brief = await build_relationship_brief(user_id, contact_id)
        return {
            "contact_name": brief["contact"].get("name", ""),
            "relationship_health": brief["relationship_health"],
            "engagement_score": brief["engagement_score"],
            "response_pattern": brief["response_pattern"],
            "last_interaction_days": brief["last_interaction_days"],
            "milestones": brief["milestones"],
            "engagement_signals": brief["engagement_signals"][:5],
            "previous_campaign_messages": brief["previous_campaign_messages"][:5],
            "human_summary": brief["human_summary"],
            "days_since_sale": brief.get("days_since_sale"),
            "days_known": brief.get("days_known"),
            "personal_details": brief.get("personal_details", {}),
        }
    except Exception as e:
        logger.error(f"Failed to build relationship brief: {e}")
        raise HTTPException(status_code=500, detail="Failed to build relationship brief")
