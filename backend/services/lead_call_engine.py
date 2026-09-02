"""
Lead Call Engine - CallDrip-style rep dialing for new leads.

Flow: lead arrives -> job created with an escalation ladder (up to 4 attempts, each its own reps
and delay) -> scheduler rings every rep in the current attempt -> rep presses 1 to claim ->
only the winner hears the whisper (name, source, comments) and is bridged to the customer.
Claiming in-app (push notification) stops the dialing too.
"""
import os
import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from xml.sax.saxutils import escape

from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
RING_SECONDS = 25
COLL = "lead_call_jobs"


def _app_url() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def _twilio_client():
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not tok:
        return None
    from twilio.rest import Client
    return Client(sid, tok)


def _e164(phone: str) -> str:
    from routers.twilio_webhooks import normalize_phone
    return normalize_phone(phone or "")


def normalize_attempts(raw: list, fallback_user_ids: list) -> list:
    """Clamp to MAX_ATTEMPTS, drop empty attempts, default the ladder to the workflow reps."""
    attempts = []
    for a in (raw or [])[:MAX_ATTEMPTS]:
        user_ids = [u for u in (a.get("user_ids") or []) if u]
        if not user_ids:
            continue
        delay = a.get("delay_seconds")
        attempts.append({"user_ids": user_ids, "delay_seconds": max(0, int(60 if delay is None else delay))})
    if not attempts and fallback_user_ids:
        attempts = [{"user_ids": list(fallback_user_ids), "delay_seconds": 60}]
    return attempts


async def start_call_workflow(source: dict, conversation_id: str, contact_id: str,
                              customer_phone: str, lead: dict, assigned_user_id: Optional[str] = None) -> Optional[str]:
    """Create the dialing job. Attempt 1 fires on the next scheduler tick (<= 15s)."""
    db = get_db()
    attempts = normalize_attempts(source.get("call_attempts"), source.get("workflow_user_ids") or [])
    if not attempts or not customer_phone:
        logger.info(f"[LeadCall] No attempts configured or no phone for conv {conversation_id}; skipping")
        return None
    if assigned_user_id:
        # Round robin: the assigned rep gets the first shot, the ladder handles escalation
        attempts = [{"user_ids": [assigned_user_id], "delay_seconds": 0}] + attempts[: MAX_ATTEMPTS - 1]

    existing = await db[COLL].find_one({"conversation_id": conversation_id, "status": "active"})
    if existing:
        return str(existing["_id"])

    now = datetime.now(timezone.utc)
    doc = {
        "token": secrets.token_urlsafe(16),
        "conversation_id": conversation_id,
        "contact_id": contact_id,
        "lead_source_id": str(source.get("_id", "")),
        "source_name": source.get("name", "Lead"),
        "customer_phone": _e164(customer_phone),
        "lead": lead,
        "attempts": attempts,
        "attempt_index": 0,
        "next_attempt_at": now,
        "status": "active",
        "claimed_by": None,
        "claimed_via": None,
        "calls": [],
        "created_at": now,
        "updated_at": now,
    }
    res = await db[COLL].insert_one(doc)
    logger.info(f"[LeadCall] Job {res.inserted_id} created for conv {conversation_id} with {len(attempts)} attempt(s)")
    return str(res.inserted_id)


async def _from_number_for(db, source: dict, rep: dict) -> str:
    return (
        source.get("phone_number")
        or rep.get("twilio_number") or rep.get("mvpline_number")
        or os.environ.get("TWILIO_PHONE_NUMBER", "")
    )


async def _run_attempt(db, job: dict):
    idx = job["attempt_index"]
    attempt = job["attempts"][idx]
    client = _twilio_client()
    source = await db.lead_sources.find_one({"_id": ObjectId(job["lead_source_id"])}) if job.get("lead_source_id") else {}
    source = source or {}
    job_id, token = str(job["_id"]), job["token"]
    placed = []
    for uid in attempt["user_ids"]:
        try:
            rep = await db.users.find_one({"_id": ObjectId(uid)}, {"phone": 1, "twilio_number": 1, "mvpline_number": 1, "name": 1})
        except Exception:
            rep = None
        rep_phone = _e164((rep or {}).get("phone", ""))
        if not rep or not rep_phone:
            placed.append({"attempt": idx + 1, "user_id": uid, "status": "no_phone", "at": datetime.now(timezone.utc)})
            continue
        entry = {"attempt": idx + 1, "user_id": uid, "rep_name": rep.get("name", ""), "status": "queued", "at": datetime.now(timezone.utc)}
        if client is None:
            entry["status"] = "twilio_disabled"
            placed.append(entry)
            continue
        try:
            base = f"{_app_url()}/api/webhooks/twilio/lead-call"
            qs = f"job={job_id}&u={uid}&t={token}"
            call = await asyncio.to_thread(
                client.calls.create,
                to=rep_phone,
                from_=await _from_number_for(db, source, rep),
                url=f"{base}/answer?{qs}",
                status_callback=f"{base}/status?{qs}",
                status_callback_event=["completed"],
                timeout=RING_SECONDS,
            )
            entry["call_sid"] = call.sid
            entry["status"] = "ringing"
        except Exception as e:
            entry["status"] = "failed"
            entry["error"] = str(e)[:200]
            logger.warning(f"[LeadCall] Call to rep {uid} failed: {e}")
        placed.append(entry)

    is_last = idx + 1 >= len(job["attempts"])
    next_delay = job["attempts"][idx + 1]["delay_seconds"] if not is_last else 0
    update = {
        "$push": {"calls": {"$each": placed}},
        "$set": {
            "attempt_index": idx + 1,
            "updated_at": datetime.now(timezone.utc),
            "next_attempt_at": datetime.now(timezone.utc) + timedelta(seconds=max(next_delay, RING_SECONDS + 5)),
            **({"status": "exhausted", "exhausted_at": datetime.now(timezone.utc)} if is_last else {}),
        },
    }
    await db[COLL].update_one({"_id": job["_id"], "status": "active"}, update)
    logger.info(f"[LeadCall] Attempt {idx + 1}/{len(job['attempts'])} fired for job {job_id}: {[(p['user_id'], p['status']) for p in placed]}")
    if is_last:
        asyncio.create_task(_notify_exhausted(job))


async def _notify_exhausted(job: dict):
    """Nobody claimed after the final attempt: tell every rep on the ladder so the lead isn't lost."""
    try:
        from routers.push_notifications import send_push_to_user
        name = (job.get("lead") or {}).get("name") or "New lead"
        reps = {u for a in job.get("attempts", []) for u in a.get("user_ids", [])}
        for uid in reps:
            await send_push_to_user(uid, f"Unclaimed lead: {name}",
                                    f"Nobody picked up after {len(job.get('attempts', []))} attempts. Tap to claim.",
                                    f"/thread/{job['conversation_id']}", "exclamationmark.triangle")
    except Exception as e:
        logger.debug(f"[LeadCall] exhausted notify failed: {e}")


async def process_lead_call_jobs():
    """Scheduler tick (every 15s): fire the next attempt for every due, unclaimed job."""
    db = get_db()
    now = datetime.now(timezone.utc)
    due = await db[COLL].find({"status": "active", "next_attempt_at": {"$lte": now}}).to_list(50)
    for job in due:
        if job["attempt_index"] >= len(job["attempts"]):
            await db[COLL].update_one({"_id": job["_id"]}, {"$set": {"status": "exhausted"}})
            continue
        # Skip if the conversation got claimed in-app between ticks
        conv = await db.conversations.find_one({"_id": ObjectId(job["conversation_id"])}, {"claimed_by": 1, "claim_source": 1})
        if conv and conv.get("claimed_by") and conv.get("claim_source") == "app":
            await mark_claimed(job["conversation_id"], conv["claimed_by"], via="app")
            continue
        try:
            await _run_attempt(db, job)
        except Exception as e:
            logger.warning(f"[LeadCall] attempt failed for job {job['_id']}: {e}")


async def try_claim_by_phone(job_id: str, user_id: str) -> tuple[bool, dict]:
    """Atomic press-1 claim. Returns (won, job)."""
    db = get_db()
    now = datetime.now(timezone.utc)
    job = await db[COLL].find_one_and_update(
        {"_id": ObjectId(job_id), "status": {"$in": ["active", "exhausted"]}, "claimed_by": None},
        {"$set": {"status": "claimed", "claimed_by": user_id, "claimed_via": "phone", "claimed_at": now, "updated_at": now}},
        return_document=True,
    )
    if not job:
        return False, await db[COLL].find_one({"_id": ObjectId(job_id)}) or {}
    await _apply_claim_to_conversation(db, job, user_id, via="phone")
    asyncio.create_task(_hangup_other_calls(job, keep_user_id=user_id))
    asyncio.create_task(_notify_claimed(job, user_id))
    return True, job


async def mark_claimed(conversation_id: str, user_id: str, via: str = "app"):
    """Called when a rep claims in-app: stop dialing everyone else."""
    db = get_db()
    now = datetime.now(timezone.utc)
    job = await db[COLL].find_one_and_update(
        {"conversation_id": conversation_id, "status": {"$in": ["active", "exhausted"]}, "claimed_by": None},
        {"$set": {"status": "claimed", "claimed_by": user_id, "claimed_via": via, "claimed_at": now, "updated_at": now}},
        return_document=True,
    )
    if job:
        asyncio.create_task(_hangup_other_calls(job, keep_user_id=user_id))
        logger.info(f"[LeadCall] Job {job['_id']} claimed via {via} by {user_id}")


async def _apply_claim_to_conversation(db, job: dict, user_id: str, via: str):
    now = datetime.now(timezone.utc)
    await db.conversations.update_one(
        {"_id": ObjectId(job["conversation_id"])},
        {"$set": {"claimed": True, "claimed_by": user_id, "assigned_to": user_id, "user_id": user_id,
                  "claimed_at": now.isoformat(), "claim_source": via, "updated_at": now.isoformat()}},
    )
    if job.get("contact_id"):
        await db.contacts.update_one(
            {"_id": ObjectId(job["contact_id"])},
            {"$set": {"user_id": user_id, "claimed_by": user_id, "claimed_at": now.isoformat(), "updated_at": now.isoformat()}},
        )


async def _hangup_other_calls(job: dict, keep_user_id: str):
    client = _twilio_client()
    if not client:
        return
    for c in job.get("calls", []):
        if c.get("call_sid") and c.get("user_id") != keep_user_id and c.get("status") in ("ringing", "queued"):
            try:
                await asyncio.to_thread(client.calls(c["call_sid"]).update, status="completed")
            except Exception:
                pass


async def _notify_claimed(job: dict, winner_id: str):
    try:
        db = get_db()
        winner = await db.users.find_one({"_id": ObjectId(winner_id)}, {"name": 1}) or {}
        name = (job.get("lead") or {}).get("name") or "the lead"
        from routers.push_notifications import send_push_to_user
        others = {u for a in job.get("attempts", []) for u in a.get("user_ids", [])} - {winner_id}
        for uid in others:
            await send_push_to_user(uid, f"{winner.get('name', 'A teammate')} claimed {name}",
                                    f"{job.get('source_name', 'Lead')} lead is handled.", f"/thread/{job['conversation_id']}", "checkmark.circle")
    except Exception as e:
        logger.debug(f"[LeadCall] claimed notify failed: {e}")


async def record_call_status(job_id: str, user_id: str, call_sid: str, status: str):
    db = get_db()
    await db[COLL].update_one(
        {"_id": ObjectId(job_id), "calls.call_sid": call_sid},
        {"$set": {"calls.$.status": status, "updated_at": datetime.now(timezone.utc)}},
    )


# ── TwiML ─────────────────────────────────────────────────────────────────────
def _say(text: str) -> str:
    return f'<Say voice="Polly.Joanna">{escape(text)}</Say>'


def twiml(*parts: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + "</Response>"


def twiml_answer(job: dict, action_url: str) -> str:
    src = (job.get("lead") or {}).get("source_label") or job.get("source_name") or "your website"
    prompt = _say(f"New lead from {src}. Press 1 to claim this lead.")
    gather = f'<Gather numDigits="1" timeout="6" action="{escape(action_url)}" method="POST">{prompt}</Gather>'
    return twiml(gather, gather, _say("No response received. Goodbye."), "<Hangup/>")


def whisper_text(job: dict) -> str:
    lead = job.get("lead") or {}
    bits = [f"You got it. New lead: {lead.get('name') or 'no name given'}."]
    if lead.get("source_label"):
        bits.append(f"They came in from {lead['source_label']}.")
    if lead.get("company"):
        bits.append(f"Company: {lead['company']}.")
    if lead.get("industry"):
        bits.append(f"Industry: {lead['industry']}.")
    if lead.get("interest"):
        bits.append(f"Interested in {lead['interest']}.")
    if lead.get("comments"):
        bits.append(f"They wrote: {lead['comments'][:300]}.")
    bits.append("Connecting you now.")
    return " ".join(bits)


def twiml_claimed_and_bridge(job: dict, caller_id: str) -> str:
    dial = f'<Dial callerId="{escape(caller_id)}" timeout="30">{escape(job["customer_phone"])}</Dial>'
    return twiml(_say(whisper_text(job)), dial, _say("The call has ended. Goodbye."))


def twiml_already_claimed(name: str) -> str:
    who = f"{name} already" if name else "Someone already"
    return twiml(_say(f"Sorry, {who} claimed this lead. Goodbye."), "<Hangup/>")


def twiml_passed() -> str:
    return twiml(_say("Okay, passing on this lead. Goodbye."), "<Hangup/>")
