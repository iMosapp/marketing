"""
Birthday Card Manual Creation Tests
Tests the POST /api/birthday/create-manual and GET /api/birthday/card/{card_id} endpoints.
Feature: Clone of Congrats Card flow for Birthday Cards with photo upload, share options.
"""
import pytest
import requests
import os
import io
import base64
from PIL import Image

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials - Super Admin
TEST_EMAIL = "forest@imonsocial.com"
TEST_PASSWORD = "Admin123!"


class TestBirthdayCardManualCreation:
    """Tests for birthday card manual creation with photo upload"""
    
    @pytest.fixture(scope="class")
    def auth_token_and_user_id(self):
        """Login and get auth token + user ID"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
        data = response.json()
        token = data.get("token") or data.get("access_token")
        user = data.get("user", {})
        user_id = user.get("_id") or user.get("id")
        if not token or not user_id:
            pytest.skip("Could not get token or user_id from login response")
        return token, user_id
    
    @pytest.fixture(scope="class")
    def test_image_bytes(self):
        """Create a test image for upload"""
        img = Image.new('RGB', (200, 200), color='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()
    
    def test_create_birthday_card_manual_success(self, auth_token_and_user_id, test_image_bytes):
        """Test POST /api/birthday/create-manual with valid data"""
        token, user_id = auth_token_and_user_id
        
        files = {
            'photo': ('test_photo.png', test_image_bytes, 'image/png')
        }
        data = {
            'salesman_id': user_id,
            'customer_name': 'TEST_Birthday Test Customer',
            'customer_phone': '+15551234567',
            'custom_message': 'Happy Birthday! Have a great day!'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/birthday/create-manual",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Create birthday card response: {response.status_code}")
        print(f"Response body: {response.text[:500] if response.text else 'empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get("success") == True, "Expected success=True"
        assert "card_id" in result, "Response should contain card_id"
        assert len(result["card_id"]) > 0, "card_id should not be empty"
        
        # Store card_id for subsequent tests
        self.__class__.created_card_id = result["card_id"]
        print(f"Created birthday card with ID: {result['card_id']}")
        
        # Verify card_url and short_url are returned
        assert "card_url" in result or "short_url" in result, "Response should contain card_url or short_url"
    
    def test_get_birthday_card_data(self, auth_token_and_user_id):
        """Test GET /api/birthday/card/{card_id} returns correct data"""
        card_id = getattr(self.__class__, 'created_card_id', None)
        if not card_id:
            pytest.skip("No card_id from previous test")
        
        token, _ = auth_token_and_user_id
        
        response = requests.get(
            f"{BASE_URL}/api/birthday/card/{card_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Get birthday card response: {response.status_code}")
        print(f"Response body: {response.text[:500] if response.text else 'empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        
        # Verify card data fields
        assert result.get("card_id") == card_id, "card_id should match"
        assert result.get("card_type") == "birthday", "card_type should be 'birthday'"
        assert "customer_name" in result, "Response should contain customer_name"
        assert "TEST_Birthday" in result.get("customer_name", ""), "Customer name should contain TEST_ prefix"
        assert "customer_photo" in result, "Response should contain customer_photo"
        assert "headline" in result, "Response should contain headline"
        assert "Happy Birthday" in result.get("headline", ""), "Headline should contain 'Happy Birthday'"
        assert "message" in result, "Response should contain message"
        assert "custom_message" in result, "Response should contain custom_message"
        assert "style" in result, "Response should contain style object"
        
        # Verify style colors
        style = result.get("style", {})
        assert "background_color" in style, "Style should have background_color"
        assert "accent_color" in style, "Style should have accent_color"
        assert "text_color" in style, "Style should have text_color"
    
    def test_get_birthday_card_not_found(self, auth_token_and_user_id):
        """Test GET /api/birthday/card/{card_id} with invalid card_id returns 404"""
        token, _ = auth_token_and_user_id
        
        response = requests.get(
            f"{BASE_URL}/api/birthday/card/nonexistent_card_12345",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Get nonexistent card response: {response.status_code}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_create_birthday_card_missing_photo(self, auth_token_and_user_id):
        """Test POST /api/birthday/create-manual without photo returns error"""
        token, user_id = auth_token_and_user_id
        
        data = {
            'salesman_id': user_id,
            'customer_name': 'TEST_No Photo Customer',
            'customer_phone': '+15559876543'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/birthday/create-manual",
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Create without photo response: {response.status_code}")
        
        # Should fail because photo is required
        assert response.status_code == 422 or response.status_code == 400, \
            f"Expected 422 or 400 for missing photo, got {response.status_code}"
    
    def test_create_birthday_card_missing_name(self, auth_token_and_user_id, test_image_bytes):
        """Test POST /api/birthday/create-manual without customer_name returns error"""
        token, user_id = auth_token_and_user_id
        
        files = {
            'photo': ('test_photo.png', test_image_bytes, 'image/png')
        }
        data = {
            'salesman_id': user_id,
            'customer_phone': '+15551112222'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/birthday/create-manual",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Create without name response: {response.status_code}")
        
        # Should fail because customer_name is required
        assert response.status_code == 422 or response.status_code == 400, \
            f"Expected 422 or 400 for missing name, got {response.status_code}"
    
    def test_birthday_card_image_endpoint(self, auth_token_and_user_id):
        """Test GET /api/birthday/card/{card_id}/image returns PNG image"""
        card_id = getattr(self.__class__, 'created_card_id', None)
        if not card_id:
            pytest.skip("No card_id from previous test")
        
        token, _ = auth_token_and_user_id
        
        response = requests.get(
            f"{BASE_URL}/api/birthday/card/{card_id}/image",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Get card image response: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "image/png" in response.headers.get("Content-Type", ""), "Should return PNG image"
        assert len(response.content) > 1000, "Image content should be substantial"
    
    def test_birthday_card_track_action(self, auth_token_and_user_id):
        """Test POST /api/birthday/card/{card_id}/track with valid action"""
        card_id = getattr(self.__class__, 'created_card_id', None)
        if not card_id:
            pytest.skip("No card_id from previous test")
        
        token, _ = auth_token_and_user_id
        
        response = requests.post(
            f"{BASE_URL}/api/birthday/card/{card_id}/track",
            json={"action": "share"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Track action response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        result = response.json()
        assert result.get("success") == True, "Expected success=True"
    
    def test_birthday_card_history(self, auth_token_and_user_id):
        """Test GET /api/birthday/history/{salesman_id} returns card list"""
        token, user_id = auth_token_and_user_id
        
        response = requests.get(
            f"{BASE_URL}/api/birthday/history/{user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Get history response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        result = response.json()
        assert isinstance(result, list), "History should return a list"
        
        # Verify our test card is in the history
        card_id = getattr(self.__class__, 'created_card_id', None)
        if card_id:
            card_ids = [c.get("card_id") for c in result]
            assert card_id in card_ids, f"Created card {card_id} should be in history"


class TestBirthdayCardPublicAccess:
    """Test public access to birthday cards (no auth required for GET /api/birthday/card/{card_id})"""
    
    def test_public_card_access_no_auth(self):
        """Test that birthday card can be viewed without authentication"""
        # First login to create a card
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code != 200:
            pytest.skip("Could not login to create test card")
        
        data = login_response.json()
        token = data.get("token") or data.get("access_token")
        user = data.get("user", {})
        user_id = user.get("_id") or user.get("id")
        
        # Create a card
        img = Image.new('RGB', (100, 100), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        files = {'photo': ('test.png', buf.getvalue(), 'image/png')}
        form_data = {
            'salesman_id': user_id,
            'customer_name': 'TEST_Public Access User'
        }
        
        create_resp = requests.post(
            f"{BASE_URL}/api/birthday/create-manual",
            files=files,
            data=form_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if create_resp.status_code != 200:
            pytest.skip(f"Could not create test card: {create_resp.text}")
        
        card_id = create_resp.json().get("card_id")
        
        # Now try to access without auth
        public_response = requests.get(f"{BASE_URL}/api/birthday/card/{card_id}")
        
        print(f"Public access response: {public_response.status_code}")
        
        assert public_response.status_code == 200, \
            f"Birthday card should be publicly accessible, got {public_response.status_code}"
        
        result = public_response.json()
        assert result.get("card_id") == card_id, "card_id should match"
        assert result.get("customer_name") == "TEST_Public Access User", "customer_name should match"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
