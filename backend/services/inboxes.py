"""
Shared inboxes: one department number (Sales, Service, Parts, BDC, "Buyers"...) worked by many reps.

Rules (agreed with the owner):
  * A thread that arrives on a shared number stays on that number while it is worked, even after a rep claims it.
    Replies (rep, Jessi, campaigns) go out from the inbox number. Reassigning never changes the customer's number.
  * When the inbox's close tag (default "Sold") is applied, the thread "graduates" per the inbox's `after_close`
    rule: `move_to_rep` -> the rep's own number (bridge text), or `stay` -> keeps the shared number forever.
  * Known customers of an active rep keep texting that rep's existing thread on its current number.
  * Personal threads have no inbox (`inbox_id` = None). Nothing about them changes.
  * Owner gets every alert; collaborators are pushed only when the owner is silent 15 min or off shift.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

COLL = "shared_inboxes"
ROUTING = ("jump_ball", "round_robin", "weighted_round_robin")
AFTER_CLOSE = ("move_to_rep", "stay")
AI_MODES = ("auto_reply", "auto_with_approval", "draft_only", "off")
DEFAULT_CLOSE_TAG = "Sold"
DEFAULT_BRIDGE_TEXT = "Hi {first_name}, it's {rep_name}. This is my direct line, save it and text me here anytime."
MANAGER_ROLES = ("super_admin", "org_admin", "store_manager", "admin", "manager")
OWNER_SILENT_MINUTES = 15

_STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}


def _oid(v):
    try:
        return ObjectId(str(v))
    except Exception:
        return None


def _now():
    return datetime.now(timezone.utc)


def _norm(phone: str) -> str:
    from services.twilio_service import normalize_phone
    return normalize_phone(phone or "") if phone else ""


def members(inbox: dict) -> list:
    return [str(u) for u in (inbox or {}).get("assigned_user_ids") or [] if u]


def serialize(inbox: dict) -> dict:
    return {
        "id": str(inbox["_id"]),
        "name": inbox.get("name") or "Inbox",
        "description": inbox.get("description") or "",
        "phone_number": inbox.get("phone_number") or "",
        "members": members(inbox),
        "member_weights": inbox.get("member_weights") or {},
        "routing": inbox.get("routing") or "jump_ball",
        "daily_cap": inbox.get("daily_cap") or 0,
        "first_reply": inbox.get("first_reply") or inbox.get("intake_text") or "",
        "after_close": inbox.get("after_close") or "move_to_rep",
        "close_tag": inbox.get("close_tag") or DEFAULT_CLOSE_TAG,
        "bridge_text": inbox.get("bridge_text") or DEFAULT_BRIDGE_TEXT,
        "ai_mode": inbox.get("ai_mode") or "auto_reply",
        "va_profile_id": inbox.get("va_profile_id") or None,
        "va_name": inbox.get("va_name") or "",
        "va_training": inbox.get("va_training") or "",
        "va_rules": inbox.get("va_rules") or "",
        "va_handoff_rules": inbox.get("va_handoff_rules") or "",
        "va_prompt_override": inbox.get("va_prompt_override") or "",
        "color": inbox.get("color") or "#C9A962",
        "icon": inbox.get("icon") or "chatbubbles",
        "store_id": inbox.get("store_id"),
        "organization_id": inbox.get("organization_id"),
        "is_active": inbox.get("is_active", True),
        "direct_source_id": inbox.get("direct_source_id"),
        "receives_demo_requests": bool(inbox.get("receives_demo_requests")),
        "created_at": inbox["created_at"].isoformat() if hasattr(inbox.get("created_at"), "isoformat") else inbox.get("created_at"),
    }


async def get_inbox(db, inbox_id) -> Optional[dict]:
    oid = _oid(inbox_id)
    return await db[COLL].find_one({"_id": oid}) if oid else None


def number_variants(phone: str) -> list:
    p = _norm(phone)
    if not p:
        return []
    return list({p, p.lstrip("+"), p[2:] if p.startswith("+1") else p})


async def inbox_by_number(db, phone: str) -> Optional[dict]:
    """The shared inbox that owns this Twilio number, any stored format."""
    variants = number_variants(phone)
    if not variants:
        return None
    return await db[COLL].find_one({"phone_number": {"$in": variants}, "is_active": {"$ne": False}})


def _scope_store_ids(user: dict) -> list:
    return [str(s) for s in ([user.get("store_id")] + list(user.get("store_ids") or [])) if s]


async def inboxes_for_user(db, user: dict) -> list:
    """Inboxes a user can see: members see theirs, managers see every inbox in their store(s)/org."""
    role = user.get("role")
    uid = str(user["_id"])
    if role == "super_admin":
        q: dict = {}
    elif role == "org_admin" and user.get("organization_id"):
        q = {"$or": [{"organization_id": user["organization_id"]}, {"assigned_user_ids": uid}]}
    elif role in ("store_manager", "admin", "manager"):
        stores = _scope_store_ids(user)
        q = {"$or": [{"store_id": {"$in": stores}}, {"assigned_user_ids": uid}]} if stores else {"assigned_user_ids": uid}
    else:
        q = {"assigned_user_ids": uid}
    q["is_active"] = {"$ne": False}
    return await db[COLL].find(q).sort("name", 1).to_list(100)


async def member_inbox_ids(db, user_id: str) -> list:
    rows = await db[COLL].find({"assigned_user_ids": str(user_id), "is_active": {"$ne": False}}, {"_id": 1}).to_list(100)
    return [str(r["_id"]) for r in rows]


def is_manager(user: dict) -> bool:
    return (user or {}).get("role") in MANAGER_ROLES


def can_manage_inbox(user: dict, inbox: dict) -> bool:
    role = (user or {}).get("role")
    if role == "super_admin":
        return True
    if role == "org_admin":
        return not inbox.get("organization_id") or str(inbox.get("organization_id")) == str(user.get("organization_id") or "")
    if role in ("store_manager", "admin", "manager"):
        return not inbox.get("store_id") or str(inbox.get("store_id")) in _scope_store_ids(user)
    return False


async def access_filter(db, user_id: str, base: Optional[dict] = None) -> dict:
    """Conversations a user may open: their own (base), threads assigned to them, threads shared with them,
    and unclaimed threads in inboxes they belong to."""
    ors = [base or {"user_id": user_id}, {"assigned_to": user_id}, {"collaborators": user_id}]
    ids = await member_inbox_ids(db, user_id)
    if ids:
        ors.append({"inbox_id": {"$in": ids}, "graduated_at": None, "$or": [{"assigned_to": None}, {"assigned_to": {"$exists": False}}]})
    return {"$or": ors}


async def counts(db, inbox_ids: list, user_id: str) -> dict:
    """{inbox_id: {unassigned, mine, open, unread}} over live (not graduated) threads."""
    out = {i: {"unassigned": 0, "mine": 0, "open": 0, "unread": 0} for i in inbox_ids}
    if not inbox_ids:
        return out
    async for row in db.conversations.aggregate([
        {"$match": {"inbox_id": {"$in": inbox_ids}, "graduated_at": None, "status": {"$nin": ["closed", "archived"]}}},
        {"$group": {"_id": "$inbox_id", "open": {"$sum": 1},
                    "unassigned": {"$sum": {"$cond": [{"$in": [{"$ifNull": ["$assigned_to", None]}, [None, ""]]}, 1, 0]}},
                    "mine": {"$sum": {"$cond": [{"$eq": ["$assigned_to", user_id]}, 1, 0]}},
                    "unread": {"$sum": {"$cond": [{"$eq": ["$unread", True]}, 1, 0]}}}},
    ]):
        if row["_id"] in out:
            out[row["_id"]] = {"open": row["open"], "unassigned": row["unassigned"], "mine": row["mine"], "unread": row.get("unread", 0)}
    return out


# ── Lead-source inheritance ───────────────────────────────────────────────────

async def inbox_for_source(db, source: Optional[dict]) -> Optional[dict]:
    """The lead-source screen stores the shared inbox in `team_id` (legacy Teams were never built); `inbox_id` is explicit."""
    if not source:
        return None
    for key in ("inbox_id", "team_id"):
        if source.get(key) and _oid(source[key]):
            inbox = await get_inbox(db, source[key])
            if inbox and inbox.get("is_active") is not False:
                return inbox
    return None


async def apply_inbox(db, source: Optional[dict]) -> Optional[dict]:
    """A lead source pointed at an inbox inherits its members, routing, first reply and number.
    Fields set on the source itself win (per-source overrides)."""
    inbox = await inbox_for_source(db, source)
    if not inbox:
        return source
    merged = dict(source)
    merged["inbox_id"] = str(inbox["_id"])
    merged["inbox_name"] = inbox.get("name")
    merged["inbox_phone_number"] = _norm(inbox.get("phone_number")) if inbox.get("phone_number") else ""
    if not merged.get("workflow_user_ids"):
        merged["workflow_user_ids"] = members(inbox)
    if not source.get("assignment_method_override"):
        merged["assignment_method"] = inbox.get("routing") or source.get("assignment_method") or "jump_ball"
    if merged["assignment_method"] != "jump_ball":
        merged["notify_all_on_intake"] = False      # the routed rep gets the New Lead push; no "tap to claim" blast
    if not (source.get("intake_text") or "").strip():
        merged["intake_text"] = inbox.get("first_reply") or inbox.get("intake_text") or ""
    if not source.get("member_weights"):
        merged["member_weights"] = inbox.get("member_weights") or {}
    if not source.get("daily_cap"):
        merged["daily_cap"] = inbox.get("daily_cap") or 0
    if not merged.get("va_profile_id"):
        merged["va_profile_id"] = inbox.get("va_profile_id")
    if not merged.get("store_id") and inbox.get("store_id"):
        merged["store_id"] = inbox["store_id"]
    if source.get("va_enabled") is None and (inbox.get("ai_mode") or "auto_reply") == "off":
        merged["va_enabled"] = False
    return merged


async def ensure_direct_source(db, inbox: dict) -> dict:
    """Every inbox owns one built-in lead source for texts straight to its number (consumer-initiated: no texting window)."""
    inbox_id = str(inbox["_id"])
    routing = inbox.get("routing") or "jump_ball"
    doc = {
        "name": inbox.get("name") or "Inbox",
        "kind": "inbox_direct",
        "inbox_id": inbox_id,
        "store_id": inbox.get("store_id"),
        "organization_id": inbox.get("organization_id"),
        "workflow_user_ids": members(inbox),
        "assignment_method": routing,
        "member_weights": inbox.get("member_weights") or {},
        "daily_cap": inbox.get("daily_cap") or 0,
        "intake_text": inbox.get("first_reply") or inbox.get("intake_text") or "",
        "contact_mode": "text_only",
        "notify_all_on_intake": routing == "jump_ball",
        "va_enabled": (inbox.get("ai_mode") or "auto_reply") != "off",
        "va_profile_id": inbox.get("va_profile_id"),
        "text_window_start": "00:00",
        "text_window_end": "00:00",
        "is_active": inbox.get("is_active", True),
        "updated_at": _now().isoformat(),
    }
    existing = await db.lead_sources.find_one({"kind": "inbox_direct", "inbox_id": inbox_id})
    if existing:
        await db.lead_sources.update_one({"_id": existing["_id"]}, {"$set": doc})
        src = {**existing, **doc}
    else:
        doc["created_at"] = _now().isoformat()
        doc["lead_count"] = 0
        res = await db.lead_sources.insert_one(doc)
        src = {**doc, "_id": res.inserted_id}
    if inbox.get("direct_source_id") != str(src["_id"]):
        await db[COLL].update_one({"_id": inbox["_id"]}, {"$set": {"direct_source_id": str(src["_id"])}})
    return src


# ── Assignment engine ─────────────────────────────────────────────────────────

async def _assigned_today(db, user_ids: list) -> dict:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    out = {u: 0 for u in user_ids}
    async for row in db.inbound_leads.aggregate([
        {"$match": {"assigned_to": {"$in": user_ids}, "created_at": {"$gte": start}}},
        {"$group": {"_id": "$assigned_to", "n": {"$sum": 1}}},
    ]):
        out[row["_id"]] = row["n"]
    return out


async def pick_assignee(db, source: dict) -> Optional[str]:
    """Round robin / weighted round robin over the source's pool (its inbox members or workflow reps).
    Jump ball returns None (nobody until someone claims). Prefers on-shift reps, honours the daily cap."""
    method = source.get("assignment_method") or "jump_ball"
    if method == "jump_ball":
        return None
    pool = [str(u) for u in (source.get("workflow_user_ids") or []) if u]
    if not pool and source.get("team_id") and _oid(source["team_id"]):
        team = await db.teams.find_one({"_id": _oid(source["team_id"])})
        pool = [str(u) for u in (team or {}).get("members") or []]
    if not pool:
        return None
    from routers.lead_intake import _get_on_shift_reps
    candidates = await _get_on_shift_reps(pool, fallback_all=True) or pool
    cap = int(source.get("daily_cap") or 0)
    if cap > 0:
        today = await _assigned_today(db, candidates)
        under = [u for u in candidates if today.get(u, 0) < cap]
        candidates = under or candidates
    key = {"_id": source["_id"]} if source.get("_id") else None
    if method == "round_robin":
        idx = int(source.get("round_robin_index") or 0)
        user_id = candidates[idx % len(candidates)]
        if key:
            await db.lead_sources.update_one(key, {"$set": {"round_robin_index": (idx + 1) % max(len(pool), 1)}})
        return user_id
    if method == "weighted_round_robin":
        counts_ = dict(source.get("member_lead_counts") or {})
        weights = source.get("member_weights") or {}

        def score(u):
            w = float(weights.get(u) or 1) or 1.0
            return counts_.get(u, 0) / w
        user_id = min(candidates, key=score)
        counts_[user_id] = counts_.get(user_id, 0) + 1
        if key:
            await db.lead_sources.update_one(key, {"$set": {"member_lead_counts": counts_}})
        return user_id
    return None


# ── Outbound number resolution ────────────────────────────────────────────────

def thread_from_number(conv: Optional[dict]) -> Optional[str]:
    """Shared inbox number while the thread lives in an inbox (not graduated)."""
    if conv and conv.get("inbox_id") and not conv.get("graduated_at") and conv.get("rep_phone"):
        return conv["rep_phone"]
    return None


async def resolve_from_number(db, user_id: Optional[str], conversation: Optional[dict] = None,
                              contact_id: Optional[str] = None) -> Optional[str]:
    """Which number an outbound text comes from: the inbox number for inbox threads, else the rep's own."""
    conv = conversation
    if conv is None and contact_id:
        q: dict = {"contact_id": str(contact_id), "inbox_id": {"$nin": [None, ""]}, "graduated_at": None}
        if user_id:
            q["$or"] = [{"user_id": user_id}, {"assigned_to": user_id}]
        conv = await db.conversations.find_one(q, sort=[("last_message_at", -1)])
    n = thread_from_number(conv)
    if n:
        return n
    if not user_id or not _oid(user_id):
        return None
    from services.twilio_service import get_rep_twilio_number
    return await get_rep_twilio_number(user_id)


async def inbox_context(db, conversation: Optional[dict]) -> Optional[dict]:
    """{inbox, from_number, members, va_profile} for a thread that lives in a shared inbox."""
    if not conversation or not conversation.get("inbox_id") or conversation.get("graduated_at"):
        return None
    inbox = await get_inbox(db, conversation["inbox_id"])
    if not inbox:
        return None
    va = None
    if inbox.get("va_profile_id") and _oid(inbox["va_profile_id"]):
        va = await db.ai_va_profiles.find_one({"_id": _oid(inbox["va_profile_id"])})
    return {"inbox": inbox, "from_number": _norm(inbox.get("phone_number")) or conversation.get("rep_phone"),
            "members": members(inbox), "va_profile": va}


def build_inbox_va_prompt(inbox: dict, va: Optional[dict], store: Optional[dict]) -> str:
    """System prompt for the department assistant while a shared-inbox thread is unassigned."""
    name = (va or {}).get("name") or (inbox.get("va_name") if inbox else None) or "Jessi"
    dept = inbox.get("name") or "our team"
    store_name = (store or {}).get("name") or "the store"
    lines = [
        f"You are {name}, the {dept} assistant for {store_name}, texting a customer from the shared {dept} line.",
        "Write like a real person texting: short, warm, one question at a time, no bullet points, no signatures, no emojis unless the customer uses them.",
        f"Goal: understand what they need and either answer it or get the details a {dept} teammate needs, then let them know a teammate will follow up shortly.",
        "Never invent prices, availability, appointment times or policies. If you don't know, say a teammate will confirm.",
        "Do not pretend to be a specific salesperson; you are the team's assistant until someone picks this up.",
    ]
    if (va or {}).get("tagline"):
        lines.append(f"Your style: {va['tagline']}")
    if (va or {}).get("bio"):
        lines.append(f"About you: {va['bio']}")
    if (va or {}).get("specialties"):
        specs = va["specialties"] if isinstance(va["specialties"], list) else [va["specialties"]]
        lines.append("You know about: " + ", ".join(str(s) for s in specs))
    for key, label in (("goal", "Outcome you're working toward"), ("training", "Training notes"), ("rules", "Rules you must follow"),
                       ("handoff_rules", "Hand to a human when"), ("data_capture", "Always collect")):
        val = (va or {}).get(key) or inbox.get(f"va_{key}")
        if val:
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            lines.append(f"{label}: {val}")
    if inbox.get("va_prompt_override"):
        lines.append(inbox["va_prompt_override"])
    return "\n".join(lines)


# ── Inbound text to a shared number ───────────────────────────────────────────

async def _enrich_name(db, phone: str) -> tuple:
    from services.contact_match import phone_clause, NOT_MERGED
    pc = phone_clause(phone) or {"phone": phone}
    any_contact = await db.contacts.find_one(
        {**pc, "status": NOT_MERGED, "name": {"$nin": ["Contact", "Unknown", "New Lead", "", None], "$not": {"$regex": "^Lead \\("}}},
        {"first_name": 1, "last_name": 1, "name": 1})
    if any_contact and any_contact.get("name"):
        first = any_contact.get("first_name") or any_contact["name"].split()[0]
        last = any_contact.get("last_name") or " ".join(any_contact["name"].split()[1:])
        return first, last
    return "Lead", f"({phone[-4:]})"


async def _rep_line(db, user_id) -> tuple:
    """(user doc, their own Twilio number) for an active rep, else (None, '')."""
    rep = await db.users.find_one({"_id": _oid(user_id), "status": {"$ne": "deactivated"}, "active": {"$ne": False}}) if _oid(user_id) else None
    number = _norm((rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number") or "")
    return rep, number


async def _existing_owner(db, inbox: dict, from_phone: str) -> tuple:
    """A known customer of an active rep in this store keeps texting that rep's own line (existing threads keep their number)."""
    from services.contact_match import find_existing_contact
    store_id = str(inbox.get("store_id") or "")
    contact, how, _ = await find_existing_contact(db, from_phone, "", "", "", store_id, extra_owner_ids=members(inbox))
    if not contact or how != "phone":
        return None, ""
    owner = str(contact.get("user_id") or "")
    if not owner or owner == store_id:
        return None, ""
    rep, number = await _rep_line(db, owner)
    if not rep or not number:
        return None, ""
    if store_id and str(rep.get("store_id") or "") != store_id and owner not in members(inbox):
        return None, ""
    return rep, number


async def notify_members(db, inbox: dict, conv_id: str, contact_id: Optional[str], title: str, body: str,
                         exclude: Optional[str] = None, sound: bool = True, only: Optional[list] = None,
                         notif_type: str = "inbox_message"):
    from routers.lead_intake import _get_on_shift_reps
    ids = [m for m in (only if only is not None else members(inbox)) if m != exclude]
    if not ids:
        return []
    recipients = await _get_on_shift_reps(ids, fallback_all=True) or ids
    now = _now()
    await db.notifications.insert_many([{
        "user_id": uid, "type": notif_type, "priority": "urgent" if sound else "normal",
        "title": title, "message": body, "conversation_id": conv_id, "contact_id": contact_id,
        "inbox_id": str(inbox["_id"]), "read": False, "dismissed": False, "created_at": now,
    } for uid in recipients])
    try:
        from routers.push_notifications import send_push_to_user, LEAD_SOUND, LEAD_CHANNEL
        for uid in recipients:
            kwargs = {"sound": LEAD_SOUND, "channel_id": LEAD_CHANNEL} if sound else {}
            asyncio.create_task(send_push_to_user(uid, title, body, f"/thread/{conv_id}", "chatbubbles", **kwargs))
    except Exception as e:
        logger.debug(f"[Inbox] push failed: {e}")
    return recipients


async def handle_inbound(db, inbox: dict, from_phone: str, body: str, media_urls: list, media_types: list,
                         message_sid: str) -> dict:
    """Text to a shared number.
    Returns {"handled": True} when fully processed here (unassigned thread), or
    {"rep_user": <user doc>, "to_phone": <number>} to continue the normal rep pipeline (assigned / graduated / known customer)."""
    inbox_number = _norm(inbox.get("phone_number"))
    inbox_id = str(inbox["_id"])
    conv = await db.conversations.find_one({"rep_phone": inbox_number, "contact_phone": from_phone, "graduated_at": None},
                                           sort=[("last_message_at", -1)])
    if conv and conv.get("assigned_to"):
        rep, _ = await _rep_line(db, conv["assigned_to"])
        if rep:
            return {"rep_user": rep, "to_phone": inbox_number}
    if not conv:
        grad = await db.conversations.find_one({"from_inbox_id": inbox_id, "contact_phone": from_phone, "graduated_at": {"$ne": None}},
                                               sort=[("last_message_at", -1)])
        if grad:
            rep, rep_number = await _rep_line(db, grad.get("assigned_to") or grad.get("user_id"))
            if rep and rep_number:
                logger.info(f"[Inbox] {from_phone} texted {inbox.get('name')} after graduating; routing to {rep.get('name')}'s line")
                return {"rep_user": rep, "to_phone": rep_number}
        rep, rep_number = await _existing_owner(db, inbox, from_phone)
        if rep:
            logger.info(f"[Inbox] {from_phone} is {rep.get('name')}'s customer; keeping their existing thread on {rep_number}")
            return {"rep_user": rep, "to_phone": rep_number}

    now = _now()
    is_new = conv is None
    is_stop = (body or "").strip().lower() in _STOP_WORDS
    if is_new and is_stop:
        from services.contact_match import phone_clause
        pc = phone_clause(from_phone) or {"phone": from_phone}
        await db.contacts.update_many(pc, {"$set": {"sms_opt_out": True, "sms_opt_out_at": now}})
        return {"handled": True}

    if is_new:
        source = await ensure_direct_source(db, inbox)
        first, last = await _enrich_name(db, from_phone)
        normalized = {"first_name": first, "last_name": last, "phone": from_phone, "comments": body or "",
                      "source_name": inbox.get("name") or "Inbox", "channel": "sms"}
        from routers.lead_intake import process_inbound_lead
        res = await process_inbound_lead(normalized, source, db, raw_body=body or "")
        conv_id, contact_id = res["conversation_id"], res["contact_id"]
        conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
        if conv and conv.get("routing_kind") == "returning_owner" and conv.get("assigned_to"):
            rep, rep_number = await _rep_line(db, conv["assigned_to"])
            if rep and rep_number and conv.get("rep_phone") and _norm(conv["rep_phone"]) != inbox_number:
                return {"rep_user": rep, "to_phone": _norm(conv["rep_phone"])}
        await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": {
            "inbox_id": inbox_id, "inbox_name": inbox.get("name"), "rep_phone": inbox_number}})
    else:
        conv_id, contact_id = str(conv["_id"]), conv.get("contact_id")
        if not conv.get("inbox_id"):
            await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"inbox_id": inbox_id, "inbox_name": inbox.get("name")}})

    message = {"conversation_id": conv_id, "content": body or "", "sender": "contact", "timestamp": datetime.utcnow(),
               "status": "received", "twilio_sid": message_sid, "from_phone": from_phone, "to_phone": inbox_number}
    if media_urls:
        message.update({"media_urls": media_urls, "media_types": media_types, "has_media": True, "num_media": len(media_urls)})
    await db.messages.insert_one(message)
    preview = (body or "").strip()[:100] or "(photo)"
    await db.conversations.update_one({"_id": ObjectId(conv_id)}, {
        "$set": {"last_message": preview, "last_message_at": datetime.utcnow(), "last_message_from": "contact", "unread": True,
                 "status": "active", "updated_at": now.isoformat()},
        "$inc": {"unread_count": 1, "unanswered_customer_replies": 1},
    })

    if is_stop and contact_id and _oid(contact_id):
        await db.contacts.update_one({"_id": _oid(contact_id)}, {"$set": {"sms_opt_out": True, "sms_opt_out_at": now}})
        await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": {"ai_mode": "off", "sms_opt_out": True}})
        await db.ai_reply_queue.update_many({"conversation_id": conv_id, "status": "pending"},
                                            {"$set": {"status": "cancelled", "cancel_reason": "contact_opted_out"}})

    contact_name = (conv or {}).get("contact_name") or from_phone
    if not is_new:
        assignee = (conv or {}).get("assigned_to")
        if assignee and _oid(assignee):
            # Round-robin lead whose rep got deactivated: back to the whole team
            await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": {"assigned_to": None, "claimed": False, "claimed_by": None}})
        await notify_members(db, inbox, conv_id, contact_id,
                             f"{inbox.get('name') or 'Inbox'}: {contact_name}", f"{preview} · Tap to claim")
    try:
        from websocket_manager import manager as ws_manager
        await ws_manager.send_to_users(members(inbox), {"type": "new_customer_message", "conversation_id": conv_id,
                                                        "contact_name": contact_name, "contact_phone": from_phone,
                                                        "message_preview": preview, "inbox_id": inbox_id})
    except Exception:
        pass

    conv_mode = ((conv or {}).get("ai_mode") or "").strip()
    inbox_mode = inbox.get("ai_mode") or "auto_reply"
    mode = conv_mode if conv_mode in ("auto_reply", "auto_with_approval", "draft_only", "off") else inbox_mode
    if (conv or {}).get("ai_enabled") is False and conv_mode not in ("auto_reply", "auto_with_approval", "draft_only"):
        mode = "off"
    if not is_new and not is_stop and mode != "off" and (body or "").strip():
        try:
            from routers.ai_reply import queue_ai_reply
            asyncio.create_task(queue_ai_reply(
                contact_id=str(contact_id or ""), conversation_id=conv_id, enrollment_id="conversation_direct", campaign_id="",
                assigned_user_id=None, incoming_message=body, ai_assist_mode=mode))
        except Exception as e:
            logger.warning(f"[Inbox] VA reply failed to queue: {e}")
    return {"handled": True}


# ── Collaborators: pushed only when the owner is silent or off shift ─────────

async def _owner_away(db, owner_id: str, conv: dict) -> Optional[str]:
    """'off_shift' / 'silent' when the owner should not be relied on right now, else None."""
    try:
        from routers.user_schedule import is_user_available
        if not await is_user_available(owner_id):
            return "off_shift"
    except Exception:
        pass
    last_contact = conv.get("last_message_at")
    last_rep = conv.get("rep_last_replied_at")
    if isinstance(last_contact, datetime):
        if last_contact.tzinfo is None:
            last_contact = last_contact.replace(tzinfo=timezone.utc)
        if isinstance(last_rep, datetime) and (last_rep.replace(tzinfo=timezone.utc) if last_rep.tzinfo is None else last_rep) >= last_contact:
            return None
        if _now() - last_contact >= timedelta(minutes=OWNER_SILENT_MINUTES):
            return "silent"
    return None


async def _push_collaborators(db, conv: dict, reason: str):
    owner_id = str(conv.get("assigned_to") or conv.get("user_id") or "")
    collabs = [c for c in (conv.get("collaborators") or []) if c and c != owner_id]
    if not collabs:
        return 0
    owner = await db.users.find_one({"_id": _oid(owner_id)}, {"name": 1}) if _oid(owner_id) else None
    name = conv.get("contact_name") or "A customer"
    why = "is off shift" if reason == "off_shift" else f"hasn't replied in {OWNER_SILENT_MINUTES} min"
    title = f"{name} is waiting"
    body = f"{_first(owner)} {why} · \"{(conv.get('last_message') or '')[:80]}\""
    now = _now()
    await db.notifications.insert_many([{
        "user_id": uid, "type": "collaborator_nudge", "priority": "urgent", "title": title, "message": body,
        "conversation_id": str(conv["_id"]), "contact_id": conv.get("contact_id"), "read": False, "dismissed": False, "created_at": now,
    } for uid in collabs])
    try:
        from routers.push_notifications import send_push_to_user
        for uid in collabs:
            asyncio.create_task(send_push_to_user(uid, title, body, f"/thread/{conv['_id']}", "people"))
    except Exception:
        pass
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"collab_nudged_for": conv.get("last_message_at"), "collab_nudged_at": now}})
    return len(collabs)


async def on_customer_message_for_collaborators(db, conversation_id: str):
    """Right after a customer text: collaborators hear about it now only if the owner is off shift."""
    conv = await db.conversations.find_one({"_id": _oid(conversation_id)}) if _oid(conversation_id) else None
    if not conv or not conv.get("collaborators"):
        return
    owner_id = str(conv.get("assigned_to") or conv.get("user_id") or "")
    if owner_id and await _owner_away(db, owner_id, conv) == "off_shift":
        await _push_collaborators(db, conv, "off_shift")


async def escalate_silent_owners() -> dict:
    """Scheduler (every minute): owner silent 15 min after a customer text -> nudge collaborators once per customer message."""
    from routers.database import get_db
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(minutes=OWNER_SILENT_MINUTES)
    nudged = 0
    cursor = db.conversations.find({"collaborators.0": {"$exists": True}, "last_message_from": "contact",
                                    "last_message_at": {"$lte": cutoff}, "status": {"$nin": ["closed", "archived"]},
                                    "$expr": {"$ne": ["$collab_nudged_for", "$last_message_at"]}}).limit(100)
    async for conv in cursor:
        owner_id = str(conv.get("assigned_to") or conv.get("user_id") or "")
        if not owner_id or await _owner_away(db, owner_id, conv) is None:
            continue
        nudged += await _push_collaborators(db, conv, "silent")
    return {"nudged": nudged}


# ── Ownership actions ────────────────────────────────────────────────────────

async def _system_message(db, conv_id: str, text: str):
    now = datetime.utcnow()
    await db.messages.insert_one({"conversation_id": conv_id, "sender": "system", "direction": "system", "channel": "system",
                                  "type": "event", "content": text, "timestamp": now, "created_at": now})


def _first(u: Optional[dict]) -> str:
    return ((u or {}).get("name") or (u or {}).get("first_name") or "a teammate").split()[0]


async def _move_book(db, contact_id: Optional[str], from_user: Optional[str], to_user: str):
    """The customer follows the new owner: contact, open tasks, live campaign enrollments and pending sends."""
    if not contact_id or not _oid(contact_id):
        return
    now = _now()
    await db.contacts.update_one({"_id": _oid(contact_id)}, {"$set": {"user_id": to_user, "claimed_by": to_user, "updated_at": now.isoformat()}})
    q_prev = {"contact_id": str(contact_id)}
    if from_user:
        q_prev["user_id"] = from_user
    await db.tasks.update_many({**q_prev, "status": {"$nin": ["completed", "cancelled"]}}, {"$set": {"user_id": to_user, "transferred_at": now}})
    await db.campaign_enrollments.update_many({**q_prev, "status": {"$in": ["active", "paused"]}}, {"$set": {"user_id": to_user, "transferred_at": now}})
    await db.campaign_pending_sends.update_many({**q_prev, "status": "pending"}, {"$set": {"user_id": to_user}})


def owner_of(conv: dict) -> str:
    return str(conv.get("assigned_to") or conv.get("claimed_by") or "")


async def assign_conversation(db, conv: dict, actor: dict, to_user_id: str, note: str = "") -> dict:
    """Claim (self) or assign/reassign (manager, or current owner handing off). Contact + follow-up move with it."""
    to_rep = await db.users.find_one({"_id": _oid(to_user_id)}) if _oid(to_user_id) else None
    if not to_rep:
        raise ValueError("Rep not found")
    actor_id = str(actor["_id"])
    prev_id = owner_of(conv)
    if prev_id == str(conv.get("store_id") or ""):
        prev_id = ""
    unassigned = not prev_id
    if prev_id == to_user_id:
        return {"success": True, "assigned_to": to_user_id, "assigned_to_name": to_rep.get("name"), "already": True}
    inbox = await get_inbox(db, conv["inbox_id"]) if conv.get("inbox_id") else None
    if not is_manager(actor):
        if unassigned:
            allowed = to_user_id == actor_id and (not inbox or actor_id in members(inbox))
        else:
            allowed = prev_id == actor_id
        if not allowed:
            raise PermissionError("Only the owner or a manager can reassign this conversation")
    if inbox and to_user_id not in members(inbox) and not is_manager(actor):
        raise PermissionError(f"{_first(to_rep)} is not on the {inbox.get('name')} inbox")
    now = _now()
    sets = {"claimed": True, "claimed_by": to_user_id, "assigned_to": to_user_id, "user_id": to_user_id,
            "claimed_at": now.isoformat(), "claim_source": "claimed" if unassigned else "reassigned",
            "routing_kind": "claimed" if unassigned else "reassigned", "owner_alert_at": None, "release_at": None,
            "updated_at": now.isoformat()}
    if not unassigned:
        sets.update({"reassigned_by": actor_id, "reassigned_from": prev_id or None, "reassigned_at": now})
    if (note or "").strip():
        sets["handoff_note"] = {"text": note.strip()[:200], "by": actor_id, "by_name": _first(actor), "at": now, "kind": "reassign"}
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": sets, "$pull": {"collaborators": to_user_id}, "$push": {"assignment_history": {
        "at": now, "by": actor_id, "from": prev_id or None, "to": to_user_id, "kind": "claim" if unassigned else "reassign", "note": (note or "")[:200]}}})
    await _move_book(db, conv.get("contact_id"), prev_id or None, to_user_id)
    try:
        from services.lead_call_engine import mark_claimed
        await mark_claimed(str(conv["_id"]), to_user_id, via="claimed" if unassigned else "reassigned")
    except Exception:
        pass
    if conv.get("contact_id") and _oid(conv["contact_id"]):
        try:
            from utils.activity_log import on_lead_claimed
            await on_lead_claimed(db, contact_id=str(conv["contact_id"]), user_id=to_user_id, via="app" if unassigned else "reassigned",
                                  previous_owner=prev_id, event_type="lead_claimed" if unassigned else "lead_reassigned",
                                  note=f"By {_first(actor)}" + (f": {note.strip()[:120]}" if (note or '').strip() else ""))
        except Exception:
            pass
    prev = await db.users.find_one({"_id": _oid(prev_id)}, {"name": 1}) if _oid(prev_id) else None
    where = f" in {inbox.get('name')}" if inbox else ""
    if unassigned and to_user_id == actor_id:
        line = f"{_first(to_rep)} picked this up{where}"
    elif unassigned:
        line = f"{_first(actor)} assigned this to {_first(to_rep)}{where}"
    else:
        line = f"{_first(actor)} moved this from {_first(prev) if prev else 'the queue'} to {_first(to_rep)}{where}"
    if (note or "").strip():
        line += f': "{note.strip()[:200]}"'
    await _system_message(db, str(conv["_id"]), line)
    lead_name = conv.get("contact_name") or "a conversation"
    if to_user_id != actor_id:
        await db.notifications.insert_one({"user_id": to_user_id, "type": "conversation_assigned", "title": f"Handed to you: {lead_name}",
                                           "message": line, "conversation_id": str(conv["_id"]), "contact_id": conv.get("contact_id"),
                                           "read": False, "dismissed": False, "created_at": now})
        try:
            from routers.push_notifications import send_push_to_user, LEAD_SOUND, LEAD_CHANNEL
            asyncio.create_task(send_push_to_user(to_user_id, f"Handed to you: {lead_name}", line, f"/thread/{conv['_id']}",
                                                  "person.fill.badge.plus", sound=LEAD_SOUND, channel_id=LEAD_CHANNEL))
        except Exception:
            pass
    if prev_id and prev_id not in (to_user_id, actor_id):
        await db.notifications.insert_one({"user_id": prev_id, "type": "conversation_reassigned", "title": f"{lead_name} moved to {_first(to_rep)}",
                                           "message": line, "conversation_id": str(conv["_id"]), "contact_id": conv.get("contact_id"),
                                           "read": False, "dismissed": False, "created_at": now})
    if inbox and unassigned:
        await db.notifications.update_many({"conversation_id": str(conv["_id"]), "type": {"$in": ["inbox_message", "new_lead"]}, "dismissed": {"$ne": True}},
                                           {"$set": {"dismissed": True, "read": True}})
        await notify_members(db, inbox, str(conv["_id"]), conv.get("contact_id"), f"{_first(to_rep)} picked up {lead_name}",
                             f"{inbox.get('name')} · no action needed", exclude=to_user_id, sound=False, notif_type="inbox_claimed")
    return {"success": True, "assigned_to": to_user_id, "assigned_to_name": to_rep.get("name"), "system_line": line}


async def release_conversation(db, conv: dict, actor: dict, note: str = "") -> dict:
    """Owner or manager puts an inbox thread back to Unassigned so the team can pick it up."""
    actor_id = str(actor["_id"])
    prev_id = owner_of(conv)
    if not is_manager(actor) and prev_id != actor_id:
        raise PermissionError("Only the owner or a manager can release this conversation")
    if not conv.get("inbox_id") or conv.get("graduated_at"):
        raise ValueError("Personal conversations can't be released; move them to an inbox instead")
    inbox = await get_inbox(db, conv["inbox_id"])
    store_id = str(conv.get("store_id") or (inbox or {}).get("store_id") or "")
    now = _now()
    sets = {"claimed": False, "claimed_by": None, "assigned_to": None, "user_id": store_id or conv.get("user_id"),
            "routing_kind": "queue", "released_at": now, "released_by": actor_id, "prev_owner_id": prev_id or None,
            "owner_alert_at": None, "release_at": None, "updated_at": now.isoformat()}
    if (note or "").strip():
        sets["handoff_note"] = {"text": note.strip()[:200], "by": actor_id, "by_name": _first(actor), "at": now, "kind": "release"}
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": sets, "$push": {"assignment_history": {
        "at": now, "by": actor_id, "from": prev_id or None, "to": None, "kind": "release", "note": (note or "")[:200]}}})
    if conv.get("contact_id") and _oid(conv["contact_id"]) and store_id:
        await db.contacts.update_one({"_id": _oid(conv["contact_id"])}, {"$set": {"user_id": store_id, "claimed_by": None, "released_from": prev_id or None}})
    line = f"{_first(actor)} released this back to {(inbox or {}).get('name') or 'the inbox'}" + (f': "{note.strip()[:200]}"' if (note or "").strip() else "")
    await _system_message(db, str(conv["_id"]), line)
    if inbox:
        await notify_members(db, inbox, str(conv["_id"]), conv.get("contact_id"), f"Up for grabs: {conv.get('contact_name') or 'a conversation'}",
                             (f"{_first(actor)}: \"{note.strip()[:120]}\"" if (note or "").strip() else f"Released in {inbox.get('name')} · tap to claim"), exclude=prev_id)
    return {"success": True, "released": True}


async def move_conversation(db, conv: dict, actor: dict, inbox_id: str, to_user_id: Optional[str] = None, note: str = "") -> dict:
    """Manager moves a thread to a different inbox (department). The customer will hear from the new inbox's number."""
    if not is_manager(actor):
        raise PermissionError("Managers only")
    inbox = await get_inbox(db, inbox_id)
    if not inbox or inbox.get("is_active") is False:
        raise ValueError("Inbox not found")
    if str(conv.get("inbox_id") or "") == str(inbox["_id"]) and not conv.get("graduated_at"):
        raise ValueError(f"Already in {inbox.get('name')}")
    now = _now()
    prev_inbox = await get_inbox(db, conv["inbox_id"]) if conv.get("inbox_id") else None
    number = _norm(inbox.get("phone_number")) or conv.get("rep_phone")
    prev_owner = owner_of(conv)
    sets = {"inbox_id": str(inbox["_id"]), "inbox_name": inbox.get("name"), "rep_phone": number, "graduated_at": None,
            "from_inbox_id": None, "moved_at": now, "moved_by": str(actor["_id"]), "store_id": inbox.get("store_id") or conv.get("store_id"),
            "claimed": False, "claimed_by": None, "assigned_to": None, "user_id": inbox.get("store_id") or conv.get("user_id"),
            "routing_kind": "queue", "updated_at": now.isoformat()}
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": sets, "$push": {"assignment_history": {
        "at": now, "by": str(actor["_id"]), "from": prev_owner or None, "to": None, "kind": "move",
        "inbox_from": str(prev_inbox["_id"]) if prev_inbox else None, "inbox_to": str(inbox["_id"]), "note": (note or "")[:200]}}})
    if conv.get("contact_id") and _oid(conv["contact_id"]) and inbox.get("store_id"):
        await db.contacts.update_one({"_id": _oid(conv["contact_id"])}, {"$set": {"user_id": inbox["store_id"], "claimed_by": None}})
    line = f"{_first(actor)} moved this from {(prev_inbox or {}).get('name') or 'a personal inbox'} to {inbox.get('name')}"
    if (note or "").strip():
        line += f': "{note.strip()[:200]}"'
    await _system_message(db, str(conv["_id"]), line)
    conv = await db.conversations.find_one({"_id": conv["_id"]})
    if to_user_id:
        return await assign_conversation(db, conv, actor, to_user_id, note)
    await notify_members(db, inbox, str(conv["_id"]), conv.get("contact_id"), f"New in {inbox.get('name')}: {conv.get('contact_name') or 'a conversation'}",
                         f"Moved here by {_first(actor)} · tap to claim")
    return {"success": True, "inbox_id": str(inbox["_id"]), "unassigned": True}


async def set_collaborator(db, conv: dict, actor: dict, user_id: str, add: bool) -> dict:
    owner = owner_of(conv) or str(conv.get("user_id") or "")
    if not is_manager(actor) and owner != str(actor["_id"]):
        raise PermissionError("Only the owner or a manager can share this conversation")
    rep = await db.users.find_one({"_id": _oid(user_id)}, {"name": 1}) if _oid(user_id) else None
    if not rep:
        raise ValueError("Rep not found")
    if add and user_id == owner:
        raise ValueError("That rep already owns this conversation")
    op = {"$addToSet" if add else "$pull": {"collaborators": user_id}}
    await db.conversations.update_one({"_id": conv["_id"]}, op)
    line = f"{_first(actor)} {'shared this with' if add else 'removed'} {_first(rep)}" + ("" if add else " from this conversation")
    await _system_message(db, str(conv["_id"]), line)
    if add and user_id != str(actor["_id"]):
        now = _now()
        await db.notifications.insert_one({"user_id": user_id, "type": "conversation_shared", "title": f"Shared with you: {conv.get('contact_name') or 'a conversation'}",
                                           "message": line, "conversation_id": str(conv["_id"]), "contact_id": conv.get("contact_id"),
                                           "read": False, "dismissed": False, "created_at": now})
        try:
            from routers.push_notifications import send_push_to_user
            asyncio.create_task(send_push_to_user(user_id, f"Shared with you: {conv.get('contact_name') or 'a conversation'}", line,
                                                  f"/thread/{conv['_id']}", "person.2"))
        except Exception:
            pass
    fresh = await db.conversations.find_one({"_id": conv["_id"]}, {"collaborators": 1})
    return {"success": True, "collaborators": (fresh or {}).get("collaborators", [])}


# ── Graduation (closing tag) ─────────────────────────────────────────────────

async def graduate_conversation(db, conv: dict, actor_id: Optional[str] = None, reason: str = "closed") -> dict:
    """Move an inbox thread onto its rep's own number and send the bridge text."""
    owner = owner_of(conv)
    rep, rep_number = await _rep_line(db, owner)
    if not rep or not rep_number:
        return {"success": False, "reason": "rep has no dedicated number"}
    inbox = await get_inbox(db, conv["inbox_id"]) if conv.get("inbox_id") else None
    now = _now()
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {
        "rep_phone": rep_number, "graduated_at": now, "graduated_reason": reason, "from_inbox_id": conv.get("inbox_id"),
        "inbox_id": None, "inbox_name": None, "user_id": owner, "updated_at": now.isoformat()},
        "$push": {"assignment_history": {"at": now, "by": actor_id, "from": owner, "to": owner, "kind": "graduate",
                                         "inbox_from": conv.get("inbox_id"), "note": reason}}})
    await _system_message(db, str(conv["_id"]), f"Moved to {_first(rep)}'s direct line ({reason})")
    contact = await db.contacts.find_one({"_id": _oid(conv["contact_id"])}) if _oid(conv.get("contact_id")) else None
    bridge = ((inbox or {}).get("bridge_text") or DEFAULT_BRIDGE_TEXT).strip()
    if bridge and conv.get("contact_phone") and not (contact or {}).get("sms_opt_out") and not (contact or {}).get("opted_out"):
        first = (contact or {}).get("first_name") or (conv.get("contact_name") or "there").split()[0]
        text = bridge.replace("{first_name}", first).replace("{rep_name}", _first(rep)).replace("{inbox_name}", (inbox or {}).get("name") or "the team")
        try:
            from services.twilio_service import send_sms
            res = await send_sms(conv["contact_phone"], text, from_phone=rep_number)
            await db.messages.insert_one({"conversation_id": str(conv["_id"]), "content": text, "sender": "user", "auto_sent": True,
                                          "is_bridge_text": True, "timestamp": datetime.utcnow(), "status": "sent" if res.get("success") else "failed",
                                          "twilio_sid": res.get("message_sid") or res.get("sid"), "from_phone": rep_number, "to_phone": conv["contact_phone"]})
            await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"last_message": text[:100], "last_message_at": datetime.utcnow(), "last_message_from": "user"}})
        except Exception as e:
            logger.warning(f"[Inbox] bridge text failed: {e}")
    return {"success": True, "rep_phone": rep_number}


async def graduate_on_close_tag(db, user_id: str, contact_id: str, tags_added: list) -> list:
    """Called when tags are added: the inbox's close tag graduates the thread per its after_close rule."""
    if not contact_id or not tags_added:
        return []
    convs = await db.conversations.find({"contact_id": str(contact_id), "inbox_id": {"$nin": [None, ""]}, "graduated_at": None}).to_list(10)
    if not convs:
        return []
    lowered = {str(t).strip().lower() for t in tags_added if t}
    out = []
    for conv in convs:
        inbox = await get_inbox(db, conv["inbox_id"])
        if not inbox:
            continue
        close_tag = (inbox.get("close_tag") or DEFAULT_CLOSE_TAG).strip()
        if close_tag.lower() not in lowered:
            continue
        if (inbox.get("after_close") or "move_to_rep") == "stay":
            await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"closed_tag_at": _now(), "closed_tag": close_tag}})
            await _system_message(db, str(conv["_id"]), f"Tagged {close_tag} · stays on the {inbox.get('name')} line")
            out.append({"conversation_id": str(conv["_id"]), "action": "stay"})
            continue
        if not owner_of(conv):
            if not _oid(user_id) or user_id == str(conv.get("store_id") or ""):
                continue
            await assign_conversation(db, conv, {"_id": ObjectId(user_id), "role": "super_admin", "name": "System"}, user_id, note=f"tagged {close_tag}")
            conv = await db.conversations.find_one({"_id": conv["_id"]})
        res = await graduate_conversation(db, conv, actor_id=user_id, reason=f"tagged {close_tag}")
        out.append({"conversation_id": str(conv["_id"]), "action": "graduate", **res})
    return out
