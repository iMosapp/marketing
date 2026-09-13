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

from services import scripts as scr
from services import scorecards as sc
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

DEPARTMENTS = ["sales", "service"]
DEPT_LABEL = {"sales": "Sales", "service": "Service"}
DEPT_SCORECARD_TEMPLATE = {"sales": "phone_up", "service": "service_bdc"}
CALL_STATUSES_OPEN = ["scheduled", "dialing", "live", "grading"]
DEFAULT_HOURS = {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4, 5]}
DEFAULT_VEHICLES = {"sales": ["the used SUV you have listed online", "the pickup you have on your website"], "service": ["my SUV", "my truck"]}

CURVEBALLS = {
    "sales": ["You already have a written quote from a competing store", "You only have 2 minutes, you are on a work break", "You want the payment over the phone before you will consider coming in",
              "You are 45 minutes away and worried about wasting the drive", "Your spouse makes the final decision and is not with you", "You ask if the price online is negotiable"],
    "service": ["You need a loaner or a ride because you work during the day", "You had a bad experience at another store and are skeptical", "You want to know the exact price before booking",
                "You can only come in on Saturday", "The warning light just came on and you are nervous about driving it", "You ask whether the work is covered under warranty"],
}

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
            {"$setOnInsert": {**tpl, "kind": "phone", "pool": "mystery_shop", "store_id": None, "shop_client_id": None, "direction": "inbound", "active": True, "created_at": _now(), "updated_at": _now()}}, upsert=True)
        n += 1 if res.upserted_id else 0
    return n


# ---------------------------------------------------------------- clients + people
def serialize_client(c: dict, extra: Optional[dict] = None) -> dict:
    out = {"id": str(c["_id"]), "name": c.get("name", ""), "brand": c.get("brand", ""), "city": c.get("city", ""), "state": c.get("state", ""), "timezone": c.get("timezone") or "America/Denver",
           "contact_name": c.get("contact_name", ""), "contact_email": c.get("contact_email", ""), "contact_phone": c.get("contact_phone", ""), "contact_title": c.get("contact_title", ""),
           "plan": {"sales_per_month": int((c.get("plan") or {}).get("sales_per_month") or 0), "service_per_month": int((c.get("plan") or {}).get("service_per_month") or 0), "price_monthly": float((c.get("plan") or {}).get("price_monthly") or 0)},
           "hours": _hours(c), "vehicles": c.get("vehicles") or [], "active": c.get("active", True), "record_calls": c.get("record_calls", True), "notes": c.get("notes", ""),
           "from_number": c.get("from_number") or "", "report_token": c.get("report_token"), "scorecards": c.get("scorecards") or {}, "billing": c.get("billing") or {},
           "created_at": c.get("created_at").isoformat() if c.get("created_at") else None}
    if extra:
        out.update(extra)
    return out


def serialize_target(t: dict, extra: Optional[dict] = None) -> dict:
    out = {"id": str(t["_id"]), "client_id": t.get("client_id"), "name": t.get("name", ""), "phone": t.get("phone", ""), "department": t.get("department", "sales"), "title": t.get("title", ""),
           "notes": t.get("notes", ""), "active": t.get("active", True), "challenge_history": t.get("challenge_history") or [], "created_at": t.get("created_at").isoformat() if t.get("created_at") else None}
    if extra:
        out.update(extra)
    return out


def serialize_call(s: dict) -> dict:
    return {"id": str(s["_id"]), "client_id": s.get("client_id"), "target_id": s.get("target_id"), "target_name": s.get("rep_name"), "department": s.get("department"), "status": s.get("status"),
            "outcome": s.get("outcome"), "fail_reason": s.get("fail_reason"), "script_id": s.get("script_id"), "script_title": s.get("script_title"), "persona_name": (s.get("persona") or {}).get("name"),
            "curveballs": s.get("curveballs") or [], "scheduled_for": s["scheduled_for"].isoformat() if s.get("scheduled_for") else None, "attempts": s.get("attempts", 0),
            "started_at": s["started_at"].isoformat() if s.get("started_at") else None, "ended_at": s["ended_at"].isoformat() if s.get("ended_at") else None,
            "score_pct": s.get("score_pct"), "adherence_pct": s.get("adherence_pct"), "evaluation_id": s.get("evaluation_id"), "recording_url": s.get("recording_url"),
            "recording_seconds": s.get("recording_seconds"), "turns": len(s.get("turns") or []), "manual": bool(s.get("manual"))}


# ---------------------------------------------------------------- challenge rotation
def fill_persona(persona: dict, client: dict, department: str) -> dict:
    pool = [v for v in (client.get("vehicles") or []) if str(v).strip()] or DEFAULT_VEHICLES[department]
    vehicle = random.choice(pool)
    if department == "sales" and not vehicle.lower().startswith(("the ", "a ", "an ", "that ")):
        vehicle = f"the {vehicle}"
    elif department == "service" and not vehicle.lower().startswith(("my ", "our ")):
        vehicle = f"my {vehicle}"
    def sub(v):
        if isinstance(v, list):
            return [sub(x) for x in v]
        return str(v).replace("{vehicle}", vehicle).replace("{store}", client.get("name") or "the store") if isinstance(v, str) else v
    return {k: sub(v) for k, v in (persona or {}).items()} | {"vehicle": vehicle}


async def challenge_pool(db, client_id: Optional[str], department: Optional[str] = None) -> list:
    await ensure_challenges(db)
    q = {"kind": "phone", "pool": "mystery_shop", "active": {"$ne": False}, "$or": [{"shop_client_id": None}, {"shop_client_id": client_id}]}
    if department:
        q["department"] = department
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
    curve = random.sample(CURVEBALLS.get(dept, []), k=random.choice([0, 1, 1, 2]))
    now = _now()
    doc = {"kind": "mystery_shop", "mode": "phone", "status": "scheduled", "user_id": None, "client_id": str(client["_id"]), "target_id": str(target["_id"]),
           "rep_name": target.get("name") or "", "rep_phone": target.get("phone"), "department": dept, "store_id": None, "store_name": client.get("name") or "the store",
           "script_id": str(script["_id"]), "script_title": script.get("title"), "script_slug": script.get("slug"), "direction": "inbound", "persona": persona, "curveballs": curve,
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
    created = {"sales": 0, "service": 0}
    for dept in DEPARTMENTS:
        quota = int((client.get("plan") or {}).get(f"{dept}_per_month") or 0)
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
def _from_number(client: dict) -> str:
    return client.get("from_number") or os.environ.get("MYSTERY_SHOP_FROM_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER", "")


async def place_shop_call(db, call: dict) -> bool:
    from services.lead_call_engine import _twilio_client
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])})
    tw = _twilio_client()
    if not client or tw is None or not _from_number(client) or not call.get("rep_phone"):
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "failed", "outcome": "not_configured", "fail_reason": "Calling is not set up (no caller number)", "updated_at": _now()}})
        return False
    sid, token = str(call["_id"]), call["token"]
    base = f"{scr._app_url()}/api/scripts/roleplay"
    now = _now()
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "dialing", "started_at": now, "last_attempt_at": now, "updated_at": now}, "$inc": {"attempts": 1}})
    try:
        tw_call = await asyncio.to_thread(
            tw.calls.create, to=call["rep_phone"], from_=_from_number(client), url=f"{base}/twiml/{sid}?t={token}", method="POST",
            status_callback=f"{base}/status/{sid}?t={token}", status_callback_event=["answered", "completed"], status_callback_method="POST",
            record=bool(client.get("record_calls", True)), recording_status_callback=f"{base}/recording/{sid}?t={token}", recording_status_callback_event=["completed"],
            machine_detection="Enable", machine_detection_timeout=12, timeout=25)
    except Exception as e:
        logger.warning(f"[MysteryShop] could not place call {sid}: {e}")
        await record_outcome(db, {**call, "attempts": call.get("attempts", 0) + 1}, "failed", "The call could not be placed")
        return False
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"call_sid": tw_call.sid, "call_status": "queued"}})
    return True


OUTCOME_LABEL = {"voicemail": "Went to voicemail", "no-answer": "No answer", "busy": "Line was busy", "failed": "The call could not be placed", "canceled": "The call was cancelled", "hung_up": "Hung up before the shop started"}


async def record_outcome(db, call: dict, outcome: str, reason: Optional[str] = None):
    """A shop attempt that never became a conversation: retry later inside business hours, or give up after max attempts."""
    client = await db.shop_clients.find_one({"_id": _oid(call["client_id"])}) or {}
    attempts = int(call.get("attempts") or 0)
    label = reason or OUTCOME_LABEL.get(outcome, outcome)
    now = _now()
    history = {"at": now, "outcome": outcome, "call_sid": call.get("call_sid")}
    if attempts < int(call.get("max_attempts") or 3) and client:
        when = next_slot(client, now, min_gap_minutes=random.randint(90, 240))
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": when, "outcome": outcome, "fail_reason": f"{label}, trying again", "call_sid": None, "call_status": None, "turns": [], "updated_at": now},
                                                                   "$push": {"attempt_history": history}})
    else:
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "unreachable", "outcome": outcome, "fail_reason": f"{label} ({attempts} tries)", "ended_at": now, "updated_at": now}, "$push": {"attempt_history": history}})


async def run_due_calls(db, limit: int = 3) -> int:
    """Scheduler tick: dial shops whose time has come (inside the client's hours), a few at a time."""
    now = _now()
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
            n += made["sales"] + made["service"]
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
    body = sc.template_body(DEPT_SCORECARD_TEMPLATE[dept])
    if not body:
        return None
    return {"_id": None, "name": body["name"], "department": body["department"], "criteria": sc.normalize_criteria(body["criteria"]), "alert_on_critical": False}


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
    for d in DEPARTMENTS:
        dc = [c for c in done if c.get("department") == d]
        by_dept[d] = {"planned": int((client.get("plan") or {}).get(f"{d}_per_month") or 0), "scheduled": len([c for c in calls if c.get("department") == d and c.get("status") in CALL_STATUSES_OPEN]),
                      "completed": len(dc), "unreachable": len([c for c in calls if c.get("department") == d and c.get("status") == "unreachable"]), "avg_score": _pct([c.get("score_pct") for c in dc])}
    call_rows = []
    for c in sorted(calls, key=lambda x: x.get("ended_at") or x.get("scheduled_for") or _now(), reverse=True):
        ev = evals.get(str(c.get("evaluation_id"))) if c.get("evaluation_id") else None
        call_rows.append({**serialize_call(c), "summary": (ev or {}).get("summary"), "critical_misses": (ev or {}).get("critical_misses") or [], "coaching": (ev or {}).get("coaching") or [],
                          "wins": (ev or {}).get("wins") or [], "adherence": (ev or {}).get("adherence") or {}, "results": (ev or {}).get("results") or [], "transcript": (ev or {}).get("transcript") or scr.transcript_text(c),
                          "customer_sentiment": (ev or {}).get("customer_sentiment")})
    themes = {}
    for ev in evals.values():
        for tip in (ev.get("coaching") or [])[:3]:
            key = no_em_dash(str(tip)).strip().rstrip(".")
            themes[key] = themes.get(key, 0) + 1
    label = start.astimezone(tz).strftime("%B %Y")
    return {"client": {"id": cid, "name": client.get("name"), "brand": client.get("brand", ""), "city": client.get("city", ""), "state": client.get("state", ""), "contact_name": client.get("contact_name", "")},
            "month": start.astimezone(tz).strftime("%Y-%m"), "month_label": label, "generated_at": _now().isoformat(),
            "summary": {"completed": len(done), "planned": by_dept["sales"]["planned"] + by_dept["service"]["planned"], "scheduled": len([c for c in calls if c.get("status") in CALL_STATUSES_OPEN]),
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
        pdf.cell(60, 6, txt(r["name"][:32])); pdf.cell(24, 6, DEPT_LABEL.get(r["department"], r["department"] or "")); pdf.cell(18, 6, str(r["completed"]))
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
    sales, service = int(t.get("sales_per_month") or 0), int(t.get("service_per_month") or 0)
    term = int(t.get("term_months") or 3)
    return [
        ("What you get", f"I'm On Social will mystery shop {p.get('client_name')} by phone every month: {sales} sales calls and {service} service calls, placed by our AI shopper at random times during your business hours. "
                         "Every call is recorded, transcribed and graded against a phone skills scorecard and the scenario's success points, with written coaching for each person."),
        ("Your report", "You receive a live store report (no login needed) plus a monthly PDF: who did well, who needs training, what the whole team misses most, and every call with its recording, transcript and coaching."),
        ("Investment", f"${price:,.0f} per month, billed monthly by invoice (card or bank transfer) for an initial term of {term} months, then month to month. The first invoice is sent as soon as this proposal is signed and shops begin once it is paid."),
        ("Your part", "Provide the names, cell numbers and department of the people to shop, your store hours, and a few vehicles to reference. You confirm you have the right to have your staff's business calls recorded and evaluated, and that you will handle any notice required in your state."),
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
                                  description=f"Mystery shop program for {client.get('name')}: {int(t.get('sales_per_month') or 0)} sales + {int(t.get('service_per_month') or 0)} service shops per month.",
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
