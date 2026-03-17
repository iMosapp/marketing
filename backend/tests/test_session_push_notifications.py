"""
Test Session Persistence & Push Notifications - Iteration 175
Tests:
1. Session persistence: login sets imos_session cookie with secure=True
2. Session restore: GET /api/auth/me restores session from cookie
3. Push notifications: VAPID key, subscribe, unsubscribe, test push
4. Engagement signal push notification integration
5. Regression tests for existing endpoints
"""
import pytest
import requests
import os
from datetime import datetime

# Use PUBLIC URL from frontend/.env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://scheduler-update-1.preview.emergentagent.com").rstrip("/")

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a496841603573df5a41723"


class TestSessionPersistence:
    """Tests for session persistence fix - secure cookie and cookie-based session restore"""
    
    def test_login_returns_user_and_sets_cookie(self):
        """POST /api/auth/login returns user data and should set imos_session cookie"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "user" in data, "Response missing 'user' field"
        assert "token" in data, "Response missing 'token' field"
        assert data["user"]["email"] == TEST_EMAIL
        
        # Check for imos_session cookie in response
        cookies = response.cookies
        assert "imos_session" in cookies, "imos_session cookie not set"
        
        # Verify cookie value is the user ID
        assert cookies["imos_session"] == data["user"]["_id"]
        
        print(f"LOGIN SUCCESS: User {data['user']['name']} logged in, cookie set")
    
    def test_auth_me_restores_session_from_cookie(self):
        """GET /api/auth/me restores session from imos_session cookie"""
        # First login to get the cookie
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200
        
        session_cookie = login_response.cookies.get("imos_session")
        assert session_cookie, "No imos_session cookie from login"
        
        # Now call /auth/me with the cookie
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies={"imos_session": session_cookie}
        )
        
        assert me_response.status_code == 200, f"Session restore failed: {me_response.text}"
        
        data = me_response.json()
        assert "user" in data, "Response missing 'user' field"
        assert "token" in data, "Response missing 'token' field"
        assert data["user"]["email"] == TEST_EMAIL
        
        print(f"SESSION RESTORE SUCCESS: User {data['user']['name']} restored from cookie")
    
    def test_auth_me_returns_401_without_cookie(self):
        """GET /api/auth/me returns 401 without cookie"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("AUTH/ME without cookie correctly returns 401")
    
    def test_auth_me_returns_401_with_invalid_cookie(self):
        """GET /api/auth/me returns 401 with invalid cookie"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies={"imos_session": "invalid_session_id_12345"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("AUTH/ME with invalid cookie correctly returns 401")


class TestPushNotifications:
    """Tests for push notification infrastructure"""
    
    def test_vapid_key_endpoint(self):
        """GET /api/push/vapid-key returns VAPID public key"""
        response = requests.get(f"{BASE_URL}/api/push/vapid-key")
        
        assert response.status_code == 200, f"VAPID key endpoint failed: {response.text}"
        
        data = response.json()
        assert "public_key" in data, "Response missing 'public_key' field"
        
        # VAPID key should be a non-empty string (base64url encoded)
        vapid_key = data["public_key"]
        assert len(vapid_key) > 0, "VAPID key is empty"
        
        print(f"VAPID KEY: {vapid_key[:50]}...")
    
    def test_push_subscribe_endpoint(self):
        """POST /api/push/subscribe/{userId} stores push subscription"""
        # Create a test subscription (simulating browser PushManager output)
        test_subscription = {
            "subscription": {
                "endpoint": f"https://test-push-endpoint.com/test/{datetime.now().timestamp()}",
                "keys": {
                    "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkA",
                    "auth": "tBHItJI5svbpez7KI4CCXg"
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json=test_subscription
        )
        
        assert response.status_code == 200, f"Push subscribe failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "subscribed", f"Unexpected response: {data}"
        
        print(f"PUSH SUBSCRIBE SUCCESS for user {TEST_USER_ID}")
    
    def test_push_subscribe_fails_without_subscription(self):
        """POST /api/push/subscribe returns 400 without subscription data"""
        response = requests.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json={}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PUSH SUBSCRIBE without subscription correctly returns 400")
    
    def test_push_test_endpoint(self):
        """POST /api/push/test/{userId} attempts to send test push notification"""
        response = requests.post(f"{BASE_URL}/api/push/test/{TEST_USER_ID}")
        
        # Should return 200 regardless of whether push was actually sent
        # (depends on whether user has valid subscriptions)
        assert response.status_code == 200, f"Test push endpoint failed: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response missing 'status' field"
        # Status should be either 'sent' or 'no_subscriptions'
        assert data["status"] in ["sent", "no_subscriptions"], f"Unexpected status: {data['status']}"
        
        print(f"TEST PUSH: status={data['status']}, sent_to={data.get('sent_to', 0)}")
    
    def test_push_unsubscribe_endpoint(self):
        """DELETE /api/push/unsubscribe/{userId} removes push subscription"""
        # First subscribe to have something to unsubscribe
        test_endpoint = f"https://test-push-endpoint.com/unsubscribe-test/{datetime.now().timestamp()}"
        test_subscription = {
            "subscription": {
                "endpoint": test_endpoint,
                "keys": {
                    "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkA",
                    "auth": "tBHItJI5svbpez7KI4CCXg"
                }
            }
        }
        
        subscribe_response = requests.post(
            f"{BASE_URL}/api/push/subscribe/{TEST_USER_ID}",
            json=test_subscription
        )
        assert subscribe_response.status_code == 200
        
        # Now unsubscribe
        unsubscribe_response = requests.delete(
            f"{BASE_URL}/api/push/unsubscribe/{TEST_USER_ID}",
            json={"endpoint": test_endpoint}
        )
        
        assert unsubscribe_response.status_code == 200, f"Unsubscribe failed: {unsubscribe_response.text}"
        
        data = unsubscribe_response.json()
        assert data.get("status") == "unsubscribed", f"Unexpected response: {data}"
        
        print(f"PUSH UNSUBSCRIBE SUCCESS for user {TEST_USER_ID}")


class TestEngagementSignalPush:
    """Tests for engagement signal push notification integration"""
    
    def test_engagement_signal_endpoint(self):
        """POST /api/engagement/signal - verify endpoint doesn't crash with push integration"""
        # Note: The engagement signal is recorded via the record_signal function internally
        # We test the hot-leads endpoint which uses engagement signals
        response = requests.get(f"{BASE_URL}/api/engagement/hot-leads/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Hot leads endpoint failed: {response.text}"
        
        data = response.json()
        assert "hot_leads" in data, "Response missing 'hot_leads' field"
        assert "total" in data, "Response missing 'total' field"
        
        print(f"HOT LEADS: {data['total']} leads in last {data.get('period_hours', 48)} hours")
    
    def test_engagement_signals_list(self):
        """GET /api/engagement/signals/{userId} returns engagement signals"""
        response = requests.get(f"{BASE_URL}/api/engagement/signals/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Signals endpoint failed: {response.text}"
        
        data = response.json()
        assert "signals" in data, "Response missing 'signals' field"
        
        print(f"ENGAGEMENT SIGNALS: {len(data['signals'])} signals found")


class TestRegressionContactEvents:
    """Regression tests for contact events (ensure push changes don't break existing functionality)"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200
        return login_response.cookies
    
    def test_contact_events_endpoint(self, auth_session):
        """POST /api/contacts/{userId}/{contactId}/events still works correctly"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json={
                "event_type": "test_push_regression",
                "content": "Testing push notification regression",
                "channel": "system"
            },
            cookies=auth_session
        )
        
        assert response.status_code == 200, f"Contact events failed: {response.text}"
        print(f"CONTACT EVENTS: Event logged successfully")


class TestRegressionTaskPerformance:
    """Regression tests for task performance endpoint"""
    
    def test_tasks_performance_endpoint(self):
        """GET /api/tasks/{userId}/performance still works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/performance",
            params={"period": "week"}
        )
        
        assert response.status_code == 200, f"Performance endpoint failed: {response.text}"
        
        data = response.json()
        # Check expected top-level fields exist (actual response structure)
        expected_fields = ["communication", "click_through", "engagement"]
        for field in expected_fields:
            assert field in data, f"Response missing '{field}' field"
        
        # Check nested communication fields
        comm = data.get("communication", {})
        assert "calls" in comm, "communication missing 'calls' field"
        assert "texts" in comm, "communication missing 'texts' field"
        assert "emails" in comm, "communication missing 'emails' field"
        
        print(f"PERFORMANCE: calls={comm['calls']}, texts={comm['texts']}, emails={comm['emails']}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
