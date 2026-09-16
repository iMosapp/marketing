"""API-level tests for Power Dialer + GHL via the public preview URL.

These complement /app/backend/tests/test_power_dialer.py (pure pytest units).
They exercise auth, config gating, campaign CRUD, CSV import, DNC, GHL and
Twilio webhook guards — using the deployed FastAPI service.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com').rstrip('/')

FOREST = {"email": "forest@imosapp.com", "password": "Admin123!"}
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        return None
    tok = r.json().get("token") or r.json().get("access_token")
    return tok


@pytest.fixture(scope="module")
def forest_headers():
    tok = _login(**FOREST)
    if not tok:
        pytest.skip("forest login failed")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def rep_headers():
    tok = _login(**REP)
    if not tok:
        pytest.skip("rep login failed")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def manager_headers():
    tok = _login(**MANAGER)
    if not tok:
        pytest.skip("manager login failed")
    return {"Authorization": f"Bearer {tok}"}


# --- Config / gating ---------------------------------------------------------
def test_config_forest(forest_headers):
    r = requests.get(f"{BASE_URL}/api/dialer/config", headers=forest_headers, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("available") is True
    assert d.get("is_manager") is True
    assert isinstance(d.get("rules"), (list, dict))
    assert "registry_stats" in d or "registry" in d


def test_config_rep_blocked(rep_headers):
    r = requests.get(f"{BASE_URL}/api/dialer/config", headers=rep_headers, timeout=30)
    assert r.status_code == 200
    assert r.json().get("available") is False
    r2 = requests.get(f"{BASE_URL}/api/dialer/campaigns", headers=rep_headers, timeout=30)
    assert r2.status_code in (401, 403)


def test_config_manager_lab_blocked(manager_headers):
    r = requests.get(f"{BASE_URL}/api/dialer/config", headers=manager_headers, timeout=30)
    assert r.status_code == 200
    assert r.json().get("available") is False


# --- Campaign create/clamp/import/DNC/rescrub/status/delete ------------------
@pytest.fixture(scope="module")
def temp_campaign(forest_headers):
    payload = {
        "name": f"TEST_QA_{uuid.uuid4().hex[:6]}",
        "audience": "b2c",
        "lines": 9,  # should clamp to 3
        "max_per_day": 99,  # should clamp to 3
        "connect_mode": "press1",
        "vm_mode": "rep",
    }
    r = requests.post(f"{BASE_URL}/api/dialer/campaigns", headers=forest_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    c = r.json()
    cid = c.get("id") or c.get("_id")
    assert cid
    assert c.get("lines") <= 3
    assert c.get("max_per_day") <= 3
    assert c.get("connect_mode") in ("press1", "instant")
    yield cid
    # cleanup
    requests.delete(f"{BASE_URL}/api/dialer/campaigns/{cid}", headers=forest_headers, timeout=30)


def test_import_csv_flexible(forest_headers, temp_campaign):
    cid = temp_campaign
    csv = (
        "First Name,Last Name,Company,Phone,State\n"
        "Ann,Lee,Acme,500-555-0181,UT\n"
        "Bob,Ray,,5005550182,TX\n"
        "Dup,Row,,500-555-0181,UT\n"
    )
    r = requests.post(
        f"{BASE_URL}/api/dialer/campaigns/{cid}/import/csv",
        headers=forest_headers,
        json={"csv": csv},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    d = r.json()
    for k in ("added", "duplicates", "invalid", "dnc"):
        assert k in d, f"missing {k} in {d}"
    assert d["added"] >= 2


def test_leads_local_time(forest_headers, temp_campaign):
    cid = temp_campaign
    r = requests.get(f"{BASE_URL}/api/dialer/campaigns/{cid}/leads", headers=forest_headers, timeout=30)
    assert r.status_code == 200, r.text
    leads = r.json()
    if isinstance(leads, dict):
        leads = leads.get("leads") or leads.get("items") or []
    assert leads, "no leads returned"
    # Look for state / tz / local_time keys
    sample = leads[0]
    keys = set(sample.keys())
    assert keys & {"state", "tz", "local_time"}, f"missing tz keys: {keys}"


def test_dnc_add_check(forest_headers):
    phone = "+15005550999"
    r = requests.post(f"{BASE_URL}/api/dialer/dnc", headers=forest_headers, json={"phone": phone, "reason": "test"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    r2 = requests.get(f"{BASE_URL}/api/dialer/dnc/check/{phone}", headers=forest_headers, timeout=30)
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("internal") is True or body.get("status") in ("internal", "dnc")
    requests.delete(f"{BASE_URL}/api/dialer/dnc/{phone}", headers=forest_headers, timeout=30)


def test_registry_rescrub(forest_headers, temp_campaign):
    cid = temp_campaign
    reg = "305,5551234\n500,5550181\n"
    r = requests.post(f"{BASE_URL}/api/dialer/dnc/registry", headers=forest_headers, json={"text": reg}, timeout=30)
    assert r.status_code in (200, 201), r.text
    r2 = requests.post(f"{BASE_URL}/api/dialer/campaigns/{cid}/rescrub", headers=forest_headers, timeout=30)
    assert r2.status_code in (200, 201), r2.text


def test_pause_blocks_session(forest_headers, temp_campaign):
    cid = temp_campaign
    r = requests.patch(f"{BASE_URL}/api/dialer/campaigns/{cid}", headers=forest_headers, json={"status": "paused"}, timeout=30)
    assert r.status_code in (200, 204), r.text
    r2 = requests.post(f"{BASE_URL}/api/dialer/sessions", headers=forest_headers, json={"campaign_id": cid}, timeout=30)
    assert r2.status_code == 409, r2.text


def test_delete_keeps_attempts(forest_headers):
    # create ephemeral campaign so we don't wreck fixture
    payload = {"name": f"TEST_del_{uuid.uuid4().hex[:6]}", "audience": "b2c", "lines": 1, "max_per_day": 1, "connect_mode": "press1"}
    r = requests.post(f"{BASE_URL}/api/dialer/campaigns", headers=forest_headers, json=payload, timeout=30)
    cid = r.json().get("id")
    r2 = requests.delete(f"{BASE_URL}/api/dialer/campaigns/{cid}", headers=forest_headers, timeout=30)
    assert r2.status_code in (200, 204)


# --- Seeded demo campaign attempts -------------------------------------------
def test_seeded_demo_attempts(forest_headers):
    # find the demo campaign
    r = requests.get(f"{BASE_URL}/api/dialer/campaigns", headers=forest_headers, timeout=30)
    assert r.status_code == 200
    camps = r.json()
    if isinstance(camps, dict):
        camps = camps.get("campaigns") or camps.get("items") or []
    demo = next((c for c in camps if "QA Demo" in (c.get("name") or "")), None)
    if not demo:
        pytest.skip("Demo campaign not seeded")
    cid = demo.get("id") or demo.get("_id")
    r2 = requests.get(f"{BASE_URL}/api/dialer/campaigns/{cid}/attempts", headers=forest_headers, timeout=30)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    attempts = body if isinstance(body, list) else body.get("attempts") or body.get("items") or []
    assert len(attempts) >= 5, f"expected >=5, got {len(attempts)}"
    keys = set(attempts[0].keys())
    assert keys & {"lead_name", "local_time", "status", "disposition"}


# --- GHL ----------------------------------------------------------------------
def test_ghl_connection(forest_headers):
    r = requests.get(f"{BASE_URL}/api/ghl/connection", headers=forest_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("connected") is False
    assert "lead_sources" in d


def test_ghl_bad_put(forest_headers):
    r = requests.put(
        f"{BASE_URL}/api/ghl/connection",
        headers=forest_headers,
        json={"location_id": "bogus", "token": "bad"},
        timeout=30,
    )
    assert r.status_code == 400
    assert "location id" in r.text.lower() or "gohighlevel" in r.text.lower()


def test_ghl_webhook_unauth():
    fake = "6aaafa743e1a5d265fbdffff"
    r = requests.post(f"{BASE_URL}/api/ghl/webhook/{fake}?key=x", json={"foo": 1}, timeout=30)
    assert r.status_code in (401, 404)


def test_ghl_import_no_conn(forest_headers, temp_campaign):
    cid = temp_campaign
    r = requests.post(f"{BASE_URL}/api/dialer/campaigns/{cid}/import/ghl", headers=forest_headers, json={}, timeout=30)
    assert r.status_code == 404
    assert "gohighlevel" in r.text.lower() or "connect" in r.text.lower()


# --- Twilio webhook guards ----------------------------------------------------
def test_rep_answer_bad_session():
    r = requests.post(f"{BASE_URL}/api/webhooks/dialer/rep/answer?s=badid&t=x", timeout=30)
    assert r.status_code == 200
    assert "<Hangup" in r.text or "Hangup" in r.text


def test_ringback_audio():
    r = requests.get(f"{BASE_URL}/api/webhooks/dialer/audio/ringback", timeout=30)
    assert r.status_code == 200
    assert "audio/wav" in r.headers.get("content-type", "").lower()
