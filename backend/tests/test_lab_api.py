"""Test Lab endpoints + dry-run gating for /api/interview/start."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")

FOREST = {"email": "forest@imosapp.com", "password": "Admin123!"}
TESTER = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}


def _token(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def forest_h():
    return {"Authorization": f"Bearer {_token(FOREST)}"}


@pytest.fixture(scope="module")
def tester_h():
    return {"Authorization": f"Bearer {_token(TESTER)}"}


@pytest.fixture(scope="module", autouse=True)
def restore_lab(forest_h):
    yield
    # ensure feature is back to lab at the end
    requests.put(f"{BASE}/api/lab/features/voice_interview", json={"status": "lab"}, headers=forest_h, timeout=30)


# --- Lab features endpoints ---
def test_lab_features_forbidden_for_non_super(tester_h):
    r = requests.get(f"{BASE}/api/lab/features", headers=tester_h, timeout=30)
    assert r.status_code == 403


def test_lab_features_shape_for_super(forest_h):
    r = requests.get(f"{BASE}/api/lab/features", headers=forest_h, timeout=30)
    assert r.status_code == 200
    feats = r.json()["features"]
    vi = next((f for f in feats if f["key"] == "voice_interview"), None)
    assert vi is not None
    for k in ("name", "icon", "tagline", "description", "how_to_test", "added", "needs", "status"):
        assert k in vi, k
    assert isinstance(vi["how_to_test"], list) and len(vi["how_to_test"]) == 4
    assert vi["status"] in ("lab", "live")


def test_lab_put_bad_status(forest_h):
    r = requests.put(f"{BASE}/api/lab/features/voice_interview", json={"status": "bogus"}, headers=forest_h, timeout=30)
    assert r.status_code == 400


def test_lab_put_unknown_key(forest_h):
    r = requests.put(f"{BASE}/api/lab/features/nope", json={"status": "live"}, headers=forest_h, timeout=30)
    assert r.status_code == 404


def test_lab_put_live_then_lab(forest_h, tester_h):
    # Live
    r = requests.put(f"{BASE}/api/lab/features/voice_interview", json={"status": "live"}, headers=forest_h, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "live"
    st = requests.get(f"{BASE}/api/interview/status", headers=tester_h, timeout=30).json()
    assert st["available"] is True
    # Back to lab
    r = requests.put(f"{BASE}/api/lab/features/voice_interview", json={"status": "lab"}, headers=forest_h, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "lab"
    st = requests.get(f"{BASE}/api/interview/status", headers=tester_h, timeout=30).json()
    assert st["available"] is False


# --- Interview start gating for non-super with feature in lab ---
def test_start_dry_run_forbidden_for_rep(tester_h, forest_h):
    # ensure lab status
    requests.put(f"{BASE}/api/lab/features/voice_interview", json={"status": "lab"}, headers=forest_h, timeout=30)
    r = requests.post(f"{BASE}/api/interview/start", json={"dry_run": True}, headers=tester_h, timeout=30)
    assert r.status_code == 403
    assert "Test Lab" in r.json().get("detail", "")


def test_start_forbidden_when_not_live(tester_h, forest_h):
    requests.put(f"{BASE}/api/lab/features/voice_interview", json={"status": "lab"}, headers=forest_h, timeout=30)
    r = requests.post(f"{BASE}/api/interview/start", json={}, headers=tester_h, timeout=30)
    assert r.status_code == 403
    assert "not open" in r.json().get("detail", "").lower()
