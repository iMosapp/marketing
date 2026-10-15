"""Fictional demo workspace for marketing screenshots (preview only). Nothing is texted or emailed: documents go straight into Mongo.
Run:  cd /app/backend && set -a && . ./.env && set +a && python tests/seed_marketing_demo.py          (idempotent, re-seeds)
      ... python tests/seed_marketing_demo.py --wipe                                                     (removes everything it made)
Login: marketing-demo@invalid.imonsocial.test / DemoShots123!  (store "Summit Partners", reps Jordan Reyes + Priya Shah)."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routers.auth import hash_password  # noqa: E402

TAG = "marketing_demo"
EMAIL = "marketing-demo@invalid.imonsocial.test"
PASSWORD = "DemoShots123!"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
U = "https://images.unsplash.com/photo-{}?w=240&h=240&fit=crop&crop=faces&q=80"
PH = {k: U.format(v) for k, v in {
    "m1": "1500648767791-00dcc994a43e", "m2": "1507003211169-0a1dd7228f2d", "m3": "1623366302587-b38b1ddaefd9", "m4": "1600603406200-5b2a104684ac",
    "m5": "1568602471122-7832951cc4c5", "w1": "1580489944761-15a19d654956", "w3": "1669844444850-5acd7e8c71c5", "w4": "1662850886700-4ec19bd30d11"}.items()}


def ago(days=0, hours=0, minutes=0):
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


def bday_in(days, year):
    d = (NOW + timedelta(days=days)).date()
    return datetime(year, d.month, d.day)


# (first, last, photo, touch_days_ago, extras): a neutral mix of homes, insurance and auto clients
BOOK = [
    ("Marcus", "Delgado", "m5", 6, {"birthday": bday_in(2, 1986), "date_sold": datetime(2023, 10, 20), "tags": ["client", "advocate"],
        "personal_details": {"spouse_name": "Lena", "kids": [{"name": "Ava", "details": "Starts kindergarten this fall"}], "interests": ["fishing", "Broncos games"],
                             "personal_notes": "Wants to refinance if rates drop. Bought his first home with us in 2023.", "referral_potential": "His brother-in-law is house hunting"}}),
    ("Jenna", "Cole", "w1", 3, {"tags": ["hot lead"], "personal_details": {"spouse_name": "Ryan", "interests": ["yoga", "hiking"],
        "personal_notes": "Baby on the way in March, needs four bedrooms before then.", "communication_preference": "Texts after 5 pm"}}),
    ("Tyler", "Brooks", "m1", 52, {"tags": ["renewal"], "personal_details": {"personal_notes": "Auto and renters policies renew in February. Asked about bundling.", "interests": ["mountain biking"]}}),
    ("Maria", "Santos", "w4", 9, {"date_sold": datetime(2025, 4, 12), "tags": ["advocate", "referral"],
        "personal_details": {"kids": [{"name": "Leo", "details": "Plays club soccer"}], "interests": ["baking"], "personal_notes": "Sent us two friends this year."}}),
    ("David", "Kim", "m2", 124, {"date_sold": datetime(2022, 6, 3), "personal_details": {"kids": [{"name": "Grace", "details": "Graduated from CU Boulder in May"}],
        "personal_notes": "Asked about coverage for his daughter's first car."}}),
    ("Rachel", "Nguyen", "w3", 21, {"birthday": bday_in(1, 1991), "personal_details": {"interests": ["running", "coffee"], "personal_notes": "Training for the Denver half marathon."}}),
    ("Chris", "Vance", "m3", 0, {"date_sold": datetime(2026, 7, 18), "tags": ["client"], "personal_details": {"personal_notes": "Just moved into the house on Juniper St. Brother-in-law Matt is looking too.", "interests": ["hunting"]}}),
    ("Ben", "Carter", "m4", 2, {"vehicle": "2019 Jeep Wrangler (trade)", "tags": ["trade"], "personal_details": {"personal_notes": "Trading the Wrangler. Wants numbers before Saturday.", "interests": ["off-roading"]}}),
    ("Olivia", "Grant", None, 14, {"personal_details": {"personal_notes": "Opened your card twice this week."}}),
    ("Sam", "Patel", None, 18, {"date_sold": datetime(2024, 10, 19), "personal_details": {"kids": [{"name": "Riya", "details": "Turns 16 in December"}]}}),
    ("Hannah", "Lee", None, 61, {"personal_details": {"personal_notes": "Moved to Littleton in the summer."}}),
    ("Luis", "Ortega", None, 103, {"date_sold": datetime(2021, 9, 1)}),
    ("Grace", "Miller", None, 30, {"personal_details": {"interests": ["golf"]}}),
    ("Noah", "Bennett", None, 11, {"personal_details": {"personal_notes": "New job at Lockheed, longer commute."}}),
    ("Emma", "Rossi", None, 40, {"date_sold": datetime(2025, 12, 2)}),
    ("Jack", "Turner", None, 75, {}),
    ("Sophie", "Martin", None, 8, {"personal_details": {"interests": ["skiing"], "personal_notes": "Asked about a home inspection checklist."}}),
    ("Ethan", "Walsh", None, 95, {"date_sold": datetime(2020, 11, 14)}),
    ("Ava", "Thompson", None, 4, {"personal_details": {"personal_notes": "First apartment, dad co-signing."}}),
    ("Owen", "Fisher", None, 28, {}),
]
TEAM = [("Jordan", "Reyes", "jordan"), ("Priya", "Shah", "priya")]
TEAM_BOOK = {"jordan": [("Kayla", "Ross", 1, "Call Kayla back about the policy quote"), ("Mason", "Hill", 70, "Check in with Mason, 70 days quiet")],
             "priya": [("Zoe", "Price", 0, "Send Zoe the listing options"), ("Leo", "Ward", 3, "Thank Leo for the review")]}
THREADS = {  # contact first name -> [(sender, text, minutes_ago)]
    "Chris": [("user", "Hey Chris, how's the first week in the new house?", 1500), ("contact", "Love it. My brother-in-law Matt is looking too, ok if I send him your way?", 22)],
    "Jenna": [("user", "Hi Jenna! A 4-bedroom on Maple just listed. Want to see it this weekend?", 300), ("contact", "Yes! Could we come by Saturday morning? Ryan wants to see it too.", 48)],
    "Ben": [("contact", "Any word on what the Wrangler is worth?", 260), ("ai", "Hi Ben, Alex here. I'm pulling the numbers now and will have them to you before Saturday.", 255)],
    "Maria": [("contact", "Just left you a review! My friend Dana will text you this week.", 1440), ("user", "Maria, you're the best. Thank you! I'll take great care of Dana.", 1400)],
    "Rachel": [("user", "Good luck at the half marathon this weekend, Rachel!", 2900), ("contact", "Thank you!! First one, wish me luck", 2880)],
    "Marcus": [("user", "Marcus, rates dipped this week. Want me to run the refinance numbers?", 4300), ("contact", "Yes please. Let's talk after Ava's school thing Friday.", 4200)],
    "Tyler": [("user", "Tyler, your policies renew in February. Want me to quote the bundle?", 6000), ("contact", "Sure, send it over when you can.", 5900)],
    "Sam": [("user", "Sam, happy 2 years in the new place! Anything you need?", 9000)],
}
TASKS = [("Ben", "Send Ben the trade-in numbers", "call", "high", 0), ("Jenna", "Book Jenna's Saturday showing", "text", "high", 0),
         ("Maria", "Thank Maria for the referral", "text", "medium", 0), ("David", "Quote coverage for Grace's first car", "call", "medium", 0),
         ("Tyler", "Send Tyler the bundle quote before renewal", "email", "medium", 0)]
MEMOS = [
    ("Marcus", "Marcus closing day notes", 38, ["client", "family"],
     "Just handed Marcus Delgado the keys. His wife is Lena, daughter Ava starts kindergarten this fall. He wants to refinance if rates drop. His brother-in-law is house hunting too.",
     "Closed on the house. Wife Lena, daughter Ava (kindergarten this fall). Refinance if rates drop. Brother-in-law is house hunting."),
    ("Jenna", "Jenna needs more space", 24, ["hot lead"],
     "Jenna Cole called. Baby due in March, so they need four bedrooms. Husband Ryan wants to see the Maple listing. Text her after five.",
     "Baby due in March, needs four bedrooms. Ryan wants to see the Maple listing. Prefers texts after 5 pm."),
    ("Ben", "Ben's Wrangler trade", 19, ["trade"],
     "Ben Carter is trading his 2019 Wrangler. Wants the numbers before Saturday.", "Trading a 2019 Wrangler, wants numbers before Saturday."),
]
UNATTACHED = [("Open house notes, Saturday", 51, ["follow-up"], "Couple from Golden asked about the Maple listing, didn't get their names yet. Ask Maria if they're her friends."),
              ("Trade show thoughts", 33, ["idea"], "Bring QR cards to the home show. Everyone wanted to scan the card.")]
CAMPAIGNS = [("Birthday wishes", "birthday", "cake", "#FF375F", "Happy birthday {first_name}! Hope it's a great one. - Alex"),
             ("Client anniversary", "sold_date", "heart", "#C9A962", "Hey {first_name}, can't believe it's been a year already! Anything I can help with?"),
             ("90-day check-in", None, "chatbubbles", "#34C759", "Hi {first_name}, Alex here. Checking in, how is everything going?")]


async def wipe(db):
    users = [str(u["_id"]) async for u in db.users.find({"seed_key": TAG}, {"_id": 1})]
    for coll in ("contacts", "conversations", "messages", "tasks", "voice_notes", "campaigns", "campaign_enrollments", "contact_events"):
        await db[coll].delete_many({"$or": [{"seed_key": TAG}, {"user_id": {"$in": users}}]})
    await db.users.delete_many({"seed_key": TAG})
    await db.stores.delete_many({"seed_key": TAG})


async def seed(db):
    await wipe(db)
    sid = ObjectId()
    await db.stores.insert_one({"_id": sid, "seed_key": TAG, "name": "Summit Partners", "slug": "summit-partners-demo", "city": "Denver", "state": "CO",
                                "timezone": "America/Denver", "primary_color": "#C9A962", "created_at": ago(200)})

    async def user(first, last, email, role, phone, photo=None):
        uid = ObjectId()
        await db.users.insert_one({"_id": uid, "seed_key": TAG, "email": email, "password": hash_password(PASSWORD), "name": f"{first} {last}", "first_name": first,
                                   "last_name": last, "phone": phone, "role": role, "organization_id": None, "store_id": str(sid), "store_ids": [], "title": "Client Advisor",
                                   "status": "active", "is_active": True, "onboarding_complete": True, "needs_password_change": False, "activation_pending": False,
                                   "phone_verified": True, "tos_accepted": True, "tos_accepted_at": ago(150), "photo_url": photo, "created_at": ago(180), "updated_at": NOW})
        return str(uid)

    alex = await user("Alex", "Morgan", EMAIL, "store_manager", "+15005550090", PH["m1"].replace("1500648767791-00dcc994a43e", "1507003211169-0a1dd7228f2d"))
    ids = {}

    async def contact(owner, i, first, last, photo, touch, ex):
        cid = ObjectId()
        doc = {"_id": cid, "seed_key": TAG, "user_id": owner, "first_name": first, "last_name": last, "name": f"{first} {last}", "phone": f"+15005550{100 + i:03d}",
               "email": f"{first.lower()}.{last.lower()}@invalid.imonsocial.test", "tags": ex.get("tags", []), "status": "active", "ownership_type": "org",
               "created_at": ago(max(touch, 30) + 40), "updated_at": ago(touch), "last_activity_at": ago(touch), "last_contacted_at": ago(touch),
               "personal_details": ex.get("personal_details", {}), "vehicle": ex.get("vehicle", ""), "address_city": "Denver", "address_state": "CO"}
        for k in ("birthday", "date_sold"):
            if ex.get(k):
                doc[k] = ex[k]
        if photo:
            doc["photo_url"] = doc["photo_thumbnail"] = PH[photo]
        await db.contacts.insert_one(doc)
        await db.contact_events.insert_one({"seed_key": TAG, "contact_id": str(cid), "user_id": owner, "event_type": "sms_sent", "channel": "sms", "title": "Text sent",
                                            "content_preview": "Checked in", "timestamp": ago(touch, hours=1)})
        return str(cid)

    for i, (f, l, ph, t, ex) in enumerate(BOOK):
        ids[f] = await contact(alex, i, f, l, ph, t, ex)
    for f, d, kind in (("Jenna", 0, "digital_card_viewed"), ("Olivia", 1, "digital_card_viewed"), ("Chris", 0, "link_clicked"), ("Maria", 9, "review_submitted"), ("Marcus", 20, "review_submitted")):
        await db.contact_events.insert_one({"seed_key": TAG, "contact_id": ids[f], "user_id": alex, "event_type": kind, "icon": "eye", "title": "Viewed Digital Card" if "card" in kind else kind.replace("_", " ").title(),
                                            "category": "customer_activity", "timestamp": ago(d, hours=2)})

    for f, msgs in THREADS.items():
        conv = ObjectId()
        last = min(m[2] for m in msgs)
        inbound_last = msgs[-1][0] == "contact"
        await db.conversations.insert_one({"_id": conv, "seed_key": TAG, "user_id": alex, "contact_id": ids[f], "contact_phone": f"+15005550{100 + [b[0] for b in BOOK].index(f):03d}",
                                           "contact_name": f"{f} {[b[1] for b in BOOK if b[0] == f][0]}", "status": "active", "ai_enabled": True, "created_at": ago(minutes=max(m[2] for m in msgs) + 60),
                                           "last_message_at": ago(minutes=last), "unread": inbound_last and last < 600, "unread_count": 1 if inbound_last and last < 600 else 0,
                                           "needs_assistance": False, "unanswered_customer_replies": 1 if inbound_last else 0})
        for sender, text, mins in msgs:
            await db.messages.insert_one({"seed_key": TAG, "conversation_id": str(conv), "user_id": alex, "content": text, "sender": sender, "sender_id": alex if sender != "contact" else None,
                                          "timestamp": ago(minutes=mins), "status": "received" if sender == "contact" else "delivered",
                                          "direction": "inbound" if sender == "contact" else "outbound", "channel": "sms", "event_type": "sms_received" if sender == "contact" else "sms_sent"})

    for f, title, action, prio, d in TASKS:
        await db.tasks.insert_one({"seed_key": TAG, "user_id": alex, "contact_id": ids[f], "contact_name": f"{f} {[b[1] for b in BOOK if b[0] == f][0]}", "type": "follow_up",
                                   "source": "voice_memo" if f == "Ben" else "manual", "title": title, "description": "", "action_type": action, "priority": prio,
                                   "priority_order": 1 if prio == "high" else 2, "status": "pending", "completed": False, "due_date": NOW.replace(hour=23, minute=0) + timedelta(days=d),
                                   "has_time": False, "appointment_type": "task", "created_at": ago(1)})

    for f, title, dur, tags, transcript, summary in MEMOS:
        await db.voice_notes.insert_one({"seed_key": TAG, "user_id": alex, "kind": "memo", "audio_url": "/api/images/voice-notes/demo/none.m4a", "audio_path": "none", "duration": float(dur),
                                         "source": TAG, "suggested_contacts": [], "contact_id": ids[f], "contact_name": f"{f} {[b[1] for b in BOOK if b[0] == f][0]}", "title": title,
                                         "tags": tags, "transcript": transcript, "summary": summary, "created_at": ago(2, hours=3), "attached_at": ago(2, hours=2)})
    for title, dur, tags, transcript in UNATTACHED:
        await db.voice_notes.insert_one({"seed_key": TAG, "user_id": alex, "kind": "memo", "audio_url": "/api/images/voice-notes/demo/none.m4a", "audio_path": "none", "duration": float(dur),
                                         "source": TAG, "suggested_contacts": [], "unattached": True, "title": title, "tags": tags, "transcript": transcript, "summary": transcript,
                                         "created_at": ago(1, hours=5)})

    for name, date_type, icon, color, tmpl in CAMPAIGNS:
        camp = ObjectId()
        doc = {"_id": camp, "seed_key": TAG, "user_id": alex, "store_id": str(sid), "name": name, "type": date_type or "custom", "icon": icon, "color": color,
               "delivery_mode": "manual", "ai_enabled": True, "active": True, "created_at": ago(90),
               "sequences": [{"step": 1, "delay_days": 0 if date_type else 90, "delay_months": 0, "channel": "sms", "ai_generated": False, "message_template": tmpl, "media_urls": []}]}
        if date_type:
            doc["date_type"] = date_type
        else:
            doc["trigger_tag"] = "sold"
        await db.campaigns.insert_one(doc)
        for f in [b[0] for b in BOOK][: (14 if date_type == "birthday" else 9 if date_type else 5)]:
            await db.campaign_enrollments.insert_one({"seed_key": TAG, "user_id": alex, "campaign_id": str(camp), "contact_id": ids[f], "contact_name": f,
                                                      "current_step": 1, "status": "active", "enrolled_at": ago(60), "next_send_at": ago(-20), "messages_sent": []})

    for n, (first, last, key) in enumerate(TEAM):
        rep = await user(first, last, f"{key}.demo@invalid.imonsocial.test", "user", f"+15005550{91 + n}")
        for j, (cf, cl, touch, task) in enumerate(TEAM_BOOK[key]):
            cid = await contact(rep, 40 + n * 10 + j, cf, cl, None, touch, {})
            await db.tasks.insert_one({"seed_key": TAG, "user_id": rep, "contact_id": cid, "contact_name": f"{cf} {cl}", "type": "follow_up", "source": "manual", "title": task,
                                       "action_type": "call", "priority": "high", "priority_order": 1, "status": "pending", "completed": False,
                                       "due_date": NOW.replace(hour=23, minute=0), "has_time": False, "appointment_type": "task", "created_at": ago(1)})
    print(f"seeded store {sid}, manager {alex} ({EMAIL} / {PASSWORD}), {len(BOOK)} contacts, {len(THREADS)} threads")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if "--wipe" in sys.argv:
        await wipe(db)
        print("wiped")
    else:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
