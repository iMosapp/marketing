"""
API tests for event type resolution - testing the actual endpoints.
Run: cd /app/backend && python -m pytest tests/test_event_types_api.py -v
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com').rstrip('/')

class TestLogin:
    """Test login functionality"""
    
    def test_login_super_admin(self):
        """POST /api/auth/login with super admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        assert response.status_code == 200
        data = response.json()
        assert "user" in data or "_id" in data
        print(f"Login successful: user_id = {data.get('user', {}).get('_id', data.get('_id'))}")
        return data


class TestMasterFeed:
    """Test master-feed returns correct event types and titles"""
    
    def test_master_feed_returns_feed(self):
        """GET /api/contacts/{user_id}/master-feed returns activity feed"""
        user_id = "69a0b7095fddcede09591667"
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/master-feed?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert "feed" in data
        print(f"Master feed returned {len(data['feed'])} items")
        return data
    
    def test_master_feed_event_types_are_correct(self):
        """Verify event_type and title fields are correctly set for different card types"""
        user_id = "69a0b7095fddcede09591667"
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/master-feed?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        # Check for different event types - they should NOT all be congrats_card_sent
        event_types_found = set()
        for item in data.get("feed", []):
            event_type = item.get("event_type")
            title = item.get("title")
            if event_type:
                event_types_found.add(event_type)
            # CRITICAL: Check that title matches event_type
            if "birthday" in event_type.lower():
                assert "Birthday" in title, f"Birthday event should have Birthday in title, got: {title}"
            if "thank_you" in event_type.lower() or "thankyou" in event_type.lower():
                assert "Thank You" in title, f"Thank you event should have Thank You in title, got: {title}"
            if "holiday" in event_type.lower():
                assert "Holiday" in title, f"Holiday event should have Holiday in title, got: {title}"
            if "welcome" in event_type.lower():
                assert "Welcome" in title, f"Welcome event should have Welcome in title, got: {title}"
            if "anniversary" in event_type.lower():
                assert "Anniversary" in title, f"Anniversary event should have Anniversary in title, got: {title}"
        
        print(f"Event types found: {event_types_found}")


class TestContactEvents:
    """Test contact events endpoint returns correct titles"""
    
    def test_contact_events_returns_events(self):
        """GET /api/contacts/{user_id}/{contact_id}/events returns events"""
        user_id = "69a0b7095fddcede09591667"
        contact_id = "69a8abe36a8712d026633756"
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/{contact_id}/events?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        print(f"Contact events returned {len(data['events'])} items")
        return data
    
    def test_contact_events_titles_from_centralized_labels(self):
        """Titles should be derived from centralized labels, not stored in DB"""
        user_id = "69a0b7095fddcede09591667"
        contact_id = "69a8abe36a8712d026633756"
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/{contact_id}/events?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        for event in data.get("events", []):
            event_type = event.get("event_type", "")
            title = event.get("title", "")
            
            # The title should match the centralized label for the event type
            if "birthday_card_sent" in event_type:
                assert "Birthday" in title, f"Expected Birthday in title for {event_type}, got: {title}"
            if "thank_you_card_sent" in event_type or "thankyou_card_sent" in event_type:
                assert "Thank You" in title, f"Expected Thank You in title for {event_type}, got: {title}"
            if "holiday_card_sent" in event_type:
                assert "Holiday" in title, f"Expected Holiday in title for {event_type}, got: {title}"
            if "welcome_card_sent" in event_type:
                assert "Welcome" in title, f"Expected Welcome in title for {event_type}, got: {title}"
            if "anniversary_card_sent" in event_type:
                assert "Anniversary" in title, f"Expected Anniversary in title for {event_type}, got: {title}"
            
            # CRITICAL: If it's a birthday/holiday/etc event_type, it should NOT have "Congrats Card" title
            if event_type != "congrats_card_sent" and "card_sent" in event_type:
                # Only congrats_card_sent should have "Congrats Card" title
                if "birthday" in event_type or "holiday" in event_type or "thank_you" in event_type or "welcome" in event_type or "anniversary" in event_type:
                    assert "Congrats Card" not in title, f"Event type {event_type} should NOT have 'Congrats Card' title, got: {title}"
        
        print("All event titles correctly match centralized labels")


class TestActionProgress:
    """Test action-progress endpoint"""
    
    def test_action_progress_returns_progress(self):
        """GET /api/contacts/{user_id}/{contact_id}/action-progress returns progress data"""
        user_id = "69a0b7095fddcede09591667"
        contact_id = "69a8abe36a8712d026633756"
        response = requests.get(f"{BASE_URL}/api/contacts/{user_id}/{contact_id}/action-progress")
        assert response.status_code == 200
        data = response.json()
        assert "progress" in data
        assert "completed" in data
        assert "total" in data
        print(f"Action progress: {data['completed']}/{data['total']} completed")
        return data


class TestDataMigration:
    """Test the data migration endpoint"""
    
    def test_fix_event_types_endpoint_exists(self):
        """POST /api/contacts/admin/fix-event-types should work"""
        response = requests.post(f"{BASE_URL}/api/contacts/admin/fix-event-types")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"Migration result: {data.get('events_retyped', 0)} events retyped, {data.get('titles_fixed', 0)} titles fixed")
        return data
