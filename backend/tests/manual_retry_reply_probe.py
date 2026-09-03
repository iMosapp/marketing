"""Probe: customer texts back while a voicemail retry is open -> retry closed, queued just-tried text cancelled, rep pinged.
Run: cd /app/backend && python tests/manual_retry_reply_probe.py   (no SMS; push to Forest is stubbed)"""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
from bson import ObjectId
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from routers.database import get_db
import routers.push_notifications as pn
from services import call_followup as cf

pushes = []
async def _fake_push(user_id, title, body, link=None, icon=None, *a, **k):
    pushes.append((title, body, link))
pn.send_push_to_user = _fake_push

async def main():
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"}, {"_id": 1})
    uid = str(forest["_id"])
    now = datetime.now(timezone.utc)
    c = await db.contacts.insert_one({"user_id": uid, "name": "Probe Retry", "first_name": "Probe", "phone": "+15005550021",
                                      "created_at": now, "call_retry": {"attempts": 2, "last_at": now, "last_outcome": "voicemail"}})
    cid = str(c.inserted_id)
    conv = await db.conversations.insert_one({"user_id": uid, "contact_id": cid, "contact_name": "Probe Retry", "status": "active", "created_at": now})
    convid = str(conv.inserted_id)
    t = await db.tasks.insert_one({"user_id": uid, "contact_id": cid, "type": "call", "auto_kind": "call_retry", "retry_attempt": 2,
                                   "title": "Try Probe again", "status": "pending", "completed": False, "due_date": now + timedelta(hours=1),
                                   "just_tried_sent_at": now - timedelta(minutes=5), "created_at": now})
    tid = str(t.inserted_id)
    ps = await db.campaign_pending_sends.insert_one({"user_id": uid, "contact_id": cid, "task_id": tid, "type": "direct_scheduled",
                                                     "status": "pending", "send_at": now + timedelta(hours=10), "campaign_name": "Just tried you", "created_at": now})
    try:
        # 1) no-op when nothing open for another contact
        r0 = await cf.on_customer_replied(uid, str(ObjectId()), convid, "hi")
        assert r0 == {"closed": 0}, r0
        # 2) real reply closes the retry
        r = await cf.on_customer_replied(uid, cid, convid, "Hey sorry I missed you, call me after 3")
        await asyncio.sleep(0.1)
        task = await db.tasks.find_one({"_id": t.inserted_id})
        send = await db.campaign_pending_sends.find_one({"_id": ps.inserted_id})
        contact = await db.contacts.find_one({"_id": c.inserted_id}, {"call_retry": 1})
        notif = await db.notifications.find_one({"user_id": uid, "type": "call_retry_replied", "contact_id": cid})
        ev = await db.contact_events.find_one({"contact_id": cid, "event_type": "call_retry_replied"})
        assert r["closed"] == 1 and r["cancelled_texts"] == 1 and r["just_tried"] is True, r
        assert task["completed"] is True and task["completed_via"] == "customer_replied", task
        assert send["status"] == "cancelled" and send["cancel_reason"] == "customer_replied", send
        assert contact.get("call_retry") is None, contact
        assert notif and notif["title"] == "Probe replied to your just-tried text", notif
        assert notif["conversation_id"] == convid
        assert ev, "event missing"
        assert pushes and pushes[0][0] == "Probe replied to your just-tried text" and pushes[0][2] == f"/thread/{convid}", pushes
        # 3) idempotent: second reply is a no-op
        r2 = await cf.on_customer_replied(uid, cid, convid, "thanks")
        assert r2 == {"closed": 0}, r2
        # 4) analytics endpoint counts it as 'replied'
        from fastapi import Request
        from routers.lead_intake import call_retry_outcomes
        from routers.auth import create_jwt_token
        tok = create_jwt_token(uid, "super_admin")
        scope = {"type": "http", "headers": [(b"authorization", f"Bearer {tok}".encode())] if tok else [], "query_string": b"", "path": "/x"}
        if tok:
            res = await call_retry_outcomes(Request(scope), None, 7)
            me = next((x for x in res["reps"] if x["user_id"] == uid), None)
            assert me and me["replied"] >= 1 and me["just_tried"] >= 1, (res["totals"], me)
            print("analytics totals:", res["totals"])
        print("PASS", r, pushes[0])
    finally:
        await db.tasks.delete_one({"_id": t.inserted_id})
        await db.campaign_pending_sends.delete_one({"_id": ps.inserted_id})
        await db.conversations.delete_one({"_id": conv.inserted_id})
        await db.contacts.delete_one({"_id": c.inserted_id})
        await db.notifications.delete_many({"contact_id": cid})
        await db.contact_events.delete_many({"contact_id": cid})

asyncio.run(main())
