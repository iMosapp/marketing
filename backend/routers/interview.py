"""Onboarding voice interview API: the rep taps "Call me", Jessi rings them, interviews them and builds their VA. Plus the Twilio side (per-session token, no user auth)."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import interview as svc
from services import voice_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["Onboarding interview"], dependencies=[Depends(require_user)])
public = APIRouter(prefix="/interview", tags=["Onboarding interview"])


def _mask(p: Optional[str]) -> str:
    d = "".join(c for c in (p or "") if c.isdigit())[-10:]
    return f"({d[:3]}) •••-{d[6:]}" if len(d) == 10 else (p or "")


def _oid(v: str) -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=404, detail="Interview not found")
    return ObjectId(str(v))


async def _mine(db, sid: str, me: dict) -> dict:
    s = await db[svc.COLL].find_one({"_id": _oid(sid), "user_id": str(me["_id"])})
    if not s:
        raise HTTPException(status_code=404, detail="Interview not found")
    return s


def _persona_filled(user: dict) -> int:
    p = user.get("persona") or {}
    return sum(1 for k in ("bio", "specialties", "tone", "hobbies", "years_experience", "ideal_customer", "never_say", "family_info", "vehicles", "personal_motto", "humor_level") if (p.get(k) if not isinstance(p.get(k), list) else len(p.get(k) or [])))


class StartBody(BaseModel):
    dry_run: bool = False


@router.get("/status")
async def status(request: Request):
    """Everything the interview card needs: the latest session, Voice ID state, whether we can call, whether the feature is live."""
    me = await _resolve(request)
    db = get_db()
    from services import lab
    s = await svc.latest(db, str(me["_id"]))
    user = await db.users.find_one({"_id": ObjectId(str(me["_id"]))}, {"voice_id": 1, "persona": 1, "phone": 1, "persona_interviewed_at": 1})
    phone = (user or {}).get("phone") or ""
    return {"session": svc.serialize(s), "voice": voice_id.summary(user), "phone": _mask(phone), "can_call": len("".join(c for c in phone if c.isdigit())) >= 10,
            "available": await lab.visible(db, me, "voice_interview"), "is_super_admin": me.get("role") == "super_admin",
            "persona_filled": _persona_filled(user or {}), "interviewed_at": (user or {}).get("persona_interviewed_at").isoformat() if (user or {}).get("persona_interviewed_at") else None}


@router.get("/coverage")
async def coverage(request: Request, days: int = 7):
    """Managers: which reps have a voice print and how many of the recent recorded calls Voice ID confirmed were them."""
    me = await _resolve(request)
    db = get_db()
    from services.lead_flows import MANAGER_ROLES, store_reps, user_store_id
    if me.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Managers only")
    days = max(1, min(90, int(days or 7)))
    sid = user_store_id(me)
    reps = [r for r in await store_reps(db, sid, me) if r.get("on_team", True)]
    ids = [r["_id"] for r in reps]
    oids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    users = {str(u["_id"]): u for u in await db.users.find({"_id": {"$in": oids}}, {"voice_id.status": 1, "voice_id.percent": 1, "voice_id.enrolled_at": 1, "voice_id.attempted_at": 1, "voice_id.source": 1, "voice_id.profile": 1, "voice_id.error": 1}).to_list(len(oids) or 1)}
    since = datetime.now(timezone.utc) - timedelta(days=days)
    counts = {i: {"total": 0, "verified": 0, "mismatched": 0, "unchecked": 0} for i in ids}
    async for row in db.call_logs.aggregate([{"$match": {"user_id": {"$in": ids}, "created_at": {"$gte": since}}},
                                             {"$group": {"_id": {"u": "$user_id", "v": "$voice_verified"}, "n": {"$sum": 1}}}]):
        c = counts.get(row["_id"]["u"])
        if c is None:
            continue
        v = row["_id"].get("v")
        c["total"] += row["n"]
        c["verified" if v is True else "mismatched" if v is False else "unchecked"] += row["n"]
    out = []
    for r in reps:
        u = users.get(r["_id"]) or {}
        v = voice_id.summary(u)
        v.pop("error", None)
        out.append({"id": r["_id"], "name": r["name"], "role": r.get("role"), "photo_url": r.get("photo_url"), "voice": v, "calls": counts[r["_id"]]})
    out.sort(key=lambda x: (not x["voice"]["enrolled"], -x["calls"]["total"], x["name"].lower()))
    totals = {"reps": len(out), "enrolled": sum(1 for x in out if x["voice"]["enrolled"]),
              "calls": {k: sum(x["calls"][k] for x in out) for k in ("total", "verified", "mismatched", "unchecked")}}
    store = await db.stores.find_one({"_id": ObjectId(str(sid))}, {"name": 1}) if sid and ObjectId.is_valid(str(sid)) else None
    return {"days": days, "store_name": (store or {}).get("name"), "eagle": voice_id.available() is None, "totals": totals, "reps": out}



@router.post("/start")
async def start(request: Request, body: Optional[StartBody] = None):
    me = await _resolve(request)
    from services.lab import visible
    from services.lead_flows import user_store_id
    me["store_id"] = user_store_id(me)
    dry = bool(body and body.dry_run)
    if dry and me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Test runs are for the Test Lab")
    if not dry and not await visible(get_db(), me, "voice_interview") and me.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="The interview is not open yet")
    try:
        return await svc.start(get_db(), me, dry_run=dry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sessions/{sid}")
async def get_session(sid: str, request: Request):
    me = await _resolve(request)
    db = get_db()
    return svc.serialize(await svc.reconcile_dialing(db, await _mine(db, sid, me)))


@router.post("/sessions/{sid}/hangup")
async def hangup(sid: str, request: Request):
    """Rep ends it from the app: whatever was said so far still gets built (if there is enough)."""
    me = await _resolve(request)
    db = get_db()
    s = await _mine(db, sid, me)
    if s.get("status") in ("dialing", "live", "ending"):
        if s.get("call_sid"):
            from services.lead_call_engine import _twilio_client
            client = _twilio_client()
            if client:
                try:
                    await asyncio.to_thread(client.calls(s["call_sid"]).update, status="completed")
                except Exception as e:
                    logger.debug(f"[Interview] hangup failed: {e}")
        asyncio.create_task(svc.finalize(db, sid, "rep_hung_up_in_app"))
    return {"ok": True}


@router.post("/sessions/{sid}/rebuild")
async def rebuild(sid: str, request: Request):
    """Building failed (or the rep wants Jessi to take another pass): run the transcript through again."""
    me = await _resolve(request)
    db = get_db()
    s = await _mine(db, sid, me)
    if sum(1 for t in s.get("turns", []) if t.get("role") == "rep") < svc.MIN_REP_TURNS:
        raise HTTPException(status_code=400, detail="Not enough of a conversation to build from")
    await db[svc.COLL].update_one({"_id": s["_id"]}, {"$set": {"status": "building", "updated_at": datetime.now(timezone.utc)}})
    out = await svc.build(db, await db[svc.COLL].find_one({"_id": s["_id"]}))
    if not out:
        raise HTTPException(status_code=502, detail="Jessi could not write your profile from this call, try again in a minute")
    return svc.serialize(out)


@router.post("/sessions/{sid}/apply")
async def apply_now(sid: str, request: Request):
    """Test Lab run the rep liked: put the write-up on their profile after all."""
    me = await _resolve(request)
    db = get_db()
    s = await _mine(db, sid, me)
    if s.get("status") != "completed" or not s.get("extracted"):
        raise HTTPException(status_code=400, detail="Nothing to save yet, the write-up is not finished")
    return svc.serialize(await svc.apply_session(db, s))


@router.delete("/voice")
async def forget_voice(request: Request):
    me = await _resolve(request)
    await voice_id.clear_user(get_db(), str(me["_id"]))
    return {"ok": True, "voice": voice_id.summary(None)}


# ---------------------------------------------------------------- Twilio callbacks (per-session token)
async def _session(sid: str, token: str) -> dict:
    """Internal only (TwiML builders), never returned to a client."""
    doc = await svc.by_token(get_db(), sid, token) if ObjectId.is_valid(str(sid or "")) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Interview not found")
    return doc


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


@public.post("/call/twiml/{sid}")
async def call_twiml(sid: str, t: str):
    return _twiml(svc.twiml(await _session(sid, t)))


@public.post("/call/after/{sid}")
async def call_after(sid: str, t: str, request: Request):
    s = await _session(sid, t)
    form = await request.form()
    db = get_db()
    if form.get("SessionStatus") == "failed":
        logger.warning(f"[Interview] ConversationRelay failed for {sid}: {form.get('ErrorCode')} {form.get('ErrorMessage')}")
        if not any(x.get("role") == "rep" for x in s.get("turns", [])):
            await db[svc.COLL].update_one({"_id": s["_id"], "status": {"$in": ["dialing", "live"]}},
                                          {"$set": {"status": "failed", "fail_reason": f"The line had a problem ({form.get('ErrorCode') or 'relay'}), tap Call me to try again", "updated_at": datetime.now(timezone.utc)}})
            return _twiml(svc.hangup_twiml("Sorry, the line had a problem. Tap Call me in the app and we'll try again."))
    asyncio.create_task(svc.finalize(db, sid, f"relay_{form.get('SessionStatus') or 'ended'}"))
    return _twiml(svc.goodbye_twiml())


@public.post("/call/status/{sid}")
async def call_status(sid: str, t: str, request: Request):
    s = await _session(sid, t)
    form = await request.form()
    status = form.get("CallStatus") or ""
    db = get_db()
    sets = {"call_status": status, "updated_at": datetime.now(timezone.utc)}
    if status == "in-progress":
        await db[svc.COLL].update_one({"_id": s["_id"], "status": "dialing"}, {"$set": {**sets, "status": "live"}})
    elif status in svc.FAIL_REASONS and s.get("status") == "dialing":
        await db[svc.COLL].update_one({"_id": s["_id"]}, {"$set": {**sets, **svc.failure_from_status(status, form.get("SipResponseCode") or None, s.get("from_number"))}})
    elif status == "completed":
        await db[svc.COLL].update_one({"_id": s["_id"]}, {"$set": sets})
        asyncio.create_task(svc.finalize(db, sid, "call_completed"))
    else:
        await db[svc.COLL].update_one({"_id": s["_id"]}, {"$set": sets})
    return Response(content="", status_code=204)


@public.post("/call/recording/{sid}")
async def call_recording(sid: str, t: str, request: Request):
    await _session(sid, t)
    form = await request.form()
    if form.get("RecordingUrl"):
        asyncio.create_task(svc.save_recording(get_db(), sid, form["RecordingUrl"], form.get("RecordingDuration")))
    return Response(content="", status_code=204)


@public.websocket("/relay/{sid}/{token}")
async def relay_ws(ws: WebSocket, sid: str, token: str):
    """ConversationRelay <-> Jessi the interviewer: rep speech arrives as text, Jessi's next question goes back as text."""
    db = get_db()
    s = await db[svc.COLL].find_one({"_id": ObjectId(sid), "token": token}) if ObjectId.is_valid(sid) else None
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
                    await ws.send_text(json.dumps({"type": "end", "handoffData": json.dumps({"reason": "interview_done"})}))
            elif kind == "interrupt":
                await svc.relay_interrupt(db, sid, msg.get("utteranceUntilInterrupt"))
            elif kind == "error":
                logger.warning(f"[Interview] relay error for {sid}: {msg.get('description')}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[Interview] relay websocket ended for {sid}: {e}")
    finally:
        asyncio.create_task(svc.finalize(db, sid, "websocket_closed"))
