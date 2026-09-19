"""Idempotent seed: preview-only org admin on the TEST_Store_Org (69a907033b77512d1d8d8a08) for the Communications screen tests."""
import asyncio, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient
from routers.auth import hash_password

EMAIL = "qa-orgadmin@invalid.imonsocial.test"
PASSWORD = "OrgAdmin123!"
ORG_ID = "69a907033b77512d1d8d8a08"
STORE_ID = "69a907033b77512d1d8d8a4a"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    store = await db.stores.find_one({"organization_id": ORG_ID}, {"_id": 1})
    doc = {
        "name": "QA Org Admin", "email": EMAIL, "password": hash_password(PASSWORD), "role": "org_admin",
        "organization_id": ORG_ID, "store_id": str(store["_id"]) if store else None, "phone": "+15005550088",
        "is_active": True, "status": "active", "onboarding_complete": True, "phone_verified": True, "updated_at": datetime.now(timezone.utc),
    }
    r = await db.users.update_one({"email": EMAIL}, {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
    print("upserted" if r.upserted_id else "updated", EMAIL, "org", ORG_ID, "store", doc["store_id"])


asyncio.run(main())
