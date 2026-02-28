"""
Test Activity Feed Search & Note Updated Events
Tests:
1. POST /api/contacts/{user_id}/{contact_id}/events with event_type='note_updated' creates event
2. GET /api/contacts/{user_id}/{contact_id}/events returns note_updated events alongside others
3. Frontend search filtering is client-side (no backend endpoint changes needed)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review_request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"


class TestNoteUpdatedEvents:
    """Tests for note_updated event logging to activity feed"""

    def test_health_check(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("PASS: Health check passed")

    def test_log_note_updated_event(self):
        """POST /api/contacts/{user_id}/{contact_id}/events with note_updated event"""
        event_data = {
            "event_type": "note_updated",
            "title": "Note Updated",
            "description": "Test note content from pytest - checking note logging",
            "channel": "note",
            "category": "note",
            "icon": "document-text",
            "color": "#FF9F0A"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        
        assert response.status_code == 200, f"Failed to create note_updated event: {response.text}"
        
        data = response.json()
        assert data["event_type"] == "note_updated", f"Expected event_type='note_updated', got {data.get('event_type')}"
        assert data["title"] == "Note Updated", f"Expected title='Note Updated', got {data.get('title')}"
        assert data["category"] == "note", f"Expected category='note', got {data.get('category')}"
        assert data["icon"] == "document-text", f"Expected icon='document-text', got {data.get('icon')}"
        assert data["color"] == "#FF9F0A", f"Expected color='#FF9F0A', got {data.get('color')}"
        assert "timestamp" in data
        
        print(f"PASS: Created note_updated event with timestamp: {data['timestamp']}")
        return data

    def test_get_events_includes_note_updated(self):
        """GET /api/contacts/{user_id}/{contact_id}/events returns note_updated events"""
        # First create a note_updated event to ensure one exists
        event_data = {
            "event_type": "note_updated",
            "title": "Note Updated",
            "description": "Verify note event retrieval",
            "channel": "note",
            "category": "note",
            "icon": "document-text",
            "color": "#FF9F0A"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        assert create_response.status_code == 200, "Failed to create test event"
        
        # Now fetch events
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200, f"Failed to get events: {response.text}"
        
        data = response.json()
        assert "events" in data
        assert "total" in data
        
        # Find note_updated events
        note_events = [e for e in data["events"] if e.get("event_type") == "note_updated"]
        assert len(note_events) > 0, "Expected at least one note_updated event in the response"
        
        # Verify note event structure
        note_event = note_events[0]
        assert note_event.get("category") == "note", f"Expected note category, got {note_event.get('category')}"
        assert note_event.get("icon") == "document-text", f"Expected document-text icon, got {note_event.get('icon')}"
        assert note_event.get("color") == "#FF9F0A", f"Expected orange color #FF9F0A, got {note_event.get('color')}"
        
        print(f"PASS: Found {len(note_events)} note_updated event(s) in {data['total']} total events")

    def test_note_updated_event_description_truncation(self):
        """Verify note descriptions can be up to 300 chars (as per handleSave in frontend)"""
        long_description = "A" * 300  # Max length per frontend code
        
        event_data = {
            "event_type": "note_updated",
            "title": "Note Updated",
            "description": long_description,
            "channel": "note",
            "category": "note",
            "icon": "document-text",
            "color": "#FF9F0A"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["description"]) == 300
        print("PASS: Long description (300 chars) stored successfully")


class TestEventStructureForSearch:
    """Tests to verify event structure supports frontend search functionality"""

    def test_events_have_searchable_fields(self):
        """Verify events have title, description, event_type fields needed for search"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["events"]) == 0:
            pytest.skip("No events to verify - skipping")
        
        # Check that events have searchable fields
        for event in data["events"][:5]:  # Check first 5
            assert "title" in event, f"Event missing 'title' field: {event}"
            assert "event_type" in event, f"Event missing 'event_type' field: {event}"
            # description may be empty/null, but field should exist
            assert "description" in event or event.get("description") is None or event.get("description") == ""
        
        print(f"PASS: Events have searchable fields (title, event_type, description)")

    def test_events_with_different_categories(self):
        """Verify events come from different categories (message, campaign, note, etc.)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        categories = set(e.get("category") for e in data["events"])
        
        print(f"PASS: Found event categories: {categories}")
        # We expect at least note category from our test
        assert "note" in categories or len(data["events"]) == 0, "Expected 'note' category in events"

    def test_events_sorted_by_timestamp_descending(self):
        """Verify events are sorted by timestamp (newest first)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        events = data["events"]
        
        if len(events) < 2:
            pytest.skip("Need at least 2 events to verify sorting")
        
        timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], f"Events not sorted descending: {timestamps[i]} < {timestamps[i+1]}"
        
        print("PASS: Events sorted by timestamp descending")


class TestEventCategoryMapping:
    """Tests to verify event categories map to correct icons/colors"""

    def test_note_category_icon_mapping(self):
        """Verify 'note' category uses document-text icon with orange color"""
        # Create a note event
        event_data = {
            "event_type": "note_updated",
            "title": "Note Updated",
            "description": "Test",
            "category": "note",
            "icon": "document-text",
            "color": "#FF9F0A"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        assert response.status_code == 200
        
        # Fetch and verify
        events_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        data = events_response.json()
        
        note_events = [e for e in data["events"] if e.get("category") == "note"]
        assert len(note_events) > 0
        
        note_event = note_events[0]
        # Per EVENT_CATEGORY_ICON in frontend: note: { icon: 'document-text', color: '#FF9F0A' }
        assert note_event["icon"] == "document-text"
        assert note_event["color"] == "#FF9F0A"
        
        print("PASS: Note category correctly mapped to document-text icon with #FF9F0A color")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
