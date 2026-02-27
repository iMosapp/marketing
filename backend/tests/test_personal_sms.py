"""
Test Personal SMS Mode - Tests for users without Twilio numbers (no mvpline_number)
When user has no mvpline_number, messages should be logged with channel 'sms_personal'
without attempting to send via Twilio.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPersonalSMSMode:
    """Tests for personal SMS mode (users without Twilio mvpline_number)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and get auth token"""
        self.email = "forest@imosapp.com"
        self.password = "Admin123!"
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
        self.user_id = self.user.get('_id')
        self.token = data.get('token')
        
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        self.session.close()
    
    def test_user_has_no_mvpline_number(self):
        """Verify test user (forest@imosapp.com) has no mvpline_number set"""
        # The user should NOT have mvpline_number for personal SMS mode to activate
        mvpline_number = self.user.get('mvpline_number')
        print(f"User mvpline_number: {mvpline_number}")
        assert mvpline_number is None or mvpline_number == "", \
            f"Test user should not have mvpline_number for this test, but has: {mvpline_number}"
    
    def test_get_contacts_for_conversation(self):
        """Get contacts to find one for testing message send"""
        response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        assert response.status_code == 200, f"Failed to get contacts: {response.text}"
        
        contacts = response.json()
        assert len(contacts) > 0, "No contacts found for testing"
        
        # Store contact for later tests
        self.test_contact = contacts[0]
        print(f"Found test contact: {self.test_contact.get('first_name')} {self.test_contact.get('last_name')} - {self.test_contact.get('phone')}")
        return self.test_contact
    
    def test_send_personal_sms_returns_success(self):
        """POST /api/messages/send/{user_id} with channel 'sms_personal' should return status 'sent'"""
        # First get a contact
        contacts_response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        assert contacts_response.status_code == 200
        contacts = contacts_response.json()
        assert len(contacts) > 0, "No contacts for testing"
        
        contact = contacts[0]
        contact_id = contact.get('_id')
        
        # Get or create conversation
        conv_response = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": contact_id,
            "contact_phone": contact.get('phone')
        })
        assert conv_response.status_code == 200, f"Failed to create/get conversation: {conv_response.text}"
        conversation = conv_response.json()
        conversation_id = conversation.get('_id')
        
        # Send message with sms_personal channel
        send_response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}/{conversation_id}", json={
            "content": "Test personal SMS message - sent from user device",
            "channel": "sms_personal"
        })
        
        assert send_response.status_code == 200, f"Send failed: {send_response.text}"
        message = send_response.json()
        
        # Verify response
        assert message.get('status') == 'sent', f"Expected status 'sent', got: {message.get('status')}"
        assert message.get('channel') == 'sms_personal', f"Expected channel 'sms_personal', got: {message.get('channel')}"
        
        print(f"Message sent successfully with channel: {message.get('channel')}, status: {message.get('status')}")
        return message
    
    def test_personal_sms_message_logged_in_db(self):
        """Verify message with sms_personal channel is persisted in database"""
        # Get contacts
        contacts_response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        contacts = contacts_response.json()
        contact = contacts[0]
        contact_id = contact.get('_id')
        
        # Get conversation
        conv_response = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": contact_id
        })
        conversation = conv_response.json()
        conversation_id = conversation.get('_id')
        
        # Send personal SMS
        unique_content = f"Personal SMS test message - {os.urandom(4).hex()}"
        send_response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}/{conversation_id}", json={
            "content": unique_content,
            "channel": "sms_personal"
        })
        assert send_response.status_code == 200
        sent_message = send_response.json()
        
        # Get thread to verify message is persisted
        thread_response = self.session.get(f"{BASE_URL}/api/messages/thread/{conversation_id}")
        assert thread_response.status_code == 200, f"Failed to get thread: {thread_response.text}"
        
        messages = thread_response.json()
        
        # Find our sent message
        found_message = None
        for msg in messages:
            if unique_content in msg.get('content', ''):
                found_message = msg
                break
        
        assert found_message is not None, f"Sent message not found in thread"
        print(f"Message persisted in DB: {found_message.get('_id')}")
    
    def test_regular_sms_channel_still_works(self):
        """Verify regular SMS channel still works (for users with Twilio number)"""
        # Get contacts
        contacts_response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        contacts = contacts_response.json()
        contact = contacts[0]
        contact_id = contact.get('_id')
        
        # Get conversation
        conv_response = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": contact_id
        })
        conversation = conv_response.json()
        conversation_id = conversation.get('_id')
        
        # Send with regular SMS channel
        send_response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}/{conversation_id}", json={
            "content": "Test regular SMS message",
            "channel": "sms"
        })
        
        assert send_response.status_code == 200, f"Regular SMS send failed: {send_response.text}"
        message = send_response.json()
        
        # Status could be 'sent' or 'failed' depending on Twilio config, but should not error
        assert message.get('status') in ['sent', 'failed'], f"Unexpected status: {message.get('status')}"
        print(f"Regular SMS status: {message.get('status')}")
    
    def test_email_channel_no_regression(self):
        """Verify email channel still works (no regression)"""
        # Get contacts
        contacts_response = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        contacts = contacts_response.json()
        contact = contacts[0]
        contact_id = contact.get('_id')
        
        # Get conversation
        conv_response = self.session.post(f"{BASE_URL}/api/messages/conversations/{self.user_id}", json={
            "contact_id": contact_id
        })
        conversation = conv_response.json()
        conversation_id = conversation.get('_id')
        
        # Try email channel
        send_response = self.session.post(f"{BASE_URL}/api/messages/send/{self.user_id}/{conversation_id}", json={
            "content": "Test email message",
            "channel": "email"
        })
        
        # Should return 200 (even if email fails due to missing contact email)
        assert send_response.status_code == 200, f"Email send request failed: {send_response.text}"
        message = send_response.json()
        
        # Email status depends on contact having email
        print(f"Email channel status: {message.get('status')}, error: {message.get('error', 'none')}")


class TestInboxAPI:
    """Test inbox/conversations API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials"""
        self.email = "forest@imosapp.com"
        self.password = "Admin123!"
        self.session = requests.Session()
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        data = login_response.json()
        self.user_id = data.get('user', {}).get('_id')
        self.token = data.get('token')
        
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        self.session.close()
    
    def test_get_conversations(self):
        """GET /api/messages/conversations/{user_id} returns conversations list"""
        response = self.session.get(f"{BASE_URL}/api/messages/conversations/{self.user_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        conversations = response.json()
        assert isinstance(conversations, list), "Expected list of conversations"
        print(f"Found {len(conversations)} conversations")
    
    def test_conversation_has_contact_info(self):
        """Verify conversation includes contact info"""
        response = self.session.get(f"{BASE_URL}/api/messages/conversations/{self.user_id}")
        assert response.status_code == 200
        
        conversations = response.json()
        if len(conversations) > 0:
            conv = conversations[0]
            assert 'contact' in conv or 'contact_phone' in conv, "Conversation missing contact info"
            print(f"First conversation contact: {conv.get('contact', {}).get('name', conv.get('contact_phone'))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
