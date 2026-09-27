"""Chat now: Jessi on the dealership's website. Answers hours / store facts / specials / live inventory; anything about price,
payments, trade value or "talk to a person" is handed to the team: she collects name + mobile and the visitor becomes a lead
through the same intake pipeline as Text us (store-line text, rep ping, transcript in the thread).
A rep can also jump into a live chat from the app (mode "human"): Jessi goes quiet, the rep types, the visitor sees it live.
Visitors can book a test drive / service visit inside the chat; that creates the lead, an appointment and a task for the rep."""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone, date, time as dtime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import widgets as W
from services.llm_models import CUSTOMER_TEXT_MODEL
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "widget_chats"
MAX_TURNS = 60
HISTORY = 14
LLM_TIMEOUT_S = 25
LIVE_WINDOW_MIN = 20     # a chat is "live" while something happened in the last 20 minutes
HERE_S = 25              # the visitor still has the window open if it polled in the last 25 s
PUBLIC_ROLES = ("visitor", "jessi", "rep", "system")   # "note" is rep-only
BOOK_KINDS = {"test_drive": "Test drive", "service": "Service visit", "visit": "Store visit"}
BUSINESS_KINDS = {"demo": "Demo", "meeting": "Call with the team"}


def kinds_for(cfg: dict) -> dict:
    return BUSINESS_KINDS if cfg["kb"].get("mode") == "business" else BOOK_KINDS

HANDOFF = re.compile(r"\b(price|prices|pricing|cost|costs|how much|payment|payments|monthly|per month|a month|lease|leasing|financ\w*|apr|interest rate|"
                     r"trade[- ]?in|trade value|my trade|discount|discounts|deal|deals|negotiat\w*|best price|out the door|otd|msrp|down payment|"
                     r"rebate|rebates|incentive|incentives|cheaper|lowest|haggle|make an offer|what would you take|bottom line|money down)\b", re.I)
HUMAN = re.compile(r"\b((talk|speak|chat)\s+(to|with)\s+(a\s+|an\s+)?(someone|somebody|real|human|person|sales|rep|manager|agent|live))|"
                   r"(real person|a human|salesperson|sales rep|representative|call me|someone call|have someone|actual person)\b", re.I)
BOOK = re.compile(r"\b(test[- ]?drive|appointment|appt|schedule|book(ing)?|come (in|by|down)|stop by|swing by|drop (it|my car|the car) off|bring (it|my car) in|"
                  r"come (see|look at|check out)|see it in person|set up a time|what time (can|could) i|oil change|service visit|reserve)\b", re.I)
BOOK_BUSINESS = re.compile(r"\b(demo|walk ?through|walk me through|show me (how|the)|see it in action|schedule|book(ing)?|set up a (time|call|meeting)|appointment|"
                           r"(talk|speak|get) (to|with|on) (a|the) (call|phone)|call with|meeting|consult\w*|get started|sign ?up|start a trial|free trial|onboard\w*)\b", re.I)
PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})\b")
NAME = re.compile(r"\b(?:i am|i'm|im|my name is|this is|it's|its|name's)\s+([A-Z][a-zA-Z'-]{1,20})(?:\s+([A-Z][a-zA-Z'-]{1,25}))?", re.I)
DAYS = [("monday", "Mon"), ("tuesday", "Tue"), ("wednesday", "Wed"), ("thursday", "Thu"), ("friday", "Fri"), ("saturday", "Sat"), ("sunday", "Sun")]

FALLBACK = "Good question. Let me get a team member to answer that properly, they can text you in a minute. What's your first name and mobile number?"
CONFIRM = "Done, {first}. {store} just texted you at {phone}, reply there and a real person takes it from here. Anything else I can look up while you wait?"
ASK_CONTACT = "That one is a team member's call, not mine, and they're quick. What's your first name and mobile number? They'll text you right away."


def _now():
    return datetime.now(timezone.utc)


def _msg(role: str, text: str, **extra) -> dict:
    return {"role": role, "text": text, "at": _now(), **extra}


def _iso(v) -> Optional[str]:
    return v.isoformat() if isinstance(v, datetime) else None


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


def knowledge_text(store: dict, kb: dict, facts: list, inv_lines: list, inv_total: int, site: str = "") -> str:
    business = kb.get("mode") == "business"
    name = store.get("name") or ("the company" if business else "the store")
    parts = [f"{'COMPANY' if business else 'STORE'}: {name}"]
    addr = ", ".join(str(x) for x in [store.get("address"), store.get("city"), store.get("state"), store.get("zip") or store.get("zip_code")] if x)
    if addr:
        parts.append(f"ADDRESS: {addr}")
    if store.get("phone") or store.get("main_phone"):
        parts.append(f"MAIN PHONE: {store.get('phone') or store.get('main_phone')}")
    if store.get("website"):
        parts.append(f"WEBSITE: {store['website']}")
    hl = hours_lines(store)
    if business:
        if hl:
            parts.append("OFFICE / SUPPORT HOURS:\n" + "\n".join(hl))
    else:
        parts.append("HOURS:\n" + "\n".join(hl) if hl else "HOURS: not on file (say you will have the team confirm)")
    if facts:
        parts.append(("COMPANY FACTS" if business else "STORE FACTS") + " (accurate, quote plainly):\n" + "\n".join(f"- {f}" for f in facts[:30]))
    sp = _active_specials(kb)
    if sp:
        parts.append(("CURRENT OFFERS" if business else "CURRENT SPECIALS") + " (you may mention these exactly as written, never add numbers of your own):\n" + "\n".join(
            f"- {s['title']}" + (f": {s['details']}" if s.get("details") else "") + (f" (through {s['ends']})" if s.get("ends") else "") for s in sp[:10]))
    if (kb.get("notes") or "").strip():
        parts.append("MORE FROM THE MANAGER:\n" + kb["notes"].strip()[:2000])
    if site:
        parts.append("WHAT THE WEBSITE SAYS (the source of truth for the product, features, plans and prices; passages are pulled from the pages, feature sheet and industry presentations that match this question; "
                     "quote feature names, numbers and outcomes from them plainly and specifically, and when the visitor names their industry lean on that industry's presentation):\n" + site)
    elif business:
        parts.append("WEBSITE: not read yet, so only use the facts above; when something is not covered, offer a demo or a team member.")
    if business:
        return "\n\n".join(parts)
    if inv_total:
        parts.append(f"INVENTORY: {inv_total} vehicles available right now." + ("\nMATCHES FOR WHAT THEY ASKED:\n" + "\n".join(f"- {l}" for l in inv_lines) if inv_lines else ""))
    else:
        parts.append("INVENTORY: no live inventory feed connected, so do not claim anything is or is not in stock; offer to have the team check.")
    return "\n\n".join(parts)


def system_prompt(store: dict, kb: dict, knowledge: str, mode: str, have_contact: bool, booking: bool = False, coach: str = "") -> str:
    if kb.get("mode") == "business":
        return business_prompt(store, kb, knowledge, mode, have_contact, booking) + coach
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
    if booking:
        base += ("\nBOOKING: The visitor wants to come in (test drive, service or a visit). In one or two sentences say you can set that up right here and point them to the "
                 "booking form that just appeared below (pick a day and time). Do not ask them to call and do not ask for their number in the text; the form collects it.")
    return base + coach


def business_prompt(store: dict, kb: dict, knowledge: str, mode: str, have_contact: bool, booking: bool = False) -> str:
    name = store.get("name") or "the company"
    never = "; ".join(kb.get("never") or []) or "none listed"
    base = (
        f"You are Jessi, the assistant in the chat window on {name}'s website, and you are the resident expert on {name}: what it does, who it is for, every feature, "
        "how it works, plans and pricing, setup and support. You are talking to a prospect or customer visiting the site.\n"
        "STYLE: warm, confident, plain English, like the sharpest person on the team who knows the product cold and has demoed it a thousand times. Two to four short sentences; a short list of up to four items is fine when they ask what is included. "
        "No emojis, no em dashes, no headings. Answer the question directly first with a concrete (a feature name, a number, how it works, an example for their kind of business), then the one detail that helps most.\n"
        "CONFIDENCE: You always answer as the expert. Never say you do not have something loaded, on file, in front of you, or from the website; never say you are not sure, cannot see, or would need to check; never apologize for missing detail; "
        "never point people to support hours, a phone number or an email unless they ask how to reach the team. If a specific detail is not in WHAT YOU KNOW, speak to it at the level you do know (what the capability does, the outcome, who uses it) "
        "and move on; the demo is where the fine print gets shown. Never guess what the product does from its name.\n"
        "TRUTH: WHAT YOU KNOW is your source. Quote plan names, prices, limits and feature names exactly as written there. Never invent features, numbers, integrations, dates or policies.\n"
        f"HARD RULES: never discuss: {never}. Never pretend to be human; if asked, you are Jessi, {name}'s assistant, and a real person is one tap away. "
        "Do not ask for contact details unless a hand-off is happening.\n\n"
        f"WHAT YOU KNOW:\n{knowledge}\n"
    )
    if mode == "handoff":
        base += ("\nMODE: HAND-OFF. The visitor asked for a person or for something only the team handles. In one or two sentences say a real person on the team will take it and that they are fast. "
                 + ("Their name and mobile are already on file, so tell them the team is texting them right now and offer to keep helping meanwhile."
                    if have_contact else "Ask for their first name and mobile number so the team can text them right away."))
    elif mode == "handed_off":
        base += "\nMODE: A team member already has this visitor's number and is texting them. Keep answering product questions fully; remind them the team member has anything you cannot answer."
    if booking:
        base += ("\nBOOKING: The visitor wants a demo or a call. In one or two sentences say you can set that up right here and point them to the "
                 "booking form that just appeared below (pick a day and time). Do not ask for their number in the text; the form collects it.")
    return base


def _rank_scripts(scripts: list, text: str, top: int = 6) -> list:
    toks = set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))
    def sc(s):
        return len(toks & set(re.findall(r"[a-z0-9]{3,}", s["q"].lower())))
    return sorted([s for s in scripts if sc(s) > 0], key=sc, reverse=True)[:top]


def coaching(cfg: dict, pb_state: dict, text: str, mode: str, booking: bool, pitch: bool = False) -> tuple:
    """Owner training layered on the prompt: specificity rule, scripted answers that match this line, and the playbook's next question or pitch.
    Returns (prompt_text, index_of_question_to_ask_or_None)."""
    kb = cfg["kb"]
    out = ["\nSPECIFICITY: Lead with a concrete detail from WHAT YOU KNOW: a number, a named plan or feature, a step, a real example. "
           "Never a generic summary like 'we offer a range of solutions'. If asked what something costs or includes, name the plan or item. Vague is a failure."]
    scripts = _rank_scripts(kb.get("scripts") or [], text)
    if scripts:
        out.append("SCRIPTED ANSWERS (the owner wrote these; when the visitor's line matches one, answer with that wording, only lightly adapted):\n"
                   + "\n".join(f"- Q: {s['q']}\n  A: {s['a']}" for s in scripts))
    pb = W.playbook_for(cfg)
    next_q = None
    if pb["on"] and pitch:
        out.append(f"CLOSE NOW: They have answered your qualifying questions, this is the moment to ask for the {pb['goal'].lower()}. Answer their last line in one or two specific sentences, "
                   f"then transition with the owner's pitch line adapted to what they told you: \"{pb['pitch']}\" Finish by pointing them to the booking form that just appeared below "
                   "(pick a day and time). Do not ask another qualifying question and do not ask for their number; the form collects it.")
    elif pb["on"] and mode == "normal" and not booking:
        asked = set(pb_state.get("asked") or [])
        remaining = [(i, q) for i, q in enumerate(pb["questions"]) if i not in asked]
        if remaining:
            next_q = remaining[0][0]
            lst = "\n".join(f"  {n + 1}. {q}" for n, (_, q) in enumerate(remaining))
            out.append(f"PLAYBOOK: Your goal is to get this visitor to {pb['goal'].lower()}. Answer their last line first with specifics, then end your reply with ONE qualifying question, "
                       f"worded naturally in one sentence. Take the first question on this list that the visitor has NOT already answered anywhere in the conversation (skip answered ones):\n{lst}\n"
                       "Ask exactly one question and make it the last sentence. Keep the whole reply under 80 words before the question. Do not ask for their contact details.")
    return "\n".join(out), next_q


def _asked_index(reply: str, cfg: dict, pb_state: dict) -> Optional[int]:
    """Which playbook question did Jessi actually end with? Best token overlap among the ones not asked yet (None if she asked none)."""
    asked = set(pb_state.get("asked") or [])
    qs = re.findall(r"[^.!?\n]*\?", reply or "")
    if not qs:
        return None
    toks = set(re.findall(r"[a-z0-9]{3,}", qs[-1].lower()))  # only the closing question, not the product talk above it
    best, score = None, 0
    for i, q in enumerate(W.playbook_for(cfg)["questions"]):
        if i in asked:
            continue
        hit = len(toks & set(re.findall(r"[a-z0-9]{3,}", q.lower())))
        if hit > score:
            best, score = i, hit
    return best if score >= 2 else None


HEDGE = re.compile(r"(don'?t have|do not have|not (yet )?loaded|in front of me|on file yet|i'?m not sure|not certain|can'?t see|cannot see|unable to (see|find)|would need to check|i'?d need to check|no (exact|specific) (details?|steps?) (on|from)|isn'?t (listed|loaded|covered)|not (listed|covered) (on|in) (our|the) (site|website))", re.I)


def hedges(text: str) -> bool:
    return bool(HEDGE.search(text or ""))


async def _confident(system: str, transcript: str) -> Optional[str]:
    """Business-mode reply with one rewrite pass if Jessi hedged; she answers as the expert or not at all."""
    answer = await _llm(system, transcript)
    if answer and hedges(answer):
        redo = await _llm(system + "\nREWRITE: your draft hedged (said you lacked something, were unsure, or pointed to support). Rewrite it: state what the product does for them at the level you know, confidently, "
                          "no disclaimers, no phone numbers or hours, same closing question if there was one.\nDRAFT:\n" + answer, transcript)
        if redo and not hedges(redo):
            return redo
        return HEDGE.sub("", answer).strip() if redo is None else redo
    return answer


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
    text = re.sub(r"\n{3,}", "\n\n", no_em_dash((out if isinstance(out, str) else str(out)).strip()))
    if len(text) > 1100:
        cut = text[:1100]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("\n"))
        text = cut[: end + 1].strip() if end > 300 else cut.rstrip()  # never chop mid-sentence, the closing question matters
    return text or None


def _transcript(session: dict, limit: int = HISTORY) -> str:
    rows = [m for m in session.get("messages") or [] if m.get("role") in ("visitor", "jessi", "rep")][-limit:]
    return "\n".join(f"{'Visitor' if m['role'] == 'visitor' else 'Jessi' if m['role'] == 'jessi' else 'Team member ' + (m.get('who') or '')}: {m['text']}" for m in rows)


async def store_facts(db, store: dict) -> list:
    return [f.get("text") for f in (store or {}).get("va_facts") or [] if f.get("text")]


def _first(user: dict) -> str:
    return ((user or {}).get("first_name") or ((user or {}).get("name") or "").split(" ")[0] or "A team member").strip()


def _aware(v) -> Optional[datetime]:
    return v.replace(tzinfo=timezone.utc) if isinstance(v, datetime) and v.tzinfo is None else (v if isinstance(v, datetime) else None)


def _here(session: dict) -> bool:
    seen = _aware(session.get("visitor_seen_at"))
    return bool(seen and (_now() - seen).total_seconds() < HERE_S)


# ---------------------------------------------------------------- sessions
async def start(db, w: dict, body: dict, ip: str) -> dict:
    if not W.allow(ip, "chat_start", 10):
        raise ValueError("Too many chats started from this connection. Give it a minute.")
    cfg = W.normalize_config(w)
    store = await W.store_of(db, w)
    sname = store.get("name") or ("the company" if cfg["kb"].get("mode") == "business" else "the store")
    default = (f"Hi! I'm Jessi, {sname}'s assistant. Ask me anything about what we do, how it works or pricing. Want a person? Just say so."
               if cfg["kb"].get("mode") == "business" else f"Hi! I'm Jessi, {sname}'s assistant. Ask me about hours, what's in stock or anything about the store. Want a person? Just say so.")
    greeting = (cfg["kb"].get("welcome") or "").strip() or default
    greeting = greeting.replace("{store}", store.get("name") or "").replace("{{store_name}}", store.get("name") or "")
    doc = {"sid": secrets.token_urlsafe(18), "widget_id": str(w["_id"]), "key": w["key"], "store_id": w.get("store_id"),
           "visitor": (body.get("visitor") or "")[:64], "page": (body.get("page") or "")[:500], "title": (body.get("title") or "")[:200], "host": W.host_of(body.get("page") or ""),
           "name": "", "phone": "", "status": "open", "mode": "jessi", "rep_user_id": None, "rep_first": "", "rep_unread": 0,
           "awaiting_contact": False, "handoff_reason": "", "offer_booking": False, "booking": None, "turns": 0,
           "messages": [_msg("jessi", greeting)], "visitor_seen_at": _now(), "created_at": _now(), "updated_at": _now(), "ip": ip}
    await db[COLL].insert_one(doc)
    await W.log_event(db, w, "chat", {**body, "door": "chat"})
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.chats": 1}})
    return {"sid": doc["sid"], "greeting": greeting, "status": "open", "mode": "jessi"}


async def load(db, key: str, sid: str) -> Optional[dict]:
    return await db[COLL].find_one({"key": key, "sid": sid}) if sid else None


async def touch_visitor(db, session: dict):
    await db[COLL].update_one({"_id": session["_id"]}, {"$set": {"visitor_seen_at": _now()}})


def public_state(session: dict) -> dict:
    b = session.get("booking") or None
    mode = session.get("mode") or "jessi"
    return {"sid": session["sid"], "status": session.get("status"), "mode": mode, "agent": session.get("rep_first") or "",
            "need_contact": bool(session.get("awaiting_contact")) and not session.get("phone") and mode != "human",
            "name": session.get("name") or "", "has_phone": bool(session.get("phone")),
            "offer_booking": bool(session.get("offer_booking")) and not b and mode != "human" and session.get("status") != "closed",
            "booking": {"kind": b["kind_label"], "when": b["when_label"]} if b else None,
            "messages": [{"role": m["role"], "text": m["text"], **({"who": m["who"]} if m.get("who") else {})} for m in (session.get("messages") or []) if m.get("role") in PUBLIC_ROLES][-80:]}


def _detect(kb: dict, text: str) -> str:
    if HUMAN.search(text or ""):
        return "asked for a person"
    if kb.get("mode") != "business" and HANDOFF.search(text or ""):
        return "pricing / payments / trade"
    hit = never_hit(kb, text)
    return f"topic the store keeps for the team ({hit})" if hit else ""


def _wants_booking(kb: dict, text: str) -> bool:
    return bool((BOOK_BUSINESS if kb.get("mode") == "business" else BOOK).search(text or ""))


async def _knowledge(db, w: dict, store: dict, kb: dict, text: str) -> tuple:
    """(knowledge text, inventory lines, inventory total) for this turn; business sites pull the relevant website pages instead of inventory."""
    if kb.get("mode") == "business":
        from services.widget_crawl import site_context
        return knowledge_text(store, kb, await store_facts(db, store), [], 0, site=await site_context(db, w, text)), [], 0
    inv_lines, inv_total = await inventory_lines(db, w.get("store_id"), text, bool(kb.get("share_listed_prices")))
    return knowledge_text(store, kb, await store_facts(db, store), inv_lines, inv_total), inv_lines, inv_total


async def _notify_live(db, w: dict, cfg: dict, session: dict, text: str):
    """First visitor line: ping the ring group so someone can jump in while the visitor is still on the page."""
    reps = cfg["routing"].get("call_user_ids") or []
    if not reps or not cfg["doors"]["chat"].get("notify_reps", True):
        return
    try:
        from routers.push_notifications import send_push_to_users
        host = session.get("host") or "your website"
        await send_push_to_users(reps, "Live web chat", f"Visitor on {host}: \"{text[:70]}\" Jessi is answering. Tap to jump in.", f"/webchat/{session['sid']}", "chatbubbles")
        await db[COLL].update_one({"_id": session["_id"]}, {"$set": {"notified_at": _now()}})
    except Exception as e:
        logger.warning(f"[WidgetChat] live notify failed: {e}")


async def reply(db, w: dict, session: dict, text: str, ip: str) -> dict:
    text = " ".join((text or "").split())[:1000]
    if not text:
        raise ValueError("Say something first.")
    if not W.allow(ip, "chat_msg", 20):
        raise ValueError("Slow down a little, one message at a time.")
    if session.get("status") == "closed":
        raise ValueError("That chat has ended. Start a new one.")
    if session.get("turns", 0) >= MAX_TURNS:
        return {**public_state(session), "reply": "We've covered a lot. A team member can pick this up by text, tap Talk to a person and they'll reach out.", "handoff": False}
    cfg = W.normalize_config(w)
    kb = cfg["kb"]
    store = await W.store_of(db, w)
    first_turn = session.get("turns", 0) == 0
    msgs = list(session.get("messages") or []) + [_msg("visitor", text)]
    session["messages"] = msgs
    updates: dict = {"turns": session.get("turns", 0) + 1, "updated_at": _now(), "last_visitor_at": _now(), "visitor_seen_at": _now()}

    # names / phones the visitor types in passing
    nm = NAME.search(text)
    if nm and not session.get("name"):
        session["name"] = updates["name"] = " ".join(x for x in nm.groups() if x)
    ph = PHONE.search(text)
    phone = W.clean_phone("".join(ph.groups())) if ph else ""

    if session.get("mode") == "human":
        # a rep is in the chat: no Jessi, just store the line for the rep's screen
        updates["rep_unread"] = int(session.get("rep_unread") or 0) + 1
        updates["messages"] = msgs
        if phone and not session.get("phone"):
            updates["phone"] = session["phone"] = phone
        await db[COLL].update_one({"_id": session["_id"]}, {"$set": updates})
        session.update(updates)
        return {**public_state(session), "reply": None, "handoff": False}

    reason = _detect(kb, text) if session.get("status") != "handed_off" else ""
    mode = "normal"
    answer = None
    booking = False
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
    if answer is None and mode in ("normal", "handed_off") and cfg["doors"]["chat"].get("booking_on", True) and not session.get("booking") and _wants_booking(kb, text):
        booking = True
        updates["offer_booking"] = session["offer_booking"] = True
    # playbook progress: the line after a qualifying question counts as its answer
    pb_state = dict(session.get("pb") or {})
    if pb_state.get("pending") is not None:
        pb_state["asked"] = list(pb_state.get("asked") or []) + [pb_state["pending"]]
        pb_state["answered"] = int(pb_state.get("answered") or 0) + 1
        pb_state["pending"] = None
    pitch = False
    if (answer is None and mode == "normal" and not booking and not session.get("booking") and not pb_state.get("pitched")
            and cfg["doors"]["chat"].get("booking_on", True) and W.playbook_for(cfg)["on"] and int(pb_state.get("answered") or 0) >= W.playbook_for(cfg)["offer_after"]):
        booking = pitch = True
        pb_state["pitched"] = True
        updates["offer_booking"] = session["offer_booking"] = True
    if answer is None:
        knowledge, _, _ = await _knowledge(db, w, store, kb, text)
        coach, next_q = coaching(cfg, pb_state, text, mode, booking, pitch)
        system = system_prompt(store, kb, knowledge, mode, bool(session.get("phone")), booking=booking and not pitch, coach=coach)
        gen = _confident if kb.get("mode") == "business" else _llm
        answer = await gen(system, _transcript(session) + "\n\nReply to the visitor's last line as Jessi.")
        if next_q is not None and answer:
            hit = _asked_index(answer, cfg, pb_state)
            # she skipped ahead: everything before the one she asked counts as already answered
            if hit is not None:
                pb_state["asked"] = sorted(set(pb_state.get("asked") or []) | {i for i in range(hit)})  # skipped ones are done, but only real exchanges count toward the pitch
            pb_state["pending"] = hit if hit is not None else next_q
        if not answer:
            answer = ("Happy to set that up. Pick a day and time below and I'll get you booked." if booking else ASK_CONTACT if mode == "handoff" else FALLBACK)
            if mode != "handoff" and not booking and not session.get("phone"):
                updates["awaiting_contact"] = session["awaiting_contact"] = True
    msgs.append(_msg("jessi", answer))
    updates["messages"] = msgs
    updates["pb"] = session["pb"] = pb_state
    for k in ("status", "phone", "name", "lead_id", "contact_id", "conversation_id", "awaiting_contact", "handed_off_at"):
        if k in session and k not in updates:
            updates[k] = session[k]
    await db[COLL].update_one({"_id": session["_id"]}, {"$set": updates})
    session.update(updates)
    if first_turn:
        asyncio.create_task(_notify_live(db, w, cfg, session, text))
    return {**public_state(session), "reply": answer, "handoff": mode == "handoff" or session.get("status") == "handed_off"}


async def _save(db, session: dict, extra: Optional[dict] = None):
    keys = ("messages", "awaiting_contact", "handoff_reason", "status", "phone", "name", "lead_id", "contact_id", "conversation_id", "offer_booking", "booking", "mode", "rep_user_id", "rep_first", "rep_unread")
    sets = {k: session.get(k) for k in keys} | {"updated_at": _now()} | (extra or {})
    await db[COLL].update_one({"_id": session["_id"]}, {"$set": sets})


async def request_human(db, w: dict, session: dict) -> dict:
    """The visitor tapped 'Talk to a person'."""
    cfg = W.normalize_config(w)
    store = await W.store_of(db, w)
    if session.get("mode") == "human":
        text = f"{session.get('rep_first') or 'A team member'} is right here with you. Go ahead."
    elif session.get("status") == "handed_off":
        text = "A team member already has your number and is texting you now. Keep an eye on your phone."
    elif session.get("phone"):
        text = await _handoff(db, w, session, session["phone"], session.get("name") or "", cfg, store, reason="asked for a person")
    else:
        session["awaiting_contact"] = True
        session["handoff_reason"] = "asked for a person"
        text = "Happy to. What's your first name and mobile number? A team member will text you in a minute."
    session["messages"] = list(session.get("messages") or []) + [_msg("jessi", text)]
    await _save(db, session)
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
    session["messages"] = list(session.get("messages") or []) + [_msg("jessi", text)]
    await _save(db, session)
    return {**public_state(session), "reply": text, "handoff": True}


async def _handoff(db, w: dict, session: dict, phone: str, name: str, cfg: dict, store: dict, reason: str = "", quiet: bool = False) -> str:
    """Create the lead through the intake pipeline; the transcript lands in the thread; the visitor gets the store-line text (none when quiet)."""
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
    if quiet:
        src["intake_text"] = src["after_hours_text"] = ""
        normalized["no_intake_text"] = True
    else:
        src["intake_text"] = (cfg["routing"].get("chat_intake_text") or "").replace("{{first_name}}", first).replace("{first_name}", first).replace("{{store_name}}", store_name).replace("{store_name}", store_name)
    from routers.lead_intake import process_inbound_lead
    res = await process_inbound_lead(normalized, src, db, raw_body="")
    if res.get("conversation_id"):
        await db.messages.insert_one({"conversation_id": res["conversation_id"], "contact_id": res.get("contact_id"), "sender": "contact", "direction": "inbound", "channel": "webchat",
                                      "type": "webchat_transcript", "content": f"Web chat on {W.host_of(page) or 'the website'} ({reason}):\n\n{transcript}"[:3000],
                                      "read": False, "timestamp": _now(), "created_at": _now(), "webchat_sid": session["sid"]})
        await db.conversations.update_one({"_id": ObjectId(res["conversation_id"])}, {"$set": {"last_message_at": _now(), "status": "active", "webchat_sid": session["sid"]}})
    session.update({"status": "handed_off", "awaiting_contact": False, "phone": phone, "name": name or session.get("name") or "", "lead_id": res.get("lead_id"),
                    "contact_id": res.get("contact_id"), "conversation_id": res.get("conversation_id"), "handed_off_at": _now(), "handoff_reason": reason, "assigned_to": res.get("assigned_to")})
    await W.log_event(db, w, "lead", {"page": page, "door": "chat", "visitor": session.get("visitor")})
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.chat_handoffs": 1}})
    logger.info(f"[WidgetChat] {session['sid']} handed off ({reason}) -> lead {res.get('lead_id')}")
    return "" if quiet else CONFIRM.format(first=first, store=store_name, phone=_fmt(phone))


def _fmt(p: str) -> str:
    d = re.sub(r"\D", "", p or "")[-10:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else p


# ---------------------------------------------------------------- booking inside the chat
def _tz(store: dict) -> ZoneInfo:
    from services.lead_timing import store_timezone
    try:
        return ZoneInfo(store_timezone(store))
    except Exception:
        return ZoneInfo("America/Denver")


def _hm(hhmm: str, default: str) -> dtime:
    try:
        h, m = (int(x) for x in (hhmm or default).split(":")[:2])
        return dtime(h, m)
    except Exception:
        h, m = (int(x) for x in default.split(":"))
        return dtime(h, m)


def slots(store: dict, days: int = 10, kinds: Optional[dict] = None) -> dict:
    """Open half-hour slots for the next `days` days, in the store's time zone, inside its hours (9 to 6 when none are on file)."""
    tz = _tz(store)
    now = datetime.now(tz)
    hours = (store or {}).get("business_hours") or {}
    out = []
    for i in range(days):
        day = (now + timedelta(days=i)).date()
        h = hours.get(day.strftime("%A").lower()) if hours else None
        if hours and (not h or h.get("closed") or not (h.get("open") and h.get("close"))):
            continue
        start = datetime.combine(day, _hm((h or {}).get("open"), "09:00"), tz)
        end = datetime.combine(day, _hm((h or {}).get("close"), "18:00"), tz) - timedelta(minutes=30)
        earliest = now + timedelta(minutes=45)
        cur, ss = start, []
        while cur <= end:
            if cur >= earliest:
                ss.append({"v": cur.strftime("%H:%M"), "l": _t12(cur.strftime("%H:%M"))})
            cur += timedelta(minutes=30)
        if ss:
            out.append({"date": day.isoformat(), "label": "Today" if i == 0 else "Tomorrow" if i == 1 else day.strftime("%a %b ") + str(day.day), "slots": ss})
    return {"tz": tz.key, "days": out, "kinds": [{"v": k, "l": l} for k, l in (kinds or BOOK_KINDS).items()]}


async def _booking_rep(db, session: dict, cfg: dict) -> Optional[str]:
    if session.get("conversation_id") and ObjectId.is_valid(str(session["conversation_id"])):
        conv = await db.conversations.find_one({"_id": ObjectId(session["conversation_id"])}, {"assigned_to": 1, "user_id": 1})
        if conv and (conv.get("assigned_to") or conv.get("user_id")):
            return str(conv.get("assigned_to") or conv.get("user_id"))
    if session.get("assigned_to"):
        return str(session["assigned_to"])
    reps = cfg["routing"].get("call_user_ids") or []
    return str(reps[0]) if reps else None


async def _text_booked(db, session: dict, uid: Optional[str], phone: str, body: str) -> bool:
    """Booking confirmation from the thread's line (store line, else the rep's number); logged on the thread so replies land there."""
    conv_id = str(session.get("conversation_id") or "")
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id)}, {"rep_phone": 1}) if ObjectId.is_valid(conv_id) else None
    frm = (conv or {}).get("rep_phone") or ""
    if not frm and uid and ObjectId.is_valid(uid):
        rep = await db.users.find_one({"_id": ObjectId(uid)}, {"twilio_number": 1, "mvpline_number": 1})
        frm = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number") or ""
    frm = frm or os.environ.get("TWILIO_PHONE_NUMBER", "")
    if conv:
        from routers.lead_intake import _send_intake_sms
        res = await _send_intake_sms(db, conv_id, phone, frm, body)
        if res.get("success") and not conv.get("rep_phone") and frm:
            await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"rep_phone": frm}})
    else:
        from services.twilio_service import send_sms
        res = await send_sms(phone, body, from_phone=frm or None)
    if not res.get("success"):
        logger.warning(f"[WidgetChat] {session['sid']} booking text failed: {res.get('error')}")
    return bool(res.get("success"))


async def book(db, w: dict, session: dict, body: dict, ip: str) -> dict:
    if not W.allow(ip, "lead", 5):
        raise ValueError("Please wait a minute before sending again.")
    if session.get("status") == "closed":
        raise ValueError("That chat has ended. Start a new one.")
    if session.get("booking"):
        raise ValueError("You already have a visit booked. Ask a team member if you need to move it.")
    cfg = W.normalize_config(w)
    if not cfg["doors"]["chat"].get("booking_on", True):
        raise ValueError("Booking is turned off for this site.")
    store = await W.store_of(db, w)
    kinds = kinds_for(cfg)
    kind = body.get("kind") if body.get("kind") in kinds else next(iter(kinds))
    d, t = str(body.get("date") or "")[:10], str(body.get("time") or "")[:5]
    day = next((x for x in slots(store)["days"] if x["date"] == d), None)
    if not day or t not in [s["v"] for s in day["slots"]]:
        raise ValueError("That time is not open anymore. Pick another one.")
    name = " ".join((body.get("name") or "").split())[:80] or session.get("name") or ""
    phone = W.clean_phone(body.get("phone") or "") or session.get("phone") or ""
    if not name or not phone:
        raise ValueError("Please add your first name and a 10 digit mobile number.")
    vehicle = " ".join((body.get("vehicle") or "").split())[:80]
    start = datetime.combine(date.fromisoformat(d), _hm(t, "09:00"), _tz(store))
    when = f"{start.strftime('%A %b ')}{start.day} at {_t12(t)}"
    kind_label = kinds[kind]
    first = W.split_name(name)[0]
    store_name = store.get("name") or "the store"
    what = kind_label + (f" ({vehicle})" if vehicle else "")
    biz = cfg["kb"].get("mode") == "business"
    meeting = cfg["doors"]["chat"].get("meeting_link") or "" if biz else ""
    if not session.get("contact_id"):
        await _handoff(db, w, session, phone, name, cfg, store, reason=f"booked a {kind_label.lower()}", quiet=True)
    uid = await _booking_rep(db, session, cfg)
    booking = {"kind": kind, "kind_label": kind_label, "date": d, "time": t, "when_label": when, "vehicle": vehicle, "start": start.isoformat(),
               "user_id": uid, "appointment_id": None, "task_id": None, "created_at": _now()}
    link = ""
    if uid:
        try:
            from routers.calendar import create_appointment_from_ai
            from routers.tasks import create_task
            from services.calendar_invite import invite_link
            title = f"{kind_label}: {name}" + (f" · {vehicle}" if vehicle else "")
            a = await create_appointment_from_ai(uid, {"contact_id": session.get("contact_id"), "conversation_id": session.get("conversation_id"), "contact_name": name, "contact_phone": phone,
                                                      "title": title, "start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat(), "location": meeting or store_name,
                                                      "notes": f"Booked in the website chat ({session.get('host') or 'website'})."})
            tk = await create_task(uid, {"title": title, "description": f"Booked in the website chat, {when}.", "contact_id": session.get("contact_id") or "", "type": "appointment",
                                         "appointment_type": kind, "action_type": "manual", "due_date": start.astimezone(timezone.utc).isoformat(), "has_time": True, "priority": "high"})
            booking["appointment_id"] = (a or {}).get("appointment_id")
            booking["task_id"] = (tk or {}).get("_id") or (tk or {}).get("id")
            if booking["task_id"] and biz:
                await db.tasks.update_one({"_id": ObjectId(str(booking["task_id"]))}, {"$set": {"meeting_link": meeting, "event_kind": kind_label}})
            task = await db.tasks.find_one({"_id": ObjectId(str(booking["task_id"]))}) if booking["task_id"] else None
            if task and task.get("contact_id"):
                link = await invite_link(db, task)
        except Exception as e:
            logger.warning(f"[WidgetChat] booking calendar/task failed: {e}")
    if biz:
        confirm = (f"Hi {first}, {store_name} here. Your {what.lower()} is set for {when}. "
                   + (f"Join here: {meeting}\n" if meeting else "") + (f"Add it to your calendar: {link}\n" if link else "")
                   + "Reply here if anything changes. Talk soon!")
    else:
        confirm = (f"Hi {first}, {store_name} here. You're booked: {what} on {when}. "
                   + (f"Tap to add it to your calendar: {link}\n" if link else "") + "Reply here if anything changes. See you then!")
    texted = await _text_booked(db, session, uid, phone, confirm)
    if texted and link:
        from services.calendar_invite import mark_invite_sent
        await mark_invite_sent(db, str(booking["task_id"]), link)
    if session.get("conversation_id") and ObjectId.is_valid(str(session["conversation_id"])):
        await db.messages.insert_one({"conversation_id": session["conversation_id"], "contact_id": session.get("contact_id"), "sender": "contact", "direction": "inbound", "channel": "webchat",
                                      "type": "webchat_booking", "content": f"Booked in the web chat: {what} on {when}.", "read": False, "timestamp": _now(), "created_at": _now(), "webchat_sid": session["sid"]})
        await db.conversations.update_one({"_id": ObjectId(session["conversation_id"])}, {"$set": {"last_message_at": _now()}})
    if biz:
        extras = [x for x in ["the meeting link" if meeting else "", "a link to add it to your calendar" if link else ""] if x]
        tail = (f"We just texted you the details{(' with ' + ' and '.join(extras)) if extras else ''}, and someone from the team will be on the call."
                if texted else "Someone from the team will be on the call.")
        text = f"You're all set, {first}. {what} on {when}. {tail} Anything else I can answer in the meantime?"
    else:
        tail = (f"{store_name} just texted you a confirmation{' with a link to add it to your calendar' if link else ''}, and a team member will be ready for you."
                if texted else "A team member will be ready for you.")
        text = f"You're all set, {first}. {what} on {when}. {tail} Anything else I can help with?"
    session["messages"] = list(session.get("messages") or []) + [_msg("jessi", text)]
    session.update({"booking": booking, "offer_booking": False})
    await _save(db, session)
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$inc": {"stats.chat_bookings": 1}})
    logger.info(f"[WidgetChat] {session['sid']} booked {kind} {d} {t} for rep {uid}")
    return {**public_state(session), "reply": text, "booked": True}


# ---------------------------------------------------------------- reps: jump into a live chat
def rep_view(session: dict) -> dict:
    b = session.get("booking") or None
    return {"sid": session["sid"], "status": session.get("status"), "mode": session.get("mode") or "jessi", "agent": session.get("rep_first") or "", "rep_user_id": session.get("rep_user_id"),
            "name": session.get("name") or "", "phone": _fmt(session["phone"]) if session.get("phone") else "", "page": session.get("page") or "", "title": session.get("title") or "",
            "host": session.get("host") or "", "turns": session.get("turns", 0), "visitor_here": _here(session), "rep_unread": int(session.get("rep_unread") or 0),
            "contact_id": session.get("contact_id"), "conversation_id": session.get("conversation_id"), "lead_id": session.get("lead_id"), "handoff_reason": session.get("handoff_reason") or "",
            "booking": {"kind": b["kind_label"], "when": b["when_label"], "vehicle": b.get("vehicle") or "", "task_id": b.get("task_id")} if b else None,
            "created_at": _iso(session.get("created_at")), "updated_at": _iso(session.get("updated_at")), "last_visitor_at": _iso(session.get("last_visitor_at")),
            "messages": [{"role": m["role"], "text": m["text"], "who": m.get("who") or "", "uid": m.get("uid") or "", "at": _iso(m.get("at"))} for m in (session.get("messages") or [])][-200:]}


def summary(session: dict, store_name: str = "") -> dict:
    last = next((m["text"] for m in reversed(session.get("messages") or []) if m.get("role") == "visitor"), "")
    return {"sid": session["sid"], "name": session.get("name") or "Website visitor", "store_name": store_name, "host": session.get("host") or "", "page": session.get("page") or "",
            "mode": session.get("mode") or "jessi", "agent": session.get("rep_first") or "", "rep_user_id": session.get("rep_user_id"), "status": session.get("status"),
            "turns": session.get("turns", 0), "rep_unread": int(session.get("rep_unread") or 0), "visitor_here": _here(session), "last": last[:120],
            "has_lead": bool(session.get("contact_id")), "conversation_id": session.get("conversation_id"), "booked": bool(session.get("booking")),
            "at": _iso(session.get("last_visitor_at") or session.get("updated_at"))}


async def live_list(db, widget_ids: list, limit: int = 30) -> list:
    since = _now() - timedelta(minutes=LIVE_WINDOW_MIN)
    q = {"widget_id": {"$in": [str(x) for x in widget_ids]}, "status": {"$ne": "closed"}, "turns": {"$gte": 1},
         "$or": [{"updated_at": {"$gte": since}}, {"visitor_seen_at": {"$gte": since}}]}
    return await db[COLL].find(q).sort("updated_at", -1).limit(limit).to_list(limit)


async def for_conversation(db, conversation_id: str) -> Optional[dict]:
    """The live chat behind an Inbox thread, if the visitor is still around."""
    s = await db[COLL].find_one({"conversation_id": str(conversation_id), "status": {"$ne": "closed"}}, sort=[("updated_at", -1)])
    if not s:
        return None
    recent = _now() - timedelta(minutes=10)
    seen, upd = _aware(s.get("visitor_seen_at")), _aware(s.get("updated_at"))
    return s if (seen and seen >= recent) or (upd and upd >= recent) else None


async def join(db, w: dict, session: dict, user: dict) -> dict:
    if session.get("status") == "closed":
        raise ValueError("That chat has ended.")
    first = _first(user)
    store = await W.store_of(db, w)
    already = session.get("mode") == "human" and str(session.get("rep_user_id")) == str(user["_id"])
    if not already:
        text = f"{first} took over the chat." if session.get("mode") == "human" else f"{first} from {store.get('name') or 'the store'} joined the chat."
        session["messages"] = list(session.get("messages") or []) + [_msg("system", text)]
    session.update({"mode": "human", "rep_user_id": str(user["_id"]), "rep_first": first, "offer_booking": False, "awaiting_contact": False, "rep_unread": 0})
    await _save(db, session, {"joined_at": _now()})
    logger.info(f"[WidgetChat] {session['sid']} rep {user.get('email')} joined")
    return rep_view(session)


async def rep_message(db, w: dict, session: dict, user: dict, text: str) -> dict:
    text = " ".join((text or "").split())[:1000]
    if not text:
        raise ValueError("Type something first.")
    if session.get("status") == "closed":
        raise ValueError("That chat has ended.")
    if session.get("mode") != "human" or str(session.get("rep_user_id")) != str(user["_id"]):
        await join(db, w, session, user)
    session["messages"] = list(session.get("messages") or []) + [_msg("rep", text, who=session.get("rep_first") or _first(user), uid=str(user["_id"]))]
    session["rep_unread"] = 0
    await _save(db, session)
    return rep_view(session)


async def leave(db, w: dict, session: dict, user: dict) -> dict:
    first = session.get("rep_first") or _first(user)
    if session.get("mode") == "human":
        session["messages"] = list(session.get("messages") or []) + [_msg("system", f"{first} stepped away. Jessi is back to help.")]
    session.update({"mode": "jessi", "rep_user_id": None, "rep_first": "", "rep_unread": 0})
    await _save(db, session)
    return rep_view(session)


async def end(db, w: dict, session: dict, user: dict) -> dict:
    if session.get("status") != "closed":
        session["messages"] = list(session.get("messages") or []) + [_msg("system", "Chat ended by the team. Thanks for stopping by!")]
    session.update({"status": "closed", "mode": "jessi", "rep_unread": 0})
    await _save(db, session, {"ended_at": _now(), "ended_by": str(user["_id"])})
    return rep_view(session)


async def mark_read(db, session: dict):
    if session.get("rep_unread"):
        await db[COLL].update_one({"_id": session["_id"]}, {"$set": {"rep_unread": 0}})


async def save_lead(db, w: dict, session: dict, user: dict, name: str, phone: str) -> dict:
    """Rep saves the visitor as a lead from the live chat (no text goes out, the rep is already talking to them)."""
    name = " ".join((name or "").split())[:80] or session.get("name") or "Website Visitor"
    phone = W.clean_phone(phone or "") or session.get("phone") or ""
    if not phone:
        raise ValueError("Add a 10 digit mobile number first.")
    if session.get("contact_id"):
        return rep_view(session)
    cfg = W.normalize_config(w)
    store = await W.store_of(db, w)
    await _handoff(db, w, session, phone, name, cfg, store, reason=f"{session.get('rep_first') or _first(user)} saved them from the live chat", quiet=True)
    session["messages"] = list(session.get("messages") or []) + [_msg("note", f"Saved as a lead: {name}, {_fmt(phone)}.")]
    await _save(db, session)
    return rep_view(session)


# ---------------------------------------------------------------- manager: "Test Jessi"
async def ask(db, w: dict, question: str) -> dict:
    cfg = W.normalize_config(w)
    kb = cfg["kb"]
    store = await W.store_of(db, w)
    reason = _detect(kb, question)
    knowledge, inv_lines, inv_total = await _knowledge(db, w, store, kb, question)
    facts = await store_facts(db, store)
    coach, _ = coaching(cfg, {}, question, "handoff" if reason else "normal", False)
    system = system_prompt(store, kb, knowledge, "handoff" if reason else "normal", False, coach=coach)
    gen = _confident if kb.get("mode") == "business" else _llm
    answer = await gen(system, f"Visitor: {question}\n\nReply to the visitor's last line as Jessi.") or (ASK_CONTACT if reason else FALLBACK)
    from services.widget_crawl import PAGES_COLL
    pages = await db[PAGES_COLL].count_documents({"widget_id": str(w["_id"])}) if kb.get("mode") == "business" else 0
    return {"reply": answer, "handoff": bool(reason), "reason": reason, "used": {"facts": len(facts), "specials": len(_active_specials(kb)), "inventory_matches": len([l for l in inv_lines if not l.startswith("...")]),
                                                                                    "inventory_total": inv_total, "hours": bool(hours_lines(store)), "site_pages": pages, "mode": kb.get("mode"),
                                                                                    "scripts": len(_rank_scripts(kb.get("scripts") or [], question)), "playbook": W.playbook_for(cfg)["on"]}}
