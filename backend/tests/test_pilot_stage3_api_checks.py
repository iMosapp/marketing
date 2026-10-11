"""Stage 3 F8 live API probes against the preview URL."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")

PILOT_EMAIL = "qa-pilot-owner-ui@invalid.imonsocial.test"
PILOT_PASS = "PilotOwner123!"
PILOT_USER_ID = "6acbcb1fe4b243ca9cc2a230"
PILOT_ORG_ID = "6acbcb1fe4b243ca9cc2a21e"

MGR_EMAIL = "qa-manager@invalid.imonsocial.test"
MGR_PASS = "Manager123!"

FOREST_EMAIL = "forest@imosapp.com"
FOREST_PASS = "Admin123!"


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data, data
    return data


@pytest.fixture(scope="module")
def pilot():
    return _login(PILOT_EMAIL, PILOT_PASS)


@pytest.fixture(scope="module")
def mgr():
    return _login(MGR_EMAIL, MGR_PASS)


@pytest.fixture(scope="module")
def forest():
    return _login(FOREST_EMAIL, FOREST_PASS)


# ---------- F8.1 login pilot flags ----------
def test_pilot_login_has_pilot_flags(pilot):
    u = pilot["user"]
    assert u.get("pilot") is True
    assert u.get("pilot_owner") is True
    assert u.get("pilot_billing_status") == "active"


def test_legacy_login_no_pilot_key(mgr):
    u = mgr["user"]
    assert "pilot" not in u or u.get("pilot") in (False, None)


# ---------- F8.2 /api/pilot/checklist ----------
def test_pilot_checklist_ok(pilot):
    r = requests.get(f"{BASE}/api/pilot/checklist", headers={"Authorization": f"Bearer {pilot['token']}"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 5
    assert len(data["steps"]) == 5
    assert "done" in data and "complete" in data and "business_name" in data


def test_pilot_checklist_mgr_404(mgr):
    r = requests.get(f"{BASE}/api/pilot/checklist", headers={"Authorization": f"Bearer {mgr['token']}"}, timeout=30)
    assert r.status_code == 404
    assert "pilot" in r.text.lower()


def test_pilot_checklist_anonymous_401():
    r = requests.get(f"{BASE}/api/pilot/checklist", timeout=30)
    assert r.status_code in (401, 403)


# ---------- F8.3 bug-reports category normalization ----------
def test_bug_report_nonsense_category_becomes_other(pilot):
    r = requests.post(
        f"{BASE}/api/bug-reports/{PILOT_USER_ID}",
        headers={"Authorization": f"Bearer {pilot['token']}"},
        json={"category": "nonsense", "description": "TEST_nonsense category normalize", "platform": "web", "screen": "test"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    report_id = body.get("report_id") or body.get("id")
    assert report_id, body
    # Verify via Mongo that category stored as 'other'
    from pymongo import MongoClient
    from bson import ObjectId
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    doc = db.bug_reports.find_one({"_id": ObjectId(report_id)}) or db.bug_reports.find_one({"id": report_id})
    assert doc, f"bug_report {report_id} not found"
    assert doc.get("category") == "other", doc.get("category")


def test_bug_report_empty_description_400(pilot):
    r = requests.post(
        f"{BASE}/api/bug-reports/{PILOT_USER_ID}",
        headers={"Authorization": f"Bearer {pilot['token']}"},
        json={"category": "question", "description": "", "platform": "web", "screen": "test"},
        timeout=30,
    )
    assert r.status_code == 400, r.text


# ---------- F8.4 /api/customers (list vs detail) ----------
def test_forest_customer_detail(forest):
    r = requests.get(
        f"{BASE}/api/customers/{PILOT_ORG_ID}",
        headers={"Authorization": f"Bearer {forest['token']}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "progress" in data
    p = data["progress"]
    assert "done" in p and "total" in p and "complete" in p and "steps" in p
    assert "last_activity" in data
    assert "issues_open" in data
    assert "attention" in data
    assert "issues" in data


def test_forest_customer_list_has_summary_no_issues(forest):
    r = requests.get(
        f"{BASE}/api/customers",
        headers={"Authorization": f"Bearer {forest['token']}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    row = next((x for x in rows if x.get("id") == PILOT_ORG_ID or x.get("org_id") == PILOT_ORG_ID), rows[0])
    assert "progress" in row
    assert "last_activity" in row
    assert "issues_open" in row
    assert "attention" in row
    assert "issues" not in row


def test_mgr_customers_list_forbidden(mgr):
    r = requests.get(
        f"{BASE}/api/customers",
        headers={"Authorization": f"Bearer {mgr['token']}"},
        timeout=30,
    )
    assert r.status_code == 403
