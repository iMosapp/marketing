"""
RBAC Permissions Tests - Testing role-based access control
Tests the permissions.py module and login endpoint with different roles
"""
import pytest
import requests
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from permissions import merge_permissions, get_role_defaults, ROLE_PERMISSIONS, DEFAULT_PERMISSIONS

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestMergePermissions:
    """Test the merge_permissions function with different roles"""

    def test_user_role_has_admin_disabled(self):
        """Regular user role should have admin._enabled=False"""
        perms = merge_permissions(None, "user")
        assert "admin" in perms, "admin section should exist"
        assert perms["admin"].get("_enabled") == False, "admin._enabled should be False for user role"
        print("PASS: user role has admin._enabled=False")

    def test_store_manager_admin_enabled_limited(self):
        """Store manager should have admin._enabled=True but limited items"""
        perms = merge_permissions(None, "store_manager")
        
        # Admin should be enabled
        assert perms["admin"].get("_enabled") == True, "admin._enabled should be True for store_manager"
        
        # Should have these admin items enabled
        assert perms["admin"].get("users") == True, "store_manager should have users access"
        assert perms["admin"].get("invite_team") == True, "store_manager should have invite_team access"
        assert perms["admin"].get("store_profile") == True, "store_manager should have store_profile access"
        
        # Should NOT have these admin items
        assert perms["admin"].get("admin_dashboard") == False, "store_manager should NOT have admin_dashboard"
        assert perms["admin"].get("lead_sources") == False, "store_manager should NOT have lead_sources"
        assert perms["admin"].get("integrations") == False, "store_manager should NOT have integrations"
        
        print("PASS: store_manager has admin._enabled=True with limited items (no admin_dashboard, lead_sources, integrations)")

    def test_org_admin_full_admin_access(self):
        """Org admin should have admin._enabled=True with full items"""
        perms = merge_permissions(None, "org_admin")
        
        # Admin should be enabled
        assert perms["admin"].get("_enabled") == True, "admin._enabled should be True for org_admin"
        
        # Should have all admin items enabled
        assert perms["admin"].get("admin_dashboard") == True, "org_admin should have admin_dashboard"
        assert perms["admin"].get("lead_sources") == True, "org_admin should have lead_sources"
        assert perms["admin"].get("integrations") == True, "org_admin should have integrations"
        assert perms["admin"].get("accounts") == True, "org_admin should have accounts"
        
        print("PASS: org_admin has admin._enabled=True with full items")

    def test_super_admin_everything_enabled(self):
        """Super admin should have everything enabled"""
        perms = merge_permissions(None, "super_admin")
        
        # All sections should be enabled
        for section_key, section_perms in perms.items():
            assert section_perms.get("_enabled") == True, f"{section_key}._enabled should be True for super_admin"
        
        # All admin items should be enabled
        assert perms["admin"].get("admin_dashboard") == True
        assert perms["admin"].get("lead_sources") == True
        assert perms["admin"].get("integrations") == True
        assert perms["admin"].get("accounts") == True
        
        print("PASS: super_admin has everything enabled")

    def test_legacy_admin_role_falls_back_to_user(self):
        """Legacy 'admin' role should fall back to user permissions"""
        perms = merge_permissions(None, "admin")  # Legacy role name
        
        # Should fallback to user permissions (admin._enabled=False)
        assert perms["admin"].get("_enabled") == False, "legacy 'admin' role should fall back to user permissions"
        
        print("PASS: legacy 'admin' role falls back to user permissions (admin._enabled=False)")

    def test_legacy_manager_role_falls_back_to_user(self):
        """Legacy 'manager' role should fall back to user permissions"""
        perms = merge_permissions(None, "manager")  # Legacy role name
        
        # Should fallback to user permissions (admin._enabled=False)
        assert perms["admin"].get("_enabled") == False, "legacy 'manager' role should fall back to user permissions"
        
        print("PASS: legacy 'manager' role falls back to user permissions (admin._enabled=False)")

    def test_default_permissions_has_key_features(self):
        """All default permissions should have date_triggers, manage_showcase, activity_reports, email_analytics enabled"""
        # Test for all roles
        roles_to_test = ["user", "store_manager", "org_admin", "super_admin"]
        
        for role in roles_to_test:
            perms = merge_permissions(None, role)
            
            # Check campaigns.date_triggers
            assert perms.get("campaigns", {}).get("date_triggers") == True, f"{role} should have date_triggers=True"
            
            # Check content.manage_showcase
            assert perms.get("content", {}).get("manage_showcase") == True, f"{role} should have manage_showcase=True"
            
            # Check insights.activity_reports
            assert perms.get("insights", {}).get("activity_reports") == True, f"{role} should have activity_reports=True"
            
            # Check insights.email_analytics
            assert perms.get("insights", {}).get("email_analytics") == True, f"{role} should have email_analytics=True"
        
        print("PASS: All roles have date_triggers=True, manage_showcase=True, activity_reports=True, email_analytics=True")


class TestLoginRolePermissions:
    """Test that login returns role-appropriate permissions"""

    def test_super_admin_login_returns_admin_section(self):
        """Super admin login should return feature_permissions with admin section enabled"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Check user exists
        assert "user" in data, "Response should have user object"
        user = data["user"]
        
        # Check role is super_admin
        assert user.get("role") == "super_admin", f"User role should be super_admin, got {user.get('role')}"
        
        # Check feature_permissions exist
        assert "feature_permissions" in user, "User should have feature_permissions"
        perms = user["feature_permissions"]
        
        # Check admin section is enabled
        assert "admin" in perms, "feature_permissions should have admin section"
        assert perms["admin"].get("_enabled") == True, "admin._enabled should be True for super_admin"
        
        # Check all admin items are enabled
        admin_items = ["users", "invite_team", "store_profile", "brand_kit", "admin_dashboard", 
                       "review_approvals", "showcase_approvals", "review_links", "contact_tags", 
                       "lead_sources", "integrations", "accounts"]
        for item in admin_items:
            assert perms["admin"].get(item) == True, f"super_admin should have admin.{item}=True"
        
        print(f"PASS: super_admin login returns role-appropriate permissions with admin section")


class TestCustomerRankingsAPI:
    """Test the customer rankings endpoint"""

    def test_customer_rankings_endpoint_exists(self):
        """GET /api/tracking/customer-rankings/{user_id} should return 200 or data"""
        # First login to get a valid user_id
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        user_id = login_response.json()["user"]["_id"]
        
        # Test customer rankings endpoint
        response = requests.get(f"{BASE_URL}/api/tracking/customer-rankings/{user_id}")
        
        assert response.status_code == 200, f"Customer rankings failed: {response.text}"
        data = response.json()
        
        # Should have rankings array
        assert "rankings" in data, "Response should have rankings array"
        assert isinstance(data["rankings"], list), "rankings should be a list"
        
        print(f"PASS: GET /api/tracking/customer-rankings/{user_id} returns rankings data")

    def test_customer_rankings_period_filter(self):
        """Test period filter parameters"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        user_id = login_response.json()["user"]["_id"]
        
        periods = ["today", "week", "month", "all"]
        for period in periods:
            response = requests.get(
                f"{BASE_URL}/api/tracking/customer-rankings/{user_id}",
                params={"period": period}
            )
            assert response.status_code == 200, f"Period={period} failed: {response.text}"
            print(f"  - Period={period}: OK")
        
        print("PASS: All period filters work (today, week, month, all)")

    def test_customer_rankings_scope_filter(self):
        """Test scope filter parameters"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        user_id = login_response.json()["user"]["_id"]
        
        scopes = ["user", "org", "global"]
        for scope in scopes:
            response = requests.get(
                f"{BASE_URL}/api/tracking/customer-rankings/{user_id}",
                params={"scope": scope}
            )
            assert response.status_code == 200, f"Scope={scope} failed: {response.text}"
            print(f"  - Scope={scope}: OK")
        
        print("PASS: All scope filters work (user, org, global)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
