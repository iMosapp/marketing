"""
Tests for Congrats Cards API
- POST /api/congrats/create - creates new congrats card
- GET /api/congrats/card/{card_id} - returns card data
- GET /api/congrats/template/{store_id} - returns default template
- POST /api/congrats/card/{card_id}/track - tracks downloads/shares
- GET /api/congrats/history/{salesman_id} - gets card history
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://integration-hub-54.preview.emergentagent.com').rstrip('/')
SALESMAN_ID = "699907444a076891982fab35"  # Super Admin user ID from test credentials

# Test card ID that was pre-created by main agent
EXISTING_CARD_ID = "6a304660-0e5"


class TestCongratsTemplates:
    """Test template endpoint"""
    
    def test_get_default_template(self):
        """GET /api/congrats/template/{store_id} returns default template for non-existent store"""
        response = requests.get(f"{BASE_URL}/api/congrats/template/nonexistent_store_123")
        print(f"Template response status: {response.status_code}")
        print(f"Template response: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return default template
        assert data["exists"] == False
        assert "template" in data
        template = data["template"]
        assert template["headline"] == "Thank You!"
        assert "message" in template
        assert "background_color" in template
        assert "accent_color" in template
        assert "text_color" in template


class TestCongratsCardRetrieval:
    """Test card retrieval endpoint"""
    
    def test_get_existing_card(self):
        """GET /api/congrats/card/{card_id} returns existing card data"""
        response = requests.get(f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}")
        print(f"Get card response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Card data: {data.keys()}")
            
            # Verify card structure
            assert "card_id" in data
            assert data["card_id"] == EXISTING_CARD_ID
            assert "customer_name" in data
            assert "customer_photo" in data
            assert "headline" in data
            assert "message" in data
            assert "style" in data
            assert "background_color" in data["style"]
            assert "accent_color" in data["style"]
            assert "text_color" in data["style"]
            
            # Salesman info might be present
            if data.get("salesman"):
                assert "name" in data["salesman"]
            
            print("Card retrieval test PASSED")
        else:
            # Card may not exist if it was cleaned up
            print(f"Card not found (may be expected): {response.json()}")
            pytest.skip("Pre-created test card not found")
    
    def test_get_nonexistent_card(self):
        """GET /api/congrats/card/{card_id} returns 404 for non-existent card"""
        response = requests.get(f"{BASE_URL}/api/congrats/card/nonexistent_card_xyz")
        print(f"Get nonexistent card response status: {response.status_code}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print("Non-existent card returns 404 - PASSED")


class TestCongratsCardCreation:
    """Test card creation endpoint"""
    
    def test_create_congrats_card(self):
        """POST /api/congrats/create creates a new congrats card"""
        # Create a small test image (1x1 pixel PNG)
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        test_image_bytes = base64.b64decode(test_image_base64)
        
        files = {
            'photo': ('test_photo.png', test_image_bytes, 'image/png')
        }
        data = {
            'salesman_id': SALESMAN_ID,
            'customer_name': 'TEST_John Doe',
            'customer_phone': '+15551234567',
            'custom_message': 'TEST: Thank you for your business!'
        }
        
        response = requests.post(f"{BASE_URL}/api/congrats/create", files=files, data=data)
        print(f"Create card response status: {response.status_code}")
        print(f"Create card response: {response.json()}")
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] == True
        assert "card_id" in result
        assert len(result["card_id"]) > 0
        assert result["message"] == "Congrats card created!"
        
        # Store card_id for cleanup and verification
        created_card_id = result["card_id"]
        print(f"Created card ID: {created_card_id}")
        
        # Verify the card can be retrieved
        verify_response = requests.get(f"{BASE_URL}/api/congrats/card/{created_card_id}")
        print(f"Verify card response status: {verify_response.status_code}")
        
        assert verify_response.status_code == 200
        card_data = verify_response.json()
        
        assert card_data["customer_name"] == "TEST_John Doe"
        assert "customer_photo" in card_data
        assert card_data["custom_message"] == "TEST: Thank you for your business!"
        
        print("Card creation and verification PASSED")
        
        return created_card_id
    
    def test_create_card_without_photo(self):
        """POST /api/congrats/create fails without photo"""
        data = {
            'salesman_id': SALESMAN_ID,
            'customer_name': 'TEST_No Photo',
        }
        
        response = requests.post(f"{BASE_URL}/api/congrats/create", data=data)
        print(f"Create card without photo response status: {response.status_code}")
        
        # Should fail - photo is required
        assert response.status_code == 422  # Unprocessable Entity
        print("Card creation without photo correctly rejected - PASSED")
    
    def test_create_card_invalid_salesman(self):
        """POST /api/congrats/create fails with invalid salesman_id"""
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        test_image_bytes = base64.b64decode(test_image_base64)
        
        files = {
            'photo': ('test_photo.png', test_image_bytes, 'image/png')
        }
        data = {
            'salesman_id': 'invalid_id_xyz',
            'customer_name': 'TEST_Invalid Salesman',
        }
        
        response = requests.post(f"{BASE_URL}/api/congrats/create", files=files, data=data)
        print(f"Create card invalid salesman response status: {response.status_code}")
        
        # Should fail - invalid salesman
        assert response.status_code == 404
        print("Card creation with invalid salesman correctly rejected - PASSED")


class TestCongratsCardTracking:
    """Test card tracking endpoint"""
    
    def test_track_download(self):
        """POST /api/congrats/card/{card_id}/track tracks download action"""
        # First verify the card exists
        card_response = requests.get(f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}")
        if card_response.status_code != 200:
            pytest.skip("Pre-created test card not found")
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}/track",
            json={"action": "download"}
        )
        print(f"Track download response status: {response.status_code}")
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        print("Download tracking PASSED")
    
    def test_track_share(self):
        """POST /api/congrats/card/{card_id}/track tracks share action"""
        card_response = requests.get(f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}")
        if card_response.status_code != 200:
            pytest.skip("Pre-created test card not found")
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}/track",
            json={"action": "share"}
        )
        print(f"Track share response status: {response.status_code}")
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        print("Share tracking PASSED")
    
    def test_track_invalid_action(self):
        """POST /api/congrats/card/{card_id}/track rejects invalid action"""
        card_response = requests.get(f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}")
        if card_response.status_code != 200:
            pytest.skip("Pre-created test card not found")
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/card/{EXISTING_CARD_ID}/track",
            json={"action": "invalid_action"}
        )
        print(f"Track invalid action response status: {response.status_code}")
        
        assert response.status_code == 400
        print("Invalid action correctly rejected - PASSED")


class TestCongratsCardHistory:
    """Test card history endpoint"""
    
    def test_get_card_history(self):
        """GET /api/congrats/history/{salesman_id} returns card history"""
        response = requests.get(f"{BASE_URL}/api/congrats/history/{SALESMAN_ID}")
        print(f"Card history response status: {response.status_code}")
        print(f"Card history response: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list)
        
        # If there are cards, verify structure
        if len(data) > 0:
            card = data[0]
            assert "card_id" in card
            assert "customer_name" in card
            assert "views" in card
            assert "downloads" in card
            assert "shares" in card
            print(f"Found {len(data)} cards in history")
        else:
            print("No cards in history (may be expected for new user)")
        
        print("Card history retrieval PASSED")


# Cleanup function to remove test data
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_cards():
    """Cleanup TEST_ prefixed cards after test module completes"""
    yield
    # Note: No direct delete endpoint exists, so we can't clean up
    # Test cards are prefixed with TEST_ for identification
    print("Test cleanup complete - TEST_ prefixed cards remain in DB for manual cleanup if needed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
