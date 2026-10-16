"""Which contacts a {user_id} route may act on: the rep's own, those of reps they manage (get_data_filter) and, for messaging,
contacts whose thread is assigned or shared with them. Anything else answers 404, so a contact id from another dealership
can't be used to open a conversation, send a text or attach a recording."""
from bson import ObjectId
from fastapi import HTTPException

from routers.database import get_data_filter
from services import contact_access_audit


async def owned_contact(db, user_id: str, contact_id: str, projection: dict | None = None, shared_thread: bool = False) -> dict:
    cid = str(contact_id or "")
    if not ObjectId.is_valid(cid):
        raise HTTPException(status_code=404, detail="Contact not found")
    scope = await get_data_filter(str(user_id))
    contact = await db.contacts.find_one({"$and": [{"_id": ObjectId(cid)}, scope]}, projection)
    if contact:
        await contact_access_audit.note(db, cid, contact=contact)
        return contact
    if shared_thread:
        from services.inboxes import access_filter
        thread = await db.conversations.find_one({"$and": [{"contact_id": cid}, await access_filter(db, str(user_id), scope)]}, {"_id": 1})
        if thread:
            contact = await db.contacts.find_one({"_id": ObjectId(cid)}, projection)
            if contact:
                return contact
    raise HTTPException(status_code=404, detail="Contact not found")


async def owned_by_a_person(db, contact: dict | None) -> bool:
    """True when the contact belongs to an individual salesperson (its user_id is a user), False for store-owned / unassigned leads."""
    owner = str((contact or {}).get("user_id") or "")
    return ObjectId.is_valid(owner) and bool(await db.users.find_one({"_id": ObjectId(owner)}, {"_id": 1}))


async def relationship_ok(db, caller_id: str, contact: dict) -> bool:
    """May this caller see the contact's private relationship data (notes, personal details, memos, intelligence)? The owner, the owner's
    managers (data scope) and super admins; store-owned / unassigned leads stay open to whoever can see their thread."""
    caller = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1}) if ObjectId.is_valid(str(caller_id)) else None
    if not caller:
        return False
    if caller.get("role") == "super_admin":
        return True
    if await db.contacts.find_one({"$and": [{"_id": contact["_id"]}, await get_data_filter(str(caller_id))]}, {"_id": 1}):
        return True
    return not await owned_by_a_person(db, contact)


async def contact_visible(db, scope_user_id: str, caller_id: str, contact_id: str, conversation_ok: bool = False) -> bool:
    """Identity-middleware check for every signed-in route with a {contact_id}: the contact is inside the {user_id}'s data scope (that id
    is already bound to the caller or a user they manage) or the caller's own scope when the route has no {user_id}. Seeing one of its
    threads (own, assigned, shared, or in an inbox they belong to / manage) is enough only for conversation routes (conversation_ok) or
    for store-owned / unassigned leads: a teammate's own customer never opens their notes, memos or intelligence through a shared thread.
    Super admins pass and are audited. A valid contact id on its own grants nothing. Non-ObjectId values are left to the handler."""
    cid = str(contact_id or "")
    if not ObjectId.is_valid(cid):
        return True
    caller = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1, "organization_id": 1, "store_id": 1, "store_ids": 1}) if ObjectId.is_valid(str(caller_id)) else None
    if not caller:
        return False
    if caller.get("role") == "super_admin":
        await contact_access_audit.note(db, cid)
        return True
    if await db.contacts.find_one({"$and": [{"_id": ObjectId(cid)}, await get_data_filter(str(scope_user_id))]}, {"_id": 1}):
        return True
    if not conversation_ok and await owned_by_a_person(db, await db.contacts.find_one({"_id": ObjectId(cid)}, {"user_id": 1})):
        return False
    from services.inboxes import inboxes_for_user
    uid = str(caller["_id"])
    ors = [{"user_id": uid}, {"assigned_to": uid}, {"collaborators": uid}]
    inbox_ids = [str(i["_id"]) for i in await inboxes_for_user(db, caller)]
    if inbox_ids:
        ors.append({"inbox_id": {"$in": inbox_ids}})
    return bool(await db.conversations.find_one({"contact_id": cid, "$or": ors}, {"_id": 1}))


async def contacts_in_scope(db, user_id: str, contact_ids: list) -> list:
    """The subset of contact_ids (strings) the user may act on, in the given order."""
    oids = [ObjectId(str(c)) for c in contact_ids or [] if ObjectId.is_valid(str(c))]
    if not oids:
        return []
    scope = await get_data_filter(str(user_id))
    ok = {str(d["_id"]) async for d in db.contacts.find({"$and": [{"_id": {"$in": oids}}, scope]}, {"_id": 1})}
    return [str(c) for c in contact_ids if str(c) in ok]
