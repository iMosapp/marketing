"""
Test suite for Public Review Page features (Podium-style landing page)
- Review page data endpoint
- Click tracking
- Click statistics
- Forgot password (no dev_code leak)
- Debug endpoint removed
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_STORE_SLUG = "imos-demo"
TEST_STORE_ID = "69a0b7095fddcede09591668"
TEST_USER_EMAIL = "forest@imosapp.com"


class TestHealthAndBasicEndpoints:
    """Test basic API health and removed endpoints"""
    
    def test_api_health(self):
        """API health endpoint should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("PASS: Health endpoint working")
    
    def test_debug_endpoint_removed(self):
        """Debug/db-info endpoint should be removed (404)"""
        response = requests.get(f"{BASE_URL}/api/debug/db-info")
        assert response.status_code == 404
        print("PASS: Debug endpoint correctly removed")


class TestPublicReviewPageAPI:
    """Test the public review page data endpoint"""
    
    def test_get_review_page_data(self):
        """GET /api/review/page/{store_slug} should return store data with review links"""
        response = requests.get(f"{BASE_URL}/api/review/page/{TEST_STORE_SLUG}")
        assert response.status_code == 200
        data = response.json()
        
        # Validate store data
        assert "store" in data
        store = data["store"]
        assert store["id"] == TEST_STORE_ID
        assert store["name"] == "i'M On Social Demo Dealership"
        assert store["slug"] == TEST_STORE_SLUG
        assert "logo_url" in store
        assert "phone" in store
        assert "address" in store
        assert "city" in store
        assert "state" in store
        assert "website" in store
        
        # Validate brand_kit
        assert "brand_kit" in data
        brand_kit = data["brand_kit"]
        assert "company_name" in brand_kit
        assert "primary_color" in brand_kit
        
        # Validate review_links
        assert "review_links" in data
        review_links = data["review_links"]
        assert "google" in review_links
        assert "yelp" in review_links
        assert "facebook" in review_links
        assert "dealerrater" in review_links
        assert "custom" in review_links
        
        # Validate custom links array
        custom_links = review_links.get("custom", [])
        assert isinstance(custom_links, list)
        
        print("PASS: Review page data returned correctly with all expected fields")
    
    def test_get_review_page_nonexistent_store(self):
        """GET /api/review/page/{invalid_slug} should return 404"""
        response = requests.get(f"{BASE_URL}/api/review/page/nonexistent-store-xyz")
        assert response.status_code == 404
        print("PASS: Nonexistent store returns 404")
    
    def test_get_review_page_with_salesperson(self):
        """GET /api/review/page/{store_slug}?sp={id} should include salesperson info"""
        response = requests.get(f"{BASE_URL}/api/review/page/{TEST_STORE_SLUG}?sp=invalid_id")
        assert response.status_code == 200
        data = response.json()
        # salesperson field should be present even if ID is invalid
        assert "salesperson" in data
        print("PASS: Review page handles salesperson parameter")


class TestClickTracking:
    """Test click tracking functionality"""
    
    def test_track_click_success(self):
        """POST /api/review/track-click/{store_slug} should track clicks"""
        payload = {
            "platform": "google",
            "url": "https://g.page/r/example/review",
            "salesperson_id": None
        }
        response = requests.post(
            f"{BASE_URL}/api/review/track-click/{TEST_STORE_SLUG}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("PASS: Click tracked successfully")
    
    def test_track_click_different_platforms(self):
        """Track clicks for different platforms"""
        platforms = ["google", "yelp", "facebook", "dealerrater"]
        
        for platform in platforms:
            payload = {
                "platform": platform,
                "url": f"https://example.com/{platform}/review"
            }
            response = requests.post(
                f"{BASE_URL}/api/review/track-click/{TEST_STORE_SLUG}",
                json=payload
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
        
        print(f"PASS: All {len(platforms)} platform clicks tracked")
    
    def test_track_click_with_salesperson(self):
        """Track click with salesperson ID"""
        payload = {
            "platform": "google",
            "url": "https://g.page/r/example/review",
            "salesperson_id": "507f1f77bcf86cd799439011"  # Example ObjectId
        }
        response = requests.post(
            f"{BASE_URL}/api/review/track-click/{TEST_STORE_SLUG}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("PASS: Click with salesperson tracked")
    
    def test_track_click_invalid_store(self):
        """Track click for nonexistent store should return 404"""
        payload = {
            "platform": "google",
            "url": "https://example.com"
        }
        response = requests.post(
            f"{BASE_URL}/api/review/track-click/nonexistent-store-xyz",
            json=payload
        )
        assert response.status_code == 404
        print("PASS: Invalid store returns 404")


class TestClickStatistics:
    """Test click statistics endpoint"""
    
    def test_get_click_stats(self):
        """GET /api/review/click-stats/{store_id} should return statistics"""
        response = requests.get(f"{BASE_URL}/api/review/click-stats/{TEST_STORE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "store_totals" in data
        assert "detailed" in data
        
        # store_totals should have counts
        store_totals = data["store_totals"]
        assert isinstance(store_totals, dict)
        
        # detailed should be a list
        detailed = data["detailed"]
        assert isinstance(detailed, list)
        
        # Each detailed item should have platform and count
        if detailed:
            for item in detailed:
                assert "platform" in item
                assert "count" in item
        
        print("PASS: Click statistics returned correctly")


class TestForgotPasswordSecurity:
    """Test forgot password endpoint security (no dev_code leak)"""
    
    def test_forgot_password_no_dev_code(self):
        """POST /api/auth/forgot-password/request should NOT return dev_code"""
        payload = {"email": TEST_USER_EMAIL}
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password/request",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should only contain generic message
        assert "message" in data
        
        # Should NOT contain dev_code or code
        assert "dev_code" not in data
        assert "code" not in data
        
        print("PASS: Forgot password does NOT leak dev_code")
    
    def test_forgot_password_generic_response(self):
        """Forgot password should return generic message for non-existent email"""
        payload = {"email": "nonexistent@example.com"}
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password/request",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return same generic message regardless of email existence
        assert "message" in data
        assert "dev_code" not in data
        
        print("PASS: Forgot password returns generic response for security")


class TestCustomReviewLinks:
    """Test custom review links functionality"""
    
    def test_custom_links_in_review_data(self):
        """Custom links should be included in review page data"""
        response = requests.get(f"{BASE_URL}/api/review/page/{TEST_STORE_SLUG}")
        assert response.status_code == 200
        data = response.json()
        
        review_links = data.get("review_links", {})
        custom_links = review_links.get("custom", [])
        
        # Verify custom links structure
        assert isinstance(custom_links, list)
        
        # If there are custom links, validate their structure
        for link in custom_links:
            assert "name" in link
            assert "url" in link
        
        print(f"PASS: Custom links ({len(custom_links)}) validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
