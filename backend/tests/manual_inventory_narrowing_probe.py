"""Real-LLM check of the inventory narrowing flow: broad truck ask -> qualifying question; answer -> 2-3 pick shortlist.
No SMS: draft_only queue items are cancelled immediately; all seeded data is removed.
run: cd /app/backend && python tests/manual_inventory_narrowing_probe.py
"""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

USER_ID = "69a0b7095fddcede09591667"   # forest (preview) - store 69a0b7095fddcede09591668
STORE_ID = "69a0b7095fddcede09591668"
TRUCKS = [(2024, "Ford", "F-150", "Lariat", 58900.0, "new", 1200), (2021, "Ford", "F-150", "XLT", 36500.0, "used", 41000),
          (2023, "Chevrolet", "Silverado 1500", "LT", 47900.0, "new", 5000), (2019, "Toyota", "Tacoma", "SR5", 29900.0, "used", 62000),
          (2022, "Ford", "Ranger", "XLT", 33400.0, "used", 28000), (2020, "Ram", "1500", "Big Horn", 34900.0, "used", 51000),
          (2024, "Toyota", "Tundra", "SR5", 52400.0, "new", 800), (2018, "Chevrolet", "Colorado", "Z71", 26900.0, "used", 71000)]


async def main():
    from routers.database import get_db
    db = get_db()
    now = datetime.now(timezone.utc)
    inv = await db.inventory.insert_many([
        {"name": f"{y} {mk} {md} {tr}", "status": "available", "price": p, "created_by_user_id": USER_ID, "is_probe": True,
         "attributes": {"year": str(y), "make": mk, "model": md, "trim": tr, "condition": c, "mileage": str(mi), "color": "Gray"},
         "created_at": now} for y, mk, md, tr, p, c, mi in TRUCKS])
    c = await db.contacts.insert_one({"first_name": "Probe", "last_name": "Trucks", "phone": "+15005550198", "user_id": USER_ID,
                                      "status": "active", "created_at": now, "updated_at": now})
    cid = str(c.inserted_id)
    conv = await db.conversations.insert_one({"contact_id": cid, "user_id": USER_ID, "contact_phone": "+15005550198",
                                              "contact_name": "Probe Trucks", "status": "active", "ai_mode": "draft_only",
                                              "ai_enabled": True, "created_at": now, "updated_at": now})
    conv_id = str(conv.inserted_id)
    from routers.ai_reply import queue_ai_reply

    async def turn(text):
        await db.messages.insert_one({"conversation_id": conv_id, "contact_id": cid, "user_id": USER_ID, "sender": "contact",
                                      "content": text, "timestamp": datetime.now(timezone.utc)})
        q = await queue_ai_reply(contact_id=cid, conversation_id=conv_id, enrollment_id="", campaign_id="",
                                 assigned_user_id=USER_ID, incoming_message=text, ai_assist_mode="draft_only")
        body = (q or {}).get("body") or ""
        media = (q or {}).get("media_urls") or []; print("  hot_escalation:", bool((q or {}).get("hot_topic_escalation")))
        if q and q.get("_id"):
            await db.ai_reply_queue.update_one({"_id": q["_id"]}, {"$set": {"status": "cancelled", "cancel_reason": "probe"}})
        await db.messages.insert_one({"conversation_id": conv_id, "contact_id": cid, "user_id": USER_ID, "sender": "ai",
                                      "content": body, "timestamp": datetime.now(timezone.utc)})
        c2 = await db.conversations.find_one({"_id": conv.inserted_id}, {"inventory_narrowing": 1})
        print(f"\nCUSTOMER: {text}\nJESSI   : {body}\n  media={len(media)} narrowing_pending={bool(c2.get('inventory_narrowing'))}")
        return body

    try:
        b1 = await turn("What trucks do you have in stock?")
        b2 = await turn("Probably under 40k, mostly for work and towing")
        import re
        listed1 = len(re.findall(r"\$\d", b1))
        names2 = sum(1 for n in ("F-150", "Silverado", "Tacoma", "Ranger", "Ram", "1500", "Tundra", "Colorado") if n.lower() in b2.lower())
        print(f"\nturn1 prices listed: {listed1} (want 0) | asks a question: {'?' in b1}")
        print(f"turn2 models named: {names2} (want 2-3) | any over 40k named (F-150 Lariat/Silverado/Tundra): "
              f"{any(x in b2 for x in ('58,9', '47,9', '52,4', 'Tundra', 'Silverado'))}")
    finally:
        await db.inventory.delete_many({"_id": {"$in": inv.inserted_ids}})
        await db.messages.delete_many({"conversation_id": conv_id})
        await db.ai_reply_queue.delete_many({"conversation_id": conv_id})
        await db.notifications.delete_many({"conversation_id": conv_id})
        await db.inventory_interest.delete_many({"contact_id": cid})
        await db.contact_events.delete_many({"contact_id": cid})
        await db.conversations.delete_one({"_id": conv.inserted_id})
        await db.contacts.delete_one({"_id": c.inserted_id})
        print("\ncleanup done")

asyncio.run(main())
