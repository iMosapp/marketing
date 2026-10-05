"""Agent Hub API. Super admins build the library; every manager can read it to pick an agent for a widget, lead source or inbox."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.lead_sources import require_manager
from services import agents as AG

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["Agent Hub"])


async def require_super(request: Request) -> dict:
    user = await require_manager(request)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins build agents. You can still pick one for your widget, lead source or inbox.")
    return user


class AgentBody(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    tagline: Optional[str] = None
    avatar_color: Optional[str] = None
    photo_url: Optional[str] = None
    tone: Optional[str] = None
    brevity: Optional[str] = None
    emoji: Optional[str] = None
    goal: Optional[str] = None
    instructions: Optional[str] = None
    specialties: Optional[str] = None
    facts: Optional[List[str]] = None
    never_say: Optional[List[str]] = None
    hand_to_human: Optional[List[str]] = None
    always_collect: Optional[List[str]] = None
    language: Optional[str] = None
    custom_prompt: Optional[str] = None
    status: Optional[str] = None
    starter_key: Optional[str] = None


class TryBody(BaseModel):
    messages: List[dict] = []
    channel: str = "sms"
    store_id: Optional[str] = None


class DeployBody(BaseModel):
    kind: str
    target_id: str
    on: bool = True


async def _load(db, agent_id: str) -> dict:
    doc = await db[AG.COLL].find_one({"_id": AG._oid(agent_id)}) if AG._oid(agent_id) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    return doc


@router.get("")
async def list_agents(request: Request, include_archived: bool = False, _m: dict = Depends(require_manager)):
    db = get_db()
    q = {} if include_archived else {"status": {"$ne": "archived"}}
    docs = await db[AG.COLL].find(q).sort([("status", 1), ("name", 1)]).to_list(300)
    counts: dict = {}
    for coll, field in (("widgets", "persona.agent_id"), ("lead_sources", "agent_id"), ("shared_inboxes", "agent_id")):
        extra = {"persona.source": "agent"} if coll == "widgets" else {"kind": {"$nin": ["website_widget", "inbox_direct"]}} if coll == "lead_sources" else {}
        async for row in db[coll].aggregate([{"$match": {field: {"$in": [str(d["_id"]) for d in docs]}, **extra}}, {"$group": {"_id": f"${field}", "n": {"$sum": 1}}}]):
            counts[row["_id"]] = counts.get(row["_id"], 0) + row["n"]
    return {"agents": [{**AG.serialize(d), "used_count": counts.get(str(d["_id"]), 0)} for d in docs],
            "can_edit": request.state.user.get("role") == "super_admin", "starters": AG.STARTERS, "tones": list(AG.TONES), "languages": list(AG.LANGUAGES)}


@router.post("")
async def create_agent(body: AgentBody, request: Request, _s: dict = Depends(require_super)):
    db = get_db()
    data = body.model_dump(exclude_unset=True)
    key = data.pop("starter_key", None)
    starter = next((s for s in AG.STARTERS if s["key"] == key), None)
    doc = AG.normalize({**(starter or {}), **{k: v for k, v in data.items() if v is not None}})
    if not doc["name"]:
        raise HTTPException(status_code=400, detail="Give the agent a name")
    me = request.state.user
    doc.update({"starter_key": (starter or {}).get("key") or "", "created_by": str(me["_id"]), "created_by_name": me.get("name") or "", "created_at": AG._now(), "updated_at": AG._now()})
    res = await db[AG.COLL].insert_one(doc)
    return {"agent": AG.serialize({**doc, "_id": res.inserted_id}, used_by=[])}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, request: Request, _m: dict = Depends(require_manager)):
    db = get_db()
    doc = await _load(db, agent_id)
    return {"agent": AG.serialize(doc, used_by=await AG.used_by(db, agent_id)), "can_edit": request.state.user.get("role") == "super_admin"}


@router.put("/{agent_id}")
async def update_agent(agent_id: str, body: AgentBody, _s: dict = Depends(require_super)):
    db = get_db()
    doc = await _load(db, agent_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k != "starter_key"}
    merged = AG.normalize({**doc, **data})
    if not merged["name"]:
        raise HTTPException(status_code=400, detail="Give the agent a name")
    await db[AG.COLL].update_one({"_id": doc["_id"]}, {"$set": {**merged, "updated_at": AG._now()}})
    fresh = await db[AG.COLL].find_one({"_id": doc["_id"]})
    return {"agent": AG.serialize(fresh, used_by=await AG.used_by(db, agent_id))}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, _s: dict = Depends(require_super)):
    """Archive when the agent is deployed somewhere (so threads keep working), delete outright when it is not."""
    db = get_db()
    doc = await _load(db, agent_id)
    used = await AG.used_by(db, agent_id)
    if used:
        await db[AG.COLL].update_one({"_id": doc["_id"]}, {"$set": {"status": "archived", "updated_at": AG._now()}})
        return {"ok": True, "archived": True, "used_count": len(used)}
    await db[AG.COLL].delete_one({"_id": doc["_id"]})
    return {"ok": True, "archived": False}


@router.get("/{agent_id}/targets")
async def agent_targets(agent_id: str, _s: dict = Depends(require_super)):
    db = get_db()
    await _load(db, agent_id)
    return await AG.targets(db, agent_id)


@router.put("/{agent_id}/deploy")
async def deploy_agent(agent_id: str, body: DeployBody, _s: dict = Depends(require_super)):
    db = get_db()
    doc = await _load(db, agent_id)
    if body.on and doc.get("status") == "archived":
        raise HTTPException(status_code=400, detail="Unarchive the agent first")
    try:
        await AG.deploy(db, agent_id, body.kind, body.target_id, body.on)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "used_by": await AG.used_by(db, agent_id)}


@router.post("/{agent_id}/try")
async def try_agent(agent_id: str, body: TryBody, request: Request, _m: dict = Depends(require_manager)):
    db = get_db()
    doc = await _load(db, agent_id)
    agent = {**AG.normalize(doc), "_id": doc["_id"]}
    store = None
    sid = body.store_id or request.state.user.get("store_id")
    if sid and AG._oid(sid):
        store = await db.stores.find_one({"_id": AG._oid(sid)}, {"name": 1})
    try:
        reply = await AG.try_reply(agent, body.messages, "webchat" if body.channel == "webchat" else "sms", (store or {}).get("name") or "Demo Motors")
    except Exception as e:
        logger.warning(f"[Agents] try failed: {e}")
        raise HTTPException(status_code=502, detail=str(e)[:200] or "Jessi did not answer")
    return {"reply": reply}
