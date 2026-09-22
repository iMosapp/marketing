"""Mint a fresh single-use Jessi activation link for a Jessi-onboarded user (preview testing of /auth/activate?token=...).
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/mint_activation_link.py +15005550078"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor.motor_asyncio import AsyncIOMotorClient

from services import jessi_onboarding as jo


async def main(phone: str):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    doc = await db.user_onboarding.find_one({"phone": phone})
    if not doc:
        print("no onboarding doc for", phone)
        return
    link = await jo.activation_link(db, doc)
    token = link.split("token=")[-1] if "token=" in link else None
    if not token:  # short link: read the token back from the newest link doc
        t = await db.password_reset_tokens.find_one({"user_id": doc["user_id"], "purpose": "activate_link", "used": False}, sort=[("created_at", -1)])
        token = t["token"]
    base = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
    print(f"{base}/auth/activate?token={token}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "+15005550078"))
