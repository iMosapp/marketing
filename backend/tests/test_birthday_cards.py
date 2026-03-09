"""
Test Birthday Card API endpoints
Testing:
- GET /api/birthday/card/{card_id} - Get birthday card data
- POST /api/birthday/card/{card_id}/track - Track card actions (share/download)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://rms-polish.preview.emergentagent.com"

TEST_CARD_ID = "3ffea59c-c37"


class TestBirthdayCardAPI:
    """Birthday Card API tests"""
    
    def test_get_birthday_card_success(self):
        """Test getting birthday card data - returns valid card"""
        response = requests.get(f"{BASE_URL}/api/birthday/card/{TEST_CARD_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # Verify required fields
        assert "card_id" in data
        assert data["card_id"] == TEST_CARD_ID
        assert "card_type" in data
        assert data["card_type"] == "birthday"
        assert "customer_name" in data
        assert "headline" in data
        assert "message" in data
        assert "salesman" in data
        assert "style" in data
        
        # Verify style object
        style = data["style"]
        assert "background_color" in style
        assert "accent_color" in style
        assert "text_color" in style
        
        print(f"SUCCESS: Birthday card retrieved - customer: {data['customer_name']}")
    
    def test_get_birthday_card_not_found(self):
        """Test getting non-existent birthday card"""
        response = requests.get(f"{BASE_URL}/api/birthday/card/nonexistent-card-id")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        print("SUCCESS: Non-existent card returns 404")
    
    def test_birthday_card_track_share(self):
        """Test tracking share action on birthday card"""
        response = requests.post(
            f"{BASE_URL}/api/birthday/card/{TEST_CARD_ID}/track",
            json={"action": "share"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        print("SUCCESS: Share action tracked")
    
    def test_birthday_card_track_download(self):
        """Test tracking download action on birthday card"""
        response = requests.post(
            f"{BASE_URL}/api/birthday/card/{TEST_CARD_ID}/track",
            json={"action": "download"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        print("SUCCESS: Download action tracked")
    
    def test_birthday_card_track_invalid_action(self):
        """Test tracking invalid action returns error"""
        response = requests.post(
            f"{BASE_URL}/api/birthday/card/{TEST_CARD_ID}/track",
            json={"action": "invalid"}
        )
        assert response.status_code == 400
        print("SUCCESS: Invalid action returns 400")
    
    def test_birthday_card_image_endpoint(self):
        """Test birthday card image generation endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/birthday/card/{TEST_CARD_ID}/image",
            stream=True
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "image/png"
        print("SUCCESS: Birthday card image endpoint returns PNG")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
