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
async def enroll_campaign(db, user: dict, args: dict, focus: Optional[dict], live: Optional[dict]):
    contact, err = await _person(db, user, args, focus, live)
    if err:
        return err, None, None
    first, uid, cid = _first(contact), str(user["_id"]), str(contact["_id"])
    from routers.campaigns import list_campaigns_simple
    rows = [c for c in ((await list_campaigns_simple(uid)).get("campaigns") or []) if c.get("active")]
    if not rows:
        return "You do not have any active campaigns yet. Set one up under Campaigns and I can enroll people from here.", None, lv._open_target("contact", contact)
    want = (args.get("campaign") or "").strip().lower()
    words = [w for w in re.findall(r"[a-z0-9]+", want) if len(w) > 2 and w not in ("campaign", "plan", "the", "and", "for")]
    scored = sorted(((max([lv._sim(w, x) for w in words for x in re.findall(r"[a-z0-9]+", (c.get("name") or "").lower())] or [0]), sum(1 for w in words if w in (c.get("name") or "").lower()), c) for c in rows), key=lambda x: (-x[1], -x[0]))
    best = scored[0] if scored and words and (scored[0][1] or scored[0][0] >= 0.85) else None
    if not best:
        names = "; ".join(c["name"] for c in rows[:5])
        return f"Which campaign for {first}? You have {names}.", None, lv._open_target("contact", contact)
    camp = best[2]
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
