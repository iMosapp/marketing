"""Walkaround video -> a handful of sharp, distinct still frames. Plain image math (ffmpeg + PIL + numpy), no AI.
Every frame keeps the timestamp it came from so a finding can always point back to 'customer_walkaround.mov at 00:27'."""
import io
import logging
import os
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

TARGET_CANDIDATES = 120      # frames pulled from the video before scoring
MIN_KEEP, MAX_KEEP = 12, 18  # what we hand to the AI when the video has that much distinct content
SHARP_FLOOR = 40.0           # Laplacian variance under this is motion blur / out of focus
DUP_DISTANCE = 10            # dHash Hamming distance at or under this is a near-duplicate
FRAME_WIDTH = 1024


def ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def probe_duration(path: str) -> float:
    out = subprocess.run([ffmpeg(), "-i", path], capture_output=True, text=True, timeout=60).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", out)
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 0.0


def sharpness(jpeg: bytes) -> float:
    g = Image.open(io.BytesIO(jpeg)).convert("L")
    g.thumbnail((320, 320))
    a = np.asarray(g, dtype=np.float32)
    lap = a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4 * a[1:-1, 1:-1]
    return float(lap.var())


def dhash(jpeg: bytes) -> int:
    g = Image.open(io.BytesIO(jpeg)).convert("L").resize((9, 8), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def thumb(jpeg: bytes, width: int = 480) -> bytes:
    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    im.thumbnail((width, width))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def _ts(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def probe(video: bytes, ext: str) -> dict:
    """Duration plus a poster frame, cheap enough to run at upload time."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, f"in.{ext}")
        with open(src, "wb") as f:
            f.write(video)
        duration = probe_duration(src)
        poster = os.path.join(d, "poster.jpg")
        at = min(1.0, max(0.0, duration / 2)) if duration else 0
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-ss", str(at), "-i", src, "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", "-q:v", "4", poster],
                       capture_output=True, timeout=120)
        poster_jpeg = open(poster, "rb").read() if os.path.exists(poster) else None
    return {"duration": duration, "poster": poster_jpeg}


def select(cands: list, duration: float) -> dict:
    """cands: [{t, jpeg, sharpness, hash}] in time order -> kept frames + what was dropped and why."""
    median = float(np.median([c["sharpness"] for c in cands])) if cands else 0.0
    floor = max(SHARP_FLOOR, 0.25 * median)
    sharp = [c for c in cands if c["sharpness"] >= floor]
    poor = len(cands) > 0 and (len(sharp) < 4 or len(sharp) / len(cands) < 0.3)
    pool = sharp if sharp else sorted(cands, key=lambda c: -c["sharpness"])[:6]
    pool = sorted(pool, key=lambda c: c["t"])
    kept, dupes = [], 0
    for c in pool:
        if any(hamming(c["hash"], k["hash"]) <= DUP_DISTANCE for k in kept):
            dupes += 1
            continue
        kept.append(c)
    if len(kept) > MAX_KEEP:
        span = max(duration, kept[-1]["t"] + 0.5)
        buckets: dict = {}
        for c in kept:
            b = min(MAX_KEEP - 1, int(c["t"] / span * MAX_KEEP))
            if b not in buckets or c["sharpness"] > buckets[b]["sharpness"]:
                buckets[b] = c
        kept = [buckets[b] for b in sorted(buckets)]
    for c in kept:
        c["label"] = _ts(c["t"])
    return {"duration": duration, "candidates": len(cands), "sharp": len(sharp), "blurry_dropped": len(cands) - len(sharp), "duplicates_removed": dupes,
            "quality": "poor" if poor else "ok", "frames": kept}


def extract(video: bytes, ext: str) -> dict:
    """Pull candidate stills, score them, drop blur and repeats, spread the survivors across the clip."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, f"in.{ext}")
        with open(src, "wb") as f:
            f.write(video)
        duration = probe_duration(src)
        fps = 2.0 if duration <= 0 else min(2.0, max(0.5, TARGET_CANDIDATES / duration))
        r = subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", src, "-vf", f"fps={fps:.3f},scale={FRAME_WIDTH}:-2", "-q:v", "3", os.path.join(d, "f_%04d.jpg")],
                           capture_output=True, text=True, timeout=600)
        files = sorted(f for f in os.listdir(d) if f.startswith("f_"))
        if not files:
            raise ValueError(f"Could not read that video ({(r.stderr or '').strip()[:120] or 'no frames'})")
        cands = []
        for i, fn in enumerate(files):
            jpeg = open(os.path.join(d, fn), "rb").read()
            cands.append({"t": i / fps, "jpeg": jpeg, "sharpness": sharpness(jpeg), "hash": dhash(jpeg)})
    out = select(cands, duration)
    out["fps"] = fps
    return out
