"""Subscription access policy (approved Jun 2026). Locks only follow a Stripe subscription's own status:
past_due -> the 14-day grace, then lock; unpaid and incomplete_expired -> lock; canceled -> lock once the paid-through period ends.
Never locked: super admins, the internal organization, active pilots, explicit billing exceptions, and every organization without
a Stripe subscription (legacy accounts; an admin may classify them with a review date and, on purpose, an expiration date).
While locked: team members see the access-paused screen, account owners keep billing only, inbound texts keep saving, outbound
texts and automations pause (services/outbound_gate.py)."""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

TTL = 20.0
GRACE_DAYS = 14
LOCK_REASONS = {
    "past_due_grace_ended": "The payment is past due and the 14-day grace period has ended.",
    "unpaid": "The subscription is unpaid.",
    "incomplete_expired": "The first payment was never completed.",
    "canceled": "The subscription was canceled and the paid period has ended.",
    "legacy_expired": "The account's billing review date has passed without a subscription.",
}
TEAM_MSG = "Access to your organization's account is paused. Texts your contacts send are still being saved. Your account owner can restore service."
OWNER_MSG = "Your subscription needs attention. Restore billing to turn everything back on. Texts your contacts send are still being saved."
ALWAYS_OPEN = ("/api/auth/", "/api/health", "/api/billing/access")
OWNER_OPEN = ("/api/billing/",)
_cache: dict = {}


def _dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def evaluate(org: Optional[dict], internal: bool = False, now: Optional[datetime] = None) -> dict:
    """Pure decision for one organization: {locked, reason, state, grace_until, period_end}."""
    now = now or datetime.now(timezone.utc)
    out = {"locked": False, "reason": None, "state": "ok", "grace_until": None, "period_end": None}
    if not org:
        return out
    if internal or org.get("internal"):
        return {**out, "state": "internal"}
    c = org.get("customer") or {}
    legacy = org.get("billing_legacy") or {}
    if c.get("billing_status") == "pilot":
        return {**out, "state": "pilot"}
    if c.get("billing_status") == "exception":
        return {**out, "state": "exception"}
    if not c.get("stripe_subscription_id"):
        exp = _dt(legacy.get("expires_at"))
        if legacy and exp and exp <= now:
            return {**out, "locked": True, "reason": "legacy_expired", "state": "locked"}
        return {**out, "state": "legacy" if legacy else ("no_subscription" if c else "legacy_unclassified")}
    raw = c.get("subscription_status") or ""
    period_end = _dt(c.get("current_period_end"))
    out["period_end"] = period_end.isoformat() if period_end else None
    if raw in ("active", "trialing", "incomplete"):
        return {**out, "state": raw}
    if raw in ("past_due", "paused"):
        grace = _dt(c.get("grace_until")) or ((_dt(c.get("payment_failed_at")) or now) + timedelta(days=GRACE_DAYS))
        out["grace_until"] = grace.isoformat()
        return {**out, "locked": True, "reason": "past_due_grace_ended", "state": "locked"} if grace <= now else {**out, "state": "grace"}
    if raw in ("unpaid", "incomplete_expired"):
        return {**out, "locked": True, "reason": raw, "state": "locked"}
    if raw == "canceled":
        if period_end and period_end > now:
            return {**out, "state": "canceling"}
        return {**out, "locked": True, "reason": "canceled", "state": "locked"}
    return {**out, "state": raw or "unknown"}


async def _internal(db, org_id: str) -> bool:
    from services.sender_policy import internal_org_ids
    return str(org_id) in await internal_org_ids(db)


async def org_state(db, org_id: Optional[str]) -> dict:
    if not org_id or not ObjectId.is_valid(str(org_id)):
        return evaluate(None)
    key = f"org:{org_id}"
    hit = _cache.get(key)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    org = await db.organizations.find_one({"_id": ObjectId(str(org_id))}, {"customer": 1, "billing_legacy": 1, "internal": 1, "name": 1})
    st = evaluate(org, internal=await _internal(db, org_id))
    _cache[key] = (st, time.monotonic() + TTL)
    return st


def is_owner(user: dict, org: Optional[dict]) -> bool:
    c = (org or {}).get("customer") or {}
    return str(user.get("_id")) == str(c.get("owner_user_id") or "") or user.get("role") in ("org_admin", "admin")


async def for_user(db, user: Optional[dict]) -> dict:
    """{locked, reason, owner, message, state} for a signed-in person (super admins are never locked)."""
    if not user or user.get("role") == "super_admin" or not user.get("organization_id"):
        return {"locked": False, "state": "ok"}
    st = await org_state(db, user["organization_id"])
    if not st["locked"]:
        return {"locked": False, "state": st["state"], "grace_until": st.get("grace_until"), "period_end": st.get("period_end")}
    org = await db.organizations.find_one({"_id": ObjectId(str(user["organization_id"]))}, {"customer.owner_user_id": 1})
    owner = is_owner(user, org)
    return {"locked": True, "reason": st["reason"], "reason_text": LOCK_REASONS.get(st["reason"], ""), "owner": owner,
            "message": OWNER_MSG if owner else TEAM_MSG, "state": "locked"}


async def for_caller(db, user_id: str) -> Optional[dict]:
    key = f"user:{user_id}"
    hit = _cache.get(key)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "organization_id": 1}) if ObjectId.is_valid(user_id) else None
    st = await for_user(db, user)
    _cache[key] = (st, time.monotonic() + TTL)
    return st


def path_allowed(path: str, lock: dict) -> bool:
    return path.startswith(ALWAYS_OPEN) or (lock.get("owner") and path.startswith(OWNER_OPEN))


def invalidate() -> None:
    _cache.clear()


async def classify_legacy(db, actor: dict, apply: bool = False, review_days: int = 90) -> dict:
    """Organizations without a Stripe subscription become legacy exceptions with a review date (never an expiration: only an admin sets that)."""
    now = datetime.now(timezone.utc)
    q = {"customer.stripe_subscription_id": {"$in": [None, ""]}, "billing_legacy": {"$exists": False}, "internal": {"$ne": True}}
    rows = await db.organizations.find(q, {"name": 1, "customer.billing_status": 1}).to_list(5000)
    if apply:
        for o in rows:
            await db.organizations.update_one({"_id": o["_id"], "billing_legacy": {"$exists": False}}, {"$set": {"billing_legacy": {
                "classified_at": now.isoformat(), "classified_by": str(actor["_id"]), "review_by": (now + timedelta(days=review_days)).isoformat(),
                "expires_at": None, "note": "Existing account without a Stripe subscription"}}})
        invalidate()
    return {"count": len(rows), "applied": apply, "organizations": [{"id": str(o["_id"]), "name": o.get("name"), "billing_status": (o.get("customer") or {}).get("billing_status")} for o in rows[:500]]}
