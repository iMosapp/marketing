"""
Test Setup Wizard API - Tests for Phase 1 Admin Setup Wizard endpoints:
- GET /api/setup-wizard/progress/{org_id}: returns default progress for unknown org
- POST /api/setup-wizard/progress/{org_id}: saves wizard progress
- POST /api/setup-wizard/bulk-invite: creates team members with temp passwords
- POST /api/setup-wizard/complete/{org_id}: marks wizard complete
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_USER_ID = "69a0b7095fddcede09591667"  # forest@imonsocial.com user ID
TEST_STORE_ID = "69a0b7095fddcede09591668"  # existing store


class TestSetupWizardProgress:
    """Tests for wizard progress endpoints"""

    def test_get_progress_unknown_org(self):
        """GET /api/setup-wizard/progress/{org_id} returns default progress for unknown org"""
        random_org_id = f"test_{uuid.uuid4().hex[:12]}"
        response = requests.get(
            f"{BASE_URL}/api/setup-wizard/progress/{random_org_id}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("organization_id") == random_org_id, f"org_id mismatch: {data}"
        assert data.get("current_step") == 1, f"expected current_step=1, got {data.get('current_step')}"
        assert data.get("completed_steps") == [], f"expected empty completed_steps, got {data.get('completed_steps')}"
        assert data.get("completed") == False, f"expected completed=False, got {data.get('completed')}"
        print(f"[PASS] GET progress for unknown org returns default values")

    def test_save_and_get_progress(self):
        """POST /api/setup-wizard/progress/{org_id} saves progress and GET retrieves it"""
        test_org_id = f"test_{uuid.uuid4().hex[:12]}"
        
        # Save progress
        progress_payload = {
            "store_id": TEST_STORE_ID,
            "current_step": 3,
            "completed_steps": [1, 2],
            "completed": False
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/setup-wizard/progress/{test_org_id}",
            json=progress_payload,
            headers={"X-User-ID": TEST_USER_ID, "Content-Type": "application/json"}
        )
        
        assert save_response.status_code == 200, f"Expected 200, got {save_response.status_code}: {save_response.text}"
        save_data = save_response.json()
        assert save_data.get("success") == True, f"Expected success=True, got {save_data}"
        print(f"[PASS] POST progress saves successfully")
        
        # Retrieve progress to verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/setup-wizard/progress/{test_org_id}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        
        assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}"
        get_data = get_response.json()
        
        assert get_data.get("organization_id") == test_org_id
        assert get_data.get("current_step") == 3
        assert get_data.get("completed_steps") == [1, 2]
        assert get_data.get("completed") == False
        print(f"[PASS] GET progress retrieves saved values correctly")


class TestSetupWizardBulkInvite:
    """Tests for bulk team member invite endpoint"""

    def test_bulk_invite_creates_users(self):
        """POST /api/setup-wizard/bulk-invite creates team members with temp passwords"""
        unique_id = uuid.uuid4().hex[:8]
        members = [
            {
                "name": f"Test User {unique_id} A",
                "email": f"testuser_{unique_id}_a@testexample.com",
                "phone": "5551234567",
                "role": "user"
            },
            {
                "name": f"Test User {unique_id} B",
                "email": f"testuser_{unique_id}_b@testexample.com",
                "phone": "5559876543",
                "role": "store_manager"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/bulk-invite",
            json={
                "store_id": TEST_STORE_ID,
                "members": members
            },
            headers={"X-User-ID": TEST_USER_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("total") == 2, f"Expected total=2, got {data.get('total')}"
        assert data.get("created") == 2, f"Expected created=2, got {data.get('created')}"
        
        results = data.get("results", [])
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        for result in results:
            assert result.get("status") == "created", f"Expected status=created, got {result}"
            assert "temp_password" in result, f"Expected temp_password in result: {result}"
            assert len(result.get("temp_password", "")) > 0, f"Expected non-empty temp_password"
            assert "user_id" in result, f"Expected user_id in result: {result}"
        
        print(f"[PASS] Bulk invite creates {data.get('created')} users with temp passwords")

    def test_bulk_invite_skip_existing_email(self):
        """POST /api/setup-wizard/bulk-invite skips existing email"""
        # Use existing user email
        members = [
            {
                "name": "Test Existing User",
                "email": "forest@imonsocial.com",  # existing user
                "phone": "5551111111",
                "role": "user"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/bulk-invite",
            json={
                "store_id": TEST_STORE_ID,
                "members": members
            },
            headers={"X-User-ID": TEST_USER_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        results = data.get("results", [])
        assert len(results) == 1
        assert results[0].get("status") == "skipped", f"Expected status=skipped for existing email, got {results[0]}"
        assert "already exists" in results[0].get("reason", "").lower(), f"Expected 'already exists' reason, got {results[0]}"
        
        print(f"[PASS] Bulk invite skips existing email correctly")

    def test_bulk_invite_requires_auth(self):
        """POST /api/setup-wizard/bulk-invite requires X-User-ID header"""
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/bulk-invite",
            json={
                "store_id": TEST_STORE_ID,
                "members": []
            },
            headers={"Content-Type": "application/json"}
            # No X-User-ID header
        )
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}: {response.text}"
        print(f"[PASS] Bulk invite correctly requires auth header")

    def test_bulk_invite_invalid_store(self):
        """POST /api/setup-wizard/bulk-invite returns 404 for invalid store"""
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/bulk-invite",
            json={
                "store_id": "000000000000000000000000",  # invalid store ID
                "members": [{"name": "Test", "email": "test@test.com", "role": "user"}]
            },
            headers={"X-User-ID": TEST_USER_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid store, got {response.status_code}: {response.text}"
        print(f"[PASS] Bulk invite returns 404 for invalid store")


class TestSetupWizardComplete:
    """Tests for wizard completion endpoint"""

    def test_mark_wizard_complete(self):
        """POST /api/setup-wizard/complete/{org_id} marks wizard complete"""
        test_org_id = f"test_{uuid.uuid4().hex[:12]}"
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/complete/{test_org_id}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "completed" in data.get("message", "").lower() or data.get("success") == True
        
        print(f"[PASS] Mark wizard complete returns success")
        
        # Verify completion state via GET progress
        get_response = requests.get(
            f"{BASE_URL}/api/setup-wizard/progress/{test_org_id}",
            headers={"X-User-ID": TEST_USER_ID}
        )
        
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("completed") == True, f"Expected completed=True after marking complete, got {get_data}"
        print(f"[PASS] GET progress confirms wizard is marked complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
