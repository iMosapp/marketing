"""Met-At campaigns API: groups by where the rep met people, a preview of who joins a campaign, and the batch enroll (after the rep's yes)."""
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from routers.database import get_db
from services import met_at

router = APIRouter(prefix="/met-at", tags=["met-at"])


class EnrollBody(BaseModel):
    campaign_id: str
    event: str
    contact_ids: Optional[List[str]] = None


@router.get("/{user_id}/events")
async def list_events(user_id: str):
    return {"events": await met_at.events(get_db(), user_id)}


@router.get("/{user_id}/preview")
async def preview(user_id: str, campaign_id: str, event: str):
    return await met_at.preview(get_db(), user_id, campaign_id, event)


@router.post("/{user_id}/enroll")
async def enroll(user_id: str, body: EnrollBody):
    return await met_at.enroll(get_db(), user_id, body.campaign_id, body.event, body.contact_ids)
