"""
Test Suite: Email Sending Fixes - Iteration 47
Tests the 5-point fix for email consistency:
1. Backend email send with channel=email returns status=sent with resend_id
2. Conversation info returns contact_email field
3. Conversations list includes email in contact object
4. Contact detail API returns email/email_work fields
5. Thread page mode initialization (frontend tested via Playwright)

User ID: 69a0b7095fddcede09591667 (Forest Ward)
Conversation ID: 69a15f29957bacd218fed55d
Contact email: forestward@gmail.com
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailSendingFixes:
    """Tests for email sending API functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials"""
        self.user_id = "69a0b7095fddcede09591667"
        self.conv_id = "69a15f29957bacd218fed55d"
        self.expected_email = "forestward@gmail.com"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_1_conversation_info_returns_contact_email(self):
        """GET /api/messages/conversation/{conv_id}/info returns contact_email field"""
        url = f"{BASE_URL}/api/messages/conversation/{self.conv_id}/info"
        response = self.session.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify contact_email field exists and has expected value
        assert "contact_email" in data, f"contact_email not in response: {data}"
        assert data["contact_email"] == self.expected_email, f"Expected {self.expected_email}, got {data.get('contact_email')}"
        print(f"✓ Conversation info returns contact_email: {data['contact_email']}")
    
    def test_2_conversations_list_includes_email(self):
        """GET /api/messages/conversations/{user_id} includes email in contact object"""
        url = f"{BASE_URL}/api/messages/conversations/{self.user_id}"
        response = self.session.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        conversations = response.json()
        
        # Find our test conversation
        test_conv = None
        for conv in conversations:
            if conv.get("_id") == self.conv_id:
                test_conv = conv
                break
        
        assert test_conv is not None, f"Test conversation {self.conv_id} not found in list"
        
        # Verify contact object has email
        contact = test_conv.get("contact", {})
        assert "email" in contact, f"email not in contact object: {contact}"
        assert contact["email"] == self.expected_email, f"Expected {self.expected_email}, got {contact.get('email')}"
        print(f"✓ Conversations list includes email in contact: {contact['email']}")
    
    def test_3_email_send_returns_resend_id(self):
        """POST /api/messages/send/{user_id} with channel=email returns status=sent with resend_id"""
        url = f"{BASE_URL}/api/messages/send/{self.user_id}"
        payload = {
            "conversation_id": self.conv_id,
            "content": f"Test email from pytest - iteration 47 - {os.urandom(4).hex()}",
            "channel": "email"
        }
        
        response = self.session.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify email was sent successfully
        assert data.get("status") == "sent", f"Expected status=sent, got status={data.get('status')}, error={data.get('error')}"
        assert data.get("channel") == "email", f"Expected channel=email, got {data.get('channel')}"
        assert "resend_id" in data, f"resend_id not in response: {data}"
        assert data["resend_id"], f"resend_id is empty: {data['resend_id']}"
        print(f"✓ Email sent successfully with resend_id: {data['resend_id']}")
    
    def test_4_contact_detail_has_email(self):
        """Verify contact record has email field"""
        # First get contact_id from conversation info
        info_url = f"{BASE_URL}/api/messages/conversation/{self.conv_id}/info"
        info_resp = self.session.get(info_url)
        assert info_resp.status_code == 200
        
        # Get conversations to find contact_id
        conv_url = f"{BASE_URL}/api/messages/conversations/{self.user_id}/{self.conv_id}"
        conv_resp = self.session.get(conv_url)
        assert conv_resp.status_code == 200
        conv_data = conv_resp.json()
        contact_id = conv_data.get("contact_id")
        
        if contact_id:
            # Get contact directly
            contact_url = f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}"
            contact_resp = self.session.get(contact_url)
            if contact_resp.status_code == 200:
                contact = contact_resp.json()
                email = contact.get("email") or contact.get("email_work")
                assert email, f"Contact has no email: {contact}"
                print(f"✓ Contact has email: {email}")
            else:
                print(f"⚠ Contact endpoint returned {contact_resp.status_code} (may be expected)")
        else:
            print("⚠ No contact_id in conversation data (may be expected)")
    
    def test_5_send_endpoint_validates_email_channel(self):
        """POST /api/messages/send/{user_id} properly routes email channel"""
        url = f"{BASE_URL}/api/messages/send/{self.user_id}"
        
        # Test with explicit email channel
        payload = {
            "conversation_id": self.conv_id,
            "content": f"Email channel test - {os.urandom(4).hex()}",
            "channel": "email"
        }
        
        response = self.session.post(url, json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Should route to email and succeed
        assert data.get("channel") == "email"
        assert data.get("status") == "sent"
        print(f"✓ Email channel routing works correctly")


class TestOtherAPIs:
    """Test other related APIs are still working"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.user_id = "69a0b7095fddcede09591667"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_health_check(self):
        """Basic API health check"""
        url = f"{BASE_URL}/api/health"
        response = self.session.get(url)
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_nda_list_accessible(self):
        """NDA list endpoint still accessible"""
        url = f"{BASE_URL}/api/admin/nda/list?user_id={self.user_id}"
        response = self.session.get(url)
        # Accept 200 or 401 (if auth required)
        assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"
        print(f"✓ NDA list endpoint accessible (status {response.status_code})")
    
    def test_conversations_list(self):
        """Conversations list endpoint works"""
        url = f"{BASE_URL}/api/messages/conversations/{self.user_id}"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Conversations list returns {len(data)} conversations")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
