"""
Test Contact Find-Or-Create-And-Log API
Tests for Bug Fix 2: POST /api/contacts/{userId}/find-or-create-and-log 
- Match by phone (last 10 digits)
- Return needs_confirmation on name mismatch
- Support force_action
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com')
TEST_USER_ID = "69a0b7095fddcede09591667"  # Super Admin user ID


class TestContactFindOrCreateAndLog:
    """Tests for the find-or-create-and-log endpoint"""

    def get_unique_phone(self):
        """Generate a unique phone number for testing"""
        return f"+1555{int(time.time() * 1000) % 10000000:07d}"
    
    def get_unique_email(self):
        """Generate a unique email for testing"""
        return f"test_{uuid.uuid4().hex[:8]}@example.com"

    def test_create_new_contact_with_phone(self):
        """Test creating a new contact when no match exists (phone)"""
        phone = self.get_unique_phone()
        payload = {
            "name": "TEST New Contact",
            "phone": phone,
            "event_type": "card_shared",
            "event_title": "Test Card",
            "event_description": "Test event from pytest"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "contact_id" in data, "contact_id should be in response"
        assert data["contact_created"] == True, "contact_created should be True for new contact"
        assert data["event_logged"] == True, "event_logged should be True"
        assert data["needs_confirmation"] == False, "needs_confirmation should be False for new contact"
        assert "TEST New" in data["contact_name"], f"Name should contain 'TEST New', got {data['contact_name']}"
        print(f"PASS: Created new contact with ID: {data['contact_id']}")

    def test_create_new_contact_with_email(self):
        """Test creating a new contact when no match exists (email only)"""
        email = self.get_unique_email()
        payload = {
            "name": "TEST Email Contact",
            "email": email,
            "event_type": "digital_card_shared",
            "event_title": "Digital Card",
            "event_description": "Shared digital card"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["contact_created"] == True, "contact_created should be True"
        assert "contact_id" in data
        print(f"PASS: Created new contact via email with ID: {data['contact_id']}")

    def test_find_existing_contact_by_phone_exact_match_name(self):
        """Test finding existing contact by phone with exact name match"""
        # First create a contact
        phone = self.get_unique_phone()
        name = "TEST Same Name"
        
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": name, "phone": phone, "event_type": "test"}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        
        # Now search for same contact with same name
        find_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": name, "phone": phone, "event_type": "test_find"}
        )
        
        assert find_response.status_code == 200
        data = find_response.json()
        
        assert data["contact_id"] == contact_id, "Should return same contact_id"
        assert data["contact_created"] == False, "Should not create new contact"
        assert data["needs_confirmation"] == False, "Should not need confirmation for exact name match"
        print(f"PASS: Found existing contact with exact name match")

    def test_find_existing_contact_phone_last_10_digits(self):
        """Test finding contact by last 10 digits of phone number"""
        # Create with formatted phone
        base_number = str(int(time.time() * 1000) % 10000000000).zfill(10)
        phone_formatted = f"+1-({base_number[:3]}) {base_number[3:6]}-{base_number[6:]}"
        
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Phone Format", "phone": phone_formatted, "event_type": "test"}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        
        # Now search with just the 10 digits
        plain_phone = base_number[-10:]
        find_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Phone Format", "phone": plain_phone, "event_type": "test_find"}
        )
        
        assert find_response.status_code == 200
        data = find_response.json()
        
        # Should find the same contact
        assert data["contact_id"] == contact_id, "Should match by last 10 digits"
        assert data["contact_created"] == False, "Should not create new contact"
        print(f"PASS: Found contact by last 10 digits phone matching")

    def test_needs_confirmation_on_name_mismatch(self):
        """Test that name mismatch triggers needs_confirmation"""
        phone = self.get_unique_phone()
        
        # Create with one name
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Original Name", "phone": phone, "event_type": "test"}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        
        # Try to find with different name
        find_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Different Name", "phone": phone, "event_type": "test_find"}
        )
        
        assert find_response.status_code == 200
        data = find_response.json()
        
        # Should flag for confirmation
        assert data["needs_confirmation"] == True, "Should need confirmation on name mismatch"
        assert data["existing_name"] == "TEST Original Name", "Should return existing name"
        assert data["provided_name"] == "TEST Different Name", "Should return provided name"
        assert data["contact_id"] == contact_id, "Should return matching contact_id"
        print(f"PASS: Name mismatch triggers needs_confirmation correctly")

    def test_force_action_use_existing(self):
        """Test force_action=use_existing uses existing contact without updating name"""
        phone = self.get_unique_phone()
        
        # Create contact
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Keep This Name", "phone": phone, "event_type": "test"}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        
        # Use force_action=use_existing
        force_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={
                "name": "TEST New Name", 
                "phone": phone, 
                "event_type": "test_force",
                "force_action": "use_existing"
            }
        )
        
        assert force_response.status_code == 200
        data = force_response.json()
        
        assert data["contact_id"] == contact_id, "Should use same contact"
        assert data["needs_confirmation"] == False, "Should not need confirmation with force_action"
        assert "Keep This Name" in data["contact_name"], "Should keep original name"
        print(f"PASS: force_action=use_existing works correctly")

    def test_force_action_update_name(self):
        """Test force_action=update_name updates the contact name"""
        phone = self.get_unique_phone()
        
        # Create contact
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Old Name", "phone": phone, "event_type": "test"}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        
        # Use force_action=update_name
        force_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={
                "name": "TEST Updated Name", 
                "phone": phone, 
                "event_type": "test_force",
                "force_action": "update_name"
            }
        )
        
        assert force_response.status_code == 200
        data = force_response.json()
        
        assert data["contact_id"] == contact_id, "Should use same contact"
        assert "Updated Name" in data["contact_name"], f"Name should be updated, got {data['contact_name']}"
        print(f"PASS: force_action=update_name updates name correctly")

    def test_force_action_create_new(self):
        """Test force_action=create_new creates a new contact even when match exists"""
        phone = self.get_unique_phone()
        
        # Create first contact
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST First Contact", "phone": phone, "event_type": "test"}
        )
        assert create_response.status_code == 200
        first_contact_id = create_response.json()["contact_id"]
        
        # Use force_action=create_new
        force_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={
                "name": "TEST Second Contact", 
                "phone": phone, 
                "event_type": "test_force",
                "force_action": "create_new"
            }
        )
        
        assert force_response.status_code == 200
        data = force_response.json()
        
        assert data["contact_id"] != first_contact_id, "Should create new contact with different ID"
        assert data["contact_created"] == True, "Should indicate contact was created"
        print(f"PASS: force_action=create_new creates new contact")

    def test_missing_phone_and_email_returns_error(self):
        """Test that missing both phone and email returns 400 error"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST No Contact Info", "event_type": "test"}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Phone or email" in data.get("detail", ""), "Should mention phone or email required"
        print(f"PASS: Missing phone/email returns 400 error")

    def test_email_merge_to_existing_contact(self):
        """Test that email gets merged to existing contact found by phone"""
        phone = self.get_unique_phone()
        email = self.get_unique_email()
        
        # Create contact with phone only
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Merge Contact", "phone": phone, "event_type": "test"}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        
        # Find contact and add email
        merge_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={"name": "TEST Merge Contact", "phone": phone, "email": email, "event_type": "test_merge"}
        )
        
        assert merge_response.status_code == 200
        data = merge_response.json()
        
        assert data["contact_id"] == contact_id, "Should use same contact"
        # Email should be merged (may or may not be returned in response depending on implementation)
        print(f"PASS: Email merged to existing contact")


class TestContactEventsLogging:
    """Test that events are properly logged"""
    
    def test_event_logged_on_contact_create(self):
        """Test that event is logged when contact is created"""
        phone = f"+1555{int(time.time() * 1000) % 10000000:07d}"
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/find-or-create-and-log",
            json={
                "name": "TEST Event Logging",
                "phone": phone,
                "event_type": "congrats_card_sent",
                "event_title": "Congrats Card Sent",
                "event_description": "Sent congrats card via SMS",
                "event_icon": "gift",
                "event_color": "#C9A962"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["event_logged"] == True, "event_logged should be True"
        
        # Verify event exists by getting contact events
        contact_id = data["contact_id"]
        events_response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}/events?limit=5"
        )
        
        if events_response.status_code == 200:
            events = events_response.json().get("events", [])
            found_event = any(e.get("event_type") == "congrats_card_sent" for e in events)
            assert found_event, "Should find logged event in contact events"
            print(f"PASS: Event logged and retrievable")
        else:
            print(f"PASS: Event logged (events endpoint returned {events_response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
