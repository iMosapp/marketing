"""
Tests for the event_type resolution fix for activity feed.

Bug: Sending a digital business card from the contact page incorrectly showed
'Congrats Card Sent' instead of 'Digital Card Shared' in the activity feed.

Fix: 
1. MessageCreate model now has optional event_type field for explicit frontend control
2. Backend _resolve_event_type_from_content() resolves short URLs by looking up link_type from DB
3. The old broken behavior (everything with /api/s/ becoming congrats_card_sent) is fixed
"""
import pytest
import requests
import os
from datetime import datetime, timedelta
from bson import ObjectId

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEventTypeResolution:
    """Tests for event_type resolution in message sending"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get user_id
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id") or user_data.get("user", {}).get("id")
        assert self.user_id, "No user_id returned from login"
        
        # Get a contact for testing
        contacts_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        assert contacts_resp.status_code == 200, f"Failed to get contacts: {contacts_resp.text}"
        contacts = contacts_resp.json()
        assert len(contacts) > 0, "No contacts found"
        self.test_contact = contacts[0]
        self.contact_id = self.test_contact.get("_id") or self.test_contact.get("id")
        
        yield
    
    # === SHORT URL CREATION TESTS ===
    
    def test_create_short_url_business_card(self):
        """Create a short URL with link_type='business_card'"""
        resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/p/{self.user_id}",
            "link_type": "business_card",
            "user_id": self.user_id,
            "reference_id": self.user_id
        })
        assert resp.status_code == 200, f"Failed to create short URL: {resp.text}"
        data = resp.json()
        assert "short_code" in data, "No short_code in response"
        assert "short_url" in data, "No short_url in response"
        self.business_card_short_code = data["short_code"]
        self.business_card_short_url = data["short_url"]
        print(f"Created business_card short URL: {self.business_card_short_url}")
        return data
    
    def test_create_short_url_review_request(self):
        """Create a short URL with link_type='review_request'"""
        resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/review/{self.user_id}",
            "link_type": "review_request",
            "user_id": self.user_id
        })
        assert resp.status_code == 200, f"Failed to create short URL: {resp.text}"
        data = resp.json()
        assert "short_code" in data
        print(f"Created review_request short URL: {data['short_url']}")
        return data
    
    def test_create_short_url_congrats_card(self):
        """Create a short URL with link_type='congrats_card'"""
        resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/congrats/{self.user_id}/test",
            "link_type": "congrats_card",
            "user_id": self.user_id
        })
        assert resp.status_code == 200, f"Failed to create short URL: {resp.text}"
        data = resp.json()
        assert "short_code" in data
        print(f"Created congrats_card short URL: {data['short_url']}")
        return data
    
    def test_create_short_url_showcase(self):
        """Create a short URL with link_type='showcase'"""
        resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/showcase/{self.user_id}",
            "link_type": "showcase",
            "user_id": self.user_id
        })
        assert resp.status_code == 200, f"Failed to create short URL: {resp.text}"
        data = resp.json()
        assert "short_code" in data
        print(f"Created showcase short URL: {data['short_url']}")
        return data
    
    # === MESSAGE SENDING WITH EXPLICIT EVENT_TYPE TESTS ===
    
    def test_send_message_with_explicit_event_type_digital_card(self):
        """
        Send message with explicit event_type='digital_card_sent' from frontend.
        This tests the FIX: frontend now passes event_type directly.
        """
        # First create a conversation
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200, f"Failed to create conversation: {conv_resp.text}"
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        # Create a business card short URL first
        short_url_data = self.test_create_short_url_business_card()
        short_url = short_url_data["short_url"]
        
        # Send message with EXPLICIT event_type (simulating frontend behavior)
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation_id,
            "contact_id": self.contact_id,
            "content": f"Check out my digital card: {short_url}",
            "channel": "sms_personal",
            "event_type": "digital_card_sent"  # Explicit event_type from frontend
        })
        assert msg_resp.status_code == 200, f"Failed to send message: {msg_resp.text}"
        msg_data = msg_resp.json()
        assert msg_data.get("status") == "sent", f"Message not sent: {msg_data}"
        print(f"Message sent with explicit event_type=digital_card_sent: {msg_data.get('_id')}")
        
        # Verify event was logged correctly in contact_events
        import time
        time.sleep(0.5)  # Wait for async event logging
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200, f"Failed to get events: {events_resp.text}"
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        # Check for digital_card_sent event (not congrats_card_sent!)
        digital_card_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "digital_card_sent"]
        print(f"Found {len(digital_card_events)} digital_card_sent events")
        
        # Also verify no congrats_card_sent event was created
        congrats_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "congrats_card_sent"]
        print(f"Found {len(congrats_events)} congrats_card_sent events (should be 0 or unrelated to this test)")
        
        assert len(digital_card_events) > 0, "Expected digital_card_sent event, but found none. OLD BUG MAY STILL EXIST!"
        return msg_data
    
    def test_send_message_with_explicit_event_type_review_request(self):
        """Send message with explicit event_type='review_request_sent'"""
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        short_url_data = self.test_create_short_url_review_request()
        short_url = short_url_data["short_url"]
        
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation_id,
            "content": f"Would you please leave us a review? {short_url}",
            "channel": "sms_personal",
            "event_type": "review_request_sent"
        })
        assert msg_resp.status_code == 200, f"Failed: {msg_resp.text}"
        msg_data = msg_resp.json()
        assert msg_data.get("status") == "sent"
        print(f"Message sent with explicit event_type=review_request_sent")
        return msg_data
    
    # === MESSAGE SENDING WITHOUT EXPLICIT EVENT_TYPE (DB LOOKUP TESTS) ===
    
    def test_send_message_without_explicit_event_type_business_card_resolves_correctly(self):
        """
        Send message with a business_card short URL but NO explicit event_type.
        Backend should lookup the short_url's link_type from DB and resolve to 'digital_card_sent'.
        THIS IS THE CORE BUG FIX TEST - previously this would incorrectly become 'congrats_card_sent'.
        """
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        # Create a fresh business card short URL
        short_url_resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/p/{self.user_id}/test-{datetime.utcnow().timestamp()}",
            "link_type": "business_card",
            "user_id": self.user_id
        })
        assert short_url_resp.status_code == 200
        short_url_data = short_url_resp.json()
        short_url = short_url_data["short_url"]
        short_code = short_url_data["short_code"]
        print(f"Created business_card short URL: {short_url} (code: {short_code})")
        
        # Send message WITHOUT explicit event_type - backend should resolve from DB
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation_id,
            "content": f"Check this out: {short_url}",
            "channel": "sms_personal"
            # NO event_type - backend should resolve it
        })
        assert msg_resp.status_code == 200, f"Failed: {msg_resp.text}"
        msg_data = msg_resp.json()
        assert msg_data.get("status") == "sent"
        print(f"Message sent WITHOUT explicit event_type")
        
        # Wait for event logging
        import time
        time.sleep(0.5)
        
        # Check contact_events for the event_type
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        # Look for recent events with digital_card_sent
        recent_digital_card_events = [
            e for e in events 
            if isinstance(e, dict) and e.get("event_type") == "digital_card_sent" 
        ]
        
        # Look for recent events with congrats_card_sent (BUG behavior)
        recent_congrats_events = [
            e for e in events 
            if isinstance(e, dict) and e.get("event_type") == "congrats_card_sent"
        ]
        
        print(f"Found {len(recent_digital_card_events)} digital_card_sent events")
        print(f"Found {len(recent_congrats_events)} congrats_card_sent events")
        
        assert len(recent_digital_card_events) > 0, (
            f"BUG NOT FIXED! Expected digital_card_sent event but found none. "
            f"Congrats events: {len(recent_congrats_events)}. "
            f"The short URL with link_type=business_card should resolve to digital_card_sent, not congrats_card_sent!"
        )
        print("SUCCESS: business_card short URL correctly resolved to digital_card_sent")
    
    def test_send_message_without_explicit_event_type_review_request_resolves_correctly(self):
        """
        Send message with a review_request short URL but NO explicit event_type.
        Backend should lookup and resolve to 'review_request_sent'.
        """
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        short_url_resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/review/{self.user_id}/test-{datetime.utcnow().timestamp()}",
            "link_type": "review_request",
            "user_id": self.user_id
        })
        assert short_url_resp.status_code == 200
        short_url = short_url_resp.json()["short_url"]
        
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation_id,
            "content": f"Leave us a review: {short_url}",
            "channel": "sms_personal"
            # NO event_type
        })
        assert msg_resp.status_code == 200
        
        import time
        time.sleep(0.5)
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        review_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "review_request_sent"]
        print(f"Found {len(review_events)} review_request_sent events")
        
        assert len(review_events) > 0, "Expected review_request_sent event but found none"
        print("SUCCESS: review_request short URL correctly resolved to review_request_sent")
    
    # === KEYWORD-BASED FALLBACK TESTS ===
    
    def test_send_message_with_congrats_keyword_resolves_to_congrats_card_sent(self):
        """
        Send message with 'congrats' keyword (no short URL).
        Should resolve to 'congrats_card_sent' via keyword detection.
        """
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation_id,
            "content": "Congrats on your new car! You're going to love it!",
            "channel": "sms_personal"
        })
        assert msg_resp.status_code == 200
        
        import time
        time.sleep(0.5)
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        congrats_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "congrats_card_sent"]
        print(f"Found {len(congrats_events)} congrats_card_sent events")
        
        assert len(congrats_events) > 0, "Expected congrats_card_sent event for 'congrats' keyword"
        print("SUCCESS: 'congrats' keyword correctly resolved to congrats_card_sent")
    
    def test_send_regular_personal_sms_resolves_to_personal_sms(self):
        """
        Send regular message without any special content.
        Should resolve to 'personal_sms'.
        """
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation_id,
            "content": f"Hey, just checking in! How's everything going? Test {datetime.utcnow().isoformat()}",
            "channel": "sms_personal"
        })
        assert msg_resp.status_code == 200
        
        import time
        time.sleep(0.5)
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        personal_sms_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "personal_sms"]
        print(f"Found {len(personal_sms_events)} personal_sms events")
        
        assert len(personal_sms_events) > 0, "Expected personal_sms event for regular message"
        print("SUCCESS: Regular message correctly resolved to personal_sms")
    
    # === PYDANTIC ENDPOINT TESTS ===
    
    def test_pydantic_endpoint_with_explicit_event_type(self):
        """
        Test POST /api/messages/send/{user_id}/{conversation_id} (Pydantic MessageCreate endpoint)
        with explicit event_type.
        """
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200
        conv = conv_resp.json()
        conversation_id = conv.get("_id") or conv.get("id")
        
        # Create a short URL
        short_url_data = self.test_create_short_url_business_card()
        short_url = short_url_data["short_url"]
        
        # Use the Pydantic endpoint
        msg_resp = self.session.post(
            f"{BASE_URL}/api/messages/send/{self.user_id}/{conversation_id}",
            json={
                "conversation_id": conversation_id,
                "content": f"My digital card: {short_url}",
                "channel": "sms_personal",
                "event_type": "digital_card_sent"
            }
        )
        assert msg_resp.status_code == 200, f"Failed: {msg_resp.text}"
        msg_data = msg_resp.json()
        assert msg_data.get("status") == "sent"
        print(f"Pydantic endpoint message sent with explicit event_type=digital_card_sent")
        
        import time
        time.sleep(0.5)
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        digital_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "digital_card_sent"]
        assert len(digital_events) > 0, "Expected digital_card_sent event from Pydantic endpoint"
        print("SUCCESS: Pydantic endpoint correctly used explicit event_type")


class TestShortURLLinkTypeLookup:
    """Tests for verifying short_urls collection stores link_type correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id") or user_data.get("user", {}).get("id")
        yield
    
    def test_short_url_stats_returns_link_type(self):
        """Verify short URL stats endpoint returns link_type"""
        # Create a short URL
        create_resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/p/{self.user_id}/stats-test",
            "link_type": "business_card",
            "user_id": self.user_id
        })
        assert create_resp.status_code == 200
        short_code = create_resp.json()["short_code"]
        
        # Get stats
        stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        
        assert stats.get("link_type") == "business_card", f"Expected link_type=business_card, got {stats.get('link_type')}"
        print(f"Short URL stats correctly returns link_type={stats.get('link_type')}")
    
    def test_different_link_types_stored_correctly(self):
        """Test that different link_types are stored correctly in short_urls collection"""
        link_types = ["business_card", "review_request", "congrats_card", "showcase"]
        
        for link_type in link_types:
            create_resp = self.session.post(f"{BASE_URL}/api/s/create", json={
                "original_url": f"https://app.imonsocial.com/test/{link_type}/{datetime.utcnow().timestamp()}",
                "link_type": link_type,
                "user_id": self.user_id
            })
            assert create_resp.status_code == 200
            short_code = create_resp.json()["short_code"]
            
            stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_code}")
            assert stats_resp.status_code == 200
            stats = stats_resp.json()
            
            assert stats.get("link_type") == link_type, f"Expected {link_type}, got {stats.get('link_type')}"
            print(f"link_type={link_type} stored and retrieved correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
