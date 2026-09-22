"""Preview demo data for the Jessi Onboarding dashboard (no texts go out). Idempotent; `--wipe` removes.
Creates two Jessi-onboarded users under Forest: Quinn QA-Onboard (+15005550077, waiting on them at INTERVIEW_INVITED for ~30 h,
so the morning digest lists them) and Riley QA-Onboard (+15005550078, ACTIVATION_SENT, write-up confirmed, photo in).
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/seed_jessi_onboarding_demo.py [--wipe]"""
import asyncio
import os
import secrets
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor.motor_asyncio import AsyncIOMotorClient

from services import jessi_onboarding as jo

PEOPLE = [
    {"first": "Quinn", "phone": "+15005550077", "state": "INTERVIEW_INVITED", "email": "", "age_h": 36},
    {"first": "Riley", "phone": "+15005550078", "state": "ACTIVATION_SENT", "email": "riley.qa@invalid.imonsocial.test"},
]


async def wipe(db):
    for p in PEOPLE:
        async for u in db.users.find({"phone": p["phone"]}, {"_id": 1}):
            await db.user_onboarding.delete_many({"user_id": str(u["_id"])})
            await db.password_reset_tokens.delete_many({"user_id": str(u["_id"])})
            await db.contacts.delete_many({"user_id": str(u["_id"])})
            await db.contact_events.delete_many({"user_id": str(u["_id"])})
            await db.users.delete_one({"_id": u["_id"]})
        await db.user_onboarding.delete_many({"phone": p["phone"]})


async def seed(db):
    await wipe(db)
    admin = await db.users.find_one({"email": "forest@imosapp.com"})
    snd = await jo.sender(db)
    now = jo._now()
    out = []
    for p in PEOPLE:
        name = f"{p['first']} QA-Onboard"
        res = await db.users.insert_one({"first_name": p["first"], "last_name": "QA-Onboard", "name": name, "phone": p["phone"], "email": p["email"], "role": "user", "is_active": True,
                                         "activation_pending": True, "needs_password_change": True, "jessi_onboarding": True, "password": "x", "created_at": now, "created_by": str(admin["_id"]),
                                         "persona": {"bio": "I've sold trucks in southern Utah for twelve years and I keep it plain and friendly.", "hometown": "Cedar City", "tone": "friendly", "specialties": ["Trucks", "First-time buyers"]} if p["state"] != "INTERVIEW_INVITED" else {}})
        uid = str(res.inserted_id)
        idx = jo.ORDER[p["state"]]
        base_h = p.get("age_h", 1)
        steps = {s: now - timedelta(hours=(idx - i) * 3 + base_h) for i, s in enumerate(jo.STATES[: idx + 1])}
        first = p["first"]
        thread = [
            {"role": "jessi", "text": jo.text("intro", first=first), "at": steps["JESSI_INTRODUCED"], "ok": True, "kind": "intro"},
            {"role": "jessi", "text": jo.text("vcf"), "at": steps["CONTACT_CARD_SENT"], "ok": True, "kind": "vcf", "media": [jo.vcf_url()]},
            {"role": "jessi", "text": jo.text("explain"), "at": steps["INTERVIEW_INVITED"], "ok": True, "kind": "explain"},
        ]
        doc = {"user_id": uid, "first_name": first, "name": name, "phone": p["phone"], "sender_user_id": str(snd["_id"]), "from_number": jo.sender_number(snd), "store_id": None, "organization_id": None,
               "role": "user", "created_by": str(admin["_id"]), "state": p["state"], "steps": steps, "events": [{"type": s, "at": steps[s], "note": "", "ref": ""} for s in jo.STATES[: idx + 1]],
               "thread": thread, "facts": {"email": p["email"]}, "seen_sids": [], "reminders": {"count": 0, "last_at": None}, "paused": False, "call_token": secrets.token_urlsafe(18),
               "created_at": steps["NOT_STARTED"], "updated_at": now, "qa_seed": True}
        thread.append({"role": "jessi", "text": jo.text("invite", phone=jo._mask(p["phone"]), link=jo.call_link(doc)), "at": steps["INTERVIEW_INVITED"], "ok": True, "kind": "invite"})
        if p["state"] == "INTERVIEW_INVITED":
            asked = now - timedelta(hours=base_h - 6) if base_h > 6 else now - timedelta(minutes=40)
            thread.append({"role": "user", "text": "what does this app even do?", "at": asked, "sid": "SMseed1"})
            thread.append({"role": "jessi", "text": "It keeps up with your customers by text for you: reminders, your digital card, review asks. Ready for the setup call? Reply CALL.", "at": asked + timedelta(minutes=1), "ok": True, "kind": "chat"})
            doc["last_inbound_at"] = asked
        else:
            thread += [
                {"role": "user", "text": "CALL", "at": steps["INTERVIEW_STARTED"], "sid": "SMseed2"},
                {"role": "jessi", "text": jo.text("calling", first=first), "at": steps["INTERVIEW_STARTED"], "ok": True, "kind": "calling"},
                {"role": "jessi", "text": jo.text("summary", summary="You've sold trucks in southern Utah for twelve years, you grew up in Cedar City, and you like to keep things plain and friendly with your customers."), "at": steps["INTERVIEW_COMPLETE"], "ok": True, "kind": "summary"},
                {"role": "user", "text": "Yep", "at": steps["PHOTO_REQUESTED"], "sid": "SMseed3"},
                {"role": "jessi", "text": jo.text("photo"), "at": steps["PHOTO_REQUESTED"], "ok": True, "kind": "photo_ask"},
                {"role": "user", "text": "", "at": steps["PHOTO_RECEIVED"], "sid": "SMseed4", "media": ["https://app.imonsocial.com/api/public/shop-contact/logo.png"]},
                {"role": "jessi", "text": jo.text("photo_done"), "at": steps["PHOTO_RECEIVED"], "ok": True, "kind": "photo_done"},
                {"role": "jessi", "text": jo.text("activation", first=first, link="https://app.imonsocial.com/auth/activate?token=seed"), "at": steps["ACTIVATION_SENT"], "ok": True, "kind": "activation"},
            ]
            doc.update({"summary_text": "You've sold trucks in southern Utah for twelve years, you grew up in Cedar City, and you like to keep things plain and friendly with your customers.",
                        "summary_confirmed": True, "photo_url": "https://app.imonsocial.com/api/public/shop-contact/logo.png", "activation_url": "https://app.imonsocial.com/auth/activate?token=seed",
                        "last_inbound_at": steps["PHOTO_RECEIVED"]})
        doc["last_outbound_at"] = thread[-1]["at"]
        await db.user_onboarding.insert_one(doc)
        out.append((name, uid, p["state"], jo.call_link(doc)))
    return out


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if "--wipe" in sys.argv:
        await wipe(db)
        print("wiped")
        return
    for name, uid, state, link in await seed(db):
        print(f"{name}  user_id={uid}  state={state}\n  detail: /admin/onboarding-jessi/{uid}\n  call page: {link}")


if __name__ == "__main__":
    asyncio.run(main())
