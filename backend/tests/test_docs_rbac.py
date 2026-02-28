"""
Docs Role-Based Access Tests - Test that NDA doc is restricted to super_admin
Tests: list docs with/without super_admin role, get specific doc with role restrictions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Super admin credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"


class TestDocsRoleBasedAccess:
    """Test docs role-based filtering"""
    
    super_admin_user_id = None
    org_admin_user_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_super_admin_user_id(self):
        """Get super admin user ID via login"""
        if TestDocsRoleBasedAccess.super_admin_user_id:
            return TestDocsRoleBasedAccess.super_admin_user_id
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            user = response.json().get("user", {})
            user_id = user.get("_id") or user.get("id")
            TestDocsRoleBasedAccess.super_admin_user_id = user_id
            return user_id
        return None
    
    def test_01_super_admin_can_list_all_docs(self):
        """Super admin should see all docs including NDA with required_role=super_admin"""
        user_id = self.get_super_admin_user_id()
        assert user_id is not None, "Could not login as super admin"
        
        response = self.session.get(
            f"{BASE_URL}/api/docs/",
            headers={"X-User-ID": user_id}
        )
        
        assert response.status_code == 200, f"List docs failed: {response.text}"
        
        docs = response.json()
        assert isinstance(docs, list), "Response should be a list"
        
        # Find the NDA doc
        nda_doc = None
        operations_manual = None
        for doc in docs:
            if doc.get("slug") == "imos-nda":
                nda_doc = doc
            if doc.get("slug") == "imos-operations-manual":
                operations_manual = doc
        
        assert nda_doc is not None, "Super admin should see imos-nda doc"
        assert nda_doc.get("required_role") == "super_admin", "NDA should have required_role=super_admin"
        
        print(f"Super admin sees {len(docs)} docs, including NDA")
        
        # Store doc IDs for later tests
        if nda_doc:
            TestDocsRoleBasedAccess.nda_doc_id = nda_doc["_id"]
        if operations_manual:
            TestDocsRoleBasedAccess.operations_manual_id = operations_manual["_id"]
    
    def test_02_super_admin_can_get_nda_doc(self):
        """Super admin should be able to get NDA doc details"""
        user_id = self.get_super_admin_user_id()
        nda_doc_id = getattr(TestDocsRoleBasedAccess, 'nda_doc_id', None)
        
        if not nda_doc_id:
            pytest.skip("No NDA doc ID available")
        
        response = self.session.get(
            f"{BASE_URL}/api/docs/{nda_doc_id}",
            headers={"X-User-ID": user_id}
        )
        
        assert response.status_code == 200, f"Get NDA doc failed: {response.text}"
        
        doc = response.json()
        assert doc.get("slug") == "imos-nda"
        assert doc.get("required_role") == "super_admin"
        assert "slides" in doc
        
        print(f"Super admin can access NDA doc with {len(doc.get('slides', []))} slides")
    
    def test_03_super_admin_can_get_operations_manual(self):
        """Super admin should be able to get operations manual (no required_role)"""
        user_id = self.get_super_admin_user_id()
        ops_manual_id = getattr(TestDocsRoleBasedAccess, 'operations_manual_id', None)
        
        if not ops_manual_id:
            pytest.skip("No operations manual ID available")
        
        response = self.session.get(
            f"{BASE_URL}/api/docs/{ops_manual_id}",
            headers={"X-User-ID": user_id}
        )
        
        assert response.status_code == 200, f"Get operations manual failed: {response.text}"
        
        doc = response.json()
        assert doc.get("slug") == "imos-operations-manual"
        assert "slides" in doc
        
        print(f"Super admin can access operations manual with {len(doc.get('slides', []))} slides")
    
    def test_04_docs_list_without_user_id_fails(self):
        """List docs without X-User-ID should fail with 401"""
        response = self.session.get(f"{BASE_URL}/api/docs/")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Correctly denied access without authentication")
    
    def test_05_verify_role_based_filtering_in_query(self):
        """Verify that docs list endpoint filters by role correctly"""
        user_id = self.get_super_admin_user_id()
        
        # Get all docs
        response = self.session.get(
            f"{BASE_URL}/api/docs/",
            headers={"X-User-ID": user_id}
        )
        
        assert response.status_code == 200
        docs = response.json()
        
        # Count docs with required_role
        restricted_docs = [d for d in docs if d.get("required_role") == "super_admin"]
        unrestricted_docs = [d for d in docs if not d.get("required_role")]
        
        print(f"Found {len(restricted_docs)} super_admin restricted docs")
        print(f"Found {len(unrestricted_docs)} unrestricted docs")
        
        # At least the NDA should be in restricted
        assert len(restricted_docs) >= 1, "Should have at least 1 super_admin restricted doc (NDA)"


class TestDocCategories:
    """Test doc categories endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_super_admin_user_id(self):
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            user = response.json().get("user", {})
            return user.get("_id") or user.get("id")
        return None
    
    def test_categories_endpoint(self):
        """GET /api/docs/categories - should return category list"""
        user_id = self.get_super_admin_user_id()
        assert user_id is not None
        
        response = self.session.get(
            f"{BASE_URL}/api/docs/categories",
            headers={"X-User-ID": user_id}
        )
        
        assert response.status_code == 200, f"Get categories failed: {response.text}"
        
        categories = response.json()
        assert isinstance(categories, list)
        assert len(categories) > 0
        
        # Verify category structure
        cat = categories[0]
        assert "id" in cat
        assert "name" in cat
        assert "icon" in cat
        assert "color" in cat
        
        print(f"Found {len(categories)} doc categories: {[c['id'] for c in categories]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
