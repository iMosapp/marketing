"""Text (SMS) mystery shops: the AI shopper texts the person from the shop number like a real lead, keeps the thread going
as they reply, and the shop is graded like a call: reply speed is measured by the clock, quality by the same AI grader."""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services import i18n
from services import locales as loc
from services import scripts as scr
from services import scorecards as sc
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

REPLY_WINDOW_MIN = 240    # no answer for 4 hours: the shopper gives up and the shop is graded on what happened
MAX_HOURS = 24            # a text shop never runs longer than a day
MAX_EXCHANGES = 12
FIRST_REPLY_S = 5 * 60    # the lead-response benchmark
PACE_S = 15 * 60
THINK_S = (20, 75)        # a real shopper does not answer two seconds after your text
STALE_REPLY_S = 150       # the scheduler answers for a delayed reply that was lost (process restart)
LOCK_S = 120
SPEED_IDS = ("text_first", "text_pace")

SPEED = {
    "en": {"suffix": " (text)",
           "first": ("Replied to the first text within 5 minutes", "A text lead expects an answer in minutes. Even 'On it, give me one sec' beats silence."),
           "pace": ("Kept every reply under 15 minutes", "Once you are texting, do not leave them hanging. Stepping away? Tell them when you will be back.")},
    "nl": {"suffix": " (sms)",
           "first": ("Binnen 5 minuten gereageerd op het eerste bericht", "Een lead die appt of sms't verwacht binnen minuten antwoord. Zelfs 'Ik kijk het even na, momentje' is beter dan stilte."),
           "pace": ("Elke reactie binnen 15 minuten", "Laat iemand niet hangen zodra het gesprek loopt. Even weg? Zeg wanneer je terug bent.")},
}


def _now():
    return datetime.now(timezone.utc)


def _utc(dt):
    return dt.replace(tzinfo=timezone.utc) if isinstance(dt, datetime) and dt.tzinfo is None else dt


def dur(secs: Optional[int], lang: str = "en") -> str:
    if secs is None:
        return ""
    if secs < 60:
        return i18n.t(lang, "tx.under_min")
    h, m = divmod(int(secs) // 60, 60)
    return f"{h} {i18n.t(lang, 'tx.h')} {m} min" if h else f"{m} min"


def stats(s: dict) -> dict:
    turns = s.get("turns") or []
    delays = [int(t["delay_s"]) for t in turns if t.get("role") == "rep" and t.get("delay_s") is not None]
    waiting = s.get("status") == "live" and turns and turns[-1]["role"] == "customer"
    return {"replies": sum(1 for t in turns if t["role"] == "rep"), "customer_texts": sum(1 for t in turns if t["role"] == "customer"),
            "first_reply_s": delays[0] if delays else None, "avg_reply_s": round(sum(delays) / len(delays)) if delays else None, "max_reply_s": max(delays) if delays else None,
            "waiting_since": _utc(turns[-1]["at"]).isoformat() if waiting else None, "end_reason": s.get("end_reason")}


def speed_card(card: dict, locale: Optional[str]) -> dict:
    """The department's scorecard with the two measured reply-speed criteria in front."""
    sp = SPEED.get(loc.language(locale), SPEED["en"])
    crit = [{"id": "text_first", "text": sp["first"][0], "hint": sp["first"][1], "weight": 2, "critical": True},
            {"id": "text_pace", "text": sp["pace"][0], "hint": sp["pace"][1], "weight": 1, "critical": False}]
    return {**card, "name": f"{card.get('name') or 'Scorecard'}{sp['suffix']}", "criteria": crit + [c for c in card.get("criteria") or [] if c.get("id") not in SPEED_IDS]}


def speed_results(s: dict, locale: Optional[str]) -> dict:
    """criterion_id -> (passed, evidence), decided by the clock, never by the model."""
    lang = loc.language(locale)
    st = stats(s)
    if st["first_reply_s"] is None:
        ev = i18n.t(lang, "tx.noreply.evidence")
        return {"text_first": (False, ev), "text_pace": (False, ev)}
    return {"text_first": (st["first_reply_s"] <= FIRST_REPLY_S, i18n.t(lang, "tx.first_after", d=dur(st["first_reply_s"], lang))),
            "text_pace": (st["max_reply_s"] <= PACE_S, i18n.t(lang, "tx.pace", d=dur(st["max_reply_s"], lang), avg=dur(st["avg_reply_s"], lang)))}


def apply_speed(s: dict, graded: dict):
    fixed = speed_results(s, s.get("locale"))
    for r in graded.get("results") or []:
        if r["criterion_id"] in fixed:
            passed, ev = fixed[r["criterion_id"]]
            r.update({"passed": passed, "ai_passed": passed, "evidence": ev, "confidence": 1.0})


def grader_transcript(s: dict) -> str:
    """The thread with how long each reply took, so the grader (and the shopper) can see the rep going quiet."""
    lines = []
    for t in s.get("turns") or []:
        if t["role"] == "customer":
            lines.append(f"CUSTOMER: {t['text']}")
        else:
            note = ("" if t.get("delay_s") is None else " [replied within a minute]" if t["delay_s"] < 60 else f" [replied after {dur(t['delay_s'])}]")
            lines.append(f"REP:{note} {t['text']}")
    if s.get("end_reason") == "no_reply_mid":
        lines.append(f"(The rep never replied again; the shop closed after {REPLY_WINDOW_MIN // 60} hours of silence.)")
    elif s.get("end_reason") == "expired":
        lines.append(f"(The shop closed after {MAX_HOURS} hours.)")
    return "\n".join(lines)


def transcript_turns(s: dict) -> list:
    return [{**scr._turn_out(t), "delay_s": t.get("delay_s")} for t in s.get("turns") or []]


def _system(script: dict, s: dict) -> str:
    rep_first = (s.get("rep_name") or "the salesperson").split(" ")[0]
    return scr._customer_system(script, s.get("persona") or {}, s.get("store_name") or "the business", rep_first, s.get("curveballs") or [], live=False, direction="inbound",
                                mystery=True, industry=s.get("industry"), department=s.get("department"), locale=s.get("locale"), channel="text")


async def opening_text(db, s: dict, client: dict) -> str:
    persona = s.get("persona") or {}
    opening = persona.get("opening_line") or "Hi, I saw something you have listed online and had a question."
    fallback = opening.replace("calling", "texting").replace("I'm on the phone", "I'm texting")
    script = await db.scripts.find_one({"_id": ObjectId(s["script_id"])}) if ObjectId.is_valid(str(s.get("script_id") or "")) else None
    user = (f"Write your very first text message to {s.get('store_name') or 'the business'}. In phone words your intent was: '{opening}'. Make it read like a real text lead: 1 or 2 short sentences, "
            f"one concrete detail ({persona.get('offering') or persona.get('vehicle') or 'what you want'}, a time, or a question), casual, no letter style, under 240 characters. JSON only.")
    try:
        data = await scr._llm_json(_system(script or {}, s), user, timeout=40)
        say = no_em_dash(str(data.get("say") or "")).strip()[:320]
    except Exception as e:
        logger.warning(f"[TextShop] opening text failed for {s.get('_id')}: {e}")
        say = ""
    return say or no_em_dash(fallback)[:320]


async def start_text_shop(db, call: dict) -> bool:
    """The text twin of place_shop_call: send the shopper's first text from the shop number and wait for the reply."""
    from services import mystery_shops as ms
    from services.twilio_service import send_sms
    client = await db.shop_clients.find_one({"_id": ms._oid(call["client_id"])})
    frm = await ms.from_number(db, client) if client else ""
    now = _now()
    if not client or not frm or not call.get("rep_phone"):
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "failed", "outcome": "not_configured", "fail_reason": "Texting is not set up (no shop number)", "updated_at": now}})
        return False
    # one live thread per phone pair: two shops texting the same person from the same number could not tell the replies apart
    other = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "mode": "text", "status": {"$in": ["live", "ending"]}, "from_number": frm, "rep_phone": call["rep_phone"], "_id": {"$ne": call["_id"]}}, {"_id": 1})
    if other:
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": now + timedelta(hours=3), "updated_at": now}})
        return True
    text = await opening_text(db, call, client)
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "live", "started_at": now, "last_attempt_at": now, "from_number": frm, "expires_at": now + timedelta(hours=MAX_HOURS), "turns": [], "updated_at": now}, "$inc": {"attempts": 1}})
    r = await send_sms(call["rep_phone"], text, from_phone=frm)
    if not r.get("success"):
        logger.warning(f"[TextShop] could not send opening text for {call['_id']}: {r.get('error')}")
        await ms.record_outcome(db, {**call, "attempts": int(call.get("attempts") or 0) + 1, "from_number": frm}, "failed", "The text could not be sent")
        return False
    turn = {"role": "customer", "text": text, "at": _now(), "mood": "neutral", "sid": r.get("sid")}
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$push": {"turns": turn}, "$set": {"updated_at": _now()}})
    return True


async def handle_inbound(db, to_phone: str, from_phone: str, body: str, sid: str = "", media: int = 0) -> bool:
    """Twilio /incoming: a text to a shop number from someone in a live text shop is the rep's reply. False = not ours."""
    s = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "mode": "text", "status": "live", "from_number": to_phone, "rep_phone": from_phone})
    if not s:
        return False
    now = _now()
    text = (body or "").strip() or ("[photo]" if media else "")
    if not text:
        return True
    turns = s.get("turns") or []
    last_cust = next((t for t in reversed(turns) if t["role"] == "customer"), None)
    delay = int((now - _utc(last_cust["at"])).total_seconds()) if last_cust and turns and turns[-1]["role"] == "customer" else None
    turn = {"role": "rep", "text": text[:1600], "at": now, "sid": sid, **({"delay_s": max(0, delay)} if delay is not None else {})}
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$push": {"turns": turn}, "$set": {"updated_at": now, "last_rep_at": now}})
    schedule_reply(str(s["_id"]))
    return True


def schedule_reply(sid: str):
    async def _go():
        await asyncio.sleep(random.randint(*THINK_S))
        try:
            from routers.database import get_db
            await reply_if_due(get_db(), sid)
        except Exception as e:
            logger.warning(f"[TextShop] delayed reply failed for {sid}: {e}")
    asyncio.create_task(_go())


async def _customer_reply(db, s: dict) -> dict:
    script = await db.scripts.find_one({"_id": ObjectId(s["script_id"])}) if ObjectId.is_valid(str(s.get("script_id") or "")) else None
    turns = s.get("turns") or []
    exchanges = sum(1 for t in turns if t["role"] == "rep")
    started = _utc(s.get("started_at")) or _now()
    wrap = exchanges >= MAX_EXCHANGES or (_now() - started) >= timedelta(hours=MAX_HOURS - 1)
    user = (f"TEXT THREAD SO FAR (newest last):\n{grader_transcript(s)}\n\n(This is exchange {exchanges}. Reply as the customer with your next text."
            + (" Wrap up now: one short closing text and set ended to true.)" if wrap else ")"))
    try:
        data = await scr._llm_json(_system(script or {}, s), user, timeout=45)
    except Exception as e:
        logger.warning(f"[TextShop] customer reply failed for {s.get('_id')}: {e}")
        data = {}
    say = no_em_dash(str(data.get("say") or "Sorry, what was that?")).strip()[:320]
    return {"say": say, "ended": bool(data.get("ended")) or wrap, "mood": data.get("mood") if data.get("mood") in ("warm", "neutral", "guarded", "annoyed") else "neutral"}


async def reply_if_due(db, sid: str) -> bool:
    """Answer the rep's latest text once, whoever gets here first (delayed task or scheduler sweep)."""
    from services.twilio_service import send_sms
    now = _now()
    s = await db.roleplay_sessions.find_one_and_update(
        {"_id": ObjectId(sid), "mode": "text", "status": "live", "$or": [{"text_lock": None}, {"text_lock": {"$lt": now - timedelta(seconds=LOCK_S)}}]},
        {"$set": {"text_lock": now}})
    if not s:
        return False
    try:
        turns = s.get("turns") or []
        if not turns or turns[-1]["role"] != "rep":
            return False
        data = await _customer_reply(db, s)
        r = await send_sms(s["rep_phone"], data["say"], from_phone=s.get("from_number"))
        if not r.get("success"):
            logger.warning(f"[TextShop] reply send failed for {sid}: {r.get('error')}")
            return False
        turn = {"role": "customer", "text": data["say"], "at": _now(), "mood": data["mood"], "sid": r.get("sid")}
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$push": {"turns": turn}, "$set": {"updated_at": _now(), **({"status": "ending"} if data["ended"] else {})}})
        if data["ended"]:
            await finish(db, sid, "customer_ended")
        return True
    finally:
        await db.roleplay_sessions.update_one({"_id": ObjectId(sid)}, {"$set": {"text_lock": None}})


async def finish(db, sid: str, reason: str) -> Optional[dict]:
    """Thread over (shopper said goodbye, rep went quiet, admin ended it, day is up): grade once."""
    now = _now()
    claimed = await db.roleplay_sessions.find_one_and_update({"_id": ObjectId(sid), "mode": "text", "status": {"$in": ["live", "ending"]}},
                                                             {"$set": {"status": "grading", "ended_at": now, "end_reason": reason, "updated_at": now}})
    if not claimed:
        return None
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)})
    try:
        if not any(t["role"] == "rep" for t in s.get("turns") or []):
            return await _grade_no_reply(db, s)
        return await scr.grade_session(db, s)
    except Exception as e:
        logger.warning(f"[TextShop] grading failed for {sid}: {e}")
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "failed", "fail_reason": "Grading failed, the texts are saved", "updated_at": _now()}})
        return None


async def _grade_no_reply(db, s: dict) -> dict:
    """Nobody answered the text lead: that IS the result, so it scores 0 with every criterion missed and lands on the report."""
    from services import mystery_shops as ms
    from zoneinfo import ZoneInfo
    lang = loc.language(s.get("locale"))
    card = speed_card(await ms.scorecard_for(db, s) or {"_id": None, "name": "Text shop", "department": "", "criteria": []}, s.get("locale"))
    ev_text = i18n.t(lang, "tx.noreply.evidence")
    results = [{"criterion_id": c["id"], "text": c["text"], "critical": bool(c.get("critical")), "weight": int(c.get("weight") or 1), "passed": False, "ai_passed": None, "evidence": ev_text, "confidence": 1.0, "override": None} for c in card["criteria"]]
    pct, misses = sc.compute_score(results, card["criteria"])
    first = (s.get("rep_name") or "").split(" ")[0] or "The rep"
    client = await db.shop_clients.find_one({"_id": ms._oid(s["client_id"])}) or {}
    tz = ZoneInfo(client.get("timezone") or loc.get(s.get("locale"))["timezone"])
    started = _utc(s.get("started_at")) or _now()
    when = started.astimezone(tz).strftime("%H:%M" if lang == "nl" else "%-I:%M %p")
    hours = max(1, round(((_utc(s.get("ended_at")) or _now()) - started).total_seconds() / 3600))
    persona = s.get("persona") or {}
    now = _now()
    ev = {"call_sid": f"RP_{s['_id']}", "is_roleplay": False, "is_mystery_shop": True, "roleplay_session_id": str(s["_id"]), "assignment_id": None, "shop_client_id": s.get("client_id"), "shop_target_id": s.get("target_id"),
          "user_id": None, "rep_name": s.get("rep_name") or first, "store_id": None, "contact_id": None, "contact_name": f"{persona.get('name', 'AI customer')} (mystery shopper)", "conversation_id": None, "inbox_id": None,
          "scorecard_id": str(card["_id"]) if card.get("_id") else None, "scorecard_name": card.get("name"), "department": card.get("department") or "", "duration_s": int((now - started).total_seconds()), "direction": "inbound", "call_at": started,
          "results": results, "score_pct": pct if pct is not None else 0, "critical_misses": misses, "summary": i18n.t(lang, "tx.noreply.summary", name=first, time=when, hours=hours), "wins": [],
          "coaching": [i18n.t(lang, "tx.noreply.coaching")], "customer_sentiment": "negative", "call_type": "mystery_shop", "channel": "text", "text_stats": stats(s), "script_id": s.get("script_id"), "script_title": s.get("script_title"),
          "adherence": {"score_pct": None, "hits": [], "misses": [], "coaching": [], "summary": ""}, "transcript": scr.transcript_text(s), "model": "clock", "graded_by": "system", "created_at": now, "updated_at": now, "alerts_sent_at": None, "alerted_user_ids": []}
    await db.call_evaluations.update_one({"call_sid": ev["call_sid"]}, {"$set": ev}, upsert=True)
    ev_id = str((await db.call_evaluations.find_one({"call_sid": ev["call_sid"]}, {"_id": 1}))["_id"])
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "completed", "outcome": "no_reply", "fail_reason": ms.OUTCOME_LABEL["no_reply"], "ended_at": now, "evaluation_id": ev_id, "score_pct": ev["score_pct"], "adherence_pct": None, "updated_at": now}})
    try:
        await ms.after_graded(db, str(s["_id"]))
    except Exception as e:
        logger.warning(f"[TextShop] follow-up after no-reply failed: {e}")
    return {"evaluation_id": ev_id, "score_pct": ev["score_pct"]}


async def sweep(db) -> int:
    """Scheduler tick: lost delayed replies, reps who went quiet, threads older than a day, goodbyes that never got graded."""
    now = _now()
    n = 0
    rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "mode": "text", "status": {"$in": ["live", "ending"]}}).to_list(200)
    for s in rows:
        sid = str(s["_id"])
        turns = s.get("turns") or []
        started = _utc(s.get("started_at")) or now
        if not turns:
            if now - started > timedelta(minutes=10):
                await db.roleplay_sessions.update_one({"_id": s["_id"], "status": "live"}, {"$set": {"status": "failed", "outcome": "failed", "fail_reason": "The text could not be sent", "updated_at": now}})
                n += 1
            continue
        last = turns[-1]
        since = (now - _utc(last["at"])).total_seconds()
        if s["status"] == "ending":
            if since >= LOCK_S:
                await finish(db, sid, "customer_ended")
                n += 1
            continue
        if now - started >= timedelta(hours=MAX_HOURS):
            await finish(db, sid, "expired")
            n += 1
        elif last["role"] == "rep":
            if since >= STALE_REPLY_S and await reply_if_due(db, sid):
                n += 1
        elif since >= REPLY_WINDOW_MIN * 60:
            await finish(db, sid, "no_reply" if not any(t["role"] == "rep" for t in turns) else "no_reply_mid")
            n += 1
    return n
