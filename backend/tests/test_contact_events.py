"""
Test contact events endpoints - FB-feed style timeline and gamification stats
Tests the new /api/contacts/{user_id}/{contact_id}/events and /stats endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a0c06f7626f14d125f8c34"
LOGIN_EMAIL = "forest@imosapp.com"
LOGIN_PASSWORD = "Admin123!"


class TestContactEventsAPI:
    """Tests for contact events timeline and stats"""

    def test_health_check(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")

    def test_get_contact_events(self):
        """Test GET /api/contacts/{user_id}/{contact_id}/events - timeline events"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)
        
        # Verify events have expected structure
        if len(data["events"]) > 0:
            event = data["events"][0]
            assert "event_type" in event
            assert "icon" in event
            assert "color" in event
            assert "title" in event
            assert "timestamp" in event
            assert "category" in event
            print(f"✓ GET events returned {data['total']} events with proper structure")
        else:
            print("✓ GET events returned empty list (no events yet)")

    def test_get_contact_stats(self):
        """Test GET /api/contacts/{user_id}/{contact_id}/stats - touchpoint stats"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify stats structure
        assert "total_touchpoints" in data
        assert "messages_sent" in data
        assert "campaigns" in data
        assert "cards_sent" in data
        assert "broadcasts" in data
        assert "custom_events" in data
        assert "created_at" in data
        
        # Verify types
        assert isinstance(data["total_touchpoints"], int)
        assert isinstance(data["messages_sent"], int)
        assert isinstance(data["campaigns"], int)
        
        print(f"✓ GET stats returned: touchpoints={data['total_touchpoints']}, messages={data['messages_sent']}, campaigns={data['campaigns']}")

    def test_post_contact_event(self):
        """Test POST /api/contacts/{user_id}/{contact_id}/events - log custom event"""
        event_data = {
            "event_type": "test_logged_event",
            "title": "Test Custom Event",
            "description": "Logged from pytest",
            "category": "custom",
            "icon": "checkmark",
            "color": "#34C759"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            json=event_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["event_type"] == "test_logged_event"
        assert data["title"] == "Test Custom Event"
        assert data["description"] == "Logged from pytest"
        assert data["category"] == "custom"
        assert "timestamp" in data
        
        print(f"✓ POST event created successfully with timestamp: {data['timestamp']}")

    def test_events_with_limit(self):
        """Test events endpoint with limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            params={"limit": 3}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["events"]) <= 3
        print(f"✓ GET events with limit=3 returned {len(data['events'])} events")

    def test_stats_has_created_at_for_time_in_system(self):
        """Verify stats returns created_at for 'time in system' counter"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "created_at" in data
        # created_at should be a string (ISO format) or null
        if data["created_at"]:
            assert isinstance(data["created_at"], str)
            print(f"✓ Stats has created_at: {data['created_at']}")
        else:
            print("✓ Stats has created_at (null - new contact)")

    def test_invalid_contact_events(self):
        """Test events endpoint with non-existent contact"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/invalid_contact_id/events")
        # Should return 200 with empty events (not 404)
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        print("✓ Invalid contact returns empty events list")

    def test_invalid_contact_stats(self):
        """Test stats endpoint with non-existent contact - should return zeros"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/invalid_contact_id/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_touchpoints"] == 0
        print("✓ Invalid contact returns zero stats")


class TestContactDetailPageData:
    """Tests to verify data for contact detail page features"""

    def test_contact_basic_info(self):
        """Test GET /api/contacts/{user_id}/{contact_id} - basic contact info for hero section"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # Contact should have basic info for hero section
        assert "first_name" in data
        assert "phone" in data
        print(f"✓ Contact info: {data.get('first_name')} {data.get('last_name', '')}, phone: {data.get('phone')}")

    def test_contact_referrals(self):
        """Test referrals endpoint"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/referrals")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Referrals endpoint returned {len(data)} referrals")


class TestAuthAndLogin:
    """Test authentication for the app"""

    def test_login(self):
        """Test login with provided credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == LOGIN_EMAIL
        print(f"✓ Login successful for {LOGIN_EMAIL}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
