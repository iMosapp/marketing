"""Voice notes on an appraisal: the rep (or the customer, through the trade link) talks about the car, Whisper types it, and the words land in the
appraisal notes the desk already reads. The clip is kept for playback. Nothing said in a voice note is ever a value or a confirmed input."""
import asyncio
import io
import logging
import os

from bson import ObjectId

from services.appraisals.core import A, VOICE_BY, _name, _now, audit, public_voice_note
from utils.image_storage import put_object
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MAX_SECONDS = 5 * 60
MAX_BYTES = 25 * 1024 * 1024
MAX_NOTES = 8000
MAX_PER_APPRAISAL = 30
MAX_CUSTOMER = 5
NO_SPEECH_MAX = 0.6  # Whisper segments likelier than this to be silence/noise are dropped so quiet clips do not invent words
CONTENT_TYPES = {"m4a": "audio/mp4", "wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg", "webm": "audio/webm"}
PROMPT = ("Spoken notes about a trade-in vehicle at a car dealership: condition, dents, scratches, rust, tires, brakes, warning lights, smells, "
          "service history, accidents, aftermarket parts, keys, mileage, year make model trim.")


def _ext(content_type: str, name: str = "") -> str:
    ct, n = (content_type or "").lower(), (name or "").lower()
    if "mp4" in ct or "m4a" in ct or "aac" in ct or n.endswith((".m4a", ".mp4")):
        return "m4a"
    if "wav" in ct or n.endswith(".wav"):
        return "wav"
    if "mpeg" in ct or "mp3" in ct or n.endswith(".mp3"):
        return "mp3"
    if "ogg" in ct or n.endswith(".ogg"):
        return "ogg"
    return "webm"


async def transcribe(audio: bytes, filename: str) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("[AppraisalVoice] no EMERGENT_LLM_KEY, skipping transcription")
        return ""
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        f = io.BytesIO(audio)
        f.name = filename
        r = await OpenAISpeechToText(api_key=api_key).transcribe(file=f, model="whisper-1", language="en", response_format="verbose_json", prompt=PROMPT)
        segs = getattr(r, "segments", None)
        if segs:
            def _g(s, k):
                return s.get(k) if isinstance(s, dict) else getattr(s, k, None)
            text = " ".join((_g(s, "text") or "").strip() for s in segs if (_g(s, "no_speech_prob") or 0) <= NO_SPEECH_MAX)
        else:
            text = (getattr(r, "text", "") or "")
        return no_em_dash(" ".join(text.split()))
    except Exception as e:  # noqa: BLE001
        logger.error(f"[AppraisalVoice] transcription failed: {e}")
        return ""


def _stamp(d) -> str:
    return d.strftime("%b %d, %I:%M %p").replace(" 0", " ").lstrip("0")


async def add_voice_note(db, appr: dict, actor: dict, *, by: str, data: bytes, content_type: str, duration: float, name: str = "") -> dict:
    """Store the clip, type it, append the words to the notes. Returns the public voice note."""
    if by not in VOICE_BY:
        raise ValueError("Unknown voice note author")
    if not data:
        raise ValueError("Empty recording")
    if len(data) > MAX_BYTES:
        raise ValueError("That recording is too large")
    if duration and duration > MAX_SECONDS:
        raise ValueError(f"Keep each voice note under {MAX_SECONDS // 60} minutes")
    existing = appr.get("voice_notes") or []
    if len(existing) >= MAX_PER_APPRAISAL:
        raise ValueError("That is plenty of voice notes on this appraisal")
    if by == "customer" and sum(1 for v in existing if v.get("by") == "customer") >= MAX_CUSTOMER:
        raise ValueError(f"That is plenty of voice notes ({MAX_CUSTOMER} max). Type anything else in the box.")
    ext = _ext(content_type, name)
    if ext == "webm":
        from routers.voice_notes import _convert_webm_to_m4a
        try:
            data = await asyncio.to_thread(_convert_webm_to_m4a, data)
            ext = "m4a"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[AppraisalVoice] webm->m4a failed, keeping webm: {e}")
    content_type = CONTENT_TYPES[ext]
    vid = str(ObjectId())
    path = f"appraisals/{appr['user_id']}/{appr['_id']}/voice_{vid}.{ext}"
    await asyncio.to_thread(put_object, path, data, content_type)
    transcript = await transcribe(data, f"voice_{vid}.{ext}")
    now = _now()
    block = f"[{VOICE_BY[by]} · {_stamp(now)}] {transcript}" if transcript else ""
    notes = (appr.get("notes") or "").rstrip()
    new_notes = (f"{notes}\n\n{block}" if notes else block) if block else notes
    if len(new_notes) > MAX_NOTES:
        new_notes = notes
    note = {"id": vid, "by": by, "by_name": _name(actor) if by == "rep" else (appr.get("contact_name") or "Customer"), "audio_path": path, "audio_url": f"/api/images/{path}",
            "content_type": content_type, "size": len(data), "duration": round(float(duration or 0), 1), "transcript": transcript, "note_block": block, "created_at": now}
    await db[A].update_one({"_id": appr["_id"]}, {"$push": {"voice_notes": note}, "$set": {"notes": new_notes, "updated_at": now}})
    await audit(db, appr, actor, "voice_note_added", f"{VOICE_BY[by]}: {transcript[:200]}" if transcript else f"{VOICE_BY[by]} recorded (no words made out)",
                meta={"voice_note_id": vid, "duration": note["duration"], "by": by})
    return public_voice_note(note)


async def delete_voice_note(db, appr: dict, me: dict, note_id: str):
    """Remove the clip and take its words back out of the notes."""
    v = next((x for x in appr.get("voice_notes") or [] if x.get("id") == note_id), None)
    if not v:
        raise ValueError("Voice note not found")
    notes = appr.get("notes") or ""
    if v.get("note_block"):
        notes = notes.replace(v["note_block"], "").replace("\n\n\n\n", "\n\n").strip()
    await db[A].update_one({"_id": appr["_id"]}, {"$pull": {"voice_notes": {"id": note_id}}, "$set": {"notes": notes, "updated_at": _now()}})
    await audit(db, appr, me, "voice_note_removed", f"{VOICE_BY.get(v.get('by') or '', 'Voice note')} removed", meta={"voice_note_id": note_id})
