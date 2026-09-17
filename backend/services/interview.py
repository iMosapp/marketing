"""Onboarding voice interview: Jessi rings the rep (Twilio ConversationRelay), runs a friendly ~10 minute two-way interview,
then turns the transcript into the rep's VA persona, bio and card title. The call records the rep's side only
(recording_track=inbound), which is exactly the single-speaker audio Voice ID needs to enroll them."""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services import industries as ind
from services import locales as loc
from services import voice_id
from services.scripts import FAIL_REASONS, _app_url, _llm_json, _now, _xml, fail_label, failure_key, hangup_twiml
from services.speech import speakable
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "interview_sessions"
MAX_MINUTES = 6
WRAP_AFTER_MINUTES = 4
MAX_REP_TURNS = 24
CALL_TIME_LIMIT_S = (MAX_MINUTES + 3) * 60
MIN_REP_TURNS = 3  # fewer than this and there is nothing worth building from

# Nine neutral topics that fit any industry, plus ONE industry slot (industries.VA[...]["slot"]: what they drive for a dealership, their neighborhood for real estate...)
BASE_TOPICS = [
    ("nickname", "What customers call them and their role"),
    ("years", "How long they have done this work and how they got into it"),
    ("hometown", "Where they grew up and where they live now"),
    ("family", "Family: partner, kids, pets"),
    ("hobbies", "What they do outside work, weekends, hobbies"),
    ("why", "Why they do this work and why customers pick them over anyone else"),
    ("texting", "How they text customers: casual or buttoned-up, emojis or none, short or detailed, how much humor"),
    ("never_say", "Words or things they never say to a customer"),
    ("fun_fact", "A fun fact people are surprised to learn about them"),
]


def slot(industry_key: Optional[str]) -> tuple:
    return ind.va(industry_key)["slot"]


def topics(industry_key: Optional[str]) -> list:
    field, question, _ = slot(industry_key)
    return BASE_TOPICS[:5] + [(field, question)] + BASE_TOPICS[5:]


PERSONA_STR = ["bio", "professional_identity", "hometown", "family_info", "vehicles", "years_experience", "personal_motto", "ideal_customer", "never_say"]
PERSONA_LIST = ["hobbies", "fun_facts", "specialties", "interests"]
PERSONA_ENUM = {"tone": ("casual", "friendly", "professional", "formal"), "humor_level": ("none", "light", "some", "lots"),
                "response_length": ("brief", "balanced", "detailed"), "emoji_usage": ("never", "minimal", "moderate", "frequent")}
LABELS = {"bio": "Your story", "professional_identity": "Title", "hometown": "Hometown", "family_info": "Family", "vehicles": "What you drive", "years_experience": "Years in the business",
          "personal_motto": "Motto", "ideal_customer": "Ideal customer", "never_say": "Never says",
          "hobbies": "Hobbies", "fun_facts": "Fun facts", "specialties": "Specialties", "interests": "Interests", "tone": "Tone", "humor_level": "Humor", "response_length": "Message length", "emoji_usage": "Emojis"}


def greeting(first: str) -> str:
    hi = f"Hey {first}, " if first else "Hey, "
    return (f"{hi}it's Jessi from I'm On Social. This is your interview call, about five minutes, easy questions, nothing graded. "
            "Everything you tell me builds your assistant, your bio and your business card so they sound like you. "
            "Let's start simple: what do your customers usually call you, and what's your role?")


def _first(name: Optional[str]) -> str:
    return (name or "").strip().split(" ")[0] if name else ""


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def serialize(s: Optional[dict]) -> Optional[dict]:
    if not s:
        return None
    started = _aware(s.get("started_at"))
    ended = _aware(s.get("ended_at"))
    elapsed = int(((ended or _now()) - started).total_seconds()) if started and s.get("status") != "dialing" else 0
    slot_field, _, slot_label = slot(s.get("industry"))
    return {"id": str(s["_id"]), "status": s.get("status"), "call_status": s.get("call_status"), "fail_reason": s.get("fail_reason"), "end_reason": s.get("end_reason"),
            "started_at": started.isoformat() if started else None, "ended_at": ended.isoformat() if ended else None, "elapsed_s": max(0, elapsed),
            "turns": [{"role": t["role"], "text": t["text"], "at": t["at"].isoformat() if hasattr(t.get("at"), "isoformat") else t.get("at")} for t in s.get("turns") or []],
            "rep_turns": sum(1 for t in s.get("turns") or [] if t["role"] == "rep"),
            "covered": s.get("covered") or [], "topics_total": len(topics(s.get("industry"))), "extracted": s.get("extracted") or None, "highlights": s.get("highlights") or [],
            "applied_fields": s.get("applied_fields") or [], "applied": bool(s.get("applied")), "dry_run": bool(s.get("dry_run")), "labels": {**LABELS, slot_field: slot_label}, "recording_url": s.get("recording_url"), "recording_seconds": s.get("recording_seconds"),
            "voice": s.get("voice"), "rep_phone": s.get("rep_phone"), "industry": s.get("industry")}


# ---------------------------------------------------------------- placing the call
async def start(db, me: dict, dry_run: bool = False) -> dict:
    """dry_run = Test Lab: the whole call and the write-up happen, nothing touches the profile until the rep taps Save."""
    from routers.twilio_webhooks import normalize_phone
    from services.lead_call_engine import _twilio_client
    rep_phone = normalize_phone(me.get("phone") or "")
    if not rep_phone or len(rep_phone) < 11:
        raise ValueError("Add your cell number under Edit My Info first, that is the phone Jessi calls")
    client = _twilio_client()
    if client is None:
        raise RuntimeError("Calling is not set up on this account yet")
    from_number = me.get("twilio_number") or me.get("mvpline_number") or os.environ.get("TWILIO_PHONE_NUMBER", "")
    if not from_number:
        raise RuntimeError("No number to call you from yet, ask your admin to assign one")
    store = await db.stores.find_one({"_id": ObjectId(me["store_id"])}, {"name": 1, "locale": 1}) if ObjectId.is_valid(str(me.get("store_id") or "")) else None
    industry = (await ind.va_industry_for(db, me))["key"]
    now = _now()
    token = uuid.uuid4().hex
    await hangup_live(db, str(me["_id"]), "restarted")
    doc = {"user_id": str(me["_id"]), "rep_name": me.get("name") or "", "rep_phone": rep_phone, "from_number": from_number, "store_id": me.get("store_id"),
           "store_name": (store or {}).get("name") or "the store", "role_title": me.get("title") or "", "locale": loc.key_of(store), "industry": industry,
           "status": "dialing", "token": token, "turns": [], "covered": [], "dry_run": bool(dry_run), "created_at": now, "updated_at": now}
    res = await db[COLL].insert_one(doc)
    sid = str(res.inserted_id)
    base = f"{_app_url()}/api/interview/call"
    try:
        call = await asyncio.to_thread(
            client.calls.create, to=rep_phone, from_=from_number, url=f"{base}/twiml/{sid}?t={token}", method="POST",
            status_callback=f"{base}/status/{sid}?t={token}", status_callback_event=["answered", "completed"], status_callback_method="POST",
            record=True, recording_track="inbound", recording_channels="mono", recording_status_callback=f"{base}/recording/{sid}?t={token}", recording_status_callback_event=["completed"],
            timeout=25, time_limit=CALL_TIME_LIMIT_S)
    except Exception as e:
        logger.warning(f"[Interview] could not place call: {e}")
        await db[COLL].update_one({"_id": res.inserted_id}, {"$set": {"status": "failed", "fail_reason": "The call could not be placed", "updated_at": _now()}})
        raise RuntimeError("The call could not be placed, try again in a minute")
    await db[COLL].update_one({"_id": res.inserted_id}, {"$set": {"call_sid": call.sid, "call_status": "queued"}})
    return serialize(await db[COLL].find_one({"_id": res.inserted_id}))


async def hangup_live(db, user_id: str, reason: str):
    """Any interview still on the line for this rep gets hung up and marked abandoned (no building)."""
    from services.lead_call_engine import _twilio_client
    rows = await db[COLL].find({"user_id": user_id, "status": {"$in": ["dialing", "live", "ending"]}}).to_list(5)
    client = _twilio_client() if rows else None
    for s in rows:
        if client and s.get("call_sid"):
            try:
                await asyncio.to_thread(client.calls(s["call_sid"]).update, status="completed")
            except Exception as e:
                logger.debug(f"[Interview] hangup failed: {e}")
        await db[COLL].update_one({"_id": s["_id"], "status": {"$in": ["dialing", "live", "ending"]}},
                                  {"$set": {"status": "abandoned", "fail_reason": "Interview restarted" if reason == "restarted" else "Hung up from the app", "ended_at": _now(), "end_reason": reason, "updated_at": _now()}})


async def latest(db, user_id: str) -> Optional[dict]:
    s = await db[COLL].find_one({"user_id": user_id}, sort=[("created_at", -1)])
    return await reconcile_dialing(db, s) if s else None


async def by_token(db, sid: str, token: str) -> Optional[dict]:
    return await db[COLL].find_one({"_id": ObjectId(sid), "token": token})


async def reconcile_dialing(db, s: dict) -> dict:
    """Lost status callbacks must never leave the app spinning: after 30 s of dialing ask Twilio."""
    started = s.get("created_at")
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if s.get("status") != "dialing" or not s.get("call_sid") or not started or (_now() - started).total_seconds() < 30:
        return s
    from services.lead_call_engine import _twilio_client
    client = _twilio_client()
    if client is None:
        return s
    try:
        call = await asyncio.to_thread(client.calls(s["call_sid"]).fetch)
    except Exception as e:
        logger.debug(f"[Interview] reconcile fetch failed: {e}")
        return s
    sets = {"call_status": call.status, "updated_at": _now()}
    if call.status in FAIL_REASONS:
        sets.update(status="failed", fail_reason=fail_label(call.status, s.get("from_number")))
    elif call.status == "in-progress":
        sets["status"] = "live"
    elif call.status == "completed":
        await db[COLL].update_one({"_id": s["_id"]}, {"$set": sets})
        await finalize(db, str(s["_id"]), "reconciled_completed")
        return await db[COLL].find_one({"_id": s["_id"]})
    await db[COLL].update_one({"_id": s["_id"]}, {"$set": sets})
    return {**s, **sets}


# ---------------------------------------------------------------- Twilio side
def twiml(session: dict) -> str:
    sid, token = str(session["_id"]), session["token"]
    base = _app_url()
    ws = base.replace("https://", "wss://").replace("http://", "ws://") + f"/api/interview/relay/{sid}/{token}"
    provider, voice = loc.relay_voice(None, "female")
    hints = ",".join(h for h in ["Jessi", "I'm On Social", session.get("store_name"), session.get("rep_name")] if h)
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response><Connect action="{_xml(base)}/api/interview/call/after/{sid}?t={token}">'
            f'<ConversationRelay url="{_xml(ws)}" welcomeGreeting="{_xml(speakable(greeting(_first(session.get("rep_name")))))}" ttsProvider="{provider}" voice="{_xml(voice)}" language="en-US" '
            f'transcriptionProvider="Deepgram" speechModel="nova-3-general" interruptible="any" interruptSensitivity="medium" ignoreBackchannel="true" hints="{_xml(hints)}" />'
            f'</Connect></Response>')


async def relay_setup(db, sid: str, msg: dict):
    s = await db[COLL].find_one({"_id": ObjectId(sid)}, {"turns": 1, "rep_name": 1})
    if not s:
        return
    now = _now()
    sets = {"status": "live", "call_status": "in-progress", "started_at": now, "updated_at": now}
    if msg.get("callSid"):
        sets["call_sid"] = msg["callSid"]
    update = {"$set": sets}
    if not s.get("turns"):
        update["$push"] = {"turns": {"role": "jessi", "text": greeting(_first(s.get("rep_name"))), "at": now}}
    await db[COLL].update_one({"_id": s["_id"]}, update)


def _system(s: dict, minutes: float, rep_turns: int) -> str:
    first = _first(s.get("rep_name")) or "the rep"
    covered = set(s.get("covered") or [])
    tops = topics(s.get("industry"))
    left = [f"{k}: {label}" for k, label in tops if k not in covered]
    done = [k for k, _ in tops if k in covered]
    out_of_time = minutes >= MAX_MINUTES or rep_turns >= MAX_REP_TURNS or not left
    if out_of_time:
        pace = "TIME IS UP: do not ask anything new. Thank them by name, tell them their assistant and card will be ready in the app in a minute, say goodbye, set ended to true."
    elif minutes >= WRAP_AFTER_MINUTES:
        pace = f"You are {minutes:.0f} minutes in: ask at most one or two more of the most valuable topics left, then wrap up warmly and set ended to true."
    else:
        pace = f"You are {minutes:.0f} minutes in. Keep a relaxed pace, one question at a time, about five minutes total."
    business = ind.va(s.get("industry"))["business"]
    return (f"You are Jessi, the friendly onboarding host at I'm On Social, on a LIVE phone call interviewing {first}"
            f"{', ' + s['role_title'] if s.get('role_title') else ''} at {s.get('store_name') or 'their ' + business}. "
            "Purpose: learn who they really are so we can write their AI assistant's persona, their bio and their business card in THEIR voice. "
            "STYLE: warm, curious, quick. React to what they just said in a few words (never repeat it back in full), then ask ONE question. "
            "1 to 2 short spoken sentences, under 40 words total, contractions, no lists, never say 'great question', never coach, never sell, no em dashes. "
            "If an answer is short, one gentle follow-up at most, then move on. If they ask what this is for, one sentence, then continue. "
            "If they say they need to go or ask to stop, thank them and wrap up immediately with ended true. "
            "Their words come from speech-to-text and may contain mistakes; interpret generously and never comment on them. "
            f"TOPICS STILL TO COVER (pick the most natural next one, weave it into what they just said): {'; '.join(left) if left else 'none'}. "
            f"ALREADY COVERED: {', '.join(done) if done else 'nothing yet'}. {pace} "
            "Return ONLY JSON: {\"say\": \"your spoken words\", \"ended\": true|false, \"covered\": [topic keys the rep's LAST answer fully covered]}")


async def relay_turn(db, sid: str, heard: str) -> dict:
    """Rep spoke -> Jessi reacts and asks the next thing."""
    s = await db[COLL].find_one({"_id": ObjectId(sid)})
    if not s or s.get("status") not in ("live", "ending", "dialing"):
        return {"say": "", "ended": True}
    now = _now()
    heard = heard[:1200]
    turns = list(s.get("turns") or []) + [{"role": "rep", "text": heard, "at": now}]
    rep_turns = sum(1 for t in turns if t["role"] == "rep")
    started = s.get("started_at") or now
    minutes = (now - (started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started)).total_seconds() / 60
    history = "\n".join(f"{'JESSI' if t['role'] == 'jessi' else 'REP'}: {t['text']}" for t in turns[-40:])
    try:
        data = await _llm_json(_system(s, minutes, rep_turns), f"CALL SO FAR:\n{history}\n\n(Reply as Jessi.)", timeout=40)
    except Exception as e:
        logger.warning(f"[Interview] turn failed: {e}")
        data = {}
    say = no_em_dash(str(data.get("say") or "")).strip() or "Sorry, I lost you for a second. Tell me that one more time?"
    ended = bool(data.get("ended")) or minutes >= MAX_MINUTES + 1
    covered = [k for k in (data.get("covered") or []) if k in {t for t, _ in topics(s.get("industry"))}]
    sets = {"updated_at": now}
    if ended:
        sets["status"] = "ending"
    await db[COLL].update_one({"_id": s["_id"]}, {"$push": {"turns": {"$each": [{"role": "rep", "text": heard, "at": now}, {"role": "jessi", "text": say, "at": _now()}]}},
                                                  "$addToSet": {"covered": {"$each": covered}}, "$set": sets})
    return {"say": speakable(say), "ended": ended}


async def relay_interrupt(db, sid: str, spoken: Optional[str]):
    s = await db[COLL].find_one({"_id": ObjectId(sid)}, {"turns": 1})
    turns = (s or {}).get("turns") or []
    if not turns or turns[-1].get("role") != "jessi":
        return
    idx = len(turns) - 1
    sets = {f"turns.{idx}.interrupted": True}
    if spoken and spoken.strip():
        sets[f"turns.{idx}.text"] = spoken.strip()
    await db[COLL].update_one({"_id": s["_id"]}, {"$set": sets})


async def save_recording(db, sid: str, recording_url: str, duration: Optional[str]):
    """The inbound-only track = the rep alone. Keep it (playback) and enroll their Voice ID from it."""
    import httpx
    from utils.image_storage import put_object
    s = await db[COLL].find_one({"_id": ObjectId(sid)}, {"user_id": 1, "status": 1})
    if not s:
        return
    tw_sid, tw_tok = os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", "")
    mp3 = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"
    resp = None
    for attempt in range(3):
        async with httpx.AsyncClient() as client:
            resp = await client.get(mp3, auth=(tw_sid, tw_tok), follow_redirects=True, timeout=60.0)
        if resp.status_code == 200 and resp.content:
            break
        await asyncio.sleep(2 + attempt * 2)
    else:
        logger.warning(f"[Interview] recording fetch failed for {sid}: HTTP {resp.status_code if resp else '?'}")
        return
    path = f"interview/{sid}/rep.mp3"
    stored = (await asyncio.to_thread(put_object, path, resp.content, "audio/mpeg")).get("path") or path
    sets = {"recording_url": f"/api/images/{stored}", "recording_twilio_url": recording_url, "updated_at": _now()}
    try:
        sets["recording_seconds"] = int(float(duration)) if duration else None
    except ValueError:
        pass
    await db[COLL].update_one({"_id": s["_id"]}, {"$set": sets})
    if (sets.get("recording_seconds") or 0) >= 20 or not duration:
        voice = await voice_id.enroll_user(db, s["user_id"], resp.content, "interview", sets.get("recording_seconds"))
    else:
        voice = {**voice_id.summary(None), "status": "too_short", "error": "The call was too short to learn your voice"}
    await db[COLL].update_one({"_id": s["_id"]}, {"$set": {"voice": voice, "updated_at": _now()}})


# ---------------------------------------------------------------- after the call: transcript -> persona
async def finalize(db, sid: str, reason: str) -> Optional[dict]:
    """Call over: build the persona once, whoever gets here first."""
    claimed = await db[COLL].find_one_and_update({"_id": ObjectId(sid), "status": {"$in": ["live", "ending", "dialing"]}},
                                                {"$set": {"status": "building", "ended_at": _now(), "end_reason": reason, "updated_at": _now()}})
    if not claimed:
        return None
    s = await db[COLL].find_one({"_id": ObjectId(sid)})
    if sum(1 for t in s.get("turns", []) if t.get("role") == "rep") < MIN_REP_TURNS:
        await db[COLL].update_one({"_id": s["_id"]}, {"$set": {"status": "abandoned", "fail_reason": "The call ended before we got going. Tap Call me to try again", "updated_at": _now()}})
        return None
    try:
        from services import photo_request
        await photo_request.ask(db, s)
    except Exception as e:
        logger.warning(f"[Interview] photo request text failed: {e}")
    return await build(db, s)


async def build(db, s: dict) -> Optional[dict]:
    try:
        extracted = await extract(s)
        applied = [] if s.get("dry_run") else await apply(db, s["user_id"], extracted)
    except Exception as e:
        logger.warning(f"[Interview] building persona failed for {s['_id']}: {e}")
        await db[COLL].update_one({"_id": s["_id"]}, {"$set": {"status": "failed", "fail_reason": "Jessi could not write your profile from the call. The interview is saved, tap Rebuild", "updated_at": _now()}})
        return None
    await db[COLL].update_one({"_id": s["_id"]}, {"$set": {"status": "completed", "extracted": {k: v for k, v in extracted.items() if k != "highlights"}, "highlights": extracted.get("highlights") or [],
                                                           "applied_fields": applied, "applied": not s.get("dry_run"), "built_at": _now(), "updated_at": _now()}})
    try:
        from routers.push_notifications import send_push_to_user
        body = "Test run done: see what Jessi learned, nothing was saved yet." if s.get("dry_run") else "Jessi turned your interview into your assistant, bio and card. Take a look."
        if not s.get("dry_run") and await db.photo_requests.find_one({"session_id": str(s["_id"]), "status": "open"}, {"_id": 1}):
            body = "Jessi turned your interview into your assistant, bio and card. Reply to her text with a photo to finish the card."
        await send_push_to_user(s["user_id"], "Your VA is ready" if not s.get("dry_run") else "Interview test finished", body, f"/interview/review?session={s['_id']}", "sparkles")
    except Exception as e:
        logger.debug(f"[Interview] push failed: {e}")
    return await db[COLL].find_one({"_id": s["_id"]})


async def apply_session(db, s: dict) -> dict:
    """Test Lab follow-up: the rep liked the write-up and wants it on their profile after all."""
    applied = await apply(db, s["user_id"], {**(s.get("extracted") or {}), "highlights": s.get("highlights") or []})
    await db[COLL].update_one({"_id": s["_id"]}, {"$set": {"applied_fields": applied, "applied": True, "applied_at": _now(), "updated_at": _now()}})
    return await db[COLL].find_one({"_id": s["_id"]})


async def extract(s: dict) -> dict:
    first = _first(s.get("rep_name")) or "the rep"
    slot_field, slot_question, _ = slot(s.get("industry"))
    transcript = "\n".join(f"{'JESSI' if t['role'] == 'jessi' else first.upper()}: {t['text']}" for t in s.get("turns") or [])
    slot_desc = f"vehicles ({slot_question}), " if slot_field == "vehicles" else ""
    interests_desc = f"interests (list; {slot_question})" if slot_field == "interests" else "interests (list, only if they came up)"
    system = (f"You turn an onboarding interview transcript into {first}'s AI assistant profile for a business texting app. Use ONLY what {first} said (Jessi's lines are just questions); "
              "leave a field empty (\"\" or []) when the interview did not cover it, never invent. Write in their own words and rhythm where possible. Speech-to-text mistakes are likely, fix them silently. No em dashes, no cliches like passionate or dedicated. "
              "Return ONLY JSON with exactly these keys: "
              "bio (3 to 5 sentences, FIRST PERSON, warm and specific, for their public business card and landing page: who they are, how long, what they are known for, one personal touch such as family, hobby or hometown, and why customers pick them), "
              f"professional_identity (job title as it would read on a card, e.g. Sales Consultant), hometown, family_info, {slot_desc}years_experience (e.g. 12 years), personal_motto (only if they said one), ideal_customer (only if it came up), "
              "never_say (words or topics they avoid with customers), "
              f"hobbies (list of short strings), fun_facts (list), specialties (list, what they are known for, only if it came up), {interests_desc}, "
              "tone (one of casual, friendly, professional, formal), humor_level (one of none, light, some, lots), response_length (one of brief, balanced, detailed), emoji_usage (one of never, minimal, moderate, frequent), "
              "highlights (5 to 8 short plain sentences of what Jessi learned, written to the rep as 'you', e.g. You have sold trucks in Ogden for 12 years).")
    data = await _llm_json(system, f"INTERVIEW TRANSCRIPT:\n{transcript[:14000]}", timeout=90)
    out = {}
    for k in PERSONA_STR:
        v = data.get(k)
        if isinstance(v, dict):
            v = ", ".join(str(x) for x in v.values() if x)
        out[k] = no_em_dash(", ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")).strip()[:1200 if k == "bio" else 300]
    if slot_field != "vehicles":
        out["vehicles"] = ""
    for k in PERSONA_LIST:
        v = data.get(k)
        items = v if isinstance(v, list) else ([x.strip() for x in str(v).split(",")] if v else [])
        out[k] = [no_em_dash(str(x)).strip()[:80] for x in items if str(x).strip()][:12]
    for k, allowed in PERSONA_ENUM.items():
        v = str(data.get(k) or "").strip().lower()
        out[k] = v if v in allowed else ""
    hl = data.get("highlights")
    out["highlights"] = [no_em_dash(str(x)).strip()[:200] for x in (hl if isinstance(hl, list) else []) if str(x).strip()][:8]
    if len(out["bio"]) < 40:
        raise ValueError("bio missing")
    return out


async def apply(db, user_id: str, extracted: dict) -> list:
    """Fill the persona with everything the interview produced; fields the interview did not cover keep their current value."""
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"persona": 1, "title": 1, "photo_url": 1, "photo_path": 1, "onboarding_complete": 1})
    if not user:
        return []
    sets, applied = {}, []
    for k in PERSONA_STR + PERSONA_LIST + list(PERSONA_ENUM):
        v = extracted.get(k)
        if v:
            sets[f"persona.{k}"] = v
            applied.append(k)
    if extracted.get("professional_identity") and not (user.get("title") or "").strip():
        sets["title"] = extracted["professional_identity"][:80]
        applied.append("title")
    has_photo = bool(user.get("photo_url") or user.get("photo_path"))
    if has_photo and extracted.get("bio") and not user.get("onboarding_complete"):
        sets["onboarding_complete"] = True
    sets["persona_interviewed_at"] = _now()
    await db.users.update_one({"_id": user["_id"]}, {"$set": sets})
    return applied


def failure_from_status(status: str, sip_code=None, from_number=None) -> dict:
    key = failure_key(status, sip_code)
    return {"status": "failed", "fail_reason": fail_label(key, from_number, fix="ask your admin to switch your number to a local one"), "sip_code": sip_code}


def goodbye_twiml() -> str:
    return hangup_twiml("Thanks, that was perfect. Your assistant and your card are being built right now, check the app in a minute.")
