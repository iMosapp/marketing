"""
One place to write Activity feed events for the lead pipeline and every outbound touch.
Everything here lands in contact_events, which powers the Activity tab and the contact timeline.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from utils.event_types import EVENT_META, get_event_label

logger = logging.getLogger(__name__)

TEXT_TYPES = {"sms_sent", "personal_sms", "mms_sent", "auto_text_sent", "ai_reply_sent", "campaign_step_sent",
              "just_tried_text", "customer_reply", "sms_failed"}
CALL_TYPES = {"call_placed", "outbound_call", "inbound_call", "call_outbound", "call_received", "lead_call_attempt",
              "lead_call_connected", "call_voicemail", "call_no_answer", "call_busy"}
# Customer-initiated views never stand in for a touch we sent
VIEW_TYPES_RE = "_(viewed|clicked|downloaded|submitted)$"


def _oid(v) -> Optional[ObjectId]:
    try:
        return ObjectId(str(v)) if v and ObjectId.is_valid(str(v)) else None
    except Exception:
        return None


def _preview(text: str, n: int = 140) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


async def log_activity(db, *, user_id: str, contact_id: str, event_type: str, description: str = "",
                       channel: Optional[str] = None, ref: Optional[str] = None, metadata: Optional[dict] = None,
                       timestamp: Optional[datetime] = None) -> Optional[str]:
    """Insert one contact_events row (idempotent on `ref`, e.g. a Twilio SID) and bump last_activity_at."""
    if not user_id or not _oid(contact_id):
        return None
    if ref and str(ref).startswith("MOCK_"):
        ref = None
    if ref and await db.contact_events.find_one({"ref": ref, "event_type": event_type}, {"_id": 1}):
        return None
    icon, color, category = EVENT_META.get(event_type, ("flag", "#8E8E93", "custom"))
    event = {
        "contact_id": str(contact_id),
        "user_id": str(user_id),
        "event_type": event_type,
        "title": get_event_label(event_type),
        "description": _preview(description),
        "icon": icon,
        "color": color,
        "category": category,
        "timestamp": timestamp or datetime.now(timezone.utc),
    }
    if channel:
        event["channel"] = channel
    if ref:
        event["ref"] = ref
    if metadata:
        event["metadata"] = metadata
    try:
        res = await db.contact_events.insert_one(event)
        await db.contacts.update_one({"_id": _oid(contact_id), "last_activity_at": {"$not": {"$gt": event["timestamp"]}}},
                                     {"$set": {"last_activity_at": event["timestamp"]}})
        return str(res.inserted_id)
    except Exception as e:
        logger.warning(f"[Activity] log {event_type} failed for contact {contact_id}: {e}")
        return None


async def owner_for_contact(db, contact_id: str, fallback: str = "") -> str:
    c = await db.contacts.find_one({"_id": _oid(contact_id)}, {"user_id": 1}) if _oid(contact_id) else None
    return str((c or {}).get("user_id") or fallback or "")


async def contact_for_conversation(db, conversation_id: str) -> tuple[str, str]:
    """(contact_id, user_id) for a conversation, empty strings when unknown."""
    conv = await db.conversations.find_one({"_id": _oid(conversation_id)}, {"contact_id": 1, "user_id": 1, "assigned_to": 1}) if _oid(conversation_id) else None
    if not conv:
        return "", ""
    return str(conv.get("contact_id") or ""), str(conv.get("assigned_to") or conv.get("user_id") or "")


async def on_lead_claimed(db, *, contact_id: str, user_id: str, via: str = "app", previous_owner: Optional[str] = None,
                          event_type: str = "lead_claimed", note: str = "") -> None:
    """A rep now owns this lead: move the lead's queue-time history onto the rep's feed and log the claim."""
    if not _oid(contact_id) or not user_id:
        return
    try:
        # Only queue-time history moves (store / org owned rows). Another rep's own touches stay on their feed.
        prev = {""}
        if previous_owner and _oid(previous_owner) and not await db.users.find_one({"_id": _oid(previous_owner)}, {"_id": 1}):
            prev.add(previous_owner)
        contact = await db.contacts.find_one({"_id": _oid(contact_id)}, {"store_id": 1, "organization_id": 1, "user_id": 1})
        rep = await db.users.find_one({"_id": _oid(user_id)}, {"store_id": 1, "organization_id": 1}) if _oid(user_id) else None
        for doc in (contact, rep):
            for k in ("store_id", "organization_id"):
                if (doc or {}).get(k):
                    prev.add(str(doc[k]))
        prev.discard(str(user_id))
        await db.contact_events.update_many(
            {"contact_id": str(contact_id), "user_id": {"$in": list(prev)}},
            {"$set": {"user_id": str(user_id)}},
        )
        pretty = {"phone": "by phone", "app": "in the app", "reassigned": "by a manager", "chat": "from chat"}.get(via, via)
        await log_activity(db, user_id=user_id, contact_id=contact_id, event_type=event_type,
                           description=(note or f"Claimed {pretty}"), metadata={"via": via})
    except Exception as e:
        logger.warning(f"[Activity] on_lead_claimed failed for {contact_id}: {e}")


# ── One-time backfill so leads, texts and calls that predate this logging show up ──────────

def _as_dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00").replace(" ", "T")).astimezone(timezone.utc)
        except Exception:
            return None
    return None


async def _has_nearby(db, contact_id: str, types: Optional[set], at: datetime, window_s: int = 120) -> bool:
    """Any event of `types` (or any non-view event when types is None) within the window."""
    q = {"contact_id": contact_id, "timestamp": {"$gte": at - timedelta(seconds=window_s), "$lte": at + timedelta(seconds=window_s)}}
    q["event_type"] = {"$in": list(types)} if types else {"$not": {"$regex": VIEW_TYPES_RE}}
    return await db.contact_events.find_one(q, {"_id": 1}) is not None


async def backfill_activity(db, days: int = 90) -> dict:
    """Create missing events for inbound leads, texts and calls from the last `days`. Safe to re-run."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = {"leads": 0, "texts": 0, "calls": 0}
    conv_cache: dict = {}

    async def conv_info(cid: str):
        if cid not in conv_cache:
            conv_cache[cid] = await contact_for_conversation(db, cid)
        return conv_cache[cid]

    async for lead in db.inbound_leads.find({"created_at": {"$gte": since}}, {"contact_id": 1, "source_name": 1, "vehicle_interest": 1, "is_new_contact": 1, "created_at": 1, "assigned_to": 1}):
        cid = str(lead.get("contact_id") or "")
        if not _oid(cid) or await db.contact_events.find_one({"contact_id": cid, "event_type": {"$in": ["new_lead", "returning_lead"]}}, {"_id": 1}):
            continue
        owner = await owner_for_contact(db, cid, str(lead.get("assigned_to") or ""))
        et = "new_lead" if lead.get("is_new_contact", True) else "returning_lead"
        desc = " · ".join(filter(None, [lead.get("source_name"), lead.get("vehicle_interest") or "New inquiry"]))
        if await log_activity(db, user_id=owner, contact_id=cid, event_type=et, description=desc, timestamp=_as_dt(lead.get("created_at"))):
            out["leads"] += 1

    q = {"timestamp": {"$gte": since}, "channel": {"$in": ["sms", "sms_personal", "mms", "voice", None]}}
    async for m in db.messages.find(q, {"conversation_id": 1, "contact_id": 1, "user_id": 1, "content": 1, "direction": 1, "sender": 1, "channel": 1, "type": 1, "twilio_sid": 1, "timestamp": 1, "ai_generated": 1}).sort("timestamp", 1):
        at = _as_dt(m.get("timestamp"))
        if not at:
            continue
        cid, conv_owner = str(m.get("contact_id") or ""), ""
        if not _oid(cid) and m.get("conversation_id"):
            cid, conv_owner = await conv_info(str(m["conversation_id"]))
        if not _oid(cid):
            continue
        inbound = m.get("direction") == "inbound" or m.get("sender") in ("contact", "customer")
        if m.get("sender") == "system" or m.get("direction") == "system":
            continue
        is_call = m.get("channel") == "voice" or m.get("type") == "call_log"
        if await _has_nearby(db, cid, CALL_TYPES if is_call else None, at):
            continue
        owner = str(m.get("user_id") or conv_owner or await owner_for_contact(db, cid))
        if is_call:
            et = "inbound_call" if inbound else "outbound_call"
        elif inbound:
            et = "customer_reply"
        elif m.get("sender") == "ai" or m.get("ai_generated"):
            et = "ai_reply_sent"
        else:
            et = "sms_sent"
        if await log_activity(db, user_id=owner, contact_id=cid, event_type=et, description=m.get("content") or "", channel="sms",
                              ref=m.get("twilio_sid"), timestamp=at):
            out["calls" if is_call else "texts"] += 1

    for coll, dir_key in (("calls", "type"), ("call_logs", "direction")):
        async for c in db[coll].find({"timestamp": {"$gte": since}}, {"contact_id": 1, "user_id": 1, dir_key: 1, "timestamp": 1, "duration": 1, "duration_s": 1, "call_sid": 1}):
            at, cid = _as_dt(c.get("timestamp")), str(c.get("contact_id") or "")
            if not at or not _oid(cid) or await _has_nearby(db, cid, CALL_TYPES, at):
                continue
            inbound = (c.get(dir_key) or "outbound") == "inbound"
            dur = c.get("duration_s") or c.get("duration")
            desc = f"{int(float(dur))}s" if dur not in (None, "", "0", 0) else ""
            if await log_activity(db, user_id=str(c.get("user_id") or await owner_for_contact(db, cid)), contact_id=cid,
                                  event_type="inbound_call" if inbound else "outbound_call", description=desc, ref=c.get("call_sid"), timestamp=at):
                out["calls"] += 1
    logger.info(f"[Activity] backfill done: {out}")
    return out


async def run_backfill_once(db, name: str = "activity_backfill_v1") -> None:
    if await db.migrations.find_one({"name": name}):
        return
    await db.migrations.insert_one({"name": name, "started_at": datetime.now(timezone.utc)})
    try:
        result = await backfill_activity(db)
        await db.migrations.update_one({"name": name}, {"$set": {"done_at": datetime.now(timezone.utc), "result": result}})
    except Exception as e:
        logger.warning(f"[Activity] backfill failed: {e}")
        await db.migrations.delete_one({"name": name})
