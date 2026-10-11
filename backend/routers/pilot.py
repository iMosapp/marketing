"""Stage 3: the pilot user's own onboarding checklist. Pilot = any user whose organization carries customer.pilot."""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from routers.database import get_db
from routers.rbac import get_current_user
from services import customers as cust
from services import pilot as svc

router = APIRouter(prefix="/pilot", tags=["Pilot"])


@router.get("/checklist")
async def my_checklist(me: dict = Depends(get_current_user)):
    db = get_db()
    org = await cust.customer_org(db, me.get("organization_id"))
    if not org or not (org.get("customer") or {}).get("pilot"):
        raise HTTPException(status_code=404, detail="Not a pilot account")
    user = await db.users.find_one({"_id": ObjectId(str(me["_id"]))})
    return {**await svc.checklist(db, user), "business_name": org.get("name")}
