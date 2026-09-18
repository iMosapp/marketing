"""The rep's day as Jessi walks it out loud: customers waiting on a reply, overdue touchpoints, today's 3, then the top hot opportunities.
Same sources as the Home screen (Do this next, Your 3, Hot opportunities), so what she says matches what the rep sees."""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

MAX_REPLIES = 3
MAX_TASKS = 3
MAX_HOT = 3
REPLY_WINDOW_DAYS = 3


def _now():
    return datetime.now(timezone.utc)


def _name(c: Optional[dict]) -> str:
    return f"{(c or {}).get('first_name') or ''} {(c or {}).get('last_name') or ''}".strip() or ((c or {}).get("name") or (c or {}).get("phone") or "a customer")


def _first(c: Optional[dict]) -> str:
    return (c or {}).get("first_name") or _name(c).split(" ")[0]


def _ago(when, now) -> str:
    if isinstance(when, str):
        try:
            when = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if not isinstance(when, datetime):
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    s = int((now - when).total_seconds())
    if s < 3600:
        return f"{max(1, s // 60)} minutes ago"
    if s < 86400:
        h = s // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = s // 86400
    return "yesterday" if d == 1 else f"{d} days ago"


def _excerpt(text: str, n: int = 110) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "..."


def _stop(kind: str, contact: Optional[dict], say: str, why: str, **extra) -> dict:
    return {"key": extra.pop("key", f"{kind}:{str((contact or {}).get('_id') or extra.get('conversation_id') or extra.get('task_id') or '')}"),
            "kind": kind, "contact_id": str(contact["_id"]) if contact else None, "name": _name(contact), "first": _first(contact), "say": say, "why": why,
            "conversation_id": None, "task_id": None, **extra}


async def _contacts(db, ids: list) -> dict:
    oids = [ObjectId(i) for i in {str(i) for i in ids if i and ObjectId.is_valid(str(i))}]
    rows = await db.contacts.find({"_id": {"$in": oids}}, {"first_name": 1, "last_name": 1, "name": 1, "phone": 1, "vehicle": 1, "vehicle_interest": 1}).to_list(len(oids)) if oids else []
    return {str(r["_id"]): r for r in rows}


async def _replies_and_hot(db, uid: str, dismissed: set, now):
    """Conversations where the customer spoke last (reply stops, hot first) and hot conversations already answered (for the closing section)."""
    since = now - timedelta(days=REPLY_WINDOW_DAYS)
    convs = await db.conversations.find({"user_id": uid, "$or": [{"hot_opportunity": True}, {"last_message_at": {"$gte": since}}]},
                                        {"contact_id": 1, "hot_opportunity": 1, "intent_signals": 1, "last_message_at": 1, "hot_last_at": 1}).sort("last_message_at", -1).limit(60).to_list(60)
    people = await _contacts(db, [c.get("contact_id") for c in convs])
    waiting, hot = [], []
    for c in convs:
        cid = str(c["_id"])
        if f"hot:{cid}" in dismissed or not c.get("contact_id") or c["contact_id"] not in people:
            continue
        last = await db.messages.find_one({"conversation_id": cid, "sender": {"$ne": "ai_draft"}, "content": {"$exists": True, "$ne": ""}}, {"sender": 1, "content": 1, "timestamp": 1}, sort=[("timestamp", -1)])
        contact = people[c["contact_id"]]
        signal = (c.get("intent_signals") or [None])[0]
        if last and last.get("sender") == "contact":
            when = last.get("timestamp")
            if not c.get("hot_opportunity") and (not isinstance(when, datetime) or (when.replace(tzinfo=when.tzinfo or timezone.utc) < since)):
                continue
            why = f"texted {_ago(when, now)}: \"{_excerpt(last.get('content'))}\"" + (f". {signal}" if signal else "")
            say = (f"Reply to {_name(contact)}. {_first(contact)} {why}, and hasn't heard back. Want me to draft the reply?")
            waiting.append((0 if c.get("hot_opportunity") else 1, _stop("reply", contact, say, why, conversation_id=cid, key=f"hot:{cid}", hot=bool(c.get("hot_opportunity")))))
        elif c.get("hot_opportunity"):
            why = signal or "high buying intent on your card"
            say = f"Hot opportunity: {_name(contact)}. {why}. Want to text {_first(contact)}?"
            hot.append(_stop("hot", contact, say, why, conversation_id=cid, key=f"hot:{cid}"))
    waiting.sort(key=lambda x: x[0])
    return [w[1] for w in waiting][:MAX_REPLIES], hot[:MAX_HOT]


async def _overdue(db, uid: str, start_utc, now) -> list:
    tasks = await db.tasks.find({"user_id": uid, "status": {"$in": ["pending", None]}, "completed": {"$ne": True}, "due_date": {"$lt": start_utc}},
                                {"title": 1, "contact_id": 1, "due_date": 1, "action_type": 1, "task_type": 1}).sort("due_date", 1).limit(MAX_TASKS).to_list(MAX_TASKS)
    people = await _contacts(db, [t.get("contact_id") for t in tasks])
    out = []
    for t in tasks:
        contact = people.get(str(t.get("contact_id") or ""))
        title = _excerpt(t.get("title") or "follow up", 80)
        due = t.get("due_date")
        why = f"overdue since {_ago(due, now).replace(' ago', '')}: {title}" if due else f"overdue: {title}"
        who = f" with {_name(contact)}" if contact else ""
        say = f"Overdue touchpoint{who}: {title}, due {_ago(due, now).replace(' ago', ' back') if due else 'earlier'}. Want me to pull {('them' if not contact else _first(contact))} up, or is it done?"
        out.append(_stop("task", contact, say, why, task_id=str(t["_id"]), key=f"task:{t['_id']}"))
    return out


async def build(db, user_id: str) -> list:
    """Ordered stops: replies waiting -> overdue touchpoints -> today's 3 (not done) -> top hot opportunities. One stop per person."""
    from routers.home_intelligence import _local_day, get_my_3
    uid = str(user_id)
    now = _now()
    day, start_utc, _ = await _local_day(uid, db)
    states = await db.home_action_state.find({"user_id": uid, "day": day}, {"key": 1, "status": 1}).to_list(300)
    dismissed = {s["key"] for s in states if s.get("status") == "dismissed"}
    replies, hot = await _replies_and_hot(db, uid, dismissed, now)
    stops = list(replies) + await _overdue(db, uid, start_utc, now)
    seen = {s["contact_id"] for s in stops if s.get("contact_id")}
    for it in await get_my_3(uid, db):
        cid = it.get("contact_id")
        if not cid or cid in seen or it.get("done") or cid in dismissed:
            continue
        seen.add(cid)
        contact = {"_id": ObjectId(cid), "first_name": it.get("first_name"), "last_name": it.get("last_name"), "phone": it.get("phone")}
        why = (it.get("reason_label") or "one of your three today") + (f". {it['hook']}" if it.get("hook") else "")
        action = (it.get("action_label") or "Text").lower()
        say = f"{_name(contact)}, one of your three. {why}. Want me to draft the {'call notes' if action == 'call' else 'text'}?"
        stops.append(_stop("my3", contact, say, why, key=cid, action=action))
    for h in hot:
        if h.get("contact_id") in seen:
            continue
        seen.add(h.get("contact_id"))
        stops.append(h)
    for i, s in enumerate(stops):
        s["n"] = i + 1
    return stops


def intro(user: dict, stops: list) -> str:
    first = (user.get("name") or "").split(" ")[0] or "there"
    if not stops:
        return f"Hey {first}. You are caught up: nobody is waiting on a reply, your three are done and no hot leads are sitting. Anything else?"
    kinds = {"reply": 0, "task": 0, "my3": 0, "hot": 0}
    for s in stops:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    parts = []
    if kinds["reply"]:
        names = [s["first"] for s in stops if s["kind"] == "reply"]
        parts.append(f"reply to {names[0]}" if len(names) == 1 else f"{len(names)} replies waiting")
    if kinds["task"]:
        parts.append(f"{kinds['task']} overdue touchpoint{'s' if kinds['task'] != 1 else ''}")
    if kinds["my3"]:
        names = [s["first"] for s in stops if s["kind"] == "my3"]
        parts.append("your three: " + ", ".join(names) if len(names) > 1 else f"your pick for today, {names[0]}")
    if kinds["hot"]:
        parts.append(f"{kinds['hot']} hot opportunit{'ies' if kinds['hot'] != 1 else 'y'} to close on")
    plan = "; ".join(parts)
    return f"Hey {first}. {len(stops)} stop{'s' if len(stops) != 1 else ''} today: {plan}. First up: {stops[0]['say']}"


def outro(done: int, skipped: int, total: int) -> str:
    if total == 0:
        return "Nothing else on the board. Go find the next one."
    bits = []
    if done:
        bits.append(f"{done} handled")
    if skipped:
        bits.append(f"{skipped} skipped")
    left = total - done - skipped
    if left > 0:
        bits.append(f"{left} still open on Home")
    return "That's your day. " + (", ".join(bits) + ". " if bits else "") + "Go get 'em."


def open_target(stop: dict) -> Optional[dict]:
    if not stop:
        return {"kind": "home"}
    if stop["kind"] in ("reply", "hot") and stop.get("conversation_id"):
        return {"kind": "thread", "id": stop["contact_id"], "name": stop["name"], "first": stop["first"]}
    if stop["kind"] == "task" and stop.get("task_id"):
        return {"kind": "task", "id": stop["task_id"], "name": stop["why"], "contact_id": stop.get("contact_id") or ""}
    if stop.get("contact_id"):
        return {"kind": "contact", "id": stop["contact_id"], "name": stop["name"], "first": stop["first"]}
    return None


async def settle(db, user_id: str, stop: dict, action: str):
    """Make Home agree with what the rep just said: done ticks it off, skip hides it for today."""
    from routers.home_intelligence import _local_day, _home_cache
    uid = str(user_id)
    day, _, _ = await _local_day(uid, db)
    now = _now()
    if stop["kind"] == "task" and stop.get("task_id") and action == "done":
        await db.tasks.update_one({"_id": ObjectId(stop["task_id"])}, {"$set": {"status": "completed", "completed": True, "completed_at": now, "completed_via": "jessi_walkthrough", "updated_at": now}})
        return
    if stop["kind"] == "task":
        return
    status = "done" if action == "done" else "dismissed"
    if stop["kind"] in ("reply", "hot"):
        status = "dismissed"  # Home hides a hot thread for today either way; a real reply shows up on its own
    await db.home_action_state.update_one({"user_id": uid, "day": day, "key": stop["key"]},
                                          {"$set": {"status": status, "source": "jessi_walkthrough", "updated_at": now}}, upsert=True)
    _home_cache.pop(uid, None)
