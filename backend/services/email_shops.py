"""Email mystery shops: the AI shopper emails the person like a real internet lead, keeps the thread going as they reply
(replies come back through the Resend inbound webhook), and the shop is graded like a call: reply speed by the clock, quality by the AI grader.
Setup: INBOUND_EMAIL_DOMAIN (Resend receiving subdomain, MX record) + the `email.received` webhook at /api/webhooks/resend/inbound; RESEND_API_KEY for sending."""
import asyncio
import logging
import os
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services import i18n
from services import locales as loc
from services import scripts as scr
from services import scorecards as sc
from services import text_shops as tx
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

REPLY_WINDOW_MIN = 24 * 60   # a day of silence: the shopper gives up and the shop is graded on what happened
MAX_HOURS = 72               # an email shop never runs longer than three days
MAX_EXCHANGES = 6
FIRST_REPLY_S = 30 * 60      # the internet-lead benchmark
PACE_S = 2 * 3600
THINK_S = (180, 900)         # a real shopper answers an email minutes later, not seconds
STALE_REPLY_S = 20 * 60
LOCK_S = 120
SPEED_IDS = ("email_first", "email_pace")
SHOP_RE = re.compile(r"shop\+([0-9a-f]{24})@", re.I)

SPEED = {
    "en": {"suffix": " (email)",
           "first": ("Replied to the first email within 30 minutes", "An internet lead emails three businesses at once; the first real reply usually wins. Even 'Got it, details in an hour' beats silence."),
           "pace": ("Kept every reply under 2 hours", "Once the thread is going, do not let it go cold. Away for the afternoon? Say when you will be back.")},
    "nl": {"suffix": " (e-mail)",
           "first": ("Binnen 30 minuten gereageerd op de eerste e-mail", "Een internetlead mailt drie bedrijven tegelijk; wie het eerst echt antwoordt wint meestal. Zelfs 'Ontvangen, je hoort binnen een uur van me' is beter dan stilte."),
           "pace": ("Elke reactie binnen 2 uur", "Laat de mailwissel niet doodbloeden zodra die loopt. Een middag weg? Zeg wanneer je terug bent.")},
}

stats = tx.stats
dur = tx.dur
transcript_turns = tx.transcript_turns


def _now():
    return datetime.now(timezone.utc)


def configured() -> Optional[str]:
    """None when email shops can run, else the reason."""
    if not (os.environ.get("RESEND_API_KEY") or "").strip():
        return "Email shops are not switched on for this server yet: the email key (RESEND_API_KEY) is missing from the deployed environment. Phone and text shops still work."
    if not (os.environ.get("INBOUND_EMAIL_DOMAIN") or "").strip():
        return "Email shops are not switched on for this server yet: the receiving domain (INBOUND_EMAIL_DOMAIN, with Resend's email.received webhook pointed at /api/webhooks/resend/inbound) is missing from the deployed environment. Phone and text shops still work."
    return None


def shop_address(sid: str) -> str:
    return f"shop+{sid}@{(os.environ.get('INBOUND_EMAIL_DOMAIN') or '').strip().lower()}"


def _addr_of(to) -> str:
    return str(to.get("email") or to.get("address") or "") if isinstance(to, dict) else str(to or "")


def session_id_from(to_list: list) -> Optional[str]:
    """The live shop an inbound email belongs to, from its shop+<id>@ address."""
    for to in to_list or []:
        m = SHOP_RE.search(_addr_of(to))
        if m:
            return m.group(1).lower()
    return None


def from_address(s: dict) -> str:
    """The shopper's From: their persona name on the verified sending domain (any local part works on a Resend domain)."""
    name = ((s.get("persona") or {}).get("name") or "A Customer").strip()
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    domain = (os.environ.get("SHOP_EMAIL_DOMAIN") or sender.split("@")[-1]).strip().lower()
    slug = re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".") or "customer"
    return f"{name} <{slug}@{domain}>"


def speed_card(card: dict, locale: Optional[str]) -> dict:
    sp = SPEED.get(loc.language(locale), SPEED["en"])
    crit = [{"id": "email_first", "text": sp["first"][0], "hint": sp["first"][1], "weight": 2, "critical": True},
            {"id": "email_pace", "text": sp["pace"][0], "hint": sp["pace"][1], "weight": 1, "critical": False}]
    return {**card, "name": f"{card.get('name') or 'Scorecard'}{sp['suffix']}", "criteria": crit + [c for c in card.get("criteria") or [] if c.get("id") not in SPEED_IDS]}


def speed_results(s: dict, locale: Optional[str]) -> dict:
    lang = loc.language(locale)
    st = stats(s)
    if st["first_reply_s"] is None:
        ev = i18n.t(lang, "em.noreply.evidence")
        return {"email_first": (False, ev), "email_pace": (False, ev)}
    return {"email_first": (st["first_reply_s"] <= FIRST_REPLY_S, i18n.t(lang, "tx.first_after", d=dur(st["first_reply_s"], lang))),
            "email_pace": (st["max_reply_s"] <= PACE_S, i18n.t(lang, "tx.pace", d=dur(st["max_reply_s"], lang), avg=dur(st["avg_reply_s"], lang)))}


def apply_speed(s: dict, graded: dict):
    fixed = speed_results(s, s.get("locale"))
    for r in graded.get("results") or []:
        if r["criterion_id"] in fixed:
            passed, ev = fixed[r["criterion_id"]]
            r.update({"passed": passed, "ai_passed": passed, "evidence": ev, "confidence": 1.0})


def grader_transcript(s: dict) -> str:
    """The email thread with how long each reply took."""
    lines = [f"SUBJECT: {s.get('subject')}"] if s.get("subject") else []
    for t in s.get("turns") or []:
        if t["role"] == "customer":
            lines.append(f"CUSTOMER: {t['text']}")
        else:
            note = "" if t.get("delay_s") is None else " [replied within a minute]" if t["delay_s"] < 60 else f" [replied after {dur(t['delay_s'])}]"
            lines.append(f"REP:{note} {t['text']}")
    if s.get("end_reason") == "no_reply_mid":
        lines.append(f"(The rep never replied again; the shop closed after {REPLY_WINDOW_MIN // 60} hours of silence.)")
    elif s.get("end_reason") == "expired":
        lines.append(f"(The shop closed after {MAX_HOURS} hours.)")
    return "\n".join(lines)


def _system(script: dict, s: dict) -> str:
    rep_first = (s.get("rep_name") or "the salesperson").split(" ")[0]
    return scr._customer_system(script, s.get("persona") or {}, s.get("store_name") or "the business", rep_first, s.get("curveballs") or [], live=False, direction="inbound",
                                mystery=True, industry=s.get("industry"), department=s.get("department"), locale=s.get("locale"), channel="email", covert=bool(s.get("lead_shop_id")))


async def opening_email(db, s: dict, client: dict) -> dict:
    persona = s.get("persona") or {}
    opening = persona.get("opening_line") or "Hi, I saw something you have listed online and had a question."
    script = await db.scripts.find_one({"_id": ObjectId(s["script_id"])}) if ObjectId.is_valid(str(s.get("script_id") or "")) else None
    user = (f"Write your very first email to {s.get('store_name') or 'the business'}. In phone words your intent was: '{opening}'. Make it read like a real internet lead typed on their phone: "
            f"a short subject line, a greeting, 2 to 4 short sentences with one concrete detail ({persona.get('offering') or persona.get('vehicle') or 'what you want'}, a time, or a question), "
            "sign off with just your first name. JSON only.")
    try:
        data = await scr._llm_json(_system(script or {}, s), user, timeout=45)
        subject = no_em_dash(str(data.get("subject") or "")).strip()[:120]
        body = no_em_dash(str(data.get("say") or "")).strip()[:2000]
    except Exception as e:
        logger.warning(f"[EmailShop] opening email failed for {s.get('_id')}: {e}")
        subject, body = "", ""
    first = (persona.get("name") or "").split(" ")[0]
    return {"subject": subject or f"Question about {persona.get('offering') or persona.get('vehicle') or 'something you have listed'}"[:120],
            "body": body or no_em_dash(f"Hi,\n\n{opening.replace('calling', 'emailing').replace('I am on the phone', 'I am emailing')} Could you get back to me with the details?\n\nThanks,\n{first}")}


async def _send(db, s: dict, subject: str, body: str) -> dict:
    """One email from the shopper to the person; replies route to shop+<id>@INBOUND_EMAIL_DOMAIN."""
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key or not s.get("rep_email"):
        return {"success": False, "error": "Email is not configured" if not key else "No email address for this person"}
    import resend
    resend.api_key = key
    sid = str(s["_id"])
    payload = {"from": s.get("lead_from") or from_address(s), "to": [s["rep_email"]], "reply_to": s.get("lead_reply_to") or shop_address(sid), "subject": subject, "text": body,
               "headers": {"X-Entity-Ref-ID": f"shop-{sid}-{len(s.get('turns') or [])}"}}
    try:
        r = await asyncio.to_thread(resend.Emails.send, payload)
        return {"success": True, "id": (r or {}).get("id")}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


async def start_email_shop(db, call: dict) -> bool:
    """The email twin of place_shop_call: send the shopper's first email and wait for the reply."""
    from services import mystery_shops as ms
    client = await db.shop_clients.find_one({"_id": ms._oid(call["client_id"])})
    now = _now()
    reason = configured() or (None if call.get("rep_email") else "This person has no email address")
    if not client or reason:
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "failed", "outcome": "not_configured", "fail_reason": reason or "Client not found", "updated_at": now}})
        return False
    other = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "mode": "email", "status": {"$in": ["live", "ending"]}, "rep_email": call["rep_email"], "_id": {"$ne": call["_id"]}}, {"_id": 1})
    if other:
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": now + timedelta(hours=6), "updated_at": now}})
        return True
    op = await opening_email(db, call, client)
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "live", "started_at": now, "last_attempt_at": now, "subject": op["subject"], "from_email": from_address(call),
                                                                         "reply_to": shop_address(str(call["_id"])), "expires_at": now + timedelta(hours=MAX_HOURS), "turns": [], "updated_at": now}, "$inc": {"attempts": 1}})
    r = await _send(db, {**call, "turns": []}, op["subject"], op["body"])
    if not r.get("success"):
        logger.warning(f"[EmailShop] could not send opening email for {call['_id']}: {r.get('error')}")
        await ms.record_outcome(db, {**call, "attempts": int(call.get("attempts") or 0) + 1}, "failed", "The email could not be sent")
        return False
    turn = {"role": "customer", "text": op["body"], "subject": op["subject"], "at": _now(), "mood": "neutral", "email_id": r.get("id")}
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$push": {"turns": turn}, "$set": {"updated_at": _now()}})
    return True


async def handle_inbound(db, sid: str, from_email: str, subject: str, body: str, email_id: str = "") -> bool:
    """Resend inbound: an email to shop+<id>@ is the person's reply in that live shop. False = not ours (let the thread router have it)."""
    if not ObjectId.is_valid(sid):
        return False
    s = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "mode": "email", "_id": ObjectId(sid)})
    if not s:
        return False
    if s.get("status") != "live":
        return True  # ours, but the shop is over: swallow it
    if email_id and any(t.get("email_id") == email_id for t in s.get("turns") or []):
        return True
    now = _now()
    text = (body or "").strip()
    if not text:
        text = f"(empty reply) {subject or ''}".strip()
    turns = s.get("turns") or []
    last_cust = next((t for t in reversed(turns) if t["role"] == "customer"), None)
    delay = int((now - tx._utc(last_cust["at"])).total_seconds()) if last_cust and turns and turns[-1]["role"] == "customer" else None
    turn = {"role": "rep", "text": text[:4000], "subject": (subject or "")[:200], "from": from_email, "at": now, "email_id": email_id, **({"delay_s": max(0, delay)} if delay is not None else {})}
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
            logger.warning(f"[EmailShop] delayed reply failed for {sid}: {e}")
    asyncio.create_task(_go())


async def _customer_reply(db, s: dict) -> dict:
    script = await db.scripts.find_one({"_id": ObjectId(s["script_id"])}) if ObjectId.is_valid(str(s.get("script_id") or "")) else None
    turns = s.get("turns") or []
    exchanges = sum(1 for t in turns if t["role"] == "rep")
    started = tx._utc(s.get("started_at")) or _now()
    wrap = exchanges >= MAX_EXCHANGES or (_now() - started) >= timedelta(hours=MAX_HOURS - 6)
    user = (f"EMAIL THREAD SO FAR (newest last):\n{grader_transcript(s)}\n\n(This is exchange {exchanges}. Reply as the customer with your next email, body only, no subject."
            + (" Wrap up now: one short closing email and set ended to true.)" if wrap else ")"))
    try:
        data = await scr._llm_json(_system(script or {}, s), user, timeout=45)
    except Exception as e:
        logger.warning(f"[EmailShop] customer reply failed for {s.get('_id')}: {e}")
        data = {}
    say = no_em_dash(str(data.get("say") or "Sorry, could you clarify that for me?")).strip()[:2000]
    return {"say": say, "ended": bool(data.get("ended")) or wrap, "mood": data.get("mood") if data.get("mood") in ("warm", "neutral", "guarded", "annoyed") else "neutral"}


async def reply_if_due(db, sid: str) -> bool:
    """Answer the person's latest email once, whoever gets here first (delayed task or scheduler sweep)."""
    now = _now()
    s = await db.roleplay_sessions.find_one_and_update(
        {"_id": ObjectId(sid), "mode": "email", "status": "live", "$or": [{"text_lock": None}, {"text_lock": {"$lt": now - timedelta(seconds=LOCK_S)}}]},
        {"$set": {"text_lock": now}})
    if not s:
        return False
    try:
        turns = s.get("turns") or []
        if not turns or turns[-1]["role"] != "rep":
            return False
        data = await _customer_reply(db, s)
        subject = s.get("subject") or ""
        r = await _send(db, s, subject if subject.lower().startswith("re:") else f"Re: {subject}", data["say"])
        if not r.get("success"):
            logger.warning(f"[EmailShop] reply send failed for {sid}: {r.get('error')}")
            return False
        turn = {"role": "customer", "text": data["say"], "at": _now(), "mood": data["mood"], "email_id": r.get("id")}
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$push": {"turns": turn}, "$set": {"updated_at": _now(), **({"status": "ending"} if data["ended"] else {})}})
        if data["ended"]:
            await finish(db, sid, "customer_ended")
        return True
    finally:
        await db.roleplay_sessions.update_one({"_id": ObjectId(sid)}, {"$set": {"text_lock": None}})


async def finish(db, sid: str, reason: str) -> Optional[dict]:
    """Thread over (shopper signed off, person went quiet, admin ended it, time is up): grade once."""
    now = _now()
    claimed = await db.roleplay_sessions.find_one_and_update({"_id": ObjectId(sid), "mode": "email", "status": {"$in": ["live", "ending"]}},
                                                             {"$set": {"status": "grading", "ended_at": now, "end_reason": reason, "updated_at": now}})
    if not claimed:
        return None
    s = await db.roleplay_sessions.find_one({"_id": ObjectId(sid)})
    try:
        if not any(t["role"] == "rep" for t in s.get("turns") or []):
            return await _grade_no_reply(db, s)
        return await scr.grade_session(db, s)
    except Exception as e:
        logger.warning(f"[EmailShop] grading failed for {sid}: {e}")
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "failed", "fail_reason": "Grading failed, the emails are saved", "updated_at": _now()}})
        return None


async def _grade_no_reply(db, s: dict) -> dict:
    """Nobody answered the email lead: that IS the result, so it scores 0 with every criterion missed and lands on the report."""
    from services import mystery_shops as ms
    from zoneinfo import ZoneInfo
    lang = loc.language(s.get("locale"))
    card = speed_card(await ms.scorecard_for(db, s) or {"_id": None, "name": "Email shop", "department": "", "criteria": []}, s.get("locale"))
    ev_text = i18n.t(lang, "em.noreply.evidence")
    results = [{"criterion_id": c["id"], "text": c["text"], "critical": bool(c.get("critical")), "weight": int(c.get("weight") or 1), "passed": False, "ai_passed": None, "evidence": ev_text, "confidence": 1.0, "override": None} for c in card["criteria"]]
    pct, misses = sc.compute_score(results, card["criteria"])
    first = (s.get("rep_name") or "").split(" ")[0] or "The rep"
    client = await db.shop_clients.find_one({"_id": ms._oid(s["client_id"])}) or {}
    tz = ZoneInfo(client.get("timezone") or loc.get(s.get("locale"))["timezone"])
    started = tx._utc(s.get("started_at")) or _now()
    when = started.astimezone(tz).strftime("%H:%M" if lang == "nl" else "%-I:%M %p")
    hours = max(1, round(((tx._utc(s.get("ended_at")) or _now()) - started).total_seconds() / 3600))
    persona = s.get("persona") or {}
    now = _now()
    ev = {"call_sid": f"RP_{s['_id']}", "is_roleplay": False, "is_mystery_shop": True, "roleplay_session_id": str(s["_id"]), "assignment_id": None, "shop_client_id": s.get("client_id"), "shop_target_id": s.get("target_id"),
          "user_id": None, "rep_name": s.get("rep_name") or first, "store_id": None, "contact_id": None, "contact_name": f"{persona.get('name', 'AI customer')} (mystery shopper)", "conversation_id": None, "inbox_id": None,
          "scorecard_id": str(card["_id"]) if card.get("_id") else None, "scorecard_name": card.get("name"), "department": card.get("department") or "", "duration_s": int((now - started).total_seconds()), "direction": "inbound", "call_at": started,
          "results": results, "score_pct": pct if pct is not None else 0, "critical_misses": misses, "summary": i18n.t(lang, "em.noreply.summary", name=first, time=when, hours=hours), "wins": [],
          "coaching": [i18n.t(lang, "em.noreply.coaching")], "customer_sentiment": "negative", "call_type": "mystery_shop", "channel": "email", "text_stats": stats(s), "script_id": s.get("script_id"), "script_title": s.get("script_title"),
          "adherence": {"score_pct": None, "hits": [], "misses": [], "coaching": [], "summary": ""}, "transcript": grader_transcript(s), "model": "clock", "graded_by": "system", "created_at": now, "updated_at": now, "alerts_sent_at": None, "alerted_user_ids": []}
    await db.call_evaluations.update_one({"call_sid": ev["call_sid"]}, {"$set": ev}, upsert=True)
    ev_id = str((await db.call_evaluations.find_one({"call_sid": ev["call_sid"]}, {"_id": 1}))["_id"])
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "completed", "outcome": "no_reply", "fail_reason": f"No reply to the email in {REPLY_WINDOW_MIN // 60} hours", "ended_at": now, "evaluation_id": ev_id, "score_pct": ev["score_pct"], "adherence_pct": None, "updated_at": now}})
    try:
        await ms.after_graded(db, str(s["_id"]))
    except Exception as e:
        logger.warning(f"[EmailShop] follow-up after no-reply failed: {e}")
    return {"evaluation_id": ev_id, "score_pct": ev["score_pct"]}


async def sweep(db) -> int:
    """Scheduler tick: lost delayed replies, people who went quiet, threads older than three days, sign-offs that never got graded."""
    now = _now()
    n = 0
    rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "mode": "email", "status": {"$in": ["live", "ending"]}}).to_list(200)
    for s in rows:
        sid = str(s["_id"])
        turns = s.get("turns") or []
        started = tx._utc(s.get("started_at")) or now
        if not turns:
            if now - started > timedelta(minutes=10):
                await db.roleplay_sessions.update_one({"_id": s["_id"], "status": "live"}, {"$set": {"status": "failed", "outcome": "failed", "fail_reason": "The email could not be sent", "updated_at": now}})
                n += 1
            continue
        last = turns[-1]
        since = (now - tx._utc(last["at"])).total_seconds()
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
