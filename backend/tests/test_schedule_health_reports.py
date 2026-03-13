"""
Tests for Scheduled Health Reports CRUD API
Tests: POST /api/account-health/schedules, GET /api/account-health/schedules, 
       PUT /api/account-health/schedules/{id}, DELETE /api/account-health/schedules/{id}
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID (existing user)
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestSchedulesCRUD:
    """Tests for schedule CRUD operations"""
    
    created_schedule_ids = []  # Track for cleanup
    
    # --- CREATE Tests ---
    
    def test_create_schedule_user_scope(self):
        """POST /api/account-health/schedules - Create schedule for individual user"""
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "target_name": "Test User Schedule",
            "recipient_email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "recipient_name": "Test Recipient",
            "note": "Automated test schedule"
        }
        response = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure and values
        assert data["scope"] == "user"
        assert data["target_id"] == TEST_USER_ID
        assert data["recipient_email"] == payload["recipient_email"]
        assert data["note"] == "Automated test schedule"
        assert data["frequency"] == "monthly"
        assert data["active"] == True
        assert "id" in data
        assert "created_at" in data
        assert data["last_sent_at"] is None
        
        # Store for cleanup
        self.created_schedule_ids.append(data["id"])
        print(f"Created schedule: {data['id']}")
    
    def test_create_schedule_with_minimal_fields(self):
        """POST - Create schedule with only required fields"""
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "recipient_email": f"minimal_{uuid.uuid4().hex[:8]}@example.com"
        }
        response = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["scope"] == "user"
        assert data["active"] == True
        assert "id" in data
        
        self.created_schedule_ids.append(data["id"])
        print(f"Created minimal schedule: {data['id']}")
    
    def test_create_schedule_invalid_scope(self):
        """POST - Should return 400 for invalid scope"""
        payload = {
            "scope": "invalid",
            "target_id": TEST_USER_ID,
            "recipient_email": "test@example.com"
        }
        response = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "scope must be 'user' or 'org'" in response.json().get("detail", "")
    
    def test_create_schedule_nonexistent_user(self):
        """POST - Should return 404 for non-existent user"""
        payload = {
            "scope": "user",
            "target_id": "000000000000000000000000",  # Valid format but non-existent
            "recipient_email": "test@example.com"
        }
        response = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    
    # --- READ Tests ---
    
    def test_list_schedules(self):
        """GET /api/account-health/schedules - List all schedules"""
        # First create a schedule to ensure list is not empty
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "recipient_email": f"list_test_{uuid.uuid4().hex[:8]}@example.com"
        }
        create_resp = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert create_resp.status_code == 200
        created_id = create_resp.json()["id"]
        self.created_schedule_ids.append(created_id)
        
        # Now list
        response = requests.get(f"{BASE_URL}/api/account-health/schedules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify structure of items
        schedule = data[0]
        assert "id" in schedule
        assert "scope" in schedule
        assert "target_id" in schedule
        assert "recipient_email" in schedule
        assert "active" in schedule
        assert "created_at" in schedule
        print(f"Listed {len(data)} schedules")
    
    # --- UPDATE Tests ---
    
    def test_update_schedule_toggle_active(self):
        """PUT /api/account-health/schedules/{id} - Toggle active status"""
        # Create a schedule first
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "recipient_email": f"toggle_test_{uuid.uuid4().hex[:8]}@example.com"
        }
        create_resp = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert create_resp.status_code == 200
        schedule_id = create_resp.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Toggle to inactive
        update_resp = requests.put(
            f"{BASE_URL}/api/account-health/schedules/{schedule_id}",
            json={"active": False}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "updated"
        
        # Verify via GET
        list_resp = requests.get(f"{BASE_URL}/api/account-health/schedules")
        schedules = list_resp.json()
        updated = next((s for s in schedules if s["id"] == schedule_id), None)
        assert updated is not None
        assert updated["active"] == False
        
        # Toggle back to active
        update_resp = requests.put(
            f"{BASE_URL}/api/account-health/schedules/{schedule_id}",
            json={"active": True}
        )
        assert update_resp.status_code == 200
        
        list_resp = requests.get(f"{BASE_URL}/api/account-health/schedules")
        updated = next((s for s in list_resp.json() if s["id"] == schedule_id), None)
        assert updated["active"] == True
        print(f"Toggle test passed for {schedule_id}")
    
    def test_update_schedule_change_email(self):
        """PUT - Update recipient email"""
        # Create
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "recipient_email": f"original_{uuid.uuid4().hex[:8]}@example.com"
        }
        create_resp = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        schedule_id = create_resp.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Update email
        new_email = f"updated_{uuid.uuid4().hex[:8]}@example.com"
        update_resp = requests.put(
            f"{BASE_URL}/api/account-health/schedules/{schedule_id}",
            json={"recipient_email": new_email}
        )
        assert update_resp.status_code == 200
        
        # Verify
        list_resp = requests.get(f"{BASE_URL}/api/account-health/schedules")
        updated = next((s for s in list_resp.json() if s["id"] == schedule_id), None)
        assert updated["recipient_email"] == new_email
        print(f"Email update test passed")
    
    def test_update_schedule_nonexistent(self):
        """PUT - Should return 404 for non-existent schedule"""
        response = requests.put(
            f"{BASE_URL}/api/account-health/schedules/000000000000000000000000",
            json={"active": False}
        )
        assert response.status_code == 404
    
    def test_update_schedule_invalid_fields(self):
        """PUT - Should return 400 for invalid/no fields"""
        # Create first
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "recipient_email": f"invalid_field_{uuid.uuid4().hex[:8]}@example.com"
        }
        create_resp = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        schedule_id = create_resp.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Try to update with invalid field
        response = requests.put(
            f"{BASE_URL}/api/account-health/schedules/{schedule_id}",
            json={"invalid_field": "value"}
        )
        assert response.status_code == 400
        assert "No valid fields to update" in response.json().get("detail", "")
    
    # --- DELETE Tests ---
    
    def test_delete_schedule(self):
        """DELETE /api/account-health/schedules/{id} - Delete a schedule"""
        # Create
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "recipient_email": f"delete_test_{uuid.uuid4().hex[:8]}@example.com"
        }
        create_resp = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        schedule_id = create_resp.json()["id"]
        
        # Delete
        delete_resp = requests.delete(f"{BASE_URL}/api/account-health/schedules/{schedule_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"
        
        # Verify deleted - should not be in list
        list_resp = requests.get(f"{BASE_URL}/api/account-health/schedules")
        deleted = next((s for s in list_resp.json() if s["id"] == schedule_id), None)
        assert deleted is None
        print(f"Delete test passed for {schedule_id}")
    
    def test_delete_schedule_nonexistent(self):
        """DELETE - Should return 404 for non-existent schedule"""
        response = requests.delete(f"{BASE_URL}/api/account-health/schedules/000000000000000000000000")
        assert response.status_code == 404
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Cleanup created test schedules after all tests"""
        yield
        for schedule_id in self.created_schedule_ids:
            try:
                requests.delete(f"{BASE_URL}/api/account-health/schedules/{schedule_id}")
            except:
                pass
        self.created_schedule_ids.clear()


class TestScheduleDataPersistence:
    """Test data persistence and integrity"""
    
    def test_create_and_verify_all_fields(self):
        """Create schedule with all fields and verify persistence"""
        unique_email = f"persist_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "scope": "user",
            "target_id": TEST_USER_ID,
            "target_name": "Persistence Test User",
            "recipient_email": unique_email,
            "recipient_name": "Persistence Recipient",
            "note": "Testing field persistence"
        }
        
        # Create
        create_resp = requests.post(f"{BASE_URL}/api/account-health/schedules", json=payload)
        assert create_resp.status_code == 200
        schedule_id = create_resp.json()["id"]
        
        # Verify via GET
        list_resp = requests.get(f"{BASE_URL}/api/account-health/schedules")
        schedule = next((s for s in list_resp.json() if s["id"] == schedule_id), None)
        
        assert schedule is not None
        assert schedule["scope"] == "user"
        assert schedule["target_id"] == TEST_USER_ID
        assert schedule["target_name"] == "Persistence Test User"
        assert schedule["recipient_email"] == unique_email
        assert schedule["recipient_name"] == "Persistence Recipient"
        assert schedule["note"] == "Testing field persistence"
        assert schedule["frequency"] == "monthly"
        assert schedule["active"] == True
        assert schedule["last_sent_at"] is None
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/account-health/schedules/{schedule_id}")
        print("Field persistence verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
