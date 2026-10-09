"""Company-scoped plumbing for the leadership team: tenant resolution, controls (budget, stop), usage, audit.
Isolation is enforced here and in every query, never by prompt text."""
from datetime import datetime, timedelta, timezone

from services import command_center as cc
from services import command_center_ai as ai

COMPANIES, AUDIT = "lt_companies", "lt_audit"
DEFAULT_COMPANY = "imos"
DEFAULT_CONTROLS = {"soft_usd": 25.0, "hard_usd": 50.0, "stopped": False, "max_participants": 6, "hourly_calls": 120}


def _now():
    return datetime.now(timezone.utc)


def company_for(me: dict) -> str:
    """Phase 1: the founder's own company. Membership-based resolution (Phase 3) replaces this function and nothing else."""
    return DEFAULT_COMPANY


def scope(company_id: str) -> dict:
    """Query filter for company-owned records. Legacy Command Center documents carry no company_id and belong to the default company."""
    return {"$or": [{"company_id": company_id}, {"company_id": {"$exists": False}}]} if company_id == DEFAULT_COMPANY else {"company_id": company_id}


async def company(db, company_id: str) -> dict:
    doc = await db[COMPANIES].find_one({"_id": company_id})
    if not doc:
        doc = {"_id": company_id, "name": "I'm On Social" if company_id == DEFAULT_COMPANY else company_id, "controls": dict(DEFAULT_CONTROLS), "created_at": _now(), "updated_at": _now()}
        await db[COMPANIES].update_one({"_id": company_id}, {"$setOnInsert": doc}, upsert=True)
    doc["controls"] = {**DEFAULT_CONTROLS, **(doc.get("controls") or {})}
    return doc


async def update_controls(db, company_id: str, body: dict, me: dict) -> dict:
    cur = (await company(db, company_id))["controls"]
    upd = {}
    for k in ("soft_usd", "hard_usd"):
        if k in body and body[k] is not None:
            upd[k] = max(0.0, float(body[k]))
    if "max_participants" in body and body["max_participants"] is not None:
        upd["max_participants"] = max(2, min(6, int(body["max_participants"])))
    if "stopped" in body:
        upd["stopped"] = bool(body["stopped"])
    if upd.get("hard_usd", cur["hard_usd"]) < upd.get("soft_usd", cur["soft_usd"]):
        raise ValueError("The hard limit cannot be below the soft warning")
    await db[COMPANIES].update_one({"_id": company_id}, {"$set": {**{f"controls.{k}": v for k, v in upd.items()}, "updated_at": _now()}})
    await audit(db, company_id, me, "controls_updated", {"kind": "company", "id": company_id}, before=cur, after={**cur, **upd})
    return (await company(db, company_id))["controls"]


def _usage_filter(company_id: str, since: datetime) -> dict:
    # Pre-leadership advisor rows have no company_id; they are the default company's spend.
    return {"created_at": {"$gte": since}, **scope(company_id)}


async def month_spend(db, company_id: str) -> float:
    start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = await db[ai.USAGE].aggregate([{"$match": _usage_filter(company_id, start)}, {"$group": {"_id": None, "cost": {"$sum": "$approx_cost_usd"}}}]).to_list(1)
    return round(float(rows[0]["cost"]) if rows else 0.0, 4)


async def check_budget(db, company_id: str):
    """Hard limit and emergency stop refuse NEW model work only; reading conversations, briefs and decisions keeps working."""
    c = await company(db, company_id)
    ctl = c["controls"]
    if ctl.get("stopped"):
        raise ai.AdvisorBusy("Emergency stop is on for the leadership team. Resume it in Team > Controls to start new AI work.")
    spent = await month_spend(db, company_id)
    if spent >= ctl["hard_usd"]:
        raise ai.AdvisorBusy(f"The leadership team reached its monthly hard limit (${ctl['hard_usd']:.2f}); ${spent:.2f} used. Raise the limit in Team > Controls to continue.")
    n = await db[ai.USAGE].count_documents({"created_at": {"$gte": _now() - timedelta(hours=1)}, "kind": {"$regex": "^lt_"}, **scope(company_id)})
    if n >= ctl.get("hourly_calls", 120):
        raise ai.AdvisorBusy("The leadership team made too many model calls in the last hour; give it a few minutes.")
    return {"spent": spent, "soft": ctl["soft_usd"], "hard": ctl["hard_usd"], "warning": spent >= ctl["soft_usd"]}


async def usage(db, company_id: str) -> dict:
    c = await company(db, company_id)
    spent = await month_spend(db, company_id)

    async def window(h):
        rows = await db[ai.USAGE].aggregate([{"$match": {**_usage_filter(company_id, _now() - timedelta(hours=h)), "kind": {"$regex": "^lt_"}}},
                                             {"$group": {"_id": "$kind", "n": {"$sum": 1}, "pin": {"$sum": "$prompt_tokens"}, "pout": {"$sum": "$completion_tokens"}, "cost": {"$sum": "$approx_cost_usd"}, "failed": {"$sum": {"$cond": ["$ok", 0, 1]}}}}]).to_list(30)
        return {"requests": sum(r["n"] for r in rows), "failures": sum(r["failed"] for r in rows), "prompt_tokens": sum(r["pin"] for r in rows), "completion_tokens": sum(r["pout"] for r in rows),
                "approx_cost_usd": round(sum(r["cost"] for r in rows), 4), "by_kind": {r["_id"]: {"n": r["n"], "approx_cost_usd": round(r["cost"], 4)} for r in rows}}
    return {"month_spend_usd": spent, "month_all_ai_usd": spent, "controls": c["controls"], "soft_warning": spent >= c["controls"]["soft_usd"], "hard_reached": spent >= c["controls"]["hard_usd"],
            "last_24h": await window(24), "last_30d": await window(24 * 30), "model": ai.MODEL[1], "prices_per_1m_tokens": {"input": ai.PRICES[ai.MODEL[1]][0], "output": ai.PRICES[ai.MODEL[1]][1], "approximate": True},
            "measured_note": "Costs are computed from the provider's reported token counts at the list prices above; they are approximate, never invented."}


async def audit(db, company_id: str, me: dict | None, action: str, subject: dict, before=None, after=None, reason: str = ""):
    await db[AUDIT].insert_one({"company_id": company_id, "at": _now(), "actor": {"kind": "human", **cc._who(me)} if me else {"kind": "system"}, "action": action, "subject": subject,
                                "before": before, "after": after, "reason": (reason or "")[:500]})


async def audit_list(db, company_id: str, limit: int = 100) -> list:
    rows = await db[AUDIT].find({"company_id": company_id}).sort("at", -1).to_list(limit)
    return [{**{k: v for k, v in r.items() if k != "_id"}, "id": str(r["_id"]), "at": cc._iso(r["at"])} for r in rows]
