"""Delete every 'Test Lead' (is_test) and all of its side data. Preview cleanup helper."""
import os, sys, asyncio
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from bson import ObjectId
from routers.database import get_db


async def main():
    db = get_db()
    contacts = await db.contacts.find({"is_test": True}, {"_id": 1, "phone": 1}).to_list(500)
    cids = [str(c["_id"]) for c in contacts]
    convs = await db.conversations.find({"$or": [{"is_test": True}, {"contact_id": {"$in": cids}}]}, {"_id": 1}).to_list(500)
    conv_ids = [str(c["_id"]) for c in convs]
    counts = {}
    counts["messages"] = (await db.messages.delete_many({"conversation_id": {"$in": conv_ids}})).deleted_count
    counts["ai_reply_queue"] = (await db.ai_reply_queue.delete_many({"conversation_id": {"$in": conv_ids}})).deleted_count
    counts["notifications"] = (await db.notifications.delete_many({"$or": [{"conversation_id": {"$in": conv_ids}}, {"contact_id": {"$in": cids}}]})).deleted_count
    counts["lead_call_jobs"] = (await db.lead_call_jobs.delete_many({"conversation_id": {"$in": conv_ids}})).deleted_count
    counts["lead_deferred_actions"] = (await db.lead_deferred_actions.delete_many({"conversation_id": {"$in": conv_ids}})).deleted_count
    counts["inbound_leads"] = (await db.inbound_leads.delete_many({"$or": [{"is_test": True}, {"conversation_id": {"$in": conv_ids}}]})).deleted_count
    counts["campaign_enrollments"] = (await db.campaign_enrollments.delete_many({"contact_id": {"$in": cids}})).deleted_count
    counts["contact_events"] = (await db.contact_events.delete_many({"contact_id": {"$in": cids}})).deleted_count
    counts["conversations"] = (await db.conversations.delete_many({"_id": {"$in": [ObjectId(c) for c in conv_ids]}})).deleted_count
    counts["contacts"] = (await db.contacts.delete_many({"_id": {"$in": [ObjectId(c) for c in cids]}})).deleted_count
    counts["lead_release_slots"] = (await db.lead_release_slots.delete_many({})).deleted_count
    print("cleaned:", counts)

asyncio.run(main())
