"""Trade Appraisal reporting (MVP5): a focused manager dashboard, the manager follow-up view and the salesperson pipeline. Facts and opportunities only;
no scoring. Every query carries the caller's scope and hits indexed fields (store/org/user + status/dates)."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services.appraisals import core, relationship
from services.appraisals.core import A, _now, _oid
from services.appraisals.workflow import OUTCOMES, OPEN_FOR_DECISION, STATUS_LABELS, DECISIONS as _D  # noqa: F401

DEC = "appraisal_decisions"
WAITING_TOO_LONG_S = 2 * 3600
BIG_GAP = 2000
BIG_ADJ = 1000
BIG_ADJ_PCT = 5.0


def _avg(rows: list, key) -> Optional[int]:
    vals = [key(r) for r in rows]
    vals = [v for v in vals if v is not None]
    return int(round(sum(vals) / len(vals))) if vals else None


def _dt(v):
    return v if (v is None or v.tzinfo) else v.replace(tzinfo=timezone.utc)


async def _base(db, me: dict, f: dict) -> dict:
    q = {"deleted": {"$ne": True}, **(await core.scope(me))}
    if f.get("store_id"):
        q["store_id"] = f["store_id"]
    if f.get("user_id"):
        q["user_id"] = f["user_id"]
    if f.get("manager_id"):
        q["approved_by"] = f["manager_id"]
    if f.get("outcome"):
        q["outcome"] = f["outcome"]
    if f.get("make"):
        q["vehicle.make"] = {"$regex": f"^{f['make']}$", "$options": "i"}
    if f.get("date_from") or f.get("date_to"):
        q["created_at"] = {k: v for k, v in (("$gte", f.get("date_from")), ("$lte", f.get("date_to"))) if v}
    return q


async def summary(db, me: dict, f: dict) -> dict:
    """Counts, averages and small fact tables for the filter. One scan of the filtered appraisals (indexed by scope + created_at)."""
    q = await _base(db, me, f)
    rows = await db[A].find(q, {"status": 1, "first_submitted_at": 1, "approved_at": 1, "presented_at": 1, "outcome": 1, "suggested_acv": 1, "approved_value": 1, "manager_adjustment": 1,
                               "customer_expected_value": 1, "trade_confirmed_at": 1, "user_id": 1, "user_name": 1, "approved_by": 1, "approved_by_name": 1, "vehicle.make": 1, "is_reappraisal": 1,
                               "declined_reason": 1}).to_list(5000)
    ids = [str(r["_id"]) for r in rows]
    first_dec = {}
    if ids:
        async for d in db[DEC].find({"appraisal_id": {"$in": ids}}, {"appraisal_id": 1, "response_s": 1, "manager_id": 1, "manager_name": 1, "action": 1, "decided_at": 1}).sort("decided_at", 1):
            first_dec.setdefault(d["appraisal_id"], d)
    accepted = [r for r in rows if r.get("outcome") == "accepted"]
    confirmed = [r for r in accepted if r.get("trade_confirmed_at")]
    gaps = [(r["customer_expected_value"] - (r.get("approved_value") or r.get("suggested_acv"))) for r in rows if r.get("customer_expected_value") and (r.get("approved_value") or r.get("suggested_acv"))]
    adj = [(r.get("manager_adjustment") or {}).get("delta") for r in rows if (r.get("manager_adjustment") or {}).get("delta") is not None]
    counts = {"started": len(rows), "reappraisals": sum(1 for r in rows if r.get("is_reappraisal")), "submitted": sum(1 for r in rows if r.get("first_submitted_at")),
              "approved": sum(1 for r in rows if r.get("approved_at")), "declined": sum(1 for r in rows if r.get("status") == "declined" or r.get("declined_reason")),
              "presented": sum(1 for r in rows if r.get("presented_at")), "closed": sum(1 for r in rows if r.get("status") == "closed"),
              **{o: sum(1 for r in rows if r.get("outcome") == o) for o in OUTCOMES}, "trade_confirmed": len(confirmed), "waiting_now": sum(1 for r in rows if r.get("status") in OPEN_FOR_DECISION)}
    presented = counts["presented"] or 0
    averages = {"suggested_acv": _avg(rows, lambda r: r.get("suggested_acv")), "approved_value": _avg(rows, lambda r: r.get("approved_value")),
                "manager_adjustment": int(round(sum(adj) / len(adj))) if adj else None, "manager_adjustment_abs": int(round(sum(abs(a) for a in adj) / len(adj))) if adj else None,
                "expectation_gap": int(round(sum(gaps) / len(gaps))) if gaps else None,
                "manager_response_s": _avg(list(first_dec.values()), lambda d: d.get("response_s"))}
    rates = {"acceptance": round(len(accepted) / presented * 100, 1) if presented else None, "confirmed_trade": round(len(confirmed) / len(accepted) * 100, 1) if accepted else None,
             "approval": round(counts["approved"] / counts["submitted"] * 100, 1) if counts["submitted"] else None}

    def table(key_fn, name_fn):
        groups: dict = {}
        for r in rows:
            k = key_fn(r)
            if not k:
                continue
            g = groups.setdefault(k, {"id": k, "name": name_fn(r), "started": 0, "submitted": 0, "approved": 0, "presented": 0, "accepted": 0, "wants_more": 0, "thinking": 0, "not_trading": 0, "_sug": [], "_app": [], "_adj": [], "_gap": []})
            g["started"] += 1
            g["submitted"] += 1 if r.get("first_submitted_at") else 0
            g["approved"] += 1 if r.get("approved_at") else 0
            g["presented"] += 1 if r.get("presented_at") else 0
            for o in ("accepted", "wants_more", "thinking", "not_trading"):
                g[o] += 1 if r.get("outcome") == o else 0
            if r.get("suggested_acv") is not None: g["_sug"].append(r["suggested_acv"])
            if r.get("approved_value") is not None: g["_app"].append(r["approved_value"])
            if (r.get("manager_adjustment") or {}).get("delta") is not None: g["_adj"].append(r["manager_adjustment"]["delta"])
            if r.get("customer_expected_value") and (r.get("approved_value") or r.get("suggested_acv")): g["_gap"].append(r["customer_expected_value"] - (r.get("approved_value") or r.get("suggested_acv")))
        out = []
        for g in groups.values():
            out.append({**{k: v for k, v in g.items() if not k.startswith("_")}, "avg_suggested": int(sum(g["_sug"]) / len(g["_sug"])) if g["_sug"] else None, "avg_approved": int(sum(g["_app"]) / len(g["_app"])) if g["_app"] else None,
                        "avg_adjustment": int(sum(g["_adj"]) / len(g["_adj"])) if g["_adj"] else None, "avg_gap": int(sum(g["_gap"]) / len(g["_gap"])) if g["_gap"] else None,
                        "acceptance": round(g["accepted"] / g["presented"] * 100, 1) if g["presented"] else None})
        return sorted(out, key=lambda x: -x["started"])

    by_sales = table(lambda r: r.get("user_id"), lambda r: r.get("user_name") or "Rep")
    by_manager = table(lambda r: r.get("approved_by"), lambda r: r.get("approved_by_name") or "Manager")
    for m in by_manager:
        rs = [d.get("response_s") for d in first_dec.values() if d.get("manager_id") == m["id"] and d.get("response_s") is not None]
        m["avg_response_s"] = int(sum(rs) / len(rs)) if rs else None
        m["decisions"] = sum(1 for d in first_dec.values() if d.get("manager_id") == m["id"])
    by_make = table(lambda r: ((r.get("vehicle") or {}).get("make") or "").title() or None, lambda r: ((r.get("vehicle") or {}).get("make") or "").title())
    return {"filters": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in f.items()}, "counts": counts, "averages": averages, "rates": rates,
            "by_salesperson": by_sales, "by_manager": by_manager, "by_make": by_make[:15], "options": await filter_options(db, me)}


async def filter_options(db, me: dict) -> dict:
    scope_q = {"deleted": {"$ne": True}, **(await core.scope(me))}
    reps = await db[A].aggregate([{"$match": scope_q}, {"$group": {"_id": "$user_id", "name": {"$last": "$user_name"}}}, {"$limit": 200}]).to_list(200)
    mgrs = await db[A].aggregate([{"$match": {**scope_q, "approved_by": {"$ne": None}}}, {"$group": {"_id": "$approved_by", "name": {"$last": "$approved_by_name"}}}, {"$limit": 100}]).to_list(100)
    makes = await db[A].distinct("vehicle.make", scope_q)
    store_ids = await db[A].distinct("store_id", scope_q)
    stores = await db.stores.find({"_id": {"$in": [ObjectId(s) for s in store_ids if s and ObjectId.is_valid(str(s))]}}, {"name": 1}).to_list(50) if store_ids else []
    return {"salespeople": sorted([{"id": r["_id"], "name": r.get("name") or "Rep"} for r in reps if r["_id"]], key=lambda x: x["name"]),
            "managers": sorted([{"id": r["_id"], "name": r.get("name") or "Manager"} for r in mgrs if r["_id"]], key=lambda x: x["name"]),
            "makes": sorted({(m or "").title() for m in makes if m}), "stores": [{"id": str(s["_id"]), "name": s.get("name")} for s in stores], "outcomes": OUTCOMES}


def _row(a: dict, now=None) -> dict:
    now = now or _now()
    basis = a.get("approved_value") or a.get("suggested_acv")
    return {**core.public_appraisal(a), "status_label": STATUS_LABELS.get(a.get("status") or "", a.get("status")), "outcome_label": OUTCOMES.get(a.get("outcome") or "", None),
            "gap": (a["customer_expected_value"] - basis) if a.get("customer_expected_value") and basis else None,
            "manager_delta": (a.get("manager_adjustment") or {}).get("delta"), "manager_delta_pct": (a.get("manager_adjustment") or {}).get("delta_percentage"), "approved_by_name": a.get("approved_by_name"),
            "needs_info_request": a.get("needs_info_request"), "market_retail": (a.get("market_summary") or {}).get("estimated_retail"), "market_live": (a.get("market_summary") or {}).get("live"),
            "waiting_s": int((now - _dt(a["submitted_at"])).total_seconds()) if a.get("submitted_at") and a.get("status") in OPEN_FOR_DECISION else None,
            "age_s": int((now - _dt(a["updated_at"])).total_seconds()) if a.get("updated_at") else None}


async def search(db, me: dict, q: str = "", status: Optional[str] = None, outcome: Optional[str] = None, make: Optional[str] = None, user_id: Optional[str] = None,
                 store_id: Optional[str] = None, date_from=None, date_to=None, limit: int = 100) -> dict:
    """Appraisal search: VIN, customer, salesperson, vehicle, stock #, plus status / outcome / make / rep / store / date filters. Scoped."""
    import re
    f = {k: v for k, v in {"user_id": user_id, "store_id": store_id, "outcome": outcome, "make": make, "date_from": date_from, "date_to": date_to}.items() if v}
    base = await _base(db, me, f)
    if status:
        base["status"] = {"$in": [s for s in status.split(",") if s]}
    q = (q or "").strip()
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        base["$or"] = [{"contact_name": rx}, {"vin": rx}, {"stock_number": rx}, {"user_name": rx}, {"vehicle.make": rx}, {"vehicle.model": rx}, {"vehicle.trim": rx}]
        if q.isdigit() and len(q) == 4:
            base["$or"].append({"vehicle.year": int(q)})
    rows = await db[A].find(base).sort("updated_at", -1).to_list(max(1, min(limit, 300)))
    now = _now()
    return {"appraisals": [_row(a, now) for a in rows], "total": await db[A].count_documents(base), "statuses": STATUS_LABELS, "outcomes": OUTCOMES}


async def followup_view(db, me: dict) -> dict:
    """Manager follow-up: facts and opportunities, newest first. No salesperson scoring."""
    base = {"deleted": {"$ne": True}, **(await core.scope(me))}
    now = _now()
    row = lambda a: _row(a, now)
    waiting = [row(a) for a in await db[A].find({**base, "status": {"$in": list(OPEN_FOR_DECISION)}, "submitted_at": {"$lte": now - timedelta(seconds=WAITING_TOO_LONG_S)}}).sort("submitted_at", 1).to_list(50)]
    recent = {**base, "updated_at": {"$gte": now - timedelta(days=90)}}
    gaps = [r for r in (row(a) for a in await db[A].find({**recent, "customer_expected_value": {"$ne": None}, "status": {"$in": ["approved", "changed", "presented", "closed"]}}).sort("updated_at", -1).to_list(300)) if (r["gap"] or 0) >= BIG_GAP]
    adjs = [r for r in (row(a) for a in await db[A].find({**recent, "manager_adjustment.delta": {"$ne": None}}).sort("approved_at", -1).to_list(300)) if abs(r["manager_delta"] or 0) >= BIG_ADJ or abs(r["manager_delta_pct"] or 0) >= BIG_ADJ_PCT]
    wants = [row(a) for a in await db[A].find({**base, "outcome": "wants_more", "closed_at": {"$gte": now - timedelta(days=180)}}).sort("closed_at", -1).to_list(50)]
    thinking = [row(a) for a in await db[A].find({**base, "outcome": "thinking", "closed_at": {"$gte": now - timedelta(days=180)}}).sort("closed_at", -1).to_list(50)]
    old = await relationship.opportunities(db, me, limit=50)
    return {"waiting_too_long": waiting, "large_gaps": sorted(gaps, key=lambda r: -(r["gap"] or 0))[:50], "large_adjustments": sorted(adjs, key=lambda r: -abs(r["manager_delta"] or 0))[:50],
            "wants_more": wants, "thinking": thinking, "revisit": [o for o in old if o["kind"] == "stale"], "thresholds": {"waiting_s": WAITING_TOO_LONG_S, "gap": BIG_GAP, "adjustment": BIG_ADJ, "adjustment_pct": BIG_ADJ_PCT},
            "counts": {"waiting_too_long": len(waiting), "large_gaps": len(gaps), "large_adjustments": len(adjs), "wants_more": len(wants), "thinking": len(thinking), "revisit": sum(1 for o in old if o["kind"] == "stale")}}


async def pipeline(db, me: dict, team: bool = False) -> dict:
    """MY TRADE PIPELINE for a salesperson: what to do next, in order. Managers may ask for the team view (their scope)."""
    is_mgr = me.get("role") in ("store_manager", "org_admin", "super_admin")
    mine = not (team and is_mgr)
    base = {"deleted": {"$ne": True}, **(await core.scope(me)), **({"user_id": str(me["_id"])} if mine else {})}
    now = _now()
    row = lambda a: _row(a, now)
    needs = [row(a) for a in await db[A].find({**base, "$or": [{"status": "needs_info"}, {"status": {"$in": ["draft", "capturing", "ready"]}, "updated_at": {"$lte": now - timedelta(hours=24)}}]}).sort("updated_at", 1).to_list(50)]
    waiting = [row(a) for a in await db[A].find({**base, "status": {"$in": list(OPEN_FOR_DECISION)}}).sort("submitted_at", 1).to_list(50)]
    present = [row(a) for a in await db[A].find({**base, "status": {"$in": ["approved", "changed"]}}).sort("approved_at", 1).to_list(50)]
    presented = [row(a) for a in await db[A].find({**base, "status": {"$in": ["presented", "declined"]}}).sort("updated_at", 1).to_list(50)]
    opps = await relationship.opportunities(db, me, limit=30, user_id=str(me["_id"]) if mine else None)
    closed = [row(a) for a in await db[A].find({**base, "status": "closed", "closed_at": {"$gte": now - timedelta(days=30)}}).sort("closed_at", -1).to_list(30)]
    groups = [{"key": "needs_attention", "label": "Needs attention", "items": needs}, {"key": "waiting_on_manager", "label": "Waiting on manager", "items": waiting},
              {"key": "approved_to_present", "label": "Approved, present it", "items": present}, {"key": "presented_follow_up", "label": "Presented, follow up", "items": presented},
              {"key": "reappraisal_opportunities", "label": "Reappraisal opportunities", "items": opps}, {"key": "recently_closed", "label": "Recently closed", "items": closed}]
    return {"groups": groups, "counts": {g["key"]: len(g["items"]) for g in groups}, "actionable": sum(len(g["items"]) for g in groups[:5]), "team": not mine, "can_team": is_mgr}
