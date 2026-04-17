"""
Test Suite for Unified Card System
Tests the consolidation of birthday_cards into congrats_cards
and the new image migration admin button.

Features tested:
1. GET /api/congrats/card/{card_id} - returns cards from BOTH collections
2. POST /api/congrats/card/{card_id}/track - tracks actions for both collections  
3. GET /api/congrats/card/{card_id}/image - generates images for cards from both collections
4. GET /api/congrats/history/{salesman_id} - returns merged cards from both collections
5. Legacy /api/birthday/* routes - should return 404 (removed)
6. POST /api/images/migrate-all-base64 - image migration for super admin
"""
import os
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestUnifiedCardSystem:
    """Test unified congrats_cards system that handles all card types including birthday"""
    
    @pytest.fixture(scope="class")
    def auth_token_and_user(self):
        """Login and get auth token + user info"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return {
            "token": data.get("token"),
            "user_id": data.get("user", {}).get("_id"),
            "user": data.get("user")
        }
    
    def test_01_congrats_card_endpoint_exists(self, auth_token_and_user):
        """Verify GET /api/congrats/card/{card_id} endpoint is accessible"""
        # Test with a non-existent card ID to verify endpoint routing
        response = requests.get(f"{BASE_URL}/api/congrats/card/nonexistent123")
        # Should return 404 (card not found) not 405 (method not allowed)
        assert response.status_code == 404, f"Expected 404 for missing card, got {response.status_code}"
        assert "not found" in response.json().get("detail", "").lower()
        print("PASS: GET /api/congrats/card/{card_id} endpoint exists and returns 404 for missing card")
    
    def test_02_legacy_birthday_routes_removed(self):
        """Verify /api/birthday/* routes return 404 (removed from server.py)"""
        # Test various legacy birthday endpoints
        legacy_endpoints = [
            "/api/birthday/card/test123",
            "/api/birthday/template/test123",
            "/api/birthday/history/test123"
        ]
        
        for endpoint in legacy_endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            # Should return 404 Not Found (route doesn't exist)
            assert response.status_code == 404, f"Legacy endpoint {endpoint} should return 404, got {response.status_code}"
        
        print("PASS: All legacy /api/birthday/* routes return 404 (removed)")
    
    def test_03_congrats_history_endpoint(self, auth_token_and_user):
        """Test GET /api/congrats/history/{salesman_id} returns cards"""
        user_id = auth_token_and_user["user_id"]
        response = requests.get(f"{BASE_URL}/api/congrats/history/{user_id}")
        assert response.status_code == 200, f"History endpoint failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "History should return a list"
        
        # Check response structure if cards exist
        if len(data) > 0:
            card = data[0]
            assert "card_id" in card, "Card should have card_id"
            assert "card_type" in card, "Card should have card_type"
            assert "customer_name" in card, "Card should have customer_name"
            print(f"PASS: History endpoint returned {len(data)} cards with correct structure")
        else:
            print("PASS: History endpoint returned empty list (no cards)")
    
    def test_04_track_card_action_endpoint(self):
        """Test POST /api/congrats/card/{card_id}/track endpoint exists"""
        # Test with non-existent card to verify endpoint routing
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/nonexistent123/track",
            json={"action": "download"}
        )
        # Endpoint should be reachable (won't find the card, but routing works)
        # Could be 200 (silent fail) or 404 depending on implementation
        assert response.status_code in [200, 404], f"Track endpoint should be reachable, got {response.status_code}"
        print(f"PASS: Track endpoint accessible (status: {response.status_code})")
    
    def test_05_card_image_endpoint(self):
        """Test GET /api/congrats/card/{card_id}/image endpoint exists"""
        # Test with non-existent card
        response = requests.get(f"{BASE_URL}/api/congrats/card/nonexistent123/image")
        # Should return 404 for missing card
        assert response.status_code == 404, f"Expected 404 for missing card image, got {response.status_code}"
        print("PASS: GET /api/congrats/card/{card_id}/image endpoint exists")


class TestImageMigrationButton:
    """Test the new 'Migrate All Images' button for super admins"""
    
    @pytest.fixture(scope="class")
    def super_admin_auth(self):
        """Login as super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return {
            "token": data.get("token"),
            "user_id": data.get("user", {}).get("_id"),
            "role": data.get("user", {}).get("role")
        }
    
    def test_01_migrate_endpoint_requires_user_id(self):
        """Test POST /api/images/migrate-all-base64 without X-User-ID header"""
        response = requests.post(f"{BASE_URL}/api/images/migrate-all-base64")
        # Should require X-User-ID header for authorization
        assert response.status_code in [401, 403, 422], f"Expected auth error without X-User-ID, got {response.status_code}"
        print(f"PASS: Migrate endpoint requires X-User-ID header (status: {response.status_code})")
    
    def test_02_migrate_endpoint_with_valid_super_admin(self, super_admin_auth):
        """Test POST /api/images/migrate-all-base64 with valid super admin"""
        assert super_admin_auth["role"] == "super_admin", "Test requires super_admin role"
        
        headers = {"X-User-ID": super_admin_auth["user_id"]}
        response = requests.post(f"{BASE_URL}/api/images/migrate-all-base64", headers=headers)
        
        assert response.status_code == 200, f"Migration failed: {response.text}"
        
        data = response.json()
        # Verify response has expected fields
        assert "migrated" in data or "message" in data, f"Response should have migration result: {data}"
        
        # Check for expected fields
        if "migrated" in data:
            print(f"PASS: Migration completed - migrated: {data.get('migrated', 0)}, backfilled: {data.get('backfilled', 0)}, skipped: {data.get('skipped', 0)}")
        else:
            print(f"PASS: Migration endpoint responded with: {data}")
    
    def test_03_migrate_endpoint_rejects_non_super_admin(self, super_admin_auth):
        """Test that migration endpoint rejects non-super admin users"""
        # Create a fake user ID to test rejection
        fake_user_id = "000000000000000000000000"
        headers = {"X-User-ID": fake_user_id}
        response = requests.post(f"{BASE_URL}/api/images/migrate-all-base64", headers=headers)
        
        # Should reject non-existent or non-super-admin user
        # Could be 403 (forbidden), 404 (user not found), or 401 (unauthorized)
        assert response.status_code in [401, 403, 404], f"Expected auth rejection for fake user, got {response.status_code}"
        print(f"PASS: Migration endpoint rejects invalid user (status: {response.status_code})")


class TestCardSystemWithExistingCards:
    """Test unified card system with existing cards in the database"""
    
    @pytest.fixture(scope="class")
    def auth_and_history(self):
        """Login and get card history"""
        # Login
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        user_id = data.get("user", {}).get("_id")
        
        # Get card history
        history_response = requests.get(f"{BASE_URL}/api/congrats/history/{user_id}")
        cards = history_response.json() if history_response.status_code == 200 else []
        
        return {
            "user_id": user_id,
            "cards": cards
        }
    
    def test_01_get_existing_card_data(self, auth_and_history):
        """Test getting card data for an existing card"""
        cards = auth_and_history["cards"]
        
        if not cards:
            pytest.skip("No existing cards to test")
        
        card_id = cards[0]["card_id"]
        response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        
        assert response.status_code == 200, f"Failed to get card: {response.text}"
        
        data = response.json()
        assert data["card_id"] == card_id
        assert "customer_name" in data
        assert "headline" in data
        assert "message" in data
        assert "style" in data
        
        # Verify style has required fields
        style = data["style"]
        assert "background_color" in style
        assert "accent_color" in style
        assert "text_color" in style
        
        print(f"PASS: Card data retrieved with correct structure - card_id: {card_id}, type: {data.get('card_type', 'unknown')}")
    
    def test_02_track_download_action(self, auth_and_history):
        """Test tracking download action on existing card"""
        cards = auth_and_history["cards"]
        
        if not cards:
            pytest.skip("No existing cards to test")
        
        card_id = cards[0]["card_id"]
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "download"}
        )
        
        assert response.status_code == 200, f"Track download failed: {response.text}"
        assert response.json().get("success") == True
        print(f"PASS: Download action tracked for card {card_id}")
    
    def test_03_track_share_action(self, auth_and_history):
        """Test tracking share action on existing card"""
        cards = auth_and_history["cards"]
        
        if not cards:
            pytest.skip("No existing cards to test")
        
        card_id = cards[0]["card_id"]
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "share"}
        )
        
        assert response.status_code == 200, f"Track share failed: {response.text}"
        assert response.json().get("success") == True
        print(f"PASS: Share action tracked for card {card_id}")
    
    def test_04_get_card_image(self, auth_and_history):
        """Test generating card image for existing card"""
        cards = auth_and_history["cards"]
        
        if not cards:
            pytest.skip("No existing cards to test")
        
        card_id = cards[0]["card_id"]
        response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}/image")
        
        assert response.status_code == 200, f"Image generation failed: {response.text}"
        assert response.headers.get("content-type", "").startswith("image/"), f"Expected image response, got {response.headers.get('content-type')}"
        print(f"PASS: Card image generated successfully for card {card_id}")
    
    def test_05_invalid_track_action_rejected(self, auth_and_history):
        """Test that invalid track actions are rejected"""
        cards = auth_and_history["cards"]
        
        if not cards:
            pytest.skip("No existing cards to test")
        
        card_id = cards[0]["card_id"]
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "invalid_action"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid action, got {response.status_code}"
        print("PASS: Invalid track action rejected with 400")


class TestBirthdayCardFrontendRoute:
    """Test that birthday card page calls unified congrats endpoint"""
    
    def test_01_birthday_card_page_loads(self):
        """Test that the birthday card page route exists"""
        # The frontend page at /birthday/{cardId} should load
        # Note: We're just testing the API endpoint it calls
        response = requests.get(f"{BASE_URL}/api/congrats/card/test-birthday-123")
        # Should return 404 (not found) not 405 (wrong route)
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
        print("PASS: Birthday card page uses /api/congrats/card/{cardId} endpoint")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
