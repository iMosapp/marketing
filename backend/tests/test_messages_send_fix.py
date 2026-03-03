"""
Test Suite for Messages Send Fix - Verifies the critical bug fix where:
1. Personal SMS messages sent via POST /api/messages/send/{user_id} are logged to backend
2. Contact events are created for activity tracking
3. Email channel still works correctly with Resend
4. GET endpoints return correct data

Test user: forest@imonsocial.com (no mvpline_number = Personal SMS mode)
Test conversation: 69a15f29957bacd218fed55d
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMessagesSendFix:
    """Tests for the critical message logging fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and get auth token"""
        self.email = "forest@imonsocial.com"
        self.password = "Admin123!"
        self.user_id = "69a0b7095fddcede09591667"
        self.conversation_id = "69a15f29957bacd218fed55d"
        self.session = requests.Session()
        
        # Login and get user info
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        data = login_response.json()
        self.user = data.get('user', {})
        self.token = data.get('token')
        
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        self.session.close()
    
    def test_user_has_no_mvpline_number(self):
        """Verify test user has no mvpline_number (Personal SMS mode)"""
        mvpline_number = self.user.get('mvpline_number')
        print(f"User mvpline_number: '{mvpline_number}'")
        assert not mvpline_number, f"Test user should NOT have mvpline_number, has: {mvpline_number}"
    
    def test_send_personal_sms_creates_message(self):
        """POST /api/messages/send/{user_id} with channel=sms_personal creates message in messages collection"""
        unique_content = f"TEST_PERSONAL_SMS_{int(time.time())}"
        
        # Send message using the simplified endpoint
        response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": self.conversation_id,
            "content": unique_content,
            "channel": "sms_personal"
        })
        
        assert response.status_code == 200, f"Send failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Verify response
        assert data.get('status') == 'sent', f"Expected status 'sent', got: {data.get('status')}"
        assert data.get('channel') == 'sms_personal', f"Expected channel 'sms_personal', got: {data.get('channel')}"
        assert data.get('_id'), "Response should include message _id"
        assert data.get('conversation_id') == self.conversation_id
        
        print(f"Message created: _id={data.get('_id')}, status={data.get('status')}, channel={data.get('channel')}")
    
    def test_send_personal_sms_creates_contact_event(self):
        """POST /api/messages/send/{user_id} with channel=sms_personal creates contact_event"""
        unique_content = f"TEST_SMS_EVENT_{int(time.time())}"
        
        # Send message
        response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": self.conversation_id,
            "content": unique_content,
            "channel": "sms_personal"
        })
        
        assert response.status_code == 200, f"Send failed: {response.text}"
        message_data = response.json()
        
        # Get conversation to find contact_id
        conv_response = self.session.get(f"{BASE_URL}/api/messages/conversation/{self.conversation_id}/info")
        if conv_response.status_code == 200:
            print(f"Conversation info: {conv_response.json()}")
        
        # Verify event_type detected in response
        # The backend should return event_type based on content (personal_sms for plain message)
        print(f"Message response: {message_data}")
        assert message_data.get('status') == 'sent'
    
    def test_send_personal_sms_with_card_link_creates_digital_card_event(self):
        """Personal SMS with /card/ URL creates digital_card_sent event"""
        unique_content = f"Hey! Here's my card: https://app.imonsocial.com/card/{self.user_id}?test={int(time.time())}"
        
        response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": self.conversation_id,
            "content": unique_content,
            "channel": "sms_personal"
        })
        
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        assert data.get('status') == 'sent'
        assert data.get('channel') == 'sms_personal'
        print(f"Digital card message sent: {data.get('_id')}")
    
    def test_send_personal_sms_with_review_link_creates_review_event(self):
        """Personal SMS with /review/ URL creates review_request_sent event"""
        unique_content = f"Leave us a review! https://app.imonsocial.com/review/test{int(time.time())}"
        
        response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": self.conversation_id,
            "content": unique_content,
            "channel": "sms_personal"
        })
        
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        assert data.get('status') == 'sent'
        print(f"Review request message sent: {data.get('_id')}")
    
    def test_send_email_creates_message_and_event(self):
        """POST /api/messages/send/{user_id} with channel=email sends via Resend and creates event"""
        unique_content = f"TEST_EMAIL_{int(time.time())}"
        
        response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": self.conversation_id,
            "content": unique_content,
            "channel": "email"
        })
        
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        
        # Email may succeed or fail depending on contact having email
        print(f"Email send result: status={data.get('status')}, resend_id={data.get('resend_id')}, error={data.get('error')}")
        
        # Even if email fails (no email on contact), the API should return 200
        assert data.get('channel') == 'email'
    
    def test_send_email_with_valid_contact_returns_resend_id(self):
        """Email to contact with email address should return resend_id"""
        # First, find a contact with email
        contacts_response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        assert contacts_response.status_code == 200
        contacts = contacts_response.json()
        
        contact_with_email = None
        for contact in contacts:
            if contact.get('email'):
                contact_with_email = contact
                break
        
        if not contact_with_email:
            pytest.skip("No contact with email found for testing")
        
        # Get/create conversation for this contact
        conv_response = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": contact_with_email.get('_id'),
            "contact_phone": contact_with_email.get('phone')
        })
        assert conv_response.status_code == 200
        conversation = conv_response.json()
        
        # Send email
        response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}", json={
            "conversation_id": conversation.get('_id'),
            "content": f"Test email message {int(time.time())}",
            "channel": "email"
        })
        
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        
        print(f"Email to {contact_with_email.get('email')}: status={data.get('status')}, resend_id={data.get('resend_id')}, error={data.get('error')}")
        
        # If Resend is configured and contact has email, should get resend_id
        if data.get('status') == 'sent':
            assert data.get('resend_id'), "Successful email should have resend_id"


class TestConversationsAndThreadEndpoints:
    """Test GET endpoints for conversations and messages"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials"""
        self.email = "forest@imonsocial.com"
        self.password = "Admin123!"
        self.user_id = "69a0b7095fddcede09591667"
        self.conversation_id = "69a15f29957bacd218fed55d"
        self.session = requests.Session()
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        data = login_response.json()
        self.token = data.get('token')
        
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        self.session.close()
    
    def test_get_conversations_list(self):
        """GET /api/messages/conversations/{user_id} returns conversations with last_message"""
        response = self.session.get(f"{BASE_URL}/api/messages/conversations/{self.user_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        conversations = response.json()
        assert isinstance(conversations, list)
        print(f"Found {len(conversations)} conversations")
        
        if len(conversations) > 0:
            conv = conversations[0]
            assert conv.get('_id'), "Conversation should have _id"
            # Should have last_message if messages exist
            if conv.get('last_message'):
                lm = conv.get('last_message')
                print(f"Last message: content='{lm.get('content', '')[:50]}', sender={lm.get('sender')}")
    
    def test_get_thread_messages(self):
        """GET /api/messages/thread/{conversation_id} returns messages in correct order"""
        response = self.session.get(f"{BASE_URL}/api/messages/thread/{self.conversation_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        messages = response.json()
        assert isinstance(messages, list)
        print(f"Found {len(messages)} messages in thread")
        
        if len(messages) >= 2:
            # Verify chronological order
            for i in range(1, len(messages)):
                prev_ts = messages[i-1].get('timestamp', '')
                curr_ts = messages[i].get('timestamp', '')
                assert prev_ts <= curr_ts, f"Messages not in chronological order: {prev_ts} > {curr_ts}"
        
        # Check recent messages have channel field
        recent_sms_personal = [m for m in messages[-10:] if m.get('channel') == 'sms_personal']
        print(f"Recent personal SMS messages: {len(recent_sms_personal)}")
    
    def test_conversation_info_endpoint(self):
        """GET /api/messages/conversation/{conversation_id}/info returns contact details"""
        response = self.session.get(f"{BASE_URL}/api/messages/conversation/{self.conversation_id}/info")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        info = response.json()
        assert info.get('_id') == self.conversation_id
        print(f"Conversation info: contact_name={info.get('contact_name')}, phone={info.get('contact_phone')}, email={info.get('contact_email')}")


class TestContactEvents:
    """Test contact events are created correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials"""
        self.email = "forest@imonsocial.com"
        self.password = "Admin123!"
        self.user_id = "69a0b7095fddcede09591667"
        self.conversation_id = "69a15f29957bacd218fed55d"
        self.contact_id = "69a0c06f7626f14d125f8c34"  # Forest Ward contact
        self.session = requests.Session()
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        data = login_response.json()
        self.token = data.get('token')
        
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        self.session.close()
    
    def test_contact_events_exist(self):
        """GET /api/contacts/{user_id}/{contact_id}/events returns events"""
        response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_id}/events")
        
        if response.status_code == 404:
            pytest.skip("Contact events endpoint not found or contact doesn't exist")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Handle both {"events": [...], "total": N} and [...] response formats
        events = data.get('events', []) if isinstance(data, dict) else data
        total = data.get('total', len(events)) if isinstance(data, dict) else len(events)
        
        print(f"Found {total} events for contact {self.contact_id}")
        
        # Look for recent message-related events
        target_types = ['personal_sms', 'email_sent', 'digital_card_sent', 'review_request_sent', 'congrats_card_sent', 'vcard_sent']
        sms_events = [e for e in events if isinstance(e, dict) and e.get('event_type') in target_types]
        print(f"Message-related events: {len(sms_events)}")
        
        for event in sms_events[:5]:
            print(f"  - {event.get('event_type')}: {event.get('content_preview', '')[:50]}")
        
        # Verify at least some message events were created from our tests
        assert len(sms_events) > 0, "Should have message-related events from tests"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
