"""Power dialer engine.

One rep, on their own cell, stays on one Twilio call for the whole session. Every "Press 1" (phone) or "Dial next" (app)
is the human launching a burst of 1-3 lead calls. The first lead that answers is dropped into the rep's conference
instantly; the other ringing legs are cancelled (no live person = not an abandoned call). A second live answer in the
race window hears the TSR abandonment message (seller + number + press 9 = do not call) and counts against the
campaign's 3% budget, which throttles the campaign back to one line. Every dial is a `dialer_attempts` row: the
compliance log, never deleted."""
import asyncio
import io
import logging
import math
import os
import re
import secrets
import struct
import wave
from datetime import datetime, timezone, timedelta
from typing import Optional
from xml.sax.saxutils import escape

from bson import ObjectId

from services import compliance as comp

logger = logging.getLogger(__name__)

CAMPAIGNS, LEADS, SESSIONS, BURSTS, ATTEMPTS = "dialer_campaigns", "dialer_leads", "dialer_sessions", "dialer_bursts", "dialer_attempts"
RING_SECONDS = 25
BURST_TIMEOUT_S = RING_SECONDS + 20
ACCEPT_TIMEOUT_S = 5
IDLE_TIMEOUT_MIN = 30
START_TIMEOUT_S = 90
MAX_LINES = 3
LAB_KEY = "power_dialer"
MANAGER_ROLES = {"super_admin", "admin", "org_admin", "store_manager", "manager"}
TERMINAL_CALL = {"completed", "busy", "no-answer", "failed", "canceled"}
LIVE_ATTEMPT = {"queued", "ringing", "answered"}

DISPOSITIONS = [
    {"key": "interested", "label": "Interested", "outcome": "done", "promote": True, "icon": "flame", "color": "#34C759"},
    {"key": "callback", "label": "Call back", "outcome": "callback", "promote": True, "icon": "calendar", "color": "#C9A962"},
    {"key": "voicemail", "label": "Voicemail", "outcome": "retry", "icon": "recording", "color": "#8E8E93"},
    {"key": "no_answer", "label": "No answer", "outcome": "retry", "icon": "call-outline", "color": "#8E8E93"},
    {"key": "not_interested", "label": "Not interested", "outcome": "done", "icon": "close-circle", "color": "#FF9500"},
    {"key": "wrong_number", "label": "Wrong number", "outcome": "done", "icon": "help-circle", "color": "#FF9500"},
    {"key": "dnc", "label": "Do not call", "outcome": "dnc", "icon": "ban", "color": "#FF3B30"},
]
DISPO = {d["key"]: d for d in DISPOSITIONS}

DEFAULTS = {
    "audience": "b2b", "lines": 2, "connect_mode": "instant", "recording": "off", "voicemail": "skip",
    "hours": {"start": "09:00", "end": "20:00"}, "max_attempts": 3, "retry_hours": 24, "max_per_day": 2,
    "allow_registry_b2b": False, "script": "", "rep_ids": [], "caller_id": "", "seller_name": "",
    "ghl": {"tag": "", "push": True, "pipeline_id": "", "stage_id": ""},
}
SETTINGS_KEYS = tuple(DEFAULTS.keys())
_indexes_done = False


def _now():
    return datetime.now(timezone.utc)


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if v and ObjectId.is_valid(str(v)) else None


def _app_url() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def _client():
    from services.lead_call_engine import _twilio_client
    return _twilio_client()


def is_manager(user: dict) -> bool:
    return (user or {}).get("role") in MANAGER_ROLES


async def available(db, user: dict) -> bool:
    from services import lab
    return (user or {}).get("role") == "super_admin" or await lab.is_live(db, LAB_KEY)


async def ensure_indexes(db):
    global _indexes_done
    if _indexes_done:
        return
    _indexes_done = True
    await db[LEADS].create_index([("campaign_id", 1), ("phone", 1)], unique=True)
    await db[LEADS].create_index([("campaign_id", 1), ("status", 1), ("prio", 1), ("next_attempt_at", 1)])
    await db[ATTEMPTS].create_index([("campaign_id", 1), ("started_at", -1)])
    await db[ATTEMPTS].create_index([("lead_id", 1), ("started_at", -1)])
    await db[ATTEMPTS].create_index("call_sid")
    await db[comp.DNC_LIST].create_index("phone", unique=True)
    await db[comp.DNC_REGISTRY].create_index("n", unique=True)


# ── campaigns ─────────────────────────────────────────────────────────────────
def campaign_scope(me: dict) -> dict:
    from services.lead_flows import user_store_id
    uid, sid = str(me["_id"]), user_store_id(me)
    if is_manager(me):
        if sid:
            return {"$or": [{"store_id": sid}, {"created_by": uid}, {"rep_ids": uid}]}
        if me.get("role") in ("super_admin", "org_admin"):
            return {}
        return {"$or": [{"created_by": uid}, {"rep_ids": uid}]}
    return {"rep_ids": uid, "status": "active"}


def _hm(v, default) -> str:
    return v if isinstance(v, str) and re.fullmatch(r"\d{2}:\d{2}", v) else default


def clean_settings(body: dict) -> dict:
    out = {}
    if "audience" in body:
        out["audience"] = "b2c" if body["audience"] == "b2c" else "b2b"
    if "lines" in body:
        out["lines"] = max(1, min(int(body["lines"] or 1), MAX_LINES))
    if "connect_mode" in body:
        out["connect_mode"] = "press1" if body["connect_mode"] == "press1" else "instant"
    if "recording" in body:
        out["recording"] = "on" if body["recording"] == "on" else "off"
    if "voicemail" in body:
        out["voicemail"] = "rep" if body["voicemail"] == "rep" else "skip"
    if isinstance(body.get("hours"), dict):
        out["hours"] = {"start": _hm(body["hours"].get("start"), "09:00"), "end": _hm(body["hours"].get("end"), "20:00")}
    if "max_attempts" in body:
        out["max_attempts"] = max(1, min(int(body["max_attempts"] or 3), 10))
    if "retry_hours" in body:
        out["retry_hours"] = max(1, min(int(body["retry_hours"] or 24), 24 * 14))
    if "max_per_day" in body:
        out["max_per_day"] = max(1, min(int(body["max_per_day"] or 2), comp.FEDERAL_MAX_PER_DAY))
    if "allow_registry_b2b" in body:
        out["allow_registry_b2b"] = bool(body["allow_registry_b2b"])
    if "script" in body:
        out["script"] = str(body["script"] or "")[:4000]
    if isinstance(body.get("rep_ids"), list):
        out["rep_ids"] = [str(r) for r in body["rep_ids"] if r][:50]
    if "caller_id" in body:
        out["caller_id"] = comp.e164(body["caller_id"] or "")
    if "seller_name" in body:
        out["seller_name"] = " ".join(str(body["seller_name"] or "").split())[:80]
    if isinstance(body.get("ghl"), dict):
        g = body["ghl"]
        out["ghl"] = {"tag": str(g.get("tag") or "")[:80], "push": bool(g.get("push", True)), "pipeline_id": str(g.get("pipeline_id") or ""), "stage_id": str(g.get("stage_id") or "")}
    return out


async def create_campaign(db, me: dict, body: dict) -> dict:
    from services.lead_flows import user_store_id
    store_id = body.get("store_id") or user_store_id(me)
    store = await db.stores.find_one({"_id": _oid(store_id)}, {"name": 1}) if _oid(store_id) else None
    doc = {**DEFAULTS, "ghl": dict(DEFAULTS["ghl"]), "hours": dict(DEFAULTS["hours"]), **clean_settings(body)}
    doc.update({"name": " ".join(str(body.get("name") or "").split())[:80] or "New campaign", "store_id": store_id, "created_by": str(me["_id"]),
                "status": "active", "created_at": _now(), "updated_at": _now()})
    doc["seller_name"] = doc["seller_name"] or (store or {}).get("name") or "our team"
    if not is_manager(me) and str(me["_id"]) not in doc["rep_ids"]:
        doc["rep_ids"] = doc["rep_ids"] + [str(me["_id"])]
    res = await db[CAMPAIGNS].insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def lead_counts(db, campaign_id) -> dict:
    rows = await db[LEADS].aggregate([{"$match": {"campaign_id": str(campaign_id)}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]).to_list(20)
    counts = {r["_id"]: r["n"] for r in rows}
    counts["total"] = sum(counts.values())
    counts["remaining"] = sum(n for k, n in counts.items() if k in ("new", "queued", "callback", "calling", "wrapup"))
    return counts


async def campaign_stats(db, c: dict) -> dict:
    since = _now() - timedelta(days=30)
    rows = await db[ATTEMPTS].aggregate([
        {"$match": {"campaign_id": str(c["_id"]), "started_at": {"$gte": since}}},
        {"$group": {"_id": None, "dials": {"$sum": 1},
                    "answered_live": {"$sum": {"$cond": [{"$eq": ["$answered_live", True]}, 1, 0]}},
                    "abandoned": {"$sum": {"$cond": [{"$eq": ["$abandoned", True]}, 1, 0]}},
                    "connected": {"$sum": {"$cond": [{"$eq": ["$status", "connected"]}, 1, 0]}},
                    "voicemail": {"$sum": {"$cond": [{"$eq": ["$status", "voicemail"]}, 1, 0]}},
                    "talk_s": {"$sum": {"$ifNull": ["$talk_s", 0]}}}},
    ]).to_list(1)
    r = rows[0] if rows else {}
    answered, abandoned = int(r.get("answered_live") or 0), int(r.get("abandoned") or 0)
    dispo = await db[ATTEMPTS].aggregate([{"$match": {"campaign_id": str(c["_id"]), "disposition": {"$ne": None}}}, {"$group": {"_id": "$disposition", "n": {"$sum": 1}}}]).to_list(20)
    return {"dials": int(r.get("dials") or 0), "answered_live": answered, "abandoned": abandoned, "connected": int(r.get("connected") or 0),
            "voicemail": int(r.get("voicemail") or 0), "talk_s": int(r.get("talk_s") or 0), "abandon_rate": round(abandoned / answered, 4) if answered else 0.0,
            "abandon_limit": comp.ABANDON_RATE_LIMIT, "lines_effective": comp.throttle_lines(c.get("lines", 1), answered, abandoned),
            "throttled": comp.throttle_lines(c.get("lines", 1), answered, abandoned) < max(1, int(c.get("lines") or 1)),
            "dispositions": {d["_id"]: d["n"] for d in dispo}, "window_days": 30}


async def ready_count(db, c: dict, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    cur = db[LEADS].find({"campaign_id": str(c["_id"]), "status": {"$in": ["new", "queued", "callback"]}}, {"state": 1, "tz": 1, "dnc": 1, "attempts": 1, "status": 1, "next_attempt_at": 1}).limit(3000)
    ready = waiting = 0
    opens = []
    async for l in cur:
        na = l.get("next_attempt_at")
        if na and (na.replace(tzinfo=timezone.utc) if na.tzinfo is None else na) > now:
            waiting += 1
            opens.append(na)
            continue
        chk = comp.check_lead(l, c, now)
        if chk["ok"]:
            ready += 1
        elif chk["reason"] == "outside_window":
            waiting += 1
            if chk["next_open"]:
                opens.append(chk["next_open"])
    nxt = min(opens) if opens else None
    return {"ready": ready, "waiting_window": waiting, "next_open": _iso(nxt)}


async def serialize_campaign(db, c: dict, with_stats: bool = False) -> dict:
    out = {k: c.get(k, DEFAULTS.get(k)) for k in SETTINGS_KEYS}
    out.update({"id": str(c["_id"]), "name": c.get("name"), "store_id": c.get("store_id"), "status": c.get("status"), "created_by": c.get("created_by"),
                "created_at": _iso(c.get("created_at")), "updated_at": _iso(c.get("updated_at")), "counts": await lead_counts(db, c["_id"])})
    if with_stats:
        out["stats"] = await campaign_stats(db, c)
        out["queue"] = await ready_count(db, c)
        reps = await db.users.find({"_id": {"$in": [o for o in (_oid(r) for r in c.get("rep_ids") or []) if o]}}, {"name": 1, "first_name": 1, "phone": 1, "twilio_number": 1, "mvpline_number": 1}).to_list(60)
        out["reps"] = [{"id": str(u["_id"]), "name": u.get("name") or u.get("first_name") or "", "has_phone": bool(u.get("phone")), "has_number": bool(u.get("twilio_number") or u.get("mvpline_number"))} for u in reps]
    return out


def serialize_lead(l: dict) -> dict:
    return {"id": str(l["_id"]), "campaign_id": l.get("campaign_id"), "phone": l.get("phone"), "first_name": l.get("first_name") or "", "last_name": l.get("last_name") or "",
            "name": lead_name(l), "company": l.get("company") or "", "email": l.get("email") or "", "title": l.get("title") or "", "city": l.get("city") or "", "state": l.get("state"),
            "tz": l.get("tz"), "notes": l.get("notes") or "", "source": l.get("source"), "status": l.get("status"), "attempts": int(l.get("attempts") or 0),
            "disposition": l.get("disposition"), "last_outcome": l.get("last_outcome"), "last_attempt_at": _iso(l.get("last_attempt_at")), "next_attempt_at": _iso(l.get("next_attempt_at")),
            "dnc": (l.get("dnc") or {}).get("status"), "contact_id": l.get("contact_id"), "ghl_contact_id": l.get("ghl_contact_id"), "ghl_sync_error": l.get("ghl_sync_error"),
            "imported_at": _iso(l.get("imported_at")), "local_time": comp.check_lead(l, {"max_attempts": 999}, _now()).get("local_time")}


def lead_name(l: dict) -> str:
    n = f"{l.get('first_name') or ''} {l.get('last_name') or ''}".strip()
    return n or l.get("company") or l.get("phone") or "Unknown"


def serialize_attempt(a: dict) -> dict:
    keys = ("burst_id", "session_id", "campaign_id", "lead_id", "user_id", "phone", "caller_id", "status", "call_status", "answered_by", "answered_live", "abandoned",
            "disposition", "notes", "duration_s", "talk_s", "recording_url", "lead_name", "lead_state", "local_time", "compliance", "voicemail_detected")
    out = {k: a.get(k) for k in keys}
    out.update({"id": str(a["_id"]), **{k: _iso(a.get(k)) for k in ("started_at", "ringing_at", "answered_at", "connected_at", "ended_at", "dispositioned_at")}})
    return out


# ── import ────────────────────────────────────────────────────────────────────
HEADER_ALIASES = {
    "phone": ["phone", "mobile", "cell", "cell phone", "mobile phone", "telephone", "phone number", "number", "tel", "phone1", "phone 1", "phone 1 - value", "primary phone", "work phone", "direct"],
    "first_name": ["first name", "first", "firstname", "given name", "voornaam"],
    "last_name": ["last name", "last", "lastname", "surname", "family name", "achternaam"],
    "name": ["name", "full name", "contact", "contact name", "naam"],
    "company": ["company", "organization", "organisation", "business", "dealership", "dealer", "account", "company name", "organization name", "store", "bedrijf"],
    "email": ["email", "e-mail", "email address", "e-mail 1 - value", "work email"],
    "state": ["state", "st", "region", "province", "address 1 - region", "state/province"],
    "city": ["city", "town", "address 1 - city", "plaats"],
    "title": ["title", "job title", "position", "role", "functie"],
    "notes": ["notes", "note", "comments", "comment", "remarks"],
}


def parse_csv_leads(text: str) -> list:
    import csv
    text = (text or "").lstrip("\ufeff")
    if not text.strip():
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    alias = {a: k for k, al in HEADER_ALIASES.items() for a in al}
    rows = []
    for raw in reader:
        row = {}
        for h, v in (raw or {}).items():
            key = alias.get((h or "").strip().lower().replace("_", " "))
            if key and v and str(v).strip() and key not in row:
                row[key] = str(v).strip()
        if row.get("name") and not row.get("first_name"):
            parts = row.pop("name").split(" ", 1)
            row["first_name"], row["last_name"] = parts[0], (parts[1] if len(parts) > 1 else row.get("last_name", ""))
        row.pop("name", None)
        if any(row.values()):
            rows.append(row)
    return rows


async def import_rows(db, c: dict, rows: list, source: str, me: Optional[dict]) -> dict:
    await ensure_indexes(db)
    cid = str(c["_id"])
    existing = {l["phone"] async for l in db[LEADS].find({"campaign_id": cid}, {"phone": 1})}
    docs, dupes, invalid, dnc = [], 0, 0, 0
    now = _now()
    for r in rows:
        phone = comp.e164(r.get("phone") or "")
        if not phone:
            invalid += 1
            continue
        if phone in existing:
            dupes += 1
            continue
        existing.add(phone)
        reg = comp.region(phone, r.get("state"))
        st = await comp.dnc_status(db, phone, c)
        if st["blocked"]:
            dnc += 1
        docs.append({"campaign_id": cid, "store_id": c.get("store_id"), "phone": phone, "first_name": (r.get("first_name") or "")[:60], "last_name": (r.get("last_name") or "")[:60],
                     "company": (r.get("company") or "")[:120], "email": (r.get("email") or "").lower()[:120], "title": (r.get("title") or "")[:80], "city": (r.get("city") or "")[:80],
                     "state": reg["state"], "tz": reg["tz"], "notes": (r.get("notes") or "")[:1000], "source": source, "ghl_contact_id": r.get("ghl_contact_id"), "contact_id": r.get("contact_id"),
                     "status": "dnc" if st["blocked"] else "new", "prio": 2, "attempts": 0, "dnc": st, "imported_at": now, "imported_by": str(me["_id"]) if me else None,
                     "next_attempt_at": None, "disposition": None, "last_outcome": None})
    if docs:
        await db[LEADS].insert_many(docs)
        await db[CAMPAIGNS].update_one({"_id": c["_id"]}, {"$set": {"updated_at": now}})
    return {"added": len(docs), "duplicates": dupes, "invalid": invalid, "dnc": dnc, "rows": len(rows)}


async def rescrub(db, c: dict) -> dict:
    """Re-check every open lead against the DNC lists (run after a registry import)."""
    flagged = 0
    async for l in db[LEADS].find({"campaign_id": str(c["_id"]), "status": {"$in": ["new", "queued", "callback", "dnc"]}}):
        st = await comp.dnc_status(db, l["phone"], c)
        upd = {"dnc": st}
        if st["blocked"] and l.get("status") != "dnc":
            upd["status"], flagged = "dnc", flagged + 1
        elif not st["blocked"] and l.get("status") == "dnc" and (l.get("dnc") or {}).get("status") != "internal":
            upd["status"] = "new"
        await db[LEADS].update_one({"_id": l["_id"]}, {"$set": upd})
    return {"flagged": flagged}


# ── who to dial next ──────────────────────────────────────────────────────────
async def _attempts_last_24h(db, lead_id) -> int:
    return await db[ATTEMPTS].count_documents({"lead_id": str(lead_id), "started_at": {"$gte": _now() - timedelta(hours=24)}})


async def next_leads(db, c: dict, n: int) -> tuple:
    now = _now()
    picked, info = [], {"skipped_window": 0, "next_open": None}
    cur = db[LEADS].find({"campaign_id": str(c["_id"]), "status": {"$in": ["new", "queued", "callback"]},
                          "$or": [{"next_attempt_at": None}, {"next_attempt_at": {"$lte": now}}]}).sort([("prio", 1), ("next_attempt_at", 1), ("_id", 1)]).limit(400)
    async for l in cur:
        chk = comp.check_lead(l, c, now, await _attempts_last_24h(db, l["_id"]))
        if chk["ok"]:
            l["_check"] = chk
            picked.append(l)
            if len(picked) >= n:
                break
            continue
        if chk["reason"] == "dnc":
            await db[LEADS].update_one({"_id": l["_id"]}, {"$set": {"status": "dnc", "last_outcome": "dnc"}})
        elif chk["reason"] == "max_attempts":
            await db[LEADS].update_one({"_id": l["_id"]}, {"$set": {"status": "done", "last_outcome": l.get("last_outcome") or "exhausted"}})
        elif chk["next_open"]:
            info["skipped_window"] += 1
            info["next_open"] = min(info["next_open"], chk["next_open"]) if info["next_open"] else chk["next_open"]
            await db[LEADS].update_one({"_id": l["_id"]}, {"$set": {"next_attempt_at": chk["next_open"]}})
        else:
            await db[LEADS].update_one({"_id": l["_id"]}, {"$set": {"next_attempt_at": now + timedelta(hours=12)}})
    info["next_open"] = _iso(info["next_open"])
    return picked, info


# ── sessions ──────────────────────────────────────────────────────────────────
async def caller_id_for(db, c: dict, rep: dict) -> str:
    from routers.twilio_webhooks import normalize_phone
    for cand in (rep.get("twilio_number"), rep.get("mvpline_number"), c.get("caller_id"), os.environ.get("TWILIO_PHONE_NUMBER")):
        if cand:
            return normalize_phone(cand)
    return ""


async def active_session(db, user_id: str) -> Optional[dict]:
    return await db[SESSIONS].find_one({"user_id": str(user_id), "status": {"$ne": "ended"}}, sort=[("started_at", -1)])


async def start_session(db, c: dict, rep: dict) -> dict:
    await ensure_indexes(db)
    from routers.twilio_webhooks import normalize_phone
    rep_phone = normalize_phone(rep.get("phone") or "")
    if not rep_phone:
        raise ValueError("Add your cell number to your profile first, the dialer rings you there")
    caller_id = await caller_id_for(db, c, rep)
    if not caller_id:
        raise ValueError("No caller ID: you need a work number (or the campaign a caller ID)")
    client = _client()
    if client is None:
        raise ValueError("Calling is not configured on this server")
    doc = {"campaign_id": str(c["_id"]), "user_id": str(rep["_id"]), "store_id": c.get("store_id"), "status": "starting", "token": secrets.token_urlsafe(16),
           "rep_phone": rep_phone, "caller_id": caller_id, "started_at": _now(), "last_activity_at": _now(), "current_burst_id": None, "current_attempt_id": None,
           "stats": {"bursts": 0, "dials": 0, "connects": 0, "voicemails": 0, "abandoned": 0, "dispositions": 0}, "ended_at": None, "end_reason": None}
    res = await db[SESSIONS].insert_one(doc)
    doc["_id"] = res.inserted_id
    doc["conference"] = f"dialer-{res.inserted_id}"
    try:
        call = await asyncio.to_thread(client.calls.create, to=rep_phone, from_=caller_id, url=rep_url(doc, "answer"), status_callback=rep_url(doc, "status"),
                                       status_callback_event=["completed"], timeout=35)
        await db[SESSIONS].update_one({"_id": doc["_id"]}, {"$set": {"rep_call_sid": call.sid, "conference": doc["conference"]}})
        doc["rep_call_sid"] = call.sid
    except Exception as e:
        await db[SESSIONS].update_one({"_id": doc["_id"]}, {"$set": {"status": "ended", "ended_at": _now(), "end_reason": "rep_call_failed", "error": str(e)[:200]}})
        raise ValueError(f"Could not ring your phone: {str(e)[:120]}")
    return doc


async def _update_call(sid: Optional[str], **kw):
    client = _client()
    if not sid or client is None:
        return
    try:
        await asyncio.to_thread(client.calls(sid).update, **kw)
    except Exception as e:
        logger.info(f"[Dialer] call update {sid} {list(kw)} ignored: {str(e)[:120]}")


async def fire_burst(db, s: dict, c: dict, via: str, place_calls: bool = True) -> tuple:
    stats = await campaign_stats(db, c)
    n = stats["lines_effective"]
    leads, info = await next_leads(db, c, n)
    info.update({"lines": n, "throttled": stats["throttled"]})
    if not leads:
        return None, info
    now = _now()
    record = c.get("recording") == "on" and all(comp.recording_allowed(l.get("state"), c) for l in leads)
    burst = {"session_id": str(s["_id"]), "campaign_id": str(c["_id"]), "user_id": s["user_id"], "state": "ringing", "started_at": now, "connected_attempt_id": None,
             "record": record, "via": via, "lines": n, "mode": c.get("connect_mode", "instant"), "ended_at": None, "reason": None}
    bres = await db[BURSTS].insert_one(burst)
    burst["_id"] = bres.inserted_id
    attempts = []
    for l in leads:
        chk = l.get("_check") or {}
        attempts.append({"burst_id": str(burst["_id"]), "session_id": str(s["_id"]), "campaign_id": str(c["_id"]), "lead_id": str(l["_id"]), "user_id": s["user_id"],
                         "phone": l["phone"], "caller_id": s["caller_id"], "status": "queued", "started_at": now, "answered_live": False, "abandoned": False, "answered_by": None,
                         "lead_name": lead_name(l), "lead_state": l.get("state"), "lead_tz": l.get("tz"), "local_time": chk.get("local_time"), "token": secrets.token_hex(8),
                         "compliance": {"audience": c.get("audience"), "mode": c.get("connect_mode"), "dnc": (l.get("dnc") or {}).get("status"), "window_ok": True, "lines": n,
                                        "record": record, "max_per_day": comp.max_per_day(l.get("state"), c)}, "disposition": None, "notes": ""})
    ares = await db[ATTEMPTS].insert_many(attempts)
    for a, _id in zip(attempts, ares.inserted_ids):
        a["_id"] = _id
    await db[BURSTS].update_one({"_id": burst["_id"]}, {"$set": {"attempt_ids": [str(a["_id"]) for a in attempts]}})
    await db[LEADS].update_many({"_id": {"$in": [l["_id"] for l in leads]}}, {"$set": {"status": "calling", "last_attempt_at": now}, "$inc": {"attempts": 1}})
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"status": "dialing", "current_burst_id": str(burst["_id"]), "current_attempt_id": None, "last_activity_at": now, "last_message": None},
                                                       "$inc": {"stats.bursts": 1, "stats.dials": len(attempts)}})
    burst["attempts"] = attempts
    if place_calls:
        await place_burst_calls(db, burst)
    return burst, info


async def place_burst_calls(db, burst: dict):
    client = _client()
    attempts = burst.get("attempts") or await db[ATTEMPTS].find({"burst_id": str(burst["_id"])}).to_list(MAX_LINES)

    async def place(a):
        if client is None:
            await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "failed", "ended_at": _now(), "error": "twilio_disabled"}})
            return
        try:
            call = await asyncio.to_thread(client.calls.create, to=a["phone"], from_=a["caller_id"], url=lead_url(a, "answer"), status_callback=lead_url(a, "status"),
                                           status_callback_event=["initiated", "ringing", "answered", "completed"], machine_detection="Enable", async_amd="true",
                                           async_amd_status_callback=lead_url(a, "amd"), timeout=RING_SECONDS)
            await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"call_sid": call.sid, "status": "ringing"}})
        except Exception as e:
            logger.warning(f"[Dialer] lead call failed {a['phone']}: {e}")
            await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "failed", "ended_at": _now(), "error": str(e)[:200]}})
            await _finalize_lead(db, a, "failed")

    await asyncio.gather(*(place(a) for a in attempts))
    await maybe_end_burst(db, await db[BURSTS].find_one({"_id": burst["_id"]}))


async def cancel_burst_legs(db, burst: dict, except_id: Optional[str] = None):
    async for a in db[ATTEMPTS].find({"burst_id": str(burst["_id"]), "status": {"$in": list(LIVE_ATTEMPT)}}):
        if str(a["_id"]) == except_id:
            continue
        await db[ATTEMPTS].update_one({"_id": a["_id"], "status": {"$in": ["queued", "ringing"]}}, {"$set": {"status": "canceling"}})
        await _update_call(a.get("call_sid"), status="completed")


async def maybe_end_burst(db, burst: Optional[dict]):
    if not burst or burst.get("state") != "ringing":
        return
    live = await db[ATTEMPTS].count_documents({"burst_id": str(burst["_id"]), "status": {"$in": list(LIVE_ATTEMPT) + ["canceling"]}})
    if live == 0:
        await end_burst(db, burst, "no_answer")


BURST_SAY = {"no_answer": "No answer. Press 1 to dial the next.", "voicemail": "That was a voicemail. Press 1 to dial the next.", "timeout": "No one picked up. Press 1 to try the next.",
             "missed": "Missed that one. Press 1 to dial again.", "failed": "Those calls could not be placed. Press 1 to try again."}


async def end_burst(db, burst: dict, reason: str, redirect_rep: bool = True):
    res = await db[BURSTS].find_one_and_update({"_id": burst["_id"], "state": {"$ne": "ended"}}, {"$set": {"state": "ended", "ended_at": _now(), "reason": reason}})
    if not res:
        return
    await cancel_burst_legs(db, burst)
    s = await db[SESSIONS].find_one({"_id": _oid(burst["session_id"])})
    if not s or s.get("status") == "ended" or s.get("current_burst_id") != str(burst["_id"]):
        return
    connected = False
    if res.get("connected_attempt_id"):
        ca = await db[ATTEMPTS].find_one({"_id": _oid(res["connected_attempt_id"])}, {"status": 1})
        connected = bool(ca and ca.get("status") == "connected")
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"status": "wrapup" if connected else "idle", "current_attempt_id": s.get("current_attempt_id") if connected else None, "last_activity_at": _now(), "last_message": BURST_SAY.get(reason)}})
    if redirect_rep and s.get("rep_call_sid"):
        await _update_call(s["rep_call_sid"], url=rep_url(s, "idle", say=reason))


# ── Twilio events: lead legs ──────────────────────────────────────────────────
async def on_lead_answer(db, a: dict, call_sid: str) -> str:
    now = _now()
    burst = await db[BURSTS].find_one({"_id": _oid(a["burst_id"])})
    s = await db[SESSIONS].find_one({"_id": _oid(a["session_id"])})
    c = await db[CAMPAIGNS].find_one({"_id": _oid(a["campaign_id"])})
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"answered_at": now, "call_sid": call_sid or a.get("call_sid"), "call_status": "in-progress"}})
    won = burst and s and s.get("status") != "ended" and await db[BURSTS].find_one_and_update(
        {"_id": burst["_id"], "state": "ringing", "connected_attempt_id": None}, {"$set": {"connected_attempt_id": str(a["_id"]), "state": "connected", "connected_at": now}})
    if not won:
        await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "abandoned", "abandoned": True, "answered_live": True, "abandon_message_at": now}})
        await db[LEADS].update_one({"_id": _oid(a["lead_id"])}, {"$set": {"last_outcome": "abandoned"}})
        if s:
            await db[SESSIONS].update_one({"_id": s["_id"]}, {"$inc": {"stats.abandoned": 1}})
        logger.warning(f"[Dialer] abandoned call {a['phone']} campaign {a['campaign_id']}")
        return twiml_lead_abandon(a, c or {}, s or {})
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "connected", "answered_live": True, "connected_at": now}})
    await db[LEADS].update_one({"_id": _oid(a["lead_id"])}, {"$set": {"status": "wrapup", "last_outcome": "connected"}})
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"status": "connected", "current_attempt_id": str(a["_id"]), "last_activity_at": now, "last_message": None}, "$inc": {"stats.connects": 1}})
    asyncio.create_task(cancel_burst_legs(db, burst, except_id=str(a["_id"])))
    if (c or {}).get("connect_mode") == "press1":
        asyncio.create_task(_update_call(s.get("rep_call_sid"), url=rep_url(s, "accept", a=str(a["_id"]))))
    return twiml_lead_join(s, burst, action=lead_url(a, "after"))


async def on_lead_amd(db, a: dict, answered_by: str):
    machine = (answered_by or "").startswith("machine") or answered_by == "fax"
    upd = {"answered_by": answered_by}
    if machine:
        upd.update({"answered_live": False, "abandoned": False})
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": upd})
    if not machine:
        return
    a = await db[ATTEMPTS].find_one({"_id": a["_id"]})
    c = await db[CAMPAIGNS].find_one({"_id": _oid(a["campaign_id"])}) or {}
    s = await db[SESSIONS].find_one({"_id": _oid(a["session_id"])}) or {}
    if a.get("status") == "abandoned":
        await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "voicemail"}})
        await db[SESSIONS].update_one({"_id": s["_id"]}, {"$inc": {"stats.abandoned": -1}}) if s else None
        await _update_call(a.get("call_sid"), status="completed")
        return
    if a.get("status") != "connected":
        return
    if c.get("voicemail") == "rep":
        await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"voicemail_detected": True}})
        return
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "voicemail", "voicemail_detected": True}})
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$inc": {"stats.voicemails": 1}, "$set": {"last_message": BURST_SAY["voicemail"]}})
    await _update_call(a.get("call_sid"), status="completed")
    burst = await db[BURSTS].find_one({"_id": _oid(a["burst_id"])})
    if burst and c.get("connect_mode") == "press1":
        # the rep is on the accept prompt, pull them back to idle
        await end_burst(db, burst, "voicemail", redirect_rep=True)
    # instant mode: the lead hang-up ends the conference and the rep's <Dial> action returns them to idle with the voicemail line


async def on_lead_status(db, a: dict, call_status: str, form: dict):
    now = _now()
    upd = {"call_status": call_status}
    if call_status == "ringing" and not a.get("ringing_at"):
        upd["ringing_at"] = now
    if call_status == "in-progress" and not a.get("answered_at"):
        upd["answered_at"] = now
    if call_status in TERMINAL_CALL:
        upd["ended_at"] = now
        try:
            upd["duration_s"] = int(form.get("CallDuration") or 0)
        except Exception:
            pass
        if a.get("connected_at"):
            upd["talk_s"] = max(0, int((now - a["connected_at"].replace(tzinfo=timezone.utc)).total_seconds()))
        final = a.get("status")
        if final not in ("connected", "abandoned", "voicemail"):
            final = {"busy": "busy", "no-answer": "no_answer", "failed": "failed", "canceled": "canceled"}.get(call_status, "canceled" if final == "canceling" else "completed")
        upd["status"] = final
        await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": upd})
        await _finalize_lead(db, {**a, **upd}, final)
        await maybe_end_burst(db, await db[BURSTS].find_one({"_id": _oid(a["burst_id"])}))
        return
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": upd})


async def _finalize_lead(db, a: dict, status: str):
    """Lead bookkeeping once a leg is over. Connected legs wait for the rep's disposition."""
    lead = await db[LEADS].find_one({"_id": _oid(a["lead_id"])})
    c = await db[CAMPAIGNS].find_one({"_id": _oid(a["campaign_id"])}) or {}
    if not lead or a.get("disposition"):
        return
    if status == "connected":
        return
    await _retry_or_done(db, lead, c, status)


async def _retry_or_done(db, lead: dict, c: dict, outcome: str, retry_hours: Optional[int] = None):
    if lead.get("status") == "dnc":
        return
    if int(lead.get("attempts") or 0) >= int(c.get("max_attempts") or 3):
        await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"status": "done", "last_outcome": outcome}})
    else:
        await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"status": "queued", "prio": 1, "last_outcome": outcome, "next_attempt_at": _now() + timedelta(hours=retry_hours or int(c.get("retry_hours") or 24))}})


async def on_lead_optout(db, a: dict, digits: str) -> str:
    if digits.strip() == "9":
        await comp.add_dnc(db, a["phone"], "press9", campaign_id=a.get("campaign_id"), note="Pressed 9 on the abandonment message")
        await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"optout_pressed": True}})
        return twiml(_say("You have been added to our do not call list. We will not call again. Goodbye."), "<Hangup/>")
    return twiml("<Hangup/>")


# ── Twilio events: rep leg ────────────────────────────────────────────────────
async def on_rep_answer(db, s: dict) -> str:
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"status": "idle", "rep_answered_at": _now(), "last_activity_at": _now()}})
    q = await ready_count(db, c)
    intro = f"You are in the dialer for {c.get('name', 'your campaign')}. {q['ready']} {'lead is' if q['ready'] == 1 else 'leads are'} ready to call."
    return twiml_rep_idle(s, c, say=intro)


async def on_rep_digit(db, s: dict, digits: str) -> str:
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    d = (digits or "").strip()
    if d == "*":
        await end_session(db, s, "rep_star", hangup_rep=False)
        return twiml(_say("Session finished. Nice work. Goodbye."), "<Hangup/>")
    if d == "2":
        q = await ready_count(db, c)
        return twiml_rep_idle(s, c, say=f"{q['ready']} ready now, {q['waiting_window']} waiting for their calling window.")
    if d != "1":
        return twiml_rep_idle(s, c)
    if s.get("status") == "dialing":
        burst = await db[BURSTS].find_one({"_id": _oid(s.get("current_burst_id"))})
        return twiml_rep_burst(s, c, burst) if burst and burst.get("state") == "ringing" else twiml_rep_idle(s, c)
    if s.get("status") not in ("idle", "wrapup"):
        return twiml_rep_idle(s, c)
    if c.get("status") != "active":
        return twiml_rep_idle(s, c, say="This campaign is paused. Ask your manager to start it again.")
    burst, info = await fire_burst(db, s, c, via="phone", place_calls=False)
    if not burst:
        return twiml_rep_idle(s, c, say=_no_leads_line(info))
    asyncio.create_task(place_burst_calls(db, burst))
    return twiml_rep_burst(s, c, burst)


def _no_leads_line(info: dict) -> str:
    if info.get("skipped_window"):
        return f"Nothing to dial right now. {info['skipped_window']} leads are outside their legal calling window. Press 2 for the count, star to finish."
    return "No leads left to call in this campaign. Press star to finish."


async def dial_from_app(db, s: dict, c: dict) -> dict:
    if s.get("status") not in ("idle", "wrapup"):
        raise ValueError("Finish the current call first")
    if c.get("status") != "active":
        raise ValueError("This campaign is paused")
    if not s.get("rep_call_sid"):
        raise ValueError("Your phone is not connected")
    burst, info = await fire_burst(db, s, c, via="app", place_calls=False)
    if not burst:
        await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"last_message": _no_leads_line(info)}})
        return {"dialed": 0, **info}
    await _update_call(s["rep_call_sid"], url=rep_url(s, "burst", b=str(burst["_id"])))
    asyncio.create_task(place_burst_calls(db, burst))
    return {"dialed": len(burst["attempts"]), "burst_id": str(burst["_id"]), **info}


async def on_rep_burst_twiml(db, s: dict, burst_id: str) -> str:
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    burst = await db[BURSTS].find_one({"_id": _oid(burst_id)})
    if not burst or burst.get("state") == "ended":
        return twiml_rep_idle(s, c)
    return twiml_rep_burst(s, c, burst)


async def on_rep_accept(db, s: dict, attempt_id: str, digits: Optional[str]) -> str:
    """press1 mode: the lead is waiting in the conference; 1 joins the rep, anything else abandons the lead properly."""
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    a = await db[ATTEMPTS].find_one({"_id": _oid(attempt_id)})
    burst = await db[BURSTS].find_one({"_id": _oid(a["burst_id"])}) if a else None
    if not a or not burst or a.get("status") != "connected":
        return twiml_rep_idle(s, c, say="That call already ended. Press 1 to dial the next.")
    if (digits or "").strip() == "1":
        await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"rep_accepted_at": _now()}})
        conf = escape(s.get("conference") or f"dialer-{s['_id']}")
        return twiml(f'<Dial action="{escape(rep_url(s, "after-burst", b=str(burst["_id"])))}" method="POST">'
                     f'<Conference startConferenceOnEnter="true" endConferenceOnExit="true" beep="false"{_record_attrs(s, burst)}>{conf}</Conference></Dial>',
                     f'<Redirect method="POST">{escape(rep_url(s, "idle"))}</Redirect>')
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"status": "abandoned", "abandoned": True, "abandon_message_at": _now(), "abandon_reason": "rep_did_not_accept"}})
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$inc": {"stats.abandoned": 1}})
    await _update_call(a.get("call_sid"), url=lead_url(a, "abandon"))
    await db[BURSTS].update_one({"_id": burst["_id"]}, {"$set": {"state": "ended", "ended_at": _now(), "reason": "missed"}})
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"status": "idle", "current_attempt_id": None, "last_message": BURST_SAY["missed"]}})
    return twiml_rep_idle(s, c, say="missed")


async def on_rep_after_burst(db, s: dict, burst_id: str) -> str:
    """The conference ended (lead hung up, voicemail skipped, or nobody answered)."""
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    burst = await db[BURSTS].find_one({"_id": _oid(burst_id)})
    if burst and burst.get("state") != "ended":
        connected = bool(burst.get("connected_attempt_id"))
        reason = "call_ended" if connected else "no_answer"
        if connected:
            a = await db[ATTEMPTS].find_one({"_id": _oid(burst["connected_attempt_id"])})
            if a and a.get("status") == "voicemail":
                reason = "voicemail"
        await db[BURSTS].update_one({"_id": burst["_id"]}, {"$set": {"state": "ended", "ended_at": _now(), "reason": reason}})
        await cancel_burst_legs(db, burst)
        await db[SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"status": "wrapup" if reason == "call_ended" else "idle", "last_activity_at": _now(), "last_message": BURST_SAY.get(reason)}})
        if reason == "call_ended":
            return twiml_rep_idle(s, c, say="Call ended. Mark the outcome in the app, then press 1 for the next lead.")
        return twiml_rep_idle(s, c, say=reason)
    fresh = await db[SESSIONS].find_one({"_id": s["_id"]}) or s
    return twiml_rep_idle(s, c, say=(fresh.get("last_message") if fresh.get("status") != "ended" else None))


async def on_rep_status(db, s: dict, call_status: str):
    if call_status in TERMINAL_CALL and s.get("status") != "ended":
        await end_session(db, s, "rep_hangup", hangup_rep=False)


async def hangup_current(db, s: dict) -> bool:
    a = await db[ATTEMPTS].find_one({"_id": _oid(s.get("current_attempt_id"))}) if s.get("current_attempt_id") else None
    if not a or a.get("status") != "connected":
        return False
    await _update_call(a.get("call_sid"), status="completed")
    return True


async def end_session(db, s: dict, reason: str, hangup_rep: bool = True):
    res = await db[SESSIONS].find_one_and_update({"_id": s["_id"], "status": {"$ne": "ended"}}, {"$set": {"status": "ended", "ended_at": _now(), "end_reason": reason}})
    if not res:
        return
    if s.get("current_burst_id"):
        burst = await db[BURSTS].find_one({"_id": _oid(s["current_burst_id"])})
        if burst and burst.get("state") != "ended":
            await db[BURSTS].update_one({"_id": burst["_id"]}, {"$set": {"state": "ended", "ended_at": _now(), "reason": "session_ended"}})
            await cancel_burst_legs(db, burst)
            if burst.get("connected_attempt_id"):
                a = await db[ATTEMPTS].find_one({"_id": _oid(burst["connected_attempt_id"])})
                if a and a.get("status") == "connected":
                    await _update_call(a.get("call_sid"), status="completed")
    if hangup_rep:
        await _update_call(s.get("rep_call_sid"), status="completed")
    # connected calls the rep never marked: back into the queue as a plain attempt
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    async for a in db[ATTEMPTS].find({"session_id": str(s["_id"]), "status": "connected", "disposition": None}):
        lead = await db[LEADS].find_one({"_id": _oid(a["lead_id"])})
        if lead and lead.get("status") in ("wrapup", "calling"):
            await _retry_or_done(db, lead, c, "connected_no_disposition")
    await db[LEADS].update_many({"status": "calling", "campaign_id": str(s["campaign_id"]), "last_attempt_at": {"$lte": _now() - timedelta(seconds=BURST_TIMEOUT_S)}},
                                {"$set": {"status": "queued", "prio": 1}})


# ── dispositions ──────────────────────────────────────────────────────────────
async def apply_disposition(db, s: dict, a: dict, key: str, notes: str, callback_at: Optional[datetime], me: dict) -> dict:
    d = DISPO.get(key)
    if not d:
        raise ValueError("Unknown disposition")
    c = await db[CAMPAIGNS].find_one({"_id": _oid(a["campaign_id"])}) or {}
    lead = await db[LEADS].find_one({"_id": _oid(a["lead_id"])})
    if not lead:
        raise ValueError("Lead not found")
    now = _now()
    notes = (notes or "").strip()[:2000]
    await db[ATTEMPTS].update_one({"_id": a["_id"]}, {"$set": {"disposition": key, "notes": notes, "dispositioned_at": now, "callback_at": callback_at}})
    upd = {"disposition": key, "last_outcome": key, "updated_at": now}
    if notes:
        upd["notes"] = (f"{lead.get('notes') or ''}\n{now.strftime('%b %-d')}: {notes}").strip()[:4000]
    if d["outcome"] == "done":
        upd["status"] = "done"
    elif d["outcome"] == "callback":
        upd.update({"status": "callback", "prio": 0, "next_attempt_at": callback_at or now + timedelta(hours=24), "callback_at": callback_at})
    elif d["outcome"] == "dnc":
        upd["status"] = "dnc"
        await comp.add_dnc(db, lead["phone"], "rep", by=str(me["_id"]), campaign_id=str(c.get("_id")), note=notes or "Asked not to be called")
    await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": upd})
    if d["outcome"] == "retry":
        await _retry_or_done(db, await db[LEADS].find_one({"_id": lead["_id"]}), c, key)
    if d.get("promote"):
        cid = await promote_lead(db, await db[LEADS].find_one({"_id": lead["_id"]}), s["user_id"], c, notes)
        if key == "callback" and cid:
            await _callback_task(db, s["user_id"], cid, lead, callback_at or now + timedelta(hours=24), notes)
    await db[SESSIONS].update_one({"_id": s["_id"], "status": "wrapup"}, {"$set": {"status": "idle", "current_attempt_id": None}})
    await db[SESSIONS].update_one({"_id": s["_id"]}, {"$inc": {"stats.dispositions": 1}, "$set": {"last_activity_at": now}})
    if (c.get("ghl") or {}).get("push", True):
        from services import ghl
        asyncio.create_task(ghl.push_outcome(db, c, await db[LEADS].find_one({"_id": lead["_id"]}), await db[ATTEMPTS].find_one({"_id": a["_id"]}), me))
    return await db[LEADS].find_one({"_id": lead["_id"]})


async def promote_lead(db, lead: dict, user_id: str, c: dict, notes: str = "") -> Optional[str]:
    """Interested / call back: the lead becomes a real contact in the rep's book (purchased lists stay out of it until then)."""
    from utils.activity_log import log_activity
    tags = ["Power Dialer", c.get("name") or "Dialer"]
    cid = lead.get("contact_id")
    if not cid:
        existing = await db.contacts.find_one({"user_id": user_id, "phone": lead["phone"], "status": {"$ne": "purged"}}, {"_id": 1})
        if existing:
            cid = str(existing["_id"])
            await db.contacts.update_one({"_id": existing["_id"]}, {"$addToSet": {"tags": {"$each": tags}}, "$set": {"updated_at": _now()}})
        else:
            doc = {"user_id": user_id, "first_name": lead.get("first_name") or lead.get("company") or "Unknown", "last_name": lead.get("last_name") or "", "phone": lead["phone"],
                   "email": lead.get("email") or None, "organization_name": lead.get("company") or None, "employer": lead.get("company") or None, "occupation": lead.get("title") or None,
                   "address_city": lead.get("city") or None, "address_state": lead.get("state"), "tags": tags, "notes": (lead.get("notes") or "")[:4000], "source": "dialer",
                   "ownership_type": "org", "status": "active", "original_user_id": user_id, "created_at": _now(), "updated_at": _now(), "phones": [], "emails": [],
                   "external_ids": {"ghl": lead["ghl_contact_id"]} if lead.get("ghl_contact_id") else {}}
            res = await db.contacts.insert_one(doc)
            cid = str(res.inserted_id)
        await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"contact_id": cid}})
    try:
        await log_activity(db, user_id=user_id, contact_id=cid, event_type="dialer_call", channel="voice",
                           description=f"Power dialer call: {DISPO.get(lead.get('disposition') or '', {}).get('label', 'talked')}{(' - ' + notes) if notes else ''}",
                           ref=f"dialer:{lead['_id']}:{_now().timestamp():.0f}", metadata={"campaign_id": str(c.get("_id")), "lead_id": str(lead["_id"])})
    except Exception as e:
        logger.info(f"[Dialer] activity log skipped: {e}")
    return cid


async def _callback_task(db, user_id: str, contact_id: str, lead: dict, due: datetime, notes: str):
    name = lead_name(lead)
    await db.tasks.insert_one({"user_id": user_id, "contact_id": contact_id, "contact_name": name, "contact_phone": lead["phone"], "type": "manual", "title": f"Call back {name}",
                               "description": (notes or "From the power dialer")[:500], "action_type": "call", "due_date": due, "priority": "high", "status": "pending", "completed": False,
                               "created_at": _now(), "source": "dialer"})


# ── session view for the app ──────────────────────────────────────────────────
STATUS_LINE = {"starting": "Ringing your phone. Pick up to start.", "idle": "Ready. Tap Dial next or press 1 on your phone.", "dialing": "Dialing…",
               "connected": "On the call", "wrapup": "Call ended. How did it go?", "ended": "Session ended"}


async def session_view(db, s: dict) -> dict:
    c = await db[CAMPAIGNS].find_one({"_id": _oid(s["campaign_id"])}) or {}
    burst = await db[BURSTS].find_one({"_id": _oid(s.get("current_burst_id"))}) if s.get("current_burst_id") else None
    legs = await db[ATTEMPTS].find({"burst_id": str(burst["_id"])}).to_list(MAX_LINES) if burst else []
    current = None
    a = await db[ATTEMPTS].find_one({"_id": _oid(s.get("current_attempt_id"))}) if s.get("current_attempt_id") else None
    if not a and s.get("status") in ("wrapup", "idle"):
        a = await db[ATTEMPTS].find_one({"session_id": str(s["_id"]), "status": "connected", "disposition": None}, sort=[("connected_at", -1)])
    if a:
        lead = await db[LEADS].find_one({"_id": _oid(a["lead_id"])})
        current = {"attempt": serialize_attempt(a), "lead": serialize_lead(lead) if lead else None, "needs_disposition": a.get("status") in ("connected", "voicemail") and not a.get("disposition")}
    stats = await campaign_stats(db, c) if c else {}
    return {"id": str(s["_id"]), "status": s.get("status"), "line": STATUS_LINE.get(s.get("status"), ""), "message": s.get("last_message"), "end_reason": s.get("end_reason"),
            "campaign": {"id": str(c.get("_id")), "name": c.get("name"), "connect_mode": c.get("connect_mode"), "lines": c.get("lines"), "script": c.get("script") or "", "seller_name": c.get("seller_name"),
                         "voicemail": c.get("voicemail"), "status": c.get("status")} if c else None,
            "caller_id": s.get("caller_id"), "rep_phone": s.get("rep_phone"), "started_at": _iso(s.get("started_at")), "ended_at": _iso(s.get("ended_at")),
            "stats": {**(s.get("stats") or {}), "lines_effective": stats.get("lines_effective"), "abandon_rate": stats.get("abandon_rate"), "throttled": stats.get("throttled")},
            "burst": {"id": str(burst["_id"]), "state": burst.get("state"), "lines": burst.get("lines"), "record": burst.get("record"), "started_at": _iso(burst.get("started_at")),
                      "legs": [{"attempt_id": str(l["_id"]), "lead_name": l.get("lead_name"), "state": l.get("lead_state"), "status": l.get("status"), "answered_by": l.get("answered_by"), "local_time": l.get("local_time")} for l in legs]} if burst else None,
            "current": current, "queue": await ready_count(db, c) if c else None, "dispositions": DISPOSITIONS}


# ── scheduler sweep ───────────────────────────────────────────────────────────
async def sweep(db):
    await ensure_indexes(db)
    now = _now()
    async for b in db[BURSTS].find({"state": "ringing", "started_at": {"$lte": now - timedelta(seconds=BURST_TIMEOUT_S)}}):
        await end_burst(db, b, "timeout")
    async for s in db[SESSIONS].find({"status": "starting", "started_at": {"$lte": now - timedelta(seconds=START_TIMEOUT_S)}}):
        await end_session(db, s, "rep_no_answer")
    async for s in db[SESSIONS].find({"status": {"$in": ["idle", "wrapup"]}, "last_activity_at": {"$lte": now - timedelta(minutes=IDLE_TIMEOUT_MIN)}}):
        await end_session(db, s, "idle_timeout")
    async for s in db[SESSIONS].find({"status": "connected", "last_activity_at": {"$lte": now - timedelta(hours=3)}}):
        await end_session(db, s, "stale")


# ── TwiML ─────────────────────────────────────────────────────────────────────
def twiml(*parts: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + "</Response>"


def _say(text: str) -> str:
    from services.speech import speakable
    return f'<Say voice="Polly.Joanna-Neural">{escape(speakable(text))}</Say>'


def _qs(params: dict) -> str:
    return "&".join(f"{k}={v}" for k, v in params.items() if v is not None)


def rep_url(s: dict, action: str, **extra) -> str:
    return f"{_app_url()}/api/webhooks/dialer/rep/{action}?{_qs({'s': str(s['_id']), 't': s['token'], **extra})}"


def lead_url(a: dict, action: str, **extra) -> str:
    return f"{_app_url()}/api/webhooks/dialer/lead/{action}?{_qs({'a': str(a['_id']), 't': a['token'], **extra})}"


def ringback_url() -> str:
    return f"{_app_url()}/api/webhooks/dialer/audio/ringback"


def _record_attrs(s: dict, burst: dict) -> str:
    if not burst.get("record"):
        return ""
    return f' record="record-from-start" recordingStatusCallback="{escape(rep_url(s, "recording", b=str(burst["_id"])))}" recordingStatusCallbackMethod="POST"'


def twiml_rep_idle(s: dict, c: dict, say: Optional[str] = None, quiet: bool = False) -> str:
    lines = int(c.get("lines") or 1)
    parts = []
    if say:
        parts.append(_say(BURST_SAY.get(say, say)))
    action = escape(rep_url(s, "digit"))
    if quiet:
        gather = f'<Gather numDigits="1" timeout="55" action="{action}" method="POST"><Pause length="55"/></Gather>'
    else:
        prompt = f"Press 1 to dial the next {'lead' if lines == 1 else str(lines) + ' leads'}. Press 2 for the count, star to finish."
        gather = f'<Gather numDigits="1" timeout="20" action="{action}" method="POST">{_say(prompt)}</Gather>'
    return twiml(*parts, gather, f'<Redirect method="POST">{escape(rep_url(s, "idle", quiet=1))}</Redirect>')


def twiml_rep_burst(s: dict, c: dict, burst: dict) -> str:
    n = len(burst.get("attempt_ids") or burst.get("attempts") or []) or burst.get("lines") or 1
    intro = _say(f"Dialing {n}." if n > 1 else "Dialing.")
    if c.get("connect_mode") == "press1":
        gather = (f'<Gather numDigits="1" timeout="{RING_SECONDS + 15}" action="{escape(rep_url(s, "digit"))}" method="POST">{intro}'
                  f'<Play loop="8">{escape(ringback_url())}</Play></Gather>')
        return twiml(gather, f'<Redirect method="POST">{escape(rep_url(s, "idle"))}</Redirect>')
    conf = escape(s.get("conference") or f"dialer-{s['_id']}")
    dial = (f'<Dial action="{escape(rep_url(s, "after-burst", b=str(burst["_id"])))}" method="POST">'
            f'<Conference startConferenceOnEnter="false" endConferenceOnExit="true" beep="false" waitUrl="{escape(ringback_url())}" waitMethod="GET"{_record_attrs(s, burst)}>{conf}</Conference></Dial>')
    return twiml(intro, dial, f'<Redirect method="POST">{escape(rep_url(s, "idle"))}</Redirect>')


def twiml_rep_accept(s: dict, a: dict) -> str:
    first = (a.get("lead_name") or "Someone").split(" ")[0]
    gather = f'<Gather numDigits="1" timeout="{ACCEPT_TIMEOUT_S}" action="{escape(rep_url(s, "accept-digit", a=str(a["_id"])))}" method="POST">{_say(f"{first} answered. Press 1.")}</Gather>'
    return twiml(gather, f'<Redirect method="POST">{escape(rep_url(s, "accept-digit", a=str(a["_id"]), timeout=1))}</Redirect>')


def twiml_lead_join(s: dict, burst: dict, action: str) -> str:
    conf = escape(s.get("conference") or f"dialer-{s['_id']}")
    return twiml(f'<Dial action="{escape(action)}" method="POST"><Conference startConferenceOnEnter="true" endConferenceOnExit="true" beep="false">{conf}</Conference></Dial>', "<Hangup/>")


def twiml_lead_abandon(a: dict, c: dict, s: dict) -> str:
    msg = comp.abandon_message(c.get("seller_name") or "our team", a.get("caller_id") or s.get("caller_id") or "")
    gather = f'<Gather numDigits="1" timeout="6" action="{escape(lead_url(a, "optout"))}" method="POST">{_say(msg)}</Gather>'
    return twiml(gather, _say("Thank you. Goodbye."), "<Hangup/>")


def twiml_ringback() -> str:
    return twiml(f'<Play loop="10">{escape(ringback_url())}</Play>')


_RINGBACK: Optional[bytes] = None


def ringback_wav() -> bytes:
    """US ringback: 440+480 Hz, 2 s on / 4 s off, 8 kHz mono 16-bit."""
    global _RINGBACK
    if _RINGBACK is None:
        rate, frames = 8000, []
        for i in range(rate * 6):
            t = i / rate
            v = 0.28 * (math.sin(2 * math.pi * 440 * t) + math.sin(2 * math.pi * 480 * t)) if t < 2.0 else 0.0
            frames.append(struct.pack("<h", int(max(-1, min(1, v)) * 32767)))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(frames))
        _RINGBACK = buf.getvalue()
    return _RINGBACK
