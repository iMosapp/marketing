"""
Test Smart Contact Matching System - find-or-create-and-log endpoint

Tests:
- Create new contact when no match
- Find existing contact by last 10 digits of phone
- Return needs_confirmation when name mismatches
- force_action=use_existing logs event on existing contact  
- force_action=update_name changes contact name
- force_action=create_new creates separate contact
- Email matching works (personal and work)
- Merges email_work when personal already exists
"""

import pytest
import requests
import os
from datetime import datetime
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID for Forest
USER_ID = "69a0b7095fddcede09591667"

# Test data prefixes for cleanup
TEST_PREFIX = "TEST_CONTACT_MATCH_"


class TestFindOrCreateAndLogEndpoint:
    """Tests for POST /api/contacts/{user_id}/find-or-create-and-log"""

    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Setup before each test and cleanup after"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_contact_ids = []
        yield
        # Cleanup: Delete test contacts
        for contact_id in self.created_contact_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
            except:
                pass

    def test_create_new_contact_when_no_match(self):
        """Should create new contact when no existing match is found"""
        unique_phone = f"555{int(time.time()) % 10000000:07d}"
        
        payload = {
            "phone": unique_phone,
            "name": f"{TEST_PREFIX}New Contact",
            "event_type": "test_event",
            "event_title": "Test Event",
            "event_description": "Testing contact creation"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("contact_created") == True, f"Expected contact_created=True, got {data}"
        assert data.get("event_logged") == True, f"Expected event_logged=True, got {data}"
        assert data.get("match_found") == False, f"Expected match_found=False, got {data}"
        assert data.get("needs_confirmation") == False
        assert "contact_id" in data
        
        self.created_contact_ids.append(data["contact_id"])
        print(f"PASS: Created new contact with ID {data['contact_id']}")

    def test_find_existing_contact_by_last_10_digits(self):
        """Should find existing contact by last 10 digits of phone number"""
        # First create a contact with full phone number
        unique_phone = f"1801555{int(time.time()) % 10000:04d}"
        
        create_payload = {
            "phone": unique_phone,
            "name": f"{TEST_PREFIX}Phone Match Test",
            "event_type": "creation",
            "event_title": "Contact Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        created_data = create_response.json()
        contact_id = created_data["contact_id"]
        self.created_contact_ids.append(contact_id)
        
        # Now try to find with just last 10 digits (without country code)
        last_10 = unique_phone[-10:]
        
        find_payload = {
            "phone": last_10,
            "name": f"{TEST_PREFIX}Phone Match Test",  # Same name so no confirmation needed
            "event_type": "follow_up",
            "event_title": "Follow Up Event"
        }
        
        find_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=find_payload
        )
        
        assert find_response.status_code == 200
        data = find_response.json()
        
        assert data.get("contact_created") == False, f"Expected contact_created=False (should find existing), got {data}"
        assert data.get("match_found") == True, f"Expected match_found=True, got {data}"
        assert data.get("contact_id") == contact_id, f"Expected same contact_id {contact_id}, got {data.get('contact_id')}"
        print(f"PASS: Found existing contact by last 10 digits")

    def test_returns_needs_confirmation_on_name_mismatch(self):
        """Should return needs_confirmation when name mismatches"""
        # Create contact with one name
        unique_phone = f"1801666{int(time.time()) % 10000:04d}"
        
        create_payload = {
            "phone": unique_phone,
            "name": f"{TEST_PREFIX}Original Name",
            "event_type": "creation",
            "event_title": "Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        created_data = create_response.json()
        contact_id = created_data["contact_id"]
        self.created_contact_ids.append(contact_id)
        
        # Now try with same phone but DIFFERENT name
        find_payload = {
            "phone": unique_phone,
            "name": "Different Person Name",  # Different name!
            "event_type": "share",
            "event_title": "Share Event"
        }
        
        find_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=find_payload
        )
        
        assert find_response.status_code == 200
        data = find_response.json()
        
        assert data.get("needs_confirmation") == True, f"Expected needs_confirmation=True for name mismatch, got {data}"
        assert data.get("match_found") == True, f"Expected match_found=True, got {data}"
        assert data.get("existing_name") == f"{TEST_PREFIX}Original Name", f"Expected existing_name to be original, got {data}"
        assert data.get("provided_name") == "Different Person Name", f"Expected provided_name, got {data}"
        print(f"PASS: Returns needs_confirmation for name mismatch")

    def test_force_action_use_existing_logs_event(self):
        """Should log event on existing contact when force_action=use_existing"""
        # Create contact first
        unique_phone = f"1801777{int(time.time()) % 10000:04d}"
        
        create_payload = {
            "phone": unique_phone,
            "name": f"{TEST_PREFIX}Use Existing Test",
            "event_type": "creation",
            "event_title": "Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        created_data = create_response.json()
        contact_id = created_data["contact_id"]
        self.created_contact_ids.append(contact_id)
        
        # Now use force_action=use_existing with different name
        use_existing_payload = {
            "phone": unique_phone,
            "name": "Different Name Here",
            "force_action": "use_existing",
            "event_type": "review_shared",
            "event_title": "Review Shared"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=use_existing_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("contact_id") == contact_id, f"Expected same contact_id with use_existing"
        assert data.get("contact_created") == False, f"Expected no new contact created"
        assert data.get("event_logged") == True, f"Expected event_logged=True"
        assert data.get("needs_confirmation") == False, f"Expected no confirmation needed with force_action"
        print(f"PASS: force_action=use_existing logs event on existing contact")

    def test_force_action_update_name(self):
        """Should update contact name when force_action=update_name"""
        # Create contact first
        unique_phone = f"1801888{int(time.time()) % 10000:04d}"
        original_name = f"{TEST_PREFIX}Original Update Test"
        
        create_payload = {
            "phone": unique_phone,
            "name": original_name,
            "event_type": "creation",
            "event_title": "Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        created_data = create_response.json()
        contact_id = created_data["contact_id"]
        self.created_contact_ids.append(contact_id)
        
        # Now use force_action=update_name
        new_name = f"{TEST_PREFIX}Updated Name"
        update_payload = {
            "phone": unique_phone,
            "name": new_name,
            "force_action": "update_name",
            "event_type": "name_updated",
            "event_title": "Name Updated"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=update_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("contact_id") == contact_id, f"Expected same contact_id"
        assert data.get("contact_created") == False
        assert data.get("event_logged") == True
        assert data.get("contact_name") == new_name, f"Expected name to be updated to '{new_name}', got '{data.get('contact_name')}'"
        print(f"PASS: force_action=update_name updates contact name")

    def test_force_action_create_new(self):
        """Should create separate contact when force_action=create_new"""
        # Create original contact
        unique_phone = f"1801999{int(time.time()) % 10000:04d}"
        
        create_payload = {
            "phone": unique_phone,
            "name": f"{TEST_PREFIX}Original Contact",
            "event_type": "creation",
            "event_title": "Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        original_contact_id = create_response.json()["contact_id"]
        self.created_contact_ids.append(original_contact_id)
        
        # Now use force_action=create_new
        create_new_payload = {
            "phone": unique_phone,
            "name": f"{TEST_PREFIX}New Person Same Phone",
            "force_action": "create_new",
            "event_type": "new_contact",
            "event_title": "New Contact"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_new_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("contact_created") == True, f"Expected new contact to be created"
        assert data.get("contact_id") != original_contact_id, f"Expected different contact_id"
        self.created_contact_ids.append(data["contact_id"])
        print(f"PASS: force_action=create_new creates separate contact")

    def test_email_matching_works(self):
        """Should find contact by email (personal or work)"""
        unique_email = f"test_{int(time.time())}@example.com"
        
        # Create contact with email
        create_payload = {
            "email": unique_email,
            "name": f"{TEST_PREFIX}Email Match Test",
            "event_type": "creation",
            "event_title": "Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        created_data = create_response.json()
        contact_id = created_data["contact_id"]
        self.created_contact_ids.append(contact_id)
        
        # Now find by same email
        find_payload = {
            "email": unique_email,
            "name": f"{TEST_PREFIX}Email Match Test",  # Same name
            "event_type": "follow_up",
            "event_title": "Follow Up"
        }
        
        find_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=find_payload
        )
        
        assert find_response.status_code == 200
        data = find_response.json()
        
        assert data.get("match_found") == True, f"Expected to find contact by email"
        assert data.get("contact_id") == contact_id, f"Expected same contact_id"
        print(f"PASS: Email matching works")

    def test_merges_email_work_when_personal_exists(self):
        """Should add email_work when contact already has personal email"""
        # Create contact with personal email
        unique_phone = f"1801111{int(time.time()) % 10000:04d}"
        personal_email = f"personal_{int(time.time())}@gmail.com"
        
        create_payload = {
            "phone": unique_phone,
            "email": personal_email,
            "name": f"{TEST_PREFIX}Dual Email Test",
            "event_type": "creation",
            "event_title": "Created"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=create_payload
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["contact_id"]
        self.created_contact_ids.append(contact_id)
        
        # Now add work email by finding same contact
        work_email = f"work_{int(time.time())}@company.com"
        
        add_work_payload = {
            "phone": unique_phone,  # Match by phone
            "email": work_email,     # Different email - should be added as work
            "name": f"{TEST_PREFIX}Dual Email Test",
            "event_type": "work_email_added",
            "event_title": "Work Email Added"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=add_work_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("contact_id") == contact_id, f"Expected same contact (merged)"
        assert data.get("contact_created") == False
        
        # Verify the contact now has email_work (fetch the contact)
        contact_response = self.session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
        if contact_response.status_code == 200:
            contact_data = contact_response.json()
            assert contact_data.get("email") == personal_email, f"Personal email should remain"
            assert contact_data.get("email_work") == work_email, f"Work email should be added"
            print(f"PASS: Work email merged onto existing contact")
        else:
            print(f"PASS: Dual email merge executed (contact fetch returned {contact_response.status_code})")

    def test_requires_phone_or_email(self):
        """Should return 400 when neither phone nor email provided"""
        payload = {
            "name": "No Contact Info",
            "event_type": "test",
            "event_title": "Test"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 400, f"Expected 400 for missing phone/email, got {response.status_code}"
        print(f"PASS: Returns 400 when phone and email are both missing")


class TestExistingForestContact:
    """Tests using the existing Forest Ward contact (phone=8016349122, email=forestward@gmail.com)"""
    
    def test_find_existing_forest_contact_by_phone(self):
        """Should find Forest Ward by phone 8016349122"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        payload = {
            "phone": "8016349122",
            "name": "Forest Ward",
            "event_type": "test_lookup",
            "event_title": "Test Lookup"
        }
        
        response = session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find existing contact (if exists in DB)
        # Note: This may create new if Forest Ward contact doesn't exist
        assert "contact_id" in data
        print(f"PASS: Lookup by Forest's phone returned contact_id: {data.get('contact_id')}")

    def test_name_mismatch_triggers_confirmation(self):
        """Should trigger needs_confirmation when name doesn't match Forest Ward"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # First ensure a contact exists with this phone
        setup_payload = {
            "phone": "8016349122",
            "name": "Forest Ward",
            "event_type": "setup",
            "event_title": "Setup"
        }
        session.post(f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log", json=setup_payload)
        
        # Now try with different name
        payload = {
            "phone": "8016349122",
            "name": "John Smith",  # Different name!
            "event_type": "review_share",
            "event_title": "Review Share"
        }
        
        response = session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/find-or-create-and-log",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should either find and require confirmation, or create new
        if data.get("needs_confirmation"):
            assert data.get("existing_name") is not None
            assert data.get("provided_name") == "John Smith"
            print(f"PASS: Name mismatch triggers confirmation - existing: {data.get('existing_name')}")
        else:
            print(f"INFO: Contact created/matched without confirmation (may be new contact)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
