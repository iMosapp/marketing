"""Live test for customer calendar invites (text + email + public page + .ics + morning-of reminder).
Uses Twilio's 500-555 test range only (sends fail harmlessly on live creds) and Resend's delivered@resend.dev sink."""
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
HOST = API[:-4]
PHONE = "+15005550142"
EMAIL = "delivered@resend.dev"


def ok(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  {str(extra)[:220]}" if extra else ""))
    if not cond:
        sys.exit(1)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    from services.calendar_invite import send_customer_appointment_reminders, should_auto_invite, invite_eligible
    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as c:
        r = await c.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"})
        ok("login forest", r.status_code == 200, r.text[:100])
        tok = r.json()["token"]; uid = r.json()["user"].get("id") or r.json()["user"].get("_id")
        H = {"Authorization": f"Bearer {tok}"}
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"notification_settings.calendar_invites": True, "notification_settings.calendar_invite_reminder": True}})

        await db.contacts.delete_many({"phone": PHONE})
        cid = str((await db.contacts.insert_one({"user_id": uid, "first_name": "Cal", "last_name": "Tester", "phone": PHONE,
                                                 "email": EMAIL, "status": "active", "tags": [], "created_at": datetime.now(timezone.utc)})).inserted_id)
        due = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)  # 2 PM Denver (MDT)

        # A) manual booking -> auto invite (45s coalescing delay)
        r = await c.post(f"{API}/tasks/{uid}", headers=H, json={"title": "Meet Cal about the F-150", "contact_id": cid, "due_date": due.isoformat(),
                                                                 "has_time": True, "appointment_type": "appointment", "type": "appointment", "priority": "medium"})
        ok("create appointment", r.status_code == 200, r.text[:150])
        tid = r.json()["_id"]
        t0 = time.time()
        task = None
        while time.time() - t0 < 75:
            task = await db.tasks.find_one({"_id": ObjectId(tid)})
            if task.get("invite_attempted_at"):
                break
            await asyncio.sleep(3)
        ok("auto invite attempted after delay", bool(task and task.get("invite_attempted_at")), {k: task.get(k) for k in ("invite_sms_status", "invite_email_status")})
        ok("email invite delivered via Resend", task.get("invite_email_status") == "sent", task.get("invite_email_status"))
        ok("sms attempted from rep number (500-555 test number rejected by Twilio is expected)", task.get("invite_sms_status") is not None, task.get("invite_sms_status"))
        ok("invite_sent_at set + channels", task.get("invite_sent_at") and "email" in (task.get("invite_channels") or []), task.get("invite_channels"))
        ok("short link + token", task.get("invite_short_url") and task.get("invite_token"), task.get("invite_short_url"))
        msg = await db.messages.find_one({"task_id": tid, "kind": "calendar_invite"})
        ok("invite text logged in the thread", msg is not None and "add it to your calendar" in msg["content"], (msg or {}).get("content"))
        ok("text has no em dash", "—" not in msg["content"])
        conv = await db.conversations.find_one({"_id": ObjectId(msg["conversation_id"])})
        ok("conversation keyed on rep_phone + contact_phone (reply lands in thread)", conv and conv.get("rep_phone") == "+14352203414" and conv.get("contact_phone") == PHONE, {k: (conv or {}).get(k) for k in ("rep_phone", "contact_phone")})

        # B) public page + ics via short link
        code = task["invite_short_url"].rsplit("/", 1)[-1]
        r = await c.get(f"{HOST}/api/s/{code}")
        ok("short link serves interstitial 200", r.status_code == 200, r.status_code)
        loc = r.text.split('window.location.replace("')[1].split('"')[0] if 'window.location.replace("' in r.text else ""
        ok("interstitial redirects to public appt page", f"/api/public/appt/{task['invite_token']}" in loc, loc)
        ok("iMessage preview title is the appointment", "Your appointment with Forest" in r.text and "Tap to add it to your calendar" in r.text)
        r = await c.get(f"{HOST}/api/public/appt/{task['invite_token']}")
        ok("public page 200", r.status_code == 200, r.status_code)
        body = r.text
        ok("page says You're all set + rep + 2:00 PM", "You're all set" in body and "Forest" in body and "2:00 PM" in body, body[body.find("<h1"):body.find("<h1") + 120])
        ok("page has Apple/Google/other buttons", "Add to Apple Calendar" in body and "calendar.google.com" in body and 'download="appointment.ics"' in body)
        ok("page has sms: link to rep number", 'href="sms:+14352203414"' in body)
        r = await c.get(f"{HOST}/api/public/appt/{task['invite_token']}.ics")
        ok("ics 200 text/calendar", r.status_code == 200 and r.headers["content-type"].startswith("text/calendar"), r.headers.get("content-type"))
        ics = r.text
        ok("ics has VEVENT/DTSTART/SUMMARY/UID", all(k in ics for k in ("BEGIN:VEVENT", f"DTSTART:{due.strftime('%Y%m%dT%H%M%SZ')}", "SUMMARY:Appointment with Forest", f"UID:appt-{tid}@imonsocial.com", "SEQUENCE:0")), ics[:300])
        r = await c.get(f"{HOST}/api/public/appt/nope-not-a-token")
        ok("unknown token -> 404 friendly page", r.status_code == 404 and "no longer on the books" in r.text)

        # C) reschedule -> update text + SEQUENCE bump
        new_due = due + timedelta(hours=1)
        r = await c.patch(f"{API}/tasks/{uid}/{tid}", headers=H, json={"action": "edit", "due_date": new_due.isoformat()})
        ok("edit due_date", r.status_code == 200, r.text[:120])
        t0 = time.time()
        while time.time() - t0 < 75:
            task = await db.tasks.find_one({"_id": ObjectId(tid)})
            if task.get("invite_last_reason") == "updated":
                break
            await asyncio.sleep(3)
        ok("update invite sent after reschedule", task.get("invite_last_reason") == "updated" and task.get("invite_sequence") == 1, {k: task.get(k) for k in ("invite_last_reason", "invite_sequence")})
        msgs = await db.messages.find({"task_id": tid, "kind": "calendar_invite"}).to_list(10)
        ok("second text says moved to new time", len(msgs) == 2 and any("moved to" in m["content"] and "3:00 PM" in m["content"] for m in msgs), [m["content"][:90] for m in msgs])
        r = await c.get(f"{HOST}/api/public/appt/{task['invite_token']}.ics")
        ok("ics SEQUENCE:1 + new DTSTART", "SEQUENCE:1" in r.text and f"DTSTART:{new_due.strftime('%Y%m%dT%H%M%SZ')}" in r.text)
        r = await c.get(f"{HOST}/api/public/appt/{task['invite_token']}")
        ok("page eyebrow now Updated appointment", "Updated appointment" in r.text)

        # D) manual resend endpoint
        r = await c.post(f"{API}/tasks/{uid}/{tid}/send-invite", headers=H)
        ok("POST send-invite 200", r.status_code == 200 and r.json().get("success"), r.text[:160])
        ok("send-invite returns channels + when", "email" in r.json().get("channels", []) and "3:00 PM" in r.json().get("when", ""), r.json())
        r = await c.get(f"{API}/tasks/{uid}/contact/{cid}", headers=H)
        st = [t for t in r.json()["tasks"] if t["_id"] == tid][0]
        ok("contact tasks API exposes invite_sent_at + invite_channels", isinstance(st.get("invite_sent_at"), str) and st.get("invite_channels"), {k: st.get(k) for k in ("invite_sent_at", "invite_channels")})

        # E) rep toggle off -> auto invite skipped; manual still works (force)
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"notification_settings.calendar_invites": False}})
        r = await c.post(f"{API}/tasks/{uid}", headers=H, json={"title": "Second appt", "contact_id": cid, "due_date": (due + timedelta(days=1)).isoformat(),
                                                                 "has_time": True, "appointment_type": "appointment", "type": "appointment"})
        tid2 = r.json()["_id"]
        await asyncio.sleep(50)
        t2 = await db.tasks.find_one({"_id": ObjectId(tid2)})
        ok("toggle off -> no invite sent", not t2.get("invite_sent_at") and not t2.get("invite_attempted_at"), {k: t2.get(k) for k in ("invite_sent_at", "invite_attempted_at")})
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"notification_settings.calendar_invites": True}})

        # F) not eligible: no time / call type / text-extracted source
        ok("no-time appointment not eligible", not invite_eligible({"appointment_type": "appointment", "has_time": False, "contact_id": cid, "due_date": due}))
        ok("call task not eligible", not invite_eligible({"appointment_type": "call", "has_time": True, "contact_id": cid, "due_date": due}))
        ok("text-extracted appointment waits for rep tap", not should_auto_invite({"appointment_type": "appointment", "has_time": True, "contact_id": cid, "due_date": due, "source": "text_extraction"}))
        ok("call-extracted appointment auto-sends", should_auto_invite({"appointment_type": "appointment", "has_time": True, "contact_id": cid, "due_date": due, "source": "call_extraction"}))
        r = await c.post(f"{API}/tasks/{uid}", headers=H, json={"title": "Call Cal", "contact_id": cid, "due_date": due.isoformat(), "has_time": True, "appointment_type": "call", "type": "appointment"})
        tid_call = r.json()["_id"]
        r = await c.post(f"{API}/tasks/{uid}/{tid_call}/send-invite", headers=H)
        ok("send-invite on a call task -> 400", r.status_code == 400, r.text[:120])

        # G) morning-of reminder job (Denver tz fallback since forest tz=UTC)
        tz = ZoneInfo("America/Denver")
        now_local = datetime.now(tz)
        if now_local.hour < 8:
            print("SKIP reminder window test (before 8 AM Denver)")
        else:
            appt_local = now_local + timedelta(hours=2)
            if appt_local.date() != now_local.date():
                print("SKIP reminder test (appointment would roll to tomorrow)")
            else:
                r = await c.post(f"{API}/tasks/{uid}", headers=H, json={"title": "Today appt", "contact_id": cid, "due_date": appt_local.astimezone(timezone.utc).isoformat(),
                                                                         "has_time": True, "appointment_type": "appointment", "type": "appointment"})
                tid3 = r.json()["_id"]
                r = await c.post(f"{API}/tasks/{uid}", headers=H, json={"title": "Booked yesterday appt", "contact_id": cid, "due_date": (appt_local + timedelta(minutes=30)).astimezone(timezone.utc).isoformat(),
                                                                         "has_time": True, "appointment_type": "appointment", "type": "appointment"})
                tid4 = r.json()["_id"]
                await db.tasks.update_one({"_id": ObjectId(tid4)}, {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(days=1), "invite_dirty_at": "x"}})
                await db.tasks.update_one({"_id": ObjectId(tid3)}, {"$set": {"invite_dirty_at": "x"}})  # cancel pending auto-invites for these two
                n = await send_customer_appointment_reminders()
                t3 = await db.tasks.find_one({"_id": ObjectId(tid3)}); t4 = await db.tasks.find_one({"_id": ObjectId(tid4)})
                ok("booked-today appointment skipped", t3.get("customer_reminder_skipped") == "booked_today" and not t3.get("customer_reminder_status"), {k: t3.get(k) for k in ("customer_reminder_skipped", "customer_reminder_status")})
                ok("booked-yesterday appointment reminded (attempted)", t4.get("customer_reminder_sent_at") is not None and t4.get("customer_reminder_status"), t4.get("customer_reminder_status"))
                rm = await db.messages.find_one({"task_id": tid4, "kind": "appointment_reminder"})
                ok("reminder text logged: Good morning + today", rm and rm["content"].startswith("Good morning Cal") and "today" in rm["content"], (rm or {}).get("content"))
                n2 = await send_customer_appointment_reminders()
                t4b = await db.tasks.find_one({"_id": ObjectId(tid4)})
                ok("reminder not sent twice", t4b.get("customer_reminder_sent_at") == t4.get("customer_reminder_sent_at"))

        # cleanup
        ids = [ObjectId(t["_id"]) for t in await db.tasks.find({"contact_id": cid}, {"_id": 1}).to_list(50)]
        await db.tasks.delete_many({"_id": {"$in": ids}})
        await db.messages.delete_many({"contact_id": cid})
        await db.contact_events.delete_many({"contact_id": cid})
        await db.conversations.delete_many({"contact_id": cid})
        await db.short_urls.delete_many({"link_type": "calendar_invite", "reference_id": {"$in": [str(i) for i in ids]}})
        await db.contacts.delete_one({"_id": ObjectId(cid)})
        print("\nALL PASSED")


asyncio.run(main())
