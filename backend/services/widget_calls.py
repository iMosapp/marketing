"""Call me now: ring every rep in the widget's group at once, first to press 1 gets the visitor dialed and bridged.
Closed store or nobody available -> the visitor is texted (after-hours path of the intake pipeline) and a callback task is created."""
import asyncio
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Optional
from xml.sax.saxutils import escape as _x

from bson import ObjectId

from services import widgets as W

logger = logging.getLogger(__name__)

COLL = "widget_call_requests"
GRACE_S = 20


def _now():
    return datetime.now(timezone.utc)


def _fmt_phone(p: str) -> str:
    d = "".join(c for c in (p or "") if c.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (p or "")


class _DryCalls:
    """WIDGET_RING_DRY_RUN=true (preview): no phone rings, legs get fake SIDs and just time out."""

    def create(self, **kw):
        logger.info(f"[WidgetCall] DRY RUN ring {kw.get('to')} from {kw.get('from_')}")
        return type("C", (), {"sid": "CAdry" + secrets.token_hex(14)})()

    def __call__(self, sid):
        return type("U", (), {"update": staticmethod(lambda **kw: None)})()


class _DryClient:
    calls = _DryCalls()


def _twilio():
    if os.environ.get("WIDGET_RING_DRY_RUN", "").lower() == "true":
        return _DryClient()
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    if not (sid and tok):
        return None
    from twilio.rest import Client
    return Client(sid, tok)


def _hydrate(t: str, first: str, store: str, rep: str = "") -> str:
    return (t or "").replace("{{first_name}}", first).replace("{first_name}", first).replace("{{store_name}}", store).replace("{store_name}", store).replace("{{rep_name}}", rep).replace("{rep_name}", rep)


async def available_reps(db, w: dict) -> list:
    """Group members with a personal phone, on shift first; everyone with a phone when nobody has a schedule saying otherwise."""
    ids = [ObjectId(u) for u in W.normalize_config(w)["routing"]["call_user_ids"] if ObjectId.is_valid(u)]
    if not ids:
        return []
    users = await db.users.find({"_id": {"$in": ids}, "status": {"$ne": "deactivated"}, "is_active": {"$ne": False}}, {"name": 1, "first_name": 1, "phone": 1, "twilio_number": 1, "mvpline_number": 1}).to_list(50)
    users = [u for u in users if (u.get("phone") or "").strip()]
    try:
        from routers.user_schedule import is_user_available
        on = [u for u in users if await is_user_available(str(u["_id"]))]
    except Exception:
        on = users
    return on or users


async def from_number(db, w: dict, reps: list) -> str:
    r = W.normalize_config(w)["routing"]
    if r.get("inbox_id") and ObjectId.is_valid(r["inbox_id"]):
        inbox = await db.shared_inboxes.find_one({"_id": ObjectId(r["inbox_id"])}, {"phone_number": 1})
        if inbox and inbox.get("phone_number"):
            return W.clean_phone(inbox["phone_number"]) or inbox["phone_number"]
    for u in reps:
        n = u.get("twilio_number") or u.get("mvpline_number")
        if n:
            return n
    return os.environ.get("TWILIO_PHONE_NUMBER", "")


def _first(u: dict) -> str:
    return (u.get("first_name") or (u.get("name") or "a team member").split()[0])


async def request_call(db, w: dict, body: dict, ip: str) -> dict:
    name, phone = (body.get("name") or "").strip()[:80], W.clean_phone(body.get("phone") or "")
    if body.get("website"):
        return {"status": "ringing", "request_id": "hp"}
    if not name or not phone:
        raise ValueError("Please add your name and a 10 digit mobile number.")
    if not W.allow(ip, "call", 3) or not W.allow(phone, "call_phone", 2, 300):
        raise ValueError("We already have a call going for this number. Give it a minute.")
    store = await W.store_of(db, w)
    cfg = W.normalize_config(w)
    source = await db.lead_sources.find_one({"_id": ObjectId(w["lead_source_id"])}) if w.get("lead_source_id") else None
    if not source:
        w["lead_source_id"] = await W.sync_lead_source(db, w, store)
        await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"lead_source_id": w["lead_source_id"]}})
        source = await db.lead_sources.find_one({"_id": ObjectId(w["lead_source_id"])})
    first, last = W.split_name(name)
    page = (body.get("page") or "")[:500]
    store_name = store.get("name") or "our team"

    from services.lead_timing import store_hours_status
    hours = store_hours_status(store) if cfg["hours"]["mode"] == "store" else {"open": True, "opens_at": None}
    reps = await available_reps(db, w) if hours.get("open", True) else []
    ringing = bool(reps) and _twilio() is not None

    normalized = {
        "first_name": first, "last_name": last, "full_name": name, "phone": phone,
        "comments": f"Asked for a call {'right now' if ringing else 'back'} from the website{f' ({W.host_of(page)})' if page else ''}" + ("" if ringing else " (nobody available / after hours)"),
        "source_name": source.get("name"),
        "extra_fields": {"widget_key": w["key"], "door": "call", "page_url": page, "page_title": (body.get("title") or "")[:200], "visitor": (body.get("visitor") or "")[:64]},
    }
    src = dict(source)
    if ringing:
        src["intake_text"] = _hydrate(cfg["routing"]["call_intake_text"], first, store_name)
        src["call_attempts"] = []   # the ring group IS the ladder for this one
    from routers.lead_intake import process_inbound_lead
    res = await process_inbound_lead(normalized, src, db, raw_body="")
    await W.log_event(db, w, "lead", {**body, "door": "call"})
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.call_requests": 1}})

    req = {
        "widget_id": str(w["_id"]), "key": w["key"], "store_id": w.get("store_id"), "name": name, "first": first, "phone": phone, "page": page,
        "contact_id": res.get("contact_id"), "conversation_id": res.get("conversation_id"), "lead_id": res.get("lead_id"),
        "status": "ringing" if ringing else ("after_hours" if not hours.get("open", True) else "missed"),
        "legs": [], "winner_user_id": None, "winner_first": None, "from_number": "", "ring_seconds": cfg["routing"]["ring_seconds"],
        "created_at": _now(), "updated_at": _now(),
    }
    ins = await db[COLL].insert_one(req)
    req["_id"] = ins.inserted_id
    if not ringing:
        if hours.get("open", True):
            # open but nobody can take it: the intake text already went out; make sure someone calls back
            await _missed(db, req, w, reason="nobody_available", text=False)
        opens = hours.get("opens_at")
        if opens:
            from zoneinfo import ZoneInfo
            try:
                opens = opens.astimezone(ZoneInfo(hours.get("tz") or "UTC"))
            except Exception:
                pass
        return {"status": req["status"], "request_id": str(req["_id"]), "from_display": "",
                "opens_at_display": opens.strftime("%-I:%M %p") if opens else "",
                "message": cfg["doors"]["call"]["after_hours"] if req["status"] == "after_hours" else cfg["doors"]["call"]["missed"]}

    frm = await from_number(db, w, reps)
    await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"from_number": frm}})
    req["from_number"] = frm
    await _ring(db, req, reps, cfg["routing"]["ring_seconds"], W.host_of(page))
    asyncio.create_task(_watchdog(str(req["_id"]), cfg["routing"]["ring_seconds"] + GRACE_S))
    return {"status": "ringing", "request_id": str(req["_id"]), "from_display": _fmt_phone(frm), "message": cfg["doors"]["call"]["success_ringing"]}


async def _ring(db, req: dict, reps: list, ring_seconds: int, host: str):
    client = _twilio()
    base = W.app_url()
    legs = []
    for u in reps:
        tok = secrets.token_hex(6)
        to = W.clean_phone(u["phone"]) or u["phone"]
        leg = {"user_id": str(u["_id"]), "first": _first(u), "to": to, "token": tok, "status": "queued", "call_sid": None}
        try:
            call = await asyncio.to_thread(
                client.calls.create, to=to, from_=req["from_number"],
                url=f"{base}/api/w/ring/{req['_id']}/{tok}", method="POST", timeout=ring_seconds,
                status_callback=f"{base}/api/w/ring-status/{req['_id']}/{tok}", status_callback_method="POST",
                status_callback_event=["completed"])
            leg.update({"call_sid": call.sid, "status": "ringing"})
        except Exception as e:
            leg.update({"status": "failed", "error": str(e)[:200]})
            logger.warning(f"[WidgetCall] leg to {u.get('name')} failed: {e}")
        legs.append(leg)
    await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"legs": legs, "updated_at": _now()}})
    logger.info(f"[WidgetCall] {req['_id']} ringing {len([l for l in legs if l['status'] == 'ringing'])} reps for {req['name']} ({host})")
    if not any(l["status"] == "ringing" for l in legs):
        await _missed(db, req, await db[W.COLL].find_one({"_id": ObjectId(req["widget_id"])}), reason="all_legs_failed")


def _leg(req: dict, token: str) -> Optional[dict]:
    return next((l for l in req.get("legs") or [] if l.get("token") == token), None)


async def ring_twiml(db, req_id: str, token: str) -> str:
    req = await db[COLL].find_one({"_id": ObjectId(req_id)}) if ObjectId.is_valid(req_id) else None
    leg = _leg(req, token) if req else None
    if not req or not leg:
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'
    if req.get("winner_user_id"):
        who = req.get("winner_first") or "Someone"
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>{_x(who)} already took this one. Thanks!</Say><Hangup/></Response>'
    where = W.host_of(req.get("page") or "") or "the website"
    base = W.app_url()
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather numDigits="1" timeout="8" action="{base}/api/w/ring-answer/{req_id}/{token}" method="POST">'
            f'<Say>Website lead. {_x(req["name"])} is on {_x(where)} and wants a call right now. Press 1 to take it.</Say>'
            f'<Pause length="2"/><Say>Press 1 to take {_x(req["first"])}.</Say></Gather>'
            f'<Say>Releasing it to the team.</Say><Hangup/></Response>')


async def answer_twiml(db, req_id: str, token: str, digits: str) -> str:
    req = await db[COLL].find_one({"_id": ObjectId(req_id)}) if ObjectId.is_valid(req_id) else None
    leg = _leg(req, token) if req else None
    if not req or not leg:
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'
    if digits != "1":
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Okay, releasing it to the team.</Say><Hangup/></Response>'
    won = await db[COLL].find_one_and_update(
        {"_id": req["_id"], "winner_user_id": None, "status": "ringing"},
        {"$set": {"winner_user_id": leg["user_id"], "winner_first": leg["first"], "winner_token": token, "status": "connecting", "won_at": _now(), "updated_at": _now()}})
    if not won:
        fresh = await db[COLL].find_one({"_id": req["_id"]})
        who = (fresh or {}).get("winner_first") or "Someone"
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>{_x(who)} already grabbed it. Thanks!</Say><Hangup/></Response>'
    asyncio.create_task(_cancel_others(req, token))
    # a pending_calls doc so the existing recording -> transcript -> call_logs -> follow-up pipeline treats this like click-to-call
    pending = {
        "customer_phone": req["phone"], "rep_twilio_number": req["from_number"], "rep_name": leg["first"], "rep_user_id": leg["user_id"],
        "contact_id": req.get("contact_id") or "", "conversation_id": req.get("conversation_id") or "", "task_id": "",
        "token": secrets.token_hex(12), "call_sid": leg.get("call_sid"), "widget_request_id": str(req["_id"]), "source": "website_widget",
        "created_at": _now(), "host": {"transport": "widget_ring", "decision": "go", "via": "dtmf"},
    }
    await db.pending_calls.insert_one(pending)
    await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"pending_call_id": str(pending.get("_id"))}})
    from routers.twilio_webhooks import _dial_customer_twiml
    twiml = _dial_customer_twiml(pending, say=f"Connecting you to {req['first']} now.")
    # know the moment the visitor picks up
    twiml = twiml.replace("<Number>", f'<Number statusCallback="{W.app_url()}/api/w/ring-customer/{req["_id"]}" statusCallbackEvent="answered completed" statusCallbackMethod="POST">')
    logger.info(f"[WidgetCall] {req['_id']} won by {leg['first']}, dialing {req['phone']}")
    return twiml


async def _cancel_others(req: dict, winner_token: str):
    client = _twilio()
    if not client:
        return
    for l in req.get("legs") or []:
        if l.get("token") != winner_token and l.get("call_sid") and l.get("status") == "ringing":
            try:
                await asyncio.to_thread(client.calls(l["call_sid"]).update, status="completed")
            except Exception as e:
                logger.debug(f"[WidgetCall] cancel leg {l.get('first')}: {e}")


async def leg_status(db, req_id: str, token: str, call_status: str):
    req = await db[COLL].find_one({"_id": ObjectId(req_id)}) if ObjectId.is_valid(req_id) else None
    if not req:
        return
    legs = req.get("legs") or []
    for l in legs:
        if l.get("token") == token and l.get("status") == "ringing":
            l["status"] = call_status or "completed"
    await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"legs": legs, "updated_at": _now()}})
    if req.get("status") == "ringing" and not any(l.get("status") == "ringing" for l in legs):
        await _missed(db, {**req, "legs": legs}, await db[W.COLL].find_one({"_id": ObjectId(req["widget_id"])}), reason="no_rep_answered")


async def customer_status(db, req_id: str, call_status: str, duration: str = "0"):
    req = await db[COLL].find_one({"_id": ObjectId(req_id)}) if ObjectId.is_valid(req_id) else None
    if not req:
        return
    if call_status in ("in-progress", "answered") and req.get("status") == "connecting":
        created = req["created_at"] if req["created_at"].tzinfo else req["created_at"].replace(tzinfo=timezone.utc)
        secs = int((_now() - created).total_seconds())
        await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"status": "connected", "connected_at": _now(), "seconds_to_connect": secs, "updated_at": _now()}})
        await db[W.COLL].update_one({"_id": ObjectId(req["widget_id"])}, {"$inc": {"stats.calls_connected": 1}})
        logger.info(f"[WidgetCall] {req['_id']} connected in {secs}s")
    elif call_status in ("no-answer", "busy", "failed", "canceled") and req.get("status") == "connecting":
        await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"status": "missed_customer", "updated_at": _now()}})
    elif call_status == "completed" and req.get("status") == "connecting":
        await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"status": "connected" if int(duration or 0) > 5 else "missed_customer", "updated_at": _now()}})


async def _missed(db, req: dict, w: Optional[dict], reason: str, text: bool = True):
    fresh = await db[COLL].find_one({"_id": req["_id"]})
    if not fresh or fresh.get("status") not in ("ringing", "missed"):
        return
    await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"status": "missed", "missed_reason": reason, "updated_at": _now()}})
    store = await W.store_of(db, w) if w else {}
    store_name = store.get("name") or "our team"
    cfg = W.normalize_config(w or {})
    if text and req.get("phone") and req.get("from_number"):
        try:
            from services.twilio_service import send_sms
            await send_sms(req["phone"], _hydrate(cfg["routing"]["missed_text"], req["first"], store_name), from_phone=req["from_number"], contact_id=req.get("contact_id"))
        except Exception as e:
            logger.warning(f"[WidgetCall] missed text failed: {e}")
    # somebody owns the callback: the lead's assignee, else the first group member
    lead = await db.inbound_leads.find_one({"_id": ObjectId(req["lead_id"])}) if req.get("lead_id") and ObjectId.is_valid(str(req["lead_id"])) else None
    owner = (lead or {}).get("assigned_to") or next(iter(cfg["routing"]["call_user_ids"]), None)
    if owner and req.get("contact_id"):
        await db.tasks.insert_one({
            "user_id": owner, "contact_id": req["contact_id"], "contact_name": req["name"], "contact_phone": req["phone"],
            "type": "call", "source": "website_widget", "auto_kind": "widget_callback", "title": f"Call {req['first']} back (asked from the website)",
            "description": f"{req['name']} asked for a call from {W.host_of(req.get('page') or '') or 'the website'} and nobody could take it ({reason.replace('_', ' ')}). They were texted.",
            "suggested_message": "", "action_type": "call", "priority": "high", "priority_order": 1, "status": "pending", "completed": False,
            "due_date": _now(), "has_time": True, "appointment_type": "call", "reminded_15": False, "reminded_due": False, "completed_at": None,
            "snoozed_until": None, "campaign_id": None, "campaign_name": None, "pending_send_id": None, "channel": "", "conversation_id": req.get("conversation_id"), "created_at": _now(),
        })
    try:
        from routers.push_notifications import send_push_to_user
        for uid in set(cfg["routing"]["call_user_ids"]):
            asyncio.create_task(send_push_to_user(uid, f"Missed website call: {req['name']}", f"Nobody grabbed it. They were texted. Call {req['first']} back at {_fmt_phone(req['phone'])}.", f"/thread/{req.get('conversation_id')}" if req.get("conversation_id") else "/leads", "call"))
    except Exception as e:
        logger.debug(f"[WidgetCall] missed push: {e}")
    logger.info(f"[WidgetCall] {req['_id']} missed ({reason})")


async def _watchdog(req_id: str, seconds: int):
    await asyncio.sleep(seconds)
    from routers.database import get_db
    db = get_db()
    req = await db[COLL].find_one({"_id": ObjectId(req_id)})
    if req and req.get("status") == "ringing":
        await _missed(db, req, await db[W.COLL].find_one({"_id": ObjectId(req["widget_id"])}), reason="timeout")


async def visitor_status(db, key: str, req_id: str) -> dict:
    req = await db[COLL].find_one({"_id": ObjectId(req_id), "key": key}) if ObjectId.is_valid(req_id) else None
    if not req:
        return {"status": "unknown"}
    w = await db[W.COLL].find_one({"_id": ObjectId(req["widget_id"])})
    cfg = W.normalize_config(w or {})
    st = req.get("status")
    msg = cfg["doors"]["call"]["missed"] if st in ("missed", "missed_customer") else cfg["doors"]["call"]["after_hours"] if st == "after_hours" else ""
    return {"status": st, "rep_first": req.get("winner_first"), "from_display": _fmt_phone(req.get("from_number") or ""), "message": msg}
