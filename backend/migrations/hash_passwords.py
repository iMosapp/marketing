"""
One-time migration: hash all existing plain-text passwords with bcrypt.
Run: python migrations/hash_passwords.py
"""
import asyncio
import os
import sys
import bcrypt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


async def migrate():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "imos_db")
    if not mongo_url:
        print("MONGO_URL not set")
        return

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    cursor = db.users.find({"password": {"$exists": True}}, {"_id": 1, "email": 1, "password": 1})
    upgraded = 0
    skipped = 0

    async for user in cursor:
        pw = user.get("password", "")
        if pw.startswith("$2b$") or pw.startswith("$2a$"):
            skipped += 1
            continue
        hashed = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"password": hashed}})
        upgraded += 1
        print(f"  Hashed password for {user.get('email', '?')}")

    print(f"\nDone. Upgraded: {upgraded}, Already hashed: {skipped}")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
