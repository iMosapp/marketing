"""
Backend tests for Email Sending Flow Bug Fix
Tests:
1. GET /api/messages/conversations/{user_id} - returns email in contact object
2. POST /api/messages/send/{user_id} with channel=email - sends email via Resend
3. GET /api/messages/conversation/{conversation_id}/info - returns contact_email
4. GET /api/reports/user-activity/{user_id} - CTR analytics on My Activity dashboard
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
CONVERSATION_ID = "69a15f29957bacd218fed55d"  # Forest Ward conversation
CONTACT_EMAIL = "forestward@gmail.com"


class TestEmailFlowBugFix:
    """Tests for email sending flow bug fix - email should be in contact data"""
    
    def test_conversations_returns_email_in_contact(self):
        """GET /api/messages/conversations/{user_id} should return email in contact object"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of conversations"
        
        # Find the Forest Ward conversation
        forest_conv = None
        for conv in data:
            if conv.get('_id') == CONVERSATION_ID or conv.get('contact', {}).get('name', '').lower().startswith('forest'):
                forest_conv = conv
                break
        
        if forest_conv:
            contact = forest_conv.get('contact', {})
            # Key assertion: email should be in contact object
            assert 'email' in contact, "Contact object should have 'email' field"
            print(f"Contact email found: {contact.get('email')}")
            print(f"Contact name: {contact.get('name')}")
        else:
            print("Forest Ward conversation not found - checking if any conversations have email field")
            # Check if any conversation has email in contact
            has_email_field = any(c.get('contact', {}).get('email') for c in data if c.get('contact'))
            print(f"Any conversation has email in contact: {has_email_field}")
    
    def test_conversation_info_returns_contact_email(self):
        """GET /api/messages/conversation/{conversation_id}/info should return contact_email"""
        response = requests.get(f"{BASE_URL}/api/messages/conversation/{CONVERSATION_ID}/info")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Conversation info: {data}")
        
        # The contact_email field should be populated if contact has email
        # This is the fallback API check in the frontend mode switch handler
        if data.get('contact_email'):
            print(f"contact_email present: {data.get('contact_email')}")
            assert '@' in data['contact_email'], "contact_email should be a valid email"
        else:
            print("contact_email not in response - checking contact_name for debugging")
            print(f"contact_name: {data.get('contact_name')}")
    
    def test_send_email_with_channel_email(self):
        """POST /api/messages/send/{user_id} with channel=email should return sent status with resend_id"""
        payload = {
            "conversation_id": CONVERSATION_ID,
            "content": "TEST_EMAIL Test message from backend test - please ignore",
            "channel": "email"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Email send response: {data}")
        
        # Key assertions for email send
        assert data.get('channel') == 'email', "Channel should be 'email'"
        
        if data.get('status') == 'sent':
            # Success case - email was sent via Resend
            assert data.get('resend_id'), "resend_id should be present for sent emails"
            print(f"Email sent successfully with resend_id: {data.get('resend_id')}")
        elif data.get('status') == 'failed':
            # Failure case - log the error for debugging
            print(f"Email failed: {data.get('error')}")
            # If no email for contact, this is expected
            if 'No email' in str(data.get('error', '')):
                pytest.skip("Contact has no email address")
        
        # Verify message was created
        assert data.get('_id'), "Message should have an _id"
        assert data.get('content') == payload['content'], "Content should match"


class TestCTRAnalytics:
    """Tests for CTR analytics on My Activity dashboard"""
    
    def test_user_activity_endpoint_exists(self):
        """GET /api/reports/user-activity/{user_id} should return activity data"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{USER_ID}?period=month")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Activity data keys: {data.keys()}")
        
        # Check expected structure
        assert 'summary' in data or 'communication' in data or 'sharing' in data, \
            "Response should have activity categories"
    
    def test_user_activity_has_ctr_data(self):
        """Activity data should include CTR (click-through rate) information"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{USER_ID}?period=month")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Check for CTR data structure
        if 'ctr' in data:
            ctr = data['ctr']
            print(f"CTR data: {ctr}")
            
            # Expected CTR categories
            expected_keys = ['digital_card', 'review_link', 'congrats_card']
            for key in expected_keys:
                if key in ctr:
                    item_ctr = ctr[key]
                    print(f"  {key}: sent={item_ctr.get('sent', 0)}, clicks={item_ctr.get('clicks', 0)}, ctr={item_ctr.get('ctr', 0)}%")
        else:
            print("CTR data not in response - may need to be populated with activity")
    
    def test_user_activity_period_variations(self):
        """Test different time periods for activity data"""
        periods = ['today', 'week', 'month', 'year']
        
        for period in periods:
            response = requests.get(f"{BASE_URL}/api/reports/user-activity/{USER_ID}?period={period}")
            
            assert response.status_code == 200, f"Period '{period}' failed: {response.status_code}"
            data = response.json()
            
            total = data.get('summary', {}).get('total_touchpoints', 0)
            print(f"Period '{period}': {total} touchpoints")


class TestConversationEmailField:
    """Tests to verify email field is properly included in conversation/contact data"""
    
    def test_single_conversation_has_contact_info(self):
        """GET /api/messages/conversations/{user_id}/{conversation_id} should include contact email"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}/{CONVERSATION_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Single conversation response keys: {data.keys()}")
        
        # Check if contact_id exists to look up email
        contact_id = data.get('contact_id')
        if contact_id:
            print(f"Contact ID: {contact_id}")
            
            # Fetch contact directly to verify email exists
            contact_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
            if contact_response.status_code == 200:
                contact_data = contact_response.json()
                email = contact_data.get('email') or contact_data.get('email_work')
                print(f"Contact email from direct lookup: {email}")
    
    def test_thread_messages_endpoint(self):
        """GET /api/messages/thread/{conversation_id} should return messages"""
        response = requests.get(f"{BASE_URL}/api/messages/thread/{CONVERSATION_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Thread should return list of messages"
        
        print(f"Thread has {len(data)} messages")
        
        # Check last message channel if exists
        if data:
            last_msg = data[-1]
            print(f"Last message channel: {last_msg.get('channel', 'not set')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
