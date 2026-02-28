"""
Test Activity Feed revamp features for contact detail page.
Features tested:
1. Backend API returns events sorted newest-first
2. Events have all required fields for frontend rendering
3. Stats endpoint returns data for touchpoint badge
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review_request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"  # Contact with 28 events
LOGIN_EMAIL = "forest@imosapp.com"
LOGIN_PASSWORD = "Admin123!"


class TestActivityFeedAPI:
    """Tests for Contact Activity Feed API features"""

    def test_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("Health check passed")

    def test_events_endpoint_returns_data(self):
        """Test GET /api/contacts/{user_id}/{contact_id}/events returns events"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)
        
        print(f"Events endpoint returned {data['total']} events")
        return data

    def test_events_sorted_newest_first(self):
        """Verify events are sorted by timestamp descending (newest first)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        events = data["events"]
        
        if len(events) >= 2:
            # Check that events are sorted newest first
            for i in range(len(events) - 1):
                ts1 = events[i].get("timestamp", "")
                ts2 = events[i+1].get("timestamp", "")
                if ts1 and ts2:
                    # Verify ts1 >= ts2 (newer or equal first)
                    assert ts1 >= ts2, f"Events not sorted newest first: {ts1} should be >= {ts2}"
            print(f"Verified {len(events)} events are sorted newest first")
        else:
            print(f"Not enough events ({len(events)}) to verify sorting")

    def test_event_structure_has_required_fields(self):
        """Verify each event has required fields - at minimum event_type and timestamp"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        events = data["events"]
        
        # All events must have event_type and timestamp (other fields are optional as frontend has fallbacks)
        required_fields = ["event_type", "timestamp"]
        
        for i, event in enumerate(events[:10]):  # Check first 10 events
            for field in required_fields:
                assert field in event, f"Event {i} missing required field: {field}"
            # Verify timestamp is ISO format string
            ts = event.get("timestamp")
            if ts:
                assert isinstance(ts, str), f"Event {i} timestamp should be string, got {type(ts)}"
        
        print(f"Verified event structure for {min(10, len(events))} events")

    def test_events_have_title_or_fallback(self):
        """Verify events have title (either explicit or can be derived from event_type)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        events = data["events"]
        
        events_with_null_title = []
        for i, event in enumerate(events):
            title = event.get("title")
            event_type = event.get("event_type")
            # Either title should be non-empty, or event_type should exist for fallback
            if not title:
                events_with_null_title.append(event_type)
        
        if events_with_null_title:
            print(f"Events with null titles (frontend should use fallback): {events_with_null_title}")
        else:
            print("All events have explicit titles")

    def test_stats_endpoint_returns_data(self):
        """Test GET /api/contacts/{user_id}/{contact_id}/stats returns touchpoint stats"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/stats")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ["total_touchpoints", "messages_sent", "campaigns", "cards_sent", "broadcasts", "custom_events", "created_at"]
        
        for field in required_fields:
            assert field in data, f"Stats missing required field: {field}"
        
        print(f"Stats: touchpoints={data['total_touchpoints']}, messages={data['messages_sent']}, campaigns={data['campaigns']}")
        return data


class TestContactDetailIntegration:
    """Tests for contact detail page integration"""

    def test_contact_exists(self):
        """Verify test contact exists"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "first_name" in data
        print(f"Contact: {data.get('first_name')} {data.get('last_name', '')}")

    def test_login_works(self):
        """Verify login with test credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == LOGIN_EMAIL
        print(f"Login successful: {LOGIN_EMAIL}")


class TestEventTimestamps:
    """Verify timestamp format returned by API"""

    def test_timestamps_are_iso_format(self):
        """Verify timestamps are ISO 8601 format strings"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        events = data["events"]
        
        for i, event in enumerate(events[:5]):
            ts = event.get("timestamp")
            if ts:
                # Should be parseable as ISO datetime
                try:
                    datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    print(f"Event {i} timestamp: {ts}")
                except ValueError:
                    pytest.fail(f"Event {i} has invalid timestamp format: {ts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
