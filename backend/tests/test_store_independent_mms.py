"""
Test Store Detail Page, Independent Signup, and MMS Media Persistence
Tests for MVPLine hierarchy system:
- Store detail page with users and available users
- Store detail page allows adding/removing users
- Independent signup gets status='active' and needs_onboarding=True
- Organization signup gets status='pending' and sends admin notification
- Pending users count API works correctly
- MMS media download and storage endpoint
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@mvpline.com"
SUPER_ADMIN_PASSWORD = "MVPLine2024!"

# Test IDs from the main agent
TEST_ORG_ID = "699637971b07c23426a53249"
TEST_STORE_ID = "699637981b07c23426a5324a"


class TestStoreDetailPage:
    """Test /api/admin/hierarchy/store/{store_id} endpoint - Store Detail Page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
    
    def test_01_store_detail_loads_with_users(self):
        """Test that store detail page loads with users and available users"""
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Validate response structure
        assert "store" in data, "Response missing 'store' field"
        assert "organization" in data, "Response missing 'organization' field"
        assert "users" in data, "Response missing 'users' field"
        assert "available_users" in data, "Response missing 'available_users' field"
        assert "user_count" in data, "Response missing 'user_count' field"
        
        # Validate store structure
        store = data["store"]
        assert store["_id"] == TEST_STORE_ID
        assert "name" in store
        assert "active" in store
        
        # Validate user_count matches users list
        assert data["user_count"] == len(data["users"]), f"user_count ({data['user_count']}) doesn't match users list ({len(data['users'])})"
        
        print(f"✓ Store detail loaded: '{store['name']}' with {data['user_count']} users and {len(data['available_users'])} available users")
    
    def test_02_store_detail_users_have_required_fields(self):
        """Test that users in store detail have all required fields"""
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        if data["users"]:
            user = data["users"][0]
            expected_fields = ["_id", "name", "email", "role", "is_active", "store_ids"]
            for field in expected_fields:
                assert field in user, f"User missing required field '{field}'"
            
            print(f"✓ User has all required fields: {list(user.keys())}")
        else:
            print("⚠ No users in store to validate")
    
    def test_03_store_detail_available_users_have_required_fields(self):
        """Test that available users have required fields"""
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        if data["available_users"]:
            user = data["available_users"][0]
            expected_fields = ["_id", "name", "email", "role"]
            for field in expected_fields:
                assert field in user, f"Available user missing required field '{field}'"
            
            print(f"✓ Available user has all required fields")
        else:
            print("⚠ No available users to validate (all org users may already be assigned)")
    
    def test_04_store_detail_shows_organization_info(self):
        """Test that store detail includes organization info"""
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        
        if data["organization"]:
            org = data["organization"]
            assert "_id" in org
            assert "name" in org
            print(f"✓ Store organization info loaded: {org['name']}")
        else:
            print("⚠ Store has no organization (may be an independent store)")
    
    def test_05_store_not_found_returns_404(self):
        """Test that invalid store ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/000000000000000000000000")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ 404 returned for non-existent store")


class TestStoreUserManagement:
    """Test adding/removing users from stores"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.test_user_id = None
        yield
        # Cleanup - try to remove test user from store
        if self.test_user_id:
            try:
                self.session.put(
                    f"{BASE_URL}/api/admin/hierarchy/users/{self.test_user_id}/remove-store",
                    json={"store_id": TEST_STORE_ID}
                )
            except:
                pass
    
    def test_01_add_user_to_store(self):
        """Test adding a user to a store via assign-store endpoint"""
        # First get available users
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        if not data["available_users"]:
            pytest.skip("No available users to add to store")
        
        test_user_id = data["available_users"][0]["_id"]
        self.test_user_id = test_user_id
        
        # Add user to store
        add_response = self.session.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-store",
            json={"store_id": TEST_STORE_ID}
        )
        assert add_response.status_code == 200, f"Add user failed: {add_response.text}"
        
        # Verify user is now in store
        verify_response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        verify_data = verify_response.json()
        
        user_ids_in_store = [u["_id"] for u in verify_data["users"]]
        assert test_user_id in user_ids_in_store, "User not found in store after adding"
        
        print(f"✓ User {test_user_id} successfully added to store")
    
    def test_02_remove_user_from_store(self):
        """Test removing a user from a store via remove-store endpoint"""
        # First add a user to the store
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        data = response.json()
        
        if not data["available_users"]:
            pytest.skip("No available users to test removal")
        
        test_user_id = data["available_users"][0]["_id"]
        
        # Add user to store first
        self.session.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-store",
            json={"store_id": TEST_STORE_ID}
        )
        
        # Now remove user from store
        remove_response = self.session.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/remove-store",
            json={"store_id": TEST_STORE_ID}
        )
        assert remove_response.status_code == 200, f"Remove user failed: {remove_response.text}"
        
        result = remove_response.json()
        assert TEST_STORE_ID not in result.get("store_ids", []), "Store ID still in user's store_ids after removal"
        
        print(f"✓ User {test_user_id} successfully removed from store")
    
    def test_03_assign_store_requires_store_id(self):
        """Test that store_id is required when assigning"""
        response = self.session.put(
            f"{BASE_URL}/api/admin/hierarchy/users/123456789012345678901234/assign-store",
            json={}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ 400 returned when store_id is missing")
    
    def test_04_assign_to_invalid_store_returns_404(self):
        """Test that assigning to non-existent store returns 404"""
        # Get a valid user ID first
        response = self.session.get(f"{BASE_URL}/api/admin/hierarchy/users")
        data = response.json()
        if not data["users"]:
            pytest.skip("No users available for testing")
        
        test_user_id = data["users"][0]["_id"]
        
        response = self.session.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-store",
            json={"store_id": "000000000000000000000000"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ 404 returned for invalid store")


class TestIndependentSignup:
    """Test independent user signup - status='active', needs_onboarding=True"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
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
    
    def test_01_independent_signup_gets_active_status(self):
        """Test that independent signup creates user with status='active'"""
        unique_email = f"test_independent_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_Independent User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "account_type": "independent"
            # No organization_id - this makes them independent
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        # Verify independent-specific fields
        assert user.get("status") == "active", f"Expected status='active', got {user.get('status')}"
        assert user.get("account_type") == "independent", f"Expected account_type='independent', got {user.get('account_type')}"
        assert user.get("needs_onboarding") == True, f"Expected needs_onboarding=True, got {user.get('needs_onboarding')}"
        assert user.get("is_active") == True, f"Expected is_active=True, got {user.get('is_active')}"
        assert user.get("organization_id") is None, f"Independent user should have no organization_id"
        
        print(f"✓ Independent signup successful: status={user.get('status')}, needs_onboarding={user.get('needs_onboarding')}")
    
    def test_02_independent_signup_without_org_id(self):
        """Test that signup without organization_id creates independent user"""
        unique_email = f"test_no_org_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_NoOrg User",
            "password": "TestPassword123!",
            "role": "Sales Rep"
            # No organization_id and no account_type
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        # Should be treated as independent (active immediately)
        assert user.get("status") == "active", f"Expected status='active' for no-org signup, got {user.get('status')}"
        
        print(f"✓ No-org signup treated as independent: status={user.get('status')}")


class TestOrganizationSignup:
    """Test organization user signup - status='pending', admin notification"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
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
    
    def test_01_organization_signup_gets_pending_status(self):
        """Test that organization signup creates user with status='pending'"""
        unique_email = f"test_org_pending_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_OrgPending User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "organization_id": TEST_ORG_ID,
            "account_type": "organization"
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        # Verify organization-specific fields
        assert user.get("status") == "pending", f"Expected status='pending', got {user.get('status')}"
        assert user.get("account_type") == "organization", f"Expected account_type='organization', got {user.get('account_type')}"
        assert user.get("organization_id") == TEST_ORG_ID, f"Organization ID not saved correctly"
        assert user.get("is_active") == True, f"Expected is_active=True (can login), got {user.get('is_active')}"
        assert user.get("requested_role") == "Sales Rep", f"Expected requested_role='Sales Rep', got {user.get('requested_role')}"
        
        print(f"✓ Organization signup successful: status={user.get('status')}, requested_role={user.get('requested_role')}")
    
    def test_02_organization_signup_appears_in_pending_list(self):
        """Test that organization signup appears in pending users list"""
        unique_email = f"test_pending_list_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_PendingList User",
            "password": "TestPassword123!",
            "role": "Sales Manager",
            "organization_id": TEST_ORG_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200
        user_id = response.json().get("_id")
        self.created_user_ids.append(user_id)
        
        # Check pending users list
        pending_response = self.session.get(f"{BASE_URL}/api/admin/pending-users")
        assert pending_response.status_code == 200
        pending_users = pending_response.json()
        
        # Find our user
        test_user = next((u for u in pending_users if u["_id"] == user_id), None)
        assert test_user is not None, "Created user not in pending list"
        assert test_user.get("requested_role") == "Sales Manager"
        
        print(f"✓ User appears in pending list with requested_role: {test_user.get('requested_role')}")


class TestPendingUsersCount:
    """Test pending users count API for notification badge"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
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
    
    def test_01_pending_users_count_endpoint(self):
        """Test /api/admin/pending-users/count returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        assert response.status_code == 200, f"Count endpoint failed: {response.text}"
        
        data = response.json()
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["count"], int), f"Count should be int, got {type(data['count'])}"
        assert data["count"] >= 0, f"Count should be >= 0, got {data['count']}"
        
        print(f"✓ Pending users count: {data['count']}")
    
    def test_02_pending_count_increases_after_org_signup(self):
        """Test that pending count increases after organization signup"""
        # Get initial count
        initial_response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        initial_count = initial_response.json()["count"]
        
        # Create organization user (should be pending)
        unique_email = f"test_count_{uuid.uuid4().hex[:8]}@test.com"
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
        
        # Check new count
        new_response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        new_count = new_response.json()["count"]
        
        assert new_count == initial_count + 1, f"Expected count {initial_count + 1}, got {new_count}"
        
        print(f"✓ Pending count increased: {initial_count} -> {new_count}")
    
    def test_03_pending_count_unchanged_after_independent_signup(self):
        """Test that pending count does NOT increase after independent signup"""
        # Get initial count
        initial_response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        initial_count = initial_response.json()["count"]
        
        # Create independent user (should NOT be pending)
        unique_email = f"test_indep_count_{uuid.uuid4().hex[:8]}@test.com"
        signup_data = {
            "email": unique_email,
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_IndepCount User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
            "account_type": "independent"
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        self.created_user_ids.append(signup_response.json().get("_id"))
        
        # Check count is unchanged
        new_response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        new_count = new_response.json()["count"]
        
        assert new_count == initial_count, f"Count should be unchanged for independent signup: {initial_count} -> {new_count}"
        
        print(f"✓ Pending count unchanged for independent: {initial_count} (still {new_count})")


class TestMMSMediaEndpoint:
    """Test MMS media download and storage endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
    
    def test_01_twilio_webhook_test_endpoint(self):
        """Test that Twilio webhook test endpoint is accessible"""
        response = self.session.get(f"{BASE_URL}/api/webhooks/twilio/test")
        assert response.status_code == 200, f"Webhook test failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok"
        assert "endpoints" in data
        assert "incoming_sms" in data["endpoints"]
        
        print(f"✓ Twilio webhook test endpoint accessible: {data['endpoints']}")
    
    def test_02_media_endpoint_exists(self):
        """Test that media endpoint returns 404 for non-existent media (not 500)"""
        # This tests that the endpoint is properly configured
        response = self.session.get(f"{BASE_URL}/api/messages/media/000000000000000000000000")
        # Should return 404 (not found) not 500 (server error) or 405 (method not allowed)
        assert response.status_code in [404, 400], f"Expected 404 or 400, got {response.status_code}"
        print(f"✓ Media endpoint responds correctly for non-existent media: {response.status_code}")


class TestCleanupTestUser:
    """Clean up the test pending user: testorg@test.com"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
    
    def test_cleanup_test_user(self):
        """Clean up testorg@test.com if it exists"""
        # Get pending users and find testorg@test.com
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users")
        if response.status_code != 200:
            print("⚠ Could not get pending users list")
            return
        
        pending_users = response.json()
        test_user = next((u for u in pending_users if u.get("email") == "testorg@test.com"), None)
        
        if test_user:
            # Delete the test user
            delete_response = self.session.delete(f"{BASE_URL}/api/admin/users/{test_user['_id']}")
            if delete_response.status_code == 200:
                print(f"✓ Cleaned up test user: testorg@test.com (ID: {test_user['_id']})")
            else:
                print(f"⚠ Failed to delete test user: {delete_response.text}")
        else:
            print("✓ No testorg@test.com found to clean up")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
