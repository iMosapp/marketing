"""
Test for Create Partner iOS Safari Fix
Tests the POST /api/admin/partners endpoint and validates partner creation
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCreatePartnerAPI:
    """Tests for the White Label Partner creation API"""
    
    def test_create_partner_success(self):
        """Test creating a new partner with required fields"""
        unique_id = str(int(time.time()))
        payload = {
            "name": f"TEST_API_Partner_{unique_id}",
            "slug": f"test-api-partner-{unique_id}",
            "primary_color": "#E87722",
            "secondary_color": "#008B8B",
            "accent_color": "#1B2A4A"
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/partners", json=payload)
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data["name"] == payload["name"], "Partner name mismatch"
        assert data["slug"] == payload["slug"], "Partner slug mismatch"
        assert data["primary_color"] == payload["primary_color"], "Primary color mismatch"
        assert "_id" in data, "Missing _id in response"
        assert data["is_active"] == True, "Partner should be active by default"
        
        print(f"✓ Created partner: {data['name']} with ID: {data['_id']}")
        
        # Cleanup - delete the test partner
        partner_id = data["_id"]
        delete_response = requests.delete(f"{BASE_URL}/api/admin/partners/{partner_id}")
        assert delete_response.status_code == 200, "Failed to cleanup test partner"
        print(f"✓ Cleaned up test partner: {partner_id}")
    
    def test_create_partner_with_full_data(self):
        """Test creating a partner with all optional fields"""
        unique_id = str(int(time.time()))
        payload = {
            "name": f"TEST_Full_Partner_{unique_id}",
            "slug": f"test-full-partner-{unique_id}",
            "primary_color": "#FF0000",
            "secondary_color": "#00FF00",
            "accent_color": "#0000FF",
            "company_name": "Test Company Inc.",
            "company_phone": "555-1234",
            "company_email": "test@test.com",
            "company_website": "https://test.com",
            "company_address": "123 Test St",
            "powered_by_text": "Powered by Test",
            "sold_workflow_enabled": True,
            "sold_required_fields": ["customer_name", "phone_number"],
            "external_account_id_required": True,
            "event_delivery": {
                "enabled": True,
                "endpoint_url": "https://webhook.test.com/sold",
                "auth_type": "bearer",
                "auth_value_encrypted": "test-token"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/partners", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["slug"] == payload["slug"]
        assert data["company_name"] == payload["company_name"]
        assert data["sold_workflow_enabled"] == True
        assert data["sold_required_fields"] == ["customer_name", "phone_number"]
        assert data["event_delivery"]["enabled"] == True
        
        print(f"✓ Created full partner: {data['name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/partners/{data['_id']}")
        print(f"✓ Cleaned up test partner")
    
    def test_list_partners(self):
        """Test listing all partners"""
        response = requests.get(f"{BASE_URL}/api/admin/partners")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check that known partners exist
        partner_names = [p["name"] for p in data]
        print(f"✓ Found {len(data)} partners: {partner_names}")
        
        # Verify partner structure
        if len(data) > 0:
            partner = data[0]
            assert "_id" in partner, "Partner should have _id"
            assert "name" in partner, "Partner should have name"
            assert "slug" in partner, "Partner should have slug"
    
    def test_get_partner_by_id(self):
        """Test getting a specific partner by ID"""
        # First, list partners to get an ID
        list_response = requests.get(f"{BASE_URL}/api/admin/partners")
        assert list_response.status_code == 200
        
        partners = list_response.json()
        if len(partners) == 0:
            pytest.skip("No partners available to test")
        
        partner_id = partners[0]["_id"]
        
        # Get the specific partner
        response = requests.get(f"{BASE_URL}/api/admin/partners/{partner_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["_id"] == partner_id, "Partner ID mismatch"
        print(f"✓ Retrieved partner: {data['name']}")
    
    def test_create_partner_and_verify_persistence(self):
        """Test CREATE -> GET pattern to verify data persistence"""
        unique_id = str(int(time.time()))
        payload = {
            "name": f"TEST_Persist_Partner_{unique_id}",
            "slug": f"test-persist-{unique_id}",
            "primary_color": "#AABBCC"
        }
        
        # CREATE
        create_response = requests.post(f"{BASE_URL}/api/admin/partners", json=payload)
        assert create_response.status_code == 200
        
        created_data = create_response.json()
        partner_id = created_data["_id"]
        
        # GET to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/admin/partners/{partner_id}")
        assert get_response.status_code == 200
        
        fetched_data = get_response.json()
        assert fetched_data["name"] == payload["name"], "Name not persisted correctly"
        assert fetched_data["slug"] == payload["slug"], "Slug not persisted correctly"
        assert fetched_data["primary_color"] == payload["primary_color"], "Color not persisted correctly"
        
        print(f"✓ Verified partner persistence: {fetched_data['name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/partners/{partner_id}")
    
    def test_update_partner(self):
        """Test updating a partner"""
        unique_id = str(int(time.time()))
        
        # Create a partner first
        create_payload = {
            "name": f"TEST_Update_Partner_{unique_id}",
            "slug": f"test-update-{unique_id}"
        }
        create_response = requests.post(f"{BASE_URL}/api/admin/partners", json=create_payload)
        assert create_response.status_code == 200
        partner_id = create_response.json()["_id"]
        
        # Update the partner
        update_payload = {
            "name": f"TEST_Updated_Partner_{unique_id}",
            "primary_color": "#112233"
        }
        update_response = requests.put(f"{BASE_URL}/api/admin/partners/{partner_id}", json=update_payload)
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        
        updated_data = update_response.json()
        assert updated_data["name"] == update_payload["name"], "Name not updated"
        assert updated_data["primary_color"] == update_payload["primary_color"], "Color not updated"
        
        print(f"✓ Updated partner: {updated_data['name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/partners/{partner_id}")
    
    def test_delete_partner(self):
        """Test deleting a partner"""
        unique_id = str(int(time.time()))
        
        # Create a partner first
        create_payload = {
            "name": f"TEST_Delete_Partner_{unique_id}",
            "slug": f"test-delete-{unique_id}"
        }
        create_response = requests.post(f"{BASE_URL}/api/admin/partners", json=create_payload)
        assert create_response.status_code == 200
        partner_id = create_response.json()["_id"]
        
        # Delete the partner
        delete_response = requests.delete(f"{BASE_URL}/api/admin/partners/{partner_id}")
        
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        # Verify deletion - GET should return 404
        get_response = requests.get(f"{BASE_URL}/api/admin/partners/{partner_id}")
        assert get_response.status_code == 404, "Partner should not exist after deletion"
        
        print(f"✓ Successfully deleted partner: {partner_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
