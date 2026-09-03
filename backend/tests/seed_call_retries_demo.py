"""Seed/clean demo call-retry data for the Leads > Speed 'Call Retries' card. Usage: python tests/seed_call_retries_demo.py seed|clean"""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from routers.database import get_db

TAG = "call_retry_demo_seed"

async def main(cmd):
    db = get_db()
    if cmd == "clean":
        for col in (db.contact_events, db.tasks, db.contacts):
            r = await col.delete_many({"seed_tag": TAG})
            print(col.name, "deleted", r.deleted_count)
        return
    forest = await db.users.find_one({"email": "forest@imosapp.com"}, {"_id": 1})
    other = await db.users.find_one({"email": {"$ne": "forest@imosapp.com"}, "status": "active", "name": {"$exists": True}}, {"_id": 1, "name": 1})
    now = datetime.now(timezone.utc)
    plan = {str(forest["_id"]): dict(misses=6, connected=2, replied=1, open=1, gave_up=0, just_tried=2),
            str(other["_id"]): dict(misses=4, connected=1, replied=0, open=2, gave_up=1, just_tried=1)}
    for uid, p in plan.items():
        c = await db.contacts.insert_one({"user_id": uid, "name": "Seed Retry", "first_name": "Seed", "phone": "+15005550099", "created_at": now, "seed_tag": TAG})
        cid = str(c.inserted_id)
        for i in range(p["misses"]):
            await db.contact_events.insert_one({"event_type": "call_voicemail" if i % 2 == 0 else "call_no_answer", "title": "Left voicemail", "user_id": uid,
                                                "contact_id": cid, "category": "call", "timestamp": now - timedelta(hours=i + 1), "created_at": now, "seed_tag": TAG})
        def task(**kw):
            base = {"user_id": uid, "contact_id": cid, "type": "call", "auto_kind": "call_retry", "title": "Try Seed again", "status": "pending",
                    "completed": False, "due_date": now + timedelta(hours=2), "created_at": now - timedelta(hours=3), "seed_tag": TAG}
            base.update(kw); return base
        docs = []
        docs += [task(completed=True, status="completed", completed_via="call_connected", completed_at=now - timedelta(hours=1), retry_attempt=[1, 3][k % 2]) for k in range(p["connected"])]
        docs += [task(completed=True, status="completed", completed_via="customer_replied", completed_at=now - timedelta(hours=1), retry_attempt=2,
                      just_tried_sent_at=now - timedelta(hours=1, minutes=35)) for _ in range(p["replied"])]
        docs += [task(retry_attempt=1, **({"just_tried_sent_at": now - timedelta(hours=2)} if k < (p["just_tried"] - p["replied"]) else {})) for k in range(p["open"])]
        docs += [task(auto_kind="call_retry_final", type="task", title="Seed: 6 tries, no connection", retry_attempt=6) for _ in range(p["gave_up"])]
        # a few closed-without-text misses so the with/without split has a sample
        docs += [task(completed=True, status="completed", completed_via="manual", completed_at=now - timedelta(hours=1), retry_attempt=1) for _ in range(2)]
        await db.tasks.insert_many(docs)
    print("seeded for", list(plan), "other =", other.get("name"))

asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))
