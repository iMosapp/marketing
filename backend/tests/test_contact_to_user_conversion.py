"""
Test Contact to User Conversion Feature
Tests:
1. Contact search API (GET /api/contacts/{user_id}?search=X)
2. User creation with source_contact_id (POST /api/admin/users/create)
3. Contact linking after user creation (linked_user_id, linked_store_name, linked_role, imos_user tag)
4. Contact detail page shows linked account info
"""
import os
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
SUPER_ADMIN_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"  # API Test contact


class TestContactToUserConversion:
    """Test the CRM Contact to App User conversion feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_USER_ID
        })
        # Login to get auth token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_01_contact_search_api_returns_contacts(self):
        """Test GET /api/contacts/{user_id}?search=X returns contacts list"""
        # Search for contacts with "API" in name
        response = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            params={"search": "API"}
        )
        
        print(f"Contact search response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # API returns plain array, not wrapped in {contacts: []}
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Found {len(data)} contacts matching 'API'")
        
        # Should find at least one contact
        if len(data) > 0:
            contact = data[0]
            print(f"First contact: {contact.get('first_name')} {contact.get('last_name')}")
            # Verify contact has expected fields
            assert '_id' in contact or 'id' in contact, "Contact should have _id or id"
    
    def test_02_contact_search_with_empty_query(self):
        """Test contact search with empty query returns all contacts"""
        response = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total contacts without search filter: {len(data)}")
    
    def test_03_contact_search_with_phone(self):
        """Test contact search by phone number"""
        response = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            params={"search": "555"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} contacts matching '555'")
    
    def test_04_user_creation_endpoint_exists(self):
        """Test POST /api/admin/users/create endpoint exists and validates input"""
        # Test with missing required fields
        response = self.session.post(
            f"{BASE_URL}/api/admin/users/create",
            json={}
        )
        
        # Should return 400 for missing fields, not 404
        assert response.status_code in [400, 422], f"Expected 400/422 for validation error, got {response.status_code}"
        print(f"Validation error response: {response.json()}")
    
    def test_05_create_user_with_source_contact_id(self):
        """Test creating a user with source_contact_id links the contact"""
        # Generate unique email to avoid conflicts
        timestamp = int(time.time())
        test_email = f"test_convert_{timestamp}@test.com"
        
        # First, get a contact to use as source
        contacts_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            params={"search": "API"}
        )
        
        if contacts_resp.status_code != 200 or not contacts_resp.json():
            pytest.skip("No contacts found to test with")
        
        contacts = contacts_resp.json()
        source_contact = contacts[0]
        source_contact_id = source_contact.get('_id') or source_contact.get('id')
        
        print(f"Using source contact: {source_contact.get('first_name')} {source_contact.get('last_name')} (ID: {source_contact_id})")
        
        # Create user with source_contact_id
        create_payload = {
            "first_name": "Test",
            "last_name": "Convert",
            "name": "Test Convert",
            "email": test_email,
            "phone": "+15551234567",
            "role": "user",
            "send_invite": False,
            "source_contact_id": source_contact_id
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/users/create",
            json=create_payload
        )
        
        print(f"Create user response status: {response.status_code}")
        print(f"Create user response: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, "Expected success=True"
        assert 'user_id' in data, "Response should contain user_id"
        assert 'temp_password' in data, "Response should contain temp_password"
        
        created_user_id = data['user_id']
        print(f"Created user ID: {created_user_id}")
        
        # Store for cleanup
        self.created_user_id = created_user_id
        self.source_contact_id = source_contact_id
        
        return created_user_id, source_contact_id
    
    def test_06_verify_contact_linked_after_user_creation(self):
        """Test that source contact has linked_user_id and tags after user creation"""
        # Create user first
        timestamp = int(time.time())
        test_email = f"test_link_verify_{timestamp}@test.com"
        
        # Get a contact
        contacts_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            params={"search": "API"}
        )
        
        if contacts_resp.status_code != 200 or not contacts_resp.json():
            pytest.skip("No contacts found to test with")
        
        contacts = contacts_resp.json()
        source_contact = contacts[0]
        source_contact_id = source_contact.get('_id') or source_contact.get('id')
        
        # Create user with source_contact_id
        create_payload = {
            "first_name": "Link",
            "last_name": "Verify",
            "name": "Link Verify",
            "email": test_email,
            "phone": "+15559876543",
            "role": "store_manager",
            "send_invite": False,
            "source_contact_id": source_contact_id
        }
        
        create_resp = self.session.post(
            f"{BASE_URL}/api/admin/users/create",
            json=create_payload
        )
        
        assert create_resp.status_code == 200, f"User creation failed: {create_resp.text}"
        created_user_id = create_resp.json()['user_id']
        
        # Now fetch the contact and verify it has linked fields
        contact_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}/{source_contact_id}"
        )
        
        assert contact_resp.status_code == 200, f"Failed to fetch contact: {contact_resp.text}"
        
        contact_data = contact_resp.json()
        print(f"Contact after linking: {contact_data}")
        
        # Verify linked_user_id is set
        assert contact_data.get('linked_user_id') == created_user_id, \
            f"Expected linked_user_id={created_user_id}, got {contact_data.get('linked_user_id')}"
        
        # Verify linked_role is set
        assert contact_data.get('linked_role') == 'store_manager', \
            f"Expected linked_role='store_manager', got {contact_data.get('linked_role')}"
        
        # Verify tags include imos_user and role tag
        tags = contact_data.get('tags', [])
        assert 'imos_user' in tags, f"Expected 'imos_user' tag, got tags: {tags}"
        assert 'imos_store_manager' in tags, f"Expected 'imos_store_manager' tag, got tags: {tags}"
        
        print(f"Contact successfully linked with user_id={created_user_id}, role=store_manager, tags={tags}")
    
    def test_07_add_user_modal_import_section_exists(self):
        """Test that the Add User modal has Import from Contact section (frontend code check)"""
        # This is a code verification test - we check the frontend file has the expected elements
        import os
        
        users_tsx_path = "/app/frontend/app/admin/users.tsx"
        assert os.path.exists(users_tsx_path), "users.tsx file should exist"
        
        with open(users_tsx_path, 'r') as f:
            content = f.read()
        
        # Check for Import from Contact section
        assert 'Import from Contact' in content, "Should have 'Import from Contact' text"
        assert 'contact-search-input' in content, "Should have contact-search-input data-testid"
        assert 'searchContacts' in content, "Should have searchContacts function"
        assert 'source_contact_id' in content, "Should send source_contact_id in create request"
        
        print("Frontend code verification passed - Import from Contact section exists")
    
    def test_08_contact_detail_linked_account_card_exists(self):
        """Test that contact detail page has Linked App Account card (frontend code check)"""
        import os
        
        contact_tsx_path = "/app/frontend/app/contact/[id].tsx"
        assert os.path.exists(contact_tsx_path), "contact/[id].tsx file should exist"
        
        with open(contact_tsx_path, 'r') as f:
            content = f.read()
        
        # Check for Linked App Account card
        assert 'Linked App Account' in content, "Should have 'Linked App Account' comment"
        assert 'linked_user_id' in content, "Should check linked_user_id"
        assert 'linked_store_name' in content, "Should display linked_store_name"
        assert 'linked_role' in content, "Should display linked_role"
        assert 'linked-account-card' in content, "Should have linked-account-card data-testid"
        
        print("Frontend code verification passed - Linked App Account card exists")
    
    def test_09_backend_handles_source_contact_linking(self):
        """Test that backend admin.py has source_contact_id handling"""
        import os
        
        admin_py_path = "/app/backend/routers/admin.py"
        assert os.path.exists(admin_py_path), "admin.py file should exist"
        
        with open(admin_py_path, 'r') as f:
            content = f.read()
        
        # Check for source_contact_id handling
        assert 'source_contact_id' in content, "Should handle source_contact_id"
        assert 'linked_user_id' in content, "Should set linked_user_id on contact"
        assert 'linked_store_name' in content, "Should set linked_store_name on contact"
        assert 'linked_role' in content, "Should set linked_role on contact"
        assert 'imos_user' in content, "Should add imos_user tag"
        
        print("Backend code verification passed - source_contact_id handling exists")


class TestContactSearchAPI:
    """Additional tests for contact search API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_USER_ID
        })
        yield
        self.session.close()
    
    def test_search_by_email(self):
        """Test contact search by email"""
        response = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            params={"search": "@"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} contacts with '@' in search")
    
    def test_search_returns_required_fields(self):
        """Test that contact search returns fields needed for import"""
        response = self.session.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            params={"search": "test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            contact = data[0]
            # Check required fields for import
            required_fields = ['first_name', 'last_name']
            for field in required_fields:
                assert field in contact, f"Contact should have {field} field"
            
            # Check optional but useful fields
            optional_fields = ['email', 'phone']
            for field in optional_fields:
                if field in contact:
                    print(f"Contact has {field}: {contact[field]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
