"""Voice AI usage controls (P2 + P4): per-account policy, per-user overrides, server-authoritative metering with atomic reservations,
a segment ledger with labelled cost basis, and fail-safes. Accounts without an enabled policy keep the legacy live_voice path untouched
(they still get a `policy_mode: legacy` ledger row so the dashboard sees every session).

Allowance precedence: global safety -> account budget / shared caps -> user override -> account default.
Cost basis labels: server_clock (seconds measured by this server), client_report (tokens/seconds the app forwarded),
provider_usage (OpenAI sideband / session.closed, P3), invoice (reconciled actuals). Everything else is an estimate."""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

logger = logging.getLogger(__name__)

POLICY_COLL = "voice_policies"
OVERRIDE_COLL = "voice_user_overrides"
RES_COLL = "voice_reservations"          # one doc per org:user:day
ACCT_DAY_COLL = "voice_account_days"     # one doc per org:day
ACCT_MONTH_COLL = "voice_account_months"  # one doc per org:month
LEDGER_COLL = "voice_usage_ledger"       # one row per session segment (+ admin change rows)
GLOBAL_KEY = "voice_ai_global"

SLICE_S = 60             # seconds reserved per step; a device never holds more than about one unspent slice
MIN_START_S = 20         # do not start an engine with less than this left
HEARTBEAT_STALE_S = 150  # no client event for this long -> watchdog finalizes the segment (GPT-Live reports usage about once a minute)
GRACE_S = 30             # seconds added past the last heartbeat when finalizing an unconfirmed segment
STOP_GRACE_S = 20        # a session told to stop that is still open after this long is closed on the provider side (kill switch)
KILL_MAX_ATTEMPTS = 3
CONFIRMED_CLOSE_REASONS = ("close_requested", "idle", "daily_cap", "premium_cap", "backup_cap", "voice_cap", "handoff", "killed")
ENGINE_ROLE = {"live": "premium", "mini": "backup"}
ENGINE_MODES = ("live_first", "mini_only")  # founder test setting: premium first with automatic hand-off (default) or the backup engine for every session
TEST_EMAIL_SUFFIX = "@invalid.imonsocial.test"

PRICING = {"verified_on": "2026-10-13", "source": "developers.openai.com/api/docs/pricing",
           "live": {"model": "gpt-live-1", "per_min_usd": 0.05, "billing": "per second", "min_charge_s": 15},
           "mini": {"model": "gpt-realtime-2.1-mini", "per_1m_tokens_usd": {"audio_in": 10.0, "audio_in_cached": 0.30, "text_in": 0.60, "text_in_cached": 0.06, "audio_out": 20.0, "text_out": 2.40},
                    "fallback_per_min_usd": 0.015, "note": "minute rate used only when no token usage was reported"}}

DEFAULT_POLICY = {"enabled": False, "product": "imos", "plan_key": "standard", "premium_engine": "live", "backup_engine": "mini",
                  "premium_enabled": True, "backup_enabled": True,
                  "per_user_daily_premium_min": 15, "per_user_daily_backup_min": 60,
                  "account_daily_premium_min": None, "account_monthly_premium_min": None,
                  "monthly_budget_usd": None, "soft_warn_pcts": [80], "hard_premium_cap_usd": None, "account_monthly_backup_usd": None,
                  "account_monthly_hard_usd": None, "cap_super_admins": False, "killed": False, "engine_mode": "live_first",
                  "carry_over": False, "timezone": None, "notes": ""}
GLOBAL_DEFAULTS = {"enabled": True, "max_user_daily_premium_min": 240, "max_user_daily_backup_min": 480, "pricing": PRICING,
                   # production rollout: every account is on voice controls with these defaults unless it has its own setting or was switched off
                   "all_accounts": False, "default_premium_min": 15, "default_backup_min": 60, "default_monthly_hard_usd": 50.0}
ROLLOUT_FIELDS = {"per_user_daily_premium_min": "default_premium_min", "per_user_daily_backup_min": "default_backup_min", "account_monthly_hard_usd": "default_monthly_hard_usd"}
PLAN_CATALOG = {"standard": {"per_user_daily_premium_min": 15}, "pro": {"per_user_daily_premium_min": 30}, "unlimited": {"per_user_daily_premium_min": 240}}
INT_FIELDS = ("per_user_daily_premium_min", "per_user_daily_backup_min", "account_daily_premium_min", "account_monthly_premium_min")
USD_FIELDS = ("monthly_budget_usd", "hard_premium_cap_usd", "account_monthly_backup_usd", "account_monthly_hard_usd")
BOOL_FIELDS = ("enabled", "premium_enabled", "backup_enabled", "carry_over", "cap_super_admins", "killed")
DEFAULT_OVERRIDE = {"daily_premium_min": None, "daily_backup_min": None, "premium_disabled": False, "super_admin_authorized": False, "notes": "", "grants": []}
STOP_MESSAGES = {"premium_cap": "You have used today's premium Jessi minutes.", "backup_cap": "Jessi's voice is done for today. It resets at midnight.",
                 "killed": "Live Jessi was paused by the account owner."}


class NoAllowance(Exception):
    pass


def _now():
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _oid(s) -> Optional[ObjectId]:
    return ObjectId(str(s)) if s is not None and ObjectId.is_valid(str(s)) else None


def fake_provider_allowed(user: Optional[dict] = None) -> bool:
    """Preview-only switch: VOICE_FAKE_PROVIDER_ALLOWED=1 lets super admins and @invalid.imonsocial.test accounts open sessions without OpenAI. Inert in production."""
    from services.runtime_env import preview_flag
    if not preview_flag("VOICE_FAKE_PROVIDER_ALLOWED"):
        return False
    if user is None:
        return True
    return user.get("role") == "super_admin" or str(user.get("email") or "").lower().endswith(TEST_EMAIL_SUFFIX)


# ── tenant helpers ─────────────────────────────────────────────────────────────
async def org_of(db, user: dict) -> str:
    """Account key for a user: organization, else the store's organization, else the store, else the user themselves."""
    org = user.get("organization_id") or user.get("org_id")
    if org:
        return str(org)
    if user.get("store_id"):
        store = None
        oid = _oid(user["store_id"])
        if oid:
            store = await db.stores.find_one({"_id": oid}, {"organization_id": 1, "org_id": 1})
        if store and (store.get("organization_id") or store.get("org_id")):
            return str(store.get("organization_id") or store.get("org_id"))
        return f"store:{user['store_id']}"
    return f"user:{user['_id']}"


async def org_name(db, org_id: str) -> str:
    if org_id.startswith("store:"):
        s = await db.stores.find_one({"_id": _oid(org_id[6:])}, {"name": 1}) if _oid(org_id[6:]) else None
        return f"Store: {(s or {}).get('name') or org_id[6:]}"
    if org_id.startswith("user:"):
        u = await db.users.find_one({"_id": _oid(org_id[5:])}, {"name": 1, "email": 1}) if _oid(org_id[5:]) else None
        return f"Solo: {(u or {}).get('name') or (u or {}).get('email') or org_id[5:]}"
    o = await db.organizations.find_one({"_id": _oid(org_id)}, {"name": 1}) if _oid(org_id) else None
    return (o or {}).get("name") or org_id


async def account_tz(db, org_id: str, policy: dict, user: Optional[dict] = None):
    name = policy.get("timezone")
    if not name:
        org = await db.organizations.find_one({"_id": _oid(org_id)}, {"timezone": 1}) if _oid(org_id) else None
        name = (org or {}).get("timezone")
    if not name and user is not None:
        from routers.user_schedule import resolve_user_tz
        try:
            name = await resolve_user_tz(str(user["_id"]))
        except Exception:
            name = None
    try:
        return ZoneInfo(name or "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


def day_key(now_local: datetime) -> str:
    return now_local.strftime("%Y-%m-%d")


def month_key(now_local: datetime) -> str:
    return now_local.strftime("%Y-%m")


# ── settings: global, policy, overrides ───────────────────────────────────────
async def get_global(db) -> dict:
    doc = await db.settings.find_one({"key": GLOBAL_KEY}) or {}
    g = {**GLOBAL_DEFAULTS, **{k: v for k, v in (doc.get("value") or {}).items() if k in GLOBAL_DEFAULTS and k != "pricing"}}
    g["updated_at"] = doc.get("updated_at").isoformat() if doc.get("updated_at") else None
    g["updated_by"] = doc.get("updated_by")
    return g


async def save_global(db, patch: dict, by: dict) -> dict:
    cur = await get_global(db)
    val = {k: cur[k] for k in GLOBAL_DEFAULTS if k != "pricing"}
    if "enabled" in patch:
        val["enabled"] = bool(patch["enabled"])
    for k in ("max_user_daily_premium_min", "max_user_daily_backup_min"):
        if k in patch and patch[k] is not None:
            val[k] = min(1440, max(1, int(patch[k])))
    if "all_accounts" in patch:
        val["all_accounts"] = bool(patch["all_accounts"])
    for k in ("default_premium_min", "default_backup_min"):
        if k in patch and patch[k] is not None:
            val[k] = min(1440, max(0, int(patch[k])))
    if "default_monthly_hard_usd" in patch:
        val["default_monthly_hard_usd"] = None if patch["default_monthly_hard_usd"] in (None, "") else round(min(100000.0, max(0.01, float(patch["default_monthly_hard_usd"]))), 2)
    await db.settings.update_one({"key": GLOBAL_KEY}, {"$set": {"value": val, "updated_at": _now(), "updated_by": by.get("email")}}, upsert=True)
    await db[LEDGER_COLL].insert_one({"kind": "admin_global_change", "by": by.get("email"), "at": _now(), "patch": val})
    return await get_global(db)


def clean_policy(patch: dict, base: dict) -> dict:
    p = dict(base)
    for k in BOOL_FIELDS:
        if k in patch:
            p[k] = bool(patch[k])
    for k in INT_FIELDS:
        if k in patch:
            p[k] = None if patch[k] in (None, "") else min(1440 * 31, max(0, int(patch[k])))
    for k in USD_FIELDS:
        if k in patch:
            p[k] = None if patch[k] in (None, "") else round(max(0.0, float(patch[k])), 2)
    if "soft_warn_pcts" in patch and isinstance(patch["soft_warn_pcts"], list):
        p["soft_warn_pcts"] = sorted({min(100, max(1, int(x))) for x in patch["soft_warn_pcts"]})[:5]
    if patch.get("premium_engine") in ENGINE_ROLE:
        p["premium_engine"] = patch["premium_engine"]
    if patch.get("backup_engine") in ENGINE_ROLE:
        p["backup_engine"] = patch["backup_engine"]
    if patch.get("engine_mode") in ENGINE_MODES:
        p["engine_mode"] = patch["engine_mode"]
    if patch.get("plan_key") in PLAN_CATALOG:
        p["plan_key"] = patch["plan_key"]
    if "timezone" in patch:
        tz = patch["timezone"]
        if tz in (None, ""):
            p["timezone"] = None
        else:
            try:
                ZoneInfo(str(tz))
                p["timezone"] = str(tz)
            except Exception:
                pass
    if isinstance(patch.get("notes"), str):
        p["notes"] = patch["notes"].strip()[:600]
    if isinstance(patch.get("product"), str) and patch["product"].strip():
        p["product"] = patch["product"].strip()[:24]
    return p


def _custom_keys(doc: dict) -> list:
    """Fields this account set on purpose. Rows written before the rollout kept every field, so all of them count as set."""
    c = doc.get("custom")
    return [k for k in (c if isinstance(c, list) else doc.keys()) if k in DEFAULT_POLICY]


def account_defaults(g: dict) -> dict:
    """What an account gets without its own setting: the rollout defaults while voice controls is on for every account."""
    base = dict(DEFAULT_POLICY)
    if g.get("all_accounts"):
        base["enabled"] = True
        for field, gk in ROLLOUT_FIELDS.items():
            base[field] = g.get(gk)
    return base


async def get_policy(db, org_id: str, g: Optional[dict] = None) -> dict:
    g = g or await get_global(db)
    doc = await db[POLICY_COLL].find_one({"org_id": org_id}) or {}
    custom = _custom_keys(doc)
    p = {**account_defaults(g), **{k: doc[k] for k in custom if k in doc}}
    p.update({"org_id": org_id, "exists": bool(doc), "custom": sorted(custom), "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None, "updated_by": doc.get("updated_by")})
    return p


async def save_policy(db, org_id: str, patch: dict, by: dict, reset: Optional[list] = None) -> dict:
    """Writes only what changed and remembers it as this account's own setting; `reset` hands fields back to the defaults."""
    cur = await get_policy(db, org_id)
    p = clean_policy(patch, {k: cur[k] for k in DEFAULT_POLICY})
    changed = {k: p[k] for k in patch if k in DEFAULT_POLICY}
    reset = [k for k in (reset or []) if k in DEFAULT_POLICY and k not in changed]
    doc = await db[POLICY_COLL].find_one({"org_id": org_id}) or {}
    custom = sorted((set(_custom_keys(doc)) | set(changed)) - set(reset))
    upd = {"$set": {**changed, "custom": custom, "updated_at": _now(), "updated_by": by.get("email")}, "$setOnInsert": {"created_at": _now()}}
    if reset:
        upd["$unset"] = {k: "" for k in reset}
    await db[POLICY_COLL].update_one({"org_id": org_id}, upd, upsert=True)
    await db[LEDGER_COLL].insert_one({"org_id": org_id, "kind": "admin_policy_change", "by": by.get("email"), "at": _now(), "patch": changed, "reset": reset})
    return await get_policy(db, org_id)


async def get_override(db, org_id: str, user_id: str) -> dict:
    doc = await db[OVERRIDE_COLL].find_one({"org_id": org_id, "user_id": user_id}) or {}
    o = {**DEFAULT_OVERRIDE, **{k: v for k, v in doc.items() if k in DEFAULT_OVERRIDE}}
    for g in o.get("grants") or []:
        if hasattr(g.get("at"), "isoformat"):
            g["at"] = g["at"].isoformat()
    o.update({"org_id": org_id, "user_id": user_id, "exists": bool(doc), "updated_by": doc.get("updated_by")})
    return o


async def save_override(db, org_id: str, user_id: str, patch: dict, by: dict, super_admin: bool) -> dict:
    cur = await get_override(db, org_id, user_id)
    o = {k: cur[k] for k in DEFAULT_OVERRIDE if k != "grants"}
    for k in ("daily_premium_min", "daily_backup_min"):
        if k in patch:
            o[k] = None if patch[k] in (None, "") else min(1440, max(0, int(patch[k])))
    if "premium_disabled" in patch:
        o["premium_disabled"] = bool(patch["premium_disabled"])
    if "super_admin_authorized" in patch and super_admin:
        o["super_admin_authorized"] = bool(patch["super_admin_authorized"])
    if isinstance(patch.get("notes"), str):
        o["notes"] = patch["notes"].strip()[:600]
    await db[OVERRIDE_COLL].update_one({"org_id": org_id, "user_id": user_id},
                                       {"$set": {**o, "updated_at": _now(), "updated_by": by.get("email")}, "$setOnInsert": {"grants": [], "created_at": _now()}}, upsert=True)
    await db[LEDGER_COLL].insert_one({"org_id": org_id, "user_id": user_id, "kind": "admin_override", "by": by.get("email"), "at": _now(), "patch": o})
    return await get_override(db, org_id, user_id)


async def grant_minutes(db, org_id: str, user_id: str, minutes: int, by: dict, day: str, reason: str = "") -> dict:
    minutes = min(600, max(1, int(minutes)))
    grant = {"id": uuid.uuid4().hex[:8], "minutes": minutes, "day": day, "reason": (reason or "")[:200], "by": by.get("email"), "at": _now()}
    await db[OVERRIDE_COLL].update_one({"org_id": org_id, "user_id": user_id},
                                       {"$push": {"grants": grant}, "$set": {"updated_at": _now()},
                                        "$setOnInsert": {**{k: v for k, v in DEFAULT_OVERRIDE.items() if k != "grants"}, "created_at": _now()}}, upsert=True)
    await db[LEDGER_COLL].insert_one({"org_id": org_id, "user_id": user_id, "kind": "admin_grant", "by": by.get("email"), "at": _now(), "grant": grant})
    return await get_override(db, org_id, user_id)


# ── cost estimates ────────────────────────────────────────────────────────────
def live_cost(seconds: int) -> float:
    if seconds <= 0:
        return 0.0
    return round(max(PRICING["live"]["min_charge_s"], seconds) * PRICING["live"]["per_min_usd"] / 60, 4)


def mini_cost(tokens: Optional[dict], seconds: int) -> float:
    prices = PRICING["mini"]["per_1m_tokens_usd"]
    if tokens and any(tokens.get(k) for k in prices):
        return round(sum(float(tokens.get(k) or 0) * prices[k] / 1_000_000 for k in prices), 4)
    return round(max(0, seconds) / 60 * PRICING["mini"]["fallback_per_min_usd"], 4)


def est_cost(engine: str, seconds: int, tokens: Optional[dict]) -> float:
    return live_cost(seconds) if engine == "live" else mini_cost(tokens, seconds)


def _usd_to_s(usd: float, engine: str) -> int:
    per_min = PRICING["live"]["per_min_usd"] if engine == "live" else PRICING["mini"]["fallback_per_min_usd"]
    return int(max(0.0, usd) / per_min * 60)


# ── resolve the effective allowance ───────────────────────────────────────────
def _uncapped(user: dict) -> bool:
    return user.get("role") == "super_admin" or bool(user.get("is_owner"))


async def enrolled_policy(db, user: dict) -> Optional[dict]:
    """The account's policy when voice controls apply to this user, else None (legacy path)."""
    g = await get_global(db)
    if not g["enabled"]:
        return None
    org_id = await org_of(db, user)
    p = await get_policy(db, org_id)
    return p if p["enabled"] else None


async def resolve(db, user: dict, policy: dict) -> dict:
    """Effective premium/backup seconds left right now for this user, with every limit that shaped the answer."""
    g = await get_global(db)
    org_id = policy["org_id"]
    uid = str(user["_id"])
    tz = await account_tz(db, org_id, policy, user)
    now_local = _now().astimezone(tz)
    day, month = day_key(now_local), month_key(now_local)
    ov = await get_override(db, org_id, uid)
    res = await db[RES_COLL].find_one({"_id": f"{org_id}:{uid}:{day}"}) or {}
    aday = await db[ACCT_DAY_COLL].find_one({"_id": f"{org_id}:{day}"}) or {}
    amonth = await db[ACCT_MONTH_COLL].find_one({"_id": f"{org_id}:{month}"}) or {}
    limits = []
    uncapped = _uncapped(user) and not policy["cap_super_admins"]  # the founder pilot puts super admins under the same allowances
    def used(doc, role):
        return int(doc.get(f"{role}_used_s") or 0) + int(doc.get(f"{role}_reserved_s") or 0)

    # user allowance (override > account default), grants for today, global ceiling unless super-admin authorized
    prem_min = ov["daily_premium_min"] if ov["daily_premium_min"] is not None else policy["per_user_daily_premium_min"]
    back_min = ov["daily_backup_min"] if ov["daily_backup_min"] is not None else policy["per_user_daily_backup_min"]
    if ov["daily_premium_min"] is not None or ov["daily_backup_min"] is not None:
        limits.append("user_override")
    grants = sum(int(x.get("minutes") or 0) for x in ov.get("grants") or [] if x.get("day") == day)
    if not ov["super_admin_authorized"]:
        if prem_min > g["max_user_daily_premium_min"]:
            limits.append("global_max_premium")
        if back_min > g["max_user_daily_backup_min"]:
            limits.append("global_max_backup")
        prem_min = min(prem_min, g["max_user_daily_premium_min"])
        back_min = min(back_min, g["max_user_daily_backup_min"])
    user_prem_allow = (prem_min + grants) * 60
    user_back_allow = back_min * 60
    if ov["premium_disabled"] or not policy["premium_enabled"]:
        user_prem_allow = 0
        limits.append("premium_disabled")
    if not policy["backup_enabled"]:
        user_back_allow = 0
        limits.append("backup_disabled")
    prem_left = user_prem_allow - used(res, "premium")
    back_left = user_back_allow - used(res, "backup")

    # account caps and budgets (shared pools); an override bypasses the shared minute caps / soft budget only with super-admin authorization.
    # Seconds other sessions on this account are holding right now (reserved, not yet settled) already count against every shared pool.
    acct_reserved = int(aday.get("premium_reserved_s") or 0)
    acct_prem_left = None
    if policy["account_daily_premium_min"] is not None:
        acct_prem_left = policy["account_daily_premium_min"] * 60 - used(aday, "premium")
        limits.append("account_daily_premium")
    if policy["account_monthly_premium_min"] is not None:
        v = policy["account_monthly_premium_min"] * 60 - int(amonth.get("premium_s") or 0) - acct_reserved
        acct_prem_left = v if acct_prem_left is None else min(acct_prem_left, v)
        limits.append("account_monthly_premium")
    if policy["monthly_budget_usd"] is not None:
        v = _usd_to_s(policy["monthly_budget_usd"] - float(amonth.get("est_cost_usd") or 0), "live") - acct_reserved
        acct_prem_left = v if acct_prem_left is None else min(acct_prem_left, v)
        limits.append("monthly_budget")
    bypass_shared = ov["super_admin_authorized"] or uncapped
    if acct_prem_left is not None and not bypass_shared:
        prem_left = min(prem_left, acct_prem_left)
    hard_left = None
    hard_back_left = None
    if policy["hard_premium_cap_usd"] is not None:  # the hard $ cap binds everyone, authorized or not
        hard_left = _usd_to_s(policy["hard_premium_cap_usd"] - float(amonth.get("premium_cost_usd") or 0), "live") - acct_reserved
        limits.append("hard_premium_cap")
    if policy["account_monthly_hard_usd"] is not None:  # total spend (both engines) this month; binds everyone except uncapped super admins (applied below)
        remaining = policy["account_monthly_hard_usd"] - float(amonth.get("est_cost_usd") or 0)
        v = _usd_to_s(remaining, "live") - acct_reserved
        hard_left = v if hard_left is None else min(hard_left, v)
        hard_back_left = _usd_to_s(remaining, "mini") - int(aday.get("backup_reserved_s") or 0)
        limits.append("account_hard_cap")
    acct_back_left = None
    if policy["account_monthly_backup_usd"] is not None:
        acct_back_left = _usd_to_s(policy["account_monthly_backup_usd"] - float(amonth.get("backup_cost_usd") or 0), "mini") - int(aday.get("backup_reserved_s") or 0)
        if not bypass_shared:
            back_left = min(back_left, acct_back_left)
        limits.append("account_monthly_backup")
    if uncapped:   # super admins are never capped, not even by the account's monthly $ cap (their spend still counts toward it)
        prem_left, back_left = 24 * 3600, 24 * 3600
        user_prem_allow, user_back_allow = 24 * 3600, 24 * 3600
        limits.append("super_admin_uncapped")
    if hard_left is not None and not uncapped:
        prem_left = min(prem_left, hard_left)
    if hard_back_left is not None and not uncapped:
        back_left = min(back_left, hard_back_left)
    if policy["killed"]:  # owner kill switch: nothing starts, open sessions are told to stop
        prem_left, back_left = 0, 0
        limits.append("killed")
    reset_at = (now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
    return {"org_id": org_id, "user_id": uid, "day": day, "month": month, "timezone": str(tz), "reset_at": reset_at,
            "premium_engine": policy["premium_engine"], "backup_engine": policy["backup_engine"],
            "premium_allowance_s": user_prem_allow, "backup_allowance_s": user_back_allow, "grants_min_today": grants,
            "premium_used_s": int(res.get("premium_used_s") or 0), "backup_used_s": int(res.get("backup_used_s") or 0),
            "premium_reserved_s": int(res.get("premium_reserved_s") or 0), "backup_reserved_s": int(res.get("backup_reserved_s") or 0),
            "premium_left_s": max(0, prem_left), "backup_left_s": max(0, back_left),
            "account": {"premium_day_used_s": used(aday, "premium"), "backup_day_used_s": used(aday, "backup"),
                        "premium_month_s": int(amonth.get("premium_s") or 0), "backup_month_s": int(amonth.get("backup_s") or 0),
                        "est_cost_month_usd": round(float(amonth.get("est_cost_usd") or 0), 4), "premium_cost_month_usd": round(float(amonth.get("premium_cost_usd") or 0), 4),
                        "backup_cost_month_usd": round(float(amonth.get("backup_cost_usd") or 0), 4), "premium_left_s": acct_prem_left, "hard_left_s": hard_left, "hard_back_left_s": hard_back_left,
                        "backup_left_s": acct_back_left},
            "limits": limits, "bypass_shared": bypass_shared,
            "override": {k: ov[k] for k in ("daily_premium_min", "daily_backup_min", "premium_disabled", "super_admin_authorized")}}


def pick_engine(policy: dict, eff: dict) -> Optional[str]:
    """Premium while it has at least MIN_START_S left, else backup, else None (nothing to start). mini_only: the backup engine or nothing."""
    if policy.get("engine_mode") == "mini_only":
        return policy["backup_engine"] if eff["backup_left_s"] >= MIN_START_S else None
    if eff["premium_left_s"] >= MIN_START_S:
        return policy["premium_engine"]
    if eff["backup_left_s"] >= MIN_START_S:
        return policy["backup_engine"]
    return None


def cap_message(eff: dict) -> str:
    if "killed" in eff["limits"]:
        return "Live Jessi is paused for your account by the account owner."
    if eff["premium_allowance_s"] <= 0 and eff["backup_allowance_s"] <= 0:
        return "Jessi's voice is switched off for your account. Ask your manager."
    return "You have used today's Jessi voice minutes. It resets at midnight your time."


# ── atomic reservations ───────────────────────────────────────────────────────
async def _ensure_docs(db, org_id: str, uid: str, day: str, month: str):
    now = _now()
    await db[RES_COLL].update_one({"_id": f"{org_id}:{uid}:{day}"}, {"$setOnInsert": {"org_id": org_id, "user_id": uid, "day": day, "premium_used_s": 0, "premium_reserved_s": 0, "backup_used_s": 0, "backup_reserved_s": 0, "created_at": now}, "$set": {"updated_at": now}}, upsert=True)
    await db[ACCT_DAY_COLL].update_one({"_id": f"{org_id}:{day}"}, {"$setOnInsert": {"org_id": org_id, "day": day, "premium_used_s": 0, "premium_reserved_s": 0, "backup_used_s": 0, "backup_reserved_s": 0, "sessions": 0, "created_at": now}, "$set": {"updated_at": now}}, upsert=True)
    await db[ACCT_MONTH_COLL].update_one({"_id": f"{org_id}:{month}"}, {"$setOnInsert": {"org_id": org_id, "month": month, "premium_s": 0, "backup_s": 0, "premium_cost_usd": 0.0, "backup_cost_usd": 0.0, "est_cost_usd": 0.0, "thresholds_hit": [], "created_at": now}, "$set": {"updated_at": now}}, upsert=True)


async def reserve(db, eff: dict, engine: str, want_s: int) -> int:
    """Reserve up to want_s seconds of `engine` for this user today, never beyond what is actually left (user pool, then the account
    pool). Atomic conditional updates so two devices can never jointly exceed the allowance. Returns the seconds reserved (0 = none)."""
    role = ENGINE_ROLE[engine]
    want = int(min(want_s, eff[f"{role}_left_s"]))
    if want <= 0:
        return 0
    org_id, uid, day = eff["org_id"], eff["user_id"], eff["day"]
    await _ensure_docs(db, org_id, uid, day, eff["month"])
    user_allow = 10 ** 9 if "super_admin_uncapped" in eff["limits"] else eff[f"{role}_allowance_s"]
    r = await db[RES_COLL].find_one_and_update(
        {"_id": f"{org_id}:{uid}:{day}", "$expr": {"$lte": [{"$add": [f"${role}_used_s", f"${role}_reserved_s", want]}, user_allow]}},
        {"$inc": {f"{role}_reserved_s": want}, "$set": {"updated_at": _now()}})
    if not r:
        return 0
    # shared account pool: the day doc's premium counter must stay within what the account has left (cap snapshot = used now + left now)
    acct_cap = None
    if role == "premium":
        acct_left = eff["account"].get("premium_left_s")
        if acct_left is not None and not eff.get("bypass_shared"):
            acct_cap = int(eff["account"]["premium_day_used_s"]) + acct_left
        hard_left = eff["account"].get("hard_left_s")
        if hard_left is not None:
            hard_cap = int(eff["account"]["premium_day_used_s"]) + hard_left
            acct_cap = hard_cap if acct_cap is None else min(acct_cap, hard_cap)
    if acct_cap is not None:
        a = await db[ACCT_DAY_COLL].find_one_and_update(
            {"_id": f"{org_id}:{day}", "$expr": {"$lte": [{"$add": ["$premium_used_s", "$premium_reserved_s", want]}, acct_cap]}},
            {"$inc": {"premium_reserved_s": want}, "$set": {"updated_at": _now()}})
        if not a:
            await db[RES_COLL].update_one({"_id": f"{org_id}:{uid}:{day}"}, {"$inc": {f"{role}_reserved_s": -want}})
            return 0
    else:
        await db[ACCT_DAY_COLL].update_one({"_id": f"{org_id}:{day}"}, {"$inc": {f"{role}_reserved_s": want}})
    return want


async def _clamp(db, org_id: str, uid: str, day: str, role: str):
    for coll, key in ((RES_COLL, f"{org_id}:{uid}:{day}"), (ACCT_DAY_COLL, f"{org_id}:{day}")):
        await db[coll].update_one({"_id": key, f"{role}_reserved_s": {"$lt": 0}}, {"$set": {f"{role}_reserved_s": 0}})


async def release(db, org_id: str, uid: str, day: str, engine: str, seconds: int):
    if seconds <= 0:
        return
    role = ENGINE_ROLE[engine]
    await db[RES_COLL].update_one({"_id": f"{org_id}:{uid}:{day}"}, {"$inc": {f"{role}_reserved_s": -seconds}})
    await db[ACCT_DAY_COLL].update_one({"_id": f"{org_id}:{day}"}, {"$inc": {f"{role}_reserved_s": -seconds}})
    await _clamp(db, org_id, uid, day, role)


async def settle(db, org_id: str, uid: str, day: str, month: str, engine: str, seconds: int, cost_delta: float):
    """Move `seconds` from reserved to used on the user and account pools and add the cost estimate to the month."""
    if seconds <= 0 and cost_delta == 0:
        return
    role = ENGINE_ROLE[engine]
    inc = {f"{role}_used_s": seconds, f"{role}_reserved_s": -seconds}
    await db[RES_COLL].update_one({"_id": f"{org_id}:{uid}:{day}"}, {"$inc": inc, "$set": {"updated_at": _now()}})
    await db[ACCT_DAY_COLL].update_one({"_id": f"{org_id}:{day}"}, {"$inc": inc, "$set": {"updated_at": _now()}})
    await db[ACCT_MONTH_COLL].update_one({"_id": f"{org_id}:{month}"}, {"$inc": {f"{role}_s": seconds, f"{role}_cost_usd": cost_delta, "est_cost_usd": cost_delta}, "$set": {"updated_at": _now()}}, upsert=True)
    await _clamp(db, org_id, uid, day, role)


async def start(db, user: dict, policy: dict) -> dict:
    """Pick the engine for a new session and hold its first slice. Premium first; if the premium pool is gone (or another device just took
    the last slice) the backup engine is used with a fallback_reason; nothing left -> NoAllowance."""
    eff = await resolve(db, user, policy)
    engine = pick_engine(policy, eff)
    if not engine:
        raise NoAllowance(cap_message(eff))
    fallback_reason = None
    if engine == policy["backup_engine"]:
        fallback_reason = "mini_only" if policy.get("engine_mode") == "mini_only" else "premium_disabled" if "premium_disabled" in eff["limits"] else "premium_cap"
    got = await reserve(db, eff, engine, SLICE_S)
    if got < MIN_START_S and engine == policy["premium_engine"]:
        if got:
            await release(db, eff["org_id"], eff["user_id"], eff["day"], engine, got)
        eff = await resolve(db, user, policy)
        engine, fallback_reason = policy["backup_engine"], "premium_cap"
        got = await reserve(db, eff, engine, SLICE_S) if eff["backup_left_s"] >= MIN_START_S else 0
    if got < MIN_START_S:
        if got:
            await release(db, eff["org_id"], eff["user_id"], eff["day"], engine, got)
        raise NoAllowance(cap_message(eff))
    role = ENGINE_ROLE[engine]
    return {"engine": engine, "eff": eff, "reserved_s": got, "fallback_reason": fallback_reason, "role": role, "left_s": eff[f"{role}_left_s"]}


# ── session metering (called from live_voice) ─────────────────────────────────
async def open_segment(db, live: dict, eff: Optional[dict], engine: str, reserved_s: int, policy_mode: str, device_id: Optional[str] = None,
                       reconnect_of: Optional[str] = None, fallback_reason: Optional[str] = None, segment_no: int = 1) -> dict:
    seg = {"org_id": eff["org_id"] if eff else live.get("org_id"), "user_id": live["user_id"], "live_id": live["live_id"], "segment_no": segment_no, "kind": "segment",
           "engine": engine, "model": live.get("model"), "role": ENGINE_ROLE.get(engine), "mode": live.get("mode"), "policy_mode": policy_mode,
           "started_at": live["started_at"], "ended_at": None, "status": "open", "billable_s": 0, "client_s": None, "tokens": None, "est_cost_usd": 0.0,
           "actual_cost_usd": None, "cost_basis": "server_clock" if engine == "live" else "client_report", "reconciled": False, "unconfirmed": True,
           "reserved_s": reserved_s, "settled_s": 0, "overrun_s": 0, "slices": 1 if reserved_s else 0, "heartbeat_at": _now(), "fallback_reason": fallback_reason, "reconnect_of": reconnect_of,
           "device_id": device_id, "fake_provider": bool(live.get("fake_provider")), "thresholds_hit": [], "stop_reason": None, "errors": [],
           "day": eff["day"] if eff else None, "month": eff["month"] if eff else None}
    r = await db[LEDGER_COLL].insert_one(seg)
    seg["_id"] = r.inserted_id
    if eff:
        await db[ACCT_DAY_COLL].update_one({"_id": f"{eff['org_id']}:{eff['day']}"}, {"$inc": {"sessions": 1}})
    return seg


async def on_heartbeat(db, live: dict, client_seconds: Optional[int], tokens: Optional[dict], closing: bool = False, close_reason: Optional[str] = None) -> dict:
    """Server-authoritative metering step: billable seconds come from this server's clock since the session started (a client report can
    only raise the number, never lower it). Settles elapsed seconds against the reservation, tops the reservation up one slice at a time,
    and returns a stop directive when the pool is exhausted. Legacy (non-enrolled) sessions only get their ledger row updated."""
    seg = await db[LEDGER_COLL].find_one({"live_id": live["live_id"], "kind": "segment", "status": "open"}, sort=[("segment_no", -1)])
    if not seg:
        return {}
    now = _now()
    elapsed = int((now - _aware(live["started_at"])).total_seconds())
    if client_seconds is not None:
        elapsed = max(elapsed, int(client_seconds))
    engine = seg["engine"]
    tokens = tokens or seg.get("tokens")
    new_cost = est_cost(engine, elapsed, tokens)
    out = {"billable_s": elapsed, "est_cost_usd": new_cost, "policy_mode": seg.get("policy_mode")}
    sets = {"billable_s": elapsed, "est_cost_usd": new_cost, "heartbeat_at": now, "unconfirmed": (not closing) or close_reason not in CONFIRMED_CLOSE_REASONS}
    if client_seconds is not None:
        sets["client_s"] = int(client_seconds)
    if tokens:
        sets["tokens"] = tokens
        sets["cost_basis"] = "client_report"
    if seg.get("policy_mode") != "controls":
        if closing:
            sets.update({"status": "closed", "ended_at": now, "stop_reason": close_reason})
        await db[LEDGER_COLL].update_one({"_id": seg["_id"]}, {"$set": sets})
        return out
    org_id, uid, day, month = seg["org_id"], seg["user_id"], seg["day"], seg["month"]
    settled = int(seg.get("settled_s") or 0)
    reserved = int(seg.get("reserved_s") or 0)
    delta = max(0, elapsed - settled)
    reserved_left = max(0, reserved - settled)
    settle_s = min(delta, reserved_left)
    overrun = delta - settle_s
    cost_delta = round(new_cost - float(seg.get("est_cost_usd") or 0), 4)
    await settle(db, org_id, uid, day, month, engine, settle_s, cost_delta)
    if overrun:
        # seconds spoken beyond the reservation: counted as used (never hidden), flagged for the dashboard
        role = ENGINE_ROLE[engine]
        await db[RES_COLL].update_one({"_id": f"{org_id}:{uid}:{day}"}, {"$inc": {f"{role}_used_s": overrun}})
        await db[ACCT_DAY_COLL].update_one({"_id": f"{org_id}:{day}"}, {"$inc": {f"{role}_used_s": overrun}})
        await db[ACCT_MONTH_COLL].update_one({"_id": f"{org_id}:{month}"}, {"$inc": {f"{role}_s": overrun}})
        sets["overrun_s"] = int(seg.get("overrun_s") or 0) + overrun
    sets["settled_s"] = settled + settle_s + overrun
    sets["reserved_s"] = max(reserved, sets["settled_s"])
    stop = None
    if closing:
        unused = max(0, reserved - sets["settled_s"])
        await release(db, org_id, uid, day, engine, unused)
        sets.update({"status": "closed", "ended_at": now, "stop_reason": close_reason, "released_s": unused})
        out["left_s"] = None
    else:
        headroom = sets["reserved_s"] - sets["settled_s"]
        user = await db.users.find_one({"_id": _oid(uid)}) if _oid(uid) else None
        policy = await get_policy(db, org_id)
        eff = await resolve(db, user or {"_id": uid, "role": "user"}, policy)
        role = ENGINE_ROLE[engine]
        if "killed" in eff["limits"]:
            stop = "killed"
            sets["stop_reason"] = stop
            if not seg.get("stop_requested_at"):
                sets["stop_requested_at"] = now
            out["fallback_engine"] = None
        elif headroom < SLICE_S // 2:
            got = await reserve(db, eff, engine, SLICE_S) if user else 0
            if got:
                sets["reserved_s"] += got
                sets["slices"] = int(seg.get("slices") or 0) + 1
                headroom += got
            elif headroom <= 0:
                stop = f"{role}_cap"
                sets["stop_reason"] = stop
                sets["stop_requested_at"] = now
                out["fallback_engine"] = policy["backup_engine"] if (engine == policy["premium_engine"] and eff["backup_left_s"] >= MIN_START_S) else None
            else:
                sets["cap_warning"] = True
        pct_hit = _pct_hits(eff, engine, seg.get("thresholds_hit") or [])
        if pct_hit:
            sets["thresholds_hit"] = (seg.get("thresholds_hit") or []) + pct_hit
            out["thresholds_hit"] = pct_hit
        out["left_s"] = max(0, headroom) + eff[f"{role}_left_s"]
    await db[LEDGER_COLL].update_one({"_id": seg["_id"]}, {"$set": sets})
    if stop:
        out["stop"] = stop
        out["message"] = STOP_MESSAGES[stop]
    return out


def _pct_hits(eff: dict, engine: str, already: list) -> list:
    role = ENGINE_ROLE[engine]
    allow = eff[f"{role}_allowance_s"]
    if allow <= 0 or "super_admin_uncapped" in eff["limits"]:
        return []
    used = eff[f"{role}_used_s"] + eff[f"{role}_reserved_s"]
    hits = []
    for pct in (80, 100):
        key = f"{role}_{pct}"
        if key not in already and used * 100 >= allow * pct:
            hits.append(key)
    return hits


async def _finalize(db, seg: dict, billable: int, stop_reason: str, extra: Optional[dict] = None, cost_basis: Optional[str] = None):
    """Close a segment from the server side: settle what was spoken against the reservation, release the rest, close the live_sessions row."""
    cost = est_cost(seg["engine"], billable, seg.get("tokens"))
    sets = {"status": "closed", "ended_at": _now(), "stop_reason": stop_reason, "billable_s": billable, "est_cost_usd": cost, "unconfirmed": cost_basis != "provider_usage", **(extra or {})}
    if cost_basis:
        sets["cost_basis"] = cost_basis
    if seg.get("policy_mode") == "controls":
        settled = int(seg.get("settled_s") or 0)
        reserved = int(seg.get("reserved_s") or 0)
        delta = max(0, billable - settled)
        settle_s = min(delta, max(0, reserved - settled))
        overrun = delta - settle_s
        await settle(db, seg["org_id"], seg["user_id"], seg["day"], seg["month"], seg["engine"], settle_s, round(cost - float(seg.get("est_cost_usd") or 0), 4))
        if overrun:
            role = ENGINE_ROLE[seg["engine"]]
            await db[RES_COLL].update_one({"_id": f"{seg['org_id']}:{seg['user_id']}:{seg['day']}"}, {"$inc": {f"{role}_used_s": overrun}})
            await db[ACCT_DAY_COLL].update_one({"_id": f"{seg['org_id']}:{seg['day']}"}, {"$inc": {f"{role}_used_s": overrun}})
            await db[ACCT_MONTH_COLL].update_one({"_id": f"{seg['org_id']}:{seg['month']}"}, {"$inc": {f"{role}_s": overrun}})
            sets["overrun_s"] = int(seg.get("overrun_s") or 0) + overrun
        released = max(0, reserved - settled - settle_s)
        await release(db, seg["org_id"], seg["user_id"], seg["day"], seg["engine"], released)
        sets["settled_s"] = settled + settle_s + overrun
        sets["released_s"] = released
    await db[LEDGER_COLL].update_one({"_id": seg["_id"]}, {"$set": sets})
    await db.live_sessions.update_one({"live_id": seg["live_id"], "status": "open"}, {"$set": {"status": "closed", "close_reason": stop_reason, "ended_at": _now(), "seconds": billable, "cost_usd": cost, "meter.stop_reason": stop_reason, "updated_at": _now()}})


async def kill_segment(db, seg: dict, stop_reason: str = "server_kill", force: bool = False) -> bool:
    """Close one open segment on the provider side and finalize it. Returns True when finalized (the kill either succeeded or ran out
    of attempts; with `force` the segment is finalized even when the provider call failed)."""
    from services import live_voice as lv
    now = _now()
    attempts = int(seg.get("kill_attempts") or 0)
    if attempts >= KILL_MAX_ATTEMPTS and not force:
        return False
    live = await db.live_sessions.find_one({"live_id": seg["live_id"]}) or {"live_id": seg["live_id"], "engine": seg["engine"], "started_at": seg["started_at"]}
    result = await lv.provider_close(live)
    await db[LEDGER_COLL].update_one({"_id": seg["_id"]}, {"$inc": {"kill_attempts": 1}, "$set": {"kill_at": now, "kill_result": result}})
    if not result.get("ok") and attempts + 1 < KILL_MAX_ATTEMPTS and not force:
        return False
    billable = max(int(seg.get("billable_s") or 0), int((now - _aware(live.get("started_at") or seg["started_at"])).total_seconds()))
    basis = None
    if result.get("provider_seconds") is not None:
        billable, basis = max(billable, int(result["provider_seconds"])), "provider_usage"
    await _finalize(db, seg, billable, stop_reason, {"kill_attempts": attempts + 1, "kill_at": now, "kill_result": result}, basis)
    return True


async def watchdog(db) -> dict:
    """Fail-safes, run every minute. (1) Sessions that stopped reporting (tab killed, app backgrounded, network drop, server restart in
    between): finalize at last heartbeat + GRACE_S, release the unspent reservation, flag unconfirmed. (2) Kill switch: a session that was
    told to stop (pool gone, hard cap) and is still open after STOP_GRACE_S is closed on the provider side and finalized as server_kill."""
    now = _now()
    n = killed = 0
    async for seg in db[LEDGER_COLL].find({"kind": "segment", "status": "open", "heartbeat_at": {"$lt": now - timedelta(seconds=HEARTBEAT_STALE_S)}}):
        hb = _aware(seg.get("heartbeat_at") or seg["started_at"])
        billable = max(int(seg.get("billable_s") or 0), int((hb - _aware(seg["started_at"])).total_seconds()) + GRACE_S)
        await _finalize(db, seg, billable, "stale_meter", {"watchdog_at": now})
        n += 1
    async for seg in db[LEDGER_COLL].find({"kind": "segment", "status": "open", "policy_mode": "controls", "stop_requested_at": {"$lt": now - timedelta(seconds=STOP_GRACE_S)}}):
        if await kill_segment(db, seg, "killed" if seg.get("stop_reason") == "killed" else "server_kill"):
            killed += 1
    return {"finalized": n, "killed": killed}


async def kill_open_sessions(db, org_id: str) -> int:
    """Owner kill switch: every open metered session on the account is hung up on the provider side and finalized right now."""
    n = 0
    async for seg in db[LEDGER_COLL].find({"kind": "segment", "status": "open", "policy_mode": "controls", "org_id": org_id}):
        if await kill_segment(db, seg, "killed", force=True):
            n += 1
    return n


async def account_members(db, org_id: str, limit: int = 300) -> list:
    """Everyone whose voice minutes count against this account (same rules as org_of)."""
    proj = {"name": 1, "email": 1, "role": 1, "status": 1}
    if org_id.startswith("store:"):
        q = {"store_id": org_id[6:]}
    elif org_id.startswith("user:"):
        q = {"_id": _oid(org_id[5:])}
    else:
        stores = [str(x["_id"]) async for x in db.stores.find({"$or": [{"organization_id": org_id}, {"org_id": org_id}]}, {"_id": 1})]
        q = {"$or": [{"organization_id": org_id}, {"org_id": org_id}, {"store_id": {"$in": stores}}]}
    q = {"$and": [q, {"status": {"$nin": ["deleted", "deactivated", "inactive"]}}]}
    return [{"user_id": str(u["_id"]), "name": u.get("name") or u.get("email") or "", "email": u.get("email") or "", "role": u.get("role") or "user"}
            async for u in db.users.find(q, proj).sort("name", 1).limit(limit)]


# ── production rollout ────────────────────────────────────────────────────────
async def rollout(db, on: bool, me: dict) -> dict:
    """Voice controls for every account (on) or only accounts switched on one by one (off). Turning it on hands the founder pilot
    account back to the defaults (its pilot allowances and 'cap super admins' were for the test only)."""
    g = await save_global(db, {"all_accounts": bool(on)}, me)
    if on:
        org_id = await org_of(db, me)
        doc = await db[POLICY_COLL].find_one({"org_id": org_id}) or {}
        if doc:
            await save_policy(db, org_id, {}, me, reset=[k for k in DEFAULT_POLICY if k not in ("killed",)])
    return g


# ── founder pilot (one account, the owner's own) ───────────────────────────────
PILOT_DEFAULTS = {"premium_min": 2, "backup_min": 10, "hard_usd": 20.0}


async def pilot_enroll(db, me: dict, premium_min: int, backup_min: int, hard_usd: float) -> dict:
    org_id = await org_of(db, me)
    g = await get_global(db)   # once every account is on voice limits, super admins are never capped (the pilot cap was for the test only)
    patch = {"enabled": True, "cap_super_admins": not g["all_accounts"], "killed": False, "per_user_daily_premium_min": premium_min, "per_user_daily_backup_min": backup_min,
             "account_monthly_hard_usd": hard_usd, "notes": f"Founder voice pilot, enrolled by {me.get('email')}"}
    await save_policy(db, org_id, patch, me)
    return await pilot_status(db, me)


async def pilot_engine_mode(db, me: dict, mode: str) -> dict:
    """Founder engine test for the caller's own account: live_first (default) or mini_only. Pools, caps, ledger and kill switch are untouched."""
    await save_policy(db, await org_of(db, me), {"engine_mode": mode}, me)
    return await pilot_status(db, me)


async def pilot_status(db, me: dict) -> dict:
    """Everything the founder needs on one screen: own account policy, safety flags, today's pools, month spend vs cap, open sessions,
    recent handoffs and segments, how many OTHER accounts are enrolled (should be zero during the pilot)."""
    from services import live_voice as lv
    org_id = await org_of(db, me)
    policy = await get_policy(db, org_id)
    g = await get_global(db)
    tz = await account_tz(db, org_id, policy, me)
    now_local = _now().astimezone(tz)
    day, month = day_key(now_local), month_key(now_local)
    aday = await db[ACCT_DAY_COLL].find_one({"_id": f"{org_id}:{day}"}) or {}
    amonth = await db[ACCT_MONTH_COLL].find_one({"_id": f"{org_id}:{month}"}) or {}
    eff = await resolve(db, me, policy) if policy["enabled"] and g["enabled"] else None
    others = [p["org_id"] async for p in db[POLICY_COLL].find({"enabled": True, "org_id": {"$ne": org_id}}, {"org_id": 1})]
    names = {}
    async for s in db[LEDGER_COLL].find({"kind": "segment", "org_id": org_id}).sort("started_at", -1).limit(40):
        names.setdefault(s["user_id"], None)
    async for u in db.users.find({"_id": {"$in": [o for o in (_oid(x) for x in names) if o]}}, {"email": 1, "name": 1}):
        names[str(u["_id"])] = u.get("name") or u.get("email")

    def row(s):
        return {"live_id": s["live_id"], "user": names.get(s["user_id"]) or s["user_id"], "engine": s["engine"], "role": s.get("role"), "status": s["status"], "device_id": s.get("device_id"),
                "started_at": s["started_at"].isoformat() if s.get("started_at") else None, "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
                "billable_s": int(s.get("billable_s") or 0), "reserved_s": int(s.get("reserved_s") or 0), "settled_s": int(s.get("settled_s") or 0), "est_cost_usd": round(float(s.get("est_cost_usd") or 0), 4),
                "cost_basis": s.get("cost_basis"), "stop_reason": s.get("stop_reason"), "fallback_reason": s.get("fallback_reason"), "reconnect_of": s.get("reconnect_of"), "segment_no": s.get("segment_no"),
                "unconfirmed": bool(s.get("unconfirmed")), "fake_provider": bool(s.get("fake_provider")), "kill_attempts": int(s.get("kill_attempts") or 0)}

    active = [row(s) async for s in db[LEDGER_COLL].find({"kind": "segment", "status": "open", "org_id": org_id}).sort("started_at", -1).limit(20)]
    recent = [row(s) async for s in db[LEDGER_COLL].find({"kind": "segment", "org_id": org_id}).sort("started_at", -1).limit(15)]
    handoffs = []
    async for s in db[LEDGER_COLL].find({"kind": "segment", "org_id": org_id, "reconnect_of": {"$ne": None}}).sort("started_at", -1).limit(15):
        prev = await db[LEDGER_COLL].find_one({"live_id": s["reconnect_of"], "kind": "segment"}, {"engine": 1, "billable_s": 1, "stop_reason": 1})
        handoffs.append({"at": s["started_at"].isoformat() if s.get("started_at") else None, "user": names.get(s["user_id"]) or s["user_id"], "from_live_id": s["reconnect_of"], "to_live_id": s["live_id"],
                         "from_engine": (prev or {}).get("engine"), "to_engine": s["engine"], "reason": s.get("fallback_reason") or (prev or {}).get("stop_reason") or "reconnect",
                         "from_billable_s": int((prev or {}).get("billable_s") or 0), "to_billable_s": int(s.get("billable_s") or 0), "to_status": s["status"]})
    cap = policy["account_monthly_hard_usd"]
    spent = round(float(amonth.get("est_cost_usd") or 0), 4)
    try:
        from server import BUILD
    except Exception:
        BUILD = None
    allowance = None
    if eff:
        allowance = {k: eff[k] for k in ("premium_allowance_s", "backup_allowance_s", "premium_left_s", "backup_left_s", "premium_used_s", "backup_used_s", "premium_reserved_s", "backup_reserved_s", "limits", "reset_at", "timezone")}
        allowance["next_engine"] = pick_engine(policy, eff)
    return {"org_id": org_id, "org_name": await org_name(db, org_id), "me": {"user_id": str(me["_id"]), "email": me.get("email"), "role": me.get("role")},
            "enrolled": bool(policy["enabled"] and g["enabled"]), "policy": policy, "global_enabled": g["enabled"], "other_enrolled_org_ids": others, "defaults": PILOT_DEFAULTS,
            "rollout": {"all_accounts": bool(g["all_accounts"]), "premium_min": g["default_premium_min"], "backup_min": g["default_backup_min"], "hard_usd": g["default_monthly_hard_usd"],
                        "updated_at": g["updated_at"], "updated_by": g["updated_by"]},
            "env": {"fake_provider_allowed": fake_provider_allowed(), "openai_configured": lv.configured() is None, "openai_reason": lv.configured(), "build": BUILD},
            "allowance": allowance,
            "today": {k: int(aday.get(k) or 0) for k in ("premium_used_s", "premium_reserved_s", "backup_used_s", "backup_reserved_s", "sessions")} | {"day": day},
            "month": {"month": month, "premium_s": int(amonth.get("premium_s") or 0), "backup_s": int(amonth.get("backup_s") or 0), "premium_cost_usd": round(float(amonth.get("premium_cost_usd") or 0), 4),
                      "backup_cost_usd": round(float(amonth.get("backup_cost_usd") or 0), 4), "est_cost_usd": spent, "cap_usd": cap, "cap_left_usd": round(max(0.0, cap - spent), 4) if cap is not None else None},
            "active": active, "handoffs": handoffs, "recent": recent}


async def trail(db, live_id: str) -> Optional[dict]:
    """The whole conversation a session belongs to: every segment in order (engine, seconds, est. cost, cost basis, why it ended) with totals."""
    first = await db[LEDGER_COLL].find_one({"live_id": live_id, "kind": "segment"})
    if not first:
        return None
    seen = {first["live_id"]}
    chain = [first]
    cur = first
    while cur.get("reconnect_of") and cur["reconnect_of"] not in seen:
        prev = await db[LEDGER_COLL].find_one({"live_id": cur["reconnect_of"], "kind": "segment"})
        if not prev:
            break
        seen.add(prev["live_id"])
        chain.insert(0, prev)
        cur = prev
    cur = first
    while True:
        nxt = await db[LEDGER_COLL].find_one({"reconnect_of": cur["live_id"], "kind": "segment", "live_id": {"$nin": list(seen)}})
        if not nxt:
            break
        seen.add(nxt["live_id"])
        chain.append(nxt)
        cur = nxt
    segs = [serialize_segment(s) for s in chain]
    totals = {"segments": len(segs), "premium_s": sum(s["billable_s"] or 0 for s in segs if s["role"] == "premium"), "backup_s": sum(s["billable_s"] or 0 for s in segs if s["role"] == "backup"),
              "est_cost_usd": round(sum(float(s["est_cost_usd"] or 0) for s in segs), 4), "engines": sorted({s["engine"] for s in segs}), "cost_basis": sorted({s["cost_basis"] for s in segs if s["cost_basis"]}),
              "unconfirmed": any(s["unconfirmed"] for s in segs), "handoffs": sum(1 for s in segs if s["reconnect_of"]), "started_at": segs[0]["started_at"], "ended_at": segs[-1]["ended_at"], "open": any(s["status"] == "open" for s in segs)}
    totals["total_s"] = totals["premium_s"] + totals["backup_s"]
    return {"conversation_id": segs[0]["live_id"], "segments": segs, "totals": totals}


# ── reads for the API ─────────────────────────────────────────────────────────
def serialize_segment(s: dict) -> dict:
    out = {k: s.get(k) for k in ("org_id", "user_id", "live_id", "segment_no", "engine", "model", "role", "mode", "policy_mode", "status", "billable_s", "client_s", "tokens", "est_cost_usd",
                                 "actual_cost_usd", "cost_basis", "reconciled", "unconfirmed", "reserved_s", "settled_s", "overrun_s", "released_s", "slices", "fallback_reason", "reconnect_of",
                                 "device_id", "fake_provider", "thresholds_hit", "stop_reason", "cap_warning", "kill_attempts", "kill_result", "day", "month")}
    out["id"] = str(s["_id"])
    for k in ("started_at", "ended_at", "heartbeat_at", "stop_requested_at", "kill_at"):
        v = s.get(k)
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


async def list_segments(db, org_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 50) -> list:
    q = {"kind": "segment"}
    if org_id:
        q["org_id"] = org_id
    if user_id:
        q["user_id"] = user_id
    rows = await db[LEDGER_COLL].find(q).sort("started_at", -1).limit(max(1, min(500, limit))).to_list(500)
    return [serialize_segment(s) for s in rows]


async def user_usage(db, org_id: str, since: datetime) -> list:
    pipe = [{"$match": {"org_id": org_id, "kind": "segment", "started_at": {"$gte": since}}},
            {"$group": {"_id": {"u": "$user_id", "r": "$role"}, "s": {"$sum": "$billable_s"}, "n": {"$sum": 1}, "cost": {"$sum": "$est_cost_usd"},
                        "caps": {"$sum": {"$cond": [{"$in": ["$stop_reason", ["premium_cap", "backup_cap", "daily_cap"]]}, 1, 0]}}, "last": {"$max": "$started_at"}}}]
    rows = {}
    async for g in db[LEDGER_COLL].aggregate(pipe):
        u = rows.setdefault(g["_id"]["u"], {"user_id": g["_id"]["u"], "premium_s": 0, "backup_s": 0, "sessions": 0, "est_cost_usd": 0.0, "cap_hits": 0, "last_active": None})
        u[f"{g['_id']['r'] or 'premium'}_s"] += int(g["s"] or 0)
        u["sessions"] += int(g["n"] or 0)
        u["est_cost_usd"] = round(u["est_cost_usd"] + float(g["cost"] or 0), 4)
        u["cap_hits"] += int(g["caps"] or 0)
        last = g.get("last").isoformat() if hasattr(g.get("last"), "isoformat") else None
        u["last_active"] = max(u["last_active"] or "", last or "") or None
    if rows:
        ids = [ObjectId(x) for x in rows if ObjectId.is_valid(x)]
        async for usr in db.users.find({"_id": {"$in": ids}}, {"name": 1, "email": 1, "role": 1}):
            rows[str(usr["_id"])].update({"name": usr.get("name"), "email": usr.get("email"), "role": usr.get("role")})
    return sorted(rows.values(), key=lambda r: -(r["premium_s"] + r["backup_s"]))


async def account_overview(db, since: datetime) -> list:
    """One row per account: every organization, stores without one, and any other account with a policy or usage since `since`.
    Minutes by role, sessions, est. cost, this month's spend against the cap, and the effective policy (own settings vs defaults)."""
    g = await get_global(db)
    pipe = [{"$match": {"kind": "segment", "started_at": {"$gte": since}, "org_id": {"$ne": None}}},
            {"$group": {"_id": {"o": "$org_id", "r": "$role"}, "s": {"$sum": "$billable_s"}, "n": {"$sum": 1}, "cost": {"$sum": "$est_cost_usd"}, "users": {"$addToSet": "$user_id"},
                        "caps": {"$sum": {"$cond": [{"$in": ["$stop_reason", ["premium_cap", "backup_cap", "daily_cap"]]}, 1, 0]}}}}]
    rows = {}

    def row(org_id):
        return rows.setdefault(org_id, {"org_id": org_id, "premium_s": 0, "backup_s": 0, "sessions": 0, "est_cost_usd": 0.0, "users": set(), "cap_hits": 0})

    async for o in db.organizations.find({"status": {"$nin": ["deleted", "archived"]}}, {"_id": 1}):
        row(str(o["_id"]))
    async for st in db.stores.find({"$and": [{"$or": [{"organization_id": {"$in": [None, ""]}}, {"organization_id": {"$exists": False}}]},
                                             {"$or": [{"org_id": {"$in": [None, ""]}}, {"org_id": {"$exists": False}}]}]}, {"_id": 1}):
        row(f"store:{st['_id']}")
    async for gr in db[LEDGER_COLL].aggregate(pipe):
        r = row(gr["_id"]["o"])
        r[f"{gr['_id']['r'] or 'premium'}_s"] += int(gr["s"] or 0)
        r["sessions"] += int(gr["n"] or 0)
        r["est_cost_usd"] = round(r["est_cost_usd"] + float(gr["cost"] or 0), 4)
        r["users"] |= set(gr.get("users") or [])
        r["cap_hits"] += int(gr["caps"] or 0)
    async for p in db[POLICY_COLL].find({}, {"org_id": 1}):
        row(p["org_id"])
    out = []
    for r in rows.values():
        r["active_users"] = len(r.pop("users"))
        pol = await get_policy(db, r["org_id"], g)
        tz = await account_tz(db, r["org_id"], pol)
        now_local = _now().astimezone(tz)
        aday = await db[ACCT_DAY_COLL].find_one({"_id": f"{r['org_id']}:{day_key(now_local)}"}) or {}
        amonth = await db[ACCT_MONTH_COLL].find_one({"_id": f"{r['org_id']}:{month_key(now_local)}"}) or {}
        r["policy"] = {k: pol[k] for k in DEFAULT_POLICY} | {"custom": pol["custom"], "exists": pol["exists"]}
        r["enabled"] = bool(pol["enabled"] and g["enabled"])
        r["killed"] = bool(pol["killed"])
        r["today"] = {"premium_s": int(aday.get("premium_used_s") or 0), "backup_s": int(aday.get("backup_used_s") or 0), "sessions": int(aday.get("sessions") or 0)}
        r["month"] = {"est_cost_usd": round(float(amonth.get("est_cost_usd") or 0), 2), "cap_usd": pol["account_monthly_hard_usd"]}
        r["name"] = await org_name(db, r["org_id"])
        out.append(r)
    return sorted(out, key=lambda r: (-(r["premium_s"] + r["backup_s"]), r["name"].lower()))
