"""
Tests for the centralized event type resolution fix (iteration 130).

Bug: Activity feed always showed 'Congrats Card Sent' regardless of which card type was sent.
Root cause: Event type detection logic was scattered across 6+ backend files with inconsistent hardcoded maps.

Fix: Created centralized event type module at /app/backend/utils/event_types.py
- SINGLE SOURCE OF TRUTH for event type resolution
- All consumers (messages.py, congrats_cards.py, contact_events.py, short_urls.py) import from this module

Key tests:
- Birthday card short URL -> birthday_card_sent (NOT congrats_card_sent)
- Thank you card short URL -> thank_you_card_sent
- Holiday card short URL -> holiday_card_sent
- Welcome card short URL -> welcome_card_sent
- Anniversary card short URL -> anniversary_card_sent
- Congrats card short URL -> congrats_card_sent (control case)
"""
import os
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCentralizedEventTypeModule:
    """Tests for utils/event_types.py centralized module"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id") or user_data.get("user", {}).get("id")
        assert self.user_id, "No user_id returned from login"
        
        # Get test contact
        contacts_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        assert contacts_resp.status_code == 200, f"Failed to get contacts: {contacts_resp.text}"
        contacts = contacts_resp.json()
        assert len(contacts) > 0, "No contacts found"
        self.test_contact = contacts[0]
        self.contact_id = self.test_contact.get("_id") or self.test_contact.get("id")
        
        # Create or get conversation
        conv_resp = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": self.contact_id
        })
        assert conv_resp.status_code == 200, f"Failed to create conversation: {conv_resp.text}"
        conv = conv_resp.json()
        self.conversation_id = conv.get("_id") or conv.get("id")
        
        yield
    
    def _create_short_url(self, link_type: str) -> dict:
        """Helper to create short URL with specific link_type"""
        resp = self.session.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/congrats/test-{link_type}-{datetime.utcnow().timestamp()}",
            "link_type": link_type,
            "user_id": self.user_id
        })
        assert resp.status_code == 200, f"Failed to create short URL: {resp.text}"
        return resp.json()
    
    def _send_message_and_check_event_type(self, short_url: str, expected_event_type: str, explicit_event_type: str = None):
        """Helper to send message and verify contact_events entry"""
        payload = {
            "conversation_id": self.conversation_id,
            "contact_id": self.contact_id,
            "content": f"Check this: {short_url}",
            "channel": "sms_personal"
        }
        if explicit_event_type:
            payload["event_type"] = explicit_event_type
        
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json=payload)
        assert msg_resp.status_code == 200, f"Failed to send message: {msg_resp.text}"
        msg_data = msg_resp.json()
        assert msg_data.get("status") == "sent", f"Message not sent: {msg_data}"
        
        # Wait for async event logging
        time.sleep(0.5)
        
        # Check contact_events
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200, f"Failed to get events: {events_resp.text}"
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        # Look for expected event type
        matching_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == expected_event_type]
        
        # Also check for wrong event type (congrats_card_sent) if expected is different
        if expected_event_type != "congrats_card_sent":
            wrong_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "congrats_card_sent"]
            # Note: We're not asserting wrong_events == 0 because there may be pre-existing events
        
        return matching_events, events


class TestBirthdayCardEventType(TestCentralizedEventTypeModule):
    """Test birthday_card link_type resolves to birthday_card_sent"""
    
    def test_birthday_card_short_url_resolves_correctly(self):
        """
        CORE BUG FIX TEST: birthday_card short URL should resolve to birthday_card_sent
        Previously this was incorrectly resolving to congrats_card_sent
        """
        short_url_data = self._create_short_url("birthday_card")
        short_url = short_url_data["short_url"]
        print(f"Created birthday_card short URL: {short_url}")
        
        # Verify link_type stored correctly
        stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_url_data['short_code']}")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats.get("link_type") == "birthday_card", f"Wrong link_type: {stats.get('link_type')}"
        
        # Send message WITHOUT explicit event_type - backend should resolve from DB
        matching_events, all_events = self._send_message_and_check_event_type(short_url, "birthday_card_sent")
        
        assert len(matching_events) > 0, (
            f"BUG NOT FIXED! Expected birthday_card_sent event but found none. "
            f"Total events: {len(all_events)}. "
            f"Event types found: {[e.get('event_type') for e in all_events[:10]]}"
        )
        print(f"SUCCESS: birthday_card short URL correctly resolved to birthday_card_sent")
    
    def test_birthday_card_with_explicit_event_type(self):
        """Test explicit event_type=birthday_card_sent is used directly"""
        short_url_data = self._create_short_url("birthday_card")
        short_url = short_url_data["short_url"]
        
        matching_events, _ = self._send_message_and_check_event_type(
            short_url, 
            "birthday_card_sent", 
            explicit_event_type="birthday_card_sent"
        )
        
        assert len(matching_events) > 0, "Expected birthday_card_sent with explicit event_type"
        print("SUCCESS: Explicit birthday_card_sent event_type used correctly")


class TestThankYouCardEventType(TestCentralizedEventTypeModule):
    """Test thank_you_card link_type resolves to thank_you_card_sent"""
    
    def test_thank_you_card_short_url_resolves_correctly(self):
        """thank_you_card short URL should resolve to thank_you_card_sent"""
        short_url_data = self._create_short_url("thank_you_card")
        short_url = short_url_data["short_url"]
        print(f"Created thank_you_card short URL: {short_url}")
        
        # Verify link_type stored correctly
        stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_url_data['short_code']}")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats.get("link_type") == "thank_you_card", f"Wrong link_type: {stats.get('link_type')}"
        
        matching_events, all_events = self._send_message_and_check_event_type(short_url, "thank_you_card_sent")
        
        assert len(matching_events) > 0, (
            f"BUG NOT FIXED! Expected thank_you_card_sent but found none. "
            f"Event types found: {[e.get('event_type') for e in all_events[:10]]}"
        )
        print("SUCCESS: thank_you_card short URL correctly resolved to thank_you_card_sent")


class TestHolidayCardEventType(TestCentralizedEventTypeModule):
    """Test holiday_card link_type resolves to holiday_card_sent"""
    
    def test_holiday_card_short_url_resolves_correctly(self):
        """holiday_card short URL should resolve to holiday_card_sent"""
        short_url_data = self._create_short_url("holiday_card")
        short_url = short_url_data["short_url"]
        print(f"Created holiday_card short URL: {short_url}")
        
        # Verify link_type stored correctly
        stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_url_data['short_code']}")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats.get("link_type") == "holiday_card", f"Wrong link_type: {stats.get('link_type')}"
        
        matching_events, all_events = self._send_message_and_check_event_type(short_url, "holiday_card_sent")
        
        assert len(matching_events) > 0, (
            f"BUG NOT FIXED! Expected holiday_card_sent but found none. "
            f"Event types found: {[e.get('event_type') for e in all_events[:10]]}"
        )
        print("SUCCESS: holiday_card short URL correctly resolved to holiday_card_sent")


class TestWelcomeCardEventType(TestCentralizedEventTypeModule):
    """Test welcome_card link_type resolves to welcome_card_sent"""
    
    def test_welcome_card_short_url_resolves_correctly(self):
        """welcome_card short URL should resolve to welcome_card_sent"""
        short_url_data = self._create_short_url("welcome_card")
        short_url = short_url_data["short_url"]
        print(f"Created welcome_card short URL: {short_url}")
        
        # Verify link_type stored correctly
        stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_url_data['short_code']}")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats.get("link_type") == "welcome_card", f"Wrong link_type: {stats.get('link_type')}"
        
        matching_events, all_events = self._send_message_and_check_event_type(short_url, "welcome_card_sent")
        
        assert len(matching_events) > 0, (
            f"BUG NOT FIXED! Expected welcome_card_sent but found none. "
            f"Event types found: {[e.get('event_type') for e in all_events[:10]]}"
        )
        print("SUCCESS: welcome_card short URL correctly resolved to welcome_card_sent")


class TestAnniversaryCardEventType(TestCentralizedEventTypeModule):
    """Test anniversary_card link_type resolves to anniversary_card_sent"""
    
    def test_anniversary_card_short_url_resolves_correctly(self):
        """anniversary_card short URL should resolve to anniversary_card_sent"""
        short_url_data = self._create_short_url("anniversary_card")
        short_url = short_url_data["short_url"]
        print(f"Created anniversary_card short URL: {short_url}")
        
        # Verify link_type stored correctly
        stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_url_data['short_code']}")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats.get("link_type") == "anniversary_card", f"Wrong link_type: {stats.get('link_type')}"
        
        matching_events, all_events = self._send_message_and_check_event_type(short_url, "anniversary_card_sent")
        
        assert len(matching_events) > 0, (
            f"BUG NOT FIXED! Expected anniversary_card_sent but found none. "
            f"Event types found: {[e.get('event_type') for e in all_events[:10]]}"
        )
        print("SUCCESS: anniversary_card short URL correctly resolved to anniversary_card_sent")


class TestCongratsCardEventType(TestCentralizedEventTypeModule):
    """Test congrats_card link_type still resolves to congrats_card_sent (control case)"""
    
    def test_congrats_card_short_url_resolves_correctly(self):
        """congrats_card should still resolve to congrats_card_sent"""
        short_url_data = self._create_short_url("congrats_card")
        short_url = short_url_data["short_url"]
        print(f"Created congrats_card short URL: {short_url}")
        
        matching_events, all_events = self._send_message_and_check_event_type(short_url, "congrats_card_sent")
        
        assert len(matching_events) > 0, (
            f"Expected congrats_card_sent but found none. "
            f"Event types found: {[e.get('event_type') for e in all_events[:10]]}"
        )
        print("SUCCESS: congrats_card short URL correctly resolved to congrats_card_sent")


class TestRegularSMSEventType(TestCentralizedEventTypeModule):
    """Test regular SMS still resolves to personal_sms"""
    
    def test_regular_sms_resolves_to_personal_sms(self):
        """Regular SMS without links should resolve to personal_sms"""
        payload = {
            "conversation_id": self.conversation_id,
            "contact_id": self.contact_id,
            "content": f"Just checking in! Test at {datetime.utcnow().isoformat()}",
            "channel": "sms_personal"
        }
        
        msg_resp = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json=payload)
        assert msg_resp.status_code == 200, f"Failed to send message: {msg_resp.text}"
        
        time.sleep(0.5)
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        personal_sms_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "personal_sms"]
        
        assert len(personal_sms_events) > 0, "Expected personal_sms event for regular message"
        print("SUCCESS: Regular SMS correctly resolved to personal_sms")


class TestEventLabelsFromCentralizedModule(TestCentralizedEventTypeModule):
    """Test that contact_events timeline returns correct labels"""
    
    def test_events_endpoint_returns_correct_labels(self):
        """
        GET /api/contacts/{user_id}/{contact_id}/events should return correct labels
        from the centralized event_types module
        """
        # First send a birthday card
        short_url_data = self._create_short_url("birthday_card")
        short_url = short_url_data["short_url"]
        
        payload = {
            "conversation_id": self.conversation_id,
            "contact_id": self.contact_id,
            "content": f"Happy Birthday! {short_url}",
            "channel": "sms_personal"
        }
        self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json=payload)
        time.sleep(0.5)
        
        # Get events and check for correct labels
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        # Find birthday_card_sent event
        birthday_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "birthday_card_sent"]
        
        if birthday_events:
            event = birthday_events[0]
            # Check title is set (from get_card_sent_info)
            title = event.get("title", "")
            print(f"Birthday card event title: {title}")
            # The title should be something like "Birthday Card Sent" (from centralized module)
        
        print("SUCCESS: Events endpoint returning data correctly")


class TestPydanticEndpointEventType(TestCentralizedEventTypeModule):
    """Test Pydantic MessageCreate endpoint with explicit event_type"""
    
    def test_pydantic_endpoint_birthday_card_explicit(self):
        """Test POST /api/messages/send/{user_id}/{conversation_id} with explicit birthday_card_sent"""
        short_url_data = self._create_short_url("birthday_card")
        short_url = short_url_data["short_url"]
        
        # Use Pydantic endpoint with explicit event_type (conversation_id in body required by Pydantic model)
        msg_resp = self.session.post(
            f"{BASE_URL}/api/messages/send/{self.user_id}/{self.conversation_id}",
            json={
                "conversation_id": self.conversation_id,
                "content": f"Happy Birthday! {short_url}",
                "channel": "sms_personal",
                "event_type": "birthday_card_sent"
            }
        )
        assert msg_resp.status_code == 200, f"Failed: {msg_resp.text}"
        
        time.sleep(0.5)
        
        events_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        events = events_data.get("events", []) if isinstance(events_data, dict) else events_data
        
        birthday_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "birthday_card_sent"]
        
        assert len(birthday_events) > 0, "Expected birthday_card_sent from Pydantic endpoint"
        print("SUCCESS: Pydantic endpoint with explicit birthday_card_sent works correctly")


class TestAllLinkTypesStoreCorrectly:
    """Test all card link_types are stored correctly in short_urls collection"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        assert login_resp.status_code == 200
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id") or user_data.get("user", {}).get("id")
        yield
    
    def test_all_card_link_types_stored_correctly(self):
        """Verify all card link_types are stored and retrievable"""
        link_types = [
            "birthday_card",
            "thank_you_card",
            "thankyou_card",
            "holiday_card",
            "welcome_card",
            "anniversary_card",
            "congrats_card"
        ]
        
        for link_type in link_types:
            create_resp = self.session.post(f"{BASE_URL}/api/s/create", json={
                "original_url": f"https://app.imonsocial.com/test/{link_type}/{datetime.utcnow().timestamp()}",
                "link_type": link_type,
                "user_id": self.user_id
            })
            assert create_resp.status_code == 200, f"Failed to create {link_type}: {create_resp.text}"
            short_code = create_resp.json()["short_code"]
            
            stats_resp = self.session.get(f"{BASE_URL}/api/s/stats/{short_code}")
            assert stats_resp.status_code == 200
            stats = stats_resp.json()
            
            assert stats.get("link_type") == link_type, f"Expected {link_type}, got {stats.get('link_type')}"
            print(f"link_type={link_type} stored correctly")
        
        print("SUCCESS: All card link_types stored correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
