"""Campaign sending reliability (Phase 1). Behind the CAMPAIGN_RELIABILITY_V2 switch, off by default: when it is off the scheduler
behaves exactly as before. The switch is the env var (on / off) or, when the env var is unset, the db.settings row
{key: campaign_reliability_v2, enabled}, so it can be on in one environment's database and off in another.

With it on:
- a paused plan never sends what was already queued (rows wait as `paused` and come back when the plan is switched on again);
  a cancelled or paused enrollment sends nothing;
- a worker that dies mid-send never loses or doubles a touch: stale `processing` rows go back to the queue, or wait as
  unknown_outcome when the send ledger shows the provider may already have it;
- a late touch sends only inside its window (check-ins 3 days, dated occasions the same local day); past it the touch expires
  and the rep gets a task;
- a guard error holds the touch (fail closed); an AI failure retries twice, then holds with a rep task (never a generic text);
- a rate-limited provider refusal retries with backoff under a fresh ledger key (a definite refusal: nothing was delivered)."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

logger = logging.getLogger(__name__)

FLAG = "CAMPAIGN_RELIABILITY_V2"
SETTINGS_KEY = "campaign_reliability_v2"
STALE_MIN = 20
CHECKIN_MAX_LATE = timedelta(days=3)
DATED_TYPES = {"birthday", "anniversary", "sold_date", "holiday"}
DATED_CARDS = {"birthday", "anniversary", "holiday"}
AI_BACKOFF_S = (2, 5)   # two retries after the first attempt
RETRYABLE_CODES = {"20429", "14107"}   # Twilio: too many requests / rate limit (a definite refusal, never delivered)
PROVIDER_BACKOFF = (timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2))
GUARD_HOLD = timedelta(minutes=30)
MAX_GUARD_HOLDS = 3
LIVE_STATES = ("sent", "processing", "unknown_outcome", "pending_user_action")
_sleep = asyncio.sleep   # tests swap this out


async def enabled(db) -> bool:
    env = os.environ.get(FLAG, "").strip().lower()
    if env in ("1", "true", "on", "yes"):
        return True
    if env in ("0", "false", "off", "no"):
        return False
    try:
        row = await db.settings.find_one({"key": SETTINGS_KEY}, {"enabled": 1})
        return bool((row or {}).get("enabled"))
    except Exception as e:
        logger.warning(f"[CampaignV2] switch lookup failed, staying off: {e}")
        return False


def ledger_key(doc: dict) -> str:
    return doc.get("ledger_key") or f"pending:{doc['_id']}"


def _event(now: datetime, state: str, reason: str = "") -> dict:
    return {"$push": {"events": {"$each": [{"at": now, "state": state, "reason": reason}], "$slice": -30}}}


async def mark(db, send_id, now: datetime, state: str, reason: str = "", **sets) -> None:
    """Move one touch to `state` and append the step to its lifecycle log."""
    await db.campaign_pending_sends.update_one({"_id": send_id}, {"$set": {"status": state, **sets}, **_event(now, state, reason)})


async def recover_stale(db, now: datetime) -> int:
    """`processing` rows whose worker stopped: back to the queue when the provider was never called, otherwise never re-sent."""
    n = 0
    async for d in db.campaign_pending_sends.find({"status": "processing", "locked_at": {"$lt": now - timedelta(minutes=STALE_MIN)}}).limit(200):
        led = await db.send_ledger.find_one({"_id": ledger_key(d)}, {"status": 1, "message_sid": 1}) or {}
        st, sets = led.get("status"), {"locked_at": None, "worker_id": None, "recovered_at": now}
        if st == "sent":
            state, why = "sent", "provider accepted it before the worker stopped"
            sets.update(message_sid=led.get("message_sid"), delivery_status="sent", processed_at=now)
        elif st == "failed":
            state, why = "failed", "provider refused it before the worker stopped"
            sets["processed_at"] = now
        elif st:
            state, why = "unknown_outcome", "worker stopped during the provider call; never re-sent"
            sets["processed_at"] = now
        else:
            attempts = int(d.get("attempts") or 0) + 1
            state, why = ("failed", "worker stopped 3 times") if attempts >= 3 else ("pending", "worker stopped before sending; queued again")
            sets["attempts"] = attempts
        r = await db.campaign_pending_sends.update_one({"_id": d["_id"], "status": "processing"}, {"$set": {"status": state, **sets}, **_event(now, state, why)})
        n += r.modified_count
    if n:
        logger.warning(f"[CampaignV2] recovered {n} touch(es) left in processing by a stopped worker")
    return n


def is_dated(send_doc: dict, campaign: dict) -> bool:
    return (campaign.get("date_type") or campaign.get("type") or "") in DATED_TYPES or (send_doc.get("card_type") or "") in DATED_CARDS


OCCASIONS = {"birthday": "their birthday: wish them a happy birthday", "anniversary": "their anniversary: wish them a happy anniversary",
             "sold_date": "the anniversary of the day they bought from me", "holiday": "today's holiday: wish them a happy holiday"}


def occasion(campaign: dict, card_type: str = "") -> str:
    """What a dated plan is celebrating, for the writer ('' for ordinary check-ins)."""
    t = campaign.get("date_type") or campaign.get("type") or ""
    return OCCASIONS.get(t if t in OCCASIONS else (card_type or ""), "")


async def _rep_tz(db, user_id: str) -> ZoneInfo:
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)}, {"timezone": 1}) if ObjectId.is_valid(str(user_id)) else None
        return ZoneInfo((u or {}).get("timezone") or "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


async def lateness(db, send_doc: dict, campaign: dict, now: datetime) -> Optional[str]:
    """None when the touch may still go; else why it is too late. Dated occasions: the same local day only; everything else 3 days."""
    due = send_doc.get("send_at")
    if not isinstance(due, datetime) or due >= now:
        return None
    if is_dated(send_doc, campaign):
        tz = await _rep_tz(db, send_doc.get("user_id"))
        due_day = due.replace(tzinfo=timezone.utc).astimezone(tz).date()
        today = now.replace(tzinfo=timezone.utc).astimezone(tz).date()
        return None if due_day == today else f"dated occasion was {due_day.isoformat()}, today is {today.isoformat()}"
    late = now - due
    return None if late <= CHECKIN_MAX_LATE else f"{late.days} days late (limit {CHECKIN_MAX_LATE.days})"


async def preflight(db, send_doc: dict, campaign: dict, now: datetime) -> Optional[tuple]:
    """Checks made right after a touch is claimed. None = carry on; else (state, reason, extra $set)."""
    cid, eid = str(send_doc.get("campaign_id") or ""), str(send_doc.get("enrollment_id") or "")
    planned = ObjectId.is_valid(cid) and not send_doc.get("broadcast_id") and send_doc.get("type") != "direct_scheduled"
    if planned and not campaign:
        return "skipped", "campaign_missing", {"skip_reason": "campaign_missing", "processed_at": now}
    if planned and campaign.get("active") is False:
        return "paused", "campaign_paused", {"paused_reason": "campaign_paused"}
    if ObjectId.is_valid(eid):
        enr = await db.campaign_enrollments.find_one({"_id": ObjectId(eid)}, {"status": 1})
        st = (enr or {}).get("status")
        if enr is None:
            return "skipped", "enrollment_missing", {"skip_reason": "enrollment_missing", "processed_at": now}
        if st == "paused":
            return "paused", "enrollment_paused", {"paused_reason": "enrollment_paused"}
        if st in ("cancelled", "stopped", "removed"):
            return "skipped", f"enrollment_{st}", {"skip_reason": f"enrollment_{st}", "processed_at": now}
        twin = await db.campaign_pending_sends.find_one({"enrollment_id": eid, "step": send_doc.get("step"), "_id": {"$ne": send_doc["_id"]},
                                                         "$or": [{"status": {"$in": ["sent", "unknown_outcome", "pending_user_action"]}},
                                                                 {"status": "processing", "_id": {"$lt": send_doc["_id"]}}]}, {"_id": 1})
        if twin:
            return "skipped", "duplicate_touch", {"skip_reason": "duplicate_touch", "duplicate_of": str(twin["_id"]), "processed_at": now}
    why = await lateness(db, send_doc, campaign, now)
    if why:
        return "expired", why, {"skip_reason": "too_late", "processed_at": now}
    return None


async def rep_task(db, send_doc: dict, now: datetime, key: str, title: str, description: str) -> None:
    """One task per touch and reason (idempotent), so the rep can reach out personally."""
    if send_doc.get("broadcast_id"):
        return
    idem = f"campaign_{key}_{send_doc['_id']}"
    await db.tasks.update_one({"idempotency_key": idem}, {"$setOnInsert": {
        "user_id": send_doc.get("user_id"), "contact_id": send_doc.get("contact_id"), "contact_name": send_doc.get("contact_name", ""),
        "contact_phone": send_doc.get("contact_phone", ""), "type": "follow_up", "source": f"campaign_{key}", "title": title[:120],
        "description": description[:600], "suggested_message": "", "action_type": "text", "priority": "medium", "priority_order": 2,
        "status": "pending", "completed": False, "due_date": now.replace(tzinfo=timezone.utc), "has_time": False,
        "campaign_id": send_doc.get("campaign_id"), "campaign_name": send_doc.get("campaign_name", ""), "pending_send_id": str(send_doc["_id"]),
        "channel": send_doc.get("channel", "sms"), "created_at": now.replace(tzinfo=timezone.utc),
    }}, upsert=True)


def _who(send_doc: dict) -> str:
    return send_doc.get("contact_name") or "this customer"


async def expire(db, send_doc: dict, now: datetime, why: str, goal: str) -> None:
    await rep_task(db, send_doc, now, "expired", f"Missed campaign touch: {_who(send_doc)}",
                   f"'{send_doc.get('campaign_name', '')}' step {send_doc.get('step')} was due {send_doc.get('send_at'):%b %d} and is too late to "
                   f"send automatically ({why}). Goal: {goal or 'a personal check-in'}. Reach out yourself if it still makes sense.")


async def generate(fn) -> tuple:
    """(text, '') on success, ('', last error) after the first try + 2 retries."""
    err = ""
    for i in range(len(AI_BACKOFF_S) + 1):
        try:
            r = await fn()
            text = (r or {}).get("message", "").strip() if (r or {}).get("success") else ""
            if text:
                return text, ""
            err = "empty or unsuccessful result"
        except Exception as e:
            err = str(getattr(e, "detail", "") or e)[:300]
        if i < len(AI_BACKOFF_S):
            await _sleep(AI_BACKOFF_S[i])
    return "", err


async def hold_for_rep(db, send_doc: dict, now: datetime, reason: str, error: str, goal: str) -> None:
    """Nothing generic goes out: the touch waits as `held` and the rep gets a task to write it."""
    await mark(db, send_doc["_id"], now, "held", reason, held_reason=reason, error=error, processed_at=now)
    await rep_task(db, send_doc, now, "held", f"Write this campaign text: {_who(send_doc)}",
                   f"Jessi could not write '{send_doc.get('campaign_name', '')}' step {send_doc.get('step')} ({reason}). "
                   f"Goal: {goal or 'a personal check-in'}. Nothing was sent.")


def retryable(result: dict) -> bool:
    if result.get("outcome") == "unknown":
        return False
    code, text = str(result.get("error_code") or ""), str(result.get("error") or "").lower()
    return code in RETRYABLE_CODES or "too many requests" in text or "rate limit" in text


async def retry_provider(db, send_doc: dict, now: datetime, error: str) -> bool:
    """A rate-limited refusal goes back to the queue with backoff under a fresh ledger key. False when out of retries."""
    n = int(send_doc.get("provider_retries") or 0)
    if n >= len(PROVIDER_BACKOFF):
        return False
    await mark(db, send_doc["_id"], now, "pending", f"provider rate limit, retry {n + 1}", send_at=now + PROVIDER_BACKOFF[n],
               provider_retries=n + 1, ledger_key=f"pending:{send_doc['_id']}:r{n + 1}", error=error, locked_at=None, worker_id=None)
    return True


async def guard_error(db, send_doc: dict, now: datetime, error: str) -> None:
    n = int(send_doc.get("guard_errors") or 0) + 1
    if n >= MAX_GUARD_HOLDS:
        await mark(db, send_doc["_id"], now, "failed", "safety checks kept failing", error=f"guard_error: {error}"[:300], guard_errors=n, processed_at=now)
    else:
        await mark(db, send_doc["_id"], now, "pending", "safety check failed, held", send_at=now + GUARD_HOLD, held_reason="guard_error",
                   guard_errors=n, locked_at=None, worker_id=None)


async def resume_campaign(db, campaign_id: str) -> int:
    """The plan was switched back on: its paused touches return to the queue (the lateness window still applies)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    r = await db.campaign_pending_sends.update_many({"campaign_id": campaign_id, "status": "paused", "paused_reason": "campaign_paused"},
                                                    {"$set": {"status": "pending"}, "$unset": {"paused_reason": ""}, **_event(now, "pending", "plan switched back on")})
    return r.modified_count
