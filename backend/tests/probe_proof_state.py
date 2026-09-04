"""Read-only probe: lead sources cost + 90d leads + per-lead clocks (spot negative first-touch)."""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    async for s in db.lead_sources.find({}, {"name": 1, "monthly_cost": 1, "store_id": 1, "is_active": 1}):
        print("SRC", s)
    since = datetime.now(timezone.utc) - timedelta(days=90)
    leads = await db.inbound_leads.find({"received_at": {"$gte": since}, "is_test": {"$ne": True}, "conversation_id": {"$nin": [None, ""]}},
                                        {"source_name": 1, "conversation_id": 1, "contact_id": 1, "received_at": 1, "full_name": 1, "store_id": 1}).to_list(50)
    print("leads 90d:", len(leads))
    from services.lead_clocks import clocks_for_leads
    clocks = await clocks_for_leads(db, leads)
    for l in leads:
        c = clocks.get(l["conversation_id"], {})
        print(l.get("full_name"), l.get("source_name"), "rcv", l.get("received_at"), "| call", c.get("call_secs"), "human", c.get("human_secs"), "ai", c.get("ai_secs"),
              "out", c.get("outbound_texts"), "in", c.get("inbound_texts"), "calls", c.get("calls"), "reply", c.get("reply_secs"))


asyncio.run(main())
