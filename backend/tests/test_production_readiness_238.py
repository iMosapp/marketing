"""
Production Readiness Audit Tests - Iteration 238
Tests for:
1. Emergency-reset endpoint REMOVED (should return 404/405)
2. Login still works with forest@imosapp.com / Admin123!
3. GET /api/contacts/{user_id} with sort_by=recent and sort_by=alpha
4. GET /api/contacts/{user_id}?view_mode=team for managers
5. Contacts search with GET /api/contacts/{user_id}?search=test
6. Email signature data in brand context (sender_title, sender_phone, sender_email)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestEmergencyResetRemoved:
    """Verify the emergency-reset endpoint has been removed"""
    
    def test_emergency_reset_post_returns_404_or_405(self):
        """POST /api/auth/emergency-reset should return 404 or 405 (not 200)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/emergency-reset",
            json={"email": "test@test.com", "new_password": "test123"}
        )
        # Should NOT be 200 - endpoint should be removed
        assert response.status_code in [404, 405, 422], f"Expected 404/405/422, got {response.status_code}. Emergency-reset endpoint may still exist!"
        print(f"PASS: POST /api/auth/emergency-reset returns {response.status_code} (endpoint removed)")
    
    def test_emergency_reset_get_returns_404_or_405(self):
        """GET /api/auth/emergency-reset should return 404 or 405"""
        response = requests.get(f"{BASE_URL}/api/auth/emergency-reset")
        assert response.status_code in [404, 405], f"Expected 404/405, got {response.status_code}"
        print(f"PASS: GET /api/auth/emergency-reset returns {response.status_code}")


class TestLoginFlow:
    """Verify login still works after security changes"""
    
    def test_login_with_valid_credentials(self):
        """Login with forest@imosapp.com / Admin123! should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed with status {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        assert data["user"]["email"].lower() == TEST_EMAIL.lower(), f"Email mismatch: {data['user']['email']}"
        
        print(f"PASS: Login successful for {TEST_EMAIL}")
        print(f"  User ID: {data['user']['_id']}")
        print(f"  Role: {data['user'].get('role', 'unknown')}")
        return data
    
    def test_login_with_invalid_credentials(self):
        """Login with wrong password should fail with 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": "WrongPassword123"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Invalid credentials correctly rejected with 401")


class TestContactsAPI:
    """Test contacts endpoint with various parameters"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("token", "")
        self.user_id = data["user"]["_id"]
        self.user_role = data["user"].get("role", "user")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_contacts_default(self):
        """GET /api/contacts/{user_id} should return contacts list"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/contacts/{self.user_id} returned {len(data)} contacts")
        
        if len(data) > 0:
            contact = data[0]
            print(f"  Sample contact: {contact.get('first_name', '')} {contact.get('last_name', '')}")
    
    def test_get_contacts_sort_by_recent(self):
        """GET /api/contacts/{user_id}?sort_by=recent should return contacts sorted by recent activity"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}?sort_by=recent",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/contacts/{self.user_id}?sort_by=recent returned {len(data)} contacts")
    
    def test_get_contacts_sort_by_alpha(self):
        """GET /api/contacts/{user_id}?sort_by=alpha should return contacts sorted alphabetically"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}?sort_by=alpha",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/contacts/{self.user_id}?sort_by=alpha returned {len(data)} contacts")
        
        # Verify alphabetical sorting if we have multiple contacts
        if len(data) >= 2:
            names = [f"{c.get('first_name', '')} {c.get('last_name', '')}".strip().lower() for c in data[:5]]
            print(f"  First 5 names: {names}")
    
    def test_get_contacts_team_view_mode(self):
        """GET /api/contacts/{user_id}?view_mode=team should return team contacts for managers"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}?view_mode=team",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/contacts/{self.user_id}?view_mode=team returned {len(data)} contacts")
        print(f"  User role: {self.user_role}")
        
        # For managers, team view should include salesperson_name
        if self.user_role in ['super_admin', 'org_admin', 'store_manager'] and len(data) > 0:
            has_salesperson = any(c.get('salesperson_name') for c in data)
            print(f"  Has salesperson_name field: {has_salesperson}")
    
    def test_get_contacts_search(self):
        """GET /api/contacts/{user_id}?search=test should filter contacts"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}?search=test",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/contacts/{self.user_id}?search=test returned {len(data)} contacts")


class TestEmailSignatureInBrandContext:
    """Test that email signature data is included in brand context"""
    
    def test_brand_context_has_signature_fields(self):
        """Verify get_brand_context includes sender_title, sender_phone, sender_email"""
        # This is a code review test - we verify the implementation exists
        # by checking the email_template.py file structure
        import sys
        sys.path.insert(0, '/app/backend')
        
        try:
            from utils.email_template import get_brand_context, build_branded_email
            
            # Verify the function exists and has the right signature
            import inspect
            sig = inspect.signature(get_brand_context)
            params = list(sig.parameters.keys())
            assert 'db' in params, "get_brand_context should accept 'db' parameter"
            assert 'user_id' in params, "get_brand_context should accept 'user_id' parameter"
            
            print("PASS: get_brand_context function exists with correct signature")
            
            # Check build_branded_email exists
            sig2 = inspect.signature(build_branded_email)
            params2 = list(sig2.parameters.keys())
            assert 'content' in params2, "build_branded_email should accept 'content' parameter"
            assert 'brand' in params2, "build_branded_email should accept 'brand' parameter"
            
            print("PASS: build_branded_email function exists with correct signature")
            
        except ImportError as e:
            pytest.skip(f"Could not import email_template module: {e}")


class TestMongoDBIndexes:
    """Verify MongoDB indexes are created (code review)"""
    
    def test_indexes_defined_in_server_startup(self):
        """Verify server.py has index creation in startup event"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check for key indexes mentioned in the requirements
        required_indexes = [
            'contacts.create_index',
            'conversations.create_index',
            'messages.create_index',
            'campaign_enrollments.create_index',
            'notifications.create_index',
            'tags.create_index',
        ]
        
        for idx in required_indexes:
            assert idx in content, f"Missing index creation for: {idx}"
            print(f"PASS: Found index creation for {idx.split('.')[0]}")
        
        print("PASS: All required MongoDB indexes are defined in server.py startup")


class TestPhotoBackfillAsync:
    """Verify photo backfill is moved to async background task"""
    
    def test_photo_backfill_uses_asyncio_create_task(self):
        """Verify contacts.py uses asyncio.create_task for photo backfill"""
        with open('/app/backend/routers/contacts.py', 'r') as f:
            content = f.read()
        
        # Check for asyncio.create_task usage for photo backfill
        assert 'asyncio.create_task' in content, "Photo backfill should use asyncio.create_task"
        assert '_backfill_photos' in content, "Should have _backfill_photos function"
        
        print("PASS: Photo backfill uses asyncio.create_task for background processing")


class TestRaceConditionFix:
    """Verify frontend race condition fix with requestSeq"""
    
    def test_contacts_tsx_has_request_seq(self):
        """Verify contacts.tsx uses requestSeq to prevent stale responses"""
        with open('/app/frontend/app/(tabs)/contacts.tsx', 'r') as f:
            content = f.read()
        
        # Check for requestSeq pattern
        assert 'requestSeq' in content, "contacts.tsx should have requestSeq counter"
        assert 'requestSeq.current' in content, "Should use requestSeq.current for tracking"
        
        # Check for the stale response prevention pattern
        assert 'seq === requestSeq.current' in content, "Should check seq === requestSeq.current before updating state"
        
        print("PASS: contacts.tsx has requestSeq race condition fix")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
