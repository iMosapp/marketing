"""My Team: the read-only view a dealership owner/manager gets of their reps (setup progress, texting number, last activity,
7-day counts). Counts only, never message content. Scope: org_admin = their organization, store_manager = their store,
super_admin = any organization (by id). Reuses the pilot checklist rules and the dealership sender policy."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services import pilot
from services import sender_policy

MANAGER_ROLES = ("super_admin", "org_admin", "store_manager")
HIDDEN_STATUSES = ["deactivated", "inactive"]


def _iso(v) -> Optional[str]:
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
    return v if isinstance(v, str) else None


def scope_query(viewer: dict, org_id: Optional[str] = None) -> dict:
    """Which users the viewer may see. Raises PermissionError for anyone who is not a manager of that scope."""
    role = viewer.get("role")
    if role not in MANAGER_ROLES:
        raise PermissionError("Only owners and managers can see My Team")
    if role == "super_admin":
        target = org_id or viewer.get("organization_id")
        if not target:
            raise PermissionError("Pick an organization")
        return {"organization_id": str(target)}
    own = str(viewer.get("organization_id") or "")
    if not own or (org_id and str(org_id) != own):
        raise PermissionError("You can only see your own team")
    if role == "store_manager":
        if not viewer.get("store_id"):
            raise PermissionError("Your account is not attached to a store")
        return {"organization_id": own, "store_id": str(viewer["store_id"])}
    return {"organization_id": own}


async def _per_user_counts(db, coll: str, ids: list, field: str, extra: dict, since) -> dict:
    rows = await db[coll].aggregate([
        {"$match": {"user_id": {"$in": ids}, **extra, "$or": [{field: {"$gte": since}}, {field: {"$gte": since.isoformat()}}]}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}}]).to_list(1000)
    return {r["_id"]: r["n"] for r in rows}


async def _per_user_last(db, coll: str, ids: list, field: str, extra: dict) -> dict:
    rows = await db[coll].aggregate([{"$match": {"user_id": {"$in": ids}, **extra}}, {"$group": {"_id": "$user_id", "at": {"$max": f"${field}"}}}]).to_list(1000)
    return {r["_id"]: _iso(r["at"]) for r in rows}


async def _number_state(db, uid: str) -> dict:
    from services import phone_numbers as pn
    num = await db[pn.COLL].find_one({"assigned_user_id": uid, "status": {"$ne": "RELEASED"}}, {"phone_number": 1}, sort=[("updated_at", -1)])
    phone = (num or {}).get("phone_number")
    if not phone:
        u = await db.users.find_one({"_id": ObjectId(uid)}, {"twilio_number": 1, "mvpline_number": 1})
        phone = (u or {}).get("twilio_number") or (u or {}).get("mvpline_number")
    if not phone:
        return {"status": "none", "label": "No texting number", "last4": None, "reason": sender_policy.REASONS["no_number"]}
    d = await sender_policy.check(db, from_phone=phone, user_id=uid)
    if d["allowed"]:
        return {"status": "ready", "label": "Texting ready", "last4": phone[-4:], "reason": ""}
    return {"status": "pending", "label": "Registration pending" if d["code"] in ("not_ready", "not_associated") else "Not ready",
            "last4": phone[-4:], "reason": d["reason"]}


async def team(db, viewer: dict, org_id: Optional[str] = None) -> dict:
    q = scope_query(viewer, org_id)
    users = await db.users.find({**q, "status": {"$nin": HIDDEN_STATUSES}, "_id": {"$ne": viewer.get("_id")}},
                                {"name": 1, "role": 1, "title": 1, "last_login": 1, "activation_pending": 1, "photo_url": 1, "photo_path": 1,
                                 "persona": 1, "bio": 1, "pilot_checklist": 1, "created_at": 1}).sort("name", 1).to_list(500)
    ids = [str(u["_id"]) for u in users]
    since = datetime.now(timezone.utc) - timedelta(days=7)
    shares = {"event_type": {"$in": sorted(pilot.CARD_SHARE_EVENTS)}}
    texts = {"sender": "user", "direction": "outbound"}
    contacts = {"source": {"$ne": "user_creation"}}
    week = {"contacts": await _per_user_counts(db, "contacts", ids, "created_at", contacts, since),
            "shares": await _per_user_counts(db, "contact_events", ids, "timestamp", shares, since),
            "texts": await _per_user_counts(db, "messages", ids, "timestamp", texts, since)}
    last = [await _per_user_last(db, "contact_events", ids, "timestamp", {}), await _per_user_last(db, "messages", ids, "timestamp", texts),
            await _per_user_last(db, "voice_notes", ids, "created_at", {})]
    members = []
    for u in users:
        uid = str(u["_id"])
        states = await pilot._step_states(db, u)
        done = sum(1 for k in states if states[k][0])
        stamps = [_iso(u.get("last_login"))] + [m.get(uid) for m in last]
        stamps = [s for s in stamps if isinstance(s, str)]
        members.append({
            "id": uid, "name": u.get("name") or "", "role": u.get("role"), "title": u.get("title") or "",
            "activated": bool(u.get("last_login")) and not u.get("activation_pending"), "last_sign_in": _iso(u.get("last_login")),
            "setup": {"done": done, "total": len(states)}, "number": await _number_state(db, uid),
            "last_activity": max(stamps) if stamps else None,
            "week": {"contacts": week["contacts"].get(uid, 0), "cards_shared": week["shares"].get(uid, 0), "texts_sent": week["texts"].get(uid, 0)}})
    return {"scope": "store" if "store_id" in q else "organization", "members": members, "count": len(members),
            "generated_at": datetime.now(timezone.utc).isoformat()}
