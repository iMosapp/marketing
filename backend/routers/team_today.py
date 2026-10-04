"""Team today: the manager's morning digest (every rep's follow-ups for today) and manager -> rep nudges."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db
from services import team_today as tt

router = APIRouter(prefix="/team-today", tags=["Team today"], dependencies=[Depends(require_user)])


def _manager(request: Request) -> dict:
    user = request.state.user
    if not tt.is_manager(user):
        raise HTTPException(status_code=403, detail="Team today is for store managers")
    return user


@router.get("")
async def team_today(request: Request):
    me = _manager(request)
    digest = await tt.build(get_db(), me)
    return {**digest, "spoken": tt.spoken(digest)}


class NudgeBody(BaseModel):
    rep_user_id: str
    contact_id: str
    note: Optional[str] = ""


@router.post("/nudge")
async def nudge(body: NudgeBody, request: Request):
    me = _manager(request)
    db = get_db()
    if body.rep_user_id not in {r["user_id"] for r in await tt.reps_for(db, me)}:
        raise HTTPException(status_code=403, detail="That rep is not on your team")
    out = await tt.nudge(db, me, body.rep_user_id, body.contact_id, (body.note or "").strip()[:300])
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error") or "Could not nudge")
    return out
