"""Founder-driven customer launch (Stage 1): plan, seats, billing and onboarding status on `organizations.customer`.
Legacy organizations never carry the field, so nothing in here applies to them."""
import logging
import secrets
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Provisional pilot pricing (owner, Oct 11 2026). Display + seat math only: no Stripe objects exist yet.
PILOT_PLANS = {
    "pilot_store_monthly": {"key": "pilot_store_monthly", "name": "Pilot Store", "amount": 375.0, "interval": "month",
                            "seats_included": 5, "seat_price": 75.0, "kind": "store", "desc": "5 seats included, $75/mo per extra seat"},
    "pilot_individual_monthly": {"key": "pilot_individual_monthly", "name": "Pilot Individual", "amount": 100.0, "interval": "month",
                                 "seats_included": 1, "seat_price": None, "kind": "individual", "desc": "One person, one seat"},
}
BILLING_OK = {"active", "trialing", "exception", "pilot"}
INVITE_TTL_HOURS = 72
MAX_EXCEPTION_DAYS = 180
PLACEHOLDER_EMAIL_SUFFIX = "@placeholder.local"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def plan(plan_key: str) -> dict:
    p = PILOT_PLANS.get(plan_key or "")
    if not p:
        raise HTTPException(status_code=400, detail="Unknown plan")
    return p


def new_customer(plan_key: str, seats_extra: int, owner_user_id: str, created_by: str) -> dict:
    p = plan(plan_key)
    seats_extra = int(seats_extra or 0)
    if seats_extra < 0 or seats_extra > 500:
        raise HTTPException(status_code=400, detail="Extra seats must be between 0 and 500")
    if p["seat_price"] is None and seats_extra:
        raise HTTPException(status_code=400, detail="This plan has no extra seats")
    return {
        "pilot": True, "plan_key": plan_key, "plan_name": p["name"], "amount": p["amount"], "seat_price": p["seat_price"],
        "seats_included": p["seats_included"], "seats_extra": seats_extra,
        "billing_status": "unpaid", "onboarding_status": "created",
        "owner_user_id": owner_user_id, "created_by": created_by, "created_at": now_iso(), "notes": "",
    }


def seat_limit(customer: dict) -> int:
    return int(customer.get("seats_included") or 0) + int(customer.get("seats_extra") or 0)


async def seats_used(db, org_id: str) -> int:
    return await db.users.count_documents({"organization_id": org_id, "status": {"$nin": ["deactivated", "inactive"]}})


async def customer_org(db, org_id: str | None = None, store_id: str | None = None) -> dict | None:
    """The organization doc when it is a launch customer, else None (legacy orgs and unknown ids)."""
    if not org_id and store_id and ObjectId.is_valid(store_id):
        store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"organization_id": 1})
        org_id = (store or {}).get("organization_id")
    if not org_id or not ObjectId.is_valid(org_id):
        return None
    org = await db.organizations.find_one({"_id": ObjectId(org_id), "customer": {"$exists": True}})
    return org


async def assert_seat_available(db, org_id: str | None = None, store_id: str | None = None, adding: int = 1) -> None:
    """Every path that creates a user inside an organization calls this. Legacy orgs are never limited."""
    org = await customer_org(db, org_id, store_id)
    if not org:
        return
    limit = seat_limit(org["customer"])
    used = await seats_used(db, str(org["_id"]))
    if used + adding > limit:
        raise HTTPException(status_code=400, detail=f"This plan includes {limit} seat{'s' if limit != 1 else ''} and {used} {'is' if used == 1 else 'are'} in use. Add a seat to the customer before inviting more people.")


async def audit(db, org_id: str, action: str, actor: dict | None, **details) -> None:
    await db.customer_audit_log.insert_one({
        "organization_id": org_id, "action": action,
        "actor_id": str(actor["_id"]) if actor else None, "actor_name": (actor or {}).get("name") or (actor or {}).get("email") or "system",
        "details": details, "at": now_iso(),
    })


async def _set(db, org_id: str, **fields) -> None:
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {f"customer.{k}": v for k, v in fields.items()}})


def _parse_expiry(value: str) -> datetime:
    raw = (value or "").strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
    except ValueError:
        dt = None
    if not dt:
        raise HTTPException(status_code=400, detail="Expiration date is required (YYYY-MM-DD)")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    today = datetime.now(timezone.utc)
    if dt <= today:
        raise HTTPException(status_code=400, detail="Expiration must be in the future")
    if dt > today + timedelta(days=MAX_EXCEPTION_DAYS):
        raise HTTPException(status_code=400, detail=f"Exceptions can last at most {MAX_EXCEPTION_DAYS} days")
    return dt


async def grant_exception(db, org: dict, actor: dict, reason: str, expires_at: str) -> dict:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Give a reason for the exception (at least 5 characters)")
    dt = _parse_expiry(expires_at)
    exc = {"reason": reason[:500], "expires_at": dt.isoformat(), "granted_by": str(actor["_id"]), "granted_by_name": actor.get("name") or actor.get("email"), "granted_at": now_iso()}
    await _set(db, str(org["_id"]), billing_status="exception", billing_exception=exc)
    await audit(db, str(org["_id"]), "billing_exception_granted", actor, reason=exc["reason"], expires_at=exc["expires_at"])
    return exc


def _exception_expired(customer: dict) -> bool:
    exc = customer.get("billing_exception") or {}
    try:
        return datetime.fromisoformat(exc.get("expires_at", "")) <= datetime.now(timezone.utc)
    except ValueError:
        return True


async def activate(db, org: dict, actor: dict) -> dict:
    c = org["customer"]
    org_id = str(org["_id"])
    if c.get("activated_at"):
        return {"already_active": True}
    if c.get("billing_status") not in BILLING_OK:
        raise HTTPException(status_code=409, detail="Not paid yet. Confirm payment or grant a billing exception (reason + expiration) before activating.")
    if c.get("billing_status") == "exception" and _exception_expired(c):
        raise HTTPException(status_code=409, detail="The billing exception has expired. Grant a new one before activating.")
    if c.get("owner_user_id") and ObjectId.is_valid(c["owner_user_id"]):
        await db.users.update_one({"_id": ObjectId(c["owner_user_id"])}, {"$set": {"is_active": True, "updated_at": now_iso()}, "$unset": {"dormant": ""}})
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"active": True, "updated_at": now_iso()}})
    await _set(db, org_id, activated_at=now_iso(), activated_by=str(actor["_id"]), onboarding_status="activated")
    await audit(db, org_id, "account_activated", actor, billing_status=c.get("billing_status"))
    return {"activated": True}


async def invite_owner(db, org: dict, actor: dict) -> dict:
    """Mint a single-use, expiring activation link for the dormant owner and send it by text + email."""
    from routers.admin_helpers import APP_URL, send_invite_email
    c = org["customer"]
    org_id = str(org["_id"])
    if not c.get("activated_at"):
        raise HTTPException(status_code=409, detail="Activate the account before inviting the owner.")
    owner = await db.users.find_one({"_id": ObjectId(c["owner_user_id"])}) if ObjectId.is_valid(c.get("owner_user_id") or "") else None
    if not owner:
        raise HTTPException(status_code=404, detail="Owner account not found")
    if owner.get("activation_pending") is False and owner.get("activated_at"):
        raise HTTPException(status_code=409, detail="The owner already activated their account.")

    token = secrets.token_urlsafe(24)
    now_ts = datetime.now(timezone.utc).timestamp()
    await db.password_reset_tokens.update_many({"user_id": str(owner["_id"]), "purpose": "activate_link", "used": False},
                                               {"$set": {"used": True, "used_at": now_ts, "superseded": True}})
    expires_ts = now_ts + INVITE_TTL_HOURS * 3600
    await db.password_reset_tokens.insert_one({"user_id": str(owner["_id"]), "purpose": "activate_link", "token": token, "created_at": now_ts,
                                               "expires_at": expires_ts, "used": False, "attempts": 0, "source": "customer_launch", "organization_id": org_id})
    link = f"{APP_URL}/auth/activate?token={token}"
    try:
        from routers.short_urls import create_short_url
        short = await create_short_url(original_url=link, link_type="activation", reference_id=str(owner["_id"]), user_id=str(owner["_id"]), metadata={"user_name": owner.get("name", "")})
        link = short.get("short_url") or link
    except Exception as e:
        logger.debug(f"[Customers] short link skipped: {e}")

    first = (owner.get("first_name") or (owner.get("name") or "").split(" ")[0] or "there")
    sms_sent = False
    if owner.get("phone"):
        try:
            from services.twilio_service import send_sms
            body = (f"Welcome to I'm On Social, {first}! Your {org.get('name', 'company')} account is ready. "
                    f"Tap to activate and choose your password (this link works once and expires in {INVITE_TTL_HOURS} hours): {link}")
            res = await send_sms(owner["phone"], body, purpose="system", system_kind="account_invite")
            sms_sent = bool(res.get("success"))
        except Exception as e:
            logger.warning(f"[Customers] owner invite text failed for {org_id}: {e}")
    email_sent = False
    email = (owner.get("email") or "").lower()
    if email and not email.endswith(PLACEHOLDER_EMAIL_SUFFIX):
        try:
            email_sent = await send_invite_email(email=email, name=owner.get("name") or first, temp_password=None, role="store_manager",
                                                 inviter_name=actor.get("name"), phone=owner.get("phone"), activate_url=link)
        except Exception as e:
            logger.warning(f"[Customers] owner invite email failed for {org_id}: {e}")

    expires_iso = datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat()
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"customer.owner_invited_at": now_iso(), "customer.onboarding_status": "owner_invited",
                                                                      "customer.invite_expires_at": expires_iso}, "$inc": {"customer.invite_count": 1}})
    await audit(db, org_id, "owner_invited", actor, sms_sent=sms_sent, email_sent=email_sent, expires_at=expires_iso)
    return {"sms_sent": sms_sent, "email_sent": email_sent, "expires_at": expires_iso}


async def on_owner_activated(db, user_id: str) -> None:
    """Called after /auth/activate/complete: stamp the customer and tell the founder."""
    org = await db.organizations.find_one({"customer.owner_user_id": user_id}, {"name": 1, "customer": 1})
    if not org or org["customer"].get("owner_activated_at"):
        return
    org_id = str(org["_id"])
    await _set(db, org_id, owner_activated_at=now_iso(), onboarding_status="owner_active")
    await audit(db, org_id, "owner_activated", None, user_id=user_id)
    from services import pilot_program
    org = await db.organizations.find_one({"_id": org["_id"]}, {"name": 1, "customer": 1})
    started = await pilot_program.start(db, org)
    owner = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})
    founder = org["customer"].get("created_by")
    if not founder:
        return
    title = f"{(owner or {}).get('name') or 'The owner'} activated {org.get('name', 'their account')}"
    body = "They can sign in now. Next: a work number and their first card share."
    if started:
        ends = ((await db.organizations.find_one({"_id": org["_id"]}, {"customer.pilot_program.ends_at": 1}))["customer"]["pilot_program"].get("ends_at") or "")[:10]
        body = f"Their 90-day Founding Partner Pilot started today and ends {ends}. Next: a work number and their first card share."
    try:
        from routers.push_notifications import send_push_to_user
        await send_push_to_user(founder, title, body, f"/admin/customers/{org_id}", "checkmark-circle")
    except Exception as e:
        logger.warning(f"[Customers] founder push failed: {e}")
    try:
        from routers.notifications import create_notification
        await create_notification("customer_owner_activated", title, body, user_id=founder, link=f"/admin/customers/{org_id}")
    except Exception as e:
        logger.debug(f"[Customers] founder notification skipped: {e}")


async def row(db, org: dict, with_issues: bool = False) -> dict:
    """One founder-facing record per customer, computed from existing collections."""
    from services import pilot
    from services import billing as _billing
    c = dict(org.get("customer") or {})
    org_id = str(org["_id"])
    owner = None
    if ObjectId.is_valid(c.get("owner_user_id") or ""):
        owner = await db.users.find_one({"_id": ObjectId(c["owner_user_id"])}, {"name": 1, "email": 1, "phone": 1, "is_active": 1, "activation_pending": 1, "activated_at": 1, "last_login": 1, "photo_url": 1})
    users = await db.users.find({"organization_id": org_id, "status": {"$nin": ["deactivated", "inactive"]}},
                                {"activation_pending": 1, "twilio_number": 1, "mvpline_number": 1}).to_list(1000)
    store = await db.stores.find_one({"organization_id": org_id}, {"name": 1, "phone": 1, "compliance": 1})
    if c.get("billing_status") == "exception" and _exception_expired(c):
        c["exception_expired"] = True
    owner_email = (owner or {}).get("email") or ""
    signals = await pilot.founder_view(db, org, owner, with_issues=with_issues)
    from services import pilot_program
    return {
        "organization_id": org_id, "name": org.get("name"), "city": org.get("city"), "state": org.get("state"), "industry": org.get("industry"),
        "org_active": bool(org.get("active")), "created_at": org.get("created_at"),
        "customer": c,
        "pilot_program": pilot_program.view(c), "mrr": pilot_program.mrr(c), "billing_config": _billing.mode_info(),
        **signals,
        "owner": owner and {
            "user_id": str(owner["_id"]), "name": owner.get("name"), "email": "" if owner_email.endswith(PLACEHOLDER_EMAIL_SUFFIX) else owner_email,
            "phone": owner.get("phone"), "dormant": owner.get("is_active") is False,
            "activated": owner.get("activation_pending") is False and bool(owner.get("activated_at")), "last_login": owner.get("last_login"),
            "has_photo": bool(owner.get("photo_url")),
        },
        "seats": {"included": c.get("seats_included", 0), "extra": c.get("seats_extra", 0), "limit": seat_limit(c), "used": len(users)},
        "users": {"total": len(users), "activated": sum(1 for u in users if u.get("activation_pending") is False), "with_work_number": sum(1 for u in users if u.get("twilio_number") or u.get("mvpline_number"))},
        "store": store and {"store_id": str(store["_id"]), "name": store.get("name"), "phone": store.get("phone"),
                            "a2p_status": ((store.get("compliance") or {}).get("status") or "not_started")},
    }
