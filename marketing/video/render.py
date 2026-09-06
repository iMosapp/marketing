"""Render a promo MP4 from promo.html scenes + OpenAI TTS narration.

usage: python render.py relationship-os [9x16|16x9] [--fps 30] [--no-voice] [--preview]
"""
import asyncio
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv
from imageio_ffmpeg import get_ffmpeg_exe
from playwright.async_api import async_playwright

load_dotenv("/app/backend/.env")
ROOT = Path(__file__).parent
OUT_DIR = Path("/app/marketing/build-preview/videos")
CACHE = ROOT / ".cache"
FFMPEG = get_ffmpeg_exe()
SR = 48000
LEAD_MS = 350   # silence before each scene's narration starts


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


async def tts_wav(text: str, voice: str, model: str, speed: float) -> Path:
    key = hashlib.sha256(f"{text}|{voice}|{model}|{speed}".encode()).hexdigest()[:20]
    wav, mp3 = CACHE / f"{key}.wav", CACHE / f"{key}.mp3"
    if wav.exists():
        return wav
    if not mp3.exists():
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        tts = OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"])
        mp3.write_bytes(await tts.generate_speech(text=text, model=model, voice=voice, speed=speed, response_format="mp3"))
    run([FFMPEG, "-y", "-i", str(mp3), "-ar", str(SR), "-ac", "2", str(wav)])
    return wav


def wav_ms(path: Path) -> int:
    with wave.open(str(path)) as w:
        return int(w.getnframes() * 1000 / w.getframerate())


def build_track(parts, total_ms: int, out: Path):
    """parts: list of (start_ms, wav_path). Writes one stereo 48k wav of total_ms."""
    frames = bytearray(b"\x00" * int(total_ms / 1000 * SR) * 4)
    for start_ms, path in parts:
        with wave.open(str(path)) as w:
            data = w.readframes(w.getnframes())
        off = int(start_ms / 1000 * SR) * 4
        end = min(len(frames), off + len(data))
        frames[off:end] = data[: end - off]
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))


async def main():
    args = sys.argv[1:]
    video_id = args[0]
    ratio = next((a for a in args if a in ("9x16", "16x9")), "9x16")
    fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 30
    voice_on = "--no-voice" not in args
    preview = "--preview" in args  # one frame per scene, no encode

    spec = json.loads((ROOT / "specs" / f"{video_id}.json").read_text())
    CACHE.mkdir(exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    W, H = (1920, 1080) if ratio == "16x9" else (1080, 1920)
    frames_dir = ROOT / f".frames-{video_id}-{ratio}"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir()

    # 1. narration + timeline
    timeline, audio_parts, t = [], [], 0
    for sc in spec["scenes"]:
        vo_ms = 0
        if voice_on and sc.get("vo"):
            wav = await tts_wav(sc["vo"], spec.get("voice", "onyx"), spec.get("model", "tts-1-hd"), spec.get("speed", 1.0))
            vo_ms = wav_ms(wav)
            audio_parts.append((t + LEAD_MS, wav))
        dur = max(sc["min_ms"], vo_ms + LEAD_MS + 650)
        timeline.append((sc["id"], t, dur))
        t += dur
    total_ms = t
    print(f"[{video_id} {ratio}] {len(timeline)} scenes, {total_ms/1000:.1f}s, {fps}fps", flush=True)

    # 2. frames
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--force-device-scale-factor=1", "--disable-lcd-text"])
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await page.goto(f"file://{ROOT}/promo.html?ratio={ratio}")
        await page.evaluate("window.ready")
        await page.wait_for_timeout(600)
        n = 0
        for sid, start, dur in timeline:
            await page.evaluate("([id, d]) => showScene(id, d)", [sid, dur])
            await page.wait_for_timeout(120)  # let images decode
            steps = [dur * 0.55] if preview else [i * 1000 / fps for i in range(int(dur * fps / 1000))]
            for local in steps:
                await page.evaluate("t => seek(t)", local)
                await page.screenshot(path=str(frames_dir / f"{n:05d}.jpg"), type="jpeg", quality=93)
                n += 1
            print(f"  scene {sid}: {dur}ms -> {n} frames", flush=True)
        await browser.close()

    if preview:
        print(f"preview frames in {frames_dir}")
        return

    # 3. audio + mux
    out = OUT_DIR / f"{video_id}-{ratio}.mp4"
    cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i", str(frames_dir / "%05d.jpg")]
    if audio_parts:
        track = frames_dir / "track.wav"
        build_track(audio_parts, total_ms, track)
        cmd += ["-i", str(track), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(out)]
    run(cmd)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"done: {out} ({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
