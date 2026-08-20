"""
Iteration test: Bug Reports router, recent-calls (dialer Recents), date-sold backdating,
and message_in photo hide flow.
"""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASSWORD = "Admin123!"
USER_EMAIL = "mjeast1985@gmail.com"
USER_PASSWORD = "NavyBean1!"


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
    assert uid, f"no user id in login response: {list(data.keys())}"
    return uid, data.get("token") or data.get("access_token")


@pytest.fixture(scope="session")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def regular():
    return _login(USER_EMAIL, USER_PASSWORD)


@pytest.fixture(scope="session")
def admin_contact(admin):
    """Use an existing admin contact; restore its original date_sold + hidden_gallery_urls after."""
    uid, token = admin
    r = requests.get(f"{API}/contacts/{uid}", params={"limit": 5}, headers=H(token, uid), timeout=60)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    contacts = body.get("contacts") if isinstance(body, dict) else body
    assert contacts, "no contacts for admin user"
    cid = contacts[0].get("_id") or contacts[0].get("id")
    original = contacts[0].get("date_sold")
    yield cid
    # Teardown: restore original date_sold if there was one
    if original:
        requests.patch(f"{API}/contacts/{uid}/{cid}/date-sold", json={"date": str(original)}, headers=H(token, uid), timeout=30)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_bug_reports():
    """Remove TEST_QA bug reports + hidden gallery URLs created by this module (no DELETE API exists)."""
    yield
    try:
        from dotenv import dotenv_values as _dv
        from pymongo import MongoClient
        env = _dv("/app/backend/.env")
        db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
        db.bug_reports.delete_many({"description": {"$regex": "TEST[-_]QA"}})
        db.contacts.update_many({"hidden_gallery_urls": {"$regex": "TEST_QA_hidden"}},
                                {"$pull": {"hidden_gallery_urls": {"$regex": "TEST_QA_hidden"}}})
    except Exception as e:
        print(f"cleanup skipped: {e}")


# ---------- Recent calls (dialer Recents tab) ----------
class TestRecentCalls:
    def test_recent_calls_shape(self, admin):
        uid, tok = admin
        r = requests.get(f"{API}/contacts/{uid}/recent-calls", headers=H(tok, uid), timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "calls" in data and isinstance(data["calls"], list)
        for c in data["calls"][:5]:
            assert set(["contact_id", "name", "phone", "direction", "timestamp"]).issubset(c.keys())
            assert c["direction"] in ("outgoing", "incoming")
            assert c["phone"]
        print(f"recent-calls count={len(data['calls'])}")

    def test_recent_calls_limit(self, admin):
        uid, tok = admin
        r = requests.get(f"{API}/contacts/{uid}/recent-calls", params={"limit": 2}, headers=H(tok, uid), timeout=60)
        assert r.status_code == 200
        assert len(r.json()["calls"]) <= 2


# ---------- date-sold backdating ----------
class TestDateSold:
    def test_set_date_sold_persists(self, admin, admin_contact):
        uid, tok = admin
        r = requests.patch(f"{API}/contacts/{uid}/{admin_contact}/date-sold", json={"date": "2026-08-01"}, headers=H(tok, uid), timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("success") is True
        assert data.get("date_sold", "").startswith("2026-08-01")

        g = requests.get(f"{API}/contacts/{uid}/{admin_contact}", headers=H(tok, uid), timeout=60)
        assert g.status_code == 200
        c = g.json()
        c = c.get("contact", c)
        assert str(c.get("date_sold", "")).startswith("2026-08-01"), c.get("date_sold")

    def test_missing_date_400(self, admin, admin_contact):
        uid, tok = admin
        r = requests.patch(f"{API}/contacts/{uid}/{admin_contact}/date-sold", json={}, headers=H(tok, uid), timeout=30)
        assert r.status_code == 400, r.status_code

    def test_invalid_date_400(self, admin, admin_contact):
        uid, tok = admin
        r = requests.patch(f"{API}/contacts/{uid}/{admin_contact}/date-sold", json={"date": "not-a-date"}, headers=H(tok, uid), timeout=30)
        assert r.status_code == 400, r.status_code

    def test_unknown_contact_404(self, admin):
        uid, tok = admin
        r = requests.patch(f"{API}/contacts/{uid}/507f1f77bcf86cd799439011/date-sold",
                           json={"date": "2026-01-01"}, headers=H(tok, uid), timeout=30)
        assert r.status_code == 404, r.status_code


# ---------- Bug reports ----------
class TestBugReports:
    created = []

    def test_submit_requires_description(self, admin):
        uid, tok = admin
        r = requests.post(f"{API}/bug-reports/{uid}", json={"description": "   "}, timeout=30)
        assert r.status_code == 400, r.status_code

    def test_submit_and_list(self, admin):
        uid, tok = admin
        r = requests.post(f"{API}/bug-reports/{uid}", json={
            "category": "suggestion",
            "description": "TEST_QA backend report - please ignore",
            "platform": "pytest",
        }, timeout=60)
        assert r.status_code == 200, r.text[:300]
        rid = r.json().get("report_id")
        assert rid
        TestBugReports.created.append(rid)

        l = requests.get(f"{API}/bug-reports", headers={"X-User-ID": uid}, timeout=60)
        assert l.status_code == 200, l.text[:300]
        body = l.json()
        assert "reports" in body and "counts" in body
        match = [x for x in body["reports"] if x["_id"] == rid]
        assert match, "submitted report not returned by list"
        rep = match[0]
        assert rep["status"] == "open"
        assert rep["category"] == "suggestion"
        assert rep["user_email"] == ADMIN_EMAIL
        assert "_id" in rep and isinstance(rep["_id"], str)

    def test_status_transitions(self, admin):
        uid, tok = admin
        assert TestBugReports.created, "no report created"
        rid = TestBugReports.created[0]
        for st in ("in_progress", "resolved", "open"):
            p = requests.patch(f"{API}/bug-reports/{rid}/status", json={"status": st},
                               headers={"X-User-ID": uid}, timeout=30)
            assert p.status_code == 200, p.text[:300]
            assert p.json()["status"] == st
            l = requests.get(f"{API}/bug-reports", params={"status": st}, headers={"X-User-ID": uid}, timeout=60)
            assert l.status_code == 200
            assert any(x["_id"] == rid for x in l.json()["reports"]), f"filter {st} missing report"

    def test_invalid_status_400(self, admin):
        uid, tok = admin
        rid = TestBugReports.created[0]
        r = requests.patch(f"{API}/bug-reports/{rid}/status", json={"status": "bogus"},
                           headers={"X-User-ID": uid}, timeout=30)
        assert r.status_code == 400

    def test_unknown_report_404(self, admin):
        uid, tok = admin
        r = requests.patch(f"{API}/bug-reports/507f1f77bcf86cd799439011/status", json={"status": "open"},
                           headers={"X-User-ID": uid}, timeout=30)
        assert r.status_code == 404

    def test_list_forbidden_for_regular_user(self, regular):
        uid, tok = regular
        r = requests.get(f"{API}/bug-reports", headers={"X-User-ID": uid}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_patch_forbidden_for_regular_user(self, regular):
        uid, tok = regular
        rid = TestBugReports.created[0]
        r = requests.patch(f"{API}/bug-reports/{rid}/status", json={"status": "resolved"},
                           headers={"X-User-ID": uid}, timeout=30)
        assert r.status_code == 403, r.status_code

    def test_list_missing_header_401(self):
        r = requests.get(f"{API}/bug-reports", timeout=30)
        assert r.status_code in (401, 403), r.status_code


# ---------- message_in photo hide flow ----------
class TestPhotoHide:
    def test_invalid_photo_type(self, admin, admin_contact):
        uid, tok = admin
        r = requests.delete(f"{API}/contacts/{uid}/{admin_contact}/photos",
                            json={"photo_url": "https://x.test/u/a.jpg", "photo_type": "nonsense"}, headers=H(tok, uid), timeout=30)
        assert r.status_code == 400, r.status_code

    def test_missing_photo_url(self, admin, admin_contact):
        uid, tok = admin
        r = requests.delete(f"{API}/contacts/{uid}/{admin_contact}/photos",
                            json={"photo_type": "message_in"}, headers=H(tok, uid), timeout=30)
        assert r.status_code == 400, r.status_code

    def test_message_in_hidden_and_filtered(self, admin, admin_contact):
        uid, tok = admin
        url = "https://media.test.local/qa/TEST_QA_hidden.jpg"
        d = requests.delete(f"{API}/contacts/{uid}/{admin_contact}/photos",
                            json={"photo_url": url, "photo_type": "message_in"}, headers=H(tok, uid), timeout=60)
        assert d.status_code == 200, d.text[:300]

        g = requests.get(f"{API}/contacts/{uid}/{admin_contact}/photos/all", headers=H(tok, uid), timeout=60)
        assert g.status_code == 200, g.text[:300]
        body = g.json()
        photos = body.get("photos", body if isinstance(body, list) else [])
        assert all("TEST_QA_hidden.jpg" not in str(p) for p in photos)
