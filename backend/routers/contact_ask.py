"""Ask Jessi about a customer: grounded Q&A over every touchpoint for one contact, with citations back to the exact text / call moment."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db, get_data_filter
from services import contact_ask as ca


async def require_user(request: Request) -> dict:
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user = user
    return user


router = APIRouter(prefix="/contact-ask", tags=["Ask Jessi"], dependencies=[Depends(require_user)])


class AskBody(BaseModel):
    question: str
    session_id: Optional[str] = None


async def _contact(db, user: dict, contact_id: str) -> dict:
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    base = await get_data_filter(str(user["_id"]))
    contact = await db.contacts.find_one({"$and": [{"_id": ObjectId(contact_id)}, base]})
    if not contact:
        # customers reached through shared-inbox threads: members of the inbox, anyone the thread is assigned/shared to,
        # and managers of the inbox's store can ask about them even when the contact record belongs to someone else
        from services.inboxes import inboxes_for_user
        inbox_ids = [str(i["_id"]) for i in await inboxes_for_user(db, user)]
        ors = [{"user_id": str(user["_id"])}, {"assigned_to": str(user["_id"])}, {"collaborators": str(user["_id"])}]
        if inbox_ids:
            ors.append({"inbox_id": {"$in": inbox_ids}})
        conv = await db.conversations.find_one({"contact_id": contact_id, "$or": ors}, {"_id": 1})
        if conv:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/{contact_id}")
async def overview(contact_id: str, request: Request):
    db = get_db()
    me = request.state.user
    contact = await _contact(db, me, contact_id)
    record = await ca.build_record(db, contact, tz=me.get("timezone"))
    sessions = await db[ca.SESS].find({"user_id": str(me["_id"]), "contact_id": contact_id}, {"messages": {"$slice": -1}, "title": 1, "created_at": 1, "updated_at": 1}).sort("updated_at", -1).limit(10).to_list(10)
    counts = {s["_id"]: s["n"] async for s in db[ca.SESS].aggregate([{"$match": {"user_id": str(me["_id"]), "contact_id": contact_id}}, {"$project": {"n": {"$size": {"$ifNull": ["$messages", []]}}}}])}
    out_sessions = []
    for s in sessions:
        d = ca.serialize_session(s)
        d["message_count"] = counts.get(s["_id"], d["message_count"])
        d.pop("messages", None)
        out_sessions.append(d)
    return {"contact": {"id": contact_id, "name": contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(), "first_name": record["first_name"],
                        "photo": contact.get("photo_thumbnail") or contact.get("photo")},
            "stats": record["stats"], "starters": ca.starters(record["stats"], record["first_name"]), "sessions": out_sessions}


@router.get("/{contact_id}/sessions/{session_id}")
async def get_session(contact_id: str, session_id: str, request: Request):
    db = get_db()
    me = request.state.user
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    s = await db[ca.SESS].find_one({"_id": ObjectId(session_id), "user_id": str(me["_id"]), "contact_id": contact_id})
    if not s:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ca.serialize_session(s)


@router.delete("/{contact_id}/sessions/{session_id}")
async def delete_session(contact_id: str, session_id: str, request: Request):
    db = get_db()
    me = request.state.user
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    r = await db[ca.SESS].delete_one({"_id": ObjectId(session_id), "user_id": str(me["_id"]), "contact_id": contact_id})
    return {"deleted": r.deleted_count == 1}


@router.post("/{contact_id}/ask")
async def ask_question(contact_id: str, body: AskBody, request: Request):
    db = get_db()
    me = request.state.user
    q = (body.question or "").strip()
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Ask a question first")
    contact = await _contact(db, me, contact_id)
    now = datetime.now(timezone.utc)
    session = None
    if body.session_id and ObjectId.is_valid(body.session_id):
        session = await db[ca.SESS].find_one({"_id": ObjectId(body.session_id), "user_id": str(me["_id"]), "contact_id": contact_id})
    try:
        result = await ca.ask(db, me, contact, q, session)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jessi couldn't answer right now: {e}")
    user_msg = {"id": uuid.uuid4().hex[:12], "role": "user", "content": q, "created_at": now}
    ai_msg = {"id": uuid.uuid4().hex[:12], "role": "assistant", "content": result["answer"], "citations": result["citations"], "follow_ups": result["follow_ups"], "created_at": now}
    if session:
        await db[ca.SESS].update_one({"_id": session["_id"]}, {"$push": {"messages": {"$each": [user_msg, ai_msg]}}, "$set": {"updated_at": now}})
        session_id = str(session["_id"])
    else:
        doc = {"user_id": str(me["_id"]), "contact_id": contact_id, "contact_name": contact.get("name"), "title": q[:80], "messages": [user_msg, ai_msg], "created_at": now, "updated_at": now}
        res = await db[ca.SESS].insert_one(doc)
        session_id = str(res.inserted_id)
    ser = lambda m: {**m, "created_at": m["created_at"].isoformat()}
    return {"session_id": session_id, "user_message": ser(user_msg), "message": ser(ai_msg), "stats": result["stats"]}
