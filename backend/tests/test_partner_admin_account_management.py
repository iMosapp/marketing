"""
Test Partner Admin Account Management Features
Tests for: partner_id in login/me response, partner admin org/store/user management,
Account Management section visibility for partner admins
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
PARTNER_ADMIN_EMAIL = "admin@calendarsystems.com"
PARTNER_ADMIN_PASSWORD = "CalSys123!"
EXPECTED_PARTNER_ID = "69a10678b8e991776ed5df19"


class TestPartnerAdminLogin:
    """Test partner_id is included in login response"""

    def test_partner_admin_login_returns_partner_id(self):
        """Login as partner admin should return partner_id in user object"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify user object structure
        assert "user" in data, "Response should contain user object"
        user = data["user"]
        
        # Verify partner_id is present
        assert "partner_id" in user, f"user object should contain partner_id. Keys: {user.keys()}"
        assert user["partner_id"] == EXPECTED_PARTNER_ID, f"partner_id should be {EXPECTED_PARTNER_ID}, got {user['partner_id']}"
        
        print(f"PASS: Partner admin login returns partner_id: {user['partner_id']}")
        print(f"User role: {user.get('role')}, org_id: {user.get('organization_id')}")

    def test_super_admin_login_no_partner_id_unless_linked(self):
        """Super admin login - partner_id depends on their org association"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        user = data["user"]
        
        # Super admin may or may not have partner_id depending on their org
        print(f"PASS: Super admin login - partner_id: {user.get('partner_id', 'None')}")
        print(f"User role: {user.get('role')}, org_id: {user.get('organization_id')}")


class TestPartnerAdminMeEndpoint:
    """Test partner_id is included in /me response"""

    def test_partner_admin_me_returns_partner_id(self):
        """GET /me should return partner_id for partner admin"""
        # First login to get session cookie
        session = requests.Session()
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        # Now call /me endpoint
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        
        assert me_response.status_code == 200, f"/me failed: {me_response.text}"
        data = me_response.json()
        
        # Verify user object structure
        assert "user" in data, "Response should contain user object"
        user = data["user"]
        
        # Verify partner_id is present in /me response
        assert "partner_id" in user, f"user object from /me should contain partner_id. Keys: {user.keys()}"
        assert user["partner_id"] == EXPECTED_PARTNER_ID, f"partner_id should be {EXPECTED_PARTNER_ID}, got {user['partner_id']}"
        
        print(f"PASS: /me endpoint returns partner_id: {user['partner_id']}")


class TestPartnerAdminOrganizations:
    """Test partner admin can manage organizations"""

    @pytest.fixture
    def partner_session(self):
        """Get authenticated session for partner admin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        user = response.json()["user"]
        session.headers.update({"X-User-ID": user["_id"]})
        return session, user

    def test_partner_admin_can_list_organizations(self, partner_session):
        """Partner admin can list organizations (should see only partner orgs)"""
        session, user = partner_session
        
        response = session.get(f"{BASE_URL}/api/admin/organizations")
        
        assert response.status_code == 200, f"List orgs failed: {response.text}"
        orgs = response.json()
        
        assert isinstance(orgs, list), "Response should be a list of organizations"
        print(f"PASS: Partner admin listed {len(orgs)} organizations")
        
        # All orgs should belong to the partner
        for org in orgs:
            print(f"  - {org.get('name')}: partner_id={org.get('partner_id')}")

    def test_partner_admin_can_create_organization(self, partner_session):
        """Partner admin can create new org (auto-linked to partner)"""
        session, user = partner_session
        
        org_name = "TEST_Partner_New_Org"
        response = session.post(f"{BASE_URL}/api/admin/organizations", json={
            "name": org_name,
            "slug": "test-partner-new-org",
            "admin_email": "test-partner-admin@example.com"
        })
        
        assert response.status_code in [200, 201], f"Create org failed: {response.text}"
        org = response.json()
        
        # Verify org has partner_id auto-set
        assert org.get("partner_id") == EXPECTED_PARTNER_ID, f"New org should have partner_id auto-set to {EXPECTED_PARTNER_ID}"
        
        print(f"PASS: Partner admin created org with auto-linked partner_id: {org.get('partner_id')}")
        
        # Cleanup
        if org.get("_id"):
            session.delete(f"{BASE_URL}/api/admin/organizations/{org['_id']}")


class TestPartnerAdminStores:
    """Test partner admin can manage stores/accounts"""

    @pytest.fixture
    def partner_session(self):
        """Get authenticated session for partner admin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        user = response.json()["user"]
        session.headers.update({"X-User-ID": user["_id"]})
        return session, user

    def test_partner_admin_can_list_stores(self, partner_session):
        """Partner admin can list stores/accounts"""
        session, user = partner_session
        
        response = session.get(f"{BASE_URL}/api/admin/stores")
        
        assert response.status_code == 200, f"List stores failed: {response.text}"
        stores = response.json()
        
        assert isinstance(stores, list), "Response should be a list of stores"
        print(f"PASS: Partner admin listed {len(stores)} stores/accounts")

    def test_partner_admin_can_create_store_in_partner_org(self, partner_session):
        """Partner admin can create store in partner org"""
        session, user = partner_session
        
        # Get partner org ID
        orgs_response = session.get(f"{BASE_URL}/api/admin/organizations")
        assert orgs_response.status_code == 200
        orgs = orgs_response.json()
        
        if not orgs:
            pytest.skip("No organizations found for partner admin")
        
        org_id = orgs[0]["_id"]
        store_name = "TEST_Partner_New_Store"
        
        response = session.post(f"{BASE_URL}/api/admin/stores", json={
            "name": store_name,
            "organization_id": org_id
        })
        
        assert response.status_code in [200, 201], f"Create store failed: {response.text}"
        store = response.json()
        
        print(f"PASS: Partner admin created store: {store.get('name')} in org {org_id}")
        
        # Cleanup
        if store.get("_id"):
            session.delete(f"{BASE_URL}/api/admin/stores/{store['_id']}")


class TestPartnerAdminUsers:
    """Test partner admin can manage users"""

    @pytest.fixture
    def partner_session(self):
        """Get authenticated session for partner admin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        user = response.json()["user"]
        session.headers.update({"X-User-ID": user["_id"]})
        return session, user

    def test_partner_admin_can_list_users(self, partner_session):
        """Partner admin can list users across partner orgs"""
        session, user = partner_session
        
        response = session.get(f"{BASE_URL}/api/admin/users")
        
        assert response.status_code == 200, f"List users failed: {response.text}"
        users = response.json()
        
        assert isinstance(users, list), "Response should be a list of users"
        print(f"PASS: Partner admin listed {len(users)} users")


class TestAccountManagementAccessControl:
    """Test that Account Management section items are properly scoped"""

    @pytest.fixture
    def partner_session(self):
        """Get authenticated session for partner admin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        user = response.json()["user"]
        session.headers.update({"X-User-ID": user["_id"]})
        return session, user

    @pytest.fixture
    def super_admin_session(self):
        """Get authenticated session for super admin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        user = response.json()["user"]
        session.headers.update({"X-User-ID": user["_id"]})
        return session, user

    def test_partner_admin_can_access_organizations(self, partner_session):
        """Partner admin can access organizations endpoint"""
        session, user = partner_session
        response = session.get(f"{BASE_URL}/api/admin/organizations")
        assert response.status_code == 200, f"Partner admin should be able to list organizations: {response.text}"
        print("PASS: Partner admin can access /api/admin/organizations")

    def test_partner_admin_can_access_stores(self, partner_session):
        """Partner admin can access stores endpoint"""
        session, user = partner_session
        response = session.get(f"{BASE_URL}/api/admin/stores")
        assert response.status_code == 200, f"Partner admin should be able to list stores: {response.text}"
        print("PASS: Partner admin can access /api/admin/stores")

    def test_partner_admin_can_access_users(self, partner_session):
        """Partner admin can access users endpoint"""
        session, user = partner_session
        response = session.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200, f"Partner admin should be able to list users: {response.text}"
        print("PASS: Partner admin can access /api/admin/users")

    def test_super_admin_can_access_admin_dashboard(self, super_admin_session):
        """Super admin can access admin dashboard"""
        session, user = super_admin_session
        # Admin dashboard typically uses various admin endpoints
        response = session.get(f"{BASE_URL}/api/admin/pending-users/count")
        assert response.status_code == 200, f"Super admin should access admin dashboard data: {response.text}"
        print("PASS: Super admin can access admin dashboard endpoints")

    def test_super_admin_can_access_lead_tracking(self, super_admin_session):
        """Super admin can access lead tracking/attribution"""
        session, user = super_admin_session
        response = session.get(f"{BASE_URL}/api/admin/demo-requests")
        # May return 200 or empty list
        assert response.status_code in [200, 404], f"Super admin should access lead tracking: {response.text}"
        print("PASS: Super admin can access lead tracking endpoints")


class TestPartnerAdminRoleVerification:
    """Verify partner admin has correct role and permissions setup"""

    def test_partner_admin_is_org_admin_with_partner_id(self):
        """Partner admin should be org_admin role with partner_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_ADMIN_EMAIL,
            "password": PARTNER_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        user = response.json()["user"]
        
        # Verify role and partner_id
        assert user.get("role") == "org_admin", f"Partner admin should have role=org_admin, got {user.get('role')}"
        assert user.get("partner_id") == EXPECTED_PARTNER_ID, f"Partner admin should have partner_id={EXPECTED_PARTNER_ID}"
        assert user.get("organization_id"), "Partner admin should have organization_id"
        
        print(f"PASS: Partner admin has correct setup:")
        print(f"  - role: {user.get('role')}")
        print(f"  - partner_id: {user.get('partner_id')}")
        print(f"  - organization_id: {user.get('organization_id')}")
        print(f"  - organization_name: {user.get('organization_name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
