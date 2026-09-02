"""
Iteration 291 backend regression:
  1. Admin impersonation (session field alignment, 8h expiry, super_admin only)
  2. New-user activation via SMS code (/api/auth/activate/{request,verify,complete})
  3. Forgot-password refactor regression (phone in any format, non-enumerating shape)
  4. Admin create-user E.164 normalization + activation_flow response

SMS SAFETY: only 500-555-XXXX (Twilio magic test range) numbers are used.
"""
import os
import time
import uuid

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

fe = dotenv_values("/app/frontend/.env")
be = dotenv_values("/app/backend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_ID = "69a0b7095fddcede09591667"
TARGET_ID = "69c75782e051d06491e6fa9f"  # Matthew Easton
ACTIVATION_TESTER_EMAIL = "activation-tester@invalid.imonsocial.test"

db = MongoClient(be["MONGO_URL"])[be["DB_NAME"]]

STATE = {}


def _ip_headers(tag):
    """Unique X-Forwarded-For per logical test group so the per-IP code throttle (6/10min) doesn't collide."""
    return {"X-Forwarded-For": f"10.{abs(hash(tag)) % 250}.{abs(hash(tag)) % 200}.{abs(hash(tag)) % 240}"}


def _latest_code(user_id, purpose):
    doc = db.password_reset_tokens.find_one(
        {"user_id": str(user_id), "purpose": purpose}, sort=[("created_at", -1)]
    )
    return doc


@pytest.fixture(scope="session")
def admin_jwt():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=60)
    assert r.status_code == 200, f"admin login failed {r.status_code} {r.text[:300]}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in login response keys={list(data)}"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_jwt):
    return {"Authorization": f"Bearer {admin_jwt}", "X-User-ID": ADMIN_ID}


# ─────────────────────────── 1. Impersonation ───────────────────────────
class TestImpersonation:
    def test_impersonate_requires_auth(self):
        r = requests.post(f"{API}/admin/users/{TARGET_ID}/impersonate", timeout=60)
        assert r.status_code == 401, f"expected 401, got {r.status_code} {r.text[:200]}"

    def test_impersonate_success(self, admin_headers):
        r = requests.post(f"{API}/admin/users/{TARGET_ID}/impersonate", headers=admin_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        d = r.json()
        assert d.get("success") is True, d
        token = d.get("token")
        assert token and token.startswith("impersonate_"), d
        user = d.get("user") or {}
        assert str(user.get("_id")) == TARGET_ID, f"impersonated wrong user: {user.get('_id')} / {user.get('email')}"
        assert str(user.get("_id")) != ADMIN_ID
        STATE["imp_token"] = token

    def test_impersonated_reads_work(self):
        token = STATE.get("imp_token")
        assert token, "no impersonation token from previous test"
        h = {"Authorization": f"Bearer {token}", "X-User-ID": TARGET_ID}
        for path in (
            f"/home/weekly-wins/{TARGET_ID}",
            f"/relationship-health/{TARGET_ID}/summary",
        ):
            r = requests.get(f"{API}{path}", headers=h, timeout=90)
            assert r.status_code == 200, f"GET {path} -> {r.status_code} {r.text[:300]}"
            assert isinstance(r.json(), (dict, list))

    def test_impersonate_token_cannot_impersonate(self):
        token = STATE.get("imp_token")
        h = {"Authorization": f"Bearer {token}", "X-User-ID": TARGET_ID}
        r = requests.post(f"{API}/admin/users/{ADMIN_ID}/impersonate", headers=h, timeout=60)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_impersonate_self_is_400(self, admin_headers):
        r = requests.post(f"{API}/admin/users/{ADMIN_ID}/impersonate", headers=admin_headers, timeout=60)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"

    def test_bogus_impersonate_token_rejected(self):
        h = {"Authorization": "Bearer impersonate_deadbeef", "X-User-ID": TARGET_ID}
        r = requests.get(f"{API}/home/weekly-wins/{TARGET_ID}", headers=h, timeout=60)
        assert r.status_code == 401, f"expected 401, got {r.status_code} {r.text[:200]}"

    def test_session_doc_fields_and_expiry(self):
        doc = db.impersonation_sessions.find_one({"token": STATE.get("imp_token")})
        assert doc, "impersonation session not persisted"
        assert doc.get("impersonated_user_id") == TARGET_ID
        assert doc.get("admin_user_id") == ADMIN_ID
        delta = (doc["expires_at"] - doc["created_at"]).total_seconds()
        assert 7.9 * 3600 < delta < 8.1 * 3600, f"expiry delta {delta}s not ~8h"

    def test_admin_session_restore_still_admin(self, admin_jwt):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=60)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=60)
        assert me.status_code == 200, f"{me.status_code} {me.text[:200]}"
        body = me.json()
        u = body.get("user", body)
        assert (u.get("email") or "").lower() == ADMIN_EMAIL, u
        assert u.get("role") == "super_admin", u


# ───────────────── 2. Admin create user + activation flow ─────────────────
class TestActivationFlow:
    NEW_PHONE_IN = "(500) 555-0177"
    NEW_PHONE_E164 = "+15005550177"

    def test_create_user_normalizes_and_returns_activation(self, admin_headers):
        email = f"act-{uuid.uuid4().hex[:8]}@invalid.imonsocial.test"
        payload = {
            "first_name": "TEST",
            "last_name": "Activation",
            "email": email,
            "phone": self.NEW_PHONE_IN,
            "role": "user",
            "send_invite": False,
            "send_sms": True,
        }
        r = requests.post(f"{API}/admin/users/create", json=payload, headers=admin_headers, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        d = r.json()
        assert d.get("success") is True, d
        assert d.get("activation_flow") is True, d
        assert (d.get("activate_url") or "").endswith("/auth/activate"), d.get("activate_url")
        assert d.get("temp_password"), "temp_password missing (backup path)"
        STATE["new_user_id"] = d["user_id"]
        STATE["new_email"] = email

        u = db.users.find_one({"_id": ObjectId(d["user_id"])})
        assert u["phone"] == self.NEW_PHONE_E164, u.get("phone")
        assert u.get("activation_pending") is True
        assert u.get("phone_verified") is False
        assert u.get("needs_password_change") is True

    def test_activate_request_returns_safe_shape(self):
        r = requests.post(
            f"{API}/auth/activate/request", json={"phone": "500-555-0177"},
            headers=_ip_headers("activate"), timeout=90,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert set(d.keys()) == {"message", "channel"}, d
        doc = _latest_code(STATE["new_user_id"], "activate")
        assert doc, "no activation token stored"
        STATE["act_code"] = doc["code"]

    def test_activate_verify_wrong_code(self):
        r = requests.post(
            f"{API}/auth/activate/verify",
            json={"phone": "5005550177", "code": "000000"}, timeout=60,
        )
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"
        assert r.json().get("detail") == "Incorrect code. 4 attempts remaining.", r.json()

    def test_purposes_are_isolated(self):
        r = requests.post(
            f"{API}/auth/forgot-password/verify",
            json={"phone": "5005550177", "code": STATE["act_code"]}, timeout=60,
        )
        assert r.status_code == 400, f"activation code accepted by reset verify! {r.status_code} {r.text[:200]}"

    def test_activate_verify_correct(self):
        r = requests.post(
            f"{API}/auth/activate/verify",
            json={"phone": self.NEW_PHONE_E164, "code": STATE["act_code"]}, timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d.get("verified") is True, d
        assert (d.get("email") or "").lower() == STATE["new_email"].lower(), d

    def test_activate_complete_rejects_weak_password(self):
        r = requests.post(
            f"{API}/auth/activate/complete",
            json={"phone": self.NEW_PHONE_E164, "code": STATE["act_code"], "new_password": "abc"}, timeout=60,
        )
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"

    def test_activate_complete_success(self):
        r = requests.post(
            f"{API}/auth/activate/complete",
            json={"phone": self.NEW_PHONE_E164, "code": STATE["act_code"], "new_password": "NewPass123!"},
            timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d.get("message") == "Account activated", d
        assert (d.get("email") or "").lower() == STATE["new_email"].lower(), d

    def test_code_cannot_be_reused(self):
        r = requests.post(
            f"{API}/auth/activate/complete",
            json={"phone": self.NEW_PHONE_E164, "code": STATE["act_code"], "new_password": "NewPass123!"},
            timeout=60,
        )
        assert r.status_code == 400, f"consumed code reused! {r.status_code} {r.text[:200]}"

    def test_login_after_activation(self):
        r = requests.post(
            f"{API}/auth/login", json={"email": STATE["new_email"], "password": "NewPass123!"}, timeout=60
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        u = r.json().get("user") or {}
        assert u.get("needs_password_change") in (False, None), u.get("needs_password_change")
        assert u.get("phone_verified") is True, u.get("phone_verified")
        assert u.get("activation_pending") in (False, None), u.get("activation_pending")
        assert u.get("tos_accepted") is True, u.get("tos_accepted")

    def test_unknown_phone_non_enumerating(self):
        r = requests.post(
            f"{API}/auth/activate/request", json={"phone": "5005559999"},
            headers=_ip_headers("unknown-phone"), timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        d = r.json()
        assert set(d.keys()) == {"message", "channel"}, d
        assert d["channel"] == "sms", d

    def test_per_user_rate_limit(self):
        """3 codes / 10 min per user; the 4th must be 429. (Codes 1-3 land on the fresh test user.)"""
        h = _ip_headers("ratelimit")
        codes = []
        for i in range(4):
            r = requests.post(
                f"{API}/auth/activate/request", json={"phone": self.NEW_PHONE_E164}, headers=h, timeout=90
            )
            codes.append(r.status_code)
            time.sleep(0.5)
        assert codes[-1] == 429, f"expected final 429, got {codes}"


# ───────────────── 3. Forgot-password regression ─────────────────
class TestForgotPassword:
    TESTER_PHONE_DIGITS = "5005550006"

    @pytest.fixture(scope="class", autouse=True)
    def tester_user(self):
        u = db.users.find_one({"email": ACTIVATION_TESTER_EMAIL})
        if not u:
            pytest.fail(f"seed user {ACTIVATION_TESTER_EMAIL} missing from DB")
        # Clear codes left over from earlier test runs so the 3-per-10-min per-user
        # throttle doesn't block this class (test hygiene, not product behaviour).
        db.password_reset_tokens.delete_many({"user_id": str(u["_id"])})
        return u

    def _clear_codes(self):
        u = db.users.find_one({"email": ACTIVATION_TESTER_EMAIL})
        db.password_reset_tokens.delete_many({"user_id": str(u["_id"])})

    def _reset_password_to(self, new_password, tag):
        r = requests.post(
            f"{API}/auth/forgot-password/request", json={"email": ACTIVATION_TESTER_EMAIL},
            headers=_ip_headers(tag), timeout=90,
        )
        assert r.status_code == 200, f"request -> {r.status_code} {r.text[:250]}"
        assert set(r.json().keys()) == {"message", "channel"}, r.json()
        uid = db.users.find_one({"email": ACTIVATION_TESTER_EMAIL})["_id"]
        doc = _latest_code(uid, "reset")
        assert doc, "no reset token stored"
        code = doc["code"]

        v = requests.post(
            f"{API}/auth/forgot-password/verify",
            json={"email": ACTIVATION_TESTER_EMAIL, "code": code}, timeout=60,
        )
        assert v.status_code == 200, f"verify -> {v.status_code} {v.text[:250]}"
        assert v.json().get("verified") is True, v.json()

        rs = requests.post(
            f"{API}/auth/forgot-password/reset",
            json={"email": ACTIVATION_TESTER_EMAIL, "code": code, "new_password": new_password}, timeout=60,
        )
        assert rs.status_code == 200, f"reset -> {rs.status_code} {rs.text[:250]}"

        lg = requests.post(
            f"{API}/auth/login", json={"email": ACTIVATION_TESTER_EMAIL, "password": new_password}, timeout=60
        )
        assert lg.status_code == 200, f"login with new password -> {lg.status_code} {lg.text[:250]}"

    def test_reset_roundtrip(self):
        self._reset_password_to("Reset456!", "fp1")
        # restore documented credential
        self._clear_codes()
        self._reset_password_to("NewPass123!", "fp2")

    def test_phone_lookup_digits_only(self, tester_user):
        self._clear_codes()
        before = db.password_reset_tokens.count_documents(
            {"user_id": str(tester_user["_id"]), "purpose": "reset"}
        )
        r = requests.post(
            f"{API}/auth/forgot-password/request", json={"phone": self.TESTER_PHONE_DIGITS},
            headers=_ip_headers("fp-phone"), timeout=90,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:250]}"
        after = db.password_reset_tokens.count_documents(
            {"user_id": str(tester_user["_id"]), "purpose": "reset"}
        )
        assert after == before + 1, "digits-only phone did not resolve to the +1E164 user"


# ───────────────── 4. AI phone guard (pure python) ─────────────────
class TestAIPhoneGuard:
    def test_enforce_business_number_formats(self):
        from utils.text_sanitize import enforce_business_number as e
        out = e("reach me at 8016349122 or (801) 634-9122", "8016349122", "+14352203414")
        assert out.count("(435) 220-3414") == 2, out
        assert "8016349122" not in out and "801) 634-9122" not in out, out

    def test_no_business_phone_is_noop(self):
        from utils.text_sanitize import enforce_business_number as e
        text = "reach me at 8016349122"
        assert e(text, "8016349122", None) == text

    def test_clean_ai_text_and_clone_prompt(self):
        """Both DB-backed checks share one event loop (motor clients are loop-bound)."""
        import asyncio
        os.environ.setdefault("MONGO_URL", be["MONGO_URL"])
        os.environ.setdefault("DB_NAME", be["DB_NAME"])
        from utils.text_sanitize import clean_ai_text
        from routers.ai_campaigns import build_clone_system_prompt

        async def _run():
            out = await clean_ai_text("call me at 8016349122", ADMIN_ID)
            prompt = await build_clone_system_prompt(ADMIN_ID)
            return out, prompt

        out, prompt = asyncio.run(_run())
        assert "(435) 220-3414" in out, out
        assert "8016349122" not in out, out
        assert "PHONE NUMBER RULE" in prompt, prompt[-600:]
        assert "(435) 220-3414" in prompt.split("PHONE NUMBER RULE")[-1], prompt[-600:]


# ───────────────── cleanup ─────────────────
def test_zz_cleanup(admin_headers):
    uid = STATE.get("new_user_id")
    if not uid:
        pytest.skip("no user created")
    r = requests.delete(f"{API}/admin/users/{uid}/hard", headers=admin_headers, timeout=90)
    assert r.status_code in (200, 204, 404), f"hard delete -> {r.status_code} {r.text[:250]}"
    db.contacts.delete_many({"email": STATE.get("new_email"), "tags": "new-user"})
    db.password_reset_tokens.delete_many({"user_id": uid})
    assert db.users.find_one({"_id": ObjectId(uid)}) is None, "user still present after hard delete"
