"""Share-the-app links: tracked redirect, QR, first-open attribution, claim, owner stats + alerts."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
API = "http://127.0.0.1:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], str(d["user"]["_id"] if "_id" in d["user"] else d["user"]["id"])


@pytest.fixture(scope="module")
def owner():
    token, uid = login("forest@imosapp.com", "Admin123!")
    yield {"token": token, "uid": uid, "h": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="module")
def joiner():
    token, uid = login("qa-manager@invalid.imonsocial.test", "Manager123!")
    return {"token": token, "uid": uid, "h": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="module")
def install_id():
    iid = f"ios-test-{uuid.uuid4().hex[:10]}"
    yield iid
    DB.app_installs.delete_many({"install_id": iid})
    DB.app_link_taps.delete_many({"ua": {"$regex": "PYTEST-TAP"}})
    DB.notifications.delete_many({"type": {"$in": ["app_install", "app_signup"]}, "message": {"$regex": "QA Manager|iPhone"}})


class TestAppLinks:
    def test_owner_gets_personal_link_and_site_code(self, owner):
        r = requests.get(f"{API}/app-links/{owner['uid']}", headers=owner["h"], timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["code"] == "forest" and d["link"] == "https://imonsocial.com/get/forest"
        assert d["qr_path"] == "/app-links/qr/forest.png" and "site" in d["codes"]
        assert set(d["stats"]) == {"taps", "taps_week", "installs", "signups"}

    def test_other_user_cannot_read_my_link(self, owner, joiner):
        r = requests.get(f"{API}/app-links/{owner['uid']}", timeout=30)
        assert r.status_code == 401

    def test_iphone_tap_redirects_to_app_store(self):
        r = requests.get(f"{API}/get/forest", headers={"User-Agent": IPHONE_UA + " PYTEST-TAP"}, allow_redirects=False, timeout=30)
        assert r.status_code == 302 and r.headers["location"].startswith("https://apps.apple.com/us/app/im-on-social/id6774618559")
        tap = DB.app_link_taps.find_one({"ua": {"$regex": "PYTEST-TAP"}}, sort=[("created_at", -1)])
        assert tap and tap["platform"] == "ios" and tap["code"] == "forest"

    def test_android_tap_goes_to_site_section(self):
        r = requests.get(f"{API}/get/site", headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) PYTEST-TAP"}, allow_redirects=False, timeout=30)
        assert r.status_code == 302 and r.headers["location"] == "https://imonsocial.com/#get-the-app"

    def test_qr_png(self):
        r = requests.get(f"{API}/app-links/qr/forest.png", timeout=30)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"

    def test_first_open_attributes_to_recent_iphone_tap(self, owner, install_id):
        before = DB.notifications.count_documents({"user_id": owner["uid"], "type": "app_install"})
        r = requests.post(f"{API}/app-installs/first-open", json={"install_id": install_id, "platform": "ios", "os_version": "17.5", "app_version": "1.4.0", "timezone": "America/Denver"}, timeout=30)
        assert r.status_code == 200 and r.json() == {"ok": True, "attributed": True}
        inst = DB.app_installs.find_one({"install_id": install_id})
        assert inst["attributed_code"] == "forest" and inst["attributed_user_id"] == owner["uid"]
        assert DB.notifications.count_documents({"user_id": owner["uid"], "type": "app_install"}) == before + 1
        # idempotent
        r = requests.post(f"{API}/app-installs/first-open", json={"install_id": install_id, "platform": "ios"}, timeout=30)
        assert r.json().get("duplicate") is True

    def test_claim_names_the_signup_and_alerts_owner(self, owner, joiner, install_id):
        r = requests.post(f"{API}/app-installs/claim", json={"install_id": install_id}, timeout=30)
        assert r.status_code == 401
        r = requests.post(f"{API}/app-installs/claim", headers=joiner["h"], json={"install_id": install_id}, timeout=30)
        assert r.status_code == 200 and r.json()["claimed"] is True
        inst = DB.app_installs.find_one({"install_id": install_id})
        assert inst["claimed_user_id"] == joiner["uid"] and inst["claimed_name"] == "QA Manager"
        n = DB.notifications.find_one({"user_id": owner["uid"], "type": "app_signup"}, sort=[("created_at", -1)])
        assert n and n["title"] == "QA Manager joined from your link" and n["link"] == "/share-app"

    def test_stats_and_alert_center_rows(self, owner, install_id):
        d = requests.get(f"{API}/app-links/{owner['uid']}", headers=owner["h"], timeout=30).json()
        assert d["stats"]["installs"] >= 1 and d["stats"]["signups"] >= 1 and d["stats"]["taps"] >= 2
        kinds = {r["kind"] for r in d["recent"]}
        assert {"tap", "signup"} <= kinds
        assert any(r.get("name") == "QA Manager" for r in d["recent"] if r["kind"] == "signup")
        feed = requests.get(f"{API}/notification-center/{owner['uid']}?feed=for_you", headers=owner["h"], timeout=30).json()["notifications"]
        rows = {n["type"]: n for n in feed if n["type"] in ("app_install", "app_signup")}
        assert rows["app_signup"]["action"]["link"] == "/share-app" and rows["app_signup"]["title"] == "QA Manager joined from your link"
        assert rows["app_install"]["title"] == "New app install"
