"""
Test suite for Inbox loading and Photo URL fixes
- Inbox conversations API returns data correctly
- Image upload returns relative URLs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConversationsAPI:
    """Test GET /api/messages/conversations/{user_id} returns data correctly"""
    
    def test_conversations_returns_list(self):
        """Verify conversations endpoint returns a list"""
        user_id = "69a0b7095fddcede09591667"
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{user_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Got {len(data)} conversations")
    
    def test_conversation_has_required_fields(self):
        """Verify each conversation has required fields"""
        user_id = "69a0b7095fddcede09591667"
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{user_id}")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            conv = data[0]
            # Check essential fields
            assert "_id" in conv, "Conversation should have _id"
            assert "user_id" in conv, "Conversation should have user_id"
            assert "contact" in conv or "contact_name" in conv, "Conversation should have contact info"
            print(f"First conversation: {conv.get('_id')}, contact: {conv.get('contact', {}).get('name')}")


class TestImageUploadAPI:
    """Test POST /api/images/upload returns relative URLs"""
    
    def test_image_upload_returns_relative_url(self):
        """Verify image upload returns URLs starting with /api/images/"""
        # Create a minimal valid PNG image (1x1 pixel)
        import base64
        png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        png_bytes = base64.b64decode(png_base64)
        
        files = {"file": ("test.png", png_bytes, "image/png")}
        response = requests.post(f"{BASE_URL}/api/images/upload", files=files)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify relative URLs are returned
        original_url = data.get("original_url", "")
        assert original_url.startswith("/api/images/"), f"URL should start with /api/images/, got: {original_url}"
        print(f"Image upload returned relative URL: {original_url}")
    
    def test_upload_returns_thumbnail_and_avatar(self):
        """Verify image upload returns thumbnail and avatar URLs"""
        import base64
        png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        png_bytes = base64.b64decode(png_base64)
        
        files = {"file": ("test2.png", png_bytes, "image/png")}
        response = requests.post(f"{BASE_URL}/api/images/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected fields
        assert "original_url" in data, "Should have original_url"
        assert "thumbnail_url" in data, "Should have thumbnail_url"
        assert "avatar_url" in data, "Should have avatar_url"
        assert "file_id" in data, "Should have file_id"
        
        # All URLs should be relative
        for field in ["original_url", "thumbnail_url", "avatar_url"]:
            url = data.get(field, "")
            assert url.startswith("/api/images/"), f"{field} should be relative, got: {url}"
        
        print(f"Upload returned: original={data['original_url']}, thumb={data['thumbnail_url']}")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("API is healthy")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
