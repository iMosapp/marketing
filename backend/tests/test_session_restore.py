"""GET /api/auth/me session restore: the httponly cookie must carry a valid signed JWT; a bare user id (the pre-hotfix cookie
value, also visible as X-User-ID in every request) must never mint a session. Live preview API (REACT_APP_BACKEND_URL + JWT_SECRET)."""
import os
import time

import jwt as pyjwt
import pytest
import requests

from tests import qa_creds

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL = "forest@imosapp.com"


@pytest.fixture(scope="module")
def session():
    r = requests.post(f"{BASE}/api/auth/login", json=qa_creds.account(EMAIL), timeout=30)
    assert r.status_code == 200, r.text
    return {"token": r.json()["token"], "uid": r.json()["user"]["_id"], "cookies": r.cookies}


def _me(cookies=None, headers=None):
    return requests.get(f"{BASE}/api/auth/me", cookies=cookies, headers=headers, timeout=30)


def test_login_cookie_is_a_jwt_not_a_user_id(session):
    c = session["cookies"]
    assert c.get("imonsocial_session"), "session cookie missing"
    assert c["imonsocial_session"] != session["uid"]
    assert c["imonsocial_session"].count(".") == 2
    assert pyjwt.decode(c["imonsocial_session"], options={"verify_signature": False})["sub"] == session["uid"]


def test_bare_user_id_cookie_is_refused(session):
    r = _me(cookies={"imonsocial_session": session["uid"]})
    assert r.status_code == 401, r.text
    assert "token" not in r.text


def test_forged_and_expired_cookies_are_refused(session):
    forged = pyjwt.encode({"sub": session["uid"], "role": "super_admin", "iat": int(time.time()), "exp": time.time() + 600}, "not-the-secret", algorithm="HS256")
    assert _me(cookies={"imonsocial_session": forged}).status_code == 401
    expired = pyjwt.encode({"sub": session["uid"], "role": "super_admin", "iat": int(time.time()) - 7200, "exp": time.time() - 3600}, os.environ["JWT_SECRET"], algorithm="HS256")
    assert _me(cookies={"imonsocial_session": expired}).status_code == 401
    assert _me(cookies={"imonsocial_session": "mock_token_" + session["uid"]}).status_code == 401
    assert _me().status_code == 401


def test_valid_cookie_restores_and_refreshes(session):
    r = _me(cookies={"imonsocial_session": session["token"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["_id"] == session["uid"] and body["token"].count(".") == 2
    assert "password" not in body["user"]
    assert r.cookies["imonsocial_session"].count(".") == 2  # re-set with the fresh JWT


def test_bearer_header_restores_too(session):
    r = _me(headers={"Authorization": f"Bearer {session['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["_id"] == session["uid"]


def test_refresh_refuses_bare_id_and_forged(session):
    forged = pyjwt.encode({"sub": session["uid"], "role": "super_admin", "iat": int(time.time()), "exp": time.time() + 600}, "not-the-secret", algorithm="HS256")
    for tok in (session["uid"], forged, "token_" + session["uid"]):
        r = requests.post(f"{BASE}/api/auth/refresh", headers={"Authorization": f"Bearer {tok}"}, json={}, timeout=30)
        assert r.status_code == 401, (tok[:12], r.text)
