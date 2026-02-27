"""
Test suite for Templates API - CRUD operations for message templates
Tests: GET templates, POST create, PUT update, DELETE templates
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://backend-startup-3.preview.emergentagent.com')
BASE_URL = BASE_URL.rstrip('/')

# Test user ID (superadmin)
TEST_USER_ID = "69963e636d8473ba25695a34"

class TestTemplatesAPI:
    """Test all Template CRUD operations"""
    
    created_template_id = None
    
    def test_01_get_templates_for_user(self):
        """GET /api/templates/{user_id} should return list of templates"""
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        
        # Should have at least the 5 default templates
        assert len(templates) >= 5, f"Expected at least 5 default templates, got {len(templates)}"
        
        # Verify template structure
        for template in templates:
            assert "_id" in template, "Template should have _id"
            assert "name" in template, "Template should have name"
            assert "content" in template, "Template should have content"
            assert "category" in template, "Template should have category"
            assert "is_default" in template, "Template should have is_default flag"
            assert "user_id" in template, "Template should have user_id"
        
        print(f"✓ GET templates returned {len(templates)} templates")

    def test_02_get_templates_contains_defaults(self):
        """Verify default templates are created for new users"""
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        template_names = [t["name"] for t in templates]
        
        # Check for expected default templates
        expected_defaults = ["Greeting", "Follow Up", "Appointment", "Thank You", "Review Request"]
        for default_name in expected_defaults:
            assert default_name in template_names, f"Missing default template: {default_name}"
        
        print(f"✓ All 5 default templates present: {expected_defaults}")

    def test_03_create_template(self):
        """POST /api/templates/{user_id} should create new template"""
        new_template = {
            "name": "TEST_Custom Template",
            "content": "Hello {name}, this is a test template message.",
            "category": "general"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}",
            json=new_template
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        created = response.json()
        assert created["name"] == new_template["name"]
        assert created["content"] == new_template["content"]
        assert created["category"] == new_template["category"]
        assert created["is_default"] == False, "Custom template should not be default"
        assert "_id" in created, "Created template should have _id"
        
        # Store for later tests
        TestTemplatesAPI.created_template_id = created["_id"]
        
        print(f"✓ Created template with ID: {created['_id']}")

    def test_04_verify_created_template_persisted(self):
        """GET to verify the created template exists in database"""
        assert TestTemplatesAPI.created_template_id, "No template ID from create test"
        
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        template_ids = [t["_id"] for t in templates]
        
        assert TestTemplatesAPI.created_template_id in template_ids, "Created template not found in list"
        
        # Find and verify the template
        created_template = next(t for t in templates if t["_id"] == TestTemplatesAPI.created_template_id)
        assert created_template["name"] == "TEST_Custom Template"
        
        print(f"✓ Created template persisted and verified")

    def test_05_get_single_template(self):
        """GET /api/templates/{user_id}/{template_id} should return specific template"""
        assert TestTemplatesAPI.created_template_id, "No template ID from create test"
        
        response = requests.get(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{TestTemplatesAPI.created_template_id}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        template = response.json()
        assert template["_id"] == TestTemplatesAPI.created_template_id
        assert template["name"] == "TEST_Custom Template"
        
        print(f"✓ GET single template works")

    def test_06_update_template(self):
        """PUT /api/templates/{user_id}/{template_id} should update template"""
        assert TestTemplatesAPI.created_template_id, "No template ID from create test"
        
        update_data = {
            "name": "TEST_Updated Template",
            "content": "Updated content for {name}!",
            "category": "follow_up"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{TestTemplatesAPI.created_template_id}",
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        updated = response.json()
        assert updated["name"] == update_data["name"]
        assert updated["content"] == update_data["content"]
        assert updated["category"] == update_data["category"]
        
        print(f"✓ Template updated successfully")

    def test_07_verify_update_persisted(self):
        """GET to verify update was saved to database"""
        assert TestTemplatesAPI.created_template_id, "No template ID from create test"
        
        response = requests.get(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{TestTemplatesAPI.created_template_id}"
        )
        assert response.status_code == 200
        
        template = response.json()
        assert template["name"] == "TEST_Updated Template"
        assert template["content"] == "Updated content for {name}!"
        assert template["category"] == "follow_up"
        
        print(f"✓ Update persisted correctly")

    def test_08_cannot_delete_default_template(self):
        """DELETE on default template should fail with 400"""
        # Get a default template
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        templates = response.json()
        
        default_template = next((t for t in templates if t.get("is_default")), None)
        assert default_template, "No default template found"
        
        # Try to delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{default_template['_id']}"
        )
        assert delete_response.status_code == 400, f"Expected 400, got {delete_response.status_code}"
        assert "default" in delete_response.json().get("detail", "").lower()
        
        print(f"✓ Cannot delete default templates (got 400)")

    def test_09_delete_custom_template(self):
        """DELETE /api/templates/{user_id}/{template_id} should delete non-default template"""
        assert TestTemplatesAPI.created_template_id, "No template ID from create test"
        
        response = requests.delete(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{TestTemplatesAPI.created_template_id}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        print(f"✓ Custom template deleted")

    def test_10_verify_delete_persisted(self):
        """GET to verify deleted template is gone"""
        assert TestTemplatesAPI.created_template_id, "No template ID from create test"
        
        # Should get 404 when requesting deleted template
        response = requests.get(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{TestTemplatesAPI.created_template_id}"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        # Should not be in list either
        list_response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        templates = list_response.json()
        template_ids = [t["_id"] for t in templates]
        
        assert TestTemplatesAPI.created_template_id not in template_ids, "Deleted template still in list"
        
        print(f"✓ Template deletion verified")

    def test_11_create_duplicate_name_fails(self):
        """POST with duplicate name should fail"""
        duplicate_template = {
            "name": "Greeting",  # This is a default template name
            "content": "Some content",
            "category": "general"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}",
            json=duplicate_template
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "already exists" in response.json().get("detail", "").lower()
        
        print(f"✓ Duplicate template name rejected")

    def test_12_track_template_usage(self):
        """POST /api/templates/{user_id}/{template_id}/use should increment usage count"""
        # Get a template
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        templates = response.json()
        assert len(templates) > 0
        
        template = templates[0]
        original_count = template.get("usage_count", 0)
        
        # Track usage
        usage_response = requests.post(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{template['_id']}/use"
        )
        assert usage_response.status_code == 200
        
        # Verify count increased
        verify_response = requests.get(
            f"{BASE_URL}/api/templates/{TEST_USER_ID}/{template['_id']}"
        )
        updated_template = verify_response.json()
        assert updated_template["usage_count"] == original_count + 1
        
        print(f"✓ Usage tracking works")

    def test_13_get_template_categories(self):
        """GET /api/templates/{user_id}/categories/list should return category list"""
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}/categories/list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "categories" in data
        
        categories = data["categories"]
        assert len(categories) >= 6, "Should have at least 6 categories"
        
        category_ids = [c["id"] for c in categories]
        expected_categories = ["general", "greeting", "follow_up", "appointment", "thank_you", "review_request"]
        
        for cat_id in expected_categories:
            assert cat_id in category_ids, f"Missing category: {cat_id}"
        
        print(f"✓ Categories endpoint returns {len(categories)} categories")


# Run cleanup after all tests
@pytest.fixture(scope="class", autouse=True)
def cleanup_test_templates():
    """Cleanup any TEST_ prefixed templates after test class"""
    yield
    # Cleanup
    try:
        response = requests.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        if response.status_code == 200:
            templates = response.json()
            for template in templates:
                if template["name"].startswith("TEST_") and not template.get("is_default"):
                    requests.delete(f"{BASE_URL}/api/templates/{TEST_USER_ID}/{template['_id']}")
    except Exception as e:
        print(f"Cleanup warning: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
