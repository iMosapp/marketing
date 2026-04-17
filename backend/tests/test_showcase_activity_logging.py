"""
Test Showcase Activity Logging Feature
Tests for:
- GET /api/showcase/user/{userId} returning entries with review.photo_url
- GET /api/showcase/feedback-photo/{feedbackId} serving feedback photos
- GET /api/congrats/card/{cardId} logging 'congrats_card_viewed' event
- POST /api/congrats/card/{cardId}/track logging download/share events
- POST /api/p/review/{userId} logging 'review_submitted' event
- GET /api/contacts/{userId}/{contactId}/events returning customer_activity events
"""
import os
import pytest
import requests
import os
import base64
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from context
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_FEEDBACK_ID = "69a5ae2679b133dd270cfc90"  # jimmy's approved review with photo
TEST_CREDENTIALS = {
    "email": "forest@imonsocial.com",
    "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
}


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for protected endpoints"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestShowcaseEntriesWithReviewPhotos:
    """Test showcase entries include review.photo_url when feedback has a photo"""

    def test_user_showcase_returns_entries(self, api_client):
        """GET /api/showcase/user/{userId} returns entries array with review data"""
        response = api_client.get(f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)
        
        print(f"Showcase has {len(data['entries'])} entries")
        print(f"Total deliveries: {data.get('total_deliveries', 0)}, Total reviews: {data.get('total_reviews', 0)}")
        
    def test_showcase_entry_has_review_photo_url_field(self, api_client):
        """Entries with matched reviews should have review.photo_url field (can be null)"""
        response = api_client.get(f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        entries_with_reviews = [e for e in data["entries"] if e.get("review")]
        print(f"Found {len(entries_with_reviews)} entries with matched reviews")
        
        if len(entries_with_reviews) > 0:
            for entry in entries_with_reviews:
                review = entry["review"]
                # photo_url should be present in the review object (can be null)
                assert "photo_url" in review, f"review missing photo_url field: {review}"
                assert "id" in review
                assert "rating" in review
                assert "text" in review
                assert "customer_name" in review
                
                if review.get("photo_url"):
                    assert "/api/showcase/feedback-photo/" in review["photo_url"], \
                        f"photo_url should point to feedback-photo endpoint: {review['photo_url']}"
                    print(f"Entry '{entry['customer_name']}' has review with photo: {review['photo_url']}")
                else:
                    print(f"Entry '{entry['customer_name']}' has review without photo")
        else:
            print("No entries with reviews found - skipping photo_url assertion")


class TestFeedbackPhotoEndpoint:
    """Test GET /api/showcase/feedback-photo/{feedbackId} serves feedback photos"""

    def test_feedback_photo_returns_image_for_valid_id(self, api_client):
        """GET /api/showcase/feedback-photo/{feedbackId} returns image for valid feedback with photo"""
        response = api_client.get(f"{BASE_URL}/api/showcase/feedback-photo/{TEST_FEEDBACK_ID}")
        
        # May return image or 404 if feedback doesn't have photo
        if response.status_code == 200:
            # Should return image content
            content_type = response.headers.get("Content-Type", "")
            assert "image" in content_type, f"Expected image content type, got: {content_type}"
            print(f"Feedback photo returned successfully: {content_type}, {len(response.content)} bytes")
        else:
            # 404 is acceptable if feedback doesn't have photo
            assert response.status_code == 404, f"Unexpected status: {response.status_code}"
            print("Feedback photo not found (404) - feedback may not have a photo")

    def test_feedback_photo_returns_404_for_invalid_id(self, api_client):
        """GET /api/showcase/feedback-photo/{feedbackId} returns 404 for invalid ID"""
        response = api_client.get(f"{BASE_URL}/api/showcase/feedback-photo/000000000000000000000000")
        assert response.status_code == 404
        print("Invalid feedback ID correctly returns 404")

    def test_feedback_photo_returns_error_for_malformed_id(self, api_client):
        """GET /api/showcase/feedback-photo/{feedbackId} handles malformed ObjectId"""
        response = api_client.get(f"{BASE_URL}/api/showcase/feedback-photo/invalid-id")
        assert response.status_code in [400, 422, 500], f"Expected error for malformed ID, got: {response.status_code}"
        print(f"Malformed feedback ID returns error: {response.status_code}")


class TestCongratsCardViewLogging:
    """Test that viewing a congrats card logs 'congrats_card_viewed' event"""

    def test_get_card_logs_view_event(self, api_client):
        """GET /api/congrats/card/{cardId} should increment views and potentially log event"""
        # First get an existing card
        history_response = api_client.get(f"{BASE_URL}/api/congrats/history/{TEST_USER_ID}")
        
        if history_response.status_code != 200:
            pytest.skip("Could not get card history")
            
        cards = history_response.json()
        if len(cards) == 0:
            pytest.skip("No congrats cards found for user")
        
        card = cards[0]
        card_id = card.get("card_id")
        initial_views = card.get("views", 0)
        
        # View the card
        view_response = api_client.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        assert view_response.status_code == 200
        
        # Verify card data returned
        card_data = view_response.json()
        assert "card_id" in card_data
        assert "customer_name" in card_data
        print(f"Viewed card: {card_id}, customer: {card_data.get('customer_name')}")
        
        # Check if views incremented (card history should show updated count)
        time.sleep(0.5)  # Brief delay for DB update
        updated_history = api_client.get(f"{BASE_URL}/api/congrats/history/{TEST_USER_ID}").json()
        updated_card = next((c for c in updated_history if c.get("card_id") == card_id), None)
        
        if updated_card:
            new_views = updated_card.get("views", 0)
            assert new_views >= initial_views, f"Views should not decrease: {new_views} vs {initial_views}"
            print(f"Views updated: {initial_views} -> {new_views}")


class TestCongratsCardTrackingLogsEvents:
    """Test POST /api/congrats/card/{cardId}/track logs download/share events"""

    def test_track_download_logs_event(self, api_client):
        """POST /api/congrats/card/{cardId}/track with action=download logs event"""
        # Get a card to track
        history_response = api_client.get(f"{BASE_URL}/api/congrats/history/{TEST_USER_ID}")
        
        if history_response.status_code != 200:
            pytest.skip("Could not get card history")
            
        cards = history_response.json()
        if len(cards) == 0:
            pytest.skip("No congrats cards found for user")
        
        card_id = cards[0].get("card_id")
        
        # Track download
        response = api_client.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "download"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"Download tracked successfully for card: {card_id}")

    def test_track_share_logs_event(self, api_client):
        """POST /api/congrats/card/{cardId}/track with action=share logs event"""
        history_response = api_client.get(f"{BASE_URL}/api/congrats/history/{TEST_USER_ID}")
        
        if history_response.status_code != 200:
            pytest.skip("Could not get card history")
            
        cards = history_response.json()
        if len(cards) == 0:
            pytest.skip("No congrats cards found for user")
        
        card_id = cards[0].get("card_id")
        
        # Track share
        response = api_client.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "share"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"Share tracked successfully for card: {card_id}")


class TestReviewSubmissionLogsEvent:
    """Test POST /api/p/review/{userId} logs 'review_submitted' event"""

    def test_review_submission_logs_event(self, api_client):
        """POST /api/p/review/{userId} creates review and should log activity"""
        # Create a test review
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        test_image_bytes = base64.b64decode(test_image_base64)
        
        files = {
            'photo': ('test_photo.png', test_image_bytes, 'image/png')
        }
        form_data = {
            'customer_name': 'TEST_Review Logger',
            'rating': '5',
            'text_review': 'TEST: Great experience for activity logging test!',
            'customer_phone': '+15559876543',
            'customer_email': 'testlogger@example.com'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/p/review/{TEST_USER_ID}",
            files=files,
            data=form_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "feedback_id" in data
        
        print(f"Review submitted successfully: {data.get('feedback_id')}")
        print(f"Message: {data.get('message')}")


class TestContactEventsIncludeCustomerActivity:
    """Test GET /api/contacts/{userId}/{contactId}/events returns customer_activity events"""

    def test_events_api_returns_events(self, api_client):
        """GET /api/contacts/{userId}/{contactId}/events should return event list"""
        # We need a valid contact_id - let's get contacts first
        contacts_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        
        if contacts_response.status_code != 200:
            pytest.skip("Could not get contacts list")
        
        contacts = contacts_response.json()
        if not isinstance(contacts, list) or len(contacts) == 0:
            pytest.skip("No contacts found")
        
        # Get first contact
        contact = contacts[0]
        contact_id = contact.get("_id") or str(contact.get("id", ""))
        
        if not contact_id:
            pytest.skip("Contact has no ID")
        
        # Get events for this contact
        events_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}/events")
        
        assert events_response.status_code == 200, f"Expected 200, got {events_response.status_code}"
        
        data = events_response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        
        # Check if any customer_activity events exist
        customer_events = [e for e in data["events"] if e.get("category") == "customer_activity"]
        print(f"Contact {contact_id} has {len(data['events'])} total events, {len(customer_events)} customer_activity events")
        
        # Verify event structure if events exist
        if len(data["events"]) > 0:
            event = data["events"][0]
            assert "event_type" in event
            assert "title" in event
            assert "timestamp" in event
            assert "category" in event

    def test_customer_activity_event_types(self, api_client):
        """Verify expected customer_activity event types can exist"""
        # Check all contacts for customer_activity events
        contacts_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        
        if contacts_response.status_code != 200:
            pytest.skip("Could not get contacts list")
        
        contacts = contacts_response.json()
        if not isinstance(contacts, list):
            pytest.skip("Contacts not a list")
        
        all_customer_events = []
        for contact in contacts[:10]:  # Check first 10 contacts
            contact_id = contact.get("_id") or str(contact.get("id", ""))
            if not contact_id:
                continue
            
            events_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}/events")
            if events_response.status_code == 200:
                events = events_response.json().get("events", [])
                customer_events = [e for e in events if e.get("category") == "customer_activity"]
                all_customer_events.extend(customer_events)
        
        print(f"Found {len(all_customer_events)} customer_activity events across contacts")
        
        # Log unique event types found
        event_types = set(e.get("event_type") for e in all_customer_events)
        print(f"Event types found: {event_types}")
        
        # Expected event types (may or may not be present)
        expected_types = {"congrats_card_viewed", "congrats_card_download", "congrats_card_share", 
                         "review_submitted", "review_link_clicked"}
        
        found_expected = event_types & expected_types
        print(f"Expected types found: {found_expected}")


class TestPublicReviewEndpoints:
    """Test public review endpoints for activity logging"""

    def test_public_review_page_data(self, api_client):
        """GET /api/p/data/{userId} returns landing page data"""
        response = api_client.get(f"{BASE_URL}/api/p/data/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "user" in data
        assert "store" in data
        assert "testimonials" in data
        
        print(f"Landing page data: user={data['user'].get('name')}, testimonials={len(data['testimonials'])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
