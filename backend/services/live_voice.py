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
from difflib import SequenceMatcher
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
MODES = ("assistant", "lab", "shopper")
SHOPPER_IDLE_S = 45
WALKTHROUGH_RULES = ("\n\nThis session is a WALKTHROUGH OF THE REP'S DAY. The backend hands you each stop in order (a customer waiting on a reply, an overdue touchpoint, one of today's three, a hot opportunity); "
                     "say it in your own words, keep every name and detail, then stop and wait. The rep moves it along with next, skip or done, and texting or finishing a stop through you moves it along too. "
                     "Brisk and warm: this is a morning run-through, not a chat. When the backend says that's the day, wrap up in one line.")

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
TOOLS = ("who_today", "find_person", "recall_person", "send_text", "set_reminder", "draft_message", "confirm", "cancel", "answer", "open_screen", "find_duplicates", "merge_duplicates", "next_stop", "find_mentions")
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
            "You may mention it in a few words (for example 'she is up on your screen'), never in detail.\n"
            "- Duplicates: find double records in the rep's contacts (same person saved twice) and merge them. The backend reads back which records go together and merges only after the rep says yes.\n"
            "- Who mentioned: find a customer by something that came up rather than by name ('who asked about a Tesla last month', 'who did I sell a Tahoe to'). The backend searches every text, call transcript, voice memo, note and sold record and comes back with the person, the quote and when.\n\n"
            "Delegate to the backend when:\n"
            "- The rep names a person or asks who they should talk to or follow up with.\n"
            "- The rep asks to text, remind, draft, look something up, or asks about their numbers or how the app works.\n"
            "- The rep asks to open, pull up, show or go to something on the screen.\n"
            "- The rep asks about duplicates, double records, or says 'merge them' / 'combine them' / 'clean that up' after you mentioned two records for one name.\n"
            "- The rep is trying to remember WHO said or asked about something ('someone wanted a 20k Model 3, who was that').\n"
            "- The rep confirms or cancels an action you read back (yes, send it / no, hold on).\n"
            "- A correction changes a task already requested.\n"
            "- The rep picks one of several people the backend listed, spells a name, or says the person you found is the wrong one. Delegate again right away; the backend matches names loosely (Tod and Todd, Berry and Barry), so a spelled name or a last name settles it.\n\n"
            "Names: when the backend lists several people, read the names with what tells them apart (last name, spelling, vehicle) and ask which one. Never pick one yourself. "
            "When the backend says it used one of several records for the same name, pass that on in one short sentence ('you have two Tod Berrys, I used the one with the Tahoe, say the other one to switch') and carry on. "
            "If the rep says it is the wrong person, apologise in two or three words and ask for the last name or the spelling.\n\n"
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
    shop = None
    agenda = None
    if mode == "assistant" and (overrides or {}).get("walkthrough"):
        from services import day_agenda
        agenda = await day_agenda.build(db, uid)
        if agenda and agenda[0].get("contact_id"):
            contact = await focus_contact(db, user, agenda[0]["contact_id"]) or contact
    if mode == "shopper":
        from services import live_shops
        shop = await live_shops.audition(db, user, overrides or {})
        instructions, voice = shop["instructions"], shop["voice"]
    else:
        instructions, voice = (lab_instructions(cfg, user, contact) if mode == "lab" else assistant_instructions(cfg, user, contact=contact)), cfg["voice"]
        if agenda is not None:
            instructions += WALKTHROUGH_RULES
    tz = await _tz(user)
    now_local = _now().astimezone(tz).strftime("%A %B %d, %Y, %-I:%M %p")
    where = f"Their app is open on {_first_last(contact)}'s conversation. {await focus_brief(db, contact)}" if contact else "Their app is open on the Home screen."
    context = f"Right now it is {now_local}." if shop else f"Right now it is {now_local} for the rep. {where}"
    if agenda is not None:
        context += " DAY WALKTHROUGH, the stops in order: " + ("; ".join(f"{s['n']}. {s['name']} ({s['kind']}: {s['why']})" for s in agenda) if agenda else "none, the rep is caught up") + "."
    session = {"model": MODEL, "instructions": instructions, "audio": {"output": {"voice": voice}}, "delegation": {"type": "client"},
               "input": [{"type": "message", "role": "developer", "content": [{"type": "input_text", "text": context}]}]}
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
    doc = {"live_id": live_id, "user_id": uid, "user_name": user.get("name"), "mode": mode, "openai_session_id": (data.get("session") or {}).get("id"), "voice": voice,
           "contact_id": str(contact["_id"]) if contact else None, "contact_name": _first_last(contact) if contact else None, "shopper": shop["meta"] if shop else None,
           "agenda": agenda, "agenda_pos": 0 if agenda is not None else None, "agenda_done": [], "agenda_skipped": [],
           "config": {k: cfg[k] for k in DEFAULTS}, "status": "open", "started_at": _now(), "ended_at": None, "seconds": 0, "cost_usd": 0.0, "close_reason": None,
           "transcript": [], "delegations": [], "pending": None, "created_at": _now(), "updated_at": _now()}
    await db[COLL].insert_one(doc)
    logger.info(f"[Live] {mode} session {live_id} for {uid} voice={voice}" + (f" walkthrough={len(agenda)} stops" if agenda is not None else ""))
    greet = shop["greet_instruction"] if shop else None
    opened = None
    if agenda is not None:
        from services import day_agenda
        greet = f'Open with this, in your own words but keep every name and detail: "{day_agenda.intro(user, agenda)}" Then stop and wait for the rep.'
        opened = day_agenda.open_target(agenda[0]) if agenda else None
    return {"live_id": live_id, "session_id": doc["openai_session_id"], "sdp": (data.get("transport") or {}).get("sdp"), "greeting": greeting_text(cfg, user, contact), "greet_instruction": greet,
            "contact_name": _first_last(contact) if contact else None, "shopper": shop["meta"] if shop else None, "open": opened,
            "agenda": [{k: s.get(k) for k in ("n", "kind", "name", "first", "why", "contact_id")} for s in agenda] if agenda is not None else None,
            "idle_close_s": SHOPPER_IDLE_S if shop else cfg["idle_close_s"], "cap_left_s": usage["left_s"] if mode == "assistant" else None, "voice": voice}


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
           "shopper": s.get("shopper"), "walkthrough": {"stops": len(s["agenda"]), "done": len(s.get("agenda_done") or []), "skipped": len(s.get("agenda_skipped") or [])} if s.get("agenda") is not None else None,
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
- find_duplicates: the rep asks whether they have duplicates / double records / the same person twice, or wants to clean up their contacts. args: {}
- merge_duplicates: the rep wants two or more records of ONE person combined: "merge them", "combine those", "make Tod one record", "clean up Tod Berry", or "merge them" right after Jessi mentioned she found two records for a name. args: {"name": "<the person as spoken, empty when they mean the records Jessi just mentioned>"}
- next_stop: ONLY during a DAY WALKTHROUGH (shown below). The rep moves the walkthrough along: "next" / "what's next" / "move on" / "go on" / "okay next one" -> {"action": "next"}; "skip" / "skip him" / "not today" / "pass" -> {"action": "skip"}; "done" / "did that" / "already texted him" / "handled" / "mark it done" / "I called her" -> {"action": "done"}. args: {"action": "next|skip|done"}
- find_mentions: the rep is hunting for a person by something that came up, not by name: "who asked about a Tesla", "someone mentioned a 20k Model 3 last month, who was it", "find anyone looking for a truck", "who talked about a trade-in", "did anybody bring up financing", and by what they bought: "who did I sell a Tahoe to", "who bought a Silverado last year", "which customers have a Model 3". The backend searches every text, call transcript, voice memo, note and sold record. args: {"query": "<what they are looking for, as said, keep numbers and product names>", "days": <lookback in days if the rep said a time frame like last month = 45, this year = 365, else 0>}

Every tool that takes a "name" also takes "hint": how the rep pointed at ONE of several records Jessi listed, verbatim and short: "the first one", "the second one", "the other one", "the one with the Tahoe", "ending in 0100", "the Berry one", "the newer one". Empty when the rep did not pick.

Rules: "pull up Mike" or "show me Sarah" means open_screen (they want to see it); "tell me about Mike" or "what did Sarah buy" means recall_person (they want to hear it). If a person's name is unclear, still pick the tool with your best reading of the name. Names: pass first AND last name whenever the rep said both. If the rep spells a name ("T-O-D", "J E S S I E", "B as in boy, E, R..."), args.name MUST use exactly those letters for that part (J E S S I E -> Jessie, never Jesse) plus the other name part (e.g. "Jessie Walters"). If Jessi just listed several people and the rep picks one ("the second one", "the one with the Tahoe", "Berry", "not Snow, the other Todd"), args.name is that person's full name exactly as listed AND args.hint is how they picked. If Jessi said she used one of several records and the rep says "the other one" / "no, the other Tod", keep the same tool and name and set hint to "the other one". If the rep says the last match was the wrong person, do not reuse it: use the corrected name they gave. When a FOCUS CONTACT is given and the rep says him/her/them/this customer/this person or gives no name at all, args.name is the focus contact's full name. During a DAY WALKTHROUGH the focus contact is the current stop, so "draft it", "text him", "pull her up", "what did he buy" all point at that person; a bare "yes" right after Jessi offered to draft or pull someone up means do that (send_text / draft_message / open_screen for the focus contact), not confirm, unless an action is PENDING. Never invent people or data. Return ONLY JSON: {"tool": "...", "args": {...}}"""


def _first_last(c: dict) -> str:
    return f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Unknown"


def _fmt_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    return f"({d[-10:-7]}) {d[-7:-4]}-{d[-4:]}" if len(d) >= 10 else (p or "")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _soundex(s: str) -> str:
    s = _norm(s)
    if not s:
        return ""
    codes = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"), **dict.fromkeys("dt", "3"), "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}
    out, last = s[0].upper(), codes.get(s[0], "")
    for ch in s[1:]:
        code = codes.get(ch, "")
        if code and code != last:
            out += code
        if ch not in "hw":
            last = code
    return (out + "000")[:4]


def _sim(a: str, b: str) -> float:
    """How alike two spoken name parts are: exact 1.0; Tod/Todd, Berry/Barry, Jesse/Jessie land around 0.9.
    A part the rep spelled out (marked with a leading '=') must match exactly to score high."""
    strict = a.startswith("=")
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    score = SequenceMatcher(None, a, b).ratio()
    if strict:
        return score * 0.7
    if min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)):
        score = max(score, 0.9)
    if _soundex(a) == _soundex(b):
        score = max(score, 0.88)
    return score


def _despell(name: str) -> str:
    """'Tod, T-O-D Berry' -> 'Tod =TOD Berry': letters the rep spelled out become one word again, marked as spelled."""
    s = re.sub(r"\b([A-Za-z])(?:[\s\-\.,]+([A-Za-z])\b)+", lambda m: "=" + re.sub(r"[\s\-\.,]", "", m.group(0)), name or "")
    return re.sub(r"[^\w\s'\-=]", " ", s)


STOP_WORDS = {"the", "one", "guy", "lady", "customer", "and", "not", "no", "other", "yes", "mean", "meant", "i", "want", "pull", "up", "open", "with", "spelled", "spelt", "like", "in", "as", "boy"}


def _name_words(name: str) -> list:
    """Distinct name parts, spelled versions ('=tod') replacing their spoken twin, junk words dropped."""
    out: dict = {}
    for w in re.split(r"\s+", _despell(name).strip()):
        key = _norm(w)
        if not w or not key or key in STOP_WORDS:
            continue
        if key not in out or w.startswith("="):
            out[key] = w
    return list(out.values())[:3]


def _score(words: list, c: dict) -> float:
    first, last = c.get("first_name") or "", c.get("last_name") or ""
    if not words:
        return 0.0
    if len(words) == 1:
        return max(_sim(words[0], first), 0.92 * _sim(words[0], last))
    direct = (_sim(words[0], first) + _sim(words[-1], last)) / 2
    swapped = (_sim(words[0], last) + _sim(words[-1], first)) / 2
    full = SequenceMatcher(None, _norm("".join(words)), _norm(first + last)).ratio() * (0.7 if any(w.startswith("=") for w in words) else 1.0)
    return max(direct, swapped, full)


async def _find(db, user_id: str, name: str, limit: int = 5) -> list:
    """Fuzzy, spoken-name lookup over the rep's contacts: mishearings (Berry/Barry), spellings (Tod/Todd, Jesse/Jessie) and
    spelled-out letters all land on the right people. Each row carries `_score`; rows come back best first."""
    words = _name_words(name)
    if not words:
        return []
    cands = await db.contacts.find({"user_id": user_id}, {"first_name": 1, "last_name": 1}).limit(25000).to_list(25000)
    scored = sorted(((_score(words, c), c["_id"]) for c in cands), key=lambda x: -x[0])
    keep = [(s, cid) for s, cid in scored[:limit] if s >= 0.78]
    if not keep:
        return []
    rows = await db.contacts.find({"_id": {"$in": [cid for _, cid in keep]}}, {"first_name": 1, "last_name": 1, "phone": 1, "vehicle": 1, "vehicle_interest": 1, "email": 1, "tags": 1, "created_at": 1, "updated_at": 1, "last_activity_at": 1, "organization_name": 1, "lead_source_name": 1}).to_list(limit)
    by_id = {r["_id"]: r for r in rows}
    out = []
    for s, cid in keep:
        if cid in by_id:
            out.append({**by_id[cid], "_score": round(s, 3)})
    return out


def _spell(word: str) -> str:
    return "-".join(ch.upper() for ch in word if ch.isalpha())


def _match_line(c: dict, spell_first: bool = False) -> str:
    bits = [_first_last(c) + (f" ({_spell(c.get('first_name') or '')})" if spell_first and c.get("first_name") else "")]
    if c.get("vehicle"):
        bits.append(str(c["vehicle"]))
    if c.get("phone"):
        bits.append(_fmt_phone(c["phone"]))
    return ", ".join(bits)


def _choices(rows: list) -> str:
    """Spoken list of candidates; when two share a first name that is spelled differently (Tod/Todd) the spelling is read out,
    and same-name records get what tells them apart (vehicle, phone, last activity)."""
    firsts = [_norm(c.get("first_name") or "") for c in rows]
    spell = any(firsts.count(f) == 1 and any(_soundex(f) == _soundex(g) and f != g for g in firsts) for f in firsts)
    same = len({_norm(_first_last(c)) for c in rows}) == 1
    return "; ".join((f"{_first_last(c)} {_describe(c)}" if same else _match_line(c, spell_first=spell)) for c in rows[:4])


def _when(c: dict) -> Optional[datetime]:
    for k in ("last_activity_at", "updated_at", "created_at"):
        v = c.get(k)
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                v = None
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def _describe(c: dict) -> str:
    bits = []
    if c.get("vehicle") or c.get("vehicle_interest"):
        bits.append(f"with the {c.get('vehicle') or c.get('vehicle_interest')}")
    if c.get("phone"):
        bits.append(f"at {_fmt_phone(c['phone'])}")
    w = _when(c)
    if w:
        days = max(0, (_now() - w).days)
        bits.append("active today" if days == 0 else f"active {days} day{'s' if days != 1 else ''} ago")
    return ", ".join(bits) or "with no phone on file"


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


ORDINALS = {"first": 0, "1st": 0, "one": 0, "1": 0, "second": 1, "2nd": 1, "two": 1, "2": 1, "third": 2, "3rd": 2, "three": 2, "3": 2, "fourth": 3, "4th": 3, "four": 3, "4": 3, "last": -1}


def _apply_hint(hint: str, rows: list, last_pick: Optional[str] = None) -> Optional[dict]:
    """The rep's way of pointing at one of several records: an ordinal, 'the other one', phone digits, a vehicle or email word, a last name."""
    h = (hint or "").lower().strip()
    if not h or not rows:
        return None
    if any(w in h for w in ("other", "not that", "switch", "different one", "wrong one")) and last_pick:
        for r in rows:
            if str(r["_id"]) != last_pick:
                return r
    for w in re.findall(r"[a-z0-9]+", h):
        if w in ORDINALS and (w not in ("one",) or h.strip() in ("one", "the one", "number one")):
            i = ORDINALS[w]
            if -len(rows) <= i < len(rows):
                return rows[i]
    digs = _digits(h)
    if len(digs) >= 3:
        for r in rows:
            if _digits(r.get("phone") or "").endswith(digs[-4:] if len(digs) >= 4 else digs):
                return r
    words = [w for w in re.findall(r"[a-z]+", h) if w not in STOP_WORDS and w not in ORDINALS and len(w) > 2]
    for r in rows:
        hay = " ".join(str(r.get(k) or "") for k in ("vehicle", "vehicle_interest", "email", "organization_name", "lead_source_name")).lower() + " " + " ".join(r.get("tags") or []).lower()
        if any(w in hay for w in words):
            return r
    for r in rows:
        if any(_sim(w, r.get("last_name") or "") >= 0.85 for w in words):
            return r
    return None


def _same_person(contact: dict, name: str) -> bool:
    words = _name_words(name)
    if not words:
        return True
    first, last = contact.get("first_name") or "", contact.get("last_name") or ""
    if len(words) == 1:
        return _sim(words[0], first) >= 0.85 or _sim(words[0], last) >= 0.9
    return _score(words, contact) >= 0.85 and (_sim(words[-1], last) >= 0.8 or _sim(words[-1], first) >= 0.8)


async def _remember(db, live: Optional[dict], choices: list, pick: Optional[dict], question: str = "") -> None:
    """What Jessi just listed / picked, so 'the second one' or 'the other one' lands on the same records next turn."""
    if not live:
        return
    sets = {"last_choices": [str(c["_id"]) for c in choices], "last_pick": str(pick["_id"]) if pick else None, "last_question_name": question}
    live.update(sets)
    await db[COLL].update_one({"_id": live["_id"]}, {"$set": sets})


def _with_note(text: str, contact: Optional[dict]) -> str:
    return f"{text} {contact['_note']}" if contact and contact.get("_note") else text


async def _resolve(db, user_id: str, name: str, focus: Optional[dict] = None, hint: str = "", live: Optional[dict] = None):
    """One contact, or a spoken disambiguation string. Never loops: a hint ('the second one', 'ending in 0100', 'the Tahoe one') picks from
    the records Jessi just listed; same-name duplicates collapse (same phone) or default to the most active one with a 'say the other one' note;
    a question is never asked twice in a row for the same name. The focus contact wins whenever the spoken name fits them."""
    hint = (hint or "").strip()
    if live and hint and live.get("last_choices"):
        rows = await db.contacts.find({"_id": {"$in": [ObjectId(x) for x in live["last_choices"] if ObjectId.is_valid(x)]}}).to_list(10)
        rows.sort(key=lambda r: live["last_choices"].index(str(r["_id"])))
        words = _name_words(name)
        if words and not any(_score(words, r) >= 0.8 for r in rows):
            rows = []  # the list Jessi read out was about someone else; do not pick from it
        picked = _apply_hint(hint, rows, live.get("last_pick"))
        if picked:
            await _remember(db, live, rows, picked)
            return picked, None
    if focus and _same_person(focus, name) and not hint:
        return focus, None
    rows = await _find(db, user_id, name)
    if not rows:
        return None, f"I could not find anyone named {name} in your contacts. Want me to try a different spelling, or spell it for me?"
    best = rows[0].get("_score", 1.0)
    top = [r for r in rows if r.get("_score", 1.0) >= max(0.85, best - 0.1)] or rows[:1]
    if hint:
        picked = _apply_hint(hint, top, live.get("last_pick") if live else None)
        if picked:
            await _remember(db, live, top, picked)
            return picked, None
    # records that are the same person twice (same name, same phone) collapse into the most active one
    seen, uniq = {}, []
    for r in sorted(top, key=lambda r: _when(r) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        key = (_norm(_first_last(r)), _digits(r.get("phone") or "")[-10:])
        if key in seen:
            continue
        seen[key] = True
        uniq.append(r)
    top = uniq
    if len(top) == 1 and best >= 0.86:
        await _remember(db, live, top, top[0])
        return top[0], None
    same_name = len({_norm(_first_last(r)) for r in top}) == 1
    asked_before = bool(live and live.get("last_question_name") == _norm(name) and live.get("last_choices"))
    if same_name or asked_before:
        # duplicates of one person, or the rep repeated the name after being asked: go with the most active record and say so
        chosen = top[0]
        await _remember(db, live, top, chosen)
        others = "; ".join(f"{_first_last(r)} {_describe(r)}" for r in top[1:3])
        chosen["_note"] = (f"Heads up, you have {len(top)} records for {_first_last(chosen)}; I used the one {_describe(chosen)}. The other {'one is' if len(top) == 2 else 'ones are'} {others}. Say 'the other one' to switch, or 'merge them' to make it one record."
                           if same_name else f"I went with {_first_last(chosen)} {_describe(chosen)}. Say 'the other one' if you meant someone else.")
        return chosen, None
    await _remember(db, live, top, None, _norm(name))
    return None, f"I found {len(top)} people close to {name}: {_choices(top)}. Which one? You can say the last name, 'the first one', or the last four of the phone."


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


async def _recall(db, user: dict, name: str, focus: Optional[dict] = None, hint: str = "", live: Optional[dict] = None):
    contact, err = await _resolve(db, str(user["_id"]), name, focus, hint, live)
    if err:
        return err, None
    from services.contact_ask import build_record
    from services.scripts import _llm
    rec = await build_record(db, contact)
    timeline = rec.get("timeline") or ""
    facts = await _llm("You turn a CRM record into what a sharp assistant would SAY out loud to the salesperson about this person. At most 90 words, plain sentences, most useful first: what they bought or want, when you last talked and about what, anything personal worth remembering, open tasks. No headings, no markdown, no phone numbers.",
                       f"PROFILE:\n{rec.get('profile', '')[:4000]}\n\nRECENT TIMELINE (newest last):\n{timeline[-6000:]}", timeout=40)
    return _with_note(no_em_dash(facts.strip()), contact), contact


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


async def _open_screen(db, user: dict, args: dict, focus: Optional[dict] = None, live: Optional[dict] = None):
    screen = _screen_of(args.get("what") or "")
    if screen in ("tasks", "home", "inbox"):
        return {"tasks": "Your tasks are up on your screen.", "home": "Home is up.", "inbox": "Your inbox is up."}[screen], _open_target(screen)
    contact, err = await _resolve(db, str(user["_id"]), args.get("name") or "", focus, args.get("hint") or "", live)
    if err:
        return err, None
    first = contact.get("first_name") or _first_last(contact)
    return _with_note(f"{first}'s text thread is up on your screen." if screen == "thread" else f"{first} is up on your screen.", contact), _open_target(screen, contact)


async def _draft(db, user: dict, contact: dict, intent: str, wording: str = "") -> str:
    if wording and len(wording.strip()) > 8:
        return no_em_dash(wording.strip()[:400])
    from services.contact_ask import build_record
    from services.scripts import _llm
    from services.llm_models import CUSTOMER_TEXT_MODEL
    rec = await build_record(db, contact)
    rep_first = (user.get("name") or "").split(" ")[0]
    text = (await _llm(f"Write ONE text message from {rep_first} (a salesperson) to their customer {contact.get('first_name')}. Under 240 characters, sounds human, first name only, no emojis, no signature, no em dashes, references something real from the record when it helps. Output only the message.",
                       f"Goal: {intent or 'friendly check-in'}\n\nPROFILE:\n{rec.get('profile', '')[:2500]}\n\nRECENT:\n{(rec.get('timeline') or '')[-2500:]}", timeout=40, model=CUSTOMER_TEXT_MODEL)).strip().strip('"')[:400]
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


async def _reminder(db, user: dict, args: dict, focus: Optional[dict] = None, live: Optional[dict] = None):
    from routers.tasks import create_task
    name = (args.get("name") or "").strip()
    contact = None
    if name or focus:
        contact, err = await _resolve(db, str(user["_id"]), name, focus, args.get("hint") or "", live)
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
    return (_with_note(f"Done. Reminder set{who}: {title}, {spoken_when}.", contact) if task else "I could not save that reminder."), task


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


# ── duplicates ────────────────────────────────────────────────────────────────
def _set_line(s: dict) -> str:
    return f"{s['name']} ({len(s['contacts'])} records)"


async def _find_duplicates(db, user: dict, live: Optional[dict]):
    from services import duplicates as dups
    sets = await dups.find_sets(db, str(user["_id"]))
    if live is not None:
        live["_dup_sets"] = sets
    if not sets:
        return "No duplicates. Everyone in your book is one record.", None
    head = ", ".join(_set_line(s) for s in sets[:4])
    more = f", and {len(sets) - 4} more" if len(sets) > 4 else ""
    return (f"You have {len(sets)} set{'s' if len(sets) != 1 else ''} of duplicates: {head}{more}. "
            f"Say 'merge {sets[0]['name'].split(' ')[0]}' and I will read back what goes together first, or clean them up on the screen. It is up now."), {"kind": "duplicates"}


def _pick_set(sets: list, name: str, live: Optional[dict]) -> Optional[dict]:
    words = _name_words(name)
    if words:
        scored = sorted(((max(_score(words, r) for r in s["_rows"]), s) for s in sets), key=lambda x: -x[0])
        return scored[0][1] if scored and scored[0][0] >= 0.8 else None
    last = (live or {}).get("last_choices") or []
    for s in sets:  # "merge them" after Jessi used one of several records for a name
        if any(str(r["_id"]) in last for r in s["_rows"]):
            return s
    return sets[0] if len(sets) == 1 else None


async def _merge_duplicates(db, user: dict, args: dict, live: Optional[dict]):
    from services import duplicates as dups
    name = (args.get("name") or "").strip()
    sets = await dups.find_sets(db, str(user["_id"]))
    if not sets:
        return "No duplicates to merge. Everyone in your book is already one record.", None, None
    s = _pick_set(sets, name, live)
    if not s:
        if name:
            return f"I do not see duplicate records for {name}. What I do see: {', '.join(_set_line(x) for x in sets[:4])}. Which one should I merge?", None, None
        return f"Which one? You have {', '.join(_set_line(x) for x in sets[:4])}.", None, None
    rows = s["_rows"]
    keep, rest = rows[0], rows[1:]
    others = "; ".join(f"one {_describe(r)}" if _norm(_first_last(r)) == _norm(_first_last(keep)) else f"{_first_last(r)} {_describe(r)}" for r in rest[:3])
    pending = {"type": "merge", "name": s["name"], "ids": [str(r["_id"]) for r in rows], "content": f"merge {len(rows)} records for {s['name']}", "at": _now().isoformat()}
    return (f"I found {len(rows)} records for {s['name']}: the one {_describe(keep)}, and {others}. I would keep the first and fold the rest into it; every text, task and note comes along. "
            "Say yes to merge them, or no to leave it."), pending, {"kind": "contact", "id": str(keep["_id"]), "name": _first_last(keep), "first": keep.get("first_name") or ""}


async def _merge_now(db, user: dict, pending: dict):
    from services import duplicates as dups
    try:
        r = await dups.merge_set(db, str(user["_id"]), pending["ids"])
    except Exception as e:
        return f"That merge did not go through: {str(getattr(e, 'detail', None) or e)[:140]}", None
    moved = r["records_migrated"]
    return (f"Done. {pending['name']} is one record now" + (f", {moved} text{'s' if moved != 1 else ''}, tasks and notes moved over." if moved else ".")), {"kind": "contact", "id": r["primary_id"], "name": pending["name"], "first": pending["name"].split(" ")[0]}


# ── day walkthrough ───────────────────────────────────────────────────────────
def _current_stop(live: dict) -> Optional[dict]:
    agenda, pos = live.get("agenda"), live.get("agenda_pos")
    if agenda is None or pos is None or pos >= len(agenda):
        return None
    return agenda[pos]


def _walkthrough_line(live: dict) -> str:
    if live.get("agenda") is None:
        return "DAY WALKTHROUGH: none"
    cur = _current_stop(live)
    if not cur:
        return "DAY WALKTHROUGH: finished, every stop was covered"
    rest = ", ".join(s["name"] for s in live["agenda"][live["agenda_pos"] + 1:][:4])
    return f"DAY WALKTHROUGH: stop {cur['n']} of {len(live['agenda'])} is {cur['name']} ({cur['kind']}: {cur['why']}). Coming up: {rest or 'nothing, this is the last one'}."


async def _advance(db, user: dict, live: dict, action: str, prefix: str = ""):
    """Settle the current stop (done / skip / next) and hand back the next one; updates the live doc so the next delegation continues from there."""
    from services import day_agenda
    cur = _current_stop(live)
    if not cur:
        return prefix + day_agenda.outro(len(live.get("agenda_done") or []), len(live.get("agenda_skipped") or []), len(live.get("agenda") or [])), {"kind": "home"}
    sets = {"agenda_pos": live["agenda_pos"] + 1}
    push = {}
    if action in ("done", "skip"):
        try:
            await day_agenda.settle(db, str(user["_id"]), cur, action)
        except Exception as e:
            logger.warning(f"[Live] could not settle stop {cur.get('key')}: {e}")
        push = {"agenda_done" if action == "done" else "agenda_skipped": cur["key"]}
    nxt = live["agenda"][live["agenda_pos"] + 1] if live["agenda_pos"] + 1 < len(live["agenda"]) else None
    if nxt and nxt.get("contact_id"):
        sets.update(contact_id=nxt["contact_id"], contact_name=nxt["name"])
    await db[COLL].update_one({"_id": live["_id"]}, {"$set": sets, **({"$push": push} if push else {})})
    live.update(sets)
    if push:
        k = next(iter(push))
        live[k] = (live.get(k) or []) + [cur["key"]]
    if not nxt:
        return prefix + day_agenda.outro(len(live.get("agenda_done") or []), len(live.get("agenda_skipped") or []), len(live["agenda"])), {"kind": "home"}
    lead = {"done": "Done. ", "skip": "Skipped. ", "next": ""}[action]
    return f"{prefix}{lead}Next up: {nxt['say']}", day_agenda.open_target(nxt)


# ── who mentioned ─────────────────────────────────────────────────────────────
async def _find_mentions(db, user: dict, args: dict, live: Optional[dict]):
    from services import memory_search as ms
    query = (args.get("query") or "").strip()
    if not query:
        return "What should I look for? Give me the thing they mentioned, like a Tesla Model 3 or a trade-in.", None
    days = int(args.get("days") or 0) or None
    res = await ms.search(db, user, query, days)
    rs = res.get("results") or []
    if live is not None and rs:
        live["last_choices"] = [r["contact_id"] for r in rs[:5]]
        await db[COLL].update_one({"_id": live["_id"]}, {"$set": {"last_choices": live["last_choices"], "contact_id": rs[0]["contact_id"], "contact_name": rs[0]["name"]}})
        live["contact_id"], live["contact_name"] = rs[0]["contact_id"], rs[0]["name"]
    opened = {"kind": "mentions", "query": query, "id": rs[0]["contact_id"] if rs else None, "name": rs[0]["name"] if rs else "", "first": rs[0]["first"] if rs else ""} if rs else None
    return ms.spoken(res), opened


async def _shopper_delegation(db, live: dict, transcript: list, delegation_id: Optional[str], t0: datetime) -> dict:
    """Audition of the mystery shopper: no tools. The one delegation means 'I said goodbye, hang up'; anything earlier is told to stay in character."""
    from services.live_shops import call_over
    turns = [{"role": "customer" if t.get("role") == "assistant" else "rep", "text": str(t.get("text") or "")} for t in transcript or []]
    over = await call_over(turns)
    tool = "hang_up" if over else "stay_in_character"
    content = "The line is disconnecting now. Say nothing more." if over else "There is no backend help on this call. Stay in character, answer from what you know as this customer, and keep the conversation going."
    ms = int((_now() - t0).total_seconds() * 1000)
    await db[COLL].update_one({"_id": live["_id"]}, {"$push": {"delegations": {"id": delegation_id, "tool": tool, "args": {}, "result": content, "open": None, "ms": ms, "at": _now()}}, "$set": {"updated_at": _now()}})
    return {"tool": tool, "content": content, "kind": "thinking", "pending": False, "open": None, "end": over, "ms": ms}


async def delegate(db, live: dict, user: dict, transcript: list, delegation_id: Optional[str]) -> dict:
    """One delegation from GPT-Live: plan a tool from the transcript, run it, hand back a short spoken result."""
    from services.scripts import _llm_json
    t0 = _now()
    if live.get("mode") == "shopper":
        return await _shopper_delegation(db, live, transcript, delegation_id, t0)
    convo = "\n".join(f"{'JESSI' if t.get('role') == 'assistant' else 'REP'}: {str(t.get('text', ''))[:400]}" for t in (transcript or [])[-16:])
    pending = live.get("pending")
    focus = await focus_contact(db, user, live.get("contact_id")) if live.get("contact_id") else None
    focus_txt = f"FOCUS CONTACT: {_first_last(focus)} (the rep opened Jessi from this person's record)" if focus else "FOCUS CONTACT: none"
    tz = await _tz(user)
    tz_line = f"NOW (rep's local time, {getattr(tz, 'key', 'UTC')}): {_now().astimezone(tz).strftime('%A %Y-%m-%d %H:%M')}. Return when_iso in this local time without a Z suffix."
    plan = {}
    try:
        plan = await _llm_json(BRAIN_SYSTEM, f"{tz_line}\n{focus_txt}\n{_walkthrough_line(live)}\nPENDING ACTION: {json.dumps({k: pending[k] for k in ('type', 'name', 'content') if k in pending}) if pending else 'none'}\n\nTRANSCRIPT (oldest first):\n{convo}\n\nDecide the one tool call.", timeout=30)
    except Exception as e:
        logger.warning(f"[Live] brain plan failed: {e}")
    tool = plan.get("tool") if plan.get("tool") in TOOLS else "answer"
    if tool == "next_stop" and live.get("agenda") is None:
        tool = "answer"
    args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
    result, new_pending, kind, opened = "", pending, "commentary", None
    try:
        if tool == "who_today":
            result = await _who_today(db, user)
        elif tool == "find_person":
            contact, err = await _resolve(db, str(user["_id"]), args.get("name") or "", focus, args.get("hint") or "", live)
            if contact:
                result, opened = _with_note(f"Found {_match_line(contact)}. They are up on your screen.", contact), _open_target("contact", contact)
            else:
                result = err
        elif tool == "recall_person":
            result, contact = await _recall(db, user, args.get("name") or ("" if focus else _last_rep_text(transcript)), focus, args.get("hint") or "", live)
            opened = _open_target("contact", contact) if contact else None
        elif tool in ("send_text", "draft_message"):
            contact, err = await _resolve(db, str(user["_id"]), args.get("name") or "", focus, args.get("hint") or "", live)
            if err:
                result = err
            elif not contact.get("phone"):
                result = f"{_first_last(contact)} has no phone number on file, so I cannot text them."
            else:
                content = await _draft(db, user, contact, args.get("intent") or "", args.get("message") or "")
                new_pending = {"type": "send_text", "contact_id": str(contact["_id"]), "name": _first_last(contact), "content": content, "at": _now().isoformat()}
                result = _with_note(f"Here is the text for {contact.get('first_name')}: \"{content}\" Say yes and I will send it, or tell me what to change." if tool == "send_text"
                                    else f"Here is a draft for {contact.get('first_name')}: \"{content}\" Want me to send it, or will you?", contact)
                opened = _open_target("thread", contact)
        elif tool == "set_reminder":
            result, task = await _reminder(db, user, args, focus, live)
            opened = _open_target("task", task=task) if task else None
        elif tool == "confirm":
            if pending and pending.get("type") == "send_text":
                result = await _send_now(db, user, pending)
                opened = {"kind": "thread", "id": pending["contact_id"], "name": pending.get("name") or "", "first": (pending.get("name") or "").split(" ")[0]}
                new_pending = None
                cur = _current_stop(live)
                if cur and cur.get("contact_id") == pending["contact_id"] and result.startswith("Sent"):
                    result, opened = await _advance(db, user, live, "done", prefix=result + " ")
            elif pending and pending.get("type") == "merge":
                result, opened = await _merge_now(db, user, pending)
                new_pending = None
            else:
                result = "There is nothing waiting for a yes right now. What would you like me to do?"
        elif tool == "next_stop":
            action = args.get("action") if args.get("action") in ("next", "skip", "done") else "next"
            result, opened = await _advance(db, user, live, action)
            new_pending = None
        elif tool == "cancel":
            result = ("Okay, cancelled. Nothing was merged." if pending.get("type") == "merge" else "Okay, cancelled. Nothing was sent.") if pending else "Nothing to cancel."
            new_pending = None
        elif tool == "open_screen":
            result, opened = await _open_screen(db, user, args, focus, live)
        elif tool == "find_duplicates":
            result, opened = await _find_duplicates(db, user, live)
        elif tool == "find_mentions":
            result, opened = await _find_mentions(db, user, args, live)
        elif tool == "merge_duplicates":
            result, new_pending, opened = await _merge_duplicates(db, user, args, live)
            new_pending = new_pending or pending
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
