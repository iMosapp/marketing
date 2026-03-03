"""
Test link click tracking and stats endpoint for the Relationship Management System.
Tests:
1. GET /api/contacts/{user_id}/{contact_id}/stats returns link_clicks field
2. GET /api/s/{short_code} redirects properly (302)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://engagement-hub-69.preview.emergentagent.com').rstrip('/')

# Test credentials from review_request
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"


class TestContactStatsLinkClicks:
    """Test that contact stats endpoint returns link_clicks field"""

    def test_contact_stats_returns_link_clicks_field(self):
        """GET /api/contacts/{user_id}/{contact_id}/stats should include link_clicks"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/stats")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertion - verify link_clicks field exists and is a number
        data = response.json()
        assert "link_clicks" in data, f"link_clicks field missing from stats response: {data.keys()}"
        assert isinstance(data["link_clicks"], int), f"link_clicks should be an integer, got {type(data['link_clicks'])}"
        
        # Verify other expected stats fields are present
        expected_fields = ["total_touchpoints", "messages_sent", "campaigns", "cards_sent", "broadcasts", "custom_events"]
        for field in expected_fields:
            assert field in data, f"Expected field {field} missing from stats"
        
        print(f"[PASS] Contact stats returned link_clicks: {data['link_clicks']}")
        print(f"[INFO] Full stats: {data}")


class TestShortURLRedirect:
    """Test that short URL redirect works correctly"""

    def test_short_url_create_and_redirect(self):
        """Test creating a short URL and verifying redirect (302)"""
        # First create a short URL
        create_payload = {
            "original_url": "https://example.com/test-page",
            "link_type": "test",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID
        }
        
        create_response = requests.post(f"{BASE_URL}/api/s/create", json=create_payload)
        
        # Should succeed
        assert create_response.status_code == 200, f"Failed to create short URL: {create_response.text}"
        
        data = create_response.json()
        assert "short_code" in data, "short_code missing from response"
        assert "short_url" in data, "short_url missing from response"
        
        short_code = data["short_code"]
        print(f"[INFO] Created short URL with code: {short_code}")
        
        # Now test the redirect - disable follow_redirects to capture 302
        redirect_response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False
        )
        
        # Should return 302 redirect
        assert redirect_response.status_code == 302, f"Expected 302 redirect, got {redirect_response.status_code}"
        
        # Verify Location header points to original URL
        location = redirect_response.headers.get("Location", "")
        assert "example.com/test-page" in location, f"Redirect location incorrect: {location}"
        
        print(f"[PASS] Short URL redirect works: {short_code} -> {location}")

    def test_short_url_invalid_code_404(self):
        """Test that invalid short codes return 404"""
        response = requests.get(
            f"{BASE_URL}/api/s/invalid_code_xyz123",
            allow_redirects=False
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid code, got {response.status_code}"
        print("[PASS] Invalid short code returns 404")


class TestShortURLClickEventTypes:
    """Test the event type detection for different link types"""

    def test_business_card_short_url(self):
        """Test short URL for business card link type"""
        create_payload = {
            "original_url": "https://app.imosapp.com/p/user123",
            "link_type": "business_card",
            "user_id": USER_ID,
        }
        
        response = requests.post(f"{BASE_URL}/api/s/create", json=create_payload)
        assert response.status_code == 200
        
        data = response.json()
        print(f"[PASS] Business card short URL created: {data['short_code']}")

    def test_review_page_short_url(self):
        """Test short URL for review page link type"""
        create_payload = {
            "original_url": "https://app.imosapp.com/review/store123",
            "link_type": "review",
            "user_id": USER_ID,
        }
        
        response = requests.post(f"{BASE_URL}/api/s/create", json=create_payload)
        assert response.status_code == 200
        
        data = response.json()
        print(f"[PASS] Review page short URL created: {data['short_code']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
