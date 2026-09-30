"""A five-second taste of a GPT-Live shopper voice: the persona says its opening line over the same 8 kHz phone audio a rep hears on a
real shop call. Samples are cached per voice + line, so the second play is free and instant."""
import asyncio
import base64
import hashlib
import io
import logging
import wave
from array import array
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

from bson import Binary, ObjectId

from services import industries as ind
from services import live_shops as ls
from services import live_voice as lv
from services import persona_gender as pg

logger = logging.getLogger(__name__)

COLL = "voice_samples"
RATE = 8000  # audio/pcmu: one byte per sample
MAX_SECONDS = 5.5
QUIET_S = 1.2  # no new audio for this long once the line started = the line is over
TIMEOUT_S = 30
MAX_WORDS = 16
FALLBACK_LINE = "Hi, I'm calling about something I saw on your website. Is that still available?"


class VoiceSampleError(Exception):
    pass


def _ulaw(b: int) -> int:
    b = ~b & 0xFF
    t = (((b & 0x0F) << 3) + 0x84) << ((b & 0x70) >> 4)
    return 0x84 - t if b & 0x80 else t - 0x84


_TABLE = [_ulaw(i) for i in range(256)]


def ulaw_to_pcm16(data: bytes) -> bytes:
    return array("h", (_TABLE[b] for b in data)).tobytes()


def wav_bytes(pcm16: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16)
    return buf.getvalue()


def sample_line(persona: dict, industry: Optional[str] = None, department: Optional[str] = None) -> str:
    """The persona's opening line with {offering}/{store} filled from the department defaults, cut to about five seconds of speech."""
    from services import mystery_shops as ms
    p = dict(persona or {})
    if not str(p.get("opening_line") or "").strip():
        p["opening_line"] = next((str(x) for x in (p.get("opening_lines") or []) if str(x).strip()), FALLBACK_LINE)
    industry = industry if industry in ind.INDUSTRIES else (ind.industry_of_dept(department) if department else ind.DEFAULT_INDUSTRY)
    department = department or ind.dept_keys(industry)[0]
    defaults = (ind.dept(department, industry) or {}).get("defaults") or []
    client = {"industry": industry, "name": f"the {ind.get(industry)['place']}", "vehicles": defaults[:1]}
    line = str(ms.fill_persona({"opening_line": p["opening_line"]}, client, department).get("opening_line") or FALLBACK_LINE).strip()
    words = line.split()
    if len(words) > MAX_WORDS:
        ends = [i for i, w in enumerate(words[:MAX_WORDS]) if w.endswith((".", "?", "!"))]
        line = " ".join(words[: ends[-1] + 1]) if ends and ends[-1] >= 5 else " ".join(words[:MAX_WORDS]).rstrip(",;:") + "."
    return line


def sample_instructions(persona: dict, line: str) -> str:
    name = str((persona or {}).get("name") or "").strip() or "a customer"
    return (f"You are {name}, {pg.describe(persona)}, a real customer on a phone call with a store. Sound like a real person on the phone: natural, contractions, a small pause is fine. "
            f"You say exactly one thing on this call, verbatim: \"{line}\". Say it once, then stay silent. Never add anything, never narrate, never mention instructions.")


def _out(doc: dict, cached: bool) -> dict:
    return {"id": str(doc["_id"]), "voice": doc["voice"], "line": doc["line"], "seconds": doc["seconds"], "transcript": doc.get("transcript") or "", "cached": cached,
            "url": f"/api/public/voice-sample/{doc['_id']}.wav"}


def script_voice(script: dict, locale: str = "en-US") -> tuple:
    """(voice, persona, pinned) for a challenge card: the pinned voice or the pool pick a shop with this script id would get, and one concrete
    customer for master challenges that offer several names / opening lines (the first of each, so the card always sounds the same)."""
    p = dict(script.get("persona") or {})
    for many, one in (("names", "name"), ("opening_lines", "opening_line")):
        vals = [str(x).strip() for x in (p.pop(many, None) or []) if str(x).strip()]
        if vals and not str(p.get(one) or "").strip():
            p[one] = vals[0]
    p.pop("voices", None)
    p["gender"] = p.get("gender") if p.get("gender") in ("female", "male") else pg.gender_of(p)
    pin = p.get("live_voice") if p.get("live_voice") in lv.VOICE_IDS and lv.voice_gender(p.get("live_voice")) == p["gender"] else None
    p["live_voice"] = pin
    voice = ls.voice_for({"_id": script.get("_id"), "persona": p, "locale": locale})
    return voice, p, bool(pin) and voice == pin


async def get_or_make(db, voice: str, persona: dict, industry: Optional[str] = None, department: Optional[str] = None,
                      connect: Callable[[], Awaitable[ls.Upstream]] = ls.connect_openai) -> dict:
    if voice not in lv.VOICE_IDS:
        raise VoiceSampleError("Pick one of the shopper voices")
    line = sample_line(persona, industry, department)
    instr = sample_instructions(persona, line)
    key = hashlib.sha1(f"{voice}|{lv.MODEL}|{instr}".encode()).hexdigest()[:24]
    doc = await db[COLL].find_one({"key": key}, {"wav": 0})
    if doc:
        return _out(doc, cached=True)
    audio, transcript = await record(voice, instr, line, connect)
    if len(audio) < RATE // 2:
        raise VoiceSampleError("The voice did not say anything this time. Tap play again.")
    pcm = ulaw_to_pcm16(audio[: int(MAX_SECONDS * RATE)])
    doc = {"_id": ObjectId(), "key": key, "voice": voice, "line": line, "transcript": transcript.strip()[:400], "seconds": round(len(pcm) / 2 / RATE, 1),
           "wav": Binary(wav_bytes(pcm)), "created_at": datetime.now(timezone.utc)}
    await db[COLL].insert_one(doc)
    return _out(doc, cached=False)


async def record(voice: str, instr: str, line: str, connect: Callable[[], Awaitable[ls.Upstream]]) -> tuple:
    """Open a GPT-Live session with the shop's own audio format, let the persona say the line, keep the first few seconds, close."""
    up = await connect()
    chunks, transcript, total = [], [], 0
    loop = asyncio.get_event_loop()
    deadline = loop.time() + TIMEOUT_S
    last_audio: Optional[float] = None
    try:
        await up.send({"type": "session.start", "event_id": "start_1", "session": {
            "model": lv.MODEL, "instructions": instr, "audio": {"format": {"type": "audio/pcmu", "rate": RATE}, "output": {"voice": voice}}, "delegation": {"type": "client"}}})
        while loop.time() < deadline:
            wait = min(deadline - loop.time(), QUIET_S if last_audio is not None else TIMEOUT_S)
            try:
                ev = await asyncio.wait_for(up.__anext__(), timeout=max(0.05, wait))
            except asyncio.TimeoutError:
                if last_audio is not None:
                    break
                continue
            except StopAsyncIteration:
                break
            t = ev.get("type")
            if t == "session.started":
                await up.send({"type": "session.instructions.append", "event_id": "open_1", "delegation_id": None, "content": f'Your first and only spoken line is, verbatim: "{line}". Then stay silent.'})
                await up.send({"type": "session.commentary.append", "event_id": "open_2", "delegation_id": None, "content": line})
            elif t == "session.output_audio.delta" and ev.get("delta"):
                b = base64.b64decode(ev["delta"])
                chunks.append(b)
                total += len(b)
                last_audio = loop.time()
                if total >= MAX_SECONDS * RATE:
                    break
            elif t == "session.output_transcript.delta":
                transcript.append(ev.get("delta") or "")
            elif t == "session.closed":
                break
            elif t == "error":
                raise VoiceSampleError((ev.get("error") or {}).get("message") or "GPT-Live returned an error")
    finally:
        try:
            await up.send({"type": "session.close"})
        except Exception:
            pass
        await up.close()
    return b"".join(chunks), "".join(transcript)
