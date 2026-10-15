"""API-level smoke tests for the launch-compliance batch (preview-only).

Covers: login + billing_lock surface, consent CRUD + rules, STOP suppression gate,
subscription-lock middleware (locked owner + rep), team-view RBAC, public opt-in link.
"""
import os
import time
import secrets
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

CREDS = {
    "forest":   ("forest@imosapp.com", "Admin123!"),
    "manager":  ("qa-manager@invalid.imonsocial.test", "Manager123!"),
    "orgadmin": ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!"),
    "rep":      ("activation-tester@invalid.imonsocial.test", "NewPass123!"),
    "locked_owner": ("qa-locked-owner@invalid.imonsocial.test", "LockedOwner123!"),
    "locked_rep":   ("qa-locked-rep@invalid.imonsocial.test",   "LockedRep123!"),
}


def _login(key):
    email, password = CREDS[key]
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {key} failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    return data["token"], data["user"]


@pytest.fixture(scope="module")
def manager():
    return _login("manager")


@pytest.fixture(scope="module")
def rep():
    return _login("rep")


@pytest.fixture(scope="module")
def orgadmin():
    return _login("orgadmin")


@pytest.fixture(scope="module")
def forest():
    return _login("forest")


# ---------- Billing lock surface on login ----------
class TestLoginBillingLock:
    def test_unlocked_user_billing_lock_shape(self, manager):
        _, user = manager
        bl = user.get("billing_lock") or {}
        assert bl.get("locked") in (False, None)

    def test_locked_rep_login_returns_locked_lock(self):
        _, user = _login("locked_rep")
        bl = user.get("billing_lock") or {}
        assert bl.get("locked") is True, f"expected locked rep, got {bl}"
        assert bl.get("owner") is False

    def test_locked_owner_login_returns_locked_owner_true(self):
        _, user = _login("locked_owner")
        bl = user.get("billing_lock") or {}
        assert bl.get("locked") is True
        assert bl.get("owner") is True


# ---------- Subscription-lock middleware (API side) ----------
class TestLockMiddleware:
    def _auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_locked_rep_blocked_from_team_view(self):
        token, user = _login("locked_rep")
        r = requests.get(f"{BASE}/api/team-view", headers=self._auth(token), timeout=30)
        assert r.status_code == 403, r.status_code
        body = r.json()
        assert body.get("reason") == "billing_locked" or "billing_locked" in str(body).lower()
        assert body.get("owner") is False

    def test_locked_owner_blocked_from_non_billing(self):
        token, user = _login("locked_owner")
        r = requests.get(f"{BASE}/api/team-view", headers=self._auth(token), timeout=30)
        assert r.status_code == 403
        body = r.json()
        assert body.get("owner") is True

    def test_health_always_open(self):
        r = requests.get(f"{BASE}/api/health", timeout=30)
        assert r.status_code == 200

    def test_billing_access_always_open_locked_owner(self):
        token, _ = _login("locked_owner")
        r = requests.get(f"{BASE}/api/billing/access", headers=self._auth(token), timeout=30)
        assert r.status_code in (200, 204), f"{r.status_code} {r.text[:200]}"


# ---------- Consent API ----------
class TestConsentAPI:
    QA_CONTACT = "6ab851b9d83dc707df7f595b"  # QA Demo (+15005550052)

    def _auth(self, token):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def test_statements_available(self, manager):
        token, _ = manager
        r = requests.get(f"{BASE}/api/consent/statements", headers=self._auth(token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_get_contact_state_shape(self, manager):
        token, _ = manager
        r = requests.get(f"{BASE}/api/consent/contact/{self.QA_CONTACT}",
                         headers=self._auth(token), timeout=30)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # Must include per-scope state, opted_out flag, history, statements
        assert "opted_out" in data
        assert "statements" in data or "scopes" in data or "state" in data

    def test_verbal_marketing_refused(self, manager):
        token, _ = manager
        r = requests.post(
            f"{BASE}/api/consent/contact/{self.QA_CONTACT}",
            headers=self._auth(token),
            json={"scopes": ["marketing"], "method": "verbal_in_person", "source": "qa"},
            timeout=30,
        )
        # Verbal must never authorize marketing -> 400
        assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text[:200]}"

    def test_verbal_requested_and_transactional_granted(self, manager):
        token, _ = manager
        r = requests.post(
            f"{BASE}/api/consent/contact/{self.QA_CONTACT}",
            headers=self._auth(token),
            json={"scopes": ["requested_info", "transactional"],
                  "method": "verbal_in_person", "source": "qa"},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"

    def test_revoke_endpoint_exists(self, manager):
        token, _ = manager
        r = requests.post(
            f"{BASE}/api/consent/contact/{self.QA_CONTACT}/revoke",
            headers=self._auth(token),
            json={"scopes": ["marketing"], "source": "qa"},
            timeout=30,
        )
        assert r.status_code in (200, 204, 400), r.status_code

    def test_opt_in_link_create_and_public_fetch(self, manager):
        token, _ = manager
        r = requests.post(
            f"{BASE}/api/consent/contact/{self.QA_CONTACT}/opt-in-link",
            headers=self._auth(token),
            json={"scopes": ["marketing"]},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"
        body = r.json()
        token_val = body.get("token") or (body.get("url") or "").rsplit("/", 1)[-1]
        assert token_val, f"no token in {body}"
        # Public page endpoint (no auth)
        pr = requests.get(f"{BASE}/api/public/consent/{token_val}", timeout=30)
        assert pr.status_code == 200, f"{pr.status_code} {pr.text[:200]}"
        pd = pr.json()
        assert pd.get("used") in (False, None) or "scopes" in pd


# ---------- Team-view RBAC ----------
class TestTeamView:
    def _auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_manager_sees_own_store(self, manager):
        token, _ = manager
        r = requests.get(f"{BASE}/api/team-view", headers=self._auth(token), timeout=30)
        # qa-manager has a store but no organization_id: the location is the boundary
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("scope") == "store"

    def test_rep_forbidden(self, rep):
        token, _ = rep
        r = requests.get(f"{BASE}/api/team-view", headers=self._auth(token), timeout=30)
        assert r.status_code == 403

    def test_orgadmin_own_org(self, orgadmin):
        token, _ = orgadmin
        r = requests.get(f"{BASE}/api/team-view", headers=self._auth(token), timeout=30)
        assert r.status_code == 200

    def test_orgadmin_cannot_pass_other_org(self, orgadmin):
        token, _ = orgadmin
        r = requests.get(f"{BASE}/api/team-view?org_id=00000000000000000000ffff",
                         headers=self._auth(token), timeout=30)
        assert r.status_code == 403

    def test_super_admin_defaults_to_own_org(self, forest):
        token, _ = forest
        r = requests.get(f"{BASE}/api/team-view", headers=self._auth(token), timeout=30)
        # By design: without ?org_id= a super admin sees their own organization (the My Team screen sends no org_id)
        assert r.status_code == 200, r.text[:200]


# ---------- Public endpoints untouched by lock ----------
class TestAlwaysOpen:
    def test_auth_login_route_open_unauthed(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": "noone@example.com",
                                                          "password": "x"}, timeout=30)
        # 401/400 but not 403 billing_locked
        assert r.status_code in (400, 401, 422)
