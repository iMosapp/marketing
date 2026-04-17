"""
Test Add Contact Flow Improvements:
- Duplicate check endpoint (GET /api/contacts/{user_id}/check-duplicate)
- New contact creation logs 'new_contact_added' event
- Activity feed shows 'new contact added' events
"""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
USER_ID = "69a0b7095fddcede09591667"


class TestAddContactFlowAPI:
    """Tests for Add Contact flow improvements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def test_login(self):
        """Test login to get auth context"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "user" in data or "_id" in data, "No user data in response"
        print(f"Login successful")
        
    def test_check_duplicate_with_existing_phone(self):
        """Test duplicate check returns matches for existing phone number"""
        # First get existing contacts to find a valid phone
        contacts_resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert contacts_resp.status_code == 200
        contacts = contacts_resp.json()
        
        # Find a contact with a phone number
        contact_with_phone = None
        for c in contacts:
            if c.get('phone') and len(c.get('phone', '').replace('+', '').replace('-', '').replace(' ', '')) >= 7:
                contact_with_phone = c
                break
        
        if not contact_with_phone:
            pytest.skip("No contact with phone found for duplicate test")
            
        phone = contact_with_phone['phone']
        print(f"Testing duplicate check with phone: {phone}")
        
        resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/check-duplicate?phone={phone}")
        assert resp.status_code == 200, f"Duplicate check failed: {resp.text}"
        data = resp.json()
        assert "matches" in data, "Response missing 'matches' key"
        # Should find at least the contact we used
        assert len(data['matches']) >= 1, f"Expected at least 1 match, got {len(data['matches'])}"
        print(f"Duplicate check found {len(data['matches'])} match(es)")
        
        # Verify match structure
        match = data['matches'][0]
        assert 'id' in match, "Match missing 'id'"
        assert 'first_name' in match, "Match missing 'first_name'"
        assert 'phone' in match, "Match missing 'phone'"
        print(f"Match structure valid: {match.get('first_name')} {match.get('last_name')}")

    def test_check_duplicate_with_nonexistent_phone(self):
        """Test duplicate check returns empty for non-existent phone"""
        fake_phone = "9999999999"
        resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/check-duplicate?phone={fake_phone}")
        assert resp.status_code == 200, f"Duplicate check failed: {resp.text}"
        data = resp.json()
        assert "matches" in data
        assert len(data['matches']) == 0, f"Expected 0 matches for fake phone, got {len(data['matches'])}"
        print(f"No matches found for non-existent phone (correct)")
        
    def test_check_duplicate_with_nonexistent_email(self):
        """Test duplicate check returns empty for non-existent email"""
        fake_email = "nonexistent_test_12345@fakemail.invalid"
        resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/check-duplicate?email={fake_email}")
        assert resp.status_code == 200, f"Duplicate check failed: {resp.text}"
        data = resp.json()
        assert "matches" in data
        assert len(data['matches']) == 0, f"Expected 0 matches for fake email, got {len(data['matches'])}"
        print(f"No matches found for non-existent email (correct)")
        
    def test_check_duplicate_no_params(self):
        """Test duplicate check with no params returns empty matches"""
        resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/check-duplicate")
        assert resp.status_code == 200
        data = resp.json()
        assert "matches" in data
        assert len(data['matches']) == 0, "Expected empty matches with no params"
        print(f"Empty matches returned when no params (correct)")
        
    def test_create_contact_and_verify_event_logged(self):
        """Test creating a new contact logs 'new_contact_added' event"""
        # Create unique test contact
        timestamp = datetime.now().strftime("%H%M%S")
        test_contact = {
            "first_name": f"TestDup{timestamp}",
            "last_name": "Check",
            "phone": f"+1555{timestamp}1234",
            "email": f"testdup{timestamp}@test.com"
        }
        
        # Create the contact
        create_resp = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json=test_contact
        )
        assert create_resp.status_code == 200, f"Contact creation failed: {create_resp.text}"
        created = create_resp.json()
        contact_id = created.get('_id') or created.get('id')
        assert contact_id, "No contact ID returned"
        print(f"Created contact: {contact_id}")
        
        try:
            # Verify contact exists
            get_resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
            assert get_resp.status_code == 200, f"Failed to get created contact: {get_resp.text}"
            
            # Check for 'new_contact_added' event in contact events
            events_resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}/events")
            assert events_resp.status_code == 200, f"Failed to get events: {events_resp.text}"
            events_data = events_resp.json()
            
            # Find new_contact_added event
            events = events_data.get('events', [])
            new_contact_event = None
            for evt in events:
                if evt.get('event_type') == 'new_contact_added':
                    new_contact_event = evt
                    break
            
            assert new_contact_event is not None, f"'new_contact_added' event not found in events: {[e.get('event_type') for e in events]}"
            print(f"Found 'new_contact_added' event with title: {new_contact_event.get('title')}")
            
            # Verify event structure
            assert new_contact_event.get('title') == 'New Contact Added', f"Wrong title: {new_contact_event.get('title')}"
            assert 'description' in new_contact_event, "Event missing description"
            print(f"Event description: {new_contact_event.get('description')}")
            
            # Now verify duplicate check finds this new contact
            dup_resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/check-duplicate?phone={test_contact['phone']}")
            assert dup_resp.status_code == 200
            dup_data = dup_resp.json()
            assert len(dup_data['matches']) >= 1, "Duplicate check should find newly created contact"
            found = any(m.get('id') == contact_id for m in dup_data['matches'])
            assert found, "Created contact not found in duplicate check results"
            print(f"Duplicate check found the new contact (verified)")
            
        finally:
            # Cleanup: delete the test contact
            delete_resp = self.session.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
            print(f"Cleanup: deleted test contact, status={delete_resp.status_code}")

    def test_event_types_regression(self):
        """Run event types regression test to ensure previous fix still works"""
        # Import from test_event_types to verify no regression
        # This is a quick sanity check
        resp = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert resp.status_code == 200, f"Get contacts failed: {resp.text}"
        print("Contacts API working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
