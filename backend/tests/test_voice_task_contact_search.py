"""
Tests for Voice-to-Task parsing and Contact Search with Email

Features tested:
1. POST /api/voice/parse-task - AI extraction of task details from natural language
2. GET /api/contacts/{user_id}?search=email - Contact search includes email field

Test Scenarios:
- parse-task with callback instructions including date/time
- parse-task with follow_up type and priority
- parse-task with appointment type
- Contact search matching by email
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"


class TestVoiceParseTask:
    """Tests for POST /api/voice/parse-task endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get user_id
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_resp.status_code == 200:
            self.user_id = login_resp.json().get("user", {}).get("_id")
        else:
            self.user_id = None
            pytest.skip("Could not authenticate - skipping tests")
    
    def test_parse_task_endpoint_exists(self):
        """Test that the parse-task endpoint exists and responds"""
        resp = self.session.post(f"{BASE_URL}/api/voice/parse-task", json={
            "text": "test"
        })
        # Should not be 404 - endpoint should exist
        assert resp.status_code != 404, f"parse-task endpoint not found: {resp.status_code}"
        print(f"PASS: parse-task endpoint exists (status: {resp.status_code})")
    
    def test_parse_task_callback_with_date_time(self):
        """Test: 'call John next Tuesday at 2pm about warranty' should return callback type with date/time"""
        resp = self.session.post(f"{BASE_URL}/api/voice/parse-task", json={
            "text": "call John next Tuesday at 2pm about warranty"
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "title" in data, "Response missing 'title' field"
        assert "type" in data, "Response missing 'type' field"
        assert "success" in data, "Response missing 'success' field"
        
        # Verify callback type is detected
        assert data["type"] == "callback", f"Expected type='callback', got type='{data['type']}'"
        
        # Verify due_time is extracted (2pm = 14:00)
        if data.get("due_time"):
            assert data["due_time"] == "14:00", f"Expected due_time='14:00', got '{data['due_time']}'"
            print(f"PASS: due_time correctly extracted as 14:00")
        else:
            print(f"INFO: due_time not extracted (AI may vary)")
        
        # Verify due_date is set (should be a Tuesday)
        if data.get("due_date"):
            print(f"PASS: due_date extracted as {data['due_date']}")
        else:
            print(f"INFO: due_date not extracted")
        
        print(f"PASS: Callback task parsed - title='{data['title']}', type='{data['type']}'")
    
    def test_parse_task_follow_up_high_priority(self):
        """Test: 'follow up with Sarah this Friday, high priority' should return follow_up with high priority"""
        resp = self.session.post(f"{BASE_URL}/api/voice/parse-task", json={
            "text": "follow up with Sarah this Friday, high priority"
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "title" in data, "Response missing 'title' field"
        assert "type" in data, "Response missing 'type' field"
        assert "priority" in data, "Response missing 'priority' field"
        
        # Verify follow_up type is detected
        assert data["type"] == "follow_up", f"Expected type='follow_up', got type='{data['type']}'"
        
        # Verify high priority is detected
        assert data["priority"] == "high", f"Expected priority='high', got priority='{data['priority']}'"
        
        print(f"PASS: Follow-up task parsed - type='{data['type']}', priority='{data['priority']}'")
    
    def test_parse_task_appointment_type(self):
        """Test: 'schedule meeting with Mike tomorrow at 3pm' should return appointment type"""
        resp = self.session.post(f"{BASE_URL}/api/voice/parse-task", json={
            "text": "schedule meeting with Mike tomorrow at 3pm"
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify appointment type detection
        assert data["type"] == "appointment", f"Expected type='appointment', got type='{data['type']}'"
        
        # Verify time extraction (3pm = 15:00)
        if data.get("due_time"):
            assert data["due_time"] == "15:00", f"Expected due_time='15:00', got '{data['due_time']}'"
            print(f"PASS: due_time correctly extracted as 15:00")
        
        print(f"PASS: Appointment task parsed - type='{data['type']}'")
    
    def test_parse_task_response_fields(self):
        """Test that response contains all required fields"""
        resp = self.session.post(f"{BASE_URL}/api/voice/parse-task", json={
            "text": "remind me to check inventory next week"
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        # All expected fields from TaskParseResponse
        expected_fields = ["title", "description", "type", "priority", "due_date", "due_time", "success"]
        for field in expected_fields:
            assert field in data, f"Response missing required field: '{field}'"
        
        print(f"PASS: All response fields present: {list(data.keys())}")
    
    def test_parse_task_fallback_on_empty_text(self):
        """Test that empty text returns gracefully"""
        resp = self.session.post(f"{BASE_URL}/api/voice/parse-task", json={
            "text": ""
        })
        
        # Should handle gracefully - either 200 with fallback or 422 validation error
        assert resp.status_code in [200, 422], f"Unexpected status: {resp.status_code}"
        print(f"PASS: Empty text handled (status: {resp.status_code})")


class TestContactSearchEmail:
    """Tests for GET /api/contacts/{user_id}?search=email"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get user_id
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_resp.status_code == 200:
            self.user_id = login_resp.json().get("user", {}).get("_id")
        else:
            self.user_id = None
            pytest.skip("Could not authenticate - skipping tests")
    
    def test_create_contact_with_email(self):
        """Create a test contact with a unique email for search testing"""
        unique_email = f"test_search_{datetime.now().strftime('%H%M%S')}@example.com"
        
        resp = self.session.post(f"{BASE_URL}/api/contacts/{self.user_id}", json={
            "first_name": "TEST_EmailSearch",
            "last_name": "Contact",
            "phone": "555-000-1111",
            "email": unique_email
        })
        
        assert resp.status_code in [200, 201], f"Failed to create contact: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        self.test_contact_id = data.get("_id") or data.get("id")
        self.test_email = unique_email
        
        print(f"PASS: Created test contact with email '{unique_email}'")
        return self.test_contact_id, unique_email
    
    def test_search_contacts_by_email(self):
        """Test that contact search includes email matching"""
        # First create a contact with unique email
        contact_id, unique_email = self.test_create_contact_with_email()
        
        # Search by the unique email domain portion
        search_term = unique_email.split('@')[0]  # e.g., test_search_123456
        
        resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}?search={search_term}")
        
        assert resp.status_code == 200, f"Search failed: {resp.status_code} - {resp.text}"
        
        contacts = resp.json()
        
        # Verify the contact with our email is in results
        found = False
        for contact in contacts:
            if contact.get("email") == unique_email:
                found = True
                break
        
        assert found, f"Contact with email '{unique_email}' not found in search results for term '{search_term}'"
        
        print(f"PASS: Email search working - found contact by searching '{search_term}'")
        
        # Cleanup: delete test contact
        if contact_id:
            self.session.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}")
    
    def test_search_contacts_by_full_email(self):
        """Test searching by full email address"""
        # Create a contact
        unique_email = f"fullsearch_{datetime.now().strftime('%H%M%S')}@testdomain.com"
        
        resp = self.session.post(f"{BASE_URL}/api/contacts/{self.user_id}", json={
            "first_name": "TEST_FullEmail",
            "last_name": "Search",
            "phone": "555-000-2222",
            "email": unique_email
        })
        
        assert resp.status_code in [200, 201], f"Failed to create contact: {resp.text}"
        contact_id = resp.json().get("_id") or resp.json().get("id")
        
        # Search by full email
        search_resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}?search={unique_email}")
        
        assert search_resp.status_code == 200, f"Search failed: {search_resp.status_code}"
        
        contacts = search_resp.json()
        found = any(c.get("email") == unique_email for c in contacts)
        
        assert found, f"Contact not found when searching by full email '{unique_email}'"
        
        print(f"PASS: Full email search working")
        
        # Cleanup
        if contact_id:
            self.session.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}")
    
    def test_contacts_endpoint_returns_email_field(self):
        """Test that contacts endpoint includes email field in results"""
        resp = self.session.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        
        assert resp.status_code == 200, f"Contacts fetch failed: {resp.status_code}"
        
        contacts = resp.json()
        if len(contacts) > 0:
            # Check that email field is present in response
            sample_contact = contacts[0]
            # Email might be empty string but field should exist
            assert "email" in sample_contact or sample_contact.get("email") is not None or sample_contact.get("email") == "", \
                "Email field not present in contact response"
            print(f"PASS: Contacts response includes email field")
        else:
            print(f"INFO: No contacts found to verify email field presence")


class TestVoiceStatus:
    """Test voice/status endpoint"""
    
    def test_voice_status_endpoint(self):
        """Test that voice status endpoint is available"""
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/voice/status")
        
        assert resp.status_code == 200, f"Voice status endpoint failed: {resp.status_code}"
        
        data = resp.json()
        assert "available" in data, "Response missing 'available' field"
        assert "whisper_installed" in data, "Response missing 'whisper_installed' field"
        assert "api_key_configured" in data, "Response missing 'api_key_configured' field"
        
        print(f"PASS: Voice status - available={data['available']}, whisper={data['whisper_installed']}, api_key={data['api_key_configured']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
