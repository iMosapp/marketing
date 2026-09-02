"""
Iteration 291 regression tests:
  - Admin impersonation session (field names, TTL, auth guards)
  - New-user activation via SMS code (/api/auth/activate/*)
  - Forgot-password regression on shared code helpers
SMS SAFETY: only 500-555-XXXX (Twilio test range) numbers are used.
"""
import os
import re
import time
import uuid
from datetime import datetime, timedelta

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = backend_env.get("MONGO_URL")
DB_NAME = backend_env.get("DB_NAME")

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASSWORD = "Admin123!"
TARGET_USER_ID = "69c75782e051d06491e6fa9f"  # Matthew Easton
TARGET_EMAIL = "mjeast1985@gmail.com"


@pytest.fixture(scope="session")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="session")
def admin():
    """Login as super admin -> (token, user_id)"""
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:300]}")
    d = r.json()
    token = d.get("token") or d.get("access_token")
    uid = str((d.get("user") or {}).get("_id"))
    assert token, f"no token in login response: {list(d.keys())}"
    return {"token": token, "user_id": uid}


def admin_headers(admin):
    return {"Authorization": f"Bearer {admin['token']}", "X-User-ID": admin["user_id"]}


@pytest.fixture(scope="session")
def created_user_ids():
    return []


@pytest.fixture(scope="session", autouse=True)
def cleanup(admin, created_user_ids, db):
    yield
    for uid in created_user_ids:
        try:
            requests.delete(f"{BASE_URL}/api/admin/users/{uid}/hard",
                            headers=admin_headers(admin), timeout=60)
        except Exception:
            pass
    try:
        db.contacts.delete_many({"tags": "new-user", "email": {"$regex": "invalid.imonsocial.test$"}})
    except Exception:
        pass


# ─────────────────────────────── Impersonation ───────────────────────────────
class TestImpersonation:
    imp_token = None

    def test_impersonate_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/users/{TARGET_USER_ID}/impersonate", timeout=60)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}: {r.text[:200]}"

    def test_impersonate_returns_target_user(self, admin, db):
        r = requests.post(f"{BASE_URL}/api/admin/users/{TARGET_USER_ID}/impersonate",
                          headers=admin_headers(admin), timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        d = r.json()
        token = d.get("token") or d.get("impersonation_token")
        assert token and token.startswith("impersonate_"), f"bad token: {token}"
        user = d.get("user") or {}
        assert str(user.get("_id")) == TARGET_USER_ID, f"returned wrong user: {user.get('_id')}"
        assert user.get("email") == TARGET_EMAIL
        assert str(user.get("_id")) != admin["user_id"]
        TestImpersonation.imp_token = token

        # mongo session doc
        doc = db.impersonation_sessions.find_one({"token": token})
        assert doc, "no impersonation_sessions doc"
        assert doc.get("impersonated_user_id") == TARGET_USER_ID
        assert doc.get("admin_user_id") == admin["user_id"]
        delta = doc["expires_at"] - doc["created_at"]
        assert timedelta(hours=7, minutes=50) < delta < timedelta(hours=8, minutes=10), delta

    def test_impersonate_token_works_on_protected_routes(self):
        assert TestImpersonation.imp_token, "no impersonation token"
        h = {"Authorization": f"Bearer {TestImpersonation.imp_token}", "X-User-ID": TARGET_USER_ID}
        for path in [f"/api/home/weekly-wins/{TARGET_USER_ID}",
                     f"/api/relationship-health/{TARGET_USER_ID}/summary"]:
            r = requests.get(f"{BASE_URL}{path}", headers=h, timeout=90)
            assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"

    def test_protected_route_without_auth_401(self):
        r = requests.get(f"{BASE_URL}/api/home/weekly-wins/{TARGET_USER_ID}", timeout=60)
        assert r.status_code == 401, f"expected 401 got {r.status_code}"

    def test_bogus_impersonate_token_401(self):
        h = {"Authorization": "Bearer impersonate_deadbeefdeadbeef", "X-User-ID": TARGET_USER_ID}
        r = requests.get(f"{BASE_URL}/api/home/weekly-wins/{TARGET_USER_ID}", headers=h, timeout=60)
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text[:200]}"

    def test_impersonate_with_impersonate_token_403(self, admin):
        h = {"Authorization": f"Bearer {TestImpersonation.imp_token}", "X-User-ID": TARGET_USER_ID}
        r = requests.post(f"{BASE_URL}/api/admin/users/{admin['user_id']}/impersonate",
                          headers=h, timeout=60)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"


# ─────────────────────────────── Activation flow ─────────────────────────────
def latest_code(db, user_id, purpose):
    doc = db.password_reset_tokens.find_one(
        {"user_id": str(user_id), "purpose": purpose}, sort=[("created_at", -1)])
    assert doc, f"no {purpose} code doc for {user_id}"
    return doc["code"]


@pytest.fixture(scope="class")
def pending_user(admin, created_user_ids, db):
    email = f"TEST-activate-{uuid.uuid4().hex[:8]}@invalid.imonsocial.test"
    r = requests.post(f"{BASE_URL}/api/admin/users/create", headers=admin_headers(admin), json={
        "first_name": "TEST", "last_name": "Activate", "email": email,
        "phone": "(500) 555-0123", "role": "user",
        "send_invite": False, "send_sms": True,
    }, timeout=90)
    assert r.status_code == 200, f"create user failed {r.status_code}: {r.text[:400]}"
    d = r.json()
    uid = str(d.get("user_id") or (d.get("user") or {}).get("_id"))
    assert uid and uid != "None", f"no user_id in create response: {d}"
    created_user_ids.append(uid)
    return {"email": email, "id": uid, "resp": d}


class TestActivation:
    def test_create_user_response_and_db(self, pending_user, db):
        d = pending_user["resp"]
        assert d.get("success") is True, d
        assert d.get("activation_flow") is True, "activation_flow missing"
        assert d.get("activate_url"), "activate_url missing"
        assert d.get("temp_password"), "temp_password (backup) missing"
        from bson import ObjectId
        u = db.users.find_one({"_id": ObjectId(pending_user["id"])})
        assert u["phone"] == "+15005550123", f"phone not E.164: {u['phone']}"
        assert u.get("activation_pending") is True
        assert u.get("phone_verified") is False
        assert u.get("needs_password_change") is True

    def test_activate_request(self, pending_user):
        r = requests.post(f"{BASE_URL}/api/auth/activate/request",
                          json={"phone": "500-555-0123"}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        d = r.json()
        assert "message" in d and "channel" in d, d

    def test_wrong_code_message(self, pending_user):
        r = requests.post(f"{BASE_URL}/api/auth/activate/verify",
                          json={"phone": "500-555-0123", "code": "000000"}, timeout=60)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:200]}"
        assert "4 attempts remaining" in r.text, r.text[:200]

    def test_cross_purpose_code_rejected(self, pending_user, db):
        code = latest_code(db, pending_user["id"], "activate")
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password/verify",
                          json={"phone": "500-555-0123", "code": code}, timeout=60)
        assert r.status_code == 400, f"activation code accepted by reset verify! {r.status_code}"

    def test_verify_then_complete_and_login(self, pending_user, db):
        code = latest_code(db, pending_user["id"], "activate")
        r = requests.post(f"{BASE_URL}/api/auth/activate/verify",
                          json={"phone": "500-555-0123", "code": code}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        d = r.json()
        assert d.get("verified") is True
        assert d.get("email") == pending_user["email"].lower()

        # too-short password
        r = requests.post(f"{BASE_URL}/api/auth/activate/complete",
                          json={"phone": "500-555-0123", "code": code, "new_password": "abcde"}, timeout=60)
        assert r.status_code == 400, f"short password accepted: {r.status_code}"

        r = requests.post(f"{BASE_URL}/api/auth/activate/complete",
                          json={"phone": "500-555-0123", "code": code, "new_password": "NewPass123!"}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.json().get("message") == "Account activated"
        assert r.json().get("email") == pending_user["email"].lower()

        # reuse rejected
        r = requests.post(f"{BASE_URL}/api/auth/activate/complete",
                          json={"phone": "500-555-0123", "code": code, "new_password": "NewPass123!"}, timeout=60)
        assert r.status_code == 400, f"code reuse allowed: {r.status_code}"

        # login with new password
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": pending_user["email"], "password": "NewPass123!"}, timeout=60)
        assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:300]}"
        u = r.json()["user"]
        assert u.get("needs_password_change") in (False, None), u.get("needs_password_change")
        assert u.get("phone_verified") is True
        assert u.get("activation_pending") is False
        assert u.get("tos_accepted") is True

    def test_unknown_phone_no_enumeration(self):
        r = requests.post(f"{BASE_URL}/api/auth/activate/request",
                          json={"phone": "500-555-0199"}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        d = r.json()
        assert set(d.keys()) == {"message", "channel"}, d
        assert d["channel"] == "sms", d

    def test_rate_limit_after_3_requests(self, pending_user):
        codes = []
        for _ in range(4):
            r = requests.post(f"{BASE_URL}/api/auth/activate/request",
                              json={"phone": "500-555-0123"}, timeout=60)
            codes.append(r.status_code)
            time.sleep(0.3)
        assert 429 in codes, f"no 429 rate limit hit: {codes}"


# ─────────────────────────── Forgot-password regression ──────────────────────
class TestForgotPassword:
    EMAIL = "activation-tester@invalid.imonsocial.test"

    @pytest.fixture(scope="class")
    def tester_id(self, db):
        u = db.users.find_one({"email": self.EMAIL})
        if not u:
            pytest.skip("activation-tester user missing")
        return str(u["_id"])

    def test_request_by_email_and_reset(self, db, tester_id):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password/request",
                          json={"email": self.EMAIL}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert set(r.json().keys()) == {"message", "channel"}, r.json()

        code = latest_code(db, tester_id, "reset")
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password/verify",
                          json={"email": self.EMAIL, "code": code}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.json().get("verified") is True

        r = requests.post(f"{BASE_URL}/api/auth/forgot-password/reset",
                          json={"email": self.EMAIL, "code": code, "new_password": "NewPass123!"}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"

        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": self.EMAIL, "password": "NewPass123!"}, timeout=60)
        assert r.status_code == 200, f"login after reset failed {r.status_code}: {r.text[:300]}"

    def test_request_by_digits_only_phone_finds_same_user(self, db, tester_id):
        before = db.password_reset_tokens.count_documents({"user_id": tester_id, "purpose": "reset"})
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password/request",
                          json={"phone": "5005550006"}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        after = db.password_reset_tokens.count_documents({"user_id": tester_id, "purpose": "reset"})
        assert after == before + 1, f"phone lookup did not resolve user (before={before} after={after})"


# ─────────────────────────── Normal auth regression ──────────────────────────
class TestAuthRegression:
    def test_login_sets_session_cookie_and_me_restores(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert "imonsocial_session" in s.cookies, f"session cookie not set: {s.cookies.keys()}"
        assert "httponly" in r.headers.get("set-cookie", "").lower(), r.headers.get("set-cookie")
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=60)
        assert r.status_code == 200, f"/auth/me {r.status_code}: {r.text[:300]}"
        u = r.json().get("user") or r.json()
        assert u.get("email") == ADMIN_EMAIL, u.get("email")

    def test_me_without_cookie_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=60)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:200]}"

    def test_bcrypt_hash_format(self, db):
        u = db.users.find_one({"email": ADMIN_EMAIL})
        assert u["password"].startswith("$2b$"), u["password"][:10]

    def test_bad_password_rejected(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "definitely-wrong-xyz"}, timeout=60)
        assert r.status_code in (401, 403, 429), f"{r.status_code}: {r.text[:200]}"


# ─────────────────────────── Marketing static page ───────────────────────────
class TestMarketingPage:
    PATH = "/app/marketing/build/relationship-os/index.html"

    def test_own_section_content(self):
        html = open(self.PATH, encoding="utf-8").read()
        assert "Salespeople leave." in html
        assert "leave with them" in html
        assert "(435) 220-3414" in html
        assert "Tyler J." in html and "Bridger W." in html
        assert 'class="own"' in html or "own" in html

    def test_no_em_dashes(self):
        html = open(self.PATH, encoding="utf-8").read()
        bad = [m.start() for m in re.finditer(r"—|&mdash;", html)]
        assert not bad, f"{len(bad)} em dashes found at offsets {bad[:5]}"
