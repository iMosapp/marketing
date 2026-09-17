"""API surface tests for the Jessi Live Voice router (iter 332)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")

FOREST = ("forest@imosapp.com", "Admin123!")
REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
QA = ("qa-manager@invalid.imonsocial.test", "Manager123!")


def login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": creds[0], "password": creds[1]}, timeout=30)
    assert r.status_code == 200, f"login failed for {creds[0]}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.json()}"
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def forest_h():
    return login(FOREST)


@pytest.fixture(scope="module")
def rep_h():
    return login(REP)


@pytest.fixture(scope="module")
def qa_h():
    return login(QA)


# -- /api/live-voice/config --
def test_config_forest(forest_h):
    r = requests.get(f"{BASE_URL}/api/live-voice/config", headers=forest_h, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("available") is True
    assert j.get("is_super_admin") is True
    assert j.get("configured") is False
    reason = j.get("reason", "")
    assert "OPENAI_API_KEY" in reason, f"reason: {reason}"
    assert "voice" in j
    greeting = j.get("greeting", "")
    assert "Forest" in greeting, f"greeting missing name: {greeting}"
    usage = j.get("usage") or {}
    assert "used_s" in usage and usage.get("cap_s") == 900 and "left_s" in usage


def test_config_rep(rep_h):
    r = requests.get(f"{BASE_URL}/api/live-voice/config", headers=rep_h, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("available") is False
    assert j.get("is_super_admin") is False


# -- /api/live-voice/admin/config --
def test_admin_config_forest(forest_h):
    r = requests.get(f"{BASE_URL}/api/live-voice/admin/config", headers=forest_h, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "config" in j
    voices = j.get("voices") or []
    assert len(voices) == 13, f"expected 13 voices, got {len(voices)}"
    assert "labels" in j
    assert j.get("model") == "gpt-live-1"
    assert j.get("price_per_min") == 0.05


def test_admin_config_forbidden_qa(qa_h):
    r = requests.get(f"{BASE_URL}/api/live-voice/admin/config", headers=qa_h, timeout=20)
    assert r.status_code == 403, r.text


def test_admin_config_put_and_validate(forest_h):
    # save willow, energy 2
    r = requests.put(
        f"{BASE_URL}/api/live-voice/admin/config",
        headers=forest_h,
        json={"voice": "willow", "energy": 2},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    cfg = j.get("config") or j
    assert cfg.get("voice") == "willow", cfg
    updated_by = cfg.get("updated_by") or j.get("updated_by")
    assert updated_by and "forest" in updated_by.lower()

    # invalid voice -> 400
    r2 = requests.put(
        f"{BASE_URL}/api/live-voice/admin/config",
        headers=forest_h,
        json={"voice": "nope"},
        timeout=20,
    )
    assert r2.status_code == 400, r2.text


def test_admin_preview(forest_h):
    r = requests.get(
        f"{BASE_URL}/api/live-voice/admin/preview?energy=5&playful=5",
        headers=forest_h,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.text
    assert "high-energy" in body.lower(), body[:400]


def test_restore_defaults(forest_h):
    payload = {
        "voice": "gleam",
        "energy": 4,
        "pacing": 4,
        "playful": 3,
        "brevity": 4,
        "daily_cap_min": 15,
        "idle_close_s": 25,
        "greeting": "Hey {first}, it's Jessi. Who are we talking about today?",
        "notes": "",
    }
    r = requests.put(f"{BASE_URL}/api/live-voice/admin/config", headers=forest_h, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    cfg = (r.json().get("config") or r.json())
    assert cfg.get("voice") == "gleam"
    assert cfg.get("energy") == 4


# -- /api/live-voice/session --
def test_session_forest_503(forest_h):
    r = requests.post(
        f"{BASE_URL}/api/live-voice/session",
        headers=forest_h,
        json={"mode": "lab", "sdp": "v=0"},
        timeout=20,
    )
    assert r.status_code == 503, r.text
    assert "OPENAI_API_KEY" in r.text


def test_session_rep_lab_403(rep_h):
    r = requests.post(
        f"{BASE_URL}/api/live-voice/session",
        headers=rep_h,
        json={"mode": "lab", "sdp": "v=0"},
        timeout=20,
    )
    assert r.status_code == 403, r.text


def test_session_rep_assistant_403(rep_h):
    r = requests.post(
        f"{BASE_URL}/api/live-voice/session",
        headers=rep_h,
        json={"mode": "assistant", "sdp": "v=0"},
        timeout=20,
    )
    assert r.status_code == 403, r.text


def test_session_empty_sdp_400(forest_h):
    r = requests.post(
        f"{BASE_URL}/api/live-voice/session",
        headers=forest_h,
        json={"mode": "lab", "sdp": ""},
        timeout=20,
    )
    assert r.status_code == 400, r.text


# -- /api/lab/features --
def test_lab_features_includes_jessi(forest_h):
    r = requests.get(f"{BASE_URL}/api/lab/features", headers=forest_h, timeout=20)
    assert r.status_code == 200, r.text
    features = r.json()
    if isinstance(features, dict) and "features" in features:
        features = features["features"]
    keys = {f.get("key"): f for f in features} if isinstance(features, list) else {}
    assert "jessi_live_voice" in keys, f"keys={list(keys)[:10]}"
    entry = keys["jessi_live_voice"]
    assert entry.get("status") == "lab"
    needs = entry.get("needs") or ""
    assert "OPENAI_API_KEY" in needs, f"needs: {needs}"
