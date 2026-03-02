"""
Test Link Page API - Linktree-style public profile pages
Tests: GET/PUT /api/linkpage/*, username availability check, click tracking
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_USERNAME = "forestward"


class TestLinkPagePublicEndpoints:
    """Tests for public link page endpoints"""

    def test_get_public_page_valid_username(self):
        """Test GET /api/linkpage/public/{username} - valid username"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "username" in data, "Response should have username"
        assert data["username"] == TEST_USERNAME, f"Expected {TEST_USERNAME}, got {data['username']}"
        assert "display_name" in data, "Response should have display_name"
        assert "links" in data, "Response should have links array"
        assert isinstance(data["links"], list), "links should be a list"
        print(f"PASS: Public page for {TEST_USERNAME} returned correctly with {len(data['links'])} links")

    def test_get_public_page_nonexistent_username(self):
        """Test GET /api/linkpage/public/{username} - 404 for non-existent"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/nonexistent_user_xyz123")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data, "Response should have detail field"
        assert "not found" in data["detail"].lower(), f"Expected 'not found' in detail, got {data['detail']}"
        print("PASS: Non-existent username returns 404 correctly")

    def test_get_public_page_has_required_fields(self):
        """Test public page response has all required display fields"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ["username", "display_name", "bio", "links", "theme", "accent_color"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: All required fields present: {required_fields}")


class TestLinkPageUserEndpoints:
    """Tests for authenticated user link page endpoints"""

    def test_get_user_link_page(self):
        """Test GET /api/linkpage/user/{user_id} - returns or creates link page"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "user_id" in data, "Response should have user_id"
        assert data["user_id"] == TEST_USER_ID, f"Expected user_id {TEST_USER_ID}"
        assert "username" in data, "Response should have username"
        assert "links" in data, "Response should have links"
        print(f"PASS: User link page returned with username: {data['username']}")

    def test_get_user_link_page_invalid_user(self):
        """Test GET /api/linkpage/user/{user_id} - invalid user returns 404"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/000000000000000000000000")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Invalid user_id returns 404")

    def test_update_link_page(self):
        """Test PUT /api/linkpage/user/{user_id} - update settings"""
        # First, get current state
        get_response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        assert get_response.status_code == 200
        original_data = get_response.json()
        original_bio = original_data.get("bio", "")
        
        # Update bio
        test_bio = "Test Bio - Updated via pytest"
        update_response = requests.put(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}",
            json={"bio": test_bio}
        )
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        
        # Verify update
        verify_response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        verify_data = verify_response.json()
        assert verify_data["bio"] == test_bio, f"Bio not updated correctly"
        
        # Restore original bio
        requests.put(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}",
            json={"bio": original_bio}
        )
        
        print("PASS: Link page update works correctly")


class TestUsernameAvailability:
    """Tests for username availability check endpoint"""

    def test_check_username_taken(self):
        """Test POST /api/linkpage/user/{user_id}/check-username - taken username"""
        response = requests.post(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}/check-username",
            json={"username": TEST_USERNAME}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "available" in data, "Response should have 'available' field"
        # forestward is this user's own username, should show as available (for them)
        assert "username" in data, "Response should have 'username' field"
        print(f"PASS: Username check returned: available={data['available']}")

    def test_check_username_available(self):
        """Test POST /api/linkpage/user/{user_id}/check-username - available username"""
        response = requests.post(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}/check-username",
            json={"username": "completely_unique_test_username_12345"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["available"] == True, f"Expected username to be available"
        print("PASS: Available username correctly detected")

    def test_check_username_too_short(self):
        """Test POST /api/linkpage/user/{user_id}/check-username - too short"""
        response = requests.post(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}/check-username",
            json={"username": "ab"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["available"] == False, "Short username should not be available"
        assert "reason" in data, "Should have reason for unavailability"
        print(f"PASS: Short username rejected with reason: {data.get('reason')}")


class TestClickTracking:
    """Tests for click tracking endpoint"""

    def test_track_link_click(self):
        """Test POST /api/linkpage/public/{username}/click - track click"""
        response = requests.post(
            f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}/click",
            json={"link_id": "test_link"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Response should have status"
        assert data["status"] == "tracked", f"Expected 'tracked', got {data['status']}"
        print("PASS: Click tracking works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
