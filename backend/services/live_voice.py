"""Jessi live voice on OpenAI GPT-Live-1.

GPT-Live owns the spoken conversation (full duplex, interruptions, backchannels). We are the "client delegation" backend:
the browser forwards each delegation with the running transcript, the brain here picks a tool (My-3, contact recall,
send a text, set a reminder, draft, or a plain answer), runs it against the rep's real data and returns a short,
verified result that GPT-Live paraphrases aloud. Personality (voice, energy, pacing, playfulness, brevity) lives in
settings.jessi_voice and is edited in the admin Voice Lab."""
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from bson import ObjectId

from utils.text_sanitize import no_em_dash, clean_ai_text

logger = logging.getLogger(__name__)

LIVE_URL = "https://api.openai.com/v1/live/sessions"
MODEL = "gpt-live-1"
PRICE_PER_MIN = 0.05
SETTINGS_KEY = "jessi_voice"
COLL = "live_sessions"
LAB_KEY = "jessi_live_voice"
MODES = ("assistant", "lab")

VOICES = [
    {"id": "gleam", "name": "Gleam", "accent": "North American", "tone": "feminine", "natural": True},
    {"id": "marin", "name": "Marin", "accent": "OpenAI default", "tone": "feminine", "natural": True},
    {"id": "delta", "name": "Delta", "accent": "Southern U.S.", "tone": "feminine", "natural": False},
    {"id": "quartz", "name": "Quartz", "accent": "Australian", "tone": "feminine", "natural": False},
    {"id": "willow", "name": "Willow", "accent": "Irish", "tone": "feminine", "natural": True},
    {"id": "meridian", "name": "Meridian", "accent": "North American", "tone": "masculine", "natural": True},
    {"id": "cinder", "name": "Cinder", "accent": "Southern U.S.", "tone": "masculine", "natural": False},
    {"id": "ripple", "name": "Ripple", "accent": "Australian", "tone": "masculine", "natural": True},
    {"id": "vesper", "name": "Vesper", "accent": "British", "tone": "masculine", "natural": True},
    {"id": "stone", "name": "Stone", "accent": "Irish", "tone": "masculine", "natural": True},
    {"id": "beacon", "name": "Beacon", "accent": "Filipino", "tone": "masculine", "natural": False},
    {"id": "bossa", "name": "Bossa", "accent": "Brazilian Portuguese", "tone": "feminine", "natural": True},
    {"id": "tempo", "name": "Tempo", "accent": "Brazilian Portuguese", "tone": "masculine", "natural": True},
]
VOICE_IDS = {v["id"] for v in VOICES}
DEFAULTS = {"voice": "gleam", "energy": 4, "pacing": 4, "playful": 3, "brevity": 4, "daily_cap_min": 15, "idle_close_s": 25,
            "greeting": "Hey {first}, it's Jessi. Who are we talking about today?", "contact_greeting": "Hey {first}. {contact} is up. What do you want to know?", "notes": ""}
SLIDERS = ("energy", "pacing", "playful", "brevity")
ENERGY = {1: "calm and steady", 2: "relaxed and easy", 3: "warm and engaged", 4: "upbeat and energetic", 5: "high-energy and lively"}
PACING = {1: "slow and unhurried", 2: "measured", 3: "a natural pace", 4: "quick-moving, no dead air", 5: "fast and clipped"}
PLAYFUL = {1: "all business", 2: "mostly serious", 3: "lightly playful when it fits", 4: "playful", 5: "very playful, quick with a one-liner"}
BREVITY = {1: "take your time and explain fully", 2: "a few sentences", 3: "two or three short sentences", 4: "one or two short sentences, then let them talk", 5: "as few words as possible"}
TOOLS = ("who_today", "find_person", "recall_person", "send_text", "set_reminder", "draft_message", "confirm", "cancel", "answer", "open_screen")
SCREENS = {"contact": ("contact", "record", "profile", "person", "page", "card"), "thread": ("thread", "conversation", "texts", "messages", "text", "chat"),
           "tasks": ("tasks", "task", "reminders", "touchpoints", "to-dos", "todos"), "home": ("home", "today"), "inbox": ("inbox",)}


class LiveUnavailable(Exception):
    pass


class LiveCapReached(Exception):
    pass


def _now():
    return datetime.now(timezone.utc)


async def _tz(user: dict):
    from zoneinfo import ZoneInfo
    from routers.user_schedule import resolve_user_tz
    try:
        return ZoneInfo(await resolve_user_tz(str(user["_id"])))
    except Exception:
        return timezone.utc


def configured() -> Optional[str]:
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        return "GPT-Live needs your own OpenAI API key: add OPENAI_API_KEY to the backend environment (platform.openai.com, project API key, Tier 1 or higher)."
    return None


# ── settings ──────────────────────────────────────────────────────────────────
def clean_config(patch: dict, base: Optional[dict] = None) -> dict:
    cfg = dict(base or DEFAULTS)
    if not isinstance(patch, dict):
        return cfg
    if patch.get("voice") in VOICE_IDS:
        cfg["voice"] = patch["voice"]
    for k in SLIDERS:
        if k in patch:
            try:
                cfg[k] = min(5, max(1, int(patch[k])))
            except (TypeError, ValueError):
                pass
    if "daily_cap_min" in patch:
        try:
            cfg["daily_cap_min"] = min(240, max(1, int(patch["daily_cap_min"])))
        except (TypeError, ValueError):
            pass
    if "idle_close_s" in patch:
        try:
            cfg["idle_close_s"] = min(120, max(10, int(patch["idle_close_s"])))
        except (TypeError, ValueError):
            pass
    if isinstance(patch.get("greeting"), str):
        cfg["greeting"] = patch["greeting"].strip()[:220] or DEFAULTS["greeting"]
    if isinstance(patch.get("contact_greeting"), str):
        cfg["contact_greeting"] = patch["contact_greeting"].strip()[:220] or DEFAULTS["contact_greeting"]
    if isinstance(patch.get("notes"), str):
        cfg["notes"] = patch["notes"].strip()[:600]
    return cfg


async def get_config(db) -> dict:
    doc = await db.settings.find_one({"key": SETTINGS_KEY}) or {}
    cfg = clean_config(doc.get("value") or {})
    cfg["updated_at"] = doc.get("updated_at").isoformat() if doc.get("updated_at") else None
    cfg["updated_by"] = doc.get("updated_by")
    return cfg


async def save_config(db, patch: dict, by: Optional[dict]) -> dict:
    cur = await get_config(db)
    cfg = clean_config(patch, {k: cur[k] for k in DEFAULTS})
    await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {"value": cfg, "updated_at": _now(), "updated_by": (by or {}).get("email")}}, upsert=True)
    return await get_config(db)


# ── prompt compiler ───────────────────────────────────────────────────────────
def personality(cfg: dict) -> str:
    extra = f" {cfg['notes'].rstrip('.')}." if cfg.get("notes") else ""
    return (f"You are Jessi, the voice of I'm On Social, a sharp personal relationship and sales assistant for salespeople. "
            f"You sound {ENERGY[cfg['energy']]}, speak at {PACING[cfg['pacing']]}, and are {PLAYFUL[cfg['playful']]}. "
            f"Warm, confident, smart, proactive. Not a radio announcer, not a call-center agent. "
            f"Keep replies to {BREVITY[cfg['brevity']]}.{extra}\n"
            "If the rep sounds stressed, acknowledge it in a few words and get to the next useful step.")


def rep_line(user: dict) -> str:
    first = (user.get("name") or "").split(" ")[0] or "there"
    role = user.get("role") or "salesperson"
    org = user.get("organization_name") or user.get("store_name") or ""
    return f"You are talking with {first}{f', {role}' if role else ''}{f' at {org}' if org else ''}. Use their first name now and then, not every sentence."


def focus_line(contact: Optional[dict]) -> str:
    if not contact:
        return ""
    name = _first_last(contact)
    return (f"\nThe rep opened you from {name}'s record, so {name} is the person in focus: 'he', 'she', 'they', 'this customer' or 'this person' means {name} "
            f"unless the rep clearly names someone else. Anything about {name} (history, texting them, a reminder) goes to the backend.\n")


def assistant_instructions(cfg: dict, user: dict, language: str = "English", contact: Optional[dict] = None) -> str:
    return (personality(cfg) + "\n" + rep_line(user) + focus_line(contact) + f"\nSpeak {language} unless the rep switches.\n\n"
            "Backchannel policy: Use moderate backchannels. Acknowledge naturally without competing with the main response.\n\n"
            "Interruption policy: Stop speaking when the rep interrupts. Listen to what they say.\n\n"
            "Delegation policy:\n"
            "Backend tools:\n"
            "- Today's people: who the rep should reach out to today and why (their daily three).\n"
            "- Recall: the full history of anyone the rep has sold to or talked with (vehicle, last conversation, notes, open tasks).\n"
            "- Text: send a text message to one of the rep's contacts. The backend always reads the wording back first and only sends after the rep says yes.\n"
            "- Reminder: set a reminder or task, for example call someone Friday afternoon.\n"
            "- Draft: write a message the rep can send.\n"
            "- App help: how any part of I'm On Social works, and the rep's own numbers.\n"
            "- Open on screen: pull up a person's record, their text thread, or the rep's tasks on the phone screen. "
            "The app also follows along on its own: when the backend looks someone up, drafts a text or sets a reminder, that person's record, thread or the task opens on the rep's screen. "
            "You may mention it in a few words (for example 'she is up on your screen'), never in detail.\n\n"
            "Delegate to the backend when:\n"
            "- The rep names a person or asks who they should talk to or follow up with.\n"
            "- The rep asks to text, remind, draft, look something up, or asks about their numbers or how the app works.\n"
            "- The rep asks to open, pull up, show or go to something on the screen.\n"
            "- The rep confirms or cancels an action you read back (yes, send it / no, hold on).\n"
            "- A correction changes a task already requested.\n\n"
            "Do not delegate to the backend when:\n"
            "- The rep greets you, thanks you, or asks you to repeat a result already provided.\n"
            "- You need a brief clarification to understand who or what they mean.\n\n"
            "Delegate before giving an answer that depends on backend work. Do not guess a person's details, and never say a text was sent or a reminder was set before the backend confirms it. "
            "While the backend works, keep it short: a quick 'one sec, pulling that up' is plenty.")


def lab_instructions(cfg: dict, user: dict, contact: Optional[dict] = None) -> str:
    return (assistant_instructions(cfg, user, contact=contact) +
            f"\n\nThis is an audition in the Jessi Voice Lab: {(user.get('name') or 'the admin').split(' ')[0]} is choosing your voice and energy. "
            "Say hello first, mention one thing you can do in a single sentence, then behave exactly as you would with a rep.")


def greeting_text(cfg: dict, user: dict, contact: Optional[dict] = None) -> str:
    first = (user.get("name") or "").split(" ")[0] or "there"
    if contact:
        return (cfg.get("contact_greeting") or DEFAULTS["contact_greeting"]).replace("{first}", first).replace("{contact}", contact.get("first_name") or _first_last(contact))
    return (cfg.get("greeting") or DEFAULTS["greeting"]).replace("{first}", first)


async def focus_contact(db, user: dict, contact_id: Optional[str]) -> Optional[dict]:
    """The contact the rep opened Jessi from: theirs, or one they can see through a shared inbox / team."""
    if not contact_id or not ObjectId.is_valid(str(contact_id)):
        return None
    c = await db.contacts.find_one({"_id": ObjectId(str(contact_id))})
    if not c:
        return None
    if c.get("user_id") == str(user["_id"]) or user.get("role") in ("super_admin", "admin", "org_admin", "store_manager", "manager"):
        return c
    shared = await db.conversations.find_one({"contact_id": str(c["_id"]), "$or": [{"user_id": str(user["_id"])}, {"assigned_user_id": str(user["_id"])}]}, {"_id": 1})
    return c if shared else None


async def focus_brief(db, contact: dict) -> str:
    """A few plain lines about the focus contact so GPT-Live can follow the conversation; facts still come from the backend."""
    from services.contact_ask import build_record
    try:
        rec = await build_record(db, contact)
    except Exception:
        rec = {}
    bits = [f"Contact in focus: {_first_last(contact)}."]
    if contact.get("vehicle"):
        bits.append(f"Vehicle: {contact['vehicle']}.")
    if contact.get("tags"):
        bits.append("Tags: " + ", ".join(str(t) for t in contact["tags"][:6]) + ".")
    profile = (rec.get("profile") or "").strip()
    if profile:
        bits.append(profile[:700])
    return " ".join(bits)[:1200]


# ── usage / cap ───────────────────────────────────────────────────────────────
async def seconds_today(db, user_id: str) -> int:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    total = 0
    async for s in db[COLL].find({"user_id": user_id, "started_at": {"$gte": start}}, {"seconds": 1}):
        total += int(s.get("seconds") or 0)
    return total


async def usage_summary(db, user_id: str, cfg: dict) -> dict:
    used = await seconds_today(db, user_id)
    cap = int(cfg["daily_cap_min"]) * 60
    return {"used_s": used, "cap_s": cap, "left_s": max(0, cap - used)}


# ── session creation ──────────────────────────────────────────────────────────
async def create_session(db, user: dict, mode: str, sdp: str, overrides: Optional[dict] = None, contact_id: Optional[str] = None) -> dict:
    reason = configured()
    if reason:
        raise LiveUnavailable(reason)
    if mode not in MODES:
        raise ValueError("Unknown mode")
    cfg = await get_config(db)
    if mode == "lab" and overrides:
        cfg = clean_config(overrides, {k: cfg[k] for k in DEFAULTS})
    uid = str(user["_id"])
    if user.get("store_id") and not user.get("store_name"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(str(user["store_id"]))}, {"name": 1})
            if store:
                user = {**user, "store_name": store.get("name")}
        except Exception:
            pass
    usage = await usage_summary(db, uid, cfg)
    if mode == "assistant" and usage["left_s"] <= 0:
        raise LiveCapReached(f"You have used today's {cfg['daily_cap_min']} minutes of live Jessi. It resets at midnight.")
    contact = await focus_contact(db, user, contact_id)
    instructions = lab_instructions(cfg, user, contact) if mode == "lab" else assistant_instructions(cfg, user, contact=contact)
    tz = await _tz(user)
    now_local = _now().astimezone(tz).strftime("%A %B %d, %Y, %-I:%M %p")
    where = f"Their app is open on {_first_last(contact)}'s conversation. {await focus_brief(db, contact)}" if contact else "Their app is open on the Home screen."
    session = {"model": MODEL, "instructions": instructions, "audio": {"output": {"voice": cfg["voice"]}}, "delegation": {"type": "client"},
               "input": [{"type": "message", "role": "developer", "content": [{"type": "input_text", "text": f"Right now it is {now_local} for the rep. {where}"}]}]}
    body = {"session": session, "transport": {"type": "webrtc", "sdp": sdp}}
    headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY'].strip()}", "Content-Type": "application/json", "OpenAI-Safety-Identifier": f"imos-{uid[-8:]}"}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(LIVE_URL, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise LiveUnavailable(f"Could not reach OpenAI: {e}")
    if resp.status_code >= 300:
        try:
            msg = (resp.json().get("error") or {}).get("message") or resp.text[:200]
        except Exception:
            msg = resp.text[:200]
        logger.warning(f"[Live] session create failed {resp.status_code}: {msg}")
        raise LiveUnavailable(f"OpenAI refused the live session ({resp.status_code}): {msg}")
    data = resp.json()
    live_id = uuid.uuid4().hex[:12]
    doc = {"live_id": live_id, "user_id": uid, "user_name": user.get("name"), "mode": mode, "openai_session_id": (data.get("session") or {}).get("id"), "voice": cfg["voice"],
           "contact_id": str(contact["_id"]) if contact else None, "contact_name": _first_last(contact) if contact else None,
           "config": {k: cfg[k] for k in DEFAULTS}, "status": "open", "started_at": _now(), "ended_at": None, "seconds": 0, "cost_usd": 0.0, "close_reason": None,
           "transcript": [], "delegations": [], "pending": None, "created_at": _now(), "updated_at": _now()}
    await db[COLL].insert_one(doc)
    logger.info(f"[Live] {mode} session {live_id} for {uid} voice={cfg['voice']}")
    return {"live_id": live_id, "session_id": doc["openai_session_id"], "sdp": (data.get("transport") or {}).get("sdp"), "greeting": greeting_text(cfg, user, contact),
            "contact_name": _first_last(contact) if contact else None,
            "idle_close_s": cfg["idle_close_s"], "cap_left_s": usage["left_s"] if mode == "assistant" else None, "voice": cfg["voice"]}


async def get_live(db, live_id: str) -> Optional[dict]:
    return await db[COLL].find_one({"live_id": live_id})


async def record_events(db, live: dict, events: list) -> dict:
    """Transcript fragments, usage snapshots and the final close, batched by the browser."""
    rows, sets = [], {"updated_at": _now()}
    for ev in events or []:
        t = ev.get("type")
        if t == "transcript" and ev.get("text"):
            rows.append({"role": "assistant" if ev.get("role") == "assistant" else "rep", "text": str(ev["text"])[:2000], "start_ms": ev.get("start_ms"), "end_ms": ev.get("end_ms"), "at": _now()})
        elif t == "usage" and ev.get("seconds") is not None:
            sets["seconds"] = max(int(live.get("seconds") or 0), int(ev["seconds"]))
        elif t == "closed":
            secs = int(ev.get("seconds") if ev.get("seconds") is not None else live.get("seconds") or 0)
            sets.update({"status": "closed", "ended_at": _now(), "seconds": secs, "cost_usd": round(secs / 60 * PRICE_PER_MIN, 4), "close_reason": ev.get("reason") or "close_requested"})
        elif t == "error":
            sets["last_error"] = str(ev.get("message") or "")[:300]
    ops = {"$set": sets}
    if rows:
        ops["$push"] = {"transcript": {"$each": rows[-200:]}}
    await db[COLL].update_one({"_id": live["_id"]}, ops)
    if "cost_usd" in sets:
        sets["cost_usd"] = sets["cost_usd"]
    return sets


def serialize(s: dict, full: bool = False) -> dict:
    out = {"live_id": s.get("live_id"), "user_id": s.get("user_id"), "user_name": s.get("user_name"), "mode": s.get("mode"), "voice": s.get("voice"), "status": s.get("status"), "contact_name": s.get("contact_name"),
           "started_at": s["started_at"].isoformat() if s.get("started_at") else None, "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
           "seconds": int(s.get("seconds") or 0), "cost_usd": round(float(s.get("cost_usd") or 0), 4), "close_reason": s.get("close_reason"),
           "turns": len(s.get("transcript") or []), "delegations": len(s.get("delegations") or []), "tools": [d.get("tool") for d in (s.get("delegations") or [])]}
    if full:
        out["transcript"] = [{"role": r["role"], "text": r["text"], "start_ms": r.get("start_ms")} for r in s.get("transcript") or []]
        out["delegation_log"] = [{"tool": d.get("tool"), "args": d.get("args"), "result": d.get("result"), "ms": d.get("ms"), "at": d["at"].isoformat() if d.get("at") else None} for d in s.get("delegations") or []]
        out["config"] = s.get("config")
    return out


# ── the brain ─────────────────────────────────────────────────────────────────
BRAIN_SYSTEM = """You are the backend brain behind Jessi, a live voice assistant for salespeople using I'm On Social (a relationship CRM: contacts, texting, tasks, mystery shops, digital business cards).
You read the live transcript (it can contain mishearings, half sentences and later corrections) and decide ONE tool call. Use the latest thing the rep asked.

Tools:
- who_today: the rep asks who to contact / follow up with / talk to today. args: {}
- find_person: the rep mentions a person but you only need to confirm who they mean or list matches. args: {"name": "..."}
- recall_person: the rep wants to know about someone (history, what they bought, last conversation, anything about them). args: {"name": "..."}
- send_text: the rep wants to text someone. args: {"name": "...", "message": "<the exact wording if the rep gave it, else empty>", "intent": "<what the text should accomplish>"}
- set_reminder: the rep wants a reminder/task. args: {"name": "<person or empty>", "when_iso": "<ISO 8601 datetime in the rep's timezone, resolve words like Friday/tomorrow 3pm from NOW>", "note": "<what to do>", "action": "call|text|email|manual"}
- draft_message: the rep wants wording to send themselves. args: {"name": "...", "intent": "..."}
- confirm: the rep just said yes / send it / do it to an action that is PENDING. args: {}
- cancel: the rep said no / hold on / never mind to a PENDING action. args: {}
- answer: anything else (how the app works, small talk that needs facts, their numbers). args: {"say": "<the answer in at most 60 spoken words>"}
- open_screen: the rep wants something SHOWN on their phone screen: open / pull up / show / bring up / go to a person's record, a text thread, their tasks, home or the inbox. args: {"what": "contact|thread|tasks|home|inbox", "name": "<the person, empty for tasks/home/inbox>"}

Rules: "pull up Mike" or "show me Sarah" means open_screen (they want to see it); "tell me about Mike" or "what did Sarah buy" means recall_person (they want to hear it). If a person's name is unclear, still pick the tool with your best reading of the name. When a FOCUS CONTACT is given and the rep says him/her/them/this customer/this person or gives no name at all, args.name is the focus contact's full name. Never invent people or data. Return ONLY JSON: {"tool": "...", "args": {...}}"""


def _first_last(c: dict) -> str:
    return f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Unknown"


def _fmt_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    return f"({d[-10:-7]}) {d[-7:-4]}-{d[-4:]}" if len(d) >= 10 else (p or "")


async def _find(db, user_id: str, name: str, limit: int = 5) -> list:
    words = [w for w in re.split(r"\s+", (name or "").strip()) if w]
    if not words:
        return []
    q = {"user_id": user_id, "$and": [{"$or": [{"first_name": {"$regex": re.escape(w), "$options": "i"}}, {"last_name": {"$regex": re.escape(w), "$options": "i"}}]} for w in words[:3]]}
    rows = await db.contacts.find(q, {"first_name": 1, "last_name": 1, "phone": 1, "vehicle": 1, "email": 1, "tags": 1, "created_at": 1}).limit(limit).to_list(limit)
    if not rows and len(words) > 1:  # "Jim Carter" misheard as "Jim Carver": fall back to the first name only
        rows = await db.contacts.find({"user_id": user_id, "first_name": {"$regex": f"^{re.escape(words[0])}", "$options": "i"}}, {"first_name": 1, "last_name": 1, "phone": 1, "vehicle": 1}).limit(limit).to_list(limit)
    return rows


def _match_line(c: dict) -> str:
    bits = [_first_last(c)]
    if c.get("vehicle"):
        bits.append(str(c["vehicle"]))
    if c.get("phone"):
        bits.append(_fmt_phone(c["phone"]))
    return ", ".join(bits)


def _same_person(contact: dict, name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return True
    first = (contact.get("first_name") or "").strip().lower()
    return n == _first_last(contact).lower() or (bool(first) and n.split()[0] == first)


async def _resolve(db, user_id: str, name: str, focus: Optional[dict] = None):
    """One contact, or a spoken disambiguation string. The focus contact wins whenever the spoken name fits them."""
    if focus and _same_person(focus, name):
        return focus, None
    rows = await _find(db, user_id, name)
    if not rows:
        return None, f"I could not find anyone named {name} in your contacts. Want me to try a different spelling?"
    if len(rows) > 1 and not (len(name.split()) > 1 and _first_last(rows[0]).lower() == name.strip().lower()):
        return None, f"I found {len(rows)} people close to {name}: " + "; ".join(_match_line(c) for c in rows[:4]) + ". Which one?"
    return rows[0], None


async def _who_today(db, user: dict) -> str:
    from routers.home_intelligence import get_my_3
    items = await get_my_3(str(user["_id"]), db)
    if not items:
        return "Nothing is queued for today. Everyone is caught up, or there is no history to work from yet."
    lines = []
    for i, it in enumerate(items, 1):
        name = f"{it.get('first_name', '')} {it.get('last_name', '')}".strip()
        why = it.get("reason_label") or ""
        hook = it.get("hook") or ""
        done = " Already handled today." if it.get("done") else ""
        lines.append(f"{i}. {name}: {why}{'. ' + hook if hook else ''}.{done}")
    return "Your three for today. " + " ".join(lines) + " Want me to pull anyone up or text one of them?"


async def _recall(db, user: dict, name: str, focus: Optional[dict] = None):
    contact, err = await _resolve(db, str(user["_id"]), name, focus)
    if err:
        return err, None
    from services.contact_ask import build_record
    from services.scripts import _llm
    rec = await build_record(db, contact)
    timeline = rec.get("timeline") or ""
    facts = await _llm("You turn a CRM record into what a sharp assistant would SAY out loud to the salesperson about this person. At most 90 words, plain sentences, most useful first: what they bought or want, when you last talked and about what, anything personal worth remembering, open tasks. No headings, no markdown, no phone numbers.",
                       f"PROFILE:\n{rec.get('profile', '')[:4000]}\n\nRECENT TIMELINE (newest last):\n{timeline[-6000:]}", timeout=40)
    return no_em_dash(facts.strip()), contact


def _open_target(kind: str, contact: Optional[dict] = None, task: Optional[dict] = None) -> dict:
    """What the app should put on the rep's screen: {kind contact|thread|task|tasks|home|inbox, id, name}."""
    out = {"kind": kind}
    if contact:
        out.update(id=str(contact["_id"]), name=_first_last(contact), first=contact.get("first_name") or "")
    if task:
        out.update(id=str(task.get("_id") or task.get("id") or ""), name=task.get("title") or "", contact_id=task.get("contact_id") or "")
    return out


def _screen_of(what: str) -> str:
    tokens = re.findall(r"[a-z-]+", (what or "").lower())
    for screen, words in SCREENS.items():
        if any(t in words or t.rstrip("s") in words for t in tokens):
            return screen
    return "contact"


async def _open_screen(db, user: dict, args: dict, focus: Optional[dict] = None):
    screen = _screen_of(args.get("what") or "")
    if screen in ("tasks", "home", "inbox"):
        return {"tasks": "Your tasks are up on your screen.", "home": "Home is up.", "inbox": "Your inbox is up."}[screen], _open_target(screen)
    contact, err = await _resolve(db, str(user["_id"]), args.get("name") or "", focus)
    if err:
        return err, None
    first = contact.get("first_name") or _first_last(contact)
    return (f"{first}'s text thread is up on your screen." if screen == "thread" else f"{first} is up on your screen."), _open_target(screen, contact)


async def _draft(db, user: dict, contact: dict, intent: str, wording: str = "") -> str:
    if wording and len(wording.strip()) > 8:
        return no_em_dash(wording.strip()[:400])
    from services.contact_ask import build_record
    from services.scripts import _llm
    rec = await build_record(db, contact)
    rep_first = (user.get("name") or "").split(" ")[0]
    text = (await _llm(f"Write ONE text message from {rep_first} (a salesperson) to their customer {contact.get('first_name')}. Under 240 characters, sounds human, first name only, no emojis, no signature, no em dashes, references something real from the record when it helps. Output only the message.",
                       f"Goal: {intent or 'friendly check-in'}\n\nPROFILE:\n{rec.get('profile', '')[:2500]}\n\nRECENT:\n{(rec.get('timeline') or '')[-2500:]}", timeout=40)).strip().strip('"')[:400]
    return await clean_ai_text(text, str(user["_id"]))


async def _send_now(db, user: dict, pending: dict) -> str:
    from routers.messages import send_message_simple
    try:
        r = await send_message_simple(str(user["_id"]), {"contact_id": pending["contact_id"], "content": pending["content"], "channel": "sms"})
    except Exception as e:
        detail = getattr(e, "detail", None) or str(e)
        return f"That text did not go out: {str(detail)[:140]}"
    ok = not (isinstance(r, dict) and r.get("success") is False)
    return f"Sent to {pending['name']}." if ok else f"That text did not go out: {str((r or {}).get('error') or 'unknown error')[:140]}"


async def _reminder(db, user: dict, args: dict, focus: Optional[dict] = None):
    from routers.tasks import create_task
    name = (args.get("name") or "").strip()
    contact = None
    if name or focus:
        contact, err = await _resolve(db, str(user["_id"]), name, focus)
        if err:
            return err, None
    when = None
    tz = await _tz(user)
    try:
        when = datetime.fromisoformat(str(args.get("when_iso") or "").replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=tz)
    except Exception:
        when = None
    if not when:
        when = (_now().astimezone(tz) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    local = when.astimezone(tz)
    action = args.get("action") if args.get("action") in ("call", "text", "email", "manual") else "call"
    note = (args.get("note") or "").strip() or (f"{action.title()} {_first_last(contact)}" if contact else "Follow up")
    title = note if len(note) < 80 else note[:77] + "..."
    task = await create_task(str(user["_id"]), {"title": title, "description": note, "contact_id": str(contact["_id"]) if contact else "", "type": "callback" if action == "call" else "follow_up",
                                                "action_type": action, "due_date": when.astimezone(timezone.utc).isoformat(), "has_time": True, "priority": "medium"})
    spoken_when = local.strftime("%A at %-I:%M %p") if local.hour or local.minute else local.strftime("%A")
    who = f" for {_first_last(contact)}" if contact else ""
    return (f"Done. Reminder set{who}: {title}, {spoken_when}." if task else "I could not save that reminder."), task


async def _answer(user: dict, say: str, question: str) -> str:
    if say and len(say.split()) <= 70:
        return no_em_dash(say.strip())
    from services.jessie_service import KNOWLEDGE_BASE, _build_user_context
    from services.scripts import _llm
    ctx = await _build_user_context(str(user["_id"]))
    return no_em_dash((await _llm(KNOWLEDGE_BASE[:14000] + "\n" + ctx + "\nAnswer for a live voice assistant: at most 60 words, plain spoken sentences, no markdown.", question, timeout=40)).strip())


def _last_rep_text(transcript: list) -> str:
    for t in reversed(transcript or []):
        if t.get("role") != "assistant" and t.get("text"):
            return str(t["text"])
    return ""


async def delegate(db, live: dict, user: dict, transcript: list, delegation_id: Optional[str]) -> dict:
    """One delegation from GPT-Live: plan a tool from the transcript, run it, hand back a short spoken result."""
    from services.scripts import _llm_json
    t0 = _now()
    convo = "\n".join(f"{'JESSI' if t.get('role') == 'assistant' else 'REP'}: {str(t.get('text', ''))[:400]}" for t in (transcript or [])[-16:])
    pending = live.get("pending")
    focus = await focus_contact(db, user, live.get("contact_id")) if live.get("contact_id") else None
    focus_txt = f"FOCUS CONTACT: {_first_last(focus)} (the rep opened Jessi from this person's record)" if focus else "FOCUS CONTACT: none"
    tz = await _tz(user)
    tz_line = f"NOW (rep's local time, {getattr(tz, 'key', 'UTC')}): {_now().astimezone(tz).strftime('%A %Y-%m-%d %H:%M')}. Return when_iso in this local time without a Z suffix."
    plan = {}
    try:
        plan = await _llm_json(BRAIN_SYSTEM, f"{tz_line}\n{focus_txt}\nPENDING ACTION: {json.dumps({k: pending[k] for k in ('type', 'name', 'content') if k in pending}) if pending else 'none'}\n\nTRANSCRIPT (oldest first):\n{convo}\n\nDecide the one tool call.", timeout=30)
    except Exception as e:
        logger.warning(f"[Live] brain plan failed: {e}")
    tool = plan.get("tool") if plan.get("tool") in TOOLS else "answer"
    args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
    result, new_pending, kind, opened = "", pending, "commentary", None
    try:
        if tool == "who_today":
            result = await _who_today(db, user)
        elif tool == "find_person":
            rows = [focus] if focus and _same_person(focus, args.get("name") or "") else await _find(db, str(user["_id"]), args.get("name") or "")
            if len(rows) == 1:
                result, opened = f"Found {_match_line(rows[0])}. They are up on your screen.", _open_target("contact", rows[0])
            else:
                result = ("I found " + "; ".join(_match_line(c) for c in rows[:4]) + ". Which one did you mean?") if rows else f"No one named {args.get('name')} in your contacts."
        elif tool == "recall_person":
            result, contact = await _recall(db, user, args.get("name") or ("" if focus else _last_rep_text(transcript)), focus)
            opened = _open_target("contact", contact) if contact else None
        elif tool in ("send_text", "draft_message"):
            contact, err = await _resolve(db, str(user["_id"]), args.get("name") or "", focus)
            if err:
                result = err
            elif not contact.get("phone"):
                result = f"{_first_last(contact)} has no phone number on file, so I cannot text them."
            else:
                content = await _draft(db, user, contact, args.get("intent") or "", args.get("message") or "")
                new_pending = {"type": "send_text", "contact_id": str(contact["_id"]), "name": _first_last(contact), "content": content, "at": _now().isoformat()}
                result = (f"Here is the text for {contact.get('first_name')}: \"{content}\" Say yes and I will send it, or tell me what to change." if tool == "send_text"
                          else f"Here is a draft for {contact.get('first_name')}: \"{content}\" Want me to send it, or will you?")
                opened = _open_target("thread", contact)
        elif tool == "set_reminder":
            result, task = await _reminder(db, user, args, focus)
            opened = _open_target("task", task=task) if task else None
        elif tool == "confirm":
            if pending and pending.get("type") == "send_text":
                result = await _send_now(db, user, pending)
                opened = {"kind": "thread", "id": pending["contact_id"], "name": pending.get("name") or "", "first": (pending.get("name") or "").split(" ")[0]}
                new_pending = None
            else:
                result = "There is nothing waiting for a yes right now. What would you like me to do?"
        elif tool == "cancel":
            result = "Okay, cancelled. Nothing was sent." if pending else "Nothing to cancel."
            new_pending = None
        elif tool == "open_screen":
            result, opened = await _open_screen(db, user, args, focus)
        else:
            result = await _answer(user, args.get("say") or "", _last_rep_text(transcript))
    except Exception as e:
        logger.exception(f"[Live] tool {tool} failed: {e}")
        result = "Something went wrong on my side pulling that up. Try me again in a second."
    result = no_em_dash((result or "").strip()[:1400])
    ms = int((_now() - t0).total_seconds() * 1000)
    await db[COLL].update_one({"_id": live["_id"]}, {"$push": {"delegations": {"id": delegation_id, "tool": tool, "args": args, "result": result, "open": opened, "ms": ms, "at": _now()}}, "$set": {"pending": new_pending, "updated_at": _now()}})
    logger.info(f"[Live] {live['live_id']} {tool} in {ms}ms" + (f" -> open {opened['kind']}" if opened else ""))
    return {"tool": tool, "content": result, "kind": kind, "pending": bool(new_pending), "open": opened, "ms": ms}


# ── admin views ───────────────────────────────────────────────────────────────
async def list_sessions(db, limit: int = 30, user_id: Optional[str] = None) -> list:
    q = {"user_id": user_id} if user_id else {}
    rows = await db[COLL].find(q).sort("started_at", -1).limit(min(200, max(1, limit))).to_list(200)
    return [serialize(s) for s in rows]


async def stats(db) -> dict:
    now = _now()
    out = {}
    for label, since in (("today", now.replace(hour=0, minute=0, second=0, microsecond=0)), ("week", now - timedelta(days=7)), ("month", now - timedelta(days=30))):
        secs = sessions = 0
        reps = set()
        async for s in db[COLL].find({"started_at": {"$gte": since}}, {"seconds": 1, "user_id": 1}):
            secs += int(s.get("seconds") or 0)
            sessions += 1
            reps.add(s.get("user_id"))
        out[label] = {"sessions": sessions, "minutes": round(secs / 60, 1), "cost_usd": round(secs / 60 * PRICE_PER_MIN, 2), "reps": len(reps)}
    out["open"] = await db[COLL].count_documents({"status": "open", "started_at": {"$gte": now - timedelta(hours=3)}})
    return out


async def close_stale(db) -> int:
    """Sessions the browser never closed (tab killed): mark closed after 3 h using the last usage snapshot."""
    cutoff = _now() - timedelta(hours=3)
    r = await db[COLL].update_many({"status": "open", "updated_at": {"$lt": cutoff}}, [{"$set": {"status": "closed", "close_reason": "stale", "ended_at": _now(), "cost_usd": {"$round": [{"$multiply": [{"$divide": [{"$ifNull": ["$seconds", 0]}, 60]}, PRICE_PER_MIN]}, 4]}}}])
    return r.modified_count
