"""Stubbed inbound-text webhook: a customer stored with a FORMATTED phone "(500) 555-0184" texts the rep's number.
Verifies the webhook reuses that contact (no 'Lead (0184)' duplicate) and skips merged records.
All outbound side effects stubbed (push, Twilio, LLM). Cleans up. run: cd /app/backend && python tests/test_webhook_contact_match.py
"""
import sys, asyncio
from datetime import datetime, timezone
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from bson import ObjectId

FOREST = "69a0b7095fddcede09591667"
REP_PHONE = "+14352203414"
FROM = "+15005550184"


async def main():
    import twilio.rest
    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = type("M", (), {"create": lambda *a, **k: type("X", (), {"sid": "SMfake", "status": "queued"})()})()
            self.calls = type("C", (), {"create": lambda *a, **k: type("X", (), {"sid": "CAfake", "status": "queued"})()})()
    twilio.rest.Client = _FakeClient
    import routers.push_notifications as pn
    async def _fake_push(*a, **k): return {"sent": 0}
    pn.send_push_to_user = _fake_push
    import services.twilio_service as tw
    async def _fake_send_sms(*a, **k): return {"success": True, "mock": True, "message_sid": "SMfake"}
    tw.send_sms = _fake_send_sms
    import emergentintegrations.llm.chat as llm
    class _FakeChat:
        def __init__(self, *a, **k): pass
        def with_model(self, *a, **k): return self
        async def send_message(self, *a, **k): return "Thanks for reaching out!"
    llm.LlmChat = _FakeChat

    from routers.database import get_db
    db = get_db()
    now = datetime.now(timezone.utc)
    merged = await db.contacts.insert_one({"first_name": "Old", "last_name": "Merged", "phone": FROM, "user_id": FOREST, "status": "merged", "created_at": now})
    live = await db.contacts.insert_one({"first_name": "Webhook", "last_name": "Formatted", "phone": "(500) 555-0184", "user_id": FOREST,
                                         "status": "active", "created_at": now})
    ok = True
    try:
        from routers import twilio_webhooks as wh
        class _Req:
            headers = {}
            url = type("U", (), {"path": "/api/webhooks/twilio/incoming"})()
            client = type("C", (), {"host": "127.0.0.1"})()
            async def form(self): return {}
        await wh.incoming_message(_Req(), From=FROM, To=REP_PHONE, Body="Hey, is this Forest?", MessageSid=f"SMqa{ObjectId()}", NumMedia="0",
                                  MediaUrl0=None, MediaUrl1=None, MediaUrl2=None, MediaContentType0=None, MediaContentType1=None, MediaContentType2=None)
        await asyncio.sleep(2)
        rx = r"5\D*0\D*0\D*5\D*5\D*5\D*0\D*1\D*8\D*4\D*$"
        all_for_phone = await db.contacts.find({"phone": {"$regex": rx}}).to_list(20)
        new_ones = [c for c in all_for_phone if c["_id"] not in (merged.inserted_id, live.inserted_id)]
        conv = await db.conversations.find_one({"rep_phone": REP_PHONE, "contact_phone": FROM})
        msg = await db.messages.find_one({"conversation_id": str(conv["_id"]), "sender": "contact"}) if conv else None
        print("new contacts minted:", len(new_ones), [{k: c.get(k) for k in ("name","first_name","last_name","phone","user_id","source","status")} for c in new_ones])
        print("conversation contact_id == formatted live contact:", conv and conv.get("contact_id") == str(live.inserted_id))
        print("inbound message stored:", bool(msg))
        ok = not new_ones and conv and conv.get("contact_id") == str(live.inserted_id) and bool(msg)
        print("\nPASS" if ok else "\nFAIL")
    finally:
        ids = [merged.inserted_id, live.inserted_id] + [c["_id"] for c in (await db.contacts.find({"phone": {"$regex": r"5\D*0\D*0\D*5\D*5\D*5\D*0\D*1\D*8\D*4\D*$"}}).to_list(20))]
        cids = [str(i) for i in ids]
        await db.contacts.delete_many({"_id": {"$in": ids}})
        convs = await db.conversations.find({"contact_phone": FROM}).to_list(10)
        for cv in convs:
            await db.messages.delete_many({"conversation_id": str(cv["_id"])})
            await db.ai_reply_queue.delete_many({"conversation_id": str(cv["_id"])})
            await db.notifications.delete_many({"conversation_id": str(cv["_id"])})
        await db.conversations.delete_many({"contact_phone": FROM})
        await db.contact_events.delete_many({"contact_id": {"$in": cids}})
        await db.notifications.delete_many({"contact_id": {"$in": cids}})
        print("cleanup done")

asyncio.run(main())
