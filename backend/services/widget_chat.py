"""Chat now: Jessi on the dealership's website. Answers hours / store facts / specials / live inventory; anything about price,
payments, trade value or "talk to a person" is handed to the team: she collects name + mobile and the visitor becomes a lead
through the same intake pipeline as Text us (store-line text, rep ping, transcript in the thread)."""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone, date
from typing import Optional

from bson import ObjectId

from services import widgets as W
from services.llm_models import CUSTOMER_TEXT_MODEL
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "widget_chats"
MAX_TURNS = 40
HISTORY = 14
LLM_TIMEOUT_S = 25

HANDOFF = re.compile(r"\b(price|prices|pricing|cost|costs|how much|payment|payments|monthly|per month|a month|lease|leasing|financ\w*|apr|interest rate|"
                     r"trade[- ]?in|trade value|my trade|discount|discounts|deal|deals|negotiat\w*|best price|out the door|otd|msrp|down payment|"
                     r"rebate|rebates|incentive|incentives|cheaper|lowest|haggle|make an offer|what would you take|bottom line|money down)\b", re.I)
HUMAN = re.compile(r"\b((talk|speak|chat)\s+(to|with)\s+(a\s+|an\s+)?(someone|somebody|real|human|person|sales|rep|manager|agent|live))|"
                   r"(real person|a human|salesperson|sales rep|representative|call me|someone call|have someone|actual person)\b", re.I)
PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})\b")
NAME = re.compile(r"\b(?:i am|i'm|im|my name is|this is|it's|its|name's)\s+([A-Z][a-zA-Z'-]{1,20})(?:\s+([A-Z][a-zA-Z'-]{1,25}))?", re.I)
DAYS = [("monday", "Mon"), ("tuesday", "Tue"), ("wednesday", "Wed"), ("thursday", "Thu"), ("friday", "Fri"), ("saturday", "Sat"), ("sunday", "Sun")]

FALLBACK = "Good question. Let me get a team member to answer that properly, they can text you in a minute. What's your first name and mobile number?"
CONFIRM = "Done, {first}. {store} just texted you at {phone}, reply there and a real person takes it from here. Anything else I can look up while you wait?"
ASK_CONTACT = "That one is a team member's call, not mine, and they're quick. What's your first name and mobile number? They'll text you right away."


def _now():
    return datetime.now(timezone.utc)


def _t12(hhmm: str) -> str:
    try:
        h, m = (int(x) for x in hhmm.split(":")[:2])
        return f"{(h % 12) or 12}{'' if m == 0 else ':%02d' % m} {'AM' if h < 12 else 'PM'}"
    except Exception:
        return hhmm


def hours_lines(store: dict) -> list:
    hours = (store or {}).get("business_hours") or {}
    out = []
    for key, label in DAYS:
        d = hours.get(key)
        if not d or d.get("closed") or not (d.get("open") and d.get("close")):
            out.append(f"{label}: closed")
        else:
            out.append(f"{label}: {_t12(d['open'])} to {_t12(d['close'])}")
    return out if hours else []


def _active_specials(kb: dict) -> list:
    today = date.today().isoformat()
    return [s for s in kb.get("specials") or [] if (s.get("title") or "").strip() and (not s.get("ends") or s["ends"] >= today)]


def never_hit(kb: dict, text: str) -> Optional[str]:
    words = set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))
    for item in kb.get("never") or []:
        toks = [t for t in re.findall(r"[a-z0-9]{3,}", item.lower()) if t not in ("the", "and", "our", "your", "any", "about", "questions", "question")]
        if toks and all(t in words for t in toks):
            return item
    return None


async def inventory_lines(db, store_id: str, message: str, share_prices: bool) -> tuple:
    """(lines, total_available). Lines only when the visitor is clearly asking about vehicles."""
    from services import vehicle_search as vs
    if not store_id:
        return [], 0
    scope = {"store_id": str(store_id), "status": "available", "is_visible": {"$ne": False}}
    total = await db.inventory.count_documents(scope)
    if not total:
        return [], 0
    q = vs.parse_query(message or "")
    if not q["tokens"] and not q["has_filters"]:
        return [], total
    items = await db.inventory.find(scope).limit(400).to_list(400)
    matches, exact = vs.select_matches(items, q)
    lines = []
    for it in matches[:5]:
        d = vs.describe_vehicle(it)
        if not share_prices:
            d = re.sub(r"\s·\s\$[\d,]+", "", d)
        lines.append(("" if exact else "(closest) ") + d)
    if matches and len(matches) > 5:
        lines.append(f"...and {len(matches) - 5} more like these in stock")
    return lines, total


def knowledge_text(store: dict, kb: dict, facts: list, inv_lines: list, inv_total: int) -> str:
    name = store.get("name") or "the store"
    parts = [f"STORE: {name}"]
    addr = ", ".join(str(x) for x in [store.get("address"), store.get("city"), store.get("state"), store.get("zip") or store.get("zip_code")] if x)
    if addr:
        parts.append(f"ADDRESS: {addr}")
    if store.get("phone") or store.get("main_phone"):
        parts.append(f"MAIN PHONE: {store.get('phone') or store.get('main_phone')}")
    if store.get("website"):
        parts.append(f"WEBSITE: {store['website']}")
    hl = hours_lines(store)
    parts.append("HOURS:\n" + "\n".join(hl) if hl else "HOURS: not on file (say you will have the team confirm)")
    if facts:
        parts.append("STORE FACTS (accurate, quote plainly):\n" + "\n".join(f"- {f}" for f in facts[:30]))
    sp = _active_specials(kb)
    if sp:
        parts.append("CURRENT SPECIALS (you may mention these exactly as written, never add numbers of your own):\n" + "\n".join(
            f"- {s['title']}" + (f": {s['details']}" if s.get("details") else "") + (f" (through {s['ends']})" if s.get("ends") else "") for s in sp[:10]))
    if (kb.get("notes") or "").strip():
        parts.append("MORE FROM THE MANAGER:\n" + kb["notes"].strip()[:2000])
    if inv_total:
        parts.append(f"INVENTORY: {inv_total} vehicles available right now." + ("\nMATCHES FOR WHAT THEY ASKED:\n" + "\n".join(f"- {l}" for l in inv_lines) if inv_lines else ""))
    else:
        parts.append("INVENTORY: no live inventory feed connected, so do not claim anything is or is not in stock; offer to have the team check.")
    return "\n\n".join(parts)


def system_prompt(store: dict, kb: dict, knowledge: str, mode: str, have_contact: bool) -> str:
    name = store.get("name") or "the store"
    never = "; ".join(kb.get("never") or []) or "none listed"
    price_rule = ("You may state a vehicle's listed price only when it appears in the inventory lines. " if kb.get("share_listed_prices")
                  else "Never state prices, even listed ones. ")
    base = (
        f"You are Jessi, the assistant in the chat window on {name}'s website. You are talking to a website visitor, not a customer on file.\n"
        "STYLE: warm, quick, plain English. One to three short sentences. No bullet lists longer than three items, no emojis, no em dashes, no headings. "
        "Never invent facts, hours, availability, policies or numbers. If the knowledge below does not cover it, say so in one sentence and offer to have a team member text them.\n"
        f"HARD RULES: {price_rule}Never quote or negotiate payments, lease or finance terms, APR, trade-in values, discounts, rebates or 'best price'; "
        f"never discuss: {never}. Those belong to a team member. Never pretend to be human; if asked, you are Jessi, the store's assistant, and a real person is one tap away. "
        "Do not ask for their contact details unless a hand-off is happening.\n\n"
        f"WHAT YOU KNOW:\n{knowledge}\n"
    )
    if mode == "handoff":
        base += ("\nMODE: HAND-OFF. The visitor asked something only a team member handles. In one or two sentences say a real person on the team will take it and that they are fast. "
                 + ("Their name and mobile are already on file, so tell them the team is texting them right now and offer to keep helping with anything else meanwhile."
                    if have_contact else "Ask for their first name and mobile number so the team can text them right away. Do not answer the priced question itself."))
    elif mode == "handed_off":
        base += "\nMODE: A team member already has this visitor's number and is texting them. Keep helping with simple questions; if they ask a priced question again, remind them the team member has it over text."
    return base


async def _llm(system: str, transcript: str) -> Optional[str]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return None
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=api_key, session_id=f"wchat_{secrets.token_hex(4)}", system_message=system).with_model(*CUSTOMER_TEXT_MODEL)
    try:
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=transcript)), timeout=LLM_TIMEOUT_S)
    except Exception as e:
        logger.warning(f"[WidgetChat] LLM failed: {e}")
        return None
    text = no_em_dash((out if isinstance(out, str) else str(out)).strip())
    return re.sub(r"\n{3,}", "\n\n", text)[:900] or None


def _transcript(session: dict, limit: int = HISTORY) -> str:
    rows = [m for m in session.get("messages") or [] if m.get("role") in ("visitor", "jessi")][-limit:]
    return "\n".join(f"{'Visitor' if m['role'] == 'visitor' else 'Jessi'}: {m['text']}" for m in rows)


async def store_facts(db, store: dict) -> list:
    return [f.get("text") for f in (store or {}).get("va_facts") or [] if f.get("text")]


# ---------------------------------------------------------------- sessions
async def start(db, w: dict, body: dict, ip: str) -> dict:
    if not W.allow(ip, "chat_start", 10):
        raise ValueError("Too many chats started from this connection. Give it a minute.")
    cfg = W.normalize_config(w)
    store = await W.store_of(db, w)
    greeting = (cfg["kb"].get("welcome") or "").strip() or f"Hi! I'm Jessi, {store.get('name') or 'the store'}'s assistant. Ask me about hours, what's in stock or anything about the store. Want a person? Just say so."
    greeting = greeting.replace("{store}", store.get("name") or "").replace("{{store_name}}", store.get("name") or "")
    doc = {"sid": secrets.token_urlsafe(18), "widget_id": str(w["_id"]), "key": w["key"], "store_id": w.get("store_id"),
           "visitor": (body.get("visitor") or "")[:64], "page": (body.get("page") or "")[:500], "title": (body.get("title") or "")[:200], "host": W.host_of(body.get("page") or ""),
           "name": "", "phone": "", "status": "open", "awaiting_contact": False, "handoff_reason": "", "turns": 0,
           "messages": [{"role": "jessi", "text": greeting, "at": _now()}], "created_at": _now(), "updated_at": _now(), "ip": ip}
    await db[COLL].insert_one(doc)
    await W.log_event(db, w, "chat", {**body, "door": "chat"})
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.chats": 1}})
    return {"sid": doc["sid"], "greeting": greeting, "status": "open"}


async def load(db, key: str, sid: str) -> Optional[dict]:
    return await db[COLL].find_one({"key": key, "sid": sid}) if sid else None


def public_state(session: dict) -> dict:
    return {"sid": session["sid"], "status": session.get("status"), "need_contact": bool(session.get("awaiting_contact")) and not session.get("phone"),
            "name": session.get("name") or "", "has_phone": bool(session.get("phone")),
            "messages": [{"role": m["role"], "text": m["text"]} for m in (session.get("messages") or []) if m.get("role") in ("visitor", "jessi")][-60:]}


def _detect(kb: dict, text: str) -> str:
    if HUMAN.search(text or ""):
        return "asked for a person"
    if HANDOFF.search(text or ""):
        return "pricing / payments / trade"
    hit = never_hit(kb, text)
    return f"topic the store keeps for the team ({hit})" if hit else ""


async def reply(db, w: dict, session: dict, text: str, ip: str) -> dict:
    text = " ".join((text or "").split())[:1000]
    if not text:
        raise ValueError("Say something first.")
    if not W.allow(ip, "chat_msg", 20):
        raise ValueError("Slow down a little, one message at a time.")
    if session.get("turns", 0) >= MAX_TURNS:
        return {**public_state(session), "reply": "We've covered a lot. A team member can pick this up by text, tap Talk to a person and they'll reach out."}
    cfg = W.normalize_config(w)
    kb = cfg["kb"]
    store = await W.store_of(db, w)
    msgs = list(session.get("messages") or []) + [{"role": "visitor", "text": text, "at": _now()}]
    session["messages"] = msgs
    updates: dict = {"turns": session.get("turns", 0) + 1, "updated_at": _now()}

    # names / phones the visitor types in passing
    nm = NAME.search(text)
    if nm and not session.get("name"):
        session["name"] = updates["name"] = " ".join(x for x in nm.groups() if x)
    ph = PHONE.search(text)
    phone = W.clean_phone("".join(ph.groups())) if ph else ""

    reason = _detect(kb, text) if session.get("status") != "handed_off" else ""
    mode = "normal"
    answer = None
    if session.get("status") == "handed_off":
        mode = "handed_off"
    elif session.get("awaiting_contact") and phone:
        answer = await _handoff(db, w, session, phone, session.get("name") or "", cfg, store)
    elif reason or session.get("awaiting_contact"):
        mode = "handoff"
        if reason:
            updates["handoff_reason"] = session["handoff_reason"] = reason
        if session.get("phone"):
            answer = await _handoff(db, w, session, session["phone"], session.get("name") or "", cfg, store)
        else:
            updates["awaiting_contact"] = session["awaiting_contact"] = True
    if answer is None:
        inv_lines, inv_total = await inventory_lines(db, w.get("store_id"), text, bool(kb.get("share_listed_prices")))
        knowledge = knowledge_text(store, kb, await store_facts(db, store), inv_lines, inv_total)
        system = system_prompt(store, kb, knowledge, mode, bool(session.get("phone")))
        answer = await _llm(system, _transcript(session) + "\n\nReply to the visitor's last line as Jessi.")
        if not answer:
            answer = ASK_CONTACT if mode == "handoff" else FALLBACK
            if mode != "handoff" and not session.get("phone"):
                updates["awaiting_contact"] = session["awaiting_contact"] = True
    msgs.append({"role": "jessi", "text": answer, "at": _now()})
    updates["messages"] = msgs
    for k in ("status", "phone", "name", "lead_id", "contact_id", "conversation_id", "awaiting_contact", "handed_off_at"):
        if k in session and k not in updates:
            updates[k] = session[k]
    await db[COLL].update_one({"_id": session["_id"]}, {"$set": updates})
    session.update(updates)
    return {**public_state(session), "reply": answer, "handoff": mode == "handoff" or session.get("status") == "handed_off"}


async def request_human(db, w: dict, session: dict) -> dict:
    """The visitor tapped 'Talk to a person'."""
    cfg = W.normalize_config(w)
    store = await W.store_of(db, w)
    if session.get("status") == "handed_off":
        text = "A team member already has your number and is texting you now. Keep an eye on your phone."
    elif session.get("phone"):
        text = await _handoff(db, w, session, session["phone"], session.get("name") or "", cfg, store, reason="asked for a person")
    else:
        session["awaiting_contact"] = True
        session["handoff_reason"] = "asked for a person"
        text = "Happy to. What's your first name and mobile number? A team member will text you in a minute."
    msgs = list(session.get("messages") or []) + [{"role": "jessi", "text": text, "at": _now()}]
    session["messages"] = msgs
    await db[COLL].update_one({"_id": session["_id"]}, {"$set": {k: session.get(k) for k in ("messages", "awaiting_contact", "handoff_reason", "status", "phone", "name", "lead_id", "contact_id", "conversation_id")} | {"updated_at": _now()}})
    return {**public_state(session), "reply": text, "handoff": True}


async def give_contact(db, w: dict, session: dict, body: dict, ip: str) -> dict:
    """The inline name + mobile form inside the chat."""
    name, phone = " ".join((body.get("name") or "").split())[:80], W.clean_phone(body.get("phone") or "")
    if not name or not phone:
        raise ValueError("Please add your first name and a 10 digit mobile number.")
    if not W.allow(ip, "lead", 5):
        raise ValueError("Please wait a minute before sending again.")
    cfg = W.normalize_config(w)
    store = await W.store_of(db, w)
    if session.get("status") == "handed_off":
        text = "You're already in, a team member is texting you now."
    else:
        text = await _handoff(db, w, session, phone, name, cfg, store)
    msgs = list(session.get("messages") or []) + [{"role": "jessi", "text": text, "at": _now()}]
    session["messages"] = msgs
    await db[COLL].update_one({"_id": session["_id"]}, {"$set": {k: session.get(k) for k in ("messages", "awaiting_contact", "handoff_reason", "status", "phone", "name", "lead_id", "contact_id", "conversation_id")} | {"updated_at": _now()}})
    return {**public_state(session), "reply": text, "handoff": True}


async def _handoff(db, w: dict, session: dict, phone: str, name: str, cfg: dict, store: dict, reason: str = "") -> str:
    """Create the lead through the intake pipeline; the transcript lands in the thread; the visitor gets the store-line text."""
    first, last = W.split_name(name or "Website Visitor")
    reason = reason or session.get("handoff_reason") or "asked for a person"
    source = await db.lead_sources.find_one({"_id": ObjectId(w["lead_source_id"])}) if w.get("lead_source_id") else None
    if not source:
        w["lead_source_id"] = await W.sync_lead_source(db, w, store)
        await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"lead_source_id": w["lead_source_id"]}})
        source = await db.lead_sources.find_one({"_id": ObjectId(w["lead_source_id"])})
    transcript = _transcript(session, 40)
    page = session.get("page") or ""
    normalized = {
        "first_name": first, "last_name": last, "full_name": f"{first} {last}".strip(), "phone": phone,
        "comments": f"Web chat hand-off ({reason}) from {W.host_of(page) or 'the website'}{f' ({page})' if page else ''}.\n\nTranscript:\n{transcript}"[:4000],
        "source_name": source.get("name"),
        "extra_fields": {"widget_key": w["key"], "door": "chat", "page_url": page[:500], "page_title": session.get("title") or "", "visitor": session.get("visitor") or "", "chat_sid": session["sid"], "handoff_reason": reason},
    }
    src = dict(source)
    store_name = store.get("name") or "our team"
    src["intake_text"] = (cfg["routing"].get("chat_intake_text") or "").replace("{{first_name}}", first).replace("{first_name}", first).replace("{{store_name}}", store_name).replace("{store_name}", store_name)
    from routers.lead_intake import process_inbound_lead
    res = await process_inbound_lead(normalized, src, db, raw_body="")
    if res.get("conversation_id"):
        await db.messages.insert_one({"conversation_id": res["conversation_id"], "contact_id": res.get("contact_id"), "sender": "contact", "direction": "inbound", "channel": "webchat",
                                      "type": "webchat_transcript", "content": f"Web chat on {W.host_of(page) or 'the website'} (Jessi handed off: {reason}):\n\n{transcript}"[:3000],
                                      "read": False, "timestamp": _now(), "created_at": _now()})
        await db.conversations.update_one({"_id": ObjectId(res["conversation_id"])}, {"$set": {"last_message_at": _now(), "status": "active"}})
    session.update({"status": "handed_off", "awaiting_contact": False, "phone": phone, "name": name or session.get("name") or "", "lead_id": res.get("lead_id"),
                    "contact_id": res.get("contact_id"), "conversation_id": res.get("conversation_id"), "handed_off_at": _now(), "handoff_reason": reason})
    await W.log_event(db, w, "lead", {"page": page, "door": "chat", "visitor": session.get("visitor")})
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.chat_handoffs": 1}})
    logger.info(f"[WidgetChat] {session['sid']} handed off ({reason}) -> lead {res.get('lead_id')}")
    return CONFIRM.format(first=first, store=store_name, phone=_fmt(phone))


def _fmt(p: str) -> str:
    d = re.sub(r"\D", "", p or "")[-10:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else p


# ---------------------------------------------------------------- manager: "Test Jessi"
async def ask(db, w: dict, question: str) -> dict:
    cfg = W.normalize_config(w)
    kb = cfg["kb"]
    store = await W.store_of(db, w)
    reason = _detect(kb, question)
    inv_lines, inv_total = await inventory_lines(db, w.get("store_id"), question, bool(kb.get("share_listed_prices")))
    facts = await store_facts(db, store)
    knowledge = knowledge_text(store, kb, facts, inv_lines, inv_total)
    system = system_prompt(store, kb, knowledge, "handoff" if reason else "normal", False)
    answer = await _llm(system, f"Visitor: {question}\n\nReply to the visitor's last line as Jessi.") or (ASK_CONTACT if reason else FALLBACK)
    return {"reply": answer, "handoff": bool(reason), "reason": reason, "used": {"facts": len(facts), "specials": len(_active_specials(kb)), "inventory_matches": len([l for l in inv_lines if not l.startswith("...")]),
                                                                                    "inventory_total": inv_total, "hours": bool(hours_lines(store))}}
