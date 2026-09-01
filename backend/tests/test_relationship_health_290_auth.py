"""
Iteration 290: auth-aware regression + BOLA/security checks for the new
Relationship Intelligence endpoints.
"""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
BASE_URL = base_url.rstrip("/")
USER_ID = "69a0b7095fddcede09591667"


@pytest.fixture(scope="module")
def creds():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("missing test_credentials.md")
    txt = p.read_text()
    admin = re.search(r"Super Admin\s*\n- Email:\s*(\S+)\s*\n- Password:\s*(\S+)", txt)
    user = re.search(r"Test User.*\n- Email:\s*(\S+)\s*\n- Password:\s*(\S+)", txt)
    if not admin:
        pytest.skip("admin creds not parseable")
    return {
        "admin": {"email": admin.group(1), "password": admin.group(2)},
        "user": {"email": user.group(1), "password": user.group(2)} if user else None,
    }


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=45)
    return r


@pytest.fixture(scope="module")
def admin_token(creds):
    r = _login(creds["admin"]["email"], creds["admin"]["password"])
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    assert tok, f"no token in login response keys={list(d)}"
    return tok


# ── Auth playbook checks ─────────────────────────────────────────────────────
class TestAuthPlaybook:
    def test_login_sets_httponly_cookie(self, creds):
        r = _login(creds["admin"]["email"], creds["admin"]["password"])
        assert r.status_code == 200
        raw = r.headers.get("set-cookie", "")
        assert raw, "no Set-Cookie header on login"
        assert "httponly" in raw.lower(), f"no HttpOnly cookie: {raw[:200]}"

    def test_wrong_password_401(self, creds):
        r = _login(creds["admin"]["email"], "definitely-wrong-pass-290")
        assert r.status_code in (401, 403, 429), r.status_code

    def test_bcrypt_hash_format(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        async def go():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            u = await db.users.find_one({"email": "forest@imosapp.com"}, {"password": 1, "password_hash": 1})
            cli.close()
            return u

        env = dotenv_values("/app/backend/.env")
        os.environ.setdefault("MONGO_URL", env.get("MONGO_URL", ""))
        os.environ.setdefault("DB_NAME", env.get("DB_NAME", ""))
        u = asyncio.get_event_loop().run_until_complete(go()) if False else asyncio.run(go())
        assert u, "admin user not found in DB"
        h = u.get("password_hash") or u.get("password") or ""
        assert h.startswith("$2b$"), f"hash prefix not $2b$: {h[:7]}"


# ── Regression: combined home requires auth and returns correct shape ────────
class TestCombinedHomeAuthed:
    def test_combined_home_with_token(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/home/{USER_ID}",
            headers={"Authorization": f"Bearer {admin_token}"}, timeout=60,
        )
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        for k in ("streak", "my_3", "wins_feed"):
            assert k in d, f"missing {k}"
        assert len(d["my_3"]) <= 3

    def test_combined_home_without_token_401(self):
        r = requests.get(f"{BASE_URL}/api/home/{USER_ID}", timeout=60)
        assert r.status_code == 401


# ── SECURITY: new endpoints bypass the BOLA middleware ──────────────────────
class TestNewEndpointAuthorization:
    @pytest.mark.parametrize("path", [
        f"/api/relationship-health/{USER_ID}/summary",
        f"/api/relationship-health/{USER_ID}/contacts?bucket=cooling",
        f"/api/home/people-to-engage/{USER_ID}?limit=5",
        f"/api/home/touch-mix/{USER_ID}?days=7",
    ])
    def test_requires_auth(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=60)
        assert r.status_code in (401, 403), (
            f"UNAUTHENTICATED ACCESS ALLOWED ({r.status_code}) for {path}: {r.text[:200]}"
        )

    def test_other_user_cannot_read_seed_book(self, creds):
        if not creds["user"]:
            pytest.skip("no non-admin creds")
        r = _login(creds["user"]["email"], creds["user"]["password"])
        if r.status_code != 200:
            pytest.skip(f"test user login failed {r.status_code}")
        tok = r.json().get("token") or r.json().get("access_token")
        h = {"Authorization": f"Bearer {tok}"}
        resp = requests.get(
            f"{BASE_URL}/api/relationship-health/{USER_ID}/contacts?bucket=cooling",
            headers=h, timeout=60,
        )
        assert resp.status_code == 403, (
            f"BOLA: regular user read another user's book (status {resp.status_code}, "
            f"items={len(resp.json().get('items', [])) if resp.status_code == 200 else '-'})"
        )
