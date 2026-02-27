"""
Tests for contacts delete functionality - single delete and bulk delete
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://backend-startup-3.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "699907444a076891982fab35"

class TestContactsDeleteAPI:
    """Tests for DELETE /api/contacts/{user_id}/{contact_id} and POST /api/contacts/{user_id}/bulk-delete"""
    
    @pytest.fixture
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    def test_create_contact_for_deletion(self, api_client):
        """Create a test contact that will be deleted"""
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        payload = {
            "first_name": "TEST_DeleteSingle",
            "last_name": "Contact",
            "phone": unique_phone,
            "email": f"test.delete.{uuid.uuid4().hex[:6]}@test.com"
        }
        response = api_client.post(f"{BASE_URL}/api/contacts/{TEST_USER_ID}", json=payload)
        assert response.status_code == 200, f"Failed to create contact: {response.text}"
        data = response.json()
        assert "_id" in data
        assert data["first_name"] == "TEST_DeleteSingle"
        return data["_id"]
    
    def test_single_delete_contact(self, api_client):
        """Test DELETE /api/contacts/{user_id}/{contact_id} - single contact deletion"""
        # First create a contact to delete
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        payload = {
            "first_name": "TEST_ToDelete",
            "last_name": "Single",
            "phone": unique_phone
        }
        create_response = api_client.post(f"{BASE_URL}/api/contacts/{TEST_USER_ID}", json=payload)
        assert create_response.status_code == 200
        contact_id = create_response.json()["_id"]
        
        # Delete the contact
        delete_response = api_client.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        delete_data = delete_response.json()
        assert "message" in delete_data
        assert "deleted" in delete_data["message"].lower()
        
        # Verify contact no longer exists
        get_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
        assert get_response.status_code == 404, "Contact should be deleted (404 expected)"
    
    def test_single_delete_nonexistent_contact(self, api_client):
        """Test delete on a contact that doesn't exist returns 404"""
        fake_id = "000000000000000000000000"
        response = api_client.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{fake_id}")
        assert response.status_code == 404
    
    def test_bulk_delete_contacts(self, api_client):
        """Test POST /api/contacts/{user_id}/bulk-delete - multiple contacts deletion"""
        # Create 3 contacts to bulk delete
        contact_ids = []
        for i in range(3):
            unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
            payload = {
                "first_name": f"TEST_BulkDelete{i}",
                "last_name": "Contact",
                "phone": unique_phone
            }
            create_response = api_client.post(f"{BASE_URL}/api/contacts/{TEST_USER_ID}", json=payload)
            assert create_response.status_code == 200
            contact_ids.append(create_response.json()["_id"])
        
        # Bulk delete all 3 contacts
        bulk_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/bulk-delete",
            json={"contact_ids": contact_ids}
        )
        assert bulk_response.status_code == 200, f"Bulk delete failed: {bulk_response.text}"
        bulk_data = bulk_response.json()
        
        # Verify response structure
        assert "deleted" in bulk_data, "Response should contain 'deleted' count"
        assert "requested" in bulk_data, "Response should contain 'requested' count"
        assert bulk_data["deleted"] == 3
        assert bulk_data["requested"] == 3
        
        # Verify all contacts are deleted
        for contact_id in contact_ids:
            get_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
            assert get_response.status_code == 404, f"Contact {contact_id} should be deleted"
    
    def test_bulk_delete_empty_list(self, api_client):
        """Test bulk delete with empty contact_ids list returns 400"""
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/bulk-delete",
            json={"contact_ids": []}
        )
        assert response.status_code == 400, "Empty list should return 400"
    
    def test_bulk_delete_partial_nonexistent(self, api_client):
        """Test bulk delete with some nonexistent IDs still deletes valid ones"""
        # Create 1 contact
        unique_phone = f"+1555{uuid.uuid4().hex[:7]}"
        payload = {
            "first_name": "TEST_PartialDelete",
            "last_name": "Contact",
            "phone": unique_phone
        }
        create_response = api_client.post(f"{BASE_URL}/api/contacts/{TEST_USER_ID}", json=payload)
        assert create_response.status_code == 200
        valid_id = create_response.json()["_id"]
        
        # Mix valid ID with fake ID
        fake_id = "000000000000000000000000"
        bulk_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/bulk-delete",
            json={"contact_ids": [valid_id, fake_id]}
        )
        assert bulk_response.status_code == 200
        bulk_data = bulk_response.json()
        
        # Should report 1 deleted out of 2 requested
        assert bulk_data["requested"] == 2
        assert bulk_data["deleted"] == 1
        
        # Verify the valid contact is deleted
        get_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{valid_id}")
        assert get_response.status_code == 404


class TestContactsAPIEndpointExists:
    """Verify the delete endpoints exist and are accessible"""
    
    def test_delete_endpoint_method_allowed(self):
        """Verify DELETE method is allowed on single contact endpoint"""
        response = requests.options(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/test123")
        # Should not return 405 Method Not Allowed
        assert response.status_code != 405 or "DELETE" in response.headers.get("Allow", "")
    
    def test_bulk_delete_endpoint_accessible(self):
        """Verify POST bulk-delete endpoint returns proper error for empty body"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/bulk-delete",
            json={},
            headers={"Content-Type": "application/json"}
        )
        # Should return 400 (missing contact_ids) or 422 (validation error), not 404
        assert response.status_code in [400, 422], f"Unexpected status: {response.status_code}"
