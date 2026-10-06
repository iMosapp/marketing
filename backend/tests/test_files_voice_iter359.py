"""Backend regression: live-voice/config + contact-files list for Sarah Tester."""
import os
import re
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

REP_EMAIL = "activation-tester@invalid.imonsocial.test"
REP_PASS = "NewPass123!"
REP_UID = "6a978d68b8673c29063aa8b9"
SARAH_CID = "6aa413008f0d53e3f2261853"

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASS = "Admin123!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in resp: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def rep_token():
    return _login(REP_EMAIL, REP_PASS)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


def test_live_voice_config_admin_unlimited(admin_token):
    r = requests.get(f"{API}/live-voice/config", headers={"Authorization": f"Bearer {admin_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    usage = body.get("usage") or {}
    assert usage.get("unlimited") is True, f"admin should be unlimited: {usage}"
    assert usage.get("cap_s") == 86400, usage
    assert usage.get("left_s") == 86400, usage
    reset_at = usage.get("reset_at")
    assert reset_at and isinstance(reset_at, str) and re.search(r"[+-]\d{2}:?\d{2}$", reset_at), f"reset_at missing/offset: {reset_at}"


def test_live_voice_config_rep_capped(rep_token):
    r = requests.get(f"{API}/live-voice/config", headers={"Authorization": f"Bearer {rep_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    usage = body.get("usage") or {}
    assert usage.get("unlimited") in (False, None), f"rep should not be unlimited: {usage}"
    assert usage.get("cap_s") == 900, usage
    assert usage.get("left_s") is not None and usage["left_s"] <= 900, usage
    assert usage.get("reset_at"), usage
    # available false in preview (lab flag off / no OPENAI_API_KEY)
    assert body.get("available") is False, body


def test_contact_files_list(rep_token):
    url = f"{API}/contact-files/{REP_UID}/contact/{SARAH_CID}"
    r = requests.get(url, headers={"Authorization": f"Bearer {rep_token}"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "files" in body and isinstance(body["files"], list), body
    assert "scan_types" in body, body
    assert "sensitive_types" in body, body
    assert "ttl_days" in body, body
    # at least 3 pre-seeded files
    assert len(body["files"]) >= 3, f"expected >=3 seeded files, got {len(body['files'])}"
