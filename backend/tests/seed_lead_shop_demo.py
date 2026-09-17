"""Lead Shops demo data for UI checks (preview only, idempotent; --wipe removes).
Seeds: a FREE fake shopper number in the pool (+15005550311, so creating a lead shop in the UI never buys a real Twilio number),
"QA Jeep 979a" gets a CRM lead email + one COMPLETED lead shop (timeline, conversations graded, score) and one LIVE one.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/seed_lead_shop_demo.py [--wipe]"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import lead_shops as ls

SHOPPER = "+15005550311"
SHOPPER_LIVE = "+15005550312"
CLIENT_NAME = "QA Jeep 979a"


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    client = await db.shop_clients.find_one({"name": CLIENT_NAME})
    if not client:
        print("QA Jeep 979a not found, run tests/mystery_shop_e2e.py first")
        return
    cid = str(client["_id"])
    async for s in db[ls.COLL].find({"client_id": cid, "qa_seed": True}):
        await db.roleplay_sessions.delete_many({"lead_shop_id": str(s["_id"])})
        await db.call_evaluations.delete_many({"lead_shop_seed": str(s["_id"])})
    await db[ls.COLL].delete_many({"client_id": cid, "qa_seed": True})
    await db[ls.POOL].delete_many({"phone_number": {"$in": [SHOPPER, SHOPPER_LIVE]}})
    if wipe:
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$unset": {"lead_email": "", "lead_process": "", "lead_website": ""}})
        print("wiped")
        return
    me = await db.users.find_one({"email": "forest@imosapp.com"})
    now = ls._now()
    await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"lead_email": "crm-intake@invalid.imonsocial.test", "lead_website": "https://www.qajeep.example",
                                                                     "lead_process": {"first_call_min": 5, "first_text_min": 5, "first_email_min": 15, "channels": ["call", "text", "email"], "day1_calls": 3, "follow_up_days": 3}}})
    for phone in (SHOPPER, SHOPPER_LIVE):
        await db[ls.POOL].insert_one({"phone_number": phone, "twilio_sid": f"PN_seed_{phone[-4:]}", "status": "available", "assigned_user_id": None, "purpose": ls.POOL_PURPOSE, "lead_shop_id": None,
                                      "cooldown_until": None, "monthly_cost_usd": 1.15, "purchased_at": now - timedelta(days=30), "purchased_by": str(me["_id"]), "qa_seed": True})

    # completed shop: fast call, slow email, no text
    started = now - timedelta(days=3, hours=2)
    dom = ls.inbound_domain() or "reply.imonsocial.com"
    persona = {"name": "Sam Rivera", "first": "Sam", "last": "Rivera", "email": f"sam.rivera.42@{dom}", "phone": "+15005550399", "vehicle": "2022 Jeep Grand Cherokee", "offering": "2022 Jeep Grand Cherokee",
               "goals": "Is the 2022 Grand Cherokee still available and what is the out-the-door price?", "summary": "Sam is a first-time Jeep buyer comparing two stores."}
    sid = ObjectId()
    call_s = ObjectId(); email_s = ObjectId()
    events = [
        {"at": started, "channel": "lead", "direction": "out", "kind": "delivered", "summary": "Lead delivered to the store (ADF email to crm-intake@invalid.imonsocial.test)"},
        {"at": started + timedelta(seconds=40), "channel": "email", "direction": "in", "kind": "auto_reply", "summary": "Automated email from noreply@crm.test: Thank you for your inquiry", "from": "noreply@crm.test", "automated": True},
        {"at": started + timedelta(minutes=3), "channel": "call", "direction": "in", "kind": "call_answered", "summary": "Store called the shopper from +18015550140 (call 1), answered", "from": "+18015550140", "session_id": str(call_s)},
        {"at": started + timedelta(minutes=9), "channel": "call", "direction": "note", "kind": "graded", "summary": "Call graded: 82%", "session_id": str(call_s)},
        {"at": started + timedelta(hours=1, minutes=48), "channel": "email", "direction": "in", "kind": "email_received", "summary": "Store emailed from joe@qajeep.example: Re: your Grand Cherokee inquiry", "from": "joe@qajeep.example", "session_id": str(email_s)},
        {"at": started + timedelta(days=1, hours=3), "channel": "call", "direction": "in", "kind": "call_answered", "summary": "Store called the shopper from +18015550140 (call 2), answered", "from": "+18015550140", "session_id": str(call_s)},
        {"at": started + timedelta(days=3), "channel": "email", "direction": "note", "kind": "graded", "summary": "Email thread graded: 71%", "session_id": str(email_s)},
    ]
    base = {"kind": "mystery_shop", "status": "completed", "user_id": None, "client_id": cid, "target_id": None, "lead_shop_id": str(sid), "rep_name": "the store", "department": "sales", "industry": "automotive", "store_id": None,
            "store_name": CLIENT_NAME, "locale": "en-US", "script_id": "seed", "script_title": "Shopper: is it still available?", "direction": "outbound", "persona": persona, "curveballs": [], "manual": True, "notify_sms": False, "token": uuid.uuid4().hex,
            "attempts": 1, "max_attempts": 1, "created_by": str(me["_id"]), "qa_seed": True}
    turns_call = [{"role": "customer", "text": "Hello?", "at": started + timedelta(minutes=3)}, {"role": "rep", "text": "Hi Sam, this is Joe at QA Jeep about the Grand Cherokee you asked about. It is still here. Want to come see it Saturday at 10?", "at": started + timedelta(minutes=3, seconds=20)},
                  {"role": "customer", "text": "Saturday could work. What is the out-the-door price?", "at": started + timedelta(minutes=4)}, {"role": "rep", "text": "I will have that ready when you come in, I just need to check the doc fee with my manager.", "at": started + timedelta(minutes=4, seconds=30)}]
    turns_email = [{"role": "rep", "text": "Hi Sam, Joe here. The Grand Cherokee is available. Would Saturday at 10 work?", "at": started + timedelta(hours=1, minutes=48), "delay_s": 6480}, {"role": "customer", "text": "Maybe. Can you send the out-the-door price first?", "at": started + timedelta(hours=2)}]
    await db.roleplay_sessions.insert_one({**base, "_id": call_s, "mode": "phone", "rep_phone": "+18015550140", "from_number": SHOPPER, "call_sid": "CA_leadseed_1", "turns": turns_call, "started_at": started + timedelta(minutes=3), "ended_at": started + timedelta(minutes=8), "score_pct": 82, "created_at": started + timedelta(minutes=3), "updated_at": now})
    await db.roleplay_sessions.insert_one({**base, "_id": email_s, "mode": "email", "rep_email": "joe@qajeep.example", "subject": "Re: your Grand Cherokee inquiry", "from_email": persona["email"], "turns": turns_email, "started_at": started + timedelta(hours=1, minutes=48), "ended_at": started + timedelta(days=3), "score_pct": 71, "created_at": started + timedelta(hours=1, minutes=48), "updated_at": now})
    for s_id, ch, pct, summ in ((call_s, "call", 82, "Joe called within 3 minutes, confirmed the vehicle and offered a time, but dodged the price question."), (email_s, "email", 71, "The email came almost two hours in and repeated the call instead of answering the price question.")):
        ev = {"call_sid": f"RP_{s_id}", "roleplay_session_id": str(s_id), "is_mystery_shop": True, "shop_client_id": cid, "score_pct": pct, "summary": summ, "wins": ["Named the store and himself", "Offered a specific time"], "coaching": ["Answer the price question or give a range", "Confirm the email before the call ends"],
              "channel": ch, "graded_by": "ai", "results": [], "lead_shop_seed": str(sid), "created_at": now}
        await db.call_evaluations.insert_one(ev)
        await db.roleplay_sessions.update_one({"_id": s_id}, {"$set": {"evaluation_id": str((await db.call_evaluations.find_one({"call_sid": ev["call_sid"]}, {"_id": 1}))["_id"])}})
    shop = {"_id": sid, "client_id": cid, "department": "sales", "industry": "automotive", "store_name": CLIENT_NAME, "locale": "en-US", "status": "completed", "method": "adf", "source_name": "Website", "persona": persona, "script_id": "seed", "script_title": "Shopper: is it still available?",
            "window_hours": 72, "process": ls.clean_process({"first_call_min": 5, "first_text_min": 5, "first_email_min": 15, "channels": ["call", "text", "email"], "day1_calls": 3, "follow_up_days": 3}), "events": events, "sessions": {"phone": [str(call_s)], "text": None, "email": str(email_s)},
            "delivery": {"method": "adf", "to_email": "crm-intake@invalid.imonsocial.test", "sent_at": started, "email_id": "em_seed", "subject": "New Lead: Sam Rivera - 2022 Jeep Grand Cherokee"}, "started_at": started, "expires_at": started + timedelta(hours=72), "closed_at": started + timedelta(hours=72), "close_reason": "window_closed",
            "score": None, "score_token": uuid.uuid4().hex, "notes": "GM asked us to test the weekend BDC", "created_by": str(me["_id"]), "qa_seed": True, "created_at": started, "updated_at": now}
    await db[ls.COLL].insert_one(shop)
    score = await ls.compute_score(db, shop)
    await db[ls.COLL].update_one({"_id": sid}, {"$set": {"score": score}})

    # live shop, 20 minutes in, one text so far, number in use
    live_id = ObjectId()
    l_started = now - timedelta(minutes=20)
    l_persona = {**persona, "name": "Priya Bennett", "first": "Priya", "last": "Bennett", "email": f"priya.bennett.17@{dom}", "phone": SHOPPER_LIVE, "vehicle": "2023 Jeep Wrangler 4xe", "offering": "2023 Jeep Wrangler 4xe", "goals": "Do you have the Wrangler 4xe in Hydro Blue and can I see it this week?"}
    await db[ls.COLL].insert_one({**shop, "_id": live_id, "status": "live", "persona": l_persona, "source_name": "Cars.com", "script_title": "Shopper: the other store is cheaper", "window_hours": 24, "started_at": l_started, "expires_at": l_started + timedelta(hours=24), "closed_at": None, "close_reason": None, "score": None, "notes": "",
                                 "sessions": {"phone": [], "text": None, "email": None}, "number_pool_id": None, "score_token": uuid.uuid4().hex, "created_at": l_started, "updated_at": now,
                                 "events": [{"at": l_started, "channel": "lead", "direction": "out", "kind": "delivered", "summary": "Lead delivered to the store (ADF email to crm-intake@invalid.imonsocial.test)"},
                                            {"at": l_started + timedelta(minutes=7), "channel": "text", "direction": "in", "kind": "text_received", "summary": "Store texted the shopper from +18015550140: Hi Priya, Joe at QA Jeep. Hydro Blue is on the lot!", "from": "+18015550140"}]})
    await db[ls.POOL].update_one({"phone_number": SHOPPER_LIVE}, {"$set": {"status": "in_use", "lead_shop_id": str(live_id), "assigned_at": l_started}})
    print(f"seeded: completed lead shop {sid} ({score['overall']}%), live lead shop {live_id}; pool {SHOPPER} free, {SHOPPER_LIVE} in use")
    print(f"UI: /admin/mystery-shops/{cid}?tab=leads")


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
