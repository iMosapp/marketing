"""API tests for Live Shop Calls + Live Voice preview state (iteration 333)."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
CLIENT_ID = "6aa6d7dfb4c41decb2734ec4"  # QA Jeep 979a (English demo)


@pytest.fixture(scope="module")
def forest_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "forest@imosapp.com", "password": "Admin123!"},
                      timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def h(forest_token):
    return {"Authorization": f"Bearer {forest_token}"}


# ---- Lab features
def test_lab_features_contains_live_shop_calls_and_jessi_live_voice(h):
    r = requests.get(f"{BASE}/api/lab/features", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    feats = data if isinstance(data, list) else data.get("features") or data.get("items") or []
    keys = {f.get("key") or f.get("id") or f.get("name") for f in feats}
    assert "live_shop_calls" in keys, f"missing live_shop_calls; got {keys}"
    assert "jessi_live_voice" in keys, f"missing jessi_live_voice; got {keys}"

    def get(k):
        return next(f for f in feats if (f.get("key") or f.get("id") or f.get("name")) == k)

    lsc = get("live_shop_calls")
    jlv = get("jessi_live_voice")
    # status lab
    assert (lsc.get("status") or "").lower() == "lab", lsc
    # needs mentions OPENAI_API_KEY (preview has no key)
    needs_lsc = str(lsc.get("needs") or lsc.get("blocked_reason") or "")
    needs_jlv = str(jlv.get("needs") or jlv.get("blocked_reason") or "")
    assert "OPENAI_API_KEY" in needs_lsc, f"live_shop_calls needs: {needs_lsc!r}"
    assert "OPENAI_API_KEY" in needs_jlv, f"jessi_live_voice needs: {needs_jlv!r}"


# ---- Shop client tri-state live_calls
def test_shop_client_get_exposes_live_calls(h):
    r = requests.get(f"{BASE}/api/shop-clients/{CLIENT_ID}", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    client = body.get("client") or body
    assert "live_calls" in client, f"live_calls missing; keys={list(client.keys())}"


def _lc(h):
    return (requests.get(f"{BASE}/api/shop-clients/{CLIENT_ID}", headers=h, timeout=15)
            .json().get("client", {}).get("live_calls"))


def test_shop_client_toggle_live_calls_true_then_false(h):
    # PUT true
    r = requests.put(f"{BASE}/api/shop-clients/{CLIENT_ID}",
                     headers=h, json={"live_calls": True}, timeout=15)
    assert r.status_code == 200, r.text
    assert _lc(h) is True

    # PUT false
    r = requests.put(f"{BASE}/api/shop-clients/{CLIENT_ID}",
                     headers=h, json={"live_calls": False}, timeout=15)
    assert r.status_code == 200, r.text
    assert _lc(h) is False

    # PUT null is NOT supported (Optional None is skipped) — last value should remain false
    r = requests.put(f"{BASE}/api/shop-clients/{CLIENT_ID}",
                     headers=h, json={"live_calls": None}, timeout=15)
    assert r.status_code in (200, 400, 422), r.text
    assert _lc(h) is False, "expected still False after None PUT"


# ---- Live voice preview state
def test_live_voice_config_forest_available_not_configured(h):
    r = requests.get(f"{BASE}/api/live-voice/config", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg.get("available") is True, cfg
    assert cfg.get("configured") is False, cfg


def test_live_voice_session_503_no_key(h):
    r = requests.post(f"{BASE}/api/live-voice/session",
                      headers=h, json={"sdp": "v=0 fake"}, timeout=15)
    assert r.status_code == 503, r.text
    reason = str(r.json())
    assert "OPENAI_API_KEY" in reason, reason
