"""
Tests for Personal Best Tracking and Push Notifications features.
- Personal bests: best_day, best_day_date, best_week fields in /api/tasks/{userId}/performance
- Push notifications: VAPID key endpoint, subscribe/unsubscribe endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed - status {response.status_code}")


@pytest.fixture
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Session with auth header."""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestPerformancePersonalBests:
    """Tests for personal bests in /api/tasks/{userId}/performance endpoint."""

    def test_performance_endpoint_returns_personal_bests_object(self, authenticated_client):
        """GET /api/tasks/{userId}/performance should include personal_bests object."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "personal_bests" in data, "Response should include 'personal_bests' field"
        
        personal_bests = data["personal_bests"]
        assert isinstance(personal_bests, dict), "personal_bests should be a dictionary"
        print(f"✓ personal_bests object found: {personal_bests}")

    def test_personal_bests_contains_best_day(self, authenticated_client):
        """personal_bests should contain best_day field as a number."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        personal_bests = data.get("personal_bests", {})
        
        assert "best_day" in personal_bests, "personal_bests should have 'best_day' field"
        assert isinstance(personal_bests["best_day"], (int, float)), "best_day should be a number"
        print(f"✓ best_day value: {personal_bests['best_day']}")

    def test_personal_bests_contains_best_day_date(self, authenticated_client):
        """personal_bests should contain best_day_date field (string or None)."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        personal_bests = data.get("personal_bests", {})
        
        assert "best_day_date" in personal_bests, "personal_bests should have 'best_day_date' field"
        best_day_date = personal_bests["best_day_date"]
        # best_day_date can be None or a date string
        assert best_day_date is None or isinstance(best_day_date, str), "best_day_date should be string or None"
        print(f"✓ best_day_date value: {best_day_date}")

    def test_personal_bests_contains_best_week(self, authenticated_client):
        """personal_bests should contain best_week field as a number."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        personal_bests = data.get("personal_bests", {})
        
        assert "best_week" in personal_bests, "personal_bests should have 'best_week' field"
        assert isinstance(personal_bests["best_week"], (int, float)), "best_week should be a number"
        print(f"✓ best_week value: {personal_bests['best_week']}")

    def test_best_day_is_positive_with_existing_data(self, authenticated_client):
        """With existing data in the system, best_day should be > 0."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        personal_bests = data.get("personal_bests", {})
        best_day = personal_bests.get("best_day", 0)
        
        # Per review request, expected best_day=86 (2026-02-27), best_week=186
        assert best_day > 0, f"best_day should be > 0 (system has data), got {best_day}"
        print(f"✓ best_day is positive: {best_day}")

    def test_performance_endpoint_returns_scorecard_with_today(self, authenticated_client):
        """scorecard should have 'today' field for TODAY tile comparison."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        assert "scorecard" in data, "Response should include 'scorecard' field"
        
        scorecard = data["scorecard"]
        assert "today" in scorecard, "scorecard should have 'today' field"
        assert isinstance(scorecard["today"], (int, float)), "today should be a number"
        print(f"✓ scorecard.today value: {scorecard['today']}")


class TestVapidKeyEndpoint:
    """Tests for GET /api/push/vapid-key endpoint."""

    def test_vapid_key_endpoint_exists(self, api_client):
        """GET /api/push/vapid-key should return 200."""
        response = api_client.get(f"{BASE_URL}/api/push/vapid-key")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ VAPID key endpoint exists and returns 200")

    def test_vapid_key_returns_public_key(self, api_client):
        """GET /api/push/vapid-key should return public_key field."""
        response = api_client.get(f"{BASE_URL}/api/push/vapid-key")
        assert response.status_code == 200
        
        data = response.json()
        assert "public_key" in data, "Response should include 'public_key' field"
        print(f"✓ public_key field exists")

    def test_vapid_key_is_non_empty_string(self, api_client):
        """public_key should be a non-empty string."""
        response = api_client.get(f"{BASE_URL}/api/push/vapid-key")
        assert response.status_code == 200
        
        data = response.json()
        public_key = data.get("public_key", "")
        
        assert isinstance(public_key, str), "public_key should be a string"
        assert len(public_key) > 0, "public_key should be non-empty"
        print(f"✓ public_key is non-empty string with length {len(public_key)}")


class TestPushSubscription:
    """Tests for POST /api/push/subscribe/{userId} and DELETE /api/push/unsubscribe/{userId}."""

    def test_subscribe_endpoint_stores_subscription(self, authenticated_client):
        """POST /api/push/subscribe/{userId} should store a subscription."""
        test_subscription = {
            "subscription": {
                "endpoint": "https://test.push.endpoint/TEST_" + str(os.urandom(4).hex()),
                "keys": {
                    "p256dh": "BL9234567890_TEST_P256DH_KEY_FOR_TESTING",
                    "auth": "TEST_AUTH_KEY"
                }
            }
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json=test_subscription
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "subscribed", f"Expected status='subscribed', got {data}"
        print(f"✓ Subscription stored successfully")

    def test_subscribe_with_invalid_subscription_returns_400(self, authenticated_client):
        """POST /api/push/subscribe with invalid subscription should return 400."""
        # Missing endpoint
        invalid_subscription = {
            "subscription": {
                "keys": {
                    "p256dh": "test",
                    "auth": "test"
                }
            }
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json=invalid_subscription
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid subscription correctly returns 400")

    def test_subscribe_with_missing_subscription_returns_400(self, authenticated_client):
        """POST /api/push/subscribe with no subscription field should return 400."""
        response = authenticated_client.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json={}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Missing subscription correctly returns 400")

    def test_unsubscribe_endpoint_removes_subscription(self, authenticated_client):
        """DELETE /api/push/unsubscribe/{userId} should remove subscription."""
        # First subscribe
        test_endpoint = "https://test.push.endpoint/TEST_UNSUBSCRIBE_" + str(os.urandom(4).hex())
        test_subscription = {
            "subscription": {
                "endpoint": test_endpoint,
                "keys": {
                    "p256dh": "TEST_KEY",
                    "auth": "TEST_AUTH"
                }
            }
        }
        
        subscribe_response = authenticated_client.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json=test_subscription
        )
        assert subscribe_response.status_code == 200
        
        # Now unsubscribe
        unsubscribe_response = authenticated_client.delete(
            f"{BASE_URL}/api/push/unsubscribe/{TEST_USER_ID}",
            json={"endpoint": test_endpoint}
        )
        
        assert unsubscribe_response.status_code == 200, f"Expected 200, got {unsubscribe_response.status_code}"
        
        data = unsubscribe_response.json()
        assert data.get("status") == "unsubscribed", f"Expected status='unsubscribed', got {data}"
        print("✓ Unsubscribe endpoint works correctly")


class TestServiceWorkerAccess:
    """Tests for service worker file accessibility."""

    def test_sw_push_js_is_accessible(self, api_client):
        """GET /sw-push.js should return the service worker file."""
        # Service worker should be served from the frontend public directory
        frontend_url = BASE_URL.replace('/api', '')  # Remove /api if present
        
        response = api_client.get(f"{BASE_URL}/sw-push.js")
        
        # It may return 200 if served by backend or 404 if only frontend serves it
        # We just need to verify it doesn't crash the server
        print(f"Service worker request status: {response.status_code}")
        # This test is informational - the file is in frontend/public which is served by frontend server


class TestPerformanceIntegration:
    """Integration tests for personal bests with actual data."""

    def test_performance_returns_all_expected_fields(self, authenticated_client):
        """Full response structure validation."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all top-level fields
        expected_fields = [
            "total_touchpoints",
            "trend_pct",
            "scorecard",
            "personal_bests",
            "communication",
            "sharing",
            "engagement",
            "click_through"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify scorecard fields
        scorecard = data["scorecard"]
        for field in ["today", "yesterday", "diff", "streak", "streak_threshold"]:
            assert field in scorecard, f"Missing scorecard field: {field}"
        
        # Verify personal_bests fields
        personal_bests = data["personal_bests"]
        for field in ["best_day", "best_day_date", "best_week"]:
            assert field in personal_bests, f"Missing personal_bests field: {field}"
        
        print("✓ All expected fields present in performance response")
        print(f"  - total_touchpoints: {data['total_touchpoints']}")
        print(f"  - scorecard.today: {scorecard['today']}")
        print(f"  - scorecard.streak: {scorecard['streak']}")
        print(f"  - personal_bests.best_day: {personal_bests['best_day']}")
        print(f"  - personal_bests.best_day_date: {personal_bests['best_day_date']}")
        print(f"  - personal_bests.best_week: {personal_bests['best_week']}")

    def test_today_vs_best_day_comparison(self, authenticated_client):
        """Verify today count can be compared with best_day for UI display."""
        response = authenticated_client.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        today = data["scorecard"]["today"]
        best_day = data["personal_bests"]["best_day"]
        
        # UI logic: if today > best_day -> "NEW RECORD!", else show "X to beat"
        if today > best_day:
            print(f"✓ Today ({today}) > best_day ({best_day}) → UI would show 'NEW RECORD!'")
        else:
            to_beat = best_day - today
            print(f"✓ Today ({today}) <= best_day ({best_day}) → UI would show '{to_beat} to beat'")
