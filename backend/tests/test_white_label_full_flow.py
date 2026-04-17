"""
Test White-Label Partner Full Flow
Testing the complete end-to-end partner setup:
1. Create white-label partner
2. Create organization with partner_id
3. Create store under that org
4. Create org_admin user under that org (should auto-inherit partner_id)
5. Verify impersonate returns partner_id
6. Verify login returns partner_id
7. Verify sold_required_fields (including full_size_image) persist correctly
"""

import os
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"

# Use unique suffixes to avoid conflicts
TEST_SUFFIX = str(uuid.uuid4())[:8]


class TestWhiteLabelFullFlow:
    """End-to-end test for white-label partner setup flow"""
    
    partner_id = None
    org_id = None
    store_id = None
    user_id = None
    test_email = f"test_partner_admin_{TEST_SUFFIX}@testpartner.com"
    test_password = "TestPartner123!"
    
    @pytest.fixture(scope="class")
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_ID
        })
        return session

    def test_01_create_white_label_partner(self, api_client):
        """Step 1: Create a white-label partner"""
        partner_data = {
            "name": f"TEST_Partner_{TEST_SUFFIX}",
            "slug": f"test-partner-{TEST_SUFFIX}",
            "primary_color": "#FF5733",
            "secondary_color": "#33FF57",
            "sold_workflow_enabled": True,
            "sold_required_fields": ["full_size_image", "customer_name", "deal_amount"]
        }
        
        response = api_client.post(f"{BASE_URL}/api/admin/partners", json=partner_data)
        print(f"Create Partner Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Failed to create partner: {response.text}"
        data = response.json()
        
        assert "_id" in data, "Partner should have an _id"
        assert data["name"] == partner_data["name"]
        assert data["sold_workflow_enabled"] == True
        assert "full_size_image" in data.get("sold_required_fields", [])
        
        TestWhiteLabelFullFlow.partner_id = data["_id"]
        print(f"Created Partner ID: {TestWhiteLabelFullFlow.partner_id}")
    
    def test_02_verify_partner_persists_sold_fields(self, api_client):
        """Step 2: Verify sold_required_fields including full_size_image persist"""
        response = api_client.get(f"{BASE_URL}/api/admin/partners/{TestWhiteLabelFullFlow.partner_id}")
        print(f"Get Partner Response: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to get partner: {response.text}"
        data = response.json()
        
        assert data["sold_workflow_enabled"] == True, "sold_workflow_enabled should be True"
        sold_fields = data.get("sold_required_fields", [])
        assert "full_size_image" in sold_fields, f"full_size_image should be in sold_required_fields: {sold_fields}"
        assert "customer_name" in sold_fields
        print(f"Verified sold_required_fields persist: {sold_fields}")
    
    def test_03_update_partner_sold_fields(self, api_client):
        """Step 3: Update partner with additional sold fields and verify they persist"""
        update_data = {
            "sold_workflow_enabled": True,
            "sold_required_fields": ["full_size_image", "customer_name", "deal_amount", "vehicle_info"]
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/partners/{TestWhiteLabelFullFlow.partner_id}",
            json=update_data
        )
        print(f"Update Partner Response: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to update partner: {response.text}"
        data = response.json()
        
        # Verify update returned correct data
        assert "full_size_image" in data.get("sold_required_fields", [])
        
        # Re-fetch to confirm persistence
        get_response = api_client.get(f"{BASE_URL}/api/admin/partners/{TestWhiteLabelFullFlow.partner_id}")
        get_data = get_response.json()
        
        assert "full_size_image" in get_data.get("sold_required_fields", []), "full_size_image should persist after update"
        assert "vehicle_info" in get_data.get("sold_required_fields", []), "vehicle_info should persist after update"
        print(f"Verified updated sold_required_fields: {get_data.get('sold_required_fields')}")
    
    def test_04_create_organization_with_partner(self, api_client):
        """Step 4: Create organization linked to the partner"""
        org_data = {
            "name": f"TEST_PartnerOrg_{TEST_SUFFIX}",
            "admin_email": f"admin_{TEST_SUFFIX}@testorg.com",
            "city": "Test City",
            "state": "TS",
            "partner_id": TestWhiteLabelFullFlow.partner_id
        }
        
        response = api_client.post(f"{BASE_URL}/api/admin/organizations", json=org_data)
        print(f"Create Org Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Failed to create organization: {response.text}"
        data = response.json()
        
        assert "_id" in data, "Organization should have an _id"
        assert data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, "Org should have partner_id"
        
        TestWhiteLabelFullFlow.org_id = data["_id"]
        print(f"Created Organization ID: {TestWhiteLabelFullFlow.org_id}")
    
    def test_05_verify_org_partner_link(self, api_client):
        """Step 5: Verify the organization is linked to partner"""
        response = api_client.get(f"{BASE_URL}/api/admin/organizations/{TestWhiteLabelFullFlow.org_id}")
        print(f"Get Org Response: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to get organization: {response.text}"
        data = response.json()
        
        assert data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, "Org should have correct partner_id"
        print(f"Verified org {data.get('name')} is linked to partner {data.get('partner_id')}")
    
    def test_06_create_store_under_org(self, api_client):
        """Step 6: Create a store under the partner organization"""
        store_data = {
            "name": f"TEST_PartnerStore_{TEST_SUFFIX}",
            "organization_id": TestWhiteLabelFullFlow.org_id,
            "city": "Test City",
            "state": "TS"
        }
        
        response = api_client.post(f"{BASE_URL}/api/admin/stores", json=store_data)
        print(f"Create Store Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Failed to create store: {response.text}"
        data = response.json()
        
        assert "_id" in data, "Store should have an _id"
        
        TestWhiteLabelFullFlow.store_id = data["_id"]
        print(f"Created Store ID: {TestWhiteLabelFullFlow.store_id}")
    
    def test_07_create_org_admin_user(self, api_client):
        """Step 7: Create org_admin user - should AUTO-INHERIT partner_id from org"""
        user_data = {
            "email": TestWhiteLabelFullFlow.test_email,
            "password": TestWhiteLabelFullFlow.test_password,
            "name": f"TEST_PartnerAdmin_{TEST_SUFFIX}",
            "role": "org_admin",
            "organization_id": TestWhiteLabelFullFlow.org_id,
            "store_id": TestWhiteLabelFullFlow.store_id,
            "phone": f"+1555{TEST_SUFFIX[:7]}"
        }
        
        response = api_client.post(f"{BASE_URL}/api/admin/users", json=user_data)
        print(f"Create User Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        data = response.json()
        
        assert "_id" in data, "User should have an _id"
        
        # CRITICAL: User should auto-inherit partner_id from org
        assert data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, \
            f"User should auto-inherit partner_id from org! Got: {data.get('partner_id')}, Expected: {TestWhiteLabelFullFlow.partner_id}"
        
        TestWhiteLabelFullFlow.user_id = data["_id"]
        print(f"Created User ID: {TestWhiteLabelFullFlow.user_id}")
        print(f"User auto-inherited partner_id: {data.get('partner_id')}")
    
    def test_08_verify_user_has_partner_id(self, api_client):
        """Step 8: Re-fetch user and verify partner_id is stored"""
        response = api_client.get(f"{BASE_URL}/api/admin/users/{TestWhiteLabelFullFlow.user_id}")
        print(f"Get User Response: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to get user: {response.text}"
        data = response.json()
        
        assert data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, \
            f"User should have partner_id stored! Got: {data.get('partner_id')}"
        print(f"Verified user has partner_id: {data.get('partner_id')}")
    
    def test_09_impersonate_returns_partner_id(self, api_client):
        """Step 9: Impersonate the user - should return partner_id"""
        response = api_client.post(f"{BASE_URL}/api/admin/users/{TestWhiteLabelFullFlow.user_id}/impersonate")
        print(f"Impersonate Response: {response.status_code} - {response.text[:800]}")
        
        assert response.status_code == 200, f"Failed to impersonate: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Impersonation should succeed"
        assert "user" in data, "Response should include user object"
        
        user_data = data["user"]
        
        # CRITICAL: Impersonated user should have partner_id
        assert user_data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, \
            f"Impersonated user should have partner_id! Got: {user_data.get('partner_id')}, Expected: {TestWhiteLabelFullFlow.partner_id}"
        
        # Also verify isImpersonating flag
        assert user_data.get("isImpersonating") == True, "User should have isImpersonating flag"
        
        print(f"Impersonation returns partner_id: {user_data.get('partner_id')}")
        print(f"Impersonation isImpersonating: {user_data.get('isImpersonating')}")
    
    def test_10_login_returns_partner_id(self, api_client):
        """Step 10: Login as the partner org_admin - should return partner_id"""
        login_data = {
            "email": TestWhiteLabelFullFlow.test_email,
            "password": TestWhiteLabelFullFlow.test_password
        }
        
        # Use a new session without X-User-ID header
        login_session = requests.Session()
        login_session.headers.update({"Content-Type": "application/json"})
        
        response = login_session.post(f"{BASE_URL}/api/auth/login", json=login_data)
        print(f"Login Response: {response.status_code} - {response.text[:800]}")
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        assert "user" in data, "Login response should include user"
        user_data = data["user"]
        
        # CRITICAL: Logged-in user should have partner_id
        assert user_data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, \
            f"Logged-in user should have partner_id! Got: {user_data.get('partner_id')}, Expected: {TestWhiteLabelFullFlow.partner_id}"
        
        print(f"Login returns partner_id: {user_data.get('partner_id')}")
        print(f"User role: {user_data.get('role')}")
        print(f"Organization ID: {user_data.get('organization_id')}")


class TestCreateUserWithInviteInheritsPartner:
    """Test that /users/create (with invite) also inherits partner_id"""
    
    @pytest.fixture(scope="class")
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_ID
        })
        return session
    
    def test_create_user_with_invite_inherits_partner(self, api_client):
        """Create user via /users/create endpoint - should inherit partner_id"""
        # Skip if partner and org weren't created
        if not TestWhiteLabelFullFlow.org_id or not TestWhiteLabelFullFlow.partner_id:
            pytest.skip("Partner/Org not created - run full flow test first")
        
        invite_email = f"test_invite_{TEST_SUFFIX}@testpartner.com"
        user_data = {
            "email": invite_email,
            "name": f"TEST_InviteUser_{TEST_SUFFIX}",
            "role": "user",
            "organization_id": TestWhiteLabelFullFlow.org_id,
            "store_id": TestWhiteLabelFullFlow.store_id,
            "send_invite": False  # Don't actually send email
        }
        
        response = api_client.post(f"{BASE_URL}/api/admin/users/create", json=user_data)
        print(f"Create User with Invite Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        data = response.json()
        
        # Get the created user to verify partner_id
        user_id = data.get("user_id")
        assert user_id, "Response should include user_id"
        
        # Fetch user to verify partner_id was inherited
        get_response = api_client.get(f"{BASE_URL}/api/admin/users/{user_id}")
        user_data = get_response.json()
        
        assert user_data.get("partner_id") == TestWhiteLabelFullFlow.partner_id, \
            f"User created via /users/create should inherit partner_id! Got: {user_data.get('partner_id')}"
        
        print(f"User via /users/create inherited partner_id: {user_data.get('partner_id')}")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_ID
        })
        return session
    
    def test_cleanup_test_data(self, api_client):
        """Clean up all TEST_ prefixed data created during tests"""
        # This is optional - data will be cleaned up manually if needed
        print(f"\nTest Data Summary:")
        print(f"  Partner ID: {TestWhiteLabelFullFlow.partner_id}")
        print(f"  Org ID: {TestWhiteLabelFullFlow.org_id}")
        print(f"  Store ID: {TestWhiteLabelFullFlow.store_id}")
        print(f"  User ID: {TestWhiteLabelFullFlow.user_id}")
        print(f"  Test Email: {TestWhiteLabelFullFlow.test_email}")
        print(f"\nTo clean up manually, delete these entities or use API DELETE endpoints")
        
        # Optionally delete test user
        if TestWhiteLabelFullFlow.user_id:
            try:
                api_client.delete(f"{BASE_URL}/api/admin/users/{TestWhiteLabelFullFlow.user_id}")
                print(f"Deleted test user: {TestWhiteLabelFullFlow.user_id}")
            except Exception as e:
                print(f"Note: Could not delete test user: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
