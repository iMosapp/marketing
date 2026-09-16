"""Test Lab API (super admins): list the features waiting in the lab, flip one live for everyone."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import lab

router = APIRouter(prefix="/lab", tags=["Test Lab"], dependencies=[Depends(require_user)])


class StatusBody(BaseModel):
    status: str


async def _super(request: Request) -> dict:
    me = await _resolve(request)
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="The Test Lab is for the app owner")
    return me


@router.get("/features")
async def features(request: Request):
    await _super(request)
    return {"features": await lab.list_features(get_db())}


@router.put("/features/{key}")
async def set_status(key: str, body: StatusBody, request: Request):
    me = await _super(request)
    try:
        return await lab.set_status(get_db(), key, body.status, me)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
