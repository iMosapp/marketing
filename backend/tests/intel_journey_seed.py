"""Seed (or wipe) the Phase 2 end-to-end journey contact "Tom Journey" for the activation-tester rep, for pytest and for looking at the screens.

  cd /app/backend && set -a && . ./.env && set +a && python tests/intel_journey_seed.py            # contact + facts + lead + thread
  python tests/intel_journey_seed.py --draft                                                      # ... plus a Jessi draft waiting for approval (live LLM)
  python tests/intel_journey_seed.py --wipe                                                       # remove everything it created
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REP_ID = "6a978d68b8673c29063aa8b9"          # activation-tester
STORE_ID = "69a0b7095fddcede09591668"
PHONE = "+15005550792"
TAG = "QA Intel Journey"
TOWING_TEXT = "What's the towing capacity on the F-150? We just got a 7,000 lb camper."


async def wipe(db):
    for c in await db.contacts.find({"tags": TAG}, {"_id": 1}).to_list(20):
        cid = str(c["_id"])
        for coll in ("contact_facts", "contact_fact_events", "inbound_leads", "voice_notes", "messages", "conversations", "tasks", "ai_reply_queue", "contact_events", "notifications", "intel_legacy_snapshots"):
            await db[coll].delete_many({"contact_id": cid})
    await db.contacts.delete_many({"tags": TAG})
    await db.conversations.delete_many({"contact_phone": PHONE})


async def seed(db) -> dict:
    """Jeep bought 2 years ago (sale) -> camper voice memo 18 months ago -> F-150 website inquiry 2 days ago -> towing text today. Returns ids."""
    from services.intelligence import ingest
    await wipe(db)
    now = datetime.now(timezone.utc)
    rep = await db.users.find_one({"_id": ObjectId(REP_ID)})
    contact = {"first_name": "Tom", "last_name": "Journey", "name": "Tom Journey", "phone": PHONE, "user_id": REP_ID, "store_id": STORE_ID, "tags": [TAG],
               "status": "active", "created_at": now - timedelta(days=760),
               "purchase_history": [{"id": "ph_jeep_journey", "title": "2022 Jeep Wrangler Unlimited Sahara", "date": (now - timedelta(days=730)).date().isoformat(), "category": "vehicle",
                                     "notes": "Bought the Wrangler, loves the trails"}]}
    cid = (await db.contacts.insert_one(contact)).inserted_id
    contact["_id"] = cid
    out = {"cid": str(cid)}
    out["purchases"] = await ingest.from_purchases(db, contact, contact["purchase_history"], actor=rep)
    note = {"user_id": REP_ID, "contact_id": str(cid), "kind": "memo", "created_at": now - timedelta(days=540), "intelligence_done": True,
            "transcript": "Talked to Tom at the game. He just bought a camper and wants to tow it down to Moab this summer. He is not sure the Jeep is enough truck for it."}
    nid = (await db.voice_notes.insert_one(note)).inserted_id
    out["memo"] = await ingest.from_extraction(db, contact, {"interests": ["camping"], "purchase_context": "just bought a camper and wants to tow it to Moab"},
                                               transcript=note["transcript"], source_kind="voice_memo", source_ref=str(nid), occurred_at=note["created_at"], actor=rep)
    conv = {"user_id": REP_ID, "rep_phone": rep.get("twilio_number") or rep.get("mvpline_number"), "contact_id": str(cid), "contact_phone": PHONE, "contact_name": "Tom Journey",
            "status": "active", "ai_mode": "assisted", "ai_handled": False, "unread": False, "created_at": now - timedelta(days=2), "last_message_at": now, "is_internet_lead": True}
    conv_id = (await db.conversations.insert_one(conv)).inserted_id
    out["conv"] = str(conv_id)
    lead = {"contact_id": str(cid), "user_id": REP_ID, "store_id": STORE_ID, "source_name": "Website", "vehicle_interest": "2025 Ford F-150 Lariat",
            "vehicle_raw": {"vehicle_year": "2025", "vehicle_make": "Ford", "vehicle_model": "F-150", "vehicle_trim": "Lariat"},
            "comments": "Looking at the F-150 for towing a travel trailer. What can it pull?", "received_at": now - timedelta(days=2), "created_at": now - timedelta(days=2), "conversation_id": str(conv_id)}
    lead["_id"] = (await db.inbound_leads.insert_one(lead)).inserted_id
    r = await ingest.from_lead(db, contact, lead)
    out["lead"] = r
    out["f150_fact"] = str(r["fact"]["_id"])
    await db.messages.insert_many([
        {"conversation_id": str(conv_id), "contact_id": str(cid), "user_id": REP_ID, "sender": "user", "direction": "outbound", "channel": "sms",
         "content": "Hi Tom, saw your note on the F-150. Happy to help, what are you planning to tow?", "timestamp": now - timedelta(days=2, hours=-1), "status": "sent"},
        {"conversation_id": str(conv_id), "contact_id": str(cid), "sender": "contact", "direction": "inbound", "channel": "sms", "content": TOWING_TEXT, "timestamp": now, "status": "received"},
    ])
    last = await db.messages.find_one({"conversation_id": str(conv_id), "sender": "contact"})
    out["text"] = await ingest.from_inbound_message(db, contact, str(conv_id), TOWING_TEXT, {"score": 7, "category": "purchase", "hot_summary": "Asked the F-150 towing capacity for a 7,000 lb camper"},
                                                    at=now, message_id=str(last["_id"]))
    owned = await db.contact_facts.find_one({"contact_id": str(cid), "key": "vehicle.owned", "status": "current"})
    out["jeep_fact"] = str(owned["_id"])
    return out


async def draft(db, cid: str, conv: str) -> dict:
    """Queue the inbound Jessi draft (draft_only: nothing is sent) so the thread shows the approval card with 'Based on' chips."""
    from routers.ai_reply import queue_ai_reply, AI_MODE_DRAFT_ONLY
    doc = await queue_ai_reply(contact_id=cid, conversation_id=conv, enrollment_id="", campaign_id="", assigned_user_id=REP_ID, incoming_message=TOWING_TEXT, ai_assist_mode=AI_MODE_DRAFT_ONLY)
    return doc or {}


async def _main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if "--wipe" in sys.argv:
        await wipe(db)
        print("wiped")
        return
    out = await seed(db)
    print(f"contact {out['cid']}  thread /thread/{out['conv']}  contact /contact/{out['cid']}")
    print(f"F-150 fact {out['f150_fact']}  Jeep fact {out['jeep_fact']}")
    if "--draft" in sys.argv:
        d = await draft(db, out["cid"], out["conv"])
        print("draft:", (d.get("body") or "")[:200])
        print("why:", (d.get("intel_rationale") or {}).get("summary"))


if __name__ == "__main__":
    asyncio.run(_main())
