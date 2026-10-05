"""Agent Hub: a library of named AI agents (identity, style, job, knowledge, guardrails) built by super admins and
deployed anywhere Jessi talks to a customer: the website chat widget, a lead source's text replies, a shared inbox.
Replaces the old VA Library (ai_va_profiles); existing profiles are migrated once at startup."""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services.llm_models import CUSTOMER_TEXT_MODEL
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "agents"
TONES = {"friendly": "warm, friendly, upbeat", "professional": "polished, professional, calm", "casual": "relaxed, casual, down to earth",
         "energetic": "energetic, enthusiastic, quick", "direct": "direct, concise, no small talk"}
BREVITY = {"short": "One to three short sentences", "medium": "Two to four sentences, a short list of up to four items is fine when they ask what is included"}
EMOJI = {"never": "No emojis", "mirror": "Emojis only if the customer uses them first"}
LANGUAGES = {"auto": "", "en": "Always reply in English.", "es": "Always reply in Spanish (natural, Latin American), even when the customer writes in English.",
             "nl": "Always reply in Dutch (natural, informal 'je'), even when the customer writes in English."}
STATUSES = ("active", "draft", "archived")
COLORS = ("#C9A962", "#34C759", "#FF9500", "#AF52DE", "#FF3B30", "#007AFF", "#5856D6", "#FF2D55")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
MIGRATION_ID = "agents_from_va_profiles_2026_10"

DEFAULTS = {"name": "", "title": "", "tagline": "", "avatar_color": "#C9A962", "photo_url": "", "tone": "friendly", "brevity": "short", "emoji": "never",
            "goal": "", "instructions": "", "specialties": "", "facts": [], "never_say": [], "hand_to_human": [], "always_collect": [],
            "language": "auto", "custom_prompt": "", "status": "active"}

STARTERS = [
    {"key": "internet_sales", "name": "Ava", "title": "Internet Sales Assistant", "tagline": "Fast, warm, gets them in the door", "avatar_color": "#C9A962", "tone": "friendly",
     "goal": "Set a time for the customer to come in", "specialties": "New and pre-owned vehicles, trade-ins, scheduling a visit",
     "instructions": "Thank them for reaching out and answer their question first. Find out what they are looking for, whether they have a trade, and when they could come by. Offer two specific times rather than asking an open question. Keep every text short and end with one question.",
     "always_collect": ["Vehicle or type of vehicle they want", "Whether they have a trade-in", "A day and time to come in"],
     "hand_to_human": ["Price or payments", "Trade-in value", "Financing or credit", "Discounts or best price"],
     "never_say": ["As an AI", "I apologize for the delay", "Unfortunately"]},
    {"key": "service_scheduler", "name": "Max", "title": "Service Scheduler", "tagline": "Gets the car booked in two texts", "avatar_color": "#34C759", "tone": "professional",
     "goal": "Book the service visit", "specialties": "Service appointments, maintenance intervals, loaners and shuttles, recalls",
     "instructions": "Find out the year, make and model, what the car needs, and whether they need a loaner or shuttle. Offer the two soonest openings. Never diagnose over text or quote repair costs; say the advisor will confirm once they see the car.",
     "always_collect": ["Year, make and model", "What the car needs", "Preferred day and time"],
     "hand_to_human": ["Repair cost or estimates", "Warranty coverage decisions", "A complaint about past work"],
     "never_say": ["It is probably", "That should be cheap", "As an AI"]},
    {"key": "website_concierge", "name": "Jessi", "title": "Website Concierge", "tagline": "Answers in one breath, books the visit", "avatar_color": "#007AFF", "tone": "friendly",
     "goal": "Answer fast and book a visit", "specialties": "Hours, directions, what is in stock, specials, booking a visit",
     "instructions": "Answer the visitor's question in one or two sentences from what you know, then offer the natural next step: book a visit, or a quick text from the team. Never make the visitor repeat themselves.",
     "always_collect": ["First name", "Mobile number before a hand-off"],
     "hand_to_human": ["Price or payments", "Trade-in value", "Negotiating"],
     "never_say": ["I do not have that information", "As an AI"]},
    {"key": "after_hours", "name": "Riley", "title": "After-Hours Assistant", "tagline": "Keeps the lead warm until the doors open", "avatar_color": "#5856D6", "tone": "casual",
     "goal": "Keep the customer engaged and set a time for the morning", "specialties": "Taking down what the customer needs so the team can jump on it first thing",
     "instructions": "Say the team is closed right now but you are here, then gather what they are looking for and when they would like a call or a visit. Promise a human follow-up when the store opens and tell them the time it opens if you know it. Never promise availability or pricing.",
     "always_collect": ["What they are looking for", "Best time to reach them tomorrow"],
     "hand_to_human": ["Price or payments", "Anything that needs a decision"],
     "never_say": ["As an AI", "Nobody is here"]},
    {"key": "spanish", "name": "Sofía", "title": "Asistente de Ventas", "tagline": "Atención en español, cálida y rápida", "avatar_color": "#FF9500", "tone": "friendly", "language": "es",
     "goal": "Agendar una visita", "specialties": "Vehículos nuevos y usados, intercambios, citas",
     "instructions": "Responde siempre en español, con calidez y frases cortas. Averigua qué vehículo buscan, si tienen un auto para intercambiar y cuándo pueden venir. Ofrece dos horarios concretos.",
     "always_collect": ["Vehículo que buscan", "Si tienen intercambio", "Día y hora para la visita"],
     "hand_to_human": ["Precio o pagos", "Valor del intercambio", "Financiamiento"],
     "never_say": ["Como IA", "Lamentablemente"]},
    {"key": "demo_setter", "name": "Quinn", "title": "Product Specialist", "tagline": "Knows the product cold, books the demo", "avatar_color": "#AF52DE", "tone": "energetic",
     "goal": "Book a demo", "specialties": "Features, plans and pricing, how setup works, integrations",
     "instructions": "Answer the question directly with a concrete detail (a feature name, a number, how it works), then ask one qualifying question: what kind of business, how big the team, what they want fixed first. After two or three answers, offer a 20 minute demo and two times.",
     "always_collect": ["Kind of business", "Team size", "The one thing they want fixed first"],
     "hand_to_human": ["Custom contracts or enterprise pricing", "Security questionnaires", "Refunds"],
     "never_say": ["I am not sure", "I would need to check", "As an AI"]},
]


def _now():
    return datetime.now(timezone.utc)


def _strs(v, n: int, limit: int) -> list:
    if isinstance(v, str):
        v = [x for x in re.split(r"[\n,;]+", v)]
    return [" ".join(str(x).split())[:n] for x in (v or []) if str(x).strip()][:limit]


def normalize(doc: dict) -> dict:
    a = {**DEFAULTS, **{k: doc.get(k) for k in DEFAULTS if doc.get(k) is not None}}
    for k, n in (("name", 40), ("title", 60), ("tagline", 120), ("goal", 120), ("specialties", 200), ("photo_url", 300)):
        a[k] = " ".join(str(a.get(k) or "").split())[:n]
    for k, n in (("instructions", 2000), ("custom_prompt", 6000)):
        a[k] = str(a.get(k) or "").strip()[:n]
    a["avatar_color"] = a["avatar_color"].upper() if HEX.match(str(a.get("avatar_color") or "")) else COLORS[0]
    if a["photo_url"] and not a["photo_url"].lower().startswith(("http://", "https://", "/")):
        a["photo_url"] = ""
    a["tone"] = a["tone"] if a["tone"] in TONES else "friendly"
    a["brevity"] = a["brevity"] if a["brevity"] in BREVITY else "short"
    a["emoji"] = a["emoji"] if a["emoji"] in EMOJI else "never"
    a["language"] = a["language"] if a["language"] in LANGUAGES else "auto"
    a["status"] = a["status"] if a["status"] in STATUSES else "active"
    a["facts"] = _strs(a["facts"], 220, 30)
    a["never_say"] = _strs(a["never_say"], 80, 20)
    a["hand_to_human"] = _strs(a["hand_to_human"], 80, 20)
    a["always_collect"] = _strs(a["always_collect"], 60, 10)
    return a


def serialize(doc: dict, used_by: Optional[list] = None) -> dict:
    out = {"id": str(doc["_id"]), **normalize(doc), "starter_key": doc.get("starter_key") or "", "created_by_name": doc.get("created_by_name") or "",
           "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else None,
           "updated_at": doc["updated_at"].isoformat() if isinstance(doc.get("updated_at"), datetime) else None}
    if used_by is not None:
        out["used_by"] = used_by
        out["used_count"] = len(used_by)
    return out


# ---------------------------------------------------------------- prompt pieces
def identity_lines(agent: dict, store_name: str) -> list:
    nm = agent["name"] or "Jessi"
    who = f"You are {nm}" + (f", {agent['title']}" if agent.get("title") else "") + f" at {store_name}."
    return [who + f" You are {store_name}'s AI assistant with a name: speak in first person as {nm}, never claim to be a human being, and if anyone asks say you are the AI assistant and a real person is one message away.",
            f"STYLE: {TONES[agent['tone']]}. {BREVITY[agent['brevity']]}. {EMOJI[agent['emoji']]}. Plain English, no em dashes, no headings." + (f" In a few words, you are: {agent['tagline']}." if agent.get("tagline") else "")]


def job_lines(agent: dict) -> list:
    """Goal, instructions, knowledge and guardrails; the part that makes this agent different from the next one."""
    out = []
    if agent.get("custom_prompt"):
        out.append("OWNER'S INSTRUCTIONS (follow these over any general guidance):\n" + agent["custom_prompt"])
    if agent.get("goal"):
        out.append(f"YOUR JOB: {agent['goal']}. Every reply moves toward it without being pushy.")
    if agent.get("instructions"):
        out.append(f"HOW YOU WORK: {agent['instructions']}")
    if agent.get("specialties"):
        out.append(f"YOU KNOW ABOUT: {agent['specialties']}")
    if agent.get("facts"):
        out.append("WHAT YOU KNOW FOR SURE (quote plainly, never add numbers or policies of your own):\n" + "\n".join(f"- {f}" for f in agent["facts"]))
    if agent.get("always_collect"):
        out.append("ALWAYS COLLECT, one at a time and naturally over the conversation: " + "; ".join(agent["always_collect"]) + ".")
    if agent.get("hand_to_human"):
        out.append("HAND TO A PERSON WHEN THEY BRING UP: " + "; ".join(agent["hand_to_human"]) + ". Say a teammate will take that part and do not answer it yourself.")
    if agent.get("never_say"):
        out.append("NEVER SAY OR DO: " + "; ".join(agent["never_say"]) + ".")
    if LANGUAGES.get(agent.get("language") or "auto"):
        out.append("LANGUAGE: " + LANGUAGES[agent["language"]])
    return out


def sms_prompt(agent: dict, store_name: str, rep_first: str = "", dept: str = "") -> str:
    lines = identity_lines(agent, store_name) + job_lines(agent)
    lines.append("CHANNEL: You are texting. Write like a real person texting: short, warm, one question at a time, no bullet points, no signatures, no links unless one is given to you. "
                 "Never invent prices, availability, appointment times or policies; when you do not know, say a teammate will confirm.")
    if dept:
        lines.append(f"This customer texted the {dept} line. Until a teammate claims the thread you are the {dept} team's assistant; when they claim it, they take over.")
    if rep_first:
        lines.append(f"You work alongside {rep_first}, the person on this customer. When something needs a human, say {rep_first} will reach out personally. Never pretend to be {rep_first}.")
    return "\n".join(lines)


def widget_persona(agent: dict) -> dict:
    """What the website chat uses as its 'face': name, title, photo, plus the agent's full brief for the prompt."""
    return {"on": True, "source": "agent", "agent_id": str(agent.get("_id") or agent.get("id") or ""), "name": agent["name"] or "Jessi", "title": agent.get("title") or "",
            "photo": agent.get("photo_url") or "", "tone": TONES[agent["tone"]] + (f"; {agent['tagline']}" if agent.get("tagline") else ""), "intro": "", "agent": agent}


# ---------------------------------------------------------------- lookups
def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if v and ObjectId.is_valid(str(v)) else None


async def get(db, agent_id, active_only: bool = True) -> Optional[dict]:
    oid = _oid(agent_id)
    if not oid:
        return None
    doc = await db[COLL].find_one({"_id": oid})
    if not doc or (active_only and doc.get("status") == "archived"):
        return None
    return {**normalize(doc), "_id": doc["_id"]}


async def for_conversation(db, conv: Optional[dict], assigned: bool) -> Optional[dict]:
    """The agent speaking on this text thread: the shared inbox's agent while nobody owns it, else the lead source's agent."""
    if not conv:
        return None
    if conv.get("inbox_id") and not conv.get("graduated_at") and not assigned:
        inbox = await db.shared_inboxes.find_one({"_id": _oid(conv["inbox_id"])}, {"agent_id": 1}) if _oid(conv.get("inbox_id")) else None
        if inbox and inbox.get("agent_id"):
            return await get(db, inbox["agent_id"])
    if conv.get("lead_source_id"):
        src = await db.lead_sources.find_one({"_id": _oid(conv["lead_source_id"])}, {"agent_id": 1}) if _oid(conv.get("lead_source_id")) else None
        if src and src.get("agent_id"):
            return await get(db, src["agent_id"])
    return None


async def used_by(db, agent_id: str) -> list:
    aid = str(agent_id)
    out = []
    store_ids = set()
    rows = []
    async for w in db.widgets.find({"persona.source": "agent", "persona.agent_id": aid}, {"name": 1, "store_id": 1}):
        rows.append(("widget", str(w["_id"]), w.get("name") or "Website widget", w.get("store_id")))
    async for s in db.lead_sources.find({"agent_id": aid, "kind": {"$nin": ["website_widget", "inbox_direct"]}}, {"name": 1, "store_id": 1}):
        rows.append(("lead_source", str(s["_id"]), s.get("name") or "Lead source", s.get("store_id")))
    async for i in db.shared_inboxes.find({"agent_id": aid}, {"name": 1, "store_id": 1}):
        rows.append(("inbox", str(i["_id"]), i.get("name") or "Inbox", i.get("store_id")))
    for _, _, _, sid in rows:
        if _oid(sid):
            store_ids.add(_oid(sid))
    names = {str(s["_id"]): s.get("name") for s in await db.stores.find({"_id": {"$in": list(store_ids)}}, {"name": 1}).to_list(500)} if store_ids else {}
    for kind, tid, name, sid in rows:
        out.append({"kind": kind, "id": tid, "name": name, "store_id": str(sid) if sid else None, "store_name": names.get(str(sid)) or ""})
    return out


async def targets(db, agent_id: str) -> dict:
    """Everything an agent could be deployed to, with the agent currently on each (for the Deploy sheet)."""
    aid = str(agent_id)
    agents = {str(a["_id"]): a.get("name") for a in await db[COLL].find({}, {"name": 1}).to_list(500)}
    store_ids = set()
    widgets, sources, inboxes = [], [], []
    async for w in db.widgets.find({"is_active": {"$ne": False}}, {"name": 1, "store_id": 1, "persona": 1}).limit(500):
        p = w.get("persona") or {}
        cur = p.get("agent_id") if p.get("on") and p.get("source") == "agent" else None
        widgets.append({"id": str(w["_id"]), "name": w.get("name") or "Website widget", "store_id": w.get("store_id"), "on": cur == aid, "other": agents.get(str(cur or "")) if cur and cur != aid else ""})
        store_ids.add(_oid(w.get("store_id")))
    async for s in db.lead_sources.find({"is_active": {"$ne": False}, "kind": {"$nin": ["website_widget", "inbox_direct"]}}, {"name": 1, "store_id": 1, "agent_id": 1}).limit(500):
        cur = s.get("agent_id")
        sources.append({"id": str(s["_id"]), "name": s.get("name") or "Lead source", "store_id": s.get("store_id"), "on": cur == aid, "other": agents.get(str(cur or "")) if cur and cur != aid else ""})
        store_ids.add(_oid(s.get("store_id")))
    async for i in db.shared_inboxes.find({"is_active": {"$ne": False}}, {"name": 1, "store_id": 1, "agent_id": 1}).limit(500):
        cur = i.get("agent_id")
        inboxes.append({"id": str(i["_id"]), "name": i.get("name") or "Inbox", "store_id": i.get("store_id"), "on": cur == aid, "other": agents.get(str(cur or "")) if cur and cur != aid else ""})
        store_ids.add(_oid(i.get("store_id")))
    store_ids.discard(None)
    names = {str(s["_id"]): s.get("name") for s in await db.stores.find({"_id": {"$in": list(store_ids)}}, {"name": 1}).to_list(500)} if store_ids else {}
    for lst in (widgets, sources, inboxes):
        for r in lst:
            r["store_name"] = names.get(str(r.get("store_id") or "")) or ""
            r["store_id"] = str(r["store_id"]) if r.get("store_id") else None
        lst.sort(key=lambda r: (r["store_name"], r["name"]))
    return {"widgets": widgets, "lead_sources": sources, "inboxes": inboxes}


async def deploy(db, agent_id: str, kind: str, target_id: str, on: bool) -> None:
    oid = _oid(target_id)
    if not oid:
        raise ValueError("Bad target id")
    aid = str(agent_id)
    if kind == "widget":
        w = await db.widgets.find_one({"_id": oid}, {"persona": 1})
        if not w:
            raise ValueError("Widget not found")
        p = dict(w.get("persona") or {})
        if on:
            p.update({"on": True, "source": "agent", "agent_id": aid})
        elif p.get("agent_id") == aid:
            p.update({"on": False, "source": "custom", "agent_id": ""})
        await db.widgets.update_one({"_id": oid}, {"$set": {"persona": p, "updated_at": _now()}})
    elif kind == "lead_source":
        q = {"_id": oid} if on else {"_id": oid, "agent_id": aid}
        await db.lead_sources.update_one(q, {"$set": {"agent_id": aid if on else None, "updated_at": _now()}})
    elif kind == "inbox":
        q = {"_id": oid} if on else {"_id": oid, "agent_id": aid}
        await db.shared_inboxes.update_one(q, {"$set": {"agent_id": aid if on else None, "updated_at": _now()}})
        # the inbox's built-in lead source mirrors the inbox
        await db.lead_sources.update_many({"inbox_id": str(oid), "kind": "inbox_direct"}, {"$set": {"agent_id": aid if on else None}})
    else:
        raise ValueError("Unknown target kind")


# ---------------------------------------------------------------- try it
async def try_reply(agent: dict, messages: list, channel: str, store_name: str) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("Jessi's brain is not configured on this server (EMERGENT_LLM_KEY).")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    if channel == "webchat":
        system = "\n".join(identity_lines(agent, store_name) + job_lines(agent) + [
            "CHANNEL: You are the assistant in the chat window on the company's website, talking to a visitor. Never invent facts, hours, availability or numbers; when you do not know, say so in one sentence and offer a team member."])
    else:
        system = sms_prompt(agent, store_name, rep_first="Sam")
    system += "\nThis is a practice conversation the owner is running to hear how you sound. Stay fully in character."
    rows = [m for m in messages if isinstance(m, dict) and str(m.get("text") or "").strip()][-16:]
    nm = agent["name"] or "Jessi"
    transcript = "\n".join(f"{'Customer' if m.get('role') != 'agent' else nm}: {str(m['text']).strip()[:600]}" for m in rows)
    chat = LlmChat(api_key=api_key, session_id=f"agent_try_{secrets.token_hex(4)}", system_message=system).with_model(*CUSTOMER_TEXT_MODEL)
    out = await asyncio.wait_for(chat.send_message(UserMessage(text=transcript + f"\n\nReply to the customer's last line as {nm}. Just the reply text.")), timeout=30)
    text = no_em_dash((out if isinstance(out, str) else str(out)).strip().strip('"'))
    return text[:1200]


# ---------------------------------------------------------------- one-time migration from the old VA Library
async def migrate_va_profiles(db) -> dict:
    if await db.migrations.find_one({"_id": MIGRATION_ID}):
        return {"skipped": True}
    moved = relinked = 0
    async for p in db.ai_va_profiles.find({}):
        old = str(p["_id"])
        if await db[COLL].find_one({"legacy_va_profile_id": old}, {"_id": 1}):
            continue
        tone = p.get("tone") if p.get("tone") in TONES else "friendly"
        doc = normalize({"name": p.get("name") or "Assistant", "tagline": p.get("tagline") or "", "instructions": p.get("bio") or "", "specialties": p.get("specialties") or "",
                         "tone": tone, "never_say": p.get("never_say") or "", "custom_prompt": p.get("custom_prompt") or "", "avatar_color": p.get("avatar_color") or COLORS[0]})
        doc.update({"legacy_va_profile_id": old, "created_by": p.get("user_id"), "created_at": p.get("created_at") or _now(), "updated_at": _now()})
        res = await db[COLL].insert_one(doc)
        aid = str(res.inserted_id)
        for coll in ("lead_sources", "shared_inboxes"):
            r = await db[coll].update_many({"va_profile_id": old, "agent_id": {"$in": [None, ""]}}, {"$set": {"agent_id": aid}})
            relinked += r.modified_count
        moved += 1
    await db.migrations.insert_one({"_id": MIGRATION_ID, "moved": moved, "relinked": relinked, "ran_at": _now()})
    return {"moved": moved, "relinked": relinked}
