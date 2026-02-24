"""
Test Pending Users Onboarding Workflow
Tests:
- User signup creates user with status='pending'
- GET /api/admin/pending-users - List pending users
- GET /api/admin/pending-users/count - Get count for badge
- PUT /api/admin/pending-users/{id}/approve - Approve pending user
- PUT /api/admin/pending-users/{id}/reject - Reject pending user  
- GET /api/admin/stats - Includes pending_users count
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://imos-ux-polish.preview.emergentagent.com')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@mvpline.com"
SUPER_ADMIN_PASSWORD = "MVPLine2024!"


class TestPendingUsersWorkflow:
    """Test the complete pending users onboarding workflow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.test_user_id = None
        self.test_org_id = None
        yield
        # Cleanup - attempt to delete test user
        if self.test_user_id:
            try:
                self.session.delete(f"{BASE_URL}/api/admin/users/{self.test_user_id}")
            except:
                pass
    
    def test_01_login_super_admin(self):
        """Login as super admin"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Super admin login successful - role: {data['user']['role']}")
    
    def test_02_get_organizations_list(self):
        """Get organizations list for signup form dropdown"""
        response = self.session.get(f"{BASE_URL}/api/admin/organizations")
        assert response.status_code == 200, f"Failed to get orgs: {response.text}"
        orgs = response.json()
        assert isinstance(orgs, list)
        if len(orgs) > 0:
            self.test_org_id = orgs[0]["_id"]
            print(f"✓ Organizations list retrieved - count: {len(orgs)}, first org: {orgs[0].get('name', 'N/A')}")
        else:
            print("✓ Organizations list retrieved - empty list (need to create org first)")
    
    def test_03_signup_creates_pending_user(self):
        """Test that signup creates user with status='pending'"""
        unique_email = f"test_pending_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        # First get an org to associate with
        orgs_response = self.session.get(f"{BASE_URL}/api/admin/organizations")
        orgs = orgs_response.json()
        org_id = orgs[0]["_id"] if orgs else None
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_Pending User",
            "password": "TestPassword123!",
            "role": "Sales Rep",  # Requested role
        }
        if org_id:
            signup_data["organization_id"] = org_id
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.test_user_id = user.get("_id")
        
        # Verify pending status
        assert user.get("status") == "pending", f"Expected status='pending', got {user.get('status')}"
        assert user.get("role") == "user", f"Expected role='user' (basic until approved), got {user.get('role')}"
        assert user.get("requested_role") == "Sales Rep", f"Expected requested_role='Sales Rep', got {user.get('requested_role')}"
        assert user.get("is_active") == True, f"Expected is_active=True, got {user.get('is_active')}"
        
        print(f"✓ Signup created pending user - status: {user.get('status')}, requested_role: {user.get('requested_role')}, id: {self.test_user_id}")
        return self.test_user_id
    
    def test_04_get_pending_users_list(self):
        """Test GET /api/admin/pending-users"""
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users")
        assert response.status_code == 200, f"Failed to get pending users: {response.text}"
        
        users = response.json()
        assert isinstance(users, list)
        
        # Check structure of response
        if len(users) > 0:
            user = users[0]
            expected_fields = ["_id", "name", "email", "requested_role", "status", "created_at"]
            for field in expected_fields:
                assert field in user, f"Missing field '{field}' in pending user response"
            
            # Verify all have pending status
            for u in users:
                assert u.get("status") == "pending", f"User {u.get('_id')} has status {u.get('status')}, expected 'pending'"
        
        print(f"✓ Pending users list retrieved - count: {len(users)}")
    
    def test_05_get_pending_users_count(self):
        """Test GET /api/admin/pending-users/count for notification badge"""
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users/count")
        assert response.status_code == 200, f"Failed to get count: {response.text}"
        
        data = response.json()
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["count"], int), f"Count should be int, got {type(data['count'])}"
        assert data["count"] >= 0, f"Count should be >= 0, got {data['count']}"
        
        print(f"✓ Pending users count: {data['count']}")
    
    def test_06_stats_includes_pending_users(self):
        """Test that /api/admin/stats includes pending_users count"""
        response = self.session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        
        stats = response.json()
        assert "pending_users" in stats, "Stats missing 'pending_users' field"
        assert isinstance(stats["pending_users"], int), f"pending_users should be int"
        
        print(f"✓ Stats includes pending_users: {stats['pending_users']}")
        print(f"  Total users: {stats.get('total_users')}, Total orgs: {stats.get('total_organizations')}")
    
    def test_07_approve_pending_user(self):
        """Test PUT /api/admin/pending-users/{id}/approve"""
        # First create a test pending user
        unique_email = f"test_approve_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        orgs_response = self.session.get(f"{BASE_URL}/api/admin/organizations")
        orgs = orgs_response.json()
        org_id = orgs[0]["_id"] if orgs else None
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_ToApprove User",
            "password": "TestPassword123!",
            "role": "Store Manager",
        }
        if org_id:
            signup_data["organization_id"] = org_id
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        user_id = signup_response.json().get("_id")
        
        # Approve the user with configuration
        approval_data = {
            "role": "store_manager",
        }
        if org_id:
            approval_data["organization_id"] = org_id
            
            # Get stores for this org
            stores_response = self.session.get(f"{BASE_URL}/api/admin/stores?organization_id={org_id}")
            stores = stores_response.json()
            if stores:
                approval_data["store_id"] = stores[0]["_id"]
        
        response = self.session.put(f"{BASE_URL}/api/admin/pending-users/{user_id}/approve", json=approval_data)
        assert response.status_code == 200, f"Approve failed: {response.text}"
        
        result = response.json()
        assert result.get("message") == "User approved"
        assert result.get("user_id") == user_id
        
        # Verify user is now active
        user_response = self.session.get(f"{BASE_URL}/api/admin/users/{user_id}")
        assert user_response.status_code == 200
        user = user_response.json()
        
        assert user.get("status") == "active", f"Expected status='active', got {user.get('status')}"
        assert user.get("role") == "store_manager", f"Expected role='store_manager', got {user.get('role')}"
        
        print(f"✓ User approved successfully - status: {user.get('status')}, role: {user.get('role')}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
    
    def test_08_reject_pending_user(self):
        """Test PUT /api/admin/pending-users/{id}/reject"""
        # Create a test pending user
        unique_email = f"test_reject_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_ToReject User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        user_id = signup_response.json().get("_id")
        
        # Reject the user
        reject_data = {"reason": "Test rejection"}
        response = self.session.put(f"{BASE_URL}/api/admin/pending-users/{user_id}/reject", json=reject_data)
        assert response.status_code == 200, f"Reject failed: {response.text}"
        
        result = response.json()
        assert result.get("message") == "User rejected"
        assert result.get("reason") == "Test rejection"
        
        # Verify user is deleted (reject should delete the user)
        user_response = self.session.get(f"{BASE_URL}/api/admin/users/{user_id}")
        assert user_response.status_code == 404, "User should be deleted after rejection"
        
        print(f"✓ User rejected and deleted successfully")
    
    def test_09_reject_nonexistent_user(self):
        """Test rejecting a user that doesn't exist"""
        fake_id = "123456789012345678901234"  # Valid ObjectId format but doesn't exist
        
        response = self.session.put(f"{BASE_URL}/api/admin/pending-users/{fake_id}/reject", json={})
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print(f"✓ Rejecting nonexistent user returns 404 as expected")
    
    def test_10_approve_already_active_user(self):
        """Test that approving already active user works (idempotent)"""
        # Create and immediately approve a user
        unique_email = f"test_double_{uuid.uuid4().hex[:8]}@test.com"
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        
        signup_data = {
            "email": unique_email,
            "phone": unique_phone,
            "name": "TEST_DoubleApprove User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
        }
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        user_id = signup_response.json().get("_id")
        
        # First approval
        response1 = self.session.put(f"{BASE_URL}/api/admin/pending-users/{user_id}/approve", json={"role": "user"})
        assert response1.status_code == 200
        
        # Second approval should still work
        response2 = self.session.put(f"{BASE_URL}/api/admin/pending-users/{user_id}/approve", json={"role": "store_manager"})
        assert response2.status_code == 200
        
        # Verify final state
        user_response = self.session.get(f"{BASE_URL}/api/admin/users/{user_id}")
        user = user_response.json()
        assert user.get("role") == "store_manager"
        
        print(f"✓ Multiple approvals work correctly (last role wins)")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")


class TestSignupValidation:
    """Test signup validation and error handling"""
    
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
    
    def test_signup_duplicate_email(self):
        """Test that duplicate email signup fails"""
        unique_suffix = uuid.uuid4().hex[:8]
        signup_data = {
            "email": f"test_dup_{unique_suffix}@test.com",
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_Dup User",
            "password": "TestPassword123!",
            "role": "Sales Rep",
        }
        
        # First signup
        response1 = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response1.status_code == 200
        self.created_user_ids.append(response1.json().get("_id"))
        
        # Duplicate signup
        signup_data["phone"] = f"+1555{uuid.uuid4().hex[:7]}"  # Different phone
        response2 = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response2.status_code == 400, f"Expected 400 for duplicate email, got {response2.status_code}"
        assert "already registered" in response2.json().get("detail", "").lower()
        
        print(f"✓ Duplicate email signup returns 400 as expected")
    
    def test_signup_with_organization(self):
        """Test signup with organization_id"""
        # Get an org
        orgs_response = self.session.get(f"{BASE_URL}/api/admin/organizations")
        orgs = orgs_response.json()
        
        if not orgs:
            pytest.skip("No organizations available for test")
        
        org_id = orgs[0]["_id"]
        unique_suffix = uuid.uuid4().hex[:8]
        
        signup_data = {
            "email": f"test_org_{unique_suffix}@test.com",
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_OrgUser",
            "password": "TestPassword123!",
            "role": "Sales Manager",
            "organization_id": org_id,
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        user = response.json()
        self.created_user_ids.append(user.get("_id"))
        
        assert user.get("organization_id") == org_id, f"Organization not saved correctly"
        assert user.get("status") == "pending"
        
        print(f"✓ Signup with organization works - org_id: {org_id}")


class TestPendingUserFiltering:
    """Test filtering and ordering of pending users"""
    
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
    
    def test_pending_users_sorted_by_created_at_desc(self):
        """Verify pending users are sorted by created_at descending (newest first)"""
        # Create two users in sequence
        for i in range(2):
            unique_suffix = uuid.uuid4().hex[:8]
            signup_data = {
                "email": f"test_sort_{i}_{unique_suffix}@test.com",
                "phone": f"+1555{uuid.uuid4().hex[:7]}",
                "name": f"TEST_SortUser {i}",
                "password": "TestPassword123!",
                "role": f"Role {i}",
            }
            response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
            if response.status_code == 200:
                self.created_user_ids.append(response.json().get("_id"))
        
        # Get pending users
        response = self.session.get(f"{BASE_URL}/api/admin/pending-users")
        assert response.status_code == 200
        
        users = response.json()
        if len(users) >= 2:
            # Check that they're sorted by created_at descending
            for i in range(len(users) - 1):
                current_date = datetime.fromisoformat(users[i]["created_at"].replace("Z", "+00:00"))
                next_date = datetime.fromisoformat(users[i+1]["created_at"].replace("Z", "+00:00"))
                assert current_date >= next_date, "Users not sorted by created_at descending"
            
            print(f"✓ Pending users sorted correctly (newest first)")
        else:
            print(f"✓ Sorting test skipped (only {len(users)} pending users)")
    
    def test_pending_users_include_org_name(self):
        """Verify pending users response includes organization_name"""
        # Get orgs
        orgs_response = self.session.get(f"{BASE_URL}/api/admin/organizations")
        orgs = orgs_response.json()
        
        if not orgs:
            pytest.skip("No organizations available")
        
        org = orgs[0]
        
        # Create user with org
        unique_suffix = uuid.uuid4().hex[:8]
        signup_data = {
            "email": f"test_orgname_{unique_suffix}@test.com",
            "phone": f"+1555{uuid.uuid4().hex[:7]}",
            "name": "TEST_OrgNameUser",
            "password": "TestPassword123!",
            "role": "Rep",
            "organization_id": org["_id"],
        }
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200
        self.created_user_ids.append(response.json().get("_id"))
        
        # Get pending users and check for org name
        pending_response = self.session.get(f"{BASE_URL}/api/admin/pending-users")
        users = pending_response.json()
        
        # Find our user
        test_user = next((u for u in users if u["email"] == signup_data["email"]), None)
        assert test_user is not None, "Created user not in pending list"
        
        assert test_user.get("organization_name") == org["name"], f"Expected org name '{org['name']}', got '{test_user.get('organization_name')}'"
        
        print(f"✓ Pending users include organization_name: {test_user.get('organization_name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
