"""Website widget (per store): the one-line script a dealership drops on its site, its look, its doors (Text us / Call me now),
routing, and the public handlers behind it. Leads go through the normal internet-lead pipeline (process_inbound_lead)."""
import asyncio
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

COLL = "widgets"
EVENTS = "widget_events"
MANAGER_ROLES = {"super_admin", "admin", "org_admin", "store_manager", "manager"}
ICON_CHOICES = ("chat", "text", "phone", "menu", "sparkles", "image")
DOORS = ("text", "call", "chat")
HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _now():
    return datetime.now(timezone.utc)


def app_url() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def hex_or(v, default: str) -> str:
    m = HEX.match(str(v or "").strip())
    return f"#{m.group(1).upper()}" if m else default


def contrast_text(bg: str) -> str:
    """White or near-black text for a bubble color (WCAG luminance)."""
    m = HEX.match(bg or "")
    if not m:
        return "#FFFFFF"
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#111111" if lum > 0.6 else "#FFFFFF"


PLAYBOOKS = {
    "dealership": {"goal": "Book a test drive",
                   "questions": ["What are you looking for: new or pre-owned, and any model in mind?", "Do you have a trade-in?", "When are you hoping to be driving it?", "Will this be financed, leased or paid outright?"],
                   "pitch": "Easiest next step is a quick test drive so you can feel it for yourself. Want me to grab you a time?"},
    "business": {"goal": "Book a demo",
                 "questions": ["What kind of business are you, and how big is the sales team?", "What are you using today for follow-up: a CRM, texting, spreadsheets?", "What is the one thing you would want fixed first?", "Who would be on the demo with you: just you, or a manager or owner too?"],
                 "pitch": "The fastest way to see if it fits is a 20-minute demo on your own numbers. Want me to grab you a time?"},
}


def playbook_for(cfg: dict) -> dict:
    """The funnel Jessi follows: owner's playbook with blanks filled from the mode's defaults."""
    kb = cfg["kb"]
    pb = kb.get("playbook") or {}
    d = PLAYBOOKS["business" if kb.get("mode") == "business" else "dealership"]
    return {"on": pb.get("on", True), "goal": pb.get("goal") or d["goal"], "questions": pb.get("questions") or d["questions"],
            "offer_after": int(pb.get("offer_after") or 3), "pitch": pb.get("pitch") or d["pitch"]}


STARTERS = {
    "dealership": ["What are your hours?", "Is it still available?", "Book a test drive"],
    "business": ["What does it cost?", "How does it work?", "Book a demo"],
}

DEFAULTS = {
    "appearance": {
        "icon": "text", "icon_url": "", "label_on": True, "label": "Text Us", "position": "right", "offset_x": 20, "offset_y": 20,
        "bubble_color": "#2196F3", "text_color": "#FFFFFF", "panel_color": "#FFFFFF", "panel_text": "#111111", "radius": 20,
        "greeting_on": False, "greeting": "Hi there! Have a question? Text us and a real person replies in minutes.", "greeting_delay_s": 4,
        "avatar_url": "", "font": "inherit", "hide_mobile": False, "tuck_on": True, "page_rules": [],
    },
    "doors": {
        "text": {"on": True, "label": "Text us", "intro": "Text with a real person. We usually reply within a few minutes.", "button": "Send text",
                 "success": "Check your phone, we just texted you.", "ask_message": True},
        "call": {"on": True, "label": "Call me now", "intro": "Enter your number and one of us calls you back right away.", "button": "Call me now",
                 "success_ringing": "Ringing the team…", "success_connected": "Connecting you to {rep}…",
                 "missed": "Everyone is tied up this second. We just texted you instead.", "after_hours": "We're closed right now. We just texted you and we'll call when we open."},
        "chat": {"on": True, "label": "Chat now", "intro": "Ask Jessi about hours, what's in stock or the store. A real person is one tap away.", "button": "Start chat",
                 "placeholder": "Type your question", "human": "Talk to a person", "booking_on": True, "booking_label": "Book a visit", "meeting_link": "", "notify_reps": True},
    },
    "kb": {"mode": "dealership", "welcome": "", "specials": [], "never": [], "notes": "", "share_listed_prices": False, "starters": [],
           "playbook": {"on": True, "goal": "", "questions": [], "offer_after": 3, "pitch": ""}, "scripts": [], "extra_urls": []},
    "copy": {
        "title": "How can we help?", "name_label": "Name", "phone_label": "Mobile number", "message_label": "Message (optional)",
        "optin": "By submitting, you agree to receive texts from {store}. Message and data rates may apply. Reply STOP to opt out.",
    },
    "routing": {
        "call_user_ids": [], "text_send_from": "store_line", "inbox_id": "", "assignment_method": "round_robin", "notify_all": True,
        "ring_seconds": 40, "intake_text": "Hi {{first_name}}, thanks for texting {{store_name}}! A real person is jumping on this now. What can we help with?",
        "call_intake_text": "Hi {{first_name}}, this is {{store_name}}. We're calling you right now from this number, pick up and let's talk!",
        "after_hours_text": "Hi {{first_name}}, thanks for reaching out to {{store_name}}. We're closed right now but we'll be on this first thing when we open. Feel free to reply here in the meantime.",
        "missed_text": "Hi {{first_name}}, {{store_name}} here. Sorry, everyone was on the phone when you asked for a call. Reply here or tell us a good time and we'll call you right back.",
        "chat_intake_text": "Hi {{first_name}}, {{store_name}} here. Jessi handed your web chat to me, a real person. I'm reading it now, what's the best way to help?",
    },
    "hours": {"mode": "store"},
}


def _merge(base: dict, over: Optional[dict]) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif v is not None:
            out[k] = v
    return out


def normalize_config(cfg: dict) -> dict:
    """Validate what the admin saved; unknown keys drop, bad values fall back."""
    c = _merge(DEFAULTS, {k: cfg.get(k) for k in DEFAULTS if isinstance(cfg.get(k), dict)})
    a = c["appearance"]
    a["icon"] = a["icon"] if a["icon"] in ICON_CHOICES else "text"
    a["position"] = "left" if a["position"] == "left" else "right"
    a["tuck_on"] = a.get("tuck_on") is not False
    a["bubble_color"] = hex_or(a["bubble_color"], "#2196F3")
    a["text_color"] = hex_or(a["text_color"], contrast_text(a["bubble_color"]))
    a["panel_color"] = hex_or(a["panel_color"], "#FFFFFF")
    a["panel_text"] = hex_or(a["panel_text"], "#111111")
    a["label"] = str(a["label"] or "")[:30]
    a["greeting"] = str(a["greeting"] or "")[:200]
    a["radius"] = max(0, min(int(a.get("radius") or 20), 32))
    a["offset_x"] = max(0, min(int(a.get("offset_x") or 20), 120))
    a["offset_y"] = max(0, min(int(a.get("offset_y") or 20), 200))
    a["greeting_delay_s"] = max(0, min(int(a.get("greeting_delay_s") if a.get("greeting_delay_s") is not None else 4), 120))
    rules = []
    for r_ in (a.get("page_rules") or [])[:12]:
        if isinstance(r_, dict) and str(r_.get("match") or "").strip() and str(r_.get("greeting") or "").strip():
            rules.append({"match": str(r_["match"]).strip()[:120], "greeting": str(r_["greeting"]).strip()[:200],
                          "door": r_.get("door") if r_.get("door") in ("text", "call", "chat") else ""})
    a["page_rules"] = rules
    kb = c["kb"]
    kb["mode"] = "business" if kb.get("mode") == "business" else "dealership"
    kb["welcome"] = str(kb.get("welcome") or "")[:300]
    kb["notes"] = str(kb.get("notes") or "")[:2000]
    kb["share_listed_prices"] = bool(kb.get("share_listed_prices"))
    kb["never"] = [str(x).strip()[:80] for x in (kb.get("never") or []) if str(x).strip()][:20]
    kb["starters"] = [str(x).strip()[:60] for x in (kb.get("starters") or []) if str(x).strip()][:3]
    pb = kb.get("playbook") if isinstance(kb.get("playbook"), dict) else {}
    kb["playbook"] = {"on": pb.get("on") is not False, "goal": str(pb.get("goal") or "").strip()[:80],
                      "questions": [str(x).strip()[:160] for x in (pb.get("questions") or []) if str(x).strip()][:5],
                      "offer_after": max(1, min(int(pb.get("offer_after") or 3), 5)), "pitch": str(pb.get("pitch") or "").strip()[:300]}
    scripts = []
    for sc in (kb.get("scripts") or [])[:25]:
        if isinstance(sc, dict) and str(sc.get("q") or "").strip() and str(sc.get("a") or "").strip():
            scripts.append({"q": str(sc["q"]).strip()[:160], "a": str(sc["a"]).strip()[:600]})
    kb["scripts"] = scripts
    kb["extra_urls"] = [str(x).strip()[:300] for x in (kb.get("extra_urls") or []) if str(x).strip().lower().startswith(("http://", "https://"))][:10]
    ml = str(c["doors"]["chat"].get("meeting_link") or "").strip()[:300]
    c["doors"]["chat"]["meeting_link"] = ml if ml.lower().startswith(("http://", "https://")) else ""
    specials = []
    for sp in (kb.get("specials") or [])[:20]:
        if isinstance(sp, dict) and str(sp.get("title") or "").strip():
            ends = str(sp.get("ends") or "").strip()[:10]
            specials.append({"id": str(sp.get("id") or secrets.token_hex(4)), "title": str(sp["title"]).strip()[:80], "details": str(sp.get("details") or "").strip()[:300],
                             "ends": ends if re.match(r"^\d{4}-\d{2}-\d{2}$", ends) else ""})
    kb["specials"] = specials
    r = c["routing"]
    r["call_user_ids"] = [str(u) for u in (r.get("call_user_ids") or []) if u][:25]
    r["text_send_from"] = "rep_line" if r.get("text_send_from") == "rep_line" else "store_line"
    r["assignment_method"] = r["assignment_method"] if r["assignment_method"] in ("round_robin", "jump_ball", "weighted_round_robin") else "round_robin"
    r["ring_seconds"] = max(15, min(int(r.get("ring_seconds") or 40), 90))
    c["hours"]["mode"] = "always" if c["hours"].get("mode") == "always" else "store"
    for d in ("text", "call", "chat"):
        c["doors"][d]["on"] = bool(c["doors"][d].get("on"))
        for k, v in list(c["doors"][d].items()):
            if isinstance(v, str):
                c["doors"][d][k] = v[:240]
    c["doors"]["chat"]["booking_on"] = bool(c["doors"]["chat"].get("booking_on", True))
    c["doors"]["chat"]["notify_reps"] = bool(c["doors"]["chat"].get("notify_reps", True))
    for k, v in list(c["copy"].items()):
        if isinstance(v, str):
            c["copy"][k] = v[:400]
    return c


def new_key() -> str:
    return secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")[:8]


def scope_query(me: dict) -> dict:
    role = me.get("role")
    if role == "super_admin":
        return {}
    if role == "org_admin" and me.get("organization_id"):
        return {"organization_id": str(me["organization_id"])}
    stores = [str(s) for s in ([me.get("store_id")] + list(me.get("store_ids") or [])) if s]
    return {"store_id": {"$in": stores}} if stores else {"created_by": str(me["_id"])}


def can_manage(me: dict) -> bool:
    return me.get("role") in MANAGER_ROLES


def snippet(w: dict) -> str:
    return f'<script src="{app_url()}/api/w/{w["key"]}.js" async></script>'


def serialize(w: dict, store: Optional[dict] = None) -> dict:
    cfg = normalize_config(w)
    return {
        "id": str(w["_id"]), "key": w["key"], "name": w.get("name"), "store_id": w.get("store_id"), "store_name": (store or {}).get("name") or w.get("store_name"),
        "is_active": w.get("is_active", True), "domains": w.get("domains") or [], "lead_source_id": w.get("lead_source_id"),
        **cfg,
        "snippet": snippet(w), "script_url": f"{app_url()}/api/w/{w['key']}.js",
        "installed": bool(w.get("last_seen_at")), "last_seen_at": w["last_seen_at"].isoformat() if w.get("last_seen_at") else None,
        "last_seen_host": w.get("last_seen_host"),
        "stats": w.get("stats") or {}, "created_at": w["created_at"].isoformat() if w.get("created_at") else None,
        "updated_at": w["updated_at"].isoformat() if w.get("updated_at") else None,
    }


def public_config(w: dict, store: Optional[dict], preview: bool = False) -> dict:
    cfg = normalize_config(w)
    out = {"key": w["key"], "api": f"{app_url()}/api/w/{w['key']}", "store_name": (store or {}).get("name") or w.get("store_name") or "",
           "appearance": cfg["appearance"], "doors": {d: {k: v for k, v in cfg["doors"][d].items()} for d in cfg["doors"]}, "copy": cfg["copy"], "preview": preview}
    out["chat_mode"] = cfg["kb"]["mode"]
    out["starters"] = cfg["kb"]["starters"] or STARTERS[cfg["kb"]["mode"]]
    if cfg["kb"]["mode"] == "business" and out["doors"]["chat"].get("booking_label") in ("", None, DEFAULTS["doors"]["chat"]["booking_label"]):
        out["doors"]["chat"]["booking_label"] = "Book a demo"
    if preview:
        out["chat_welcome"] = cfg["kb"]["welcome"]
    return out


# ---------------------------------------------------------------- lead source behind the widget
async def sync_lead_source(db, w: dict, store: Optional[dict]) -> str:
    """Every widget owns one lead_sources doc so Text us / Call me now ride the normal intake pipeline (ladder, timing, CRM push)."""
    cfg = normalize_config(w)
    r = cfg["routing"]
    store_name = (store or {}).get("name") or "our team"

    def _st(t: str) -> str:
        return (t or "").replace("{{store_name}}", store_name).replace("{store_name}", store_name)

    doc = {
        "name": f"Website Widget · {w.get('name') or (store or {}).get('name') or w['key']}",
        "description": "Created by the website widget. Edit routing from Tools > Leads > Website Widget.",
        "store_id": w.get("store_id"), "organization_id": w.get("organization_id"),
        "widget_id": str(w["_id"]), "kind": "website_widget",
        "workflow_user_ids": r["call_user_ids"], "assignment_method": r["assignment_method"], "assignment_method_override": True,
        "inbox_id": r["inbox_id"] if r["text_send_from"] == "store_line" and r.get("inbox_id") else None,
        "intake_text": _st(r["intake_text"]), "after_hours_text": _st(r["after_hours_text"]), "notify_all_on_intake": bool(r["notify_all"]),
        "is_active": w.get("is_active", True), "updated_at": _now(),
    }
    existing = await db.lead_sources.find_one({"widget_id": str(w["_id"])}) if w.get("_id") else None
    if existing:
        await db.lead_sources.update_one({"_id": existing["_id"]}, {"$set": doc})
        return str(existing["_id"])
    doc.update({"api_key": secrets.token_urlsafe(32), "created_at": _now(), "created_by": w.get("created_by")})
    res = await db.lead_sources.insert_one(doc)
    return str(res.inserted_id)


async def load(db, key: str) -> Optional[dict]:
    return await db[COLL].find_one({"key": key, "is_active": {"$ne": False}})


async def store_of(db, w: dict) -> dict:
    sid = w.get("store_id")
    return (await db.stores.find_one({"_id": ObjectId(str(sid))}) if sid and ObjectId.is_valid(str(sid)) else None) or {}


# ---------------------------------------------------------------- abuse guard
_hits: dict = {}
DAILY_PER_PHONE = 6       # texts + calls one visitor number can trigger per day across all widgets
DAILY_PER_WIDGET = 300    # outbound texts / calls one widget can trigger per day


def allow(ip: str, bucket: str, limit: int, window_s: int = 60) -> bool:
    now = time.time()
    k = f"{bucket}:{ip}"
    arr = [t for t in _hits.get(k, []) if now - t < window_s]
    if len(arr) >= limit:
        _hits[k] = arr
        return False
    arr.append(now)
    _hits[k] = arr
    if len(_hits) > 5000:
        for kk in list(_hits)[:1000]:
            _hits.pop(kk, None)
    return True


def clean_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"+1{d}" if len(d) == 10 else ""


def split_name(n: str) -> tuple:
    parts = (n or "").strip().split()
    return (parts[0] if parts else "Website", " ".join(parts[1:]) if len(parts) > 1 else "Visitor")


def host_of(url: str) -> str:
    m = re.match(r"https?://([^/?#]+)", url or "")
    return (m.group(1) if m else "").lower().replace("www.", "")


def domain_ok(w: dict, page: str, origin: str = "") -> bool:
    """When the owner listed domains, the browser Origin/Referer (when present) and the reported page must both belong to one of them."""
    allowed = [d.lower().replace("www.", "").strip() for d in (w.get("domains") or []) if d.strip()]
    if not allowed:
        return True

    def ok(u: str) -> bool:
        host = host_of(u)
        return any(host == d or host.endswith("." + d) for d in allowed)
    return ok(page) and (not origin or ok(origin))


async def touch(db, w: dict, page: str, kind: str):
    upd = {"$set": {"last_seen_at": _now(), "last_seen_host": host_of(page) or w.get("last_seen_host")}}
    field = {"load": "loads", "open": "opens", "greeting": "greetings", "lead": "leads", "chat": "chat_starts"}.get(kind)
    if field:
        upd["$inc"] = {f"stats.{field}": 1}
    await db[COLL].update_one({"_id": w["_id"]}, upd)


async def log_event(db, w: dict, kind: str, body: dict):
    await touch(db, w, body.get("page") or "", kind)
    await db[EVENTS].insert_one({"widget_id": str(w["_id"]), "key": w["key"], "kind": kind, "door": body.get("door") if body.get("door") in DOORS else None,
                                 "page": (body.get("page") or "")[:500], "title": (body.get("title") or "")[:200], "visitor": (body.get("visitor") or "")[:64], "at": _now()})


# ---------------------------------------------------------------- Text us
async def text_lead(db, w: dict, body: dict, ip: str) -> dict:
    name, phone = (body.get("name") or "").strip()[:80], clean_phone(body.get("phone") or "")
    if body.get("website"):
        return {"ok": True, "message": "Check your phone, we just texted you."}
    if not name or not phone:
        raise ValueError("Please add your name and a 10 digit mobile number.")
    if not allow(ip, "lead", 5) or not allow(phone, "lead_phone", 2, 120):
        raise ValueError("Please wait a minute before sending another message.")
    if not allow(phone, "lead_phone_day", DAILY_PER_PHONE, 86400) or not allow(w["key"], "lead_widget_day", DAILY_PER_WIDGET, 86400):
        raise ValueError("This number has reached today's limit. Please call us instead.")
    store = await store_of(db, w)
    source = await db.lead_sources.find_one({"_id": ObjectId(w["lead_source_id"])}) if w.get("lead_source_id") else None
    if not source:
        w["lead_source_id"] = await sync_lead_source(db, w, store)
        await db[COLL].update_one({"_id": w["_id"]}, {"$set": {"lead_source_id": w["lead_source_id"]}})
        source = await db.lead_sources.find_one({"_id": ObjectId(w["lead_source_id"])})
    first, last = split_name(name)
    page = (body.get("page") or "")[:500]
    msg = (body.get("message") or "").strip()[:1000]
    normalized = {
        "first_name": first, "last_name": last, "full_name": name, "phone": phone,
        "comments": (msg + (f"\n(From {page})" if page else "")).strip() or f"Texted from the website{f' ({host_of(page)})' if page else ''}",
        "source_name": source.get("name"), "extra_fields": {"widget_key": w["key"], "door": "text", "page_url": page, "page_title": (body.get("title") or "")[:200], "visitor": (body.get("visitor") or "")[:64]},
    }
    from routers.lead_intake import process_inbound_lead
    res = await process_inbound_lead(normalized, source, db, raw_body="")
    await log_event(db, w, "lead", {**body, "door": "text"})
    await db[COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.text_leads": 1}})
    cfg = normalize_config(w)
    return {"ok": True, "message": cfg["doors"]["text"]["success"], "lead_id": res.get("lead_id"), "after_hours": res.get("is_after_hours")}


# ---------------------------------------------------------------- stats
async def stats(db, w: dict) -> dict:
    sid = w.get("lead_source_id")
    since = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    week = since - timedelta(days=6)
    leads_week = await db.inbound_leads.count_documents({"source_id": sid, "created_at": {"$gte": week}}) if sid else 0
    calls = await db.widget_call_requests.find({"widget_id": str(w["_id"])}, {"status": 1, "seconds_to_connect": 1, "created_at": 1}).sort("created_at", -1).limit(200).to_list(200)
    connected = [c for c in calls if c.get("status") == "connected"]
    avg = round(sum(c.get("seconds_to_connect") or 0 for c in connected) / len(connected), 1) if connected else None
    by_day = {}
    async for e in db[EVENTS].find({"widget_id": str(w["_id"]), "at": {"$gte": week}}, {"kind": 1, "at": 1}):
        d = e["at"].strftime("%a")
        by_day.setdefault(d, {"loads": 0, "opens": 0, "leads": 0})
        if e["kind"] in ("load", "open", "lead"):
            by_day[d][e["kind"] + "s"] += 1
    s = w.get("stats") or {}
    return {"loads": s.get("loads", 0), "opens": s.get("opens", 0), "text_leads": s.get("text_leads", 0), "call_requests": len(calls) if len(calls) < 200 else s.get("call_requests", len(calls)),
            "chats": s.get("chats", 0), "chat_handoffs": s.get("chat_handoffs", 0), "chat_bookings": s.get("chat_bookings", 0),
            "calls_connected": len(connected), "calls_missed": len([c for c in calls if c.get("status") in ("missed", "missed_customer")]),
            "calls_after_hours": len([c for c in calls if c.get("status") == "after_hours"]), "avg_seconds_to_connect": avg,
            "leads_7d": leads_week, "by_day": by_day, "open_rate": round(100 * s.get("opens", 0) / s["loads"]) if s.get("loads") else None}


def page_path(url: str) -> str:
    m = re.match(r"https?://[^/?#]+(/[^?#]*)?", url or "")
    return (m.group(1) or "/")[:80] if m else ((url or "").split("?")[0][:80] or "/")


async def door_stats(db, w: dict, days: int = 7) -> dict:
    """Per door, for the window: how often it was opened, what came out of it, and which pages sent people through it."""
    from datetime import timedelta
    wid = str(w["_id"])
    since = _now() - timedelta(days=days) if days > 0 else None
    doors = {d: {"views": 0, "leads": 0, "pages": {}} for d in DOORS}
    async for e in db[EVENTS].find({"widget_id": wid, "kind": {"$in": ["door", "lead"]}, **({"at": {"$gte": since}} if since else {})}, {"kind": 1, "door": 1, "page": 1}):
        d = e.get("door")
        if d not in doors:
            continue
        if e["kind"] == "door":
            doors[d]["views"] += 1
        else:
            doors[d]["leads"] += 1
            p = page_path(e.get("page"))
            doors[d]["pages"][p] = doors[d]["pages"].get(p, 0) + 1
    win = {"widget_id": wid, **({"created_at": {"$gte": since}} if since else {})}
    calls = await db.widget_call_requests.find(win, {"status": 1, "seconds_to_connect": 1}).to_list(5000)
    connected = [c for c in calls if c.get("status") == "connected"]
    doors["call"].update({"requests": len(calls), "connected": len(connected), "missed": len([c for c in calls if c.get("status") in ("missed", "missed_customer")]),
                          "after_hours": len([c for c in calls if c.get("status") == "after_hours"]),
                          "avg_seconds": round(sum(c.get("seconds_to_connect") or 0 for c in connected) / len(connected), 1) if connected else None})
    chats = await db.widget_chats.find(win, {"status": 1, "booking": 1, "rep_user_id": 1, "contact_id": 1}).to_list(5000)
    doors["chat"].update({"chats": len(chats), "handed_off": len([c for c in chats if c.get("status") == "handed_off" or c.get("contact_id")]),
                          "bookings": len([c for c in chats if c.get("booking")]), "taken_over": len([c for c in chats if c.get("rep_user_id")])})
    doors["call"]["leads"], doors["chat"]["leads"] = doors["call"]["requests"], doors["chat"]["handed_off"]
    for d in DOORS:
        top = sorted(doors[d]["pages"].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        doors[d]["pages"] = [{"path": p, "n": n} for p, n in top]
        doors[d]["rate"] = round(100 * doors[d]["leads"] / doors[d]["views"]) if doors[d]["views"] else None
    total = sum(doors[d]["leads"] for d in DOORS)
    return {"days": days, "total_leads": total, "busiest": max(DOORS, key=lambda d: (doors[d]["leads"], doors[d]["views"])) if total or any(doors[d]["views"] for d in DOORS) else None, "doors": doors}


# ---------------------------------------------------------------- "Match my website": pull the site's palette
CSS_COLOR = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
BRAND_HINT = re.compile(r"(primary|brand|accent|theme|btn|button|nav|header|cta|link)", re.I)


def _to_hex(m) -> Optional[str]:
    if m.group(1):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h.upper()
    try:
        r, g, b = (min(255, int(m.group(i))) for i in (2, 3, 4))
        return "#%02X%02X%02X" % (r, g, b)
    except (TypeError, ValueError):
        return None


def _boring(hx: str) -> bool:
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    return (mx - mn) < 22 or mx < 40 or mn > 235   # greys, near black, near white


async def site_palette(url: str) -> dict:
    from services.safe_fetch import safe_client
    if not re.match(r"^https?://", url or ""):
        url = "https://" + (url or "").strip()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; iMOS-WidgetPalette/1.0)"}
    found: dict = {}
    labels: dict = {}

    def add(hx, weight, label):
        if not hx or _boring(hx):
            return
        found[hx] = found.get(hx, 0) + weight
        labels.setdefault(hx, label)

    async with safe_client(timeout=10, follow_redirects=True, headers=headers) as client:
        r = await client.get(url)
        html = r.text[:600000]
        base = str(r.url)
        for m in re.finditer(r'<meta[^>]+name=["\'](theme-color|msapplication-TileColor)["\'][^>]+content=["\']([^"\']+)', html, re.I):
            for cm in CSS_COLOR.finditer(m.group(2)):
                add(_to_hex(cm), 60, "theme color")
        css_blobs = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)
        hrefs = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)', html, re.I) + re.findall(r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)["\']', html, re.I)
        seen = set()
        for href in hrefs[:6]:
            if href in seen:
                continue
            seen.add(href)
            try:
                from urllib.parse import urljoin
                cr = await client.get(urljoin(base, href))
                if cr.status_code == 200:
                    css_blobs.append(cr.text[:400000])
            except Exception:
                pass
        for blob in css_blobs:
            for rule in re.finditer(r"([^{}]{0,160})\{([^{}]{0,800})\}", blob):
                sel, body_ = rule.group(1), rule.group(2)
                hint = 2 if BRAND_HINT.search(sel) or BRAND_HINT.search(body_) else 1
                for cm in CSS_COLOR.finditer(body_):
                    prop_ctx = body_[max(0, cm.start() - 40):cm.start()]
                    w = 3 if re.search(r"background(-color)?\s*:", prop_ctx) else 1
                    add(_to_hex(cm), hint * w, "buttons & backgrounds" if w == 3 else "site colors")
        for m in re.finditer(r'style=["\']([^"\']+)', html, re.I):
            for cm in CSS_COLOR.finditer(m.group(1)):
                add(_to_hex(cm), 1, "site colors")
        # the logo's own colors
        logo = None
        for m in re.finditer(r"<img[^>]+>", html, re.I):
            tag = m.group(0)
            if re.search(r"logo", tag, re.I):
                src = re.search(r'src=["\']([^"\']+)', tag)
                if src and not src.group(1).startswith("data:"):
                    logo = src.group(1)
                    break
        if not logo:
            og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
            logo = og.group(1) if og else None
        logo_hex = []
        if logo:
            try:
                from urllib.parse import urljoin
                from io import BytesIO
                from PIL import Image
                ir = await client.get(urljoin(base, logo))
                if ir.status_code == 200 and len(ir.content) < 3_000_000:
                    img = Image.open(BytesIO(ir.content)).convert("RGBA")
                    img.thumbnail((160, 160))
                    px = [p for p in img.getdata() if p[3] > 200]
                    if px:
                        small = Image.new("RGB", (len(px), 1))
                        small.putdata([p[:3] for p in px])
                        q = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
                        pal = q.getpalette()[:18]
                        counts = sorted(q.getcolors() or [], reverse=True)
                        for cnt, idx in counts:
                            hx = "#%02X%02X%02X" % tuple(pal[idx * 3: idx * 3 + 3])
                            if not _boring(hx):
                                logo_hex.append(hx)
                                add(hx, 25 + cnt / max(1, len(px)) * 30, "logo")
            except Exception as e:
                logger.debug(f"[Widget] logo palette skipped: {e}")
    ranked = sorted(found.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for hx, score in ranked:
        if all(_dist(hx, o["hex"]) > 40 for o in out):
            out.append({"hex": hx, "label": labels.get(hx, "site colors"), "text": contrast_text(hx)})
        if len(out) >= 8:
            break
    return {"url": url, "swatches": out, "logo": logo, "host": host_of(url)}


def _dist(a: str, b: str) -> float:
    ra, ga, ba = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    rb, gb, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return ((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2) ** 0.5
