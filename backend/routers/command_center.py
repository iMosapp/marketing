"""Founder Command Center API. Owner-only through the established Owner Tools gate (key `command_center`)."""
import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db
from routers.owner import can_see
from services import command_center as cc

logger = logging.getLogger(__name__)
TOOL_KEY = "command_center"


async def require_cc(request: Request) -> dict:
    me = await require_user(request)
    if not await can_see(get_db(), me, TOOL_KEY):
        raise HTTPException(status_code=403, detail="Founder Command Center is private")
    return me


router = APIRouter(prefix="/command-center", tags=["Founder Command Center"], dependencies=[Depends(require_cc)])


class DataBody(BaseModel):
    data: dict
    reason: Optional[str] = ""


class ReasonBody(BaseModel):
    reason: str = ""


class ReplaceBody(BaseModel):
    replace_id: str
    reason: str = ""


class NextActionBody(BaseModel):
    text: str = ""
    why: Optional[str] = ""


def _oid(v: str) -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=400, detail="Bad id")
    return ObjectId(str(v))


async def _get(db, coll: str, pid: str) -> dict:
    """Internal lookup; every endpoint serialises the result through cc._pub before returning it."""
    d = await db[coll].find_one({"_id": _oid(pid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(d)


def _bad(e: Exception):
    raise HTTPException(status_code=400, detail=str(e)[:300])


async def _seeded(db, request: Request):
    """First visit seeds the drafts; later visits only insert keys that are still missing (founder edits are never overwritten)."""
    if await db[cc.BLUEPRINT].count_documents({"key": "focus"}) == 0:
        await cc.seed(db, request.state.user)


@router.post("/seed")
async def seed(request: Request):
    return await cc.seed(get_db(), request.state.user)


@router.get("/focus")
async def focus(request: Request):
    db = get_db()
    await _seeded(db, request)
    return await cc.focus(db)


@router.get("/blueprint")
async def blueprint(request: Request):
    db = get_db()
    await _seeded(db, request)
    return await cc.blueprint(db)


@router.put("/blueprint/{key}")
async def put_blueprint(key: str, body: DataBody, request: Request):
    db = get_db()
    try:
        doc = await cc.update_blueprint(db, key, {**body.data, "reason": body.reason}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.post("/blueprint/{key}/approve")
async def approve_blueprint(key: str, body: ReasonBody, request: Request):
    try:
        doc = await cc.approve_blueprint(get_db(), key, body.reason, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.get("/blueprint/{key}/versions")
async def blueprint_versions(key: str):
    return {"versions": await cc.versions(get_db(), key)}


@router.put("/next-action")
async def put_next_action(body: NextActionBody, request: Request):
    try:
        doc = await cc.update_blueprint(get_db(), "next_action", {"text": body.text, "why": body.why or ""}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.delete("/next-action")
async def clear_next_action(request: Request):
    doc = await cc.update_blueprint(get_db(), "next_action", {"text": "", "why": ""}, request.state.user)
    return cc._pub(doc)


@router.get("/priorities")
async def list_priorities():
    return {"priorities": await cc.priorities(get_db()), "slots": cc.MAX_ACTIVE}


@router.post("/priorities")
async def create_priority(body: dict, request: Request):
    try:
        doc = await cc.create_priority(get_db(), body or {}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.patch("/priorities/{pid}")
async def patch_priority(pid: str, body: dict, request: Request):
    db = get_db()
    try:
        doc = await cc.update_priority(db, await _get(db, cc.PRIORITIES, pid), body or {}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.post("/priorities/{pid}/activate")
async def activate_priority(pid: str, request: Request):
    db = get_db()
    try:
        doc = await cc.activate_priority(db, await _get(db, cc.PRIORITIES, pid), request.state.user)
    except cc.SlotsFull as e:
        raise HTTPException(status_code=409, detail={"message": "Three priorities are already active. Complete, pause or replace one, or park this as an idea.", "active": e.active})
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.post("/priorities/{pid}/pause")
async def pause_priority(pid: str, request: Request):
    db = get_db()
    try:
        doc = await cc.pause_priority(db, await _get(db, cc.PRIORITIES, pid), request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.post("/priorities/{pid}/complete")
async def complete_priority(pid: str, request: Request):
    db = get_db()
    try:
        doc = await cc.complete_priority(db, await _get(db, cc.PRIORITIES, pid), request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.post("/priorities/{pid}/replace")
async def replace_priority(pid: str, body: ReplaceBody, request: Request):
    db = get_db()
    try:
        doc = await cc.replace_priority(db, await _get(db, cc.PRIORITIES, pid), body.replace_id, body.reason, request.state.user)
    except cc.SlotsFull as e:
        raise HTTPException(status_code=409, detail={"message": "Three priorities are already active.", "active": e.active})
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.get("/notes")
async def list_notes(kind: Optional[str] = None):
    q = {"kind": kind} if kind in cc.NOTE_KINDS else {}
    return {"notes": [cc._pub(r) for r in await get_db()[cc.NOTES].find(q).sort("created_at", -1).to_list(500)]}


@router.post("/notes")
async def create_note(body: dict):
    try:
        doc = await cc.create_note(get_db(), body or {})
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.patch("/notes/{nid}")
async def patch_note(nid: str, body: dict):
    db = get_db()
    await _get(db, cc.NOTES, nid)
    try:
        upd = cc._clean_note(body or {}, False)
    except ValueError as e:
        _bad(e)
    if upd:
        await db[cc.NOTES].update_one({"_id": _oid(nid)}, {"$set": {**upd, "updated_at": cc._now()}})
    return cc._pub(await _get(db, cc.NOTES, nid))


@router.delete("/notes/{nid}")
async def delete_note(nid: str):
    await get_db()[cc.NOTES].delete_one({"_id": _oid(nid)})
    return {"deleted": True}


@router.get("/roadmap")
async def get_roadmap(request: Request):
    db = get_db()
    await _seeded(db, request)
    return await cc.roadmap(db)


@router.post("/roadmap")
async def create_roadmap(body: dict, request: Request):
    try:
        doc = await cc.create_roadmap(get_db(), body or {}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.patch("/roadmap/{rid}")
async def patch_roadmap(rid: str, body: dict):
    db = get_db()
    await _get(db, cc.ROADMAP, rid)
    try:
        upd = cc._clean_roadmap(body or {}, False)
    except ValueError as e:
        _bad(e)
    if upd:
        await db[cc.ROADMAP].update_one({"_id": _oid(rid)}, {"$set": {**upd, "updated_at": cc._now()}})
    return cc._pub(await _get(db, cc.ROADMAP, rid))


@router.delete("/roadmap/{rid}")
async def delete_roadmap(rid: str):
    await get_db()[cc.ROADMAP].delete_one({"_id": _oid(rid)})
    return {"deleted": True}


@router.get("/ideas")
async def list_ideas(status: Optional[str] = None, view: Optional[str] = None):
    return await cc.ideas(get_db(), status, view)


@router.post("/ideas")
async def create_idea(body: dict, request: Request):
    try:
        doc = await cc.create_idea(get_db(), body or {}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.patch("/ideas/{iid}")
async def patch_idea(iid: str, body: dict, request: Request):
    db = get_db()
    try:
        doc = await cc.update_idea(db, await _get(db, cc.IDEAS, iid), body or {}, request.state.user)
    except ValueError as e:
        _bad(e)
    return cc._pub(doc)


@router.delete("/ideas/{iid}")
async def delete_idea(iid: str):
    await get_db()[cc.IDEAS].delete_one({"_id": _oid(iid)})
    return {"deleted": True}


@router.get("/export.json")
async def export_json():
    return await cc.export_json(get_db())


@router.get("/export.md", response_class=PlainTextResponse)
async def export_md():
    return await cc.export_markdown(get_db())
