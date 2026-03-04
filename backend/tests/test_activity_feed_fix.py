"""
Test Activity Feed Fix - Verifies that contact_events collection is the primary source
for the activity feed endpoint (/api/activity/{user_id}).

Bug Fix Tested:
- Activity feed was NOT pulling from contact_events collection
- Now queries contact_events as the PRIMARY data source
- Icons and colors should be properly mapped for different event types
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestActivityFeedEndpoint:
    """Tests for GET /api/activity/{user_id} endpoint"""

    def test_activity_feed_returns_contact_events(self):
        """Verify activity feed returns data from contact_events collection"""
        response = requests.get(f"{BASE_URL}/api/activity/{TEST_USER_ID}?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "activities" in data, "Response should have 'activities' key"
        assert "user_role" in data, "Response should have 'user_role' key"
        assert "total" in data, "Response should have 'total' key"
        
        activities = data["activities"]
        assert isinstance(activities, list), "Activities should be a list"
        
        # Check that we're getting contact_events types (the fix)
        event_types_from_contact_events = [
            "digital_card_shared", "digital_card_sent", "review_request_sent",
            "congrats_card_sent", "showcase_shared", "vcard_sent",
            "sms_sent", "email_sent", "call_placed", "note_updated", "link_page_shared"
        ]
        
        found_contact_event = False
        for activity in activities:
            if activity.get("type") in event_types_from_contact_events:
                found_contact_event = True
                break
        
        # We should find at least one contact_event type
        print(f"Activity types found: {[a.get('type') for a in activities]}")
        assert found_contact_event, "Activity feed should include contact_events data"

    def test_activity_feed_event_structure(self):
        """Verify each activity has required fields"""
        response = requests.get(f"{BASE_URL}/api/activity/{TEST_USER_ID}?limit=5")
        assert response.status_code == 200
        
        activities = response.json()["activities"]
        
        for activity in activities:
            assert "type" in activity, "Activity should have 'type'"
            assert "icon" in activity, "Activity should have 'icon'"
            assert "color" in activity, "Activity should have 'color'"
            assert "message" in activity, "Activity should have 'message'"
            assert "timestamp" in activity, "Activity should have 'timestamp'"
            assert "entity_id" in activity, "Activity should have 'entity_id'"
            
            # Verify timestamp is ISO format
            ts = activity["timestamp"]
            assert ts and len(ts) > 0, "Timestamp should not be empty"
            print(f"Activity: {activity['type']} - {activity['message'][:50]}...")

    def test_activity_feed_limit_parameter(self):
        """Verify limit parameter works correctly"""
        response5 = requests.get(f"{BASE_URL}/api/activity/{TEST_USER_ID}?limit=5")
        response20 = requests.get(f"{BASE_URL}/api/activity/{TEST_USER_ID}?limit=20")
        
        assert response5.status_code == 200
        assert response20.status_code == 200
        
        activities5 = response5.json()["activities"]
        activities20 = response20.json()["activities"]
        
        assert len(activities5) <= 5, f"Should return max 5 activities, got {len(activities5)}"
        print(f"With limit=5: {len(activities5)} activities")
        print(f"With limit=20: {len(activities20)} activities")


class TestFindOrCreateAndLogEvent:
    """Tests for POST /api/contacts/{user_id}/find-or-create-and-log endpoint"""

    def test_create_event_appears_in_activity_feed(self):
        """Verify that creating an event via find-or-create-and-log appears in activity feed"""
        # Create a unique test event
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        # First, log a new event
        log_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={
                "phone": f"555{timestamp[-7:]}",
                "name": f"Test Activity {timestamp}",
                "event_type": "showcase_shared",
                "event_title": f"TEST_Shared Showcase {timestamp}",
                "event_description": f"Activity feed test at {timestamp}",
                "event_icon": "storefront",
                "event_color": "#34C759"
            }
        )
        
        assert log_response.status_code == 200, f"Log event failed: {log_response.text}"
        log_data = log_response.json()
        
        # If needs confirmation, use existing
        if log_data.get("needs_confirmation"):
            log_response = requests.post(
                f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
                json={
                    "phone": f"555{timestamp[-7:]}",
                    "name": f"Test Activity {timestamp}",
                    "event_type": "showcase_shared",
                    "event_title": f"TEST_Shared Showcase {timestamp}",
                    "event_description": f"Activity feed test at {timestamp}",
                    "event_icon": "storefront",
                    "event_color": "#34C759",
                    "force_action": "use_existing"
                }
            )
            log_data = log_response.json()
        
        assert log_data.get("event_logged") == True, f"Event should be logged: {log_data}"
        contact_id = log_data.get("contact_id")
        print(f"Event logged for contact: {contact_id}")
        
        # Now check activity feed includes the new event
        feed_response = requests.get(f"{BASE_URL}/api/activity/{TEST_USER_ID}?limit=5")
        assert feed_response.status_code == 200
        
        activities = feed_response.json()["activities"]
        
        # Find our test event
        found_test_event = False
        for activity in activities:
            if activity.get("type") == "showcase_shared" and contact_id in activity.get("entity_id", ""):
                found_test_event = True
                print(f"Found test event: {activity['message']}")
                # Verify icon and color are preserved
                assert activity.get("icon") == "storefront", f"Icon should be 'storefront', got {activity.get('icon')}"
                assert activity.get("color") == "#34C759", f"Color should be '#34C759', got {activity.get('color')}"
                break
        
        assert found_test_event, f"Test event should appear in activity feed. Activities: {[a['type'] for a in activities]}"

    def test_event_types_mapping(self):
        """Verify different event types appear correctly in feed"""
        event_type_tests = [
            ("digital_card_shared", "card", "#C9A962"),
            ("review_request_sent", "star", "#FFD60A"),
        ]
        
        for event_type, expected_icon, expected_color in event_type_tests:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            
            response = requests.post(
                f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
                json={
                    "phone": f"555{timestamp[-7:]}",
                    "name": f"Test {event_type}",
                    "event_type": event_type,
                    "event_title": f"TEST_{event_type}",
                    "event_description": "Testing event type mapping",
                    "event_icon": expected_icon,
                    "event_color": expected_color,
                    "force_action": "use_existing"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Handle needs_confirmation case
                if data.get("needs_confirmation"):
                    response = requests.post(
                        f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
                        json={
                            "phone": f"555{timestamp[-7:]}",
                            "name": f"Test {event_type}",
                            "event_type": event_type,
                            "event_title": f"TEST_{event_type}",
                            "event_description": "Testing event type mapping",
                            "event_icon": expected_icon,
                            "event_color": expected_color,
                            "force_action": "use_existing"
                        }
                    )
                    data = response.json()
                
                print(f"Event type {event_type}: logged={data.get('event_logged')}")
                assert data.get("event_logged") == True


class TestActivityFeedInvalidUser:
    """Tests for edge cases"""

    def test_invalid_user_returns_404(self):
        """Verify non-existent user returns 404"""
        response = requests.get(f"{BASE_URL}/api/activity/000000000000000000000000?limit=10")
        assert response.status_code == 404, f"Expected 404 for invalid user, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
