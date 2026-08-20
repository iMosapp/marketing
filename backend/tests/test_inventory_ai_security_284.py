"""
Iteration 284 tests:
- Inventory router CRUD + CSV + auth (routers/inventory.py)
- Admin AI & Security settings GET/PUT validation (routers/admin.py)
- Bug report submission still works with push best-effort (routers/bug_reports.py)
"""
import io
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASSWORD = "Admin123!"
STORE_ID = "69a0b7095fddcede09591668"


def H(token, uid=None):
    h = {"Authorization": f"Bearer {token}"}
    if uid:
        h["X-User-ID"] = uid
    return h


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:300]}"
    data = r.json()
    uid = (data.get("user") or {}).get("_id") or (data.get("user") or {}).get("id")
    assert uid
    return uid, data.get("token") or data.get("access_token")


@pytest.fixture(scope="session")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


# ---------------- Inventory ----------------
class TestInventory:
    def test_unauthenticated_list_401(self, admin):
        uid, _ = admin
        r = requests.get(f"{API}/inventory/{uid}", timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_list_seeded_items(self, admin):
        uid, token = admin
        r = requests.get(f"{API}/inventory/{uid}", headers=H(token, uid), timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "items" in body and "counts" in body
        names = " | ".join(i.get("name", "") for i in body["items"])
        assert "Tacoma" in names, f"seeded Tacoma missing: {names[:300]}"
        assert isinstance(body["counts"].get("available"), int)
        for i in body["items"]:
            assert isinstance(i["_id"], str)

    def test_search_filter(self, admin):
        uid, token = admin
        r = requests.get(f"{API}/inventory/{uid}", params={"search": "Tacoma"}, headers=H(token, uid), timeout=30)
        assert r.status_code == 200, r.text[:300]
        items = r.json()["items"]
        assert len(items) >= 1
        assert all("tacoma" in (i.get("name", "") + str(i.get("attributes", {}))).lower() for i in items)

    def test_status_filter_sold_and_all(self, admin):
        uid, token = admin
        r = requests.get(f"{API}/inventory/{uid}", params={"status": "sold"}, headers=H(token, uid), timeout=30)
        assert r.status_code == 200
        assert all(i["status"] == "sold" for i in r.json()["items"])
        r2 = requests.get(f"{API}/inventory/{uid}", params={"status": "all"}, headers=H(token, uid), timeout=30)
        assert r2.status_code == 200

    def test_create_update_delete_flow(self, admin):
        uid, token = admin
        payload = {"year": "2023", "make": "TESTMAKE", "model": "QAModel", "price": "$19,500", "color": "Red"}
        r = requests.post(f"{API}/inventory/{uid}", json=payload, headers=H(token, uid), timeout=30)
        assert r.status_code == 200, r.text[:300]
        item = r.json()["item"]
        iid = item["_id"]
        assert item["name"] == "2023 TESTMAKE QAModel"
        assert item["price"] == 19500.0
        assert item["status"] == "available"
        try:
            # GET verify persistence
            g = requests.get(f"{API}/inventory/{uid}", params={"search": "TESTMAKE"}, headers=H(token, uid), timeout=30)
            assert g.status_code == 200
            assert any(i["_id"] == iid for i in g.json()["items"]), "created item not returned by list"

            # PUT status update
            p = requests.put(f"{API}/inventory/{uid}/{iid}", json={"status": "sold"}, headers=H(token, uid), timeout=30)
            assert p.status_code == 200, p.text[:300]
            g2 = requests.get(f"{API}/inventory/{uid}", params={"search": "TESTMAKE", "status": "sold"}, headers=H(token, uid), timeout=30)
            assert any(i["_id"] == iid and i["status"] == "sold" for i in g2.json()["items"])
        finally:
            d = requests.delete(f"{API}/inventory/{uid}/{iid}", headers=H(token, uid), timeout=30)
            assert d.status_code == 200, d.text[:300]
        g3 = requests.get(f"{API}/inventory/{uid}", params={"search": "TESTMAKE", "status": "all"}, headers=H(token, uid), timeout=30)
        assert not any(i["_id"] == iid for i in g3.json()["items"]), "deleted item still listed"

    def test_create_without_identifiers_400(self, admin):
        uid, token = admin
        r = requests.post(f"{API}/inventory/{uid}", json={"color": "Blue"}, headers=H(token, uid), timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    def test_update_no_valid_fields_400(self, admin):
        uid, token = admin
        r = requests.put(f"{API}/inventory/{uid}/000000000000000000000000", json={"junk": 1}, headers=H(token, uid), timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    def test_update_missing_item_404(self, admin):
        uid, token = admin
        r = requests.put(f"{API}/inventory/{uid}/000000000000000000000000", json={"status": "sold"}, headers=H(token, uid), timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"

    def test_delete_missing_item_404(self, admin):
        uid, token = admin
        r = requests.delete(f"{API}/inventory/{uid}/000000000000000000000000", headers=H(token, uid), timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"

    def test_csv_import_and_cleanup(self, admin):
        uid, token = admin
        csv_text = "Year,Make,Model,Internet Price,Ext Color,Stock #\n2021,QACSVMAKE,Alpha,15000,Blue,QA1\n2020,QACSVMAKE,Beta,$21,000,Black,QA2\n,,,,,\n"
        files = {"file": ("qa_inv.csv", io.BytesIO(csv_text.encode()), "text/csv")}
        r = requests.post(f"{API}/inventory/{uid}/csv", files=files, headers=H(token, uid), timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["imported"] == 2, body
        assert body["skipped"] == 1, body
        g = requests.get(f"{API}/inventory/{uid}", params={"search": "QACSVMAKE", "status": "all"}, headers=H(token, uid), timeout=30)
        created = [i for i in g.json()["items"] if "QACSVMAKE" in i["name"]]
        assert len(created) == 2
        assert any(i["price"] == 15000.0 for i in created)
        for i in created:
            requests.delete(f"{API}/inventory/{uid}/{i['_id']}", headers=H(token, uid), timeout=30)

    def test_csv_bad_headers_400(self, admin):
        uid, token = admin
        files = {"file": ("bad.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")}
        r = requests.post(f"{API}/inventory/{uid}/csv", files=files, headers=H(token, uid), timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"


# ---------------- Admin AI & Security settings ----------------
class TestAiSecuritySettings:
    URL = f"{API}/admin/stores/{STORE_ID}/ai-security-settings"

    @pytest.fixture(scope="class", autouse=True)
    def restore(self, admin):
        uid, token = admin
        r = requests.get(self.URL, headers=H(token, uid), timeout=30)
        original = r.json() if r.status_code == 200 else None
        yield
        if original:
            requests.put(self.URL, json=original, headers=H(token, uid), timeout=30)

    def test_get_settings(self, admin):
        uid, token = admin
        r = requests.get(self.URL, headers=H(token, uid), timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert 1 <= d["intent_hot_threshold"] <= 10
        assert 3 <= d["login_max_fails"] <= 50
        assert 1 <= d["lockout_minutes"] <= 1440

    def test_put_and_persist(self, admin):
        uid, token = admin
        r = requests.put(self.URL, json={"intent_hot_threshold": 5, "login_max_fails": 12, "lockout_minutes": 30},
                         headers=H(token, uid), timeout=30)
        assert r.status_code == 200, r.text[:300]
        g = requests.get(self.URL, headers=H(token, uid), timeout=30).json()
        assert g == {"intent_hot_threshold": 5, "login_max_fails": 12, "lockout_minutes": 30}
        # restore explicitly
        requests.put(self.URL, json={"intent_hot_threshold": 7, "login_max_fails": 8, "lockout_minutes": 15},
                     headers=H(token, uid), timeout=30)
        g2 = requests.get(self.URL, headers=H(token, uid), timeout=30).json()
        assert g2 == {"intent_hot_threshold": 7, "login_max_fails": 8, "lockout_minutes": 15}

    def test_out_of_range_ignored(self, admin):
        uid, token = admin
        before = requests.get(self.URL, headers=H(token, uid), timeout=30).json()
        r = requests.put(self.URL, json={"intent_hot_threshold": 99, "login_max_fails": 12},
                         headers=H(token, uid), timeout=30)
        assert r.status_code == 200, r.text[:300]
        after = requests.get(self.URL, headers=H(token, uid), timeout=30).json()
        assert after["intent_hot_threshold"] == before["intent_hot_threshold"], "out-of-range threshold was applied"
        assert after["login_max_fails"] == 12
        requests.put(self.URL, json=before, headers=H(token, uid), timeout=30)

    def test_all_invalid_400(self, admin):
        uid, token = admin
        r = requests.put(self.URL, json={"intent_hot_threshold": 0, "login_max_fails": 1, "lockout_minutes": 99999},
                         headers=H(token, uid), timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    def test_bad_store_404(self, admin):
        uid, token = admin
        r = requests.get(f"{API}/admin/stores/000000000000000000000000/ai-security-settings", headers=H(token, uid), timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"


# ---------------- Bug report + push ----------------
class TestBugReportPush:
    def test_submit_bug_report(self, admin):
        uid, token = admin
        payload = {"description": "TEST-QA push check — please ignore", "category": "other"}
        r = requests.post(f"{API}/bug-reports/{uid}", json=payload, headers=H(token, uid), timeout=90)
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body.get("success") or body.get("_id") or body.get("id"), body
