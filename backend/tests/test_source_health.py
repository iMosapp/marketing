"""Source health: seeds a temporary producing-then-quiet source, checks classification, runs the alert job
twice (second run must dedupe), then cleans up everything it created."""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

STORE = "69a0b7095fddcede09591668"
TAG = "source_health_probe"


async def seed_source(db, name, offsets_days):
    sid = ObjectId()
    now = datetime.now(timezone.utc)
    await db.lead_sources.insert_one({"_id": sid, "name": name, "store_id": STORE, "is_active": True, "probe": TAG, "created_at": now})
    if offsets_days:
        await db.inbound_leads.insert_many([{"source_id": str(sid), "store_id": STORE, "received_at": now - timedelta(days=d), "is_test": False,
                                             "full_name": f"probe {i}", "phone": "5005550100", "probe": TAG} for i, d in enumerate(offsets_days)])
    return str(sid)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    from services.source_health import source_health, run_source_health_alerts
    # 10 leads over 28d, last one 10 days ago -> gap 67h, threshold 201h, quiet 240h => quiet
    quiet_id = await seed_source(db, "Probe Quiet Feed", [10, 11, 13, 15, 17, 19, 21, 23, 25, 27])
    # 10 leads, last one 2 days ago -> 48h < 201h => healthy
    healthy_id = await seed_source(db, "Probe Healthy Feed", [2, 4, 6, 9, 12, 15, 18, 21, 24, 27])
    # 2 leads only -> slow (not enough volume to judge)
    slow_id = await seed_source(db, "Probe Slow Feed", [5, 20])
    # never produced -> new
    new_id = await seed_source(db, "Probe New Feed", [])
    # hourly feed: 100 leads in 28d (gap 6.7h) with last one 3 days ago -> threshold floors at 48h => quiet
    hourly_id = await seed_source(db, "Probe Hourly Feed", [3 + i * 0.25 for i in range(100)])
    try:
        rows = {r["source_id"]: r for r in await source_health(db, STORE)}
        checks = {
            "quiet feed flagged quiet": rows[quiet_id]["status"] == "quiet",
            "quiet feed threshold ~201h": abs(rows[quiet_id]["alert_after_hours"] - 201.6) < 1,
            "healthy feed healthy": rows[healthy_id]["status"] == "healthy",
            "slow feed slow": rows[slow_id]["status"] == "slow",
            "new feed new": rows[new_id]["status"] == "new",
            "hourly feed quiet with 48h floor": rows[hourly_id]["status"] == "quiet" and rows[hourly_id]["alert_after_hours"] == 48,
            "quiet sorted first": [r["status"] for r in await source_health(db, STORE)][:2] == ["quiet", "quiet"],
        }
        sent1 = await run_source_health_alerts()
        logs = await db.source_health_alert_log.count_documents({"source_id": {"$in": [quiet_id, hourly_id]}})
        src = await db.lead_sources.find_one({"_id": ObjectId(quiet_id)})
        checks["job logged both quiet sources"] = logs == 2
        checks["health_alert_sent_at stamped"] = src.get("health_alert_sent_at") is not None and src.get("health_status") == "quiet"
        sent2 = await run_source_health_alerts()
        logs2 = await db.source_health_alert_log.count_documents({"source_id": {"$in": [quiet_id, hourly_id]}})
        checks["second run dedupes (no new log)"] = logs2 == 2
        for k, ok in checks.items():
            print("PASS" if ok else "FAIL", k)
        print("pushes run1:", sent1, "run2:", sent2, "| quiet row:", {k: rows[quiet_id][k] for k in ("status", "leads_28d", "quiet_hours", "expected_gap_hours", "alert_after_hours")})
        assert all(checks.values())
    finally:
        await db.lead_sources.delete_many({"probe": TAG})
        await db.inbound_leads.delete_many({"probe": TAG})
        await db.source_health_alert_log.delete_many({"source_id": {"$in": [quiet_id, healthy_id, slow_id, new_id, hourly_id]}})
        print("cleaned")


asyncio.run(main())
