"""Lot photo links: when a customer asks about ONE vehicle that has a website page, Jessi's inventory
context carries a tracked short link (per contact); clicking it logs a 'Viewed Vehicle Online' event + signal.
Run: cd /app/backend && python -m pytest tests/test_vehicle_link.py -q -p no:randomly
"""
import os
import asyncio
import pytest
import requests
from datetime import datetime, timedelta
from urllib.parse import unquote
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
API = "http://127.0.0.1:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
LISTING = "https://dealer.example.com/inventory/2023-jeep-gladiator-qalink"


@pytest.fixture(scope="module")
def seed():
    mgr = DB.users.find_one({"email": "qa-manager@invalid.imonsocial.test"})
    uid, store = str(mgr["_id"]), str(mgr["store_id"])
    contact = DB.contacts.insert_one({"user_id": uid, "first_name": "Link", "last_name": "Shopper", "phone": "+15005550077", "tags": ["qalink"], "created_at": datetime.utcnow()}).inserted_id
    veh = DB.inventory.insert_one({"name": "2023 Jeep Gladiator Rubicon QALINK", "category": "vehicle", "status": "available", "price": 44900.0, "store_id": store,
                                   "created_by_user_id": uid, "attributes": {"year": "2023", "make": "Jeep", "model": "Gladiator", "trim": "Rubicon QALINK", "stock_number": "QALINK1", "vin": "1C6JJTBG0PLQALINK"},
                                   "listing_url": LISTING, "images": ["https://img.example.com/g1.jpg"], "primary_image": "https://img.example.com/g1.jpg",
                                   "is_visible": True, "source_system": "test", "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}).inserted_id
    yield {"uid": uid, "contact": str(contact), "veh": str(veh)}
    DB.inventory.delete_one({"_id": veh})
    DB.contacts.delete_one({"_id": contact})
    DB.short_urls.delete_many({"link_type": "vehicle_listing", "original_url": LISTING})
    DB.short_url_clicks.delete_many({"short_code": {"$in": [s["short_code"] for s in DB.short_urls.find({"original_url": LISTING})]}})
    DB.contact_events.delete_many({"contact_id": str(contact)})
    DB.engagement_signals.delete_many({"contact_id": str(contact)})
    DB.notifications.delete_many({"contact_id": str(contact)})


def search(uid, message, contact_id):
    import sys
    sys.path.insert(0, "/app/backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    import routers.database as rdb
    from routers.ai_reply import _search_inventory_context

    async def go():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        rdb._db = db  # create_short_url uses get_db()
        return await _search_inventory_context(db, uid, message, contact_id)
    return asyncio.run(go())


class TestVehicleLink:
    def test_specific_ask_gets_tracked_short_link(self, seed):
        ctx, media, link = search(seed["uid"], "Do you still have the Gladiator Rubicon QALINK?", seed["contact"])
        assert "Gladiator" in ctx and media == ["https://img.example.com/g1.jpg"]
        assert link and link["vehicle"].startswith("2023 Jeep Gladiator") and "/api/s/" in link["url"]
        assert LISTING not in ctx  # the LLM never sees the raw URL
        doc = DB.short_urls.find_one({"original_url": LISTING, "link_type": "vehicle_listing"})
        assert doc and doc["metadata"]["contact_id"] == seed["contact"] and doc["reference_id"].endswith(seed["contact"])
        pytest.short_code = doc["short_code"]

    def test_broad_ask_has_no_link(self, seed):
        ctx, media, link = search(seed["uid"], "What trucks do you have?", seed["contact"])
        assert ctx and link is None

    def test_click_redirects_and_logs_vehicle_view(self, seed):
        r = requests.get(f"{API}/s/{pytest.short_code}", allow_redirects=False, headers={"User-Agent": "Mozilla/5.0 (iPhone) Safari"}, timeout=30)
        # short links serve a tiny HTML page (for OG previews) that immediately replaces location with the listing
        assert r.status_code == 200 and f"window.location.replace(\"{LISTING}" in r.text
        import time
        for _ in range(20):
            ev = DB.contact_events.find_one({"contact_id": seed["contact"], "event_type": "vehicle_link_clicked"})
            if ev:
                break
            time.sleep(0.25)
        assert ev and "Gladiator" in ev["description"] and ev["title"] == "Viewed Vehicle Online"
        sig = DB.engagement_signals.find_one({"contact_id": seed["contact"], "signal_type": "vehicle_viewed"})
        assert sig is not None
        notif = DB.notifications.find_one({"contact_id": seed["contact"], "type": "engagement_signal"})
        assert notif and "Gladiator" in notif["title"]
        # hot shopper alert: vehicle-first copy + deep link into the thread with a ready-to-send text
        assert notif["title"] == "Link just opened the Gladiator" and notif["message"].startswith("2023 Jeep Gladiator")
        assert notif["link"].startswith(f"/thread/{seed['contact']}?prefill=") and "Gladiator" in unquote(notif["link"])
        assert notif["inventory_id"] == seed["veh"]

    def test_repeat_view_says_back_on_it(self, seed):
        DB.engagement_signals.update_many({"contact_id": seed["contact"]}, {"$set": {"created_at": datetime.utcnow() - timedelta(minutes=40)}})
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        import routers.database as rdb
        from routers.engagement_signals import record_signal

        async def go():
            rdb._db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            await record_signal("vehicle_viewed", seed["uid"], seed["contact"], "Link Shopper",
                                {"vehicle": "2023 Jeep Gladiator Rubicon QALINK", "inventory_id": seed["veh"], "link_type": "vehicle_listing"})
        asyncio.run(go())
        notif = DB.notifications.find_one({"contact_id": seed["contact"], "type": "engagement_signal"}, sort=[("created_at", -1)])
        assert notif["title"] == "Link is back on the Gladiator"
        assert "opened 2 times" in notif["message"]

    def test_alert_center_shows_text_action_now(self, seed):
        r = requests.post(f"{API}/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}, timeout=30)
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        r = requests.get(f"{API}/notification-center/{seed['uid']}?feed=for_you", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text
        rows = [i for i in r.json()["notifications"] if i.get("contact_id") == seed["contact"] and i["type"] == "engagement_signal"]
        assert rows, r.json()["notifications"][:3]
        row = rows[0]
        assert row["bucket"] == "now" and row["title"] == "Text Link about the Gladiator"
        assert row["action"]["label"] == "Text" and row["action"]["link"].startswith(f"/thread/{seed['contact']}?prefill=")
