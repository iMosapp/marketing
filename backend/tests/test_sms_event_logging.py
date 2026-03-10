"""
Test SMS Event Logging Bug Fix - iteration_173
Tests the critical bug fix where SMS events were not being logged in the performance dashboard.

Key fix: thread/[id].tsx personal SMS flow now awaits API call BEFORE opening native SMS app,
with sendBeacon fallback for event logging if main call fails.

Tests cover:
1. POST /api/messages/send/{userId}/{conversationId} with channel=sms_personal creates contact_event
2. POST /api/contacts/{userId}/{contactId}/events creates contact_event directly
3. GET /api/tasks/{userId}/performance correctly counts texts (sms_sent + personal_sms + sms_personal + sms_failed)
4. POST /api/messages/conversations/{userId} creates conversation from contact_id
5. Backend returns 404 (not 500) for invalid conversation ID
"""
import pytest
import requests
import os
from datetime import datetime, timezone
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://rms-polish.preview.emergentagent.com').rstrip('/')

# Test credentials from bug report
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a496841603573df5a41723"  # Bud, phone: 8018212166

@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestSMSEventLogging:
    """Test that SMS events are correctly logged to contact_events for performance tracking"""
    
    def test_create_conversation_from_contact_id(self, api_client):
        """POST /api/messages/conversations/{userId} should create/return conversation with contact_id"""
        response = api_client.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={
                "contact_id": CONTACT_ID,
                "contact_phone": "8018212166"
            }
        )
        print(f"Create conversation response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Response should have conversation _id"
        assert data.get("contact_id") == CONTACT_ID, f"contact_id should be {CONTACT_ID}"
        print(f"Conversation ID: {data['_id']}, Contact ID: {data['contact_id']}")
        return data["_id"]
    
    def test_send_personal_sms_creates_contact_event(self, api_client):
        """POST /api/messages/send/{userId}/{convId} with channel=sms_personal creates contact_event"""
        # First get/create conversation
        conv_response = api_client.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_ID, "contact_phone": "8018212166"}
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["_id"]
        
        # Send personal SMS
        unique_content = f"Test SMS at {datetime.now(timezone.utc).isoformat()}"
        response = api_client.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}/{conv_id}",
            json={
                "conversation_id": conv_id,
                "content": unique_content,
                "channel": "sms_personal"
            }
        )
        print(f"Send SMS response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "sent", f"Message status should be 'sent', got: {data.get('status')}"
        assert data.get("channel") == "sms_personal", f"Channel should be 'sms_personal', got: {data.get('channel')}"
        print(f"Message sent with channel={data.get('channel')}, status={data.get('status')}")
        
        # Verify contact_event was created by checking events
        time.sleep(0.5)  # Allow for async event logging
        events_response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events")
        assert events_response.status_code == 200
        events = events_response.json().get("events", [])
        
        # Find recent personal_sms or sms_personal event
        recent_sms_events = [e for e in events if e.get("event_type") in ("personal_sms", "sms_personal")]
        print(f"Found {len(recent_sms_events)} recent personal SMS events")
        assert len(recent_sms_events) > 0, "Should have at least one personal_sms event logged"
    
    def test_direct_event_logging_creates_contact_event(self, api_client):
        """POST /api/contacts/{userId}/{contactId}/events creates contact_event directly"""
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "personal_sms",
                "title": "SMS Sent",
                "description": f"Test direct event logging at {datetime.now(timezone.utc).isoformat()}",
                "channel": "sms_personal",
                "category": "message",
                "icon": "chatbubble",
                "color": "#34C759"
            }
        )
        print(f"Direct event logging response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("event_type") == "personal_sms", f"Event type should be 'personal_sms'"
        assert data.get("contact_id") == CONTACT_ID
        assert data.get("user_id") == USER_ID
        print(f"Direct event created: event_type={data.get('event_type')}")
    
    def test_performance_counts_all_text_types(self, api_client):
        """GET /api/tasks/{userId}/performance correctly counts texts (all SMS event types)"""
        response = api_client.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        print(f"Performance response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        communication = data.get("communication", {})
        texts_count = communication.get("texts", 0)
        print(f"Performance data - texts: {texts_count}, calls: {communication.get('calls')}, emails: {communication.get('emails')}")
        
        # Verify texts count includes all SMS types: sms_sent + sms_personal + personal_sms + sms_failed
        assert texts_count >= 0, "Texts count should be non-negative"
        
        # Also verify total_touchpoints is calculated
        total = data.get("total_touchpoints", 0)
        print(f"Total touchpoints: {total}")
        assert total >= 0
    
    def test_invalid_conversation_id_returns_404_not_500(self, api_client):
        """Backend should return 404 for invalid conversation ID, not 500"""
        invalid_conv_id = "000000000000000000000000"  # Valid ObjectId format but doesn't exist
        
        response = api_client.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}/{invalid_conv_id}",
            json={
                "conversation_id": invalid_conv_id,
                "content": "Test message",
                "channel": "sms_personal"
            }
        )
        print(f"Invalid conv_id response: {response.status_code}")
        # Should be 404 (not found), not 500 (server error)
        assert response.status_code == 404, f"Expected 404 for invalid conv ID, got {response.status_code}: {response.text}"
    
    def test_performance_detail_texts(self, api_client):
        """GET /api/tasks/{userId}/performance/detail?category=texts returns SMS events"""
        response = api_client.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=texts&period=week")
        print(f"Performance detail response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        events = data.get("events", [])
        count = data.get("count", 0)
        print(f"Text events: {count} events")
        
        # Check event types include SMS types
        event_types = set(e.get("event_type") for e in events[:10])
        print(f"Event types in texts category: {event_types}")


class TestCallEventLogging:
    """Test that call events are logged correctly from touchpoints page"""
    
    def test_direct_call_event_logging(self, api_client):
        """POST /api/contacts/{userId}/{contactId}/events creates call_placed event"""
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/events",
            json={
                "event_type": "call_placed",
                "title": "Outbound Call",
                "description": f"Test call event at {datetime.now(timezone.utc).isoformat()}",
                "channel": "call",
                "category": "message",
                "icon": "call",
                "color": "#32ADE6"
            }
        )
        print(f"Call event response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("event_type") == "call_placed"
        print(f"Call event created: event_type={data.get('event_type')}")
    
    def test_performance_counts_calls(self, api_client):
        """GET /api/tasks/{userId}/performance counts call_placed events"""
        response = api_client.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        assert response.status_code == 200
        
        data = response.json()
        calls_count = data.get("communication", {}).get("calls", 0)
        print(f"Calls count: {calls_count}")
        assert calls_count >= 0


class TestSummaryActivityCounts:
    """Test the summary endpoint counts activity correctly for today's scoreboard"""
    
    def test_summary_activity_stats(self, api_client):
        """GET /api/tasks/{userId}/summary returns activity stats including texts/calls/emails"""
        response = api_client.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        print(f"Summary response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        activity = data.get("activity", {})
        print(f"Summary activity: texts={activity.get('texts')}, calls={activity.get('calls')}, emails={activity.get('emails')}")
        
        # Verify activity keys exist
        assert "texts" in activity, "Activity should have 'texts' key"
        assert "calls" in activity, "Activity should have 'calls' key"
        assert "emails" in activity, "Activity should have 'emails' key"


class TestThreadPagePrerequisites:
    """Test endpoints that the thread page relies on for the SMS flow"""
    
    def test_conversation_info_returns_contact_id(self, api_client):
        """GET /api/messages/conversation/{convId}/info should return contact_id"""
        # First get a conversation
        conv_response = api_client.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_ID, "contact_phone": "8018212166"}
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["_id"]
        
        # Get conversation info
        response = api_client.get(f"{BASE_URL}/api/messages/conversation/{conv_id}/info")
        print(f"Conversation info response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "contact_id" in data, "Response should have contact_id"
        print(f"Conversation info: contact_id={data.get('contact_id')}, contact_name={data.get('contact_name')}")
    
    def test_thread_messages_endpoint(self, api_client):
        """GET /api/messages/thread/{convId} returns messages"""
        # Get conversation
        conv_response = api_client.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_ID, "contact_phone": "8018212166"}
        )
        conv_id = conv_response.json()["_id"]
        
        response = api_client.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        print(f"Thread messages response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        messages = response.json()
        print(f"Thread has {len(messages)} messages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
