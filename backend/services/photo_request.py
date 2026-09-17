"""After the interview call: Jessi texts the rep from their own work number, says the VA is being built and asks for a photo.
When they reply with a picture it goes through the normal profile-photo pipeline and lands on their business card."""
import logging
import os
from datetime import timedelta
from typing import Optional

import httpx
from bson import ObjectId

from services import locales as loc
from services.scripts import _now

logger = logging.getLogger(__name__)

COLL = "photo_requests"
OPEN_HOURS = 48
MAX_NUDGES = 2
MAX_BYTES = 10 * 1024 * 1024
STOP_WORDS = ("STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "UNSTOP", "START", "SUBSCRIBE")

TEXTS = {
    "en": {
        "ask": "Hey {first}, it's Jessi. Your assistant, bio and card are being built right now. One more thing: reply to this text with a photo of yourself (a clear head-and-shoulders shot works best) and I'll put it on your business card.",
        "ask_replace": "Hey {first}, it's Jessi. Your assistant, bio and card are being built right now. Want a fresh photo on your card? Reply to this text with one (a clear head-and-shoulders shot works best) and I'll swap it in.",
        "nudge": "Just the photo is enough. Attach it to a reply and hit send, I'll do the rest.",
        "not_image": "That came through as a file, not a picture. Send a photo (jpg or png) and I'll put it on your card.",
        "retry": "That photo didn't come through. Try sending it again, or pick a different one.",
        "done": "Got it, {first}. That's on your card now: {link}",
        "done_nolink": "Got it, {first}. That's on your card now.",
    },
    "nl": {
        "ask": "Hoi {first}, Jessi hier. Je assistent, bio en kaartje worden nu gebouwd. Nog een ding: stuur als antwoord op dit bericht een foto van jezelf (hoofd en schouders, scherp) en ik zet hem op je visitekaartje.",
        "ask_replace": "Hoi {first}, Jessi hier. Je assistent, bio en kaartje worden nu gebouwd. Wil je een nieuwe foto op je kaartje? Stuur er een als antwoord op dit bericht (hoofd en schouders, scherp) en ik wissel hem om.",
        "nudge": "Alleen de foto is genoeg. Voeg hem toe aan je antwoord en verstuur, de rest doe ik.",
        "not_image": "Dat kwam binnen als bestand, niet als foto. Stuur een foto (jpg of png) en ik zet hem op je kaartje.",
        "retry": "Die foto kwam niet goed door. Probeer het nog eens, of kies een andere.",
        "done": "Gelukt, {first}. Hij staat nu op je kaartje: {link}",
        "done_nolink": "Gelukt, {first}. Hij staat nu op je kaartje.",
    },
}


def _first(name: Optional[str]) -> str:
    return (name or "").strip().split(" ")[0] if name else "there"


def text(lang: str, key: str, **kw) -> str:
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"][key]).format(**kw)


async def ask(db, session: dict) -> Optional[dict]:
    """Interview just ended: open a 48 h photo request and send the text. Never raises."""
    from services.twilio_service import normalize_phone, send_sms
    user = await db.users.find_one({"_id": ObjectId(session["user_id"])}, {"name": 1, "phone": 1, "photo_url": 1, "photo_path": 1, "twilio_number": 1, "mvpline_number": 1})
    if not user:
        return None
    to = normalize_phone(user.get("phone") or session.get("rep_phone") or "")
    frm = session.get("from_number") or user.get("twilio_number") or user.get("mvpline_number") or os.environ.get("TWILIO_PHONE_NUMBER", "")
    if len(to) < 11 or not frm:
        return None
    had_photo = bool(user.get("photo_url") or user.get("photo_path"))
    lang = loc.language(session.get("locale"))
    now = _now()
    await db[COLL].update_many({"user_id": session["user_id"], "status": "open"}, {"$set": {"status": "superseded", "updated_at": now}})
    doc = {"user_id": session["user_id"], "session_id": str(session["_id"]), "to_phone": to, "from_number": normalize_phone(frm), "had_photo": had_photo, "lang": lang, "dry_run": bool(session.get("dry_run")),
           "status": "open", "nudges": 0, "failures": 0, "replies": [], "asked_at": now, "expires_at": now + timedelta(hours=OPEN_HOURS), "created_at": now, "updated_at": now}
    body = text(lang, "ask_replace" if had_photo else "ask", first=_first(user.get("name")))
    try:
        r = await send_sms(to, body, from_phone=frm)
    except Exception as e:
        r = {"success": False, "error": str(e)[:200]}
    doc["sms"] = {"ok": bool(r.get("success")), "sid": r.get("message_sid") or r.get("sid"), "error": r.get("error"), "body": body}
    res = await db[COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    logger.info(f"[PhotoRequest] asked {session['user_id']} at {to} from {frm} (sent={doc['sms']['ok']})")
    return doc


async def open_request(db, to_phone: str, from_phone: str) -> Optional[dict]:
    """The rep (from_phone) is texting the work number that asked them (to_phone)."""
    return await db[COLL].find_one({"status": "open", "from_number": to_phone, "to_phone": from_phone, "expires_at": {"$gt": _now()}}, sort=[("asked_at", -1)])


async def download(url: str, content_type: str = "") -> tuple:
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", "")
    auth = (sid, tok) if sid and tok and "twilio.com" in url else None
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, auth=auth)
    if resp.status_code != 200:
        raise ValueError(f"media fetch {resp.status_code}")
    if len(resp.content) > MAX_BYTES:
        raise ValueError("media too large")
    return resp.content, (resp.headers.get("content-type") or content_type or "image/jpeg").split(";")[0].strip()


async def card_link(db, user_id: str) -> str:
    try:
        from routers.short_urls import create_short_url, get_short_url_base
        full = f"{get_short_url_base()}/p/{user_id}"
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})
        r = await create_short_url(original_url=full, link_type="business_card", reference_id=user_id, user_id=user_id, metadata={"user_name": (user or {}).get("name", "")})
        return r.get("short_url") or full
    except Exception as e:
        logger.debug(f"[PhotoRequest] card link failed: {e}")
        return ""


async def _reply(db, req: dict, body: str) -> dict:
    from services.twilio_service import send_sms
    try:
        r = await send_sms(req["to_phone"], body, from_phone=req["from_number"])
    except Exception as e:
        r = {"success": False, "error": str(e)[:200]}
    await db[COLL].update_one({"_id": req["_id"]}, {"$push": {"replies": {"at": _now(), "body": body, "ok": bool(r.get("success")), "error": r.get("error")}}, "$set": {"updated_at": _now()}})
    return r


async def handle_inbound(db, to_phone: str, from_phone: str, body: str, media_urls: list, media_types: list, message_sid: str = "") -> bool:
    """True = this text was the rep answering the photo request (swallowed, never becomes a contact/thread)."""
    if (body or "").strip().upper() in STOP_WORDS:
        return False
    req = await open_request(db, to_phone, from_phone)
    if not req:
        return False
    lang = req.get("lang") or "en"
    images = [(u, t) for u, t in zip(media_urls or [], media_types or []) if u and (t or "").lower().startswith("image/")]
    if not images:
        n = int(req.get("nudges") or 0) + 1
        await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"nudges": n, "last_reply": (body or "")[:200], "updated_at": _now()}})
        if n <= MAX_NUDGES:
            await _reply(db, req, text(lang, "not_image" if media_urls else "nudge"))
        return True
    url, ctype = images[0]
    try:
        data, ctype = await download(url, ctype)
        from routers.profile import _save_profile_photo
        saved = await _save_profile_photo(db, req["user_id"], data, ctype)
    except Exception as e:
        logger.warning(f"[PhotoRequest] photo from {from_phone} failed: {getattr(e, 'detail', None) or e}")
        await db[COLL].update_one({"_id": req["_id"]}, {"$inc": {"failures": 1}, "$set": {"last_error": str(getattr(e, 'detail', None) or e)[:200], "updated_at": _now()}})
        await _reply(db, req, text(lang, "retry"))
        return True
    user = await db.users.find_one({"_id": ObjectId(req["user_id"])}, {"name": 1})
    await db[COLL].update_one({"_id": req["_id"]}, {"$set": {"status": "done", "photo_saved_at": _now(), "photo_url": saved.get("photo_url"), "message_sid": message_sid, "updated_at": _now()}})
    link = await card_link(db, req["user_id"])
    first = _first((user or {}).get("name"))
    await _reply(db, req, text(lang, "done", first=first, link=link) if link else text(lang, "done_nolink", first=first))
    logger.info(f"[PhotoRequest] photo saved for {req['user_id']} from {from_phone}")
    return True


async def summary(db, user_id: str) -> Optional[dict]:
    """For the interview card: the latest request and where it stands."""
    r = await db[COLL].find_one({"user_id": user_id, "status": {"$in": ["open", "done"]}}, sort=[("asked_at", -1)])
    if not r:
        return None
    status = r["status"]
    if status == "open" and r.get("expires_at") and r["expires_at"].replace(tzinfo=None) <= _now().replace(tzinfo=None):
        status = "expired"
    iso = lambda v: v.isoformat() if hasattr(v, "isoformat") else None
    return {"status": status, "had_photo": bool(r.get("had_photo")), "asked_at": iso(r.get("asked_at")), "expires_at": iso(r.get("expires_at")), "photo_saved_at": iso(r.get("photo_saved_at")),
            "sms_ok": bool((r.get("sms") or {}).get("ok")), "to_phone": r.get("to_phone")}
