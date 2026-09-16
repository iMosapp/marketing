"""One VA for every industry. Four layers, always in this order:
  1. core: the standard assistant rules everyone gets
  2. industry: vocabulary, tone, what the VA may answer itself and what always goes to the rep (services.industries.VA)
  3. personal: who the rep is and how they text (persona, mostly from the interview)
  4. facts: the only source of specific answers (store facts the manager typed, the rep's own facts, links, store basics)
Lives behind the Test Lab flag `industry_va` until the owner flips it live."""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services import industries as ind
from services import lab

logger = logging.getLogger(__name__)

FEATURE = "industry_va"
MAX_FACTS = 60
TONE = {"casual": "casual and relaxed", "friendly": "friendly and warm", "professional": "professional but personable", "formal": "polished and formal"}
HUMOR = {"none": "no jokes", "light": "a light touch of humor", "some": "some humor when it fits", "moderate": "playful when it fits", "lots": "plenty of humor"}
LENGTH = {"brief": "one short sentence when possible", "balanced": "one or two sentences", "detailed": "two or three sentences, never more"}
EMOJI = {"never": "no emojis", "minimal": "an emoji only once in a while", "light": "an emoji only once in a while", "moderate": "an emoji now and then", "frequent": "emojis are fine"}
_STOP = {"the", "and", "for", "are", "you", "your", "with", "that", "this", "what", "when", "have", "does", "much", "how", "can", "about", "price", "cost", "there", "any", "our", "get", "from", "will", "would", "could", "should"}


async def enabled(db, user: Optional[dict]) -> bool:
    """The owner's account always runs the new VA (Test Lab); everyone else once it is live."""
    if (user or {}).get("role") == "super_admin":
        return True
    return await lab.is_live(db, FEATURE)


async def enabled_for_id(db, user_id) -> bool:
    if not user_id or not ObjectId.is_valid(str(user_id)):
        return await lab.is_live(db, FEATURE)
    u = await db.users.find_one({"_id": ObjectId(str(user_id))}, {"role": 1})
    return await enabled(db, u)


# ---------------------------------------------------------------- facts
def _fact(text: str, me: dict, scope: str) -> dict:
    return {"id": ObjectId().__str__(), "text": text.strip()[:240], "scope": scope, "added_by": str(me["_id"]), "added_by_name": me.get("name"), "at": datetime.now(timezone.utc)}


async def facts_for(db, user: Optional[dict]) -> dict:
    """{store: [...], mine: [...], store_id, store_name, can_edit_store}"""
    from services.lead_flows import MANAGER_ROLES, user_store_id
    if not user:
        return {"store": [], "mine": [], "store_id": None, "store_name": None, "can_edit_store": False}
    sid = user_store_id(user)
    store = await db.stores.find_one({"_id": ObjectId(str(sid))}, {"va_facts": 1, "name": 1}) if sid and ObjectId.is_valid(str(sid)) else None
    return {"store": (store or {}).get("va_facts") or [], "mine": user.get("va_facts") or [], "store_id": str(store["_id"]) if store else None,
            "store_name": (store or {}).get("name"), "can_edit_store": bool(store) and user.get("role") in MANAGER_ROLES}


def _tokens(text: str) -> set:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 3 and w not in _STOP}


def match_facts(message: str, facts: list) -> list:
    """Facts that plausibly answer this message (shared meaningful word), so the VA may answer instead of holding."""
    words = _tokens(message)
    if not words:
        return []
    return [f["text"] for f in facts if _tokens(f.get("text", "")) & words][:6]


def facts_block(facts: list) -> str:
    if not facts:
        return ""
    return "FACTS YOU MAY USE (current and accurate, quote them plainly; if they do not answer the exact question, say you will check):\n" + "\n".join(f"- {t}" for t in facts) + "\n\n"


# ---------------------------------------------------------------- the prompt
def _join(items) -> str:
    return ", ".join(str(x) for x in (items if isinstance(items, list) else [items]) if str(x).strip())


def personal_block(first: str, persona: dict, title: str, store_name: Optional[str], slot: tuple) -> str:
    slot_field, _, slot_label = slot
    lines = []
    if persona.get("bio"):
        lines.append(persona["bio"].strip())
    role = title or persona.get("professional_identity")
    if role or store_name:
        lines.append(f"Role: {role or 'team member'}" + (f" at {store_name}" if store_name else ""))
    for key, label in (("years_experience", "Time in this work"), ("hometown", "From"), ("family_info", "Family"), ("hobbies", "Outside work"), ("fun_facts", "Fun facts"),
                       ("vehicles", slot_label if slot_field == "vehicles" else "Drives"), ("interests", slot_label if slot_field == "interests" else "Interests"),
                       ("specialties", "Known for"), ("ideal_customer", "Favorite customers"), ("personal_motto", "Motto")):
        v = persona.get(key)
        if key == "years_experience" and str(v or "").strip().isdigit():
            v = f"{v} years"
        if v and _join(v):
            lines.append(f"{label}: {_join(v)}")
    return "\n".join(lines) if lines else f"{first} has not told us much yet. Stay warm and general, never invent details about them."


def style_block(first: str, persona: dict) -> str:
    bits = [TONE.get(persona.get("tone") or "", None), HUMOR.get(persona.get("humor_level") or "", None), LENGTH.get(persona.get("response_length") or persona.get("brevity") or "", None),
            EMOJI.get(persona.get("emoji_usage") or persona.get("emoji_use") or "", None)]
    bits = [b for b in bits if b]
    return f"{first} texts {', '.join(bits)}." if bits else f"{first} texts like a real person: short, warm, contractions, one thought at a time."


def build_text(user: dict, store: Optional[dict], vab: dict, facts: dict) -> str:
    name = user.get("name") or "the rep"
    first = name.split(" ")[0]
    persona = user.get("persona") or {}
    store_name = (store or {}).get("name")
    basics = []
    if store:
        basics.append(f"{vab['business'].capitalize()}: {store_name}")
        if store.get("address"):
            basics.append(f"Address: {store['address']}")
        if store.get("phone"):
            basics.append(f"Main line: {store['phone']}")
        if store.get("hours"):
            basics.append(f"Hours: {store['hours'] if isinstance(store['hours'], str) else ', '.join(f'{k} {v}' for k, v in store['hours'].items())}")
    links = [f"Scheduling link: {persona['scheduling_link']}" if persona.get("scheduling_link") else "", f"Payment link: {persona['payment_link']}" if persona.get("payment_link") else "",
             f"Other links: {persona['key_links']}" if persona.get("key_links") else ""]
    fact_lines = [f"- {f['text']}" for f in (facts.get("store") or [])] + [f"- {f['text']}" for f in (facts.get("mine") or [])] + [f"- {l}" for l in links if l] + [f"- {b}" for b in basics]
    never = [str(x) for x in ((persona.get("never_say") if isinstance(persona.get("never_say"), list) else [persona.get("never_say")]) or []) if x]
    banned = [x.strip() for x in str(persona.get("banned_words") or "").replace("\n", ",").split(",") if x.strip()]
    from utils.text_sanitize import format_phone_display
    work_number = user.get("twilio_number") or user.get("mvpline_number")
    return (
        f"You ARE {name}. Every text comes from {name} personally, from their own phone, and the customer believes that. Speak as \"I\", never as a team or an assistant.\n\n"
        f"WHO {first.upper()} IS\n{personal_block(first, persona, user.get('title') or '', store_name, vab['slot'])}\n\n"
        f"HOW {first.upper()} TEXTS\n{style_block(first, persona)} Like texting a friend you genuinely like: warm, zero pressure, interested in them as a person. "
        "When they share something personal, acknowledge it before anything else.\n\n"
        f"THE BUSINESS ({vab['label']})\nYou work at a {vab['business']}. The people texting you are {vab['customer']}s; what they come to you for is a {vab['offering']}. {vab['tone']}\n\n"
        "WHAT YOU MAY HANDLE YOURSELF\n" + "\n".join(f"- {s}" for s in vab["safe"]) + "\n- anything covered word for word in FACTS below\n\n"
        "FACTS (the ONLY source of specifics; if it is not here or not handed to you in the message, you do not know it)\n"
        + ("\n".join(fact_lines) if fact_lines else "- Nothing confirmed yet beyond who you are.") + "\n\n"
        f"WHAT GOES TO {first.upper()} PERSONALLY (never answer these yourself, even when you think you know)\n" + "\n".join(f"- {h}" for h in vab["hold"]) + "\n"
        "When one comes up: one warm line that says you will check and get right back to them, then STOP. Do not ask qualifying questions about it (budget, money down, credit, trade, timeline), "
        "do not explain what affects it, no guessing, no estimates, no \"usually\" or \"typically\", no ranges. Example: \"Let me pull the exact numbers on that and get right back to you.\"\n\n"
        "RULES\n"
        "- 1 to 2 sentences. If you can say it in fewer words, do. One question max, and never one they already answered.\n"
        "- Read the whole conversation first. Never repeat yourself, never circle back to something covered.\n"
        "- Know when to stay quiet: a short \"sounds good!\" often beats another question.\n"
        "- Never push, never close, never rush. The relationship is the job.\n"
        "- You are a real person. Never say robot, AI, bot, assistant, automated or anything like it. If asked, answer warmly like a person would (\"Ha, no, it's me, just behind on texts!\") and keep going.\n"
        "- Never write a web address unless it is in FACTS. Never quote a number that is not in FACTS or in live data given to you.\n"
        "- No em dashes. Use a comma or a period.\n"
        + (f"- Your work number is {format_phone_display(work_number)}. If they ask how to reach you, that is the ONLY number you give.\n" if work_number else "")
        + (f"- NEVER say or write: {', '.join(never + banned)}\n" if never or banned else "")
    )


async def build(db, user_id, purpose: str = "reply") -> str:
    user = await db.users.find_one({"_id": ObjectId(str(user_id))}) if user_id and ObjectId.is_valid(str(user_id)) else None
    if not user:
        return build_text({"name": "the rep"}, None, ind.va("general"), {})
    from services.lead_flows import user_store_id
    sid = user_store_id(user)
    store = await db.stores.find_one({"_id": ObjectId(str(sid))}, {"name": 1, "address": 1, "phone": 1, "hours": 1, "industry": 1}) if sid and ObjectId.is_valid(str(sid)) else None
    industry = await ind.va_industry_for(db, user)
    return build_text(user, store, ind.va(industry["key"]), await facts_for(db, user))


async def config(db, user: dict) -> dict:
    """What the My VA screen shows: industry (and whether the rep may pick one), scenarios, facts counts, flag state."""
    industry = await ind.va_industry_for(db, user)
    vab = ind.va(industry["key"])
    facts = await facts_for(db, user)
    return {"available": await enabled(db, user), "industry": industry, "can_pick_industry": industry["source"] != "store", "industries": ind.va_options(),
            "scenarios": vab["scenarios"], "hold": vab["hold"], "safe": vab["safe"], "tone": vab["tone"],
            "facts": {"store": len(facts["store"]), "mine": len(facts["mine"]), "store_name": facts["store_name"], "can_edit_store": facts["can_edit_store"]}}


async def routing(db, user_id) -> Optional[dict]:
    """What inbound routing needs when the new VA is on for this rep: the industry's hold words and every fact the VA may answer with. None = old behaviour."""
    user = await db.users.find_one({"_id": ObjectId(str(user_id))}) if user_id and ObjectId.is_valid(str(user_id)) else None
    if not user or not await enabled(db, user):
        return None
    industry = await ind.va_industry_for(db, user)
    vab = ind.va(industry["key"])
    facts = await facts_for(db, user)
    return {"industry": industry["key"], "hold_words": vab["hold_words"], "finance_words": vab["finance_words"], "facts": (facts["store"] or []) + (facts["mine"] or [])}
