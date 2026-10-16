"""Super-admin Photo Intelligence controls (Jessi Photo Replies, Automatic Photo Intelligence, emergency Pause All, test organizations)
and the image-analysis usage & ESTIMATED cost report. No spending caps by design: visibility + the pause switch only."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db
from services import mms_vision as mv

router = APIRouter(prefix="/jessi-vision", tags=["Jessi Vision"], dependencies=[Depends(require_user)])


class SettingsBody(BaseModel):
    replies: Optional[str] = None
    intelligence: Optional[str] = None
    paused: Optional[bool] = None


def _super(request: Request) -> dict:
    me = request.state.user
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    return me


def _oid(v):
    return ObjectId(str(v)) if ObjectId.is_valid(str(v or "")) else v


async def _names(db, coll: str, ids, field: str = "name") -> dict:
    ids = [i for i in {str(x) for x in ids if x}]
    if not ids:
        return {}
    rows = await db[coll].find({"_id": {"$in": [_oid(i) for i in ids]}}, {field: 1, "email": 1}).to_list(len(ids))
    return {str(r["_id"]): r.get(field) or r.get("email") or "" for r in rows}


async def _view(db, me: dict) -> dict:
    cfg = await mv.settings(db)
    doc = await db.settings.find_one({"key": mv.SETTINGS_KEY}, {"updated_at": 1, "updated_by": 1}) or {}
    my_org = str(me.get("organization_id") or "")
    names = await _names(db, "organizations", cfg["test_org_ids"] + [my_org])
    return {**{k: cfg[k] for k in ("replies", "intelligence", "paused")}, "scopes": list(mv.SCOPES), "model": "openai/gpt-5.4",
            "test_orgs": [{"id": o, "name": names.get(o) or o} for o in cfg["test_org_ids"]],
            "my_org": {"id": my_org, "name": names.get(my_org) or my_org, "is_test": my_org in cfg["test_org_ids"],
                       "replies_on": mv.in_scope(cfg, "replies", my_org), "intelligence_on": mv.in_scope(cfg, "intelligence", my_org)} if my_org else None,
            "updated_at": doc.get("updated_at"), "updated_by": doc.get("updated_by")}


async def _save(db, me: dict, sets: dict, push: Optional[str] = None, pull: Optional[str] = None):
    before = await mv.settings(db)
    upd = {"$set": {"key": mv.SETTINGS_KEY, **sets, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": me.get("email") or str(me.get("_id"))}}
    if push:
        upd["$addToSet"] = {"test_org_ids": push}
    if pull:
        upd["$pull"] = {"test_org_ids": pull}
    await db.settings.update_one({"key": mv.SETTINGS_KEY}, upd, upsert=True)
    await db.vision_settings_events.insert_one({"before": before, "after": await mv.settings(db), "by": me.get("email") or str(me.get("_id")),
                                                "at": datetime.now(timezone.utc)})


@router.get("/settings")
async def get_settings(request: Request):
    return await _view(get_db(), _super(request))


@router.put("/settings")
async def put_settings(body: SettingsBody, request: Request):
    me, db = _super(request), get_db()
    sets = {}
    for cap in mv.CAPABILITIES:
        v = getattr(body, cap)
        if v is not None:
            if v not in mv.SCOPES:
                raise HTTPException(status_code=422, detail=f"{cap} must be one of {', '.join(mv.SCOPES)}")
            sets[cap] = v
    if body.paused is not None:
        sets["paused"] = body.paused
    if not sets:
        raise HTTPException(status_code=422, detail="Nothing to change")
    await _save(db, me, sets)
    return await _view(db, me)


@router.post("/test-orgs/mine")
async def add_my_org(request: Request):
    me, db = _super(request), get_db()
    org = str(me.get("organization_id") or "")
    if not org:
        raise HTTPException(status_code=400, detail="Your account is not in an organization")
    await _save(db, me, {}, push=org)
    return await _view(db, me)


@router.delete("/test-orgs/{org_id}")
async def remove_test_org(org_id: str, request: Request):
    me, db = _super(request), get_db()
    await _save(db, me, {}, pull=org_id)
    return await _view(db, me)


@router.post("/photo-suggestions/clear")
async def clear_photo_suggestions(request: Request):
    """Rollback helper: drop every PENDING photo proposal (accepted details stay). Run before rolling back to a build older than
    2026-10-16, whose decision code would replace a saved detail instead of adding to it."""
    me, db = _super(request), get_db()
    r = await db.contacts.update_many({"detail_suggestions.source": "a photo"}, {"$pull": {"detail_suggestions": {"source": "a photo"}}})
    await db.vision_settings_events.insert_one({"action": "clear_photo_suggestions", "contacts": r.modified_count, "by": me.get("email") or str(me.get("_id")),
                                                "at": datetime.now(timezone.utc)})
    return {"contacts": r.modified_count}


# ── Usage & estimated cost ────────────────────────────────────────────────────

AN = {"$ifNull": ["$analyzed", {"$not": ["$cached"]}]}
ACC = {
    "received": {"$sum": {"$cond": [{"$eq": ["$source", "mms"]}, 1, 0]}},
    "analyzed": {"$sum": {"$cond": [AN, 1, 0]}},
    "reused": {"$sum": {"$cond": ["$cached", 1, 0]}},
    "successful": {"$sum": {"$cond": [{"$and": [AN, "$ok"]}, 1, 0]}},
    "failed": {"$sum": {"$cond": [{"$and": [AN, {"$not": ["$ok"]}]}, 1, 0]}},
    "fetch_failed": {"$sum": {"$cond": [{"$in": ["$reason", ["fetch_failed", "too_large"]]}, 1, 0]}},
    "not_analyzed": {"$sum": {"$cond": [{"$in": ["$reason", ["paused", "limit", "not_read", "unsupported"]]}, 1, 0]}},
    "paused": {"$sum": {"$cond": [{"$eq": ["$reason", "paused"]}, 1, 0]}},
    "est_cost_usd": {"$sum": {"$ifNull": ["$est_cost_usd", 0]}},
    "ms_total": {"$sum": {"$cond": [AN, {"$ifNull": ["$ms", 0]}, 0]}},
    "reps": {"$addToSet": "$user_id"},
}


def _finish(r: dict) -> dict:
    reps = len([x for x in r.pop("reps", []) if x])
    ms = r.pop("ms_total", 0)
    cost = round(r.get("est_cost_usd") or 0, 4)
    return {**r, "est_cost_usd": cost, "active_reps": reps, "avg_cost_per_analyzed": round(cost / r["analyzed"], 5) if r.get("analyzed") else 0,
            "cost_per_active_rep": round(cost / reps, 4) if reps else 0, "avg_ms": int(ms / r["analyzed"]) if r.get("analyzed") else 0}


async def _group(db, match: dict, key, limit: int = 0) -> list:
    pipe = [{"$match": match}, {"$group": {"_id": key, **ACC}}, {"$sort": {"est_cost_usd": -1, "received": -1}}]
    if limit:
        pipe.append({"$limit": limit})
    return [{"key": r.pop("_id"), **_finish(r)} for r in await db.vision_usage.aggregate(pipe).to_list(1000)]


@router.get("/usage")
async def usage(request: Request, days: int = 30):
    """Photos received / analyzed / reused / failed and ESTIMATED cost: totals, daily (the range), monthly (12 months), per organization,
    location, rep, source and model, plus monitoring counters (unattributed rows, duplicate processing)."""
    _super(request)
    db = get_db()
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    m = {"created_at": {"$gte": since}}
    total = (await _group(db, m, None) or [{"key": None, **_finish({k: 0 for k in ACC if k != "reps"} | {"reps": []})}])[0]
    total.pop("key", None)
    daily = {r["key"]: r for r in await _group(db, m, "$day")}
    series = []
    for k in range(days - 1, -1, -1):
        d = (now - timedelta(days=k)).strftime("%Y-%m-%d")
        r = daily.get(d) or {"received": 0, "analyzed": 0, "reused": 0, "failed": 0, "est_cost_usd": 0}
        series.append({"day": d, **{f: r.get(f, 0) for f in ("received", "analyzed", "reused", "successful", "failed", "fetch_failed", "est_cost_usd", "active_reps")}})
    by_month = {r["key"]: r for r in await _group(db, {"created_at": {"$gte": now - timedelta(days=366)}}, {"$ifNull": ["$month", {"$substrCP": ["$day", 0, 7]}]})}
    months, y, mo = [], now.year, now.month
    for _ in range(12):
        months.insert(0, f"{y:04d}-{mo:02d}")
        y, mo = (y, mo - 1) if mo > 1 else (y - 1, 12)
    empty = _finish({**{k: 0 for k in ACC if k != "reps"}, "reps": []})
    monthly = [{**(by_month.get(k) or empty), "key": k} for k in months]
    f = lambda k: {"$ifNull": [f"${k}", ""]}
    orgs = await _group(db, m, f("organization_id"), 200)
    stores = await _group(db, m, {"org": f("organization_id"), "store": f("store_id")}, 100)
    reps = await _group(db, m, {"org": f("organization_id"), "store": f("store_id"), "user": f("user_id")}, 100)
    by_source = await _group(db, m, f("source"))
    by_model = await _group(db, m, f("model"))
    org_names = await _names(db, "organizations", [r["key"] for r in orgs] + [r["key"]["org"] for r in stores + reps])
    store_names = await _names(db, "stores", [r["key"]["store"] for r in stores + reps])
    user_names = await _names(db, "users", [r["key"]["user"] for r in reps])
    dup = await db.vision_usage.aggregate([
        {"$match": {**m, "source": "mms", "message_id": {"$ne": None}, "i": {"$ne": None}}},
        {"$group": {"_id": {"m": "$message_id", "i": "$i"}, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]).to_list(1)
    return {
        "days": days, "since": since.isoformat(), "cost_basis": "estimate",
        "cost_method": (f"Estimated, not provider-billed: input tokens = image tiles (OpenAI high-detail: fit 2048 px, short side 768 px, 170 tokens "
                        f"per 512 px tile + 85) + prompt characters / 4, output tokens = reply characters / 4, at ${mv.PRICE_IN_PER_M}/1M input and "
                        f"${mv.PRICE_OUT_PER_M}/1M output (gpt-5.4). Failed attempts are costed on input. Reused photos cost $0."),
        "totals": total, "daily": series, "monthly": [{"month": r.pop("key"), **r} for r in monthly],
        "organizations": [{"organization_id": r["key"], "name": org_names.get(str(r["key"])) or (r["key"] or "Unattributed"), **{k: v for k, v in r.items() if k != "key"}} for r in orgs],
        "stores": [{"organization_id": r["key"]["org"], "org_name": org_names.get(str(r["key"]["org"])) or "", "store_id": r["key"]["store"],
                    "name": store_names.get(str(r["key"]["store"])) or (r["key"]["store"] or "No location"), **{k: v for k, v in r.items() if k != "key"}} for r in stores],
        "reps": [{"user_id": r["key"]["user"], "name": user_names.get(str(r["key"]["user"])) or "Unknown rep", "organization_id": r["key"]["org"],
                  "org_name": org_names.get(str(r["key"]["org"])) or "", "store_name": store_names.get(str(r["key"]["store"])) or "",
                  **{k: v for k, v in r.items() if k != "key"}} for r in reps],
        "by_source": [{"source": r.pop("key"), **r} for r in by_source], "by_model": [{"model": r.pop("key"), **r} for r in by_model],
        "monitoring": {"unattributed_rows": await db.vision_usage.count_documents({**m, "organization_id": {"$in": ["", None]}}),
                       "duplicate_processing": (dup[0]["n"] if dup else 0)},
    }
