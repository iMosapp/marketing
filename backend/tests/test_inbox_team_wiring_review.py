"""
Backend regression tests for the shared-inbox team-wiring feature.
Covers:
- GET /api/inboxes/members/options?inbox_id=... (grouping, on_team ordering)
- GET /api/inboxes/{id}/leads (sources/other_sources/team/checklist)
- POST /api/inboxes/{id}/sources  (point a source)
- DELETE /api/inboxes/{id}/sources/{sid} (remove pointed source)
- POST .../sources with bogus id -> 400
- GET /api/lead-flows: reps include Forest (inbox-only) with via containing "inbox"
- GET /api/lead-sources/{sid}/reps returns reps + store_name + inbox null
- Activation-tester (rep) forbidden from GET inbox leads
"""
import os
import pytest
import requests

def _read_env(path, key):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _read_env("/app/frontend/.env", "REACT_APP_BACKEND_URL")
            or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

INBOX_ID = "6aa3673e65d794ba9962f1bc"        # Sales
SOURCE_ID = "6a165970ac830a1c833af189"       # TEST_Lead_Source_VA_Picker
WEBSITE_SOURCE = "69a787ca70ae63ea0ac69251"  # DO NOT point
FOREST_ID = "69a0b7095fddcede09591667"

QA = ("qa-manager@invalid.imonsocial.test", "Manager123!")
FOREST = ("forest@imosapp.com", "Admin123!")
REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token: {r.text}"
    return tok


@pytest.fixture(scope="module")
def qa_token():
    return _login(*QA)


@pytest.fixture(scope="module")
def forest_token():
    return _login(*FOREST)


@pytest.fixture(scope="module")
def rep_token():
    return _login(*REP)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# --- member options ---------------------------------------------------------

def test_member_options_qa_manager(qa_token):
    r = requests.get(f"{BASE_URL}/api/inboxes/members/options",
                     params={"inbox_id": INBOX_ID}, headers=_h(qa_token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("store_name", "").lower() == "i'm on social", data.get("store_name")
    users = data.get("users") or data.get("members") or []
    assert len(users) == 9, f"expected 9 users, got {len(users)}: {[u.get('name') for u in users]}"
    for u in users:
        assert u.get("on_team") is True, f"qa-manager should only see on_team users: {u}"
        assert isinstance(u.get("via"), list) and len(u["via"]) > 0, f"via missing: {u}"


def test_member_options_forest_orders_on_team_first(forest_token):
    r = requests.get(f"{BASE_URL}/api/inboxes/members/options",
                     params={"inbox_id": INBOX_ID}, headers=_h(forest_token), timeout=30)
    assert r.status_code == 200, r.text
    users = r.json().get("users") or r.json().get("members") or []
    assert len(users) >= 9
    flags = [bool(u.get("on_team")) for u in users]
    # All True must appear before any False
    if False in flags:
        first_false = flags.index(False)
        assert all(flags[:first_false]), "on_team=True users must come first"
        assert not any(flags[first_false:]), "on_team ordering violated"


# --- inbox leads overview ---------------------------------------------------

def test_inbox_leads_overview_shape(qa_token):
    r = requests.get(f"{BASE_URL}/api/inboxes/{INBOX_ID}/leads",
                     headers=_h(qa_token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("sources", "other_sources", "team", "checklist"):
        assert k in data, f"missing key {k}: {list(data.keys())}"
    assert isinstance(data["sources"], list)
    assert isinstance(data["other_sources"], list)


def test_rep_forbidden_inbox_leads(rep_token):
    r = requests.get(f"{BASE_URL}/api/inboxes/{INBOX_ID}/leads",
                     headers=_h(rep_token), timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# --- point/unpoint source ---------------------------------------------------

def test_point_then_unpoint_source(qa_token):
    # Ensure clean start: try delete (idempotent)
    requests.delete(f"{BASE_URL}/api/inboxes/{INBOX_ID}/sources/{SOURCE_ID}",
                    headers=_h(qa_token), timeout=30)

    # POST point
    r = requests.post(f"{BASE_URL}/api/inboxes/{INBOX_ID}/sources",
                      json={"source_id": SOURCE_ID}, headers=_h(qa_token), timeout=30)
    assert r.status_code in (200, 201), r.text

    # Verify the source now appears
    r2 = requests.get(f"{BASE_URL}/api/inboxes/{INBOX_ID}/leads",
                      headers=_h(qa_token), timeout=30)
    assert r2.status_code == 200
    ids = [s.get("id") or s.get("_id") or s.get("source_id") for s in r2.json().get("sources", [])]
    assert SOURCE_ID in ids, f"source not present after POST: {ids}"

    # DELETE unpoint
    r3 = requests.delete(f"{BASE_URL}/api/inboxes/{INBOX_ID}/sources/{SOURCE_ID}",
                         headers=_h(qa_token), timeout=30)
    assert r3.status_code in (200, 204), r3.text

    # Verify removed
    r4 = requests.get(f"{BASE_URL}/api/inboxes/{INBOX_ID}/leads",
                      headers=_h(qa_token), timeout=30)
    ids2 = [s.get("id") or s.get("_id") or s.get("source_id") for s in r4.json().get("sources", [])]
    assert SOURCE_ID not in ids2, f"source still present after DELETE: {ids2}"


def test_point_bogus_source_400(qa_token):
    r = requests.post(f"{BASE_URL}/api/inboxes/{INBOX_ID}/sources",
                      json={"source_id": "not-a-real-id-xxxxxxxxxxxxxxxx"},
                      headers=_h(qa_token), timeout=30)
    assert r.status_code == 400, f"expected 400 for bogus id, got {r.status_code}: {r.text}"


# --- lead flows include Forest via inbox -----------------------------------

def test_lead_flows_reps_include_forest_via_inbox(qa_token):
    r = requests.get(f"{BASE_URL}/api/lead-flows", headers=_h(qa_token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    reps = data.get("reps") if isinstance(data, dict) else []
    assert reps, "no reps in /api/lead-flows response"
    forest = next((rp for rp in reps if (rp.get("id") or rp.get("_id")) == FOREST_ID), None)
    assert forest is not None, f"Forest id {FOREST_ID} not in reps: {[r.get('id') for r in reps]}"
    via = forest.get("via") or []
    assert any("inbox" in str(v).lower() for v in via), f"Forest via missing 'inbox': {via}"


# --- lead source reps -------------------------------------------------------

def test_lead_source_reps_shape(qa_token):
    r = requests.get(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/reps",
                     headers=_h(qa_token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "reps" in data, data
    assert "store_name" in data, data
    assert "inbox" in data, data
    assert data["inbox"] in (None, {}, ""), f"expected inbox null-ish, got {data['inbox']}"
