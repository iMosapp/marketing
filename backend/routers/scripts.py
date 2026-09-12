"""Scripts & Practice API: phone-script library, training-video script generator, voice roleplay (mystery shop) + assignments."""
import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from routers.database import get_db
from services import scripts as svc
from services.lead_flows import MANAGER_ROLES, user_store_id

logger = logging.getLogger(__name__)


async def _resolve(request: Request) -> Optional[dict]:
    """Bearer JWT as everywhere, plus `?t=<jwt>` so a PDF can open in a browser tab / share sheet."""
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if user:
        return user
    tok = request.query_params.get("t")
    if tok:
        from routers.auth import verify_jwt_token
        from routers.database import get_user_by_id
        payload = verify_jwt_token(tok)
        if payload and payload.get("sub"):
            return await get_user_by_id(payload["sub"])
    return None


async def require_user(request: Request) -> dict:
    user = await _resolve(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


router = APIRouter(prefix="/scripts", tags=["Scripts & Practice"], dependencies=[Depends(require_user)])


async def _current(request: Request) -> dict:
    me = await _resolve(request)
    me["store_id"] = user_store_id(me)
    return me


def _is_manager(me: dict) -> bool:
    return me.get("role") in MANAGER_ROLES


def _oid(v: str, what: str = "Script") -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(str(v))


class ScriptBody(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    runtime: Optional[str] = None
    purpose: Optional[str] = None
    body: Optional[str] = None
    success_points: Optional[list] = None
    persona: Optional[dict] = None
    scorecard_id: Optional[str] = None
    training: Optional[dict] = None


class GenerateBody(BaseModel):
    feature_id: str
    format: str = "short"
    audience: Optional[str] = None
    extra: Optional[str] = ""


class StartBody(BaseModel):
    script_id: str
    assignment_id: Optional[str] = None


class TurnBody(BaseModel):
    text: Optional[str] = None
    audio_b64: Optional[str] = None
    content_type: Optional[str] = "audio/m4a"


class AssignBody(BaseModel):
    script_id: str
    rep_ids: list
    due_by: Optional[str] = None
    curveballs: Optional[list] = None
    note: Optional[str] = ""


# ---------------------------------------------------------------- library
@router.get("")
async def library(request: Request):
    me = await _current(request)
    db = get_db()
    scripts = await svc.phone_library(db, me["store_id"])
    out = {"scripts": scripts, "categories": sorted({s["category"] for s in scripts}), "can_edit": _is_manager(me), "can_assign": _is_manager(me),
           "is_super_admin": me.get("role") == "super_admin", "merge_fields": svc.MERGE_FIELDS}
    if me.get("role") == "super_admin":
        out["features"] = svc.FEATURES
    my_shops = await db.mystery_shops.find({"rep_ids": str(me["_id"]), "status": {"$ne": "cancelled"}}).sort("created_at", -1).limit(20).to_list(20)
    out["my_assignments"] = [_shop_out(s, for_user=str(me["_id"])) for s in my_shops if not (s.get("completed") or {}).get(str(me["_id"]))]
    recent = await db.roleplay_sessions.find({"user_id": str(me["_id"]), "status": "completed"}).sort("ended_at", -1).limit(10).to_list(10)
    out["my_recent"] = [{"session_id": str(s["_id"]), "script_title": s.get("script_title"), "score_pct": s.get("score_pct"), "adherence_pct": s.get("adherence_pct"),
                         "evaluation_id": s.get("evaluation_id"), "ended_at": s.get("ended_at").isoformat() if s.get("ended_at") else None} for s in recent]
    return out


@router.get("/training")
async def training_list(request: Request):
    me = await _current(request)
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Training video scripts are for the app owner")
    db = get_db()
    rows = await db.scripts.find({"kind": "training", "active": {"$ne": False}}).sort("updated_at", -1).limit(100).to_list(100)
    return {"scripts": [svc.serialize_script(r) for r in rows], "features": svc.FEATURES}


@router.post("/training/generate")
async def training_generate(body: GenerateBody, request: Request):
    me = await _current(request)
    if me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Training video scripts are for the app owner")
    feature = next((f for f in svc.FEATURES if f["id"] == body.feature_id), None)
    if not feature:
        raise HTTPException(status_code=404, detail="Unknown feature")
    fmt = "long" if body.format == "long" else "short"
    try:
        training = await svc.generate_training_script(feature, fmt, body.audience or feature.get("audience") or "reps", (body.extra or "")[:400])
    except Exception as e:
        logger.warning(f"[Scripts] training generation failed: {e}")
        raise HTTPException(status_code=502, detail="Jessi could not write that script right now, try again")
    now = datetime.now(timezone.utc)
    doc = {"kind": "training", "store_id": None, "owner_user_id": str(me["_id"]), "feature_id": feature["id"], "format": fmt, "category": "Training video",
           "title": training["title"], "runtime": f"about {training['runtime_seconds']}s", "purpose": feature["summary"], "body": svc.training_to_text(training),
           "training": training, "created_by_name": me.get("name"), "active": True, "created_at": now, "updated_at": now}
    res = await get_db().scripts.insert_one(doc)
    return svc.serialize_script(await get_db().scripts.find_one({"_id": res.inserted_id}))


@router.post("")
async def create_script(body: ScriptBody, request: Request):
    me = await _current(request)
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers can add scripts")
    if not (body.title or "").strip() or not (body.body or "").strip():
        raise HTTPException(status_code=400, detail="Title and script text are required")
    now = datetime.now(timezone.utc)
    doc = {"kind": "phone", "store_id": me["store_id"], "slug": f"custom_{ObjectId()}", "category": (body.category or "Custom").strip()[:60], "title": body.title.strip()[:120],
           "runtime": (body.runtime or "").strip()[:40], "purpose": (body.purpose or "").strip()[:400], "body": svc.no_em_dash(body.body)[:8000],
           "success_points": [str(p).strip()[:160] for p in (body.success_points or []) if str(p).strip()][:12], "persona": body.persona, "scorecard_id": body.scorecard_id,
           "created_by": str(me["_id"]), "created_by_name": me.get("name"), "active": True, "created_at": now, "updated_at": now}
    res = await get_db().scripts.insert_one(doc)
    return svc.serialize_script(await get_db().scripts.find_one({"_id": res.inserted_id}), me["store_id"])


@router.get("/{script_id}")
async def get_script(script_id: str, request: Request):
    me = await _current(request)
    s = await get_db().scripts.find_one({"_id": _oid(script_id), "active": {"$ne": False}})
    if not s or (s.get("store_id") and s.get("store_id") != me["store_id"] and me.get("role") != "super_admin"):
        raise HTTPException(status_code=404, detail="Script not found")
    if s.get("kind") == "training" and me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Training video scripts are for the app owner")
    out = svc.serialize_script(s, me["store_id"])
    if s.get("kind") == "phone":
        store = await get_db().stores.find_one({"_id": ObjectId(me["store_id"])}, {"name": 1}) if ObjectId.is_valid(str(me["store_id"] or "")) else None
        out["preview"] = svc.merge(s.get("body", ""), {"rep_name": (me.get("name") or "").split(" ")[0], "store": (store or {}).get("name") or "our store",
                                                     "first_name": "{first_name}", "vehicle": "{vehicle}", "appointment_time": "{appointment_time}", "trade": "{trade}"})
    return out


@router.put("/{script_id}")
async def update_script(script_id: str, body: ScriptBody, request: Request):
    me = await _current(request)
    db = get_db()
    s = await db.scripts.find_one({"_id": _oid(script_id)})
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    if s.get("kind") == "training":
        if me.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Training video scripts are for the app owner")
        sets = {k: v for k, v in body.dict().items() if v is not None and k in ("title", "training", "purpose")}
        if "training" in sets:
            sets["body"] = svc.training_to_text(sets["training"])
        await db.scripts.update_one({"_id": s["_id"]}, {"$set": {**sets, "updated_at": datetime.now(timezone.utc)}})
        return svc.serialize_script(await db.scripts.find_one({"_id": s["_id"]}))
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers can edit scripts")
    if not me["store_id"]:
        raise HTTPException(status_code=400, detail="Your account is not on a store")
    return await svc.save_store_copy(db, script_id, me["store_id"], me, {k: v for k, v in body.dict().items() if v is not None})


@router.delete("/{script_id}")
async def delete_script(script_id: str, request: Request):
    """Store copy -> removed (the global version comes back); global rows cannot be deleted."""
    me = await _current(request)
    db = get_db()
    s = await db.scripts.find_one({"_id": _oid(script_id)})
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    if s.get("kind") == "training":
        if me.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Not allowed")
    elif not _is_manager(me) or not s.get("store_id") or s.get("store_id") != me["store_id"]:
        raise HTTPException(status_code=403, detail="Only your store's own copies can be removed")
    await db.scripts.update_one({"_id": s["_id"]}, {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}})
    return {"deleted": True, "reverts_to_default": bool(s.get("copied_from"))}


@router.get("/{script_id}/pdf")
async def script_pdf(script_id: str, request: Request):
    me = await _current(request)
    db = get_db()
    s = await db.scripts.find_one({"_id": _oid(script_id), "active": {"$ne": False}})
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    store = await db.stores.find_one({"_id": ObjectId(me["store_id"])}, {"name": 1}) if ObjectId.is_valid(str(me["store_id"] or "")) else None
    data = svc.script_pdf(s, (store or {}).get("name") or "")
    fname = "".join(c if c.isalnum() or c in " -_" else "" for c in (s.get("title") or "script")).strip().replace(" ", "_") or "script"
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{fname}.pdf"'})


# ---------------------------------------------------------------- roleplay
@router.post("/roleplay/start")
async def roleplay_start(body: StartBody, request: Request):
    me = await _current(request)
    db = get_db()
    script = await db.scripts.find_one({"_id": _oid(body.script_id), "kind": "phone", "active": {"$ne": False}})
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    assignment = None
    if body.assignment_id:
        assignment = await db.mystery_shops.find_one({"_id": _oid(body.assignment_id, "Assignment"), "rep_ids": str(me["_id"])})
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
    await db.roleplay_sessions.update_many({"user_id": str(me["_id"]), "status": {"$in": ["active", "ending"]}}, {"$set": {"status": "abandoned", "updated_at": datetime.now(timezone.utc)}})
    return await svc.start_session(db, me, script, assignment)


@router.post("/roleplay/call")
async def roleplay_call(body: StartBody, request: Request):
    """Phone practice: we ring the rep's cell and Jessi's customer talks live (Twilio ConversationRelay)."""
    me = await _current(request)
    db = get_db()
    script = await db.scripts.find_one({"_id": _oid(body.script_id), "kind": "phone", "active": {"$ne": False}})
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    assignment = None
    if body.assignment_id:
        assignment = await db.mystery_shops.find_one({"_id": _oid(body.assignment_id, "Assignment"), "rep_ids": str(me["_id"])})
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
    await db.roleplay_sessions.update_many({"user_id": str(me["_id"]), "status": {"$in": ["active", "ending", "dialing", "live"]}}, {"$set": {"status": "abandoned", "updated_at": datetime.now(timezone.utc)}})
    try:
        return await svc.start_phone_session(db, me, script, assignment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/roleplay/{sid}/hangup")
async def roleplay_hangup(sid: str, request: Request):
    me = await _current(request)
    db = get_db()
    s = await _session(db, sid, me, owner_only=True)
    if s.get("mode") == "phone" and s.get("call_sid") and s.get("status") in ("dialing", "live", "ending"):
        from services.lead_call_engine import _twilio_client
        client = _twilio_client()
        if client:
            try:
                await asyncio.to_thread(client.calls(s["call_sid"]).update, status="completed")
            except Exception as e:
                logger.debug(f"[Roleplay] hangup failed: {e}")
        asyncio.create_task(svc.finalize_session(db, sid, "rep_hung_up_in_app"))
    return {"ok": True}


async def _session(db, sid: str, me: dict, owner_only: bool = False) -> dict:
    """Owner always; managers may read (coaching) but never speak or end someone else's call."""
    s = await db.roleplay_sessions.find_one({"_id": _oid(sid, "Session")})
    if not s or (s["user_id"] != str(me["_id"]) and (owner_only or not _is_manager(me))):
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.post("/roleplay/{sid}/turn")
async def roleplay_turn(sid: str, body: TurnBody, request: Request):
    me = await _current(request)
    db = get_db()
    s = await _session(db, sid, me, owner_only=True)
    if s["status"] not in ("active", "ending"):
        raise HTTPException(status_code=409, detail="This practice call is over")
    text = (body.text or "").strip()
    if not text and body.audio_b64:
        from routers.voice_notes import _transcribe_audio, _ext_for
        try:
            raw = base64.b64decode(body.audio_b64.split(",")[-1])
        except Exception:
            raise HTTPException(status_code=400, detail="Bad audio")
        if len(raw) > 6 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Clip too long, keep each turn under a minute")
        text = (await _transcribe_audio(raw, f"turn.{_ext_for(body.content_type or 'audio/m4a')}", "memo") or "").strip()
        if not text:
            return {"heard": "", "customer": None, "ended": False, "retry": True}
    if not text:
        raise HTTPException(status_code=400, detail="Say something first")
    out = await svc.customer_turn(db, s, text[:1200])
    return {"heard": text, **out}


@router.post("/roleplay/{sid}/end")
async def roleplay_end(sid: str, request: Request):
    me = await _current(request)
    db = get_db()
    s = await _session(db, sid, me, owner_only=True)
    if s["status"] == "completed" and s.get("evaluation_id"):
        ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])})
        if ev:
            return _result_out(ev, s)
    if s["status"] not in ("active", "ending"):
        raise HTTPException(status_code=409, detail="This practice call is over")
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"ended_at": datetime.now(timezone.utc)}})
    s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
    return await svc.grade_session(db, s)


def _result_out(ev: dict, s: dict) -> dict:
    return {"evaluation_id": str(ev["_id"]), "score_pct": ev.get("score_pct"), "scorecard_name": ev.get("scorecard_name"), "critical_misses": ev.get("critical_misses") or [],
            "adherence": ev.get("adherence") or {}, "summary": ev.get("summary"), "wins": ev.get("wins") or [], "coaching": ev.get("coaching") or [],
            "customer_sentiment": ev.get("customer_sentiment"), "duration_s": ev.get("duration_s"), "results": ev.get("results") or []}


@router.get("/roleplay/{sid}")
async def roleplay_get(sid: str, request: Request):
    me = await _current(request)
    db = get_db()
    s = await svc.reconcile_dialing(db, await _session(db, sid, me))
    ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])}) if s.get("evaluation_id") and ObjectId.is_valid(str(s["evaluation_id"])) else None
    return {"session_id": sid, "status": s["status"], "mode": s.get("mode", "text"), "call_status": s.get("call_status"), "fail_reason": s.get("fail_reason"),
            "recording_url": s.get("recording_url"), "rep_phone": s.get("rep_phone"),
            "script_title": s.get("script_title"), "script_id": s.get("script_id"), "persona": {k: (s.get("persona") or {}).get(k) for k in ("name", "summary", "voice")},
            "rep_name": s.get("rep_name"), "turns": [svc._turn_out(t) for t in s.get("turns", [])], "started_at": s["started_at"].isoformat() if s.get("started_at") else None,
            "result": _result_out(ev, s) if ev else None}


# ---------------------------------------------------------------- mystery shop assignments
def _shop_out(s: dict, for_user: Optional[str] = None) -> dict:
    return {"id": str(s["_id"]), "script_id": s.get("script_id"), "script_title": s.get("script_title"), "rep_ids": s.get("rep_ids") or [], "rep_names": s.get("rep_names") or {},
            "due_by": s.get("due_by").isoformat() if hasattr(s.get("due_by"), "isoformat") else s.get("due_by"), "curveballs": s.get("curveballs") or [], "note": s.get("note") or "",
            "created_by_name": s.get("created_by_name"), "created_at": s.get("created_at").isoformat() if s.get("created_at") else None, "status": s.get("status", "open"),
            "completed": {k: {**v, "at": v["at"].isoformat() if hasattr(v.get("at"), "isoformat") else v.get("at")} for k, v in (s.get("completed") or {}).items()},
            "mine_done": bool((s.get("completed") or {}).get(for_user)) if for_user else None}


@router.get("/mystery-shops/list")
async def shops_list(request: Request):
    me = await _current(request)
    db = get_db()
    if _is_manager(me):
        q = {"store_id": me["store_id"], "status": {"$ne": "cancelled"}} if me.get("role") != "super_admin" else {"status": {"$ne": "cancelled"}}
        rows = await db.mystery_shops.find(q).sort("created_at", -1).limit(100).to_list(100)
        reps = await db.users.find({"$or": [{"store_id": me["store_id"]}, {"store_ids": me["store_id"]}], "status": {"$ne": "deactivated"}, "active": {"$ne": False}},
                                   {"name": 1, "first_name": 1, "role": 1, "photo_url": 1}).limit(200).to_list(200) if me["store_id"] else []
        return {"assignments": [_shop_out(s) for s in rows], "reps": [{"id": str(r["_id"]), "name": r.get("name") or r.get("first_name") or "Rep", "role": r.get("role")} for r in reps]}
    rows = await db.mystery_shops.find({"rep_ids": str(me["_id"]), "status": {"$ne": "cancelled"}}).sort("created_at", -1).limit(50).to_list(50)
    return {"assignments": [_shop_out(s, str(me["_id"])) for s in rows], "reps": []}


@router.post("/mystery-shops")
async def shops_create(body: AssignBody, request: Request):
    me = await _current(request)
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers assign practice calls")
    db = get_db()
    script = await db.scripts.find_one({"_id": _oid(body.script_id), "kind": "phone", "active": {"$ne": False}})
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    rep_ids = [str(r) for r in body.rep_ids if ObjectId.is_valid(str(r))]
    if not rep_ids:
        raise HTTPException(status_code=400, detail="Pick at least one rep")
    reps = await db.users.find({"_id": {"$in": [ObjectId(r) for r in rep_ids]}}, {"name": 1, "first_name": 1}).to_list(50)
    names = {str(r["_id"]): r.get("name") or r.get("first_name") or "Rep" for r in reps}
    due = None
    if body.due_by:
        try:
            due = datetime.fromisoformat(body.due_by.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="due_by must be ISO 8601")
    now = datetime.now(timezone.utc)
    doc = {"store_id": me["store_id"], "script_id": str(script["_id"]), "script_title": script.get("title"), "rep_ids": list(names.keys()), "rep_names": names, "due_by": due,
           "curveballs": [str(c).strip()[:200] for c in (body.curveballs or []) if str(c).strip()][:5], "note": (body.note or "").strip()[:400],
           "created_by": str(me["_id"]), "created_by_name": me.get("name"), "status": "open", "completed": {}, "created_at": now}
    res = await db.mystery_shops.insert_one(doc)
    from routers.push_notifications import send_push_to_user
    due_txt = f" by {due.strftime('%a %b %-d')}" if due else ""
    for uid in names:
        await db.notifications.insert_one({"user_id": uid, "type": "practice_assigned", "title": f"Practice call: {script.get('title')}", "message": f"{me.get('name') or 'Your manager'} wants you to run this call{due_txt}. Tap to start.",
                                           "link": f"/scripts/{script['_id']}?assignment={res.inserted_id}", "read": False, "dismissed": False, "created_at": now})
        try:
            await send_push_to_user(uid, f"Practice call: {script.get('title')}", f"Roleplay it against Jessi{due_txt}. Takes about 5 minutes.", f"/scripts/{script['_id']}?assignment={res.inserted_id}", "mic")
        except Exception as e:
            logger.debug(f"[Scripts] push failed for {uid}: {e}")
    return _shop_out(await db.mystery_shops.find_one({"_id": res.inserted_id}))


@router.delete("/mystery-shops/{shop_id}")
async def shops_cancel(shop_id: str, request: Request):
    me = await _current(request)
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers assign practice calls")
    res = await get_db().mystery_shops.update_one({"_id": _oid(shop_id, "Assignment")}, {"$set": {"status": "cancelled"}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"cancelled": True}


# ---------------------------------------------------------------- Twilio side of a phone practice call (no user auth: per-session token)
relay_router = APIRouter(prefix="/scripts/roleplay", tags=["Scripts & Practice"])


async def _phone_session(sid: str, token: str) -> dict:
    s = await get_db().roleplay_sessions.find_one({"_id": _oid(sid, "Session"), "token": token, "mode": "phone"}) if ObjectId.is_valid(sid) else None
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


@relay_router.post("/twiml/{sid}")
async def relay_twiml(sid: str, t: str):
    return _twiml(svc.relay_twiml(await _phone_session(sid, t)))


@relay_router.post("/after/{sid}")
async def relay_after(sid: str, t: str, request: Request):
    s = await _phone_session(sid, t)
    form = await request.form()
    if form.get("SessionStatus") == "failed":
        logger.warning(f"[Roleplay] ConversationRelay failed for {sid}: {form.get('ErrorCode')} {form.get('ErrorMessage')}")
        if not any(x.get("role") == "rep" for x in s.get("turns", [])):
            await get_db().roleplay_sessions.update_one({"_id": s["_id"], "status": {"$in": ["dialing", "live"]}},
                                                        {"$set": {"status": "failed", "fail_reason": f"The practice line had a problem ({form.get('ErrorCode') or 'relay'})", "updated_at": datetime.now(timezone.utc)}})
            return _twiml(svc.hangup_twiml("Sorry, the practice line had a problem. Please try again in a minute."))
    asyncio.create_task(svc.finalize_session(get_db(), sid, f"relay_{form.get('SessionStatus') or 'ended'}"))
    return _twiml(svc.hangup_twiml("Nice work. Your practice call is being graded, check the app in a moment."))


@relay_router.post("/status/{sid}")
async def relay_status(sid: str, t: str, request: Request):
    s = await _phone_session(sid, t)
    form = await request.form()
    status = form.get("CallStatus") or ""
    db = get_db()
    sets = {"call_status": status, "updated_at": datetime.now(timezone.utc)}
    if status in ("ringing", "initiated", "queued") and s.get("status") == "dialing":
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": sets})
    elif status == "in-progress":
        await db.roleplay_sessions.update_one({"_id": s["_id"], "status": "dialing"}, {"$set": {**sets, "status": "live"}})
    elif status in svc.FAIL_REASONS and s.get("status") in ("dialing",):
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {**sets, "status": "failed", "fail_reason": svc.FAIL_REASONS[status]}})
    elif status == "completed":
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": sets})
        asyncio.create_task(svc.finalize_session(db, sid, "call_completed"))
    return Response(content="", status_code=204)


@relay_router.post("/recording/{sid}")
async def relay_recording(sid: str, t: str, request: Request):
    await _phone_session(sid, t)
    form = await request.form()
    if form.get("RecordingUrl"):
        asyncio.create_task(svc.save_recording(get_db(), sid, form["RecordingUrl"], form.get("RecordingDuration")))
    return Response(content="", status_code=204)


@relay_router.websocket("/relay/{sid}/{token}")
async def relay_ws(ws: WebSocket, sid: str, token: str):
    """ConversationRelay <-> Jessi: rep speech arrives as text prompts, the customer's reply goes back as text to be spoken."""
    db = get_db()
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid), "token": token, "mode": "phone"}) if ObjectId.is_valid(sid) else None
    if not s:
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            kind = msg.get("type")
            if kind == "setup":
                await svc.relay_setup(db, sid, msg)
            elif kind == "prompt":
                heard = (msg.get("voicePrompt") or "").strip()
                if not msg.get("last", True) or not heard:
                    continue
                out = await svc.relay_turn(db, sid, heard)
                if out["say"]:
                    await ws.send_text(json.dumps({"type": "text", "token": out["say"], "last": True}))
                if out["ended"]:
                    await asyncio.sleep(min(12.0, 1.5 + len(out["say"]) / 14))
                    await ws.send_text(json.dumps({"type": "end", "handoffData": json.dumps({"reason": "customer_ended"})}))
            elif kind == "interrupt":
                await svc.relay_interrupt(db, sid, msg.get("utteranceUntilInterrupt"))
            elif kind == "error":
                logger.warning(f"[Roleplay] relay error for {sid}: {msg.get('description')}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[Roleplay] relay websocket ended for {sid}: {e}")
    finally:
        asyncio.create_task(svc.finalize_session(db, sid, "websocket_closed"))
