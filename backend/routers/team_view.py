"""My Team (read-only manager view, services/team_view.py): org admins see their organization, location managers their location,
super admins any organization by id. Scope is enforced here on the server, never by the app."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from routers.contact_ask import require_user
from routers.database import get_db
from services import team_view as svc

router = APIRouter(prefix="/team-view", tags=["My Team"], dependencies=[Depends(require_user)])


@router.get("")
async def my_team(request: Request, org_id: Optional[str] = None):
    try:
        return await svc.team(get_db(), request.state.user, org_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
