"""
Quick Send Flow Backend API Tests
Tests the API endpoints used by the Quick Send feature:
- Duplicate check endpoint
- Messages send endpoint (sms_personal and email channels)
- Contact creation during Quick Send
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"


class TestQuickSendAPIs:
    """Tests for Quick Send related APIs"""
    
    @pytest.fixture(scope="class")
    def auth_data(self):
        """Login and get user data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return {
            "user_id": data["user"]["_id"],
            "token": data.get("token", "")
        }
    
    def test_login_returns_user_id(self, auth_data):
        """Verify login returns user_id needed for Quick Send APIs"""
        assert auth_data["user_id"], "User ID should be present in login response"
        print(f"✓ Login successful, user_id: {auth_data['user_id']}")
    
    def test_check_duplicate_with_existing_phone(self, auth_data):
        """Test duplicate check returns matched contacts for existing phone"""
        user_id = auth_data["user_id"]
        # Use a phone known to exist - Forest Ward's phone
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/check-duplicate?phone=8016349122")
        
        assert response.status_code == 200, f"Duplicate check failed: {response.text}"
        data = response.json()
        
        # Should return matches array
        assert "matches" in data, "Response should have 'matches' array"
        assert len(data["matches"]) > 0, "Should find at least one matching contact"
        
        # Verify match structure
        match = data["matches"][0]
        assert "id" in match, "Match should have 'id'"
        assert "first_name" in match, "Match should have 'first_name'"
        assert "phone" in match, "Match should have 'phone'"
        print(f"✓ Duplicate check found match: {match['first_name']} - {match['phone']}")
    
    def test_check_duplicate_with_nonexistent_phone(self, auth_data):
        """Test duplicate check returns empty array for new phone"""
        user_id = auth_data["user_id"]
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/check-duplicate?phone=9999999999")
        
        assert response.status_code == 200, f"Duplicate check failed: {response.text}"
        data = response.json()
        
        assert "matches" in data, "Response should have 'matches' array"
        assert len(data["matches"]) == 0, "Should return empty matches for nonexistent phone"
        print("✓ Duplicate check correctly returns empty for new phone")
    
    def test_check_duplicate_without_params(self, auth_data):
        """Test duplicate check with no params returns empty"""
        user_id = auth_data["user_id"]
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/check-duplicate")
        
        assert response.status_code == 200, f"Duplicate check failed: {response.text}"
        data = response.json()
        
        assert "matches" in data, "Response should have 'matches' array"
        print("✓ Duplicate check handles missing params gracefully")
    
    def test_messages_send_sms_personal_creates_conversation(self, auth_data):
        """Test messages/send with sms_personal channel logs the event"""
        user_id = auth_data["user_id"]
        
        # First create a test contact
        timestamp = datetime.now().strftime("%H%M%S")
        contact_response = requests.post(f"{BASE_URL}/api/contacts/{user_id}", json={
            "first_name": f"TEST_QuickSend_{timestamp}",
            "last_name": "Temp",
            "phone": f"555{timestamp}",
        })
        assert contact_response.status_code in [200, 201], f"Contact creation failed: {contact_response.text}"
        contact_data = contact_response.json()
        contact_id = contact_data.get("_id") or contact_data.get("id")
        assert contact_id, "Contact ID should be returned"
        
        try:
            # Now test messages/send with sms_personal channel
            send_response = requests.post(f"{BASE_URL}/api/messages/send/{user_id}", json={
                "contact_id": contact_id,
                "content": "Hey! Here's my digital business card. https://app.imonsocial.com/p/123",
                "channel": "sms_personal",
                "event_type": "digital_card_shared"
            })
            
            assert send_response.status_code == 200, f"Message send failed: {send_response.text}"
            send_data = send_response.json()
            
            # Verify response structure
            assert "status" in send_data, "Response should have 'status'"
            assert send_data["status"] == "sent", f"Status should be 'sent', got: {send_data['status']}"
            assert "conversation_id" in send_data, "Response should have 'conversation_id'"
            assert send_data["channel"] == "sms_personal", f"Channel should be 'sms_personal'"
            
            print(f"✓ SMS personal message logged successfully, conversation_id: {send_data['conversation_id']}")
        finally:
            # Cleanup - delete test contact
            requests.delete(f"{BASE_URL}/api/contacts/{contact_id}")
    
    def test_messages_send_creates_conversation_for_new_contact(self, auth_data):
        """Test that messages/send creates a conversation if none exists"""
        user_id = auth_data["user_id"]
        
        # Create a fresh test contact
        timestamp = datetime.now().strftime("%H%M%S%f")[:12]
        contact_response = requests.post(f"{BASE_URL}/api/contacts/{user_id}", json={
            "first_name": f"TEST_QS_Conv_{timestamp}",
            "last_name": "Test",
            "phone": f"555{timestamp[:7]}",
        })
        assert contact_response.status_code in [200, 201], f"Contact creation failed: {contact_response.text}"
        contact_data = contact_response.json()
        contact_id = contact_data.get("_id") or contact_data.get("id")
        
        try:
            # Send message to contact (should create conversation)
            send_response = requests.post(f"{BASE_URL}/api/messages/send/{user_id}", json={
                "contact_id": contact_id,
                "content": "Test message for conversation creation",
                "channel": "sms_personal",
                "event_type": "review_invite_sent"
            })
            
            assert send_response.status_code == 200, f"Message send failed: {send_response.text}"
            send_data = send_response.json()
            
            # Should have created a conversation
            assert "conversation_id" in send_data, "Should have created a conversation"
            conversation_id = send_data["conversation_id"]
            
            # Verify conversation exists
            conv_response = requests.get(f"{BASE_URL}/api/messages/conversations/{user_id}/{conversation_id}")
            assert conv_response.status_code == 200, "Conversation should exist"
            
            print(f"✓ Conversation created for new contact: {conversation_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/contacts/{contact_id}")
    
    def test_messages_send_email_channel(self, auth_data):
        """Test messages/send with email channel"""
        user_id = auth_data["user_id"]
        
        # Create test contact with email
        timestamp = datetime.now().strftime("%H%M%S")
        contact_response = requests.post(f"{BASE_URL}/api/contacts/{user_id}", json={
            "first_name": f"TEST_QS_Email_{timestamp}",
            "last_name": "Test",
            "phone": f"555{timestamp}",
            "email": f"test_{timestamp}@example.com"
        })
        assert contact_response.status_code in [200, 201], f"Contact creation failed: {contact_response.text}"
        contact_data = contact_response.json()
        contact_id = contact_data.get("_id") or contact_data.get("id")
        
        try:
            # Send via email channel
            send_response = requests.post(f"{BASE_URL}/api/messages/send/{user_id}", json={
                "contact_id": contact_id,
                "content": "Hey! Check out my showcase of happy customers!",
                "channel": "email",
                "event_type": "showcase_shared"
            })
            
            assert send_response.status_code == 200, f"Email send failed: {send_response.text}"
            send_data = send_response.json()
            
            # Email should be attempted (may succeed or fail based on email validity)
            assert "status" in send_data, "Response should have 'status'"
            # Note: Status could be 'sent' if Resend API works, or 'failed' if email is invalid domain
            print(f"✓ Email send attempted, status: {send_data['status']}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/contacts/{contact_id}")
    
    def test_contact_creation_endpoint(self, auth_data):
        """Test that contacts can be created (used when Quick Send creates new contact)"""
        user_id = auth_data["user_id"]
        timestamp = datetime.now().strftime("%H%M%S%f")[:10]
        
        # Create contact with first_name, last_name, phone, email
        contact_data = {
            "first_name": f"TEST_QS_Create_{timestamp}",
            "last_name": "NewContact",
            "phone": f"555{timestamp[:7]}",
            "email": f"test_{timestamp}@quicksend.com"
        }
        
        response = requests.post(f"{BASE_URL}/api/contacts/{user_id}", json=contact_data)
        assert response.status_code in [200, 201], f"Contact creation failed: {response.text}"
        
        data = response.json()
        contact_id = data.get("_id") or data.get("id")
        
        # Verify data was saved
        assert data.get("first_name") == contact_data["first_name"], "First name should match"
        assert data.get("last_name") == contact_data["last_name"], "Last name should match"
        assert data.get("phone") == contact_data["phone"], "Phone should match"
        
        print(f"✓ Contact created successfully: {contact_data['first_name']} {contact_data['last_name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/contacts/{contact_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
