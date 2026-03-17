"""
Tests for Personal Intelligence (personal_details) endpoints
Tests GET and PATCH /api/contacts/{user_id}/{contact_id}/personal-details
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com')
USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
CONTACT_ID = "69a8abe36a8712d026633756"  # Test contact with personal details


class TestPersonalDetailsGet:
    """Test GET /api/contacts/{user_id}/{contact_id}/personal-details"""
    
    def test_get_personal_details_success(self):
        """Test getting personal details for a contact with existing data"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "personal_details" in data, "Response should contain personal_details"
        assert "has_details" in data, "Response should contain has_details"
        assert "vehicle" in data, "Response should contain vehicle"
        
        # Verify data structure
        details = data["personal_details"]
        assert isinstance(details, dict), "personal_details should be a dict"
        
        # Verify has_details is True when data exists
        if details:
            assert data["has_details"] == True, "has_details should be True when details exist"
        
        print(f"GET personal-details response: {data}")
    
    def test_get_personal_details_nonexistent_contact(self):
        """Test getting personal details for non-existent contact returns 404"""
        fake_contact_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{fake_contact_id}/personal-details")
        
        assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"


class TestPersonalDetailsPatch:
    """Test PATCH /api/contacts/{user_id}/{contact_id}/personal-details"""
    
    def test_patch_personal_details_success(self):
        """Test updating personal details successfully"""
        payload = {
            "personal_details": {
                "spouse_name": "Test Spouse API",
                "pets": "Test Pet",
                "interests": ["Testing", "Development"]
            }
        }
        
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "personal_details" in data, "Response should contain personal_details"
        
        details = data["personal_details"]
        assert details.get("spouse_name") == "Test Spouse API", "Spouse name should be updated"
        assert details.get("pets") == "Test Pet", "Pets should be updated"
        assert details.get("interests") == ["Testing", "Development"], "Interests should be updated"
        
        print(f"PATCH personal-details response: {data}")
    
    def test_patch_personal_details_merges_with_existing(self):
        """Test that PATCH merges new data with existing data"""
        # First, set some initial data
        initial_payload = {
            "personal_details": {
                "spouse_name": "Initial Spouse",
                "occupation": "Initial Job"
            }
        }
        requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details",
            json=initial_payload
        )
        
        # Now update only spouse_name
        update_payload = {
            "personal_details": {
                "spouse_name": "Updated Spouse"
            }
        }
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details",
            json=update_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        details = data["personal_details"]
        
        # Spouse should be updated
        assert details.get("spouse_name") == "Updated Spouse", "Spouse name should be updated"
        # Occupation should still exist from initial data
        assert details.get("occupation") == "Initial Job", "Occupation should be preserved"
        
        print(f"Merge test response: {data}")
    
    def test_patch_personal_details_filters_empty_values(self):
        """Test that PATCH filters out empty string and null values"""
        payload = {
            "personal_details": {
                "spouse_name": "Valid Name",
                "spouse_details": "",  # Empty string - should be filtered
                "pets": None,  # Null - should be filtered (if sent)
                "neighborhood": "Valid Area"
            }
        }
        
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        details = data["personal_details"]
        
        assert details.get("spouse_name") == "Valid Name"
        assert details.get("neighborhood") == "Valid Area"
        # Empty values should not be in the response or should be filtered
        assert "spouse_details" not in details or details.get("spouse_details") == ""
        
        print(f"Empty values filter test response: {data}")
    
    def test_patch_personal_details_nonexistent_contact(self):
        """Test PATCH on non-existent contact returns 404"""
        fake_contact_id = "000000000000000000000000"
        payload = {
            "personal_details": {"spouse_name": "Test"}
        }
        
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{fake_contact_id}/personal-details",
            json=payload
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"
    
    def test_patch_personal_details_verify_persistence(self):
        """Test that PATCH changes persist by doing GET after PATCH"""
        # Update data
        unique_value = f"Persistence Test Spouse"
        payload = {
            "personal_details": {
                "spouse_name": unique_value,
                "pets": "Persistence Test Pet"
            }
        }
        
        patch_response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details",
            json=payload
        )
        assert patch_response.status_code == 200
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details")
        assert get_response.status_code == 200
        
        data = get_response.json()
        details = data["personal_details"]
        
        assert details.get("spouse_name") == unique_value, "Spouse name should persist"
        assert details.get("pets") == "Persistence Test Pet", "Pets should persist"
        
        print(f"Persistence test - PATCH then GET verified: {details}")


class TestPersonalDetailsAllFields:
    """Test all personal intelligence fields"""
    
    def test_all_personal_details_fields(self):
        """Test that all personal details fields can be saved and retrieved"""
        payload = {
            "personal_details": {
                "spouse_name": "Test Spouse Full",
                "spouse_details": "Works at company",
                "kids": [
                    {"name": "Child 1", "details": "Age 5"},
                    {"name": "Child 2", "details": "Age 3"}
                ],
                "interests": ["Golf", "Reading", "Travel"],
                "occupation": "Software Engineer",
                "employer": "Tech Corp",
                "vehicle_purchased": "2024 Tesla Model 3",
                "vehicle_color": "Red",
                "vehicle_details": "Long range, autopilot",
                "trade_in": "2018 Honda Accord",
                "purchase_context": "Upgraded for family safety",
                "pets": "Golden Retriever named Max",
                "neighborhood": "Westside",
                "referral_potential": "High - knows many people",
                "personal_notes": "Prefers morning calls",
                "communication_preference": "Text preferred"
            }
        }
        
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/personal-details",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        details = data["personal_details"]
        
        # Verify all fields
        assert details.get("spouse_name") == "Test Spouse Full"
        assert details.get("spouse_details") == "Works at company"
        assert len(details.get("kids", [])) == 2
        assert details.get("interests") == ["Golf", "Reading", "Travel"]
        assert details.get("occupation") == "Software Engineer"
        assert details.get("employer") == "Tech Corp"
        assert details.get("vehicle_purchased") == "2024 Tesla Model 3"
        assert details.get("vehicle_color") == "Red"
        assert details.get("vehicle_details") == "Long range, autopilot"
        assert details.get("trade_in") == "2018 Honda Accord"
        assert details.get("purchase_context") == "Upgraded for family safety"
        assert details.get("pets") == "Golden Retriever named Max"
        assert details.get("neighborhood") == "Westside"
        assert details.get("referral_potential") == "High - knows many people"
        assert details.get("personal_notes") == "Prefers morning calls"
        assert details.get("communication_preference") == "Text preferred"
        
        print("All fields test passed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
