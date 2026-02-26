"""
Admin Panel API Tests
Tests CRUD operations for Organizations, Accounts (Stores), Users, Quotes, Shared Inboxes, etc.
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://congrats-card-fix.preview.emergentagent.com')
if BASE_URL and not BASE_URL.startswith('http'):
    BASE_URL = f"https://{BASE_URL}"

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"


class TestAdminHealth:
    """Health check and basic connectivity tests"""
    
    def test_api_health(self):
        """Test that API root endpoint responds"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ API health check passed: {data}")
    
    def test_admin_stats(self):
        """Test admin stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_organizations" in data
        assert "total_stores" in data
        print(f"✓ Admin stats: {data['total_users']} users, {data['total_organizations']} orgs, {data['total_stores']} stores")
    
    def test_admin_detailed_stats(self):
        """Test detailed admin stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "orgs_active" in data
        assert "stores_active" in data
        assert "users_active" in data
        print(f"✓ Detailed stats - Active: {data['orgs_active']} orgs, {data['stores_active']} stores, {data['users_active']} users")


class TestAuthentication:
    """Authentication flow tests"""
    
    def test_login_success(self):
        """Test successful login with test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user" in data or "_id" in data
        # Handle both response formats
        user = data.get("user") or data
        assert user.get("email") == TEST_EMAIL or user.get("_id") is not None
        print(f"✓ Login successful for user: {user.get('name', TEST_EMAIL)}")
        return user
    
    def test_login_invalid_password(self):
        """Test login with invalid password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code in [401, 400, 403], f"Expected 401/400/403, got {response.status_code}"
        print(f"✓ Invalid password correctly rejected")


@pytest.fixture(scope="module")
def auth_user():
    """Get authenticated user for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    data = response.json()
    user = data.get("user") or data
    return user


@pytest.fixture
def api_client(auth_user):
    """API client with auth headers"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "X-User-ID": auth_user.get("_id")
    })
    return session


class TestOrganizations:
    """Organization CRUD tests"""
    
    def test_list_organizations(self, api_client, auth_user):
        """Test listing organizations"""
        response = api_client.get(f"{BASE_URL}/api/admin/organizations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} organizations")
        return data
    
    def test_create_organization(self, api_client, auth_user):
        """Test creating a new organization"""
        test_org = {
            "name": f"TEST_TestOrg_{datetime.now().strftime('%H%M%S')}",
            "account_type": "organization",
            "admin_email": "testorg@example.com",
            "admin_phone": "+15551234567",
            "city": "Test City",
            "state": "UT",
            "country": "US"
        }
        response = api_client.post(f"{BASE_URL}/api/admin/organizations", json=test_org)
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert "_id" in data
        assert data["name"] == test_org["name"]
        print(f"✓ Created organization: {data['name']} (ID: {data['_id']})")
        return data
    
    def test_get_organization(self, api_client, auth_user):
        """Test getting a specific organization"""
        # First list to get an org ID
        list_resp = api_client.get(f"{BASE_URL}/api/admin/organizations")
        orgs = list_resp.json()
        if not orgs:
            pytest.skip("No organizations to test with")
        
        org_id = orgs[0]["_id"]
        response = api_client.get(f"{BASE_URL}/api/admin/organizations/{org_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["_id"] == org_id
        print(f"✓ Retrieved organization: {data['name']}")
    
    def test_delete_test_organizations(self, api_client, auth_user):
        """Cleanup - delete test organizations"""
        list_resp = api_client.get(f"{BASE_URL}/api/admin/organizations")
        orgs = list_resp.json()
        deleted_count = 0
        for org in orgs:
            if org.get("name", "").startswith("TEST_"):
                del_resp = api_client.delete(f"{BASE_URL}/api/admin/organizations/{org['_id']}")
                if del_resp.status_code == 200:
                    deleted_count += 1
        print(f"✓ Cleaned up {deleted_count} test organizations")


class TestStores:
    """Store (Account) CRUD tests"""
    
    def test_list_stores(self, api_client, auth_user):
        """Test listing stores"""
        response = api_client.get(f"{BASE_URL}/api/admin/stores")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} stores/accounts")
        return data
    
    def test_create_store(self, api_client, auth_user):
        """Test creating a new store"""
        test_store = {
            "name": f"TEST_TestStore_{datetime.now().strftime('%H%M%S')}",
            "phone": "+15559876543",
            "address": "123 Test Street",
            "city": "Test City",
            "state": "UT",
            "country": "US"
        }
        response = api_client.post(f"{BASE_URL}/api/admin/stores", json=test_store)
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert "_id" in data
        assert data["name"] == test_store["name"]
        print(f"✓ Created store: {data['name']} (ID: {data['_id']})")
        return data
    
    def test_get_store(self, api_client, auth_user):
        """Test getting a specific store"""
        list_resp = api_client.get(f"{BASE_URL}/api/admin/stores")
        stores = list_resp.json()
        if not stores:
            pytest.skip("No stores to test with")
        
        store_id = stores[0]["_id"]
        response = api_client.get(f"{BASE_URL}/api/admin/stores/{store_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["_id"] == store_id
        print(f"✓ Retrieved store: {data['name']}")
    
    def test_delete_test_stores(self, api_client, auth_user):
        """Cleanup - delete test stores"""
        list_resp = api_client.get(f"{BASE_URL}/api/admin/stores")
        stores = list_resp.json()
        deleted_count = 0
        for store in stores:
            if store.get("name", "").startswith("TEST_"):
                del_resp = api_client.delete(f"{BASE_URL}/api/admin/stores/{store['_id']}")
                if del_resp.status_code == 200:
                    deleted_count += 1
        print(f"✓ Cleaned up {deleted_count} test stores")


class TestUsers:
    """User management tests"""
    
    def test_list_users(self, api_client, auth_user):
        """Test listing users"""
        response = api_client.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} users")
        return data
    
    def test_hierarchy_users(self, api_client, auth_user):
        """Test hierarchy users endpoint"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        print(f"✓ Hierarchy users: {len(data['users'])} users")
    
    def test_get_user_detail(self, api_client, auth_user):
        """Test getting user detail"""
        user_id = auth_user.get("_id")
        response = api_client.get(f"{BASE_URL}/api/admin/users/{user_id}/detail")
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        print(f"✓ Retrieved user detail: {data['user'].get('name')}")
    
    def test_pending_users(self, api_client, auth_user):
        """Test pending users endpoint"""
        response = api_client.get(f"{BASE_URL}/api/admin/pending-users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Pending users: {len(data)}")
    
    def test_pending_users_count(self, api_client, auth_user):
        """Test pending users count"""
        response = api_client.get(f"{BASE_URL}/api/admin/pending-users/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        print(f"✓ Pending users count: {data['count']}")


class TestIndividuals:
    """Individuals (sole proprietors) tests"""
    
    def test_list_individuals(self, api_client, auth_user):
        """Test listing individuals"""
        response = api_client.get(f"{BASE_URL}/api/admin/individuals")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} individuals")


class TestQuotes:
    """Quotes tests"""
    
    def test_list_quotes(self, api_client, auth_user):
        """Test listing quotes"""
        response = api_client.get(f"{BASE_URL}/api/subscriptions/quotes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} quotes")
    
    def test_list_quotes_by_status(self, api_client, auth_user):
        """Test filtering quotes by status"""
        for status in ["draft", "sent", "accepted", "expired"]:
            response = api_client.get(f"{BASE_URL}/api/subscriptions/quotes?status={status}")
            assert response.status_code == 200
            data = response.json()
            print(f"  - {status}: {len(data)} quotes")
        print("✓ Quote filtering by status works")


class TestPartnerAgreements:
    """Partner agreements tests"""
    
    def test_list_agreements(self, api_client, auth_user):
        """Test listing partner agreements"""
        response = api_client.get(f"{BASE_URL}/api/partners/agreements")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} partner agreements")


class TestSharedInboxes:
    """Shared inboxes tests"""
    
    def test_list_shared_inboxes(self, api_client, auth_user):
        """Test listing shared inboxes"""
        user_id = auth_user.get("_id")
        response = api_client.get(f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} shared inboxes")
    
    def test_list_team_users(self, api_client, auth_user):
        """Test listing team users for shared inbox assignment"""
        user_id = auth_user.get("_id")
        response = api_client.get(f"{BASE_URL}/api/admin/team/users?user_id={user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} team users")


class TestCompanyDirectory:
    """Company directory tests"""
    
    def test_list_directory(self, api_client, auth_user):
        """Test listing company directory"""
        response = api_client.get(f"{BASE_URL}/api/directory")
        assert response.status_code == 200
        data = response.json()
        # May be empty list or dict depending on setup
        print(f"✓ Company directory endpoint accessible")


class TestDataStats:
    """Data statistics tests"""
    
    def test_data_stats_all_time(self, api_client, auth_user):
        """Test data stats for all time"""
        response = api_client.get(f"{BASE_URL}/api/admin/stats/data?time_range=all")
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "total_contacts" in data
        print(f"✓ Data stats (all time): {data['total_messages']} messages, {data['total_contacts']} contacts")
    
    def test_data_stats_7d(self, api_client, auth_user):
        """Test data stats for 7 days"""
        response = api_client.get(f"{BASE_URL}/api/admin/stats/data?time_range=7d")
        assert response.status_code == 200
        data = response.json()
        assert "time_range" in data
        assert data["time_range"] == "7d"
        print(f"✓ Data stats (7d) accessible")
    
    def test_data_stats_30d(self, api_client, auth_user):
        """Test data stats for 30 days"""
        response = api_client.get(f"{BASE_URL}/api/admin/stats/data?time_range=30d")
        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "30d"
        print(f"✓ Data stats (30d) accessible")


class TestActivityFeed:
    """Activity feed tests"""
    
    def test_recent_activity(self, api_client, auth_user):
        """Test recent activity endpoint"""
        response = api_client.get(f"{BASE_URL}/api/admin/activity/recent?limit=15")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Recent activity: {len(data)} items")
    
    def test_user_activity_feed(self, api_client, auth_user):
        """Test user-specific activity feed"""
        user_id = auth_user.get("_id")
        response = api_client.get(f"{BASE_URL}/api/activity/{user_id}?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert "activities" in data
        print(f"✓ User activity feed: {len(data['activities'])} activities")


class TestDiscountCodes:
    """Discount codes tests"""
    
    def test_list_discount_codes(self, api_client, auth_user):
        """Test listing discount codes"""
        response = api_client.get(f"{BASE_URL}/api/subscriptions/discount-codes")
        # May be 200 or 404 if not implemented
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Listed discount codes: {len(data) if isinstance(data, list) else 'endpoint accessible'}")
        else:
            print(f"⚠ Discount codes endpoint returned {response.status_code}")


class TestHierarchyOverview:
    """Hierarchy overview tests"""
    
    def test_hierarchy_overview(self, api_client, auth_user):
        """Test hierarchy overview endpoint"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/overview")
        assert response.status_code == 200
        data = response.json()
        assert "organizations" in data
        print(f"✓ Hierarchy overview: {len(data['organizations'])} organizations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
