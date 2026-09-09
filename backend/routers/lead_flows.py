"""Lead Flows API: the store's library of reusable lead intake / escalation playbooks. Managers and admins only."""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from services import lead_flows as lf


async def require_manager(request: Request) -> dict:
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in lf.MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Manager or admin role required")
    request.state.user = user
    return user


router = APIRouter(prefix="/lead-flows", tags=["Lead Flows"], dependencies=[Depends(require_manager)])


class FlowBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contact_mode: Optional[str] = None
    call_attempts: Optional[list] = None
    workflow_user_ids: Optional[list] = None   # text-only flows: who gets the push
    notify_all_on_intake: Optional[bool] = None
    intake_text: Optional[str] = None
    after_hours_text: Optional[str] = None
    intake_delay_seconds: Optional[int] = None
    no_answer_text: Optional[str] = None
    va_enabled: Optional[bool] = None
    inquiry_context: Optional[str] = None
    after_hours_mode: Optional[str] = None
    text_window_start: Optional[str] = None
    text_window_end: Optional[str] = None
    caller_id_mode: Optional[str] = None
    auto_call_on_claim: Optional[bool] = None
    tags_on_claim: Optional[list] = None
    tags_on_no_answer: Optional[list] = None
    exhausted_text_lead: Optional[bool] = None
    exhausted_push_manager: Optional[bool] = None
    template_key: Optional[str] = None
    store_id: Optional[str] = None


class AttachBody(BaseModel):
    flow_id: Optional[str] = None


def _oid(v: str, what: str = "Flow") -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(str(v))


async def _flow(db, flow_id: str, user: dict) -> dict:
    flow = await db[lf.COLL].find_one({"_id": _oid(flow_id), **lf.scope_filter(user)})
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


async def _names(db, flows: list) -> dict:
    ids = {u for f in flows for a in f.get("call_attempts") or [] for u in a.get("user_ids") or [] if ObjectId.is_valid(str(u))}
    names = {}
    if ids:
        async for u in db.users.find({"_id": {"$in": [ObjectId(i) for i in ids]}}, {"name": 1, "first_name": 1}):
            names[str(u["_id"])] = (u.get("name") or u.get("first_name") or "Rep").split(" ")[0]
    return names


async def _sources_by_flow(db, flow_ids: list) -> dict:
    out: dict = {fid: [] for fid in flow_ids}
    async for s in db.lead_sources.find({"flow_id": {"$in": flow_ids}}, {"name": 1, "flow_id": 1}):
        out.setdefault(s["flow_id"], []).append(s)
    return out


def _validate(body: dict):
    import re
    hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    for k in ("text_window_start", "text_window_end"):
        if body.get(k) is not None and not hhmm.match(body[k]):
            raise HTTPException(status_code=400, detail=f"{k} must be HH:MM (24h)")
    if body.get("contact_mode") == "text_and_call" and not lf.normalize_flow_attempts(body.get("call_attempts") or []):
        raise HTTPException(status_code=400, detail="Text + Call needs at least one attempt with a rep on it")


async def _store_hours(db, store_id: str | None) -> dict | None:
    if not store_id or not ObjectId.is_valid(store_id):
        return None
    store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"business_hours": 1, "timezone": 1, "name": 1}) or {}
    from services.lead_timing import store_hours_status
    st = store_hours_status(store)
    return {"store_name": store.get("name"), "timezone": st["tz"], "configured": st["configured"], "open_now": st["open"],
            "opens_at": st["opens_at"].isoformat() if st.get("opens_at") else None, "hours": store.get("business_hours") or {}}


@router.get("")
async def list_flows(request: Request, store_id: Optional[str] = None):
    db = get_db()
    me = request.state.user
    q = lf.scope_filter(me)
    if store_id and me.get("role") in ("super_admin", "org_admin"):
        q = {"store_id": store_id}
    flows = await db[lf.COLL].find(q).sort("name", 1).to_list(200)
    names = await _names(db, flows)
    by_flow = await _sources_by_flow(db, [str(f["_id"]) for f in flows])
    sid = store_id or lf.user_store_id(me)
    return {"flows": [lf.serialize(f, by_flow.get(str(f["_id"])), names) for f in flows],
            "store_id": sid, "reps": await lf.store_reps(db, sid, me), "store_hours": await _store_hours(db, sid),
            "templates": [{"key": t["key"], "name": t["name"], "description": t["description"], "contact_mode": t["contact_mode"], "attempts": len(t.get("call_attempts") or [])} for t in lf.TEMPLATES]}


@router.get("/templates")
async def list_templates():
    return {"templates": [{"key": t["key"], "name": t["name"], "description": t["description"], "contact_mode": t["contact_mode"], "attempts": len(t.get("call_attempts") or [])} for t in lf.TEMPLATES]}


@router.post("")
async def create_flow(body: FlowBody, request: Request):
    db = get_db()
    me = request.state.user
    data = body.dict(exclude_unset=True)
    sid = data.pop("store_id", None) or lf.user_store_id(me)
    tpl_key = data.pop("template_key", None)
    base = await lf.flow_from_template(db, tpl_key, sid, me) if tpl_key else {}
    if tpl_key and not base:
        raise HTTPException(status_code=400, detail="Unknown template")
    if not tpl_key and "contact_mode" not in data and not data.get("call_attempts"):
        data["contact_mode"] = "text_only"   # blank flow starts as text-only; manager adds the ladder
    merged = {**base, **{k: v for k, v in data.items() if v is not None}}
    flow = lf.clean_flow(merged)
    _validate(flow)
    now = datetime.now(timezone.utc)
    flow.update({"store_id": sid, "owner_user_id": None if sid else str(me["_id"]), "template_key": tpl_key,
                 "created_at": now, "updated_at": now, "created_by": str(me["_id"]), "updated_by_name": me.get("name") or me.get("email")})
    flow["_id"] = (await db[lf.COLL].insert_one(flow)).inserted_id
    return lf.serialize(flow, [], await _names(db, [flow]))


@router.get("/{flow_id}")
async def get_flow(flow_id: str, request: Request):
    db = get_db()
    flow = await _flow(db, flow_id, request.state.user)
    by_flow = await _sources_by_flow(db, [str(flow["_id"])])
    return lf.serialize(flow, by_flow.get(str(flow["_id"])), await _names(db, [flow]))


@router.put("/{flow_id}")
async def update_flow(flow_id: str, body: FlowBody, request: Request):
    db = get_db()
    me = request.state.user
    existing = await _flow(db, flow_id, me)
    data = {k: v for k, v in body.dict(exclude_unset=True).items() if k not in ("template_key", "store_id")}
    flow = lf.clean_flow(data, existing)
    _validate(flow)
    flow.update({"updated_at": datetime.now(timezone.utc), "updated_by": str(me["_id"]), "updated_by_name": me.get("name") or me.get("email")})
    await db[lf.COLL].update_one({"_id": existing["_id"]}, {"$set": flow})
    flow = await db[lf.COLL].find_one({"_id": existing["_id"]})
    synced = await lf.sync_flow_to_sources(db, flow)
    by_flow = await _sources_by_flow(db, [str(flow["_id"])])
    out = lf.serialize(flow, by_flow.get(str(flow["_id"])), await _names(db, [flow]))
    out["synced_sources"] = synced
    return out


@router.post("/{flow_id}/duplicate")
async def duplicate_flow(flow_id: str, request: Request):
    db = get_db()
    me = request.state.user
    src = await _flow(db, flow_id, me)
    now = datetime.now(timezone.utc)
    copy = lf.clean_flow({"name": f"{src.get('name', 'Flow')} (copy)"[:80]}, src)
    copy.update({"store_id": src.get("store_id"), "owner_user_id": src.get("owner_user_id"), "template_key": src.get("template_key"),
                 "created_at": now, "updated_at": now, "created_by": str(me["_id"]), "updated_by_name": me.get("name") or me.get("email")})
    copy["_id"] = (await db[lf.COLL].insert_one(copy)).inserted_id
    return lf.serialize(copy, [], await _names(db, [copy]))


@router.delete("/{flow_id}")
async def delete_flow(flow_id: str, request: Request, force: bool = False):
    db = get_db()
    flow = await _flow(db, flow_id, request.state.user)
    attached = await db.lead_sources.count_documents({"flow_id": str(flow["_id"])})
    if attached and not force:
        raise HTTPException(status_code=409, detail=f"This flow is used by {attached} lead source(s). Detach them first or delete with force.")
    if attached:
        await db.lead_sources.update_many({"flow_id": str(flow["_id"])}, {"$unset": {"flow_id": "", "flow_name": ""}})
    await db[lf.COLL].delete_one({"_id": flow["_id"]})
    return {"success": True, "detached_sources": attached}


@router.put("/source/{source_id}")
async def attach_to_source(source_id: str, body: AttachBody, request: Request):
    """Point a lead source at a flow (flow_id) or detach it (flow_id null)."""
    db = get_db()
    me = request.state.user
    source = await db.lead_sources.find_one({"_id": _oid(source_id, "Lead source")})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    my_sid = lf.user_store_id(me)
    if me.get("role") not in ("super_admin", "org_admin") and my_sid and str(source.get("store_id") or "") != my_sid:
        raise HTTPException(status_code=403, detail="That source belongs to another store")
    flow = await _flow(db, body.flow_id, me) if body.flow_id else None
    updated = await lf.attach_flow(db, source_id, flow)
    from routers.lead_sources import serialize_lead_source
    return {"success": True, "lead_source": serialize_lead_source(updated),
            "flow": lf.serialize(flow, [updated], await _names(db, [flow])) if flow else None}
