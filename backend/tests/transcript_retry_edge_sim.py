"""In-process checks: manual retry no 2nd task, manual retry on a 'retrying' note, brief labels, inactive campaign 400. Cleans up."""
import asyncio
import sys
from datetime import timedelta

sys.path.insert(0, ".")
from bson import ObjectId  # noqa: E402

UID, CID, CAMP = "6a978d68b8673c29063aa8b9", "6ad255ff5d01fb1e41498bbe", "6ad2565e176f60e4da573e2a"


async def main():
    from routers.database import get_db
    import routers.voice_notes as vn
    from services import transcript_retry as tr
    db = get_db()

    async def boom(*a, **k):
        raise RuntimeError("sim outage")
    vn._whisper = boom
    out = await vn._process_voice_note(db, UID, CID, open("/tmp/transcript_sim.wav", "rb").read(), "audio/wav", 2.0, "memo")
    nid = out["id"]
    n = await db.voice_notes.find_one({"_id": ObjectId(nid)})
    print("A upload", n["transcript_status"], n["transcript_attempts"], "next-created", n["transcript_next_at"] - n["created_at"])
    ev = await db.contact_events.find_one({"metadata.voice_note_id": nid})
    print("A event exists", bool(ev), ev and ev.get("description"))
    for _ in range(3):
        await db.voice_notes.update_one({"_id": ObjectId(nid)}, {"$set": {"transcript_next_at": tr._now() - timedelta(seconds=1)}})
        await tr.sweep(db)
    print("A tasks after fail", await db.tasks.count_documents({"idempotency_key": f"transcript_failed_{nid}"}))
    n = await db.voice_notes.find_one({"_id": ObjectId(nid)})
    r = await tr.retry_one(db, n, manual=True)
    print("A manual retry still failing ->", r["transcript_status"], "tasks", await db.tasks.count_documents({"idempotency_key": f"transcript_failed_{nid}"}))
    t = await db.tasks.find_one({"idempotency_key": f"transcript_failed_{nid}"})
    print("A task", t["title"], t["user_id"], t["status"])
    # recovery via scheduled path updates the event
    async def ok(*a, **k):
        return "He said his wife Linda wants a third row SUV and they met us at the Mesa rodeo."
    vn._whisper = ok
    n = await db.voice_notes.find_one({"_id": ObjectId(nid)})
    await tr.retry_one(db, n, manual=True)
    ev = await db.contact_events.find_one({"metadata.voice_note_id": nid})
    t = await db.tasks.find_one({"idempotency_key": f"transcript_failed_{nid}"})
    n = await db.voice_notes.find_one({"_id": ObjectId(nid)})
    print("A recovered", n["transcript_status"], "| event:", ev.get("description")[:60], "| task", t.get("completed"), t.get("completed_reason"),
          "| intel_done", n.get("intelligence_done"))

    # B: manual Retry while still 'retrying' and failing
    vn._whisper = boom
    out = await vn._process_voice_note(db, UID, CID, open("/tmp/transcript_sim.wav", "rb").read(), "audio/wav", 2.0, "memo")
    nid2 = out["id"]
    n = await db.voice_notes.find_one({"_id": ObjectId(nid2)})
    await tr.retry_one(db, n, manual=True)
    n = await db.voice_notes.find_one({"_id": ObjectId(nid2)})
    print("B manual retry while retrying ->", n["transcript_status"], "next", n.get("transcript_next_at"), "tasks",
          await db.tasks.count_documents({"idempotency_key": f"transcript_failed_{nid2}"}))

    # C: brief labels
    from services.relationship_intel import build_relationship_brief
    b = await build_relationship_brief(UID, CID)
    txt = str(b)
    i = txt.find("recorded by")
    print("C brief has 'recorded by':", i >= 0, txt[max(0, i - 80): i + 30] if i >= 0 else "")

    # D: inactive campaign
    from services import met_at
    from fastapi import HTTPException
    await db.campaigns.update_one({"_id": ObjectId(CAMP)}, {"$set": {"active": False}})
    try:
        await met_at.enroll(db, UID, CAMP, "NADA")
        print("D inactive -> no error (BUG)")
    except HTTPException as e:
        print("D inactive ->", e.status_code, e.detail)
    finally:
        await db.campaigns.update_one({"_id": ObjectId(CAMP)}, {"$set": {"active": True}})

    for x in (nid, nid2):
        await db.voice_notes.delete_one({"_id": ObjectId(x)})
        await db.contact_events.delete_many({"metadata.voice_note_id": x})
        await db.tasks.delete_many({"$or": [{"idempotency_key": f"transcript_failed_{x}"}, {"voice_note_id": x}]})
    print("cleaned")


asyncio.run(main())
