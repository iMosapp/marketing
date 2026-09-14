"""One answer to "who is on this store's team?" for shared inboxes, lead sources and lead flow ladders.

The team = people linked to the store (store_id / store_ids) + the store's org admins + members of the store's
shared inboxes + the caller. Every picker that puts someone on a ladder or an inbox reads from here, so a rep who
shows up in one place shows up in all of them."""
from typing import Optional

from bson import ObjectId

RANK = {"user": 0, "salesperson": 0, "store_manager": 1, "manager": 1, "org_admin": 2, "admin": 2, "super_admin": 3}
ADMIN_ROLES = ("org_admin", "admin", "super_admin")
PROJ = {"name": 1, "first_name": 1, "last_name": 1, "email": 1, "role": 1, "title": 1, "phone": 1, "twilio_number": 1,
        "mvpline_number": 1, "photo_url": 1, "photo_thumbnail": 1, "store_id": 1, "store_ids": 1, "organization_id": 1, "status": 1}
ACTIVE = {"status": {"$ne": "deactivated"}, "active": {"$ne": False}}


def _sid_values(sid: str) -> list:
    return [sid] + ([ObjectId(sid)] if ObjectId.is_valid(sid) else [])


def _card(u: dict, via: list) -> dict:
    uid = str(u["_id"])
    name = u.get("name") or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("email") or "Rep"
    return {"_id": uid, "id": uid, "name": name, "email": u.get("email", ""), "role": u.get("role", "user"), "title": u.get("title") or "",
            "phone": u.get("phone", ""), "has_number": bool(u.get("twilio_number") or u.get("mvpline_number")),
            "photo_url": u.get("photo_url"), "photo": u.get("photo_thumbnail") or u.get("photo_url"),
            "store_id": str(u.get("store_id")) if u.get("store_id") else None, "via": via, "on_team": bool(via)}


async def store_inbox_member_ids(db, store_id: Optional[str], inbox_ids: Optional[list] = None) -> set:
    """Members of the given inboxes, or of every active inbox on the store."""
    q: dict = {"is_active": {"$ne": False}}
    if inbox_ids:
        q["_id"] = {"$in": [ObjectId(i) for i in inbox_ids if ObjectId.is_valid(str(i))]}
    elif store_id:
        q["store_id"] = {"$in": _sid_values(store_id)}
    else:
        return set()
    out: set = set()
    async for row in db.shared_inboxes.find(q, {"assigned_user_ids": 1}):
        out.update(str(u) for u in row.get("assigned_user_ids") or [] if u)
    return out


async def eligible_people(db, store_id: Optional[str], me: Optional[dict] = None, inbox_ids: Optional[list] = None,
                          include_everyone: bool = False) -> dict:
    """{people: [...], store_name}. Each person carries `via` (store | inbox | org | you) and `on_team`.
    include_everyone appends every other active user (on_team False) so super admins can still add anyone."""
    sid = str(store_id) if store_id else ""
    store = await db.stores.find_one({"_id": ObjectId(sid)}, {"name": 1, "organization_id": 1}) if ObjectId.is_valid(sid) else None
    inbox_members = await store_inbox_member_ids(db, sid, inbox_ids)
    ors: list = []
    if sid:
        ors += [{"store_id": {"$in": _sid_values(sid)}}, {"store_ids": {"$in": _sid_values(sid)}}]
    org_id = (store or {}).get("organization_id")
    if org_id:
        ors.append({"organization_id": {"$in": [org_id, str(org_id)]}, "role": {"$in": list(ADMIN_ROLES)}})
    if inbox_members:
        ors.append({"_id": {"$in": [ObjectId(i) for i in inbox_members if ObjectId.is_valid(i)]}})
    if me:
        ors.append({"_id": ObjectId(str(me["_id"]))})
    people: dict = {}
    if ors:
        async for u in db.users.find({**ACTIVE, "$or": ors}, PROJ).limit(500):
            via = []
            if sid and (str(u.get("store_id") or "") == sid or sid in [str(s) for s in u.get("store_ids") or []]):
                via.append("store")
            if str(u["_id"]) in inbox_members:
                via.append("inbox")
            if org_id and str(u.get("organization_id") or "") == str(org_id) and u.get("role") in ADMIN_ROLES and "store" not in via:
                via.append("org")
            if me and str(u["_id"]) == str(me["_id"]):
                via.append("you")
            people[str(u["_id"])] = _card(u, via)
    if include_everyone:
        async for u in db.users.find({**ACTIVE, "_id": {"$nin": [ObjectId(i) for i in people]}}, PROJ).sort("name", 1).limit(1000):
            people[str(u["_id"])] = _card(u, [])
    rows = list(people.values())
    rows.sort(key=lambda r: (0 if r["on_team"] else 1, RANK.get(r["role"], 1), r["name"].lower()))
    return {"people": rows, "store_name": (store or {}).get("name"), "store_id": sid or None}


async def link_to_store(db, user_ids: list, store_id: Optional[str]) -> int:
    """Putting someone on a store's inbox makes them part of that store's team: no store yet -> store_id,
    another home store -> added to store_ids. Super admins are left alone (they already see everything)."""
    sid = str(store_id) if store_id else ""
    if not ObjectId.is_valid(sid) or not user_ids:
        return 0
    oids = [ObjectId(u) for u in user_ids if ObjectId.is_valid(str(u))]
    n = 0
    async for u in db.users.find({"_id": {"$in": oids}}, {"store_id": 1, "store_ids": 1, "role": 1}):
        if u.get("role") == "super_admin":
            continue
        cur = str(u.get("store_id") or "")
        extra = [str(s) for s in u.get("store_ids") or []]
        if cur == sid or sid in extra:
            continue
        if not cur:
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"store_id": sid}})
        else:
            await db.users.update_one({"_id": u["_id"]}, {"$addToSet": {"store_ids": sid}})
        n += 1
    return n
