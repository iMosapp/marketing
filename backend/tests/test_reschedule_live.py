"""Live test: reschedule-from-reply (detect -> pending change -> approve/decline) + import preview.
Uses Forest (has a Twilio number), a 500-555 test contact, and the real inbound webhook."""
import asyncio, os, sys, json, time
import httpx
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip() + "/api"
PHONE = "+15005550188"
TZ = ZoneInfo("America/Denver")


def ok(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  {str(extra)[:220]}" if extra else ""))
    if not cond:
        sys.exit(1)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    from services.appointment_changes import detect_appointment_change, CHANGE_HINT
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"})
        tok = r.json()["token"]; uid = r.json()["user"].get("id") or r.json()["user"].get("_id")
        H = {"Authorization": f"Bearer {tok}"}
        rep_num = (await db.users.find_one({"_id": ObjectId(uid)}, {"twilio_number": 1}))["twilio_number"]
        await db.contacts.delete_many({"phone": PHONE})
        await db.conversations.delete_many({"contact_phone": PHONE})  # leftovers from older tests would hijack the webhook match
        await db.messages.delete_many({"from_phone": PHONE})
        cid = str((await db.contacts.insert_one({"user_id": uid, "first_name": "Bud", "last_name": "Mover", "phone": PHONE,
                                                 "status": "active", "tags": [], "created_at": datetime.now(timezone.utc)})).inserted_id)
        conv_id = str((await db.conversations.insert_one({"user_id": uid, "rep_phone": rep_num, "contact_phone": PHONE, "contact_id": cid,
                                                          "contact_name": "Bud Mover", "status": "active", "ai_mode": "suggest", "ai_enabled": False,
                                                          "created_at": datetime.now(timezone.utc), "last_message_at": datetime.now(timezone.utc)})).inserted_id)

        # ── Import preview ──────────────────────────────────────────────────────
        rows = [{"first_name": "Bud", "phone": "(500) 555-0188"},                       # already have
                {"first_name": "New", "last_name": "Guy", "phone": "+15005550189", "birthday": "1988-05-05", "email": "n@invalid.test"},
                {"first_name": "Leap", "phone": "5005550190", "birthday": "1900-02-29"},  # date dropped
                {"first_name": "NoPhone", "phone": ""}, "junk"]
        r = await c.post(f"{API}/contacts/{uid}/import/preview?source=phone_import", headers=H, json=rows)
        ok("preview 200", r.status_code == 200, r.text[:200])
        s = r.json()
        ok("preview counts", s["total"] == 5 and s["new"] == 3 and s["already_have"] == 1 and s["failed"] == 1
           and s["with_birthday"] == 1 and s["with_email"] == 1 and s["no_phone"] == 1 and s["dates_dropped"] == 1, s)
        ok("preview wrote nothing", await db.contacts.count_documents({"phone": {"$in": ["+15005550189", "+15005550190"]}}) == 0)

        # ── Appointment tomorrow 2 PM Denver ────────────────────────────────────
        appt_local = (datetime.now(TZ) + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
        r = await c.post(f"{API}/tasks/{uid}", headers=H, json={"title": "Meet Bud about the Bronco", "contact_id": cid, "due_date": appt_local.astimezone(timezone.utc).isoformat(),
                                                                 "has_time": True, "appointment_type": "appointment", "type": "appointment"})
        tid = r.json()["_id"]
        await db.tasks.update_one({"_id": ObjectId(tid)}, {"$set": {"invite_dirty_at": "cancel-auto"}})  # skip the auto invite for this test

        ok("hint regex catches 'can we do 3 instead'", bool(CHANGE_HINT.search("can we do 3 instead")))
        ok("hint regex catches 'can't make it'", bool(CHANGE_HINT.search("Something came up, I can't make it")))

        # ── Negative: confirmation is not a change ──────────────────────────────
        res = await detect_appointment_change(uid, cid, conv_id, "are we still on for 2 tomorrow?", "m0")
        ok("'still on for 2?' -> no change request", res is None, res)

        # ── Reschedule via the REAL inbound webhook ─────────────────────────────
        r = await c.post(f"{API}/webhooks/twilio/incoming", data={"From": PHONE, "To": rep_num, "Body": "can we do 3 instead?", "MessageSid": f"SMtest{int(time.time())}"})
        ok("webhook accepted", r.status_code == 200, r.status_code)
        ch = None
        for _ in range(30):
            ch = await db.appointment_changes.find_one({"task_id": tid, "status": "pending"})
            if ch:
                break
            await asyncio.sleep(2)
        ok("change request created from inbound text", ch is not None)
        ok("action reschedule -> same day 3:00 PM", ch["action"] == "reschedule" and ch["new_due"].replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%H:%M") == "15:00"
           and ch["new_due"].replace(tzinfo=timezone.utc).astimezone(TZ).date() == appt_local.date(), (ch["old_label"], ch["new_label"]))
        ok("no duplicate appointment task was extracted", await db.tasks.count_documents({"contact_id": cid, "status": {"$ne": "dismissed"}}) == 1)
        t = await db.tasks.find_one({"_id": ObjectId(tid)})
        ok("task flagged pending_change_id", t.get("pending_change_id") == str(ch["_id"]))
        n = await db.notifications.find_one({"change_id": str(ch["_id"])})
        ok("rep notification created", n and "wants to move" in n["title"] and "3:00 PM" in n["title"], (n or {}).get("title"))
        conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
        ok("conversation marked needs_assistance", conv.get("needs_assistance") is True)

        r = await c.get(f"{API}/tasks/{uid}/changes", headers=H, params={"conversation_id": conv_id, "status": "pending"})
        ok("GET /changes lists it", r.status_code == 200 and len(r.json()["changes"]) == 1 and r.json()["changes"][0]["id"] == str(ch["_id"]), r.text[:200])
        r = await c.get(f"{API}/tasks/{uid}/contact/{cid}", headers=H)
        st = [x for x in r.json()["tasks"] if x["_id"] == tid][0]
        ok("contact tasks include pending_change", st.get("pending_change", {}).get("new_label") == ch["new_label"], st.get("pending_change"))

        # held Jessi draft should be dropped on approve
        await db.ai_reply_queue.insert_one({"conversation_id": conv_id, "user_id": uid, "contact_id": cid, "status": "pending", "requires_approval": True,
                                            "body": "Let me check with Forest on 3.", "created_at": datetime.utcnow(), "send_at": datetime.utcnow()})
        r = await c.post(f"{API}/tasks/{uid}/changes/{ch['_id']}/approve", headers=H, json={})
        ok("approve 200", r.status_code == 200 and r.json().get("success"), r.text[:200])
        t = await db.tasks.find_one({"_id": ObjectId(tid)})
        ok("task moved to 3:00 PM", t["due_date"].replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%H:%M") == "15:00" and not t.get("pending_change_id"))
        m = await db.messages.find_one({"task_id": tid, "kind": "calendar_invite"}, sort=[("timestamp", -1)])
        ok("customer got the 'moved to' calendar update text", m and "moved to" in m["content"] and "3:00 PM" in m["content"], (m or {}).get("content"))
        q = await db.ai_reply_queue.find_one({"conversation_id": conv_id})
        ok("Jessi's held draft dropped (no double text)", q["status"] == "cancelled", q["status"])
        conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
        ok("needs_assistance cleared", conv.get("needs_assistance") is False)
        n = await db.notifications.find_one({"change_id": str(ch["_id"])})
        ok("notification dismissed", n.get("dismissed") is True)
        chd = await db.appointment_changes.find_one({"_id": ch["_id"]})
        ok("change marked approved", chd["status"] == "approved")
        r = await c.post(f"{API}/tasks/{uid}/changes/{ch['_id']}/approve", headers=H, json={})
        ok("double approve -> 400", r.status_code == 400)

        # ── Decline path: 'push it to Friday' ───────────────────────────────────
        res = await detect_appointment_change(uid, cid, conv_id, "can we push it to Friday?", "m2")
        ok("'push it to Friday' -> reschedule same clock time", res and res["action"] == "reschedule" and res["new_label"] and "Fri" in res["new_label"] and "3:00 PM" in res["new_label"], res and res["new_label"])
        r = await c.post(f"{API}/tasks/{uid}/changes/{res['id']}/decline", headers=H)
        ok("decline 200", r.status_code == 200)
        t = await db.tasks.find_one({"_id": ObjectId(tid)})
        ok("declined: task untouched + flag cleared", t["due_date"].replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%H:%M") == "15:00" and not t.get("pending_change_id"))

        # ── Running late (only meaningful when the appointment is imminent) ────────
        soon = (datetime.now(timezone.utc) + timedelta(minutes=40)).replace(second=0, microsecond=0)
        await db.tasks.update_one({"_id": ObjectId(tid)}, {"$set": {"due_date": soon}})
        res = await detect_appointment_change(uid, cid, conv_id, "running about 20 min late, sorry!", "m3")
        exp = (soon + timedelta(minutes=20)).astimezone(TZ).strftime("%-I:%M %p")
        ok(f"'running 20 min late' -> {exp}", res and res["new_label"] and exp in res["new_label"], res and res["new_label"])
        await db.appointment_changes.update_one({"_id": ObjectId(res["id"])}, {"$set": {"status": "declined"}})
        await db.tasks.update_one({"_id": ObjectId(tid)}, {"$unset": {"pending_change_id": ""}})

        # ── Cancel path ─────────────────────────────────────────────────────────
        res = await detect_appointment_change(uid, cid, conv_id, "Something came up, I can't make it. Sorry", "m4")
        ok("'can't make it' -> cancel request", res and res["action"] == "cancel", res and res["action"])
        r = await c.post(f"{API}/tasks/{uid}/changes/{res['id']}/approve", headers=H, json={})
        ok("approve cancel 200", r.status_code == 200 and r.json().get("action") == "cancel", r.text[:200])
        t = await db.tasks.find_one({"_id": ObjectId(tid)})
        ok("task taken off the books", t["status"] == "dismissed" and t.get("dismiss_reason") == "customer_cancelled")
        m = await db.messages.find_one({"task_id": tid, "kind": "appointment_cancelled"})
        ok("customer told it's cancelled", m and "off the books" in m["content"] and m["content"].startswith("No problem Bud"), (m or {}).get("content"))

        # ── No upcoming appointment -> nothing happens ─────────────────────────
        res = await detect_appointment_change(uid, cid, conv_id, "can we do 3 instead?", "m5")
        ok("no open appointment -> None", res is None)

        # cleanup
        await db.tasks.delete_many({"contact_id": cid}); await db.messages.delete_many({"contact_id": cid})
        await db.messages.delete_many({"conversation_id": conv_id}); await db.conversations.delete_one({"_id": ObjectId(conv_id)})
        await db.appointment_changes.delete_many({"contact_id": cid}); await db.notifications.delete_many({"contact_id": cid})
        await db.ai_reply_queue.delete_many({"conversation_id": conv_id}); await db.contact_events.delete_many({"contact_id": cid})
        await db.short_urls.delete_many({"link_type": "calendar_invite", "reference_id": tid}); await db.contacts.delete_one({"_id": ObjectId(cid)})
        print("\nALL PASSED")


asyncio.run(main())
