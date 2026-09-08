"""Reproduce + verify: a website demo lead whose contact carries automotive history.
BEFORE (legacy thread, no inquiry) Jessi drifts to the customer's vehicle; AFTER (lead thread w/ inquiry) she stays on the software demo.
Never sends SMS: drafts are queued in draft_only mode and cancelled immediately. Cleans up everything it creates.
run: cd /app/backend && python tests/manual_lead_inquiry_probe.py
"""
import asyncio, os, re, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from bson import ObjectId

USER_ID = "69a0b7095fddcede09591667"   # forest (preview)
SOURCE_ID = "69a787ca70ae63ea0ac69251"  # Website catch-all (preview)
VEHICLE_WORDS = re.compile(r"\b(mojave|gladiator|jeep|vehicle|truck|car|inspection|test drive|trade|lot|mileage|miles)\b", re.I)
REPLY = "Yeah the photos make it look kind of rough honestly"


async def main():
    from routers.database import get_db
    db = get_db()
    now = datetime.now(timezone.utc)
    created = {"contacts": [], "conversations": [], "messages": [], "inbound_leads": [], "ai_reply_queue": [], "voice_notes": []}

    # Contact with automotive history (what Forest Ward's record looks like in production)
    c = await db.contacts.insert_one({
        "first_name": "Probe", "last_name": "Demo", "phone": "+15005550199", "user_id": USER_ID,
        "vehicle": "2021 Jeep Gladiator Mojave", "vehicle_purchased": "2021 Jeep Gladiator Mojave",
        "personal_details": {"vehicle_details": "40 inch tires, lifted", "vehicle_color": "Sting Gray"},
        "notes": "Bought the Mojave in 2021, loves off-roading", "tags": ["sold"], "status": "active",
        "created_at": now - timedelta(days=400), "updated_at": now,
    })
    cid = str(c.inserted_id); created["contacts"].append(c.inserted_id)
    old = await db.conversations.insert_one({"contact_id": cid, "user_id": USER_ID, "contact_phone": "+15005550199",
                                             "contact_name": "Probe Demo", "status": "active", "created_at": now - timedelta(days=300)})
    created["conversations"].append(old.inserted_id)
    for sender, txt, d in (("user", "Hey Probe, how's the Mojave treating you on those 40s?", 299),
                           ("contact", "Love it! Took it to Moab last month", 298)):
        m = await db.messages.insert_one({"conversation_id": str(old.inserted_id), "contact_id": cid, "user_id": USER_ID,
                                          "sender": sender, "content": txt, "timestamp": now - timedelta(days=d)})
        created["messages"].append(m.inserted_id)

    async def run_case(label, is_internet_lead, with_inquiry):
        from services.lead_context import build_lead_inquiry
        source = await db.lead_sources.find_one({"_id": ObjectId(SOURCE_ID)})
        normalized = {"first_name": "Probe", "company": "Probe Motors", "industry": "Automotive dealer",
                      "comments": "Want to see how the texting and AI works for my team",
                      "attribution": {"kind": "website_form", "source_label": "the Pricing page"}, "source_name": "Website"}
        inquiry = build_lead_inquiry(normalized, source)
        lead = await db.inbound_leads.insert_one({"contact_id": cid, "source_name": "Website", "comments": normalized["comments"],
                                                  "vehicle_interest": "", "inquiry": inquiry, "is_test": True, "created_at": now})
        created["inbound_leads"].append(lead.inserted_id)
        conv_doc = {"contact_id": cid, "user_id": USER_ID, "assigned_to": USER_ID, "contact_phone": "+15005550199",
                    "contact_name": "Probe Demo", "status": "active", "is_internet_lead": is_internet_lead,
                    "lead_source_id": SOURCE_ID, "lead_source_name": "Website", "inbound_lead_id": str(lead.inserted_id),
                    "attribution": normalized["attribution"], "ai_mode": "draft_only", "ai_enabled": True, "is_test": True,
                    "created_at": now, "updated_at": now}
        if with_inquiry:
            conv_doc["inquiry"] = inquiry
        conv = await db.conversations.insert_one(conv_doc)
        conv_id = str(conv.inserted_id); created["conversations"].append(conv.inserted_id)
        for sender, txt, secs in (("user", "Hey Probe! I see you were on the website and requested a demo?", 120),
                                  ("contact", REPLY, 5)):
            m = await db.messages.insert_one({"conversation_id": conv_id, "contact_id": cid, "user_id": USER_ID, "sender": sender,
                                              "content": txt, "timestamp": now - timedelta(seconds=secs)})
            created["messages"].append(m.inserted_id)

        from routers.ai_reply import queue_ai_reply
        q = await queue_ai_reply(contact_id=cid, conversation_id=conv_id, enrollment_id="", campaign_id="",
                                 assigned_user_id=USER_ID, incoming_message=REPLY, ai_assist_mode="draft_only")
        body = (q or {}).get("ai_body") or (q or {}).get("body") or ""
        if q and q.get("_id"):
            created["ai_reply_queue"].append(q["_id"])
            await db.ai_reply_queue.update_one({"_id": q["_id"]}, {"$set": {"status": "cancelled", "cancel_reason": "probe"}})
        if not body and q:
            body = str({k: v for k, v in q.items() if "body" in k or "message" in k})
        # Jessi suggests (rep-side) for the same thread
        from routers.messages import get_ai_suggestion_smart
        sug = await get_ai_suggestion_smart(conv_id)
        await db.notifications.delete_many({"conversation_id": conv_id})
        print(f"\n=== {label} ===")
        print("AUTO-REPLY :", body)
        print("SUGGESTS   :", sug.get("suggestion"), f"[{sug.get('intent')}]")
        return body, sug.get("suggestion", "")

    try:
        b1, s1 = await run_case("BEFORE (regular thread, today's production behaviour)", is_internet_lead=False, with_inquiry=False)
        b2, s2 = await run_case("AFTER legacy lead thread (no stored inquiry, derived on the fly)", is_internet_lead=True, with_inquiry=False)
        b3, s3 = await run_case("AFTER new lead thread (inquiry stored at intake)", is_internet_lead=True, with_inquiry=True)
        print("\nvehicle words BEFORE:", bool(VEHICLE_WORDS.search(b1 + " " + s1)))
        for name, txt in (("legacy auto", b2), ("legacy suggest", s2), ("new auto", b3), ("new suggest", s3)):
            hit = VEHICLE_WORDS.search(txt)
            print(f"{name:15s} vehicle words: {bool(hit)}{' -> ' + hit.group(0) if hit else ''} | mentions demo/software: {bool(re.search(r'demo|software|platform|walk', txt, re.I))}")
    finally:
        for coll, ids in created.items():
            if ids:
                await db[coll].delete_many({"_id": {"$in": ids}})
        await db.ai_reply_queue.delete_many({"contact_id": cid})
        await db.contact_events.delete_many({"contact_id": cid})
        await db.notifications.delete_many({"contact_id": cid})
        print("\ncleanup done")

asyncio.run(main())
