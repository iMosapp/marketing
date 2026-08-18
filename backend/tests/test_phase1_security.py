"""
Phase 1 Security Tests:
- verify_jwt_token mock_token_ rejection
- X-User-ID header fallback removed (JWT only)
- GET /auth/user/{id} requires JWT + ownership
- POST /auth/ref/backfill requires super_admin
- GET /auth/ref/{ref_code} returns minimal info
"""
import pytest
import requests
import os
import sys

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"

# ── Helper ────────────────────────────────────────────────────────────────────

def get_super_admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp.json()["token"]


# ── Test 1: Login returns a real JWT ─────────────────────────────────────────

class TestLoginReturnsRealJWT:
    def test_login_token_starts_with_eyj(self):
        """Login must return a proper signed JWT (starts with eyJ)."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("token", "")
        assert token.startswith("eyJ"), f"Token does not look like a JWT: {token[:20]}"
        print(f"PASS: Token starts with eyJ — real JWT confirmed")


# ── Test 2: verify_jwt_token unit-level via HTTP behavior ────────────────────

class TestMockTokenRejected:
    def test_mock_token_rejected_on_rbac_endpoint(self):
        """Bearer mock_token_ must return 401 on any RBAC-protected endpoint."""
        # Use GET /api/auth/user/{id} which requires JWT
        resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={"Authorization": "Bearer mock_token_anyid"}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print(f"PASS: mock_token_ rejected with 401")

    def test_empty_bearer_rejected(self):
        """Empty Bearer token must return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={"Authorization": "Bearer "}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Empty Bearer token rejected with 401")

    def test_no_auth_header_rejected(self):
        """No auth header must return 401 on protected endpoint."""
        resp = requests.get(f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: No auth header returns 401")


# ── Test 3: X-User-ID header alone must NOT work ─────────────────────────────

class TestXUserIDFallbackRemoved:
    def test_x_user_id_header_alone_fails(self):
        """X-User-ID header without JWT must return 401 on RBAC endpoint."""
        resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("PASS: X-User-ID header alone rejected with 401")

    def test_x_user_id_with_mock_token_fails(self):
        """X-User-ID header + mock_token_ must return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={
                "X-User-ID": SUPER_ADMIN_ID,
                "Authorization": f"Bearer mock_token_{SUPER_ADMIN_ID}"
            }
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: X-User-ID + mock_token_ rejected with 401")


# ── Test 4: GET /auth/user/{id} ownership check ──────────────────────────────

class TestGetUserOwnership:
    def test_get_own_user_with_valid_jwt_returns_200(self):
        """Owner can fetch their own profile with valid JWT."""
        token = get_super_admin_token()
        resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "_id" in data or "id" in str(data)
        print("PASS: Owner can fetch own profile with valid JWT")

    def test_get_different_user_with_low_role_returns_403(self):
        """A non-admin user fetching another user's profile must get 403."""
        # Login as the test user (role: user)
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "mjeast1985@gmail.com",
            "password": "NavyBean1!"
        })
        if resp.status_code != 200:
            pytest.skip(f"Test user login failed: {resp.status_code}")
        token = resp.json()["token"]
        test_user_id = resp.json()["user"]["_id"]

        # Try to fetch super admin's profile (different user)
        fetch_resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert fetch_resp.status_code == 403, f"Expected 403, got {fetch_resp.status_code}: {fetch_resp.text}"
        print("PASS: Non-admin user gets 403 when fetching another user's profile")

    def test_super_admin_can_fetch_any_user(self):
        """Super admin can fetch any user's profile."""
        token = get_super_admin_token()
        # Fetch the test user's profile using super admin token
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "mjeast1985@gmail.com",
            "password": "NavyBean1!"
        })
        if resp.status_code != 200:
            pytest.skip("Test user not available")
        test_user_id = resp.json()["user"]["_id"]

        fetch_resp = requests.get(
            f"{BASE_URL}/api/auth/user/{test_user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert fetch_resp.status_code == 200, f"Expected 200, got {fetch_resp.status_code}"
        print("PASS: Super admin can fetch any user profile")


# ── Test 5: POST /auth/ref/backfill requires super_admin ─────────────────────

class TestRefBackfillAuth:
    def test_backfill_without_auth_returns_403(self):
        """POST /auth/ref/backfill without auth must return 403."""
        resp = requests.post(f"{BASE_URL}/api/auth/ref/backfill")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: /ref/backfill without auth returns 403")

    def test_backfill_with_mock_token_returns_403(self):
        """POST /auth/ref/backfill with mock_token_ must return 403."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/ref/backfill",
            headers={"Authorization": f"Bearer mock_token_{SUPER_ADMIN_ID}"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("PASS: /ref/backfill with mock_token_ returns 403")

    def test_backfill_with_super_admin_jwt_succeeds(self):
        """POST /auth/ref/backfill with super_admin JWT must succeed."""
        token = get_super_admin_token()
        resp = requests.post(
            f"{BASE_URL}/api/auth/ref/backfill",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "success"
        print(f"PASS: Super admin can call /ref/backfill. Backfilled: {data.get('backfilled')}")

    def test_backfill_with_non_admin_jwt_returns_403(self):
        """POST /auth/ref/backfill with non-super_admin JWT must return 403."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "mjeast1985@gmail.com",
            "password": "NavyBean1!"
        })
        if resp.status_code != 200:
            pytest.skip("Test user login failed")
        token = resp.json()["token"]

        backfill_resp = requests.post(
            f"{BASE_URL}/api/auth/ref/backfill",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert backfill_resp.status_code == 403, f"Expected 403, got {backfill_resp.status_code}"
        print("PASS: Non-admin user gets 403 on /ref/backfill")


# ── Test 6: GET /auth/ref/{ref_code} minimal info ────────────────────────────

class TestRefCodeMinimalInfo:
    def test_ref_code_returns_only_allowed_fields(self):
        """GET /auth/ref/{ref_code} must NOT return email, role, or org_id."""
        # First get the super admin's ref code
        token = get_super_admin_token()
        user_resp = requests.get(
            f"{BASE_URL}/api/auth/user/{SUPER_ADMIN_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if user_resp.status_code != 200:
            pytest.skip("Could not fetch super admin user to get ref_code")
        ref_code = user_resp.json().get("ref_code")
        if not ref_code:
            pytest.skip("Super admin has no ref_code")

        ref_resp = requests.get(f"{BASE_URL}/api/auth/ref/{ref_code}")
        assert ref_resp.status_code == 200
        data = ref_resp.json()

        # Must have status + user_id + name
        assert data.get("status") == "found"
        assert "user_id" in data
        assert "name" in data

        # Must NOT have sensitive fields
        assert "email" not in data, f"email should NOT be in ref response: {data}"
        assert "role" not in data, f"role should NOT be in ref response: {data}"
        assert "org_id" not in data, f"org_id should NOT be in ref response: {data}"
        assert "organization_id" not in data, f"organization_id should NOT be in ref response: {data}"
        print(f"PASS: /ref/{{ref_code}} returns only: {list(data.keys())}")

    def test_ref_code_not_found_returns_status(self):
        """GET /auth/ref/INVALID returns status=not_found."""
        resp = requests.get(f"{BASE_URL}/api/auth/ref/INVALIDCODE999")
        assert resp.status_code == 200
        assert resp.json().get("status") == "not_found"
        print("PASS: Invalid ref_code returns status=not_found")
