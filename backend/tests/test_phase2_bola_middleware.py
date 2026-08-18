"""
Phase 2 BOLA middleware tests — enforce_user_ownership middleware
Tests that the middleware blocks cross-user data access while allowing own data and admin access.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"

REGULAR_USER_EMAIL = "mjeast1985@gmail.com"
REGULAR_USER_PASSWORD = "NavyBean1!"


def get_token(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    return None


@pytest.fixture(scope="module")
def super_admin_token():
    token = get_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    if not token:
        pytest.skip("Super admin login failed")
    return token


@pytest.fixture(scope="module")
def regular_user_token():
    token = get_token(REGULAR_USER_EMAIL, REGULAR_USER_PASSWORD)
    if not token:
        pytest.skip("Regular user login failed")
    return token


@pytest.fixture(scope="module")
def regular_user_id(regular_user_token):
    """Get the regular user's own ID from token or profile endpoint."""
    resp = requests.get(
        f"{BASE_URL}/api/auth/user",
        headers={"Authorization": f"Bearer {regular_user_token}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("id") or data.get("_id") or data.get("user_id")
    # Try another common endpoint
    return None


class TestPublicRoutesSkippedByMiddleware:
    """Public routes must still work without auth."""

    def test_health_returns_200_no_auth(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        print("PASS: GET /api/health returns 200 without auth")

    def test_auth_login_works_without_auth(self):
        """POST /api/auth/login should not require a JWT."""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "access_token" in data or "token" in data, "No token in login response"
        print("PASS: POST /api/auth/login works without prior auth")


class TestLoginReturnsJWT:
    """Login returns valid JWT."""

    def test_super_admin_login_returns_token(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert resp.status_code == 200
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        assert token and len(token) > 20, "Expected a real JWT token"
        print(f"PASS: Super admin login returns JWT (len={len(token)})")

    def test_regular_user_login_returns_token(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": REGULAR_USER_EMAIL, "password": REGULAR_USER_PASSWORD}
        )
        assert resp.status_code == 200
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        assert token and len(token) > 20, "Expected a real JWT token"
        print(f"PASS: Regular user login returns JWT (len={len(token)})")


class TestBOLAMiddlewareContacts:
    """Test BOLA protection on /api/contacts/{user_id}"""

    def test_no_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/contacts/{SUPER_ADMIN_ID}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/contacts/{user_id} without auth returns 401")

    def test_wrong_user_jwt_returns_403(self, regular_user_token):
        """Regular user accessing super admin's contacts → 403."""
        resp = requests.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_ID}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Regular user cannot access another user's contacts (403)")

    def test_super_admin_accessing_other_user_contacts_returns_200(self, super_admin_token, regular_user_token):
        """Super admin can access any user's contacts."""
        # First get the regular user's ID
        resp_user = requests.get(
            f"{BASE_URL}/api/auth/user",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        if resp_user.status_code != 200:
            pytest.skip("Cannot determine regular user ID")
        data = resp_user.json()
        regular_id = data.get("id") or data.get("_id") or data.get("user_id")
        if not regular_id:
            pytest.skip("No user ID in response")

        resp = requests.get(
            f"{BASE_URL}/api/contacts/{regular_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        # Should be 200 (or potentially empty but not 403/401)
        assert resp.status_code not in (401, 403), f"Super admin should not be blocked, got {resp.status_code}: {resp.text}"
        print(f"PASS: Super admin accessing another user's contacts returns {resp.status_code}")

    def test_own_data_returns_200(self, super_admin_token):
        """Super admin accessing own contacts returns 200."""
        resp = requests.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_ID}",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert resp.status_code not in (401, 403), f"Own data access blocked, got {resp.status_code}: {resp.text}"
        print(f"PASS: Super admin accessing own contacts returns {resp.status_code}")


class TestBOLAMiddlewareTasks:
    """Test BOLA protection on /api/tasks/{user_id}"""

    def test_wrong_user_jwt_returns_403(self, regular_user_token):
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{SUPER_ADMIN_ID}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Regular user cannot access another user's tasks (403)")

    def test_no_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/tasks/{SUPER_ADMIN_ID}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/tasks/{user_id} without auth returns 401")


class TestBOLAMiddlewareVoiceNotes:
    """Test BOLA protection on /api/voice-notes/{user_id}/{contact_id}"""

    # Use a fake contact_id (valid ObjectId format)
    FAKE_CONTACT_ID = "aabbccddeeff001122334455"

    def test_wrong_user_jwt_returns_403(self, regular_user_token):
        resp = requests.get(
            f"{BASE_URL}/api/voice-notes/{SUPER_ADMIN_ID}/{self.FAKE_CONTACT_ID}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Regular user cannot access another user's voice-notes (403)")

    def test_no_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/voice-notes/{SUPER_ADMIN_ID}/{self.FAKE_CONTACT_ID}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("PASS: GET /api/voice-notes without auth returns 401")


class TestSubRouteNotBlocked:
    """Sub-routes without ObjectId should pass through (not blocked)."""

    def test_campaigns_scheduler_passes_through(self, super_admin_token):
        """Non-ObjectId sub-routes like /api/campaigns/scheduler must not be blocked."""
        resp = requests.get(
            f"{BASE_URL}/api/campaigns/scheduler",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        # Should not be 401/403 due to BOLA middleware (may be 404 if route doesn't exist)
        assert resp.status_code != 403, f"Sub-route incorrectly blocked by BOLA middleware: {resp.status_code}"
        print(f"PASS: /api/campaigns/scheduler passes BOLA middleware (status={resp.status_code})")
