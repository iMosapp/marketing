"""Seed/clean demo internet-lead data for Leads > Speed and Proof tabs. Usage: python tests/seed_lead_proof_demo.py seed|clean"""
import asyncio, os, sys, random
from datetime import datetime, timezone, timedelta
from bson import ObjectId
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from routers.database import get_db

TAG = "lead_proof_demo_seed"
random.seed(7)

async def main(cmd):
    db = get_db()
    if cmd == "clean":
        for col in (db.inbound_leads, db.conversations, db.messages, db.contacts, db.calls, db.lead_sources):
            r = await col.delete_many({"seed_tag": TAG})
            print(col.name, "deleted", r.deleted_count)
        return
    forest = await db.users.find_one({"email": "forest@imosapp.com"}, {"_id": 1, "store_id": 1})
    uid, store = str(forest["_id"]), forest.get("store_id")
    now = datetime.now(timezone.utc)
    srcs = {"Seed Autotrader": 10000, "Seed Cars.com": 4000, "Seed Website": 0}
    for name, cost in srcs.items():
        await db.lead_sources.insert_one({"name": name, "monthly_cost": cost, "store_id": store, "status": "active", "created_at": now, "seed_tag": TAG})
    plan = [  # (source, first_touch_secs or None, human_secs or None, customer_reply, touches, sold, days_to_sold)
        ("Seed Autotrader", 90, 240, True, 6, True, 4), ("Seed Autotrader", 120, 1500, True, 5, True, 9), ("Seed Autotrader", 60, None, True, 3, False, None),
        ("Seed Autotrader", 4000, 4000, False, 1, False, None), ("Seed Autotrader", 9000, None, False, 2, False, None), ("Seed Autotrader", 200, 300, True, 8, True, 2),
        ("Seed Autotrader", None, None, False, 0, False, None), ("Seed Autotrader", 30000, 30000, False, 1, False, None),
        ("Seed Cars.com", 100, 200, True, 4, True, 6), ("Seed Cars.com", 3000, 3000, False, 2, False, None), ("Seed Cars.com", 150, None, True, 3, False, None),
        ("Seed Cars.com", 100000, None, False, 1, False, None), ("Seed Cars.com", 80, 100, True, 7, True, 12),
        ("Seed Website", 45, 600, True, 5, True, 3), ("Seed Website", 50, None, False, 1, False, None), ("Seed Website", 70, 900, True, 4, False, None),
        ("Seed Website", 5000, None, False, 2, False, None), ("Seed Website", 40, 120, True, 9, True, 1),
    ]
    for i, (src, touch, human, reply, touches, sold, dts) in enumerate(plan):
        received = now - timedelta(days=random.randint(3, 60), hours=random.randint(0, 20))
        c = await db.contacts.insert_one({"user_id": uid, "name": f"Seed Lead {i}", "first_name": "Seed", "phone": f"+1500555{i:04d}", "created_at": received,
                                          "date_sold": (received + timedelta(days=dts)) if sold else None, "seed_tag": TAG})
        conv = await db.conversations.insert_one({"user_id": uid, "contact_id": str(c.inserted_id), "contact_name": f"Seed Lead {i}", "status": "active", "created_at": received, "seed_tag": TAG})
        cid = str(conv.inserted_id)
        await db.inbound_leads.insert_one({"source_name": src, "store_id": store, "contact_id": str(c.inserted_id), "conversation_id": cid, "phone": f"+1500555{i:04d}",
                                           "full_name": f"Seed Lead {i}", "status": "sent", "received_at": received, "created_at": received, "assigned_to": uid, "seed_tag": TAG})
        msgs = []
        if touch is not None:
            msgs.append({"conversation_id": cid, "sender": "ai", "direction": "outbound", "ai_generated": True, "content": "Hey! Thanks for reaching out.", "timestamp": received + timedelta(seconds=touch), "seed_tag": TAG})
        if human is not None:
            msgs.append({"conversation_id": cid, "sender": "user", "user_id": uid, "direction": "outbound", "content": "This is Forest, when works for a test drive?", "timestamp": received + timedelta(seconds=human), "seed_tag": TAG})
        first_out = min([m["timestamp"] for m in msgs], default=None)
        if reply and first_out:
            msgs.append({"conversation_id": cid, "sender": "contact", "direction": "inbound", "content": "Tomorrow at 5 works", "timestamp": first_out + timedelta(minutes=random.randint(3, 240)), "seed_tag": TAG})
            for k in range(min(touches, 3) - 1):
                msgs.append({"conversation_id": cid, "sender": "contact", "direction": "inbound", "content": "Sounds good", "timestamp": first_out + timedelta(hours=2 + k), "seed_tag": TAG})
        extra_out = max(0, touches - len([m for m in msgs if m["sender"] != "contact"]) - 1)
        for k in range(extra_out):
            msgs.append({"conversation_id": cid, "sender": "user", "user_id": uid, "direction": "outbound", "content": "Checking in", "timestamp": received + timedelta(hours=5 + k), "seed_tag": TAG})
        if msgs:
            await db.messages.insert_many(msgs)
        if touches >= 4:
            await db.calls.insert_one({"contact_id": str(c.inserted_id), "type": "outbound", "duration": 120, "user_id": uid, "timestamp": received + timedelta(seconds=(touch or 600) + 60), "seed_tag": TAG})
    print("seeded", len(plan), "leads for store", store)

asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))
