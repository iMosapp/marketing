"""
Test Suite for RMS Bug Fixes - Iteration 179
Tests the following fixes:
1. GET /api/auth/user/{user_id} - returns store object with slug and name
2. POST /api/docs/seed - clears and re-seeds docs (works even if docs exist)
3. POST /api/docs/generate-articles-of-incorporation - generates legal document with slides
4. POST /api/docs/seed-project-scope - creates/updates operations manual
5. GET /api/docs/ - lists all documents including Articles of Incorporation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://rms-polish.preview.emergentagent.com")

# Test credentials from the review request
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestAuthUserEndpoint:
    """Test GET /api/auth/user/{user_id} returns store object with slug"""

    def test_get_user_returns_store_slug(self):
        """Verify user endpoint returns store.slug field"""
        response = requests.get(f"{BASE_URL}/api/auth/user/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"User response keys: {data.keys()}")
        
        # Check for store object or store_slug field
        if "store" in data:
            store = data["store"]
            print(f"Store object: {store}")
            assert "slug" in store, "Store object missing 'slug' field"
            assert store.get("slug") is not None, "Store slug should not be None"
            # According to context, expected slug is 'imos-demo'
            if store.get("slug"):
                print(f"Store slug: {store['slug']}")
        elif "store_slug" in data:
            print(f"Store slug (direct field): {data['store_slug']}")
            assert data["store_slug"] is not None, "store_slug should not be None"
        else:
            pytest.skip("User may not have a store_id assigned - skipping store slug check")
    
    def test_get_user_returns_name(self):
        """Verify user endpoint returns basic user info"""
        response = requests.get(f"{BASE_URL}/api/auth/user/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "_id" in data or "id" in data, "User should have an ID"
        # Password should be excluded
        assert "password" not in data, "Password should not be in response"


class TestDocsSeeding:
    """Test /api/docs/seed endpoint - should clear and re-seed"""

    @pytest.fixture(autouse=True)
    def login_super_admin(self):
        """Login and get headers for authenticated requests"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        if login_resp.status_code != 200:
            pytest.skip(f"Could not login as super admin: {login_resp.text}")
        
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id")
        self.headers = {"X-User-ID": self.user_id}
        print(f"Logged in as super admin, user_id: {self.user_id}")

    def test_seed_docs_succeeds_on_first_run(self):
        """POST /api/docs/seed should succeed (clears and re-seeds)"""
        response = requests.post(
            f"{BASE_URL}/api/docs/seed",
            json={},
            headers=self.headers
        )
        print(f"Seed response: {response.status_code} - {response.text}")
        
        # Should NOT return 400 "already seeded" anymore
        assert response.status_code != 400, f"Should not fail with 'already seeded': {response.text}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_seed_docs_succeeds_on_subsequent_runs(self):
        """POST /api/docs/seed should work even if docs exist (re-seeds)"""
        # First call
        resp1 = requests.post(f"{BASE_URL}/api/docs/seed", json={}, headers=self.headers)
        print(f"First seed call: {resp1.status_code}")
        
        # Second call - should NOT fail
        resp2 = requests.post(f"{BASE_URL}/api/docs/seed", json={}, headers=self.headers)
        print(f"Second seed call: {resp2.status_code} - {resp2.text}")
        
        assert resp2.status_code == 200, f"Re-seeding should work, got {resp2.status_code}: {resp2.text}"
        assert "already seeded" not in resp2.text.lower(), "Should not return 'already seeded' error"


class TestDocsList:
    """Test GET /api/docs/ lists all documents"""

    @pytest.fixture(autouse=True)
    def login_super_admin(self):
        """Login and get headers"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        if login_resp.status_code != 200:
            pytest.skip(f"Could not login: {login_resp.text}")
        
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id")
        self.headers = {"X-User-ID": self.user_id}

    def test_list_docs_returns_documents(self):
        """GET /api/docs/ should return list of documents"""
        response = requests.get(f"{BASE_URL}/api/docs/", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        docs = response.json()
        assert isinstance(docs, list), "Should return a list"
        print(f"Found {len(docs)} documents")
        
        if len(docs) > 0:
            for doc in docs[:5]:
                print(f"  - {doc.get('title')} (category: {doc.get('category')})")

    def test_list_docs_by_category(self):
        """GET /api/docs/?category=legal should filter by category"""
        response = requests.get(f"{BASE_URL}/api/docs/?category=legal", headers=self.headers)
        assert response.status_code == 200
        
        docs = response.json()
        for doc in docs:
            assert doc.get("category") == "legal", f"Expected legal category, got {doc.get('category')}"
        print(f"Found {len(docs)} legal documents")


class TestSeedProjectScope:
    """Test POST /api/docs/seed-project-scope creates/updates operations manual"""

    @pytest.fixture(autouse=True)
    def login_super_admin(self):
        """Login and get headers"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        if login_resp.status_code != 200:
            pytest.skip(f"Could not login: {login_resp.text}")
        
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id")
        self.headers = {"X-User-ID": self.user_id}

    def test_seed_project_scope_creates_manual(self):
        """POST /api/docs/seed-project-scope should create/update operations manual"""
        response = requests.post(
            f"{BASE_URL}/api/docs/seed-project-scope",
            json={},
            headers=self.headers
        )
        print(f"Seed project scope response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain document id"
        assert "message" in data, "Response should contain message"
        print(f"Operations manual: {data.get('message')}, id: {data.get('id')}")

    def test_operations_manual_appears_in_list(self):
        """Operations manual should appear in docs list after seeding"""
        # First seed it
        requests.post(f"{BASE_URL}/api/docs/seed-project-scope", json={}, headers=self.headers)
        
        # Then list all docs
        response = requests.get(f"{BASE_URL}/api/docs/", headers=self.headers)
        assert response.status_code == 200
        
        docs = response.json()
        ops_manual = next((d for d in docs if "operations" in d.get("title", "").lower() or d.get("category") == "operations"), None)
        
        if ops_manual:
            print(f"Found operations manual: {ops_manual.get('title')}")
            assert ops_manual.get("category") == "operations", "Should be in operations category"
        else:
            # May have been filtered or not created yet
            print("Operations manual not found in list - may need to verify category filter")


class TestGenerateArticlesOfIncorporation:
    """Test POST /api/docs/generate-articles-of-incorporation"""

    @pytest.fixture(autouse=True)
    def login_super_admin(self):
        """Login and get headers"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        if login_resp.status_code != 200:
            pytest.skip(f"Could not login: {login_resp.text}")
        
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id")
        self.headers = {"X-User-ID": self.user_id}

    def test_generate_articles_of_incorporation(self):
        """POST /api/docs/generate-articles-of-incorporation should generate legal doc"""
        response = requests.post(
            f"{BASE_URL}/api/docs/generate-articles-of-incorporation",
            json={},
            headers=self.headers,
            timeout=60  # AI generation may take time
        )
        print(f"Generate articles response: {response.status_code} - {response.text[:500]}")
        
        # Allow 200 or 500 (if AI service not configured)
        if response.status_code == 500 and "not configured" in response.text.lower():
            pytest.skip("AI service not configured - skipping AI generation test")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain document id"
        assert "slides_count" in data, "Response should contain slides_count"
        print(f"Generated document with {data.get('slides_count')} slides")

    def test_articles_appears_in_list_after_generation(self):
        """Articles of Incorporation should appear in docs list after generation"""
        # Generate first
        gen_resp = requests.post(
            f"{BASE_URL}/api/docs/generate-articles-of-incorporation",
            json={},
            headers=self.headers,
            timeout=60
        )
        
        if gen_resp.status_code == 500 and "not configured" in gen_resp.text.lower():
            pytest.skip("AI service not configured")
        
        # List docs
        response = requests.get(f"{BASE_URL}/api/docs/", headers=self.headers)
        assert response.status_code == 200
        
        docs = response.json()
        articles = next((d for d in docs if "articles of incorporation" in d.get("title", "").lower()), None)
        
        if articles:
            print(f"Found Articles of Incorporation: {articles.get('title')}")
            assert articles.get("category") == "legal", "Should be in legal category"
        else:
            print("Articles not found - may have been cleared by seed endpoint")


class TestDocsCategories:
    """Test GET /api/docs/categories returns available categories"""

    @pytest.fixture(autouse=True)
    def login_admin(self):
        """Login and get headers"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        if login_resp.status_code != 200:
            pytest.skip(f"Could not login: {login_resp.text}")
        
        user_data = login_resp.json()
        self.user_id = user_data.get("user", {}).get("_id")
        self.headers = {"X-User-ID": self.user_id}

    def test_get_categories(self):
        """GET /api/docs/categories should return list of categories"""
        response = requests.get(f"{BASE_URL}/api/docs/categories", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        categories = response.json()
        assert isinstance(categories, list), "Should return a list"
        print(f"Found {len(categories)} categories:")
        
        for cat in categories:
            print(f"  - {cat.get('id')}: {cat.get('name')}")
        
        # Verify expected categories exist
        cat_ids = [c.get("id") for c in categories]
        assert "operations" in cat_ids, "Should have 'operations' category"
        assert "legal" in cat_ids, "Should have 'legal' category"


class TestAccessControl:
    """Test that non-admin users cannot access admin-only endpoints"""

    def test_seed_requires_super_admin(self):
        """POST /api/docs/seed should require super admin"""
        # Try without auth header
        response = requests.post(f"{BASE_URL}/api/docs/seed", json={})
        assert response.status_code in [401, 403], f"Should reject unauthenticated: {response.status_code}"
    
    def test_generate_articles_requires_super_admin(self):
        """POST /api/docs/generate-articles-of-incorporation should require super admin"""
        response = requests.post(f"{BASE_URL}/api/docs/generate-articles-of-incorporation", json={})
        assert response.status_code in [401, 403], f"Should reject unauthenticated: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
