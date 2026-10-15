"""Idempotent preview seed for the subscription lock UI: "QA Launch Locked Co" with an owner and a team member.
`--state canceled|unpaid|past_due_grace|past_due_ended|active` sets the fake Stripe status (default canceled, paid period already over); `--wipe` removes it.
No Stripe or Twilio call is made: the subscription id is fake and only the stored status drives services/billing_lock.py."""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from routers.auth import hash_password
from tests import qa_creds

ORG_NAME = "QA Launch Locked Co"
OWNER = "qa-locked-owner@invalid.imonsocial.test"
REP = "qa-locked-rep@invalid.imonsocial.test"


def status_fields(state: str, now: datetime) -> dict:
    past, future = (now - timedelta(days=2)).isoformat(), (now + timedelta(days=20)).isoformat()
    return {
        "canceled": {"subscription_status": "canceled", "current_period_end": past},
        "unpaid": {"subscription_status": "unpaid", "current_period_end": past},
        "past_due_grace": {"subscription_status": "past_due", "payment_failed_at": (now - timedelta(days=3)).isoformat(), "grace_until": None, "current_period_end": future},
        "past_due_ended": {"subscription_status": "past_due", "payment_failed_at": (now - timedelta(days=20)).isoformat(), "grace_until": None, "current_period_end": past},
        "active": {"subscription_status": "active", "current_period_end": future},
    }[state]


async def main(state: str, wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    org = await db.organizations.find_one({"name": ORG_NAME})
    if wipe:
        if org:
            await db.users.delete_many({"organization_id": str(org["_id"])})
            await db.stores.delete_many({"organization_id": str(org["_id"])})
            await db.organizations.delete_one({"_id": org["_id"]})
        print("wiped", ORG_NAME)
        return
    now = datetime.now(timezone.utc)
    oid = org["_id"] if org else ObjectId()
    store = await db.stores.find_one({"organization_id": str(oid)})
    sid = store["_id"] if store else ObjectId()
    if not store:
        await db.stores.insert_one({"_id": sid, "name": "QA Launch Locked Store", "organization_id": str(oid), "created_at": now})
    ids = {}
    for email, name, role in ((OWNER, "Lena Owner", "store_manager"), (REP, "Ravi Teammate", "user")):
        doc = {"name": name, "email": email, "password": hash_password(qa_creds.password_for(email)), "role": role, "store_id": str(sid),
               "organization_id": str(oid), "is_active": True, "status": "active", "onboarding_complete": True, "phone_verified": True, "updated_at": now}
        await db.users.update_one({"email": email}, {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True)
        ids[email] = str((await db.users.find_one({"email": email}, {"_id": 1}))["_id"])
    customer = {"billing_status": "active", "stripe_subscription_id": "sub_qa_locked_fake", "stripe_customer_id": "cus_qa_locked_fake",
                "owner_user_id": ids[OWNER], "plan": "pilot_store_monthly", **status_fields(state, now)}
    await db.organizations.update_one({"_id": oid}, {"$set": {"name": ORG_NAME, "customer": customer, "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
    print(f"{ORG_NAME} {oid} state={state} owner={OWNER} rep={REP} (billing lock cache clears within 20 s)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--state", default="canceled", choices=["canceled", "unpaid", "past_due_grace", "past_due_ended", "active"])
    p.add_argument("--wipe", action="store_true")
    a = p.parse_args()
    asyncio.run(main(a.state, a.wipe))
