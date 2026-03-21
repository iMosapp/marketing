"""
Chat Widget API Tests - Jessi AI Chat Widget for i'M On Social marketing website
Tests: POST /api/chat/start, POST /api/chat/message, POST /api/chat/capture
Also tests auto-extraction of name, email, phone from messages
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestChatWidgetStart:
    """Tests for POST /api/chat/start - creates a new session"""
    
    def test_start_session_success(self):
        """Test starting a new chat session returns session_id and greeting"""
        response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "greeting" in data, "Response should contain greeting"
        assert len(data["session_id"]) > 0, "session_id should not be empty"
        assert "Jessi" in data["greeting"], "Greeting should mention Jessi"
        print(f"✓ Start session success - session_id: {data['session_id'][:8]}...")
        return data["session_id"]
    
    def test_start_session_with_page_source(self):
        """Test starting session with different page sources"""
        pages = ["seo_page", "digital_card_page", "pricing_page"]
        for page in pages:
            response = requests.post(
                f"{BASE_URL}/api/chat/start",
                json={"page": page}
            )
            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data
            print(f"✓ Start session with page={page} success")


class TestChatWidgetMessage:
    """Tests for POST /api/chat/message - sends visitor message and gets AI response"""
    
    def test_send_message_success(self):
        """Test sending a message and receiving AI response"""
        # First start a session
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        # Send a message
        response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "What is i'M On Social?"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "response" in data, "Response should contain 'response' field"
        assert "lead_captured" in data, "Response should contain 'lead_captured' field"
        assert len(data["response"]) > 0, "AI response should not be empty"
        print(f"✓ Send message success - AI response: {data['response'][:100]}...")
    
    def test_send_message_invalid_session(self):
        """Test sending message with invalid session returns error"""
        response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": "invalid-session-id",
                "message": "Hello"
            }
        )
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert "error" in data, "Should return error for invalid session"
        print(f"✓ Invalid session handled correctly")
    
    def test_send_empty_message(self):
        """Test sending empty message returns error"""
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": ""
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data, "Should return error for empty message"
        print(f"✓ Empty message handled correctly")


class TestAutoExtraction:
    """Tests for auto-extraction of contact info from messages"""
    
    def test_extract_name_from_message(self):
        """Test auto-extraction of name from 'I'm John Smith' pattern"""
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        # Send message with name
        response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "Hi, I'm John Smith and I'm interested in your product"
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Name alone doesn't trigger lead_captured (needs email or phone too)
        assert "response" in data
        print(f"✓ Name extraction test passed")
    
    def test_extract_email_from_message(self):
        """Test auto-extraction of email from message"""
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        # First provide name
        requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "I'm Jane Doe"
            }
        )
        
        # Then provide email - this should trigger lead capture
        response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "You can reach me at test@example.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("lead_captured") == True, "Lead should be captured with name + email"
        print(f"✓ Email extraction and lead capture test passed")
    
    def test_extract_phone_from_message(self):
        """Test auto-extraction of phone from message"""
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        # First provide name
        requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "My name is Bob Wilson"
            }
        )
        
        # Then provide phone - this should trigger lead capture
        response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "Call me at (555) 123-4567"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("lead_captured") == True, "Lead should be captured with name + phone"
        print(f"✓ Phone extraction and lead capture test passed")


class TestChatWidgetCapture:
    """Tests for POST /api/chat/capture - manually captures lead contact info"""
    
    def test_capture_lead_success(self):
        """Test manually capturing lead info"""
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        # Manually capture lead
        response = requests.post(
            f"{BASE_URL}/api/chat/capture",
            json={
                "session_id": session_id,
                "name": "Test User",
                "email": "testuser@example.com",
                "phone": "555-987-6543"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", "Status should be 'ok'"
        assert data.get("lead_captured") == True, "Lead should be captured"
        print(f"✓ Manual lead capture success")
    
    def test_capture_lead_invalid_session(self):
        """Test capturing lead with invalid session"""
        response = requests.post(
            f"{BASE_URL}/api/chat/capture",
            json={
                "session_id": "invalid-session",
                "name": "Test",
                "email": "test@test.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data, "Should return error for invalid session"
        print(f"✓ Invalid session capture handled correctly")
    
    def test_capture_requires_name_and_contact(self):
        """Test that capture requires name + email or phone"""
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "homepage"}
        )
        session_id = start_response.json()["session_id"]
        
        # Only name - should not capture
        response = requests.post(
            f"{BASE_URL}/api/chat/capture",
            json={
                "session_id": session_id,
                "name": "Only Name"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("lead_captured") == False, "Lead should not be captured with only name"
        print(f"✓ Capture requires name + contact method")


class TestLeadCreation:
    """Tests for lead creation in MongoDB when lead is captured"""
    
    def test_lead_creates_contact_and_conversation(self):
        """Test that captured lead creates Contact, Conversation, Message in MongoDB"""
        # Start session
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "seo_page"}
        )
        session_id = start_response.json()["session_id"]
        
        # Have a conversation
        requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "I'm interested in your SEO features"
            }
        )
        time.sleep(3)  # Wait for AI response
        
        # Capture lead
        unique_email = f"test_lead_{int(time.time())}@example.com"
        response = requests.post(
            f"{BASE_URL}/api/chat/capture",
            json={
                "session_id": session_id,
                "name": "Test Lead User",
                "email": unique_email,
                "phone": "555-111-2222"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("lead_captured") == True
        print(f"✓ Lead captured successfully with email: {unique_email}")
        
        # Note: We can't directly verify MongoDB entries without admin access,
        # but the lead_captured=True indicates the _create_inbox_lead was called


class TestChatWidgetIntegration:
    """End-to-end integration tests for the chat widget flow"""
    
    def test_full_chat_flow(self):
        """Test complete chat flow: start -> messages -> capture"""
        # 1. Start session
        start_response = requests.post(
            f"{BASE_URL}/api/chat/start",
            json={"page": "digital_card_page"}
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        greeting = start_response.json()["greeting"]
        print(f"1. Session started: {session_id[:8]}...")
        print(f"   Greeting: {greeting}")
        
        # 2. Send first message
        msg1_response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "What are digital business cards?"
            }
        )
        assert msg1_response.status_code == 200
        msg1_data = msg1_response.json()
        assert "response" in msg1_data
        print(f"2. First message sent, AI response received")
        
        time.sleep(2)  # Wait between messages
        
        # 3. Send message with name
        msg2_response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "I'm Sarah Johnson from ABC Company"
            }
        )
        assert msg2_response.status_code == 200
        print(f"3. Name provided in message")
        
        time.sleep(2)
        
        # 4. Send message with email - should trigger lead capture
        msg3_response = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={
                "session_id": session_id,
                "message": "My email is sarah.johnson@abccompany.com"
            }
        )
        assert msg3_response.status_code == 200
        msg3_data = msg3_response.json()
        assert msg3_data.get("lead_captured") == True, "Lead should be captured after name + email"
        print(f"4. Email provided, lead captured: {msg3_data.get('lead_captured')}")
        
        print(f"✓ Full chat flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
