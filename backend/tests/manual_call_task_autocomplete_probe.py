"""Manual probe: connected-call auto-completes the task the rep tapped Call from.
Simulates pending_calls + Twilio recording-complete webhook, then cleans up. Run from /app/backend."""
import asyncio, os, sys, json, subprocess
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient

API = subprocess.check_output("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2", shell=True, text=True).strip()
USER_ID = open("/tmp/uid").read().strip()
CONTACT_ID = "69a496841603573df5a41723"
SID = "CA_probe_task_autocomplete_001"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    t = await db.tasks.insert_one({
        "user_id": USER_ID, "contact_id": CONTACT_ID, "contact_name": "Bud", "type": "appointment",
        "appointment_type": "call", "title": "PROBE call task", "status": "pending", "completed": False,
        "due_date": datetime.now(timezone.utc) + timedelta(hours=2), "has_time": True,
        "created_at": datetime.now(timezone.utc), "source": "manual", "priority": "medium", "priority_order": 2,
    })
    tid = str(t.inserted_id)
    await db.pending_calls.insert_one({
        "call_sid": SID, "customer_phone": "+15005550006", "rep_twilio_number": "+15005550007",
        "rep_user_id": USER_ID, "contact_id": CONTACT_ID, "task_id": tid, "created_at": datetime.utcnow(),
    })
    # 1) duration 0 (rep hung up before customer answered) -> must NOT complete
    r = subprocess.run(["curl", "-s", "-X", "POST", f"{API}/api/webhooks/twilio/recording-complete",
                        "-d", f"CallSid={SID}&RecordingUrl=https://example.invalid/rec&RecordingSid=RE1&RecordingStatus=completed&RecordingDuration=0"],
                       capture_output=True, text=True)
    print("webhook(dur=0):", r.stdout.strip())
    await asyncio.sleep(1)
    doc = await db.tasks.find_one({"_id": ObjectId(tid)})
    print("after dur=0 -> completed:", doc.get("completed"))
    assert not doc.get("completed")
    # 2) duration 42s -> completes
    r = subprocess.run(["curl", "-s", "-X", "POST", f"{API}/api/webhooks/twilio/recording-complete",
                        "-d", f"CallSid={SID}&RecordingUrl=https://example.invalid/rec&RecordingSid=RE2&RecordingStatus=completed&RecordingDuration=42"],
                       capture_output=True, text=True)
    print("webhook(dur=42):", r.stdout.strip())
    await asyncio.sleep(1)
    doc = await db.tasks.find_one({"_id": ObjectId(tid)})
    print("after dur=42 -> completed:", doc.get("completed"), "via:", doc.get("completed_via"))
    assert doc.get("completed") and doc.get("completed_via") == "call_connected"
    ev = await db.contact_events.find_one({"event_type": "task_completed", "contact_id": CONTACT_ID, "title": "Task Completed: PROBE call task"})
    print("event logged:", bool(ev), (ev or {}).get("description"))
    # contact tasks endpoint must no longer list it
    tok = open("/tmp/tok").read().strip()
    out = subprocess.check_output(["curl", "-s", f"{API}/api/tasks/{USER_ID}/contact/{CONTACT_ID}", "-H", f"Authorization: Bearer {tok}"], text=True)
    ids = [x["_id"] for x in json.loads(out)["tasks"]]
    print("still listed as open:", tid in ids)
    assert tid not in ids
    await asyncio.sleep(4)  # let background transcription attempt finish
    # cleanup
    print("cleanup:",
          (await db.tasks.delete_one({"_id": ObjectId(tid)})).deleted_count,
          (await db.pending_calls.delete_many({"call_sid": SID})).deleted_count,
          (await db.call_logs.delete_many({"call_sid": SID})).deleted_count,
          (await db.contact_events.delete_many({"$or": [{"call_sid": SID}, {"title": "Task Completed: PROBE call task"}]})).deleted_count,
          (await db.notifications.delete_many({"user_id": USER_ID, "type": "call_recorded", "recording_url": "https://example.invalid/rec"})).deleted_count,
          (await db.messages.delete_many({"call_sid": SID})).deleted_count)
    print("PASS")

asyncio.run(main())
