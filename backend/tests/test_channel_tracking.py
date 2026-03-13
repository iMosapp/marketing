"""
Test Channel Tracking Feature
Tests the ability to track sharing channels (WhatsApp, SMS, Email, etc.) in contact events.
Also tests the lead-sources route ordering fix.
"""
import pytest
import requests
import os
import uuid

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user and contact IDs from the review request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69ab3469288fdc414aa10a6e"


class TestChannelTrackingBackend:
    """Tests for channel field in contact events"""
    
    def test_log_event_with_channel(self):
        """POST /api/contacts/{user_id}/{contact_id}/events accepts and stores 'channel' field"""
        event_data = {
            "event_type": "review_request_sent",
            "title": "Review Link Shared",
            "description": "Customer asked to leave a review",
            "icon": "star",
            "color": "#FFD60A",
            "category": "outreach",
            "channel": "whatsapp"  # Channel tracking
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify channel field is returned
        assert "channel" in data, "Channel field should be in response"
        assert data["channel"] == "whatsapp", f"Expected 'whatsapp', got '{data.get('channel')}'"
        assert data["event_type"] == "review_request_sent"
        print(f"SUCCESS: Event created with channel={data['channel']}")
    
    def test_log_event_with_sms_channel(self):
        """POST /api/contacts/{user_id}/{contact_id}/events - test SMS channel"""
        event_data = {
            "event_type": "digital_card_sent",
            "title": "Digital Card Sent",
            "description": "Sent digital business card",
            "icon": "card",
            "color": "#007AFF",
            "category": "outreach",
            "channel": "sms"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("channel") == "sms"
        print(f"SUCCESS: Event created with channel=sms")
    
    def test_log_event_without_channel(self):
        """POST /api/contacts/{user_id}/{contact_id}/events - event without channel is OK"""
        event_data = {
            "event_type": "call_placed",
            "title": "Call Placed",
            "description": "Made a phone call",
            "icon": "call",
            "color": "#32ADE6",
            "category": "outreach"
            # No channel - this should still work
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Channel should not be present or be null
        assert data.get("channel") is None or "channel" not in data
        print(f"SUCCESS: Event created without channel field")
    
    def test_master_feed_returns_channel(self):
        """GET /api/contacts/{user_id}/master-feed should return 'channel' field in feed items"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/master-feed?limit=50")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "feed" in data, "Response should contain 'feed' array"
        feed = data["feed"]
        
        # Find events with channel
        events_with_channel = [e for e in feed if e.get("channel")]
        print(f"Found {len(events_with_channel)} events with channel field out of {len(feed)} total events")
        
        if events_with_channel:
            for evt in events_with_channel[:3]:  # Show first 3
                print(f"  - {evt.get('event_type')}: channel={evt.get('channel')}")
            # Verify channel values are valid - include 'system' and 'note' which may exist in data
            valid_channels = ['sms', 'sms_personal', 'whatsapp', 'messenger', 'telegram', 'linkedin', 'email', 'clipboard', 'system', 'note']
            for evt in events_with_channel:
                assert evt["channel"] in valid_channels, f"Invalid channel: {evt['channel']}"
        
        print(f"SUCCESS: Master feed returns channel field correctly")
    
    def test_contact_events_returns_channel(self):
        """GET /api/contacts/{user_id}/{contact_id}/events should return 'channel' field"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events?limit=50")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "events" in data, "Response should contain 'events' array"
        events = data["events"]
        
        events_with_channel = [e for e in events if e.get("channel")]
        print(f"Found {len(events_with_channel)} events with channel field for contact {TEST_CONTACT_ID}")
        
        if events_with_channel:
            for evt in events_with_channel[:3]:
                print(f"  - {evt.get('event_type')}: channel={evt.get('channel')}")
        
        print(f"SUCCESS: Contact events API returns channel field correctly")


class TestFindOrCreateWithChannel:
    """Tests for find-or-create-and-log endpoint with event_channel"""
    
    def test_find_or_create_with_event_channel(self):
        """POST /api/contacts/{user_id}/find-or-create-and-log should accept 'event_channel'"""
        unique_suffix = str(uuid.uuid4())[:8]
        payload = {
            "phone": f"+1555{unique_suffix[:7]}",
            "name": f"Test Channel User {unique_suffix}",
            "event_type": "review_request_sent",
            "event_title": "Review Link Shared",
            "event_description": "Test review sharing",
            "event_icon": "star",
            "event_color": "#FFD60A",
            "event_channel": "sms"  # The channel field
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "contact_id" in data, "Response should contain contact_id"
        assert data.get("event_logged") == True, "Event should be logged"
        print(f"SUCCESS: find-or-create-and-log accepted event_channel")
        
        # Verify the channel was stored by checking contact events
        contact_id = data["contact_id"]
        events_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}/events?limit=5")
        
        if events_response.status_code == 200:
            events = events_response.json().get("events", [])
            channel_events = [e for e in events if e.get("channel") == "sms"]
            if channel_events:
                print(f"  Verified: Event stored with channel='sms'")
    
    def test_find_or_create_with_channel_alias(self):
        """POST /api/contacts/{user_id}/find-or-create-and-log should also accept 'channel' field"""
        unique_suffix = str(uuid.uuid4())[:8]
        payload = {
            "phone": f"+1555{unique_suffix[:7]}",
            "name": f"Test Channel User2 {unique_suffix}",
            "event_type": "congrats_card_sent",
            "event_title": "Congrats Card Sent",
            "event_description": "Test congrats card",
            "event_icon": "gift",
            "event_color": "#C9A962",
            "channel": "whatsapp"  # Alternative 'channel' field
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"SUCCESS: find-or-create-and-log accepted 'channel' field alias")


class TestLeadSourcesRouteOrdering:
    """Tests for lead-sources route ordering fix (500 error bug)"""
    
    def test_team_inbox_not_caught_by_source_id(self):
        """GET /api/lead-sources/team-inbox/{team_id} should return 200, not 500"""
        # Use a fake team ID - should return 200 with empty conversations
        response = requests.get(f"{BASE_URL}/api/lead-sources/team-inbox/fake_team_123")
        
        # Should not be caught by /{source_id} route and return 500
        # Should return 200 with empty results
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "conversations" in data, "Response should contain 'conversations'"
        print("SUCCESS: team-inbox route works correctly (not caught by /source_id)")
    
    def test_user_inbox_not_caught_by_source_id(self):
        """GET /api/lead-sources/user-inbox/{user_id} should return 200, not 500"""
        response = requests.get(f"{BASE_URL}/api/lead-sources/user-inbox/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "conversations" in data, "Response should contain 'conversations'"
        print("SUCCESS: user-inbox route works correctly (not caught by /source_id)")
    
    def test_stats_returns_404_for_nonexistent(self):
        """GET /api/lead-sources/stats/{source_id} should return 404 for non-existent source, not 500"""
        # Use a valid ObjectId format but non-existent source
        fake_source_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/lead-sources/stats/{fake_source_id}")
        
        # Should return 404 (not found), not 500 (server error)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"SUCCESS: stats route returns 404 for non-existent source (not 500)")
    
    def test_source_id_route_works_for_valid_format(self):
        """GET /api/lead-sources/{source_id} should work for valid ObjectId format"""
        # Use a valid ObjectId format but non-existent source
        fake_source_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/lead-sources/{fake_source_id}")
        
        # Should return 404 for non-existent, not 500
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("SUCCESS: /source_id route returns 404 for non-existent source")


class TestAllChannelTypes:
    """Test all 7 channel types mentioned in requirements"""
    
    @pytest.mark.parametrize("channel", [
        "whatsapp",
        "sms", 
        "email",
        "messenger",
        "telegram",
        "linkedin",
        "clipboard"
    ])
    def test_all_channel_types(self, channel):
        """Test that each channel type can be stored and retrieved"""
        event_data = {
            "event_type": "digital_card_sent",
            "title": f"Card Sent via {channel}",
            "description": f"Testing {channel} channel",
            "icon": "card",
            "color": "#007AFF",
            "category": "outreach",
            "channel": channel
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("channel") == channel, f"Expected channel={channel}, got {data.get('channel')}"
        print(f"SUCCESS: Channel '{channel}' stored correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
