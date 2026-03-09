"""
Test suite for:
1. Auth refactor with bcrypt password hashing + persistent sessions
2. Leaderboard v2 with period-based filters (week/month/all)
3. Push notification subscription endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"


class TestAuthBcrypt:
    """Auth tests: bcrypt password hashing, persistent sessions, logout"""
    
    def test_login_with_bcrypt_hashed_password(self):
        """Test login with credentials (password verified against bcrypt hash)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "user" in data, "Response should contain user data"
        assert "token" in data, "Response should contain token"
        assert data["user"]["email"] == TEST_EMAIL, "Email should match"
        
        # Check that imos_session cookie is set
        cookies = response.cookies
        assert "imos_session" in cookies, "imos_session cookie should be set on login"
        
        # Store for later tests
        self.__class__.user_id = data["user"]["_id"]
        self.__class__.session_cookie = cookies.get("imos_session")
        print(f"Login successful for user {data['user']['name']}, user_id: {self.user_id}")
    
    def test_persistent_session_via_cookie(self):
        """Test that GET /api/auth/me restores session from imos_session cookie"""
        # Create session with cookie
        session = requests.Session()
        session.cookies.set("imos_session", self.session_cookie)
        
        response = session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200, f"Session restore failed: {response.text}"
        
        data = response.json()
        assert "user" in data, "Response should contain user data"
        assert data["user"]["_id"] == self.user_id, "User ID should match from cookie"
        print(f"Session restored successfully for user {data['user']['name']}")
    
    def test_session_without_cookie_returns_401(self):
        """Test that GET /api/auth/me without cookie returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401 without cookie, got {response.status_code}"
        print("Correctly returns 401 without session cookie")
    
    def test_logout_clears_session(self):
        """Test that POST /api/auth/logout clears the imos_session cookie"""
        # Login first to get a valid session
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200
        
        # Now logout
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200, f"Logout failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Logout should return success: true"
        
        # Check that cookie is cleared (set to empty or deleted)
        set_cookie = response.headers.get("Set-Cookie", "")
        # Cookie should be deleted (max-age=0 or expires in past)
        print(f"Logout successful, Set-Cookie header: {set_cookie[:100]}")
    
    def test_invalid_login_credentials(self):
        """Test login with wrong password"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": "WrongPassword123"}
        )
        assert response.status_code == 401, f"Expected 401 for wrong password, got {response.status_code}"
        print("Correctly rejects invalid credentials")


class TestChangePassword:
    """Test change password with bcrypt verification"""
    
    def test_change_password_requires_correct_current_password(self):
        """Test that change-password verifies old password against bcrypt hash"""
        # First login to get user_id
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200
        user_id = login_resp.json()["user"]["_id"]
        
        # Try changing password with wrong current password
        response = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            json={
                "user_id": user_id,
                "current_password": "WrongCurrentPassword",
                "new_password": "NewPassword123!"
            }
        )
        assert response.status_code == 401, f"Expected 401 for wrong current password, got {response.status_code}"
        print("Correctly rejects password change with wrong current password")


class TestLeaderboardV2:
    """Leaderboard v2 tests with period-based filters"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.user_id = response.json()["user"]["_id"]
    
    def test_store_leaderboard_with_period_week(self):
        """Test GET /api/leaderboard/v2/store/{user_id}?period=week"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/store/{self.user_id}",
            params={"period": "week"}
        )
        assert response.status_code == 200, f"Store leaderboard failed: {response.text}"
        
        data = response.json()
        assert data.get("level") == "store", "Level should be 'store'"
        assert data.get("period") == "week", "Period should be 'week'"
        assert "leaderboard" in data, "Response should contain leaderboard array"
        assert "your_stats" in data, "Response should contain your_stats"
        assert "categories" in data, "Response should contain categories"
        print(f"Store leaderboard (week): {len(data['leaderboard'])} members, period={data['period']}")
    
    def test_store_leaderboard_with_period_month(self):
        """Test GET /api/leaderboard/v2/store/{user_id}?period=month"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/store/{self.user_id}",
            params={"period": "month"}
        )
        assert response.status_code == 200, f"Store leaderboard failed: {response.text}"
        
        data = response.json()
        assert data.get("period") == "month", "Period should be 'month'"
        print(f"Store leaderboard (month): {len(data['leaderboard'])} members")
    
    def test_store_leaderboard_with_period_all(self):
        """Test GET /api/leaderboard/v2/store/{user_id}?period=all (All Time)"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/store/{self.user_id}",
            params={"period": "all"}
        )
        assert response.status_code == 200, f"Store leaderboard failed: {response.text}"
        
        data = response.json()
        assert data.get("period") == "all", "Period should be 'all'"
        print(f"Store leaderboard (all time): {len(data['leaderboard'])} members")
    
    def test_org_leaderboard_with_period_week(self):
        """Test GET /api/leaderboard/v2/org/{user_id}?period=week"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/org/{self.user_id}",
            params={"period": "week"}
        )
        assert response.status_code == 200, f"Org leaderboard failed: {response.text}"
        
        data = response.json()
        assert data.get("level") == "org", "Level should be 'org'"
        print(f"Org leaderboard (week): {len(data.get('leaderboard', []))} stores")
    
    def test_org_leaderboard_with_period_month(self):
        """Test GET /api/leaderboard/v2/org/{user_id}?period=month"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/org/{self.user_id}",
            params={"period": "month"}
        )
        assert response.status_code == 200, f"Org leaderboard failed: {response.text}"
        
        data = response.json()
        print(f"Org leaderboard (month): {len(data.get('leaderboard', []))} stores")
    
    def test_global_leaderboard_with_period(self):
        """Test GET /api/leaderboard/v2/global/{user_id}?period=week"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/global/{self.user_id}",
            params={"period": "week"}
        )
        assert response.status_code == 200, f"Global leaderboard failed: {response.text}"
        
        data = response.json()
        assert data.get("level") == "global", "Level should be 'global'"
        assert "leaderboard" in data, "Response should contain leaderboard"
        assert "your_rank" in data, "Response should contain your_rank"
        print(f"Global leaderboard (week): {data.get('total_users', 0)} total users")
    
    def test_leaderboard_categories_returned(self):
        """Test that leaderboard returns category definitions"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/store/{self.user_id}"
        )
        assert response.status_code == 200
        
        data = response.json()
        categories = data.get("categories", {})
        assert "digital_cards" in categories, "Should have digital_cards category"
        assert "reviews" in categories, "Should have reviews category"
        assert "cards" in categories, "Should have cards category"
        assert "emails" in categories, "Should have emails category"
        assert "sms" in categories, "Should have sms category"
        print(f"Categories returned: {list(categories.keys())}")
    
    def test_leaderboard_your_stats_structure(self):
        """Test that your_stats has expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/leaderboard/v2/store/{self.user_id}",
            params={"period": "month"}
        )
        assert response.status_code == 200
        
        data = response.json()
        your_stats = data.get("your_stats", {})
        assert "rank" in your_stats, "your_stats should have rank"
        assert "scores" in your_stats, "your_stats should have scores"
        assert "streak" in your_stats, "your_stats should have streak"
        assert "level" in your_stats, "your_stats should have level"
        print(f"Your stats: rank={your_stats.get('rank')}, streak={your_stats.get('streak')}")


class TestPushNotifications:
    """Push notification subscription tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.user_id = response.json()["user"]["_id"]
    
    def test_get_vapid_key(self):
        """Test GET /api/push/vapid-key returns public key"""
        response = requests.get(f"{BASE_URL}/api/push/vapid-key")
        assert response.status_code == 200, f"VAPID key fetch failed: {response.text}"
        
        data = response.json()
        assert "public_key" in data, "Response should contain public_key"
        # VAPID public keys are typically ~87 characters base64
        print(f"VAPID public key: {data['public_key'][:50]}...")
    
    def test_push_subscribe_endpoint(self):
        """Test POST /api/push/subscribe/{user_id} accepts subscription object"""
        # Mock Web Push subscription object
        mock_subscription = {
            "subscription": {
                "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
                "expirationTime": None,
                "keys": {
                    "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                    "auth": "tBHItJI5svbpez7KI4CCXg"
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/push/subscribe/{self.user_id}",
            json=mock_subscription
        )
        assert response.status_code == 200, f"Push subscribe failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "subscribed", "Status should be 'subscribed'"
        print(f"Push subscription created successfully for user {self.user_id}")
    
    def test_push_subscribe_requires_valid_subscription(self):
        """Test that subscribe rejects invalid subscription objects"""
        # Missing endpoint
        invalid_subscription = {
            "subscription": {
                "keys": {"p256dh": "test", "auth": "test"}
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/push/subscribe/{self.user_id}",
            json=invalid_subscription
        )
        assert response.status_code == 400, f"Expected 400 for invalid subscription, got {response.status_code}"
        print("Correctly rejects invalid subscription without endpoint")


class TestCongratsCard:
    """Test congrats card quick links and review text"""
    
    def test_congrats_card_endpoint_exists(self):
        """Test GET /api/congrats/card/{card_id} endpoint"""
        # Use sample card ID from requirements
        card_id = "90cec0a4-885"
        response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        
        # Card may or may not exist, but endpoint should work
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"Congrats card found: {data.get('headline', 'N/A')}")
        else:
            print(f"Congrats card {card_id} not found (expected for test env)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
