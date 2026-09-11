"""Preview-only demo data for Call Scorecards: fake recorded calls (transcripts, no audio) for the Activation Tester rep,
graded through the real AI pipeline. Idempotent; `--wipe` removes everything it created.
Usage: cd /app/backend && python tests/seed_scorecard_demo.py [--wipe] [--no-grade]"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from bson import ObjectId  # noqa: E402

REP_EMAIL = "activation-tester@invalid.imonsocial.test"
TAG = "scorecard_demo"

CALLS = [
    {
        "sid": "CA_scdemo_good_001", "contact": "Sarah Tester", "phone": "+15005550041", "direction": "outbound", "duration": 312, "age_h": 3,
        "turns": [
            ("rep", "Hi Sarah, this is Alex over at i'M On social Motors. You reached out about the 2024 Tahoe Z71 on our website, do you have a quick minute?"),
            ("customer", "Oh yes, hi Alex. Yeah I was looking at that one, is it still available?"),
            ("rep", "It is, I actually walked past it this morning, it's the Midnight Blue one with the tan interior. What's got you looking at a Tahoe?"),
            ("customer", "We just had our third kid and the Explorer is getting tight. My husband wants something that can tow the boat too."),
            ("rep", "Congratulations! The Z71 tows about eight thousand pounds so the boat is no problem. What's your timeline, are you hoping to be in something before summer?"),
            ("customer", "Ideally in the next couple of weeks."),
            ("rep", "Perfect. Will you have the Explorer to trade in?"),
            ("customer", "Yeah, it's a 2019 with about seventy thousand miles."),
            ("rep", "Great, we're paying strong money for those right now. When could you and your husband come see the Tahoe, would this evening or tomorrow work better?"),
            ("customer", "Tomorrow is better, maybe after work."),
            ("rep", "Does 5:30 or 6:15 work better for you?"),
            ("customer", "5:30 works."),
            ("rep", "5:30 tomorrow it is. I have your number as 555-0041, is that the best one for a confirmation text?"),
            ("customer", "Yes that's my cell."),
            ("rep", "Awesome. So tomorrow at 5:30 I'll have the Tahoe pulled up front and I'll get the Explorer looked at while you drive it. Thanks so much Sarah, see you then."),
            ("customer", "Thanks Alex, bye."),
        ],
    },
    {
        "sid": "CA_scdemo_miss_002", "contact": "Mike Tester", "phone": "+15005550042", "direction": "outbound", "duration": 148, "age_h": 26,
        "turns": [
            ("rep", "Hey, is this Mike?"),
            ("customer", "Yeah."),
            ("rep", "Hey Mike, it's Alex from the dealership, you filled out something on the F-150 online."),
            ("customer", "Oh right. What's the best price you can do on it?"),
            ("rep", "So it's listed at forty-eight five, we can probably do a little better in person but I'd have to talk to my manager."),
            ("customer", "Hmm okay. I'm kind of just shopping around right now."),
            ("rep", "Totally understand. Well it's a nice truck, XLT with the tow package."),
            ("customer", "Yeah I saw that. Alright, let me think about it."),
            ("rep", "Sure thing, I'll shoot you an email with some info. Have a good one."),
            ("customer", "Okay, thanks."),
        ],
    },
    {
        "sid": "CA_scdemo_mid_003", "contact": "Dana Tester", "phone": "+15005550043", "direction": "inbound", "duration": 201, "age_h": 50,
        "turns": [
            ("rep", "i'M On social Motors, this is Alex, how can I help you?"),
            ("customer", "Hi, I saw a red Bronco on your website, the Badlands. Is it still there?"),
            ("rep", "Let me check for you. Yes, the Badlands is still here. Who am I speaking with?"),
            ("customer", "Dana."),
            ("rep", "Nice to meet you Dana. Are you looking to replace something or add to the driveway?"),
            ("customer", "Replacing my Jeep, it's a 2017 Wrangler."),
            ("rep", "Oh nice, we'd definitely take a look at that as a trade. When would be a good time for you to come drive the Bronco?"),
            ("customer", "Maybe this weekend."),
            ("rep", "Saturday or Sunday better?"),
            ("customer", "Saturday probably, I'll just swing by."),
            ("rep", "Sounds great, ask for Alex when you get here. Thanks Dana!"),
            ("customer", "Thanks."),
        ],
    },
]


async def main():
    wipe = "--wipe" in sys.argv
    grade = "--no-grade" not in sys.argv
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    rep = await db.users.find_one({"email": REP_EMAIL})
    assert rep, f"{REP_EMAIL} missing"
    rep_id = str(rep["_id"])
    if not wipe and not rep.get("store_id"):
        mgr = await db.users.find_one({"email": "qa-manager@invalid.imonsocial.test"}, {"store_id": 1})
        if mgr and mgr.get("store_id"):
            await db.users.update_one({"_id": rep["_id"]}, {"$set": {"store_id": mgr["store_id"]}})
            print(f"activation tester joined store {mgr['store_id']}")

    if wipe:
        sids = [c["sid"] for c in CALLS]
        for coll in ("call_logs", "call_evaluations", "notes", "messages"):
            r = await db[coll].delete_many({"call_sid": {"$in": sids}})
            print(f"  {coll}: -{r.deleted_count}")
        r = await db.contacts.delete_many({"tags": TAG, "user_id": rep_id})
        print(f"  contacts: -{r.deleted_count}")
        r = await db.notifications.delete_many({"idempotency_key": {"$regex": "^scorecard_"}})
        print(f"  notifications: -{r.deleted_count}")
        return

    now = datetime.now(timezone.utc)
    for c in CALLS:
        contact = await db.contacts.find_one({"user_id": rep_id, "phone": c["phone"]})
        if not contact:
            first, last = c["contact"].split(" ", 1)
            res = await db.contacts.insert_one({"user_id": rep_id, "first_name": first, "last_name": last, "name": c["contact"], "phone": c["phone"],
                                                "tags": [TAG], "status": "active", "created_at": now, "updated_at": now})
            contact_id = str(res.inserted_id)
        else:
            contact_id = str(contact["_id"])
        t = 0.0
        segs = []
        for role, text in c["turns"]:
            segs.append({"speaker": "Alex" if role == "rep" else c["contact"].split(" ")[0], "role": role, "start": round(t, 1), "text": text})
            t += max(3.0, len(text.split()) * 0.45)
        ts = now - timedelta(hours=c["age_h"])
        await db.call_logs.update_one({"call_sid": c["sid"]}, {"$set": {
            "user_id": rep_id, "contact_id": contact_id, "contact_name": c["contact"], "contact_phone": c["phone"], "call_sid": c["sid"],
            "recording_sid": "", "recording_url": "", "duration_s": c["duration"], "transcript": "\n".join(f"{s['speaker']}: {s['text']}" for s in segs),
            "transcript_segments": segs, "ai_summary": "", "direction": c["direction"], "outcome": "connected", "timestamp": ts, "created_at": ts, "is_demo": TAG,
        }}, upsert=True)
        print(f"call_log {c['sid']} -> {c['contact']} ({c['duration']}s)")

    if grade:
        from services.scorecards import evaluate_call
        for c in CALLS:
            ev = await evaluate_call(c["sid"], force=True)
            if ev:
                print(f"  graded {c['sid']}: {ev['score_pct']}% critical misses={ev['critical_misses']} alerted={ev.get('alerted_user_ids')}")
            else:
                print(f"  {c['sid']}: not graded (no scorecard for the rep's store?)")


if __name__ == "__main__":
    asyncio.run(main())
