"""
Test Signup and Onboarding Flow - Iteration 17
Tests:
1. Independent signup creates user with status='active', needs_onboarding=true, account_type='independent'
2. Organization signup creates user with status='pending', account_type='organization'
3. Pending users count endpoint returns correct count
4. Admin approve endpoint changes user status to 'active'
5. Store detail page API returns store with users
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://engagement-hub-69.preview.emergentagent.com')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@mvpline.com"
SUPER_ADMIN_PASSWORD = "MVPLine2024!"
TEST_ORG_ID = "699637971b07c23426a53249"


class TestIndependentSignupFlow:
    """Test that independent signup creates users with correct attributes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_user_ids = []
        yield
        # Cleanup
        for user_id in self.created_user_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
            except:
                pass
    
    def test_independent_signup_with_account_type(self):
        """Test signup with account_type='independent' explicitly set"""
        unique_email = f"testind_{uuid.uuid4().hex[:8]}@example.com"
        
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_Independent User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "account_type": "independent"  # Explicitly set
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        # Verify all required attributes
        assert user.get("status") == "active", f"Expected status='active', got {user.get('status')}"
        assert user.get("needs_onboarding") == True, f"Expected needs_onboarding=True, got {user.get('needs_onboarding')}"
        assert user.get("account_type") == "independent", f"Expected account_type='independent', got {user.get('account_type')}"
        assert user.get("organization_id") is None, f"Expected organization_id=None, got {user.get('organization_id')}"
        assert user.get("is_active") == True, f"Expected is_active=True, got {user.get('is_active')}"
        
        print(f"✓ Independent signup with explicit account_type: status={user.get('status')}, needs_onboarding={user.get('needs_onboarding')}, account_type={user.get('account_type')}")
    
    def test_independent_signup_without_org_id(self):
        """Test signup without organization_id is treated as independent"""
        unique_email = f"testind2_{uuid.uuid4().hex[:8]}@example.com"
        
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_NoOrg User",
            "password": "TestPassword123!",
            "role": "Sales Rep"
            # No organization_id or account_type
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        # Verify treated as independent
        assert user.get("status") == "active", f"Expected status='active', got {user.get('status')}"
        assert user.get("needs_onboarding") == True, f"Expected needs_onboarding=True, got {user.get('needs_onboarding')}"
        assert user.get("account_type") == "independent", f"Expected account_type='independent', got {user.get('account_type')}"
        
        print(f"✓ Signup without org_id treated as independent: status={user.get('status')}, account_type={user.get('account_type')}")


class TestOrganizationSignupFlow:
    """Test that organization signup creates users with pending status"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_user_ids = []
        yield
        # Cleanup
        for user_id in self.created_user_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
            except:
                pass
    
    def test_org_signup_gets_pending_status(self):
        """Test signup with organization_id gets status='pending'"""
        unique_email = f"testorg_{uuid.uuid4().hex[:8]}@example.com"
        
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_Org User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "organization_id": TEST_ORG_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        # Verify pending status
        assert user.get("status") == "pending", f"Expected status='pending', got {user.get('status')}"
        assert user.get("account_type") == "organization", f"Expected account_type='organization', got {user.get('account_type')}"
        assert user.get("organization_id") == TEST_ORG_ID, f"Expected organization_id={TEST_ORG_ID}, got {user.get('organization_id')}"
        assert user.get("requested_role") == "Sales Rep", f"Expected requested_role='Sales Rep', got {user.get('requested_role')}"
        assert user.get("is_active") == True, f"Expected is_active=True (can login), got {user.get('is_active')}"
        
        print(f"✓ Org signup gets pending status: status={user.get('status')}, account_type={user.get('account_type')}, requested_role={user.get('requested_role')}")


class TestPendingUsersCount:
    """Test the pending users count endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_user_ids = []
        yield
        # Cleanup
        for user_id in self.created_user_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
            except:
                pass
    
    def test_pending_count_returns_correct_value(self):
        """Test GET /api/admin/pending-users/count returns correct count"""
        # Get initial count
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        assert response.status_code == 200, f"Failed to get count: {response.text}"
        
        initial_count = response.json().get("count")
        assert isinstance(initial_count, int), f"Count should be int, got {type(initial_count)}"
        
        # Create an org user (pending)
        unique_email = f"testcount_{uuid.uuid4().hex[:8]}@example.com"
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_Count User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "organization_id": TEST_ORG_ID
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        self.created_user_ids.append(signup_response.json().get("_id"))
        
        # Get new count
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        assert response.status_code == 200
        
        new_count = response.json().get("count")
        assert new_count == initial_count + 1, f"Expected count to increase by 1: {initial_count} -> {new_count}"
        
        print(f"✓ Pending count increased correctly: {initial_count} -> {new_count}")
    
    def test_pending_count_not_affected_by_independent(self):
        """Test that independent signup doesn't increase pending count"""
        # Get initial count
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        initial_count = response.json().get("count")
        
        # Create an independent user
        unique_email = f"testindcount_{uuid.uuid4().hex[:8]}@example.com"
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_IndCount User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "account_type": "independent"
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        self.created_user_ids.append(signup_response.json().get("_id"))
        
        # Get new count - should be same
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        new_count = response.json().get("count")
        assert new_count == initial_count, f"Independent signup should not affect pending count: {initial_count} -> {new_count}"
        
        print(f"✓ Pending count unchanged after independent signup: {initial_count}")


class TestAdminApproveFlow:
    """Test the admin approve endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_user_ids = []
        yield
        # Cleanup
        for user_id in self.created_user_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
            except:
                pass
    
    def test_approve_changes_status_to_active(self):
        """Test PUT /api/admin/pending-users/{id}/approve changes status to 'active'"""
        # Create a pending user
        unique_email = f"testapprove_{uuid.uuid4().hex[:8]}@example.com"
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_Approve User",
            "password": "TestPassword123!",
            "role": "Store Manager",
            "organization_id": TEST_ORG_ID
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        
        user = signup_response.json()
        user_id = user.get("_id")
        self.created_user_ids.append(user_id)
        
        # Verify pending status
        assert user.get("status") == "pending", f"Initial status should be pending, got {user.get('status')}"
        
        # Approve the user
        approval_data = {
            "role": "store_manager",
            "organization_id": TEST_ORG_ID
        }
        
        approve_response = self.session.put(f"{BASE_URL}/api/admin/pending-users/{user_id}/approve", json=approval_data)
        assert approve_response.status_code == 200, f"Approve failed: {approve_response.text}"
        
        result = approve_response.json()
        assert result.get("message") == "User approved", f"Expected 'User approved', got {result.get('message')}"
        
        # Verify user is now active
        user_response = self.session.get(f"{BASE_URL}/api/admin/users/{user_id}")
        assert user_response.status_code == 200
        
        updated_user = user_response.json()
        assert updated_user.get("status") == "active", f"Expected status='active' after approval, got {updated_user.get('status')}"
        assert updated_user.get("role") == "store_manager", f"Expected role='store_manager', got {updated_user.get('role')}"
        
        print(f"✓ User approved successfully: status changed to 'active', role set to 'store_manager'")
    
    def test_approve_with_store_assignment(self):
        """Test approval with store assignment"""
        # First get a store from the org
        stores_response = self.session.get(f"{BASE_URL}/api/admin/stores?organization_id={TEST_ORG_ID}")
        stores = stores_response.json()
        
        if not stores:
            pytest.skip("No stores available for this org")
        
        store_id = stores[0]["_id"]
        
        # Create a pending user
        unique_email = f"testapprovestore_{uuid.uuid4().hex[:8]}@example.com"
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_ApproveStore User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "organization_id": TEST_ORG_ID
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        
        user_id = signup_response.json().get("_id")
        self.created_user_ids.append(user_id)
        
        # Approve with store assignment
        approval_data = {
            "role": "user",
            "organization_id": TEST_ORG_ID,
            "store_id": store_id
        }
        
        approve_response = self.session.put(f"{BASE_URL}/api/admin/pending-users/{user_id}/approve", json=approval_data)
        assert approve_response.status_code == 200
        
        # Verify user has store assigned
        user_response = self.session.get(f"{BASE_URL}/api/admin/users/{user_id}")
        updated_user = user_response.json()
        
        assert updated_user.get("status") == "active"
        assert updated_user.get("store_id") == store_id or store_id in updated_user.get("store_ids", [])
        
        print(f"✓ User approved with store assignment: store_id={store_id}")


class TestStoreDetailPage:
    """Test store detail page API returns store with users"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_store_detail_returns_users(self):
        """Test GET /api/admin/hierarchy/store/{id} returns store with users"""
        # Get stores for the test org
        stores_response = self.session.get(f"{BASE_URL}/api/admin/stores?organization_id={TEST_ORG_ID}")
        stores = stores_response.json()
        
        if not stores:
            pytest.skip("No stores available for testing")
        
        store_id = stores[0]["_id"]
        
        # Get store detail
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{store_id}")
        assert response.status_code == 200, f"Failed to get store detail: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "store" in data, "Response missing 'store' field"
        assert "users" in data, "Response missing 'users' field"
        assert "available_users" in data, "Response missing 'available_users' field"
        assert "user_count" in data, "Response missing 'user_count' field"
        
        store = data["store"]
        assert store.get("_id") == store_id
        assert "name" in store
        
        print(f"✓ Store detail returned: name={store.get('name')}, user_count={data['user_count']}, available_users={len(data['available_users'])}")
    
    def test_store_detail_users_have_required_fields(self):
        """Test that users in store detail have required fields"""
        stores_response = self.session.get(f"{BASE_URL}/api/admin/stores?organization_id={TEST_ORG_ID}")
        stores = stores_response.json()
        
        if not stores:
            pytest.skip("No stores available for testing")
        
        store_id = stores[0]["_id"]
        
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{store_id}")
        assert response.status_code == 200
        
        data = response.json()
        users = data.get("users", [])
        
        if users:
            for user in users:
                assert "_id" in user, "User missing '_id'"
                assert "name" in user, "User missing 'name'"
                assert "email" in user, "User missing 'email'"
                assert "role" in user, "User missing 'role'"
                assert "is_active" in user, "User missing 'is_active'"
            
            print(f"✓ Users have all required fields: {len(users)} users verified")
        else:
            print("✓ Store has no users (but structure is correct)")


class TestLoginWithPendingStatus:
    """Test that pending users can login but have restricted access info"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_user_ids = []
        yield
        # Cleanup
        for user_id in self.created_user_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
            except:
                pass
    
    def test_pending_user_can_login(self):
        """Test that pending users can login and get their status"""
        unique_email = f"testlogin_{uuid.uuid4().hex[:8]}@example.com"
        password = "TestPassword123!"
        
        # Create a pending user
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_Login User",
            "password": password,
            "role": "Sales Rep",
            "organization_id": TEST_ORG_ID
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        self.created_user_ids.append(signup_response.json().get("_id"))
        
        # Login with the pending user
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": password
        })
        
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        login_data = login_response.json()
        assert "token" in login_data, "Login should return token"
        assert "user" in login_data, "Login should return user"
        
        user = login_data["user"]
        assert user.get("status") == "pending", f"User status should be 'pending', got {user.get('status')}"
        
        print(f"✓ Pending user can login: status={user.get('status')}, email={user.get('email')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
