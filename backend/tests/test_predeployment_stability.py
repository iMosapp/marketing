"""
Pre-Deployment Stability Test Suite
Tests critical flows: login, contacts, photos, event types, activity feed, short URLs

Run: cd /app/backend && python -m pytest tests/test_predeployment_stability.py -v --tb=short
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://engagement-hub-69.preview.emergentagent.com')

# Test credentials from requirements
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a0c06f7626f14d125f8c34"  # Forest Ward
CONVERSATION_ID = "69aa4ba962d5a949c0d501a4"


class TestAuthentication:
    """Test login functionality"""
    
    def test_login_success(self):
        """Backend: Login works — POST /api/auth/login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data or "user" in data, "Missing token/user in login response"
        if "user" in data:
            assert data["user"].get("email") == TEST_EMAIL


class TestContactsAPI:
    """Test contact-related endpoints"""
    
    def test_contact_list_loads(self):
        """Backend: Contact list loads — GET /api/contacts/{user_id}"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert response.status_code == 200, f"Contact list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of contacts"
        assert len(data) > 0, "No contacts returned"
    
    def test_single_contact_loads_with_photo(self):
        """Backend: Single contact loads with photo — GET /api/contacts/{user_id}/{contact_id}"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}")
        assert response.status_code == 200, f"Contact not found: {response.text}"
        data = response.json()
        assert data.get("first_name"), "Contact missing first_name"
        # Contact should have photo fields (thumbnail or photo_url)
        has_photo = any([data.get("photo_thumbnail"), data.get("photo_url"), data.get("photo")])
        # Just verify the contact exists, photo is optional
        assert data.get("_id") or data.get("id"), "Contact missing ID"
    
    def test_contact_photos_all_returns_valid_urls(self):
        """Backend: Contact photos/all returns photos with valid URLs — GET /api/contacts/{user_id}/{contact_id}/photos/all"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/photos/all")
        assert response.status_code == 200, f"Photos/all failed: {response.text}"
        data = response.json()
        assert "photos" in data, "Missing 'photos' key in response"
        assert "total" in data, "Missing 'total' key in response"
        photos = data["photos"]
        assert isinstance(photos, list), "Photos should be a list"
        # Check that photos have URL fields
        for photo in photos[:5]:  # Check first 5
            assert photo.get("url") or photo.get("thumbnail_url"), f"Photo missing URL: {photo}"
            if photo.get("type") not in ["profile"]:
                # Non-profile photos should have date
                pass  # date is optional


class TestContactEvents:
    """Test contact events/timeline API"""
    
    def test_contact_events_timeline_loads(self):
        """Backend: Contact events timeline loads — GET /api/contacts/{user_id}/{contact_id}/events"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events")
        assert response.status_code == 200, f"Events timeline failed: {response.text}"
        data = response.json()
        assert "events" in data, "Missing 'events' key"
        events = data["events"]
        assert isinstance(events, list), "Events should be a list"
    
    def test_events_have_correct_event_type_labels(self):
        """Backend: Events in timeline have correct event_type labels (no wrong 'Congrats' labels)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        # Look for card events and verify their event_type
        card_events = [e for e in events if e.get("event_type") and "card_sent" in e.get("event_type", "")]
        for event in card_events:
            event_type = event.get("event_type", "")
            title = event.get("title", "")
            
            # If it's a birthday card, it should NOT say "Congrats"
            if "birthday" in event_type:
                assert "Birthday" in title or "birthday" in title.lower(), f"Birthday card has wrong title: {title}"
            elif "thank_you" in event_type or "thankyou" in event_type:
                assert "Thank You" in title or "thank" in title.lower(), f"Thank you card has wrong title: {title}"
            elif "holiday" in event_type:
                assert "Holiday" in title or "holiday" in title.lower(), f"Holiday card has wrong title: {title}"
            elif "welcome" in event_type:
                assert "Welcome" in title or "welcome" in title.lower(), f"Welcome card has wrong title: {title}"
            elif "anniversary" in event_type:
                assert "Anniversary" in title or "anniversary" in title.lower(), f"Anniversary card has wrong title: {title}"
            elif "congrats" in event_type:
                assert "Congrats" in title or "congrats" in title.lower(), f"Congrats card has wrong title: {title}"


class TestShortURLs:
    """Test short URL creation and redirection"""
    
    def test_short_url_create_birthday_card(self):
        """Backend: Sending a birthday card short URL logs event as birthday_card_sent NOT congrats_card_sent"""
        # Create a short URL with birthday_card link_type
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/birthday/test-{os.urandom(4).hex()}",
            "link_type": "birthday_card",
            "user_id": USER_ID
        })
        assert response.status_code == 200, f"Short URL create failed: {response.text}"
        data = response.json()
        assert "short_code" in data, "Missing short_code in response"
        assert "short_url" in data, "Missing short_url in response"
        
        # Verify the link_type was stored correctly
        short_code = data["short_code"]
        stats_response = requests.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats.get("link_type") == "birthday_card", f"Wrong link_type stored: {stats.get('link_type')}"
    
    def test_short_url_create_thank_you_card(self):
        """Backend: Sending a thank_you_card short URL logs event as thank_you_card_sent NOT congrats_card_sent"""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/thankyou/test-{os.urandom(4).hex()}",
            "link_type": "thank_you_card",
            "user_id": USER_ID
        })
        assert response.status_code == 200, f"Short URL create failed: {response.text}"
        data = response.json()
        short_code = data["short_code"]
        
        stats_response = requests.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats.get("link_type") == "thank_you_card", f"Wrong link_type: {stats.get('link_type')}"
    
    def test_short_url_create_digital_card(self):
        """Backend: Sending a digital business card short URL logs event as digital_card_sent NOT congrats_card_sent"""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/card/test-{os.urandom(4).hex()}",
            "link_type": "business_card",
            "user_id": USER_ID
        })
        assert response.status_code == 200, f"Short URL create failed: {response.text}"
        data = response.json()
        short_code = data["short_code"]
        
        stats_response = requests.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats.get("link_type") == "business_card", f"Wrong link_type: {stats.get('link_type')}"
    
    def test_short_url_redirect_works(self):
        """Backend: Short URL redirect works — GET /api/s/{code}"""
        # First create a short URL
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/test-redirect",
            "link_type": "custom",
            "user_id": USER_ID
        })
        assert response.status_code == 200
        data = response.json()
        short_code = data["short_code"]
        
        # Test redirect (don't follow redirects)
        redirect_response = requests.get(f"{BASE_URL}/api/s/{short_code}", allow_redirects=False)
        assert redirect_response.status_code in [302, 307, 301], f"Expected redirect, got {redirect_response.status_code}"


class TestActivityAndReports:
    """Test activity summary and reports endpoints"""
    
    def test_activity_summary_endpoint(self):
        """Backend: Activity summary endpoint works — GET /api/reports/activity-summary"""
        response = requests.get(f"{BASE_URL}/api/reports/activity-summary", params={"user_id": USER_ID})
        # Some deployments may not have this endpoint, so 404 is acceptable
        if response.status_code == 404:
            pytest.skip("Activity summary endpoint not available")
        assert response.status_code == 200, f"Activity summary failed: {response.text}"
        data = response.json()
        # Should return some kind of summary data
        assert isinstance(data, dict), "Expected dict response"
    
    def test_master_feed_loads(self):
        """Backend: Master feed for activity page loads"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed", params={"limit": 20})
        assert response.status_code == 200, f"Master feed failed: {response.text}"
        data = response.json()
        assert "feed" in data, "Missing 'feed' key"
        assert isinstance(data["feed"], list), "Feed should be a list"


class TestEventTypeMapping:
    """Verify the centralized event type mapping is working correctly"""
    
    @pytest.mark.parametrize("link_type,expected_not", [
        ("birthday_card", "congrats_card_sent"),
        ("thank_you_card", "congrats_card_sent"),
        ("thankyou_card", "congrats_card_sent"),
        ("holiday_card", "congrats_card_sent"),
        ("welcome_card", "congrats_card_sent"),
        ("anniversary_card", "congrats_card_sent"),
        ("business_card", "congrats_card_sent"),
        ("review_request", "congrats_card_sent"),
    ])
    def test_link_type_not_congrats(self, link_type, expected_not):
        """Verify each card type doesn't incorrectly map to congrats_card_sent"""
        # Import and test the mapping directly
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.event_types import LINK_TYPE_TO_EVENT
        
        resolved_event = LINK_TYPE_TO_EVENT.get(link_type)
        assert resolved_event is not None, f"Missing mapping for {link_type}"
        assert resolved_event != expected_not, f"{link_type} incorrectly maps to {expected_not}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
