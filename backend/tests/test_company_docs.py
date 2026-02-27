"""
Test Company Docs API endpoints
- Tests admin-only document hub for policies, security, training, and integrations
- Requires super_admin/org_admin/store_manager authentication via X-User-ID header
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - super_admin user
SUPER_ADMIN_USER_ID = "69a0b7095fddcede09591667"


class TestCompanyDocsAPI:
    """Company Docs API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test client with auth headers"""
        self.headers = {"X-User-ID": SUPER_ADMIN_USER_ID}
    
    def test_list_all_docs_returns_8_documents(self):
        """GET /api/docs/ - Returns all 8 seeded documents"""
        response = requests.get(f"{BASE_URL}/api/docs/", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) == 8, f"Expected 8 documents, got {len(docs)}"
        
        # Verify expected document titles
        expected_titles = [
            "Cyber Security Policy",
            "Company Policy & Code of Conduct", 
            "Terms of Service",
            "Privacy Policy",
            "Data Retention Policy",
            "Security Awareness Training",
            "Platform Onboarding Guide",
            "Integration & API Documentation"
        ]
        titles = [d.get("title") for d in docs]
        for expected in expected_titles:
            assert expected in titles, f"Missing document: {expected}"
        
    def test_filter_docs_by_category_security(self):
        """GET /api/docs/?category=security - Returns only security docs"""
        response = requests.get(f"{BASE_URL}/api/docs/?category=security", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) >= 1, "Expected at least 1 security document"
        
        # Verify all returned docs are security category
        for doc in docs:
            assert doc.get("category") == "security", f"Doc '{doc.get('title')}' is not security category"
    
    def test_filter_docs_by_category_legal(self):
        """GET /api/docs/?category=legal - Returns only legal docs"""
        response = requests.get(f"{BASE_URL}/api/docs/?category=legal", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) >= 2, "Expected at least 2 legal documents (Terms of Service, Privacy Policy)"
        
        # Verify all returned docs are legal category
        for doc in docs:
            assert doc.get("category") == "legal", f"Doc '{doc.get('title')}' is not legal category"
    
    def test_search_docs_by_privacy(self):
        """GET /api/docs/?search=privacy - Returns matching docs"""
        response = requests.get(f"{BASE_URL}/api/docs/?search=privacy", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) >= 1, "Expected at least 1 document matching 'privacy'"
        
        # Verify Privacy Policy is in results
        titles = [d.get("title") for d in docs]
        assert "Privacy Policy" in titles, "Privacy Policy should be in search results"
    
    def test_search_docs_by_security(self):
        """GET /api/docs/?search=security - Returns matching docs"""
        response = requests.get(f"{BASE_URL}/api/docs/?search=security", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) >= 1, "Expected at least 1 document matching 'security'"
    
    def test_get_categories_returns_5_categories(self):
        """GET /api/docs/categories - Returns 5 categories"""
        response = requests.get(f"{BASE_URL}/api/docs/categories", headers=self.headers)
        
        assert response.status_code == 200
        categories = response.json()
        assert len(categories) == 5, f"Expected 5 categories, got {len(categories)}"
        
        # Verify expected category names
        expected_names = ["Cyber Security", "Company Policy", "Legal", "Training", "Integrations"]
        names = [c.get("name") for c in categories]
        for expected in expected_names:
            assert expected in names, f"Missing category: {expected}"
        
        # Verify category structure
        for cat in categories:
            assert "id" in cat, "Category missing 'id' field"
            assert "name" in cat, "Category missing 'name' field"
            assert "icon" in cat, "Category missing 'icon' field"
            assert "color" in cat, "Category missing 'color' field"
    
    def test_get_single_doc_returns_full_document_with_slides(self):
        """GET /api/docs/{doc_id} - Returns full document with slides"""
        # First get a doc_id from the list
        list_response = requests.get(f"{BASE_URL}/api/docs/?search=privacy", headers=self.headers)
        assert list_response.status_code == 200
        docs = list_response.json()
        assert len(docs) >= 1, "Need at least 1 document to test"
        
        doc_id = docs[0].get("_id")
        
        # Get full document
        response = requests.get(f"{BASE_URL}/api/docs/{doc_id}", headers=self.headers)
        
        assert response.status_code == 200
        doc = response.json()
        
        # Verify document structure
        assert doc.get("title") == "Privacy Policy", f"Expected 'Privacy Policy', got '{doc.get('title')}'"
        assert "slides" in doc, "Document missing 'slides' field"
        assert len(doc.get("slides", [])) >= 1, "Document should have at least 1 slide"
        
        # Verify slide structure
        slide = doc.get("slides")[0]
        assert "order" in slide, "Slide missing 'order' field"
        assert "title" in slide, "Slide missing 'title' field"
        assert "description" in slide, "Slide missing 'description' field"
    
    def test_get_nonexistent_doc_returns_404(self):
        """GET /api/docs/{invalid_id} - Returns 404 for invalid doc"""
        # Use a valid ObjectId format but non-existent document
        fake_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/docs/{fake_id}", headers=self.headers)
        
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    def test_unauthenticated_request_returns_401(self):
        """GET /api/docs/ without X-User-ID - Returns 401"""
        response = requests.get(f"{BASE_URL}/api/docs/")
        
        assert response.status_code == 401
    
    def test_docs_list_excludes_slides(self):
        """GET /api/docs/ - List endpoint should NOT include slides (for performance)"""
        response = requests.get(f"{BASE_URL}/api/docs/", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        
        # Verify no slides in list response
        for doc in docs:
            assert "slides" not in doc, f"Document '{doc.get('title')}' should not include slides in list view"
    
    def test_doc_has_required_fields(self):
        """Verify documents have all required fields"""
        response = requests.get(f"{BASE_URL}/api/docs/", headers=self.headers)
        
        assert response.status_code == 200
        docs = response.json()
        
        required_fields = ["_id", "title", "summary", "category", "icon", "version"]
        for doc in docs:
            for field in required_fields:
                assert field in doc, f"Document '{doc.get('title')}' missing '{field}' field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
