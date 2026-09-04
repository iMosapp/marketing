"""User scenario: $1,000/mo Website spend that started this month, 3 leads, 2 sold. 90-day view must say
$1,000 spent and $500/sale (not $3,000 / $1,500). Also: long-running source charges full window, explicit
spend_started_at override wins, 7-day window prorates."""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

STORE = str(ObjectId())
TAG = "spend_months_probe"


async def seed(db, name, monthly, lead_days, sold_flags, spend_started_at=None):
    now = datetime.now(timezone.utc)
    sid = ObjectId()
    await db.lead_sources.insert_one({"_id": sid, "name": name, "store_id": STORE, "is_active": True, "monthly_cost": monthly, "spend_started_at": spend_started_at, "probe": TAG})
    for d, sold in zip(lead_days, sold_flags):
        cid = ObjectId()
        await db.contacts.insert_one({"_id": cid, "name": "p", "phone": "5005550100", "store_id": STORE, "probe": TAG, **({"date_sold": (now - timedelta(days=1)).isoformat()} if sold else {})})
        await db.inbound_leads.insert_one({"conversation_id": str(ObjectId()), "contact_id": str(cid), "store_id": STORE, "source_id": str(sid), "source_name": name,
                                           "received_at": now - timedelta(days=d), "is_test": False, "probe": TAG})


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    from routers.lead_intake import compute_proof
    now = datetime.now(timezone.utc)
    await seed(db, "Website", 1000, [3, 8, 12], [True, True, False])                       # started this month
    await seed(db, "Cars.com", 1000, [5, 30, 60, 85], [True, False, False, False])          # producing for 85 days -> full window
    await seed(db, "Old Vendor", 1000, [4], [True], spend_started_at=(now - timedelta(days=400)).isoformat())  # override: paying for over a year
    try:
        p90 = {s["source_name"]: s for s in (await compute_proof(db, STORE, 90))["sources"]}
        p30 = {s["source_name"]: s for s in (await compute_proof(db, STORE, 30))["sources"]}
        p7 = {s["source_name"]: s for s in (await compute_proof(db, STORE, 7))["sources"]}
        w90, w30, w7 = p90["Website"], p30["Website"], p7["Website"]
        checks = {
            "90d: Website spent $1,000 (1 month), not $3,000": w90["period_cost"] == 1000 and w90["months_charged"] == 1,
            "90d: Website $500 / sale": w90["cost_per_sale"] == 500,
            "30d: Website $1,000 / $500 per sale": w30["period_cost"] == 1000 and w30["cost_per_sale"] == 500,
            "7d: Website prorated $233": abs(w7["period_cost"] - 1000 * 7 / 30) < 1,
            "90d: Cars.com full 3 months = $3,000": p90["Cars.com"]["period_cost"] == 3000 and p90["Cars.com"]["months_charged"] == 3,
            "90d: Old Vendor override -> full 3 months": p90["Old Vendor"]["period_cost"] == 3000,
            "spend_started_at echoed": w90["spend_started_at"] is not None,
        }
        for k, ok in checks.items():
            print("PASS" if ok else "FAIL", k)
        print({k: w90[k] for k in ("monthly_cost", "months_charged", "period_cost", "cost_per_lead", "cost_per_sale")})
        assert all(checks.values())
    finally:
        await db.lead_sources.delete_many({"probe": TAG})
        await db.inbound_leads.delete_many({"probe": TAG})
        await db.contacts.delete_many({"probe": TAG})
        print("cleaned")


asyncio.run(main())
