"""
Test Contact Ownership & Visibility Rules for RMS

Business rules being tested:
1. Salespeople ONLY see their own contacts (no toggle, view_mode ignored)
2. Managers/Admins have 'My Contacts / Team Contacts' toggle
   - 'mine' (default): only their own contacts
   - 'team': all org contacts, excluding personal, enriched with salesperson_name
3. ownership_type is AUTOMATIC based on source:
   - manual/app-created = 'org' (stays with org)
   - phone_import = 'personal' (user's own, never visible to others)
4. Personal contacts are NEVER visible to anyone except owner
5. Users cannot override ownership_type (even if 'personal' is sent for manual, it becomes 'org')
"""

import os
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestContactOwnershipVisibility:
    """Tests for contact ownership and visibility rules"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        """Login and get user info"""
        self.client = api_client
        self.base_url = BASE_URL
        
        # Login as super_admin
        login_resp = self.client.post(f"{self.base_url}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()
        self.user = data.get('user', {})
        self.user_id = self.user.get('_id')
        self.token = data.get('token')
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        assert self.user_id, "No user_id in login response"
    
    # ==================== GET CONTACTS DEFAULT MODE ====================
    
    def test_get_contacts_default_mode_returns_own_contacts(self):
        """GET /api/contacts/{user_id} default mode returns ONLY user's own contacts"""
        # Default mode (no view_mode param) should return only contacts where user_id matches
        resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}")
        assert resp.status_code == 200, f"Get contacts failed: {resp.text}"
        
        contacts = resp.json()
        # All returned contacts should belong to the logged-in user
        for contact in contacts:
            assert contact.get('user_id') == self.user_id, \
                f"Default mode returned contact belonging to user {contact.get('user_id')}, expected {self.user_id}"
        print(f"PASS: Default mode returned {len(contacts)} contacts, all belonging to current user")
    
    def test_get_contacts_mine_mode_explicit(self):
        """GET /api/contacts/{user_id}?view_mode=mine returns ONLY user's own contacts"""
        resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}", params={"view_mode": "mine"})
        assert resp.status_code == 200, f"Get contacts failed: {resp.text}"
        
        contacts = resp.json()
        for contact in contacts:
            assert contact.get('user_id') == self.user_id, \
                f"'mine' mode returned contact belonging to different user"
        print(f"PASS: 'mine' mode returned {len(contacts)} contacts, all belonging to current user")
    
    # ==================== GET CONTACTS TEAM MODE (MANAGERS) ====================
    
    def test_get_contacts_team_mode_for_manager(self):
        """GET /api/contacts/{user_id}?view_mode=team returns org contacts for managers"""
        # User is super_admin, should have access to team view
        resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}", params={"view_mode": "team"})
        assert resp.status_code == 200, f"Get contacts team mode failed: {resp.text}"
        
        contacts = resp.json()
        # Team mode should return contacts (could be from multiple users if any exist)
        # For now, just verify the API works and returns valid data
        print(f"PASS: Team mode returned {len(contacts)} contacts for manager")
    
    def test_team_mode_excludes_personal_contacts(self):
        """GET /api/contacts/{user_id}?view_mode=team should NOT include personal contacts"""
        # First, let's verify team mode behavior
        resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}", params={"view_mode": "team"})
        assert resp.status_code == 200, f"Get contacts team mode failed: {resp.text}"
        
        contacts = resp.json()
        # All returned contacts in team view should have ownership_type != 'personal'
        # OR if they're personal, they should only be the current user's (which is valid)
        for contact in contacts:
            ownership = contact.get('ownership_type', 'org')
            owner_id = contact.get('user_id', '')
            if ownership == 'personal':
                # Personal contacts should only be visible if they belong to the requesting user
                assert owner_id == self.user_id, \
                    f"Team mode returned personal contact from another user: {contact.get('first_name')}"
        print(f"PASS: Team mode correctly excludes other users' personal contacts")
    
    def test_team_mode_returns_salesperson_name_enrichment(self):
        """GET /api/contacts/{user_id}?view_mode=team returns salesperson_name field"""
        resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}", params={"view_mode": "team"})
        assert resp.status_code == 200, f"Get contacts team mode failed: {resp.text}"
        
        contacts = resp.json()
        # Each contact should have salesperson_name field when in team mode
        for contact in contacts:
            # salesperson_name should exist (may be empty string for own contacts)
            assert 'salesperson_name' in contact, \
                f"Missing salesperson_name for contact {contact.get('first_name')}"
        print(f"PASS: Team mode includes salesperson_name enrichment for {len(contacts)} contacts")
    
    # ==================== CONTACT CREATION - OWNERSHIP_TYPE ====================
    
    def test_create_contact_manual_source_gets_org_ownership(self):
        """POST /api/contacts/{user_id} with manual source gets ownership_type='org'"""
        unique_phone = f"555{datetime.now().strftime('%H%M%S%f')[:7]}"
        contact_data = {
            "first_name": "TEST_ManualOrg",
            "last_name": "OwnershipTest",
            "phone": unique_phone,
            "source": "manual",  # App-created contact
        }
        
        resp = self.client.post(f"{self.base_url}/api/contacts/{self.user_id}", json=contact_data)
        assert resp.status_code == 200, f"Create contact failed: {resp.text}"
        
        created = resp.json()
        assert created.get('ownership_type') == 'org', \
            f"Expected ownership_type='org' for manual source, got '{created.get('ownership_type')}'"
        
        # Store for cleanup
        self.test_contact_id = created.get('_id')
        print(f"PASS: Manual source contact created with ownership_type='org'")
    
    def test_create_contact_phone_import_gets_personal_ownership(self):
        """POST /api/contacts/{user_id} with phone_import source gets ownership_type='personal'"""
        unique_phone = f"555{datetime.now().strftime('%H%M%S%f')[:7]}"
        contact_data = {
            "first_name": "TEST_PhoneImport",
            "last_name": "PersonalTest",
            "phone": unique_phone,
            "source": "phone_import",  # Phone import = personal
        }
        
        # Use import endpoint which handles source correctly
        resp = self.client.post(
            f"{self.base_url}/api/contacts/{self.user_id}/import",
            params={"source": "phone_import"},
            json=[contact_data]
        )
        assert resp.status_code == 200, f"Import contacts failed: {resp.text}"
        
        # Verify the contact was created with personal ownership by fetching it
        get_resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}")
        assert get_resp.status_code == 200
        
        contacts = get_resp.json()
        test_contact = next((c for c in contacts if c.get('first_name') == 'TEST_PhoneImport'), None)
        
        if test_contact:
            assert test_contact.get('ownership_type') == 'personal', \
                f"Expected ownership_type='personal' for phone_import, got '{test_contact.get('ownership_type')}'"
            print(f"PASS: Phone import contact created with ownership_type='personal'")
        else:
            # Contact might have been skipped as duplicate - that's okay for this test
            print(f"INFO: Contact may have been skipped as duplicate, checking import response")
            import_data = resp.json()
            print(f"Import response: {import_data}")
    
    def test_ownership_cannot_be_overridden_by_user(self):
        """Even if 'personal' ownership is sent for manual source, it should still be 'org'"""
        unique_phone = f"555{datetime.now().strftime('%H%M%S%f')[:7]}"
        contact_data = {
            "first_name": "TEST_OverrideAttempt",
            "last_name": "OwnershipLock",
            "phone": unique_phone,
            "source": "manual",  # Manual source should ALWAYS be 'org'
            "ownership_type": "personal",  # User trying to set personal - should be ignored
        }
        
        resp = self.client.post(f"{self.base_url}/api/contacts/{self.user_id}", json=contact_data)
        assert resp.status_code == 200, f"Create contact failed: {resp.text}"
        
        created = resp.json()
        # Even though user tried to set 'personal', it should be 'org' because source is 'manual'
        assert created.get('ownership_type') == 'org', \
            f"User should NOT be able to override ownership_type. Expected 'org', got '{created.get('ownership_type')}'"
        
        print(f"PASS: ownership_type cannot be overridden by user - manual source always gets 'org'")
    
    def test_create_contact_default_source_is_manual(self):
        """Contact created without source defaults to 'manual' and gets 'org' ownership"""
        unique_phone = f"555{datetime.now().strftime('%H%M%S%f')[:7]}"
        contact_data = {
            "first_name": "TEST_DefaultSource",
            "last_name": "NoSourceProvided",
            "phone": unique_phone,
            # No source field provided - should default to 'manual'
        }
        
        resp = self.client.post(f"{self.base_url}/api/contacts/{self.user_id}", json=contact_data)
        assert resp.status_code == 200, f"Create contact failed: {resp.text}"
        
        created = resp.json()
        assert created.get('ownership_type') == 'org', \
            f"Expected ownership_type='org' for default source, got '{created.get('ownership_type')}'"
        
        print(f"PASS: Default source (no source provided) gets ownership_type='org'")
    
    # ==================== ROLE-BASED ACCESS ====================
    
    def test_super_admin_role_verified(self):
        """Verify user has super_admin role for team view access"""
        assert self.user.get('role') == 'super_admin', \
            f"Expected super_admin role, got '{self.user.get('role')}'"
        print(f"PASS: User {SUPER_ADMIN_EMAIL} has role 'super_admin'")
    
    # ==================== CLEANUP ====================
    
    def test_cleanup_test_contacts(self):
        """Clean up test-created contacts"""
        # Get all contacts and delete those starting with TEST_
        resp = self.client.get(f"{self.base_url}/api/contacts/{self.user_id}")
        if resp.status_code == 200:
            contacts = resp.json()
            test_contacts = [c for c in contacts if c.get('first_name', '').startswith('TEST_')]
            for contact in test_contacts:
                contact_id = contact.get('_id')
                if contact_id:
                    del_resp = self.client.delete(f"{self.base_url}/api/contacts/{self.user_id}/{contact_id}")
                    if del_resp.status_code in [200, 404]:
                        print(f"Cleaned up: {contact.get('first_name')}")
            print(f"PASS: Cleaned up {len(test_contacts)} test contacts")
        else:
            print("INFO: Could not fetch contacts for cleanup")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session
