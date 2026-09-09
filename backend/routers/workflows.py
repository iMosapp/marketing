"""Workflows API: what happens when a contact is tagged (store-wide rulebook). Managers edit, reps view."""
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from services import tag_workflows as tw


async def require_user(request: Request) -> dict:
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user = user
    return user


router = APIRouter(prefix="/workflows", tags=["Workflows"], dependencies=[Depends(require_user)])


class WorkflowUpdate(BaseModel):
    jessi_mode: Optional[str] = None          # auto_reply | draft_only | off
    campaign_ids: Optional[list] = None       # None = auto (by trigger tag)
    stop_tags: Optional[list] = None
    stop_campaigns: Optional[bool] = None
    clear_hot: Optional[bool] = None


def _same_scope(actor: dict, target: dict) -> bool:
    if actor.get("role") == "super_admin":
        return True
    return tw.scope_key(actor) == tw.scope_key(target) or str(actor["_id"]) == str(target["_id"])


async def _target(request: Request, user_id: str) -> dict:
    actor = request.state.user
    target = await tw._user(get_db(), user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target["_id"] = ObjectId(user_id)
    if not _same_scope(actor, target):
        raise HTTPException(status_code=403, detail="Not your store")
    return target


@router.get("/{user_id}")
async def list_workflows(user_id: str, request: Request):
    db = get_db()
    target = await _target(request, user_id)
    editable = tw.can_edit(request.state.user)
    campaigns = await tw.visible_campaigns(db, target)
    tags = list(tw.KNOWN_TAGS.keys())
    async for doc in db[tw.COLL].find({"scope_key": tw.scope_key(target)}, {"tag": 1}):
        if doc["tag"] not in tags:
            tags.append(doc["tag"])
    for c in campaigns:  # any other tag-triggered campaign shows up too
        t = (c.get("trigger_tag") or "").lower()
        if t and t not in tags:
            tags.append(t)
    out = [tw.serialize_workflow(await tw.get_workflow(db, target, t, campaigns), editable) for t in tags]
    store = None
    sid = target.get("store_id")
    if sid and ObjectId.is_valid(str(sid)):
        store = await db.stores.find_one({"_id": ObjectId(str(sid))}, {"name": 1})
    return {"scope": {"key": tw.scope_key(target), "store_name": (store or {}).get("name"), "shared": tw.scope_key(target).startswith("store:")},
            "editable": editable, "workflows": out}


@router.get("/{user_id}/campaign-options")
async def campaign_options(user_id: str, request: Request):
    db = get_db()
    target = await _target(request, user_id)
    camps = await tw.visible_campaigns(db, target)
    return {"campaigns": [{"id": str(c["_id"]), "name": c.get("name"), "trigger_tag": c.get("trigger_tag"), "steps": len(c.get("sequences") or []),
                          "ai_enabled": bool(c.get("ai_enabled")), "scope": tw._campaign_scope(c), "type": c.get("type")} for c in camps]}


@router.get("/{user_id}/{tag}")
async def get_workflow(user_id: str, tag: str, request: Request):
    db = get_db()
    target = await _target(request, user_id)
    return tw.serialize_workflow(await tw.get_workflow(db, target, tag), tw.can_edit(request.state.user))


@router.put("/{user_id}/{tag}")
async def save_workflow(user_id: str, tag: str, body: WorkflowUpdate, request: Request):
    actor = request.state.user
    if not tw.can_edit(actor):
        raise HTTPException(status_code=403, detail="Only store managers and admins can change workflows")
    db = get_db()
    target = await _target(request, user_id)
    tag = tag.lower().strip()
    if tag in tw.DATE_OPTIN_TAGS:
        raise HTTPException(status_code=400, detail="Birthday and Anniversary are date-based and not editable here")
    if body.jessi_mode is not None and body.jessi_mode not in tw.JESSI_MODES:
        raise HTTPException(status_code=400, detail="jessi_mode must be auto_reply, draft_only or off")
    update = {k: v for k, v in body.dict().items() if v is not None}
    if "campaign_ids" in update:
        update["campaign_ids"] = [str(i) for i in update["campaign_ids"] if ObjectId.is_valid(str(i))]
    if "stop_tags" in update:
        update["stop_tags"] = [str(t).strip() for t in update["stop_tags"] if str(t).strip()]
    update.update({"updated_at": datetime.utcnow(), "updated_by": str(actor["_id"]), "updated_by_name": actor.get("name") or actor.get("email")})
    await db[tw.COLL].update_one({"scope_key": tw.scope_key(target), "tag": tag}, {"$set": update, "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True)
    return tw.serialize_workflow(await tw.get_workflow(db, target, tag), True)


@router.delete("/{user_id}/{tag}")
async def reset_workflow(user_id: str, tag: str, request: Request):
    """Back to the built-in defaults for this tag."""
    if not tw.can_edit(request.state.user):
        raise HTTPException(status_code=403, detail="Only store managers and admins can change workflows")
    db = get_db()
    target = await _target(request, user_id)
    await db[tw.COLL].delete_one({"scope_key": tw.scope_key(target), "tag": tag.lower().strip()})
    return tw.serialize_workflow(await tw.get_workflow(db, target, tag), True)
