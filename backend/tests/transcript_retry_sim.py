"""Simulates Whisper failing then recovering for one voice note (no real Whisper calls), end to end through the retry pipeline.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/transcript_retry_sim.py <user_id> <contact_id>
Prints each step; leaves the recovered note on the contact (delete it in the app or with --cleanup)."""
import asyncio
import sys
import wave
from datetime import timedelta

sys.path.insert(0, ".")
from bson import ObjectId  # noqa: E402


def _silent_wav(path: str = "/tmp/transcript_sim.wav") -> bytes:
    w = wave.open(path, "w")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\x00\x00" * 16000); w.close()
    return open(path, "rb").read()


async def main(uid: str, cid: str, cleanup: bool):
    from routers.database import get_db
    import routers.voice_notes as vn
    from services import transcript_retry as tr
    db = get_db()

    async def boom(*a, **k):
        raise RuntimeError("simulated whisper outage")
    vn._whisper = boom
    out = await vn._process_voice_note(db, uid, cid, _silent_wav(), "audio/wav", 2.0, "memo")
    nid = out["id"]
    print("upload ->", out["transcript_status"], nid)
    for i in range(3):
        await db.voice_notes.update_one({"_id": ObjectId(nid)}, {"$set": {"transcript_next_at": tr._now() - timedelta(seconds=1)}})
        await tr.sweep(db)
        n = await db.voice_notes.find_one({"_id": ObjectId(nid)})
        print(f"scheduled retry {i + 1} ->", n["transcript_status"], "attempts", n.get("transcript_attempts"), "next", n.get("transcript_next_at"))
    t = await db.tasks.find_one({"idempotency_key": f"transcript_failed_{nid}"})
    print("reminder task ->", t and t["title"])

    async def ok(*a, **k):
        return "We met at the Phoenix auto show. His daughter Emma plays travel soccer and he wants to trade his F-150 for a Silverado."
    vn._whisper = ok
    n = await db.voice_notes.find_one({"_id": ObjectId(nid)})
    print("manual retry ->", (await tr.retry_one(db, n, manual=True))["transcript_status"])
    t = await db.tasks.find_one({"idempotency_key": f"transcript_failed_{nid}"})
    print("reminder closed ->", t and t.get("completed"))
    if cleanup:
        await db.voice_notes.delete_one({"_id": ObjectId(nid)})
        await db.contact_events.delete_many({"metadata.voice_note_id": nid})
        await db.tasks.delete_many({"idempotency_key": f"transcript_failed_{nid}"})
        print("cleaned up", nid)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(args[0], args[1], "--cleanup" in sys.argv))
