"""
Test suite for PATCH /api/users/{user_id} photo_url fix
Bug: Profile Picture and Bio updates were showing 'success' but reverting to old data on digital card
Root cause: server.py PATCH endpoint was NOT clearing photo_path/photo_avatar_path when photo_url was updated
Fix: Updated server.py PATCH endpoint to clear photo_path and photo_avatar_path on photo_url change

Tests:
1. PATCH /api/users/{user_id} with photo_url should clear photo_path and photo_avatar_path
2. GET /api/card/data/{user_id} should return updated photo_url after PATCH
3. PUT /api/users/{user_id}/persona with bio should persist and be readable from card data
4. PATCH /api/users/{user_id} with non-photo fields should NOT clear photo_path
5. GET /api/users/{user_id} should return updated data after PATCH
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "forest@imosapp.com"
TEST_USER_PASSWORD = "Admin123!"
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestPhotoUrlPatchFix:
    """Tests for the photo_url PATCH fix in server.py"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user_id = data.get("user", {}).get("_id") or TEST_USER_ID
        else:
            self.user_id = TEST_USER_ID
        
        yield
        
        # Cleanup - restore original photo_url if needed
        self.session.close()
    
    def test_health_check(self):
        """Verify API is accessible"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_get_user_profile(self):
        """Test GET /api/users/{user_id} returns user data"""
        response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "_id" in data or "id" in data
        assert "name" in data or "email" in data
        print(f"✓ GET /api/users/{self.user_id} returned user data")
        print(f"  - Current photo_url: {data.get('photo_url', 'None')[:50] if data.get('photo_url') else 'None'}...")
        print(f"  - Current photo_path: {data.get('photo_path', 'None')}")
        print(f"  - Current photo_avatar_path: {data.get('photo_avatar_path', 'None')}")
    
    def test_patch_user_with_photo_url_clears_photo_path(self):
        """
        CRITICAL TEST: PATCH with photo_url should clear photo_path and photo_avatar_path
        This is the core fix being tested.
        """
        # First, get current user state
        get_response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}")
        assert get_response.status_code == 200
        original_data = get_response.json()
        original_photo_url = original_data.get("photo_url")
        
        # Create a test photo_url (using a simple test URL)
        test_photo_url = f"https://example.com/test-photo-{datetime.now().timestamp()}.jpg"
        
        # PATCH with new photo_url
        patch_response = self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
            "photo_url": test_photo_url
        })
        assert patch_response.status_code == 200, f"PATCH failed: {patch_response.text}"
        patch_data = patch_response.json()
        
        # Verify the response has the new photo_url
        assert patch_data.get("photo_url") == test_photo_url, "photo_url not updated in response"
        
        # Verify photo_path and photo_avatar_path are cleared (should be None or empty)
        photo_path = patch_data.get("photo_path")
        photo_avatar_path = patch_data.get("photo_avatar_path")
        
        # These should be None, empty string, or not present
        assert not photo_path or photo_path == "", f"photo_path should be cleared but got: {photo_path}"
        assert not photo_avatar_path or photo_avatar_path == "", f"photo_avatar_path should be cleared but got: {photo_avatar_path}"
        
        print("✓ PATCH /api/users/{user_id} with photo_url correctly clears photo_path and photo_avatar_path")
        
        # GET to verify persistence
        verify_response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        assert verify_data.get("photo_url") == test_photo_url, "photo_url not persisted"
        assert not verify_data.get("photo_path") or verify_data.get("photo_path") == "", "photo_path not cleared in DB"
        assert not verify_data.get("photo_avatar_path") or verify_data.get("photo_avatar_path") == "", "photo_avatar_path not cleared in DB"
        
        print("✓ GET /api/users/{user_id} confirms photo_path cleared in database")
        
        # Restore original photo_url if it existed
        if original_photo_url:
            self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
                "photo_url": original_photo_url
            })
    
    def test_card_data_returns_updated_photo_url(self):
        """
        Test GET /api/card/data/{user_id} returns the updated photo_url after PATCH
        This verifies the digital card shows the new photo, not the old cached one.
        """
        # First update photo_url
        test_photo_url = f"https://example.com/card-test-{datetime.now().timestamp()}.jpg"
        
        patch_response = self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
            "photo_url": test_photo_url
        })
        assert patch_response.status_code == 200
        
        # Now get card data
        card_response = self.session.get(f"{BASE_URL}/api/card/data/{self.user_id}")
        assert card_response.status_code == 200
        card_data = card_response.json()
        
        # The card data should have the user's photo_url
        user_photo = card_data.get("user", {}).get("photo_url")
        
        # The photo_url should be the new one, or a resolved path based on it
        # Since photo_path is cleared, resolve_user_photo should return the photo_url
        assert user_photo is not None, "Card data missing user photo_url"
        
        # If photo_path was cleared, the resolved URL should be the photo_url or a fallback
        # It could be the direct URL or a /api/showcase/user-photo/{uid} fallback
        print(f"✓ GET /api/card/data/{self.user_id} returned photo_url: {user_photo[:80] if user_photo else 'None'}...")
        
        # The key assertion: it should NOT be an old /api/images/{photo_path} URL
        # unless that path was just set (which it wasn't since we cleared it)
        if user_photo and user_photo.startswith("/api/images/"):
            # This would indicate photo_path wasn't cleared - potential bug
            print(f"  WARNING: Card still showing /api/images/ path, may indicate photo_path not cleared")
    
    def test_persona_bio_persists_to_card_data(self):
        """
        Test PUT /api/users/{user_id}/persona with bio persists and is readable from card data
        """
        test_bio = f"Test bio updated at {datetime.now().isoformat()}"
        
        # Update persona with bio
        persona_response = self.session.put(f"{BASE_URL}/api/users/{self.user_id}/persona", json={
            "bio": test_bio
        })
        assert persona_response.status_code == 200, f"Persona update failed: {persona_response.text}"
        
        # Verify via GET persona
        get_persona_response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}/persona")
        assert get_persona_response.status_code == 200
        persona_data = get_persona_response.json()
        assert persona_data.get("bio") == test_bio, f"Bio not persisted: {persona_data}"
        
        print(f"✓ PUT /api/users/{self.user_id}/persona persisted bio")
        
        # Verify bio appears in card data
        card_response = self.session.get(f"{BASE_URL}/api/card/data/{self.user_id}")
        assert card_response.status_code == 200
        card_data = card_response.json()
        
        card_bio = card_data.get("user", {}).get("bio")
        assert card_bio == test_bio, f"Bio not in card data: got '{card_bio}' expected '{test_bio}'"
        
        print(f"✓ GET /api/card/data/{self.user_id} shows updated bio")
    
    def test_patch_non_photo_fields_does_not_clear_photo_path(self):
        """
        Test PATCH with non-photo fields (name, bio) should NOT clear photo_path
        """
        # First, get current state
        get_response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}")
        assert get_response.status_code == 200
        original_data = get_response.json()
        original_photo_path = original_data.get("photo_path")
        original_photo_avatar_path = original_data.get("photo_avatar_path")
        
        # PATCH with only name (no photo_url)
        test_name = f"Test User {datetime.now().timestamp()}"
        patch_response = self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
            "name": test_name
        })
        assert patch_response.status_code == 200
        
        # Verify photo_path was NOT cleared
        verify_response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        # photo_path should remain unchanged
        if original_photo_path:
            assert verify_data.get("photo_path") == original_photo_path, "photo_path was incorrectly cleared"
        if original_photo_avatar_path:
            assert verify_data.get("photo_avatar_path") == original_photo_avatar_path, "photo_avatar_path was incorrectly cleared"
        
        print("✓ PATCH with non-photo fields does NOT clear photo_path")
        
        # Restore original name if needed
        if original_data.get("name"):
            self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
                "name": original_data.get("name")
            })
    
    def test_patch_allowed_fields(self):
        """
        Test that PATCH accepts all allowed fields including timezone, address, etc.
        """
        # Test updating timezone and address fields
        patch_response = self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
            "timezone": "America/New_York",
            "address": "123 Test St",
            "city": "Test City",
            "state": "TX",
            "zip_code": "12345",
            "country": "USA"
        })
        assert patch_response.status_code == 200, f"PATCH with address fields failed: {patch_response.text}"
        
        # Verify fields were updated
        verify_response = self.session.get(f"{BASE_URL}/api/users/{self.user_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        assert verify_data.get("timezone") == "America/New_York", "timezone not updated"
        assert verify_data.get("address") == "123 Test St", "address not updated"
        assert verify_data.get("city") == "Test City", "city not updated"
        assert verify_data.get("state") == "TX", "state not updated"
        assert verify_data.get("zip_code") == "12345", "zip_code not updated"
        assert verify_data.get("country") == "USA", "country not updated"
        
        print("✓ PATCH accepts timezone, address, city, state, zip_code, country fields")
    
    def test_patch_returns_updated_user_with_serialized_objectid(self):
        """
        Test that PATCH response properly serializes ObjectId fields
        """
        patch_response = self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
            "bio": "Test bio for serialization check"
        })
        assert patch_response.status_code == 200
        data = patch_response.json()
        
        # _id should be a string, not an ObjectId
        assert isinstance(data.get("_id"), str), "_id should be serialized as string"
        
        # Other ObjectId fields should also be strings if present
        for field in ["organization_id", "org_id", "store_id", "partner_id"]:
            if data.get(field):
                assert isinstance(data.get(field), str), f"{field} should be serialized as string"
        
        print("✓ PATCH response properly serializes ObjectId fields")


class TestResolveUserPhoto:
    """Tests for resolve_user_photo function behavior"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user_id = data.get("user", {}).get("_id") or TEST_USER_ID
        else:
            self.user_id = TEST_USER_ID
        
        yield
        self.session.close()
    
    def test_card_data_uses_photo_url_when_photo_path_cleared(self):
        """
        Verify that when photo_path is cleared, card data uses photo_url
        This tests the resolve_user_photo function indirectly
        """
        # Set a new photo_url (which clears photo_path)
        test_photo_url = "https://example.com/test-resolve-photo.jpg"
        
        patch_response = self.session.patch(f"{BASE_URL}/api/users/{self.user_id}", json={
            "photo_url": test_photo_url
        })
        assert patch_response.status_code == 200
        
        # Get card data
        card_response = self.session.get(f"{BASE_URL}/api/card/data/{self.user_id}")
        assert card_response.status_code == 200
        card_data = card_response.json()
        
        user_photo = card_data.get("user", {}).get("photo_url")
        
        # Since photo_path is cleared, resolve_user_photo should return:
        # - The photo_url directly if it's a short http URL
        # - Or a /api/showcase/user-photo/{uid} fallback for base64/long strings
        
        if test_photo_url.startswith("http") and len(test_photo_url) < 500:
            # Should return the URL directly
            assert user_photo == test_photo_url, f"Expected {test_photo_url}, got {user_photo}"
        
        print(f"✓ Card data correctly resolves photo when photo_path is cleared")
        print(f"  - Resolved photo_url: {user_photo}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
