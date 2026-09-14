"""Leaderboard demo data on the QA Jeep 979a client (preview only). Idempotent; `--wipe` removes it.
Seeds 3 sales people, 1 parts, 1 body shop with completed shops this month + last month so the report shows ranked boards with badges."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
CLIENT_ID = "6aa6d7dfb4c41decb2734ec4"
TAG = "qa_leader_demo"
PEOPLE = [("Bud Ward", "sales", "+15005550701", [(88, 0), (74, 1), (60, 35)]), ("Jessi Lane", "sales", "+15005550702", [(92, 0), (81, 34)]), ("Tom Reyes", "sales", "+15005550703", [(58, 0), (66, 2), (70, 3), (64, 33)]),
          ("Pat Counter", "parts", "+15005550704", [(84, 1), (72, 36)]), ("Dana Estimator", "collision", "+15005550705", [(77, 1)])]


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await db.roleplay_sessions.delete_many({TAG: True})
    await db.call_evaluations.delete_many({TAG: True})
    await db.shop_targets.delete_many({TAG: True})
    if wipe:
        print("wiped")
        return
    now = datetime.now(timezone.utc)
    if now.day < 5:
        now = now.replace(day=6)
    for name, dept, phone, shops in PEOPLE:
        t = await db.shop_targets.insert_one({"client_id": CLIENT_ID, "name": name, "phone": phone, "department": dept, "title": "", "active": True, "challenge_history": [], "created_at": now, "updated_at": now, TAG: True})
        for score, days_ago in shops:
            when = now.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
            ev = await db.call_evaluations.insert_one({"call_sid": f"RP_{TAG}_{ObjectId()}", "is_mystery_shop": True, "department": dept.title(), "score_pct": score, "critical_misses": [] if score >= 70 else ["x"],
                                                        "results": [{"criterion_id": "x", "text": "Asked for an appointment with two times", "critical": True, "passed": score >= 70}, {"criterion_id": "y", "text": "Got the caller's phone number", "critical": False, "passed": score >= 60}],
                                                        "summary": f"{name} took a {dept} call and scored {score}%.", "coaching": ["Offer two appointment times before the caller asks."] if score < 80 else ["Keep leading with the appointment."], "wins": ["Warm greeting"],
                                                        "created_at": when, TAG: True})
            await db.roleplay_sessions.insert_one({"kind": "mystery_shop", "client_id": CLIENT_ID, "target_id": str(t.inserted_id), "rep_name": name, "rep_phone": phone, "department": dept, "status": "completed",
                                                   "scheduled_for": when, "started_at": when, "ended_at": when + timedelta(minutes=4), "score_pct": score, "adherence_pct": score, "evaluation_id": str(ev.inserted_id),
                                                   "script_title": f"Shopper: {dept} call", "persona": {"name": "Shopper"}, "turns": [{"role": "customer", "text": "Hi, is this the store?"}, {"role": "rep", "text": f"This is {name}."}],
                                                   "created_at": when, TAG: True})
    print("seeded", len(PEOPLE), "people on", CLIENT_ID)


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
