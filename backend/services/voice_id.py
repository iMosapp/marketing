"""Voice ID: one Picovoice Eagle speaker profile per rep, enrolled from the onboarding interview (rep-only audio track),
then used to confirm who is talking on recorded calls and recorded conversations. Everything degrades to "not configured"
until PICOVOICE_ACCESS_KEY is in the backend .env."""
import array
import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

from bson import Binary, ObjectId

logger = logging.getLogger(__name__)

VERSION = 1
THRESHOLD = float(os.environ.get("VOICE_ID_THRESHOLD", "0.6"))
MIN_GAP = 0.15  # two channels: the rep's channel must beat the other by this much
WARMUP_FRAMES = 30  # Eagle scores settle after ~1 s of voice


def configured() -> bool:
    return bool(os.environ.get("PICOVOICE_ACCESS_KEY"))


def _key() -> str:
    return os.environ["PICOVOICE_ACCESS_KEY"]


def _ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def to_pcm16k(raw: bytes, mulaw8k: bool = False) -> bytes:
    """Any container (mp3/wav/m4a/webm) or raw Twilio mu-law -> mono 16-bit PCM at 16 kHz, what Eagle eats."""
    src = ["-f", "mulaw", "-ar", "8000", "-ac", "1"] if mulaw8k else []
    cmd = [_ffmpeg(), "-hide_banner", "-loglevel", "error", *src, "-i", "pipe:0", "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1"]
    p = subprocess.run(cmd, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if p.returncode != 0 or len(p.stdout) < 2:
        raise ValueError("audio could not be decoded")
    return p.stdout


def pcm_seconds(pcm: bytes) -> float:
    return len(pcm) / 2 / 16000


def _frames(pcm: bytes, n: int):
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if sys.byteorder != "little":
        samples.byteswap()
    for i in range(0, len(samples) - n + 1, n):
        yield samples[i:i + n].tolist()


def enroll(pcm: bytes) -> dict:
    """Blocking. {"profile": bytes | None, "percent": float}; profile is None until Eagle heard enough clean speech."""
    import pveagle
    profiler = pveagle.create_profiler(_key(), min_enrollment_chunks=3)
    try:
        pct = 0.0
        for f in _frames(pcm, profiler.frame_length):
            pct = profiler.enroll(f)
        pct = profiler.flush()
        if pct < 100.0:
            return {"profile": None, "percent": round(pct, 1)}
        return {"profile": profiler.export().to_bytes(), "percent": 100.0}
    finally:
        profiler.delete()


def score(pcm: bytes, profiles: list) -> list:
    """Blocking. One similarity score (0..1) per profile, median over voiced frames after warm-up; None = no usable voice."""
    import pveagle
    eagle = pveagle.create_recognizer(_key())
    try:
        profs = [pveagle.EagleProfile.from_bytes(b) for b in profiles]
        per = [[] for _ in profs]
        for f in _frames(pcm, eagle.frame_length):
            r = eagle.process(f, profs)
            if r is None:
                continue
            for i, v in enumerate(r):
                per[i].append(float(v))
        out = []
        for xs in per:
            xs = xs[WARMUP_FRAMES:] if len(xs) > WARMUP_FRAMES * 2 else xs
            out.append(round(sorted(xs)[len(xs) // 2], 3) if xs else None)
        return out
    finally:
        eagle.delete()


def summary(user: Optional[dict]) -> dict:
    """What the app shows: never the profile bytes."""
    v = (user or {}).get("voice_id") or {}
    at = v.get("enrolled_at") or v.get("attempted_at")
    return {"configured": configured(), "status": v.get("status") or ("none" if configured() else "not_configured"),
            "enrolled": bool(v.get("profile")), "percent": v.get("percent"), "at": at.isoformat() if hasattr(at, "isoformat") else at,
            "source": v.get("source"), "seconds": v.get("seconds"), "error": v.get("error")}


async def enroll_user(db, user_id: str, audio: bytes, source: str = "interview", seconds: Optional[float] = None) -> dict:
    """Build (or rebuild) the rep's voice print from single-speaker audio and store it on the user."""
    now = datetime.now(timezone.utc)
    if not configured():
        state = {"status": "not_configured", "attempted_at": now, "source": source}
        await db.users.update_one({"_id": ObjectId(user_id), "voice_id.profile": {"$exists": False}}, {"$set": {"voice_id": state}})
        return summary({"voice_id": state})
    try:
        pcm = await asyncio.to_thread(to_pcm16k, audio)
        out = await asyncio.to_thread(enroll, pcm)
    except Exception as e:
        logger.warning(f"[VoiceID] enrollment failed for {user_id}: {e}")
        state = {"status": "failed", "attempted_at": now, "source": source, "error": str(e)[:200]}
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {f"voice_id.{k}": v for k, v in state.items()}})
        return summary(await db.users.find_one({"_id": ObjectId(user_id)}, {"voice_id": 1}))
    if out["profile"]:
        state = {"status": "enrolled", "profile": Binary(out["profile"]), "percent": 100.0, "enrolled_at": now, "attempted_at": now, "source": source,
                 "seconds": round(seconds if seconds is not None else pcm_seconds(pcm), 1), "version": VERSION, "error": None}
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"voice_id": state}})
        logger.info(f"[VoiceID] enrolled {user_id} from {source} ({state['seconds']}s)")
    else:
        # not enough clean speech: keep an older profile if there is one, record the partial attempt
        state = {"status": "partial", "percent": out["percent"], "attempted_at": now, "source": source, "error": None}
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {f"voice_id.{k}": v for k, v in state.items()}})
        await db.users.update_one({"_id": ObjectId(user_id), "voice_id.profile": {"$exists": True}}, {"$set": {"voice_id.status": "enrolled"}})
    return summary(await db.users.find_one({"_id": ObjectId(user_id)}, {"voice_id": 1}))


async def clear_user(db, user_id: str):
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$unset": {"voice_id": ""}})


async def _profiles(db, user_ids: list) -> dict:
    rows = await db.users.find({"_id": {"$in": [ObjectId(u) for u in user_ids if ObjectId.is_valid(str(u))]}, "voice_id.profile": {"$exists": True}}, {"voice_id.profile": 1}).to_list(50)
    return {str(r["_id"]): bytes(r["voice_id"]["profile"]) for r in rows}


async def identify(db, audio: bytes, candidate_user_ids: list, pcm: Optional[bytes] = None) -> Optional[dict]:
    """Who out of these enrolled reps is talking? None when nothing can be said (not configured, nobody enrolled, no voice)."""
    if not configured() or not candidate_user_ids:
        return None
    profiles = await _profiles(db, candidate_user_ids)
    if not profiles:
        return None
    try:
        pcm = pcm or await asyncio.to_thread(to_pcm16k, audio)
        scores = await asyncio.to_thread(score, pcm, list(profiles.values()))
    except Exception as e:
        logger.warning(f"[VoiceID] identify failed: {e}")
        return None
    by_user = dict(zip(profiles.keys(), scores))
    ranked = sorted(((s, u) for u, s in by_user.items() if s is not None), reverse=True)
    if not ranked:
        return {"user_id": None, "score": None, "verified": False, "scores": by_user, "threshold": THRESHOLD}
    best, uid = ranked[0]
    return {"user_id": uid if best >= THRESHOLD else None, "score": best, "verified": best >= THRESHOLD, "scores": by_user, "threshold": THRESHOLD}


async def verify_user(db, user_id: str, audio: bytes) -> Optional[dict]:
    """Is this the rep? {"score", "verified"} or None when we cannot tell."""
    out = await identify(db, audio, [user_id])
    if out is None:
        return None
    return {"user_id": user_id, "score": out["scores"].get(user_id), "verified": out["verified"], "threshold": THRESHOLD}


async def rep_channel(db, user_id: str, wav_paths) -> Optional[dict]:
    """Dual-channel call recording: which channel carries the rep? {"channel": 0|1|None, "scores": [l, r]}; None when unknown."""
    if not configured() or not user_id or not wav_paths:
        return None
    profiles = await _profiles(db, [user_id])
    if not profiles:
        return None
    try:
        scores = []
        for p in wav_paths:
            with open(p, "rb") as f:
                pcm = await asyncio.to_thread(to_pcm16k, f.read())
            scores.append((await asyncio.to_thread(score, pcm, list(profiles.values())))[0])
    except Exception as e:
        logger.warning(f"[VoiceID] channel check failed: {e}")
        return None
    l, r = (scores + [None, None])[:2]
    channel = None
    if l is not None and (r is None or l - r >= MIN_GAP) and l >= THRESHOLD:
        channel = 0
    elif r is not None and (l is None or r - l >= MIN_GAP) and r >= THRESHOLD:
        channel = 1
    return {"channel": channel, "scores": [l, r], "threshold": THRESHOLD}
