"""Tag Workflows: the store-wide rulebook for "what happens when a contact gets tagged X".

One engine for every path that applies tags (Sold screen, Sold wizard, contact tag editor, contact create/update,
congrats cards). For each NEWLY added tag it: stops competing nurtures, clears the hot-buying-intent flag,
enrolls the contact in the store's campaign(s) for that tag, and hands the conversation to Jessi (or not).
Managers/admins edit the rules once (db.tag_workflows, scoped per store); reps only view.
"""
import logging
from datetime import datetime, timedelta

from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)

COLL = "tag_workflows"
DATE_OPTIN_TAGS = {"birthday", "anniversary"}  # date-based: never instant-fire, never change Jessi
JESSI_MODES = ("auto_reply", "draft_only", "off")
MANAGER_ROLES = {"super_admin", "org_admin", "store_manager", "manager", "admin"}

# Defaults every store starts with. Managers override per store; anything not listed is "auto" (campaigns by tag).
KNOWN_TAGS = {
    "sold": {
        "label": "Sold", "jessi_mode": "auto_reply", "clear_hot": True, "stop_campaigns": True,
        "stop_tags": ["Working", "Met", "Lost Contact", "Hot"],
        "instant": ["Save-my-number text with your contact card", "Congrats card or delivery photo (+2 min)", "Review request (+7 min)"],
        "instant_note": "Sent by the Sold screen the moment you mark the sale.",
        "blurb": "A customer who just bought. Pre-sale chasing stops; the long-term relationship starts.",
    },
    "working": {"label": "Working", "jessi_mode": "auto_reply", "clear_hot": False, "stop_campaigns": False, "stop_tags": [],
                "blurb": "An active deal you're working. Nurture texts keep them warm; Jessi answers replies."},
    "met": {"label": "Met", "jessi_mode": "auto_reply", "clear_hot": False, "stop_campaigns": False, "stop_tags": [],
            "blurb": "Someone you just met. Follow-up texts build the relationship; Jessi answers replies."},
    "lost contact": {"label": "Lost Contact", "jessi_mode": "auto_reply", "clear_hot": False, "stop_campaigns": False, "stop_tags": [],
                     "blurb": "Went quiet. Re-engagement texts try to bring them back."},
    "vip": {"label": "VIP", "jessi_mode": "auto_reply", "clear_hot": False, "stop_campaigns": False, "stop_tags": [],
            "blurb": "Your best customers. White-glove touches through the year."},
    "birthday": {"label": "Birthday", "date_based": True, "blurb": "Opt-in marker: the birthday text goes out day-of, never at tagging time."},
    "anniversary": {"label": "Anniversary", "date_based": True, "blurb": "Opt-in marker: the purchase-anniversary text goes out day-of."},
}


# ---------------------------------------------------------------- scope / permissions
def scope_key(user: dict) -> str:
    sid = user.get("store_id") or (user.get("store_ids") or [None])[0]
    return f"store:{sid}" if sid else f"user:{user['_id']}"


def can_edit(user: dict) -> bool:
    return (user or {}).get("role") in MANAGER_ROLES


async def _user(db, user_id: str) -> dict:
    try:
        return await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1, "store_ids": 1, "organization_id": 1, "org_id": 1, "name": 1}) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------- campaign visibility (same rule as GET /campaigns)
async def visible_campaigns(db, user: dict) -> list:
    user_id = str(user["_id"])
    store_id = user.get("store_id") or (user.get("store_ids") or [None])[0]
    org_id = user.get("organization_id") or user.get("org_id")
    conditions = [{"user_id": user_id}]
    if store_id:
        store_user_ids = [str(u["_id"]) async for u in db.users.find({"store_id": store_id}, {"_id": 1})]
        if store_user_ids:
            conditions.append({"user_id": {"$in": store_user_ids}, "scope": "account"})
            conditions.append({"user_id": {"$in": store_user_ids}, "ownership_level": "store"})
        conditions.append({"store_id": store_id, "scope": "account"})
    if org_id:
        conditions.append({"org_id": org_id, "scope": "org"})
    return await db.campaigns.find({"$or": conditions, "active": True}).limit(500).to_list(500)


def _campaign_scope(c: dict) -> str:
    if c.get("scope") == "org":
        return "org"
    if c.get("scope") == "account" or c.get("ownership_level") == "store":
        return "store"
    return "personal"


def _campaigns_for_tag(campaigns: list, tag: str) -> list:
    """Auto mode: active campaigns triggered by this tag; store/org versions win over same-named personal copies."""
    rank = {"org": 0, "store": 1, "personal": 2}
    best: dict = {}
    for c in campaigns:
        if (c.get("trigger_tag") or "").lower() != tag:
            continue
        key = (c.get("name"), c.get("type"))
        if key not in best or rank[_campaign_scope(c)] < rank[_campaign_scope(best[key])]:
            best[key] = c
    return list(best.values())


# ---------------------------------------------------------------- resolve a workflow
async def get_workflow(db, user: dict, tag: str, campaigns: list | None = None) -> dict:
    tag = (tag or "").lower().strip()
    base = dict(KNOWN_TAGS.get(tag) or {"label": tag.title(), "jessi_mode": None, "clear_hot": False, "stop_campaigns": False, "stop_tags": []})
    stored = await db[COLL].find_one({"scope_key": scope_key(user), "tag": tag}) or {}
    for k in ("jessi_mode", "clear_hot", "stop_campaigns", "stop_tags", "campaign_ids"):
        if k in stored:
            base[k] = stored[k]
    if campaigns is None:
        campaigns = await visible_campaigns(db, user)
    if base.get("campaign_ids"):
        ids = [ObjectId(i) for i in base["campaign_ids"] if ObjectId.is_valid(str(i))]
        found = await db.campaigns.find({"_id": {"$in": ids}}).to_list(50)
        chosen = [c for c in found if c.get("active", True)]
        campaign_mode = "custom"
    else:
        chosen = _campaigns_for_tag(campaigns, tag)
        campaign_mode = "auto"
    if not base.get("jessi_mode") and not base.get("date_based"):
        base["jessi_mode"] = "auto_reply" if any(c.get("ai_enabled") for c in chosen) else None
    return {**base, "tag": tag, "campaigns": chosen, "campaign_mode": campaign_mode, "customized": bool(stored),
            "updated_at": stored.get("updated_at"), "updated_by_name": stored.get("updated_by_name")}


# ---------------------------------------------------------------- timeline (plain English)
def _delay_label(step: dict) -> str:
    mins = int(step.get("delay_minutes", 0) or 0) + 60 * int(step.get("delay_hours", 0) or 0)
    days = int(step.get("delay_days", 0) or 0) + 30 * int(step.get("delay_months", 0) or 0)
    total_min = mins + days * 1440
    if total_min == 0:
        return "Right away"
    if total_min < 60:
        return f"+{total_min} min"
    if total_min < 1440:
        h = total_min / 60
        return f"+{h:g} hr"
    d = total_min // 1440
    if d % 365 == 0 and d >= 365:
        return f"Year {d // 365}"
    if d >= 60 and d % 30 == 0:
        return f"Month {d // 30}"
    if d % 7 == 0 and d >= 14:
        return f"Week {d // 7}"
    return f"Day {d}"


def _step_kind(step: dict) -> str:
    ch = (step.get("channel") or "sms").lower()
    if step.get("media_type") == "video" or ch == "video":
        return "Video text"
    if step.get("media_urls"):
        return "Photo text"
    if ch == "email":
        return "Email"
    if ch == "call":
        return "Call task"
    return "Text"


def build_timeline(wf: dict) -> list:
    rows = []
    for text in wf.get("instant") or []:
        rows.append({"when": "Now", "what": text, "kind": "instant"})
    for c in wf.get("campaigns") or []:
        for i, step in enumerate(c.get("sequences") or []):
            preview = (step.get("message_template") or step.get("message") or "").replace("\n", " ").strip()
            rows.append({"when": _delay_label(step), "what": f"{_step_kind(step)} {i + 1} of {len(c.get('sequences') or [])}",
                         "campaign": c.get("name"), "kind": "campaign", "preview": preview[:140],
                         "ai": bool(c.get("ai_enabled")), "sort": _sort_minutes(step)})
    rows.sort(key=lambda r: r.get("sort", -1))
    return rows


def _sort_minutes(step: dict) -> int:
    return (int(step.get("delay_minutes", 0) or 0) + 60 * int(step.get("delay_hours", 0) or 0)
            + 1440 * (int(step.get("delay_days", 0) or 0) + 30 * int(step.get("delay_months", 0) or 0)))


def serialize_workflow(wf: dict, editable: bool) -> dict:
    return {
        "tag": wf["tag"], "label": wf.get("label"), "blurb": wf.get("blurb"), "date_based": bool(wf.get("date_based")),
        "jessi_mode": wf.get("jessi_mode"), "clear_hot": bool(wf.get("clear_hot")), "stop_campaigns": bool(wf.get("stop_campaigns")),
        "stop_tags": wf.get("stop_tags") or [], "campaign_mode": wf.get("campaign_mode"), "customized": wf.get("customized", False),
        "instant": wf.get("instant") or [], "instant_note": wf.get("instant_note"),
        "campaigns": [{"id": str(c["_id"]), "name": c.get("name"), "steps": len(c.get("sequences") or []), "ai_enabled": bool(c.get("ai_enabled")),
                       "scope": _campaign_scope(c), "trigger_tag": c.get("trigger_tag")} for c in wf.get("campaigns") or []],
        "timeline": build_timeline(wf), "editable": editable,
        "updated_at": wf.get("updated_at").isoformat() if isinstance(wf.get("updated_at"), datetime) else wf.get("updated_at"),
        "updated_by_name": wf.get("updated_by_name"),
    }


# ---------------------------------------------------------------- the engine
async def enroll_contact(db, user_id: str, campaign: dict, contact: dict, trigger_type: str, ai_mode: str | None) -> bool:
    """Enroll + pre-schedule every step (moved from contacts._check_tag_campaign_enrollment). Idempotent."""
    campaign_id = str(campaign["_id"])
    contact_id = str(contact["_id"])
    if await db.campaign_enrollments.find_one({"campaign_id": campaign_id, "contact_id": contact_id, "status": {"$in": ["active", "completed"]}}):
        return False
    sequences = campaign.get("sequences") or []
    if not sequences:
        return False
    contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or contact.get("name", "")
    now = datetime.utcnow()
    assist = ai_mode or ("auto_reply" if campaign.get("ai_enabled") else "off")
    enrollment = {
        "user_id": user_id, "campaign_id": campaign_id, "campaign_name": campaign.get("name", ""),
        "contact_id": contact_id, "contact_name": contact_name, "contact_phone": contact.get("phone", ""),
        "current_step": 1, "total_steps": len(sequences), "status": "active", "enrolled_at": now, "next_send_at": now,
        "messages_sent": [], "trigger_type": trigger_type, "trigger_tag": campaign.get("trigger_tag", ""), "ai_assist_mode": assist,
    }
    enrollment_id = str((await db.campaign_enrollments.insert_one(enrollment)).inserted_id)
    delivery_mode = campaign.get("delivery_mode", "auto")
    docs = []
    for i, step in enumerate(sequences):
        send_at = now + timedelta(minutes=_sort_minutes(step))
        docs.append({
            "user_id": user_id, "campaign_id": campaign_id, "campaign_name": campaign.get("name", ""),
            "contact_id": contact_id, "contact_name": contact_name, "contact_phone": contact.get("phone", ""),
            "enrollment_id": enrollment_id, "step": i + 1,
            "message_template": step.get("message_template") or step.get("message", ""),
            "media_type": step.get("media_type", ""), "media_urls": step.get("media_urls", []), "channel": step.get("channel", "sms"),
            "delivery_mode": delivery_mode, "ai_enabled": campaign.get("ai_enabled", False),
            "send_at": send_at, "status": "pending", "created_at": now,
        })
    if docs:
        await db.campaign_pending_sends.insert_many(docs)
    logger.info(f"[Workflows] Enrolled {contact_name} in '{campaign.get('name')}' ({trigger_type}), {len(docs)} sends pre-scheduled, jessi={assist}")
    return True


async def stop_competing(db, user_id: str, contact: dict, stop_tags: list, stop_campaigns: bool, keep_tag: str) -> dict:
    stop_lower = {t.lower() for t in stop_tags}
    removed = [t for t in contact.get("tags") or [] if t.lower() in stop_lower and t.lower() != keep_tag]
    if removed:
        await db.contacts.update_one({"_id": contact["_id"]}, {"$pull": {"tags": {"$in": removed}}})
    cancelled = []
    if stop_campaigns:
        async for e in db.campaign_enrollments.find({"contact_id": str(contact["_id"]), "status": {"$in": ["active", "paused"]}}):
            trig = (e.get("trigger_tag") or "").lower()
            if not trig and ObjectId.is_valid(str(e.get("campaign_id"))):
                camp = await db.campaigns.find_one({"_id": ObjectId(e["campaign_id"])}, {"trigger_tag": 1})
                trig = ((camp or {}).get("trigger_tag") or "").lower()
            if trig in stop_lower:
                now = datetime.utcnow()
                await db.campaign_enrollments.update_one({"_id": e["_id"]}, {"$set": {"status": "cancelled", "cancelled_at": now, "cancelled_reason": f"tag:{keep_tag}"}})
                await db.campaign_pending_sends.update_many({"enrollment_id": str(e["_id"]), "status": "pending"}, {"$set": {"status": "cancelled", "cancelled_at": now}})
                cancelled.append(e.get("campaign_name") or trig)
    return {"removed_tags": removed, "cancelled_campaigns": cancelled}


async def set_jessi(db, user_id: str, contact: dict, mode: str) -> int:
    """Contact-level default + every existing conversation between this rep and this contact."""
    on = mode != "off"
    await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"ai_default_mode": mode}})
    ors = [{"user_id": user_id, "contact_id": str(contact["_id"])}]
    if contact.get("phone"):
        ors.append({"user_id": user_id, "contact_phone": contact["phone"]})
    res = await db.conversations.update_many({"$or": ors}, {"$set": {"ai_enabled": on, "ai_mode": mode, "ai_mode_source": "workflow"}})
    return res.modified_count


async def initial_ai_state(db, contact_id) -> dict:
    """AI fields for a brand-new conversation: honours the contact's workflow default (e.g. Sold => Jessi on)."""
    try:
        c = await db.contacts.find_one({"_id": ObjectId(str(contact_id))}, {"ai_default_mode": 1}) if contact_id and ObjectId.is_valid(str(contact_id)) else None
    except Exception:
        c = None
    mode = (c or {}).get("ai_default_mode")
    if mode in ("auto_reply", "draft_only", "auto_with_approval"):
        return {"ai_enabled": True, "ai_mode": mode, "ai_mode_source": "workflow"}
    return {"ai_enabled": False, "ai_mode": "suggest"}


async def apply_tag_workflows(user_id: str, contact_id: str, tags_added: list, source: str = "") -> list:
    """Run the rulebook for each newly added tag. Returns a list of action summaries (also written to the contact's activity log)."""
    db = get_db()
    tags = []
    for t in tags_added or []:
        tl = (t or "").lower().strip()
        if tl and tl not in tags and tl not in DATE_OPTIN_TAGS:
            tags.append(tl)
    if not tags:
        return []
    user = await _user(db, user_id)
    if not user:
        return []
    campaigns = await visible_campaigns(db, user)
    actions = []
    for tag in tags:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            break
        wf = await get_workflow(db, user, tag, campaigns)
        summary = {"tag": tag, "label": wf.get("label")}
        if wf.get("stop_tags") or wf.get("stop_campaigns"):
            summary.update(await stop_competing(db, user_id, contact, wf.get("stop_tags") or [], bool(wf.get("stop_campaigns")), tag))
        if wf.get("clear_hot"):
            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"hot_opportunity": False}, "$pull": {"tags": {"$in": ["hot", "Hot"]}}})
            await db.conversations.update_many({"user_id": user_id, "contact_id": contact_id}, {"$set": {"hot_opportunity": False}})
            summary["cleared_hot"] = True
        enrolled = []
        for camp in wf.get("campaigns") or []:
            if await enroll_contact(db, user_id, camp, contact, "tag", wf.get("jessi_mode")):
                enrolled.append(camp.get("name"))
        summary["enrolled"] = enrolled
        if wf.get("jessi_mode") in JESSI_MODES:
            summary["jessi_mode"] = wf["jessi_mode"]
            summary["conversations_updated"] = await set_jessi(db, user_id, contact, wf["jessi_mode"])
        actions.append(summary)
        try:
            parts = []
            if enrolled:
                parts.append("enrolled in " + ", ".join(enrolled))
            if summary.get("cancelled_campaigns"):
                parts.append("stopped " + ", ".join(summary["cancelled_campaigns"]))
            if summary.get("removed_tags"):
                parts.append("removed " + ", ".join(summary["removed_tags"]))
            if summary.get("jessi_mode") == "auto_reply":
                parts.append("Jessi answers replies")
            elif summary.get("jessi_mode") == "off":
                parts.append("Jessi off")
            if parts:
                from utils.activity_log import log_activity
                await log_activity(db, user_id=user_id, contact_id=contact_id, event_type="workflow",
                                   description=f"{wf.get('label') or tag.title()} workflow: " + "; ".join(parts),
                                   metadata={"tag": tag, "source": source, **{k: v for k, v in summary.items() if k not in ("tag", "label")}})
        except Exception as e:
            logger.debug(f"[Workflows] activity log skipped: {e}")
    logger.info(f"[Workflows] {source or 'tags'} -> {contact_id}: {actions}")
    return actions
