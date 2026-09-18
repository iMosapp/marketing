"""Change feed -> outgoing webhooks. Runs every 60s from the scheduler.
Looks at what changed since the last run (contacts, messages, calls, timeline events, tasks), works out which store/org each
change belongs to, and delivers the matching events to that tenant's active subscriptions. No hooks in hot paths needed,
so every way data enters the app (rep, CSV, lead source, Twilio, Jessi, API) ends up in the CRM."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from routers.database import get_db
from routers.webhook_subscriptions import build_event, deliver, subscription_matches

logger = logging.getLogger(__name__)
CURSOR_ID = "webhook_outbox"
MAX_PER_COLLECTION = 2000

# contact_events.event_type -> webhook event
EVENT_MAP = {"note_added": "note.added", "purchase_added": "deal.closed", "task_completed": "task.completed",
             "appointment_created": "appointment.created", "review_submitted": "review.submitted",
             "campaign_enrolled": "campaign.enrolled", "campaign_completed": "campaign.completed"}


def _aware(d) -> Optional[datetime]:
    if not isinstance(d, datetime):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _in(d, since: datetime, until: datetime) -> bool:
    d = _aware(d)
    return bool(d and since < d <= until)


def contact_payload(c: dict) -> dict:
    return {
        "id": str(c["_id"]), "first_name": c.get("first_name"), "last_name": c.get("last_name"), "phone": c.get("phone"),
        "email": c.get("email") or c.get("email_work"), "tags": c.get("tags") or [], "source": c.get("source"),
        "external_id": c.get("external_id"), "external_ids": c.get("external_ids") or {}, "vehicle": c.get("vehicle"),
        "vehicle_interest": c.get("vehicle_interest"), "notes": c.get("notes"), "owner_user_id": c.get("user_id"),
        "store_id": c.get("store_id"), "status": c.get("status"), "date_sold": c.get("date_sold"),
        "purchase_history": c.get("purchase_history") or [], "photo_url": c.get("photo_url"),
        "created_at": c.get("created_at"), "updated_at": c.get("updated_at"),
    }


def message_payload(m: dict, contact_id: Optional[str]) -> dict:
    return {"id": str(m["_id"]), "contact_id": contact_id, "conversation_id": m.get("conversation_id"), "user_id": m.get("user_id") or m.get("sender_id"),
            "direction": m.get("direction") or ("inbound" if m.get("sender") == "contact" else "outbound"), "sender": m.get("sender"),
            "channel": m.get("channel") or m.get("mode") or "sms", "content": m.get("content"), "media_url": m.get("media_url"),
            "ai_generated": bool(m.get("ai_generated")), "status": m.get("status"), "timestamp": m.get("timestamp")}


def call_payload(c: dict) -> dict:
    return {"id": str(c["_id"]), "contact_id": c.get("contact_id"), "user_id": c.get("user_id"), "direction": c.get("direction"),
            "duration_s": c.get("duration_s"), "outcome": c.get("outcome"), "connected": c.get("connected"), "transcript": c.get("transcript"),
            "ai_summary": c.get("ai_summary"), "recording_url": c.get("recording_url"), "timestamp": c.get("created_at") or c.get("timestamp")}


async def _tenant_of_users(db, user_ids: set) -> dict:
    """user_id -> {store_id, organization_id}"""
    oids = [ObjectId(u) for u in user_ids if u and ObjectId.is_valid(u)]
    out = {}
    if oids:
        async for u in db.users.find({"_id": {"$in": oids}}, {"store_id": 1, "organization_id": 1}):
            out[str(u["_id"])] = {"store_id": u.get("store_id"), "organization_id": u.get("organization_id")}
    return out


async def collect_events(db, since: datetime, until: datetime) -> list:
    """Every (owner_user_id, store_id, event_type, payload) that happened in the window."""
    win = {"$gt": since, "$lte": until}
    out = []  # (user_id, store_id, event_type, payload)

    async for c in db.contacts.find({"$or": [{"created_at": win}, {"updated_at": win}, {"hidden_at": win}]}, {"photo": 0, "photo_thumbnail": 0}).limit(MAX_PER_COLLECTION):
        if c.get("status") == "merged":
            continue
        if _in(c.get("created_at"), since, until):
            ev = "contact.created"
        elif c.get("status") in ("hidden", "deleted") and _in(c.get("hidden_at") or c.get("updated_at"), since, until):
            ev = "contact.deleted"
        else:
            ev = "contact.updated"
        out.append((c.get("user_id"), c.get("store_id"), ev, contact_payload(c)))

    msgs = await db.messages.find({"timestamp": win}).limit(MAX_PER_COLLECTION).to_list(MAX_PER_COLLECTION)
    conv_ids = {m.get("conversation_id") for m in msgs if m.get("conversation_id") and ObjectId.is_valid(m.get("conversation_id"))}
    convs = {}
    if conv_ids:
        async for cv in db.conversations.find({"_id": {"$in": [ObjectId(i) for i in conv_ids]}}, {"user_id": 1, "contact_id": 1}):
            convs[str(cv["_id"])] = cv
    for m in msgs:
        cv = convs.get(m.get("conversation_id") or "", {})
        owner = m.get("user_id") or m.get("sender_id") or cv.get("user_id")
        if not owner:
            continue
        inbound = m.get("direction") == "inbound" or m.get("sender") == "contact"
        out.append((owner, None, "message.received" if inbound else "message.sent", message_payload(m, cv.get("contact_id") or m.get("contact_id"))))

    async for c in db.call_logs.find({"$or": [{"created_at": win}, {"timestamp": win}]}).limit(MAX_PER_COLLECTION):
        if c.get("user_id"):
            out.append((c["user_id"], None, "call.logged", call_payload(c)))

    async for e in db.contact_events.find({"timestamp": win}).limit(MAX_PER_COLLECTION):
        ev = EVENT_MAP.get(e.get("event_type") or "", "activity.logged")
        if ev == "activity.logged" and not e.get("contact_id"):
            continue
        payload = {"id": str(e["_id"]), "contact_id": e.get("contact_id"), "user_id": e.get("user_id"), "event_type": e.get("event_type"), "source": e.get("source"),
                   "title": e.get("title"), "description": e.get("description"), "metadata": e.get("metadata") or {}, "timestamp": e.get("timestamp")}
        out.append((e.get("user_id"), None, ev, payload))

    async for t in db.tasks.find({"$or": [{"created_at": win}, {"completed_at": win}]}).limit(MAX_PER_COLLECTION):
        ev = "task.created" if _in(t.get("created_at"), since, until) else "task.completed"
        payload = {"id": str(t["_id"]), "contact_id": t.get("contact_id"), "user_id": t.get("user_id"), "type": t.get("type"), "title": t.get("title"),
                   "due_date": t.get("due_date"), "priority": t.get("priority"), "status": t.get("status"), "source": t.get("source"),
                   "created_at": t.get("created_at"), "completed_at": t.get("completed_at")}
        out.append((t.get("user_id"), None, ev, payload))

    # Fill in store/org for owner-less rows (contacts owned directly by a store) and resolve users -> tenant
    tenants = await _tenant_of_users(db, {u for u, _, _, _ in out if u})
    resolved = []
    for user_id, store_id, ev, payload in out:
        t = tenants.get(user_id or "", {})
        sid = store_id or t.get("store_id")
        oid = t.get("organization_id")
        if not sid and not oid:
            continue
        resolved.append((sid, oid, ev, payload))
    return resolved


async def run_webhook_outbox(db=None, now: Optional[datetime] = None) -> dict:
    db = get_db() if db is None else db
    now = now or datetime.now(timezone.utc)
    cursor = await db.system_cursors.find_one({"_id": CURSOR_ID})
    since = _aware(cursor.get("last_run")) if cursor else None
    if not since or now - since > timedelta(hours=6):
        since = now - timedelta(minutes=2)  # first run / long outage: do not replay history into someone's CRM
    subs = await db.webhook_subscriptions.find({"is_active": True, "$or": [{"store_id": {"$nin": [None, ""]}}, {"organization_id": {"$nin": [None, ""]}}]}).to_list(500)
    delivered = 0
    if subs:
        events = await collect_events(db, since, now)
        jobs = []
        for store_id, org_id, ev, payload in events:
            for s in subs:
                if not subscription_matches(s, ev):
                    continue
                if s.get("store_id"):
                    hit = s["store_id"] == store_id
                else:
                    hit = bool(org_id) and s.get("organization_id") == org_id
                if hit:
                    jobs.append(deliver(db, s, build_event(ev, payload, {"store_id": store_id, "organization_id": org_id})))
        for i in range(0, len(jobs), 25):
            results = await asyncio.gather(*jobs[i:i + 25], return_exceptions=True)
            delivered += sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    await db.system_cursors.update_one({"_id": CURSOR_ID}, {"$set": {"last_run": now}}, upsert=True)
    if delivered:
        logger.info(f"[WebhookOutbox] delivered {delivered} events ({since.isoformat()} -> {now.isoformat()})")
    return {"since": since.isoformat(), "until": now.isoformat(), "subscriptions": len(subs), "delivered": delivered}
