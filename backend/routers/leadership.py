"""AI Leadership Team (Command Center Phase 1): roster, company knowledge, Ask an Executive, Leadership Roundtable, decisions, operating review, controls.
Founder-only through the Command Center gate. Every model call is advisory; nothing in here writes to the Command Center collections."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.command_center import _ai_error, _seeded, require_cc
from routers.database import get_db
from services import command_center_ai as ai
from services.leadership import ask, core, knowledge, roster
from services.leadership import orchestrator as rt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/command-center/team", tags=["AI Leadership Team"], dependencies=[Depends(require_cc)])


class RosterBody(BaseModel):
    enabled: Optional[bool] = None
    display_name: Optional[str] = None
    extra_boundaries: Optional[list] = None


class FactStatusBody(BaseModel):
    status: str
    note: str = ""


class ThreadBody(BaseModel):
    agent_key: str = ask.ADVISOR
    title: str = ""


class ThreadPatch(BaseModel):
    title: Optional[str] = None
    archived: Optional[bool] = None


class TurnBody(BaseModel):
    text: str
    agent_key: Optional[str] = None


class ParticipantBody(BaseModel):
    agent_key: str


class ConveneBody(BaseModel):
    question: str
    source: Optional[dict] = None


class ParticipantsBody(BaseModel):
    keys: list


class DecideBody(BaseModel):
    action: str
    reason: str = ""


class ControlsBody(BaseModel):
    soft_usd: Optional[float] = None
    hard_usd: Optional[float] = None
    max_participants: Optional[int] = None
    stopped: Optional[bool] = None


def _co(request: Request) -> str:
    return core.company_for(request.state.user)


async def _ready(db, request: Request) -> str:
    await _seeded(db, request)
    cid = _co(request)
    await knowledge.seed(db, cid)
    return cid


# ───────────────────────── roster + readiness ─────────────────────────
@router.get("/roster")
async def get_roster(request: Request):
    db = get_db()
    cid = await _ready(db, request)
    ros = await roster.roster(db, cid)
    snap = await knowledge.cc_snapshot(db)
    for a in ros:
        a["readiness"] = await knowledge.readiness(db, cid, a, snap)
        a.pop("prompt", None)
    co = await core.company(db, cid)
    return {"executives": ros, "company": {"id": cid, "name": co["name"]}, "controls": co["controls"], "month_spend_usd": await core.month_spend(db, cid)}


@router.patch("/roster/{key}")
async def patch_roster(key: str, body: RosterBody, request: Request):
    db = get_db()
    cid = _co(request)
    if key not in roster.ROLE_BY_KEY:
        raise HTTPException(status_code=404, detail="Unknown executive")
    if body.enabled is False and key in ("chief_of_staff", "strategic_advisor"):
        raise HTTPException(status_code=400, detail="The Chief of Staff and the Strategic Advisor always sit on the team")
    before = await roster.agent(db, cid, key)
    out = await roster.update_agent(db, cid, key, body.model_dump(exclude_none=True))
    await core.audit(db, cid, request.state.user, "roster_updated", {"kind": "agent", "id": key}, before={"enabled": before["enabled"], "display_name": before["title"]}, after={"enabled": out["enabled"], "display_name": out["title"]})
    out["readiness"] = await knowledge.readiness(db, cid, out)
    return out


# ───────────────────────── company knowledge ─────────────────────────
@router.get("/knowledge")
async def list_knowledge(request: Request, domain: Optional[str] = None):
    db = get_db()
    cid = await _ready(db, request)
    return {"facts": await knowledge.list_facts(db, cid, domain), "domains": list(knowledge.DOMAINS), "statuses": list(knowledge.STATUSES), "kinds": list(knowledge.KINDS), "source_kinds": list(knowledge.SOURCE_KINDS)}


@router.post("/knowledge")
async def create_knowledge(body: dict, request: Request):
    db = get_db()
    cid = _co(request)
    try:
        f = await knowledge.create_fact(db, cid, body or {}, request.state.user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])
    await core.audit(db, cid, request.state.user, "fact_created", {"kind": "fact", "id": f["id"]}, after={"key": f["key"], "status": f["status"]})
    return f


@router.post("/knowledge/{fid}/status")
async def set_knowledge_status(fid: str, body: FactStatusBody, request: Request):
    db = get_db()
    cid = _co(request)
    f = await knowledge.set_status(db, cid, fid, body.status, request.state.user, body.note)
    if not f:
        raise HTTPException(status_code=400, detail="Unknown fact or status")
    await core.audit(db, cid, request.state.user, "fact_status", {"kind": "fact", "id": fid}, after={"status": body.status}, reason=body.note)
    return f


# ───────────────────────── Mode A: Ask an Executive ─────────────────────────
async def _thread(db, cid: str, tid: str) -> dict:
    c = await ask.get_thread(db, cid, tid)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return c


@router.get("/threads")
async def list_threads(request: Request):
    db = get_db()
    cid = await _ready(db, request)
    return {"threads": await ask.list_threads(db, cid)}


@router.post("/threads")
async def create_thread(body: ThreadBody, request: Request):
    db = get_db()
    cid = await _ready(db, request)
    try:
        return await ask.create_thread(db, cid, request.state.user, body.agent_key, body.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])


@router.get("/threads/{tid}")
async def get_thread(tid: str, request: Request):
    db = get_db()
    return ask._pub(await _thread(db, _co(request), tid), full=True)


@router.patch("/threads/{tid}")
async def patch_thread(tid: str, body: ThreadPatch, request: Request):
    db = get_db()
    c = await _thread(db, _co(request), tid)
    await ai.update_conversation(db, c, body.model_dump(exclude_none=True))
    return ask._pub(await db[ai.CONVOS].find_one({"_id": c["_id"]}), full=True)


@router.post("/threads/{tid}/messages")
async def thread_turn(tid: str, body: TurnBody, request: Request):
    db = get_db()
    cid = await _ready(db, request)
    c = await _thread(db, cid, tid)
    try:
        return await ask.turn(db, request.state.user, c, body.text, agent_key=body.agent_key)
    except Exception as e:
        _ai_error(e)


@router.post("/threads/{tid}/participants")
async def thread_add_participant(tid: str, body: ParticipantBody, request: Request):
    db = get_db()
    cid = _co(request)
    c = await _thread(db, cid, tid)
    try:
        return await ask.add_participant(db, cid, c, body.agent_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])


@router.get("/starters")
async def starters(request: Request, agent_key: str = ask.ADVISOR):
    db = get_db()
    await _seeded(db, request)
    ctx = await ai.assemble_context(db)
    return {"questions": ask.starters(agent_key, ctx), "facts": ctx["facts"]}


# ───────────────────────── Mode B: Leadership Roundtable ─────────────────────────
async def _rt(db, cid: str, rid: str) -> dict:
    r = await rt.get(db, cid, rid)
    if not r:
        raise HTTPException(status_code=404, detail="Roundtable not found")
    return r


async def _rt_out(db, r: dict) -> dict:
    out = rt.pub(r)
    if r.get("decision_id"):
        d = await db[rt.DECISIONS].find_one({"_id": ai.cc._oid(r["decision_id"])})
        out["decision"] = rt.pub_decision(d) if d else None
    return out


@router.get("/roundtables")
async def list_roundtables(request: Request):
    db = get_db()
    cid = await _ready(db, request)
    await rt.fail_interrupted(db)
    return {"roundtables": await rt.list_roundtables(db, cid), "estimate_per_participant_usd": rt.AVG_CALL_USD * 2}


@router.post("/roundtables")
async def convene(body: ConveneBody, request: Request):
    db = get_db()
    cid = await _ready(db, request)
    try:
        return await rt.create(db, cid, request.state.user, body.question, body.source)
    except Exception as e:
        _ai_error(e)


@router.get("/roundtables/{rid}")
async def get_roundtable(rid: str, request: Request):
    db = get_db()
    cid = _co(request)
    await rt.fail_interrupted(db)
    return await _rt_out(db, await _rt(db, cid, rid))


@router.put("/roundtables/{rid}/participants")
async def put_participants(rid: str, body: ParticipantsBody, request: Request):
    db = get_db()
    cid = _co(request)
    try:
        return await rt.set_participants(db, cid, await _rt(db, cid, rid), [str(k) for k in body.keys])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])


@router.post("/roundtables/{rid}/start")
async def start_roundtable(rid: str, request: Request):
    db = get_db()
    cid = _co(request)
    try:
        return await rt.start(db, cid, await _rt(db, cid, rid), request.state.user)
    except Exception as e:
        _ai_error(e)


@router.post("/roundtables/{rid}/resume")
async def resume_roundtable(rid: str, request: Request):
    db = get_db()
    cid = _co(request)
    try:
        return await rt.resume(db, cid, await _rt(db, cid, rid), request.state.user)
    except Exception as e:
        _ai_error(e)


@router.post("/roundtables/{rid}/cancel")
async def cancel_roundtable(rid: str, request: Request):
    db = get_db()
    cid = _co(request)
    return await rt.cancel(db, cid, await _rt(db, cid, rid), request.state.user)


# ───────────────────────── decisions ─────────────────────────
@router.get("/decisions")
async def list_decisions(request: Request, status: Optional[str] = None):
    db = get_db()
    cid = await _ready(db, request)
    return {"decisions": await rt.decisions(db, cid, status)}


@router.post("/decisions/{did}")
async def decide(did: str, body: DecideBody, request: Request):
    db = get_db()
    cid = _co(request)
    try:
        return await rt.decide(db, cid, did, request.state.user, body.action, body.reason)
    except Exception as e:
        _ai_error(e)


# ───────────────────────── Mode D lite: operating review ─────────────────────────
@router.get("/review")
async def latest_review(request: Request):
    db = get_db()
    return {"review": await rt.latest_review(db, _co(request))}


@router.post("/review")
async def generate_review(request: Request):
    db = get_db()
    cid = await _ready(db, request)
    try:
        return {"review": await rt.review(db, cid, request.state.user)}
    except Exception as e:
        _ai_error(e)


# ───────────────────────── usage, controls, audit ─────────────────────────
@router.get("/usage")
async def usage(request: Request):
    return await core.usage(get_db(), _co(request))


@router.get("/controls")
async def get_controls(request: Request):
    return (await core.company(get_db(), _co(request)))["controls"]


@router.put("/controls")
async def put_controls(body: ControlsBody, request: Request):
    try:
        return await core.update_controls(get_db(), _co(request), body.model_dump(exclude_none=True), request.state.user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])


@router.get("/audit")
async def audit(request: Request, limit: int = 100):
    return {"entries": await core.audit_list(get_db(), _co(request), max(1, min(500, limit)))}
