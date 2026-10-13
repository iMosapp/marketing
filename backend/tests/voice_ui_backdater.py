"""Smoke helper for the fallback UI run: for `duration` seconds, every 2 s, every OPEN live session of the UI demo user that is younger
than `age` seconds is backdated to `age` seconds ago, so the next heartbeat makes the server stop premium and hand off to mini."""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
user = db.users.find_one({"email": "qa-voice-ui@invalid.imonsocial.test"})
duration = float(sys.argv[1]) if len(sys.argv) > 1 else 90
age = float(sys.argv[2]) if len(sys.argv) > 2 else 70
engine = sys.argv[3] if len(sys.argv) > 3 else None
end = time.time() + duration
while time.time() < end:
    now = datetime.now(timezone.utc)
    q = {"user_id": str(user["_id"]), "status": "open", "started_at": {"$gt": now - timedelta(seconds=age - 5)}}
    if engine:
        q["engine"] = engine
    r = db.live_sessions.update_many(q, {"$set": {"started_at": now - timedelta(seconds=age)}})
    if r.modified_count:
        print(f"{now.isoformat()} backdated {r.modified_count}", flush=True)
    time.sleep(2)
