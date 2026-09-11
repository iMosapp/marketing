"""Seed demo shared inboxes on PREVIEW for UI testing (idempotent: wipes and recreates its own data).
Store: Forest's "i'M On social" (69a0b7095fddcede09591668). Members: QA manager + Activation Tester (+ Forest on Sales).
Phones are Twilio test-range numbers only. SMS / push / LLM are stubbed while seeding.

Usage:  cd /app/backend && python tests/seed_inbox_demo.py [--wipe]
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

TAG = "inbox-demo"
STORE = "69a0b7095fddcede09591668"
QA = "6a9b2b82cc6e7504dafc33f2"
TESTER = "6a978d68b8673c29063aa8b9"
FOREST = "69a0b7095fddcede09591667"
SALES_NUM, SERVICE_NUM = "+15005550200", "+15005550210"
CUSTOMERS = {"sales_open": "+15005550031", "sales_owned": "+15005550032", "service_open": "+15005550033"}


async def _stub():
    import emergentintegrations.llm.chat as llm
    import routers.push_notifications as pn
    import services.twilio_service as ts

    class _FakeChat:
        def __init__(self, *a, **k): pass
        def with_model(self, *a, **k): return self
        async def send_message(self, *a, **k): return "Happy to help, what are you looking for?"

    async def _sms(to_phone, message, media_urls=None, from_phone=None, **k):
        return {"success": True, "message_sid": "SMdemo", "mock": True}

    async def _push(*a, **k):
        return {"sent": 0}
    llm.LlmChat = _FakeChat
    pn.send_push_to_user = _push
    ts.send_sms = _sms


async def wipe(db):
    inbox_ids = [str(i["_id"]) async for i in db.shared_inboxes.find({"demo_tag": TAG}, {"_id": 1})]
    phones = list(CUSTOMERS.values())
    convs = [c async for c in db.conversations.find({"$or": [{"inbox_id": {"$in": inbox_ids}}, {"from_inbox_id": {"$in": inbox_ids}}, {"contact_phone": {"$in": phones}}]}, {"_id": 1, "contact_id": 1})]
    conv_ids = [str(c["_id"]) for c in convs]
    contact_ids = [c.get("contact_id") for c in convs if c.get("contact_id")]
    from bson import ObjectId
    await db.messages.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.notifications.delete_many({"$or": [{"conversation_id": {"$in": conv_ids}}, {"inbox_id": {"$in": inbox_ids}}]})
    await db.inbound_leads.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.lead_call_jobs.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.lead_deferred_actions.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.ai_reply_queue.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.conversations.delete_many({"_id": {"$in": [c["_id"] for c in convs]}})
    await db.contacts.delete_many({"$or": [{"_id": {"$in": [ObjectId(c) for c in contact_ids if ObjectId.is_valid(c)]}}, {"phone": {"$in": phones}}]})
    await db.contact_events.delete_many({"contact_id": {"$in": contact_ids}})
    await db.lead_sources.delete_many({"kind": "inbox_direct", "inbox_id": {"$in": inbox_ids}})
    await db.users.update_many({"shared_inbox_ids": {"$in": inbox_ids}}, {"$pull": {"shared_inbox_ids": {"$in": inbox_ids}}})
    await db.shared_inboxes.delete_many({"demo_tag": TAG})
    print(f"wiped {len(inbox_ids)} inboxes, {len(conv_ids)} conversations")


async def main():
    import routers.database as rdb
    db = rdb.get_db()
    await wipe(db)
    if "--wipe" in sys.argv:
        return
    await _stub()
    from services import inboxes as ib
    now = datetime.utcnow()
    base = {"store_id": STORE, "after_close": "move_to_rep", "close_tag": "Sold", "ai_mode": "auto_reply", "is_active": True,
            "demo_tag": TAG, "created_by": QA, "created_at": now, "updated_at": now, "daily_cap": 0}
    sales_id = (await db.shared_inboxes.insert_one({**base, "name": "Sales", "phone_number": SALES_NUM, "assigned_user_ids": [QA, TESTER, FOREST],
                                                    "routing": "jump_ball", "color": "#34C759", "icon": "car-sport",
                                                    "first_reply": "Thanks for texting Sales, {{first_name}}! Someone will be right with you."})).inserted_id
    service_id = (await db.shared_inboxes.insert_one({**base, "name": "Service", "phone_number": SERVICE_NUM, "assigned_user_ids": [QA, TESTER],
                                                      "routing": "round_robin", "color": "#5AC8FA", "icon": "construct", "first_reply": ""})).inserted_id
    for iid, members in ((sales_id, [QA, TESTER, FOREST]), (service_id, [QA, TESTER])):
        from bson import ObjectId
        await db.users.update_many({"_id": {"$in": [ObjectId(m) for m in members]}}, {"$addToSet": {"shared_inbox_ids": str(iid)}})
    sales = await db.shared_inboxes.find_one({"_id": sales_id})
    service = await db.shared_inboxes.find_one({"_id": service_id})
    await ib.ensure_direct_source(db, sales)
    await ib.ensure_direct_source(db, service)

    # Sales: up for grabs
    await ib.handle_inbound(db, sales, CUSTOMERS["sales_open"], "Hi, is the blue Tahoe on your lot still available?", [], [], "SMdemo1")
    # Sales: owned by the QA manager
    await ib.handle_inbound(db, sales, CUSTOMERS["sales_owned"], "Can I come by Saturday for a test drive?", [], [], "SMdemo2")
    owned = await db.conversations.find_one({"contact_phone": CUSTOMERS["sales_owned"], "inbox_id": str(sales_id)})
    qa = await db.users.find_one({"_id": __import__("bson").ObjectId(QA)})
    await ib.assign_conversation(db, owned, qa, QA)
    # Service: up for grabs with a handoff note
    await ib.handle_inbound(db, service, CUSTOMERS["service_open"], "My check engine light came on this morning", [], [], "SMdemo3")
    svc = await db.conversations.find_one({"contact_phone": CUSTOMERS["service_open"], "inbox_id": str(service_id)})
    tester = await db.users.find_one({"_id": __import__("bson").ObjectId(TESTER)})
    await ib.assign_conversation(db, svc, qa, TESTER)
    svc = await db.conversations.find_one({"_id": svc["_id"]})
    await ib.release_conversation(db, svc, tester, note="Needs a loaner, I'm off tomorrow")

    for c in await db.conversations.find({"inbox_id": {"$in": [str(sales_id), str(service_id)]}}).to_list(10):
        print(f"  conv {c['_id']} {c.get('inbox_name')} {c.get('contact_name')} owner={c.get('assigned_to')}")
    print(f"Sales inbox {sales_id}  Service inbox {service_id}")


if __name__ == "__main__":
    asyncio.run(main())
