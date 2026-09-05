"""
Alerts (notification center) - an ACTION list, not a log.
Every item is verb-first ("Reply to Sarah"), carries one action button that lands on the exact
screen, sits in a bucket (now / today / later) and can be dismissed (swipe) or cleared in bulk.
Activity-type items (sent confirmations, clicks, campaign chores) still come back for feed=activity
so older app builds keep working, but the app no longer shows them here (the Activity tab does).
"""
import logging
import urllib.parse
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from bson import ObjectId
from cachetools import TTLCache

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notification-center", tags=["notification-center"])

_notifications_cache: TTLCache = TTLCache(maxsize=500, ttl=30)
_SECTION_TIMEOUT = 3.0
_TOTAL_TIMEOUT = 10.0

# db.notifications type -> (bucket, verb title, action label, action icon)
# {name} = contact full name, {first} = first name
ACTION_TYPES = {
    "you_are_needed":             ("now",   "Reply to {name}",                  "Reply",    "chatbubble"),
    "customer_reply":             ("now",   "Reply to {name}",                  "Reply",    "chatbubble"),
    "call_retry_replied":         ("now",   "Reply to {name}",                  "Reply",    "chatbubble"),
    "slow_lead":                  ("now",   "Respond to {name}",                "Respond",  "flash"),
    "ai_draft_approval_required": ("now",   "Approve draft for {first}",        "Approve",  "sparkles"),
    "jump_ball":                  ("now",   "Claim {name}",                     "Claim",    "hand-left"),
    "new_lead":                   ("now",   "Respond to {name}",                "Respond",  "person-add"),
    "lead_assigned":              ("now",   "Respond to {name}",                "Respond",  "person-add"),
    "lead_reassigned":            ("now",   "Pick up {name}",                   "Open",     "swap-horizontal"),
    "keyword_alert":              ("now",   "Check {first}'s message",          "Open",     "key"),
    "engagement_signal":          ("today", "Reach out to {name}",              "Text",     "flame"),
    "new_demo_request":           ("today", "Follow up with {name}",            "Open",     "person-add"),
    "appointment_extracted":      ("today", "Confirm {first}'s appointment",    "Review",   "calendar"),
    "task_reminder":              ("today", "{title}",                          "Open",     "alarm"),
    "manager_nudge":              ("today", "{title}",                          "Open",     "megaphone"),
    "inventory_feed_issue":       ("today", "{title}",                          "Fix",      "cloud-offline"),
}
BUCKETS = ("now", "today", "later")
# legacy category (older app builds filter on it)
_CATEGORY = {"you_are_needed": "urgent", "slow_lead": "urgent", "customer_reply": "replies", "call_retry_replied": "replies",
             "ai_draft_approval_required": "replies", "keyword_alert": "replies", "appointment_extracted": "appts",
             "task_reminder": "appts", "manager_nudge": "appts"}
FOR_YOU_CATEGORIES = ("urgent", "leads", "replies", "appts")
VIRTUAL_PREFIXES = ("task_", "task_soon_", "msg_", "flag_", "evt_", "csend_")


def _ts(val) -> str:
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val else datetime.now(timezone.utc).isoformat()


def _dt(val) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _first(name: str) -> str:
    return (name or "").strip().split(" ")[0] if (name or "").strip() else "them"


async def _get_user_teams(db, user_id: str) -> list:
    user_teams = []
    try:
        teams = await db.teams.find({"members": user_id}, {"_id": 1}).to_list(50)
        user_teams.extend([str(t["_id"]) for t in teams])
        shared_inboxes = await db.shared_inboxes.find({"user_ids": user_id}, {"_id": 1}).to_list(50)
        user_teams.extend([str(si["_id"]) for si in shared_inboxes])
    except Exception:
        pass
    return user_teams


async def _run_section(coro, section_name: str, fallback=None):
    try:
        return await asyncio.wait_for(coro, timeout=_SECTION_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"[Alerts] Section '{section_name}' timed out")
        return fallback if fallback is not None else []
    except Exception as e:
        logger.debug(f"[Alerts] Section '{section_name}' error: {e}")
        return fallback if fallback is not None else []


def _notif_link(n: dict) -> str | None:
    """Where the action button lands for a db.notifications doc."""
    conversation_id = n.get("conversation_id", "")
    contact_id = n.get("contact_id", "")
    ntype = n.get("type", "")
    if ntype in ("you_are_needed", "customer_reply", "customer_reply_ai_handling", "slow_lead", "call_retry_replied",
                 "ai_draft_approval_required", "keyword_alert", "new_lead", "lead_assigned", "lead_reassigned", "jump_ball") and conversation_id:
        return f"/thread/{conversation_id}"
    if ntype in ("appointment_extracted", "task_reminder"):
        if contact_id and n.get("task_id"):
            return f"/contact/{contact_id}?taskId={n['task_id']}"
        return f"/contact/{contact_id}" if contact_id else "/dates-calendar"
    if ntype == "manager_nudge":
        return "/touchpoints"
    if n.get("link"):
        return n["link"]
    if ntype == "engagement_signal" and conversation_id:
        return f"/thread/{conversation_id}"
    if contact_id:
        return f"/contact/{contact_id}"
    if conversation_id:
        return f"/thread/{conversation_id}"
    if n.get("demo_request_id"):
        return "/admin/lead-tracking"
    return None


def _age_bucket(bucket: str, ts: datetime, now: datetime) -> str:
    """Stale alerts sink: now -> today after 24h, today -> later after 48h."""
    age = now - ts
    if bucket == "now" and age > timedelta(hours=24):
        bucket = "today"
    if bucket == "today" and age > timedelta(hours=48):
        bucket = "later"
    return bucket


def _task_action(t: dict, contact: dict | None, overdue: bool, now: datetime) -> dict:
    contact_id = t.get("contact_id", "")
    task_id = str(t["_id"])
    title = t.get("title", "Follow up")
    name = (t.get("contact_name") or (f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() if contact else "")).strip()
    first = _first(name)
    ttype = (t.get("type") or t.get("action_type") or "").lower()
    due = _dt(t.get("due_date"))
    if overdue:
        days = max(1, (now - due).days) if now - due >= timedelta(days=1) else 0
        when = f"Overdue {days}d" if days else "Overdue today"
    else:
        when = "Due " + due.strftime("%-I:%M %p") if t.get("has_time") else "Due today"
    kind = "call" if ttype in ("call", "phone") or title.lower().startswith("call") else (
        "text" if ttype in ("text", "sms") or title.lower().startswith(("text", "write")) else "open")
    if kind == "call" and name:
        verb = f"Call {name}"
        label, icon = "Call", "call"
        phone = (contact or {}).get("phone", "")
        link = ("/call-screen?" + urllib.parse.urlencode({"phone": phone, "contact_name": name, "contact_id": contact_id, "task_id": task_id})
                if phone else f"/contact/{contact_id}?taskId={task_id}")
    elif kind == "text" and name:
        verb = f"Text {name}"
        label, icon = "Text", "chatbubble"
        link = f"/contact/{contact_id}?taskId={task_id}" if contact_id else "/dates-calendar"
    else:
        verb = title
        label, icon = "Open", "checkmark-circle"
        link = f"/contact/{contact_id}?taskId={task_id}" if contact_id else "/dates-calendar"
    context = f"{when} · {title}" if verb != title else (f"{when} · {name}" if name else when)
    return {"title": verb, "context": context, "link": link, "action": {"label": label, "icon": icon, "link": link},
            "contact_name": name, "contact_id": contact_id, "task_id": task_id}


async def _get_full_feed(user_id: str) -> dict:
    if user_id in _notifications_cache:
        return _notifications_cache[user_id]
    try:
        built = await asyncio.wait_for(_build_feed(user_id), timeout=_TOTAL_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"[Alerts] Timeout for user {user_id}")
        built = {"items": [], "unread_count": 0, "category_counts": {}, "bucket_counts": {}, "activity_count": 0, "timed_out": True}
    _notifications_cache[user_id] = built
    return built


async def _build_feed(user_id: str) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)
    items = []

    user_teams = await _run_section(_get_user_teams(db, user_id), "teams", [])
    reads = await _run_section(db.notification_reads.find_one({"user_id": user_id}), "read_status", None) or {}
    read_ids = set(reads.get("read_ids", []))
    dismissed_ids = set(reads.get("dismissed_ids", []))

    # 1. db.notifications -> action items (or activity for non-action types)
    notif_query = {"$or": [{"user_id": user_id}, {"team_id": {"$in": user_teams}, "user_id": None}], "dismissed": {"$ne": True}}
    notifs = await _run_section(db.notifications.find(notif_query).sort("created_at", -1).limit(80).to_list(80), "notifications")

    # Self-cleaning: an alert disappears once the thing it asked for happened.
    #  - duplicates (same type + same lead/thread) collapse to the newest
    #  - reply-type alerts resolve when the rep has texted that thread since
    #  - draft approvals resolve when the draft is no longer waiting
    stale_ids: list = []
    seen_keys: set = set()
    keep: list = []
    for n in notifs:
        ntype = n.get("type", "")
        if ntype in ACTION_TYPES:
            key = (ntype, str(n.get("conversation_id") or n.get("contact_id") or n.get("contact_name") or n["_id"]))
            if key in seen_keys:
                stale_ids.append(n["_id"])
                continue
            seen_keys.add(key)
        keep.append(n)
    notifs = keep

    reply_types = ("you_are_needed", "customer_reply", "call_retry_replied", "slow_lead", "new_lead", "lead_assigned", "lead_reassigned", "keyword_alert", "jump_ball")
    conv_ids = list({str(n["conversation_id"]) for n in notifs if n.get("type") in reply_types and n.get("conversation_id")})
    replied_at: dict = {}
    if conv_ids:
        human = await _run_section(db.messages.find({"conversation_id": {"$in": conv_ids}, "sender": "user"},
                                                    {"conversation_id": 1, "timestamp": 1}).sort("timestamp", -1).limit(300).to_list(300), "human_replies")
        for m in human:
            cid = str(m.get("conversation_id"))
            t = _dt(m.get("timestamp"))
            if cid not in replied_at or t > replied_at[cid]:
                replied_at[cid] = t
    queue_ids = [n["queue_id"] for n in notifs if n.get("type") == "ai_draft_approval_required" and n.get("queue_id") and ObjectId.is_valid(str(n.get("queue_id")))]
    pending_queue: set = set()
    if queue_ids:
        qs = await _run_section(db.ai_reply_queue.find({"_id": {"$in": [ObjectId(q) for q in queue_ids]}, "status": "pending"}, {"_id": 1}).to_list(100), "pending_drafts")
        pending_queue = {str(q["_id"]) for q in qs}
    keep = []
    for n in notifs:
        ntype = n.get("type", "")
        if ntype in reply_types and n.get("conversation_id"):
            t = replied_at.get(str(n["conversation_id"]))
            if t and t > _dt(n.get("created_at")):
                stale_ids.append(n["_id"])
                continue
        if ntype == "ai_draft_approval_required" and n.get("queue_id") and str(n["queue_id"]) not in pending_queue:
            stale_ids.append(n["_id"])
            continue
        keep.append(n)
    notifs = keep
    if stale_ids:
        await _run_section(db.notifications.update_many({"_id": {"$in": stale_ids}}, {"$set": {"dismissed": True, "read": True, "auto_resolved": True}}), "auto_resolve", None)

    # names for docs that only carry a contact_id
    missing = [n["contact_id"] for n in notifs if not n.get("contact_name") and n.get("contact_id") and ObjectId.is_valid(str(n.get("contact_id")))]
    names = {}
    if missing:
        docs = await _run_section(db.contacts.find({"_id": {"$in": [ObjectId(c) for c in missing[:40]]}},
                                                   {"first_name": 1, "last_name": 1}).to_list(40), "names")
        names = {str(c["_id"]): f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() for c in docs}

    for n in notifs:
        ntype = n.get("type", "activity")
        contact_id = str(n.get("contact_id") or "")
        name = (n.get("contact_name") or names.get(contact_id) or "").strip()
        body = n.get("message") or n.get("form_details") or ""
        ts = _dt(n.get("created_at"))
        base = {
            "id": str(n["_id"]), "type": ntype, "contact_name": name or None, "contact_id": contact_id,
            "conversation_id": n.get("conversation_id", ""), "demo_request_id": n.get("demo_request_id", ""),
            "timestamp": ts.isoformat(), "read": bool(n.get("read", False)),
        }
        spec = ACTION_TYPES.get(ntype)
        if spec:
            bucket, verb, label, icon = spec
            if ntype == "engagement_signal" and (n.get("is_return_visit") or n.get("view_count", 1) >= 3):
                bucket = "now"
            shown_name = name or "this customer"
            title = verb.format(name=shown_name, first=_first(shown_name), title=n.get("title", ntype.replace("_", " ").title()))
            link = _notif_link(n)
            context = body
            if ntype in ("new_lead", "lead_assigned") and name and body.lower().startswith(name.lower()):
                rest = body[len(name):].strip(" .:-")
                context = (rest[:1].upper() + rest[1:]) if rest else body
            items.append({**base, "feed": "for_you", "bucket": _age_bucket(bucket, ts, now),
                          "category": _CATEGORY.get(ntype, "leads"), "title": title, "body": context, "context": context,
                          "link": link, "action": {"label": label, "icon": icon, "link": link}, "source": "notifications"})
        else:
            items.append({**base, "feed": "activity", "bucket": "later", "category": "activity", "priority": 6,
                          "title": n.get("title", ntype.replace("_", " ").title()), "body": body, "context": body,
                          "link": _notif_link(n), "action": None, "source": "activity"})

    # 2. Tasks: overdue (today) + due in the next 24h (later); campaign chores excluded
    task_filter = {"user_id": user_id, "completed": {"$ne": True}, "status": {"$nin": ["completed", "cancelled"]},
                   "type": {"$nin": ["campaign_send", "campaign_step"]}}
    overdue = await _run_section(db.tasks.find({**task_filter, "due_date": {"$lt": now}}).sort("due_date", -1).limit(15).to_list(15), "overdue_tasks")
    upcoming = await _run_section(db.tasks.find({**task_filter, "due_date": {"$gte": now, "$lte": now + timedelta(hours=24)}}).sort("due_date", 1).limit(8).to_list(8), "upcoming_tasks")
    cids = [t["contact_id"] for t in overdue + upcoming if t.get("contact_id") and ObjectId.is_valid(str(t.get("contact_id")))]
    contacts = {}
    if cids:
        docs = await _run_section(db.contacts.find({"_id": {"$in": [ObjectId(c) for c in cids]}},
                                                   {"first_name": 1, "last_name": 1, "phone": 1}).to_list(40), "task_contacts")
        contacts = {str(c["_id"]): c for c in docs}
    for t in overdue:
        a = _task_action(t, contacts.get(str(t.get("contact_id"))), True, now)
        items.append({"id": f"task_{t['_id']}", "type": "task_overdue", "feed": "for_you", "bucket": "today", "category": "appts",
                      "timestamp": _ts(t.get("due_date")), "read": False, "source": "tasks", "body": a["context"], **a})
    for t in upcoming:
        a = _task_action(t, contacts.get(str(t.get("contact_id"))), False, now)
        items.append({"id": f"task_soon_{t['_id']}", "type": "task_due_soon", "feed": "for_you", "bucket": "later", "category": "appts",
                      "timestamp": _ts(t.get("due_date")), "read": False, "source": "tasks", "body": a["context"], **a})

    # 3. Activity extras (only returned for feed=activity; kept for older builds)
    cutoff = now - timedelta(hours=24)
    recent = await _run_section(db.contact_events.find({"user_id": user_id, "timestamp": {"$gte": cutoff}, "event_type": {"$in": [
        "link_click", "review_submitted", "new_contact", "digital_card_sent", "review_request_sent", "congrats_card_sent", "email_sent", "sms_sent"]}})
        .sort("timestamp", -1).limit(15).to_list(15), "recent_activity")
    for ev in recent:
        items.append({"id": f"evt_{ev['_id']}", "type": ev.get("event_type", "activity"), "feed": "activity", "bucket": "later", "category": "activity",
                      "title": ev.get("title") or ev.get("event_type", "Activity").replace("_", " ").title(),
                      "body": ev.get("description", ""), "context": ev.get("description", ""), "link": f"/contact/{ev.get('contact_id', '')}",
                      "action": None, "timestamp": _ts(ev.get("timestamp")), "read": True, "source": "activity"})

    # overlays: read + dismissed (virtual ids live in notification_reads)
    items = [n for n in items if n["id"] not in dismissed_ids]
    for n in items:
        if n["id"] in read_ids:
            n["read"] = True

    # buckets in order; newest first inside a bucket, unread before read
    grouped = []
    for b in BUCKETS:
        grp = [n for n in items if n.get("bucket") == b]
        grp.sort(key=lambda n: (n.get("read", False), -_dt(n.get("timestamp")).timestamp()))
        grouped.extend(grp)
    items = grouped + [n for n in items if n.get("bucket") not in BUCKETS]

    for_you = [n for n in items if n["feed"] == "for_you"]
    category_counts = {c: 0 for c in FOR_YOU_CATEGORIES}
    bucket_counts = {b: 0 for b in BUCKETS}
    for n in for_you:
        category_counts[n["category"]] = category_counts.get(n["category"], 0) + 1
        bucket_counts[n["bucket"]] = bucket_counts.get(n["bucket"], 0) + 1
    return {
        "items": items,
        "unread_count": sum(1 for n in for_you if not n["read"]),
        "category_counts": category_counts,
        "bucket_counts": bucket_counts,
        "activity_count": sum(1 for n in items if n["feed"] == "activity"),
    }


@router.get("/{user_id}")
async def get_notifications(user_id: str, limit: int = 50, category: str = "all", feed: str = "for_you"):
    """Action feed (default) or the legacy activity feed."""
    built = await _get_full_feed(user_id)
    if feed == "activity":
        filtered = [n for n in built["items"] if n["feed"] == "activity"]
        filtered.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
    else:
        filtered = [n for n in built["items"] if n["feed"] == "for_you"]
        if category not in ("all", ""):
            filtered = [n for n in filtered if n["category"] == category]
    return {
        "success": True,
        "notifications": filtered[:limit],
        "unread_count": built["unread_count"],
        "total": len(filtered),
        "category_counts": built["category_counts"],
        "bucket_counts": built.get("bucket_counts", {}),
        "activity_count": built["activity_count"],
        "timed_out": built.get("timed_out", False),
    }


@router.get("/{user_id}/unread-count")
async def get_unread_count(user_id: str):
    try:
        built = await _get_full_feed(user_id)
        return {"count": built["unread_count"]}
    except Exception as e:
        logger.error(f"Unread count error for {user_id}: {e}")
        return {"count": 0}


def _split_ids(ids: list) -> tuple[list, list]:
    real = [i for i in ids if not str(i).startswith(VIRTUAL_PREFIXES) and ObjectId.is_valid(str(i))]
    virtual = [i for i in ids if str(i).startswith(VIRTUAL_PREFIXES)]
    return real, virtual


@router.post("/{user_id}/read")
async def mark_notifications_read(user_id: str, data: dict = None):
    db = get_db()
    ids = [str(i) for i in (data or {}).get("ids", [])]
    real, _ = _split_ids(ids)
    if real:
        await db.notifications.update_many({"_id": {"$in": [ObjectId(i) for i in real]}, "user_id": user_id}, {"$set": {"read": True}})
    if ids:
        await db.notification_reads.update_one({"user_id": user_id}, {"$addToSet": {"read_ids": {"$each": ids}}}, upsert=True)
    _notifications_cache.pop(user_id, None)
    return {"success": True, "message": "Marked as read"}


@router.post("/{user_id}/read-all")
async def mark_all_read(user_id: str):
    db = get_db()
    result = await db.notifications.update_many({"user_id": user_id, "read": {"$ne": True}}, {"$set": {"read": True}})
    built = await _get_full_feed(user_id)
    all_ids = [n["id"] for n in built["items"]]
    if all_ids:
        await db.notification_reads.update_one(
            {"user_id": user_id}, {"$addToSet": {"read_ids": {"$each": all_ids}}, "$set": {"last_cleared_at": datetime.now(timezone.utc)}}, upsert=True)
    _notifications_cache.pop(user_id, None)
    return {"success": True, "message": "All marked as read", "count": result.modified_count}


@router.post("/{user_id}/dismiss")
async def dismiss_notifications(user_id: str, data: dict = None):
    """Swipe-away: hides the alert. Tasks / threads themselves are untouched."""
    db = get_db()
    ids = [str(i) for i in (data or {}).get("ids", [])]
    real, virtual = _split_ids(ids)
    now = datetime.now(timezone.utc)
    if real:
        await db.notifications.update_many(
            {"_id": {"$in": [ObjectId(i) for i in real]}, "$or": [{"user_id": user_id}, {"user_id": None}]},
            {"$set": {"dismissed": True, "read": True, "dismissed_at": now, "dismissed_by": user_id}})
    if virtual:
        await db.notification_reads.update_one({"user_id": user_id}, {"$addToSet": {"dismissed_ids": {"$each": virtual}, "read_ids": {"$each": virtual}}}, upsert=True)
    _notifications_cache.pop(user_id, None)
    return {"success": True, "dismissed": len(real) + len(virtual)}


@router.post("/{user_id}/undismiss")
async def undismiss_notifications(user_id: str, data: dict = None):
    """Undo for a swipe."""
    db = get_db()
    ids = [str(i) for i in (data or {}).get("ids", [])]
    real, virtual = _split_ids(ids)
    if real:
        await db.notifications.update_many({"_id": {"$in": [ObjectId(i) for i in real]}, "$or": [{"user_id": user_id}, {"user_id": None}]},
                                           {"$set": {"dismissed": False}})
    if virtual:
        await db.notification_reads.update_one({"user_id": user_id}, {"$pull": {"dismissed_ids": {"$in": virtual}}})
    _notifications_cache.pop(user_id, None)
    return {"success": True, "restored": len(real) + len(virtual)}


@router.post("/{user_id}/clear-all")
async def clear_all(user_id: str):
    """Clear every alert on the screen. Returns the ids so the app can offer Undo."""
    db = get_db()
    built = await _get_full_feed(user_id)
    ids = [n["id"] for n in built["items"] if n["feed"] == "for_you"]
    real, virtual = _split_ids(ids)
    now = datetime.now(timezone.utc)
    if real:
        await db.notifications.update_many({"_id": {"$in": [ObjectId(i) for i in real]}},
                                           {"$set": {"dismissed": True, "read": True, "dismissed_at": now, "dismissed_by": user_id}})
    if virtual:
        await db.notification_reads.update_one({"user_id": user_id}, {"$addToSet": {"dismissed_ids": {"$each": virtual}, "read_ids": {"$each": virtual}}}, upsert=True)
    _notifications_cache.pop(user_id, None)
    return {"success": True, "cleared": len(ids), "ids": ids}
