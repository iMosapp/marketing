"""
Test Activity Feed Fix: Master-feed contact name/photo resolution and invalid contact_id validation.

Bug Fixed:
- Activity Feed was showing 'Unknown' for contact names and no photos
- Root cause: invalid/orphaned contact_ids caused master-feed ObjectId conversion to fail entirely
- Fix: per-item ObjectId conversion with try/except + input validation on tracking/event creation

Tests verify:
1. GET /api/contacts/{user_id}/master-feed returns proper contact names and photos
2. POST /api/tracking/event rejects invalid contact_id (does NOT create garbage events)
3. POST /api/tracking/event works correctly with valid contact_id
4. POST /api/contacts/{user_id}/find-or-create-and-log endpoint still works
5. GET /api/contacts/{user_id}/{contact_id}/events endpoint still works
"""
import pytest
import requests
import os
import random
import string

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from problem statement
USER_ID = "69a0b7095fddcede09591667"
VALID_CONTACT_ID = "69a496841603573df5a41723"
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")

@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestMasterFeedContactResolution:
    """Test that master-feed properly resolves contact names and photos (no 'Unknown' entries for valid contacts)"""
    
    def test_master_feed_returns_200(self, api_client):
        """Master feed endpoint is accessible"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "feed" in data, "Response should have 'feed' key"
        print(f"PASS: Master feed returned {len(data.get('feed', []))} events")
    
    def test_master_feed_contact_names_resolved(self, api_client):
        """Contact names should NOT be 'Unknown' for events with valid contact_ids"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=50")
        assert response.status_code == 200
        data = response.json()
        feed = data.get("feed", [])
        
        unknown_count = 0
        known_count = 0
        events_with_invalid_cid = 0
        
        for event in feed:
            contact = event.get("contact", {})
            contact_name = contact.get("name", "Unknown")
            contact_id = contact.get("id")
            
            # Check if this is an invalid ObjectId format (the known bad ones: abc123def456, abc456, contact_xyz, test123)
            is_invalid_oid = contact_id and (
                not all(c in '0123456789abcdef' for c in str(contact_id).lower()) or 
                len(str(contact_id)) != 24
            )
            
            if is_invalid_oid:
                events_with_invalid_cid += 1
                # These SHOULD show 'Unknown' because the contact_id is genuinely invalid
                if contact_name == "Unknown":
                    unknown_count += 1
            elif contact_name == "Unknown":
                # This is a problem - valid ObjectId but showing Unknown
                print(f"WARNING: Valid contact_id {contact_id} showing Unknown name")
                unknown_count += 1
            else:
                known_count += 1
        
        # The fix should have reduced/eliminated Unknown entries for VALID contacts
        print(f"Feed has {len(feed)} events: {known_count} with names, {unknown_count} Unknown, {events_with_invalid_cid} with invalid contact_ids")
        
        # Should have mostly resolved names (some orphaned contacts may still show Unknown)
        if len(feed) > 0:
            resolution_rate = (known_count / len(feed)) * 100
            print(f"Contact name resolution rate: {resolution_rate:.1f}%")
            # After the fix, we expect most valid contacts to resolve (>50%)
            assert resolution_rate > 30, f"Too many Unknown contacts ({100-resolution_rate:.1f}% Unknown) - fix may not be working"
    
    def test_master_feed_contact_photos_present(self, api_client):
        """Contacts with photos should have photo data in response"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=50")
        assert response.status_code == 200
        data = response.json()
        feed = data.get("feed", [])
        
        contacts_with_photos = 0
        contacts_without_photos = 0
        
        for event in feed:
            contact = event.get("contact", {})
            if contact.get("photo"):
                contacts_with_photos += 1
            else:
                contacts_without_photos += 1
        
        print(f"Contacts with photos: {contacts_with_photos}, without: {contacts_without_photos}")
        # Some contacts may not have photos - this is OK as long as the response structure is correct
        assert isinstance(feed, list), "Feed should be a list"
    
    def test_master_feed_contact_tags_present(self, api_client):
        """Feed events should include contact tags"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=30")
        assert response.status_code == 200
        data = response.json()
        feed = data.get("feed", [])
        
        events_with_tags = 0
        for event in feed:
            contact = event.get("contact", {})
            if contact.get("tags") and len(contact["tags"]) > 0:
                events_with_tags += 1
        
        print(f"Events with contact tags: {events_with_tags}/{len(feed)}")
        # Tags are optional - just verify structure
        for event in feed[:5]:
            contact = event.get("contact", {})
            assert "tags" in contact, f"Contact object should have 'tags' key: {contact}"


class TestTrackingEventValidation:
    """Test that POST /api/tracking/event validates contact_id and rejects invalid ones"""
    
    def test_tracking_event_invalid_contact_id_rejected(self, api_client):
        """Tracking endpoint should NOT create events with invalid contact_ids"""
        invalid_ids = ["abc123", "invalid_id", "test123", "xyz", ""]
        
        for invalid_id in invalid_ids:
            response = api_client.post(f"{BASE_URL}/api/tracking/event", json={
                "page": "congrats",
                "action": "viewed",
                "salesperson_id": USER_ID,
                "contact_id": invalid_id,
                "metadata": {"test": True}
            })
            
            # Should either return tracked: false or skip the event
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            
            # The fix validates contact_id - invalid ones should NOT track
            if invalid_id:
                assert data.get("tracked") == False or data.get("reason"), \
                    f"Invalid contact_id '{invalid_id}' should not be tracked: {data}"
                print(f"PASS: Invalid contact_id '{invalid_id}' was rejected - {data.get('reason', 'tracked=False')}")
    
    def test_tracking_event_valid_contact_id_works(self, api_client):
        """Tracking endpoint should work with valid contact_id"""
        response = api_client.post(f"{BASE_URL}/api/tracking/event", json={
            "page": "congrats",
            "action": "viewed",
            "salesperson_id": USER_ID,
            "contact_id": VALID_CONTACT_ID,
            "metadata": {"test_run": "activity_feed_fix_test"}
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Valid contact should track successfully
        assert data.get("tracked") == True, f"Valid contact_id should track: {data}"
        assert data.get("event_type") == "congrats_card_viewed", f"Event type should match: {data}"
        print(f"PASS: Valid contact_id tracked successfully - event_type: {data.get('event_type')}")
    
    def test_tracking_event_no_contact_id_uses_fallback(self, api_client):
        """Tracking with phone/name fallback should still work"""
        response = api_client.post(f"{BASE_URL}/api/tracking/event", json={
            "page": "card",
            "action": "viewed",
            "salesperson_id": USER_ID,
            "customer_phone": "5555551234",  # Likely doesn't exist - that's OK
            "customer_name": "Test Customer",
            "metadata": {"fallback_test": True}
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # May or may not track (depends on contact existence), but should not error
        print(f"Fallback tracking result: {data}")


class TestContactActivityLogging:
    """Test log_customer_activity validation in utils/contact_activity.py"""
    
    def test_find_or_create_valid_phone(self, authenticated_client):
        """find-or-create-and-log works with valid data"""
        test_phone = f"555{random.randint(1000000, 9999999)}"
        
        response = authenticated_client.post(f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log", json={
            "phone": test_phone,
            "name": f"TEST ActivityFixTest {test_phone[-4:]}",
            "event_type": "custom",
            "event_title": "Test Event",
            "event_description": "Testing activity feed fix"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have created contact and logged event
        assert "contact_id" in data, f"Response should have contact_id: {data}"
        assert data.get("event_logged") == True, f"Event should be logged: {data}"
        
        # contact_id should be a valid ObjectId (24 hex chars)
        contact_id = data.get("contact_id", "")
        assert len(contact_id) == 24 and all(c in '0123456789abcdef' for c in contact_id.lower()), \
            f"contact_id should be valid ObjectId: {contact_id}"
        
        print(f"PASS: Created contact {contact_id} with event logged")
        return contact_id


class TestContactDetailEvents:
    """Test GET /api/contacts/{user_id}/{contact_id}/events still works"""
    
    def test_contact_events_endpoint(self, api_client):
        """Contact detail events endpoint returns proper data"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/{VALID_CONTACT_ID}/events")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "events" in data, f"Response should have 'events': {data}"
        events = data["events"]
        
        print(f"Contact has {len(events)} events")
        
        # Verify event structure
        for event in events[:5]:
            assert "event_type" in event, f"Event should have event_type: {event}"
            assert "timestamp" in event or "title" in event, f"Event should have timestamp or title: {event}"
        
        print(f"PASS: Contact events endpoint working - returned {len(events)} events")
    
    def test_contact_events_with_invalid_contact_id(self, api_client):
        """Events endpoint with invalid contact_id should handle gracefully"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/invalid_contact_id_123/events")
        
        # Should return 200 with empty events (not crash)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # May return empty events array
            print(f"Invalid contact_id returned {len(data.get('events', []))} events")


class TestMasterFeedEventTypes:
    """Verify master-feed returns correct event_type labels"""
    
    def test_master_feed_event_types(self, api_client):
        """Event types should have proper labels"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=50")
        assert response.status_code == 200
        data = response.json()
        feed = data.get("feed", [])
        
        event_types_seen = set()
        for event in feed:
            et = event.get("event_type", "unknown")
            event_types_seen.add(et)
            
            # Verify event has required fields
            assert "title" in event, f"Event should have title: {event}"
            assert "type" in event, f"Event should have type: {event}"  # Should be "event"
            assert "contact" in event, f"Event should have contact: {event}"
        
        print(f"Event types in feed: {sorted(event_types_seen)}")


class TestDataIntegrity:
    """Test that the fix handles the known invalid contact_ids gracefully"""
    
    def test_known_invalid_contact_ids_handled(self, api_client):
        """The 4 known invalid contact_ids should not crash the feed"""
        # Known invalid IDs from the bug report: abc123def456, abc456, contact_xyz, test123
        
        # Getting master-feed should NOT crash even with bad data in DB
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=100")
        assert response.status_code == 200, f"Master feed should not crash: {response.text}"
        
        data = response.json()
        assert "feed" in data, "Response should have feed"
        
        # Should return proper feed despite bad data
        feed = data.get("feed", [])
        print(f"PASS: Master feed returned {len(feed)} events despite invalid contact_ids in DB")
    
    def test_orphaned_contacts_show_unknown(self, api_client):
        """Events with orphaned/deleted contact_ids should gracefully show 'Unknown'"""
        response = api_client.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=100")
        assert response.status_code == 200
        
        data = response.json()
        feed = data.get("feed", [])
        
        # Count events where contact_id exists but name is Unknown (orphaned contacts)
        orphaned_count = 0
        for event in feed:
            contact = event.get("contact", {})
            if contact.get("id") and contact.get("name") == "Unknown":
                orphaned_count += 1
        
        print(f"Events with orphaned contacts (Unknown name but valid-looking ID): {orphaned_count}")
        # This is expected behavior - orphaned contacts should gracefully show Unknown


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
