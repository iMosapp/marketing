"""
Test Campaign Permissions Feature:
- GET /api/admin/stores/{store_id}/campaign-settings - returns campaign permission settings
- PUT /api/admin/stores/{store_id}/campaign-settings - updates campaign permission settings
- GET /api/campaigns/{user_id}/permissions - returns permission status based on user role and store settings
- POST /api/campaigns/{user_id} - respects permission settings (403 if no permission)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://imos-auth-ui.preview.emergentagent.com')

# Test credentials
SALES_REP_EMAIL = "sales@mvpline.com"
SALES_REP_PASSWORD = "Sales123!"
SUPER_ADMIN_EMAIL = "forest@mvpline.com"
SUPER_ADMIN_PASSWORD = "MVPLine2024!"
TEST_STORE_ID = "699783e741097acc0e570b8c"


class TestCampaignPermissionsAPI:
    """Tests for campaign permissions endpoints"""
    
    @pytest.fixture(scope="class")
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    @pytest.fixture(scope="class")
    def sales_user(self, api_client):
        """Login sales rep and get user data"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": SALES_REP_EMAIL,
            "password": SALES_REP_PASSWORD
        })
        assert response.status_code == 200, f"Sales login failed: {response.text}"
        data = response.json()
        return data.get("user", {})
    
    @pytest.fixture(scope="class")
    def admin_user(self, api_client):
        """Login super admin and get user data"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        return data.get("user", {})
    
    # =============================================================
    # TEST: GET /api/admin/stores/{store_id}/campaign-settings
    # =============================================================
    
    def test_get_campaign_settings_success(self, api_client):
        """GET campaign settings returns managers_can_edit and sales_can_edit"""
        response = api_client.get(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings")
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "managers_can_edit" in data, "Response should have 'managers_can_edit' field"
        assert "sales_can_edit" in data, "Response should have 'sales_can_edit' field"
        assert isinstance(data["managers_can_edit"], bool), "managers_can_edit should be boolean"
        assert isinstance(data["sales_can_edit"], bool), "sales_can_edit should be boolean"
        print(f"Current settings: managers_can_edit={data['managers_can_edit']}, sales_can_edit={data['sales_can_edit']}")
    
    def test_get_campaign_settings_invalid_store(self, api_client):
        """GET campaign settings returns 404 for non-existent store"""
        response = api_client.get(f"{BASE_URL}/api/admin/stores/000000000000000000000000/campaign-settings")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    
    # =============================================================
    # TEST: PUT /api/admin/stores/{store_id}/campaign-settings
    # =============================================================
    
    def test_update_campaign_settings_enable_sales(self, api_client):
        """PUT campaign settings enables sales_can_edit"""
        payload = {
            "managers_can_edit": True,
            "sales_can_edit": True
        }
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json=payload
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "message" in data, "Response should have success message"
        
        # Verify persistence with GET
        verify_response = api_client.get(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings")
        verify_data = verify_response.json()
        assert verify_data["sales_can_edit"] == True, "sales_can_edit should be True after update"
        assert verify_data["managers_can_edit"] == True, "managers_can_edit should be True"
        print(f"Settings updated: {verify_data}")
    
    def test_update_campaign_settings_disable_sales(self, api_client):
        """PUT campaign settings disables sales_can_edit"""
        payload = {
            "managers_can_edit": True,
            "sales_can_edit": False
        }
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json=payload
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = api_client.get(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings")
        verify_data = verify_response.json()
        assert verify_data["sales_can_edit"] == False, "sales_can_edit should be False after update"
        print(f"Settings updated: {verify_data}")
    
    def test_update_campaign_settings_invalid_store(self, api_client):
        """PUT campaign settings returns 404 for non-existent store"""
        payload = {"managers_can_edit": True, "sales_can_edit": True}
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/000000000000000000000000/campaign-settings",
            json=payload
        )
        
        assert response.status_code == 404
    
    # =============================================================
    # TEST: GET /api/campaigns/{user_id}/permissions
    # =============================================================
    
    def test_admin_always_has_permission(self, api_client, admin_user):
        """Super admin always has campaign permission regardless of settings"""
        user_id = admin_user.get("_id")
        
        response = api_client.get(f"{BASE_URL}/api/campaigns/{user_id}/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] == True, "Super admin should always have access"
        assert "Admin" in data.get("reason", ""), "Reason should mention admin access"
        print(f"Admin permission: {data}")
    
    def test_sales_permission_when_enabled(self, api_client, sales_user):
        """Sales rep has permission when sales_can_edit is True"""
        user_id = sales_user.get("_id")
        
        # First enable sales permissions
        api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json={"managers_can_edit": True, "sales_can_edit": True}
        )
        
        # Check permission
        response = api_client.get(f"{BASE_URL}/api/campaigns/{user_id}/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] == True, "Sales should have access when enabled"
        print(f"Sales permission (enabled): {data}")
    
    def test_sales_permission_when_disabled(self, api_client, sales_user):
        """Sales rep denied when sales_can_edit is False"""
        user_id = sales_user.get("_id")
        
        # Disable sales permissions
        api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json={"managers_can_edit": True, "sales_can_edit": False}
        )
        
        # Check permission
        response = api_client.get(f"{BASE_URL}/api/campaigns/{user_id}/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] == False, "Sales should NOT have access when disabled"
        assert "not enabled" in data.get("reason", "").lower() or "disabled" in data.get("reason", "").lower()
        print(f"Sales permission (disabled): {data}")
    
    def test_invalid_user_permission(self, api_client):
        """Non-existent user returns allowed=False"""
        response = api_client.get(f"{BASE_URL}/api/campaigns/000000000000000000000000/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] == False, "Non-existent user should be denied"
        assert "not found" in data.get("reason", "").lower()
        print(f"Invalid user permission: {data}")
    
    # =============================================================
    # TEST: POST /api/campaigns/{user_id} - Permission enforcement
    # =============================================================
    
    def test_admin_can_create_campaign(self, api_client, admin_user):
        """Super admin can create campaign regardless of settings"""
        user_id = admin_user.get("_id")
        
        payload = {
            "name": "TEST_Admin_Campaign",
            "type": "general",
            "active": False,
            "sequences": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/campaigns/{user_id}", json=payload)
        
        assert response.status_code == 200, f"Admin should be able to create campaign: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST_Admin_Campaign"
        print(f"Admin created campaign: {data.get('_id', data.get('id'))}")
        
        # Cleanup - delete the test campaign
        campaign_id = data.get("_id") or data.get("id")
        if campaign_id:
            api_client.delete(f"{BASE_URL}/api/campaigns/{user_id}/{campaign_id}")
    
    def test_sales_create_campaign_when_enabled(self, api_client, sales_user):
        """Sales rep can create campaign when enabled"""
        user_id = sales_user.get("_id")
        
        # Enable sales permissions
        api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json={"managers_can_edit": True, "sales_can_edit": True}
        )
        
        payload = {
            "name": "TEST_Sales_Campaign_Enabled",
            "type": "general",
            "active": False,
            "sequences": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/campaigns/{user_id}", json=payload)
        
        assert response.status_code == 200, f"Sales should create campaign when enabled: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST_Sales_Campaign_Enabled"
        print(f"Sales created campaign: {data.get('_id', data.get('id'))}")
        
        # Cleanup
        campaign_id = data.get("_id") or data.get("id")
        if campaign_id:
            api_client.delete(f"{BASE_URL}/api/campaigns/{user_id}/{campaign_id}")
    
    def test_sales_create_campaign_when_disabled(self, api_client, sales_user):
        """Sales rep gets 403 when creating campaign with permissions disabled"""
        user_id = sales_user.get("_id")
        
        # Disable sales permissions
        api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json={"managers_can_edit": True, "sales_can_edit": False}
        )
        
        payload = {
            "name": "TEST_Sales_Campaign_Disabled",
            "type": "general",
            "active": False,
            "sequences": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/campaigns/{user_id}", json=payload)
        
        # Should get 403 Forbidden
        assert response.status_code == 403, f"Expected 403 when disabled, got {response.status_code}: {response.text}"
        print(f"Sales denied: {response.json()}")
    
    # =============================================================
    # Cleanup: Re-enable sales permissions after tests
    # =============================================================
    
    def test_cleanup_reenable_sales(self, api_client):
        """Cleanup: Re-enable sales permissions for other tests"""
        payload = {
            "managers_can_edit": True,
            "sales_can_edit": True
        }
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}/campaign-settings",
            json=payload
        )
        assert response.status_code == 200
        print("Cleanup: Sales permissions re-enabled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
