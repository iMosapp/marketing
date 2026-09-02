"""Stubbed webhook simulation: a website lead replies to its intake text. Verifies the reply lands on
the LEAD conversation + contact (no duplicate 'Lead (xxxx)') and Jessi queues an auto reply.
All outbound side effects stubbed (push, Twilio SMS/calls, LLM). Preview only."""
import os, sys, asyncio
from datetime import datetime
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from bson import ObjectId

CONV = sys.argv[1]
SENT = []


class _FakeMessages:
    def create(self, **kw):
        SENT.append(kw)
        return type("M", (), {"sid": "SMfake", "status": "queued"})()


class _FakeClient:
    def __init__(self, *a, **k):
        self.messages = _FakeMessages()
        self.calls = type("C", (), {"create": lambda *a, **k: type("X", (), {"sid": "CAfake", "status": "queued"})()})()

    def __call__(self, *a, **k):
        return self


async def _fake_push(*a, **k):
    return {"sent": 0}


async def main():
    import twilio.rest
    twilio.rest.Client = _FakeClient
    import routers.push_notifications as pn
    pn.send_push_to_user = _fake_push
    import services.twilio_service as tw
    async def _fake_send_sms(to_phone, message, media_urls=None, from_phone=None):
        SENT.append({"to": to_phone, "from": from_phone, "body": message})
        return {"success": True, "mock": True, "message_sid": "SMfake"}
    tw.send_sms = _fake_send_sms
    import emergentintegrations.llm.chat as llm
    class _FakeChat:
        def __init__(self, *a, **k): pass
        def with_model(self, *a, **k): return self
        async def send_message(self, *a, **k): return "Thanks for reaching out, happy to help!"
    llm.LlmChat = _FakeChat

    from routers.database import get_db
    db = get_db()
    conv = await db.conversations.find_one({"_id": ObjectId(CONV)})
    print("lead conv before:", {k: conv.get(k) for k in ["contact_id", "rep_phone", "contact_phone", "ai_mode", "user_id"]})
    contacts_before = await db.contacts.count_documents({"phone": conv["contact_phone"]})
    convs_before = await db.conversations.count_documents({"contact_phone": conv["contact_phone"]})

    from routers import twilio_webhooks as wh
    class _Req:
        headers = {}
        url = type("U", (), {"path": "/api/webhooks/twilio/incoming"})()
        client = type("C", (), {"host": "127.0.0.1"})()
        async def form(self): return {}
    res = await wh.incoming_message(_Req(), From=conv["contact_phone"], To=conv["rep_phone"], Body="Yes I would like to hear more", MessageSid=f"SMprobe{ObjectId()}", NumMedia="0", MediaUrl0=None, MediaUrl1=None, MediaUrl2=None, MediaContentType0=None, MediaContentType1=None, MediaContentType2=None)
    await asyncio.sleep(3)

    contacts_after = await db.contacts.count_documents({"phone": conv["contact_phone"]})
    convs_after = await db.conversations.count_documents({"contact_phone": conv["contact_phone"]})
    msg = await db.messages.find_one({"conversation_id": CONV, "sender": "contact"}, sort=[("timestamp", -1)])
    queued = await db.ai_reply_queue.find({"conversation_id": CONV}).to_list(5)
    print("contacts for phone: before", contacts_before, "after", contacts_after, "| convs: before", convs_before, "after", convs_after)
    print("inbound msg on lead conv:", bool(msg), (msg or {}).get("content"))
    print("ai queue on lead conv:", [(q["status"], q.get("ai_mode_used"), q.get("body", "")[:40]) for q in queued])
    await db.ai_reply_queue.update_many({"conversation_id": CONV, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_probe"}})
    print("outbound stubs captured:", len(SENT))

asyncio.run(main())
