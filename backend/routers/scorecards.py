"""Scorecards API: manager-built call QA checklists per department + AI-graded call evaluations.
Reps see their own scores; managers see their store's team, override grades, get critical-miss alerts."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from routers.database import get_db
from services import scorecards as sc
from services.lead_flows import MANAGER_ROLES, user_store_id, store_reps


async def require_user(request: Request) -> dict:
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user = user
    return user


router = APIRouter(prefix="/scorecards", tags=["Scorecards"], dependencies=[Depends(require_user)])


class AppliesTo(BaseModel):
    user_ids: List[str] = []
    inbox_ids: List[str] = []
    source_ids: List[str] = []


class CardBody(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[list] = None
    applies_to: Optional[AppliesTo] = None
    is_default: Optional[bool] = None
    active: Optional[bool] = None
    alert_on_critical: Optional[bool] = None
    alert_below_pct: Optional[int] = Field(default=None, ge=0, le=100)
    clear_alert_below: Optional[bool] = None
    notify_rep: Optional[bool] = None
    template_key: Optional[str] = None
    store_id: Optional[str] = None


class OverrideBody(BaseModel):
    criterion_id: str
    passed: Optional[bool] = None
    note: str = ""


class RescoreBody(BaseModel):
    scorecard_id: Optional[str] = None


class MuteBody(BaseModel):
    rep_id: str
    muted: bool = True


def _me(request: Request) -> dict:
    return request.state.user


def _is_manager(user: dict) -> bool:
    return user.get("role") in MANAGER_ROLES


def _require_manager(user: dict):
    if not _is_manager(user):
        raise HTTPException(status_code=403, detail="Manager or admin role required")


def _oid(v: str, what: str = "Scorecard") -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(str(v))


async def _card(db, card_id: str, user: dict) -> dict:
    card = await db[sc.COLL].find_one({"_id": _oid(card_id), **(await sc.card_scope_filter(user))})
    if not card:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return card


async def _eval(db, ev_id: str, user: dict) -> dict:
    ev = await db[sc.EVAL_COLL].find_one({"_id": _oid(ev_id, "Evaluation"), **(await sc.eval_scope_filter(user))})
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return ev


async def _store_options(db, store_id: Optional[str], me: dict) -> dict:
    reps = [r for r in await store_reps(db, store_id, me) if r["role"] != "super_admin" or r["_id"] == str(me["_id"])]
    q = {"is_active": {"$ne": False}, **({"store_id": store_id} if store_id else {})}
    inboxes = [{"id": str(i["_id"]), "name": i.get("name"), "color": i.get("color")} async for i in db.shared_inboxes.find(q, {"name": 1, "color": 1})]
    sq = {"is_active": {"$ne": False}, **({"store_id": store_id} if store_id else {})}
    sources = [{"id": str(s["_id"]), "name": s.get("name")} async for s in db.lead_sources.find(sq, {"name": 1}).limit(50)]
    return {"reps": reps, "inboxes": inboxes, "sources": sources}


def _apply_body(card: dict, body: CardBody):
    data = body.model_dump(exclude_unset=True)
    for k in ("name", "department", "description"):
        if k in data and data[k] is not None:
            card[k] = data[k].strip()
    if "criteria" in data and data["criteria"] is not None:
        card["criteria"] = sc.normalize_criteria(data["criteria"])
    if "applies_to" in data and data["applies_to"] is not None:
        card["applies_to"] = {k: [str(x) for x in (data["applies_to"].get(k) or [])] for k in ("user_ids", "inbox_ids", "source_ids")}
    for k in ("is_default", "active", "alert_on_critical", "notify_rep"):
        if k in data and data[k] is not None:
            card[k] = bool(data[k])
    if data.get("clear_alert_below"):
        card["alert_below_pct"] = None
    elif "alert_below_pct" in data and data["alert_below_pct"] is not None:
        card["alert_below_pct"] = int(data["alert_below_pct"])


# ---------------------------------------------------------------- library
@router.get("")
async def list_scorecards(request: Request):
    db = get_db()
    me = _me(request)
    cards = await db[sc.COLL].find({"active": {"$ne": False}, **(await sc.card_scope_filter(me))}).sort([("is_default", -1), ("created_at", 1)]).to_list(100)
    ids = [str(c["_id"]) for c in cards]
    counts: dict = {}
    if ids:
        since = datetime.now(timezone.utc) - timedelta(days=30)
        async for row in db[sc.EVAL_COLL].aggregate([{"$match": {"scorecard_id": {"$in": ids}, "call_at": {"$gte": since}}},
                                                    {"$group": {"_id": "$scorecard_id", "n": {"$sum": 1}, "avg": {"$avg": "$score_pct"}}}]):
            counts[row["_id"]] = {"calls_30d": row["n"], "avg_30d": int(round(row["avg"])) if row.get("avg") is not None else None}
    out = {"scorecards": [sc.serialize(c, counts.get(str(c["_id"]), {"calls_30d": 0, "avg_30d": None})) for c in cards],
           "templates": [{"key": t["key"], "name": t["name"], "department": t["department"], "description": t["description"], "criteria_count": len(t["criteria"])} for t in sc.TEMPLATES],
           "departments": sc.DEPARTMENTS, "can_manage": _is_manager(me), "store_id": user_store_id(me)}
    if _is_manager(me):
        out.update(await _store_options(db, user_store_id(me), me))
    return out


@router.post("")
async def create_scorecard(body: CardBody, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    card = sc.template_body(body.template_key) if body.template_key else {"name": "", "department": "", "description": "", "criteria": []}
    if card is None:
        raise HTTPException(status_code=400, detail="Unknown template")
    card.setdefault("applies_to", {"user_ids": [], "inbox_ids": [], "source_ids": []})
    card.update({"active": True, "alert_on_critical": True, "alert_below_pct": None, "notify_rep": True, "is_default": False})
    _apply_body(card, body)
    if not card.get("name"):
        raise HTTPException(status_code=400, detail="Give the scorecard a name")
    now = datetime.now(timezone.utc)
    store_id = body.store_id if (body.store_id and me.get("role") in ("super_admin", "org_admin")) else user_store_id(me)
    card.update({"store_id": store_id, "owner_user_id": str(me["_id"]), "created_by": str(me["_id"]), "created_at": now, "updated_at": now})
    existing = await db[sc.COLL].count_documents({"store_id": store_id, "active": {"$ne": False}})
    if existing == 0 and body.is_default is None:
        card["is_default"] = True
    res = await db[sc.COLL].insert_one(card)
    card["_id"] = res.inserted_id
    if card.get("is_default"):
        await sc.ensure_single_default(db, store_id, res.inserted_id)
    return sc.serialize(card)


# ---------------------------------------------------------------- evaluations (declared before /{card_id})
@router.get("/evaluations/mine")
async def my_evaluations(request: Request, days: int = 30, limit: int = 40):
    db = get_db()
    me = _me(request)
    days = max(7, min(365, days))
    since = datetime.now(timezone.utc) - timedelta(days=2 * days)
    evals = await db[sc.EVAL_COLL].find({"user_id": str(me["_id"]), "call_at": {"$gte": since}}).sort("call_at", -1).to_list(2000)
    stats = sc.rep_stats(evals, days)
    recent = [e for e in evals if sc._dt(e) >= datetime.now(timezone.utc) - timedelta(days=days)][:limit]
    return {"user": {"id": str(me["_id"]), "name": me.get("name")}, "stats": stats, "evaluations": [sc.serialize_eval(e) for e in recent]}


@router.get("/evaluations/call/{call_sid}")
async def evaluation_for_call(call_sid: str, request: Request):
    db = get_db()
    me = _me(request)
    ev = await db[sc.EVAL_COLL].find_one({"call_sid": call_sid, **(await sc.eval_scope_filter(me))})
    if not ev:
        log = await db.call_logs.find_one({"call_sid": call_sid}, {"transcript": 1, "duration_s": 1, "outcome": 1, "user_id": 1})
        if not log:
            raise HTTPException(status_code=404, detail="Call not found")
        reason = ("no_transcript" if not log.get("transcript") else "too_short" if int(log.get("duration_s") or 0) < sc.MIN_DURATION_S
                  else "voicemail" if log.get("outcome") in ("voicemail", "no_answer") else "no_scorecard")
        return {"evaluation": None, "reason": reason, "can_manage": _is_manager(me)}
    return {"evaluation": sc.serialize_eval(ev), "can_manage": _is_manager(me)}


@router.get("/evaluations/{ev_id}")
async def get_evaluation(ev_id: str, request: Request):
    db = get_db()
    me = _me(request)
    return {"evaluation": sc.serialize_eval(await _eval(db, ev_id, me)), "can_manage": _is_manager(me)}


@router.put("/evaluations/{ev_id}/override")
async def override_evaluation(ev_id: str, body: OverrideBody, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    ev = await _eval(db, ev_id, me)
    try:
        ev = await sc.apply_override(db, ev, body.criterion_id, body.passed, me, body.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sc.serialize_eval(ev)


@router.post("/evaluations/rescore/{call_sid}")
async def rescore_call(call_sid: str, body: RescoreBody, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    log = await db.call_logs.find_one({"call_sid": call_sid}, {"user_id": 1})
    if not log:
        raise HTTPException(status_code=404, detail="Call not found")
    rep = await db.users.find_one({"_id": _oid(log.get("user_id"), "Rep")}, {"store_id": 1, "store_ids": 1})
    scope = await sc.scope_store_ids(me)
    if scope is not None and user_store_id(rep or {}) not in scope and str(log.get("user_id")) != str(me["_id"]):
        raise HTTPException(status_code=403, detail="That call is outside your store")
    if body.scorecard_id:
        await _card(db, body.scorecard_id, me)
    try:
        ev = await sc.evaluate_call(call_sid, scorecard_id=body.scorecard_id, force=True, actor_id=str(me["_id"]))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Grading failed: {e}")
    if not ev:
        raise HTTPException(status_code=400, detail="This call can't be graded: it needs a transcript, at least 30 seconds of conversation and a scorecard that applies")
    return {"evaluation": sc.serialize_eval(ev), "can_manage": True}


# ---------------------------------------------------------------- manager views
@router.get("/team")
async def team_dashboard(request: Request, days: int = 30, scorecard_id: Optional[str] = None):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    if scorecard_id:
        await _card(db, scorecard_id, me)
    data = await sc.team_stats(db, await sc.eval_scope_filter(me), max(7, min(365, days)), scorecard_id or None)
    data["muted_reps"] = me.get("scorecard_muted_reps") or []
    return data


@router.get("/rep/{user_id}")
async def rep_dashboard(user_id: str, request: Request, days: int = 30, limit: int = 40):
    db = get_db()
    me = _me(request)
    if str(me["_id"]) != user_id:
        _require_manager(me)
    rep = await db.users.find_one({"_id": _oid(user_id, "Rep")}, {"name": 1, "first_name": 1, "photo_url": 1, "photo_thumbnail": 1, "store_id": 1, "store_ids": 1, "role": 1})
    if not rep:
        raise HTTPException(status_code=404, detail="Rep not found")
    scope = await sc.scope_store_ids(me)
    if str(me["_id"]) != user_id and scope is not None and user_store_id(rep) not in scope:
        raise HTTPException(status_code=403, detail="That rep is outside your store")
    days = max(7, min(365, days))
    since = datetime.now(timezone.utc) - timedelta(days=2 * days)
    evals = await db[sc.EVAL_COLL].find({"user_id": user_id, "call_at": {"$gte": since}}).sort("call_at", -1).to_list(2000)
    recent = [e for e in evals if sc._dt(e) >= datetime.now(timezone.utc) - timedelta(days=days)][:limit]
    return {"user": {"id": user_id, "name": rep.get("name") or rep.get("first_name"), "photo": rep.get("photo_thumbnail") or rep.get("photo_url"), "role": rep.get("role")},
            "stats": sc.rep_stats(evals, days), "evaluations": [sc.serialize_eval(e) for e in recent],
            "can_manage": _is_manager(me), "muted": user_id in (me.get("scorecard_muted_reps") or [])}


@router.put("/alerts/mute")
async def mute_rep_alerts(body: MuteBody, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    op = {"$addToSet" if body.muted else "$pull": {"scorecard_muted_reps": body.rep_id}}
    await db.users.update_one({"_id": ObjectId(str(me["_id"]))}, op)
    return {"rep_id": body.rep_id, "muted": body.muted}


# ---------------------------------------------------------------- single card
@router.get("/{card_id}")
async def get_scorecard(card_id: str, request: Request):
    db = get_db()
    me = _me(request)
    card = await _card(db, card_id, me)
    out = sc.serialize(card)
    if _is_manager(me):
        out.update(await _store_options(db, card.get("store_id"), me))
    return out


@router.put("/{card_id}")
async def update_scorecard(card_id: str, body: CardBody, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    card = await _card(db, card_id, me)
    _apply_body(card, body)
    if not card.get("name"):
        raise HTTPException(status_code=400, detail="Give the scorecard a name")
    if not card.get("criteria"):
        raise HTTPException(status_code=400, detail="Add at least one criterion")
    card["updated_at"] = datetime.now(timezone.utc)
    card["updated_by"] = str(me["_id"])
    await db[sc.COLL].replace_one({"_id": card["_id"]}, card)
    if card.get("is_default"):
        await sc.ensure_single_default(db, card.get("store_id"), card["_id"])
    return sc.serialize(card)


@router.post("/{card_id}/duplicate")
async def duplicate_scorecard(card_id: str, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    card = await _card(db, card_id, me)
    now = datetime.now(timezone.utc)
    copy = {k: v for k, v in card.items() if k != "_id"}
    copy.update({"name": f"{card.get('name')} (copy)", "is_default": False, "applies_to": {"user_ids": [], "inbox_ids": [], "source_ids": []},
                 "created_at": now, "updated_at": now, "created_by": str(me["_id"]), "owner_user_id": str(me["_id"])})
    copy["criteria"] = [{**c, "id": ObjectId().binary.hex()[:8]} for c in card.get("criteria") or []]
    res = await db[sc.COLL].insert_one(copy)
    copy["_id"] = res.inserted_id
    return sc.serialize(copy)


@router.delete("/{card_id}")
async def delete_scorecard(card_id: str, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    card = await _card(db, card_id, me)
    graded = await db[sc.EVAL_COLL].count_documents({"scorecard_id": str(card["_id"])})
    await db[sc.COLL].update_one({"_id": card["_id"]}, {"$set": {"active": False, "is_default": False, "deleted_at": datetime.now(timezone.utc)}})
    return {"deleted": True, "kept_evaluations": graded}
