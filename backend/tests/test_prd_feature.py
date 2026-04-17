"""
Test PRD Feature - Backend API Tests
Tests GET /api/docs/prd, PUT /api/docs/prd, and GET /api/docs/categories
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPRDFeature:
    """PRD document viewing and editing feature tests"""

    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Login and get auth headers with user ID"""
        # Login as super admin
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        user_id = data.get('user', {}).get('_id') or data.get('user_id')
        assert user_id, f"No user ID in response: {data}"
        return {"X-User-ID": user_id}

    def test_01_get_categories_includes_prd(self, auth_headers):
        """GET /api/docs/categories should include PRD as first category"""
        response = requests.get(f"{BASE_URL}/api/docs/categories", headers=auth_headers)
        assert response.status_code == 200, f"Categories failed: {response.text}"
        categories = response.json()
        
        # Verify it's a list
        assert isinstance(categories, list), "Categories should be a list"
        assert len(categories) > 0, "Categories should not be empty"
        
        # PRD should be first category
        first_cat = categories[0]
        assert first_cat['id'] == 'prd', f"First category should be 'prd', got: {first_cat['id']}"
        assert first_cat['name'] == 'PRD', f"PRD category name mismatch: {first_cat['name']}"
        assert 'icon' in first_cat, "PRD category should have icon"
        assert 'color' in first_cat, "PRD category should have color"
        print(f"PASS: PRD is first category with id='{first_cat['id']}', name='{first_cat['name']}'")

    def test_02_get_prd_document(self, auth_headers):
        """GET /api/docs/prd should return PRD document with content, title, updated_at"""
        response = requests.get(f"{BASE_URL}/api/docs/prd", headers=auth_headers)
        assert response.status_code == 200, f"GET PRD failed: {response.text}"
        
        doc = response.json()
        
        # Verify required fields
        assert 'title' in doc, "PRD should have 'title'"
        assert 'content' in doc, "PRD should have 'content'"
        assert 'updated_at' in doc, "PRD should have 'updated_at'"
        
        # Verify content is markdown string
        assert isinstance(doc['content'], str), "PRD content should be string"
        assert len(doc['content']) > 0, "PRD content should not be empty"
        
        # Verify title
        assert doc['title'] == 'Product Requirements Document', f"Title mismatch: {doc['title']}"
        
        # Verify it has PRD category and slug
        assert doc.get('category') == 'prd', f"Category should be 'prd': {doc.get('category')}"
        assert doc.get('slug') == 'product-requirements-document', f"Slug mismatch: {doc.get('slug')}"
        
        print(f"PASS: PRD document loaded - title='{doc['title']}', content_length={len(doc['content'])}")

    def test_03_update_prd_document(self, auth_headers):
        """PUT /api/docs/prd should update content and return success + updated_at"""
        # First get current content
        get_response = requests.get(f"{BASE_URL}/api/docs/prd", headers=auth_headers)
        assert get_response.status_code == 200, f"GET PRD failed: {get_response.text}"
        original_content = get_response.json()['content']
        
        # Add a test line
        test_marker = "\n\n<!-- PRD Test Update -->"
        new_content = original_content + test_marker
        
        # Update PRD
        response = requests.put(
            f"{BASE_URL}/api/docs/prd",
            json={"content": new_content},
            headers=auth_headers
        )
        assert response.status_code == 200, f"PUT PRD failed: {response.text}"
        
        result = response.json()
        assert result.get('success') == True, f"Update should return success=True: {result}"
        assert 'updated_at' in result, "Update should return updated_at"
        
        # Verify the content was persisted
        verify_response = requests.get(f"{BASE_URL}/api/docs/prd", headers=auth_headers)
        assert verify_response.status_code == 200
        updated_doc = verify_response.json()
        assert test_marker in updated_doc['content'], "Content update was not persisted"
        
        print(f"PASS: PRD updated successfully - updated_at={result['updated_at']}")
        
        # Restore original content
        restore_response = requests.put(
            f"{BASE_URL}/api/docs/prd",
            json={"content": original_content},
            headers=auth_headers
        )
        assert restore_response.status_code == 200, f"Restore failed: {restore_response.text}"
        print("PASS: PRD content restored to original")

    def test_04_update_prd_requires_content(self, auth_headers):
        """PUT /api/docs/prd without content field should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/docs/prd",
            json={},  # No content field
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got: {response.status_code}"
        print(f"PASS: Missing content returns 400 as expected")

    def test_05_prd_requires_auth(self):
        """GET and PUT /api/docs/prd require authentication"""
        # GET without auth
        get_response = requests.get(f"{BASE_URL}/api/docs/prd")
        assert get_response.status_code in [401, 403], f"GET should require auth: {get_response.status_code}"
        
        # PUT without auth
        put_response = requests.put(
            f"{BASE_URL}/api/docs/prd",
            json={"content": "test"}
        )
        assert put_response.status_code in [401, 403], f"PUT should require auth: {put_response.status_code}"
        print("PASS: PRD endpoints require authentication")

    def test_06_prd_content_has_markdown(self, auth_headers):
        """PRD content should contain markdown structure (headings, bullets)"""
        response = requests.get(f"{BASE_URL}/api/docs/prd", headers=auth_headers)
        assert response.status_code == 200
        content = response.json()['content']
        
        # Check for common markdown elements
        has_h1 = '# ' in content
        has_h2 = '## ' in content
        has_bullets = '- ' in content
        
        assert has_h1 or has_h2, "PRD should have markdown headings (# or ##)"
        print(f"PASS: PRD has markdown structure - H1={has_h1}, H2={has_h2}, bullets={has_bullets}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
