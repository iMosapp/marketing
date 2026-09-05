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
                              customer_phone: str, lead: dict, assigned_user_id: Optional[str] = None,
                              not_before: Optional[datetime] = None, deferred_reasons: Optional[list] = None) -> Optional[str]:
    """Create the dialing job. Attempt 1 fires on the next scheduler tick (<= 15s), or at
    `not_before` when the store is closed / outside the customer's texting window."""
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
    deferred = bool(not_before and not_before > now)
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
        "next_attempt_at": not_before if deferred else now,
        "status": "active",
        "deferred": deferred,
        "deferred_until": not_before if deferred else None,
        "deferred_reasons": deferred_reasons or [],
        "claimed_by": None,
        "claimed_via": None,
        "calls": [],
        "created_at": now,
        "updated_at": now,
    }
    res = await db[COLL].insert_one(doc)
    logger.info(f"[LeadCall] Job {res.inserted_id} created for conv {conversation_id} with {len(attempts)} attempt(s)"
                + (f", deferred until {not_before.isoformat()} ({deferred_reasons})" if deferred else ""))
    return str(res.inserted_id)


async def _rep_already_engaged(db, conversation_id: str) -> bool:
    """A human rep texted or called this lead already (Jessi and intake texts don't count)."""
    hit = await db.messages.find_one(
        {"conversation_id": conversation_id, "sender": "user", "direction": {"$ne": "inbound"}},
        {"_id": 1},
    )
    return hit is not None


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
            **({"deferred": False, "was_deferred": True, "released_at": datetime.now(timezone.utc)} if job.get("deferred") else {}),
            **({"status": "exhausted", "exhausted_at": datetime.now(timezone.utc)} if is_last else {}),
        },
    }
    await db[COLL].update_one({"_id": job["_id"], "status": "active"}, update)
    logger.info(f"[LeadCall] Attempt {idx + 1}/{len(job['attempts'])} fired for job {job_id}: {[(p['user_id'], p['status']) for p in placed]}")
    # Activity feed: each rep that was rung sees the attempt on the lead's timeline
    from utils.activity_log import log_activity
    lead_name = (job.get("lead") or {}).get("name") or "New lead"
    for p in placed:
        if p.get("status") == "ringing" and job.get("contact_id"):
            await log_activity(db, user_id=p["user_id"], contact_id=job["contact_id"], event_type="lead_call_attempt",
                               description=f"Attempt {idx + 1} of {len(job['attempts'])} · {job.get('source_name', 'Lead')} · {lead_name}",
                               ref=p.get("call_sid"), metadata={"job_id": job_id, "attempt": idx + 1})
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
        first_rung = job["attempt_index"] == 0
        if conv and conv.get("claimed_by") and (conv.get("claim_source") == "app" or (job.get("deferred") and first_rung)):
            await mark_claimed(job["conversation_id"], conv["claimed_by"], via=conv.get("claim_source") or "app")
            continue
        # An overnight lead a rep already texted/called by morning does not need the ladder
        if job.get("deferred") and first_rung and await _rep_already_engaged(db, job["conversation_id"]):
            await db[COLL].update_one({"_id": job["_id"]}, {"$set": {"status": "handled", "handled_reason": "rep_replied", "updated_at": now}})
            logger.info(f"[LeadCall] Deferred job {job['_id']} skipped: rep already engaged the lead")
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
        prev = await db.contacts.find_one_and_update(
            {"_id": ObjectId(job["contact_id"])},
            {"$set": {"user_id": user_id, "claimed_by": user_id, "claimed_at": now.isoformat(), "updated_at": now.isoformat()}},
        )
        from utils.activity_log import on_lead_claimed
        await on_lead_claimed(db, contact_id=job["contact_id"], user_id=user_id, via=via,
                              previous_owner=str((prev or {}).get("user_id") or ""))


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
    """Twilio final status (completed / no-answer / busy / failed / canceled). Never overwrites
    an outcome we learned from the rep's keypress (answered / passed / claimed / late)."""
    db = get_db()
    now = datetime.now(timezone.utc)
    await db[COLL].update_one(
        {"_id": ObjectId(job_id), "calls.call_sid": call_sid},
        {"$set": {"calls.$.twilio_status": status, "calls.$.ended_at": now, "updated_at": now}},
    )
    await db[COLL].update_one(
        {"_id": ObjectId(job_id), "calls": {"$elemMatch": {"call_sid": call_sid, "status": {"$in": ["ringing", "queued"]}}}},
        {"$set": {"calls.$.status": status}},
    )


async def record_call_event(job_id: str, call_sid: str, **fields):
    """Mark what the rep did on a ringing leg: answered_at, passed, late, claimed."""
    if not call_sid:
        return
    db = get_db()
    sets = {f"calls.$.{k}": v for k, v in fields.items()}
    sets["updated_at"] = datetime.now(timezone.utc)
    await db[COLL].update_one({"_id": ObjectId(job_id), "calls.call_sid": call_sid}, {"$set": sets})


def _outcome(c: dict, job: dict) -> str:
    if c.get("status") == "no_phone":
        return "no_phone"
    if c.get("status") in ("twilio_disabled", "failed"):
        return "failed"
    if c.get("passed"):
        return "passed"
    if job.get("claimed_via") == "phone" and job.get("claimed_by") == c.get("user_id") and c.get("answered_at"):
        return "claimed"
    if c.get("late"):
        return "late"
    if c.get("answered_at"):
        return "answered"
    st = c.get("twilio_status") or c.get("status")
    if st in ("no-answer", "busy", "canceled", "completed"):
        return "no_answer"
    return "ringing"


async def timeline_for_conversation(conversation_id: str) -> dict:
    """Everything a manager wants to see about how a lead was worked: every ring, pass, claim."""
    db = get_db()
    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)}) or {}
    job = await db[COLL].find_one({"conversation_id": conversation_id}, sort=[("created_at", -1)])
    plan = conv.get("routing_plan") or {}
    received = conv.get("created_at")
    if isinstance(received, str):
        try:
            received = datetime.fromisoformat(received)
        except Exception:
            received = None
    if received is not None and received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)

    ids = set()
    if job:
        ids |= {c.get("user_id") for c in job.get("calls", []) if c.get("user_id")}
        ids |= {u for a in job.get("attempts", []) for u in a.get("user_ids", [])}
        if job.get("claimed_by"):
            ids.add(job["claimed_by"])
    if conv.get("claimed_by"):
        ids.add(conv["claimed_by"])
    names = {}
    oids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    if oids:
        async for u in db.users.find({"_id": {"$in": oids}}, {"name": 1, "first_name": 1}):
            names[str(u["_id"])] = u.get("name") or u.get("first_name") or "Rep"

    def iso(v):
        return v.isoformat() if isinstance(v, datetime) else v

    intake = await db.messages.find_one({"conversation_id": conversation_id, "is_intake_text": True}, {"timestamp": 1})
    deferred_intake = await db.lead_deferred_actions.find_one({"conversation_id": conversation_id, "kind": "intake_text"}, {"run_at": 1, "status": 1})
    first_human = await db.messages.find_one(
        {"conversation_id": conversation_id, "sender": "user", "direction": {"$ne": "inbound"}}, {"timestamp": 1}, sort=[("timestamp", 1)]
    )

    out = {
        "conversation_id": conversation_id,
        "received_at": iso(received),
        "is_test": bool(conv.get("is_test")),
        "plan": plan,
        "jessi_on": conv.get("ai_mode") == "auto_reply" and conv.get("ai_enabled") is not False,
        "sms_consent": conv.get("sms_consent"),
        "intake": {
            "sent_at": iso((intake or {}).get("timestamp")),
            "scheduled_for": iso((deferred_intake or {}).get("run_at")) if deferred_intake and deferred_intake.get("status") == "pending" else None,
        },
        "first_human_reply_at": iso((first_human or {}).get("timestamp")),
        "clocks": None,
        "claimed_by": conv.get("claimed_by"),
        "claimed_by_name": names.get(conv.get("claimed_by") or ""),
        "claimed_at": iso(conv.get("claimed_at")),
        "claim_source": conv.get("claim_source"),
        "job": None,
    }
    if job:
        claimed_at = job.get("claimed_at")
        if isinstance(claimed_at, datetime) and claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        # Overnight leads: measure from the first ring, not from the 2 AM form submit
        clock_start = received
        if job.get("was_deferred") or job.get("deferred"):
            first_ring = next((c.get("at") for c in job.get("calls", []) if c.get("at")), None)
            if isinstance(first_ring, datetime):
                clock_start = first_ring if first_ring.tzinfo else first_ring.replace(tzinfo=timezone.utc)
        tts = None
        if claimed_at and clock_start:
            tts = max(0, int((claimed_at - clock_start).total_seconds()))
        out["job"] = {
            "status": job.get("status"),
            "deferred": bool(job.get("deferred")),
            "was_deferred": bool(job.get("was_deferred") or job.get("deferred")),
            "deferred_until": iso(job.get("deferred_until")),
            "released_at": iso(job.get("released_at")),
            "deferred_reasons": job.get("deferred_reasons") or [],
            "handled_reason": job.get("handled_reason"),
            "attempt_index": job.get("attempt_index", 0),
            "attempts": [
                {"n": i + 1, "delay_seconds": a.get("delay_seconds", 0),
                 "reps": [{"user_id": u, "name": names.get(u, "Rep")} for u in a.get("user_ids", [])]}
                for i, a in enumerate(job.get("attempts", []))
            ],
            "calls": [
                {"attempt": c.get("attempt"), "user_id": c.get("user_id"), "name": names.get(c.get("user_id") or "", c.get("rep_name") or "Rep"),
                 "outcome": _outcome(c, job), "at": iso(c.get("at")), "answered_at": iso(c.get("answered_at")),
                 "ended_at": iso(c.get("ended_at")), "error": c.get("error")}
                for c in job.get("calls", [])
            ],
            "claimed_by": job.get("claimed_by"),
            "claimed_by_name": names.get(job.get("claimed_by") or ""),
            "claimed_via": job.get("claimed_via"),
            "claimed_at": iso(claimed_at),
            "time_to_claim_seconds": tts,
            "exhausted_at": iso(job.get("exhausted_at")),
            "next_attempt_at": iso(job.get("next_attempt_at")) if job.get("status") == "active" else None,
        }
    try:
        from services.lead_clocks import clocks_for_conversation
        out["clocks"] = await clocks_for_conversation(db, conversation_id)
    except Exception as e:
        logger.warning(f"[LeadTimeline] clocks failed for {conversation_id}: {e}")
    return out


# ── TwiML ─────────────────────────────────────────────────────────────────────
def _say(text: str) -> str:
    return f'<Say voice="Polly.Joanna">{escape(text)}</Say>'


def twiml(*parts: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + "</Response>"


def twiml_answer(job: dict, action_url: str) -> str:
    src = (job.get("lead") or {}).get("source_label") or job.get("source_name") or "your website"
    kind = "Overnight lead" if job.get("deferred") else "New lead"
    prompt = _say(f"{kind} from {src}. Press 1 to claim this lead.")
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
