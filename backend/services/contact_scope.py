"""Which contacts a {user_id} route may act on: the rep's own, those of reps they manage (get_data_filter) and, for messaging,
contacts whose thread is assigned or shared with them. Anything else answers 404, so a contact id from another dealership
can't be used to open a conversation, send a text or attach a recording."""
from bson import ObjectId
from fastapi import HTTPException

from routers.database import get_data_filter


async def owned_contact(db, user_id: str, contact_id: str, projection: dict | None = None, shared_thread: bool = False) -> dict:
    cid = str(contact_id or "")
    if not ObjectId.is_valid(cid):
        raise HTTPException(status_code=404, detail="Contact not found")
    scope = await get_data_filter(str(user_id))
    contact = await db.contacts.find_one({"$and": [{"_id": ObjectId(cid)}, scope]}, projection)
    if contact:
        return contact
    if shared_thread:
        from services.inboxes import access_filter
        thread = await db.conversations.find_one({"$and": [{"contact_id": cid}, await access_filter(db, str(user_id), scope)]}, {"_id": 1})
        if thread:
            contact = await db.contacts.find_one({"_id": ObjectId(cid)}, projection)
            if contact:
                return contact
    raise HTTPException(status_code=404, detail="Contact not found")
