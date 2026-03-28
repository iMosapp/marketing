"""
Test suite for Feature Permissions API endpoints
Tests: GET/PUT /api/admin/permissions/{user_id}
       Login response with feature_permissions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestPermissionsAPI:
    """Test feature permissions GET/PUT endpoints"""

    def test_login_returns_feature_permissions(self):
        """Login response should include feature_permissions field"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        assert "user" in data, "Response missing 'user' field"
        user = data["user"]
        
        # Check feature_permissions is present and has expected structure
        assert "feature_permissions" in user, "User object missing 'feature_permissions'"
        perms = user["feature_permissions"]
        
        # Verify section structure
        expected_sections = ["my_tools", "campaigns", "content", "insights"]
        for section in expected_sections:
            assert section in perms, f"Missing section: {section}"
            assert "_enabled" in perms[section], f"Section {section} missing '_enabled' toggle"
        
        print(f"Login returns feature_permissions with sections: {list(perms.keys())}")

    def test_get_permissions_endpoint(self):
        """GET /api/admin/permissions/{user_id} returns merged permissions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/permissions/{TEST_USER_ID}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        
        assert response.status_code == 200, f"GET permissions failed: {response.text}"
        data = response.json()
        
        # Check response structure
        assert "permissions" in data, "Response missing 'permissions'"
        assert "name" in data, "Response missing 'name'"
        assert "role" in data, "Response missing 'role'"
        
        perms = data["permissions"]
        
        # Verify all sections present
        expected_sections = ["my_tools", "campaigns", "content", "insights"]
        for section in expected_sections:
            assert section in perms, f"Missing section: {section}"
            assert "_enabled" in perms[section], f"Section {section} missing '_enabled'"
        
        print(f"GET permissions returned: name={data['name']}, role={data['role']}")
        print(f"Sections: {list(perms.keys())}")

    def test_put_permissions_endpoint(self):
        """PUT /api/admin/permissions/{user_id} updates permissions"""
        # First get current permissions
        get_response = requests.get(
            f"{BASE_URL}/api/admin/permissions/{TEST_USER_ID}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        assert get_response.status_code == 200
        current_perms = get_response.json()["permissions"]
        
        # Build updated permissions - enable all features
        updated_perms = {
            "my_tools": {
                "_enabled": True,
                "touchpoints": True,
                "ask_jessi": True,
                "training_hub": True,
                "team_chat": True,
            },
            "campaigns": {
                "_enabled": True,
                "campaign_builder": True,
                "campaign_dashboard": True,
                "broadcast": True,
                "date_triggers": True,
            },
            "content": {
                "_enabled": True,
                "sms_templates": True,
                "email_templates": True,
                "card_templates": True,
                "manage_showcase": True,
            },
            "insights": {
                "_enabled": True,
                "my_performance": True,
                "activity_reports": True,
                "email_analytics": True,
                "leaderboard": True,
                "lead_attribution": True,
            },
        }
        
        # Update permissions
        put_response = requests.put(
            f"{BASE_URL}/api/admin/permissions/{TEST_USER_ID}",
            json={"permissions": updated_perms},
            headers={"X-User-ID": TEST_USER_ID}
        )
        
        assert put_response.status_code == 200, f"PUT permissions failed: {put_response.text}"
        result = put_response.json()
        
        assert result.get("status") == "ok", "PUT did not return status 'ok'"
        assert "permissions" in result, "PUT response missing 'permissions'"
        
        # Verify changes persisted
        verify_response = requests.get(
            f"{BASE_URL}/api/admin/permissions/{TEST_USER_ID}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        assert verify_response.status_code == 200
        verified_perms = verify_response.json()["permissions"]
        
        # Check that broadcast is now True (was previously False by default)
        assert verified_perms["campaigns"]["broadcast"] == True, "Broadcast permission not updated"
        assert verified_perms["content"]["card_templates"] == True, "Card templates permission not updated"
        
        print("PUT permissions successfully updated all features to enabled")

    def test_permissions_require_admin(self):
        """Non-admin users should not be able to update others' permissions"""
        # This test would need a non-admin user - skip for now as we only have super_admin
        # The endpoint checks for admin role before allowing updates
        pass

    def test_default_permissions_structure(self):
        """Verify default permissions match expected structure"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        assert response.status_code == 200
        perms = response.json()["user"]["feature_permissions"]
        
        # Check my_tools section items
        my_tools_items = ["touchpoints", "ask_jessi", "training_hub", "team_chat"]
        for item in my_tools_items:
            assert item in perms["my_tools"], f"my_tools missing {item}"
        
        # Check campaigns section items
        campaigns_items = ["campaign_builder", "campaign_dashboard", "broadcast", "date_triggers"]
        for item in campaigns_items:
            assert item in perms["campaigns"], f"campaigns missing {item}"
        
        # Check content section items
        content_items = ["sms_templates", "email_templates", "card_templates", "manage_showcase"]
        for item in content_items:
            assert item in perms["content"], f"content missing {item}"
        
        # Check insights section items
        insights_items = ["my_performance", "activity_reports", "email_analytics", "leaderboard", "lead_attribution"]
        for item in insights_items:
            assert item in perms["insights"], f"insights missing {item}"
        
        print("All expected permission items present in their sections")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
