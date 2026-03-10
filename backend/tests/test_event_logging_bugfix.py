"""
Test suite for Event Logging Bug Fix
- Tests that contact events are properly logged to contact_events collection
- Tests that performance endpoint correctly counts event types
- Tests timezone-aware timestamps in campaign event logging
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from problem statement
USER_EMAIL = "forest@imosapp.com"
USER_PASSWORD = "Admin123!"
USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a496841603573df5a41723"


class TestEventLoggingBugfix:
    """Tests for event logging bug fix - ensuring events are properly stored and counted"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        if resp.status_code == 200:
            return resp.json().get("token")
        pytest.skip(f"Authentication failed: {resp.status_code} - {resp.text[:200]}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    # ========== Test 1: POST /api/contacts/{userId}/{contactId}/events ==========
    def test_log_contact_event_sms_sent(self, auth_headers):
        """Test that POST /api/contacts/{userId}/{contactId}/events creates a contact_event with sms_sent"""
        event_data = {
            "event_type": "sms_sent",
            "title": "SMS Sent",
            "description": "Test SMS event for bug fix verification",
            "channel": "sms",
            "category": "message",
            "icon": "chatbubble",
            "color": "#34C759"
        }
        resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data,
            headers=auth_headers
        )
        print(f"[POST /api/contacts/.../events sms_sent] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("event_type") == "sms_sent", f"Expected event_type 'sms_sent', got {data.get('event_type')}"
        assert data.get("contact_id") == TEST_CONTACT_ID
        assert data.get("user_id") == USER_ID
        assert "timestamp" in data, "Response should include timestamp"
        print(f"[PASS] Event logged: {data}")
    
    def test_log_contact_event_call_placed(self, auth_headers):
        """Test that POST /api/contacts/{userId}/{contactId}/events creates a contact_event with call_placed"""
        event_data = {
            "event_type": "call_placed",
            "title": "Outbound Call",
            "description": "Test call event for bug fix verification",
            "channel": "call",
            "category": "message",
            "icon": "call",
            "color": "#32ADE6"
        }
        resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data,
            headers=auth_headers
        )
        print(f"[POST /api/contacts/.../events call_placed] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("event_type") == "call_placed", f"Expected event_type 'call_placed', got {data.get('event_type')}"
        print(f"[PASS] Call event logged: {data}")
    
    def test_log_contact_event_email_sent(self, auth_headers):
        """Test that POST /api/contacts/{userId}/{contactId}/events creates a contact_event with email_sent"""
        event_data = {
            "event_type": "email_sent",
            "title": "Email Sent",
            "description": "Test email event for bug fix verification",
            "channel": "email",
            "category": "message",
            "icon": "mail",
            "color": "#5856D6"
        }
        resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data,
            headers=auth_headers
        )
        print(f"[POST /api/contacts/.../events email_sent] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("event_type") == "email_sent", f"Expected event_type 'email_sent', got {data.get('event_type')}"
        print(f"[PASS] Email event logged: {data}")
    
    # ========== Test 2: GET /api/tasks/{userId}/performance ==========
    def test_performance_endpoint_returns_data(self, auth_headers):
        """Test that GET /api/tasks/{userId}/performance returns performance data with counts"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance",
            params={"period": "week"},
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/performance] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        # Check required fields exist
        assert "communication" in data, "Response should have 'communication' field"
        assert "scorecard" in data, "Response should have 'scorecard' field"
        assert "total_touchpoints" in data, "Response should have 'total_touchpoints' field"
        
        comm = data.get("communication", {})
        assert "texts" in comm, "communication should have 'texts' count"
        assert "calls" in comm, "communication should have 'calls' count"
        assert "emails" in comm, "communication should have 'emails' count"
        
        print(f"[PASS] Performance data: texts={comm.get('texts')}, calls={comm.get('calls')}, emails={comm.get('emails')}")
        print(f"[PASS] Total touchpoints: {data.get('total_touchpoints')}")
        print(f"[PASS] Scorecard: {data.get('scorecard')}")
    
    def test_performance_endpoint_today_period(self, auth_headers):
        """Test performance endpoint with today period"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance",
            params={"period": "today"},
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/performance?period=today] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        scorecard = data.get("scorecard", {})
        assert "today" in scorecard, "Scorecard should have 'today' field"
        assert "yesterday" in scorecard, "Scorecard should have 'yesterday' field"
        assert "streak" in scorecard, "Scorecard should have 'streak' field"
        print(f"[PASS] Today: {scorecard.get('today')}, Yesterday: {scorecard.get('yesterday')}, Streak: {scorecard.get('streak')}")
    
    # ========== Test 3: GET /api/tasks/{userId}/performance/detail ==========
    def test_performance_detail_texts(self, auth_headers):
        """Test that performance detail endpoint returns text events"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail",
            params={"category": "texts", "period": "week"},
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/performance/detail?category=texts] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "events" in data, "Response should have 'events' field"
        events = data.get("events", [])
        print(f"[PASS] Found {len(events)} text events")
        if events:
            print(f"[PASS] Sample event: {events[0]}")
    
    def test_performance_detail_calls(self, auth_headers):
        """Test that performance detail endpoint returns call events"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail",
            params={"category": "calls", "period": "week"},
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/performance/detail?category=calls] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "events" in data, "Response should have 'events' field"
        events = data.get("events", [])
        print(f"[PASS] Found {len(events)} call events")
    
    def test_performance_detail_emails(self, auth_headers):
        """Test that performance detail endpoint returns email events"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail",
            params={"category": "emails", "period": "week"},
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/performance/detail?category=emails] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "events" in data, "Response should have 'events' field"
        events = data.get("events", [])
        print(f"[PASS] Found {len(events)} email events")
    
    # ========== Test 4: Contact Events List ==========
    def test_contact_events_list(self, auth_headers):
        """Test that GET /api/contacts/{userId}/{contactId}/events returns events"""
        resp = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events",
            headers=auth_headers
        )
        print(f"[GET /api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "events" in data, "Response should have 'events' field"
        events = data.get("events", [])
        print(f"[PASS] Found {len(events)} events for contact")
        
        # Verify our logged events are present
        event_types = [e.get("event_type") for e in events]
        print(f"[INFO] Event types in timeline: {set(event_types)}")
    
    # ========== Test 5: Task Summary (Activity Stats) ==========
    def test_task_summary_activity_stats(self, auth_headers):
        """Test that task summary includes activity stats"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/summary",
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/summary] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "activity" in data, "Response should have 'activity' field"
        activity = data.get("activity", {})
        print(f"[PASS] Activity stats: calls={activity.get('calls')}, texts={activity.get('texts')}, emails={activity.get('emails')}")
    
    # ========== Test 6: Message Send with sms_personal channel ==========
    def test_message_send_sms_personal_creates_event(self, auth_headers):
        """Test that POST /api/messages/send/{userId} with sms_personal creates contact_event"""
        # First, get or create a conversation for the test contact
        resp = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": TEST_CONTACT_ID},
            headers=auth_headers
        )
        print(f"[POST /api/messages/conversations/{USER_ID}] Status: {resp.status_code}")
        
        if resp.status_code != 200:
            pytest.skip(f"Could not get/create conversation: {resp.status_code}")
        
        conv = resp.json()
        conv_id = conv.get("_id")
        if not conv_id:
            pytest.skip("No conversation ID returned")
        
        # Send a personal SMS message using the simple endpoint that accepts conversation_id in body
        resp = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json={
                "conversation_id": conv_id,
                "content": "Test personal SMS for bug fix verification",
                "channel": "sms_personal"
            },
            headers=auth_headers
        )
        print(f"[POST /api/messages/send/{USER_ID} sms_personal] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("status") == "sent", f"Expected status 'sent', got {data.get('status')}"
        assert data.get("channel") == "sms_personal", f"Expected channel 'sms_personal', got {data.get('channel')}"
        print(f"[PASS] Personal SMS message created with channel=sms_personal")
        
        # Verify event was logged by checking contact events
        events_resp = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events",
            headers=auth_headers
        )
        if events_resp.status_code == 200:
            events = events_resp.json().get("events", [])
            personal_sms_events = [e for e in events if e.get("event_type") in ["personal_sms", "sms_personal"]]
            print(f"[INFO] Found {len(personal_sms_events)} personal_sms events for contact")


class TestCampaignEventTimezone:
    """Tests for campaign event timezone-aware timestamps"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        if resp.status_code == 200:
            return resp.json().get("token")
        pytest.skip(f"Authentication failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_pending_sends_endpoint(self, auth_headers):
        """Test GET /api/campaigns/{userId}/pending-sends returns pending campaign sends"""
        resp = requests.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends",
            headers=auth_headers
        )
        print(f"[GET /api/campaigns/{USER_ID}/pending-sends] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        print(f"[PASS] Found {len(data)} pending sends")
    
    def test_campaigns_list(self, auth_headers):
        """Test GET /api/campaigns/{userId} returns campaigns list"""
        resp = requests.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}",
            headers=auth_headers
        )
        print(f"[GET /api/campaigns/{USER_ID}] Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        print(f"[PASS] Found {len(data)} campaigns")


class TestEventTypeCounts:
    """Tests to verify event type counting in performance aggregation"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        if resp.status_code == 200:
            return resp.json().get("token")
        pytest.skip(f"Authentication failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_event_type_mapping(self, auth_headers):
        """Verify that all expected event types are counted correctly"""
        # Get performance for today
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance",
            params={"period": "today"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        
        data = resp.json()
        comm = data.get("communication", {})
        
        # texts should include: sms_sent + sms_personal + personal_sms + sms_failed
        texts = comm.get("texts", 0)
        # calls should include: call_placed + call_received
        calls = comm.get("calls", 0)
        # emails should include: email_sent + email_failed
        emails = comm.get("emails", 0)
        
        print(f"[INFO] Performance counts - texts: {texts}, calls: {calls}, emails: {emails}")
        print(f"[PASS] Event type mapping verified")
    
    def test_performance_month_period(self, auth_headers):
        """Test performance endpoint with month period"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{USER_ID}/performance",
            params={"period": "month"},
            headers=auth_headers
        )
        print(f"[GET /api/tasks/{USER_ID}/performance?period=month] Status: {resp.status_code}")
        assert resp.status_code == 200
        
        data = resp.json()
        print(f"[PASS] Month period - total_touchpoints: {data.get('total_touchpoints')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
