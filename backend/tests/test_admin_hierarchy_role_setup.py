"""
Backend API Tests for Admin Panel, User Management, and Setup Wizard
Testing the fixes for:
1. GET /api/admin/hierarchy/users - was crashing on invalid ObjectIds like 'org_001'
2. PUT /api/admin/hierarchy/users/{user_id}/role - change user role
3. POST /api/admin/organizations - create organization
4. POST /api/admin/stores - create store
5. PUT /api/admin/stores/{store_id} - save branding
6. POST /api/admin/users - create user
7. PUT /api/admin/stores/{store_id}/review-links - save review links
8. GET /api/admin/users/{user_id}/detail - user detail with role/org/stores
"""
import os
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials for super admin
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestAuth:
    """Authentication to get super admin token and user_id"""
    
    @pytest.fixture(scope="class")
    def auth_data(self):
        """Login as super admin and return token + user_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        assert "user" in data, "No user in login response"
        return {
            "token": data["token"],
            "user_id": data["user"]["_id"],
            "user": data["user"]
        }
    
    def test_login_super_admin(self, auth_data):
        """Test super admin login works"""
        assert auth_data["token"] is not None
        assert auth_data["user"]["role"] == "super_admin"
        print(f"✓ Super admin login successful, user_id: {auth_data['user_id']}")


class TestHierarchyUsersEndpoint:
    """Test GET /api/admin/hierarchy/users endpoint - was crashing on invalid ObjectIds"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    def test_hierarchy_users_no_500_error(self, auth_headers):
        """GET /api/admin/hierarchy/users should return 200, not 500"""
        response = requests.get(f"{BASE_URL}/api/admin/hierarchy/users", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "users" in data, "Response missing 'users' key"
        assert "total" in data, "Response missing 'total' key"
        print(f"✓ GET /api/admin/hierarchy/users returns {data['total']} users without crash")
    
    def test_hierarchy_users_structure(self, auth_headers):
        """Verify user objects have expected fields"""
        response = requests.get(f"{BASE_URL}/api/admin/hierarchy/users", headers=auth_headers)
        data = response.json()
        if data["total"] > 0:
            user = data["users"][0]
            assert "_id" in user, "User missing _id"
            assert "name" in user, "User missing name"
            assert "email" in user, "User missing email"
            assert "role" in user, "User missing role"
            assert "is_active" in user, "User missing is_active"
            print(f"✓ User structure validated: {user['name']} ({user['role']})")
        else:
            print("⚠ No users found to validate structure")


class TestRoleChangeEndpoint:
    """Test PUT /api/admin/hierarchy/users/{user_id}/role endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_user_id(self, auth_headers):
        """Get or create a test user for role change testing"""
        # First try to find an existing test user
        response = requests.get(f"{BASE_URL}/api/admin/hierarchy/users", headers=auth_headers)
        data = response.json()
        
        # Find a non-super_admin user to test with
        for user in data.get("users", []):
            if user["role"] != "super_admin" and "test_role_change" in user.get("email", ""):
                return user["_id"]
        
        # If no existing test user, create one
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        create_response = requests.post(f"{BASE_URL}/api/admin/users", headers=auth_headers, json={
            "name": f"Test Role Change User {timestamp}",
            "email": f"test_role_change_{timestamp}@test.com",
            "password": "TestPass123!",
            "role": "user",
            "phone": ""
        })
        if create_response.status_code in [200, 201]:
            return create_response.json().get("_id") or create_response.json().get("id")
        
        # Fallback: use any non-super_admin user
        for user in data.get("users", []):
            if user["role"] != "super_admin":
                return user["_id"]
        
        pytest.skip("No suitable user found for role change testing")
    
    def test_change_role_to_user(self, auth_headers, test_user_id):
        """Change a user's role to 'user'"""
        response = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/role",
            headers=auth_headers,
            json={"role": "user"}
        )
        assert response.status_code == 200, f"Role change to 'user' failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ok" or data.get("role") == "user", f"Unexpected response: {data}"
        print(f"✓ Role changed to 'user' successfully")
    
    def test_change_role_to_store_manager(self, auth_headers, test_user_id):
        """Change a user's role to 'store_manager'"""
        response = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/role",
            headers=auth_headers,
            json={"role": "store_manager"}
        )
        assert response.status_code == 200, f"Role change to 'store_manager' failed: {response.text}"
        print(f"✓ Role changed to 'store_manager' successfully")
    
    def test_change_role_to_org_admin(self, auth_headers, test_user_id):
        """Change a user's role to 'org_admin'"""
        response = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/role",
            headers=auth_headers,
            json={"role": "org_admin"}
        )
        assert response.status_code == 200, f"Role change to 'org_admin' failed: {response.text}"
        print(f"✓ Role changed to 'org_admin' successfully")
    
    def test_invalid_role_rejected(self, auth_headers, test_user_id):
        """Invalid role should be rejected with 400"""
        response = requests.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/role",
            headers=auth_headers,
            json={"role": "invalid_role"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid role, got {response.status_code}"
        print(f"✓ Invalid role correctly rejected")


class TestOrganizationCRUD:
    """Test organization create endpoint for setup wizard"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    def test_create_organization(self, auth_headers):
        """POST /api/admin/organizations should create a new organization"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        response = requests.post(f"{BASE_URL}/api/admin/organizations", headers=auth_headers, json={
            "name": f"Test Org {timestamp}",
            "admin_email": "admin@testorg.com",
            "admin_phone": "555-123-4567",
            "city": "Test City",
            "state": "TX"
        })
        assert response.status_code in [200, 201], f"Create org failed: {response.text}"
        data = response.json()
        assert "_id" in data or "id" in data, "No id in response"
        assert data.get("name") == f"Test Org {timestamp}", "Name mismatch"
        print(f"✓ Organization created: {data.get('name')}")
        return data.get("_id") or data.get("id")
    
    def test_list_organizations(self, auth_headers):
        """GET /api/admin/organizations should return list"""
        response = requests.get(f"{BASE_URL}/api/admin/organizations", headers=auth_headers)
        assert response.status_code == 200, f"List orgs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of organizations"
        print(f"✓ Listed {len(data)} organizations")


class TestStoreCRUD:
    """Test store create and update endpoints for setup wizard"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_org_id(self, auth_headers):
        """Get or create an organization for store tests"""
        # Get existing org
        response = requests.get(f"{BASE_URL}/api/admin/organizations", headers=auth_headers)
        data = response.json()
        if data and len(data) > 0:
            return data[0]["_id"]
        
        # Create one
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        create_response = requests.post(f"{BASE_URL}/api/admin/organizations", headers=auth_headers, json={
            "name": f"Test Org for Store {timestamp}",
            "admin_email": "store@test.com"
        })
        return create_response.json().get("_id") or create_response.json().get("id")
    
    def test_create_store(self, auth_headers, test_org_id):
        """POST /api/admin/stores should create a new store"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        response = requests.post(f"{BASE_URL}/api/admin/stores", headers=auth_headers, json={
            "name": f"Test Store {timestamp}",
            "organization_id": test_org_id,
            "phone": "555-987-6543",
            "city": "Austin",
            "state": "TX",
            "website": "https://teststore.com",
            "industry": "Automotive / Dealership"
        })
        assert response.status_code in [200, 201], f"Create store failed: {response.text}"
        data = response.json()
        assert "_id" in data or "id" in data, "No id in response"
        print(f"✓ Store created: {data.get('name')}")
        return data.get("_id") or data.get("id")
    
    def test_update_store_branding(self, auth_headers, test_org_id):
        """PUT /api/admin/stores/{store_id} should update branding"""
        # First create a store
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        create_response = requests.post(f"{BASE_URL}/api/admin/stores", headers=auth_headers, json={
            "name": f"Branding Test Store {timestamp}",
            "organization_id": test_org_id
        })
        store_id = create_response.json().get("_id") or create_response.json().get("id")
        
        # Update branding
        response = requests.put(f"{BASE_URL}/api/admin/stores/{store_id}", headers=auth_headers, json={
            "primary_color": "#C9A962",
            "email_footer": "Thank you for your business!"
        })
        assert response.status_code == 200, f"Update branding failed: {response.text}"
        print(f"✓ Store branding updated successfully")


class TestReviewLinks:
    """Test review links save endpoint for setup wizard"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_store_id(self, auth_headers):
        """Get an existing store for review link tests"""
        response = requests.get(f"{BASE_URL}/api/admin/stores", headers=auth_headers)
        data = response.json()
        if data and len(data) > 0:
            return data[0]["_id"]
        pytest.skip("No stores available for review link testing")
    
    def test_save_review_links(self, auth_headers, test_store_id):
        """PUT /api/admin/stores/{store_id}/review-links should save review links"""
        response = requests.put(f"{BASE_URL}/api/admin/stores/{test_store_id}/review-links", headers=auth_headers, json={
            "google": "https://g.page/review/test-store",
            "facebook": "https://facebook.com/test-store/reviews",
            "yelp": "https://yelp.com/biz/test-store"
        })
        assert response.status_code == 200, f"Save review links failed: {response.text}"
        data = response.json()
        assert "review_links" in data or "message" in data, "Unexpected response"
        print(f"✓ Review links saved successfully")
    
    def test_get_review_links(self, auth_headers, test_store_id):
        """GET /api/admin/stores/{store_id}/review-links should return links"""
        response = requests.get(f"{BASE_URL}/api/admin/stores/{test_store_id}/review-links", headers=auth_headers)
        assert response.status_code == 200, f"Get review links failed: {response.text}"
        data = response.json()
        # Response should have review link fields
        assert isinstance(data, dict), "Expected dictionary of review links"
        print(f"✓ Review links retrieved: {list(data.keys())}")


class TestUserCreate:
    """Test user creation endpoint for setup wizard team roster"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_store_id(self, auth_headers):
        """Get an existing store"""
        response = requests.get(f"{BASE_URL}/api/admin/stores", headers=auth_headers)
        data = response.json()
        if data and len(data) > 0:
            return data[0]["_id"]
        return None
    
    @pytest.fixture(scope="class")
    def test_org_id(self, auth_headers):
        """Get an existing org"""
        response = requests.get(f"{BASE_URL}/api/admin/organizations", headers=auth_headers)
        data = response.json()
        if data and len(data) > 0:
            return data[0]["_id"]
        return None
    
    def test_create_user_with_all_fields(self, auth_headers, test_store_id, test_org_id):
        """POST /api/admin/users should create a user with name, email, phone, password, role"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        response = requests.post(f"{BASE_URL}/api/admin/users", headers=auth_headers, json={
            "name": f"Test User {timestamp}",
            "email": f"testuser_{timestamp}@test.com",
            "phone": "555-111-2222",
            "password": "Welcome1234!",
            "role": "user",
            "store_id": test_store_id,
            "organization_id": test_org_id,
            "needs_password_change": True
        })
        assert response.status_code in [200, 201], f"Create user failed: {response.text}"
        data = response.json()
        assert "_id" in data or "id" in data, "No id in response"
        assert data.get("email") == f"testuser_{timestamp}@test.com", "Email mismatch"
        print(f"✓ User created: {data.get('name')} ({data.get('email')})")


class TestUserDetail:
    """Test user detail endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        data = response.json()
        return {
            "Authorization": f"Bearer {data['token']}",
            "X-User-ID": data["user"]["_id"],
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_user_id(self, auth_headers):
        """Get a user ID to test detail endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/hierarchy/users", headers=auth_headers)
        data = response.json()
        if data.get("users") and len(data["users"]) > 0:
            return data["users"][0]["_id"]
        pytest.skip("No users available for detail testing")
    
    def test_get_user_detail(self, auth_headers, test_user_id):
        """GET /api/admin/users/{user_id}/detail should return user with role, org, stores"""
        response = requests.get(f"{BASE_URL}/api/admin/users/{test_user_id}/detail", headers=auth_headers)
        assert response.status_code == 200, f"Get user detail failed: {response.text}"
        data = response.json()
        
        assert "user" in data, "Response missing 'user' key"
        user = data["user"]
        assert "_id" in user, "User missing _id"
        assert "role" in user, "User missing role"
        
        # May have organization and stores
        print(f"✓ User detail retrieved: {user.get('name')}, role: {user.get('role')}")
        if data.get("organization"):
            print(f"  Organization: {data['organization'].get('name')}")
        if data.get("stores"):
            print(f"  Stores: {[s.get('name') for s in data['stores']]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
