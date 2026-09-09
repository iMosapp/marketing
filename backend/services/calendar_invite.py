"""Customer calendar invites: when a rep books a timed appointment, text (and email) the customer an
Add-to-Calendar link from the rep's number, then a morning-of reminder text. Public page: routers/public_appt.py."""
import os
import base64
import logging
from services.tag_workflows import initial_ai_state as _ai_state
import secrets
import asyncio
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from bson import ObjectId

from routers.database import get_db
from services.twilio_service import send_sms, get_rep_twilio_number, normalize_phone
from utils.activity_log import log_activity

logger = logging.getLogger(__name__)

INVITE_TYPES = ("appointment", "test_drive", "delivery", "meeting")
DURATION_MIN = 60
AUTO_SOURCES = ("manual", "call_extraction")  # text-extracted appointments wait for the rep to tap Send
REMINDER_HOUR = 8


def invite_eligible(task: dict) -> bool:
    return (task.get("appointment_type") in INVITE_TYPES and bool(task.get("has_time"))
            and bool(task.get("contact_id")) and isinstance(task.get("due_date"), datetime))


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def public_base() -> str:
    return (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "").rstrip("/")


async def user_tz(db, user: dict) -> ZoneInfo:
    name = (user or {}).get("timezone")
    if (not name or name == "UTC") and (user or {}).get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(str(user["store_id"]))}, {"timezone": 1})
            name = (store or {}).get("timezone") or name
        except Exception:
            pass
    try:
        return ZoneInfo(name if name and name != "UTC" else "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


async def load_context(db, task: dict) -> dict | None:
    """Everything the text, page, .ics and email need, resolved once."""
    if not ObjectId.is_valid(str(task.get("user_id") or "")) or not ObjectId.is_valid(str(task.get("contact_id") or "")):
        return None
    user = await db.users.find_one({"_id": ObjectId(task["user_id"])},
                                   {"name": 1, "email": 1, "phone": 1, "timezone": 1, "store_id": 1,
                                    "twilio_number": 1, "mvpline_number": 1, "notification_settings": 1})
    contact = await db.contacts.find_one({"_id": ObjectId(task["contact_id"])},
                                         {"first_name": 1, "last_name": 1, "phone": 1, "email": 1})
    if not user or not contact:
        return None
    store = None
    if user.get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(str(user["store_id"]))},
                                             {"name": 1, "address": 1, "city": 1, "state": 1, "zip_code": 1, "zip": 1, "phone": 1})
        except Exception:
            store = None
    tz = await user_tz(db, user)
    start = _utc(task["due_date"])
    rep_name = (user.get("name") or "your rep").strip()
    store_name = (store or {}).get("name") or ""
    addr_parts = [(store or {}).get("address"), (store or {}).get("city"),
                  " ".join(p for p in [(store or {}).get("state"), (store or {}).get("zip_code") or (store or {}).get("zip")] if p)]
    address = ", ".join(p.strip() for p in addr_parts if p and p.strip())
    return {
        "task": task, "user": user, "contact": contact, "store": store, "tz": tz,
        "start": start, "end": start + timedelta(minutes=DURATION_MIN), "local": start.astimezone(tz),
        "rep_name": rep_name, "rep_first": rep_name.split()[0],
        "rep_number": user.get("twilio_number") or user.get("mvpline_number") or "",
        "store_name": store_name, "address": address,
        "location": ", ".join(p for p in [store_name, address] if p),
        "first": (contact.get("first_name") or "").strip() or "there",
        "phone": contact.get("phone") or "", "email": (contact.get("email") or "").strip(),
        "event_title": f"Appointment with {rep_name}" + (f" at {store_name}" if store_name else ""),
    }


def when_label(ctx: dict, with_day: bool = True) -> str:
    d = ctx["local"]
    t = d.strftime("%-I:%M %p")
    return f"{d.strftime('%a, %b %-d')} at {t}" if with_day else t


def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(ctx: dict, method: str = "PUBLISH") -> str:
    task = ctx["task"]
    fmt = "%Y%m%dT%H%M%SZ"
    who = f"{ctx['rep_name']}" + (f" ({ctx['rep_number']})" if ctx["rep_number"] else "")
    desc = f"Booked with {who}. Reply to the text or call if anything changes."
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//I'm On Social//Appointments//EN", f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:appt-{task['_id']}@imonsocial.com",
        f"SEQUENCE:{int(task.get('invite_sequence') or 0)}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}",
        f"DTSTART:{ctx['start'].strftime(fmt)}",
        f"DTEND:{ctx['end'].strftime(fmt)}",
        f"SUMMARY:{_ics_escape(ctx['event_title'])}",
        f"DESCRIPTION:{_ics_escape(desc)}",
    ]
    if ctx["location"]:
        lines.append(f"LOCATION:{_ics_escape(ctx['location'])}")
    if method == "REQUEST" and ctx["user"].get("email"):
        lines.append(f"ORGANIZER;CN={_ics_escape(ctx['rep_name'])}:mailto:{ctx['user']['email']}")
        if ctx["email"]:
            lines.append(f"ATTENDEE;CN={_ics_escape(ctx['first'])};RSVP=TRUE;PARTSTAT=NEEDS-ACTION:mailto:{ctx['email']}")
    lines += ["STATUS:CONFIRMED", "BEGIN:VALARM", "TRIGGER:-PT1H", "ACTION:DISPLAY",
              "DESCRIPTION:Appointment in 1 hour", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def google_url(ctx: dict) -> str:
    fmt = "%Y%m%dT%H%M%SZ"
    q = (f"action=TEMPLATE&text={quote(ctx['event_title'])}"
         f"&dates={ctx['start'].strftime(fmt)}/{ctx['end'].strftime(fmt)}"
         f"&details={quote('Booked with ' + ctx['rep_name'] + '. Reply to the text if anything changes.')}")
    if ctx["location"]:
        q += f"&location={quote(ctx['location'])}"
    return "https://calendar.google.com/calendar/render?" + q


async def ensure_token(db, task: dict) -> str:
    if task.get("invite_token"):
        return task["invite_token"]
    token = secrets.token_urlsafe(12)
    await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"invite_token": token}})
    task["invite_token"] = token
    return token


async def _short_link(db, task: dict, token: str) -> str:
    from routers.short_urls import create_short_url
    url = f"{public_base()}/api/public/appt/{token}"
    try:
        res = await create_short_url(url, "calendar_invite", reference_id=str(task["_id"]), user_id=task["user_id"],
                                     metadata={"contact_id": str(task["contact_id"])})
        return res["short_url"]
    except Exception as e:
        logger.warning(f"[CalInvite] short link failed, using long url: {e}")
        return url


async def _conversation(db, ctx: dict) -> dict | None:
    """Same (rep_phone, contact_phone) key the Twilio webhook uses, so the customer's reply lands in this thread."""
    task, user = ctx["task"], ctx["user"]
    rep_phone = ctx["rep_number"]
    contact_phone = normalize_phone(ctx["phone"]) if ctx["phone"] else ""
    conv = None
    if rep_phone and contact_phone:
        conv = await db.conversations.find_one({"rep_phone": rep_phone, "contact_phone": contact_phone})
    if not conv:
        conv = await db.conversations.find_one({"user_id": task["user_id"],
                                                "contact_id": {"$in": [str(task["contact_id"]), ObjectId(str(task["contact_id"]))]}},
                                               sort=[("last_message_at", -1)])
    if conv:
        return conv
    now = datetime.now(timezone.utc)
    doc = {"user_id": task["user_id"], "rep_phone": rep_phone, "contact_id": str(task["contact_id"]),
           "contact_phone": contact_phone, "contact_name": f"{ctx['contact'].get('first_name', '')} {ctx['contact'].get('last_name', '')}".strip(),
           "status": "active", **(await _ai_state(db, task["contact_id"])), "unread": False, "unread_count": 0,
           "needs_assistance": False, "created_at": now, "last_message_at": now}
    doc["_id"] = (await db.conversations.insert_one(doc)).inserted_id
    return doc


async def _text_customer(db, ctx: dict, body: str, kind: str) -> dict:
    """Send from the rep's number and log the bubble in the thread + activity feed."""
    if not ctx["phone"]:
        return {"success": False, "error": "no_phone"}
    if not ctx["rep_number"]:
        return {"success": False, "error": "no_rep_number"}
    res = await send_sms(ctx["phone"], body, from_phone=ctx["rep_number"])
    now = datetime.now(timezone.utc)
    conv = await _conversation(db, ctx)
    sid = res.get("message_sid") or res.get("sid")
    await db.messages.insert_one({
        "conversation_id": str(conv["_id"]) if conv else f"auto_{ctx['task']['user_id']}_{ctx['task']['contact_id']}",
        "sender": "user", "content": body, "timestamp": now, "auto_sent": True, "kind": kind, "channel": "sms",
        "user_id": ctx["task"]["user_id"], "contact_id": str(ctx["task"]["contact_id"]), "task_id": str(ctx["task"]["_id"]),
        "twilio_sid": sid, "status": "sent" if res.get("success") else "failed",
        "error_message": None if res.get("success") else str(res.get("error") or "send failed"),
    })
    if conv:
        await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {
            "last_message_at": now, "last_message": body[:200], "last_message_sender": "user"}})
    if res.get("success"):
        await log_activity(db, user_id=ctx["task"]["user_id"], contact_id=str(ctx["task"]["contact_id"]), event_type="sms_sent",
                           description=("Calendar invite: " if kind == "calendar_invite" else "Appointment reminder: ") + when_label(ctx),
                           channel="sms", ref=sid, metadata={"task_id": str(ctx["task"]["_id"]), "kind": kind})
    return res


async def _email_customer(ctx: dict, link: str, updated: bool) -> dict:
    key = os.environ.get("RESEND_API_KEY")
    if not ctx["email"] or not key:
        return {"success": False, "error": "no_email" if not ctx["email"] else "email_disabled"}
    import resend
    resend.api_key = key
    ics = build_ics(ctx, method="REQUEST")
    when = when_label(ctx)
    where = f"<p style='margin:0 0 6px;color:#666'>{ctx['location']}</p>" if ctx["location"] else ""
    head = "Updated time for your appointment" if updated else "You're all set"
    html = (f"<div style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;padding:28px 20px;color:#111'>"
            f"<p style='font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#9a7b2f;margin:0 0 8px'>{head}</p>"
            f"<h1 style='font-size:24px;margin:0 0 6px'>{when}</h1>"
            f"<p style='margin:0 0 6px;color:#333'>with {ctx['rep_name']}{(' at ' + ctx['store_name']) if ctx['store_name'] else ''}</p>{where}"
            f"<p style='margin:20px 0'><a href='{link}' style='background:#C9A962;color:#000;text-decoration:none;font-weight:700;padding:12px 20px;border-radius:999px;display:inline-block'>Add to my calendar</a></p>"
            f"<p style='font-size:13px;color:#666;margin:0'>The invite is attached too. Reply to this email or text {ctx['rep_first']}"
            f"{(' at ' + ctx['rep_number']) if ctx['rep_number'] else ''} if anything changes.</p></div>")
    params = {
        "from": f"{ctx['rep_name']} <{os.environ.get('SENDER_EMAIL', 'notifications@imonsocial.com')}>",
        "to": [ctx["email"]],
        "reply_to": ctx["user"].get("email") or "support@imonsocial.com",
        "subject": f"{'Updated: ' if updated else ''}Your appointment with {ctx['rep_first']}: {when}",
        "html": html,
        "attachments": [{"filename": "appointment.ics", "content": base64.b64encode(ics.encode()).decode(),
                         "content_type": "text/calendar; method=REQUEST"}],
    }
    try:
        r = await asyncio.to_thread(resend.Emails.send, params)
        return {"success": True, "id": (r or {}).get("id")}
    except Exception as e:
        logger.warning(f"[CalInvite] email failed for task {ctx['task']['_id']}: {e}")
        return {"success": False, "error": str(e)}


def _sms_body(ctx: dict, link: str, updated: bool) -> str:
    where = f" at {ctx['store_name']}" if ctx["store_name"] else ""
    if updated:
        return (f"Hi {ctx['first']}, quick update from {ctx['rep_first']}: your appointment moved to {when_label(ctx)}{where}. "
                f"Tap to update your calendar: {link}\nReply here if that doesn't work for you.")
    return (f"Hi {ctx['first']}, you're all set: {when_label(ctx)} with {ctx['rep_first']}{where}. "
            f"Tap to add it to your calendar: {link}\nReply here if anything changes.")


async def send_calendar_invite(task_id: str, *, reason: str = "booked", force: bool = False) -> dict:
    """reason: booked | updated | manual. Returns {sent, sms, email, skipped}."""
    db = get_db()
    task = await db.tasks.find_one({"_id": ObjectId(task_id)}) if ObjectId.is_valid(task_id) else None
    if not task or not invite_eligible(task):
        return {"sent": False, "skipped": "not_eligible"}
    if task.get("completed") or task.get("status") in ("completed", "dismissed"):
        return {"sent": False, "skipped": "closed"}
    if _utc(task["due_date"]) < datetime.now(timezone.utc):
        return {"sent": False, "skipped": "past"}
    ctx = await load_context(db, task)
    if not ctx:
        return {"sent": False, "skipped": "no_contact"}
    if not force and (ctx["user"].get("notification_settings") or {}).get("calendar_invites") is False:
        return {"sent": False, "skipped": "disabled"}
    if not ctx["phone"] and not ctx["email"]:
        return {"sent": False, "skipped": "no_phone_or_email"}

    updated = reason == "updated"
    seq = int(task.get("invite_sequence") or 0) + (1 if updated else 0)
    task["invite_sequence"] = seq
    token = await ensure_token(db, task)
    link = task.get("invite_short_url") or await _short_link(db, task, token)

    sms = await _text_customer(db, ctx, _sms_body(ctx, link, updated), "calendar_invite")
    email = await _email_customer(ctx, link, updated)
    sent = bool(sms.get("success") or email.get("success"))
    channels = [c for c, r in (("sms", sms), ("email", email)) if r.get("success")]
    now = datetime.now(timezone.utc)
    upd = {"invite_short_url": link, "invite_sequence": seq, "invite_last_reason": reason,
           "invite_sms_status": "sent" if sms.get("success") else str(sms.get("error") or "failed"),
           "invite_email_status": "sent" if email.get("success") else str(email.get("error") or "failed"),
           "invite_attempted_at": now}
    if sent:
        upd["invite_sent_at"] = now
        upd["invite_channels"] = channels
    await db.tasks.update_one({"_id": task["_id"]}, {"$set": upd})
    logger.info(f"[CalInvite] task {task_id} reason={reason} sms={upd['invite_sms_status']} email={upd['invite_email_status']}")
    return {"sent": sent, "sms": sms.get("success", False), "email": email.get("success", False),
            "channels": channels, "link": link, "when": when_label(ctx), "first": ctx["first"]}


async def schedule_invite(task_id: str, *, reason: str = "booked", delay_s: int = 45) -> None:
    """Fire-and-forget with a short delay so a quick time correction sends ONE text, not two."""
    db = get_db()
    stamp = secrets.token_hex(6)
    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"invite_dirty_at": stamp}})

    async def _run():
        try:
            await asyncio.sleep(delay_s)
            t = await db.tasks.find_one({"_id": ObjectId(task_id)}, {"invite_dirty_at": 1, "invite_sent_at": 1})
            if not t or t.get("invite_dirty_at") != stamp:
                return
            r = reason if not (reason == "booked" and t.get("invite_sent_at")) else "updated"
            await send_calendar_invite(task_id, reason=r)
        except Exception as e:
            logger.warning(f"[CalInvite] scheduled send failed for {task_id}: {e}")

    asyncio.create_task(_run())


def should_auto_invite(task: dict) -> bool:
    return invite_eligible(task) and task.get("source") in AUTO_SOURCES


async def send_customer_appointment_reminders() -> int:
    """Scheduler (15 min): morning-of text for today's timed appointments booked before today."""
    db = get_db()
    now = datetime.now(timezone.utc)
    tasks = await db.tasks.find({
        "appointment_type": {"$in": list(INVITE_TYPES)}, "has_time": True, "completed": {"$ne": True},
        "status": {"$nin": ["completed", "dismissed"]}, "customer_reminder_sent_at": {"$exists": False},
        "due_date": {"$gte": now + timedelta(minutes=30), "$lte": now + timedelta(hours=20)},
    }).to_list(300)
    sent = 0
    for task in tasks:
        try:
            if not invite_eligible(task):
                continue
            ctx = await load_context(db, task)
            if not ctx or not ctx["phone"] or not ctx["rep_number"]:
                continue
            if (ctx["user"].get("notification_settings") or {}).get("calendar_invite_reminder") is False:
                continue
            now_local = now.astimezone(ctx["tz"])
            if ctx["local"].date() != now_local.date() or now_local.hour < REMINDER_HOUR:
                continue
            created = _utc(task.get("created_at") or now).astimezone(ctx["tz"])
            if created.date() >= now_local.date():
                await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"customer_reminder_sent_at": None, "customer_reminder_skipped": "booked_today"}})
                continue
            where = f" at {ctx['store_name']}" if ctx["store_name"] else ""
            body = (f"Good morning {ctx['first']}, quick reminder from {ctx['rep_first']}: you're set for {when_label(ctx, with_day=False)} today{where}. "
                    f"Reply here if anything has changed. See you then.")
            res = await _text_customer(db, ctx, body, "appointment_reminder")
            await db.tasks.update_one({"_id": task["_id"]}, {"$set": {
                "customer_reminder_sent_at": now, "customer_reminder_status": "sent" if res.get("success") else str(res.get("error") or "failed")}})
            sent += int(bool(res.get("success")))
        except Exception as e:
            logger.warning(f"[CalInvite] reminder failed for task {task.get('_id')}: {e}")
    if sent:
        logger.info(f"[CalInvite] Sent {sent} morning-of appointment reminders")
    return sent
