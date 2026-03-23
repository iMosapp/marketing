"""
Test Showcase Approvals and Contact Photo Delete functionality
Tests for:
1. GET /api/showcase/pending/{user_id} - returns entries with relative customer_photo URLs
2. GET /api/showcase/user/{user_id} - returns showcase entries with photo URLs
3. DELETE /api/contacts/{user_id}/{contact_id}/photos - validation tests
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"
USER_ID = "69a0b7095fddcede09591667"


class TestShowcasePendingEndpoint:
    """Tests for GET /api/showcase/pending/{user_id}"""
    
    def test_pending_endpoint_returns_200(self):
        """Test that pending endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/showcase/pending/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/showcase/pending/{USER_ID} returns 200")
    
    def test_pending_endpoint_returns_list(self):
        """Test that pending endpoint returns a list"""
        response = requests.get(f"{BASE_URL}/api/showcase/pending/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Pending endpoint returns list with {len(data)} entries")
    
    def test_pending_entries_have_required_fields(self):
        """Test that pending entries have required fields"""
        response = requests.get(f"{BASE_URL}/api/showcase/pending/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            entry = data[0]
            required_fields = ['card_id', 'customer_name', 'created_at']
            for field in required_fields:
                assert field in entry, f"Missing required field: {field}"
            print(f"✓ Pending entries have required fields: {required_fields}")
        else:
            print("⚠ No pending entries to validate fields")
    
    def test_pending_entries_have_relative_photo_urls(self):
        """Test that customer_photo URLs are relative (start with /api/)"""
        response = requests.get(f"{BASE_URL}/api/showcase/pending/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        entries_with_photos = [e for e in data if e.get('customer_photo')]
        print(f"Found {len(entries_with_photos)} entries with customer_photo out of {len(data)} total")
        
        for entry in entries_with_photos:
            photo_url = entry.get('customer_photo', '')
            # Photo URL should be relative (start with /api/) or be None
            assert photo_url.startswith('/api/'), f"Photo URL should be relative, got: {photo_url}"
        
        if entries_with_photos:
            print(f"✓ All {len(entries_with_photos)} photo URLs are relative (start with /api/)")
        else:
            print("⚠ No entries with customer_photo to validate URL format")


class TestShowcaseUserEndpoint:
    """Tests for GET /api/showcase/user/{user_id}"""
    
    def test_user_showcase_returns_200(self):
        """Test that user showcase endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/showcase/user/{USER_ID} returns 200")
    
    def test_user_showcase_has_entries(self):
        """Test that user showcase has entries array"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert 'entries' in data, "Response should have 'entries' field"
        assert isinstance(data['entries'], list), "entries should be a list"
        print(f"✓ User showcase has {len(data['entries'])} entries")
    
    def test_user_showcase_entries_have_photo_urls(self):
        """Test that showcase entries have relative photo URLs"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        entries_with_photos = [e for e in data.get('entries', []) if e.get('customer_photo')]
        
        for entry in entries_with_photos:
            photo_url = entry.get('customer_photo', '')
            # Photo URL should be relative (start with /api/) or be None
            assert photo_url.startswith('/api/'), f"Photo URL should be relative, got: {photo_url}"
        
        if entries_with_photos:
            print(f"✓ All {len(entries_with_photos)} showcase photo URLs are relative")
        else:
            print("⚠ No showcase entries with customer_photo to validate")


class TestContactPhotoDeleteEndpoint:
    """Tests for DELETE /api/contacts/{user_id}/{contact_id}/photos"""
    
    def test_delete_photo_requires_photo_url(self):
        """Test that DELETE returns 400 if photo_url is missing"""
        # Use a test contact ID
        contact_id = "69a1354f2c0649ac6fb7f3f1"
        
        response = requests.delete(
            f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}/photos",
            json={"photo_type": "profile"}  # Missing photo_url
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ DELETE /api/contacts/.../photos returns 400 when photo_url is missing")
    
    def test_delete_photo_requires_valid_photo_type(self):
        """Test that DELETE returns 400 if photo_type is invalid"""
        contact_id = "69a1354f2c0649ac6fb7f3f1"
        
        response = requests.delete(
            f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}/photos",
            json={"photo_url": "/api/images/test.webp", "photo_type": "invalid_type"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ DELETE /api/contacts/.../photos returns 400 for invalid photo_type")
    
    def test_delete_photo_accepts_valid_types(self):
        """Test that DELETE accepts valid photo_type values"""
        contact_id = "69a1354f2c0649ac6fb7f3f1"
        valid_types = ["profile", "history", "congrats", "birthday"]
        
        for photo_type in valid_types:
            response = requests.delete(
                f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}/photos",
                json={"photo_url": "/api/images/nonexistent.webp", "photo_type": photo_type}
            )
            # Should not return 400 for valid types (may return 200 or 404 depending on photo existence)
            assert response.status_code != 400, f"Should accept photo_type={photo_type}, got 400"
        
        print(f"✓ DELETE endpoint accepts valid photo_types: {valid_types}")


class TestShowcaseApproveRejectEndpoints:
    """Tests for approve/reject showcase entries"""
    
    def test_approve_endpoint_exists(self):
        """Test that approve endpoint exists"""
        # Use a fake card_id - we just want to verify the endpoint exists
        response = requests.post(f"{BASE_URL}/api/showcase/entry/fake_card_id/approve")
        # Should return 404 (card not found) not 405 (method not allowed)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print("✓ POST /api/showcase/entry/{card_id}/approve endpoint exists")
    
    def test_reject_endpoint_exists(self):
        """Test that reject endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/showcase/entry/fake_card_id/reject")
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print("✓ POST /api/showcase/entry/{card_id}/reject endpoint exists")


class TestShowcasePhotoEndpoint:
    """Tests for showcase photo serving endpoint"""
    
    def test_photo_endpoint_exists(self):
        """Test that photo endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/showcase/photo/fake_card_id")
        # Should return 404 (photo not found) not 405 (method not allowed)
        assert response.status_code in [200, 301, 404], f"Expected 200, 301, or 404, got {response.status_code}"
        print("✓ GET /api/showcase/photo/{card_id} endpoint exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
