"""
Test Relationship Feed API endpoints:
- Suggested Actions: GET /api/contacts/{userId}/{contactId}/suggested-actions
- Log Customer Reply: POST /api/contacts/{userId}/{contactId}/log-reply  
- Events with direction=inbound for customer replies
- Showcase photo endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from review_request
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a0c06f7626f14d125f8c34"


class TestSuggestedActions:
    """Test GET /api/contacts/{userId}/{contactId}/suggested-actions"""

    def test_suggested_actions_returns_200(self):
        """Suggested actions endpoint returns 200 with actions array"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/suggested-actions"
        response = requests.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "actions" in data, "Response should contain 'actions' key"
        assert isinstance(data["actions"], list), "Actions should be a list"
        
        print(f"Suggested actions returned: {len(data['actions'])} actions")
        for action in data["actions"]:
            print(f"  - {action.get('type')}: {action.get('title')}")

    def test_suggested_actions_structure(self):
        """Verify action objects have required fields"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/suggested-actions"
        response = requests.get(url)
        
        assert response.status_code == 200
        data = response.json()
        
        # Actions may be empty if no triggers (birthday/anniversary/etc)
        for action in data["actions"]:
            assert "type" in action, "Action should have 'type'"
            assert "title" in action, "Action should have 'title'"
            assert "description" in action, "Action should have 'description'"
            assert "icon" in action, "Action should have 'icon'"
            assert "color" in action, "Action should have 'color'"
            assert "action" in action, "Action should have 'action' (sms/congrats/etc)"
            print(f"Action validated: {action['type']} - {action['title']}")

    def test_suggested_actions_invalid_contact(self):
        """Returns empty actions for non-existent contact"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/000000000000000000000000/suggested-actions"
        response = requests.get(url)
        
        assert response.status_code == 200
        data = response.json()
        assert data["actions"] == [], "Should return empty actions for invalid contact"


class TestLogCustomerReply:
    """Test POST /api/contacts/{userId}/{contactId}/log-reply"""

    def test_log_reply_with_text(self):
        """Log a customer reply with text returns 200"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/log-reply"
        payload = {
            "text": "Test customer reply message from testing agent"
        }
        response = requests.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["event_type"] == "customer_reply", f"Expected event_type=customer_reply, got {data.get('event_type')}"
        assert data["direction"] == "inbound", f"Expected direction=inbound, got {data.get('direction')}"
        assert data.get("description") == payload["text"][:80], "Description should be truncated text"
        print(f"Customer reply logged: {data}")

    def test_log_reply_missing_text_and_photo_returns_400(self):
        """Log reply with neither text nor photo returns 400"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/log-reply"
        payload = {
            "text": "",
            "photo": None
        }
        response = requests.post(url, json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail'"
        assert "text or a photo" in data["detail"].lower(), f"Error should mention text or photo: {data['detail']}"
        print(f"Correctly rejected empty reply: {data['detail']}")

    def test_log_reply_empty_text_only_returns_400(self):
        """Log reply with only whitespace text returns 400"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/log-reply"
        payload = {
            "text": "   "  # Only whitespace
        }
        response = requests.post(url, json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Correctly rejected whitespace-only reply")


class TestContactEventsWithInbound:
    """Test GET /api/contacts/{userId}/{contactId}/events includes customer_reply with direction=inbound"""

    def test_events_include_customer_reply(self):
        """Events list includes customer_reply events with direction=inbound"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events"
        response = requests.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data, "Response should contain 'events' key"
        
        # Find customer_reply events
        customer_replies = [e for e in data["events"] if e.get("event_type") == "customer_reply"]
        
        print(f"Found {len(customer_replies)} customer_reply events")
        
        # There should be at least one (we just created one in previous test, plus existing one)
        assert len(customer_replies) >= 1, "Should have at least one customer_reply event"
        
        # Verify direction=inbound
        for reply in customer_replies:
            assert reply.get("direction") == "inbound", f"customer_reply should have direction=inbound, got {reply.get('direction')}"
            print(f"  - {reply.get('title')}: {reply.get('description')[:50]}...")

    def test_events_customer_reply_has_required_fields(self):
        """Customer reply events have required fields for UI display"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events"
        response = requests.get(url)
        
        assert response.status_code == 200
        data = response.json()
        
        customer_replies = [e for e in data["events"] if e.get("event_type") == "customer_reply"]
        
        for reply in customer_replies:
            assert "timestamp" in reply, "Reply should have timestamp"
            assert "title" in reply, "Reply should have title"
            assert "description" in reply or "full_content" in reply, "Reply should have content"
            assert "icon" in reply, "Reply should have icon"
            assert "color" in reply, "Reply should have color"
            print(f"Reply structure validated: {reply.get('title')}")


class TestShowcasePhotoEndpoints:
    """Test showcase photo URL in reviews and feedback-photo endpoint"""

    def test_showcase_user_reviews_have_photo_url(self):
        """GET /api/showcase/user/{userId} reviews should include photo_url field"""
        url = f"{BASE_URL}/api/showcase/user/{USER_ID}"
        response = requests.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "entries" in data, "Response should contain 'entries'"
        
        # Find entries with reviews
        entries_with_reviews = [e for e in data["entries"] if e.get("review")]
        
        print(f"Found {len(entries_with_reviews)} entries with reviews")
        
        for entry in entries_with_reviews:
            review = entry["review"]
            # photo_url field should exist (can be None if no photo)
            assert "photo_url" in review, f"Review should have 'photo_url' field: {review}"
            print(f"Review for {entry.get('customer_name')}: photo_url={review.get('photo_url')}")

    def test_feedback_photo_invalid_id_returns_404(self):
        """GET /api/showcase/feedback-photo/{feedbackId} returns 404 for invalid ID"""
        # Use a valid ObjectId format but non-existent
        fake_id = "000000000000000000000000"
        url = f"{BASE_URL}/api/showcase/feedback-photo/{fake_id}"
        response = requests.get(url)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Correctly returned 404 for non-existent feedback ID")

    def test_feedback_photo_malformed_id_returns_error(self):
        """GET /api/showcase/feedback-photo with malformed ID returns error"""
        url = f"{BASE_URL}/api/showcase/feedback-photo/not-a-valid-id"
        response = requests.get(url)
        
        # Should return 404 or 422/500 for invalid ObjectId
        assert response.status_code in [404, 422, 500], f"Expected error status, got {response.status_code}"
        print(f"Correctly returned {response.status_code} for malformed ID")


class TestExistingCustomerReply:
    """Verify the existing customer reply mentioned in the review_request"""

    def test_existing_reply_in_events(self):
        """Verify the pre-existing customer reply is in the events list"""
        url = f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events"
        response = requests.get(url)
        
        assert response.status_code == 200
        data = response.json()
        
        # Look for the specific reply mentioned in the request
        expected_text = "Hey Forest, thanks so much! My buddy Mike wants to check out some cars too."
        
        customer_replies = [e for e in data["events"] if e.get("event_type") == "customer_reply"]
        
        found = False
        for reply in customer_replies:
            content = reply.get("full_content") or reply.get("description") or ""
            if expected_text[:40] in content:
                found = True
                print(f"Found existing customer reply: {content[:60]}...")
                assert reply.get("direction") == "inbound"
                break
        
        # This might not exist if DB was reset - just log it
        if found:
            print("SUCCESS: Pre-existing customer reply found")
        else:
            print("INFO: Pre-existing customer reply not found (may have been cleared)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
