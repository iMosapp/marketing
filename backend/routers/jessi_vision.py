"""Super-admin controls for Jessi's photo understanding (MMS Stage 2): the single global switch and the cost log."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db
from services import mms_vision

router = APIRouter(prefix="/jessi-vision", tags=["Jessi Vision"], dependencies=[Depends(require_user)])


class SwitchBody(BaseModel):
    enabled: bool


def _super(request: Request) -> dict:
    me = request.state.user
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    return me


@router.get("/settings")
async def get_switch(request: Request):
    _super(request)
    doc = await get_db().settings.find_one({"key": mms_vision.SETTINGS_KEY}, {"_id": 0}) or {}
    return {"enabled": bool(doc.get("enabled")), "updated_at": doc.get("updated_at"), "updated_by": doc.get("updated_by"), "model": "openai/gpt-5.4"}


@router.put("/settings")
async def put_switch(body: SwitchBody, request: Request):
    me = _super(request)
    await get_db().settings.update_one({"key": mms_vision.SETTINGS_KEY}, {"$set": {
        "key": mms_vision.SETTINGS_KEY, "enabled": body.enabled, "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": str(me.get("_id") or me.get("id") or "")}}, upsert=True)
    return await get_switch(request)


@router.get("/usage")
async def usage(request: Request, days: int = 30):
    """Photos read and estimated cost per organization (no cap, log only)."""
    _super(request)
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
    rows = await get_db().vision_usage.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$organization_id", "images": {"$sum": 1}, "model_calls": {"$sum": {"$cond": ["$cached", 0, 1]}},
                    "failed": {"$sum": {"$cond": ["$ok", 0, 1]}}, "est_cost_usd": {"$sum": "$est_cost_usd"}}},
        {"$sort": {"est_cost_usd": -1}},
    ]).to_list(500)
    orgs = [{"organization_id": r["_id"], "images": r["images"], "model_calls": r["model_calls"], "failed": r["failed"],
             "est_cost_usd": round(r["est_cost_usd"], 4)} for r in rows]
    return {"days": days, "organizations": orgs, "total_est_cost_usd": round(sum(o["est_cost_usd"] for o in orgs), 4)}
