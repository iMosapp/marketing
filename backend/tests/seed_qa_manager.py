"""Idempotent seed: preview-only store manager on Forest's store for UI testing of manager screens."""
import asyncio, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient
from routers.auth import hash_password

EMAIL = "qa-manager@invalid.imonsocial.test"
PASSWORD = "Manager123!"
STORE_ID = "69a0b7095fddcede09591668"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    doc = {
        "name": "QA Manager", "email": EMAIL, "password": hash_password(PASSWORD), "role": "store_manager",
        "store_id": STORE_ID, "is_active": True, "status": "active", "onboarding_complete": True,
        "phone_verified": True, "updated_at": datetime.now(timezone.utc),
    }
    r = await db.users.update_one({"email": EMAIL}, {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
    print("upserted" if r.upserted_id else "updated", EMAIL)


asyncio.run(main())
