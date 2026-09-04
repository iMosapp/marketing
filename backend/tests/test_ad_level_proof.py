"""Ad-level proof: seeds leads with Facebook attribution in a throwaway store, checks campaign rollups,
estimated vs set spend, best-ad line and headline. Cleans up after itself."""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

STORE = str(ObjectId())
TAG = "ad_proof_probe"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    from routers.lead_intake import compute_proof
    now = datetime.now(timezone.utc)
    src_id = ObjectId()
    await db.lead_sources.insert_one({"_id": src_id, "name": "Probe FB Source", "store_id": STORE, "is_active": True, "monthly_cost": 3000, "probe": TAG})
    # campaign A: 4 leads, 2 sold (ads: video x3 -> 2 sold, carousel x1 -> 0). campaign B: 2 leads, 0 sold. no-attribution: 2 leads, 1 sold
    plan = [("June Truck Month", "Blue F-150 video", True), ("June Truck Month", "Blue F-150 video", True), ("June Truck Month", "Blue F-150 video", False),
            ("June Truck Month", "Carousel", False), ("Spring Clearance", "Static", False), ("Spring Clearance", "Static", False), (None, None, True), (None, None, False)]
    contact_ids, lead_docs = [], []
    for i, (camp, ad, is_sold) in enumerate(plan):
        cid = ObjectId()
        contact_ids.append(cid)
        await db.contacts.insert_one({"_id": cid, "name": f"probe {i}", "phone": "5005550100", "store_id": STORE, "probe": TAG,
                                      **({"date_sold": (now - timedelta(days=2)).isoformat()} if is_sold else {})})
        doc = {"conversation_id": str(ObjectId()), "contact_id": str(cid), "store_id": STORE, "source_id": str(src_id), "source_name": "Probe FB Source",
               "received_at": now - timedelta(days=10 + i), "is_test": False, "probe": TAG}
        if camp:
            doc["attribution"] = {"kind": "ad", "source": "meta_lead_ad", "campaign": camp, "ad": ad, "source_label": f"Facebook ad: {camp}"}
        lead_docs.append(doc)
    await db.inbound_leads.insert_many(lead_docs)
    try:
        p = await compute_proof(db, STORE, 90)
        camps = {c["campaign"]: c for c in p["campaigns"]}
        a, b = camps["June Truck Month"], camps["Spring Clearance"]
        src_period = 3000  # source started paying inside the window (first lead 10d ago) -> 1 month charged, not 3
        checks = {
            "two campaigns": len(camps) == 2,
            "A leads/sold": (a["leads"], a["sold"], a["close_rate"]) == (4, 2, 50),
            "B leads/sold": (b["leads"], b["sold"]) == (2, 0),
            "A estimated spend = 3000 * 4/8": a["cost_mode"] == "estimated" and abs(a["period_cost"] - src_period * 4 / 8) < 0.01,
            "A est cost per sale = 1500/2": abs(a["cost_per_sale"] - 750) < 0.01,
            "source months_charged = 1": next(s for s in p["sources"] if s["source_name"] == "Probe FB Source")["months_charged"] == 1,
            "best ad first": a["ads"][0]["ad"] == "Blue F-150 video" and a["ads"][0]["sold"] == 2 and a["ad_count"] == 2,
            "sorted sold first": p["campaigns"][0]["campaign"] == "June Truck Month",
            "headline present": any(h.startswith("Ad that sells: June Truck Month") for h in p["headlines"]),
            "source row unchanged": next(s for s in p["sources"] if s["source_name"] == "Probe FB Source")["cost_per_sale"] == 1000.0,
        }
        # set a real campaign spend and recompute
        await db.campaign_costs.insert_one({"store_id": STORE, "campaign_key": "june truck month", "campaign": "June Truck Month", "monthly_cost": 1200, "probe": TAG})
        p2 = await compute_proof(db, STORE, 90)
        a2 = next(c for c in p2["campaigns"] if c["campaign"] == "June Truck Month")
        checks["set spend wins: 1200 x 1 month = 1200"] = a2["cost_mode"] == "set" and a2["period_cost"] == 1200 and a2["monthly_cost"] == 1200
        checks["set cost per sale 600"] = a2["cost_per_sale"] == 600
        for k, ok in checks.items():
            print("PASS" if ok else "FAIL", k)
        print([h for h in p["headlines"] if "Ad that sells" in h])
        assert all(checks.values())
    finally:
        await db.lead_sources.delete_many({"probe": TAG})
        await db.inbound_leads.delete_many({"probe": TAG})
        await db.contacts.delete_many({"probe": TAG})
        await db.campaign_costs.delete_many({"probe": TAG})
        print("cleaned")


asyncio.run(main())
