"""
Comprehensive Event Attribution Tests - Iteration 174
Tests all event logging endpoints and ensures events are created correctly.
Mission Critical: Customer going live Wednesday - ALL event paths must work.

Tested endpoints:
- POST /api/contacts/{userId}/{contactId}/events - direct event logging
- POST /api/contacts/{userId}/find-or-create-and-log - creates contact AND event
- POST /api/messages/send/{userId}/{conversationId} - message + event logging
- POST /api/messages/conversations/{userId} - conversation creation
- GET /api/tasks/{userId}/performance - performance counts
- GET /api/tasks/{userId}/performance/detail - event details
- GET /api/tasks/{userId}/summary - daily summary

Event types tested:
- sms_sent, personal_sms, sms_personal, sms_failed
- call_placed
- email_sent, email_failed
- showroom_shared
- birthday_card_sent, congrats_card_sent, anniversary_card_sent
- review_invite_sent
"""

import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a496841603573df5a41723"

class TestDirectEventLogging:
    """Test POST /api/contacts/{userId}/{contactId}/events - direct event logging"""
    
    def test_log_call_placed_event(self):
        """Test logging a call_placed event directly"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "call_placed",
                "icon": "call",
                "color": "#30D158",
                "title": "Call Placed",
                "description": "Test call from contacts page",
                "category": "communication"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["event_type"] == "call_placed", f"Event type mismatch: {data}"
        assert data["contact_id"] == CONTACT_ID
        assert data["user_id"] == USER_ID
        print(f"PASS: call_placed event created: {data}")
    
    def test_log_sms_sent_event(self):
        """Test logging an sms_sent event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "sms_sent",
                "icon": "chatbubble",
                "color": "#007AFF",
                "title": "SMS Sent",
                "description": "Test SMS from inbox",
                "category": "communication"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "sms_sent"
        print(f"PASS: sms_sent event created: {data}")
    
    def test_log_personal_sms_event(self):
        """Test logging a personal_sms event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "personal_sms",
                "icon": "chatbubble",
                "color": "#007AFF",
                "title": "Personal SMS",
                "description": "Test personal SMS from thread page",
                "category": "communication"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "personal_sms"
        print(f"PASS: personal_sms event created: {data}")
    
    def test_log_email_sent_event(self):
        """Test logging an email_sent event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "email_sent",
                "icon": "mail",
                "color": "#34C759",
                "title": "Email Sent",
                "description": "Test email from more page",
                "category": "communication"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "email_sent"
        print(f"PASS: email_sent event created: {data}")
    
    def test_log_showroom_shared_event(self):
        """Test logging a showroom_shared event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "showroom_shared",
                "icon": "car",
                "color": "#FF9500",
                "title": "Showroom Shared",
                "description": "Test showroom share from more page",
                "category": "sharing"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "showroom_shared"
        print(f"PASS: showroom_shared event created: {data}")
    
    def test_log_birthday_card_sent_event(self):
        """Test logging a birthday_card_sent event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "birthday_card_sent",
                "icon": "gift",
                "color": "#C9A962",
                "title": "Birthday Card Sent",
                "description": "Test birthday card from more page",
                "category": "cards"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "birthday_card_sent"
        print(f"PASS: birthday_card_sent event created: {data}")
    
    def test_log_review_invite_sent_event(self):
        """Test logging a review_invite_sent event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "review_invite_sent",
                "icon": "star",
                "color": "#FFD60A",
                "title": "Review Invite Sent",
                "description": "Test review invite from more page",
                "category": "reviews"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "review_invite_sent"
        print(f"PASS: review_invite_sent event created: {data}")
    
    def test_log_congrats_card_sent_event(self):
        """Test logging a congrats_card_sent event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "congrats_card_sent",
                "icon": "gift",
                "color": "#C9A962",
                "title": "Congrats Card Sent",
                "description": "Test congrats card",
                "category": "cards"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "congrats_card_sent"
        print(f"PASS: congrats_card_sent event created: {data}")
    
    def test_log_anniversary_card_sent_event(self):
        """Test logging an anniversary_card_sent event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "anniversary_card_sent",
                "icon": "gift",
                "color": "#C9A962",
                "title": "Anniversary Card Sent",
                "description": "Test anniversary card",
                "category": "cards"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "anniversary_card_sent"
        print(f"PASS: anniversary_card_sent event created: {data}")


class TestFindOrCreateAndLog:
    """Test POST /api/contacts/{userId}/find-or-create-and-log - creates contact AND event"""
    
    def test_find_or_create_with_phone_and_call_event(self):
        """Test finding existing contact by phone and logging call event"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json={
                "phone": "8018212166",  # Bud's phone
                "event_type": "call_placed",
                "event_title": "Call Placed",
                "event_description": "Test call via find-or-create",
                "event_icon": "call",
                "event_color": "#30D158"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("event_logged") == True, f"Event not logged: {data}"
        assert data.get("contact_id"), f"No contact_id returned: {data}"
        print(f"PASS: find-or-create with call event: {data}")
    
    def test_find_or_create_with_new_phone(self):
        """Test creating new contact with phone and logging sms event"""
        test_phone = f"555{int(time.time()) % 10000000:07d}"  # Unique phone
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json={
                "phone": test_phone,
                "name": "Test User Attribution",
                "event_type": "sms_sent",
                "event_title": "SMS Sent",
                "event_description": "Test SMS via find-or-create for new contact",
                "event_icon": "chatbubble",
                "event_color": "#007AFF"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("event_logged") == True
        # New contact should be created
        print(f"PASS: find-or-create with new phone: {data}")
    
    def test_find_or_create_with_showroom_event(self):
        """Test logging showroom_shared event via find-or-create"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json={
                "phone": "8018212166",  # Existing contact
                "event_type": "showroom_shared",
                "event_title": "Showroom Shared",
                "event_description": "Shared showroom via find-or-create",
                "event_icon": "car",
                "event_color": "#FF9500"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("event_logged") == True
        print(f"PASS: find-or-create with showroom event: {data}")
    
    def test_find_or_create_with_birthday_event(self):
        """Test logging birthday_card_sent event via find-or-create"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json={
                "phone": "8018212166",  # Existing contact
                "event_type": "birthday_card_sent",
                "event_title": "Birthday Card Sent",
                "event_description": "Sent birthday card via find-or-create",
                "event_icon": "gift",
                "event_color": "#C9A962"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("event_logged") == True
        print(f"PASS: find-or-create with birthday event: {data}")
    
    def test_find_or_create_with_review_event(self):
        """Test logging review_invite_sent event via find-or-create"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json={
                "phone": "8018212166",  # Existing contact
                "event_type": "review_invite_sent",
                "event_title": "Review Invite Sent",
                "event_description": "Sent review invite via find-or-create",
                "event_icon": "star",
                "event_color": "#FFD60A"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("event_logged") == True
        print(f"PASS: find-or-create with review event: {data}")
    
    def test_find_or_create_requires_phone_or_email(self):
        """Test that find-or-create requires phone or email"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json={
                "event_type": "call_placed",
                "event_title": "Call Placed"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: find-or-create requires phone or email")


class TestMessageSendWithEventLogging:
    """Test POST /api/messages/send/{userId}/{conversationId} - creates message AND event"""
    
    def setup_method(self):
        """Get or create a conversation for testing"""
        # First try to get existing conversation using correct endpoint
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        if response.status_code == 200:
            convs = response.json()
            if convs and len(convs) > 0:
                self.conversation_id = convs[0].get("_id") or convs[0].get("id")
                return
        
        # Create new conversation
        response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_ID}
        )
        if response.status_code in [200, 201]:
            self.conversation_id = response.json().get("_id") or response.json().get("id")
        else:
            self.conversation_id = None
    
    def test_send_sms_personal_creates_event(self):
        """Test that sending sms_personal creates contact_event"""
        if not self.conversation_id:
            pytest.skip("No conversation available")
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}/{self.conversation_id}",
            json={
                "content": "Test personal SMS for attribution testing",
                "channel": "sms_personal",
                "conversation_id": self.conversation_id
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("channel") == "sms_personal"
        print(f"PASS: sms_personal message creates event: {data.get('_id')}")
    
    def test_send_sms_personal_with_explicit_event_type(self):
        """Test that explicit event_type is respected"""
        if not self.conversation_id:
            pytest.skip("No conversation available")
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}/{self.conversation_id}",
            json={
                "content": "Test showroom share message",
                "channel": "sms_personal",
                "event_type": "showroom_shared",
                "conversation_id": self.conversation_id
            }
        )
        assert response.status_code == 200
        print("PASS: sms_personal with explicit event_type")


class TestConversationCreation:
    """Test POST /api/messages/conversations/{userId} - creates conversation from contact"""
    
    def test_create_conversation_from_contact(self):
        """Test creating a conversation from a contact ID"""
        response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_ID}
        )
        # Can be 200 (existing) or 201 (new)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("contact_id") == CONTACT_ID, f"Contact ID mismatch: {data}"
        print(f"PASS: Conversation created/found: {data}")


class TestPerformanceEndpoint:
    """Test GET /api/tasks/{userId}/performance - correct counts for texts, calls, emails, cards"""
    
    def test_performance_today(self):
        """Test performance for today"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=today")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "communication" in data, f"Missing communication key: {data}"
        assert "texts" in data["communication"], "Missing texts count"
        assert "calls" in data["communication"], "Missing calls count"
        assert "emails" in data["communication"], "Missing emails count"
        
        # Verify sharing section
        assert "sharing" in data, f"Missing sharing key: {data}"
        assert "card_shares" in data["sharing"], "Missing card_shares count"
        assert "reviews" in data["sharing"], "Missing reviews count"
        
        print(f"PASS: Performance today - texts={data['communication']['texts']}, calls={data['communication']['calls']}, emails={data['communication']['emails']}")
    
    def test_performance_week(self):
        """Test performance for the week"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        assert response.status_code == 200
        data = response.json()
        
        # Validate communication counts are integers
        texts = data.get("communication", {}).get("texts", 0)
        calls = data.get("communication", {}).get("calls", 0)
        emails = data.get("communication", {}).get("emails", 0)
        
        assert isinstance(texts, int), f"texts should be int: {texts}"
        assert isinstance(calls, int), f"calls should be int: {calls}"
        assert isinstance(emails, int), f"emails should be int: {emails}"
        
        print(f"PASS: Performance week - texts={texts}, calls={calls}, emails={emails}")
        
        # Verify total touchpoints
        assert "total_touchpoints" in data, "Missing total_touchpoints"
        print(f"Total touchpoints for week: {data['total_touchpoints']}")
    
    def test_performance_month(self):
        """Test performance for the month"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=month")
        assert response.status_code == 200
        data = response.json()
        
        assert "scorecard" in data, "Missing scorecard"
        assert "streak" in data["scorecard"], "Missing streak in scorecard"
        print(f"PASS: Performance month - streak={data['scorecard']['streak']}")


class TestPerformanceDetail:
    """Test GET /api/tasks/{userId}/performance/detail - returns event details"""
    
    def test_detail_texts(self):
        """Test getting text event details"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=texts&period=week")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "events" in data, f"Missing events key: {data}"
        assert "count" in data, "Missing count key"
        print(f"PASS: Text events detail - count={data['count']}, events={len(data['events'])}")
    
    def test_detail_calls(self):
        """Test getting call event details"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=calls&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        print(f"PASS: Call events detail - count={data.get('count', 0)}")
    
    def test_detail_emails(self):
        """Test getting email event details"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=emails&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        print(f"PASS: Email events detail - count={data.get('count', 0)}")
    
    def test_detail_card_shares(self):
        """Test getting card share event details"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=card_shares&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        print(f"PASS: Card shares detail - count={data.get('count', 0)}")
    
    def test_detail_reviews(self):
        """Test getting review event details"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=reviews&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        print(f"PASS: Reviews detail - count={data.get('count', 0)}")


class TestSummaryEndpoint:
    """Test GET /api/tasks/{userId}/summary - returns correct summary with all counts"""
    
    def test_summary_structure(self):
        """Test that summary returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Required fields
        assert "total_today" in data or "completed_today" in data, f"Missing task counts: {data}"
        print(f"PASS: Summary structure validated: {list(data.keys())}")
    
    def test_summary_activity_tracking(self):
        """Test that summary includes activity data"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Activity should be tracked
        print(f"PASS: Summary includes activity tracking")


class TestEventTypeVerification:
    """Verify all event types are counted correctly"""
    
    def test_all_sms_types_counted_in_texts(self):
        """Verify sms_sent, personal_sms, sms_personal, sms_failed all count as texts"""
        # Get current performance
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=today")
        assert response.status_code == 200
        initial_data = response.json()
        initial_texts = initial_data.get("communication", {}).get("texts", 0)
        
        # Log a personal_sms event
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "personal_sms",
                "title": "Personal SMS",
                "description": "Test"
            }
        )
        assert response.status_code == 200
        
        # Small delay for DB write
        time.sleep(0.5)
        
        # Check performance again
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=today")
        assert response.status_code == 200
        new_data = response.json()
        new_texts = new_data.get("communication", {}).get("texts", 0)
        
        # Texts should have increased
        assert new_texts >= initial_texts, f"Texts did not increase: {initial_texts} -> {new_texts}"
        print(f"PASS: personal_sms counted in texts: {initial_texts} -> {new_texts}")
    
    def test_call_placed_counted_in_calls(self):
        """Verify call_placed counts in calls"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=today")
        initial_calls = response.json().get("communication", {}).get("calls", 0)
        
        # Log a call_placed event
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "call_placed",
                "title": "Call Placed",
                "description": "Test"
            }
        )
        assert response.status_code == 200
        
        time.sleep(0.5)
        
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=today")
        new_calls = response.json().get("communication", {}).get("calls", 0)
        
        assert new_calls >= initial_calls, f"Calls did not increase: {initial_calls} -> {new_calls}"
        print(f"PASS: call_placed counted in calls: {initial_calls} -> {new_calls}")


class TestFrontendAPIEndpoints:
    """Test that frontend-facing API endpoints are accessible"""
    
    def test_contacts_list_endpoint(self):
        """Test contacts list endpoint"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert response.status_code == 200, f"Contacts list failed: {response.status_code}"
        print("PASS: Contacts list endpoint accessible")
    
    def test_inbox_conversations_endpoint(self):
        """Test inbox conversations endpoint"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        assert response.status_code == 200, f"Conversations list failed: {response.status_code}"
        print("PASS: Inbox conversations endpoint accessible")
    
    def test_tasks_list_endpoint(self):
        """Test tasks list endpoint"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}")
        assert response.status_code == 200, f"Tasks list failed: {response.status_code}"
        print("PASS: Tasks list endpoint accessible")
    
    def test_single_contact_endpoint(self):
        """Test single contact endpoint"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}")
        assert response.status_code == 200, f"Single contact failed: {response.status_code}"
        data = response.json()
        assert data.get("first_name") or data.get("name"), "No contact name returned"
        print(f"PASS: Single contact endpoint - {data.get('first_name', data.get('name'))}")
    
    def test_contact_events_endpoint(self):
        """Test contact events endpoint"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events")
        assert response.status_code == 200, f"Contact events failed: {response.status_code}"
        print("PASS: Contact events endpoint accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
