"""Shared inboxes API: department numbers worked by a team, plus ownership actions on any conversation
(claim / assign / release / move / collaborators / graduate). See services/inboxes.py for the rules."""
import logging
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from routers.database import get_db
from services import inboxes as ib

logger = logging.getLogger(__name__)


async def require_user(request: Request) -> dict:
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user = user
    return user


router = APIRouter(prefix="/inboxes", tags=["Inboxes"], dependencies=[Depends(require_user)])


class InboxBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phone_number: Optional[str] = None
    members: Optional[List[str]] = None
    member_weights: Optional[dict] = None
    routing: Optional[str] = None
    daily_cap: Optional[int] = Field(default=None, ge=0, le=500)
    first_reply: Optional[str] = None
    after_close: Optional[str] = None
    close_tag: Optional[str] = None
    bridge_text: Optional[str] = None
    ai_mode: Optional[str] = None
    va_profile_id: Optional[str] = None
    va_name: Optional[str] = None
    va_training: Optional[str] = None
    va_rules: Optional[str] = None
    va_handoff_rules: Optional[str] = None
    va_prompt_override: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    store_id: Optional[str] = None
    is_active: Optional[bool] = None


class AssignBody(BaseModel):
    user_id: str
    note: str = ""


class NoteBody(BaseModel):
    note: str = ""


class MoveBody(BaseModel):
    inbox_id: str
    user_id: Optional[str] = None
    note: str = ""


class CollaboratorBody(BaseModel):
    user_id: str
    add: bool = True


def _me(request: Request) -> dict:
    return request.state.user


def _require_manager(user: dict):
    if not ib.is_manager(user):
        raise HTTPException(status_code=403, detail="Manager or admin role required")


async def _user_cards(db, ids: list) -> dict:
    oids = [ObjectId(i) for i in ids if ObjectId.is_valid(str(i))]
    out = {}
    if not oids:
        return out
    async for u in db.users.find({"_id": {"$in": oids}}, {"name": 1, "first_name": 1, "role": 1, "photo_url": 1, "photo_thumbnail": 1,
                                                          "twilio_number": 1, "mvpline_number": 1, "status": 1}):
        out[str(u["_id"])] = {"id": str(u["_id"]), "name": u.get("name") or u.get("first_name") or "Rep", "role": u.get("role"),
                              "photo": u.get("photo_thumbnail") or u.get("photo_url"),
                              "has_number": bool(u.get("twilio_number") or u.get("mvpline_number")),
                              "active": u.get("status") != "deactivated"}
    return out


async def _number_taken(db, phone: str, exclude_inbox: Optional[ObjectId] = None) -> Optional[str]:
    variants = ib.number_variants(phone)
    if not variants:
        return None
    u = await db.users.find_one({"$or": [{"twilio_number": {"$in": variants}}, {"mvpline_number": {"$in": variants}}]}, {"name": 1})
    if u:
        return f"That number is {u.get('name') or 'a rep'}'s personal line"
    q = {"phone_number": {"$in": variants}, "is_active": {"$ne": False}}
    if exclude_inbox is not None:
        q["_id"] = {"$ne": exclude_inbox}
    other = await db[ib.COLL].find_one(q, {"name": 1})
    if other:
        return f"That number already belongs to the {other.get('name')} inbox"
    return None


def _validate(body: InboxBody):
    if body.routing is not None and body.routing not in ib.ROUTING:
        raise HTTPException(status_code=400, detail=f"routing must be one of {', '.join(ib.ROUTING)}")
    if body.after_close is not None and body.after_close not in ib.AFTER_CLOSE:
        raise HTTPException(status_code=400, detail=f"after_close must be one of {', '.join(ib.AFTER_CLOSE)}")
    if body.ai_mode is not None and body.ai_mode not in ib.AI_MODES:
        raise HTTPException(status_code=400, detail=f"ai_mode must be one of {', '.join(ib.AI_MODES)}")
    if body.name is not None and not body.name.strip():
        raise HTTPException(status_code=400, detail="Give the inbox a name")
    if body.members is not None:
        bad = [m for m in body.members if not ObjectId.is_valid(str(m))]
        if bad:
            raise HTTPException(status_code=400, detail="Invalid member id")


def _sets_from(body: InboxBody) -> dict:
    sets = {}
    data = body.model_dump(exclude_unset=True)
    if "members" in data:
        sets["assigned_user_ids"] = [str(m) for m in data.pop("members") or []]
    if "phone_number" in data:
        p = data.pop("phone_number")
        sets["phone_number"] = ib._norm(p) if p else ""
    for k, v in data.items():
        if k == "close_tag":
            v = (v or ib.DEFAULT_CLOSE_TAG).strip()
        if isinstance(v, str) and k in ("name", "description", "first_reply", "bridge_text", "va_training", "va_rules", "va_handoff_rules", "va_prompt_override", "va_name"):
            v = v.strip()
        sets[k] = v
    return sets


async def _detail(db, inbox: dict, me: dict) -> dict:
    data = ib.serialize(inbox)
    cards = await _user_cards(db, data["members"])
    data["member_details"] = [cards.get(m) or {"id": m, "name": "Removed user", "active": False} for m in data["members"]]
    data["counts"] = (await ib.counts(db, [data["id"]], str(me["_id"])))[data["id"]]
    data["is_member"] = str(me["_id"]) in data["members"]
    data["can_manage"] = ib.can_manage_inbox(me, inbox)
    base = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")
    data["webhook_url"] = f"{base}/api/admin/team/shared-inboxes/{data['id']}/webhook"
    src_count = await db.lead_sources.count_documents({"$or": [{"inbox_id": data["id"]}, {"team_id": data["id"]}], "kind": {"$ne": "inbox_direct"}})
    data["lead_source_count"] = src_count
    return data


# ── Inboxes ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_inboxes(request: Request):
    db = get_db()
    me = _me(request)
    rows = await ib.inboxes_for_user(db, me)
    ids = [str(r["_id"]) for r in rows]
    cnt = await ib.counts(db, ids, str(me["_id"]))
    all_members = {m for r in rows for m in ib.members(r)}
    cards = await _user_cards(db, list(all_members))
    out = []
    for r in rows:
        d = ib.serialize(r)
        d["counts"] = cnt[d["id"]]
        d["is_member"] = str(me["_id"]) in d["members"]
        d["can_manage"] = ib.can_manage_inbox(me, r)
        d["member_details"] = [cards.get(m) or {"id": m, "name": "Removed user", "active": False} for m in d["members"]]
        out.append(d)
    return {"inboxes": out, "can_create": ib.is_manager(me), "routing_options": list(ib.ROUTING),
            "after_close_options": list(ib.AFTER_CLOSE), "ai_modes": list(ib.AI_MODES)}


@router.get("/numbers")
async def available_numbers(request: Request, inbox_id: Optional[str] = None):
    """Twilio numbers on the account that no rep and no other inbox owns (plus this inbox's own number)."""
    db = get_db()
    _require_manager(_me(request))
    current = None
    if inbox_id and ObjectId.is_valid(inbox_id):
        cur = await ib.get_inbox(db, inbox_id)
        current = ib._norm((cur or {}).get("phone_number")) if cur and cur.get("phone_number") else None
    numbers = []
    try:
        from routers.twilio_admin import _get_twilio_client, _twilio_call
        client = _get_twilio_client()
        for tn in await _twilio_call(client.incoming_phone_numbers.list):
            numbers.append({"phone_number": tn.phone_number, "friendly_name": tn.friendly_name or tn.phone_number, "sid": tn.sid})
    except HTTPException:
        pass
    except Exception as e:
        logger.warning(f"[Inboxes] Twilio number list failed: {e}")
    if not numbers:
        async for p in db.phone_number_pool.find({"status": "pool"}, {"phone_number": 1, "twilio_sid": 1}):
            if p.get("phone_number"):
                numbers.append({"phone_number": p["phone_number"], "friendly_name": p["phone_number"], "sid": p.get("twilio_sid")})
    out = []
    for n in numbers:
        norm = ib._norm(n["phone_number"])
        if current and norm == current:
            out.append({**n, "phone_number": norm, "available": True, "current": True})
            continue
        taken = await _number_taken(db, norm)
        out.append({**n, "phone_number": norm, "available": taken is None, "current": False, "taken_by": taken})
    return {"numbers": out}


@router.get("/members/options")
async def member_options(request: Request, store_id: Optional[str] = None):
    """Teammates a user can hand a thread to / share with: managers see their store(s) / org (super admin: everyone active);
    reps see their own store plus co-members of their inboxes."""
    db = get_db()
    me = _me(request)
    role = me.get("role")
    q: dict = {"status": {"$ne": "deactivated"}}
    if not ib.is_manager(me):
        stores = ib._scope_store_ids(me)
        co = set()
        for row in await db[ib.COLL].find({"assigned_user_ids": str(me["_id"]), "is_active": {"$ne": False}}, {"assigned_user_ids": 1}).to_list(50):
            co.update(ib.members(row))
        ors = [{"_id": {"$in": [ObjectId(c) for c in co if ObjectId.is_valid(c)] + [me["_id"]]}}]
        if stores:
            ors += [{"store_id": {"$in": stores}}, {"store_ids": {"$in": stores}}]
        q["$or"] = ors
    elif role == "super_admin":
        if store_id:
            q["$or"] = [{"store_id": store_id}, {"store_ids": store_id}]
    elif role == "org_admin" and me.get("organization_id"):
        q["organization_id"] = me["organization_id"]
    else:
        stores = ib._scope_store_ids(me)
        q["$or"] = [{"store_id": {"$in": stores}}, {"store_ids": {"$in": stores}}, {"_id": me["_id"]}] if stores else [{"_id": me["_id"]}]
    users = await db.users.find(q, {"name": 1, "first_name": 1, "role": 1, "photo_url": 1, "photo_thumbnail": 1, "twilio_number": 1,
                                    "mvpline_number": 1, "store_id": 1, "title": 1}).sort("name", 1).to_list(300)
    return {"users": [{"id": str(u["_id"]), "name": u.get("name") or u.get("first_name") or "Rep", "role": u.get("role"),
                       "title": u.get("title") or "", "photo": u.get("photo_thumbnail") or u.get("photo_url"),
                       "has_number": bool(u.get("twilio_number") or u.get("mvpline_number")), "store_id": u.get("store_id")} for u in users]}


@router.post("")
async def create_inbox(body: InboxBody, request: Request):
    db = get_db()
    me = _me(request)
    _require_manager(me)
    _validate(body)
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="Give the inbox a name")
    sets = _sets_from(body)
    if sets.get("phone_number"):
        taken = await _number_taken(db, sets["phone_number"])
        if taken:
            raise HTTPException(status_code=409, detail=taken)
    store_id = body.store_id or me.get("store_id")
    if me.get("role") not in ("super_admin", "org_admin") and store_id and store_id not in ib._scope_store_ids(me):
        raise HTTPException(status_code=403, detail="You can only create inboxes for your own store")
    now = ib._now()
    doc = {"routing": "jump_ball", "after_close": "move_to_rep", "close_tag": ib.DEFAULT_CLOSE_TAG, "ai_mode": "auto_reply",
           "assigned_user_ids": [], "daily_cap": 0, **sets,
           "store_id": store_id, "organization_id": me.get("organization_id"),
           "account_id": me.get("account_id") or str(me["_id"]), "created_by": str(me["_id"]), "is_active": True,
           "created_at": now, "updated_at": now}
    res = await db[ib.COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    if doc["assigned_user_ids"]:
        await db.users.update_many({"_id": {"$in": [ObjectId(u) for u in doc["assigned_user_ids"]]}},
                                   {"$addToSet": {"shared_inbox_ids": str(res.inserted_id)}})
    await ib.ensure_direct_source(db, doc)
    return await _detail(db, await ib.get_inbox(db, res.inserted_id), me)


@router.get("/{inbox_id}")
async def get_inbox(inbox_id: str, request: Request):
    db = get_db()
    me = _me(request)
    inbox = await ib.get_inbox(db, inbox_id)
    if not inbox or inbox.get("is_active") is False:
        raise HTTPException(status_code=404, detail="Inbox not found")
    if not ib.can_manage_inbox(me, inbox) and str(me["_id"]) not in ib.members(inbox):
        raise HTTPException(status_code=403, detail="You're not on this inbox")
    return await _detail(db, inbox, me)


@router.put("/{inbox_id}")
async def update_inbox(inbox_id: str, body: InboxBody, request: Request):
    db = get_db()
    me = _me(request)
    inbox = await ib.get_inbox(db, inbox_id)
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    if not ib.can_manage_inbox(me, inbox):
        raise HTTPException(status_code=403, detail="Manager or admin role required")
    _validate(body)
    sets = _sets_from(body)
    if not sets:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if sets.get("phone_number") and sets["phone_number"] != ib._norm(inbox.get("phone_number") or ""):
        taken = await _number_taken(db, sets["phone_number"], exclude_inbox=inbox["_id"])
        if taken:
            raise HTTPException(status_code=409, detail=taken)
    sets["updated_at"] = ib._now()
    await db[ib.COLL].update_one({"_id": inbox["_id"]}, {"$set": sets})
    if "assigned_user_ids" in sets:
        old, new = set(ib.members(inbox)), set(sets["assigned_user_ids"])
        if old - new:
            await db.users.update_many({"_id": {"$in": [ObjectId(u) for u in old - new]}}, {"$pull": {"shared_inbox_ids": inbox_id}})
        if new - old:
            await db.users.update_many({"_id": {"$in": [ObjectId(u) for u in new - old]}}, {"$addToSet": {"shared_inbox_ids": inbox_id}})
    fresh = await ib.get_inbox(db, inbox_id)
    await ib.ensure_direct_source(db, fresh)
    if "phone_number" in sets and sets["phone_number"]:
        await db.conversations.update_many({"inbox_id": inbox_id, "graduated_at": None}, {"$set": {"rep_phone": sets["phone_number"]}})
    if "name" in sets:
        await db.conversations.update_many({"inbox_id": inbox_id}, {"$set": {"inbox_name": sets["name"]}})
    return await _detail(db, fresh, me)


@router.delete("/{inbox_id}")
async def delete_inbox(inbox_id: str, request: Request, force: bool = False):
    db = get_db()
    me = _me(request)
    inbox = await ib.get_inbox(db, inbox_id)
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    if not ib.can_manage_inbox(me, inbox):
        raise HTTPException(status_code=403, detail="Manager or admin role required")
    live = await db.conversations.count_documents({"inbox_id": inbox_id, "graduated_at": None, "status": {"$nin": ["closed", "archived"]}})
    if live and not force:
        raise HTTPException(status_code=409, detail=f"{live} open conversation{'s' if live != 1 else ''} still live in this inbox. Move them first or delete anyway.")
    await db[ib.COLL].update_one({"_id": inbox["_id"]}, {"$set": {"is_active": False, "deleted_at": ib._now(), "deleted_by": str(me["_id"])}})
    await db.users.update_many({"shared_inbox_ids": inbox_id}, {"$pull": {"shared_inbox_ids": inbox_id}})
    await db.lead_sources.update_many({"kind": "inbox_direct", "inbox_id": inbox_id}, {"$set": {"is_active": False}})
    return {"success": True, "id": inbox_id, "live_conversations": live}


# ── Conversations in an inbox ────────────────────────────────────────────────

def _row(c: dict, cards: dict, me_id: str) -> dict:
    owner = c.get("assigned_to")
    lm = c.get("last_message_at")
    return {
        "id": str(c["_id"]), "contact_id": c.get("contact_id"), "contact_name": c.get("contact_name"), "contact_phone": c.get("contact_phone"),
        "last_message": c.get("last_message"), "last_message_at": lm.isoformat() if hasattr(lm, "isoformat") else lm,
        "last_message_from": c.get("last_message_from"), "unread": bool(c.get("unread")), "unread_count": c.get("unread_count", 0),
        "status": c.get("status"), "inbox_id": c.get("inbox_id"), "inbox_name": c.get("inbox_name"),
        "assigned_to": owner, "assigned_to_name": (cards.get(owner) or {}).get("name") if owner else None,
        "is_mine": owner == me_id, "collaborators": c.get("collaborators") or [],
        "is_collaborator": me_id in (c.get("collaborators") or []),
        "needs_assistance": bool(c.get("needs_assistance")), "ai_mode": c.get("ai_mode"), "is_internet_lead": bool(c.get("is_internet_lead")),
        "lead_source_name": c.get("lead_source_name"), "handoff_note": c.get("handoff_note"),
    }


@router.get("/{inbox_id}/conversations")
async def inbox_conversations(inbox_id: str, request: Request, view: str = "all", limit: int = 100):
    db = get_db()
    me = _me(request)
    inbox = await ib.get_inbox(db, inbox_id)
    if not inbox or inbox.get("is_active") is False:
        raise HTTPException(status_code=404, detail="Inbox not found")
    me_id = str(me["_id"])
    if not ib.can_manage_inbox(me, inbox) and me_id not in ib.members(inbox):
        raise HTTPException(status_code=403, detail="You're not on this inbox")
    q: dict = {"inbox_id": inbox_id, "graduated_at": None, "status": {"$nin": ["closed", "archived"]}}
    if view == "unassigned":
        q["$or"] = [{"assigned_to": None}, {"assigned_to": {"$exists": False}}, {"assigned_to": ""}]
    elif view == "mine":
        q["$or"] = [{"assigned_to": me_id}, {"collaborators": me_id}]
    elif view == "unread":
        q["unread"] = True
    convs = await db.conversations.find(q).sort([("unread", -1), ("last_message_at", -1)]).limit(min(limit, 300)).to_list(300)
    cards = await _user_cards(db, [c.get("assigned_to") for c in convs if c.get("assigned_to")])
    return {"inbox": ib.serialize(inbox), "conversations": [_row(c, cards, me_id) for c in convs],
            "counts": (await ib.counts(db, [inbox_id], me_id))[inbox_id]}


# ── Ownership actions on a conversation ──────────────────────────────────────

async def _conv(db, conv_id: str) -> dict:
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id)}) if ObjectId.is_valid(conv_id) else None
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


async def _can_see(db, me: dict, conv: dict) -> bool:
    me_id = str(me["_id"])
    if ib.is_manager(me) or str(conv.get("user_id") or "") == me_id or conv.get("assigned_to") == me_id or me_id in (conv.get("collaborators") or []):
        return True
    if conv.get("inbox_id"):
        inbox = await ib.get_inbox(db, conv["inbox_id"])
        return bool(inbox) and me_id in ib.members(inbox)
    return False


def _hist(h: dict) -> dict:
    at = h.get("at")
    return {**h, "at": at.isoformat() if hasattr(at, "isoformat") else at}


@router.get("/conversations/{conv_id}/ownership")
async def ownership(conv_id: str, request: Request):
    """Everything the thread details sheet needs: who owns it, who's on it, where it lives, what the caller may do."""
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    if not await _can_see(db, me, conv):
        raise HTTPException(status_code=403, detail="Not your conversation")
    me_id = str(me["_id"])
    owner = ib.owner_of(conv) or (str(conv.get("user_id")) if not conv.get("inbox_id") else "")
    if owner == str(conv.get("store_id") or ""):
        owner = ""
    inbox = await ib.get_inbox(db, conv["inbox_id"]) if conv.get("inbox_id") else None
    collabs = [c for c in (conv.get("collaborators") or []) if c]
    hist = conv.get("assignment_history") or []
    cards = await _user_cards(db, [owner] + collabs + (ib.members(inbox) if inbox else []) + [h.get("by") for h in hist] + [h.get("to") for h in hist] + [h.get("from") for h in hist])
    is_owner = bool(owner) and owner == me_id
    manager = ib.is_manager(me)
    member = bool(inbox) and me_id in ib.members(inbox)
    unassigned = not owner
    visible = await ib.inboxes_for_user(db, me)
    graduated = bool(conv.get("graduated_at"))
    from_inbox = await ib.get_inbox(db, conv["from_inbox_id"]) if graduated and conv.get("from_inbox_id") else None
    return {
        "conversation_id": conv_id,
        "inbox": ib.serialize(inbox) if inbox else None,
        "graduated": graduated, "graduated_from": ib.serialize(from_inbox) if from_inbox else None,
        "from_number": conv.get("rep_phone"),
        "owner": cards.get(owner) if owner else None,
        "collaborators": [cards.get(c) or {"id": c, "name": "Removed user"} for c in collabs],
        "history": [{**_hist(h), "by_name": (cards.get(h.get("by")) or {}).get("name"), "to_name": (cards.get(h.get("to")) or {}).get("name"),
                     "from_name": (cards.get(h.get("from")) or {}).get("name")} for h in hist[-20:]],
        "handoff_note": conv.get("handoff_note"),
        "can": {
            "claim": unassigned and (member or manager) and not graduated,
            "assign": manager or is_owner,
            "release": bool(inbox) and not graduated and bool(owner) and (manager or is_owner),
            "move": manager,
            "share": manager or is_owner or (not inbox and str(conv.get("user_id")) == me_id),
            "graduate": bool(inbox) and not graduated and bool(owner) and (manager or is_owner),
        },
        "inboxes": [{"id": str(i["_id"]), "name": i.get("name"), "color": i.get("color") or "#C9A962", "members": ib.members(i)} for i in visible],
        "members": [cards.get(m) or {"id": m, "name": "Rep"} for m in ib.members(inbox)] if inbox else [],
    }


def _err(e: Exception):
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    raise e


@router.post("/conversations/{conv_id}/claim")
async def claim(conv_id: str, request: Request):
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    if ib.owner_of(conv) and ib.owner_of(conv) != str(conv.get("store_id") or ""):
        owner = await db.users.find_one({"_id": ObjectId(ib.owner_of(conv))}, {"name": 1}) if ObjectId.is_valid(ib.owner_of(conv)) else None
        raise HTTPException(status_code=409, detail=f"{(owner or {}).get('name') or 'Someone'} already has this one")
    try:
        res = await ib.assign_conversation(db, conv, me, str(me["_id"]))
    except Exception as e:
        _err(e)
    return res


@router.post("/conversations/{conv_id}/assign")
async def assign(conv_id: str, body: AssignBody, request: Request):
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    if not ObjectId.is_valid(body.user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    try:
        res = await ib.assign_conversation(db, conv, me, body.user_id, body.note)
    except Exception as e:
        _err(e)
    return res


@router.post("/conversations/{conv_id}/release")
async def release(conv_id: str, request: Request, body: Optional[NoteBody] = None):
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    try:
        res = await ib.release_conversation(db, conv, me, (body or NoteBody()).note)
    except Exception as e:
        _err(e)
    return res


@router.post("/conversations/{conv_id}/move")
async def move(conv_id: str, body: MoveBody, request: Request):
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    if not ObjectId.is_valid(body.inbox_id):
        raise HTTPException(status_code=400, detail="Invalid inbox id")
    try:
        res = await ib.move_conversation(db, conv, me, body.inbox_id, body.user_id, body.note)
    except Exception as e:
        _err(e)
    return res


@router.post("/conversations/{conv_id}/collaborators")
async def collaborators(conv_id: str, body: CollaboratorBody, request: Request):
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    if not ObjectId.is_valid(body.user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    try:
        res = await ib.set_collaborator(db, conv, me, body.user_id, body.add)
    except Exception as e:
        _err(e)
    return res


@router.post("/conversations/{conv_id}/graduate")
async def graduate(conv_id: str, request: Request):
    """Manually move an inbox thread onto its owner's own line (same as the closing tag would)."""
    db = get_db()
    me = _me(request)
    conv = await _conv(db, conv_id)
    if not conv.get("inbox_id") or conv.get("graduated_at"):
        raise HTTPException(status_code=400, detail="This conversation isn't in a shared inbox")
    owner = ib.owner_of(conv)
    if not owner:
        raise HTTPException(status_code=400, detail="Claim it first, then move it to a personal line")
    if not ib.is_manager(me) and owner != str(me["_id"]):
        raise HTTPException(status_code=403, detail="Only the owner or a manager can do that")
    res = await ib.graduate_conversation(db, conv, actor_id=str(me["_id"]), reason="moved by " + ((me.get("name") or "manager").split()[0]))
    if not res.get("success"):
        raise HTTPException(status_code=409, detail="That rep has no personal number yet; assign one in Twilio Numbers first")
    return res
