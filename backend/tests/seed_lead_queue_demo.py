"""Seed / clean demo internet leads for the shared Leads queue (preview only, no SMS fired).

    python tests/seed_lead_queue_demo.py seed
    python tests/seed_lead_queue_demo.py clean
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

STORE_ID = "69a0b7095fddcede09591668"
SOURCE_ID = "69a787ca70ae63ea0ac69251"   # Website (Forest's store)
FOREST_ID = "69a0b7095fddcede09591667"
TAG = "lead_queue_demo"

LEADS = [
    # name, phone, minutes_ago, claimed_by, vehicle, comments, customer_replied_after_us
    ("Queue Alpha", "+15005550101", 3, None, "2024 Tahoe", "Is the Tahoe still available?", False),
    ("Queue Bravo", "+15005550102", 9, None, "2023 F-150", "Looking to trade in my Silverado", False),
    ("Queue Charlie", "+15005550103", 25, None, None, "Best price on the RAV4 please", False),
    ("Mine Delta", "+15005550104", 40, FOREST_ID, "2022 Camry", "Can I come by Saturday?", True),
    ("Mine Echo", "+15005550105", 120, FOREST_ID, None, "Thanks, see you then", False),
]


async def seed(db):
    now = datetime.now(timezone.utc)
    for name, phone, mins, claimed_by, vehicle, comments, replied_after in LEADS:
        created = now - timedelta(minutes=mins)
        first, last = name.split(" ", 1)
        contact = await db.contacts.insert_one({
            "user_id": claimed_by or STORE_ID, "store_id": STORE_ID, "first_name": first, "last_name": last, "name": name,
            "phone": phone, "tags": ["Test Lead", TAG], "source": "Website", "created_at": created.isoformat(), "updated_at": created.isoformat(),
            "claimed_by": claimed_by, "seed_tag": TAG,
        })
        conv = await db.conversations.insert_one({
            "user_id": claimed_by or STORE_ID, "store_id": STORE_ID, "contact_id": str(contact.inserted_id), "contact_name": name,
            "contact_phone": phone, "is_internet_lead": True, "lead_source_id": SOURCE_ID, "lead_source_name": "Website",
            "status": "active", "claimed": bool(claimed_by), "claimed_by": claimed_by, "assigned_to": claimed_by,
            "claimed_at": created.isoformat() if claimed_by else None, "claim_source": "app" if claimed_by else None,
            "routing_kind": "claimed" if claimed_by else "queue", "is_test": True, "seed_tag": TAG,
            "ai_mode": "auto_reply", "ai_enabled": True, "sms_consent": {"opted_in": True, "source": "demo_form"},
            "created_at": created, "updated_at": created.isoformat(), "unread_count": 0,
        })
        cid = str(conv.inserted_id)
        await db.inbound_leads.insert_one({
            "conversation_id": cid, "contact_id": str(contact.inserted_id), "source_id": SOURCE_ID, "store_id": STORE_ID,
            "vehicle_interest": vehicle, "comments": comments, "is_test": True, "seed_tag": TAG, "received_at": created,
            "attribution": {"source_label": "Book a Demo"}, "status": "skipped",
        })
        msgs = [{"conversation_id": cid, "content": comments, "sender": "contact", "direction": "inbound", "timestamp": created, "created_at": created, "seed_tag": TAG}]
        if claimed_by:
            t1 = created + timedelta(minutes=2)
            msgs.append({"conversation_id": cid, "content": f"Hi {first}, Forest here. Happy to help!", "sender": "user", "direction": "outbound",
                         "user_id": claimed_by, "timestamp": t1, "created_at": t1, "seed_tag": TAG})
            if replied_after:
                t2 = created + timedelta(minutes=10)
                msgs.append({"conversation_id": cid, "content": "Great, what time works?", "sender": "contact", "direction": "inbound",
                             "timestamp": t2, "created_at": t2, "seed_tag": TAG})
        await db.messages.insert_many(msgs)
        print(f"seeded {name} conv={cid} claimed_by={claimed_by}")


async def clean(db):
    for coll in ("messages", "inbound_leads", "conversations", "contacts", "notifications"):
        r = await db[coll].delete_many({"seed_tag": TAG})
        print(f"{coll}: removed {r.deleted_count}")
    # notifications created by the app for these leads carry conversation_id, not the seed tag
    conv_ids = [str(c["_id"]) async for c in db.conversations.find({"seed_tag": TAG}, {"_id": 1})]
    if conv_ids:
        await db.notifications.delete_many({"conversation_id": {"$in": conv_ids}})


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if mode == "clean":
        # collect conv ids before deleting the conversations so their notifications go too
        conv_ids = [str(c["_id"]) async for c in db.conversations.find({"seed_tag": TAG}, {"_id": 1})]
        if conv_ids:
            r = await db.notifications.delete_many({"conversation_id": {"$in": conv_ids}})
            print(f"notifications by conv: removed {r.deleted_count}")
        await clean(db)
    else:
        await clean(db)
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
