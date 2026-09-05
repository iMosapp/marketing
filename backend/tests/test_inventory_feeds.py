"""Inventory feeds (URL + SFTP transports): parsing, upsert, sold detection, change detection, auth, alerts.
Run: cd /app/backend && python -m pytest tests/test_inventory_feeds.py -q -p no:randomly
Serves a CSV from a local http.server so the URL transport is exercised end to end.
"""
import os
import socket
import threading
import http.server
import functools
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
API = "http://127.0.0.1:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

CSV_V1 = """Type,Stock #,VIN,Year,Make,Model,Trim,Body,Ext Color,Mileage,Internet Price,MSRP,ImageList
Used,PT-T1,3TMCZ5AN0PMPT0001,2024,Toyota,Tacoma,TRD Off-Road,Pickup Truck,Red,"12,500",42995,45000,https://img.example.com/a1.jpg|https://img.example.com/a2.jpg
New,PT-C2,2HGFE2F55RHPT0002,2024,Honda,Civic,Sport,Sedan,White,8,"28,995",29500,https://img.example.com/c1.jpg
Used,PT-R3,1C6SRFFT0NNPT0003,2022,Ram,1500,Big Horn 4x4,Pickup Truck,Gray,"31,000",39900,
"""
CSV_V2 = """Type,Stock #,VIN,Year,Make,Model,Trim,Body,Ext Color,Mileage,Internet Price,ImageList
Used,PT-T1,3TMCZ5AN0PMPT0001,2024,Toyota,Tacoma,TRD Off-Road,Pickup Truck,Red,"12,500",41500,https://img.example.com/a1.jpg
New,PT-C2,2HGFE2F55RHPT0002,2024,Honda,Civic,Sport,Sedan,White,8,"28,995",https://img.example.com/c1.jpg
"""
XML_FB = """<?xml version="1.0"?><listings><title>Dealer</title>
<listing><vehicle_id>PT-X9</vehicle_id><vin>5YJ3E1EA0PFPT0009</vin><title>2023 Tesla Model 3</title><make>Tesla</make><model>Model 3</model><year>2023</year>
<mileage><value>9000</value><unit>MI</unit></mileage><price>31000 USD</price><body_style>SEDAN</body_style><state_of_vehicle>USED</state_of_vehicle>
<image><url>https://img.example.com/t1.jpg</url></image><url>https://dealer.example.com/vdp/9</url></listing>
</listings>"""

STATE = {"csv": CSV_V1}


def run_sync(feed_id, force=False):
    """sync_feed with a fresh Motor client (each asyncio.run needs its own loop-bound client)."""
    import asyncio, sys
    sys.path.insert(0, "/app/backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.inventory_feed import sync_feed

    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        feed = await db.inventory_feeds.find_one({"_id": ObjectId(feed_id)})
        return await sync_feed(db, feed, force=force, triggered_by="test")
    return asyncio.run(go())


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (XML_FB if self.path.endswith(".xml") else STATE["csv"]).encode()
        self.send_response(404 if self.path.endswith("missing.csv") else 200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def manager():
    r = requests.post(f"{API}/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json(); u = d["user"]
    return str(u.get("_id") or u.get("id")), d["token"]


@pytest.fixture(scope="module")
def rep():
    r = requests.post(f"{API}/auth/login", json={"email": "mjeast1985@gmail.com", "password": "NavyBean1!"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json(); u = d["user"]
    return str(u.get("_id") or u.get("id")), d["token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def cleanup():
    yield
    DB.inventory.delete_many({"attributes.stock_number": {"$regex": "^PT-"}})
    for f in DB.inventory_feeds.find({"label": {"$regex": "^PT "}}):
        DB.inventory_feed_runs.delete_many({"feed_id": str(f["_id"])})
    DB.inventory_feeds.delete_many({"label": {"$regex": "^PT "}})
    DB.notifications.delete_many({"type": "inventory_feed_issue", "title": {"$regex": "PT|Other CSV"}})


class TestAuth:
    def test_unauthenticated(self, manager):
        uid, _ = manager
        assert requests.get(f"{API}/inventory-feeds/{uid}", timeout=30).status_code == 401

    def test_rep_cannot_manage(self, rep):
        uid, tok = rep
        r = requests.get(f"{API}/inventory-feeds/{uid}", headers=H(tok), timeout=30)
        assert r.status_code == 403


class TestUrlFeed:
    def test_dry_run_preview(self, server, manager, cleanup):
        uid, tok = manager
        r = requests.post(f"{API}/inventory-feeds/{uid}/test", json={"transport": "url", "provider": "homenet", "feed_url": f"{server}/inv.csv"}, headers=H(tok), timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] and d["vehicles"] == 3
        assert {"vin", "stock_number", "price", "images", "body_type", "condition"} <= set(d["fields"])
        assert d["sample"][0]["name"] == "2024 Toyota Tacoma TRD Off-Road" and d["sample"][0]["price"] == 42995.0 and d["sample"][0]["photos"] == 2
        assert DB.inventory.count_documents({"attributes.stock_number": "PT-T1"}) == 0  # dry run writes nothing

    def test_bad_url_is_friendly(self, server, manager):
        uid, tok = manager
        d = requests.post(f"{API}/inventory-feeds/{uid}/test", json={"transport": "url", "feed_url": f"{server}/missing.csv"}, headers=H(tok), timeout=60).json()
        assert d["ok"] is False and "404" in d["error"]

    def test_create_imports_and_maps(self, server, manager, cleanup):
        uid, tok = manager
        r = requests.post(f"{API}/inventory-feeds/{uid}", json={"transport": "url", "provider": "homenet", "feed_url": f"{server}/inv.csv", "label": "PT HomeNet"}, headers=H(tok), timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["run"]["status"] == "ok" and d["run"]["units_seen"] == 3 and d["run"]["added"] == 3
        assert d["feed"]["last_status"] == "ok" and d["feed"]["has_password"] is False
        pytest.feed_id = d["feed"]["id"]
        tac = DB.inventory.find_one({"attributes.stock_number": "PT-T1"})
        assert tac["price"] == 42995.0 and tac["status"] == "available"
        assert tac["attributes"]["condition"] == "used" and tac["attributes"]["body_type"] == "Pickup Truck" and tac["attributes"]["mileage"] == "12500"
        assert tac["images"] == ["https://img.example.com/a1.jpg", "https://img.example.com/a2.jpg"] and tac["primary_image"].endswith("a1.jpg")
        assert tac["feed_id"] == pytest.feed_id and tac["source_system"] == f"feed:{pytest.feed_id}"
        civic = DB.inventory.find_one({"attributes.stock_number": "PT-C2"})
        assert civic["attributes"]["condition"] == "new"

    def test_unchanged_file_is_skipped_by_scheduler_path(self, manager):
        run = run_sync(pytest.feed_id)
        assert run["status"] == "no_change"

    def test_changed_file_updates_price_and_marks_sold(self, manager):
        STATE["csv"] = CSV_V2
        run = run_sync(pytest.feed_id)
        assert run["status"] == "ok" and run["units_seen"] == 2 and run["updated"] == 2 and run["added"] == 0 and run["marked_sold"] == 1
        assert DB.inventory.find_one({"attributes.stock_number": "PT-T1"})["price"] == 41500.0
        ram = DB.inventory.find_one({"attributes.stock_number": "PT-R3"})
        assert ram["status"] == "sold" and ram["sold_reason"] == "dropped_off_feed"
        # sold unit is gone from Jessi's live count
        uid, tok = manager
        lst = requests.get(f"{API}/inventory-feeds/{uid}", headers=H(tok), timeout=30).json()
        mine = [f for f in lst["feeds"] if f["id"] == pytest.feed_id][0]
        assert mine["live_units"] == 2 and mine["runs"][0]["status"] == "ok" and mine["last_counts"]["marked_sold"] == 1

    def test_manual_pull_forces_reimport(self, manager):
        uid, tok = manager
        r = requests.post(f"{API}/inventory-feeds/{uid}/{pytest.feed_id}/run", headers=H(tok), timeout=90)
        assert r.status_code == 200 and r.json()["run"]["status"] == "ok" and r.json()["run"]["updated"] == 2

    def test_pause_and_edit_keep_settings(self, manager):
        uid, tok = manager
        r = requests.put(f"{API}/inventory-feeds/{uid}/{pytest.feed_id}", json={"enabled": False}, headers=H(tok), timeout=30)
        assert r.status_code == 200 and r.json()["feed"]["enabled"] is False and r.json()["feed"]["feed_url"].endswith("/inv.csv")
        requests.put(f"{API}/inventory-feeds/{uid}/{pytest.feed_id}", json={"enabled": True}, headers=H(tok), timeout=30)

    def test_xml_catalog_feed(self, server, manager):
        uid, tok = manager
        d = requests.post(f"{API}/inventory-feeds/{uid}/test", json={"transport": "url", "provider": "dealer_com", "feed_url": f"{server}/catalog.xml"}, headers=H(tok), timeout=60).json()
        assert d["ok"] and d["vehicles"] == 1
        assert d["sample"][0]["name"] == "2023 Tesla Model 3" and d["sample"][0]["price"] == 31000.0 and d["sample"][0]["photos"] == 1
        assert "listing_url" in d["fields"] and "body_type" in d["fields"]

    def test_google_sheet_link_normalized(self, manager):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.inventory_feed import normalize_feed_url
        assert normalize_feed_url("https://docs.google.com/spreadsheets/d/1AbC_dEf-123/edit#gid=5") == "https://docs.google.com/spreadsheets/d/1AbC_dEf-123/export?format=csv&gid=5"

    def test_delete_keeps_vehicles(self, manager, cleanup):
        uid, tok = manager
        r = requests.delete(f"{API}/inventory-feeds/{uid}/{pytest.feed_id}", headers=H(tok), timeout=30)
        assert r.status_code == 200
        assert DB.inventory.count_documents({"attributes.stock_number": "PT-T1"}) == 1
        assert DB.inventory_feeds.count_documents({"_id": ObjectId(pytest.feed_id)}) == 0


class TestSftp:
    def test_sftp_bad_host_is_friendly(self, manager):
        uid, tok = manager
        d = requests.post(f"{API}/inventory-feeds/{uid}/test", json={"transport": "sftp", "sftp_host": "sftp.invalid.example", "sftp_username": "x", "sftp_password": "y"}, headers=H(tok), timeout=90).json()
        assert d["ok"] is False and "Host not found" in d["error"]

    def test_sftp_requires_password_on_create(self, manager):
        uid, tok = manager
        r = requests.post(f"{API}/inventory-feeds/{uid}", json={"transport": "sftp", "sftp_host": "h", "sftp_username": "u", "label": "PT sftp"}, headers=H(tok), timeout=30)
        assert r.status_code == 400 and "password" in r.json()["detail"].lower()

    def test_repeated_failures_raise_alert(self, manager, cleanup):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.inventory_feed import encrypt_secret
        uid, tok = manager
        user = DB.users.find_one({"_id": ObjectId(uid)})
        fid = DB.inventory_feeds.insert_one({"transport": "sftp", "provider": "other", "label": "PT broken sftp", "sftp_host": "sftp.invalid.example", "sftp_port": 22,
                                             "sftp_username": "x", "sftp_password_enc": encrypt_secret("y"), "remote_path": "/", "file_pattern": "*.csv",
                                             "store_id": str(user["store_id"]), "created_by": uid, "enabled": True, "mark_missing_sold": True, "consecutive_failures": 0}).inserted_id
        for _ in range(2):
            run = run_sync(fid)
            assert run["status"] == "error"
        feed = DB.inventory_feeds.find_one({"_id": fid})
        assert feed["consecutive_failures"] == 2
        n = DB.notifications.find_one({"type": "inventory_feed_issue", "feed_id": str(fid), "user_id": uid})
        assert n and n["link"] == "/admin/inventory-feed" and "Host not found" in n["message"]
        # surfaces as an action in Alerts
        requests.post(f"{API}/notification-center/{uid}/read", json={"ids": []}, headers=H(tok), timeout=30)
        feed_items = requests.get(f"{API}/notification-center/{uid}?limit=200", headers=H(tok), timeout=30).json()["notifications"]
        mine = [x for x in feed_items if x["type"] == "inventory_feed_issue" and x.get("id") == str(n["_id"])]
        assert mine and mine[0]["action"]["label"] == "Fix" and mine[0]["action"]["link"] == "/admin/inventory-feed" and mine[0]["bucket"] == "today"
        DB.notifications.delete_many({"feed_id": str(fid)})
        DB.inventory_feed_runs.delete_many({"feed_id": str(fid)})
        DB.inventory_feeds.delete_one({"_id": fid})
