"""Client-side A2P 10DLC onboarding: the tokenized form we text + email to a new dealership, reminders while it sits, team
notifications (email + in-app + push) on every step and every Twilio status change, a daily digest, and the numbers exit
path (release or port-out packet) when a client cancels.

State lives in `stores.compliance.onboarding` / `.review` / `.preflight` / `.numbers_plan` / `.portout` next to the registration."""
import asyncio
import copy
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import twilio_compliance as tc
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

REMINDER_DAYS_DEFAULT = [2, 5, 9]
DIGEST_HOUR_DEFAULT = 8
DIGEST_TZ = "America/Denver"
PORT_OUT_HELP = "https://help.twilio.com/articles/223179588-How-do-I-port-my-phone-numbers-away-from-Twilio-"
SENDER_NAME = os.environ.get("COMPLIANCE_SENDER_NAME", "Forest")
ONBOARDING_STATUS_LABEL = {
    "not_sent": "Form not sent", "sent": "Form sent, not opened", "opened": "Opened, nothing saved yet", "in_progress": "Client is filling it in",
    "returned_incomplete": "Returned with gaps", "returned": "Returned, ready for review", "stalled": "No response after 3 reminders", "reviewed": "Reviewed by the team",
}


def _now():
    return datetime.now(timezone.utc)


def _app_url() -> str:
    from services.scripts import _app_url as u
    return u()


def form_url(rec: dict) -> str:
    return f"{_app_url()}/a2p-onboarding/{(rec.get('onboarding') or {}).get('token', '')}"


def portout_url(rec: dict) -> str:
    return f"{_app_url()}/port-out/{(rec.get('portout') or {}).get('token', '')}"


def ensure_tokens(rec: dict) -> dict:
    ob = rec.setdefault("onboarding", {})
    if not ob.get("token"):
        ob.update({"token": secrets.token_hex(20), "created_at": _now(), "sent": [], "reminders_sent": 0})
    po = rec.setdefault("portout", {})
    if not po.get("token"):
        po.update({"token": secrets.token_hex(20), "created_at": _now(), "sent": []})
    return rec


def onboarding_status(rec: dict) -> str:
    ob = rec.get("onboarding") or {}
    rv = rec.get("review") or {}
    if rv.get("status") == "reviewed":
        return "reviewed"
    if ob.get("returned_at"):
        return "returned_incomplete" if ob.get("returned_missing") else "returned"
    if ob.get("flagged_at"):
        return "stalled"
    if ob.get("last_saved_at"):
        return "in_progress"
    if ob.get("opened_at"):
        return "opened"
    if ob.get("first_sent_at"):
        return "sent"
    return "not_sent"


def next_action(store: dict) -> str:
    """One line for the digest / list: what the team should do next for this store."""
    rec = store.get("compliance") or {}
    stage, status = rec.get("stage") or "draft", rec.get("status") or "not_started"
    if stage == "complete":
        return "Approved. Nothing to do."
    if status in ("rejected", "error"):
        return f"Twilio {status}: {(rec.get('error') or '')[:140]}. Fix and resubmit."
    if stage != "draft":
        return f"In Twilio review ({tc.STAGE_LABEL.get(stage, stage)}). Waiting on Twilio."
    ob = onboarding_status(rec)
    miss = tc.missing_fields(rec)
    pf = rec.get("preflight") or {}
    if ob == "not_sent":
        return "Send the onboarding form to the client."
    if ob in ("sent", "opened", "in_progress"):
        n = (rec.get("onboarding") or {}).get("reminders_sent", 0)
        return f"Waiting on the client ({ONBOARDING_STATUS_LABEL[ob].lower()}, {n} reminder{'s' if n != 1 else ''} sent)."
    if ob == "stalled":
        return "Client went quiet after 3 reminders. Call them."
    if ob == "returned_incomplete" or miss:
        return "Client still owes: " + ", ".join(_pretty(m) for m in miss[:6]) + ("..." if len(miss) > 6 else "")
    if not pf.get("at"):
        return "Form is back and complete. Run pre-flight, review, submit."
    if pf.get("blockers"):
        return f"Pre-flight has {pf['blockers']} blocker{'s' if pf['blockers'] != 1 else ''}. Fix before submitting."
    if ob != "reviewed":
        return "Pre-flight clean. Mark reviewed and submit to Twilio."
    return "Reviewed and ready. Submit to Twilio."


def _pretty(key: str) -> str:
    return key.replace("business.", "").replace("rep.", "rep ").replace("campaign.", "").replace("_", " ")


# ── settings ──────────────────────────────────────────────────────────────────
async def settings(db) -> dict:
    base = await tc.get_settings(db)
    doc = await db.settings.find_one({"key": tc.SETTINGS_KEY}) or {}
    days = doc.get("reminder_days") if isinstance(doc.get("reminder_days"), list) and doc.get("reminder_days") else REMINDER_DAYS_DEFAULT
    return {**base, "auto_invite": doc.get("auto_invite", True), "reminder_days": days, "digest": doc.get("digest", True),
            "digest_hour": int(doc.get("digest_hour") or DIGEST_HOUR_DEFAULT), "last_digest_date": doc.get("last_digest_date"),
            "portout_pin": doc.get("portout_pin") or "", "portout_service_address": doc.get("portout_service_address") or "",
            "notify_emails": [e.strip().lower() for e in re.split(r"[,\s;]+", base.get("notify_email") or "") if "@" in e]}


async def save_settings(db, patch: dict, me: dict) -> dict:
    sets = {}
    if "auto_invite" in patch:
        sets["auto_invite"] = bool(patch["auto_invite"])
    if "digest" in patch:
        sets["digest"] = bool(patch["digest"])
    if "digest_hour" in patch:
        sets["digest_hour"] = max(0, min(23, int(patch["digest_hour"] or DIGEST_HOUR_DEFAULT)))
    if "reminder_days" in patch:
        days = sorted({int(d) for d in (patch["reminder_days"] or []) if str(d).strip().isdigit() and 0 < int(d) <= 60})[:5]
        sets["reminder_days"] = days or REMINDER_DAYS_DEFAULT
    for k in ("portout_pin", "portout_service_address"):
        if k in patch:
            sets[k] = str(patch[k] or "").strip()[:200]
    if sets:
        sets.update({"updated_at": _now(), "updated_by": str(me.get("_id"))})
        await db.settings.update_one({"key": tc.SETTINGS_KEY}, {"$set": sets, "$setOnInsert": {"key": tc.SETTINGS_KEY}}, upsert=True)
    return await settings(db)


# ── outbound: text + email ────────────────────────────────────────────────────
async def _email(to: str, subject: str, html: str, text: str) -> dict:
    key = os.environ.get("RESEND_API_KEY")
    if not key or not to or "@" not in to:
        return {"ok": False, "error": "Email is not configured" if not key else "No email address"}
    import resend
    resend.api_key = key
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    try:
        r = await asyncio.to_thread(resend.Emails.send, {"from": f"I'm On Social <{sender}>", "to": [to], "reply_to": os.environ.get("REPORT_REPLY_TO", "support@imonsocial.com"), "subject": subject, "html": html, "text": text})
        return {"ok": True, "id": (r or {}).get("id")}
    except Exception as e:
        logger.warning(f"[Compliance] email to {to} failed: {e}")
        return {"ok": False, "error": str(e)[:200]}


async def _sms(to: str, body: str) -> dict:
    if not to or len(re.sub(r"\D", "", to)) < 10:
        return {"ok": False, "error": "No cell number"}
    from services.twilio_service import send_sms
    try:
        r = await send_sms(to, no_em_dash(body))
        return {"ok": bool(r.get("success")), "error": r.get("error"), "sid": r.get("message_sid") or r.get("sid")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _html(title: str, lines: list[str], cta: Optional[tuple[str, str]] = None) -> str:
    body = "".join(f"<p style='margin:0 0 12px;font-size:15px;line-height:22px;color:#222'>{l}</p>" for l in lines)
    btn = f"<p style='margin:20px 0'><a href='{cta[1]}' style='background:#C9A962;color:#111;text-decoration:none;font-weight:700;padding:12px 20px;border-radius:10px;display:inline-block'>{cta[0]}</a></p><p style='font-size:12px;color:#777'>{cta[1]}</p>" if cta else ""
    return f"<div style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px'><h2 style='margin:0 0 16px;font-size:20px;color:#111'>{title}</h2>{body}{btn}<p style='font-size:12px;color:#999;margin-top:28px'>I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065</p></div>"


def _contact(rec: dict, store: dict) -> dict:
    ob = rec.get("onboarding") or {}
    rp = rec.get("rep") or {}
    c = dict(ob.get("contact") or {})
    c.setdefault("name", f"{rp.get('first_name', '')} {rp.get('last_name', '')}".strip())
    c.setdefault("email", rp.get("email") or "")
    c.setdefault("phone", rp.get("phone") or store.get("phone") or "")
    return c


def _client_messages(store: dict, rec: dict, kind: str, missing: list[str]) -> tuple[str, str, list[str]]:
    """(sms, email subject, email lines) for invite | reminder | missing."""
    name = store.get("name") or "your store"
    url = form_url(rec)
    first = ((_contact(rec, store).get("name") or "").split(" ") or [""])[0] or "there"
    if kind == "invite":
        sms = f"Hi {first}, {SENDER_NAME} at I'm On Social. Before your team can text customers, US carriers need your dealership registered (A2P 10DLC). It takes about 10 minutes: {url}"
        return sms, f"{name}: 10 minutes to unlock texting for your team", [
            f"Hi {first},",
            f"US carriers require every business that texts customers to be registered (it is called A2P 10DLC). Until {name} is registered, texts from your reps' numbers are throttled or blocked, so this is the first thing we do.",
            "We pre-filled what we already know. You add the legal business name and EIN as filed with the IRS, an authorized contact, your privacy and terms page links, and confirm how customers agree to receive texts.",
            "Save as you go; the link stays live. We review everything before it goes to the carriers and we handle the submission and the Caller ID name on your outbound calls."]
    if kind == "missing":
        items = ", ".join(_pretty(m) for m in missing[:8])
        sms = f"Hi {first}, {SENDER_NAME} here. Thanks for the registration details for {name}. Still need: {items}. Same link: {url}"
        return sms, f"{name}: a few items still needed for texting registration", [f"Hi {first},", f"Thank you for sending the registration details for {name}. The carriers will not accept the packet until these are in:", f"<b>{items}</b>", "Same link as before, everything you entered is saved."]
    sms = f"Hi {first}, quick reminder from {SENDER_NAME} at I'm On Social: {name}'s texting registration is waiting on you. About 10 minutes: {url}"
    return sms, f"Reminder: {name}'s texting registration is waiting on you", [f"Hi {first},", f"Your reps cannot text customers reliably until {name} is registered with the carriers. The form takes about 10 minutes and saves as you go.", "Reply to this email if anything is unclear and we will walk you through it."]


async def send_to_client(db, store: dict, kind: str = "invite", to_email: str = "", to_phone: str = "", channel: str = "both", me: Optional[dict] = None, note: str = "") -> dict:
    """Text + email the onboarding form (kind invite | reminder | missing). Records every attempt on the onboarding timeline."""
    rec = ensure_tokens(store.get("compliance") or tc.defaults(store))
    ob = rec["onboarding"]
    contact = _contact(rec, store)
    if to_email or to_phone:
        contact = {**contact, **({"email": to_email.strip().lower()} if to_email else {}), **({"phone": to_phone.strip()} if to_phone else {})}
    ob["contact"] = contact
    missing = tc.missing_fields(rec)
    sms, subject, lines = _client_messages(store, rec, kind, missing)
    if note:
        lines.insert(1, f"<i>{note}</i>")
        sms = f"{sms} {note}"[:600]
    results = []
    now = _now()
    if channel in ("both", "text") and contact.get("phone"):
        r = await _sms(contact["phone"], sms)
        results.append({"at": now, "kind": kind, "channel": "text", "to": contact["phone"], **r})
    if channel in ("both", "email") and contact.get("email"):
        r = await _email(contact["email"], subject, _html(subject, lines, ("Open the registration form", form_url(rec))), "\n\n".join(re.sub("<[^>]+>", "", l) for l in lines) + f"\n\n{form_url(rec)}")
        results.append({"at": now, "kind": kind, "channel": "email", "to": contact["email"], **r})
    if not results:
        raise ValueError("No email or cell number for the client. Add one first.")
    ob["sent"] = (ob.get("sent") or [])[-40:] + results
    if any(r["ok"] for r in results):
        ob.setdefault("first_sent_at", now)
        ob["last_sent_at"] = now
        if kind == "reminder":
            ob["reminders_sent"] = int(ob.get("reminders_sent") or 0) + 1
    rec["history"] = tc._hist(rec, rec.get("stage") or "draft", f"form_{kind}", ", ".join(f"{r['channel']} {'ok' if r['ok'] else 'failed: ' + str(r.get('error'))}" for r in results))
    await tc._save(db, str(store["_id"]), rec)
    ok = [r["channel"] for r in results if r["ok"]]
    if ok and kind == "invite":
        await notify_team(db, store, rec, "form_sent", f"{store.get('name')}: onboarding form sent", f"Sent by {', '.join(ok)} to {contact.get('name') or contact.get('email') or contact.get('phone')}" + (f" by {me.get('email')}" if me else " automatically at signup") + ".")
    return {"ok": bool(ok), "results": results, "onboarding": public_onboarding(rec)}


async def auto_invite(db, store_id: str, contact: dict):
    """Setup wizard hook: pre-fill the rep from the signup contact and send the form right away (settings.auto_invite)."""
    try:
        s = await settings(db)
        store = await db.stores.find_one({"_id": ObjectId(store_id)})
        if not store or (store.get("country") or "US") not in ("US", "USA"):
            return
        rec = ensure_tokens(store.get("compliance") or tc.defaults(store))
        rp = rec.setdefault("rep", {})
        parts = (contact.get("name") or "").strip().split(" ", 1)
        rp.setdefault("first_name", parts[0] if parts else "")
        if not rp.get("last_name") and len(parts) > 1:
            rp["last_name"] = parts[1]
        if not rp.get("email"):
            rp["email"] = contact.get("email") or ""
        if not rp.get("phone"):
            rp["phone"] = contact.get("phone") or ""
        if contact.get("zip") and not (rec.get("business") or {}).get("postal_code"):
            rec["business"]["postal_code"] = contact["zip"]
        rec["onboarding"]["contact"] = {"name": contact.get("name") or "", "email": contact.get("email") or "", "phone": contact.get("phone") or ""}
        await tc._save(db, store_id, rec)
        if s.get("auto_invite", True):
            store["compliance"] = rec
            await send_to_client(db, store, "invite")
    except Exception as e:
        logger.warning(f"[Compliance] auto invite for store {store_id} failed: {e}")


# ── the public form ───────────────────────────────────────────────────────────
async def store_by_token(db, token: str, kind: str = "onboarding") -> Optional[dict]:
    if not token or len(token) < 32:
        return None
    return await db.stores.find_one({f"compliance.{kind}.token": token})


def public_onboarding(rec: dict) -> dict:
    ob = dict(rec.get("onboarding") or {})
    ob["status"] = onboarding_status(rec)
    ob["status_label"] = ONBOARDING_STATUS_LABEL[ob["status"]]
    ob["url"] = form_url(rec)
    ob.pop("token", None)
    return ob


def client_view(store: dict, rec: dict) -> dict:
    """What the client sees on the public page: the record minus SIDs / history, EIN masked."""
    pub = tc.public(rec)
    return {"store": {"name": store.get("name"), "city": store.get("city"), "state": store.get("state")},
            "business": pub.get("business"), "rep": pub.get("rep"), "campaign": pub.get("campaign"), "cnam": pub.get("cnam"),
            "missing": tc.missing_fields(rec), "returned_at": (rec.get("onboarding") or {}).get("returned_at"), "submitted_to_twilio": (rec.get("stage") or "draft") != "draft",
            "sender_name": SENDER_NAME, "options": {"business_types": list(tc.BUSINESS_TYPES), "job_positions": list(tc.JOB_POSITIONS), "use_cases": tc.USE_CASES}}


async def client_opened(db, store: dict) -> dict:
    rec = store.get("compliance") or {}
    if rec.get("onboarding") and not rec["onboarding"].get("opened_at"):
        await db.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance.onboarding.opened_at": _now()}})
        rec["onboarding"]["opened_at"] = _now()
    return rec


async def client_save(db, store: dict, patch: dict, submit: bool = False) -> dict:
    """Client saved progress (or pressed Send). Edits are refused once the packet is in Twilio's hands."""
    rec = store.get("compliance") or tc.defaults(store)
    if (rec.get("stage") or "draft") != "draft" and rec.get("status") not in ("rejected", "error"):
        raise ValueError("This registration has already been submitted to the carriers. Contact us for changes.")
    before = copy.deepcopy(rec)
    rec = tc.merge_patch(rec, patch, store)
    ensure_tokens(rec)
    changed = any((before.get(b) or {}) != (rec.get(b) or {}) for b in ("business", "rep", "campaign", "cnam"))
    if changed and rec.get("preflight"):
        rec["preflight"]["stale"] = True
    if changed and (rec.get("review") or {}).get("status") == "reviewed":
        rec["review"] = {**rec["review"], "status": "returned"}
    now = _now()
    ob = rec["onboarding"]
    ob["last_saved_at"] = now
    if isinstance(patch.get("contact"), dict):
        ob["contact"] = {**(ob.get("contact") or {}), **{k: str(v or "").strip()[:160] for k, v in patch["contact"].items() if k in ("name", "email", "phone")}}
    missing = tc.missing_fields(rec)
    if submit:
        ob["returned_at"] = now
        ob["returned_missing"] = missing
        ob["returned_count"] = int(ob.get("returned_count") or 0) + 1
        rec["review"] = {**(rec.get("review") or {}), "status": "returned"}
        rec["history"] = tc._hist(rec, "draft", "form_returned", ("complete" if not missing else "missing: " + ", ".join(missing))[:400])
    await tc._save(db, str(store["_id"]), rec)
    if submit:
        title = f"{store.get('name')}: onboarding form returned" + ("" if not missing else f" ({len(missing)} gap{'s' if len(missing) != 1 else ''})")
        msg = "Everything required is in. Run pre-flight, review and submit." if not missing else "Still needed from the client: " + ", ".join(_pretty(m) for m in missing) + ". A reminder with that list goes out automatically."
        await notify_team(db, store, rec, "form_returned", title, msg)
    return rec


# ── reminders (scheduler) ─────────────────────────────────────────────────────
async def run_reminders(db) -> int:
    s = await settings(db)
    days = s["reminder_days"]
    n = 0
    now = _now()
    async for store in db.stores.find({"compliance.onboarding.first_sent_at": {"$exists": True}, "compliance.stage": {"$in": [None, "draft"]}, "compliance.onboarding.flagged_at": {"$exists": False}}):
        rec = store.get("compliance") or {}
        ob = rec.get("onboarding") or {}
        if ob.get("returned_at") and not ob.get("returned_missing"):
            continue
        if (rec.get("review") or {}).get("status") == "reviewed":
            continue
        first = ob.get("first_sent_at")
        if not isinstance(first, datetime):
            continue
        first = first if first.tzinfo else first.replace(tzinfo=timezone.utc)
        sent = int(ob.get("reminders_sent") or 0)
        if sent >= len(days):
            if not ob.get("flagged_at"):
                await db.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance.onboarding.flagged_at": now}})
                await notify_team(db, store, rec, "stalled", f"{store.get('name')}: no response after {sent} reminders", "The client has not returned the onboarding form. Time for a phone call.", priority="high")
            continue
        due = first + timedelta(days=days[sent])
        last = ob.get("last_sent_at")
        last = (last if last.tzinfo else last.replace(tzinfo=timezone.utc)) if isinstance(last, datetime) else first
        if now >= due and (now - last) >= timedelta(hours=20):
            try:
                kind = "missing" if ob.get("returned_missing") else "reminder"
                r = await send_to_client(db, store, kind)
                if kind == "missing":
                    await db.stores.update_one({"_id": store["_id"]}, {"$inc": {"compliance.onboarding.reminders_sent": 1}})
                n += 1
                fresh = await db.stores.find_one({"_id": store["_id"]}, {"compliance": 1, "name": 1})
                await notify_team(db, fresh, fresh.get("compliance") or {}, "reminder_sent", f"{store.get('name')}: reminder {sent + 1} of {len(days)} sent", "Sent by " + ", ".join(x["channel"] for x in r["results"] if x["ok"]) + ".", email=False)
            except Exception as e:
                logger.warning(f"[Compliance] reminder for {store.get('name')}: {e}")
    return n


# ── team notifications ────────────────────────────────────────────────────────
async def _team_user_ids(db) -> list[str]:
    return [str(u["_id"]) async for u in db.users.find({"role": "super_admin", "is_active": {"$ne": False}}, {"_id": 1})]


async def notify_team(db, store: dict, rec: dict, event: str, title: str, message: str, email: bool = True, priority: str = "normal"):
    """Every compliance event: in-app + push to super admins, email to the notify addresses, and a line on the store's event log."""
    title, message = no_em_dash(title), no_em_dash(message)
    link = f"/admin/compliance/{store['_id']}"
    now = _now()
    await db.stores.update_one({"_id": store["_id"]}, {"$push": {"compliance.events": {"$each": [{"at": now, "event": event, "title": title, "message": message}], "$slice": -60}}})
    try:
        from routers.notifications_center import invalidate_feed
        from routers.push_notifications import send_push_to_user
        for uid in await _team_user_ids(db):
            await db.notifications.insert_one({"user_id": uid, "type": "compliance", "event": event, "title": title, "message": message, "link": link, "priority": priority, "read": False, "dismissed": False, "created_at": now})
            invalidate_feed(uid)
            try:
                await send_push_to_user(uid, title, message, link, "shield-checkmark")
            except Exception as e:
                logger.debug(f"[Compliance] push failed for {uid}: {e}")
    except Exception as e:
        logger.warning(f"[Compliance] in-app notify failed: {e}")
    if email:
        s = await settings(db)
        url = f"{_app_url()}{link}"
        for to in s["notify_emails"]:
            await _email(to, title, _html(title, [message, f"Next action: {next_action({**store, 'compliance': rec})}"], ("Open in the app", url)), f"{message}\n\nNext action: {next_action({**store, 'compliance': rec})}\n\n{url}")


async def on_twilio_change(db, store_id: str, before: tuple, after: tuple, rec: dict):
    """Called by twilio_compliance.advance when stage/status moved."""
    store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"name": 1, "compliance": 1})
    if not store:
        return
    stage, status = after
    label = tc.STAGE_LABEL.get(stage, stage)
    if stage == "complete":
        title, msg, pr = f"{store.get('name')}: A2P registration APPROVED", "Brand and campaign are approved. Reps' numbers are attached; texting is fully registered.", "high"
    elif status in ("rejected", "error"):
        title, msg, pr = f"{store.get('name')}: Twilio {status} at {label}", (rec.get("error") or "No reason given.")[:400] + " Fix the form and press Fix & resubmit.", "high"
    elif before[0] != stage:
        title, msg, pr = f"{store.get('name')}: {tc.STAGE_LABEL.get(before[0], before[0])} approved", f"Moved on to {label}. We keep checking every 10 minutes.", "normal"
    else:
        title, msg, pr = f"{store.get('name')}: {label} {status}", f"Twilio status is now {status}.", "normal"
    await notify_team(db, store, rec, "twilio_status", title, msg, priority=pr)


# ── daily digest ──────────────────────────────────────────────────────────────
async def run_digest(db) -> bool:
    s = await settings(db)
    if not s.get("digest") or not s["notify_emails"]:
        return False
    local = _now().astimezone(ZoneInfo(DIGEST_TZ))
    today = local.strftime("%Y-%m-%d")
    if local.hour < s["digest_hour"] or s.get("last_digest_date") == today:
        return False
    rows = []
    async for st in db.stores.find({"country": {"$in": ["US", "USA", None, ""]}, "active": {"$ne": False}}, {"name": 1, "compliance": 1}).sort("name", 1):
        rec = st.get("compliance") or {}
        if (rec.get("stage") or "draft") == "complete":
            continue
        rows.append((st.get("name") or "Store", tc.STAGE_LABEL.get(rec.get("stage") or "draft", "Not started"), ONBOARDING_STATUS_LABEL[onboarding_status(rec)], next_action(st), f"{_app_url()}/admin/compliance/{st['_id']}"))
    await db.settings.update_one({"key": tc.SETTINGS_KEY}, {"$set": {"last_digest_date": today}, "$setOnInsert": {"key": tc.SETTINGS_KEY}}, upsert=True)
    if not rows:
        return False
    title = f"Texting compliance digest: {len(rows)} store{'s' if len(rows) != 1 else ''} not yet approved"
    lines = [f"<b><a href='{u}' style='color:#111'>{n}</a></b> · {stg} · {ob}<br><span style='color:#555'>{no_em_dash(act)}</span>" for n, stg, ob, act, u in rows]
    text = "\n\n".join(f"{n} | {stg} | {ob}\n{act}\n{u}" for n, stg, ob, act, u in rows)
    for to in s["notify_emails"]:
        await _email(to, title, _html(title, lines, ("Open Texting Compliance", f"{_app_url()}/admin/compliance")), text)
    return True


# ── numbers on cancel: release or port out ────────────────────────────────────
def account_number() -> str:
    return (os.environ.get("TWILIO_ACCOUNT_SID") or "")[-8:]


async def numbers_view(db, store: dict) -> dict:
    rec = store.get("compliance") or tc.defaults(store)
    if not (rec.get("portout") or {}).get("token"):
        ensure_tokens(rec)
        await tc._save(db, str(store["_id"]), rec)
    plan = rec.get("numbers_plan") or {}
    nums = await tc.store_numbers(db, str(store["_id"]))
    seen = {n["sid"] for n in nums}
    for sid, p in plan.items():
        if sid not in seen and p.get("number"):
            nums.append({"sid": sid, "number": p["number"], "owner": p.get("owner") or "", "gone": True})
    out = []
    for n in nums:
        p = plan.get(n["sid"]) or {}
        out.append({**n, "status": p.get("status") or "active", "at": p.get("at"), "note": p.get("note"), "by": p.get("by")})
    return {"numbers": out, "account_number": account_number(), "portout_url": portout_url(rec), "portout": {k: v for k, v in (rec.get("portout") or {}).items() if k != "token"}}


async def _effective_mode(db, rec: dict) -> str:
    return rec.get("mode") or (await tc.get_settings(db))["mode"]


async def set_number_status(db, store: dict, sid: str, status: str, me: dict, note: str = "") -> dict:
    if status not in ("active", "port_requested", "ported", "released"):
        raise ValueError("status must be active, port_requested, ported or released")
    rec = ensure_tokens(store.get("compliance") or tc.defaults(store))
    nums = {n["sid"]: n for n in await tc.store_numbers(db, str(store["_id"]))}
    cur = (rec.get("numbers_plan") or {}).get(sid) or {}
    n = nums.get(sid) or {"number": cur.get("number"), "owner": cur.get("owner")}
    rec.setdefault("numbers_plan", {})[sid] = {"status": status, "at": _now(), "by": me.get("email"), "note": note[:300], "number": n.get("number"), "owner": n.get("owner")}
    if status == "ported" and await _effective_mode(db, rec) != "dry_run":
        await _detach_number(rec, sid)
    rec["history"] = tc._hist(rec, rec.get("stage") or "draft", f"number_{status}", f"{n.get('number')} {note}".strip())
    await tc._save(db, str(store["_id"]), rec)
    return rec


async def _detach_number(rec: dict, sid: str):
    """After a port completes: pull the number off the messaging service so the campaign stays clean."""
    ms = (rec.get("sids") or {}).get("messaging_service")
    if not ms or not os.environ.get("TWILIO_ACCOUNT_SID"):
        return
    try:
        from twilio.rest import Client
        c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        await asyncio.to_thread(c.messaging.v1.services(ms).phone_numbers(sid).delete)
    except Exception as e:
        logger.info(f"[Compliance] detach {sid} from {ms}: {e}")


async def release_number(db, store: dict, sid: str, me: dict) -> dict:
    """Permanently give the number back to Twilio (stops billing) and clear the rep. Uses the same path as Phone Numbers admin."""
    rec = ensure_tokens(store.get("compliance") or tc.defaults(store))
    nums = {n["sid"]: n for n in await tc.store_numbers(db, str(store["_id"]))}
    n = nums.get(sid)
    if not n:
        raise ValueError("That number is not on this store any more")
    if os.environ.get("TWILIO_ACCOUNT_SID") and await _effective_mode(db, rec) != "dry_run":
        from routers.twilio_admin import release_number as _release
        await _release(sid)
    else:
        await db.users.update_many({"twilio_number_sid": sid}, {"$unset": {"mvpline_number": "", "twilio_number": "", "twilio_number_sid": ""}})
    rec.setdefault("numbers_plan", {})[sid] = {"status": "released", "at": _now(), "by": me.get("email"), "number": n.get("number"), "owner": n.get("owner")}
    rec["history"] = tc._hist(rec, rec.get("stage") or "draft", "number_released", f"{n.get('number')} ({n.get('owner') or 'pool'}) by {me.get('email')}")
    await tc._save(db, str(store["_id"]), rec)
    await notify_team(db, store, rec, "number_released", f"{store.get('name')}: {n.get('number')} released", f"Released from Twilio by {me.get('email')}. Billing stopped; the rep's number field was cleared.", email=False)
    return rec


def portout_packet(store: dict, rec: dict, s: dict, numbers: list[dict]) -> dict:
    b = rec.get("business") or {}
    return {
        "store": {"name": store.get("name")},
        "numbers": [{"number": n.get("number"), "owner": n.get("owner") or "", "status": n.get("status") or "active"} for n in numbers if (n.get("status") or "active") != "released"],
        "account_number": account_number(),
        "pin": s.get("portout_pin") or "",
        "authorized_name": "Twilio, Inc.",
        "service_address": s.get("portout_service_address") or "",
        "business": {"legal_name": b.get("legal_name"), "street": b.get("street"), "city": b.get("city"), "state": b.get("state"), "postal_code": b.get("postal_code")},
        "help_url": PORT_OUT_HELP,
        "contact_email": os.environ.get("REPORT_REPLY_TO", "support@imonsocial.com"),
        "sender_name": SENDER_NAME,
        "steps": [
            "Do not cancel or release these numbers with us until the port has completed. A released number cannot be ported.",
            "Pick your new carrier and ask them to port the numbers in. They will have you sign a Letter of Authorization (LOA).",
            "On the LOA use the account number, PIN, authorized name and service address on this page exactly as written. Twilio, Inc. is the owner of record for the numbers.",
            "Tell us the date you submitted the port. We disable emergency (E911) settings and approve the port-away request in Twilio as soon as their notice arrives; slow approvals are the usual reason ports get rejected.",
            "When the port completes we remove the numbers from your A2P campaign. Your new carrier must register their own brand and campaign before you can text from the numbers again.",
            "If a port is rejected, send us the carrier's rejection reason and we will sort it out with Twilio porting.",
        ],
    }


async def send_portout(db, store: dict, me: dict, to_email: str = "", to_phone: str = "", channel: str = "both") -> dict:
    rec = ensure_tokens(store.get("compliance") or tc.defaults(store))
    contact = _contact(rec, store)
    if to_email:
        contact["email"] = to_email.strip().lower()
    if to_phone:
        contact["phone"] = to_phone.strip()
    url = portout_url(rec)
    name = store.get("name") or "your store"
    first = ((contact.get("name") or "").split(" ") or [""])[0] or "there"
    lines = [f"Hi {first},", f"Here is everything your new carrier needs to move {name}'s phone numbers, plus the steps on our side. Please do not cancel the numbers until the port completes.", "Reply to this email with the date you submit the port so we can approve it quickly in Twilio."]
    sms = f"Hi {first}, {SENDER_NAME} at I'm On Social. Your number port-out packet for {name} (account number, PIN, steps) is here: {url}. Keep the numbers active until the port completes."
    results, now = [], _now()
    if channel in ("both", "text") and contact.get("phone"):
        results.append({"at": now, "channel": "text", "to": contact["phone"], **(await _sms(contact["phone"], sms))})
    if channel in ("both", "email") and contact.get("email"):
        results.append({"at": now, "channel": "email", "to": contact["email"], **(await _email(contact["email"], f"{name}: your phone number port-out packet", _html(f"{name}: port-out packet", lines, ("Open the port-out packet", url)), "\n\n".join(lines) + f"\n\n{url}"))})
    if not results:
        raise ValueError("No email or cell number for the client. Add one first.")
    rec["portout"]["sent"] = (rec["portout"].get("sent") or [])[-20:] + results
    rec["portout"]["last_sent_at"] = now
    rec["history"] = tc._hist(rec, rec.get("stage") or "draft", "portout_sent", ", ".join(f"{r['channel']} {'ok' if r['ok'] else 'failed'}" for r in results) + f" by {me.get('email')}")
    await tc._save(db, str(store["_id"]), rec)
    await notify_team(db, store, rec, "portout_sent", f"{store.get('name')}: port-out packet sent", f"Sent by {', '.join(r['channel'] for r in results if r['ok']) or 'nothing (failed)'} by {me.get('email')}. Watch for Twilio's port-away notice and approve it in Console.", email=False)
    return {"ok": any(r["ok"] for r in results), "results": results}
