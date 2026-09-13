"""Mystery Shop Clients: the AI shopper calls people who are NOT app users (a client store's sales/service staff),
grades every call and rolls the results into a store report the client can open without logging in."""
import asyncio
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import industries as ind
from services import scripts as scr
from services import scorecards as sc
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

DEPARTMENTS = ind.dept_keys("automotive")  # automotive keys; use ind.* for anything industry-aware
DEPT_LABEL = ind.label_map()
ALL_DEPARTMENTS = ind.all_dept_keys()
CALL_STATUSES_OPEN = ["scheduled", "dialing", "live", "grading"]
DEFAULT_HOURS = {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4, 5]}

# Global challenge pool. Persona text uses {vehicle} and {store}; the client's brand fills them in at shop time.
STARTER_CHALLENGES = [
    {"slug": "shop_sales_availability", "department": "sales", "category": "Sales calls", "title": "Shopper: is it still available?", "runtime": "3 to 5 min",
     "purpose": "The classic phone-up. A shopper saw a unit online and calls to ask if it is still there. A great rep gets the name and number, sells the visit, never the price.",
     "body": "Answer with the store and your name. Get the caller's name early and use it.\n\nConfirm the exact vehicle and that it is available (or offer two alternatives).\n\n[Discovery, 2 questions max]\nWhat drew them to it? Anything to trade?\n\n[Never quote a payment on the phone]\nGive a reason: you would rather be right than fast with their money.\n\n[Set the appointment with two times]\nGet the best cell number in case you get disconnected. Recap and thank them.",
     "success_points": ["Answers with the store name and their own name", "Gets and uses the caller's name", "Confirms the vehicle and availability", "Asks about a trade-in", "Offers two appointment times", "Gets the caller's phone number", "Recaps and thanks the caller"],
     "persona": {"name": "Dana Whitfield", "voice": "female", "summary": "41, project manager, saw {vehicle} on {store}'s website last night. Friendly, a little rushed, comparing two stores.",
                 "goals": "Find out if it is still there and whether the drive is worth it. Will give a name and number if the rep earns it.",
                 "objections": ["Can you just tell me the payment over the phone?", "Is the online price negotiable?", "I'm comparing you with another store"],
                 "opening_line": "Hi, I'm calling about {vehicle} you have listed online, is it still available?"}},
    {"slug": "shop_sales_payment_first", "department": "sales", "category": "Sales calls", "title": "Shopper: payment before I drive over", "runtime": "3 to 5 min",
     "purpose": "The shopper wants a monthly payment quoted over the phone. A great rep acknowledges, explains why a blind quote hurts the customer, and sells the visit.",
     "body": "Acknowledge the question, do not dodge it. Explain that trade, credit tier and term change the number, so a phone quote would be a guess.\n\nAsk what they are working with: trade, down payment range, how soon they want to drive it.\n\nOffer a firm appointment with two times and a specific promise: exact numbers in 20 minutes.\n\nGet the name and cell number. Recap.",
     "success_points": ["Acknowledges the payment question without dodging", "Explains why a phone quote would be a guess", "Asks about a trade-in", "Asks about timeline", "Offers two appointment times", "Gets the caller's name and number"],
     "persona": {"name": "Marcus Bell", "voice": "male", "summary": "34, warehouse supervisor, budget driven. Looking at {vehicle} at {store}. Direct, a bit impatient.",
                 "goals": "Get a monthly payment number before agreeing to anything. Will book if the rep gives a real reason and a specific plan.",
                 "objections": ["I don't want to waste a trip, just give me a ballpark", "The other store gave me a number over the phone", "I'm not filling out a credit app until I know the payment"],
                 "opening_line": "Hi, I'm looking at {vehicle} on your site. What would the monthly payment be on that?"}},
    {"slug": "shop_sales_trade", "department": "sales", "category": "Sales calls", "title": "Shopper: what's my trade worth?", "runtime": "3 to 4 min",
     "purpose": "The shopper leads with their trade. A great rep gathers the facts, never guesses a number, and gets the car on the lot.",
     "body": "Ask the facts: year, make, model, mileage, condition, payoff, keys. Never guess a number over the phone.\n\nAsk what they are replacing it with and confirm the unit they are interested in.\n\nSet the appraisal appointment with two times. Tell them what to bring (title or payoff letter). Get the cell number.",
     "success_points": ["Asks mileage, condition and payoff", "Does not guess a trade number over the phone", "Connects the trade to the vehicle they want", "Offers two appointment times", "Tells them what to bring", "Gets the caller's phone number"],
     "persona": {"name": "Priya Raman", "voice": "female", "summary": "29, nurse, owns a 2019 Honda CR-V with 61,000 miles, one small fender bender repaired. Interested in {vehicle} at {store}. Careful, wants a fair number.",
                 "goals": "Get a real trade value. Will come in if the rep explains the process and gives a time.",
                 "objections": ["Carvana gave me a number online in two minutes", "Can you at least give me a range?", "I don't want to sit at a dealership all day"],
                 "opening_line": "Hi, I've got a CR-V I'm thinking about trading in on {vehicle}. Can you tell me what it's worth?"}},
    {"slug": "shop_sales_price_match", "department": "sales", "category": "Objections", "title": "Shopper: the other store is cheaper", "runtime": "3 to 4 min",
     "purpose": "A shopper has a competing quote and wants you to beat it. A great rep stays calm, asks what the quote includes, and earns the visit.",
     "body": "Thank them for the honesty. Ask what the other quote includes: out the door, fees, trade, add-ons.\n\nDo not trash the competitor. Ask them to send the quote so you can compare apples to apples.\n\nOffer a specific appointment with two times and a promise: an honest answer on whether you can match it.",
     "success_points": ["Stays calm and thanks the caller", "Asks what the competing quote includes", "Does not badmouth the competitor", "Asks for the quote in writing", "Offers two appointment times", "Gets the caller's name and number"],
     "persona": {"name": "Tom Gerlach", "voice": "older", "summary": "58, retired, shopping {vehicle} at {store} and at a store across town that quoted 900 dollars less. Polite but firm, likes to negotiate.",
                 "goals": "Get a better price or a good reason to pick this store. Will book if the rep is honest and specific.",
                 "objections": ["Why should I drive to you if they're cheaper?", "Just match it and I'll come in today", "I've bought six cars, I know how this works"],
                 "opening_line": "Hi, I'm calling about {vehicle}. The dealer across town quoted me about nine hundred less on the same thing, can you beat that?"}},
    {"slug": "shop_sales_just_looking", "department": "sales", "category": "Sales calls", "title": "Shopper: just looking, early in the process", "runtime": "2 to 4 min",
     "purpose": "A soft, early shopper with lots of questions and no urgency. A great rep is helpful, asks discovery questions, and still asks for the visit and the number.",
     "body": "Be genuinely helpful. Ask what they are comparing and what matters most (space, mileage, budget, features).\n\nOffer a low pressure next step: come drive it, no commitment. Two times.\n\nGet the name and cell so you can text photos or a walkaround video.",
     "success_points": ["Asks what they are comparing", "Asks what matters most to them", "Offers a low pressure test drive with two times", "Offers to text photos or a video", "Gets the caller's name and number"],
     "persona": {"name": "Kelly Nguyen", "voice": "young", "summary": "26, first time buying from a dealer, saw {vehicle} at {store}. Curious, asks a lot of questions, no rush.",
                 "goals": "Learn without being pressured. Will give a number for photos if the rep is easy to talk to.",
                 "objections": ["I'm just looking right now", "I'm not ready to come in yet", "How is it different from the one at the other lot?"],
                 "opening_line": "Hi, I'm kind of early in my search but I saw {vehicle} on your site. Can you tell me a little about it?"}},
    {"slug": "shop_service_appointment", "department": "service", "category": "Service", "title": "Service caller: book an oil change", "runtime": "2 to 4 min",
     "purpose": "The everyday service call. A great advisor confirms the vehicle, offers the first available time, mentions transportation options and recaps.",
     "body": "Answer with the department and your name. Get the caller's name and the vehicle (year, make, model or mileage).\n\nAsk what they are noticing beyond the oil change.\n\nOffer the first available appointment, then an alternative. Mention shuttle, loaner or waiting area.\n\nConfirm the phone number for the reminder text and recap day, time and what to bring.",
     "success_points": ["Answers with the department and their name", "Confirms the vehicle", "Asks about other concerns", "Offers the first available time", "Mentions shuttle, loaner or waiting area", "Confirms the phone number", "Recaps the appointment"],
     "persona": {"name": "Angela Ruiz", "voice": "female", "summary": "45, teacher, drives {vehicle}, due for an oil change and a tire rotation. Pleasant, busy after school hours.",
                 "goals": "Get booked at a time that fits and know how long it takes.",
                 "objections": ["How long is that going to take?", "Do you have anything after 4?", "Is it cheaper at the quick lube place?"],
                 "opening_line": "Hi, I need to get an oil change scheduled on {vehicle}. What do you have this week?"}},
    {"slug": "shop_service_warning_light", "department": "service", "category": "Service", "title": "Service caller: warning light just came on", "runtime": "3 to 4 min",
     "purpose": "A nervous customer with a check engine light. A great advisor reassures, asks the right questions, and gets the car in quickly.",
     "body": "Reassure first. Ask which light, whether it is flashing, and how the vehicle is driving.\n\nExplain what a diagnostic visit looks like and roughly how long. Ask about warranty coverage or mileage.\n\nOffer the soonest slot, mention transportation options, confirm the number and recap.",
     "success_points": ["Reassures the caller", "Asks whether the light is flashing and how it drives", "Explains the diagnostic step", "Asks about warranty or mileage", "Offers the soonest appointment", "Mentions transportation options", "Confirms the phone number"],
     "persona": {"name": "Derek Holloway", "voice": "male", "summary": "52, sales rep who drives a lot, check engine light came on this morning in {vehicle}. Worried about being without a car.",
                 "goals": "Know if it is safe to drive and get it looked at fast without losing a work day.",
                 "objections": ["Is it safe to keep driving it?", "I can't be without my car for a whole day", "How much is the diagnostic going to cost me?"],
                 "opening_line": "Hi, the check engine light just came on in {vehicle} this morning. Should I be worried, and how soon can you look at it?"}},
    {"slug": "shop_service_price_quote", "department": "service", "category": "Service", "title": "Service caller: how much for brakes?", "runtime": "2 to 4 min",
     "purpose": "A price shopper for a common repair. A great advisor gives a helpful range, explains what drives the price, and books an inspection.",
     "body": "Ask the vehicle and what they are noticing (noise, pulsing, mileage on the pads).\n\nGive an honest range and explain what changes it: pads only versus rotors, front versus rear.\n\nOffer a free or low cost inspection with a firm time, mention how long it takes, confirm the number.",
     "success_points": ["Confirms the vehicle", "Asks what they are noticing", "Gives an honest price range", "Explains what changes the price", "Offers an inspection appointment with a time", "Confirms the phone number"],
     "persona": {"name": "Lisa Ferraro", "voice": "female", "summary": "38, small business owner, hears a grinding noise when braking in {vehicle}. Practical, comparing prices with an independent shop.",
                 "goals": "Get a real price and decide where to go. Will book if the advisor is straight with her.",
                 "objections": ["The shop down the street quoted me four hundred", "Can't you just give me a number?", "Do I really need rotors too?"],
                 "opening_line": "Hi, I'm hearing a grinding noise when I brake on {vehicle}. Can you tell me what brakes would run me?"}},
    {"slug": "shop_service_recall", "department": "service", "category": "Service", "title": "Service caller: recall notice in the mail", "runtime": "2 to 3 min",
     "purpose": "A customer got a recall letter. A great advisor confirms the VIN or vehicle, explains the fix is no charge, and books it while checking for other needs.",
     "body": "Ask for the vehicle and, if possible, the VIN or the recall number on the letter.\n\nExplain that recall work is no charge and roughly how long it takes. Ask about anything else the vehicle needs while it is in.\n\nOffer two times, mention transportation options, confirm the number and recap.",
     "success_points": ["Asks for the vehicle or VIN", "Confirms the recall is no charge", "Explains how long it takes", "Asks about other service needs", "Offers two appointment times", "Confirms the phone number"],
     "persona": {"name": "George Patel", "voice": "older", "summary": "64, retired engineer, got a recall letter for {vehicle}. Methodical, wants clear answers.",
                 "goals": "Get the recall handled and understand what is involved.",
                 "objections": ["Do I have to pay anything for this?", "How long will you need the car?", "Can you do the oil change at the same time?"],
                 "opening_line": "Hello, I received a recall notice for {vehicle}. I'd like to get that taken care of."}},
]


def _now():
    return datetime.now(timezone.utc)


def _oid(v) -> ObjectId:
    return ObjectId(str(v))


def _tz(client: dict) -> ZoneInfo:
    try:
        return ZoneInfo(client.get("timezone") or "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


def _hours(client: dict) -> dict:
    h = {**DEFAULT_HOURS, **(client.get("hours") or {})}
    h["days"] = [int(d) for d in (h.get("days") or DEFAULT_HOURS["days"])]
    return h


def _hm(v: str, fallback: str) -> tuple:
    try:
        hh, mm = (v or fallback).split(":")
        return int(hh), int(mm)
    except Exception:
        return tuple(int(x) for x in fallback.split(":"))


async def ensure_challenges(db) -> int:
    n = 0
    for tpl in STARTER_CHALLENGES:
        res = await db.scripts.update_one(
            {"slug": tpl["slug"], "pool": "mystery_shop", "shop_client_id": None},
            {"$setOnInsert": {**tpl, "kind": "phone", "pool": "mystery_shop", "industry": "automotive", "store_id": None, "shop_client_id": None, "direction": "inbound", "active": True, "created_at": _now(), "updated_at": _now()}}, upsert=True)
        n += 1 if res.upserted_id else 0
    await db.scripts.update_many({"pool": "mystery_shop", "industry": {"$exists": False}}, {"$set": {"industry": "automotive"}})
    return n


def offerings_of(client: dict) -> list:
    return [str(v).strip() for v in (client.get("offerings") or client.get("vehicles") or []) if str(v).strip()]


def plan_per_month(client: dict) -> dict:
    """Shops per department per month. New accounts store plan.per_month; the original automotive accounts stored sales_per_month / service_per_month."""
    plan = client.get("plan") or {}
    per = plan.get("per_month")
    if isinstance(per, dict) and per:
        return {k: int(v or 0) for k, v in per.items()}
    return {k: int(plan.get(f"{k}_per_month") or 0) for k in ind.dept_keys(ind.key_of(client)) if plan.get(f"{k}_per_month") is not None}


def terms_per_month(t: dict) -> dict:
    per = (t or {}).get("per_month")
    if isinstance(per, dict) and per:
        return {k: int(v or 0) for k, v in per.items()}
    return {k: int((t or {}).get(f"{k}_per_month") or 0) for k in ("sales", "service") if (t or {}).get(f"{k}_per_month")}


def per_month_text(per: dict, joiner: str = " + ") -> str:
    parts = [f"{n} {ind.dept_label(k).lower()}" for k, n in per.items() if int(n or 0) > 0]
    return joiner.join(parts) if parts else "0"


# ---------------------------------------------------------------- clients + people
def serialize_client(c: dict, extra: Optional[dict] = None) -> dict:
    out = {"id": str(c["_id"]), "name": c.get("name", ""), "brand": c.get("brand", ""), "city": c.get("city", ""), "state": c.get("state", ""), "timezone": c.get("timezone") or "America/Denver",
           "contact_name": c.get("contact_name", ""), "contact_email": c.get("contact_email", ""), "contact_phone": c.get("contact_phone", ""), "contact_title": c.get("contact_title", ""),
           "plan": {"per_month": plan_per_month(c), "sales_per_month": plan_per_month(c).get("sales", 0), "service_per_month": plan_per_month(c).get("service", 0), "price_monthly": float((c.get("plan") or {}).get("price_monthly") or 0)},
           "industry": ind.key_of(c), "industry_label": ind.get(ind.key_of(c))["label"], "departments": ind.dept_options(ind.key_of(c)), "offering": ind.get(ind.key_of(c))["offering"], "customer_noun": ind.get(ind.key_of(c))["customer"],
           "hours": _hours(c), "vehicles": offerings_of(c), "offerings": offerings_of(c), "active": c.get("active", True), "record_calls": c.get("record_calls", True), "notes": c.get("notes", ""),
           "from_number": c.get("from_number") or "", "report_token": c.get("report_token"), "scorecards": c.get("scorecards") or {}, "billing": c.get("billing") or {},
           "demo": bool(c.get("demo")), "text_scorecards": bool(c.get("text_scorecards")),
           "created_at": c.get("created_at").isoformat() if c.get("created_at") else None}
    if extra:
        out.update(extra)
    return out


def serialize_target(t: dict, extra: Optional[dict] = None) -> dict:
    out = {"id": str(t["_id"]), "client_id": t.get("client_id"), "name": t.get("name", ""), "phone": t.get("phone", ""), "department": t.get("department", "sales"), "department_label": ind.dept_label(t.get("department")), "title": t.get("title", ""),
           "notes": t.get("notes", ""), "active": t.get("active", True), "challenge_history": t.get("challenge_history") or [], "created_at": t.get("created_at").isoformat() if t.get("created_at") else None}
    if extra:
        out.update(extra)
    return out


def serialize_call(s: dict) -> dict:
    return {"id": str(s["_id"]), "client_id": s.get("client_id"), "target_id": s.get("target_id"), "target_name": s.get("rep_name"), "department": s.get("department"), "department_label": ind.dept_label(s.get("department")),
            "industry": s.get("industry") or ind.industry_of_dept(s.get("department")), "customer_noun": ind.get(s.get("industry") or ind.industry_of_dept(s.get("department")))["customer"], "status": s.get("status"),
            "outcome": s.get("outcome"), "fail_reason": s.get("fail_reason"), "script_id": s.get("script_id"), "script_title": s.get("script_title"), "persona_name": (s.get("persona") or {}).get("name"),
            "curveballs": s.get("curveballs") or [], "scheduled_for": s["scheduled_for"].isoformat() if s.get("scheduled_for") else None, "attempts": s.get("attempts", 0),
            "started_at": s["started_at"].isoformat() if s.get("started_at") else None, "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
            "score_pct": s.get("score_pct"), "adherence_pct": s.get("adherence_pct"), "evaluation_id": s.get("evaluation_id"), "recording_url": s.get("recording_url"),
            "recording_seconds": s.get("recording_seconds"), "turns": len(s.get("turns") or []), "manual": bool(s.get("manual")), "demo": bool(s.get("demo")),
            "score_url": f"{scr._app_url()}/shop-score/{s['score_token']}" if s.get("score_token") else None, "score_sms_status": s.get("score_sms_status"), "score_views": s.get("score_views") or 0}


# ---------------------------------------------------------------- challenge rotation
def fill_persona(persona: dict, client: dict, department: str) -> dict:
    industry = ind.key_of(client)
    d = ind.dept(department, industry)
    pool = offerings_of(client) or d.get("defaults") or ["what you have listed online"]
    offering = random.choice(pool)
    low = offering.lower()
    if industry == "automotive":
        if department in ("sales", "rental") and not low.startswith(("the ", "a ", "an ", "that ")):
            offering = f"{'a' if department == 'rental' else 'the'} {offering}"
        elif department in ("service", "parts") and not low.startswith(("my ", "our ")):
            offering = f"my {offering}"
    elif not low.startswith(("the ", "a ", "an ", "my ", "our ", "your ", "that ")):
        offering = f"the {offering}"
    place = client.get("name") or f"the {ind.get(industry)['place']}"
    return {k: ind.fill_offering(v, offering, place) for k, v in (persona or {}).items()} | {"vehicle": offering, "offering": offering}


async def challenge_pool(db, client_id: Optional[str], department: Optional[str] = None, industry: Optional[str] = None) -> list:
    await ensure_challenges(db)
    q = {"kind": "phone", "pool": "mystery_shop", "active": {"$ne": False}, "$or": [{"shop_client_id": None}, {"shop_client_id": client_id}]}
    if department:
        q["department"] = department
    elif industry:
        q["industry"] = industry
    return await db.scripts.find(q).sort([("department", 1), ("title", 1)]).to_list(200)


async def pick_challenge(db, client: dict, target: dict) -> Optional[dict]:
    """A challenge this person has not had; once they have had them all, the one they had longest ago."""
    pool = await challenge_pool(db, str(client["_id"]), target.get("department") or "sales")
    if not pool:
        return None
    history = [str(x) for x in (target.get("challenge_history") or [])]
    fresh = [s for s in pool if str(s["_id"]) not in history]
    if fresh:
        return random.choice(fresh)
    order = {sid: i for i, sid in enumerate(history)}
    pool.sort(key=lambda s: order.get(str(s["_id"]), -1))
    return pool[0]


# ---------------------------------------------------------------- scheduling
def _local_window(client: dict, day: datetime) -> Optional[tuple]:
    h = _hours(client)
    if day.weekday() not in h["days"]:
        return None
    sh, sm = _hm(h.get("start"), "09:00")
    eh, em = _hm(h.get("end"), "18:00")
    start = day.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = day.replace(hour=eh, minute=em, second=0, microsecond=0)
    return (start, end) if end > start else None


def in_hours(client: dict, when: Optional[datetime] = None) -> bool:
    local = (when or _now()).astimezone(_tz(client))
    win = _local_window(client, local)
    return bool(win and win[0] <= local <= win[1])


def next_slot(client: dict, after: datetime, min_gap_minutes: int = 90) -> datetime:
    """A random moment inside business hours, at least min_gap after `after` (retries) and never in the last 20 minutes of the day."""
    tz = _tz(client)
    local = after.astimezone(tz) + timedelta(minutes=min_gap_minutes)
    for i in range(14):
        day = (local + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        win = _local_window(client, day)
        if not win:
            continue
        start = max(win[0], local) if i == 0 else win[0]
        end = win[1] - timedelta(minutes=20)
        if end <= start:
            continue
        secs = int((end - start).total_seconds())
        return (start + timedelta(seconds=random.randint(0, secs))).astimezone(timezone.utc)
    return (after + timedelta(days=1)).astimezone(timezone.utc)


def month_bounds(month: Optional[str], tz: ZoneInfo) -> tuple:
    """(start, end) of a YYYY-MM month in the client's timezone, as UTC."""
    now_local = _now().astimezone(tz)
    if month:
        y, m = (int(x) for x in month.split("-")[:2])
    else:
        y, m = now_local.year, now_local.month
    start = datetime(y, m, 1, tzinfo=tz)
    end = datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def create_shop_call(db, client: dict, target: dict, when: datetime, created_by: Optional[str] = None, manual: bool = False, script: Optional[dict] = None) -> Optional[dict]:
    script = script or await pick_challenge(db, client, target)
    if not script:
        return None
    dept = target.get("department") or "sales"
    persona = fill_persona(script.get("persona") or {}, client, dept)
    industry = ind.key_of(client)
    pool_cb = [c for c in (script.get("curveballs") or []) if str(c).strip()] or ind.dept(dept, industry).get("curveballs", [])
    curve = random.sample(pool_cb, k=min(len(pool_cb), random.choice([0, 1, 1, 2])))
    now = _now()
    doc = {"kind": "mystery_shop", "mode": "phone", "status": "scheduled", "user_id": None, "client_id": str(client["_id"]), "target_id": str(target["_id"]),
           "rep_name": target.get("name") or "", "rep_phone": target.get("phone"), "department": dept, "industry": industry, "store_id": None, "store_name": client.get("name") or f"the {ind.get(industry)['place']}",
           "script_id": str(script["_id"]), "script_title": script.get("title"), "script_slug": script.get("slug"), "direction": script.get("direction") if script.get("direction") in ("inbound", "outbound") else "inbound", "persona": persona, "curveballs": curve,
           "assignment_id": None, "scheduled_for": when, "attempts": 0, "max_attempts": 3, "manual": manual, "token": uuid.uuid4().hex, "turns": [],
           "created_by": created_by, "created_at": now, "updated_at": now}
    res = await db.roleplay_sessions.insert_one(doc)
    await db.shop_targets.update_one({"_id": target["_id"]}, {"$push": {"challenge_history": str(script["_id"])}})
    doc["_id"] = res.inserted_id
    return doc


async def plan_month(db, client: dict, month: Optional[str] = None, created_by: Optional[str] = None) -> dict:
    """Top the month up to the plan quota per department, spread over the remaining business days, rotating people evenly."""
    tz = _tz(client)
    start, end = month_bounds(month, tz)
    now = _now()
    per = plan_per_month(client)
    created = {k: 0 for k in ind.dept_keys(ind.key_of(client))}
    for dept in ind.dept_keys(ind.key_of(client)):
        quota = int(per.get(dept) or 0)
        if quota <= 0:
            continue
        existing = await db.roleplay_sessions.count_documents({"kind": "mystery_shop", "client_id": str(client["_id"]), "department": dept, "scheduled_for": {"$gte": start, "$lt": end}, "status": {"$ne": "canceled"}})
        missing = quota - existing
        targets = await db.shop_targets.find({"client_id": str(client["_id"]), "department": dept, "active": {"$ne": False}}).to_list(200)
        if missing <= 0 or not targets:
            continue
        counts = {}
        async for s in db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": str(client["_id"]), "department": dept, "scheduled_for": {"$gte": start, "$lt": end}, "status": {"$ne": "canceled"}}, {"target_id": 1}):
            counts[s.get("target_id")] = counts.get(s.get("target_id"), 0) + 1
        targets.sort(key=lambda t: counts.get(str(t["_id"]), 0))
        from_dt = max(now + timedelta(minutes=30), start)
        if from_dt >= end:
            continue
        slots = []
        for _ in range(missing * 3):
            cand = next_slot(client, from_dt + timedelta(seconds=random.randint(0, max(60, int((end - from_dt).total_seconds())))), min_gap_minutes=0)
            if from_dt <= cand < end:
                slots.append(cand)
        slots = sorted(slots)[:missing]
        if len(slots) < missing:
            slots += [next_slot(client, from_dt, min_gap_minutes=0) for _ in range(missing - len(slots))]
        for i, when in enumerate(slots):
            t = targets[i % len(targets)]
            if await create_shop_call(db, client, t, when, created_by=created_by):
                created[dept] += 1
    return created


# ---------------------------------------------------------------- placing + outcomes
SHOP_NUMBER_KEY = "mystery_shop_from_number"


async def saved_shop_number(db) -> Optional[dict]:
    """The number Forest picked (or bought) as the main Mystery Shop caller ID, if any."""
    row = await db.settings.find_one({"key": SHOP_NUMBER_KEY})
    return row if row and row.get("value") else None


async def default_from_number(db) -> str:
    row = await saved_shop_number(db)
    return (row or {}).get("value") or os.environ.get("MYSTERY_SHOP_FROM_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER", "")


async def from_number(db, client: Optional[dict]) -> str:
    """Per-client override first, then the saved default, then the platform number."""
    return (client or {}).get("from_number") or await default_from_number(db)


async def is_shop_number(db, phone: str) -> bool:
    """True when an inbound call/text hits a number we shop from (so it must never ring a real person)."""
    if not phone:
        return False
    row = await saved_shop_number(db)
    if row and row.get("value") == phone:
        return True
    return bool(await db.shop_clients.find_one({"from_number": phone}, {"_id": 1}))


async def place_shop_call(db, call: dict) -> bool:
    from services.lead_call_engine import _twilio_client
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])})
    tw = _twilio_client()
    frm = await from_number(db, client) if client else ""
    if not client or tw is None or not frm or not call.get("rep_phone"):
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "failed", "outcome": "not_configured", "fail_reason": "Calling is not set up (no caller number)", "updated_at": _now()}})
        return False
    sid, token = str(call["_id"]), call["token"]
    base = f"{scr._app_url()}/api/scripts/roleplay"
    now = _now()
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "dialing", "started_at": now, "last_attempt_at": now, "updated_at": now, "from_number": frm}, "$inc": {"attempts": 1}})
    try:
        tw_call = await asyncio.to_thread(
            tw.calls.create, to=call["rep_phone"], from_=frm, url=f"{base}/twiml/{sid}?t={token}", method="POST",
            status_callback=f"{base}/status/{sid}?t={token}", status_callback_event=["answered", "completed"], status_callback_method="POST",
            record=bool(client.get("record_calls", True)), recording_status_callback=f"{base}/recording/{sid}?t={token}", recording_status_callback_event=["completed"],
            timeout=25, time_limit=scr.CALL_TIME_LIMIT_S)
    except Exception as e:
        logger.warning(f"[MysteryShop] could not place call {sid}: {e}")
        await record_outcome(db, {**call, "attempts": call.get("attempts", 0) + 1}, "failed", "The call could not be placed")
        return False
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"call_sid": tw_call.sid, "call_status": "queued"}})
    return True


OUTCOME_LABEL = {"voicemail": "Went to voicemail", "no-answer": "No answer", "busy": "Line was busy", "failed": "The call could not be placed", "canceled": "The call was cancelled", "hung_up": "Hung up before the shop started",
                 "no_response": "Went to voicemail or wasn't ready", "postponed": "Asked us to call back later"}


async def postpone_call(db, call: dict, hours: int = 2):
    """Rep pressed 2 (bad time): same shop again in a couple of hours, inside store hours, and it does not count as a try."""
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])}) or {}
    now = _now()
    when = now + timedelta(hours=hours)
    if client and not in_hours(client, when):
        when = next_slot(client, when, min_gap_minutes=0)
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": when, "outcome": "postponed", "fail_reason": OUTCOME_LABEL["postponed"], "call_sid": None, "call_status": None, "turns": [], "updated_at": now},
                                                               "$inc": {"attempts": -1 if int(call.get("attempts") or 0) > 0 else 0},
                                                               "$push": {"attempt_history": {"at": now, "outcome": "postponed", "call_sid": call.get("call_sid")}}})


async def record_outcome(db, call: dict, outcome: str, reason: Optional[str] = None):
    """A shop attempt that never became a conversation: retry later inside business hours, or give up after max attempts. Quick shops never auto-retry (the admin taps Try again)."""
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])}) or {}
    attempts = int(call.get("attempts") or 0)
    label = reason or OUTCOME_LABEL.get(outcome, outcome)
    now = _now()
    history = {"at": now, "outcome": outcome, "call_sid": call.get("call_sid")}
    if attempts < int(call.get("max_attempts") or 3) and client and not client.get("demo"):
        when = next_slot(client, now, min_gap_minutes=random.randint(90, 240))
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": when, "outcome": outcome, "fail_reason": f"{label}, trying again", "call_sid": None, "call_status": None, "turns": [], "updated_at": now},
                                                                   "$push": {"attempt_history": history}})
    else:
        tries = "" if client.get("demo") else f" ({attempts} {'try' if attempts == 1 else 'tries'})"
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "unreachable", "outcome": outcome, "fail_reason": f"{label}{tries}", "ended_at": now, "updated_at": now}, "$push": {"attempt_history": history}})
        if call.get("enrollment_id"):
            from services import courses as cs
            e = await db.course_enrollments.find_one({"_id": ObjectId(call["enrollment_id"])}) if ObjectId.is_valid(str(call["enrollment_id"])) else None
            course = await db.courses.find_one({"_id": ObjectId(e["course_id"])}) if e else None
            rounds = int((e or {}).get("unreachable_rounds") or 0)
            if e and course and rounds < 3:
                await db.course_enrollments.update_one({"_id": e["_id"]}, {"$set": {"unreachable_rounds": rounds + 1, "updated_at": now}})
                await cs.schedule_next_shop(db, e, course, delay_minutes=24 * 60)


async def sweep_stuck_calls(db) -> int:
    """Lost Twilio callbacks: ask Twilio about anything still dialing after 2 min, give up after 10; finalize a 'live' call nobody has touched in 20 min."""
    now = _now()
    n = 0
    rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "mode": "phone", "status": {"$in": ["dialing", "live"]}, "started_at": {"$lte": now - timedelta(minutes=2)}}).to_list(50)
    for s in rows:
        started = s["started_at"].replace(tzinfo=timezone.utc) if s["started_at"].tzinfo is None else s["started_at"]
        age = (now - started).total_seconds() / 60
        if s["status"] == "dialing":
            s = await scr.reconcile_dialing(db, s)
            if s.get("status") == "dialing" and age >= 10:
                await record_outcome(db, s, "no-answer")
                n += 1
        elif age >= scr.PHONE_MAX_MINUTES + 5:
            await scr.finalize_session(db, str(s["_id"]), "swept_stale")
            n += 1
    return n


async def run_due_calls(db, limit: int = 3) -> int:
    """Scheduler tick: dial shops whose time has come (inside the client's hours), a few at a time."""
    now = _now()
    try:
        await sweep_stuck_calls(db)
    except Exception as e:
        logger.warning(f"[MysteryShop] sweep failed: {e}")
    due = await db.roleplay_sessions.find({"kind": "mystery_shop", "status": "scheduled", "scheduled_for": {"$lte": now}}).sort("scheduled_for", 1).limit(limit * 3).to_list(limit * 3)
    placed = 0
    for call in due:
        if placed >= limit:
            break
        client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])})
        if not client or not client.get("active", True):
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "canceled", "fail_reason": "Client paused", "updated_at": now}})
            continue
        if not call.get("manual") and not in_hours(client, now):
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"scheduled_for": next_slot(client, now, min_gap_minutes=0), "updated_at": now}})
            continue
        busy = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "target_id": call["target_id"], "status": {"$in": ["dialing", "live", "grading"]}}, {"_id": 1})
        if busy:
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"scheduled_for": now + timedelta(minutes=45), "updated_at": now}})
            continue
        claimed = await db.roleplay_sessions.find_one_and_update({"_id": call["_id"], "status": "scheduled"}, {"$set": {"status": "dialing", "updated_at": now}})
        if claimed and await place_shop_call(db, claimed):
            placed += 1
    return placed


async def plan_active_clients(db) -> int:
    """Daily: make sure every active client's current month is fully scheduled."""
    n = 0
    async for client in db.shop_clients.find({"active": {"$ne": False}}):
        try:
            made = await plan_month(db, client)
            n += sum(made.values())
        except Exception as e:
            logger.warning(f"[MysteryShop] planning failed for {client.get('name')}: {e}")
    return n


# ---------------------------------------------------------------- grading hook (called from scripts.grade_session)
async def scorecard_for(db, session: dict) -> Optional[dict]:
    client = await db.shop_clients.find_one({"_id": _oid(session["client_id"])}) or {}
    dept = session.get("department") or "sales"
    cid = (client.get("scorecards") or {}).get(dept)
    if cid and ObjectId.is_valid(str(cid)):
        card = await db.scorecards.find_one({"_id": ObjectId(str(cid)), "active": {"$ne": False}})
        if card:
            return card
    return template_card(dept)


def template_card(dept: str) -> Optional[dict]:
    """The department's built-in scorecard (from its industry pack), so every course taker and every shop is graded the same way."""
    d = ind.dept(dept)
    if d.get("template"):
        body = sc.template_body(d["template"])
        if not body:
            return None
        return {"_id": None, "name": body["name"], "department": body["department"], "criteria": sc.normalize_criteria(body["criteria"]), "alert_on_critical": False}
    card = d.get("scorecard") or {}
    if not card.get("criteria"):
        return None
    return {"_id": None, "name": card.get("name") or f"{d['label']} Call", "department": d["label"], "criteria": sc.normalize_criteria(card["criteria"]), "alert_on_critical": False}


# ---------------------------------------------------------------- report
def _pct(vals: list) -> Optional[int]:
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals)) if vals else None


async def build_report(db, client: dict, month: Optional[str] = None) -> dict:
    tz = _tz(client)
    start, end = month_bounds(month, tz)
    cid = str(client["_id"])
    calls = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "scheduled_for": {"$gte": start, "$lt": end}, "status": {"$ne": "canceled"}}).sort("scheduled_for", 1).to_list(500)
    done = [c for c in calls if c.get("status") == "completed"]
    ev_ids = [ObjectId(c["evaluation_id"]) for c in done if c.get("evaluation_id") and ObjectId.is_valid(str(c["evaluation_id"]))]
    evals = {str(e["_id"]): e for e in await db.call_evaluations.find({"_id": {"$in": ev_ids}}).to_list(500)} if ev_ids else {}
    targets = {str(t["_id"]): t for t in await db.shop_targets.find({"client_id": cid}).to_list(500)}
    people = {}
    for c in calls:
        p = people.setdefault(c["target_id"], {"target_id": c["target_id"], "name": c.get("rep_name"), "department": c.get("department"), "shops": 0, "completed": 0, "unreachable": 0, "scores": [], "adherence": [], "critical_misses": 0, "last_shop": None, "coaching": []})
        p["shops"] += 1
        if c.get("status") == "completed":
            p["completed"] += 1
            p["scores"].append(c.get("score_pct"))
            p["adherence"].append(c.get("adherence_pct"))
            ev = evals.get(str(c.get("evaluation_id")))
            if ev:
                p["critical_misses"] += len(ev.get("critical_misses") or [])
                p["coaching"] += (ev.get("coaching") or [])[:2]
            p["last_shop"] = (c.get("ended_at") or c.get("scheduled_for"))
        elif c.get("status") == "unreachable":
            p["unreachable"] += 1
    rows = []
    for p in people.values():
        avg = _pct(p["scores"])
        rows.append({**p, "avg_score": avg, "avg_adherence": _pct(p["adherence"]), "best": max([s for s in p["scores"] if s is not None], default=None), "worst": min([s for s in p["scores"] if s is not None], default=None),
                     "needs_training": bool(p["completed"] and ((avg is not None and avg < 70) or p["critical_misses"] >= 2)), "last_shop": p["last_shop"].isoformat() if p["last_shop"] else None,
                     "title": (targets.get(p["target_id"]) or {}).get("title", ""), "coaching": p["coaching"][:3]})
        rows[-1].pop("scores"); rows[-1].pop("adherence")
    rows.sort(key=lambda r: (r["avg_score"] is None, -(r["avg_score"] or 0)))
    # what the whole store misses: pass rate per criterion text (N/A excluded)
    crit = {}
    for ev in evals.values():
        for r in ev.get("results") or []:
            if r.get("passed") is None:
                continue
            k = r.get("text") or r.get("criterion_id")
            d = crit.setdefault(k, {"text": k, "critical": bool(r.get("critical")), "passed": 0, "total": 0, "department": ev.get("department") or ""})
            d["total"] += 1
            d["passed"] += 1 if r.get("passed") else 0
    criteria = sorted([{**d, "pass_pct": round(100 * d["passed"] / d["total"])} for d in crit.values() if d["total"]], key=lambda d: d["pass_pct"])
    scores = [c.get("score_pct") for c in done]
    by_dept = {}
    per = plan_per_month(client)
    depts = list(dict.fromkeys(ind.dept_keys(ind.key_of(client)) + [c.get("department") for c in calls if c.get("department")]))
    for d in depts:
        dc = [c for c in done if c.get("department") == d]
        if not per.get(d) and not dc and not any(c.get("department") == d for c in calls):
            continue
        by_dept[d] = {"label": ind.dept_label(d), "planned": int(per.get(d) or 0), "scheduled": len([c for c in calls if c.get("department") == d and c.get("status") in CALL_STATUSES_OPEN]),
                      "completed": len(dc), "unreachable": len([c for c in calls if c.get("department") == d and c.get("status") == "unreachable"]), "avg_score": _pct([c.get("score_pct") for c in dc])}
    call_rows = []
    for c in sorted(calls, key=lambda x: x.get("ended_at") or x.get("scheduled_for") or _now(), reverse=True):
        ev = evals.get(str(c.get("evaluation_id"))) if c.get("evaluation_id") else None
        call_rows.append({**serialize_call(c), "summary": (ev or {}).get("summary"), "critical_misses": sc.miss_labels(ev or {}), "coaching": (ev or {}).get("coaching") or [],
                          "wins": (ev or {}).get("wins") or [], "adherence": (ev or {}).get("adherence") or {}, "results": (ev or {}).get("results") or [], "transcript": (ev or {}).get("transcript") or scr.transcript_text(c),
                          "customer_sentiment": (ev or {}).get("customer_sentiment")})
    themes = {}
    for ev in evals.values():
        for tip in (ev.get("coaching") or [])[:3]:
            key = no_em_dash(str(tip)).strip().rstrip(".")
            themes[key] = themes.get(key, 0) + 1
    label = start.astimezone(tz).strftime("%B %Y")
    return {"client": {"id": cid, "name": client.get("name"), "brand": client.get("brand", ""), "city": client.get("city", ""), "state": client.get("state", ""), "contact_name": client.get("contact_name", ""),
                       "industry": ind.key_of(client), "industry_label": ind.get(ind.key_of(client))["label"], "customer_noun": ind.get(ind.key_of(client))["customer"], "business_noun": ind.get(ind.key_of(client))["business"]},
            "month": start.astimezone(tz).strftime("%Y-%m"), "month_label": label, "generated_at": _now().isoformat(),
            "summary": {"completed": len(done), "planned": sum(v["planned"] for v in by_dept.values()), "scheduled": len([c for c in calls if c.get("status") in CALL_STATUSES_OPEN]),
                        "unreachable": len([c for c in calls if c.get("status") == "unreachable"]), "avg_score": _pct(scores), "avg_adherence": _pct([c.get("adherence_pct") for c in done]),
                        "people_shopped": len([r for r in rows if r["completed"]]), "needs_training": len([r for r in rows if r["needs_training"]])},
            "by_department": by_dept, "people": rows, "criteria": criteria, "coaching_themes": [{"text": k, "count": v} for k, v in sorted(themes.items(), key=lambda kv: -kv[1])[:6]], "calls": call_rows}


def report_pdf(report: dict) -> bytes:
    from fpdf import FPDF
    GOLD, INK, MUTED, RED, GREEN = (201, 169, 98), (20, 20, 20), (110, 110, 110), (220, 60, 50), (40, 160, 90)
    pdf = FPDF(format="letter")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()

    def txt(s: str) -> str:
        return (s or "").encode("latin-1", "replace").decode("latin-1")

    def h(s, size=16, color=INK, gap=2):
        pdf.set_font("Helvetica", "B", size); pdf.set_text_color(*color); pdf.cell(0, size * 0.5, txt(s), new_x="LMARGIN", new_y="NEXT"); pdf.ln(gap)

    def p(s, size=10, color=INK, style=""):
        pdf.set_font("Helvetica", style, size); pdf.set_text_color(*color); pdf.multi_cell(0, size * 0.5, txt(s), new_x="LMARGIN", new_y="NEXT")

    c, s = report["client"], report["summary"]
    pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*GOLD); pdf.cell(0, 5, "I'M ON SOCIAL  |  MYSTERY SHOP REPORT", new_x="LMARGIN", new_y="NEXT")
    h(f"{c['name']}", 20)
    p(f"{report['month_label']}  |  {c.get('brand') or ''}  {c.get('city') or ''} {c.get('state') or ''}".strip(), 10, MUTED)
    pdf.ln(3)
    pdf.set_fill_color(247, 243, 232)
    boxes = [("Shops completed", f"{s['completed']} of {s['planned']}"), ("Average score", f"{s['avg_score']}%" if s['avg_score'] is not None else "n/a"),
             ("People shopped", str(s['people_shopped'])), ("Need training", str(s['needs_training']))]
    w = (pdf.w - 32) / 4
    y = pdf.get_y()
    for i, (lab, val) in enumerate(boxes):
        x = 16 + i * w
        pdf.set_xy(x, y); pdf.set_fill_color(247, 243, 232); pdf.rect(x + 1, y, w - 2, 18, "F")
        pdf.set_xy(x + 3, y + 2); pdf.set_font("Helvetica", "B", 14); pdf.set_text_color(*INK); pdf.cell(w - 6, 8, txt(val))
        pdf.set_xy(x + 3, y + 10); pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*MUTED); pdf.cell(w - 6, 6, txt(lab.upper()))
    pdf.set_y(y + 24)

    h("Who did well, who needs another look", 13)
    pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*MUTED)
    for lab, cw in (("NAME", 60), ("DEPT", 24), ("SHOPS", 18), ("AVG", 18), ("BEST", 18), ("CRIT MISSES", 26), ("STATUS", 30)):
        pdf.cell(cw, 6, lab)
    pdf.ln(6)
    for r in report["people"]:
        pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*INK)
        pdf.cell(60, 6, txt(r["name"][:32])); pdf.cell(24, 6, txt(ind.dept_label(r["department"])[:14])); pdf.cell(18, 6, str(r["completed"]))
        pdf.cell(18, 6, f"{r['avg_score']}%" if r["avg_score"] is not None else "-"); pdf.cell(18, 6, f"{r['best']}%" if r["best"] is not None else "-"); pdf.cell(26, 6, str(r["critical_misses"]))
        pdf.set_text_color(*(RED if r["needs_training"] else (GREEN if r["completed"] else MUTED))); pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, "Needs training" if r["needs_training"] else ("On track" if r["completed"] else ("Unreachable" if r["unreachable"] else "Scheduled")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if report["criteria"]:
        h("What the whole store misses most", 13)
        for cr in report["criteria"][:8]:
            pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*INK)
            bar_w = 60; x = pdf.get_x(); y = pdf.get_y()
            pdf.set_fill_color(235, 235, 235); pdf.rect(x, y + 1.5, bar_w, 4, "F")
            pdf.set_fill_color(*(RED if cr["pass_pct"] < 60 else GOLD if cr["pass_pct"] < 85 else GREEN)); pdf.rect(x, y + 1.5, bar_w * cr["pass_pct"] / 100, 4, "F")
            pdf.set_xy(x + bar_w + 3, y); pdf.set_font("Helvetica", "B", 9); pdf.cell(12, 7, f"{cr['pass_pct']}%")
            pdf.set_font("Helvetica", "", 9); pdf.multi_cell(0, 7, txt(cr["text"] + ("  (critical)" if cr["critical"] else "")), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if report["coaching_themes"]:
        h("Coaching themes for the next meeting", 13)
        for t in report["coaching_themes"]:
            p(f"-  {t['text']}", 10)
        pdf.ln(3)

    done = [cr for cr in report["calls"] if cr["status"] == "completed"]
    if done:
        pdf.add_page()
        h("Every shop this month", 13)
        for cr in done:
            when = datetime.fromisoformat(cr["ended_at"]) if cr.get("ended_at") else None
            pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*INK)
            pdf.cell(0, 6, txt(f"{cr['target_name']}  |  {cr['script_title']}  |  {cr['score_pct']}%" if cr["score_pct"] is not None else f"{cr['target_name']}  |  {cr['script_title']}"), new_x="LMARGIN", new_y="NEXT")
            p((when.strftime("%b %d, %I:%M %p UTC") if when else "") + (f"  |  Shopper: {cr['persona_name']}" if cr.get("persona_name") else ""), 8.5, MUTED)
            if cr.get("summary"):
                p(cr["summary"], 9.5)
            if cr.get("critical_misses"):
                p("Critical misses: " + "; ".join(str(m) for m in cr["critical_misses"]), 9.5, RED, "B")
            for tip in (cr.get("coaching") or [])[:3]:
                p(f"-  {tip}", 9.5)
            pdf.ln(2)
    pdf.set_y(-14); pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, txt(f"Prepared by I'm On Social  |  imonsocial.com  |  generated {report['generated_at'][:10]}"), align="C")
    return bytes(pdf.output())


# ---------------------------------------------------------------- proposals + Stripe invoice
def _stripe():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
    return stripe


def serialize_proposal(p: dict) -> dict:
    return {"id": str(p["_id"]), "client_id": p.get("client_id"), "token": p.get("token"), "status": p.get("status"), "terms": p.get("terms") or {}, "client_name": p.get("client_name"),
            "contact_name": p.get("contact_name"), "contact_email": p.get("contact_email"), "created_at": p["created_at"].isoformat() if p.get("created_at") else None,
            "sent_at": p["sent_at"].isoformat() if p.get("sent_at") else None, "viewed_at": p["viewed_at"].isoformat() if p.get("viewed_at") else None,
            "signed_at": p["signed_at"].isoformat() if p.get("signed_at") else None, "signer": {k: v for k, v in (p.get("signer") or {}).items() if k != "ip"},
            "invoice": {k: v for k, v in (p.get("invoice") or {}).items()}, "sender_name": p.get("sender_name")}


def proposal_text(p: dict) -> list:
    t = p.get("terms") or {}
    price = float(t.get("price_monthly") or 0)
    per = terms_per_month(t)
    term = int(t.get("term_months") or 3)
    return [
        ("What you get", f"I'm On Social will mystery shop {p.get('client_name')} by phone every month: {per_month_text(per, ' and ')} calls, placed by our AI caller at random times during your business hours. "
                         "Every call is recorded, transcribed and graded against a phone skills scorecard and the scenario's success points, with written coaching for each person."),
        ("Your report", "You receive a live store report (no login needed) plus a monthly PDF: who did well, who needs training, what the whole team misses most, and every call with its recording, transcript and coaching."),
        ("Investment", f"${price:,.0f} per month, billed monthly by invoice (card or bank transfer) for an initial term of {term} months, then month to month. The first invoice is sent as soon as this proposal is signed and shops begin once it is paid."),
        ("Your part", "Provide the names, cell numbers and department of the people to shop, your business hours, and a few real products or services our caller can reference. You confirm you have the right to have your staff's business calls recorded and evaluated, and that you will handle any notice required in your state."),
        ("Cancel", f"After the initial {term} month term, cancel any time with 30 days notice. Recordings and reports stay available to you for 12 months."),
        ("Agreement", "By typing your name and signing below you agree to these terms on behalf of the store. This electronic signature is legally binding under the U.S. ESIGN Act."),
    ] + ([("Notes", t["notes"])] if t.get("notes") else [])


async def create_invoice_for(db, proposal: dict) -> dict:
    """First month's invoice, emailed by Stripe with a hosted payment page."""
    stripe = _stripe()
    t = proposal.get("terms") or {}
    amount_cents = int(round(float(t.get("price_monthly") or 0) * 100))
    if amount_cents <= 0:
        return {}
    client = await db.shop_clients.find_one({"_id": _oid(proposal["client_id"])}) or {}
    email = (proposal.get("signer") or {}).get("email") or proposal.get("contact_email") or client.get("contact_email")
    if not email:
        return {}
    cust_id = (client.get("billing") or {}).get("stripe_customer_id")
    if not cust_id:
        cust = await asyncio.to_thread(stripe.Customer.create, email=email, name=client.get("name") or proposal.get("client_name"), metadata={"shop_client_id": str(client.get("_id")), "managed_by": "imos_mystery_shop"})
        cust_id = cust.id
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"billing.stripe_customer_id": cust_id}})
    inv = await asyncio.to_thread(stripe.Invoice.create, customer=cust_id, collection_method="send_invoice", days_until_due=7, auto_advance=True,
                                  description=f"Mystery shop program for {client.get('name')}: {per_month_text(terms_per_month(t))} shops per month.",
                                  metadata={"proposal_id": str(proposal["_id"]), "shop_client_id": str(client.get("_id"))})
    await asyncio.to_thread(stripe.InvoiceItem.create, customer=cust_id, invoice=inv.id, amount=amount_cents, currency="usd", description="Phone mystery shopping, first month")
    inv = await asyncio.to_thread(stripe.Invoice.finalize_invoice, inv.id)
    try:
        inv = await asyncio.to_thread(stripe.Invoice.send_invoice, inv.id)
    except Exception as e:
        logger.warning(f"[MysteryShop] Stripe send_invoice failed (hosted link still works): {e}")
    info = {"stripe_invoice_id": inv.id, "hosted_invoice_url": inv.hosted_invoice_url, "invoice_pdf": getattr(inv, "invoice_pdf", None), "status": inv.status, "amount": amount_cents / 100, "sent_at": _now().isoformat()}
    await db.shop_proposals.update_one({"_id": proposal["_id"]}, {"$set": {"invoice": info, "updated_at": _now()}})
    await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"billing.last_invoice": info, "billing.status": "invoiced"}})
    return info


async def refresh_invoice(db, proposal: dict) -> dict:
    inv_id = (proposal.get("invoice") or {}).get("stripe_invoice_id")
    if not inv_id:
        return proposal.get("invoice") or {}
    try:
        inv = await asyncio.to_thread(_stripe().Invoice.retrieve, inv_id)
    except Exception as e:
        logger.debug(f"[MysteryShop] invoice refresh failed: {e}")
        return proposal.get("invoice") or {}
    info = {**(proposal.get("invoice") or {}), "status": inv.status, "hosted_invoice_url": inv.hosted_invoice_url, "paid_at": _now().isoformat() if inv.status == "paid" and not (proposal.get("invoice") or {}).get("paid_at") else (proposal.get("invoice") or {}).get("paid_at")}
    if info != proposal.get("invoice"):
        await db.shop_proposals.update_one({"_id": proposal["_id"]}, {"$set": {"invoice": info, **({"status": "paid"} if inv.status == "paid" else {})}})
        if inv.status == "paid":
            await db.shop_clients.update_one({"_id": _oid(proposal["client_id"])}, {"$set": {"billing.status": "paid", "billing.last_invoice": info}})
    return info


async def mark_invoice_paid(db, stripe_invoice_id: str):
    p = await db.shop_proposals.find_one({"invoice.stripe_invoice_id": stripe_invoice_id})
    if not p:
        return
    now = _now()
    await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"invoice.status": "paid", "invoice.paid_at": now.isoformat(), "status": "paid", "updated_at": now}})
    await db.shop_clients.update_one({"_id": _oid(p["client_id"])}, {"$set": {"billing.status": "paid", "billing.last_invoice.status": "paid", "billing.last_paid_at": now}})


# ---------------------------------------------------------------- proposal email + store kickoff
TIMEZONES = [("America/New_York", "Eastern"), ("America/Chicago", "Central"), ("America/Denver", "Mountain"), ("America/Phoenix", "Arizona"), ("America/Los_Angeles", "Pacific"), ("America/Anchorage", "Alaska"), ("Pacific/Honolulu", "Hawaii")]
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "imos-logo-email-168.png")


def logo_b64() -> str:
    try:
        import base64
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"[MysteryShop] logo missing: {e}")
        return ""


def _esc(v: str) -> str:
    return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def proposal_email(p: dict, sender_name: str, note: str, url: str, logo_src: str) -> tuple:
    """(subject, html) for the proposal email. logo_src is a data: URI for the in-app preview and cid:imos-logo when sending."""
    t = p.get("terms") or {}
    first = (p.get("contact_name") or "").strip().split(" ")[0] or "there"
    note_html = "".join(f'<p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{_esc(line)}</p>' for line in no_em_dash(note or "").strip().split("\n") if line.strip())
    logo = f'<img src="{logo_src}" alt="I\'m On Social" width="96" height="96" style="width:96px;height:96px;display:block;margin:0 auto" />' if logo_src else ""
    html = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f3ee">
  <div style="background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e6e1d6">
    <div style="text-align:center;padding:30px 20px 18px;border-bottom:1px solid #eee">{logo}
      <p style="margin:12px 0 0;font-size:11px;letter-spacing:2px;color:#C9A962;font-weight:800">I'M ON SOCIAL</p>
    </div>
    <div style="padding:28px 30px">
      <h1 style="font-size:22px;line-height:1.3;margin:0 0 16px;color:#111">Phone mystery shop proposal for {_esc(p.get('client_name'))}</h1>
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">Hi {_esc(first)},</p>
      {note_html}
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">Here is the proposal we talked about: <b>{per_month_text(terms_per_month(t), ' and ')}</b> mystery shops every month for <b>${float(t.get('price_monthly') or 0):,.0f}/month</b>, with recordings, grades and a store report you can open any time.</p>
      <p style="margin:26px 0;text-align:center"><a href="{url}" style="background:#C9A962;color:#111;text-decoration:none;font-weight:800;padding:14px 26px;border-radius:12px;display:inline-block;font-size:15px">Review and sign the proposal</a></p>
      <p style="font-size:13px;color:#666;line-height:1.6;margin:0 0 18px">Signing takes about a minute. Your first invoice arrives by email right after, and shops start once it is paid. Questions? Just reply to this email.</p>
      <p style="font-size:14px;color:#333;line-height:1.5;margin:0">{_esc(sender_name or "Forest")}<br><span style="color:#888">I'm On Social</span></p>
    </div>
  </div>
  <p style="text-align:center;margin:18px 0 0;color:#999;font-size:12px">I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065</p>
</div>"""
    return f"Mystery shop proposal for {p.get('client_name')}", html


async def ensure_kickoff_token(db, client: dict) -> str:
    tok = client.get("kickoff_token")
    if not tok:
        tok = uuid.uuid4().hex
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"kickoff_token": tok}})
        client["kickoff_token"] = tok
    return tok


def kickoff_url(client: dict) -> Optional[str]:
    return f"{scr._app_url()}/shop-kickoff/{client['kickoff_token']}" if client.get("kickoff_token") else None


async def notify_kickoff(db, client: dict, people_added: int, people_total: int):
    """Tell the iMOS admins who own this client that the store filled in its kickoff form."""
    from routers.push_notifications import send_push_to_user
    from routers.notifications_center import invalidate_feed
    uids = {client.get("created_by")}
    latest = await db.shop_proposals.find_one({"client_id": str(client["_id"])}, sort=[("created_at", -1)])
    if latest and latest.get("sender_id"):
        uids.add(latest["sender_id"])
    uids.discard(None)
    title = f"{client.get('name')} set up their store"
    msg = f"{people_total} people to shop ({people_added} new), hours {_hours(client)['start']} to {_hours(client)['end']}. Tap to review."
    link = f"/admin/mystery-shops/{client['_id']}?tab=people"
    now = _now()
    for uid in uids:
        await db.notifications.insert_one({"user_id": uid, "type": "shop_kickoff", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": now})
        invalidate_feed(uid)
        try:
            await send_push_to_user(uid, title, msg, link, "storefront")
        except Exception as e:
            logger.debug(f"[MysteryShop] kickoff push failed for {uid}: {e}")


# ---------------------------------------------------------------- quick shops (anyone, no client account) + texting the scorecard
DEMO_CLIENT_NAME = "Quick shops"
QUICK_NOTES = "Built-in bucket for quick shops: anyone you shop without a client account lands here. Never billed."


async def rename_legacy_quick_bucket(db):
    await db.shop_clients.update_many({"demo": True, "name": {"$ne": DEMO_CLIENT_NAME}}, {"$set": {"name": DEMO_CLIENT_NAME, "notes": QUICK_NOTES}})


async def ensure_demo_client(db, me: dict) -> dict:
    """Built-in, never-billed bucket so Forest can shop anyone on the spot without creating a client first."""
    await rename_legacy_quick_bucket(db)
    c = await db.shop_clients.find_one({"demo": True})
    if c:
        return c
    now = _now()
    doc = {"name": DEMO_CLIENT_NAME, "demo": True, "brand": "", "city": "", "state": "", "timezone": "America/Denver", "contact_name": "", "contact_email": "", "contact_phone": "", "contact_title": "",
           "plan": {"per_month": {}, "price_monthly": 0.0}, "hours": {"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4, 5, 6]}, "vehicles": [], "active": True, "industry": "automotive",
           "record_calls": True, "notes": QUICK_NOTES, "text_scorecards": True, "report_token": uuid.uuid4().hex, "billing": {},
           "created_by": str(me["_id"]), "created_at": now, "updated_at": now}
    res = await db.shop_clients.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def demo_shop(db, me: dict, name: str, phone: str, department: str, title: str, store_name: str, vehicle: str, script: Optional[dict], text_scorecard: bool, industry: Optional[str] = None) -> dict:
    c = await ensure_demo_client(db, me)
    industry = industry if industry in ind.INDUSTRIES else ind.industry_of_dept(department)
    cid, now = str(c["_id"]), _now()
    t = await db.shop_targets.find_one({"client_id": cid, "phone": phone})
    if t:
        await db.shop_targets.update_one({"_id": t["_id"]}, {"$set": {"name": name, "department": department, "title": title, "active": True, "updated_at": now}})
        t = {**t, "name": name, "department": department, "title": title}
    else:
        res = await db.shop_targets.insert_one({"client_id": cid, "name": name, "phone": phone, "department": department, "title": title, "notes": "Quick shop", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        t = await db.shop_targets.find_one({"_id": res.inserted_id})
    place = f"your {ind.get(industry)['business']}"
    persona_client = {**c, "industry": industry, "name": store_name or place, "vehicles": [vehicle] if vehicle else []}
    call = await create_shop_call(db, persona_client, t, now, created_by=str(me["_id"]), manual=True, script=script)
    if not call:
        return {"error": f"No {ind.dept_label(department)} challenges for {ind.get(industry)['label']} yet. Open the Challenge Library and let Jessi write the starters."}
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"demo": True, "notify_sms": bool(text_scorecard), "store_name": store_name or f"the {ind.get(industry)['business']}"}})
    ok = await place_shop_call(db, call)
    s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
    return {"ok": ok, "call": s, "client_id": cid}


def _short_criteria(ev: dict, passed: bool, n: int = 2) -> list:
    return [r.get("text", "").strip().rstrip(".") for r in (ev.get("results") or []) if bool(r.get("passed")) is passed and r.get("text")][:n]


def scorecard_sms(s: dict, ev: dict, url: str, course_line: str = "") -> str:
    first = (s.get("rep_name") or "").split(" ")[0] or "there"
    pct = ev.get("score_pct")
    lines = [f"Hey {first}, that practice call just now was from I'm On Social{'' if s.get('demo') else ' for ' + str(s.get('store_name') or 'your store')}. " + (f"You scored {int(pct)}%." if pct is not None else "Your scorecard is ready.")]
    good, fix = _short_criteria(ev, True), _short_criteria(ev, False)
    if good:
        lines.append("Nailed: " + ", ".join(good) + ".")
    if fix:
        lines.append("Work on: " + ", ".join(fix) + ".")
    if course_line:
        lines.append(course_line)
    lines.append(f"Full scorecard + recording: {url}")
    return no_em_dash("\n".join(lines))


async def _course_line(db, s: dict, pct) -> str:
    if not s.get("enrollment_id") or not ObjectId.is_valid(str(s["enrollment_id"])):
        return ""
    e = await db.course_enrollments.find_one({"_id": ObjectId(s["enrollment_id"])})
    course = await db.courses.find_one({"_id": ObjectId(e["course_id"])}) if e else None
    if not e or not course:
        return ""
    ids = course.get("challenge_ids") or []
    done = len([x for x in ids if ((e.get("progress") or {}).get(x) or {}).get("passed")])
    need = int(course.get("pass_pct") or 80)
    this_passed = pct is not None and pct >= need
    return f"{course.get('title')}: {done} of {len(ids)} passed." + ("" if this_passed else f" You need {need}% on this one, we will call again with it.")


async def after_graded(db, sid: str):
    """Grading just finished for a shop call: give it a public scorecard link, text the person if wanted, ping the admin who set it up."""
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)})
    if not s or s.get("kind") != "mystery_shop" or s.get("status") != "completed":
        return
    client = await db.shop_clients.find_one({"_id": _oid(s["client_id"])}) or {}
    ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])}) if s.get("evaluation_id") and ObjectId.is_valid(str(s["evaluation_id"])) else None
    if not ev:
        return
    token = s.get("score_token") or uuid.uuid4().hex
    if not s.get("score_token"):
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"score_token": token}})
    url = f"{scr._app_url()}/shop-score/{token}"
    want_sms = s.get("notify_sms") if s.get("notify_sms") is not None else bool(client.get("text_scorecards") or s.get("enrollment_id"))
    if want_sms and s.get("rep_phone") and not s.get("score_sms_sent_at"):
        from services.twilio_service import send_sms
        try:
            r = await send_sms(s["rep_phone"], scorecard_sms(s, ev, url, await _course_line(db, s, ev.get("score_pct"))), from_phone=(s.get("from_number") or await from_number(db, client)) or None)
            await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"score_sms_sent_at": _now(), "score_sms_sid": (r or {}).get("sid") or (r or {}).get("message_sid"), "score_sms_status": (r or {}).get("status") or "sent"}})
        except Exception as e:
            logger.warning(f"[MysteryShop] scorecard text failed for {sid}: {e}")
            await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"score_sms_status": "failed", "score_sms_error": str(e)[:200]}})
    if s.get("created_by") and not s.get("graded_notified_at"):
        from routers.push_notifications import send_push_to_user
        from routers.notifications_center import invalidate_feed
        first = (s.get("rep_name") or "").split(" ")[0] or "The rep"
        pct = ev.get("score_pct")
        title = f"{first} scored {int(pct)}% on the shop" if pct is not None else f"{first}'s shop call is graded"
        msg = (ev.get("summary") or "")[:160] + (" Scorecard texted to them." if want_sms else "")
        link = f"/admin/mystery-shops/{s['client_id']}?tab=calls"
        await db.notifications.insert_one({"user_id": s["created_by"], "type": "shop_graded", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": _now()})
        invalidate_feed(s["created_by"])
        try:
            await send_push_to_user(s["created_by"], title, msg, link, "storefront")
        except Exception as e:
            logger.debug(f"[MysteryShop] graded push failed: {e}")
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"graded_notified_at": _now()}})


def public_score(s: dict, ev: dict, client: dict) -> dict:
    first = (s.get("rep_name") or "").split(" ")[0]
    industry = s.get("industry") or ind.industry_of_dept(s.get("department"))
    return {"first_name": first, "name": s.get("rep_name"), "department": s.get("department"), "department_label": ind.dept_label(s.get("department")), "customer_noun": ind.get(industry)["customer"],
            "store_name": None if s.get("demo") else (s.get("store_name") or client.get("name")), "demo": bool(s.get("demo")),
            "challenge_title": s.get("script_title"), "persona_name": (s.get("persona") or {}).get("name"), "score_pct": ev.get("score_pct"), "scorecard_name": ev.get("scorecard_name"), "summary": ev.get("summary") or "",
            "wins": ev.get("wins") or [], "coaching": ev.get("coaching") or [], "customer_sentiment": ev.get("customer_sentiment") or "",
            "results": [{"text": r.get("text"), "passed": bool(r.get("passed")), "critical": bool(r.get("critical")), "evidence": r.get("evidence") or ""} for r in (ev.get("results") or [])],
            "recording_url": s.get("recording_url"), "recording_seconds": s.get("recording_seconds"), "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
            "adherence": {k: (ev.get("adherence") or {}).get(k) for k in ("score_pct", "hits", "misses", "summary")}}


# ---------------------------------------------------------------- AI challenge generator
VOICES = ("female", "male", "young", "older")


def _plain(v, n: int) -> str:
    return no_em_dash("; ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")).replace("{", "").replace("}", "")[:n].strip()


def normalize_draft(d: dict, department: str) -> Optional[dict]:
    """Coerce one model draft into the challenge shape the pool and the editor expect. Placeholders {vehicle}/{store} are allowed only in persona text."""
    body = d.get("body")
    if isinstance(body, list):
        body = "\n\n".join(str(x).strip() for x in body if str(x).strip())
    if not isinstance(d, dict) or not str(d.get("title") or "").strip() or not str(body or "").strip():
        return None
    persona = d.get("persona") if isinstance(d.get("persona"), dict) else {}
    ptxt = lambda v, n: no_em_dash(str(v or ""))[:n].strip()
    return {
        "title": _plain(d.get("title"), 120), "department": department, "runtime": _plain(d.get("runtime"), 40) or "3 to 5 min", "purpose": _plain(d.get("purpose"), 400), "body": no_em_dash(str(body))[:8000].strip(),
        "success_points": [_plain(p, 160) for p in (d.get("success_points") or []) if str(p).strip()][:12],
        "curveballs": [_plain(c, 160) for c in (d.get("curveballs") or []) if str(c).strip()][:4],
        "persona": {"name": _plain(persona.get("name"), 60) or "Jordan Lee", "voice": persona.get("voice") if persona.get("voice") in VOICES else "female", "summary": ptxt(persona.get("summary"), 400),
                    "goals": ptxt(persona.get("goals"), 200), "objections": [ptxt(o, 160) for o in (persona.get("objections") or []) if str(o).strip()][:6], "opening_line": ptxt(persona.get("opening_line"), 240)},
    }


async def generate_challenges(department: str, scenario: str, count: int = 1, client: Optional[dict] = None, industry: Optional[str] = None) -> list:
    """Forest describes a situation in plain words; Jessi drafts count distinct challenges (persona, opening line, what a great rep does, graded points, curveballs). Nothing is saved."""
    count = max(1, min(5, int(count or 1)))
    industry = industry if industry in ind.INDUSTRIES else ind.industry_of_dept(department)
    pack, d = ind.get(industry), ind.dept(department, industry)
    off = pack["offering"]
    store = f" The client is {client.get('name')}{' (' + client.get('brand') + ')' if client.get('brand') else ''}." if client else ""
    system = (f"You are Jessi, a {pack['trainer']} who writes mystery-shop challenges for {pack['label'].lower()} teams. A challenge is a realistic phone call the AI {pack['customer']} will act out against a real employee ({d['rep']}), then grade. "
              f"Department context: {d['brief']}.{store} "
              f"Write {count} DISTINCT challenge{'s' if count > 1 else ''} from the scenario below (vary the person, the wrinkle and the emotional tone; do not repeat the same caller twice). "
              f"Each challenge: title (short, starts with '{d['prefix']}'), runtime like '3 to 5 min', "
              "purpose (one or two sentences: what the situation is and what a great rep does), "
              f"body (a STRING, the coaching guide written TO THE REP in second person: 'Answer with the {pack['business']} and your name', 4 to 7 short paragraphs separated by blank lines, stage directions in [brackets]; this is what we grade the rep against, it is NOT the caller's lines; plain words, no curly braces), "
              f"success_points (5 to 8 graded rep behaviours, each 4 to 12 words starting with a verb, e.g. 'Confirms the exact {off['label']}'), curveballs (2 to 3 short second-person twists the caller may throw in, e.g. 'You only have two minutes'), "
              f"persona: name (first and last), voice one of female/male/young/older, summary (age, job, situation, mood; you MAY write {{offering}} for the {off['label']} they ask about and {{store}} for the {pack['business']} name), "
              "goals (one sentence), objections (2 to 4 things they push back with), opening_line (the exact first thing they say when the rep answers; may use {offering} and {store}). "
              "Sound like a real person on the phone, never corporate. Never use em dashes. "
              "Return JSON: {\"challenges\": [{title, runtime, purpose, body, success_points:[...], curveballs:[...], persona:{name, voice, summary, goals, objections:[...], opening_line}}]}")
    data = await scr._llm_json(system, f"SCENARIO ({pack['label']} / {d['label']}):\n{scenario.strip()[:3000]}", timeout=120)
    raw = data.get("challenges") if isinstance(data, dict) else None
    if isinstance(data, dict) and not raw and data.get("title"):
        raw = [data]
    drafts = [x for x in (normalize_draft(d, department) for d in (raw or [])) if x]
    if not drafts:
        raise ValueError("Jessi could not turn that into a challenge, try adding a little more detail")
    return drafts[:count]


async def seed_starters(db, me: dict, industry: str, department: Optional[str] = None, per_department: int = 2) -> list:
    """Jessi writes the starter challenges for an industry (or one department) from the pack briefs and saves them to the global library, flagged so the admin can review."""
    industry = industry if industry in ind.INDUSTRIES else ind.DEFAULT_INDUSTRY
    made = []
    for d in ind.departments(industry):
        if department and d["key"] != department:
            continue
        have = await db.scripts.count_documents({"pool": "mystery_shop", "shop_client_id": None, "department": d["key"], "active": {"$ne": False}})
        if have >= per_department:
            continue
        scenario = f"Write the everyday, most common versions of this call for a {ind.get(industry)['label'].lower()} team: {d['brief']}. Typical curveballs: {'; '.join(d.get('curveballs', [])[:3])}."
        drafts = await generate_challenges(d["key"], scenario, per_department - have, None, industry)
        for x in drafts:
            doc = {"kind": "phone", "pool": "mystery_shop", "industry": industry, "shop_client_id": None, "store_id": None, "slug": f"shop_starter_{ObjectId()}", "direction": "inbound", "category": d["label"], "active": True,
                   "generated_from": "starter", "created_by": str(me["_id"]), "created_at": _now(), "updated_at": _now(), **x}
            res = await db.scripts.insert_one(doc)
            doc["_id"] = res.inserted_id
            made.append(doc)
    return made
