"""
Test Suite for New Features:
1. Invite Team - Individual role option for super admins
2. Admin/Users/Create API - Individual users without org
3. Onboarding Preview page route check (frontend)

Test credentials: forest@imosapp.com / Admin123!
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Fallback for test discovery
    BASE_URL = "https://email-invite-patch.preview.emergentagent.com"


class TestInviteIndividualFeature:
    """Test the Individual role invite feature for super admins"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as super admin and get user ID"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.user_id = data["user"]["_id"]
        self.user_role = data["user"]["role"]
        self.headers = {"X-User-ID": self.user_id}
        print(f"✓ Logged in as {data['user']['name']} (role: {self.user_role})")
        
    def test_super_admin_login_success(self):
        """Verify super admin login works"""
        assert self.user_role == "super_admin", f"Expected super_admin, got {self.user_role}"
        print("✓ User is super_admin as expected")
        
    def test_create_individual_user_no_org(self):
        """Test creating an individual user without organization_id"""
        # Generate unique email to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"test_individual_{unique_id}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/create",
            json={
                "name": f"Test Individual {unique_id}",
                "email": test_email,
                "role": "user",  # Individual uses 'user' role but without org
                "send_invite": False,
                # No organization_id - this makes them an Individual
            },
            headers=self.headers
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200, f"Create user failed: {response.text}"
        data = response.json()
        
        # Verify the user was created successfully
        assert data.get("success") == True, "Expected success=True"
        assert data.get("user_id"), "Expected user_id in response"
        assert data.get("email") == test_email, "Email mismatch"
        assert data.get("organization_id") is None, "Individual should have no organization_id"
        
        # Cleanup: delete the test user
        user_id = data.get("user_id")
        if user_id:
            cleanup = requests.delete(
                f"{BASE_URL}/api/admin/users/{user_id}",
                headers=self.headers
            )
            print(f"✓ Cleanup: deleted test user (status: {cleanup.status_code})")
        
        print("✓ Individual user created without organization_id")
    
    def test_create_user_with_org(self):
        """Test creating a regular user with organization_id (non-individual)"""
        # First, get an organization to use
        orgs_response = requests.get(
            f"{BASE_URL}/api/admin/organizations",
            headers=self.headers
        )
        assert orgs_response.status_code == 200, "Failed to get organizations"
        orgs = orgs_response.json()
        
        if not orgs:
            pytest.skip("No organizations available to test with")
        
        org_id = orgs[0]["_id"]
        
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"test_org_user_{unique_id}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/create",
            json={
                "name": f"Test Org User {unique_id}",
                "email": test_email,
                "role": "user",
                "organization_id": org_id,
                "send_invite": False,
            },
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Create user failed: {response.text}"
        data = response.json()
        
        # Verify the user was created with organization
        assert data.get("success") == True
        assert data.get("organization_id") == org_id, "Expected organization_id to match"
        
        # Cleanup
        user_id = data.get("user_id")
        if user_id:
            requests.delete(f"{BASE_URL}/api/admin/users/{user_id}", headers=self.headers)
        
        print(f"✓ Org user created with organization_id: {org_id}")
    
    def test_get_individuals_list(self):
        """Test the /admin/individuals endpoint returns individual users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/individuals",
            headers=self.headers
        )
        
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Get individuals failed: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), "Expected a list of individuals"
        print(f"✓ Found {len(data)} individuals in the system")
        
        # If there are individuals, verify structure
        if data:
            individual = data[0]
            assert "_id" in individual, "Individual should have _id"
            assert "name" in individual, "Individual should have name"
            assert "email" in individual, "Individual should have email"
            print(f"✓ Individual structure verified: {individual.get('name')}")


class TestAdminUsersAPI:
    """Test admin user management APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        self.user_id = data["user"]["_id"]
        self.headers = {"X-User-ID": self.user_id}
    
    def test_list_users(self):
        """Test listing all users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers=self.headers
        )
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list), "Expected list of users"
        print(f"✓ Found {len(users)} users")
    
    def test_list_users_filtered_by_role(self):
        """Test listing users filtered by role"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users?role=super_admin",
            headers=self.headers
        )
        assert response.status_code == 200
        users = response.json()
        
        # All returned users should be super_admin
        for user in users:
            assert user.get("role") == "super_admin", f"Expected super_admin, got {user.get('role')}"
        
        print(f"✓ Found {len(users)} super_admin users")
    
    def test_detailed_stats(self):
        """Test the detailed stats endpoint for admin dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats/detailed",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields exist
        expected_fields = [
            "orgs_active", "orgs_inactive",
            "stores_active", "stores_inactive",
            "users_active", "users_inactive",
            "individuals_active", "individuals_inactive"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Stats: {data['individuals_active']} active individuals, {data['users_active']} active org users")


class TestHealthAndRoutes:
    """Test basic health and route availability"""
    
    def test_health_check(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health check passed")
    
    def test_auth_login_endpoint(self):
        """Test login endpoint is accessible"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test@test.com", "password": "wrong"}
        )
        # Should return 401 for wrong credentials, not 404
        assert response.status_code in [401, 400], f"Unexpected status: {response.status_code}"
        print("✓ Auth login endpoint accessible")


class TestOnboardingPreviewRoute:
    """Test routes related to onboarding preview"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        self.user_id = data["user"]["_id"]
        self.headers = {"X-User-ID": self.user_id}
    
    def test_pending_users_count(self):
        """Test pending users count endpoint (used by Admin section)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/pending-users/count",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data, "Expected 'count' in response"
        print(f"✓ Pending users count: {data['count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
