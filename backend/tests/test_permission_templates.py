"""
Permission Templates API Tests
Tests CRUD operations for permission templates feature
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://engagement-hub-69.preview.emergentagent.com')

# Test credentials
SUPER_ADMIN_USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com / Admin123!

# Common headers for authenticated requests
AUTH_HEADERS = {
    "Content-Type": "application/json",
    "X-User-ID": SUPER_ADMIN_USER_ID
}


def ensure_super_admin_role():
    """Ensure the test user has super_admin role"""
    requests.put(
        f"{BASE_URL}/api/admin/users/{SUPER_ADMIN_USER_ID}",
        json={"role": "super_admin"},
        headers={"Content-Type": "application/json"}
    )


class TestPermissionTemplatesRead:
    """Test Permission Templates READ operations (no auth changes)"""
    
    def test_list_templates_returns_4_prebuilt(self):
        """GET /api/permission-templates/ returns 4 prebuilt templates"""
        response = requests.get(f"{BASE_URL}/api/permission-templates/")
        assert response.status_code == 200
        
        data = response.json()
        assert "templates" in data
        templates = data["templates"]
        
        # Should have at least 4 prebuilt templates
        prebuilt = [t for t in templates if t.get("is_prebuilt")]
        assert len(prebuilt) >= 4, f"Expected 4 prebuilt templates, got {len(prebuilt)}"
        
        # Verify all expected prebuilt templates exist
        prebuilt_ids = [t["id"] for t in prebuilt]
        assert "sales_rep" in prebuilt_ids, "Missing sales_rep template"
        assert "senior_rep" in prebuilt_ids, "Missing senior_rep template"
        assert "sales_manager" in prebuilt_ids, "Missing sales_manager template"
        assert "org_admin" in prebuilt_ids, "Missing org_admin template"
        print(f"✓ Found {len(prebuilt)} prebuilt templates: {prebuilt_ids}")
    
    def test_get_single_prebuilt_template(self):
        """GET /api/permission-templates/{template_id} returns prebuilt template details"""
        response = requests.get(f"{BASE_URL}/api/permission-templates/sales_rep")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "sales_rep"
        assert data["name"] == "Sales Rep"
        assert data["role"] == "user"
        assert data["is_prebuilt"] == True
        assert "permissions" in data
        
        # Verify permissions structure
        perms = data["permissions"]
        assert "my_tools" in perms
        assert "campaigns" in perms
        assert "content" in perms
        assert "insights" in perms
        print(f"✓ Got sales_rep template with {len(perms)} permission sections")


class TestPermissionTemplatesAuth:
    """Test Permission Templates authorization checks"""
    
    def test_create_template_requires_auth(self):
        """POST /api/permission-templates/ returns 403 without X-User-ID header"""
        payload = {
            "name": "Should Not Be Created",
            "description": "This should fail",
            "role": "user"
        }
        
        # Request without auth header
        response = requests.post(
            f"{BASE_URL}/api/permission-templates/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Create template correctly requires admin authorization")
    
    def test_apply_template_requires_auth(self):
        """POST /api/permission-templates/{id}/apply/{user_id} requires admin"""
        response = requests.post(
            f"{BASE_URL}/api/permission-templates/sales_rep/apply/{SUPER_ADMIN_USER_ID}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 403
        print("✓ Apply template correctly requires admin authorization")


class TestPermissionTemplatesProtection:
    """Test prebuilt template protection"""
    
    def setup_method(self):
        ensure_super_admin_role()
    
    def test_cannot_delete_prebuilt_template(self):
        """DELETE /api/permission-templates/{id} returns 400 for prebuilt templates"""
        response = requests.delete(
            f"{BASE_URL}/api/permission-templates/sales_rep",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "prebuilt" in data.get("detail", "").lower()
        print("✓ Cannot delete prebuilt templates (returns 400)")
    
    def test_cannot_edit_prebuilt_template(self):
        """PUT /api/permission-templates/{id} returns 400 for prebuilt templates"""
        payload = {"name": "Modified Sales Rep"}
        response = requests.put(
            f"{BASE_URL}/api/permission-templates/sales_rep",
            json=payload,
            headers=AUTH_HEADERS
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "prebuilt" in data.get("detail", "").lower()
        print("✓ Cannot edit prebuilt templates (returns 400)")


class TestPermissionTemplatesCRUD:
    """Test Permission Templates CRUD operations - run last to avoid role issues"""
    
    def setup_method(self):
        ensure_super_admin_role()
    
    def test_create_template_requires_name(self):
        """POST /api/permission-templates/ returns 400 without name"""
        payload = {
            "description": "No name provided",
            "role": "user"
        }
        
        response = requests.post(f"{BASE_URL}/api/permission-templates/", json=payload, headers=AUTH_HEADERS)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Create template correctly validates name is required")
    
    def test_create_custom_template(self):
        """POST /api/permission-templates/ creates a custom template"""
        unique_name = f"TEST_Custom Template {uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "description": "A test custom template created during testing",
            "role": "user",
            "icon": "rocket",
            "color": "#FF9500",
            "permissions": {
                "my_tools": {"_enabled": True, "touchpoints": True, "ask_jessi": True, "training_hub": False, "team_chat": False},
                "campaigns": {"_enabled": False},
                "content": {"_enabled": True, "sms_templates": True, "email_templates": True, "card_templates": False, "manage_showcase": False},
                "insights": {"_enabled": False}
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/permission-templates/", json=payload, headers=AUTH_HEADERS)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert data["name"] == unique_name
        assert data["role"] == "user"
        assert data["is_prebuilt"] == False
        assert "id" in data or "_id" in data
        
        created_template_id = data.get("id") or data.get("_id")
        print(f"✓ Created custom template '{unique_name}' with ID: {created_template_id}")
        
        # Cleanup - delete the test template
        if created_template_id:
            cleanup_response = requests.delete(
                f"{BASE_URL}/api/permission-templates/{created_template_id}",
                headers=AUTH_HEADERS
            )
            assert cleanup_response.status_code == 200
            print(f"✓ Cleaned up test template")
    
    def test_delete_custom_template(self):
        """DELETE /api/permission-templates/{id} deletes a custom template"""
        # First create a template to delete
        unique_name = f"TEST_To Delete {uuid.uuid4().hex[:6]}"
        create_payload = {
            "name": unique_name,
            "description": "This template will be deleted",
            "role": "user"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/permission-templates/",
            json=create_payload,
            headers=AUTH_HEADERS
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        
        template_id = create_response.json().get("id") or create_response.json().get("_id")
        print(f"✓ Created template to delete: {template_id}")
        
        # Now delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/permission-templates/{template_id}",
            headers=AUTH_HEADERS
        )
        assert delete_response.status_code == 200
        
        # Verify it's deleted
        get_response = requests.get(f"{BASE_URL}/api/permission-templates/{template_id}")
        assert get_response.status_code == 404, f"Template should be deleted, got {get_response.status_code}"
        print(f"✓ Custom template deleted successfully")
    
    def test_full_template_lifecycle(self):
        """Test create -> update -> delete cycle"""
        unique_name = f"TEST_Lifecycle {uuid.uuid4().hex[:6]}"
        
        # 1. Create
        create_payload = {
            "name": unique_name,
            "description": "Lifecycle test template",
            "role": "user",
            "icon": "star",
            "color": "#34C759"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/permission-templates/",
            json=create_payload,
            headers=AUTH_HEADERS
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        template_id = create_response.json().get("id") or create_response.json().get("_id")
        print(f"  1. Created: {template_id}")
        
        # 2. Update
        update_payload = {"description": "Updated description for lifecycle test"}
        update_response = requests.put(
            f"{BASE_URL}/api/permission-templates/{template_id}",
            json=update_payload,
            headers=AUTH_HEADERS
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        print(f"  2. Updated description")
        
        # 3. Verify update
        get_response = requests.get(f"{BASE_URL}/api/permission-templates/{template_id}")
        assert get_response.status_code == 200
        assert "Updated description" in get_response.json().get("description", "")
        print(f"  3. Verified update")
        
        # 4. Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/permission-templates/{template_id}",
            headers=AUTH_HEADERS
        )
        assert delete_response.status_code == 200
        print(f"  4. Deleted")
        
        print("✓ Full template lifecycle test passed")


class TestPermissionTemplatesApply:
    """Test applying templates to users - run LAST since it modifies user roles"""
    
    def setup_method(self):
        ensure_super_admin_role()
    
    def test_apply_template_to_user(self):
        """POST /api/permission-templates/{id}/apply/{user_id} applies template"""
        # Create a test user to apply template to, or use a known test user
        # For this test, we'll use a different user than the admin to avoid breaking other tests
        TEST_USER_ID = "6757a82f7aaf5c88b008aab9"  # A regular user
        
        response = requests.post(
            f"{BASE_URL}/api/permission-templates/sales_rep/apply/{TEST_USER_ID}",
            headers=AUTH_HEADERS
        )
        
        # Check if test user exists
        if response.status_code == 404 and "User not found" in response.text:
            print("⚠ Test user not found - skipping apply test")
            pytest.skip("Test user not found in database")
        
        assert response.status_code == 200, f"Apply template failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "Sales Rep" in data["message"]
        assert "new_role" in data
        assert data["new_role"] == "user"
        print(f"✓ Applied sales_rep template: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
