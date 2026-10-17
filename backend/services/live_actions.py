"""Live Jessi actions beyond texting: call, dictate a note, tag, mark sold, finish/snooze reminders, update facts,
book appointments, enroll in campaigns, send the rep's card or review link. Each tool returns (spoken result, pending, open target).
Anything that reaches the customer or cannot be undone (sold, appointment, campaign, card/review text) comes back as PENDING
and runs on the rep's yes; quiet edits (note, tag, facts, reminders) happen at once."""
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services import live_voice as lv

logger = logging.getLogger(__name__)

OPEN_TASK = {"$in": ["pending", "snoozed", None]}
FACT_FIELDS = {"birthday", "anniversary", "email", "phone", "vehicle_interest", "vehicle", "occupation", "employer", "address", "personal"}
PERSONAL_KEYS = ("family", "spouse", "kids", "hobby", "pets", "work", "other")


def _first(c: dict) -> str:
    return c.get("first_name") or lv._first_last(c)


def _err(e) -> str:
    return str(getattr(e, "detail", None) or e)[:160]


async def _person(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    return await lv._resolve(db, str(user["_id"]), args.get("name") or "", focus, args.get("hint") or "", live)


def _parse_local(value: str, tz) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except Exception:
        return None
    return (d.replace(tzinfo=tz) if d.tzinfo is None else d).astimezone(tz)


def _spoken(d: datetime) -> str:
    day = d.strftime("%A, %B %-d")
    return f"{day} at {d.strftime('%-I:%M %p')}" if d.hour or d.minute else day


def _same_tag(a: str, b: str) -> bool:
    na, nb = lv._norm(a).rstrip("s"), lv._norm(b).rstrip("s")
    return bool(na) and (na == nb or lv._sim(na, nb) >= 0.88)


# ── call ──────────────────────────────────────────────────────────────────────
async def call_person(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None
    first = _first(contact)
    if not contact.get("phone"):
        return f"{first} has no phone number on file, so I cannot call them.", lv._open_target("contact", contact)
    if not (user.get("phone") or "").strip():
        return "I need your cell number to ring you first. Add it under My Profile, then ask me again.", None
    if not (user.get("twilio_number") or user.get("mvpline_number")):
        return "You do not have a business number assigned yet, so I cannot place calls for you. Ask your manager to assign one.", None
    uid, cid = str(user["_id"]), str(contact["_id"])
    conv = await db.conversations.find_one({"user_id": uid, "contact_id": cid}, {"_id": 1})
    task = await db.tasks.find_one({"user_id": uid, "contact_id": cid, "status": OPEN_TASK, "completed": {"$ne": True}}, sort=[("due_date", 1)])
    from routers.twilio_webhooks import place_click_to_call
    try:
        await place_click_to_call(uid, contact["phone"], cid, str(conv["_id"]) if conv else "", str(task["_id"]) if task else "")
    except Exception as e:
        return f"I could not start that call: {_err(e)}", lv._open_target("contact", contact)
    tail = f" Once you connect, I will mark your reminder \"{task.get('title')}\" done." if task else ""
    return lv._with_note(f"Calling {first} now. Your phone will ring from your business number; answer and press 1 to connect.{tail} I will be right here when you are done.", contact), lv._open_target("contact", contact)


# ── note ──────────────────────────────────────────────────────────────────────
async def add_note(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None
    text = (args.get("text") or "").strip()
    if not text:
        return f"What should the note on {_first(contact)} say?", None
    from routers.voice_notes import create_text_memo
    await create_text_memo(db, str(user["_id"]), str(contact["_id"]), text, source="jessi")
    return lv._with_note(f"Saved on {_first(contact)}: \"{text}\". I will pull anything useful onto their profile.", contact), lv._open_target("contact", contact)


# ── tags ──────────────────────────────────────────────────────────────────────
async def tag_person(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None
    tag = re.sub(r"\s+", " ", (args.get("tag") or "").strip(" .,\"'"))
    if not tag:
        return f"Which tag should I put on {_first(contact)}?", None
    uid, cid = str(user["_id"]), str(contact["_id"])
    have = [t for t in contact.get("tags") or [] if isinstance(t, str)]
    if (args.get("action") or "add") == "remove":
        hit = next((t for t in have if _same_tag(t, tag)), None)
        if not hit:
            return f"{lv._first_last(contact)} is not tagged {tag}. Their tags are {', '.join(have) if have else 'none'}.", lv._open_target("contact", contact)
        from routers.tags import remove_tag_from_contacts
        await remove_tag_from_contacts(uid, {"tag_name": hit, "contact_ids": [cid]})
        return lv._with_note(f"Took {hit} off {lv._first_last(contact)}" + (f", the record at {lv._fmt_phone(contact['phone'])}." if contact.get("phone") else ".") + await _tag_reach(db, user, hit), contact), lv._open_target("contact", contact)
    already = next((t for t in have if _same_tag(t, tag)), None)
    if already:
        return f"{lv._first_last(contact)}" + (f" at {lv._fmt_phone(contact['phone'])}" if contact.get("phone") else "") + f" is already tagged {already}." + await _tag_reach(db, user, already), lv._open_target("contact", contact)
    from routers.tags import get_tags, assign_tag_to_contacts
    known = [t.get("name") for t in await get_tags(uid) if t.get("name")]
    final = next((k for k in known if _same_tag(k, tag)), None)
    is_new = final is None
    final = final or tag
    started = lv._now()
    await assign_tag_to_contacts(uid, {"tag_name": final, "contact_ids": [cid], "auto_create_tag": True})
    enrolled = await db.campaign_enrollments.find_one({"contact_id": cid, "status": "active", "enrolled_at": {"$gte": started - timedelta(seconds=5)}})
    camp = ""
    if enrolled:
        c = await db.campaigns.find_one({"_id": ObjectId(enrolled["campaign_id"])}, {"name": 1}) if ObjectId.is_valid(str(enrolled.get("campaign_id"))) else None
        camp = f" That puts them on the {c.get('name')} campaign." if c else " That started a campaign for them."
    who = lv._first_last(contact) + (f", the record at {lv._fmt_phone(contact['phone'])}" if contact.get("phone") else ", the record with no phone on file")
    return lv._with_note(f"Tagged {who} as {final}." + (" New tag, it is in your list now." if is_new else "") + await _tag_reach(db, user, final) + camp, contact), lv._open_target("contact", contact)


async def _tag_reach(db, user: dict, tag: str) -> str:
    """How many of the rep's own contacts carry the tag, and the store-wide number the Tags screen shows when it differs."""
    from routers.tags import get_tag_scope, _count_scope_user_ids
    uid = str(user["_id"])
    mine = await db.contacts.count_documents({"user_id": uid, "tags": tag})
    _org, store_id, _role, _adm = await get_tag_scope(uid)
    scope = await _count_scope_user_ids(db, uid, store_id)
    store_n = await db.contacts.count_documents({"user_id": {"$in": scope}, "tags": tag}) if len(scope) > 1 else mine
    line = f" {tag} is now on {mine} of your contacts"
    if store_n > mine:
        line += f", {store_n} across the store counting your teammates' customers"
    return line + "."


# ── sold ──────────────────────────────────────────────────────────────────────
async def mark_sold(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None, None
    first = _first(contact)
    title = (args.get("title") or "").strip()
    if not title:
        return f"What did {first} buy? Give me the year, make and model.", None, lv._open_target("contact", contact)
    from services.sales import ymd
    tz = await lv._tz(user)
    today = lv._now().astimezone(tz).strftime("%Y-%m-%d")
    day = ymd(args.get("date_iso")) or today
    spoken_day = "today" if day == today else datetime.strptime(day, "%Y-%m-%d").strftime("%B %-d")
    category = args.get("category") if args.get("category") in ("vehicle", "other", "service", "product") else "vehicle"
    pending = {"type": "sold", "contact_id": str(contact["_id"]), "name": lv._first_last(contact), "title": title, "date": day, "category": category,
               "notes": (args.get("notes") or "").strip(), "content": f"mark {lv._first_last(contact)} sold: {title}, {spoken_day}", "at": lv._now().isoformat()}
    say = f"Mark {first} sold: {title}, {spoken_day}" + (f", {pending['notes']}" if pending["notes"] else "") + ". That records the sale, tags them Sold and starts the congrats card, review request and sold follow-ups. Say yes to do it, or no to hold off."
    return lv._with_note(say, contact), pending, lv._open_target("contact", contact)


async def sold_now(db, user: dict, pending: dict):
    from routers.contacts import set_date_sold
    try:
        r = await set_date_sold(str(user["_id"]), pending["contact_id"], {"date": pending["date"], "title": pending["title"], "category": pending.get("category") or "vehicle", "notes": pending.get("notes") or "", "source": "jessi"})
    except Exception as e:
        return f"That did not save: {_err(e)}", None
    n = r.get("sold_count") or 1
    kinds = {"first": "their first purchase with you", "repeat": f"purchase number {n}, a repeat buyer", "same": "I updated the existing sold record"}
    return f"Done. {pending['name']} is marked sold: {pending['title']}, {kinds.get(r.get('sale'), 'recorded')}. The sold workflow is running.", {"kind": "contact", "id": pending["contact_id"], "name": pending["name"], "first": pending["name"].split(" ")[0]}


# ── reminders: done / snooze ──────────────────────────────────────────────────
def _task_words(t: dict) -> str:
    return f"{t.get('title') or ''} {t.get('description') or ''}".lower()


async def finish_task(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    uid = str(user["_id"])
    contact = None
    if (args.get("name") or "").strip() or focus:
        contact, err = await _person(db, user, args, focus, live)
        if err:
            return err, None
    q = {"user_id": uid, "status": OPEN_TASK, "completed": {"$ne": True}}
    if contact:
        q["contact_id"] = str(contact["_id"])
    rows = await db.tasks.find(q).sort("due_date", 1).limit(20).to_list(20)
    if not rows and live and live.get("last_task_id"):
        t = await db.tasks.find_one({"_id": ObjectId(live["last_task_id"])}) if ObjectId.is_valid(str(live["last_task_id"])) else None
        rows = [t] if t else []
    if not rows:
        who = f" for {_first(contact)}" if contact else ""
        return f"There is no open reminder{who}.", lv._open_target("contact", contact) if contact else lv._open_target("tasks")
    which = (args.get("which") or "").lower()
    words = [w for w in re.findall(r"[a-z0-9]+", which) if len(w) > 2 and w not in lv.STOP_WORDS]
    task = next((t for t in rows if words and any(w in _task_words(t) for w in words)), None)
    if not task and live and live.get("last_task_id") in {str(t["_id"]) for t in rows}:
        task = next(t for t in rows if str(t["_id"]) == live["last_task_id"])
    if not task and len(rows) == 1:
        task = rows[0]
    if not task:
        names = "; ".join(f"{t.get('title')}" + (f" for {t.get('contact_name')}" if t.get("contact_name") and not contact else "") for t in rows[:3])
        who = f"{_first(contact)} has" if contact else "Your next reminders are"
        return f"Which one? {who} {names}. Say a few words from it" + ("" if contact else " or the customer's name") + ".", lv._open_target("contact", contact) if contact else lv._open_target("tasks")
    from routers.tasks import update_task
    action = "snooze" if args.get("action") == "snooze" else "complete"
    label = task.get("title") or "that reminder"
    who = f" for {task.get('contact_name')}" if task.get("contact_name") else (f" for {_first(contact)}" if contact else "")
    try:
        if action == "snooze":
            tz = await lv._tz(user)
            until = _parse_local(args.get("until_iso"), tz) or (lv._now().astimezone(tz) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            await update_task(uid, str(task["_id"]), {"action": "snooze", "snooze_until": until.astimezone(timezone.utc).isoformat()})
            return f"Snoozed \"{label}\"{who} until {_spoken(until)}.", lv._open_target("task", task=task)
        await update_task(uid, str(task["_id"]), {"action": "complete", "completed_via": "jessi"})
    except Exception as e:
        return f"I could not update that reminder: {_err(e)}", lv._open_target("task", task=task)
    left = await db.tasks.count_documents({**q, "_id": {"$ne": task["_id"]}}) if contact else 0
    more = f" {_first(contact)} still has {left} open." if contact and left else ""
    return f"Done. \"{label}\"{who} is complete.{more}", lv._open_target("task", task=task)


# ── contact facts ─────────────────────────────────────────────────────────────
def _date_value(value: str) -> Optional[datetime]:
    v = (value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", v) or None
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})$", v)
    if m:
        try:
            return datetime(1900, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


async def update_contact(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None
    first, uid, cid = _first(contact), str(user["_id"]), str(contact["_id"])
    field = (args.get("field") or "").strip().lower()
    value = str(args.get("value") or "").strip()
    if field not in FACT_FIELDS or not value:
        return f"What should I update on {first}? I can set their birthday, anniversary, email, phone, the vehicle they want or own, job, employer, address, or a personal detail.", lv._open_target("contact", contact)
    open_c = lv._open_target("contact", contact)
    if field in ("birthday", "anniversary"):
        d = _date_value(value)
        if not d:
            return "I did not catch the date. Say it like March 3rd, 1984, or just March 3rd.", open_c
        if field == "birthday":
            from routers.contacts import set_contact_birthday
            await set_contact_birthday(uid, cid, {"birthday": d.strftime("%Y-%m-%d")})
        else:
            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"anniversary": d, "updated_at": lv._now()}})
        when = d.strftime("%B %-d") + (f", {d.year}" if d.year != 1900 else "")
        return lv._with_note(f"{first}'s {field} is set to {when}." + (" Their cards will go out on it automatically." if field == "birthday" else ""), contact), open_c
    if field == "phone":
        from services.twilio_service import normalize_phone
        p = normalize_phone(value)
        if not p or len(re.sub(r"\D", "", p)) < 10:
            return "That phone number did not come through. Say all ten digits.", open_c
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"phone": p, "updated_at": lv._now()}})
        return f"{first}'s number is now {lv._fmt_phone(p)}.", open_c
    if field == "email":
        e = value.lower().replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", e):
            return "That email did not come through clean. Spell it for me.", open_c
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"email": e, "updated_at": lv._now()}})
        return f"{first}'s email is now {e}.", open_c
    if field == "personal":
        from routers.contacts import update_personal_details
        key = (args.get("key") or "other").strip().lower()
        key = key if key in PERSONAL_KEYS else "other"
        cur = (contact.get("personal_details") or {}) if isinstance(contact.get("personal_details"), dict) else {}
        old = str(cur.get(key) or "").strip()
        merged = value if not old or value.lower() in old.lower() else f"{old}; {value}"
        await update_personal_details(uid, cid, {"personal_details": {key: merged}})
        return lv._with_note(f"Noted on {first}: {value}.", contact), open_c
    label = {"vehicle_interest": "is now looking at", "vehicle": "now drives", "occupation": "works as", "employer": "works at", "address": "address is now"}[field]
    await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {field if field != "address" else "address_street": value, "updated_at": lv._now()}})
    return lv._with_note(f"Got it. {first} {label} {value}.", contact), open_c


# ── appointments ──────────────────────────────────────────────────────────────
async def book_appointment(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None, None
    first = _first(contact)
    tz = await lv._tz(user)
    start = _parse_local(args.get("when_iso"), tz)
    if not start:
        return f"When should I put {first} down for? Give me a day and a time.", None, lv._open_target("contact", contact)
    try:
        minutes = max(15, min(240, int(args.get("duration_min") or 30)))
    except (TypeError, ValueError):
        minutes = 30
    title = (args.get("title") or "").strip() or f"Appointment with {lv._first_last(contact)}"
    location = (args.get("location") or "").strip()
    pending = {"type": "appointment", "contact_id": str(contact["_id"]), "name": lv._first_last(contact), "title": title, "start": start.isoformat(), "minutes": minutes,
               "location": location, "content": f"{title}, {_spoken(start)}", "at": lv._now().isoformat()}
    say = f"{title}, {_spoken(start)}, {minutes} minutes" + (f", at {location}" if location else "") + ". I will put it on your calendar and set a reminder. Say yes to book it, and I can text them the confirmation after."
    return lv._with_note(say, contact), pending, lv._open_target("contact", contact)


async def appointment_now(db, user: dict, pending: dict):
    from routers.calendar import create_appointment_from_ai
    from routers.tasks import create_task
    uid = str(user["_id"])
    start = datetime.fromisoformat(pending["start"])
    end = start + timedelta(minutes=int(pending.get("minutes") or 30))
    contact = await db.contacts.find_one({"_id": ObjectId(pending["contact_id"])}, {"phone": 1, "first_name": 1, "last_name": 1})
    try:
        appt = await create_appointment_from_ai(uid, {"contact_id": pending["contact_id"], "contact_name": pending["name"], "contact_phone": (contact or {}).get("phone"),
                                                      "title": pending["title"], "start_time": start.isoformat(), "end_time": end.isoformat(), "location": pending.get("location") or "", "notes": "Booked with Jessi"})
        task = await create_task(uid, {"title": pending["title"], "description": (f"At {pending['location']}. " if pending.get("location") else "") + "Booked with Jessi", "contact_id": pending["contact_id"],
                                       "type": "appointment", "appointment_type": "appointment", "action_type": "manual", "due_date": start.astimezone(timezone.utc).isoformat(), "has_time": True, "priority": "high"})
    except Exception as e:
        return f"That did not book: {_err(e)}", None
    synced = (appt or {}).get("google_calendar") or {}
    cal = " It is on your Google Calendar too." if synced.get("synced") else ""
    first = pending["name"].split(" ")[0]
    return f"Booked. {pending['title']}, {_spoken(start)}.{cal} Want me to text {first} the confirmation?", lv._open_target("task", task=task) if task else {"kind": "contact", "id": pending["contact_id"], "name": pending["name"], "first": first}


# ── campaigns ─────────────────────────────────────────────────────────────────
async def _match_campaign(user: dict, spoken: str) -> tuple:
    """(campaign row, rows): the active campaign the rep named, fuzzy on its words; None when unclear (rows lets the caller list them)."""
    from routers.campaigns import list_campaigns_simple
    rows = [c for c in ((await list_campaigns_simple(str(user["_id"]))).get("campaigns") or []) if c.get("active")]
    words = [w for w in re.findall(r"[a-z0-9]+", (spoken or "").strip().lower()) if len(w) > 2 and w not in ("campaign", "plan", "the", "and", "for")]
    scored = sorted(((max([lv._sim(w, x) for w in words for x in re.findall(r"[a-z0-9]+", (c.get("name") or "").lower())] or [0]), sum(1 for w in words if w in (c.get("name") or "").lower()), c) for c in rows), key=lambda x: (-x[1], -x[0]))
    best = scored[0] if scored and words and (scored[0][1] or scored[0][0] >= 0.85) else None
    return (best[2] if best else None), rows


NO_CAMPAIGNS = "You do not have any active campaigns yet. Set one up under Campaigns and I can enroll people from here."


async def enroll_campaign(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None, None
    first, cid = _first(contact), str(contact["_id"])
    camp, rows = await _match_campaign(user, args.get("campaign") or "")
    if not rows:
        return NO_CAMPAIGNS, None, lv._open_target("contact", contact)
    if not camp:
        names = "; ".join(c["name"] for c in rows[:5])
        return f"Which campaign for {first}? You have {names}.", None, lv._open_target("contact", contact)
    if await db.campaign_enrollments.find_one({"campaign_id": camp["campaign_id"], "contact_id": cid, "status": "active"}):
        return f"{first} is already on {camp['name']}.", None, lv._open_target("contact", contact)
    full = await db.campaigns.find_one({"_id": ObjectId(camp["campaign_id"])}, {"steps": 1, "ai_enabled": 1}) if ObjectId.is_valid(str(camp["campaign_id"])) else {}
    steps = len((full or {}).get("steps") or [])
    detail = (f", {steps} touch{'es' if steps != 1 else ''}" if steps else "") + (", Jessi personalizes each text" if (full or {}).get("ai_enabled") else "")
    pending = {"type": "enroll", "contact_id": cid, "name": lv._first_last(contact), "campaign_id": camp["campaign_id"], "campaign": camp["name"], "content": f"enroll {lv._first_last(contact)} in {camp['name']}", "at": lv._now().isoformat()}
    return lv._with_note(f"Put {first} on {camp['name']}{detail}? The first touch goes out on its schedule. Say yes to enroll them.", contact), pending, lv._open_target("contact", contact)


async def enroll_now(db, user: dict, pending: dict):
    from routers.campaigns import enroll_contact_in_campaign
    try:
        await enroll_contact_in_campaign(str(user["_id"]), pending["campaign_id"], pending["contact_id"])
    except Exception as e:
        return f"That enrollment did not go through: {_err(e)}", None
    return f"Done. {pending['name']} is on {pending['campaign']}.", {"kind": "contact", "id": pending["contact_id"], "name": pending["name"], "first": pending["name"].split(" ")[0]}


def _names(people: list) -> str:
    firsts = [p.get("first") or p["name"].split(" ")[0] for p in people]
    if len(set(f.lower() for f in firsts)) < len(firsts):   # two Mikes: say full names
        firsts = [p["name"] for p in people]
    return firsts[0] if len(firsts) == 1 else f"{', '.join(firsts[:-1])} and {firsts[-1]}"


async def enroll_group(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    """Everyone met at one event onto a campaign: read back who joins and who is skipped, enroll only on yes (max met_at.MAX_BATCH)."""
    from services import met_at
    event = (args.get("event") or "").strip()
    if not met_at.event_key(event):
        return "Where did you meet them? Say something like everyone from NADA.", None, None
    camp, rows = await _match_campaign(user, args.get("campaign") or "")
    if not rows:
        return NO_CAMPAIGNS, None, None
    if not camp:
        return f"Which campaign should the {event} people go on? You have {'; '.join(c['name'] for c in rows[:5])}.", None, None
    pv = await met_at.preview(db, str(user["_id"]), camp["campaign_id"], event)
    opened = {"kind": "campaign", "id": camp["campaign_id"], "name": camp["name"]}
    if not pv["matched"]:
        return f"I do not have anyone marked as met at {event}. How we met is on each contact's profile, and I fill it in from your voice notes.", None, None
    ok = [p for p in pv["people"] if p["status"] == "ok"]
    skipped = met_at.skipped_line(pv["counts"])
    if not ok:
        return f"Nobody new to add from {pv['event']}. {skipped}".strip(), None, opened
    who = f" ({_names(ok)})" if len(ok) <= 5 else ""
    n = len(ok)
    pending = {"type": "enroll_group", "campaign_id": camp["campaign_id"], "campaign": camp["name"], "event": pv["query"], "label": pv["event"], "contact_ids": [p["id"] for p in ok],
               "name": f"{n} people met at {pv['event']}", "content": f"put {n} people met at {pv['event']} on {camp['name']}", "at": lv._now().isoformat()}
    people = "1 person" if n == 1 else f"{n} people"
    return (f"{people} you met at {pv['event']}{who} can go on {camp['name']}. {skipped + ' ' if skipped else ''}"
            "Their first touch goes out on the plan's schedule. Say yes to put them on it."), pending, opened


async def enroll_group_now(db, user: dict, pending: dict):
    from services import met_at
    opened = {"kind": "campaign", "id": pending["campaign_id"], "name": pending["campaign"]}
    try:
        res = await met_at.enroll(db, str(user["_id"]), pending["campaign_id"], pending["event"], pending.get("contact_ids") or [])
    except Exception as e:
        return f"That did not go through: {_err(e)}", opened
    n = res["enrolled"]
    if not n:
        return f"Nobody was enrolled. {met_at.skipped_line(res['skipped'])}".strip(), opened
    miss = f" {len(res['failed'])} did not go through." if res["failed"] else ""
    return f"Done. {n} {'person is' if n == 1 else 'people are'} on {pending['campaign']}.{miss}", opened


# ── build / edit a campaign ───────────────────────────────────────────────────
BRIEF_KEYS = ("goal", "audience", "trigger_tag", "length", "tone", "channels")


async def build_campaign(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    """Two or three quick questions (who, how long, tone) kept as a campaign_brief pending, then the draft is saved OFF and opened on screen."""
    from fastapi import HTTPException
    from services import campaign_builder as cb
    prev = (live or {}).get("pending") if ((live or {}).get("pending") or {}).get("type") == "campaign_brief" else None
    brief = dict((prev or {}).get("brief") or {})
    for k in BRIEF_KEYS:
        v = str(args.get(k) or "").strip()
        if v:
            brief[k] = v[:200]
    asked = list((prev or {}).get("asked") or [])
    said = (live or {}).get("_said") or ""
    # the model's "go" is trusted only when we cannot see the rep's words; an answer like "3 weeks, 5 touches" or "make it friendly" is not a go-ahead
    go = cb.go_ahead(said, bool(prev)) if said else bool(args.get("go"))
    if brief.get("trigger_tag") and not brief.get("audience"):
        brief["audience"] = f"anyone tagged {brief['trigger_tag']}"
    if not go:
        for key, question in cb.QUESTIONS:
            if not brief.get(key) and key not in asked and len(asked) < 3:
                asked.append(key)
                lead = "Sure, let's build it. " if not prev else ""
                pending = {"type": "campaign_brief", "brief": brief, "asked": asked, "name": "a new campaign", "content": f"building a campaign, asked about {key}", "at": lv._now().isoformat()}
                return f"{lead}{question}", pending, None
    try:
        made = await cb.create(db, user, brief)
    except HTTPException as e:
        why = str(e.detail).rstrip('. ')
        ask = "" if re.search(r"(?i)admin|manager", why) else " Ask your manager or admin to turn on campaign editing for you."
        return f"I cannot build campaigns on your login: {why}.{ask}", None, None
    except Exception as e:
        logger.warning(f"[Live] build_campaign failed: {e}")
        return "I could not draft that one. Try me again in a second.", None, None
    who = f" for anyone tagged {made['tag']}" if made["tag"] else ""
    tag_note = "" if not made["tag"] or made["tag_exists"] else f" You do not have a {made['tag']} tag yet; it starts the first time you tag someone with it."
    opened = {"kind": "campaign", "id": made["id"], "name": made["name"], "rev": lv._now().isoformat()}
    return (f"Here is {made['name']}{who}: {cb.outline(made['touches'])} It is on your screen and switched off.{tag_note} "
            "Tell me what to change, like make text 2 shorter or add a call on day 10, or edit it there and turn it on when you are happy."), None, opened


async def edit_campaign(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    from fastapi import HTTPException
    from services import campaign_builder as cb
    change = str(args.get("change") or (live or {}).get("_said") or "").strip()
    camp = await cb.find_draft(db, user, args.get("campaign") or "")
    if not camp:
        return "Which campaign? Say its name, or ask me to build a new one.", None
    opened = {"kind": "campaign", "id": str(camp["_id"]), "name": camp.get("name") or "", "rev": lv._now().isoformat()}
    try:
        res = await cb.edit(db, user, camp, change)
    except HTTPException as e:
        return str(e.detail), opened
    except Exception as e:
        logger.warning(f"[Live] edit_campaign failed: {e}")
        return "I could not make that change. Try saying it another way.", opened
    if not res["changed"]:
        return f"I was not sure what to change in {camp.get('name')}. Say it like make text 2 shorter, add a call on day 10, or change the tone to casual.", opened
    opened["name"] = res.get("name") or opened["name"]
    return f"{res['summary'].rstrip('. ')}. Now {cb.outline(res['touches'])} It is updated on your screen.", opened


# ── card / review link ────────────────────────────────────────────────────────
def _app_url() -> str:
    return (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "https://app.imonsocial.com").rstrip("/")


async def send_card(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    """Builds the text with the rep's card or review link; it rides the normal send_text read-back + yes."""
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None, None
    first, uid = _first(contact), str(user["_id"])
    if not contact.get("phone"):
        return f"{first} has no phone number on file, so I cannot text them.", None, lv._open_target("contact", contact)
    rep_first = (user.get("first_name") or (user.get("name") or "").split(" ")[0] or "").strip()
    what = "review" if (args.get("what") or "").lower().startswith("rev") else "card"
    if what == "review":
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])}, {"slug": 1}) if ObjectId.is_valid(str(user.get("store_id") or "")) else None
        slug = (store or {}).get("slug")
        if not slug:
            return "Your store does not have a review page set up yet, so there is no review link to send. Ask your manager to finish the store profile.", None, None
        link = f"{_app_url()}/review/{slug}?sp={uid}"
        content = f"Hi {first}, it's {rep_first}. Would you mind leaving me a quick review? It takes a minute and means a lot: {link}"
    else:
        link = f"{_app_url()}/card/{uid}"
        content = f"Hi {first}, it's {rep_first}. Here's my card so you have my info handy: {link}"
    pending = {"type": "send_text", "contact_id": str(contact["_id"]), "name": lv._first_last(contact), "content": content, "at": lv._now().isoformat()}
    label = "my card" if what == "card" else "a review request"
    return lv._with_note(f"Here is the text to send {first} {label}: \"{content}\" Say yes and I will send it.", contact), pending, lv._open_target("thread", contact)


# ── new contact ───────────────────────────────────────────────────────────────
def _clean_email(value: str) -> str:
    e = (value or "").strip().lower().replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
    return e if re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", e) else ""


async def _possible_dups(db, user: dict, first: str, last: str, phone: str, email: str) -> list:
    """Records that may already be this person: same phone or email in the rep's universe, or a very close full name."""
    from routers.contacts import _dup_owners
    uid = str(user["_id"])
    owners, _, _ = await _dup_owners(db, uid)
    ors = ([{"phone": {"$regex": re.sub(r"\D", "", phone)[-10:] + "$"}}] if len(re.sub(r"\D", "", phone)) >= 10 else []) + \
          ([{"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}] if email else [])
    rows = await db.contacts.find({"user_id": {"$in": owners}, "status": {"$nin": ["merged", "deleted", "hidden"]}, "$or": ors},
                                  {"first_name": 1, "last_name": 1, "phone": 1, "email": 1, "vehicle": 1}).limit(3).to_list(3) if ors else []
    if first and last:
        for r in await lv._find(db, uid, f"{first} {last}"):
            if r.get("_score", 0) >= 0.9 and lv._sim(last, r.get("last_name") or "") >= 0.85:
                rows.append(r)
    seen, out = set(), []
    for r in rows:
        if r["_id"] not in seen:
            seen.add(r["_id"])
            out.append(r)
    return out[:3]


def _name_case(v) -> str:
    """'mike peterson' -> 'Mike Peterson', but McDonald and DeAngelo keep the casing the brain gave."""
    words = re.sub(r"\s+", " ", str(v or "")).strip(" .,").split(" ")
    return " ".join(w.title() if (w.islower() or w.isupper()) else w[:1].upper() + w[1:] for w in words if w)[:40]


def _follow_note(v) -> str:
    """'Follow up next Tuesday about a fleet deal' / 'call him Friday about his trade' -> 'fleet deal' / 'his trade'."""
    n = re.sub(r"\s+", " ", str(v or "")).strip(" .")
    m = re.match(r"(?i)^(to\s+)?(follow\s*-?\s*up|check\s+in|call|text|email|ping|reach\s+out|touch\s+base)\b[^,]*?\b(about|regarding|re)\s+(.+)$", n)
    n = m.group(4) if m else re.sub(r"(?i)^(to\s+)?(follow\s*-?\s*up|check\s+in)(\s+with\s+\w+)?\s*", "", n)
    return re.sub(r"(?i)^((a|an|the|on|about|regarding)\s+)+", "", n).strip(" .")[:120]


async def create_contact(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    """Stage a new contact from what the rep said: read it back, warn about a likely duplicate, save only on their yes.
    Nothing is invented: a missing detail stays empty, and a name is the only thing Jessi asks for."""
    from services import how_we_met
    from services.twilio_service import normalize_phone
    prev = (live or {}).get("pending") if ((live or {}).get("pending") or {}).get("type") == "contact" else None
    said = " ".join(x for x in ((prev or {}).get("said", ""), (live or {}).get("_said", "")) if x).strip()
    first = _name_case(args.get("first_name"))
    last = _name_case(args.get("last_name"))
    if not first:
        return "What's their name?", prev, None
    raw_phone = str(args.get("phone") or "").strip()
    phone = normalize_phone(raw_phone) if len(re.sub(r"\D", "", raw_phone)) >= 10 else ""
    email = _clean_email(args.get("email") or "")
    company = str(args.get("company") or "").strip()[:80]
    met = how_we_met.clean({"event": args.get("met_at"), "place": args.get("met_place"), "date": args.get("met_date")})
    tz = await lv._tz(user)
    follow_at = _parse_local(args.get("follow_up_iso"), tz)
    if follow_at and not (follow_at.hour or follow_at.minute):
        follow_at = follow_at.replace(hour=9)
    if follow_at and follow_at <= lv._now() and follow_at.date() == lv._now().astimezone(tz).date():   # "today" after 9 AM: later today
        follow_at = (lv._now().astimezone(tz) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    follow = {"when": follow_at.isoformat(), "note": _follow_note(args.get("follow_up_note"))} if follow_at and follow_at > lv._now() else None
    name = f"{first} {last}".strip()
    bits = [name] + ([lv._fmt_phone(phone)] if phone else []) + ([email] if email else []) + ([company] if company else [])
    met_line = how_we_met.line(met)
    summary = ", ".join(bits) + (f", met {met_line[0].lower() + met_line[1:]}" if met_line else "")
    missing = "" if phone or email else " No phone or email yet, you can add those later."
    heard = " I will keep what you told me about them as a voice memo on their profile." if said or args.get("note") else ""
    dups = await _possible_dups(db, user, first, last, phone, email)
    dup = ""
    if dups:
        d = dups[0]
        dup = (f" Heads up: you already have {lv._first_last(d)}" + (f" at {lv._fmt_phone(d['phone'])}" if d.get("phone") else "") +
               ". Say yes to add a new record anyway, or tell me to add this to the one you have.")
    pending = {"type": "contact", "name": name, "content": f"add new contact {summary}", "at": lv._now().isoformat(), "said": said[:2000],
               "fields": {"first_name": first, "last_name": last, "phone": phone, "email": email, "company": company},
               "met": met, "note": str(args.get("note") or "").strip()[:2000], "follow": follow, "dup_ids": [str(d["_id"]) for d in dups]}
    say = f"Add {summary}?{missing}{heard}{dup}" + ("" if dup else " Say yes to save, or tell me what to change.")
    return say, pending, None


async def contact_now(db, user: dict, pending: dict):
    """Create the contact through the normal contacts API (no tags, so no campaign starts), keep the rep's words as a Jessi memo
    (the usual extraction makes them searchable), fill How we met, then offer the dated reminder. Returns (say, open, next pending)."""
    from models import ContactCreate
    from routers.contacts import create_contact as api_create
    from routers.voice_notes import create_text_memo
    from services import how_we_met
    uid, f = str(user["_id"]), pending["fields"]
    try:
        c = await api_create(uid, ContactCreate(first_name=f["first_name"], last_name=f.get("last_name") or None, phone=f.get("phone") or "", email=f.get("email") or None,
                                                employer=f.get("company") or None, organization_name=f.get("company") or None, source="jessi"))
    except Exception as e:
        return f"That contact did not save: {_err(e)}", None, None
    cid = str(c.id)
    await how_we_met.fill(db, cid, pending.get("met") or {}, "jessi")
    words = (pending.get("said") or pending.get("note") or "").strip()
    if len(words) >= 10:
        try:
            await create_text_memo(db, uid, cid, words, source="jessi", followup=False)
        except Exception as e:
            logger.warning(f"[LiveActions] new-contact memo failed for {cid}: {e}")
    name, first = pending["name"], f["first_name"]
    opened = {"kind": "contact", "id": cid, "name": name, "first": first}
    follow = pending.get("follow")
    if follow:
        when = datetime.fromisoformat(follow["when"])
        nxt = {"type": "reminder", "contact_id": cid, "name": name, "when": follow["when"], "note": follow.get("note") or "",
               "content": f"remind the rep to follow up with {name} {_spoken(when)}", "at": lv._now().isoformat()}
        return f"Saved {name}. Want a reminder to follow up {_spoken(when)}" + (f" about {nxt['note']}" if nxt["note"] else "") + "?", opened, nxt
    return f"Saved {name}. They are in your contacts, and anything useful you told me goes on their profile.", opened, None


async def reminder_now(db, user: dict, pending: dict):
    from routers.tasks import create_task
    when = datetime.fromisoformat(pending["when"])
    first = pending["name"].split(" ")[0]
    title = (f"Follow up with {first}: {pending['note']}" if pending.get("note") else f"Follow up with {pending['name']}")[:100]
    try:
        task = await create_task(str(user["_id"]), {"title": title, "description": pending.get("note") or title, "contact_id": pending["contact_id"], "type": "follow_up",
                                                    "action_type": "call", "due_date": when.astimezone(timezone.utc).isoformat(), "has_time": True, "priority": "medium"})
    except Exception as e:
        return f"I could not save that reminder: {_err(e)}", None
    return f"Done. Reminder set for {_spoken(when)}: {title}.", lv._open_target("task", task=task) if task else {"kind": "contact", "id": pending["contact_id"], "name": pending["name"], "first": first}
