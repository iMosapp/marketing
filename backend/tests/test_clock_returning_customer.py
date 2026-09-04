"""Regression: returning-customer lead (existing thread with old history) must not produce negative
first-touch or inflated touch counts. Seeds + cleans its own docs."""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    received = (now - timedelta(hours=3)).replace(microsecond=0)
    conv_id = str(ObjectId())
    contact_id = str(ObjectId())
    tag = "clock_regression_probe"
    msgs = [
        # 78 days of history BEFORE the lead arrived (returning customer)
        {"conversation_id": conv_id, "sender": "user", "direction": "outbound", "content": "old", "timestamp": received - timedelta(days=78), "user_id": "rep1", "probe": tag},
        {"conversation_id": conv_id, "sender": "contact", "direction": "inbound", "content": "old reply", "timestamp": received - timedelta(days=77), "probe": tag},
        {"conversation_id": conv_id, "sender": "user", "direction": "outbound", "content": "old2", "timestamp": received - timedelta(days=30), "user_id": "rep1", "probe": tag},
        # after the lead: AI at +90s, human at +40m, customer reply at +45m
        {"conversation_id": conv_id, "sender": "ai", "direction": "outbound", "content": "hi", "timestamp": received + timedelta(seconds=90), "probe": tag},
        {"conversation_id": conv_id, "sender": "user", "direction": "outbound", "content": "hey", "timestamp": received + timedelta(minutes=40), "user_id": "rep2", "probe": tag},
        {"conversation_id": conv_id, "sender": "contact", "direction": "inbound", "content": "yo", "timestamp": received + timedelta(minutes=45), "probe": tag},
    ]
    await db.messages.insert_many(msgs)
    await db.calls.insert_many([
        {"contact_id": contact_id, "type": "outbound", "timestamp": received - timedelta(days=60), "user_id": "rep1", "probe": tag},
        {"contact_id": contact_id, "type": "outbound", "timestamp": received + timedelta(minutes=10), "user_id": "rep2", "probe": tag},
    ])
    try:
        from services.lead_clocks import clocks_for_leads
        c = (await clocks_for_leads(db, [{"conversation_id": conv_id, "contact_id": contact_id, "received_at": received}]))[conv_id]
        checks = {
            "human_secs == 2400": c["human_secs"] == 2400,
            "ai_secs == 90": c["ai_secs"] == 90,
            "call_secs == 600": c["call_secs"] == 600,
            "outbound_texts == 2": c["outbound_texts"] == 2,
            "inbound_texts == 1": c["inbound_texts"] == 1,
            "calls == 1": c["calls"] == 1,
            "human_rep == rep2": c["human_rep"] == "rep2",
            "reply after first outbound (45m - 90s)": c["reply_secs"] == 45 * 60 - 90,
            "no negative": all((v or 0) >= 0 for v in (c["human_secs"], c["ai_secs"], c["call_secs"], c["reply_secs"])),
        }
        for k, ok in checks.items():
            print(("PASS" if ok else "FAIL"), k)
        print(c)
        assert all(checks.values())
    finally:
        await db.messages.delete_many({"probe": tag})
        await db.calls.delete_many({"probe": tag})
        print("cleaned")


asyncio.run(main())
