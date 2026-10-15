"""Idempotent preview seed: a team member with a (fake, Twilio test-range) texting number, so the app composer uses the provider path
(channel sms) and the consent gate. No organization: an individual account. Every send stays mocked by the preview guard (SMS_SEND_ONLY_TO).
`--wipe` removes the user and the contacts it owns."""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient

from routers.auth import hash_password
from tests import qa_creds

EMAIL = "qa-consent-rep@invalid.imonsocial.test"
NUMBER = "+15005550099"
STORE_ID = "69a0b7095fddcede09591668"


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if wipe:
        u = await db.users.find_one({"email": EMAIL}, {"_id": 1})
        if u:
            await db.contacts.delete_many({"user_id": str(u["_id"])})
            await db.users.delete_one({"_id": u["_id"]})
        print("wiped", EMAIL)
        return
    now = datetime.now(timezone.utc)
    doc = {"name": "Casey Consent", "email": EMAIL, "password": hash_password(qa_creds.password_for(EMAIL)), "role": "user", "store_id": STORE_ID,
           "twilio_number": NUMBER, "is_active": True, "status": "active", "onboarding_complete": True, "phone_verified": True, "updated_at": now}
    r = await db.users.update_one({"email": EMAIL}, {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True)
    u = await db.users.find_one({"email": EMAIL}, {"_id": 1})
    from services import sender_policy as sp
    pol = await sp.check(db, from_phone=NUMBER, user_id=str(u["_id"]), org_id=None, platform=False)
    print("upserted" if r.upserted_id else "updated", EMAIL, str(u["_id"]), "sender_policy:", pol.get("allowed"), pol.get("code"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--wipe", action="store_true")
    asyncio.run(main(p.parse_args().wipe))
