"""Live Jessi actions: call, dictated note, tags, mark sold, finish/snooze reminders, contact facts, appointments, campaigns, card/review text.
Real DB (forest@imosapp.com), real LLM for the brain routing test, fake Twilio for the call."""
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import live_voice as lv  # noqa: E402
from services import live_actions as la  # noqa: E402
import routers.twilio_webhooks as tw  # noqa: E402

pytestmark = pytest.mark.asyncio
TAG = "QA LiveActions"


async def _seed(db):
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    uid = str(forest["_id"])
    now = datetime.now(timezone.utc)
    bud = {"_id": ObjectId(), "user_id": uid, "first_name": "Bud", "last_name": "QA-Live", "phone": "+15005550801", "status": "active", "tags": [TAG], "created_at": now, "updated_at": now}
    await db.contacts.insert_one(bud)
    camp = {"_id": ObjectId(), "user_id": uid, "name": "QA Sold Quarterly Check-In", "active": True, "trigger_tag": None, "type": "custom", "ai_enabled": False,
            "steps": [{"step": 1, "delay_days": 1, "message": "Hi {first_name}, checking in."}], "created_at": now}
    await db.campaigns.insert_one(camp)
    live = {"_id": ObjectId(), "live_id": "qa-live-actions", "user_id": uid, "mode": "assistant", "pending": None, "status": "open", "transcript": [], "delegations": [], "started_at": now}
    await db[lv.COLL].insert_one(live)
    return forest, bud, camp, live, now


async def _wipe(db, bud, camp, live, since):
    cid = str(bud["_id"])
    await db.contacts.delete_one({"_id": bud["_id"]})
    await db.voice_notes.delete_many({"contact_id": cid})
    await db.contact_events.delete_many({"contact_id": cid})
    await db.tasks.delete_many({"contact_id": cid})
    await db.appointments.delete_many({"contact_id": cid})
    await db.campaign_enrollments.delete_many({"contact_id": cid})
    await db.campaigns.delete_one({"_id": camp["_id"]})
    await db[lv.COLL].delete_one({"_id": live["_id"]})
    await db.tags.delete_many({"user_id": live["user_id"], "name": {"$regex": "^harley riders$", "$options": "i"}, "created_at": {"$gte": since - timedelta(seconds=5)}})
    await db.pending_calls.delete_many({"contact_id": cid})


async def test_note_tag_facts_and_reminders():
    db = get_db()
    forest, bud, camp, live, since = await _seed(db)
    cid = str(bud["_id"])
    try:
        said, opened = await la.add_note(db, forest, {"name": "Bud QA-Live", "text": "He is shopping for a pontoon boat this spring"}, None, live)
        assert said.startswith("Saved on Bud") and opened["kind"] == "contact", said
        note = await db.voice_notes.find_one({"contact_id": cid})
        assert note and note["source"] == "jessi" and note["kind"] == "memo" and "pontoon" in note["transcript"] and not note.get("audio_url")
        assert await db.contact_events.find_one({"contact_id": cid, "event_type": "voice_note", "title": "Note dictated to Jessi"})

        said, _ = await la.tag_person(db, forest, {"name": "Bud QA-Live", "tag": "Harley rider", "action": "add"}, None, live)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert said.startswith("Tagged Bud as Harley rider") and any(t.lower().startswith("harley rider") for t in c["tags"]), (said, c["tags"])
        said, _ = await la.tag_person(db, forest, {"name": "Bud QA-Live", "tag": "harley riders", "action": "add"}, None, live)
        assert "already tagged" in said, said
        said, _ = await la.tag_person(db, forest, {"name": "Bud QA-Live", "tag": "Harley riders", "action": "remove"}, None, live)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert said.startswith("Took Harley rider") and not any("harley" in t.lower() for t in c["tags"]), (said, c["tags"])

        said, _ = await la.update_contact(db, forest, {"name": "Bud QA-Live", "field": "birthday", "value": "03-03"}, None, live)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert "birthday is set to March 3" in said and c["birthday"].month == 3 and c["birthday"].day == 3 and c["birthday"].year == 1900, (said, c.get("birthday"))
        said, _ = await la.update_contact(db, forest, {"name": "Bud QA-Live", "field": "email", "value": "bud at example dot com"}, None, live)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert c["email"] == "bud@example.com", said
        said, _ = await la.update_contact(db, forest, {"name": "Bud QA-Live", "field": "personal", "key": "family", "value": "wife Amy, kids Max and Ava"}, None, live)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert c["personal_details"]["family"] == "wife Amy, kids Max and Ava", (said, c.get("personal_details"))
        said, _ = await la.update_contact(db, forest, {"name": "Bud QA-Live", "field": "vehicle_interest", "value": "2025 Silverado"}, None, live)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert c["vehicle_interest"] == "2025 Silverado" and "looking at 2025 Silverado" in said

        # reminder -> done; second reminder -> snooze
        said, task = await lv._reminder(db, forest, {"name": "Bud QA-Live", "when_iso": (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0).isoformat(), "note": "Call Bud about the trade", "action": "call"}, None, live)
        live["last_task_id"] = str(task["_id"] if task.get("_id") else task.get("id"))
        said, opened = await la.finish_task(db, forest, {"name": "Bud QA-Live", "action": "done"}, None, live)
        t = await db.tasks.find_one({"contact_id": cid})
        assert said.startswith("Done.") and "Call Bud about the trade" in said and t["status"] == "completed", (said, t.get("status"))
        said, task2 = await lv._reminder(db, forest, {"name": "Bud QA-Live", "when_iso": (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0).isoformat(), "note": "Text Bud the numbers", "action": "text"}, None, live)
        live["last_task_id"] = str(task2["_id"] if task2.get("_id") else task2.get("id"))
        friday = (datetime.now() + timedelta(days=5)).replace(hour=9, minute=0, second=0, microsecond=0)
        said, opened = await la.finish_task(db, forest, {"name": "Bud QA-Live", "action": "snooze", "until_iso": friday.isoformat()}, None, live)
        t2 = await db.tasks.find_one({"contact_id": cid, "title": "Text Bud the numbers"})
        assert said.startswith("Snoozed") and t2["status"] == "snoozed" and abs((t2["due_date"].replace(tzinfo=timezone.utc) - friday.astimezone(timezone.utc)).total_seconds()) < 3600 * 12, (said, t2)
        live["last_task_id"] = None
        said, _ = await la.finish_task(db, forest, {"name": "Bud QA-Live", "action": "done", "which": "the numbers text"}, None, live)
        assert "Text Bud the numbers" in said and said.startswith("Done."), said
        await db.tasks.delete_many({"contact_id": cid})
        said, _ = await la.finish_task(db, forest, {"name": "Bud QA-Live", "action": "done"}, None, live)
        assert "no open reminder" in said, said
    finally:
        await _wipe(db, bud, camp, live, since)


async def test_sold_appointment_enroll_pending_then_yes():
    db = get_db()
    forest, bud, camp, live, since = await _seed(db)
    cid = str(bud["_id"])
    try:
        said, pending, opened = await la.mark_sold(db, forest, {"name": "Bud QA-Live", "title": "2024 Chevy Tahoe", "date_iso": "", "notes": "traded a 2018 Silverado"}, None, live)
        assert pending["type"] == "sold" and "Mark Bud sold: 2024 Chevy Tahoe, today, traded a 2018 Silverado" in said and "Say yes" in said, said
        said, opened = await la.sold_now(db, forest, pending)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert said.startswith("Done. Bud QA-Live is marked sold: 2024 Chevy Tahoe") and "first purchase" in said, said
        assert c["purchase_history"][0]["title"] == "2024 Chevy Tahoe" and c["purchase_history"][0]["notes"] == "traded a 2018 Silverado" and "Sold" in c["tags"], c

        said, pending, _ = await la.book_appointment(db, forest, {"name": "Bud QA-Live", "when_iso": "", "title": ""}, None, live)
        assert pending is None and "When should I put Bud down" in said, said
        when = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
        said, pending, _ = await la.book_appointment(db, forest, {"name": "Bud QA-Live", "when_iso": when.isoformat(), "title": "Test drive with Bud", "duration_min": 45, "location": "the store"}, None, live)
        assert pending["type"] == "appointment" and "Test drive with Bud" in said and "at 10:00 AM, 45 minutes, at the store" in said, said
        said, opened = await la.appointment_now(db, forest, pending)
        appt = await db.appointments.find_one({"contact_id": cid})
        task = await db.tasks.find_one({"contact_id": cid, "type": "appointment"})
        assert said.startswith("Booked. Test drive with Bud") and "text Bud the confirmation" in said, said
        assert appt and appt["title"] == "Test drive with Bud" and task and task["has_time"] and opened["kind"] == "task", (appt, task)

        said, pending, _ = await la.enroll_campaign(db, forest, {"name": "Bud QA-Live", "campaign": "the sold quarterly plan"}, None, live)
        assert pending and pending["type"] == "enroll" and pending["campaign"] == camp["name"] and "1 touch" in said, said
        said, opened = await la.enroll_now(db, forest, pending)
        enr = await db.campaign_enrollments.find_one({"contact_id": cid, "campaign_id": str(camp["_id"])})
        assert said.startswith("Done. Bud QA-Live is on QA Sold Quarterly") and enr and enr["status"] == "active", (said, enr)
        said, pending, _ = await la.enroll_campaign(db, forest, {"name": "Bud QA-Live", "campaign": "sold quarterly"}, None, live)
        assert pending is None and "already on" in said, said
        said, pending, _ = await la.enroll_campaign(db, forest, {"name": "Bud QA-Live", "campaign": "the moon landing drip"}, None, live)
        assert pending is None and "Which campaign" in said, said
    finally:
        await _wipe(db, bud, camp, live, since)


async def test_call_and_card(monkeypatch):
    db = get_db()
    forest, bud, camp, live, since = await _seed(db)
    calls = []

    async def fake_call(rep_user_id, customer_phone, contact_id="", conversation_id="", task_id=""):
        calls.append((rep_user_id, customer_phone, contact_id, task_id))
        return {"success": True, "call_sid": "CAqa", "status": "queued"}
    monkeypatch.setattr(tw, "place_click_to_call", fake_call)
    try:
        _, task = await lv._reminder(db, forest, {"name": "Bud QA-Live", "when_iso": datetime.now().isoformat(), "note": "Call Bud back", "action": "call"}, None, live)
        said, opened = await la.call_person(db, forest, {"name": "Bud QA-Live"}, None, live)
        if forest.get("phone") and (forest.get("twilio_number") or forest.get("mvpline_number")):
            assert said.startswith("Calling Bud now") and "press 1" in said and "Call Bud back" in said, said
            assert calls and calls[0][1] == "+15005550801" and calls[0][2] == str(bud["_id"]) and calls[0][3] == str(task["_id"] if task.get("_id") else task.get("id")), calls
        else:
            assert "cell number" in said or "business number" in said, said
        assert opened["kind"] == "contact"

        said, pending, opened = await la.send_card(db, forest, {"name": "Bud QA-Live", "what": "card"}, None, live)
        assert pending["type"] == "send_text" and f"/card/{forest['_id']}" in pending["content"] and "Hi Bud" in pending["content"] and opened["kind"] == "thread", pending
        said, pending, _ = await la.send_card(db, forest, {"name": "Bud QA-Live", "what": "review"}, None, live)
        store = await db.stores.find_one({"_id": ObjectId(forest["store_id"])}, {"slug": 1}) if ObjectId.is_valid(str(forest.get("store_id") or "")) else None
        if store and store.get("slug"):
            assert pending and f"/review/{store['slug']}?sp={forest['_id']}" in pending["content"] and "review" in pending["content"].lower(), pending
        else:
            assert pending is None and "review page" in said, said
    finally:
        await _wipe(db, bud, camp, live, since)


async def test_brain_routes_and_confirms(monkeypatch):
    """Real brain: the spoken asks land on the new tools, and a bare yes runs the pending sale."""
    db = get_db()
    forest, bud, camp, live, since = await _seed(db)
    cid = str(bud["_id"])

    async def fake_call(*a, **k):
        return {"success": True, "call_sid": "CAqa", "status": "queued"}
    monkeypatch.setattr(tw, "place_click_to_call", fake_call)
    try:
        cases = [("Call Bud QA-Live for me.", "call_person"), ("Add a note on Bud QA-Live: he's shopping for a pontoon boat this spring.", "add_note"),
                 ("Tag Bud QA-Live as a Harley rider.", "tag_person"), ("Bud QA-Live's birthday is March 3rd.", "update_contact"),
                 ("Set Bud QA-Live for a test drive Saturday at 10.", "book_appointment"), ("Send Bud QA-Live my card.", "send_card")]
        seen = {}
        for say, want in cases:
            live["pending"] = None
            r = await lv.delegate(db, live, forest, [{"role": "rep", "text": say}], "d")
            seen[say] = (r["tool"], r["content"][:90])
            assert r["tool"] == want, seen
        print("\nROUTES:", seen)
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert any("harley" in t.lower() for t in c["tags"]) and c.get("birthday") and c["birthday"].month == 3, c
        assert await db.voice_notes.find_one({"contact_id": cid, "source": "jessi"})
        # sold: read-back, then yes
        live["pending"] = None
        r = await lv.delegate(db, live, forest, [{"role": "rep", "text": "Mark Bud QA-Live sold, 2024 Tahoe, delivered today."}], "d")
        assert r["tool"] == "mark_sold" and r["pending"], r
        live["pending"] = (await db[lv.COLL].find_one({"_id": live["_id"]}))["pending"]
        r2 = await lv.delegate(db, live, forest, [{"role": "rep", "text": "Mark Bud QA-Live sold, 2024 Tahoe, delivered today."}, {"role": "assistant", "text": r["content"]}, {"role": "rep", "text": "Yes, do it."}], "d")
        c = await db.contacts.find_one({"_id": bud["_id"]})
        assert r2["tool"] == "confirm" and r2["content"].startswith("Done.") and c.get("purchase_history") and "Tahoe" in c["purchase_history"][0]["title"], (r2, c.get("purchase_history"))
    finally:
        await _wipe(db, bud, camp, live, since)
