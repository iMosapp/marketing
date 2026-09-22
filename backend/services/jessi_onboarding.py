"""Jessi onboards a brand-new user by text before they ever open the app.

Name + mobile -> Jessi texts from the onboarding number (Forest's for now) -> contact card -> setup interview by phone
(the existing interview: reply CALL or tap the link and Jessi rings them) -> "here's what I learned" -> photo by text ->
single-use activation link -> first login. One document per user in `user_onboarding`: current state, a timestamp per
step, an audit log of events (idempotent on Twilio SIDs), the whole SMS thread and the facts collected so far. Nothing
restarts unless an admin resets it; the scheduler job resumes stragglers and sends the configurable nudges."""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services.scripts import _app_url, _llm_json, _now
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "user_onboarding"
SETTINGS_KEY = "jessi_onboarding"

STATES = ["NOT_STARTED", "JESSI_INTRODUCED", "CONTACT_CARD_SENT", "INTERVIEW_INVITED", "INTERVIEW_STARTED", "INTERVIEW_COMPLETE",
          "PHOTO_REQUESTED", "PHOTO_RECEIVED", "PROFILE_COMPLETE", "ACTIVATION_SENT", "ACCOUNT_ACTIVATED", "FIRST_LOGIN", "FIRST_SUCCESS", "ONBOARDING_COMPLETE"]
ORDER = {s: i for i, s in enumerate(STATES)}
OPEN_STATES = STATES[:ORDER["FIRST_LOGIN"]]

DEFAULT_CFG = {
    "sender_user_id": "",
    "reminders_hours": {"interview": [24, 72, 168], "photo": [24, 72], "activation": [24, 72], "email": [24, 72], "summary": [24]},
    "quiet_start": 21, "quiet_end": 8, "timezone": "America/Denver",
    "default_on_roles": ["super_admin"],
    "activation_ttl_hours": 72,
    "kickoff_gaps_s": [25, 40, 30],
}

CALL_WORDS = {"call", "call me", "ready", "yes", "yep", "yeah", "sure", "ok", "okay", "now", "lets go", "let's go", "call now", "ring me"}
YES_WORDS = {"yep", "yes", "yup", "yeah", "correct", "right", "looks good", "looks right", "perfect", "sounds right", "that's right", "thats right", "all good", "good", "accurate", "love it"}
STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

TEXTS = {
    "intro": "Hey {first}! I'm Jessi with I'm On Social. I'm going to get your account completely set up for you.\n\nFirst thing: save me in your contacts. I'm sending you my contact card now. You can text or call me here any time you need help with I'm On Social.",
    "vcf": "Here's my card. Save me!",
    "explain": "Here's how this works, it only takes a few minutes. I'll ask you about who you are, what you sell, how you talk with your customers and how you want me to talk on your behalf. That's what I use to build your profile and personalize your assistant.\n\nWhen we're done I'll grab your photo and send you the app.",
    "invite": "Ready to build your profile? This is your setup interview: your background, your business, your customers, your style and how you want me to represent you. About 5 to 10 minutes.\n\nReply CALL and I'll ring you at {phone} right now, or tap: {link}",
    "calling": "Calling you now, {first}. Pick up and I'll walk you through it.",
    "calling_failed": "I couldn't place the call just now. Give me a minute and reply CALL again.",
    "cut_off": "Looks like we got cut off, {first}. Reply CALL whenever you have a few minutes and I'll ring you again.",
    "summary": "That was easy. Here's what I learned about you:\n\n{summary}\n\nReply YEP if that sounds right, or tell me what to fix.",
    "summary_fixed": "Fixed. Thanks for keeping me honest, {first}.",
    "photo": "Perfect. I've got what I need to personalize your account.\n\nOne last thing before I open the doors: send me the profile picture you want to use, right here in this text. A clear head-and-shoulders shot works best.",
    "photo_not_image": "That came through as a file, not a picture. Send a photo (jpg or png) and I'll put it on your card.",
    "photo_retry": "That photo didn't come through. Try sending it again, or pick a different one.",
    "photo_done": "Perfect. I've got your photo and your profile is ready.",
    "photo_which": "I got {n} photos. Reply 1, 2 or 3 to tell me which one to use.",
    "email_ask": "One quick thing before I send your login: what email should I put on your account? That's what you'll sign in with.",
    "email_saved": "Got it, {email} it is.",
    "activation": "You're officially set up, {first}.\n\nNow let's get you into I'm On Social. Tap below to activate your account. I already built your profile, so you're not starting from scratch.\n\n{link}",
    "activated": "You're in! I'll show you what to do first once you're logged in.",
    "nudge_interview": "Hey {first}, Jessi here. We still need to finish your quick setup call. When you have a few minutes, reply CALL and I'll ring you.",
    "nudge_summary": "Hey {first}, did the write-up I sent look right? Reply YEP or tell me what to fix and I'll keep going.",
    "nudge_photo": "I've got your setup interview finished, I'm just missing that good-looking profile picture. Send it to me here whenever you're ready.",
    "nudge_email": "Still need an email for your login, {first}. Just text it to me and I'll send your activation link.",
    "nudge_activation": "Your account is sitting here ready for you, {first}. Tap the link and I'll get you the rest of the way in.\n\n{link}",
    "paused": "No problem, I'll stop here. Text me any time and we'll pick up where we left off.",
}

NUDGE_KEY = {"INTERVIEW_INVITED": "interview", "INTERVIEW_COMPLETE": "summary", "PHOTO_REQUESTED": "photo", "PROFILE_COMPLETE": "email", "ACTIVATION_SENT": "activation"}


def _first(name: Optional[str]) -> str:
    return (name or "").strip().split(" ")[0] if name else "there"


def _mask(p: Optional[str]) -> str:
    d = "".join(c for c in (p or "") if c.isdigit())[-10:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (p or "")


def text(key: str, **kw) -> str:
    return no_em_dash(TEXTS[key].format(**kw))


def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if ObjectId.is_valid(str(v or "")) else None


# ---------------------------------------------------------------- config / sender
async def config(db) -> dict:
    doc = await db.settings.find_one({"key": SETTINGS_KEY}) or {}
    cfg = {**DEFAULT_CFG, **{k: v for k, v in doc.items() if k in DEFAULT_CFG}}
    cfg["reminders_hours"] = {**DEFAULT_CFG["reminders_hours"], **(doc.get("reminders_hours") or {})}
    return cfg


async def save_config(db, patch: dict, by: str = "") -> dict:
    allowed = {k: v for k, v in patch.items() if k in DEFAULT_CFG}
    if allowed:
        await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {**allowed, "updated_at": _now(), "updated_by": by}}, upsert=True)
    return await config(db)


async def sender(db, cfg: Optional[dict] = None) -> Optional[dict]:
    """The user whose Twilio number Jessi texts from. Forest's account by default: the oldest super admin with a work number."""
    cfg = cfg or await config(db)
    proj = {"name": 1, "twilio_number": 1, "mvpline_number": 1, "phone": 1, "email": 1, "photo_url": 1}
    u = await db.users.find_one({"_id": _oid(cfg.get("sender_user_id"))}, proj) if _oid(cfg.get("sender_user_id")) else None
    if not u:
        env_id = os.environ.get("ONBOARDING_SENDER_USER_ID", "")
        u = await db.users.find_one({"_id": _oid(env_id)}, proj) if _oid(env_id) else None
    if not u:
        u = await db.users.find_one({"role": "super_admin", "$or": [{"twilio_number": {"$nin": [None, ""]}}, {"mvpline_number": {"$nin": [None, ""]}}]}, proj, sort=[("created_at", 1)])
    if u and not (u.get("twilio_number") or u.get("mvpline_number")):
        return None
    return u


def sender_number(u: Optional[dict]) -> str:
    from services.twilio_service import normalize_phone
    return normalize_phone((u or {}).get("twilio_number") or (u or {}).get("mvpline_number") or "")


async def default_on_for(db, creator: Optional[dict]) -> bool:
    cfg = await config(db)
    return bool(creator) and (creator.get("role") in (cfg.get("default_on_roles") or []))


async def available_for(db, creator: Optional[dict]) -> bool:
    from services.lab import visible
    if (creator or {}).get("role") == "super_admin":
        return True
    return await visible(db, creator, "jessi_onboarding")


def _local_now(cfg: dict) -> datetime:
    try:
        return datetime.now(ZoneInfo(cfg.get("timezone") or "America/Denver"))
    except Exception:
        return datetime.now(timezone.utc)


def can_text_now(cfg: dict) -> bool:
    h = _local_now(cfg).hour
    start, end = int(cfg.get("quiet_start") or 21), int(cfg.get("quiet_end") or 8)
    return not (h >= start or h < end)


# ---------------------------------------------------------------- document helpers
async def get(db, user_id: str) -> Optional[dict]:
    return await db[COLL].find_one({"user_id": str(user_id)})


async def active_for(db, user_id: str) -> Optional[dict]:
    """The onboarding doc if this user is still being onboarded by text (interview and photo hooks check this)."""
    d = await get(db, user_id)
    return d if d and d.get("state") in OPEN_STATES and not d.get("paused") else None


async def by_phones(db, to_phone: str, from_phone: str) -> Optional[dict]:
    """Inbound text on the onboarding number from a phone we are onboarding."""
    return await db[COLL].find_one({"from_number": to_phone, "phone": from_phone, "state": {"$in": STATES[:ORDER["ONBOARDING_COMPLETE"]]}}, sort=[("created_at", -1)])


async def _event(db, doc_id, kind: str, note: str = "", ref: str = ""):
    await db[COLL].update_one({"_id": doc_id}, {"$push": {"events": {"type": kind, "at": _now(), "note": (note or "")[:300], "ref": ref or ""}}, "$set": {"updated_at": _now()}})


async def _seen(db, doc: dict, message_sid: str) -> bool:
    """Idempotency on Twilio SIDs: a retried webhook never advances a user twice."""
    if not message_sid:
        return False
    r = await db[COLL].update_one({"_id": doc["_id"], "seen_sids": {"$ne": message_sid}}, {"$addToSet": {"seen_sids": message_sid}})
    return r.modified_count == 0


async def advance(db, doc: dict, state: str, note: str = "", ref: str = "") -> dict:
    """Move forward only (a step keeps its first timestamp); never goes backwards, use `rewind` for that."""
    cur = doc.get("state") or "NOT_STARTED"
    now = _now()
    sets = {"updated_at": now}
    if ORDER[state] > ORDER.get(cur, -1):
        sets["state"] = state
    if not (doc.get("steps") or {}).get(state):
        sets[f"steps.{state}"] = now
    if state == "ONBOARDING_COMPLETE":
        sets["completed_at"] = now
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": sets, "$push": {"events": {"type": state, "at": now, "note": (note or "")[:300], "ref": ref or ""}}})
    return await db[COLL].find_one({"_id": doc["_id"]})


async def rewind(db, doc: dict, state: str, note: str = "") -> dict:
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"state": state, "updated_at": _now(), "reminders.count": 0}, "$push": {"events": {"type": f"rewind:{state}", "at": _now(), "note": note[:300], "ref": ""}}})
    return await db[COLL].find_one({"_id": doc["_id"]})


async def _say(db, doc: dict, body: str, media: Optional[list] = None, kind: str = "jessi") -> dict:
    """Text the user from the onboarding number and keep the line in the thread."""
    from services.twilio_service import send_sms
    body = no_em_dash(body)
    try:
        r = await send_sms(doc["phone"], body, media_urls=media, from_phone=doc["from_number"], user_id=doc.get("sender_user_id"))
    except Exception as e:
        r = {"success": False, "error": str(e)[:200]}
    line = {"role": "jessi", "text": body, "at": _now(), "ok": bool(r.get("success")), "sid": r.get("message_sid") or r.get("sid"), "error": r.get("error"), "kind": kind}
    if media:
        line["media"] = media
    await db[COLL].update_one({"_id": doc["_id"]}, {"$push": {"thread": line}, "$set": {"updated_at": _now(), "last_outbound_at": _now()}})
    if not r.get("success"):
        logger.warning(f"[JessiOnboarding] text to {doc['phone']} failed: {r.get('error')}")
    return r


# ---------------------------------------------------------------- start + kickoff sequence
async def start(db, user_id: str, created_by: Optional[str] = None) -> dict:
    """Admin created the user with Jessi onboarding on. Idempotent: an existing doc is returned untouched."""
    from services.twilio_service import normalize_phone
    existing = await get(db, user_id)
    if existing:
        return existing
    user = await db.users.find_one({"_id": _oid(user_id)})
    if not user:
        raise ValueError("User not found")
    cfg = await config(db)
    snd = await sender(db, cfg)
    if not snd:
        raise RuntimeError("No onboarding sender number is configured. Assign a work number to the sender account first.")
    phone = normalize_phone(user.get("phone") or "")
    if len(phone) < 11:
        raise ValueError("The new user needs a mobile number for Jessi to text")
    now = _now()
    doc = {"user_id": str(user["_id"]), "first_name": user.get("first_name") or _first(user.get("name")), "name": user.get("name") or "", "phone": phone,
           "sender_user_id": str(snd["_id"]), "from_number": sender_number(snd), "store_id": user.get("store_id"), "organization_id": user.get("organization_id"),
           "role": user.get("role"), "created_by": created_by, "state": "NOT_STARTED", "steps": {"NOT_STARTED": now}, "events": [{"type": "USER_CREATED", "at": now, "note": "", "ref": created_by or ""}],
           "thread": [], "facts": {"email": user.get("email") or ""}, "seen_sids": [], "reminders": {"count": 0, "last_at": None}, "paused": False,
           "call_token": secrets.token_urlsafe(18), "created_at": now, "updated_at": now}
    res = await db[COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    if can_text_now(cfg):
        asyncio.create_task(kickoff(db, str(doc["_id"])))
    else:
        await _event(db, doc["_id"], "KICKOFF_HELD", "quiet hours, the scheduler sends the intro in the morning")
    return doc


def call_link(doc: dict) -> str:
    return f"{_app_url()}/jessi-call/{doc.get('call_token')}"


def vcf_url() -> str:
    return f"{_app_url()}/api/onboarding-jessi/jessi.vcf"


async def kickoff(db, doc_id: str):
    """Intro -> contact card -> how it works -> interview invite, a few seconds apart so it reads like a person, not a wall."""
    cfg = await config(db)
    gaps = list(cfg.get("kickoff_gaps_s") or DEFAULT_CFG["kickoff_gaps_s"])
    for i, step in enumerate(("JESSI_INTRODUCED", "CONTACT_CARD_SENT", "INTERVIEW_INVITED")):
        doc = await db[COLL].find_one({"_id": ObjectId(doc_id)})
        if not doc or doc.get("paused") or ORDER.get(doc.get("state"), 0) >= ORDER[step]:
            continue
        await send_step(db, {**doc, "invite_gap_s": gaps[2] if len(gaps) > 2 else 20}, step)
        if i < 2:
            await asyncio.sleep(gaps[i] if i < len(gaps) else 30)


async def send_step(db, doc: dict, step: str) -> dict:
    """Send the message that belongs to `step` and stamp it. Used by kickoff, the scheduler and the admin Resend button."""
    first = doc.get("first_name") or "there"
    if step == "JESSI_INTRODUCED":
        await _say(db, doc, text("intro", first=first), kind="intro")
        return await advance(db, doc, "JESSI_INTRODUCED")
    if step == "CONTACT_CARD_SENT":
        await _say(db, doc, text("vcf"), media=[vcf_url()], kind="vcf")
        return await advance(db, doc, "CONTACT_CARD_SENT")
    if step == "INTERVIEW_INVITED":
        await _say(db, doc, text("explain"), kind="explain")
        if not doc.get("resend"):
            await asyncio.sleep(doc.get("invite_gap_s", 20))
        await _say(db, doc, text("invite", phone=_mask(doc["phone"]), link=call_link(doc)), kind="invite")
        return await advance(db, doc, "INTERVIEW_INVITED")
    if step == "INTERVIEW_COMPLETE":
        await _say(db, doc, text("summary", summary=doc.get("summary_text") or "You told me about yourself and how you like to work with customers."), kind="summary")
        return doc
    if step == "PHOTO_REQUESTED":
        return await request_photo(db, doc)
    if step == "PROFILE_COMPLETE":
        return await after_profile(db, doc)
    if step == "ACTIVATION_SENT":
        return await send_activation(db, doc)
    return doc


# ---------------------------------------------------------------- the phone interview (existing engine, onboarding number)
async def start_call(db, doc: dict, how: str = "reply") -> dict:
    """Ring the user with the existing interview engine, from the onboarding number, no login needed."""
    from services import interview as iv
    from services.lead_flows import user_store_id
    user = await db.users.find_one({"_id": _oid(doc["user_id"])})
    if not user:
        raise ValueError("User not found")
    me = {**user, "phone": doc["phone"], "twilio_number": doc["from_number"], "mvpline_number": doc["from_number"], "store_id": user_store_id(user)}
    try:
        s = await iv.start(db, me)
    except Exception as e:
        await _event(db, doc["_id"], "CALL_FAILED", str(e)[:200])
        await _say(db, doc, text("calling_failed"), kind="call_failed")
        raise
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"interview_session_id": s.get("id") or s.get("_id"), "call_started_via": how, "updated_at": _now()}})
    await _say(db, doc, text("calling", first=doc.get("first_name") or "there"), kind="calling")
    return await advance(db, doc, "INTERVIEW_STARTED", how, str(s.get("id") or ""))


async def on_interview_built(db, doc: dict, session: dict):
    """Interview transcript turned into the persona: text a 3 to 4 sentence "here's what I learned" and wait for YEP."""
    if session.get("dry_run"):
        return
    ex = session.get("extracted") or {}
    hl = session.get("highlights") or []
    summary = ""
    try:
        data = await _llm_json("You write a 3 to 4 sentence text message. Speak to the person as 'you'. Warm, specific, plain words, no em dashes, no bullet points, no quotes inside the text. Return JSON {\"summary\": \"...\"}.",
                               f"Facts Jessi learned in a phone interview with {doc.get('first_name')}:\n" + "\n".join(f"- {h}" for h in hl[:8]) + f"\nBio draft: {ex.get('bio', '')[:600]}\nTone: {ex.get('tone')}, humor {ex.get('humor_level')}, emojis {ex.get('emoji_usage')}.", timeout=45)
        summary = no_em_dash(str(data.get("summary") or "")).strip()
    except Exception as e:
        logger.debug(f"[JessiOnboarding] summary llm failed: {e}")
    if not summary:
        summary = " ".join(hl[:4]) or (ex.get("bio") or "")[:400]
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"summary_text": summary[:900], "summary_confirmed": False, "interview_session_id": str(session["_id"]), "updated_at": _now()}})
    doc = await db[COLL].find_one({"_id": doc["_id"]})
    await _say(db, doc, text("summary", summary=summary[:900]), kind="summary")
    await advance(db, doc, "INTERVIEW_COMPLETE", "summary sent", str(session["_id"]))


async def on_interview_failed(db, doc: dict, reason: str):
    """Call never got going (no answer, dropped, too short): back to the invite, one nudge, no loop."""
    if doc.get("state") != "INTERVIEW_STARTED":
        return
    await _event(db, doc["_id"], "INTERVIEW_FAILED", reason)
    await _say(db, doc, text("cut_off", first=doc.get("first_name") or "there"), kind="cut_off")
    await rewind(db, doc, "INTERVIEW_INVITED", reason)


async def apply_correction(db, doc: dict, correction: str) -> bool:
    """They corrected the write-up by text: patch the persona with only what they changed."""
    from services import interview as iv
    user = await db.users.find_one({"_id": _oid(doc["user_id"])}, {"persona": 1, "title": 1})
    persona = (user or {}).get("persona") or {}
    keys = iv.PERSONA_STR + iv.PERSONA_LIST + list(iv.PERSONA_ENUM)
    current = {k: persona.get(k) for k in keys if persona.get(k)}
    try:
        data = await _llm_json("A person is correcting the profile an assistant wrote about them from a phone interview. Return JSON with ONLY the profile keys that must change, with their corrected values "
                               f"(same types as the current values: strings, lists of short strings, or one of the allowed enum values {iv.PERSONA_ENUM}). Rewrite the bio (first person, 3 to 5 sentences, no em dashes) only if the correction touches it. "
                               "If the message is not a correction, return {}.",
                               f"CURRENT PROFILE: {current}\nTITLE: {(user or {}).get('title', '')}\nTHEIR MESSAGE: {correction[:800]}", timeout=60)
    except Exception as e:
        logger.warning(f"[JessiOnboarding] correction failed: {e}")
        return False
    sets = {}
    for k, v in (data or {}).items():
        if k not in keys or not v:
            continue
        if k in iv.PERSONA_ENUM and str(v).lower() not in iv.PERSONA_ENUM[k]:
            continue
        sets[f"persona.{k}"] = [str(x)[:80] for x in v][:12] if k in iv.PERSONA_LIST and isinstance(v, list) else no_em_dash(str(v))[:1200 if k == "bio" else 300]
    if sets:
        sets["persona.corrected_by_text_at"] = _now()
        await db.users.update_one({"_id": _oid(doc["user_id"])}, {"$set": sets})
        await _event(db, doc["_id"], "SUMMARY_CORRECTED", ", ".join(k.split(".")[-1] for k in sets if k != "persona.corrected_by_text_at"))
    return bool(sets)


# ---------------------------------------------------------------- photo
async def request_photo(db, doc: dict) -> dict:
    user = await db.users.find_one({"_id": _oid(doc["user_id"])}, {"photo_url": 1, "photo_path": 1})
    if user and (user.get("photo_url") or user.get("photo_path")):
        doc = await advance(db, doc, "PHOTO_REQUESTED", "already had a photo")
        doc = await advance(db, doc, "PHOTO_RECEIVED", "already had a photo")
        return await after_profile(db, doc)
    await _say(db, doc, text("photo"), kind="photo_ask")
    return await advance(db, doc, "PHOTO_REQUESTED")


async def save_photo(db, doc: dict, url: str, ctype: str, message_sid: str) -> bool:
    from services.photo_request import download
    from routers.profile import _save_profile_photo
    try:
        data, ctype = await download(url, ctype)
        saved = await _save_profile_photo(db, doc["user_id"], data, ctype)
    except Exception as e:
        logger.warning(f"[JessiOnboarding] photo save failed for {doc['user_id']}: {getattr(e, 'detail', None) or e}")
        await _event(db, doc["_id"], "PHOTO_FAILED", str(getattr(e, "detail", None) or e)[:200], message_sid)
        await _say(db, doc, text("photo_retry"), kind="photo_retry")
        return False
    await db.photo_requests.update_many({"user_id": doc["user_id"], "status": "open"}, {"$set": {"status": "done", "photo_saved_at": _now(), "photo_url": saved.get("photo_url"), "updated_at": _now()}})
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"photo_url": saved.get("photo_url"), "pending_photos": [], "updated_at": _now()}})
    doc = await advance(db, doc, "PHOTO_RECEIVED", "photo saved", message_sid)
    await _say(db, doc, text("photo_done"), kind="photo_done")
    await after_profile(db, doc)
    return True


async def after_profile(db, doc: dict) -> dict:
    """Profile is built and the photo is in: mark it, then either ask for the login email or send the activation link."""
    doc = await advance(db, doc, "PROFILE_COMPLETE")
    user = await db.users.find_one({"_id": _oid(doc["user_id"])}, {"email": 1, "activation_pending": 1})
    if user and not (user.get("email") or "").strip():
        if not doc.get("awaiting_email"):
            await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"awaiting_email": True, "updated_at": _now()}})
            await _say(db, doc, text("email_ask"), kind="email_ask")
        return await db[COLL].find_one({"_id": doc["_id"]})
    return await send_activation(db, doc)


# ---------------------------------------------------------------- activation
async def activation_link(db, doc: dict) -> str:
    cfg = await config(db)
    token = secrets.token_urlsafe(24)
    now_ts = datetime.utcnow().timestamp()
    await db.password_reset_tokens.update_many({"user_id": doc["user_id"], "purpose": "activate_link", "used": False}, {"$set": {"used": True, "used_at": now_ts, "superseded": True}})
    await db.password_reset_tokens.insert_one({"user_id": doc["user_id"], "purpose": "activate_link", "token": token, "created_at": now_ts,
                                               "expires_at": now_ts + int(cfg.get("activation_ttl_hours") or 72) * 3600, "used": False, "attempts": 0, "source": "jessi_onboarding"})
    full = f"{_app_url()}/auth/activate?token={token}"
    try:
        from routers.short_urls import create_short_url
        r = await create_short_url(original_url=full, link_type="activation", reference_id=doc["user_id"], user_id=doc["user_id"], metadata={"user_name": doc.get("name", "")})
        return r.get("short_url") or full
    except Exception as e:
        logger.debug(f"[JessiOnboarding] short link failed: {e}")
        return full


async def send_activation(db, doc: dict) -> dict:
    user = await db.users.find_one({"_id": _oid(doc["user_id"])}, {"activation_pending": 1, "needs_password_change": 1})
    if user and user.get("activation_pending") is False and not user.get("needs_password_change"):
        return await advance(db, doc, "ACCOUNT_ACTIVATED", "already activated")
    link = await activation_link(db, doc)
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"activation_url": link, "awaiting_email": False, "updated_at": _now()}})
    doc = await db[COLL].find_one({"_id": doc["_id"]})
    await _say(db, doc, text("activation", first=doc.get("first_name") or "there", link=link), kind="activation")
    return await advance(db, doc, "ACTIVATION_SENT", link)


async def on_activated(db, user_id: str):
    doc = await get(db, user_id)
    if not doc or doc.get("state") not in OPEN_STATES:
        return
    # Jessi built the profile, so the first login skips the product tour and lands on her welcome screen instead
    await db.users.update_one({"_id": _oid(user_id)}, {"$set": {"jessi_welcome_pending": True, "onboarding_complete": True, "updated_at": datetime.utcnow()}})
    doc = await advance(db, doc, "ACCOUNT_ACTIVATED")
    await _say(db, doc, text("activated"), kind="activated")


async def on_login(db, user_id: str):
    doc = await get(db, user_id)
    if doc and doc.get("state") == "ACCOUNT_ACTIVATED":
        await advance(db, doc, "FIRST_LOGIN")


FIRST_WINS = {
    "card": {"key": "card", "title": "Send your digital card", "body": "Text your new card to one customer or a friend. That's the fastest way to see what Jessi built for you.", "route": "/quick-send/digitalcard", "icon": "card-outline"},
    "contact": {"key": "contact", "title": "Add your first customer", "body": "Name and mobile is enough. Jessi takes it from there.", "route": "/contact/new", "icon": "person-add-outline"},
}


async def me_summary(db, user: dict) -> dict:
    """What the welcome screen shows a Jessi-onboarded user on first login: the profile she built and the first win."""
    doc = await get(db, str(user["_id"]))
    persona = user.get("persona") or {}
    from utils.image_urls import resolve_user_photo
    photo = resolve_user_photo(user)
    snd = await sender(db)
    return {"onboarded_by_jessi": bool(doc), "state": (doc or {}).get("state"), "welcome_pending": bool(user.get("jessi_welcome_pending")),
            "first_name": user.get("first_name") or _first(user.get("name")), "name": user.get("name"), "title": persona.get("title") or user.get("title") or "",
            "photo_url": photo, "bio": persona.get("bio") or "", "tone": persona.get("tone") or "", "specialties": persona.get("specialties") or [],
            "what_i_sell": persona.get("what_i_sell") or "", "hometown": persona.get("hometown") or "", "summary_text": (doc or {}).get("summary_text") or "",
            "jessi_number": sender_number(snd) if snd else "", "first_win": FIRST_WINS["card"], "other_wins": [FIRST_WINS["contact"]]}


async def first_success(db, user_id: str, which: str = "") -> Optional[dict]:
    """They took the first action from the welcome screen: onboarding is done, the welcome screen never shows again."""
    await db.users.update_one({"_id": _oid(user_id)}, {"$set": {"jessi_welcome_pending": False, "onboarding_complete": True, "updated_at": datetime.utcnow()}})
    doc = await get(db, user_id)
    if not doc:
        return None
    if ORDER.get(doc.get("state"), 0) < ORDER["FIRST_LOGIN"]:
        doc = await advance(db, doc, "FIRST_LOGIN")
    doc = await advance(db, doc, "FIRST_SUCCESS", which or "welcome")
    return await advance(db, doc, "ONBOARDING_COMPLETE")


# ---------------------------------------------------------------- inbound texts
def _classify(body: str, doc: dict) -> str:
    b = (body or "").strip().lower().rstrip("!.")
    state = doc.get("state")
    if b in CALL_WORDS and state in ("INTERVIEW_INVITED", "JESSI_INTRODUCED", "CONTACT_CARD_SENT", "NOT_STARTED"):
        return "call"
    if "call" in b.split() and len(b) <= 40 and ORDER.get(state, 0) <= ORDER["INTERVIEW_STARTED"]:
        return "call"
    if state == "INTERVIEW_COMPLETE" and not doc.get("summary_confirmed") and (b in YES_WORDS or b.startswith(("yep", "yes", "yup", "looks good", "that's right", "sounds right", "correct"))):
        return "confirm"
    if doc.get("pending_photos") and b in ("1", "2", "3"):
        return "pick_photo"
    return "other"


async def _jessi_reply(db, doc: dict, body: str) -> dict:
    """Anything else they say: Jessi answers in context and steers back to the open step. JSON so we can act on intent."""
    state = doc.get("state")
    missing = {"NOT_STARTED": "the setup call", "JESSI_INTRODUCED": "the setup call", "CONTACT_CARD_SENT": "the setup call", "INTERVIEW_INVITED": "the setup call (they reply CALL or tap the link and you ring them)",
               "INTERVIEW_STARTED": "finishing the setup call (you are calling them or just did)", "INTERVIEW_COMPLETE": "confirming the write-up you sent (they reply YEP or tell you what to fix)",
               "PHOTO_REQUESTED": "the profile photo (they text you a picture)", "PROFILE_COMPLETE": "their login email" if doc.get("awaiting_email") else "the activation link you are about to send",
               "ACTIVATION_SENT": "tapping the activation link you sent", "ACCOUNT_ACTIVATED": "logging into the app", "FIRST_LOGIN": "nothing, they are in"}.get(state, "nothing")
    user = await db.users.find_one({"_id": _oid(doc["user_id"])}, {"email": 1, "persona": 1, "title": 1, "photo_url": 1})
    facts = {k: v for k, v in ((user or {}).get("persona") or {}).items() if v and k in ("bio", "hometown", "years_experience", "specialties", "what_i_sell", "tone")}
    thread = "\n".join(f"{'JESSI' if t.get('role') == 'jessi' else 'THEM'}: {t.get('text', '')[:300]}" for t in (doc.get("thread") or [])[-12:])
    system = ("You are Jessi, the virtual assistant at I'm On Social, texting a brand-new user you are personally setting up. You are a person to them, warm, quick, plain words, 1 to 3 short sentences, "
              "no em dashes, no bullet points, at most one emoji and only if it fits. Never call yourself an AI or a bot. Answer whatever they asked (about the app: it helps salespeople keep up with their customers by text, "
              "sends their digital card, asks for reviews, reminds them who to follow up with, and you handle a lot of the texting for them), then steer back to the one open step. "
              "Never ask for anything you already have. If they want to stop or say STOP-like things, be gracious and set intent stop. "
              "Return JSON: {\"reply\": \"what you text back\", \"intent\": one of \"call\" (they want the setup call now), \"confirm\" (they confirm the write-up), \"correct\" (they are correcting the write-up), \"stop\", \"none\", "
              "\"email\": an email address if they gave one else null}")
    ctx = (f"THEIR NAME: {doc.get('first_name')}\nCURRENT STEP THEY STILL NEED: {missing}\nWE ALREADY KNOW: email={(user or {}).get('email') or 'none yet'}, photo={'yes' if (user or {}).get('photo_url') else 'no'}, facts={facts}\n"
           f"RECENT THREAD:\n{thread}\nTHEM (new): {body[:600]}")
    try:
        data = await _llm_json(system, ctx, timeout=45)
    except Exception as e:
        logger.warning(f"[JessiOnboarding] reply llm failed: {e}")
        data = {}
    return {"reply": no_em_dash(str(data.get("reply") or "")).strip(), "intent": str(data.get("intent") or "none").lower(), "email": (data.get("email") or None)}


async def _save_email(db, doc: dict, email: str) -> bool:
    email = email.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        return False
    taken = await db.users.find_one({"email": email, "_id": {"$ne": _oid(doc["user_id"])}}, {"_id": 1})
    if taken:
        await _say(db, doc, f"Hmm, {email} is already on another account. Got a different email I can use?", kind="email_taken")
        return True
    await db.users.update_one({"_id": _oid(doc["user_id"])}, {"$set": {"email": email, "updated_at": datetime.utcnow()}})
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"facts.email": email, "updated_at": _now()}})
    await _event(db, doc["_id"], "EMAIL_SAVED", email)
    await _say(db, doc, text("email_saved", email=email), kind="email_saved")
    return True


async def handle_inbound(db, to_phone: str, from_phone: str, body: str, media_urls: list, media_types: list, message_sid: str = "") -> bool:
    """True = this text was part of someone's onboarding (swallowed, never becomes a contact or a customer thread)."""
    doc = await by_phones(db, to_phone, from_phone)
    if not doc:
        return False
    if (body or "").strip().upper() in STOP_WORDS:
        await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"paused": True, "paused_at": _now(), "updated_at": _now()}})
        await _event(db, doc["_id"], "STOPPED", body, message_sid)
        return False  # let Twilio's own STOP handling run
    if await _seen(db, doc, message_sid):
        return True
    images = [(u, t) for u, t in zip(media_urls or [], media_types or []) if u and (t or "").lower().startswith("image/")]
    await db[COLL].update_one({"_id": doc["_id"]}, {"$push": {"thread": {"role": "user", "text": (body or "")[:1000], "at": _now(), "sid": message_sid, "media": [u for u, _ in images]}},
                                                    "$set": {"updated_at": _now(), "last_inbound_at": _now(), "paused": False, "reminders.count": 0}})
    doc = await db[COLL].find_one({"_id": doc["_id"]})
    first = doc.get("first_name") or "there"

    # Pictures: the profile photo, whatever step they are on (people send it early)
    if images:
        if ORDER.get(doc.get("state"), 0) >= ORDER["PHOTO_RECEIVED"] and doc.get("photo_url"):
            await _say(db, doc, "Got it. I already have a photo on your card, so I'll keep the one we've got unless you tell me to swap it.", kind="photo_extra")
            return True
        if len(images) > 1:
            await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"pending_photos": [list(x) for x in images[:3]], "updated_at": _now()}})
            await _say(db, doc, text("photo_which", n=min(3, len(images))), kind="photo_which")
            return True
        await save_photo(db, doc, images[0][0], images[0][1], message_sid)
        return True
    if media_urls and not images and doc.get("state") == "PHOTO_REQUESTED":
        await _say(db, doc, text("photo_not_image"), kind="photo_not_image")
        return True

    kind = _classify(body, doc)
    if kind == "pick_photo":
        idx = int(body.strip()) - 1
        pend = doc.get("pending_photos") or []
        if idx < len(pend):
            await save_photo(db, doc, pend[idx][0], pend[idx][1], message_sid)
        return True
    if kind == "call":
        try:
            await start_call(db, doc, "reply")
        except Exception:
            pass
        return True
    if kind == "confirm":
        await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"summary_confirmed": True, "summary_confirmed_at": _now(), "updated_at": _now()}})
        await _event(db, doc["_id"], "SUMMARY_CONFIRMED", body, message_sid)
        await request_photo(db, await db[COLL].find_one({"_id": doc["_id"]}))
        return True

    # An email in the text: save it (needed for login), keep going
    m = EMAIL_RE.search(body or "")
    user = await db.users.find_one({"_id": _oid(doc["user_id"])}, {"email": 1})
    if m and not ((user or {}).get("email") or "").strip():
        if await _save_email(db, doc, m.group(0)):
            doc = await db[COLL].find_one({"_id": doc["_id"]})
            if doc.get("awaiting_email") and doc.get("state") == "PROFILE_COMPLETE":
                await send_activation(db, doc)
            return True

    # Correction of the write-up
    if doc.get("state") == "INTERVIEW_COMPLETE" and not doc.get("summary_confirmed") and len((body or "").strip()) > 3:
        if await apply_correction(db, doc, body):
            await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"summary_confirmed": True, "summary_confirmed_at": _now(), "updated_at": _now()}})
            await _say(db, doc, text("summary_fixed", first=first), kind="summary_fixed")
            await request_photo(db, await db[COLL].find_one({"_id": doc["_id"]}))
            return True

    out = await _jessi_reply(db, doc, body or "")
    if out.get("email") and not ((user or {}).get("email") or "").strip():
        await _save_email(db, doc, out["email"])
        doc = await db[COLL].find_one({"_id": doc["_id"]})
    if out["intent"] == "stop":
        await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"paused": True, "paused_at": _now(), "updated_at": _now()}})
        await _say(db, doc, out["reply"] or text("paused"), kind="paused")
        return True
    if out["reply"]:
        await _say(db, doc, out["reply"], kind="chat")
    if out["intent"] == "call" and ORDER.get(doc.get("state"), 0) <= ORDER["INTERVIEW_STARTED"]:
        try:
            await start_call(db, doc, "reply")
        except Exception:
            pass
    elif out["intent"] == "confirm" and doc.get("state") == "INTERVIEW_COMPLETE":
        await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"summary_confirmed": True, "summary_confirmed_at": _now(), "updated_at": _now()}})
        await request_photo(db, await db[COLL].find_one({"_id": doc["_id"]}))
    elif doc.get("awaiting_email") and doc.get("state") == "PROFILE_COMPLETE" and ((await db.users.find_one({"_id": _oid(doc["user_id"])}, {"email": 1})) or {}).get("email"):
        await send_activation(db, doc)
    return True


# ---------------------------------------------------------------- scheduler: stragglers, failed calls, nudges
async def run_job(db) -> dict:
    cfg = await config(db)
    out = {"kickoff": 0, "failed_calls": 0, "nudges": 0}
    now = _now()
    async for doc in db[COLL].find({"state": {"$in": OPEN_STATES}, "paused": {"$ne": True}}):
        try:
            state = doc.get("state")
            # 1. Intro sequence that never went out (quiet hours, restart mid-sequence)
            if ORDER[state] < ORDER["INTERVIEW_INVITED"] and can_text_now(cfg):
                last = doc.get("last_outbound_at") or doc.get("created_at")
                if not last or (now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))).total_seconds() > 300:
                    nxt = STATES[ORDER[state] + 1]
                    await send_step(db, doc, nxt)
                    out["kickoff"] += 1
                continue
            # 2. A call that failed or never connected
            if state == "INTERVIEW_STARTED":
                s = await db.interview_sessions.find_one({"_id": _oid(doc.get("interview_session_id"))}, {"status": 1, "updated_at": 1}) if _oid(doc.get("interview_session_id")) else None
                st = (s or {}).get("status")
                stamped = (doc.get("steps") or {}).get("INTERVIEW_STARTED") or now
                age = (now - (stamped if stamped.tzinfo else stamped.replace(tzinfo=timezone.utc))).total_seconds()
                if st in ("failed", "abandoned") or (st in (None, "dialing") and age > 900):
                    if can_text_now(cfg):
                        await on_interview_failed(db, doc, st or "no session")
                        out["failed_calls"] += 1
                elif st == "completed" and age > 300 and not (doc.get("steps") or {}).get("INTERVIEW_COMPLETE"):
                    await on_interview_built(db, doc, await db.interview_sessions.find_one({"_id": s["_id"]}))
                continue
            # 3. Nudges, configurable hours after the step, stop the moment the step completes
            key = NUDGE_KEY.get(state)
            if not key or not can_text_now(cfg):
                continue
            if state == "PROFILE_COMPLETE" and not doc.get("awaiting_email"):
                continue
            hours = list((cfg.get("reminders_hours") or {}).get(key) or [])
            n = int((doc.get("reminders") or {}).get("count") or 0)
            if n >= len(hours):
                continue
            base = doc.get("last_inbound_at") or (doc.get("steps") or {}).get(state) or doc.get("updated_at")
            base = base if base.tzinfo else base.replace(tzinfo=timezone.utc)
            last_n = (doc.get("reminders") or {}).get("last_at")
            since = max(base, last_n if last_n and last_n.tzinfo else (last_n.replace(tzinfo=timezone.utc) if last_n else base))
            if (now - since).total_seconds() < hours[n] * 3600:
                continue
            first = doc.get("first_name") or "there"
            body = {"interview": text("nudge_interview", first=first), "summary": text("nudge_summary", first=first), "photo": text("nudge_photo"),
                    "email": text("nudge_email", first=first), "activation": text("nudge_activation", first=first, link=doc.get("activation_url") or await activation_link(db, doc))}[key]
            await _say(db, doc, body, kind=f"nudge_{key}")
            await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"reminders.count": n + 1, "reminders.last_at": now, "updated_at": now}, "$push": {"events": {"type": "NUDGE", "at": now, "note": f"{key} #{n + 1}", "ref": ""}}})
            out["nudges"] += 1
        except Exception as e:
            logger.warning(f"[JessiOnboarding] job failed for {doc.get('user_id')}: {e}")
    return out


# ---------------------------------------------------------------- admin
def waiting_on(doc: dict) -> str:
    """Who the next move belongs to: 'them' (the new user), 'jessi' (a send or a call in flight), 'done', or 'paused'."""
    if doc.get("paused"):
        return "paused"
    s = doc.get("state")
    if s in ("FIRST_SUCCESS", "ONBOARDING_COMPLETE"):
        return "done"
    if s in ("NOT_STARTED", "JESSI_INTRODUCED", "CONTACT_CARD_SENT", "INTERVIEW_STARTED", "PHOTO_RECEIVED") or (s == "PROFILE_COMPLETE" and not doc.get("awaiting_email")):
        return "jessi"
    return "them"


def serialize(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    iso = lambda v: v.isoformat() if hasattr(v, "isoformat") else v
    steps = {k: iso(v) for k, v in (doc.get("steps") or {}).items()}
    nxt = {"NOT_STARTED": "Jessi sends the intro", "JESSI_INTRODUCED": "Contact card", "CONTACT_CARD_SENT": "Interview invite", "INTERVIEW_INVITED": "They reply CALL or tap the link",
           "INTERVIEW_STARTED": "Finish the call", "INTERVIEW_COMPLETE": "They confirm the write-up", "PHOTO_REQUESTED": "They text a photo", "PHOTO_RECEIVED": "Profile wrap-up",
           "PROFILE_COMPLETE": "Login email" if doc.get("awaiting_email") else "Activation link", "ACTIVATION_SENT": "They tap the link and set a password", "ACCOUNT_ACTIVATED": "First login",
           "FIRST_LOGIN": "First win in the app", "FIRST_SUCCESS": "Done", "ONBOARDING_COMPLETE": "Done"}.get(doc.get("state"), "")
    return {"id": str(doc["_id"]), "user_id": doc.get("user_id"), "name": doc.get("name"), "first_name": doc.get("first_name"), "phone": doc.get("phone"), "from_number": doc.get("from_number"),
            "sender_user_id": doc.get("sender_user_id"), "store_id": doc.get("store_id"), "organization_id": doc.get("organization_id"), "role": doc.get("role"),
            "state": doc.get("state"), "state_index": ORDER.get(doc.get("state"), 0), "states": STATES, "next": nxt, "waiting_on": waiting_on(doc), "paused": bool(doc.get("paused")), "steps": steps,
            "events": [{**e, "at": iso(e.get("at"))} for e in (doc.get("events") or [])[-60:]],
            "thread": [{**t, "at": iso(t.get("at"))} for t in (doc.get("thread") or [])[-80:]],
            "facts": doc.get("facts") or {}, "summary_text": doc.get("summary_text"), "summary_confirmed": bool(doc.get("summary_confirmed")), "awaiting_email": bool(doc.get("awaiting_email")),
            "interview_session_id": doc.get("interview_session_id"), "photo_url": doc.get("photo_url"), "activation_url": doc.get("activation_url"), "call_link": call_link(doc),
            "reminders": {"count": (doc.get("reminders") or {}).get("count", 0), "last_at": iso((doc.get("reminders") or {}).get("last_at"))},
            "last_inbound_at": iso(doc.get("last_inbound_at")), "last_outbound_at": iso(doc.get("last_outbound_at")),
            "created_at": iso(doc.get("created_at")), "updated_at": iso(doc.get("updated_at")), "completed_at": iso(doc.get("completed_at"))}


async def reset(db, user_id: str, by: str) -> Optional[dict]:
    """Admin only: wipe the state and start over from the intro."""
    doc = await get(db, user_id)
    if not doc:
        return None
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"state": "NOT_STARTED", "steps": {"NOT_STARTED": _now()}, "paused": False, "reminders": {"count": 0, "last_at": None}, "summary_confirmed": False,
                                                            "awaiting_email": False, "pending_photos": [], "seen_sids": [], "call_token": secrets.token_urlsafe(18), "updated_at": _now()},
                                                    "$push": {"events": {"type": "RESET", "at": _now(), "note": "", "ref": by}}})
    asyncio.create_task(kickoff(db, str(doc["_id"])))
    return await get(db, user_id)


async def mark_step(db, user_id: str, state: str, by: str) -> Optional[dict]:
    doc = await get(db, user_id)
    if not doc or state not in ORDER:
        return None
    return await advance(db, doc, state, f"marked by admin {by}")


def jessi_vcard(number: str, photo_url: str = "") -> str:
    tel = number or ""
    lines = ["BEGIN:VCARD", "VERSION:3.0", "N:;Jessi;;;", "FN:Jessi (I'm On Social)", "ORG:I'm On Social", "TITLE:Your setup assistant",
             f"TEL;TYPE=CELL,VOICE:{tel}", f"URL:{_app_url()}", "NOTE:Text or call me any time you need help with I'm On Social."]
    if photo_url:
        lines.append(f"PHOTO;VALUE=URI:{photo_url}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"
