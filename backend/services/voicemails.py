"""Voicemail inbox: one doc per unanswered inbound call (kind missed -> voicemail once a recording lands).

Rows live in `voicemails`; the legacy `messages` (channel voicemail) row is still written so threads keep showing them.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

COLL = "voicemail_inbox"
GREETINGS = "voicemail_greetings"
GREETING_MAX_S = 60
MISSED_PUSH_DELAY_S = 120   # give the caller time to leave a message before we call it "missed"
MIN_VOICEMAIL_S = 2         # shorter than this is a hang-up, not a message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(p: str) -> str:
    from routers.twilio_webhooks import normalize_phone
    return normalize_phone(p or "")


def fmt_phone(p: str) -> str:
    d = "".join(c for c in (p or "") if c.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (p or "")


def fmt_duration(s) -> str:
    try:
        s = int(s or 0)
    except (TypeError, ValueError):
        s = 0
    return f"{s // 60}:{s % 60:02d}"


# ---------------------------------------------------------------- who owns the line
async def line_owner(db, to_phone: str) -> Optional[dict]:
    """The user whose Twilio number was called; registry assignment, then super admin as the catch-all."""
    u = await db.users.find_one({"$or": [{"twilio_number": to_phone}, {"mvpline_number": to_phone}], "status": {"$ne": "deactivated"}})
    if u:
        return u
    reg = await db.phone_numbers.find_one({"phone_number": to_phone, "assigned_user_id": {"$nin": [None, ""]}})
    if reg and ObjectId.is_valid(str(reg["assigned_user_id"])):
        u = await db.users.find_one({"_id": ObjectId(str(reg["assigned_user_id"]))})
        if u:
            return u
    return await db.users.find_one({"role": "super_admin", "status": {"$ne": "deactivated"}}, sort=[("created_at", 1)])


async def line_label(db, owner: Optional[dict], to_phone: str) -> str:
    reg = await db.phone_numbers.find_one({"phone_number": to_phone}, {"number_type": 1, "store_id": 1, "label": 1})
    if reg and (reg.get("number_type") or "").upper() == "STORE":
        store = await db.stores.find_one({"_id": ObjectId(str(reg["store_id"]))}, {"name": 1}) if reg.get("store_id") and ObjectId.is_valid(str(reg.get("store_id"))) else None
        return (store or {}).get("name") or reg.get("label") or "Store line"
    if owner:
        return f"{(owner.get('name') or 'Team').split()[0]}'s line"
    return "Unassigned line"


def contact_display(c: Optional[dict]) -> Optional[str]:
    if not c:
        return None
    return (c.get("name") or f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()) or None


async def match_contact(db, from_phone: str, owner_id: Optional[str]) -> Optional[dict]:
    from services.contact_match import phone_clause, NOT_MERGED
    q = {**(phone_clause(from_phone) or {"phone": from_phone}), "status": NOT_MERGED}
    if owner_id:
        c = await db.contacts.find_one({**q, "user_id": owner_id}, sort=[("photo_url", -1), ("created_at", 1)])
        if c:
            return c
    return await db.contacts.find_one(q, sort=[("photo_url", -1), ("created_at", 1)])


# ---------------------------------------------------------------- writes from the Twilio webhooks
async def open_missed(db, call_sid: str, from_phone: str, to_phone: str) -> dict:
    """<Dial> ended without the rep: record the call now; a recording upgrades it to a voicemail."""
    from_phone, to_phone = _norm(from_phone), _norm(to_phone)
    existing = await db[COLL].find_one({"call_sid": call_sid})
    if existing:
        return existing
    owner = await line_owner(db, to_phone)
    owner_id = str(owner["_id"]) if owner else None
    contact = await match_contact(db, from_phone, owner_id)
    doc = {
        "call_sid": call_sid, "kind": "missed",
        "from_phone": from_phone, "to_phone": to_phone,
        "user_id": owner_id, "line_user_id": owner_id, "line_label": await line_label(db, owner, to_phone),
        "organization_id": str(owner.get("organization_id")) if owner and owner.get("organization_id") else None,
        "contact_id": str(contact["_id"]) if contact else None,
        "contact_name": contact_display(contact),
        "contact_photo": (contact or {}).get("photo_url") or None,
        "recording_url": None, "recording_sid": None, "duration": 0,
        "transcript": "", "transcript_status": "none",
        "heard_at": None, "deleted_at": None, "notified_at": None,
        "created_at": _now(),
    }
    r = await db[COLL].insert_one(doc)
    doc["_id"] = r.inserted_id
    asyncio.create_task(_missed_push_later(call_sid))
    return doc


async def attach_recording(db, call_sid: str, from_phone: str, to_phone: str, recording_url: str, recording_sid: str, duration) -> Optional[dict]:
    """recordingStatusCallback: the caller hung up, the file is ready. Save + transcribe + notify."""
    doc = await db[COLL].find_one({"call_sid": call_sid}) or await open_missed(db, call_sid, from_phone, to_phone)
    try:
        duration = int(duration or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration < MIN_VOICEMAIL_S:
        logger.info(f"[Voicemail] {call_sid} recording {duration}s, keeping as missed call")
        return doc
    if doc.get("recording_url"):
        return doc
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {
        "kind": "voicemail", "recording_url": recording_url, "recording_sid": recording_sid,
        "duration": duration, "transcript_status": "pending", "updated_at": _now(),
    }})
    doc = await db[COLL].find_one({"_id": doc["_id"]})
    await _write_thread_message(db, doc)
    asyncio.create_task(_transcribe_and_notify(str(doc["_id"])))
    return doc


async def set_transcript(db, call_sid: str, text: str, source: str = "twilio") -> None:
    """Twilio's own transcription callback: only fills the gap when Whisper has not."""
    doc = await db[COLL].find_one({"call_sid": call_sid})
    if not doc:
        return
    if doc.get("transcript") and doc.get("transcript_status") == "done":
        return
    text = (text or "").strip()
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {
        "transcript": text or doc.get("transcript") or "",
        "transcript_status": "done" if text else doc.get("transcript_status") or "failed",
        "transcript_source": source, "updated_at": _now(),
    }})
    if text:
        await db.messages.update_one({"call_sid": call_sid, "channel": "voicemail"}, {"$set": {"content": text}})


async def _write_thread_message(db, doc: dict) -> None:
    if await db.messages.find_one({"call_sid": doc["call_sid"], "channel": "voicemail"}, {"_id": 1}):
        return
    await db.messages.insert_one({
        "user_id": doc.get("user_id"), "contact_id": doc.get("contact_id"), "contact_phone": doc["from_phone"],
        "content": doc.get("transcript") or f"Voicemail ({fmt_duration(doc.get('duration'))})",
        "recording_url": doc.get("recording_url"), "sender": "contact", "direction": "inbound",
        "channel": "voicemail", "call_sid": doc["call_sid"], "voicemail_id": str(doc["_id"]),
        "timestamp": datetime.utcnow(),
    })


async def _transcribe_and_notify(vm_id: str) -> None:
    from routers.database import get_db
    db = get_db()
    doc = await db[COLL].find_one({"_id": ObjectId(vm_id)})
    if not doc:
        return
    text, status = "", "failed"
    try:
        text = await _whisper(db, doc)
        status = "done" if text else "failed"
    except Exception as e:
        logger.warning(f"[Voicemail] Whisper failed for {doc['call_sid']}: {e}")
    if text:
        await db[COLL].update_one({"_id": doc["_id"], "transcript_status": {"$ne": "done"}}, {"$set": {
            "transcript": text, "transcript_status": "done", "transcript_source": "whisper", "updated_at": _now()}})
        await db.messages.update_one({"call_sid": doc["call_sid"], "channel": "voicemail"}, {"$set": {"content": text}})
    else:
        await db[COLL].update_one({"_id": doc["_id"], "transcript_status": "pending"}, {"$set": {"transcript_status": status}})
    doc = await db[COLL].find_one({"_id": doc["_id"]})
    await notify(db, doc)


async def _whisper(db, doc: dict) -> str:
    tw_sid, tw_token = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not (tw_sid and tw_token and key and doc.get("recording_url")):
        return ""
    import requests, uuid
    url = doc["recording_url"] if doc["recording_url"].endswith((".mp3", ".wav")) else f"{doc['recording_url']}.mp3"
    status_code, content = await asyncio.to_thread(lambda: (lambda r: (r.status_code, r.content))(requests.get(url, auth=(tw_sid, tw_token), timeout=60)))
    if status_code != 200 or not content:
        return ""
    path = f"/tmp/vm_{uuid.uuid4().hex}.mp3"
    with open(path, "wb") as f:
        f.write(content)
    lang = "en"
    try:
        from services import locales as _loc
        if doc.get("user_id") and ObjectId.is_valid(str(doc["user_id"])):
            lang = _loc.get(await _loc.user_locale(db, await db.users.find_one({"_id": ObjectId(doc["user_id"])}, {"store_id": 1})))["whisper"]
    except Exception:
        pass
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        stt = OpenAISpeechToText(api_key=key)
        with open(path, "rb") as af:
            result = await asyncio.wait_for(stt.transcribe(af, language=lang), timeout=90.0)
        text = result.text if hasattr(result, "text") else (result.get("text") if isinstance(result, dict) else str(result or ""))
        return (text or "").strip()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def caller_name(doc: dict) -> str:
    return doc.get("contact_name") or fmt_phone(doc.get("from_phone")) or "Unknown caller"


async def notify(db, doc: dict) -> None:
    if not doc.get("user_id") or doc.get("notified_at"):
        return
    who = caller_name(doc)
    if doc.get("kind") == "voicemail":
        title = f"Voicemail from {who} · {fmt_duration(doc.get('duration'))}"
        body = doc.get("transcript") or "Tap to listen"
        ntype = "voicemail"
    else:
        title = f"Missed call from {who}"
        body = f"No message · {doc.get('line_label') or 'your line'}"
        ntype = "missed_call"
    await db.notifications.insert_one({
        "user_id": doc["user_id"], "type": ntype, "title": title, "message": body[:200],
        "contact_id": doc.get("contact_id"), "recording_url": doc.get("recording_url"), "voicemail_id": str(doc["_id"]),
        "read": False, "dismissed": False, "created_at": datetime.utcnow(),
    })
    try:
        from routers.push_notifications import send_push_native
        await send_push_native(user_id=doc["user_id"], title=title, body=body[:180],
                               data={"url": "/(tabs)/dialer?tab=voicemail", "voicemail_id": str(doc["_id"]), "action": ntype})
    except Exception as e:
        logger.warning(f"[Voicemail] push failed: {e}")
    await db[COLL].update_one({"_id": doc["_id"]}, {"$set": {"notified_at": _now()}})


async def _missed_push_later(call_sid: str) -> None:
    await asyncio.sleep(MISSED_PUSH_DELAY_S)
    from routers.database import get_db
    db = get_db()
    doc = await db[COLL].find_one({"call_sid": call_sid})
    if doc and doc.get("kind") == "missed" and not doc.get("notified_at"):
        await notify(db, doc)


# ---------------------------------------------------------------- reads for the app
def scope_query(me: dict) -> dict:
    """Everyone sees the lines they own; super admins see every line."""
    return {} if me.get("role") == "super_admin" else {"user_id": str(me["_id"])}


def _play_url(recording_url: Optional[str]) -> Optional[str]:
    if not recording_url:
        return None
    import urllib.parse
    public_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    mp3 = recording_url if recording_url.endswith((".mp3", ".wav")) else f"{recording_url}.mp3"
    return f"{public_url}/api/webhooks/twilio/media-proxy?url={urllib.parse.quote(mp3, safe='')}"


def serialize(doc: dict, me: dict) -> dict:
    mine = str(doc.get("line_user_id") or doc.get("user_id") or "") == str(me["_id"])
    return {
        "id": str(doc["_id"]), "kind": doc.get("kind") or "voicemail",
        "from_phone": doc.get("from_phone"), "from_display": fmt_phone(doc.get("from_phone")),
        "caller_name": caller_name(doc), "contact_id": doc.get("contact_id"), "contact_photo": doc.get("contact_photo"),
        "to_phone": doc.get("to_phone"), "to_display": fmt_phone(doc.get("to_phone")),
        "line_label": "Your line" if mine else (doc.get("line_label") or "Team line"), "line_is_mine": mine,
        "duration": int(doc.get("duration") or 0), "duration_display": fmt_duration(doc.get("duration")),
        "transcript": doc.get("transcript") or "", "transcript_status": doc.get("transcript_status") or "none",
        "play_url": _play_url(doc.get("recording_url")),
        "heard": bool(doc.get("heard_at")),
        "created_at": (doc.get("created_at") or _now()).isoformat(),
    }


async def list_for(db, me: dict, line: Optional[str] = None, limit: int = 100) -> dict:
    await migrate_legacy(db)
    base = {**scope_query(me), "deleted_at": None}
    q = {**base, "to_phone": _norm(line)} if line else base
    docs = await db[COLL].find(q).sort("created_at", -1).limit(limit).to_list(limit)
    lines = {}
    async for d in db[COLL].find(base, {"to_phone": 1, "line_label": 1, "line_user_id": 1, "heard_at": 1}):
        row = lines.setdefault(d["to_phone"], {"phone": d["to_phone"], "display": fmt_phone(d["to_phone"]),
                                                "label": "Your line" if str(d.get("line_user_id")) == str(me["_id"]) else (d.get("line_label") or "Team line"),
                                                "unheard": 0, "total": 0})
        row["total"] += 1
        row["unheard"] += 0 if d.get("heard_at") else 1
    return {
        "items": [serialize(d, me) for d in docs],
        "lines": sorted(lines.values(), key=lambda r: (not r["label"].startswith("Your"), r["label"])),
        "unheard": await db[COLL].count_documents({**base, "heard_at": None}),
    }


async def unheard_count(db, me: dict) -> int:
    return await db[COLL].count_documents({**scope_query(me), "deleted_at": None, "heard_at": None})


async def mark_heard(db, me: dict, vm_id: str) -> bool:
    r = await db[COLL].update_one({"_id": ObjectId(vm_id), **scope_query(me), "heard_at": None}, {"$set": {"heard_at": _now()}})
    return r.matched_count > 0


async def soft_delete(db, me: dict, vm_id: str) -> bool:
    r = await db[COLL].update_one({"_id": ObjectId(vm_id), **scope_query(me), "deleted_at": None}, {"$set": {"deleted_at": _now(), "heard_at": _now()}})
    return r.matched_count > 0


_migrated = False


async def migrate_legacy(db) -> int:
    """Voicemails saved before the inbox existed live only in `messages` (channel voicemail). Pull them in once."""
    global _migrated
    if _migrated:
        return 0
    _migrated = True
    n = 0
    try:
        cur = db.messages.find({"channel": "voicemail", "voicemail_id": {"$exists": False}}).sort("timestamp", -1).limit(500)
        async for m in cur:
            sid = m.get("call_sid") or f"legacy_{m['_id']}"
            if await db[COLL].find_one({"call_sid": sid}, {"_id": 1}):
                await db.messages.update_one({"_id": m["_id"]}, {"$set": {"voicemail_id": "migrated"}})
                continue
            owner = await db.users.find_one({"_id": ObjectId(str(m["user_id"]))}) if m.get("user_id") and ObjectId.is_valid(str(m["user_id"])) else None
            to_phone = (owner or {}).get("twilio_number") or (owner or {}).get("mvpline_number") or ""
            contact = await db.contacts.find_one({"_id": ObjectId(str(m["contact_id"]))}) if m.get("contact_id") and ObjectId.is_valid(str(m["contact_id"])) else None
            text = (m.get("content") or "").strip()
            r = await db[COLL].insert_one({
                "call_sid": sid, "kind": "voicemail" if m.get("recording_url") else "missed",
                "from_phone": m.get("contact_phone") or "", "to_phone": to_phone,
                "user_id": m.get("user_id"), "line_user_id": m.get("user_id"),
                "line_label": f"{(owner.get('name') or 'Team').split()[0]}'s line" if owner else "Team line",
                "organization_id": str(owner.get("organization_id")) if owner and owner.get("organization_id") else None,
                "contact_id": m.get("contact_id"), "contact_name": contact_display(contact), "contact_photo": (contact or {}).get("photo_url"),
                "recording_url": m.get("recording_url"), "recording_sid": None, "duration": 0,
                "transcript": "" if text.startswith("(Voicemail") else text,
                "transcript_status": "failed" if text.startswith("(Voicemail") else "done",
                "heard_at": m.get("timestamp") if m.get("read") else None, "deleted_at": None,
                "notified_at": m.get("timestamp"), "created_at": m.get("timestamp") or _now(), "legacy": True,
            })
            await db.messages.update_one({"_id": m["_id"]}, {"$set": {"voicemail_id": str(r.inserted_id)}})
            n += 1
    except Exception as e:
        logger.warning(f"[Voicemail] legacy migration: {e}")
    if n:
        logger.info(f"[Voicemail] migrated {n} legacy voicemail messages")
    return n


# ---------------------------------------------------------------- the greeting callers hear
def default_greeting_text(owner: Optional[dict]) -> str:
    first = ((owner or {}).get("name") or "the team").split()[0]
    return f"Sorry, {first} is unavailable right now. Leave a message after the tone and we'll get back to you quickly."


def greeting_play_url(user_id: str) -> str:
    public_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    return f"{public_url}/api/webhooks/twilio/greeting/{user_id}.mp3"


async def greeting_twiml(db, owner: Optional[dict]) -> str:
    """<Play> the rep's recorded greeting when they have one, else <Say> the default line."""
    if owner and await db[GREETINGS].find_one({"user_id": str(owner["_id"])}, {"_id": 1}):
        return f'<Play>{greeting_play_url(str(owner["_id"]))}</Play>'
    from routers.twilio_webhooks import _xml_escape
    return f"<Say>{_xml_escape(default_greeting_text(owner))}</Say>"


def _to_mp3(raw: bytes, suffix: str) -> tuple:
    """Any phone/browser recording (m4a, webm, wav) -> mono mp3 Twilio can <Play>. Returns (mp3_bytes, seconds)."""
    import subprocess, tempfile, json as _json
    from imageio_ffmpeg import get_ffmpeg_exe
    ffmpeg = get_ffmpeg_exe()
    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix or ".bin", delete=False) as f:
            f.write(raw)
            in_path = f.name
        out_path = in_path + ".mp3"
        subprocess.run([ffmpeg, "-y", "-i", in_path, "-vn", "-ac", "1", "-ar", "22050", "-b:a", "64k", "-t", str(GREETING_MAX_S), out_path],
                       check=True, capture_output=True, timeout=120)
        probe = subprocess.run([ffmpeg, "-i", out_path, "-f", "null", "-"], capture_output=True, timeout=60)
        secs = 0
        import re as _re
        m = _re.findall(r"time=(\d+):(\d+):(\d+)\.(\d+)", probe.stderr.decode(errors="ignore"))
        if m:
            h, mi, se, _ = m[-1]
            secs = int(h) * 3600 + int(mi) * 60 + int(se)
        with open(out_path, "rb") as f:
            return f.read(), secs
    finally:
        for p in (in_path, out_path):
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass


async def save_greeting(db, me: dict, raw: bytes, filename: str) -> dict:
    ext = os.path.splitext(filename or "")[1].lower() or ".m4a"
    mp3, secs = await asyncio.to_thread(_to_mp3, raw, ext)
    from bson import Binary
    await db[GREETINGS].update_one({"user_id": str(me["_id"])}, {"$set": {
        "user_id": str(me["_id"]), "mp3": Binary(mp3), "duration": secs, "size_bytes": len(mp3),
        "source_filename": filename, "updated_at": _now(),
    }, "$setOnInsert": {"created_at": _now()}}, upsert=True)
    return await greeting_status(db, me)


async def greeting_status(db, me: dict) -> dict:
    g = await db[GREETINGS].find_one({"user_id": str(me["_id"])}, {"mp3": 0})
    return {
        "has_greeting": bool(g),
        "duration": int((g or {}).get("duration") or 0), "duration_display": fmt_duration((g or {}).get("duration")),
        "url": f"{greeting_play_url(str(me['_id']))}?v={int((g['updated_at']).timestamp())}" if g else None,
        "updated_at": g["updated_at"].isoformat() if g else None,
        "default_text": default_greeting_text(me),
        "max_seconds": GREETING_MAX_S,
    }


async def delete_greeting(db, me: dict) -> dict:
    await db[GREETINGS].delete_one({"user_id": str(me["_id"])})
    return await greeting_status(db, me)


async def greeting_mp3(db, user_id: str) -> Optional[bytes]:
    g = await db[GREETINGS].find_one({"user_id": user_id}, {"mp3": 1})
    return bytes(g["mp3"]) if g and g.get("mp3") else None
