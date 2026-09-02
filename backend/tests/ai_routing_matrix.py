"""AI routing regression matrix - runs queue_ai_reply against a throwaway user/contact/conversation.

Usage:  cd /app/backend && python tests/ai_routing_matrix.py
No real SMS: assigned user has no Twilio number, contact uses Twilio's magic test number,
every queued item is cancelled immediately, LLM + push are stubbed.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

PUSHES = []


class _FakeChat:
    def __init__(self, *a, **k): pass
    def with_model(self, *a, **k): return self
    async def send_message(self, *a, **k): return "Sounds good, see you then!"


async def _fake_push(user_id, title, body, link=None, icon=None, *a, **k):
    PUSHES.append({"user_id": user_id, "title": title, "body": body})
    return {"sent": 0}


async def main():
    import routers.database as rdb
    db = rdb.get_db()
    import routers.ai_reply as ar
    import emergentintegrations.llm.chat as llm
    llm.LlmChat = _FakeChat
    import routers.push_notifications as pn
    pn.send_push_to_user = _fake_push

    uid = (await db.users.insert_one({"name": "QA Routing Rep", "email": f"qa-routing-{ObjectId()}@test.local",
                                      "role": "user", "status": "active", "created_at": datetime.utcnow()})).inserted_id
    cid = (await db.contacts.insert_one({"user_id": str(uid), "first_name": "QA", "last_name": "Tester",
                                         "name": "QA Tester", "phone": "+15005550006", "tags": [],
                                         "created_at": datetime.utcnow()})).inserted_id
    conv_id = (await db.conversations.insert_one({"user_id": str(uid), "contact_id": str(cid), "contact_phone": "+15005550006",
                                                  "ai_mode": "auto_reply", "ai_enabled": True, "status": "active",
                                                  "created_at": datetime.utcnow()})).inserted_id
    uid, cid, conv = str(uid), str(cid), str(conv_id)

    async def reset(prev_msgs=(), keep_state=False):
        if not keep_state:
            await db.conversations.update_one({"_id": conv_id}, {"$set": {
                "needs_assistance": False, "unanswered_customer_replies": 0, "ai_paused_for_human": False}})
            await db.ai_reply_queue.update_many({"conversation_id": conv}, {"$set": {"status": "cancelled", "cancel_reason": "qa"}})
            await db.messages.delete_many({"conversation_id": conv})
            await db.notifications.delete_many({"conversation_id": conv})
        t = datetime.utcnow() - timedelta(minutes=5)
        for sender, content in prev_msgs:
            await db.messages.insert_one({"conversation_id": conv, "sender": sender, "content": content, "timestamp": t})
            t += timedelta(seconds=30)
        PUSHES.clear()

    async def fire(text):
        await db.messages.insert_one({"conversation_id": conv, "sender": "contact", "content": text, "timestamp": datetime.utcnow()})
        res = await ar.queue_ai_reply(contact_id=cid, conversation_id=conv, enrollment_id="conversation_direct", campaign_id="",
                                      assigned_user_id=uid, incoming_message=text, ai_assist_mode="auto_reply", reply_count=1)
        c = await db.conversations.find_one({"_id": conv_id})
        notifs = await db.notifications.find({"conversation_id": conv}).to_list(50)
        await db.notifications.delete_many({"conversation_id": conv})
        pending = await db.ai_reply_queue.count_documents({"conversation_id": conv, "status": "pending"})
        await db.ai_reply_queue.update_many({"conversation_id": conv, "status": "pending"},
                                            {"$set": {"status": "cancelled", "cancel_reason": "qa"}}) if not res else None
        outcome = "silent" if res is None else ("pause" if res.get("hot_topic_escalation") else
                                                 ("approval" if res.get("requires_approval") else "auto"))
        return {"outcome": outcome, "paused": bool(c.get("ai_paused_for_human")), "waiting": bool(c.get("needs_assistance")),
                "pushes": len(PUSHES), "notifs": len(notifs), "pending": pending}

    results = []

    def check(name, got, **exp):
        bad = {k: (got.get(k), v) for k, v in exp.items() if got.get(k) != v}
        results.append((name, not bad, got, bad))

    # 1 General chat -> full auto
    await reset(); check("general chat", await fire("Hey, how's it going today?"), outcome="auto", paused=False, waiting=False, pushes=0)
    # 2 Pricing -> brief reply + pause + waiting + 1 push
    await reset(); check("pricing question", await fire("How much is the Tacoma?"), outcome="pause", paused=True, waiting=True, pushes=1)
    # 3 While paused -> silent, still waiting
    check("paused stays silent", await fire("Hello? anyone there"), outcome="silent", paused=True, waiting=True)
    # 4 Fact words outside old escalation list
    await reset(); check("mileage question", await fire("What's the mileage on it?"), outcome="pause", paused=True)
    await reset(); check("lease question", await fire("Can I lease it instead?"), outcome="pause", paused=True)
    await reset(); check("monthly payment", await fire("What would the monthly payment be?"), outcome="pause", paused=True)
    # 5 False positives (substring bugs) -> must stay auto
    await reset(); check("'having' not vin", await fire("I'm having a great day, thanks!"), outcome="auto", paused=False, waiting=False)
    await reset(); check("'Kevin' not vin", await fire("Kevin here, just saying hi"), outcome="auto", paused=False)
    await reset(); check("'driving' not vin", await fire("I was driving by yesterday"), outcome="auto", paused=False)
    await reset(); check("'April' not apr", await fire("I'm looking to buy in April"), outcome="auto", paused=False)
    await reset(); check("'please' not lease", await fire("Yes please, that would be great"), outcome="auto", paused=False)
    # 6 Scheduling -> draft held for approval, waiting, exactly ONE push + ONE notification
    await reset(); check("strong scheduling", await fire("Can I come in tomorrow at 6?"), outcome="approval", paused=False, waiting=True, pushes=1, notifs=1)
    await reset(); check("'please' + time still scheduling", await fire("Tomorrow at 6 please"), outcome="approval", paused=False, waiting=True)
    await reset(); check("day + clock = scheduling", await fire("Sounds good, see you Saturday at 10am"), outcome="approval", waiting=True)
    await reset(); check("number w/o day stays auto", await fire("I have 2 kids and love the space"), outcome="auto", waiting=False)
    await reset(); await fire("How much is the Tacoma?")
    check("'ok thanks' while paused stays waiting", await fire("ok thanks"), outcome="silent", paused=True, waiting=True)
    await reset(); check("i'm available = scheduling", await fire("I'm available Tuesday at 3"), outcome="approval", paused=False)
    await reset(); check("are you available = scheduling", await fire("Are you available tomorrow?"), outcome="approval", paused=False)
    await reset([("ai", "What time works for you to come in?")]); check("short time reply w/ context", await fire("6?"), outcome="approval", waiting=True)
    await reset([("ai", "Hope your week is going well!")]); check("'today' neutral context", await fire("Pretty good today, thanks"), outcome="auto", waiting=False)
    # 7 Carry-over: held draft pending, then a non-scheduling follow-up must ALSO be held
    await reset(); await fire("Can I come in tomorrow at 6?")
    check("follow-up while draft held", await fire("Are you there? just checking"), outcome="approval", waiting=True)
    # 8 Mixed fact + schedule -> pause wins
    await reset(); check("mixed fact+schedule", await fire("Do you have it in stock? I could come by tomorrow"), outcome="pause", paused=True)
    # 9 AI suspicion -> escalate to human
    await reset(); check("ai suspicion", await fire("Are you a robot?"), outcome="pause", waiting=True, pushes=1)
    # 11 "All Good" after a fact pause -> Jessi resumes on the next message
    import routers.messages as msgs
    await reset(); await fire("How much is the Tacoma?")
    await msgs.update_conversation(uid, conv, {"needs_assistance": False})
    c = await db.conversations.find_one({"_id": conv_id})
    check("All Good clears pause", {"paused": bool(c.get("ai_paused_for_human")), "waiting": bool(c.get("needs_assistance")),
                                    "mode": c.get("ai_mode")}, paused=False, waiting=False, mode="auto_reply")
    check("Jessi resumes after All Good", await fire("Sounds good, thanks for checking"), outcome="auto", paused=False)
    # 12 Rep turns AI off while a draft is held -> held draft is cancelled, nothing lingers
    await reset(); await fire("Can I come in tomorrow at 6?")
    await msgs.update_conversation(uid, conv, {"ai_mode": "off", "ai_enabled": False})
    left = await db.ai_reply_queue.count_documents({"conversation_id": conv, "status": "pending"})
    c = await db.conversations.find_one({"_id": conv_id})
    check("AI off cancels held draft", {"pending": left, "waiting": bool(c.get("needs_assistance"))}, pending=0, waiting=False)
    await db.conversations.update_one({"_id": conv_id}, {"$set": {"ai_mode": "auto_reply", "ai_enabled": True}})
    # 13 Approve flow clears Waiting (send_sms is stubbed - no real SMS)
    import services.twilio_service as tw
    async def _fake_sms(*a, **k): return {"success": True, "sid": "QA_SID", "mock": True}
    tw.send_sms = _fake_sms
    await reset(); await fire("Can I come in tomorrow at 6?")
    held = await db.ai_reply_queue.find_one({"conversation_id": conv, "status": "pending", "requires_approval": True})

    class _Req:
        async def json(self): return {"user_id": uid}
    await ar.approve_ai_reply(str(held["_id"]), _Req())
    c = await db.conversations.find_one({"_id": conv_id})
    sent_msg = await db.messages.find_one({"conversation_id": conv, "sender": "ai", "approved_by": uid})
    check("approve sends + clears waiting", {"waiting": bool(c.get("needs_assistance")), "sent": bool(sent_msg)}, waiting=False, sent=True)

    # 10 Rep replied after AI queued -> scheduler must cancel the stale auto reply
    await reset(); await fire("Hey, how's it going today?")
    _pending = await db.ai_reply_queue.find_one({"conversation_id": conv, "status": "pending"})
    await db.ai_reply_queue.update_one({"_id": _pending["_id"]},
                                       {"$set": {"send_at": datetime.now(timezone.utc) - timedelta(seconds=5),
                                                 "created_at": datetime.now(timezone.utc) - timedelta(seconds=60)}})
    await db.messages.insert_one({"conversation_id": conv, "sender": "user", "content": "Doing great! How are you?",
                                  "timestamp": datetime.now(timezone.utc)})
    await ar.process_ai_reply_queue()
    q = await db.ai_reply_queue.find_one({"_id": _pending["_id"]})
    check("rep replied cancels AI", {"status": q.get("status"), "reason": q.get("cancel_reason")}, status="cancelled", reason="rep_replied")

    # cleanup
    await db.ai_reply_queue.delete_many({"conversation_id": conv})
    await db.messages.delete_many({"conversation_id": conv})
    await db.notifications.delete_many({"conversation_id": conv})
    await db.notifications.delete_many({"user_id": uid})
    await db.conversations.delete_one({"_id": conv_id})
    await db.contacts.delete_one({"_id": ObjectId(cid)})
    await db.users.delete_one({"_id": ObjectId(uid)})

    passed = sum(1 for r in results if r[1])
    for name, ok, got, bad in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:38s} {got if not ok else ''} {('expected ' + str({k: v[1] for k, v in bad.items()})) if bad else ''}")
    print(f"\n{passed}/{len(results)} passed")
    return passed == len(results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
