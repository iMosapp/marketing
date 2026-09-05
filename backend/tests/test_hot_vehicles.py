"""Hot vehicles: store-wide ranking of vehicles by tracked lot-link opens (x2) + Jessi asks over the last 7 days.
Run: cd /app/backend && python -m pytest tests/test_hot_vehicles.py -q -p no:randomly
"""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
API = "http://127.0.0.1:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json(); u = d["user"]
    return str(u.get("_id") or u.get("id")), d["token"]


@pytest.fixture(scope="module")
def seed():
    uid, tok = login("qa-manager@invalid.imonsocial.test", "Manager123!")
    store = str(DB.users.find_one({"_id": ObjectId(uid)})["store_id"])
    now = datetime.now(timezone.utc)
    v1 = DB.inventory.insert_one({"name": "2024 Toyota Tacoma HOTQA", "status": "available", "price": 42995.0, "store_id": store, "created_by_user_id": uid,
                                  "attributes": {"stock_number": "HOTQA1"}, "primary_image": "https://img.example.com/h1.jpg", "is_visible": True, "created_at": now}).inserted_id
    v2 = DB.inventory.insert_one({"name": "2022 Ford F-150 HOTQA", "status": "available", "price": 45500.0, "store_id": store, "created_by_user_id": uid,
                                  "attributes": {"stock_number": "HOTQA2"}, "is_visible": True, "created_at": now}).inserted_id
    v3 = DB.inventory.insert_one({"name": "2021 Honda Civic HOTQA", "status": "available", "price": 21000.0, "store_id": store, "created_by_user_id": uid,
                                  "attributes": {"stock_number": "HOTQA3"}, "is_visible": True, "created_at": now}).inserted_id
    c1 = DB.contacts.insert_one({"user_id": uid, "first_name": "Hot", "last_name": "Shopper", "phone": "+15005550088", "tags": ["hotqa"], "created_at": now}).inserted_id
    c2 = DB.contacts.insert_one({"user_id": uid, "first_name": "Warm", "last_name": "Browser", "phone": "+15005550089", "tags": ["hotqa"], "created_at": now}).inserted_id
    ev = []
    for i in range(3):  # Tacoma: 3 opens by c1 (2) + c2 (1)
        ev.append({"contact_id": str(c1 if i < 2 else c2), "user_id": uid, "event_type": "vehicle_link_clicked", "title": "Viewed Vehicle Online",
                   "description": "x", "metadata": {"inventory_id": str(v1), "vehicle": "2024 Toyota Tacoma HOTQA"}, "timestamp": now - timedelta(hours=i + 1), "qa": "hotqa"})
    ev.append({"contact_id": str(c2), "user_id": uid, "event_type": "vehicle_link_clicked", "title": "Viewed Vehicle Online", "description": "x",
               "metadata": {"inventory_id": str(v2), "vehicle": "2022 Ford F-150 HOTQA"}, "timestamp": now - timedelta(days=1), "qa": "hotqa"})
    # last week's opens for the F-150 (should count as prev only)
    ev.append({"contact_id": str(c2), "user_id": uid, "event_type": "vehicle_link_clicked", "title": "Viewed Vehicle Online", "description": "x",
               "metadata": {"inventory_id": str(v2), "vehicle": "2022 Ford F-150 HOTQA"}, "timestamp": now - timedelta(days=9), "qa": "hotqa"})
    DB.contact_events.insert_many(ev)
    DB.inventory_interest.insert_many([
        {"inventory_id": str(v2), "contact_id": str(c1), "user_id": uid, "store_id": store, "kind": "asked", "timestamp": now - timedelta(hours=3), "qa": "hotqa"},
        {"inventory_id": str(v2), "contact_id": str(c2), "user_id": uid, "store_id": store, "kind": "asked", "timestamp": now - timedelta(hours=4), "qa": "hotqa"},
        {"inventory_id": str(v2), "contact_id": str(c2), "user_id": uid, "store_id": store, "kind": "asked", "timestamp": now - timedelta(hours=5), "qa": "hotqa"},
    ])
    yield {"uid": uid, "tok": tok, "v1": str(v1), "v2": str(v2), "v3": str(v3), "c1": str(c1), "c2": str(c2)}
    DB.inventory.delete_many({"_id": {"$in": [v1, v2, v3]}})
    DB.contacts.delete_many({"_id": {"$in": [c1, c2]}})
    DB.contact_events.delete_many({"qa": "hotqa"})
    DB.inventory_interest.delete_many({"qa": "hotqa"})


class TestHotVehicles:
    def test_auth(self, seed):
        assert requests.get(f"{API}/inventory/{seed['uid']}/hot", timeout=30).status_code == 401

    def test_ranking_and_shoppers(self, seed):
        r = requests.get(f"{API}/inventory/{seed['uid']}/hot?days=7", headers={"Authorization": f"Bearer {seed['tok']}"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        mine = [v for v in d["vehicles"] if v["inventory_id"] in (seed["v1"], seed["v2"], seed["v3"])]
        assert [v["inventory_id"] for v in mine] == [seed["v1"], seed["v2"]]  # Tacoma 3x2=6 beats F-150 1x2+3=5; Civic has nothing
        tac, f150 = mine
        assert tac["clicks"] == 3 and tac["asks"] == 0 and tac["shopper_count"] == 2 and tac["score"] == 6 and tac["trend"] == "new"
        assert tac["photo"] is None and tac["primary_image"].endswith("h1.jpg")
        assert tac["shoppers"][0]["name"] == "Hot Shopper" and tac["shoppers"][0]["clicks"] == 2 and tac["shoppers"][0]["mine"] is True
        assert f150["clicks"] == 1 and f150["asks"] == 3 and f150["score"] == 5 and f150["prev_score"] == 1 and f150["trend"] == "up"
        assert d["total_shoppers"] >= 2

    def test_days_window(self, seed):
        d = requests.get(f"{API}/inventory/{seed['uid']}/hot?days=1", headers={"Authorization": f"Bearer {seed['tok']}"}, timeout=30).json()
        f150 = [v for v in d["vehicles"] if v["inventory_id"] == seed["v2"]]
        assert f150 and f150[0]["clicks"] == 0 and f150[0]["asks"] == 3  # the 1-day-old open falls outside a 24h window
