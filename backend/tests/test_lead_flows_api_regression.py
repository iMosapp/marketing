"""Lead Flows API regression tests (no ladder/test-lead - covered separately).
Covers list/create/update/duplicate/delete/attach/detach + RBAC + 'flow wins' rule on source workflow save.
Uses TEST_Lead_Source_VA_Picker (never Website source). Cleans up all created flows and detaches at end.
"""
import os
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL"):
                return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_base()
API = f"{BASE_URL}/api"

QA_EMAIL = "qa-manager@invalid.imonsocial.test"
QA_PASS = "Manager123!"
REP_EMAIL = "activation-tester@invalid.imonsocial.test"
REP_PASS = "NewPass123!"

TEST_SOURCE = "6a165970ac830a1c833af189"  # TEST_Lead_Source_VA_Picker (SAFE)
TESTER_ID = "6a978d68b8673c29063aa8b9"    # Activation Tester (Twilio test number)


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def mgr_headers():
    return {"Authorization": f"Bearer {_login(QA_EMAIL, QA_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def rep_headers():
    return {"Authorization": f"Bearer {_login(REP_EMAIL, REP_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_flow_ids():
    ids = []
    yield ids
    # cleanup: detach source, force-delete flows
    h = {"Authorization": f"Bearer {_login(QA_EMAIL, QA_PASS)}", "Content-Type": "application/json"}
    try:
        requests.put(f"{API}/lead-flows/source/{TEST_SOURCE}", json={"flow_id": None}, headers=h, timeout=15)
    except Exception:
        pass
    for fid in ids:
        try:
            requests.delete(f"{API}/lead-flows/{fid}?force=true", headers=h, timeout=15)
        except Exception:
            pass


# --- RBAC ---
def test_rep_gets_403_on_list(rep_headers):
    r = requests.get(f"{API}/lead-flows", headers=rep_headers, timeout=15)
    assert r.status_code == 403


# --- list envelope ---
def test_list_flows_envelope(mgr_headers):
    r = requests.get(f"{API}/lead-flows", headers=mgr_headers, timeout=15)
    assert r.status_code == 200
    j = r.json()
    for k in ("flows", "reps", "store_id", "store_hours", "templates"):
        assert k in j, f"missing {k}"
    keys = {t["key"] for t in j["templates"]}
    assert {"ring_all_then_manager", "text_first_push_only", "after_hours_jessi"} <= keys
    # QA manager itself is in reps (safe reference)
    rep_ids = {r["id"] for r in j["reps"]}
    assert "6a9b2b82cc6e7504dafc33f2" in rep_ids  # QA Manager


# --- validation ---
def test_create_text_and_call_without_reps_returns_400(mgr_headers):
    body = {"name": "TEST_bad_flow", "contact_mode": "text_and_call", "call_attempts": [{"user_ids": [], "delay_seconds": 0, "delivery": "call"}]}
    r = requests.post(f"{API}/lead-flows", json=body, headers=mgr_headers, timeout=15)
    assert r.status_code == 400, r.text


# --- template create ---
def test_create_from_template_prefills_reps(mgr_headers, created_flow_ids):
    r = requests.post(f"{API}/lead-flows", json={"template_key": "ring_all_then_manager", "name": "TEST_Regression_Ring"}, headers=mgr_headers, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["id"]
    created_flow_ids.append(j["id"])
    assert j["contact_mode"] == "text_and_call"
    assert len(j["call_attempts"]) > 0
    # at least one attempt should have a rep pre-filled from store reps
    any_rep = any(a.get("user_ids") for a in j["call_attempts"])
    assert any_rep, "template create should pre-fill reps"


# --- update returns synced_sources ---
def test_update_returns_synced_sources(mgr_headers, created_flow_ids):
    fid = created_flow_ids[0]
    r = requests.put(f"{API}/lead-flows/{fid}", json={"description": "regression edit", "tags_on_claim": ["Working", "VIP"]}, headers=mgr_headers, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "synced_sources" in j
    assert j["tags_on_claim"] == ["Working", "VIP"]


# --- duplicate ---
def test_duplicate(mgr_headers, created_flow_ids):
    fid = created_flow_ids[0]
    r = requests.post(f"{API}/lead-flows/{fid}/duplicate", headers=mgr_headers, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["name"].endswith("(copy)")
    created_flow_ids.append(j["id"])


# --- attach / detach / flow wins ---
def test_attach_mirrors_and_flow_wins(mgr_headers, created_flow_ids):
    fid = created_flow_ids[0]
    # attach
    r = requests.put(f"{API}/lead-flows/source/{TEST_SOURCE}", json={"flow_id": fid}, headers=mgr_headers, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["lead_source"].get("flow_id") == fid
    # workflow endpoint exposes flow
    r2 = requests.get(f"{API}/lead-sources/{TEST_SOURCE}/workflow", headers=mgr_headers, timeout=15)
    assert r2.status_code == 200
    wf = r2.json()
    assert wf.get("flow_id") == fid
    assert wf.get("flow", {}).get("id") == fid
    intake_before = wf.get("intake_text")
    # try to override intake_text via source workflow save - flow should win
    r3 = requests.put(f"{API}/lead-sources/{TEST_SOURCE}/workflow", json={"intake_text": "SHOULD_NOT_STICK", "just_tried_text": "regression just tried"}, headers=mgr_headers, timeout=15)
    assert r3.status_code == 200, r3.text
    r4 = requests.get(f"{API}/lead-sources/{TEST_SOURCE}/workflow", headers=mgr_headers, timeout=15)
    wf2 = r4.json()
    assert wf2.get("intake_text") == intake_before, f"flow_wins violated: {wf2.get('intake_text')}"
    # non-flow field persists
    assert wf2.get("just_tried_text") == "regression just tried"


def test_delete_blocked_while_attached(mgr_headers, created_flow_ids):
    fid = created_flow_ids[0]
    r = requests.delete(f"{API}/lead-flows/{fid}", headers=mgr_headers, timeout=15)
    assert r.status_code == 409, r.text


def test_detach_and_delete(mgr_headers, created_flow_ids):
    fid = created_flow_ids[0]
    r = requests.put(f"{API}/lead-flows/source/{TEST_SOURCE}", json={"flow_id": None}, headers=mgr_headers, timeout=15)
    assert r.status_code == 200
    r2 = requests.get(f"{API}/lead-sources/{TEST_SOURCE}/workflow", headers=mgr_headers, timeout=15)
    assert r2.json().get("flow_id") in (None, "")
    r3 = requests.delete(f"{API}/lead-flows/{fid}", headers=mgr_headers, timeout=15)
    assert r3.status_code == 200
    # remove fid from cleanup list since deleted
    created_flow_ids.remove(fid)


def test_force_delete_while_attached(mgr_headers, created_flow_ids):
    # create a new one, attach, force delete
    r = requests.post(f"{API}/lead-flows", json={"template_key": "text_first_push_only", "name": "TEST_ForceDelete"}, headers=mgr_headers, timeout=15)
    assert r.status_code == 200
    fid = r.json()["id"]
    created_flow_ids.append(fid)
    requests.put(f"{API}/lead-flows/source/{TEST_SOURCE}", json={"flow_id": fid}, headers=mgr_headers, timeout=15)
    r2 = requests.delete(f"{API}/lead-flows/{fid}?force=true", headers=mgr_headers, timeout=15)
    assert r2.status_code == 200
    j = r2.json()
    assert j.get("detached_sources", 0) >= 1
    created_flow_ids.remove(fid)
    # verify source detached
    r3 = requests.get(f"{API}/lead-sources/{TEST_SOURCE}/workflow", headers=mgr_headers, timeout=15)
    assert r3.json().get("flow_id") in (None, "")
