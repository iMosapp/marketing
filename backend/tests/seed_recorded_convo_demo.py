"""Seed one recorded in-person conversation (12s tone as audio + realistic transcript) for Sarah Tester / Activation Tester,
then run Recording Highlights so tasks + highlights exist. Idempotent. `--wipe` removes everything it created.
Run: cd /app/backend && python tests/seed_recorded_convo_demo.py [--wipe]"""
import asyncio
import io
import math
import os
import struct
import sys
import wave
from datetime import datetime, timezone

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

REP_EMAIL = "activation-tester@invalid.imonsocial.test"
MARK = "recorded_convo_demo"
TRANSCRIPT = (
    "Rep: Thanks for coming by, Sarah. So you liked the white Tahoe Z71 out front? "
    "Customer: I did, but I need to know what my Explorer is worth on trade, it has about sixty two thousand miles. "
    "Rep: I'll get you a firm trade number and the out-the-door price on the Tahoe texted over by tomorrow morning. "
    "Customer: Perfect. My husband wants to see it too, can we come back next Saturday around ten? "
    "Rep: Next Saturday at ten works, I'll have it pulled up front and washed. "
    "Customer: Great. I also need to send you a copy of my insurance card and the payoff letter from my credit union. "
    "Rep: Sounds good, text those to me when you get home and I'll build the deal around them."
)


def _tone_wav(seconds: int = 12, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        frames = bytearray()
        for i in range(rate * seconds):
            t = i / rate
            amp = 0.25 * (0.6 + 0.4 * math.sin(2 * math.pi * 0.5 * t))
            frames += struct.pack("<h", int(32767 * amp * math.sin(2 * math.pi * (220 + 40 * math.sin(t)) * t)))
        w.writeframes(bytes(frames))
    return buf.getvalue()


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rep = await db.users.find_one({"email": REP_EMAIL}, {"_id": 1})
    ev = await db.call_evaluations.find_one({"call_sid": "CA_scdemo_good_001"}, {"contact_id": 1})
    if not rep or not ev:
        print("need the scorecard demo seed first (tests/seed_scorecard_demo.py)"); return
    rep_id, contact_id = str(rep["_id"]), ev["contact_id"]
    if wipe:
        notes = [n["_id"] for n in await db.voice_notes.find({MARK: True}, {"_id": 1}).to_list(50)]
        r1 = await db.tasks.delete_many({"voice_note_id": {"$in": [str(n) for n in notes]}})
        r2 = await db.contact_events.delete_many({"metadata.voice_note_id": {"$in": [str(n) for n in notes]}})
        r3 = await db.voice_notes.delete_many({MARK: True})
        print(f"wiped notes={r3.deleted_count} tasks={r1.deleted_count} events={r2.deleted_count}"); return
    existing = await db.voice_notes.find_one({MARK: True, "contact_id": contact_id})
    if existing:
        print(f"already seeded: voice note {existing['_id']} ({len(existing.get('highlights') or [])} highlights)"); return
    from utils.image_storage import put_object
    from services.recording_highlights import process_recorded_conversation
    path = f"voice-notes/{contact_id}/demo_convo_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.wav"
    stored = put_object(path, _tone_wav(), "audio/wav").get("path") or path
    now = datetime.now(timezone.utc)
    res = await db.voice_notes.insert_one({"contact_id": contact_id, "user_id": rep_id, "audio_url": f"/api/images/{stored}", "audio_path": stored,
                                           "transcript": TRANSCRIPT, "summary": "", "kind": "conversation", "duration": 12.0, "created_at": now, MARK: True})
    note_id = str(res.inserted_id)
    await db.contact_events.insert_one({"event_type": "conversation_recorded", "title": "In-person conversation recorded", "description": TRANSCRIPT[:200], "contact_id": contact_id,
                                        "user_id": rep_id, "channel": "voice_note", "category": "voice_note", "icon": "people", "color": "#C9A962", "content": TRANSCRIPT,
                                        "metadata": {"voice_note_id": note_id, "duration": 12.0, "kind": "conversation"}, "timestamp": now, "created_at": now})
    out = await process_recorded_conversation(db, rep_id, contact_id, note_id, TRANSCRIPT)
    print(f"seeded voice note {note_id} for contact {contact_id}: {len(out['tasks'])} tasks")
    for t in out["tasks"]:
        print("  -", t["title"], t["due_date"], t["action"])


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
