"""Power dialer API: campaigns, lead lists, live sessions, dispositions, the DNC lists and the compliance log."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import compliance as comp
from services import dialer as eng

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dialer", tags=["Power Dialer"], dependencies=[Depends(require_user)])


class CampaignBody(BaseModel):
    name: Optional[str] = None
    store_id: Optional[str] = None
    audience: Optional[str] = None
    lines: Optional[int] = None
    connect_mode: Optional[str] = None
    recording: Optional[str] = None
    voicemail: Optional[str] = None
    hours: Optional[dict] = None
    max_attempts: Optional[int] = None
    retry_hours: Optional[int] = None
    max_per_day: Optional[int] = None
    allow_registry_b2b: Optional[bool] = None
    script: Optional[str] = None
    rep_ids: Optional[list] = None
    caller_id: Optional[str] = None
    seller_name: Optional[str] = None
    ghl: Optional[dict] = None
    status: Optional[str] = None


class CsvBody(BaseModel):
    csv: str


class TagBody(BaseModel):
    tag: Optional[str] = None
    query: Optional[str] = None


class SessionBody(BaseModel):
    campaign_id: str


class DispositionBody(BaseModel):
    attempt_id: Optional[str] = None
    disposition: str
    notes: str = ""
    callback_at: Optional[datetime] = None


class DncBody(BaseModel):
    phone: str
    note: str = ""


class RegistryBody(BaseModel):
    text: str


def _oid(v: str, what: str = "Campaign") -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=400, detail=f"Bad {what.lower()} id")
    return ObjectId(str(v))


async def _me(request: Request) -> dict:
    me = await _resolve(request)
    if not await eng.available(get_db(), me):
        raise HTTPException(status_code=403, detail="The power dialer is not released yet")
    return me


def _manager(me: dict):
    if not eng.is_manager(me):
        raise HTTPException(status_code=403, detail="Managers run campaigns")


async def _campaign(db, me: dict, cid: str, manage: bool = False) -> dict:
    c = await db[eng.CAMPAIGNS].find_one({"_id": _oid(cid), **eng.campaign_scope(me)}) if not manage else await db[eng.CAMPAIGNS].find_one({"_id": _oid(cid)})
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if manage:
        _manager(me)
        scope = eng.campaign_scope(me)
        if scope and not await db[eng.CAMPAIGNS].find_one({"_id": c["_id"], **scope}):
            raise HTTPException(status_code=403, detail="Not your campaign")
    return c


# ── config ────────────────────────────────────────────────────────────────────
@router.get("/config")
async def config(request: Request):
    db = get_db()
    me = await _resolve(request)
    from services import lab
    avail = await eng.available(db, me)
    out = {"available": avail, "is_manager": eng.is_manager(me), "live": await lab.is_live(db, eng.LAB_KEY), "dispositions": eng.DISPOSITIONS, "max_lines": eng.MAX_LINES,
           "defaults": eng.DEFAULTS, "has_phone": bool(me.get("phone")), "has_number": bool(me.get("twilio_number") or me.get("mvpline_number")),
           "rules": comp.rules_table(), "all_party_states": sorted(comp.ALL_PARTY_RECORDING)}
    if avail:
        s = await eng.active_session(db, str(me["_id"]))
        out["active_session_id"] = str(s["_id"]) if s else None
        out["registry"] = await comp.registry_stats(db)
    return out


# ── campaigns ─────────────────────────────────────────────────────────────────
@router.get("/campaigns")
async def list_campaigns(request: Request):
    db = get_db()
    me = await _me(request)
    rows = await db[eng.CAMPAIGNS].find(eng.campaign_scope(me)).sort("created_at", -1).to_list(200)
    return {"campaigns": [await eng.serialize_campaign(db, c) for c in rows], "is_manager": eng.is_manager(me)}


@router.post("/campaigns")
async def create_campaign(body: CampaignBody, request: Request):
    db = get_db()
    me = await _me(request)
    _manager(me)
    c = await eng.create_campaign(db, me, body.model_dump(exclude_none=True))
    return await eng.serialize_campaign(db, c, with_stats=True)


@router.get("/campaigns/{cid}")
async def get_campaign(cid: str, request: Request):
    db = get_db()
    me = await _me(request)
    return await eng.serialize_campaign(db, await _campaign(db, me, cid), with_stats=True)


@router.patch("/campaigns/{cid}")
async def update_campaign(cid: str, body: CampaignBody, request: Request):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid, manage=True)
    upd = eng.clean_settings(body.model_dump(exclude_none=True))
    if body.name is not None:
        upd["name"] = " ".join(body.name.split())[:80] or c["name"]
    if body.status in ("active", "paused", "done"):
        upd["status"] = body.status
    upd["updated_at"] = eng._now()
    await db[eng.CAMPAIGNS].update_one({"_id": c["_id"]}, {"$set": upd})
    return await eng.serialize_campaign(db, await db[eng.CAMPAIGNS].find_one({"_id": c["_id"]}), with_stats=True)


@router.delete("/campaigns/{cid}")
async def delete_campaign(cid: str, request: Request):
    """Removes the campaign and its lead list. The attempt log (compliance record) is kept."""
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid, manage=True)
    if await db[eng.SESSIONS].find_one({"campaign_id": str(c["_id"]), "status": {"$ne": "ended"}}):
        raise HTTPException(status_code=409, detail="Someone is dialing this campaign right now")
    await db[eng.LEADS].delete_many({"campaign_id": str(c["_id"])})
    await db[eng.CAMPAIGNS].delete_one({"_id": c["_id"]})
    return {"deleted": True}


@router.get("/campaigns/{cid}/leads")
async def list_leads(cid: str, request: Request, status: Optional[str] = None, q: Optional[str] = None, skip: int = 0, limit: int = 100):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid)
    flt = {"campaign_id": str(c["_id"])}
    if status:
        flt["status"] = {"$in": status.split(",")}
    if q:
        rx = {"$regex": q.strip(), "$options": "i"}
        flt["$or"] = [{"first_name": rx}, {"last_name": rx}, {"company": rx}, {"phone": {"$regex": "".join(ch for ch in q if ch.isdigit()) or q}}]
    total = await db[eng.LEADS].count_documents(flt)
    rows = await db[eng.LEADS].find(flt).sort([("status", 1), ("prio", 1), ("_id", 1)]).skip(max(0, skip)).limit(max(1, min(limit, 500))).to_list(500)
    return {"total": total, "leads": [eng.serialize_lead(l) for l in rows]}


@router.post("/campaigns/{cid}/import/csv")
async def import_csv(cid: str, body: CsvBody, request: Request):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid, manage=True)
    rows = eng.parse_csv_leads(body.csv)
    if not rows:
        raise HTTPException(status_code=400, detail="No rows found. The first line must be column names (phone, first name, last name, company...)")
    if len(rows) > 20000:
        raise HTTPException(status_code=400, detail="Max 20,000 rows per import")
    return await eng.import_rows(db, c, rows, "csv", me)


@router.post("/campaigns/{cid}/import/contacts")
async def import_contacts(cid: str, body: TagBody, request: Request):
    """Pull the caller's (or, for managers, the store's) contacts that carry a tag into the campaign."""
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid, manage=True)
    tag = (body.tag or "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Pick a tag")
    owner_ids = [str(me["_id"])] + [str(r) for r in (c.get("rep_ids") or [])]
    if c.get("store_id"):
        owner_ids += [str(u["_id"]) async for u in db.users.find({"$or": [{"store_id": c["store_id"]}, {"store_ids": c["store_id"]}]}, {"_id": 1})]
    cur = db.contacts.find({"user_id": {"$in": list(set(owner_ids))}, "tags": {"$regex": f"^{__import__('re').escape(tag)}$", "$options": "i"}, "status": {"$ne": "purged"}, "phone": {"$nin": [None, ""]}},
                           {"first_name": 1, "last_name": 1, "phone": 1, "email": 1, "organization_name": 1, "employer": 1, "address_state": 1, "address_city": 1, "notes": 1, "do_not_call": 1, "opted_out": 1}).limit(20000)
    rows = []
    async for ct in cur:
        if ct.get("do_not_call"):
            continue
        rows.append({"phone": ct.get("phone"), "first_name": ct.get("first_name"), "last_name": ct.get("last_name"), "email": ct.get("email"), "company": ct.get("organization_name") or ct.get("employer"),
                     "state": ct.get("address_state"), "city": ct.get("address_city"), "notes": (ct.get("notes") or "")[:500], "contact_id": str(ct["_id"])})
    return await eng.import_rows(db, c, rows, "contacts", me)


@router.post("/campaigns/{cid}/import/ghl")
async def import_ghl(cid: str, body: TagBody, request: Request):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid, manage=True)
    from services import ghl
    conn = await ghl.connection_for_campaign(db, c)
    if not conn:
        raise HTTPException(status_code=404, detail="Connect GoHighLevel for this store first")
    try:
        rows = await ghl.search_contacts(conn, tag=body.tag, query=body.query)
    except ghl.GhlError as e:
        raise HTTPException(status_code=400, detail=e.message)
    if body.tag:
        await db[eng.CAMPAIGNS].update_one({"_id": c["_id"]}, {"$set": {"ghl.tag": body.tag.strip()}})
    res = await eng.import_rows(db, c, rows, "ghl", me)
    await db[ghl.COLL].update_one({"_id": conn["_id"]}, {"$set": {"last_sync": eng._now().isoformat()}})
    return {**res, "pulled": len(rows)}


@router.post("/campaigns/{cid}/rescrub")
async def rescrub(cid: str, request: Request):
    db = get_db()
    me = await _me(request)
    return await eng.rescrub(db, await _campaign(db, me, cid, manage=True))


@router.post("/campaigns/{cid}/leads/{lead_id}/dnc")
async def lead_dnc(cid: str, lead_id: str, request: Request):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid)
    lead = await db[eng.LEADS].find_one({"_id": _oid(lead_id, "Lead"), "campaign_id": str(c["_id"])})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await comp.add_dnc(db, lead["phone"], "rep", by=str(me["_id"]), campaign_id=str(c["_id"]), note="Marked from the lead list")
    return eng.serialize_lead(await db[eng.LEADS].find_one({"_id": lead["_id"]}))


@router.delete("/campaigns/{cid}/leads/{lead_id}")
async def delete_lead(cid: str, lead_id: str, request: Request):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid, manage=True)
    res = await db[eng.LEADS].delete_one({"_id": _oid(lead_id, "Lead"), "campaign_id": str(c["_id"]), "status": {"$ne": "calling"}})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Lead not found (or being dialed)")
    return {"deleted": True}


@router.get("/campaigns/{cid}/attempts")
async def list_attempts(cid: str, request: Request, limit: int = 100, skip: int = 0):
    """The compliance log: every dial with time, local time, outcome, abandonment flag and disposition."""
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, cid)
    flt = {"campaign_id": str(c["_id"])}
    if not eng.is_manager(me):
        flt["user_id"] = str(me["_id"])
    rows = await db[eng.ATTEMPTS].find(flt).sort("started_at", -1).skip(max(0, skip)).limit(max(1, min(limit, 500))).to_list(500)
    names = {str(u["_id"]): u.get("name") or u.get("first_name") for u in await db.users.find({"_id": {"$in": [ObjectId(a["user_id"]) for a in rows if ObjectId.is_valid(a.get("user_id", ""))]}}, {"name": 1, "first_name": 1}).to_list(100)}
    return {"total": await db[eng.ATTEMPTS].count_documents(flt), "attempts": [{**eng.serialize_attempt(a), "rep_name": names.get(a.get("user_id"))} for a in rows]}


# ── sessions ──────────────────────────────────────────────────────────────────
@router.get("/sessions/active")
async def my_active_session(request: Request):
    db = get_db()
    me = await _me(request)
    s = await eng.active_session(db, str(me["_id"]))
    return {"session": await eng.session_view(db, s) if s else None}


@router.post("/sessions")
async def start_session(body: SessionBody, request: Request):
    db = get_db()
    me = await _me(request)
    c = await _campaign(db, me, body.campaign_id)
    if c.get("status") != "active":
        raise HTTPException(status_code=409, detail="This campaign is paused")
    if not eng.is_manager(me) and str(me["_id"]) not in (c.get("rep_ids") or []):
        raise HTTPException(status_code=403, detail="You are not on this campaign")
    live = await eng.active_session(db, str(me["_id"]))
    if live:
        raise HTTPException(status_code=409, detail="You already have a live dialer session")
    fresh = await db.users.find_one({"_id": me["_id"]})
    try:
        s = await eng.start_session(db, c, fresh or me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await eng.session_view(db, s)


async def _session(db, me: dict, sid: str) -> dict:
    s = await db[eng.SESSIONS].find_one({"_id": _oid(sid, "Session")})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s["user_id"] != str(me["_id"]) and not eng.is_manager(me):
        raise HTTPException(status_code=403, detail="Not your session")
    return dict(s)


@router.get("/sessions/{sid}")
async def get_session(sid: str, request: Request):
    db = get_db()
    me = await _me(request)
    return await eng.session_view(db, await _session(db, me, sid))


@router.post("/sessions/{sid}/dial")
async def dial_next(sid: str, request: Request):
    db = get_db()
    me = await _me(request)
    s = await _session(db, me, sid)
    if s.get("status") == "ended":
        raise HTTPException(status_code=409, detail="This session has ended")
    c = await db[eng.CAMPAIGNS].find_one({"_id": eng._oid(s["campaign_id"])}) or {}
    try:
        res = await eng.dial_from_app(db, s, c)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {**res, "session": await eng.session_view(db, await db[eng.SESSIONS].find_one({"_id": s["_id"]}))}


@router.post("/sessions/{sid}/hangup")
async def hangup(sid: str, request: Request):
    db = get_db()
    me = await _me(request)
    s = await _session(db, me, sid)
    return {"hung_up": await eng.hangup_current(db, s)}


@router.post("/sessions/{sid}/end")
async def end_session(sid: str, request: Request):
    db = get_db()
    me = await _me(request)
    s = await _session(db, me, sid)
    await eng.end_session(db, s, "app")
    return await eng.session_view(db, await db[eng.SESSIONS].find_one({"_id": s["_id"]}))


@router.post("/sessions/{sid}/disposition")
async def disposition(sid: str, body: DispositionBody, request: Request):
    db = get_db()
    me = await _me(request)
    s = await _session(db, me, sid)
    if body.attempt_id:
        a = await db[eng.ATTEMPTS].find_one({"_id": _oid(body.attempt_id, "Attempt"), "session_id": str(s["_id"])})
    else:
        a = await db[eng.ATTEMPTS].find_one({"session_id": str(s["_id"]), "status": {"$in": ["connected", "voicemail"]}, "disposition": None}, sort=[("connected_at", -1), ("started_at", -1)])
    if not a:
        raise HTTPException(status_code=404, detail="No call to mark")
    if body.disposition == "callback" and body.callback_at and body.callback_at.tzinfo is None:
        body.callback_at = body.callback_at.replace(tzinfo=timezone.utc)
    try:
        lead = await eng.apply_disposition(db, s, a, body.disposition, body.notes, body.callback_at, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"lead": eng.serialize_lead(lead), "session": await eng.session_view(db, await db[eng.SESSIONS].find_one({"_id": s["_id"]}))}


# ── Do Not Call ───────────────────────────────────────────────────────────────
@router.get("/dnc")
async def list_dnc(request: Request, q: Optional[str] = None, limit: int = 100):
    db = get_db()
    me = await _me(request)
    _manager(me)
    flt = {}
    if q:
        flt["phone"] = {"$regex": "".join(ch for ch in q if ch.isdigit()) or q}
    rows = await db[comp.DNC_LIST].find(flt).sort("added_at", -1).limit(max(1, min(limit, 500))).to_list(500)
    return {"total": await db[comp.DNC_LIST].count_documents(flt), "registry": await comp.registry_stats(db),
            "entries": [{"phone": r["phone"], "source": r.get("source"), "note": r.get("note"), "added_at": r["added_at"].isoformat() if r.get("added_at") else None, "campaign_id": r.get("campaign_id")} for r in rows]}


@router.post("/dnc")
async def add_dnc(body: DncBody, request: Request):
    db = get_db()
    me = await _me(request)
    _manager(me)
    if not comp.e164(body.phone):
        raise HTTPException(status_code=400, detail="Enter a full phone number")
    added = await comp.add_dnc(db, body.phone, "manual", by=str(me["_id"]), note=body.note)
    return {"added": added, "phone": comp.e164(body.phone)}


@router.delete("/dnc/{phone}")
async def remove_dnc(phone: str, request: Request):
    """Only a super admin, only for a manual/rep mistake. Press-9 and STOP entries stay."""
    db = get_db()
    me = await _me(request)
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only a super admin can remove a Do Not Call entry")
    p = comp.e164(phone)
    res = await db[comp.DNC_LIST].delete_one({"phone": p, "source": {"$in": ["manual", "rep"]}})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Not found, or it was the customer's own request and cannot be removed")
    await db.contacts.update_many({"phone": p}, {"$set": {"do_not_call": False}})
    return {"removed": True}


@router.post("/dnc/registry")
async def import_registry(body: RegistryBody, request: Request):
    """Paste / upload the FTC National Do Not Call Registry download (one `areacode,number` per line). Chunk big files."""
    db = get_db()
    me = await _me(request)
    _manager(me)
    if len(body.text) > 6_000_000:
        raise HTTPException(status_code=413, detail="Send the file in chunks under 5 MB")
    res = await comp.import_registry(db, body.text, by=str(me["_id"]))
    if not res["lines"]:
        raise HTTPException(status_code=400, detail="No phone numbers found in that text")
    return {**res, "registry": await comp.registry_stats(db)}


@router.get("/dnc/check/{phone}")
async def check_dnc(phone: str, request: Request):
    db = get_db()
    await _me(request)
    p = comp.e164(phone)
    if not p:
        raise HTTPException(status_code=400, detail="Enter a full phone number")
    return {"phone": p, **{k: v for k, v in (await comp.dnc_status(db, p)).items() if k != "checked_at"}, **{k: v for k, v in comp.region(p).items()}}
