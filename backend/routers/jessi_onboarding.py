"""Jessi new-user onboarding: admin view + actions, and the public bits a not-yet-logged-in user touches
(Jessi's contact card, the "call me" landing page from the invite text)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import jessi_onboarding as jo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/onboarding-jessi", tags=["Jessi onboarding"], dependencies=[Depends(require_user)])
public = APIRouter(prefix="/onboarding-jessi", tags=["Jessi onboarding"])
me_router = APIRouter(prefix="/onboarding-jessi/me", tags=["Jessi onboarding"], dependencies=[Depends(require_user)])

MANAGER_ROLES = ("super_admin", "org_admin", "store_manager")


# ---------------------------------------------------------------- the user themself (first login welcome)
@me_router.get("")
async def my_onboarding(request: Request):
    me = await _resolve(request)
    return await jo.me_summary(get_db(), me)


class FirstWinBody(BaseModel):
    which: Optional[str] = ""


@me_router.post("/first-success")
async def my_first_success(request: Request, body: Optional[FirstWinBody] = None):
    me = await _resolve(request)
    doc = await jo.first_success(get_db(), str(me["_id"]), (body.which if body else "") or "")
    return {"ok": True, "state": (doc or {}).get("state")}


@me_router.post("/win")
async def my_first_win(request: Request, body: Optional[FirstWinBody] = None):
    """The app just saw this user do their first real thing (a card sent): celebrate once if Jessi onboarded them."""
    me = await _resolve(request)
    kind = (body.which if body else "") or "card"
    out = await jo.claim_celebration(get_db(), str(me["_id"]), kind)
    doc = await jo.get(get_db(), str(me["_id"]))
    return {**out, "state": (doc or {}).get("state")}


async def _admin(request: Request) -> dict:
    me = await _resolve(request)
    if not me or me.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Managers only")
    return me


def _scope(me: dict) -> dict:
    return jo.scope_query(me)


# ---------------------------------------------------------------- admin
@router.get("/senders")
async def list_senders(request: Request):
    """Accounts Jessi could text from: managers and admins with a work number."""
    me = await _resolve(request)
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admins only")
    db = get_db()
    cur = db.users.find({"role": {"$in": list(MANAGER_ROLES)}, "is_active": {"$ne": False}, "$or": [{"twilio_number": {"$nin": [None, ""]}}, {"mvpline_number": {"$nin": [None, ""]}}]},
                        {"name": 1, "role": 1, "twilio_number": 1, "mvpline_number": 1, "photo_url": 1}).sort("created_at", 1).limit(60)
    cfg = await jo.config(db)
    current = await jo.sender(db, cfg)
    return {"current_id": str(current["_id"]) if current else None,
            "senders": [{"id": str(u["_id"]), "name": u.get("name"), "role": u.get("role"), "number": jo.sender_number(u)} async for u in cur]}


@router.get("/digest/preview")
async def digest_preview(request: Request):
    me = await _admin(request)
    db = get_db()
    cfg = await jo.config(db)
    rows = await jo.stuck_rows(db, me, cfg)
    return {"count": len(rows), "rows": rows, "text": jo.digest_text(me.get("first_name") or jo._first(me.get("name")), rows),
            "opt_in": not me.get("jessi_digest_opt_out"), "last": me.get("jessi_digest_last"), "hour": cfg.get("digest_hour"), "stuck_hours": cfg.get("digest_stuck_hours"), "enabled": bool(cfg.get("digest_enabled", True))}


@router.post("/digest/send")
async def digest_send_now(request: Request):
    """Text me today's digest right now (even when nothing is stuck, so the manager sees what it looks like)."""
    me = await _admin(request)
    r = await jo.send_digest(get_db(), me, force=True)
    if not r.get("sent"):
        raise HTTPException(status_code=400, detail=r.get("error") or r.get("reason") or "Could not send")
    return r


class DigestMeBody(BaseModel):
    opt_in: bool


@router.put("/digest/me")
async def digest_me(body: DigestMeBody, request: Request):
    me = await _admin(request)
    await get_db().users.update_one({"_id": jo._oid(me["_id"])}, {"$set": {"jessi_digest_opt_out": not body.opt_in}})
    return {"opt_in": body.opt_in}


@router.get("")
async def list_onboarding(request: Request, state: Optional[str] = None, open_only: bool = False):
    me = await _admin(request)
    db = get_db()
    q = _scope(me)
    if state:
        q["state"] = state
    elif open_only:
        q["state"] = {"$in": jo.OPEN_STATES}
    docs = await db[jo.COLL].find(q).sort("updated_at", -1).limit(300).to_list(300)
    ids = [jo._oid(d.get("user_id")) for d in docs if jo._oid(d.get("user_id"))]
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": ids}}, {"email": 1, "photo_url": 1, "photo_thumbnail_url": 1, "last_login": 1, "activation_pending": 1, "title": 1})} if ids else {}
    rows = []
    for d in docs:
        s = jo.serialize(d)
        s.pop("thread", None)
        s.pop("events", None)
        u = users.get(d.get("user_id")) or {}
        s["email"] = u.get("email") or ""
        s["user_photo_url"] = u.get("photo_thumbnail_url") or u.get("photo_url") or d.get("photo_url")
        s["last_login"] = u["last_login"].isoformat() if hasattr(u.get("last_login"), "isoformat") else u.get("last_login")
        s["waiting_on"] = jo.waiting_on(d)
        rows.append(s)
    counts = {}
    async for r in db[jo.COLL].aggregate([{"$match": _scope(me)}, {"$group": {"_id": "$state", "n": {"$sum": 1}}}]):
        counts[r["_id"]] = r["n"]
    snd = await jo.sender(db)
    return {"rows": rows, "counts": counts, "states": jo.STATES, "sender": {"id": str(snd["_id"]), "name": snd.get("name"), "number": jo.sender_number(snd)} if snd else None}


@router.get("/config")
async def get_config(request: Request):
    me = await _resolve(request)
    db = get_db()
    cfg = await jo.config(db)
    snd = await jo.sender(db, cfg)
    return {"config": cfg if me.get("role") == "super_admin" else {k: cfg[k] for k in ("default_on_roles", "digest_hour", "digest_stuck_hours", "digest_enabled")},
            "available": await jo.available_for(db, me), "default_on": await jo.default_on_for(db, me), "is_super_admin": me.get("role") == "super_admin",
            "digest_opt_in": not me.get("jessi_digest_opt_out"),
            "sender": {"id": str(snd["_id"]), "name": snd.get("name"), "number": jo.sender_number(snd)} if snd else None}


class ConfigBody(BaseModel):
    sender_user_id: Optional[str] = None
    reminders_hours: Optional[dict] = None
    quiet_start: Optional[int] = None
    quiet_end: Optional[int] = None
    timezone: Optional[str] = None
    default_on_roles: Optional[list] = None
    activation_ttl_hours: Optional[int] = None
    digest_enabled: Optional[bool] = None
    digest_hour: Optional[int] = None
    digest_stuck_hours: Optional[int] = None


@router.put("/config")
async def put_config(body: ConfigBody, request: Request):
    me = await _resolve(request)
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admins only")
    patch = {k: v for k, v in body.dict().items() if v is not None}
    if "reminders_hours" in patch:
        clean = {}
        for k, v in (patch["reminders_hours"] or {}).items():
            if k in jo.DEFAULT_CFG["reminders_hours"]:
                clean[k] = sorted({int(h) for h in (v or []) if 1 <= int(h) <= 24 * 30})
        patch["reminders_hours"] = clean
    for k, lo, hi in (("quiet_start", 0, 24), ("quiet_end", 0, 24), ("digest_hour", 0, 23), ("digest_stuck_hours", 1, 24 * 14), ("activation_ttl_hours", 1, 24 * 30)):
        if k in patch and not (lo <= int(patch[k]) <= hi):
            raise HTTPException(status_code=400, detail=f"{k} out of range")
    if "timezone" in patch:
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(patch["timezone"])
        except Exception:
            raise HTTPException(status_code=400, detail="Unknown timezone")
    cfg = await jo.save_config(get_db(), patch, str(me["_id"]))
    snd = await jo.sender(get_db(), cfg)
    if not snd:
        raise HTTPException(status_code=400, detail="That sender has no work number assigned")
    return {"config": cfg, "sender": {"id": str(snd["_id"]), "name": snd.get("name"), "number": jo.sender_number(snd)}}


@router.get("/{user_id}")
async def detail(user_id: str, request: Request):
    await _admin(request)
    db = get_db()
    doc = await jo.get(db, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Jessi onboarding for this user")
    out = jo.serialize(doc)
    user = await db.users.find_one({"_id": jo._oid(user_id)}, {"name": 1, "email": 1, "phone": 1, "photo_url": 1, "persona": 1, "title": 1, "activation_pending": 1, "last_login": 1, "onboarding_complete": 1})
    if user:
        user["_id"] = str(user["_id"])
        for k in ("last_login",):
            if hasattr(user.get(k), "isoformat"):
                user[k] = user[k].isoformat()
    out["user"] = user
    if jo._oid(doc.get("interview_session_id")):
        from services import interview as iv
        out["interview"] = iv.serialize(await db[iv.COLL].find_one({"_id": jo._oid(doc["interview_session_id"])}))
    return out


@router.post("/{user_id}/start")
async def start_for_user(user_id: str, request: Request):
    """Put an existing user (created before, or without the toggle) through Jessi's onboarding."""
    me = await _admin(request)
    try:
        doc = await jo.start(get_db(), user_id, str(me["_id"]))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return jo.serialize(doc)


@router.post("/{user_id}/resend")
async def resend(user_id: str, request: Request):
    """Send the current step's message again."""
    await _admin(request)
    db = get_db()
    doc = await jo.get(db, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Jessi onboarding for this user")
    state = doc["state"]
    target = {"NOT_STARTED": "JESSI_INTRODUCED", "JESSI_INTRODUCED": "CONTACT_CARD_SENT", "CONTACT_CARD_SENT": "INTERVIEW_INVITED", "INTERVIEW_STARTED": "INTERVIEW_INVITED",
              "PHOTO_RECEIVED": "PROFILE_COMPLETE"}.get(state, state)
    if target == "INTERVIEW_INVITED" and state in ("INTERVIEW_INVITED", "INTERVIEW_STARTED"):
        await jo._say(db, doc, jo.text("invite", phone=jo._mask(doc["phone"]), link=await jo.invite_link(doc)), kind="invite_resend")
        await jo._event(db, doc["_id"], "RESENT", "invite")
        return jo.serialize(await jo.get(db, user_id))
    await jo.send_step(db, {**doc, "resend": True}, target)
    await jo._event(db, doc["_id"], "RESENT", target)
    return jo.serialize(await jo.get(db, user_id))


class MessageBody(BaseModel):
    text: str


@router.post("/{user_id}/message")
async def custom_message(user_id: str, body: MessageBody, request: Request):
    me = await _admin(request)
    db = get_db()
    doc = await jo.get(db, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Jessi onboarding for this user")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Nothing to send")
    r = await jo._say(db, doc, body.text.strip()[:1200], kind=f"admin:{me.get('name', '')}")
    await jo._event(db, doc["_id"], "ADMIN_MESSAGE", body.text[:200], str(me["_id"]))
    return {"ok": bool(r.get("success")), "error": r.get("error")}


@router.post("/{user_id}/call")
async def admin_call(user_id: str, request: Request):
    """Admin taps Call: Jessi rings them for the interview right now."""
    await _admin(request)
    db = get_db()
    doc = await jo.get(db, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Jessi onboarding for this user")
    try:
        return jo.serialize(await jo.start_call(db, doc, "admin"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@router.post("/{user_id}/reset")
async def reset(user_id: str, request: Request):
    me = await _admin(request)
    doc = await jo.reset(get_db(), user_id, str(me["_id"]))
    if not doc:
        raise HTTPException(status_code=404, detail="No Jessi onboarding for this user")
    return jo.serialize(doc)


@router.post("/{user_id}/pause")
async def pause(user_id: str, request: Request, resume: bool = False):
    await _admin(request)
    db = get_db()
    doc = await jo.get(db, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Jessi onboarding for this user")
    await db[jo.COLL].update_one({"_id": doc["_id"]}, {"$set": {"paused": not resume, "updated_at": jo._now()}})
    await jo._event(db, doc["_id"], "RESUMED" if resume else "PAUSED")
    return jo.serialize(await jo.get(db, user_id))


@router.post("/{user_id}/mark/{state}")
async def mark(user_id: str, state: str, request: Request):
    me = await _admin(request)
    db = get_db()
    doc = await jo.mark_step(db, user_id, state.upper(), str(me["_id"]))
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown user or state")
    # marking a step by hand still runs what naturally follows it
    doc = await jo.get(db, user_id)
    if state.upper() == "INTERVIEW_COMPLETE" and doc.get("summary_text") is None:
        await jo.request_photo(db, doc)
    elif state.upper() == "PHOTO_RECEIVED":
        await jo.after_profile(db, doc)
    elif state.upper() == "PROFILE_COMPLETE":
        await jo.send_activation(db, doc)
    return jo.serialize(await jo.get(db, user_id))


# ---------------------------------------------------------------- public (no login: the new user has no account yet)
@public.get("/jessi.vcf")
async def jessi_vcf():
    db = get_db()
    snd = await jo.sender(db)
    if not snd:
        raise HTTPException(status_code=404, detail="Not configured")
    body = jo.jessi_vcard(jo.sender_number(snd))
    return Response(content=body, media_type="text/vcard", headers={"Content-Disposition": 'inline; filename="jessi.vcf"'})


@public.get("/call/{token}")
async def call_page_info(token: str):
    db = get_db()
    doc = await db[jo.COLL].find_one({"call_token": token})
    if not doc:
        raise HTTPException(status_code=404, detail="This link is not valid any more")
    s = None
    if jo._oid(doc.get("interview_session_id")):
        s = await db.interview_sessions.find_one({"_id": jo._oid(doc["interview_session_id"])}, {"status": 1})
    return {"first_name": doc.get("first_name"), "phone": jo._mask(doc["phone"]), "state": doc.get("state"), "paused": bool(doc.get("paused")),
            "can_call": jo.ORDER.get(doc.get("state"), 0) <= jo.ORDER["INTERVIEW_STARTED"], "call_status": (s or {}).get("status")}


@public.post("/call/{token}")
async def call_page_start(token: str):
    """The CALL JESSI button on the landing page: Jessi rings them within seconds."""
    db = get_db()
    doc = await db[jo.COLL].find_one({"call_token": token})
    if not doc:
        raise HTTPException(status_code=404, detail="This link is not valid any more")
    if jo.ORDER.get(doc.get("state"), 0) > jo.ORDER["INTERVIEW_STARTED"]:
        raise HTTPException(status_code=400, detail="Your interview is already done. Check your texts from Jessi for the next step.")
    if doc.get("state") == "INTERVIEW_STARTED" and jo._oid(doc.get("interview_session_id")):
        s = await db.interview_sessions.find_one({"_id": jo._oid(doc["interview_session_id"])}, {"status": 1})
        if s and s.get("status") in ("dialing", "live"):
            return {"ok": True, "already": True, "phone": jo._mask(doc["phone"])}
    try:
        await jo.start_call(db, doc, "link")
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)[:200] or "The call could not be placed, try again in a minute")
    return {"ok": True, "phone": jo._mask(doc["phone"])}
