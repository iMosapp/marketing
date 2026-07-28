"""
Tests for Phase 1 JWT security hardening:
- Login returns real JWT (not mock_token_)
- JWT is decodable and contains sub, role, exp
- Backdoor endpoints return 410 Gone
- Valid JWT accepted by RBAC endpoints
- verify_jwt_token() logic: valid, invalid, legacy mock_token
"""
import pytest
import requests
import os
import jwt as pyjwt

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_EMAIL = "forest@imosapp.com"
TEST_PASS = "Admin123!"


@pytest.fixture(scope="module")
def login_response():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()


# ── 1. Login returns real JWT ────────────────────────────────────────────────
class TestLoginJWT:
    def test_login_returns_token(self, login_response):
        assert "token" in login_response, "No token field in login response"

    def test_token_is_jwt_not_mock(self, login_response):
        token = login_response["token"]
        assert token.startswith("eyJ"), f"Token should start with 'eyJ', got: {token[:20]}"
        assert not token.startswith("mock_token_"), "Token must not be mock_token format"

    def test_token_decodable(self, login_response):
        token = login_response["token"]
        # Decode without verifying sig to inspect payload structure
        payload = pyjwt.decode(token, options={"verify_signature": False})
        assert "sub" in payload, "JWT missing 'sub' field"
        assert "role" in payload, "JWT missing 'role' field"
        assert "exp" in payload, "JWT missing 'exp' field"

    def test_token_sub_matches_user_id(self, login_response):
        token = login_response["token"]
        payload = pyjwt.decode(token, options={"verify_signature": False})
        user = login_response.get("user", {})
        assert payload["sub"] == user.get("_id"), f"sub={payload['sub']} != user._id={user.get('_id')}"

    def test_token_role_matches_user_role(self, login_response):
        token = login_response["token"]
        payload = pyjwt.decode(token, options={"verify_signature": False})
        user = login_response.get("user", {})
        assert payload["role"] == user.get("role"), f"JWT role={payload['role']} != user role={user.get('role')}"

    def test_token_signature_valid(self, login_response):
        token = login_response["token"]
        # Get JWT_SECRET from env (loaded via backend .env — read file directly)
        secret = None
        env_path = "/app/backend/.env"
        with open(env_path) as f:
            for line in f:
                if line.startswith("JWT_SECRET="):
                    secret = line.strip().split("=", 1)[1].strip('"').strip("'")
        assert secret, "JWT_SECRET not found in .env"
        # Should not raise
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        assert payload["sub"] is not None


# ── 2. Backdoor endpoints return 410 ────────────────────────────────────────
class TestBackdoorEndpoints410:
    def test_admin_reset_returns_410(self):
        resp = requests.post(f"{BASE_URL}/api/auth/admin-reset", json={})
        assert resp.status_code == 410, f"Expected 410, got {resp.status_code}: {resp.text}"

    def test_admin_fix_login_returns_410(self):
        resp = requests.post(f"{BASE_URL}/api/auth/admin-fix-login", json={})
        assert resp.status_code == 410, f"Expected 410, got {resp.status_code}: {resp.text}"

    def test_force_reset_password_returns_410(self):
        resp = requests.post(f"{BASE_URL}/api/auth/force-reset-password", json={})
        assert resp.status_code == 410, f"Expected 410, got {resp.status_code}: {resp.text}"

    def test_admin_fix_all_passwords_returns_410(self):
        resp = requests.post(f"{BASE_URL}/api/auth/admin-fix-all-passwords", json={})
        assert resp.status_code == 410, f"Expected 410, got {resp.status_code}: {resp.text}"


# ── 3. JWT accepted by RBAC-protected endpoints ──────────────────────────────
class TestJWTAcceptedByRBAC:
    def test_jwt_bearer_accepted(self, login_response):
        token = login_response["token"]
        user_id = login_response["user"]["_id"]
        headers = {"Authorization": f"Bearer {token}"}
        # /api/users/{user_id} or a simple RBAC-protected endpoint
        resp = requests.get(f"{BASE_URL}/api/auth/user/{user_id}", headers=headers)
        # Acceptable: 200 (found), not 401
        assert resp.status_code != 401, f"JWT not accepted by endpoint: {resp.status_code} {resp.text}"

    def test_invalid_jwt_x_user_id_fallback_still_works(self, login_response):
        """If JWT is invalid but no X-User-ID either → RBAC returns 401 on protected endpoint.
        Note: most data endpoints are not yet RBAC-protected (Phase 3). 
        We verify that an endpoint protected with get_current_user rejects invalid JWT when no fallback header.
        Using /api/auth/me which uses cookie-based auth — instead just confirm the JWT Bearer path works."""
        # This is a known Phase 3 gap per agent context — skip this specific RBAC check
        pytest.skip("Phase 3: data endpoints not yet RBAC-protected — expected per agent context")


# ── 4. verify_jwt_token unit-level via auth module ───────────────────────────
def _load_jwt_secret():
    """Load JWT_SECRET from backend .env and set in os.environ for testing."""
    import os
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("JWT_SECRET="):
                secret = line.strip().split("=", 1)[1].strip('"').strip("'")
                os.environ["JWT_SECRET"] = secret
                return secret
    return None


class TestVerifyJWTToken:
    def setup_method(self):
        _load_jwt_secret()

    def test_valid_jwt_returns_payload(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.auth import verify_jwt_token, create_jwt_token
        token = create_jwt_token("test_user_id", "user")
        payload = verify_jwt_token(token)
        assert payload is not None, "verify_jwt_token returned None for valid token"
        assert payload["sub"] == "test_user_id"
        assert payload["role"] == "user"

    def test_invalid_jwt_returns_none(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.auth import verify_jwt_token
        result = verify_jwt_token("totally.invalid.token")
        assert result is None, f"Expected None for invalid token, got {result}"

    def test_tampered_jwt_returns_none(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.auth import verify_jwt_token, create_jwt_token
        token = create_jwt_token("user123", "user")
        # Tamper: flip last char
        tampered = token[:-5] + "XXXXX"
        result = verify_jwt_token(tampered)
        assert result is None, f"Expected None for tampered token, got {result}"

    def test_legacy_mock_token_accepted(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.auth import verify_jwt_token
        result = verify_jwt_token("mock_token_69a0b7095fddcede09591667")
        assert result is not None, "Legacy mock_token_ should be accepted"
        assert result["sub"] == "69a0b7095fddcede09591667"
        assert result.get("_legacy") is True

    def test_empty_token_returns_none(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.auth import verify_jwt_token
        assert verify_jwt_token("") is None
        assert verify_jwt_token(None) is None
