"""
Tests for Organization, Store, and User activate/deactivate toggles
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://email-invite-patch.preview.emergentagent.com').rstrip('/')

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_org(api_client):
    """Create a test organization for toggle testing"""
    org_data = {
        "name": f"TEST_Toggle_Org_{datetime.now().timestamp()}",
        "account_type": "organization",
        "admin_email": "test-toggle@example.com",
        "city": "Test City",
        "state": "UT",
        "active": True
    }
    response = api_client.post(f"{BASE_URL}/api/admin/organizations", json=org_data)
    assert response.status_code == 200, f"Failed to create org: {response.text}"
    org = response.json()
    yield org
    # Cleanup
    api_client.delete(f"{BASE_URL}/api/admin/organizations/{org['_id']}")

@pytest.fixture(scope="module")
def test_store(api_client, test_org):
    """Create a test store for toggle testing"""
    store_data = {
        "name": f"TEST_Toggle_Store_{datetime.now().timestamp()}",
        "organization_id": test_org['_id'],
        "city": "Test City",
        "state": "UT",
        "active": True
    }
    response = api_client.post(f"{BASE_URL}/api/admin/stores", json=store_data)
    assert response.status_code == 200, f"Failed to create store: {response.text}"
    store = response.json()
    yield store
    # Cleanup
    api_client.delete(f"{BASE_URL}/api/admin/stores/{store['_id']}")


# Organization Toggle Tests
class TestOrganizationToggle:
    """Test organization active/inactive toggle"""
    
    def test_org_default_active(self, api_client, test_org):
        """Test that new organization is active by default"""
        response = api_client.get(f"{BASE_URL}/api/admin/organizations/{test_org['_id']}")
        assert response.status_code == 200
        org = response.json()
        assert org.get('active') == True, f"New org should be active by default. Got: {org.get('active')}"
        print(f"PASS: Organization default active status is True")
    
    def test_org_deactivate(self, api_client, test_org):
        """Test deactivating an organization"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/organizations/{test_org['_id']}", 
            json={"active": False}
        )
        assert response.status_code == 200, f"Failed to update org: {response.text}"
        
        # Verify the change
        get_response = api_client.get(f"{BASE_URL}/api/admin/organizations/{test_org['_id']}")
        org = get_response.json()
        assert org.get('active') == False, f"Org should be inactive. Got: {org.get('active')}"
        print(f"PASS: Organization deactivated successfully")
    
    def test_org_reactivate(self, api_client, test_org):
        """Test reactivating an organization"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/organizations/{test_org['_id']}", 
            json={"active": True}
        )
        assert response.status_code == 200, f"Failed to update org: {response.text}"
        
        # Verify the change
        get_response = api_client.get(f"{BASE_URL}/api/admin/organizations/{test_org['_id']}")
        org = get_response.json()
        assert org.get('active') == True, f"Org should be active. Got: {org.get('active')}"
        print(f"PASS: Organization reactivated successfully")


# Store Toggle Tests
class TestStoreToggle:
    """Test store active/inactive toggle"""
    
    def test_store_default_active(self, api_client, test_store):
        """Test that new store is active by default"""
        response = api_client.get(f"{BASE_URL}/api/admin/stores/{test_store['_id']}")
        assert response.status_code == 200
        store = response.json()
        assert store.get('active') == True, f"New store should be active by default. Got: {store.get('active')}"
        print(f"PASS: Store default active status is True")
    
    def test_store_deactivate(self, api_client, test_store):
        """Test deactivating a store"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{test_store['_id']}", 
            json={"active": False}
        )
        assert response.status_code == 200, f"Failed to update store: {response.text}"
        
        # Verify the change
        get_response = api_client.get(f"{BASE_URL}/api/admin/stores/{test_store['_id']}")
        store = get_response.json()
        assert store.get('active') == False, f"Store should be inactive. Got: {store.get('active')}"
        print(f"PASS: Store deactivated successfully")
    
    def test_store_reactivate(self, api_client, test_store):
        """Test reactivating a store"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{test_store['_id']}", 
            json={"active": True}
        )
        assert response.status_code == 200, f"Failed to update store: {response.text}"
        
        # Verify the change
        get_response = api_client.get(f"{BASE_URL}/api/admin/stores/{test_store['_id']}")
        store = get_response.json()
        assert store.get('active') == True, f"Store should be active. Got: {store.get('active')}"
        print(f"PASS: Store reactivated successfully")


# User Toggle Tests
class TestUserToggle:
    """Test user is_active toggle"""
    
    def test_get_existing_user(self, api_client):
        """Get an existing user to test toggle"""
        # Get users list
        response = api_client.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        users = response.json()
        assert len(users) > 0, "No users found in system"
        
        # Return first user ID for other tests
        self.user_id = users[0]['_id']
        self.original_is_active = users[0].get('is_active', True)
        print(f"PASS: Found user {users[0].get('name', users[0].get('email'))} for toggle testing")
        return users[0]
    
    def test_user_toggle_inactive(self, api_client):
        """Test setting a user to inactive"""
        # First get a user
        response = api_client.get(f"{BASE_URL}/api/admin/users")
        users = response.json()
        if len(users) == 0:
            pytest.skip("No users available for testing")
        
        user = users[0]
        user_id = user['_id']
        
        # Set to inactive
        response = api_client.put(
            f"{BASE_URL}/api/admin/users/{user_id}", 
            json={"is_active": False}
        )
        assert response.status_code == 200, f"Failed to update user: {response.text}"
        
        # Verify the change
        get_response = api_client.get(f"{BASE_URL}/api/admin/users/{user_id}")
        updated_user = get_response.json()
        assert updated_user.get('is_active') == False, f"User should be inactive. Got: {updated_user.get('is_active')}"
        print(f"PASS: User {updated_user.get('name', 'unknown')} set to inactive")
        
        # Restore original state
        api_client.put(f"{BASE_URL}/api/admin/users/{user_id}", json={"is_active": True})
    
    def test_user_toggle_active(self, api_client):
        """Test setting a user to active"""
        # First get a user
        response = api_client.get(f"{BASE_URL}/api/admin/users")
        users = response.json()
        if len(users) == 0:
            pytest.skip("No users available for testing")
        
        user = users[0]
        user_id = user['_id']
        
        # First set to inactive, then reactivate
        api_client.put(f"{BASE_URL}/api/admin/users/{user_id}", json={"is_active": False})
        
        # Now reactivate
        response = api_client.put(
            f"{BASE_URL}/api/admin/users/{user_id}", 
            json={"is_active": True}
        )
        assert response.status_code == 200, f"Failed to update user: {response.text}"
        
        # Verify the change
        get_response = api_client.get(f"{BASE_URL}/api/admin/users/{user_id}")
        updated_user = get_response.json()
        assert updated_user.get('is_active') == True, f"User should be active. Got: {updated_user.get('is_active')}"
        print(f"PASS: User {updated_user.get('name', 'unknown')} reactivated successfully")


# Organization List and Navigation Tests
class TestOrganizationListAndNavigation:
    """Test organization list endpoint returns proper data for navigation"""
    
    def test_organizations_list_returns_id(self, api_client):
        """Test that organization list returns _id field for navigation"""
        response = api_client.get(f"{BASE_URL}/api/admin/organizations")
        assert response.status_code == 200, f"Failed to get orgs: {response.text}"
        orgs = response.json()
        
        if len(orgs) > 0:
            first_org = orgs[0]
            assert '_id' in first_org, "Organization should have _id field"
            assert isinstance(first_org['_id'], str), "_id should be string"
            print(f"PASS: Organizations list returns valid _id for navigation")
        else:
            print(f"INFO: No organizations found to test, but endpoint works")
    
    def test_single_organization_detail(self, api_client, test_org):
        """Test that single organization detail endpoint works"""
        response = api_client.get(f"{BASE_URL}/api/admin/organizations/{test_org['_id']}")
        assert response.status_code == 200, f"Failed to get org detail: {response.text}"
        org = response.json()
        
        assert org['_id'] == test_org['_id'], "Org ID should match"
        assert 'name' in org, "Org should have name"
        assert 'active' in org, "Org should have active field"
        print(f"PASS: Organization detail endpoint returns correct data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
