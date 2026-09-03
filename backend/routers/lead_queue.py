"""
Internet Leads shared queue.

Every internet lead lands here until a rep on that source's workflow claims it. Returning customers
(existing contact with an active owner in the store) skip the queue and go straight to their rep,
with a manager alert / auto-release safety net if that rep goes quiet.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db

logger = logging.getLogger(__name__)

MANAGER_ROLES = ("super_admin", "admin", "manager", "store_manager", "org_admin")


async def require_queue_user(request: Request) -> dict:
    """JWT caller must be the {user_id} in the path, or a manager."""
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    path_uid = request.path_params.get("user_id")
    if path_uid and str(user.get("_id")) != str(path_uid) and user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="You can only view your own lead queue")
    request.state.user = user
    return user


router = APIRouter(prefix="/leads/queue", tags=["lead-queue"], dependencies=[Depends(require_queue_user)])
QUEUE_WINDOW_DAYS = 30
DEFAULTS = {"timer_green_minutes": 5, "timer_amber_minutes": 15,
            "returning_alert_minutes": 10, "returning_release_minutes": 30, "digest_hour": 18}


def _utc(dt):
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _iso(dt):
    d = _utc(dt)
    return d.isoformat() if d else None


def source_thresholds(source: dict) -> dict:
    return {k: int(source.get(k) or v) for k, v in DEFAULTS.items()}


def source_member_ids(source: dict) -> set:
    ids = set(source.get("workflow_user_ids") or [])
    for a in source.get("call_attempts") or []:
        ids.update(a.get("user_ids") or [])
    return {str(i) for i in ids if i}


async def _me(db, user_id: str) -> dict:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    me = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1, "name": 1})
    if not me:
        raise HTTPException(status_code=404, detail="User not found")
    me["_id"] = str(me["_id"])
    me["store_id"] = str(me.get("store_id") or "")
    me["is_manager"] = me.get("role") in MANAGER_ROLES
    return me


async def _store_sources(db, store_id: str, me: Optional[dict] = None) -> list:
    """Active sources for the store. Super/org admins without a store see every store's sources."""
    if not store_id:
        if not (me and me.get("role") in ("super_admin", "org_admin")):
            return []
        q = {"active": {"$ne": False}, "$or": [{"lead_count": {"$gt": 0}}, {"website_default": True}, {"workflow_user_ids.0": {"$exists": True}}]}
    else:
        q = {"store_id": store_id, "active": {"$ne": False}}
    out = []
    async for s in db.lead_sources.find(q):
        s["_id"] = str(s["_id"])
        out.append(s)
    return out


def _visible_sources(me: dict, sources: list) -> list:
    if me["is_manager"]:
        return sources
    return [s for s in sources if me["_id"] in source_member_ids(s)]


async def _store_managers(db, store_id: str) -> list:
    if not store_id:
        return []
    q = {"role": {"$in": list(MANAGER_ROLES)}, "active": {"$ne": False}, "status": {"$ne": "deactivated"},
         "$or": [{"store_id": store_id}, {"store_id": ObjectId(store_id)} if ObjectId.is_valid(store_id) else {"store_id": store_id},
                 {"role": "super_admin", "store_id": {"$in": [None, ""]}}]}
    return [str(u["_id"]) async for u in db.users.find(q, {"_id": 1})]


async def _message_stats(db, conv_ids: list) -> dict:
    """Per conversation: first/last human outbound ts, last inbound ts + text."""
    if not conv_ids:
        return {}
    pipeline = [
        {"$match": {"conversation_id": {"$in": conv_ids}}},
        {"$addFields": {"_ts": {"$ifNull": ["$timestamp", "$created_at"]},
                        "_human": {"$and": [{"$eq": ["$sender", "user"]}, {"$ne": ["$auto_sent", True]}]},
                        "_in": {"$or": [{"$eq": ["$sender", "contact"]}, {"$eq": ["$direction", "inbound"]}]}}},
        {"$sort": {"_ts": 1}},
        {"$group": {"_id": "$conversation_id",
                    "first_human": {"$min": {"$cond": ["$_human", "$_ts", None]}},
                    "last_human": {"$max": {"$cond": ["$_human", "$_ts", None]}},
                    "last_in": {"$max": {"$cond": ["$_in", "$_ts", None]}},
                    "in_bodies": {"$push": {"$cond": ["$_in", {"$ifNull": ["$content", "$body"]}, None]}}}},
    ]
    out = {}
    async for row in db.messages.aggregate(pipeline):
        bodies = [b for b in (row.get("in_bodies") or []) if b]
        out[row["_id"]] = {"first_human": _utc(row.get("first_human")), "last_human": _utc(row.get("last_human")),
                           "last_in": _utc(row.get("last_in")), "last_in_body": bodies[-1] if bodies else None}
    return out


def _display_name(u: Optional[dict]) -> str:
    if not u:
        return ""
    return u.get("name") or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "Rep"


async def _build_items(db, convs: list, sources_by_id: dict, now: datetime) -> list:
    conv_ids = [str(c["_id"]) for c in convs]
    stats = await _message_stats(db, conv_ids)
    leads = {}
    async for l in db.inbound_leads.find({"conversation_id": {"$in": conv_ids}},
                                         {"conversation_id": 1, "vehicle_interest": 1, "comments": 1, "matched_inventory": 1, "attribution": 1}):
        leads[l["conversation_id"]] = l
    rep_ids = {str(c.get("claimed_by")) for c in convs if c.get("claimed_by") and ObjectId.is_valid(str(c.get("claimed_by")))}
    reps = {}
    if rep_ids:
        async for u in db.users.find({"_id": {"$in": [ObjectId(r) for r in rep_ids]}}, {"name": 1, "first_name": 1, "last_name": 1, "photo_url": 1}):
            reps[str(u["_id"])] = u
    items = []
    for c in convs:
        cid = str(c["_id"])
        src = sources_by_id.get(str(c.get("lead_source_id") or ""), {})
        th = source_thresholds(src)
        st = stats.get(cid, {})
        created = _utc(c.get("created_at")) or now
        lead = leads.get(cid, {})
        first_human = st.get("first_human")
        last_in, last_human = st.get("last_in"), st.get("last_human")
        # Waiting = customer is owed a human reply (never replied, or their last text came after our last one)
        if not first_human:
            waiting_since = created
        elif last_in and (not last_human or last_in > last_human):
            waiting_since = last_in
        else:
            waiting_since = None
        waiting_s = int((now - waiting_since).total_seconds()) if waiting_since else None
        heat = None
        if waiting_s is not None:
            heat = "green" if waiting_s < th["timer_green_minutes"] * 60 else "amber" if waiting_s < th["timer_amber_minutes"] * 60 else "red"
        mi = lead.get("matched_inventory") or {}
        rep = reps.get(str(c.get("claimed_by") or ""))
        attribution = lead.get("attribution") or c.get("attribution") or {}
        items.append({
            "id": cid,
            "contact_id": c.get("contact_id"),
            "contact_name": c.get("contact_name") or "Unknown",
            "phone": c.get("contact_phone"),
            "source_id": str(c.get("lead_source_id") or ""),
            "source_name": c.get("lead_source_name") or src.get("name") or "Lead",
            "source_color": src.get("color") or "#007AFF",
            "source_label": attribution.get("source_label") or attribution.get("page") or None,
            "vehicle": lead.get("vehicle_interest") or None,
            "in_stock": {"name": mi.get("name"), "stock_number": mi.get("stock_number")} if mi else None,
            "comments": (lead.get("comments") or st.get("last_in_body") or "")[:200],
            "sms_opt_in": bool((c.get("sms_consent") or {}).get("opted_in")) if isinstance(c.get("sms_consent"), dict) else False,
            "is_test": bool(c.get("is_test")),
            "after_hours": bool(c.get("after_hours_lead")),
            "ai_on": c.get("ai_mode") == "auto_reply",
            "routing_kind": c.get("routing_kind") or ("assigned" if c.get("claimed") else "queue"),
            "created_at": _iso(created),
            "claimed": bool(c.get("claimed")),
            "claimed_by": str(c.get("claimed_by")) if c.get("claimed_by") else None,
            "claimed_by_name": _display_name(rep),
            "claimed_by_photo": (rep or {}).get("photo_url"),
            "claimed_at": _iso(c.get("claimed_at")),
            "first_reply_seconds": int((first_human - created).total_seconds()) if first_human else None,
            "waiting_since": _iso(waiting_since),
            "waiting_seconds": waiting_s,
            "heat": heat,
            "green_m": th["timer_green_minutes"],
            "amber_m": th["timer_amber_minutes"],
            "owner_alert_at": _iso(c.get("owner_alert_at")),
            "release_at": _iso(c.get("release_at")),
            "released_at": _iso(c.get("released_at")),
        })
    return items


def _sort_key(it: dict):
    return (0 if it["waiting_seconds"] is not None else 1, -(it["waiting_seconds"] or 0), it["created_at"] or "")


@router.get("/{user_id}/summary")
async def queue_summary(user_id: str):
    """Badge + Home strip: how many unclaimed leads this user can see, oldest wait, names."""
    db = get_db()
    me = await _me(db, user_id)
    all_sources = await _store_sources(db, me["store_id"], me)
    src_ids = [s["_id"] for s in _visible_sources(me, all_sources)]
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=QUEUE_WINDOW_DAYS)
    q_or: list = [{"claimed_by": user_id}]
    if src_ids:
        q_or.append({"lead_source_id": {"$in": src_ids}, "claimed": {"$ne": True}})
    convs = await db.conversations.find(
        {"is_internet_lead": True, "status": {"$ne": "closed"}, "created_at": {"$gte": since}, "$or": q_or}
    ).to_list(300)
    items = await _build_items(db, convs, {s["_id"]: s for s in all_sources}, now)
    unclaimed = sorted([i for i in items if not i["claimed"]], key=_sort_key)
    mine_waiting = sorted([i for i in items if i["claimed_by"] == user_id and i["waiting_seconds"] is not None], key=_sort_key)
    rank = {"red": 3, "amber": 2, "green": 1}
    worst = max((rank.get(i["heat"] or "", 0) for i in unclaimed + mine_waiting), default=0)

    def brief(i):
        return {"conversation_id": i["id"], "contact_name": i["contact_name"], "waiting_seconds": i["waiting_seconds"], "heat": i["heat"]}

    return {
        "visible": bool(src_ids),
        "waiting": len(unclaimed),
        "oldest_seconds": unclaimed[0]["waiting_seconds"] if unclaimed and unclaimed[0]["waiting_seconds"] is not None else 0,
        "oldest": brief(unclaimed[0]) if unclaimed else None,
        "names": [i["contact_name"].split()[0] for i in unclaimed[:3]],
        "red": sum(1 for i in unclaimed if i["heat"] == "red"),
        "mine_waiting": len(mine_waiting),
        "mine_oldest": brief(mine_waiting[0]) if mine_waiting else None,
        "mine_names": [i["contact_name"].split()[0] for i in mine_waiting[:3]],
        "heat": {3: "red", 2: "amber", 1: "green"}.get(worst),
    }


@router.get("/{user_id}")
async def get_queue(user_id: str):
    """Full queue: unclaimed (from sources you're on), mine, and (managers) everyone else's."""
    db = get_db()
    me = await _me(db, user_id)
    all_sources = await _store_sources(db, me["store_id"], me)
    visible = _visible_sources(me, all_sources)
    sources_by_id = {s["_id"]: s for s in all_sources}
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=QUEUE_WINDOW_DAYS)
    vis_ids = [s["_id"] for s in visible]
    q_or = [{"claimed_by": user_id}]
    if vis_ids:
        q_or.append({"lead_source_id": {"$in": vis_ids}, "claimed": {"$ne": True}})
        if me["is_manager"]:
            q_or.append({"lead_source_id": {"$in": vis_ids}})
    convs = await db.conversations.find(
        {"is_internet_lead": True, "status": {"$ne": "closed"}, "created_at": {"$gte": since}, "$or": q_or}
    ).sort("created_at", -1).to_list(400)
    items = await _build_items(db, convs, sources_by_id, now)
    unclaimed = sorted([i for i in items if not i["claimed"]], key=_sort_key)
    mine = sorted([i for i in items if i["claimed"] and i["claimed_by"] == user_id], key=_sort_key)
    others = sorted([i for i in items if i["claimed"] and i["claimed_by"] != user_id], key=_sort_key) if me["is_manager"] else []
    return {
        "is_manager": me["is_manager"],
        "visible": bool(vis_ids) or bool(mine),
        "can_claim_source_ids": vis_ids,
        "sources": [{"id": s["_id"], "name": s.get("name"), "color": s.get("color") or "#007AFF", **source_thresholds(s)} for s in visible],
        "unclaimed": unclaimed,
        "mine": mine,
        "claimed": others,
        "counts": {"unclaimed": len(unclaimed), "mine": len(mine), "claimed": len(others),
                   "red": sum(1 for i in items if i["heat"] == "red")},
    }


@router.get("/{user_id}/reps")
async def queue_reps(user_id: str):
    """Reassign picker: active reps in the store with on-shift flag and open lead count."""
    db = get_db()
    me = await _me(db, user_id)
    if not me["is_manager"]:
        raise HTTPException(status_code=403, detail="Managers only")
    sid = me["store_id"]
    q: dict = {"active": {"$ne": False}, "status": {"$ne": "deactivated"}}
    if sid:
        q["$or"] = [{"store_id": sid}, {"store_id": ObjectId(sid)}] if ObjectId.is_valid(sid) else [{"store_id": sid}]
    users = await db.users.find(q, {"name": 1, "first_name": 1, "last_name": 1, "photo_url": 1, "role": 1}).to_list(300)
    members: set = set()
    for s in await _store_sources(db, sid, me):
        members |= source_member_ids(s)
    ids = [str(u["_id"]) for u in users]
    try:
        from routers.lead_intake import _get_on_shift_reps
        on_shift = set(await _get_on_shift_reps(ids, fallback_all=False))
    except Exception:
        on_shift = set(ids)
    since = datetime.now(timezone.utc) - timedelta(days=QUEUE_WINDOW_DAYS)
    counts = {}
    async for row in db.conversations.aggregate([
        {"$match": {"is_internet_lead": True, "status": {"$ne": "closed"}, "claimed_by": {"$in": ids}, "created_at": {"$gte": since}}},
        {"$group": {"_id": "$claimed_by", "n": {"$sum": 1}}},
    ]):
        counts[row["_id"]] = row["n"]
    out = [{"user_id": str(u["_id"]), "name": _display_name(u), "photo_url": u.get("photo_url"), "role": u.get("role"),
            "on_workflow": str(u["_id"]) in members, "on_shift": str(u["_id"]) in on_shift, "open_leads": counts.get(str(u["_id"]), 0)}
           for u in users]
    out.sort(key=lambda r: (not r["on_workflow"], not r["on_shift"], r["open_leads"], r["name"].lower()))
    return {"reps": out, "me": me["_id"]}


class ReassignBody(BaseModel):
    to_user_id: str
    note: str = ""


async def _system_message(db, conv_id: str, text: str):
    now = datetime.now(timezone.utc)
    await db.messages.insert_one({"conversation_id": conv_id, "content": text, "sender": "system", "direction": "system",
                                  "channel": "system", "type": "event", "timestamp": now, "created_at": now})


async def _conv(db, conv_id: str) -> dict:
    if not ObjectId.is_valid(conv_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
    if not conv or not conv.get("is_internet_lead"):
        raise HTTPException(status_code=404, detail="Lead not found")
    return conv


@router.post("/{user_id}/reassign/{conv_id}")
async def reassign_lead(user_id: str, conv_id: str, body: ReassignBody):
    """Manager moves a claimed lead (thread + contact ownership) to another rep."""
    db = get_db()
    me = await _me(db, user_id)
    if not me["is_manager"]:
        raise HTTPException(status_code=403, detail="Managers only")
    conv = await _conv(db, conv_id)
    if not ObjectId.is_valid(body.to_user_id):
        raise HTTPException(status_code=400, detail="Pick a rep")
    to_rep = await db.users.find_one({"_id": ObjectId(body.to_user_id)}, {"name": 1, "first_name": 1, "last_name": 1, "store_id": 1})
    if not to_rep:
        raise HTTPException(status_code=404, detail="Rep not found")
    if me.get("role") not in ("super_admin", "org_admin") and str(to_rep.get("store_id") or "") != me["store_id"]:
        raise HTTPException(status_code=403, detail="Rep is not in your store")
    now = datetime.now(timezone.utc)
    prev_id = str(conv.get("claimed_by") or "")
    prev = await db.users.find_one({"_id": ObjectId(prev_id)}, {"name": 1, "first_name": 1, "last_name": 1}) if ObjectId.is_valid(prev_id) else None
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {
        "claimed": True, "claimed_by": body.to_user_id, "assigned_to": body.to_user_id, "user_id": body.to_user_id,
        "claimed_at": now.isoformat(), "claim_source": "reassigned", "routing_kind": "reassigned",
        "reassigned_by": user_id, "reassigned_from": prev_id or None, "reassigned_at": now,
        "owner_alert_at": None, "release_at": None, "updated_at": now.isoformat(),
    }})
    if conv.get("contact_id") and ObjectId.is_valid(str(conv["contact_id"])):
        await db.contacts.update_one({"_id": ObjectId(conv["contact_id"])},
                                     {"$set": {"user_id": body.to_user_id, "claimed_by": body.to_user_id, "updated_at": now.isoformat()}})
    try:
        from services.lead_call_engine import mark_claimed
        await mark_claimed(conv_id, body.to_user_id, via="reassigned")
    except Exception:
        pass
    to_name, prev_name, mgr = _display_name(to_rep), _display_name(prev) or "the queue", (me.get("name") or "a manager").split()[0]
    await _system_message(db, conv_id, f"Reassigned from {prev_name} to {to_name} by {mgr}" + (f": {body.note}" if body.note else ""))
    lead_name = conv.get("contact_name") or "a lead"
    try:
        from routers.push_notifications import send_push_to_user, LEAD_SOUND, LEAD_CHANNEL
        asyncio.create_task(send_push_to_user(body.to_user_id, f"Lead handed to you: {lead_name}",
                                              f"{mgr} moved this {conv.get('lead_source_name') or 'internet'} lead to you. Reply now.",
                                              f"/thread/{conv_id}", "person.fill.badge.plus", sound=LEAD_SOUND, channel_id=LEAD_CHANNEL))
    except Exception:
        pass
    docs = [{"user_id": body.to_user_id, "type": "lead_reassigned", "title": f"Lead handed to you: {lead_name}",
             "message": f"From {prev_name} · by {mgr}", "conversation_id": conv_id, "contact_id": conv.get("contact_id"),
             "read": False, "dismissed": False, "created_at": now}]
    if prev_id and prev_id != body.to_user_id:
        docs.append({"user_id": prev_id, "type": "lead_reassigned", "title": f"{lead_name} moved to {to_name}",
                     "message": f"Reassigned by {mgr}", "conversation_id": conv_id, "contact_id": conv.get("contact_id"),
                     "read": False, "dismissed": False, "created_at": now})
    await db.notifications.insert_many(docs)
    return {"success": True, "claimed_by": body.to_user_id, "claimed_by_name": to_name}


async def release_to_queue(db, conv: dict, actor_id: Optional[str], reason: str) -> dict:
    """Put a claimed lead back in the shared queue and tell the workflow reps."""
    now = datetime.now(timezone.utc)
    conv_id = str(conv["_id"])
    store_id = str(conv.get("store_id") or "")
    prev_id = str(conv.get("claimed_by") or "")
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {
        "claimed": False, "claimed_by": None, "assigned_to": None, "user_id": store_id or conv.get("user_id"),
        "routing_kind": "queue", "released_at": now, "released_by": actor_id, "release_reason": reason,
        "owner_alert_at": None, "release_at": None, "updated_at": now.isoformat(),
    }})
    if conv.get("contact_id") and ObjectId.is_valid(str(conv["contact_id"])) and store_id:
        await db.contacts.update_one({"_id": ObjectId(conv["contact_id"])},
                                     {"$set": {"user_id": store_id, "claimed_by": None, "released_from": prev_id or None, "updated_at": now.isoformat()}})
    prev = await db.users.find_one({"_id": ObjectId(prev_id)}, {"name": 1, "first_name": 1, "last_name": 1}) if ObjectId.is_valid(prev_id) else None
    actor = await db.users.find_one({"_id": ObjectId(actor_id)}, {"name": 1}) if actor_id and ObjectId.is_valid(actor_id) else None
    who = (actor or {}).get("name", "").split()[0] if actor else "Jessi"
    await _system_message(db, conv_id, f"Released back to the lead queue by {who}" + (f" ({reason})" if reason else ""))
    lead_name = conv.get("contact_name") or "A lead"
    src = await db.lead_sources.find_one({"_id": ObjectId(conv["lead_source_id"])}) if ObjectId.is_valid(str(conv.get("lead_source_id") or "")) else None
    members = [m for m in source_member_ids(src or {}) if m != prev_id]
    try:
        from routers.push_notifications import send_push_to_user, LEAD_SOUND, LEAD_CHANNEL
        for uid in members:
            asyncio.create_task(send_push_to_user(uid, f"Up for grabs: {lead_name}",
                                                  f"{_display_name(prev) or 'Their rep'} hasn't answered this {(src or {}).get('name', 'internet')} lead. Tap to claim.",
                                                  "/(tabs)/inbox?segment=leads", "flame", sound=LEAD_SOUND, channel_id=LEAD_CHANNEL))
    except Exception:
        pass
    if members:
        await db.notifications.insert_many([{
            "user_id": uid, "type": "lead_released", "title": f"Up for grabs: {lead_name}",
            "message": f"Back in the queue ({reason or 'released'})", "conversation_id": conv_id, "contact_id": conv.get("contact_id"),
            "read": False, "dismissed": False, "created_at": now} for uid in members])
    return {"success": True, "released": True, "notified": len(members)}


@router.post("/{user_id}/release/{conv_id}")
async def release_lead(user_id: str, conv_id: str):
    db = get_db()
    me = await _me(db, user_id)
    conv = await _conv(db, conv_id)
    if not me["is_manager"] and str(conv.get("claimed_by") or "") != user_id:
        raise HTTPException(status_code=403, detail="Only the rep who claimed it or a manager can release it")
    if not conv.get("claimed"):
        raise HTTPException(status_code=400, detail="Lead is already in the queue")
    return await release_to_queue(db, conv, user_id, "released by " + ("manager" if me["is_manager"] else "rep"))


# ── Scheduler jobs ────────────────────────────────────────────────────────────

async def process_returning_lead_escalations() -> dict:
    """Every minute: returning-customer leads whose owner hasn't replied -> manager alert, then auto-release."""
    db = get_db()
    now = datetime.now(timezone.utc)
    convs = await db.conversations.find({
        "is_internet_lead": True, "routing_kind": "returning_owner", "claimed": True, "status": {"$ne": "closed"},
        "$or": [{"owner_alerted": {"$ne": True}, "owner_alert_at": {"$lte": now}}, {"release_at": {"$lte": now}}],
    }).to_list(200)
    if not convs:
        return {"alerted": 0, "released": 0}
    from routers.lead_intake import _first_human_replies
    replied = await _first_human_replies(db, [str(c["_id"]) for c in convs])
    alerted = released = 0
    for c in convs:
        cid = str(c["_id"])
        if cid in replied:
            await db.conversations.update_one({"_id": c["_id"]}, {"$set": {"owner_alert_at": None, "release_at": None, "routing_resolved": True}})
            continue
        owner = await db.users.find_one({"_id": ObjectId(c["claimed_by"])}, {"name": 1}) if ObjectId.is_valid(str(c.get("claimed_by") or "")) else None
        owner_name = _display_name(owner) or "their rep"
        mins = int((now - (_utc(c.get("created_at")) or now)).total_seconds() // 60)
        release_at = _utc(c.get("release_at"))
        if release_at and release_at <= now:
            await release_to_queue(db, c, None, f"{owner_name} did not reply within {mins} min")
            released += 1
            continue
        alert_at = _utc(c.get("owner_alert_at"))
        if not c.get("owner_alerted") and alert_at and alert_at <= now:
            managers = await _store_managers(db, str(c.get("store_id") or ""))
            title = f"Lead going cold: {c.get('contact_name') or 'returning customer'}"
            body = f"Returning customer routed to {owner_name} {mins}m ago, no reply yet. Auto-releases at {int(((release_at or now) - now).total_seconds() // 60)}m. Tap to reassign."
            try:
                from routers.push_notifications import send_push_to_user
                for uid in managers:
                    asyncio.create_task(send_push_to_user(uid, title, body, "/(tabs)/inbox?segment=leads", "alert-circle"))
            except Exception:
                pass
            if managers:
                await db.notifications.insert_many([{"user_id": uid, "type": "lead_going_cold", "title": title, "message": body,
                                                     "conversation_id": cid, "contact_id": c.get("contact_id"),
                                                     "read": False, "dismissed": False, "created_at": now} for uid in managers])
            await db.conversations.update_one({"_id": c["_id"]}, {"$set": {"owner_alerted": True, "owner_alerted_at": now}})
            alerted += 1
    if alerted or released:
        logger.info(f"[LeadQueue] escalations: alerted={alerted} released={released}")
    return {"alerted": alerted, "released": released}


async def send_red_leads_digest() -> dict:
    """Every 15 min: at each store's digest hour (default 6 PM local) push managers today's speed-to-lead report."""
    db = get_db()
    now = datetime.now(timezone.utc)
    sent = 0
    store_ids = await db.conversations.distinct("store_id", {"is_internet_lead": True, "created_at": {"$gte": now - timedelta(hours=36)}})
    for sid in store_ids:
        sid = str(sid or "")
        if not ObjectId.is_valid(sid):
            continue
        store = await db.stores.find_one({"_id": ObjectId(sid)}, {"timezone": 1, "name": 1, "red_digest_sent_on": 1})
        if not store:
            continue
        sources = await _store_sources(db, sid)
        digest_hour = min([source_thresholds(s)["digest_hour"] for s in sources] or [DEFAULTS["digest_hour"]])
        try:
            tz = ZoneInfo(store.get("timezone") or "America/Denver")
        except Exception:
            tz = ZoneInfo("America/Denver")
        local = now.astimezone(tz)
        if local.hour != digest_hour or local.minute >= 15:
            continue
        today_key = local.strftime("%Y-%m-%d")
        if store.get("red_digest_sent_on") == today_key:
            continue
        day_start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        convs = await db.conversations.find({"is_internet_lead": True, "store_id": sid, "is_test": {"$ne": True},
                                             "created_at": {"$gte": day_start}}).to_list(500)
        await db.stores.update_one({"_id": store["_id"]}, {"$set": {"red_digest_sent_on": today_key}})
        if not convs:
            continue
        items = await _build_items(db, convs, {s["_id"]: s for s in sources}, now)
        fast = [i for i in items if i["first_reply_seconds"] is not None and i["first_reply_seconds"] < i["green_m"] * 60]
        red = [i for i in items if (i["first_reply_seconds"] is not None and i["first_reply_seconds"] > i["amber_m"] * 60)
               or (i["first_reply_seconds"] is None and (i["waiting_seconds"] or 0) > i["amber_m"] * 60)]
        by_rep: dict = {}
        for i in red:
            key = (i["claimed_by_name"] or "Unclaimed").split()[0]
            mins = int(((i["first_reply_seconds"] if i["first_reply_seconds"] is not None else i["waiting_seconds"]) or 0) // 60)
            by_rep.setdefault(key, []).append(f"{i['contact_name'].split()[0]} {mins}m")
        red_txt = "; ".join(f"{k}: {', '.join(v)}" for k, v in by_rep.items())
        title = f"Leads report · {len(items)} today"
        body = f"{len(fast)} answered fast · {len(red)} went red" + (f" ({red_txt})" if red_txt else " · nice work") + ". Tap for details."
        managers = await _store_managers(db, sid)
        try:
            from routers.push_notifications import send_push_to_user
            for uid in managers:
                asyncio.create_task(send_push_to_user(uid, title, body, "/leads", "stats-chart"))
        except Exception:
            pass
        if managers:
            await db.notifications.insert_many([{"user_id": uid, "type": "leads_digest", "title": title, "message": body,
                                                 "read": False, "dismissed": False, "created_at": now} for uid in managers])
        sent += 1
    return {"stores": sent}


@router.post("/{user_id}/digest/send-now")
async def digest_send_now(user_id: str):
    """Preview today's red-leads digest for my store right now (managers)."""
    db = get_db()
    me = await _me(db, user_id)
    if not me["is_manager"]:
        raise HTTPException(status_code=403, detail="Managers only")
    sid = me["store_id"]
    store = await db.stores.find_one({"_id": ObjectId(sid)}, {"timezone": 1}) if ObjectId.is_valid(sid) else None
    try:
        tz = ZoneInfo((store or {}).get("timezone") or "America/Denver")
    except Exception:
        tz = ZoneInfo("America/Denver")
    now = datetime.now(timezone.utc)
    day_start = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    sources = await _store_sources(db, sid, me)
    conv_q = {"is_internet_lead": True, "created_at": {"$gte": day_start}}
    if sid:
        conv_q["store_id"] = sid
    convs = await db.conversations.find(conv_q).to_list(500)
    items = await _build_items(db, convs, {s["_id"]: s for s in sources}, now)
    fast = sum(1 for i in items if i["first_reply_seconds"] is not None and i["first_reply_seconds"] < i["green_m"] * 60)
    red = [i for i in items if (i["first_reply_seconds"] is not None and i["first_reply_seconds"] > i["amber_m"] * 60)
           or (i["first_reply_seconds"] is None and (i["waiting_seconds"] or 0) > i["amber_m"] * 60)]
    title = f"Leads report · {len(items)} today"
    body = f"{fast} answered fast · {len(red)} went red" + (f" ({', '.join(i['contact_name'].split()[0] for i in red[:4])})" if red else " · nice work") + ". Tap for details."
    n = 0
    if items:
        from routers.push_notifications import send_push_to_user
        n = await send_push_to_user(user_id, title, body, "/leads", "stats-chart")
    return {"sent": n > 0, "title": title, "body": body, "leads": len(items), "red": len(red)}
