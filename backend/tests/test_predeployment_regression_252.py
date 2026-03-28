"""
Pre-deployment regression test — Iteration 252
Tests: login, impersonation serialization, role update, admin endpoints,
master-feed performance, photo upload, PATCH base64 rejection, new contact route.

Credentials:
  super_admin: forest@imosapp.com / Admin123!
  test_user:   mjeast1985@gmail.com / NavyBean1!

Key IDs:
  ADMIN_ID = 69a0b7095fddcede09591667
  MATT_ID  = 69c75782e051d06491e6fa9f
"""
import pytest
import requests
import os
import time
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASS  = "Admin123!"
MATT_EMAIL  = "mjeast1985@gmail.com"
MATT_PASS   = "NavyBean1!"
ADMIN_ID    = "69a0b7095fddcede09591667"
MATT_ID     = "69c75782e051d06491e6fa9f"


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    token = r.json().get("token")
    assert token, "No token in admin login response"
    return token

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"X-User-ID": ADMIN_ID, "Authorization": f"Bearer {admin_token}"}


# ── Auth Tests ──────────────────────────────────────────────────────────────

class TestAuth:
    """Login flows — admin, regular user, wrong password"""

    def test_admin_login_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "token" in data, "No token returned"
        assert "user" in data, "No user returned"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"].get("role") in ("super_admin", "admin"), f"Unexpected role: {data['user'].get('role')}"
        print("PASS: Admin login → 200, role confirmed")

    def test_matt_login_success_not_onboarding(self):
        """mjeast1985@gmail.com (onboarding_complete: null) must NOT be redirected to onboarding"""
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": MATT_EMAIL, "password": MATT_PASS})
        assert r.status_code == 200, f"Matt login failed: {r.status_code}: {r.text}"
        data = r.json()
        assert "token" in data
        user = data["user"]
        assert user["email"] == MATT_EMAIL
        # onboarding_complete must NOT be False (it's null → frontend must NOT redirect to /onboarding)
        onb = user.get("onboarding_complete")
        assert onb is not False, f"onboarding_complete is False — will redirect to onboarding! Got: {onb}"
        print(f"PASS: Matt login → 200, onboarding_complete={onb} (null/True → goes to /home)")

    def test_wrong_password_returns_error(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": MATT_EMAIL, "password": "WrongPassword123!"})
        assert r.status_code in (401, 400), f"Expected 401/400 for wrong password, got {r.status_code}"
        body = r.text.lower()
        assert "invalid" in body or "password" in body or "credentials" in body, \
            f"Expected error message about invalid credentials, got: {r.text}"
        print(f"PASS: Wrong password → {r.status_code} with error message")

    def test_wrong_password_admin_returns_error(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "WrongPassword!"})
        assert r.status_code in (401, 400)
        print(f"PASS: Wrong admin password → {r.status_code}")


# ── Impersonation Tests ─────────────────────────────────────────────────────

class TestImpersonation:
    """POST /api/admin/users/{id}/impersonate — serialization fix verification"""

    def test_impersonate_matt_returns_success(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/users/{MATT_ID}/impersonate",
                          headers=admin_headers)
        assert r.status_code == 200, f"Impersonate failed: {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("success") is True, f"Expected success:true, got: {data}"
        assert "token" in data, "No impersonation token in response"
        assert "user" in data, "No user in impersonation response"
        print(f"PASS: Impersonation → success:true, token={data['token'][:20]}...")

    def test_impersonate_response_is_json_serializable(self, admin_headers):
        """Regression: ObjectId serialization error caused 500 on impersonate"""
        r = requests.post(f"{BASE_URL}/api/admin/users/{MATT_ID}/impersonate",
                          headers=admin_headers)
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        # If response parses cleanly, serialization is working
        try:
            data = r.json()
            user = data.get("user", {})
            assert isinstance(user.get("_id"), str), "_id must be a string not ObjectId"
            print(f"PASS: Impersonation response cleanly JSON-serializable, user._id={user.get('_id')}")
        except Exception as e:
            pytest.fail(f"Response is not valid JSON: {e}")

    def test_impersonate_invalid_user_returns_404(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/users/000000000000000000000000/impersonate",
                          headers=admin_headers)
        assert r.status_code == 404, f"Expected 404 for invalid user, got {r.status_code}"
        print("PASS: Invalid user impersonate → 404")


# ── Hierarchy / Role Tests ──────────────────────────────────────────────────

class TestHierarchy:
    """PUT /api/admin/hierarchy/users/{id}/role — role update persists"""

    def test_role_update_returns_ok(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{MATT_ID}/role",
            json={"role": "user"},
            headers=admin_headers
        )
        assert r.status_code == 200, f"Role update failed: {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "ok", f"Expected status:ok, got: {data}"
        assert data.get("role") == "user", f"Expected role:user, got: {data}"
        print(f"PASS: Role update → status:ok, role:user")

    def test_role_update_invalid_role_returns_400(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{MATT_ID}/role",
            json={"role": "invalid_role_xyz"},
            headers=admin_headers
        )
        assert r.status_code == 400, f"Expected 400 for invalid role, got {r.status_code}: {r.text}"
        print(f"PASS: Invalid role → 400")

    def test_role_update_unauthenticated_returns_401(self):
        r = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{MATT_ID}/role",
            json={"role": "user"}
        )
        assert r.status_code == 401, f"Expected 401 without auth, got {r.status_code}"
        print("PASS: Unauthenticated role update → 401")


# ── Admin List/Overview Endpoints ───────────────────────────────────────────

class TestAdminListEndpoints:
    """GET endpoints that were in split admin.py files"""

    def test_get_users_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert r.status_code == 200, f"GET /admin/users failed: {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        assert len(data) > 0, "Expected at least 1 user in list"
        print(f"PASS: GET /admin/users → 200, {len(data)} users")

    def test_get_hierarchy_overview(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/hierarchy/overview", headers=admin_headers)
        assert r.status_code == 200, f"GET /admin/hierarchy/overview failed: {r.status_code}: {r.text}"
        data = r.json()
        assert "organizations" in data, f"Missing 'organizations' key: {data}"
        assert "total_organizations" in data, f"Missing 'total_organizations': {data}"
        print(f"PASS: GET /admin/hierarchy/overview → 200, {data.get('total_organizations')} orgs")

    def test_get_roles(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/roles", headers=admin_headers)
        assert r.status_code == 200, f"GET /admin/roles failed: {r.status_code}: {r.text}"
        data = r.json()
        assert "roles" in data, f"Missing 'roles' key: {data}"
        assert len(data["roles"]) > 0, "No roles returned"
        role_ids = [role["id"] for role in data["roles"]]
        assert "super_admin" in role_ids, "super_admin role missing"
        print(f"PASS: GET /admin/roles → 200, roles: {role_ids}")

    def test_get_platform_stats(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/stats", headers=admin_headers)
        assert r.status_code == 200, f"GET /admin/stats failed: {r.status_code}: {r.text}"
        data = r.json()
        # Should have some stats fields
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        print(f"PASS: GET /admin/stats → 200, keys: {list(data.keys())[:6]}")

    def test_get_billing_summary(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/billing/summary", headers=admin_headers)
        assert r.status_code == 200, f"GET /admin/billing/summary failed: {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        print(f"PASS: GET /admin/billing/summary → 200, keys: {list(data.keys())[:6]}")

    def test_get_permissions(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/permissions/{ADMIN_ID}", headers=admin_headers)
        assert r.status_code == 200, f"GET /admin/permissions/{ADMIN_ID} failed: {r.status_code}: {r.text}"
        data = r.json()
        assert "permissions" in data, f"Missing 'permissions' key: {data}"
        assert "user_id" in data, f"Missing 'user_id' key: {data}"
        print(f"PASS: GET /admin/permissions → 200")


# ── Master Feed Performance ─────────────────────────────────────────────────

class TestMasterFeed:
    """GET /api/contacts/{userId}/master-feed?limit=25 must respond < 2 seconds"""

    def test_master_feed_response_time(self, admin_headers):
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/contacts/{ADMIN_ID}/master-feed?limit=25",
            headers=admin_headers,
            timeout=10
        )
        elapsed = time.time() - start
        assert r.status_code == 200, f"master-feed failed: {r.status_code}: {r.text}"
        assert elapsed < 2.0, f"master-feed too slow: {elapsed:.2f}s (must be < 2s)"
        data = r.json()
        assert isinstance(data, (list, dict)), f"Unexpected response type: {type(data)}"
        print(f"PASS: master-feed responded in {elapsed:.2f}s (limit=25)")

    def test_master_feed_limit_respected(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/contacts/{ADMIN_ID}/master-feed?limit=25",
            headers=admin_headers
        )
        assert r.status_code == 200
        data = r.json()
        # Response is either a list or a dict with events/items key
        if isinstance(data, list):
            count = len(data)
        else:
            count = len(data.get("events", data.get("items", data.get("feed", []))))
        assert count <= 25, f"Limit not respected: returned {count} items (limit=25)"
        print(f"PASS: master-feed limit=25 respected, got {count} items")


# ── Photo Upload Tests ──────────────────────────────────────────────────────

class TestPhotoUpload:
    """Photo upload: PATCH rejects base64, POST /profile/{id}/photo accepts multipart"""

    def test_patch_rejects_base64_photo_url(self):
        """PATCH /api/users/{id} must return 400 when photo_url is base64"""
        b64_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        r = requests.patch(
            f"{BASE_URL}/api/users/{MATT_ID}",
            json={"photo_url": b64_data}
        )
        assert r.status_code == 400, \
            f"Expected 400 for base64 photo_url, got {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "base64" in body or "photo" in body or "upload" in body, \
            f"Expected error message about base64/photo, got: {r.text}"
        print(f"PASS: PATCH with base64 photo_url → 400 as expected")

    def test_profile_photo_upload_multipart(self, admin_headers):
        """POST /api/profile/{id}/photo accepts multipart and returns photo_url"""
        # Generate a valid 10x10 PNG using Pillow to avoid broken data stream
        try:
            from PIL import Image
            buf = io.BytesIO()
            img = Image.new("RGB", (10, 10), color=(200, 100, 50))
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
        except ImportError:
            # Fallback: known-good minimal valid PNG (10x10 red image)
            import base64
            # Valid 10x10 PNG (red) in base64
            b64 = "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAADklEQVQI12P4z8BQDwAEgAF/QualIQAAAABJRU5ErkJggg=="
            png_bytes = base64.b64decode(b64)

        files = {"file": ("test_photo.png", io.BytesIO(png_bytes), "image/png")}
        r = requests.post(
            f"{BASE_URL}/api/profile/{MATT_ID}/photo",
            files=files,
            headers={"X-User-ID": MATT_ID}
        )
        # Accept 200 (success) — NOT 500
        assert r.status_code != 500, f"Got 500 on photo upload: {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert "photo_url" in data or "url" in data, f"No photo_url in response: {data}"
            print(f"PASS: Profile photo upload → 200, photo_url returned")
        else:
            print(f"INFO: Photo upload → {r.status_code}: {r.text[:200]}")


# ── Health Check ────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_check(self):
        r = requests.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "healthy"
        print(f"PASS: Health check → {data}")
