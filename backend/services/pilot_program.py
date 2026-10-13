"""Founding Partner Pilot: 90 complimentary days from owner activation, founder reminders, explicit conversion only.
State lives on organizations.customer.pilot_program; legacy orgs (no `customer`) are never touched."""
import asyncio
import logging
import math
import os
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from fastapi import HTTPException

from services import customers as cust

logger = logging.getLogger(__name__)

DAYS = 90
REMINDER_DAYS = (30, 60, 75, 90)
EXTEND_CHOICES = (30, 60, 90)
RETENTION_DAYS = 365
ENDED_MSG = "Your Founding Partner Pilot with I'm On Social has ended. Text or email Forest to continue; your contacts and messages are safe."
PILOT_STATES = ("pending", "active", "completed")


def _dt(iso):
    try:
        d = datetime.fromisoformat(iso) if iso else None
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d


def new_program(actor: dict) -> dict:
    return {"kind": "founding_partner", "days": DAYS, "state": "pending", "granted_at": cust.now_iso(),
            "granted_by": str(actor["_id"]), "granted_by_name": actor.get("name") or actor.get("email"),
            "started_at": None, "ends_at": None, "reminders_sent": [], "reminder_log": [], "extensions": []}


def view(c: dict) -> dict | None:
    """Read-side summary: effective state (a passed end date reads as completed), days left, pilot day number."""
    p = c.get("pilot_program")
    if not p:
        return None
    now = datetime.now(timezone.utc)
    ends, started = _dt(p.get("ends_at")), _dt(p.get("started_at"))
    state = p.get("state")
    if state == "active" and ends and ends <= now:
        state = "completed"
    days_left = max(0, math.ceil((ends - now).total_seconds() / 86400)) if ends else None
    day = (now - started).days + 1 if started else None
    return {"kind": p.get("kind"), "state": state, "days": p.get("days", DAYS), "started_at": p.get("started_at"), "ends_at": p.get("ends_at"),
            "days_left": days_left, "day": day, "reminders_sent": p.get("reminders_sent", []), "extensions": p.get("extensions", []),
            "ended_at": p.get("ended_at"), "ended_reason": p.get("ended_reason"), "converted_at": p.get("converted_at"),
            "ended_days_ago": (now - _dt(p["ended_at"])).days if p.get("ended_at") and _dt(p["ended_at"]) else None}


def mrr(c: dict) -> dict:
    """Actual MRR (charged subscription) is never mixed with potential pilot MRR."""
    amount = float(c.get("amount") or 0) + float(c.get("seat_price") or 0) * int(c.get("seats_extra") or 0)
    bs = c.get("billing_status")
    if bs in ("active", "past_due"):
        kind = "actual"
    elif bs == "trialing":
        kind = "scheduled"
    elif bs == "canceled" or (c.get("pilot_program") or {}).get("state") == "ended":
        kind = "none"
    else:
        kind = "potential"
    return {"amount": amount, "kind": kind, "first_charge_on": c.get("current_period_end") if kind == "scheduled" else None}


async def _set_program(db, org_id: str, **fields) -> None:
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {f"customer.pilot_program.{k}": v for k, v in fields.items()}})


async def grant(db, org: dict, actor: dict) -> dict:
    """Put an unpaid customer on the 90-day pilot. The clock starts when the owner activates (or now if they already did)."""
    c = org["customer"]
    org_id = str(org["_id"])
    if c.get("stripe_subscription_id") and c.get("billing_status") in ("active", "trialing", "past_due"):
        raise HTTPException(status_code=409, detail="This customer already pays through Stripe.")
    if c.get("billing_status") == "pilot":
        raise HTTPException(status_code=409, detail="This customer is already on the pilot.")
    program = new_program(actor)
    await cust._set(db, org_id, billing_status="pilot", pilot_program=program)
    await cust.audit(db, org_id, "pilot_granted", actor, days=DAYS, plan_key=c.get("plan_key"), amount=c.get("amount"))
    if c.get("owner_activated_at"):
        await start(db, await cust.customer_org(db, org_id))
    return program


async def start(db, org: dict) -> bool:
    """Owner activation starts the clock exactly once; later logins never move it."""
    c = org["customer"]
    p = c.get("pilot_program") or {}
    if c.get("billing_status") != "pilot" or p.get("state") != "pending":
        return False
    now = datetime.now(timezone.utc)
    ends = now + timedelta(days=int(p.get("days") or DAYS))
    r = await db.organizations.update_one({"_id": org["_id"], "customer.pilot_program.state": "pending"},
                                          {"$set": {"customer.pilot_program.state": "active", "customer.pilot_program.started_at": now.isoformat(),
                                                    "customer.pilot_program.ends_at": ends.isoformat()}})
    if r.modified_count:
        await cust.audit(db, str(org["_id"]), "pilot_started", None, started_at=now.isoformat(), ends_at=ends.isoformat(), days=p.get("days", DAYS))
    return bool(r.modified_count)


def _require_pilot(c: dict, states=PILOT_STATES) -> dict:
    p = c.get("pilot_program")
    if not p or c.get("billing_status") != "pilot":
        raise HTTPException(status_code=409, detail="This customer is not on the pilot.")
    if p.get("state") not in states:
        raise HTTPException(status_code=409, detail=f"The pilot is {p.get('state')}; this action does not apply.")
    return p


def _reason(reason: str) -> str:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Give a reason (at least 5 characters)")
    return reason[:500]


async def extend(db, org: dict, actor: dict, days: int, reason: str) -> dict:
    c = org["customer"]
    p = _require_pilot(c)
    reason = _reason(reason)
    days = int(days or 0)
    if days < 1 or days > 180:
        raise HTTPException(status_code=400, detail="Extend by 1 to 180 days")
    org_id = str(org["_id"])
    now = datetime.now(timezone.utc)
    before = p.get("ends_at")
    if p.get("state") == "pending":
        fields = {"days": int(p.get("days") or DAYS) + days}
        after = None
    else:
        base = max(_dt(before) or now, now)
        after = (base + timedelta(days=days)).isoformat()
        fields = {"ends_at": after, "state": "active"}
    entry = {"days": days, "reason": reason, "by": str(actor["_id"]), "by_name": actor.get("name") or actor.get("email"), "at": cust.now_iso(), "ends_at_before": before, "ends_at_after": after}
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {f"customer.pilot_program.{k}": v for k, v in fields.items()}, "$push": {"customer.pilot_program.extensions": entry}})
    await cust.audit(db, org_id, "pilot_extended", actor, reason=reason, days=days, ends_at_before=before, ends_at_after=after)
    return entry


async def end(db, org: dict, actor: dict, reason: str) -> dict:
    """Founder ends the pilot: every user of the org is blocked (sign-in, session restore and every API call). Data is never touched."""
    c = org["customer"]
    _require_pilot(c)
    reason = _reason(reason)
    org_id = str(org["_id"])
    now = cust.now_iso()
    await _set_program(db, org_id, state="ended", ended_at=now, ended_by=str(actor["_id"]), ended_reason=reason, resumed_at=None)
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"active": False, "updated_at": now}})
    users = await db.users.find({"organization_id": org_id}, {"_id": 1}).to_list(2000)
    await db.users.update_many({"organization_id": org_id}, {"$set": {"access_blocked": {"reason": "pilot_ended", "organization_id": org_id, "at": now}}})
    from services import access_block
    access_block.invalidate([str(u["_id"]) for u in users])
    await cust.audit(db, org_id, "pilot_ended", actor, reason=reason, users_blocked=len(users))
    return {"ended_at": now, "users_blocked": len(users)}


async def resume(db, org: dict, actor: dict, reason: str, extra_days: int = 0) -> dict:
    c = org["customer"]
    p = _require_pilot(c, states=("ended",))
    reason = _reason(reason)
    org_id = str(org["_id"])
    now = datetime.now(timezone.utc)
    fields = {"state": "active" if p.get("started_at") else "pending", "resumed_at": now.isoformat(), "resumed_by": str(actor["_id"]), "resume_reason": reason}
    if extra_days and p.get("started_at"):
        fields["ends_at"] = (max(_dt(p.get("ends_at")) or now, now) + timedelta(days=int(extra_days))).isoformat()
    await _set_program(db, org_id, **fields)
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"active": True, "updated_at": now.isoformat()}})
    users = await db.users.find({"organization_id": org_id}, {"_id": 1}).to_list(2000)
    await db.users.update_many({"organization_id": org_id}, {"$unset": {"access_blocked": ""}})
    from services import access_block
    access_block.invalidate([str(u["_id"]) for u in users])
    await cust.audit(db, org_id, "pilot_resumed", actor, reason=reason, extra_days=int(extra_days or 0), ends_at=fields.get("ends_at", p.get("ends_at")))
    return {"resumed_at": fields["resumed_at"], "ends_at": fields.get("ends_at", p.get("ends_at"))}


async def mark_converted(db, org: dict, source: str, status: str) -> None:
    """A Stripe subscription appeared for a pilot customer: they chose to continue. Nothing here is automatic.
    Atomic claim on the state so two webhook deliveries (two pods, two events) record and notify exactly once."""
    org_id = str(org["_id"])
    c = org["customer"]
    claimed = await db.organizations.find_one_and_update(
        {"_id": org["_id"], "customer.pilot_program.kind": "founding_partner", "customer.pilot_program.state": {"$ne": "converted"}},
        {"$set": {"customer.pilot_program.state": "converted", "customer.pilot_program.converted_at": cust.now_iso(),
                  "customer.pilot_program.converted_via": source, "updated_at": cust.now_iso()}})
    if not claimed:
        return
    await cust.audit(db, org_id, "pilot_converted", None, source=source, stripe_status=status, first_charge_on=c.get("current_period_end"))
    when = f" The first charge lands on {(c.get('current_period_end') or '')[:10]}." if status == "trialing" else ""
    await notify_founder(db, org, "customer_pilot_converted", f"{org.get('name')} chose to continue after the pilot",
                         f"Payment method saved through Stripe.{when} Nothing to do.")


async def notify_founder(db, org: dict, ntype: str, title: str, body: str) -> dict:
    """Push + in-app Alert (existing founder channel) + email. Returns what each channel did."""
    from services.billing import _notify_founder
    result = {"push_alert": False, "email": False}
    try:
        await _notify_founder(db, org, ntype, title, body)
        result["push_alert"] = True
    except Exception as e:
        logger.warning(f"[Pilot] founder push/alert failed: {e}")
    founder_id = (org.get("customer") or {}).get("created_by")
    founder = await db.users.find_one({"_id": ObjectId(founder_id)}, {"email": 1}) if founder_id and ObjectId.is_valid(founder_id) else None
    email = (founder or {}).get("email")
    if email and os.environ.get("RESEND_API_KEY"):
        try:
            import resend
            resend.api_key = os.environ.get("RESEND_API_KEY")
            sender = os.environ.get("SENDER_EMAIL", "notifications@imonsocial.com")
            link = f"{os.environ.get('APP_URL', 'https://app.imonsocial.com').rstrip('/')}/admin/customers/{org['_id']}"
            html = (f"<div style=\"font-family:-apple-system,Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px\"><h2 style=\"color:#1a1a1a\">{title}</h2>"
                    f"<p style=\"font-size:15px;line-height:22px\">{body}</p><p><a href=\"{link}\" style=\"background:#C9A962;color:#111;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:700\">Open the customer</a></p></div>")
            r = await asyncio.to_thread(resend.Emails.send, {"from": f"I'm On Social <{sender}>", "to": [email], "subject": title, "html": html, "text": f"{title}\n\n{body}\n\n{link}"})
            result["email"] = bool((r or {}).get("id"))
        except Exception as e:
            logger.warning(f"[Pilot] founder email failed: {e}")
    return result


def _reminder_text(org: dict, c: dict, v: dict, day: int) -> tuple[str, str]:
    name = org.get("name", "A pilot customer")
    money = f"${mrr(c)['amount']:,.0f}/mo"
    ends = (v.get("ends_at") or "")[:10]
    if day >= 90:
        return (f"{name}: the 90-day pilot is over", f"Nothing was charged and nothing happens automatically. Decide: send the continue link ({money}), extend the pilot, or end it. Access stays on until you choose.")
    left = v.get("days_left") or 0
    return (f"{name}: pilot day {day}, {left} days left", f"Ends {ends}. Agreed pricing after the pilot: {money}. A good moment to check in and ask whether they want to continue.")


async def tick(db) -> dict:
    """Daily: send each due milestone once (claimed atomically per milestone), mark finished pilots completed."""
    now = datetime.now(timezone.utc)
    sent, completed = [], []
    async for org in db.organizations.find({"customer.billing_status": "pilot", "customer.pilot_program.state": {"$in": ["active", "completed"]}}):
        c = org["customer"]
        v = view(c)
        if not v or not v.get("started_at"):
            continue
        day = (now - _dt(v["started_at"])).days
        for m in REMINDER_DAYS:
            if day < m:
                continue
            r = await db.organizations.update_one({"_id": org["_id"], "customer.pilot_program.reminders_sent": {"$ne": m}}, {"$addToSet": {"customer.pilot_program.reminders_sent": m}})
            if not r.modified_count:
                continue
            title, body = _reminder_text(org, c, v, m)
            res = await notify_founder(db, org, f"customer_pilot_day_{m}", title, body)
            await db.organizations.update_one({"_id": org["_id"]}, {"$push": {"customer.pilot_program.reminder_log": {"milestone": m, "at": cust.now_iso(), **res}}})
            await cust.audit(db, str(org["_id"]), "pilot_reminder_sent", None, milestone=m, **res)
            sent.append({"organization_id": str(org["_id"]), "milestone": m, **res})
        if (c.get("pilot_program") or {}).get("state") == "active" and v["state"] == "completed":
            r = await db.organizations.update_one({"_id": org["_id"], "customer.pilot_program.state": "active"}, {"$set": {"customer.pilot_program.state": "completed", "customer.pilot_program.completed_at": cust.now_iso()}})
            if r.modified_count:
                await cust.audit(db, str(org["_id"]), "pilot_completed", None, ends_at=v.get("ends_at"))
                completed.append(str(org["_id"]))
    return {"sent": sent, "completed": completed, "at": now.isoformat()}
