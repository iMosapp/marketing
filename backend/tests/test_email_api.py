"""
Tests for Email API endpoints - Email mode feature
Tests: preferences, templates, campaigns
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://reports-analytics-1.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "forestward@gmail.com"
TEST_PASSWORD = "Admin123!"


class TestEmailPreferences:
    """Test email preferences endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.user = response.json()["user"]
        self.user_id = self.user["_id"]
    
    def test_get_preferences_valid_user(self):
        """Test getting preferences for valid user"""
        response = requests.get(f"{BASE_URL}/api/email/preferences/{self.user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "default_mode" in data
        assert "toggle_style" in data
        assert data["default_mode"] in ["sms", "email"]
        assert data["toggle_style"] in ["pill", "fab", "tabs", "segmented"]
        print(f"PASS: Got preferences: {data}")
    
    def test_get_preferences_invalid_user_returns_defaults(self):
        """Test that invalid user_id returns default preferences"""
        response = requests.get(f"{BASE_URL}/api/email/preferences/invalid123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["default_mode"] == "sms"
        assert data["toggle_style"] == "pill"
        print("PASS: Invalid user returns default preferences")
    
    def test_update_preferences(self):
        """Test updating preferences"""
        response = requests.put(
            f"{BASE_URL}/api/email/preferences/{self.user_id}",
            json={"default_mode": "email", "toggle_style": "segmented"}
        )
        assert response.status_code == 200
        
        # Verify update
        get_response = requests.get(f"{BASE_URL}/api/email/preferences/{self.user_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["default_mode"] == "email"
        assert data["toggle_style"] == "segmented"
        print("PASS: Preferences updated successfully")
        
        # Reset to defaults
        requests.put(
            f"{BASE_URL}/api/email/preferences/{self.user_id}",
            json={"default_mode": "sms", "toggle_style": "pill"}
        )


class TestEmailTemplates:
    """Test email templates CRUD"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.user_id = response.json()["user"]["_id"]
    
    def test_get_templates(self):
        """Test getting email templates - should include default templates"""
        response = requests.get(f"{BASE_URL}/api/email/templates/{self.user_id}")
        assert response.status_code == 200
        
        templates = response.json()
        assert isinstance(templates, list)
        assert len(templates) >= 5, "Should have at least 5 default templates"
        
        # Check template structure
        for template in templates[:3]:
            assert "_id" in template
            assert "name" in template
            assert "subject" in template
            assert "html_content" in template
            assert "category" in template
        
        # Check categories
        categories = [t.get("category") for t in templates]
        assert "greeting" in categories
        assert "digital_card" in categories
        print(f"PASS: Got {len(templates)} templates")
    
    def test_create_template(self):
        """Test creating a new email template"""
        unique_name = f"TEST_Template_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/email/templates/{self.user_id}",
            json={
                "name": unique_name,
                "subject": "Test Subject",
                "html_content": "<p>Test content</p>",
                "category": "general"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == unique_name
        assert data["category"] == "general"
        assert "_id" in data
        print(f"PASS: Created template {unique_name}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/email/templates/{self.user_id}/{data['_id']}")
    
    def test_update_template(self):
        """Test updating an email template"""
        # Create template first
        create_response = requests.post(
            f"{BASE_URL}/api/email/templates/{self.user_id}",
            json={
                "name": f"TEST_Update_{int(time.time())}",
                "subject": "Original Subject",
                "html_content": "<p>Original</p>",
                "category": "general"
            }
        )
        assert create_response.status_code == 200
        template_id = create_response.json()["_id"]
        
        # Update
        update_response = requests.put(
            f"{BASE_URL}/api/email/templates/{self.user_id}/{template_id}",
            json={"subject": "Updated Subject"}
        )
        assert update_response.status_code == 200
        print("PASS: Template updated successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/email/templates/{self.user_id}/{template_id}")
    
    def test_cannot_delete_default_template(self):
        """Test that default templates cannot be deleted"""
        # Get templates to find a default one
        response = requests.get(f"{BASE_URL}/api/email/templates/{self.user_id}")
        templates = response.json()
        
        default_template = next((t for t in templates if t.get("is_default")), None)
        if default_template:
            delete_response = requests.delete(
                f"{BASE_URL}/api/email/templates/{self.user_id}/{default_template['_id']}"
            )
            assert delete_response.status_code == 400
            print("PASS: Cannot delete default templates")
        else:
            pytest.skip("No default template found")


class TestEmailCampaigns:
    """Test email campaigns CRUD"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.user_id = response.json()["user"]["_id"]
    
    def test_get_campaigns(self):
        """Test getting email campaigns"""
        response = requests.get(f"{BASE_URL}/api/email/campaigns/{self.user_id}")
        assert response.status_code == 200
        
        campaigns = response.json()
        assert isinstance(campaigns, list)
        print(f"PASS: Got {len(campaigns)} campaigns")
    
    def test_create_campaign(self):
        """Test creating an email campaign"""
        unique_name = f"TEST_Campaign_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/email/campaigns/{self.user_id}",
            json={
                "name": unique_name,
                "description": "Test campaign",
                "subject": "Test Campaign Subject",
                "html_content": "<p>Test campaign content</p>",
                "trigger_type": "manual"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == unique_name
        assert data["active"] == True
        assert data["sent_count"] == 0
        assert "_id" in data
        print(f"PASS: Created campaign {unique_name}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/email/campaigns/{self.user_id}/{data['_id']}")
    
    def test_update_campaign_status(self):
        """Test toggling campaign active status"""
        # Create campaign
        create_response = requests.post(
            f"{BASE_URL}/api/email/campaigns/{self.user_id}",
            json={
                "name": f"TEST_Toggle_{int(time.time())}",
                "subject": "Toggle Test",
                "html_content": "<p>Test</p>",
                "trigger_type": "manual"
            }
        )
        assert create_response.status_code == 200
        campaign = create_response.json()
        campaign_id = campaign["_id"]
        
        # Toggle status
        update_response = requests.put(
            f"{BASE_URL}/api/email/campaigns/{self.user_id}/{campaign_id}",
            json={"active": False}
        )
        assert update_response.status_code == 200
        print("PASS: Campaign status toggled")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/email/campaigns/{self.user_id}/{campaign_id}")
    
    def test_delete_campaign(self):
        """Test deleting an email campaign"""
        # Create campaign
        create_response = requests.post(
            f"{BASE_URL}/api/email/campaigns/{self.user_id}",
            json={
                "name": f"TEST_Delete_{int(time.time())}",
                "subject": "Delete Test",
                "html_content": "<p>Test</p>",
                "trigger_type": "manual"
            }
        )
        assert create_response.status_code == 200
        campaign_id = create_response.json()["_id"]
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/email/campaigns/{self.user_id}/{campaign_id}"
        )
        assert delete_response.status_code == 200
        print("PASS: Campaign deleted successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
