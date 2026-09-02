"""
Twilio voice webhooks for the Lead Call Engine (rep answers -> press 1 -> whisper -> bridge).
URLs carry job id + per-job secret token so they can't be spoofed.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, Form
from bson import ObjectId

from routers.database import get_db
from services import lead_call_engine as eng

router = APIRouter(prefix="/webhooks/twilio/lead-call", tags=["Lead Call Engine"])
logger = logging.getLogger(__name__)


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


async def _load_job(request: Request):
    q = request.query_params
    job_id, token, user_id = q.get("job", ""), q.get("t", ""), q.get("u", "")
    try:
        job = await get_db()[eng.COLL].find_one({"_id": ObjectId(job_id), "token": token})
    except Exception:
        job = None
    return job, user_id


@router.post("/answer")
async def lead_call_answer(request: Request, CallSid: str = Form(default="")):
    job, user_id = await _load_job(request)
    if not job:
        return _xml(eng.twiml(eng._say("Sorry, this lead is no longer available. Goodbye."), "<Hangup/>"))
    await eng.record_call_event(str(job["_id"]), CallSid, answered_at=datetime.now(timezone.utc), status="answered")
    if job.get("claimed_by"):
        await eng.record_call_event(str(job["_id"]), CallSid, late=True)
        name = await _rep_name(job["claimed_by"])
        return _xml(eng.twiml_already_claimed(name))
    action = f"{eng._app_url()}/api/webhooks/twilio/lead-call/claim?job={job['_id']}&u={user_id}&t={job['token']}"
    return _xml(eng.twiml_answer(job, action))


@router.post("/claim")
async def lead_call_claim(request: Request, Digits: str = Form(default=""), CallSid: str = Form(default="")):
    job, user_id = await _load_job(request)
    if not job:
        return _xml(eng.twiml(eng._say("Sorry, this lead is no longer available. Goodbye."), "<Hangup/>"))
    if Digits.strip() != "1":
        await eng.record_call_event(str(job["_id"]), CallSid, passed=True, status="passed")
        return _xml(eng.twiml_passed())
    won, job = await eng.try_claim_by_phone(str(job["_id"]), user_id)
    if not won:
        await eng.record_call_event(str(job["_id"]), CallSid, late=True, status="late")
        return _xml(eng.twiml_already_claimed(await _rep_name(job.get("claimed_by"))))
    await eng.record_call_event(str(job["_id"]), CallSid, status="claimed")
    db = get_db()
    rep = await db.users.find_one({"_id": ObjectId(user_id)}, {"twilio_number": 1, "mvpline_number": 1}) or {}
    source = await db.lead_sources.find_one({"_id": ObjectId(job["lead_source_id"])}) if job.get("lead_source_id") else {}
    caller_id = await eng._from_number_for(db, source or {}, rep)
    await db.messages.insert_one({
        "conversation_id": job["conversation_id"], "user_id": user_id, "contact_id": job.get("contact_id"),
        "sender": "user", "direction": "outbound", "channel": "voice", "type": "call_log",
        "content": f"Claimed by phone and called {job['customer_phone']}", "call_status": "placed",
        "timestamp": datetime.now(timezone.utc),
    })
    logger.info(f"[LeadCall] {user_id} claimed job {job['_id']} by phone; bridging to {job['customer_phone']}")
    return _xml(eng.twiml_claimed_and_bridge(job, caller_id))


@router.post("/status")
async def lead_call_status(request: Request, CallSid: str = Form(default=""), CallStatus: str = Form(default="")):
    job, user_id = await _load_job(request)
    if job and CallSid:
        await eng.record_call_status(str(job["_id"]), user_id, CallSid, CallStatus)
    return Response(content="", status_code=204)


async def _rep_name(user_id) -> str:
    if not user_id:
        return ""
    try:
        u = await get_db().users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "first_name": 1})
        return (u or {}).get("first_name") or (u or {}).get("name") or ""
    except Exception:
        return ""
