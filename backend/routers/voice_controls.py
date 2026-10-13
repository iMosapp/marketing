"""Voice AI usage controls API (P2 + P4): global safety, per-account policies, per-user overrides and grants, allowance, ledger.
Writes are super_admin only; an org admin may read their own account."""
import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import voice_controls as vc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice-controls", tags=["Voice AI Controls"], dependencies=[Depends(require_user)])
RANGES = {"today": 1, "7d": 7, "30d": 30, "90d": 90}


class GlobalBody(BaseModel):
    enabled: Optional[bool] = None
    max_user_daily_premium_min: Optional[int] = None
    max_user_daily_backup_min: Optional[int] = None


class PolicyBody(BaseModel):
    enabled: Optional[bool] = None
    product: Optional[str] = None
    plan_key: Optional[str] = None
    premium_engine: Optional[str] = None
    backup_engine: Optional[str] = None
    premium_enabled: Optional[bool] = None
    backup_enabled: Optional[bool] = None
    per_user_daily_premium_min: Optional[int] = None
    per_user_daily_backup_min: Optional[int] = None
    account_daily_premium_min: Optional[int] = None
    account_monthly_premium_min: Optional[int] = None
    monthly_budget_usd: Optional[float] = None
    soft_warn_pcts: Optional[list] = None
    hard_premium_cap_usd: Optional[float] = None
    account_monthly_backup_usd: Optional[float] = None
    carry_over: Optional[bool] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None
    clear: Optional[list] = None  # field names to reset to "no limit"


class OverrideBody(BaseModel):
    daily_premium_min: Optional[int] = None
    daily_backup_min: Optional[int] = None
    premium_disabled: Optional[bool] = None
    super_admin_authorized: Optional[bool] = None
    notes: Optional[str] = None
    clear: Optional[list] = None


class GrantBody(BaseModel):
    minutes: int
    reason: str = ""
    day: Optional[str] = None


class PilotBody(BaseModel):
    premium_min: int = vc.PILOT_DEFAULTS["premium_min"]
    backup_min: int = vc.PILOT_DEFAULTS["backup_min"]
    hard_usd: float = vc.PILOT_DEFAULTS["hard_usd"]


def _is_super(me: dict) -> bool:
    return me.get("role") == "super_admin"


async def _super(request: Request) -> dict:
    me = await _resolve(request)
    if not _is_super(me):
        raise HTTPException(status_code=403, detail="Voice AI controls are for the app owner")
    return me


async def _reader(request: Request, db, org_id: str) -> dict:
    """Super admin: any account. Org admin: their own account only."""
    me = await _resolve(request)
    if _is_super(me):
        return me
    if me.get("role") in ("org_admin", "admin") and await vc.org_of(db, me) == org_id:
        return me
    raise HTTPException(status_code=403, detail="Not your account")


def _patch(body: BaseModel) -> dict:
    data = body.model_dump()
    clear = data.pop("clear", None) or []
    patch = {k: v for k, v in data.items() if v is not None}
    for k in clear:
        if k in data:
            patch[k] = None
    return patch


async def _user_in_org(db, org_id: str, user_id: str) -> dict:
    u = await db.users.find_one({"_id": vc._oid(user_id)}, {"name": 1, "email": 1, "role": 1, "organization_id": 1, "org_id": 1, "store_id": 1, "is_owner": 1, "timezone": 1}) if vc._oid(user_id) else None
    if not u or await vc.org_of(db, u) != org_id:
        raise HTTPException(status_code=404, detail="That user is not on this account")
    return u


def _since(range_key: str):
    days = RANGES.get(range_key, 1)
    now = vc._now()
    return (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)) if days > 1 else now - timedelta(hours=24)


# ── the signed-in user ────────────────────────────────────────────────────────
@router.get("/me")
async def my_allowance(request: Request):
    me = await _resolve(request)
    db = get_db()
    policy = await vc.enrolled_policy(db, me)
    if not policy:
        return {"enrolled": False, "policy_mode": "legacy", "org_id": await vc.org_of(db, me)}
    eff = await vc.resolve(db, me, policy)
    return {"enrolled": True, "policy_mode": "controls", **{k: eff[k] for k in ("org_id", "day", "timezone", "reset_at", "premium_engine", "backup_engine", "premium_allowance_s", "backup_allowance_s",
                                                                              "premium_used_s", "backup_used_s", "premium_reserved_s", "backup_reserved_s", "premium_left_s", "backup_left_s", "grants_min_today", "limits")},
            "next_engine": vc.pick_engine(policy, eff)}


# ── global safety ─────────────────────────────────────────────────────────────
@router.get("/global")
async def get_global(request: Request):
    await _super(request)
    return {"global": await vc.get_global(get_db()), "plan_catalog": vc.PLAN_CATALOG, "defaults": vc.DEFAULT_POLICY,
            "constants": {"slice_s": vc.SLICE_S, "min_start_s": vc.MIN_START_S, "heartbeat_stale_s": vc.HEARTBEAT_STALE_S, "grace_s": vc.GRACE_S},
            "fake_provider_allowed": vc.fake_provider_allowed()}


@router.put("/global")
async def put_global(body: GlobalBody, request: Request):
    me = await _super(request)
    return {"global": await vc.save_global(get_db(), {k: v for k, v in body.model_dump().items() if v is not None}, me)}


@router.get("/pricing")
async def pricing(request: Request):
    await _super(request)
    return vc.PRICING


# ── accounts ──────────────────────────────────────────────────────────────────
@router.get("/accounts")
async def accounts(request: Request, range: str = "30d"):
    await _super(request)
    db = get_db()
    rows = await vc.account_overview(db, _since(range))
    return {"range": range, "accounts": rows, "totals": {"premium_s": sum(r["premium_s"] for r in rows), "backup_s": sum(r["backup_s"] for r in rows),
                                                         "sessions": sum(r["sessions"] for r in rows), "est_cost_usd": round(sum(r["est_cost_usd"] for r in rows), 4),
                                                         "enabled": sum(1 for r in rows if r["enabled"])}}


@router.get("/accounts/{org_id}")
async def account(org_id: str, request: Request, range: str = "30d"):
    db = get_db()
    await _reader(request, db, org_id)
    policy = await vc.get_policy(db, org_id)
    overrides = [{k: o.get(k) for k in ("user_id", "daily_premium_min", "daily_backup_min", "premium_disabled", "super_admin_authorized", "notes", "updated_by")} | {"grants": len(o.get("grants") or [])}
                 async for o in db[vc.OVERRIDE_COLL].find({"org_id": org_id})]
    tz = await vc.account_tz(db, org_id, policy)
    now_local = vc._now().astimezone(tz)
    month = await db[vc.ACCT_MONTH_COLL].find_one({"_id": f"{org_id}:{vc.month_key(now_local)}"}) or {}
    day = await db[vc.ACCT_DAY_COLL].find_one({"_id": f"{org_id}:{vc.day_key(now_local)}"}) or {}
    return {"org_id": org_id, "name": await vc.org_name(db, org_id), "policy": policy, "timezone": str(tz), "overrides": overrides, "range": range,
            "users": await vc.user_usage(db, org_id, _since(range)),
            "today": {k: int(day.get(k) or 0) for k in ("premium_used_s", "premium_reserved_s", "backup_used_s", "backup_reserved_s", "sessions")},
            "month": {"premium_s": int(month.get("premium_s") or 0), "backup_s": int(month.get("backup_s") or 0), "est_cost_usd": round(float(month.get("est_cost_usd") or 0), 4),
                      "premium_cost_usd": round(float(month.get("premium_cost_usd") or 0), 4), "backup_cost_usd": round(float(month.get("backup_cost_usd") or 0), 4)}}


@router.put("/accounts/{org_id}")
async def put_policy(org_id: str, body: PolicyBody, request: Request):
    me = await _super(request)
    patch = _patch(body)
    if patch.get("premium_engine") and patch["premium_engine"] not in vc.ENGINE_ROLE:
        raise HTTPException(status_code=400, detail="Unknown engine")
    if patch.get("backup_engine") and patch["backup_engine"] not in vc.ENGINE_ROLE:
        raise HTTPException(status_code=400, detail="Unknown engine")
    if patch.get("plan_key") and patch["plan_key"] not in vc.PLAN_CATALOG:
        raise HTTPException(status_code=400, detail="Unknown plan")
    return {"policy": await vc.save_policy(get_db(), org_id, patch, me)}


# ── users on an account ───────────────────────────────────────────────────────
@router.get("/accounts/{org_id}/users/{user_id}")
async def user_detail(org_id: str, user_id: str, request: Request, limit: int = 30):
    db = get_db()
    await _reader(request, db, org_id)
    u = await _user_in_org(db, org_id, user_id)
    policy = await vc.get_policy(db, org_id)
    return {"user": {"id": str(u["_id"]), "name": u.get("name"), "email": u.get("email"), "role": u.get("role")},
            "override": await vc.get_override(db, org_id, user_id), "allowance": await vc.resolve(db, u, policy) if policy["enabled"] else None,
            "segments": await vc.list_segments(db, org_id, user_id, limit)}


@router.put("/accounts/{org_id}/users/{user_id}")
async def put_override(org_id: str, user_id: str, body: OverrideBody, request: Request):
    me = await _super(request)
    db = get_db()
    await _user_in_org(db, org_id, user_id)
    return {"override": await vc.save_override(db, org_id, user_id, _patch(body), me, super_admin=True)}


@router.post("/accounts/{org_id}/users/{user_id}/grant")
async def grant(org_id: str, user_id: str, body: GrantBody, request: Request):
    me = await _super(request)
    db = get_db()
    u = await _user_in_org(db, org_id, user_id)
    policy = await vc.get_policy(db, org_id)
    day = body.day or vc.day_key(vc._now().astimezone(await vc.account_tz(db, org_id, policy, u)))
    if body.minutes < 1 or body.minutes > 600:
        raise HTTPException(status_code=400, detail="Grant 1 to 600 minutes")
    return {"override": await vc.grant_minutes(db, org_id, user_id, body.minutes, me, day, body.reason)}


# ── ledger + maintenance ──────────────────────────────────────────────────────
@router.get("/ledger")
async def ledger(request: Request, org_id: str = "", user_id: str = "", limit: int = 50):
    await _super(request)
    return {"segments": await vc.list_segments(get_db(), org_id or None, user_id or None, limit)}


@router.get("/sessions/{live_id}/trail")
async def session_trail(live_id: str, request: Request):
    """Conversation audit trail (every engine segment, seconds, est. cost, cost basis, totals). Super admin, or the org admin of that account."""
    db = get_db()
    seg = await db[vc.LEDGER_COLL].find_one({"live_id": live_id, "kind": "segment"}, {"org_id": 1})
    if not seg:
        raise HTTPException(status_code=404, detail="No ledger for that session")
    await _reader(request, db, seg.get("org_id") or "")
    return await vc.trail(db, live_id)


@router.post("/watchdog")
async def run_watchdog(request: Request):
    await _super(request)
    return await vc.watchdog(get_db())


# ── founder pilot: the caller's OWN account only ──────────────────────────────
@router.get("/pilot")
async def pilot(request: Request):
    me = await _super(request)
    return await vc.pilot_status(get_db(), me)


@router.post("/pilot/enroll")
async def pilot_enroll(body: PilotBody, request: Request):
    me = await _super(request)
    if not (1 <= body.premium_min <= 240) or not (1 <= body.backup_min <= 480):
        raise HTTPException(status_code=400, detail="Allowances: 1 to 240 premium minutes and 1 to 480 backup minutes per day")
    if not (0.01 <= body.hard_usd <= 1000):
        raise HTTPException(status_code=400, detail="The monthly hard cap must be between $0.01 and $1000")
    return await vc.pilot_enroll(get_db(), me, body.premium_min, body.backup_min, round(body.hard_usd, 2))


class EngineModeBody(BaseModel):
    mode: str


@router.post("/pilot/engine-mode")
async def pilot_engine_mode(body: EngineModeBody, request: Request):
    me = await _super(request)
    if body.mode not in vc.ENGINE_MODES:
        raise HTTPException(status_code=400, detail="mode must be live_first or mini_only")
    return await vc.pilot_engine_mode(get_db(), me, body.mode)


@router.post("/pilot/kill")
async def pilot_kill(request: Request):
    """Kill switch: no new sessions on the account, every open session is hung up and finalized now."""
    me = await _super(request)
    db = get_db()
    org_id = await vc.org_of(db, me)
    await vc.save_policy(db, org_id, {"killed": True}, me)
    killed = await vc.kill_open_sessions(db, org_id)
    return {"killed": killed, **(await vc.pilot_status(db, me))}


@router.post("/pilot/resume")
async def pilot_resume(request: Request):
    me = await _super(request)
    db = get_db()
    await vc.save_policy(db, await vc.org_of(db, me), {"killed": False}, me)
    return await vc.pilot_status(db, me)


@router.post("/pilot/leave")
async def pilot_leave(request: Request):
    """Back to the legacy caps for the whole account (nothing is deleted: usage, ledger and the policy row stay for the record)."""
    me = await _super(request)
    db = get_db()
    org_id = await vc.org_of(db, me)
    await vc.save_policy(db, org_id, {"enabled": False, "killed": False, "cap_super_admins": False}, me)
    return {"killed": await vc.kill_open_sessions(db, org_id), **(await vc.pilot_status(db, me))}
