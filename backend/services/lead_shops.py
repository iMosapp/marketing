"""Lead Shops: a mystery shop that arrives at the store as a real internet lead.

We push an ADF/XML lead (or hand the admin an identity card to submit the store's web form) with a persona that is fully
reachable: a dedicated Twilio number from our pool and its own email address. Whatever the store does next lands here:
a call is answered by the AI shopper in that persona (ConversationRelay), a text or email gets the AI's reply, and every
touch is stamped on a timeline. When the window closes we grade the store's whole response against the process it promised
(first response per channel, day-one effort, channels used, persistence) plus the quality of every conversation."""
import asyncio
import logging
import os
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from xml.sax.saxutils import escape

from bson import ObjectId

logger = logging.getLogger(__name__)

COLL = "lead_shops"
POOL = "phone_number_pool"
POOL_PURPOSE = "lead_shop"
POOL_CAP = 10
COOLDOWN_DAYS = 14
WINDOWS = {24: "24 hours", 72: "3 days", 168: "7 days"}
DEFAULT_PROCESS = {"first_call_min": 5, "first_text_min": 5, "first_email_min": 15, "channels": ["call", "text", "email"], "day1_calls": 3, "follow_up_days": 3,
                   "must": ["Answer the question the lead asked", "Offer a specific appointment time", "Give their name and the store name", "Confirm what the lead asked about is available"]}
AUTO_REPLY_S = 90
CHANNEL_LABEL = {"call": "Call", "text": "Text", "email": "Email", "lead": "Lead"}


def _now():
    return datetime.now(timezone.utc)


def _utc(dt):
    if not dt:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if v and ObjectId.is_valid(str(v)) else None


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _app_url() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def inbound_domain() -> str:
    return (os.environ.get("INBOUND_EMAIL_DOMAIN") or "").strip().lower()


def clean_process(raw: Optional[dict]) -> dict:
    raw = raw or {}
    out = dict(DEFAULT_PROCESS)
    for k in ("first_call_min", "first_text_min", "first_email_min", "day1_calls", "follow_up_days"):
        if k in raw:
            try:
                out[k] = max(0 if k.startswith("first") else 1, min(int(raw[k]), 24 * 60 if k.startswith("first") else 14))
            except (TypeError, ValueError):
                pass
    if isinstance(raw.get("channels"), list):
        out["channels"] = [c for c in ("call", "text", "email") if c in raw["channels"]] or ["call"]
    if isinstance(raw.get("must"), list):
        out["must"] = [str(m).strip()[:120] for m in raw["must"] if str(m).strip()][:8]
    return out


# ── phone number pool ─────────────────────────────────────────────────────────
async def pool_state(db) -> dict:
    rows = await db[POOL].find({"purpose": POOL_PURPOSE}).sort("purchased_at", 1).to_list(50)
    now = _now()
    out = []
    for r in rows:
        cd = _utc(r.get("cooldown_until"))
        out.append({"phone": r["phone_number"], "status": r.get("status"), "lead_shop_id": r.get("lead_shop_id"), "cooling": bool(cd and cd > now), "cooldown_until": _iso(cd),
                    "purchased_at": _iso(r.get("purchased_at")), "monthly_cost_usd": r.get("monthly_cost_usd")})
    return {"numbers": out, "available": sum(1 for r in out if r["status"] == "available" and not r["cooling"]), "in_use": sum(1 for r in out if r["status"] == "in_use"), "cap": POOL_CAP, "total": len(out)}


async def buy_number(db, me: Optional[dict], area_code: Optional[str] = None) -> dict:
    from routers.twilio_admin import _get_twilio_client, _twilio_call, NUMBER_MONTHLY_COST
    if (os.environ.get("LEAD_SHOP_BUY_NUMBERS") or "true").strip().lower() in ("0", "false", "no", "off"):
        raise ValueError("Buying shopper numbers is switched off in this environment (LEAD_SHOP_BUY_NUMBERS)")
    if await db[POOL].count_documents({"purpose": POOL_PURPOSE}) >= POOL_CAP:
        raise ValueError(f"The shopper number pool is at its cap of {POOL_CAP}")
    client = _get_twilio_client()
    params = {"limit": 5, "voice_enabled": True, "sms_enabled": True}
    ac = "".join(ch for ch in (area_code or "") if ch.isdigit())[:3]
    if len(ac) == 3:
        params["area_code"] = ac
    found = await _twilio_call(lambda: client.available_phone_numbers("US").local.list(**params))
    if not found and ac:
        found = await _twilio_call(lambda: client.available_phone_numbers("US").local.list(limit=5, voice_enabled=True, sms_enabled=True))
    if not found:
        raise ValueError("Twilio has no numbers to sell right now")
    base = _app_url()
    bought = await _twilio_call(client.incoming_phone_numbers.create, phone_number=found[0].phone_number, friendly_name="Lead shopper", voice_url=f"{base}/api/webhooks/twilio/voice", voice_method="POST",
                                sms_url=f"{base}/api/webhooks/twilio/incoming", sms_method="POST", timeout=30)
    ms_sid = os.environ.get("TWILIO_MESSAGING_SERVICE_SID")
    if ms_sid:
        try:
            await _twilio_call(client.messaging.v1.services(ms_sid).phone_numbers.create, phone_number_sid=bought.sid)
        except Exception as e:
            logger.warning(f"[LeadShop] could not add {bought.phone_number} to the messaging service: {e}")
    doc = {"phone_number": bought.phone_number, "twilio_sid": bought.sid, "status": "available", "assigned_user_id": None, "purpose": POOL_PURPOSE, "lead_shop_id": None, "cooldown_until": None,
           "monthly_cost_usd": NUMBER_MONTHLY_COST, "purchased_at": _now(), "purchased_by": str(me["_id"]) if me else None}
    await db[POOL].insert_one(doc)
    logger.info(f"[LeadShop] bought shopper number {bought.phone_number}")
    return doc


async def acquire_number(db, client: dict, me: Optional[dict]) -> dict:
    now = _now()
    row = await db[POOL].find_one_and_update({"purpose": POOL_PURPOSE, "status": "available", "$or": [{"cooldown_until": None}, {"cooldown_until": {"$lte": now}}]},
                                             {"$set": {"status": "in_use", "assigned_at": now}}, sort=[("cooldown_until", 1)])
    if row:
        return row
    ac = re.sub(r"\D", "", client.get("contact_phone") or "")
    ac = ac[1:4] if len(ac) == 11 and ac.startswith("1") else ac[:3]
    bought = await buy_number(db, me, ac)
    await db[POOL].update_one({"_id": bought["_id"]}, {"$set": {"status": "in_use", "assigned_at": now}})
    return bought


async def release_number(db, shop: dict):
    await db[POOL].update_one({"purpose": POOL_PURPOSE, "lead_shop_id": str(shop["_id"])},
                              {"$set": {"status": "available", "cooldown_until": _now() + timedelta(days=COOLDOWN_DAYS), "last_lead_shop_id": str(shop["_id"]), "lead_shop_id": None}})


async def number_owner(db, phone: str) -> tuple:
    """(live lead shop, pool row) for a called/texted number; (None, row) when the number is ours but cooling down."""
    row = await db[POOL].find_one({"purpose": POOL_PURPOSE, "phone_number": phone})
    if not row:
        return None, None
    if row.get("status") == "in_use" and row.get("lead_shop_id"):
        shop = await db[COLL].find_one({"_id": _oid(row["lead_shop_id"]), "status": {"$in": ["pending_delivery", "live", "closing"]}})
        if shop:
            return shop, row
    return None, row


# ── persona + lead ────────────────────────────────────────────────────────────
def _email_for(persona: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", ".", (persona.get("name") or "lead").lower()).strip(".") or "lead"
    return f"{slug}.{random.randint(10, 99)}@{inbound_domain()}"


async def build_persona(db, client: dict, department: str, offering: Optional[str] = None, script: Optional[dict] = None) -> tuple:
    from services import mystery_shops as ms
    from services import locales as loc
    script = script or await ms.pick_challenge(db, client, {"department": department, "challenge_history": []})
    if not script:
        raise ValueError("No challenge in the library for that department yet")
    persona = ms.fill_persona(script.get("persona") or {}, client, department)
    if offering:
        persona["offering"] = offering
        persona["vehicle"] = offering
    name = (persona.get("name") or "Sam Rivera").strip()
    parts = name.split(" ", 1)
    persona["first"], persona["last"] = parts[0], (parts[1] if len(parts) > 1 else random.choice(["Rivera", "Bennett", "Okafor", "Lindqvist", "Marsh", "Patel"]))
    persona["name"] = f"{persona['first']} {persona['last']}"
    persona["email"] = _email_for(persona)
    nl = loc.language(loc.key_of(client)) == "nl"
    persona["opening_line"] = "Hallo?" if nl else random.choice(["Hello?", f"Hi, this is {persona['first']}.", "Hello, who's this?"])
    what = persona.get("offering") or persona.get("vehicle") or "what they have listed"
    ctx = (f" Je hebt online een aanvraag gedaan bij {client.get('name')} over {what} en dit nummer en e-mailadres achtergelaten; wie contact opneemt reageert op die aanvraag. Je hebt nog met niemand gesproken."
           if nl else f" You sent {client.get('name')} an online inquiry about {what} and left this phone number and email; anyone reaching out is following up on that inquiry. You have not spoken to anyone there yet.")
    persona["summary"] = (persona.get("summary") or "") + ctx
    return persona, script


def adf_xml(shop: dict, client: dict) -> str:
    p = shop["persona"]
    now = _utc(shop.get("created_at")) or _now()
    veh = (p.get("vehicle") or p.get("offering") or "").strip()
    year = re.search(r"\b(19|20)\d{2}\b", veh)
    words = [w for w in re.sub(r"\b(19|20)\d{2}\b", "", veh).replace("the ", "").replace("a ", "").split() if w]
    make, model = (words[0], " ".join(words[1:])) if words else ("", "")
    comments = escape(p.get("goals") or p.get("summary") or f"Interested in {veh}")
    vehicle = (f"<vehicle interest=\"buy\" status=\"used\">{f'<year>{year.group(0)}</year>' if year else ''}{f'<make>{escape(make)}</make>' if make else ''}{f'<model>{escape(model)}</model>' if model else ''}</vehicle>"
               if client.get("industry", "automotive") in (None, "automotive") and veh else "")
    return ("<?xml version=\"1.0\"?><?adf version=\"1.0\"?>\n<adf>\n <prospect status=\"new\">\n"
            f"  <id sequence=\"1\" source=\"{escape(shop.get('source_name') or 'Website')}\">{str(shop['_id'])[-8:]}</id>\n"
            f"  <requestdate>{now.strftime('%Y-%m-%dT%H:%M:%S%z')[:-2] + ':' + now.strftime('%z')[-2:]}</requestdate>\n"
            f"  {vehicle}\n"
            "  <customer>\n   <contact>\n"
            f"    <name part=\"first\">{escape(p['first'])}</name>\n    <name part=\"last\">{escape(p['last'])}</name>\n"
            f"    <email>{escape(p['email'])}</email>\n    <phone type=\"voice\" time=\"day\">{escape(p['phone'])}</phone>\n"
            f"    <address><city>{escape(client.get('city') or '')}</city><regioncode>{escape(client.get('state') or '')}</regioncode></address>\n"
            "   </contact>\n"
            f"   <comments>{comments}</comments>\n"
            "  </customer>\n"
            f"  <vendor><vendorname>{escape(client.get('name') or '')}</vendorname></vendor>\n"
            f"  <provider><name part=\"full\">{escape(shop.get('source_name') or 'Website')}</name><service>Internet lead</service></provider>\n"
            " </prospect>\n</adf>\n")


def plain_lead_text(shop: dict, client: dict) -> str:
    p = shop["persona"]
    return (f"New website lead for {client.get('name')}\n\nName: {p['name']}\nPhone: {p['phone']}\nEmail: {p['email']}\n"
            f"Interested in: {p.get('offering') or p.get('vehicle') or ''}\nMessage: {p.get('goals') or p.get('summary') or ''}\n\nSource: {shop.get('source_name') or 'Website'}\n")


async def deliver(db, shop: dict, client: dict) -> dict:
    """Push the lead into the store's CRM inbox (ADF for automotive, a plain lead email otherwise)."""
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    to = (client.get("lead_email") or "").strip().lower()
    if not key or not to:
        return {"success": False, "error": "No CRM lead email on this client" if not to else "Email is not configured (RESEND_API_KEY)"}
    import resend
    resend.api_key = key
    p = shop["persona"]
    auto = client.get("industry", "automotive") in (None, "automotive")
    body = adf_xml(shop, client) if auto else plain_lead_text(shop, client)
    subject = f"New Lead: {p['name']}" + (f" - {p.get('vehicle') or p.get('offering')}" if (p.get('vehicle') or p.get('offering')) else "")
    sender_domain = (os.environ.get("SENDER_EMAIL", "notifications@imonsocial.com").split("@")[-1]).strip().lower()
    payload = {"from": f"{shop.get('source_name') or 'Website'} Leads <leads@{sender_domain}>", "to": [to], "reply_to": p["email"], "subject": subject, "text": body,
               "headers": {"X-Entity-Ref-ID": f"lead-shop-{shop['_id']}"}}
    if auto:
        payload["attachments"] = [{"filename": "lead.xml", "content": list(body.encode("utf-8"))}]
    try:
        r = await asyncio.to_thread(resend.Emails.send, payload)
        return {"success": True, "id": (r or {}).get("id"), "subject": subject}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


async def create(db, client: dict, me: dict, body: dict) -> dict:
    department = body.get("department") or "sales"
    method = "manual" if body.get("method") == "manual" else "adf"
    window = int(body.get("window_hours") or 72)
    window = window if window in WINDOWS else 72
    if method == "adf" and not (client.get("lead_email") or "").strip():
        raise ValueError("Add the store's CRM lead email in Lead shop setup first (or pick 'I'll submit the web form')")
    if not inbound_domain():
        raise ValueError("Email receiving is not configured (INBOUND_EMAIL_DOMAIN)")
    script = None
    if body.get("script_id") and _oid(body["script_id"]):
        script = await db.scripts.find_one({"_id": _oid(body["script_id"])})
    persona, script = await build_persona(db, client, department, (body.get("offering") or "").strip()[:80] or None, script)
    now = _now()
    doc = {"client_id": str(client["_id"]), "department": department, "industry": client.get("industry") or "automotive", "store_name": client.get("name"), "locale": client.get("locale"),
           "status": "pending_delivery", "method": method, "source_name": (body.get("source_name") or "").strip()[:60] or ("Website" if method == "adf" else "Website form"),
           "persona": persona, "script_id": str(script["_id"]), "script_title": script.get("title"), "window_hours": window, "process": clean_process(client.get("lead_process")),
           "events": [], "sessions": {"phone": [], "text": None, "email": None}, "delivery": {"method": method, "to_email": (client.get("lead_email") or "").strip().lower() if method == "adf" else None},
           "started_at": None, "expires_at": None, "closed_at": None, "score": None, "score_token": uuid.uuid4().hex, "notes": (body.get("notes") or "")[:500],
           "created_by": str(me["_id"]), "created_at": now, "updated_at": now}
    res = await db[COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    try:
        number = await acquire_number(db, client, me)
    except Exception as e:
        await db[COLL].delete_one({"_id": doc["_id"]})
        raise ValueError(f"No shopper phone number: {str(e)[:160]}")
    await db[POOL].update_one({"_id": number["_id"]}, {"$set": {"lead_shop_id": str(doc["_id"])}})
    doc["persona"]["phone"] = number["phone_number"]
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"persona.phone": number["phone_number"], "number_pool_id": str(number["_id"])}})
    if method == "adf":
        r = await deliver(db, doc, client)
        if not r.get("success"):
            await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"delivery.error": r.get("error"), "updated_at": _now()}})
            raise ValueError(f"The lead email could not be sent: {r.get('error')}")
        await mark_delivered(db, await db[COLL].find_one({"_id": doc["_id"]}), email_id=r.get("id"), subject=r.get("subject"))
    return await db[COLL].find_one({"_id": doc["_id"]})


async def mark_delivered(db, shop: dict, email_id: Optional[str] = None, subject: Optional[str] = None):
    now = _now()
    ev = {"at": now, "channel": "lead", "direction": "out", "kind": "delivered", "summary": f"Lead delivered to the store ({'ADF email to ' + (shop.get('delivery') or {}).get('to_email', '') if shop.get('method') == 'adf' else 'web form submitted by hand'})"}
    await db[COLL].update_one({"_id": shop["_id"]}, {"$set": {"status": "live", "started_at": now, "expires_at": now + timedelta(hours=int(shop.get("window_hours") or 72)), "delivery.sent_at": now,
                                                              "delivery.email_id": email_id, "delivery.subject": subject, "delivery.error": None, "updated_at": now}, "$push": {"events": ev}})


async def add_event(db, shop_id, channel: str, kind: str, summary: str, **extra):
    ev = {"at": _now(), "channel": channel, "direction": extra.pop("direction", "in"), "kind": kind, "summary": summary[:300], **extra}
    await db[COLL].update_one({"_id": _oid(shop_id)}, {"$push": {"events": ev}, "$set": {"updated_at": _now()}})
    return ev


# ── the store reaches out ─────────────────────────────────────────────────────
def _child_base(shop: dict, mode: str, rep_phone: Optional[str] = None, rep_email: Optional[str] = None) -> dict:
    now = _now()
    p = shop["persona"]
    return {"kind": "mystery_shop", "mode": mode, "status": "live", "user_id": None, "client_id": shop["client_id"], "target_id": None, "lead_shop_id": str(shop["_id"]),
            "rep_name": "the store", "rep_phone": rep_phone, "rep_email": rep_email, "department": shop.get("department") or "sales", "industry": shop.get("industry"), "store_id": None,
            "store_name": shop.get("store_name") or "the store", "locale": shop.get("locale"), "script_id": shop["script_id"], "script_title": shop.get("script_title"),
            "direction": "outbound", "persona": p, "curveballs": [], "assignment_id": None, "scheduled_for": now, "attempts": 1, "max_attempts": 1, "manual": True, "notify_sms": False,
            "token": uuid.uuid4().hex, "turns": [], "started_at": now, "created_by": shop.get("created_by"), "created_at": now, "updated_at": now}


async def inbound_call(db, to_phone: str, from_phone: str, call_sid: str) -> Optional[str]:
    """The store calls the shopper: answer in persona over ConversationRelay. None = not one of our shopper numbers."""
    from services import scripts as scr
    shop, row = await number_owner(db, to_phone)
    if not row:
        return None
    if not shop:
        if row.get("last_lead_shop_id"):
            await add_event(db, row["last_lead_shop_id"], "call", "late_call", f"Called {to_phone} after the shop closed", **{"from": from_phone})
        return _voicemail_twiml()
    if shop.get("status") == "pending_delivery":
        return _voicemail_twiml()
    doc = _child_base(shop, "phone", rep_phone=from_phone)
    doc.update({"call_sid": call_sid, "call_status": "in-progress", "from_number": to_phone})
    res = await db.roleplay_sessions.insert_one(doc)
    doc["_id"] = res.inserted_id
    n_before = sum(1 for e in shop.get("events") or [] if e.get("channel") == "call")
    await add_event(db, shop["_id"], "call", "call_answered", f"Store called the shopper from {from_phone} (call {n_before + 1}), answered", **{"from": from_phone, "session_id": str(res.inserted_id)})
    await db[COLL].update_one({"_id": shop["_id"]}, {"$push": {"sessions.phone": str(res.inserted_id)}})
    client = await db.shop_clients.find_one({"_id": _oid(shop["client_id"])}) or {}
    if client.get("record_calls", True) and call_sid:
        asyncio.create_task(_record_call(call_sid, str(res.inserted_id), doc["token"]))
    from services import live_shops
    use_live, why = await live_shops.decide(db, doc)
    logger.info(f"[LeadShop] callback {res.inserted_id}: {'GPT-Live' if use_live else 'classic relay'} ({why})")
    if use_live:
        return live_shops.stream_twiml(doc)
    await live_shops.mark_relay(db, doc, why)
    return scr.relay_twiml(doc)


def _voicemail_twiml() -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna-Neural">Hi, sorry I missed you. Leave a message and I will get back to you.</Say>'
            '<Record maxLength="90" playBeep="true"/><Say voice="Polly.Joanna-Neural">Thanks, bye.</Say></Response>')


async def _record_call(call_sid: str, sid: str, token: str):
    """ConversationRelay has no record attribute: start a recording on the live call a moment after it connects."""
    await asyncio.sleep(1.5)
    try:
        from routers.twilio_admin import _get_twilio_client
        client = _get_twilio_client()
        await asyncio.to_thread(client.calls(call_sid).recordings.create, recording_status_callback=f"{_app_url()}/api/scripts/roleplay/recording/{sid}?t={token}", recording_channels="dual")
    except Exception as e:
        logger.info(f"[LeadShop] recording not started for {call_sid}: {str(e)[:120]}")


async def inbound_text(db, to_phone: str, from_phone: str, body: str, sid: str = "", media: int = 0) -> bool:
    from services import text_shops as tx
    shop, row = await number_owner(db, to_phone)
    if not row:
        return False
    if not shop:
        if row.get("last_lead_shop_id"):
            await add_event(db, row["last_lead_shop_id"], "text", "late_text", f"Texted after the shop closed: {(body or '')[:80]}", **{"from": from_phone})
        return True
    if shop.get("status") == "pending_delivery":
        return True
    s = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "mode": "text", "lead_shop_id": str(shop["_id"]), "status": {"$in": ["live", "ending"]}})
    if not s:
        doc = _child_base(shop, "text", rep_phone=from_phone)
        doc.update({"from_number": to_phone, "expires_at": _now() + timedelta(hours=tx.MAX_HOURS)})
        res = await db.roleplay_sessions.insert_one(doc)
        await db[COLL].update_one({"_id": shop["_id"]}, {"$set": {"sessions.text": str(res.inserted_id)}})
        await add_event(db, shop["_id"], "text", "text_received", f"Store texted the shopper from {from_phone}: {(body or '[photo]')[:120]}", **{"from": from_phone, "session_id": str(res.inserted_id)})
    elif s.get("rep_phone") != from_phone:
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"rep_phone": from_phone}})
        await add_event(db, shop["_id"], "text", "text_received", f"Text from a second store number {from_phone}: {(body or '')[:120]}", **{"from": from_phone, "session_id": str(s["_id"])})
    else:
        await add_event(db, shop["_id"], "text", "text_received", f"Store texted: {(body or '[photo]')[:120]}", **{"from": from_phone, "session_id": str(s["_id"])})
    return await tx.handle_inbound(db, to_phone, from_phone, body, sid, media)


async def lead_shop_for_email(db, to_list: list) -> Optional[dict]:
    addrs = set()
    for t in to_list or []:
        v = str(t.get("email") or t.get("address") or "") if isinstance(t, dict) else str(t or "")
        m = re.search(r"<([^>]+)>", v)
        addrs.add((m.group(1) if m else v).strip().lower())
    addrs.discard("")
    if not addrs:
        return None
    return await db[COLL].find_one({"persona.email": {"$in": list(addrs)}}, sort=[("created_at", -1)])


async def inbound_email(db, shop: dict, from_email: str, subject: str, body: str, email_id: str = "") -> bool:
    from services import email_shops as ems
    if shop.get("status") not in ("live", "closing"):
        if shop.get("status") == "completed":
            await add_event(db, shop["_id"], "email", "late_email", f"Emailed after the shop closed: {subject[:80]}", **{"from": from_email})
        return True
    automated = _looks_automated(shop, subject, body)
    s = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "mode": "email", "lead_shop_id": str(shop["_id"]), "status": {"$in": ["live", "ending"]}})
    if not s:
        p = shop["persona"]
        doc = _child_base(shop, "email", rep_email=from_email)
        doc.update({"subject": subject[:200], "from_email": p["email"], "reply_to": p["email"], "lead_from": f"{p['name']} <{p['email']}>", "lead_reply_to": p["email"], "expires_at": _now() + timedelta(hours=ems.MAX_HOURS)})
        res = await db.roleplay_sessions.insert_one(doc)
        s = await db.roleplay_sessions.find_one({"_id": res.inserted_id})
        await db[COLL].update_one({"_id": shop["_id"]}, {"$set": {"sessions.email": str(res.inserted_id)}})
    elif s.get("rep_email") != from_email and not automated:
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"rep_email": from_email}})
    await add_event(db, shop["_id"], "email", "auto_reply" if automated else "email_received", f"{'Automated email' if automated else 'Store emailed'} from {from_email}: {subject[:100]}", **{"from": from_email, "session_id": str(s["_id"]), "automated": automated})
    if automated:
        return True  # an auto-responder is a response on the clock, but the shopper does not answer a robot
    return await ems.handle_inbound(db, str(s["_id"]), from_email, subject, body, email_id)


def _looks_automated(shop: dict, subject: str, body: str) -> bool:
    started = _utc(shop.get("started_at"))
    quick = bool(started) and (_now() - started).total_seconds() < AUTO_REPLY_S
    blob = f"{subject}\n{body}".lower()
    words = ("do not reply", "do-not-reply", "noreply", "no-reply", "automated", "auto-reply", "autoreply", "this is an automatic", "thank you for your inquiry", "we have received your", "we received your request")
    return quick or any(w in blob for w in words)


# ── closing + scoring ─────────────────────────────────────────────────────────
async def close(db, shop: dict, reason: str = "window_closed"):
    """Stop the clock: finish live conversations (they grade themselves), then score once every child is done."""
    from services import text_shops as tx
    from services import email_shops as ems
    res = await db[COLL].find_one_and_update({"_id": shop["_id"], "status": {"$in": ["live", "pending_delivery"]}}, {"$set": {"status": "closing", "closed_at": _now(), "close_reason": reason, "updated_at": _now()}})
    if not res:
        return
    async for s in db.roleplay_sessions.find({"lead_shop_id": str(shop["_id"]), "status": {"$in": ["live", "ending"]}}):
        try:
            if s.get("mode") == "text":
                await tx.finish(db, str(s["_id"]), "lead_shop_closed")
            elif s.get("mode") == "email":
                await ems.finish(db, str(s["_id"]), "lead_shop_closed")
        except Exception as e:
            logger.warning(f"[LeadShop] finishing {s['_id']} failed: {e}")
    await release_number(db, shop)
    await maybe_score(db, await db[COLL].find_one({"_id": shop["_id"]}))


async def maybe_score(db, shop: Optional[dict]):
    if not shop or shop.get("status") != "closing":
        return
    pending = await db.roleplay_sessions.count_documents({"lead_shop_id": str(shop["_id"]), "status": {"$in": ["live", "ending", "grading", "dialing"]}})
    if pending:
        return
    score = await compute_score(db, shop)
    await db[COLL].update_one({"_id": shop["_id"]}, {"$set": {"status": "completed", "score": score, "updated_at": _now()}})
    await _notify(db, shop, score)


def _speed_pts(minutes: Optional[float], target: int) -> int:
    if minutes is None:
        return 0
    if target <= 0:
        return 100
    if minutes <= target:
        return 100
    if minutes >= target * 4:
        return 15
    return int(round(100 - 85 * (minutes - target) / (target * 3)))


async def compute_score(db, shop: dict) -> dict:
    from services import scripts as scr
    proc = clean_process(shop.get("process"))
    started = _utc(shop.get("started_at")) or _utc(shop.get("created_at"))
    closed = _utc(shop.get("closed_at")) or _now()
    events = sorted([e for e in shop.get("events") or [] if e.get("channel") in ("call", "text", "email") and e.get("direction", "in") == "in" and not str(e.get("kind", "")).startswith("late")], key=lambda e: _utc(e["at"]))
    firsts, per_channel = {}, {}
    for ch in ("call", "text", "email"):
        evs = [e for e in events if e["channel"] == ch]
        human = [e for e in evs if not e.get("automated")]
        first = _utc(evs[0]["at"]) if evs else None
        first_human = _utc(human[0]["at"]) if human else None
        mins = round((first - started).total_seconds() / 60, 1) if first and started else None
        human_mins = round((first_human - started).total_seconds() / 60, 1) if first_human and started else None  # a CRM auto-responder is not the store answering
        target = proc.get(f"first_{ch}_min", 0)
        per_channel[ch] = {"required": ch in proc["channels"], "count": len(evs), "human_count": len(human), "first_minutes": mins, "first_human_minutes": human_mins,
                           "target_minutes": target, "speed_pts": _speed_pts(human_mins, target) if ch in proc["channels"] else None, "auto_reply_only": bool(evs) and not human}
        firsts[ch] = human_mins
    required = [c for c in ("call", "text", "email") if c in proc["channels"]]
    speed = int(round(sum(per_channel[c]["speed_pts"] for c in required) / len(required))) if required else 100
    day1_calls = sum(1 for e in events if e["channel"] == "call" and started and _utc(e["at"]) - started <= timedelta(hours=24))
    effort = min(100, int(round(100 * day1_calls / max(1, proc["day1_calls"])))) if "call" in required else 100
    coverage = int(round(100 * sum(1 for c in required if per_channel[c]["human_count"]) / len(required))) if required else 100
    days_in_window = max(1, int(((closed - started).total_seconds() // 86400) + 1)) if started else 1
    want_days = min(int(proc.get("follow_up_days") or 1), days_in_window)
    contact_days = len({_utc(e["at"]).date() for e in events if not e.get("automated")})
    persistence = min(100, int(round(100 * contact_days / want_days))) if want_days > 1 else None
    weights = {"speed": 50, "effort": 20, "coverage": 15, "persistence": 15} if persistence is not None else {"speed": 55, "effort": 25, "coverage": 20}
    parts = {"speed": speed, "effort": effort, "coverage": coverage, **({"persistence": persistence} if persistence is not None else {})}
    process_score = int(round(sum(parts[k] * w for k, w in weights.items()) / sum(weights.values())))
    evals = await db.call_evaluations.find({"roleplay_session_id": {"$in": [str(s["_id"]) async for s in db.roleplay_sessions.find({"lead_shop_id": str(shop["_id"])}, {"_id": 1})]}, "graded_by": {"$ne": "system"}}).to_list(20)
    quality_rows = [{"session_id": e["roleplay_session_id"], "channel": e.get("channel"), "score_pct": e.get("score_pct"), "summary": e.get("summary"), "coaching": (e.get("coaching") or [])[:3], "wins": (e.get("wins") or [])[:3]} for e in evals if e.get("score_pct") is not None]
    quality = int(round(sum(r["score_pct"] for r in quality_rows) / len(quality_rows))) if quality_rows else None
    overall = int(round(0.55 * process_score + 0.45 * quality)) if quality is not None else int(round(process_score * 0.7))
    if not events:
        overall = 0
    timeline = [f"{_fmt_delta(_utc(e['at']) - started) if started else ''} {e.get('summary')}" for e in sorted(shop.get("events") or [], key=lambda e: _utc(e["at"]))]
    coaching = await _coach(db, shop, proc, per_channel, parts, quality_rows, timeline, overall, scr)
    return {"overall": overall, "process": process_score, "quality": quality, "parts": parts, "weights": weights, "per_channel": per_channel, "day1_calls": day1_calls, "contact_days": contact_days,
            "want_days": want_days, "no_contact": not events, "quality_rows": quality_rows, "timeline": timeline, **coaching, "scored_at": _iso(_now())}


def _fmt_delta(d: timedelta) -> str:
    s = int(d.total_seconds())
    if s < 60:
        return "+0m"
    if s < 3600:
        return f"+{s // 60}m"
    if s < 86400:
        return f"+{s // 3600}h {(s % 3600) // 60}m"
    return f"+{s // 86400}d {(s % 86400) // 3600}h"


async def _coach(db, shop, proc, per_channel, parts, quality_rows, timeline, overall, scr) -> dict:
    system = ("You review how a business handled one internet lead during a mystery shop. You get the process they promised, what actually happened (timeline with +minutes since the lead arrived), "
              "the speed/effort scores and the graded conversations. Write for the store's general manager: plain words, specific, kind but direct. No em dashes. "
              "Return ONLY JSON: {\"summary\": \"3 sentences max\", \"wins\": [\"up to 3\"], \"coaching\": [\"up to 4 specific fixes, each one sentence\"]}")
    user = (f"STORE: {shop.get('store_name')} ({shop.get('department')})\nPROMISED PROCESS: first call within {proc['first_call_min']} min, first text within {proc['first_text_min']} min, first email within {proc['first_email_min']} min; "
            f"channels: {', '.join(proc['channels'])}; {proc['day1_calls']} call attempts on day one; follow up for {proc['follow_up_days']} days; must: {'; '.join(proc.get('must') or [])}.\n"
            f"WHAT HAPPENED:\n" + ("\n".join(timeline) or "Nothing. Nobody contacted the lead.") +
            f"\n\nPER CHANNEL: {per_channel}\nSCORES: {parts}, overall {overall}\nCONVERSATIONS GRADED: " + ("\n".join(f"- {r['channel']}: {r['score_pct']}%: {r['summary']}" for r in quality_rows) or "none"))
    try:
        data = await scr._llm_json(system, user, timeout=60)
        return {"summary": scr.no_em_dash(str(data.get("summary") or ""))[:600], "wins": [scr.no_em_dash(str(w))[:200] for w in (data.get("wins") or [])][:3], "coaching": [scr.no_em_dash(str(c))[:240] for c in (data.get("coaching") or [])][:4]}
    except Exception as e:
        logger.warning(f"[LeadShop] coaching failed: {e}")
        return {"summary": "Scored from the timeline; the written review could not be generated this time.", "wins": [], "coaching": []}


async def _notify(db, shop: dict, score: dict):
    if not shop.get("created_by"):
        return
    try:
        from routers.notifications_center import invalidate_feed
        from routers.push_notifications import send_push_to_user
        title = f"Lead shop at {shop.get('store_name')}: {score['overall']}%"
        msg = (score.get("summary") or "")[:160]
        link = f"/admin/mystery-shops/{shop['client_id']}?tab=leads"
        await db.notifications.insert_one({"user_id": shop["created_by"], "type": "lead_shop_graded", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": _now()})
        invalidate_feed(shop["created_by"])
        await send_push_to_user(shop["created_by"], title, msg, link, "storefront")
    except Exception as e:
        logger.debug(f"[LeadShop] notify failed: {e}")


async def child_finished(db, session: dict):
    """A conversation inside a lead shop just graded: stamp the result on the timeline and score the shop if it was closing."""
    shop = await db[COLL].find_one({"_id": _oid(session.get("lead_shop_id"))})
    if not shop:
        return
    pct = session.get("score_pct")
    label = {"phone": "Call", "text": "Text thread", "email": "Email thread"}.get(session.get("mode"), "Conversation")
    await add_event(db, shop["_id"], session.get("mode") if session.get("mode") != "phone" else "call", "graded", f"{label} graded: {int(pct)}%" if pct is not None else f"{label} ended", direction="note", session_id=str(session["_id"]))
    await maybe_score(db, await db[COLL].find_one({"_id": shop["_id"]}))


async def sweep(db) -> int:
    now = _now()
    n = 0
    async for shop in db[COLL].find({"status": "live", "expires_at": {"$lte": now}}):
        await close(db, shop, "window_closed")
        n += 1
    async for shop in db[COLL].find({"status": "closing", "closed_at": {"$lte": now - timedelta(minutes=2)}}):
        await maybe_score(db, shop)
    async for shop in db[COLL].find({"status": "closing", "closed_at": {"$lte": now - timedelta(minutes=30)}}):
        # a child stuck in grading for half an hour must not hold the report hostage
        await db.roleplay_sessions.update_many({"lead_shop_id": str(shop["_id"]), "status": {"$in": ["live", "ending", "grading", "dialing"]}}, {"$set": {"status": "failed", "fail_reason": "Lead shop closed", "updated_at": now}})
        await maybe_score(db, await db[COLL].find_one({"_id": shop["_id"]}))
    return n


# ── read model ────────────────────────────────────────────────────────────────
async def serialize(db, shop: dict, with_sessions: bool = False) -> dict:
    p = shop.get("persona") or {}
    started = _utc(shop.get("started_at"))
    out = {"id": str(shop["_id"]), "client_id": shop.get("client_id"), "status": shop.get("status"), "method": shop.get("method"), "source_name": shop.get("source_name"), "department": shop.get("department"),
           "store_name": shop.get("store_name"), "window_hours": shop.get("window_hours"), "window_label": WINDOWS.get(int(shop.get("window_hours") or 72), ""), "process": clean_process(shop.get("process")),
           "persona": {"name": p.get("name"), "first": p.get("first"), "last": p.get("last"), "email": p.get("email"), "phone": p.get("phone"), "offering": p.get("offering") or p.get("vehicle"), "goals": p.get("goals"), "summary": p.get("summary")},
           "script_title": shop.get("script_title"), "delivery": {k: _iso(v) for k, v in (shop.get("delivery") or {}).items()}, "created_at": _iso(shop.get("created_at")), "started_at": _iso(started),
           "expires_at": _iso(shop.get("expires_at")), "closed_at": _iso(shop.get("closed_at")), "close_reason": shop.get("close_reason"), "score": shop.get("score"), "notes": shop.get("notes"),
           "events": [{**{k: v for k, v in e.items() if k != "at"}, "at": _iso(e.get("at")), "since": _fmt_delta(_utc(e["at"]) - started) if started and e.get("at") else None} for e in sorted(shop.get("events") or [], key=lambda e: _utc(e["at"]))],
           "counts": {ch: sum(1 for e in shop.get("events") or [] if e.get("channel") == ch and e.get("direction", "in") == "in" and not str(e.get("kind", "")).startswith("late")) for ch in ("call", "text", "email")}}
    if with_sessions:
        from services import mystery_shops as ms
        rows = await db.roleplay_sessions.find({"lead_shop_id": str(shop["_id"])}).sort("created_at", 1).to_list(20)
        out["conversations"] = [ms.serialize_call(s) for s in rows]
    return out


def identity_card(shop: dict) -> dict:
    p = shop.get("persona") or {}
    return {"name": p.get("name"), "first": p.get("first"), "last": p.get("last"), "email": p.get("email"), "phone": p.get("phone"), "offering": p.get("offering") or p.get("vehicle"),
            "message": p.get("goals") or p.get("summary") or "", "zip": "", "note": "Submit the store's website form with exactly these details, then tap 'I submitted the form' to start the clock."}
