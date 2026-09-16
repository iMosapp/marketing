"""Twilio voice webhooks for the power dialer. Every URL carries the session / attempt id plus its secret token."""
import logging
from fastapi import APIRouter, Request, Response, Form
from bson import ObjectId

from routers.database import get_db
from services import dialer as eng

router = APIRouter(prefix="/webhooks/dialer", tags=["Power Dialer webhooks"])
logger = logging.getLogger(__name__)


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


def _bye(text: str = "Sorry, this call is no longer active. Goodbye.") -> Response:
    return _xml(eng.twiml(eng._say(text), "<Hangup/>"))


async def _session(request: Request):
    q = request.query_params
    sid, tok = q.get("s", ""), q.get("t", "")
    if not ObjectId.is_valid(sid) or not tok:
        return None
    doc = await get_db()[eng.SESSIONS].find_one({"_id": ObjectId(sid), "token": tok})
    return doc or None


async def _attempt(request: Request):
    q = request.query_params
    aid, tok = q.get("a", ""), q.get("t", "")
    if not ObjectId.is_valid(aid) or not tok:
        return None
    doc = await get_db()[eng.ATTEMPTS].find_one({"_id": ObjectId(aid), "token": tok})
    return doc or None


# ── rep leg ───────────────────────────────────────────────────────────────────
@router.post("/rep/answer")
async def rep_answer(request: Request):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye()
    return _xml(await eng.on_rep_answer(get_db(), s))


@router.post("/rep/idle")
async def rep_idle(request: Request):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye("Session finished. Goodbye.")
    c = await get_db()[eng.CAMPAIGNS].find_one({"_id": eng._oid(s["campaign_id"])}) or {}
    say = request.query_params.get("say")
    if say:
        await get_db()[eng.SESSIONS].update_one({"_id": s["_id"]}, {"$set": {"last_message": eng.BURST_SAY.get(say, say)}})
    return _xml(eng.twiml_rep_idle(s, c, say=say, quiet=bool(request.query_params.get("quiet")) and not say))


@router.post("/rep/digit")
async def rep_digit(request: Request, Digits: str = Form(default="")):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye("Session finished. Goodbye.")
    return _xml(await eng.on_rep_digit(get_db(), s, Digits))


@router.post("/rep/burst")
async def rep_burst(request: Request):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye()
    return _xml(await eng.on_rep_burst_twiml(get_db(), s, request.query_params.get("b", "")))


@router.post("/rep/accept")
async def rep_accept(request: Request):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye()
    a = await get_db()[eng.ATTEMPTS].find_one({"_id": eng._oid(request.query_params.get("a"))})
    if not a:
        c = await get_db()[eng.CAMPAIGNS].find_one({"_id": eng._oid(s["campaign_id"])}) or {}
        return _xml(eng.twiml_rep_idle(s, c))
    return _xml(eng.twiml_rep_accept(s, a))


@router.post("/rep/accept-digit")
async def rep_accept_digit(request: Request, Digits: str = Form(default="")):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye()
    digits = "" if request.query_params.get("timeout") else Digits
    return _xml(await eng.on_rep_accept(get_db(), s, request.query_params.get("a", ""), digits))


@router.post("/rep/after-burst")
async def rep_after_burst(request: Request):
    s = await _session(request)
    if not s or s.get("status") == "ended":
        return _bye("Session finished. Goodbye.")
    return _xml(await eng.on_rep_after_burst(get_db(), s, request.query_params.get("b", "")))


@router.post("/rep/status")
async def rep_status(request: Request, CallStatus: str = Form(default="")):
    s = await _session(request)
    if s:
        await eng.on_rep_status(get_db(), s, CallStatus)
    return Response(status_code=204)


@router.post("/rep/recording")
async def rep_recording(request: Request, RecordingUrl: str = Form(default=""), RecordingSid: str = Form(default=""), RecordingDuration: str = Form(default="")):
    s = await _session(request)
    if s and RecordingUrl:
        db = get_db()
        burst = await db[eng.BURSTS].find_one({"_id": eng._oid(request.query_params.get("b"))})
        if burst and burst.get("connected_attempt_id"):
            await db[eng.ATTEMPTS].update_one({"_id": eng._oid(burst["connected_attempt_id"])}, {"$set": {"recording_url": RecordingUrl, "recording_sid": RecordingSid, "recording_duration_s": int(RecordingDuration or 0)}})
    return Response(status_code=204)


# ── lead legs ─────────────────────────────────────────────────────────────────
@router.post("/lead/answer")
async def lead_answer(request: Request, CallSid: str = Form(default="")):
    a = await _attempt(request)
    if not a:
        return _xml(eng.twiml("<Hangup/>"))
    return _xml(await eng.on_lead_answer(get_db(), a, CallSid))


@router.post("/lead/amd")
async def lead_amd(request: Request, AnsweredBy: str = Form(default="")):
    a = await _attempt(request)
    if a:
        await eng.on_lead_amd(get_db(), a, AnsweredBy)
    return Response(status_code=204)


@router.post("/lead/status")
async def lead_status(request: Request):
    a = await _attempt(request)
    if a:
        form = dict(await request.form())
        await eng.on_lead_status(get_db(), a, form.get("CallStatus", ""), form)
    return Response(status_code=204)


@router.post("/lead/after")
async def lead_after(request: Request):
    return _xml(eng.twiml("<Hangup/>"))


@router.post("/lead/abandon")
async def lead_abandon(request: Request):
    a = await _attempt(request)
    if not a:
        return _xml(eng.twiml("<Hangup/>"))
    db = get_db()
    c = await db[eng.CAMPAIGNS].find_one({"_id": eng._oid(a["campaign_id"])}) or {}
    s = await db[eng.SESSIONS].find_one({"_id": eng._oid(a["session_id"])}) or {}
    return _xml(eng.twiml_lead_abandon(a, c, s))


@router.post("/lead/optout")
async def lead_optout(request: Request, Digits: str = Form(default="")):
    a = await _attempt(request)
    if not a:
        return _xml(eng.twiml("<Hangup/>"))
    return _xml(await eng.on_lead_optout(get_db(), a, Digits))


# ── audio ─────────────────────────────────────────────────────────────────────
@router.api_route("/audio/ringback", methods=["GET", "POST"])
async def ringback():
    return Response(content=eng.ringback_wav(), media_type="audio/wav", headers={"Cache-Control": "public, max-age=86400"})
