"""Probe: auto "just tried you" text after a miss. Stubs the SMS send + push. Run: cd /app/backend && python tests/manual_auto_just_tried_probe.py"""
import asyncio, os, sys
from datetime import datetime, timezone
from bson import ObjectId
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from routers.database import get_db
import routers.push_notifications as pn
import routers.messages as msgs
from services import call_followup as cf

sent, pushes = [], []
async def _fake_send(user_id, payload):
    sent.append(payload); return {"status": "sent", "message_id": "probe"}
async def _fake_push(user_id, title, body, link=None, icon=None, *a, **k):
    pushes.append((title, body))
msgs.send_message_simple = _fake_send
pn.send_push_to_user = _fake_push
import services.lead_timing as lt
lt.window_status = lambda src, tz: {"inside": True, "opens_at": datetime.now(timezone.utc), "start": "8:00 AM", "end": "9:00 PM"}

async def main():
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"}, {"_id": 1, "call_retry_cadence": 1})
    uid = str(forest["_id"]); saved = forest.get("call_retry_cadence")
    now = datetime.now(timezone.utc)
    c = await db.contacts.insert_one({"user_id": uid, "name": "Auto Probe", "first_name": "Auto", "phone": "+15005550031", "created_at": now})
    cid = str(c.inserted_id)
    contact = await db.contacts.find_one({"_id": c.inserted_id})
    pending = {"conversation_id": None, "task_id": None, "customer_phone": "+15005550031"}
    try:
        # 1) auto off -> no text
        await db.users.update_one({"_id": forest["_id"]}, {"$set": {"call_retry_cadence": {**cf.DEFAULT_CADENCE, "auto_just_tried": False}}})
        r1 = await cf._on_missed(db, uid, contact, "Auto", pending, "voicemail", "probe", "CA1", now)
        assert r1["task_id"] and not sent, (r1, sent)
        t1 = await db.tasks.find_one({"_id": ObjectId(r1["task_id"])})
        assert not t1.get("just_tried_sent_at")
        # 2) auto on from miss #2 -> miss #1 already happened (attempt 1, no text); miss #2 sends once
        await db.users.update_one({"_id": forest["_id"]}, {"$set": {"call_retry_cadence": {**cf.DEFAULT_CADENCE, "auto_just_tried": True, "auto_just_tried_from": 2}}})
        contact = await db.contacts.find_one({"_id": c.inserted_id})
        r2 = await cf._on_missed(db, uid, contact, "Auto", pending, "no_answer", "probe", "CA2", now)
        assert r2["attempt"] == 2 and len(sent) == 1, (r2, sent)
        t2 = await db.tasks.find_one({"_id": ObjectId(r2["task_id"])})
        assert t2.get("just_tried_sent_at") and t2.get("just_tried_auto") is True, t2
        assert any("text sent" in p[1] for p in pushes), pushes
        ev = await db.contact_events.find_one({"contact_id": cid, "event_type": "just_tried_text"})
        assert ev and "auto-sent" in ev["title"], ev
        # 3) miss #3 in the same streak -> no second text
        contact = await db.contacts.find_one({"_id": c.inserted_id})
        r3 = await cf._on_missed(db, uid, contact, "Auto", pending, "voicemail", "probe", "CA3", now)
        assert r3["attempt"] == 3 and len(sent) == 1, (r3, len(sent))
        # 4) opted-out contact -> skipped, streak still tracked
        c2 = await db.contacts.insert_one({"user_id": uid, "name": "Opt Out", "first_name": "Opt", "phone": "+15005550032", "opted_out": True, "created_at": now})
        contact2 = await db.contacts.find_one({"_id": c2.inserted_id})
        await db.users.update_one({"_id": forest["_id"]}, {"$set": {"call_retry_cadence": {**cf.DEFAULT_CADENCE, "auto_just_tried": True, "auto_just_tried_from": 1}}})
        r4 = await cf._on_missed(db, uid, contact2, "Opt", pending, "voicemail", "probe", "CA4", now)
        assert r4["task_id"] and len(sent) == 1, (r4, len(sent))
        assert any("auto-text skipped" in p[1] for p in pushes), pushes
        # 5) normalize_cadence clamps
        n = cf.normalize_cadence({"auto_just_tried": "yes", "auto_just_tried_from": 99})
        assert n["auto_just_tried"] is True and n["auto_just_tried_from"] == 6, n
        print("PASS", sent[0]["content"][:60], "| pushes:", pushes)
        await db.tasks.delete_many({"contact_id": {"$in": [cid, str(c2.inserted_id)]}})
        await db.contacts.delete_one({"_id": c2.inserted_id})
        await db.contact_events.delete_many({"contact_id": str(c2.inserted_id)})
        await db.notifications.delete_many({"contact_id": str(c2.inserted_id)})
    finally:
        if saved is not None:
            await db.users.update_one({"_id": forest["_id"]}, {"$set": {"call_retry_cadence": saved}})
        else:
            await db.users.update_one({"_id": forest["_id"]}, {"$unset": {"call_retry_cadence": ""}})
        await db.tasks.delete_many({"contact_id": cid})
        await db.contacts.delete_one({"_id": c.inserted_id})
        await db.contact_events.delete_many({"contact_id": cid})
        await db.notifications.delete_many({"contact_id": cid})

asyncio.run(main())
