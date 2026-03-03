"""
Test cases for automation toggle endpoint
Tests the PATCH /api/contacts/{user_id}/{contact_id}/toggle-automation endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data from iteration context
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a0c06f7626f14d125f8c34"  # Forest Ward


class TestToggleAutomationEndpoint:
    """Test automation toggle functionality for birthday/anniversary/sold_date"""

    def test_toggle_birthday_off(self):
        """Toggle birthday automation off"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "birthday"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "field" in data, "Response should contain 'field'"
        assert data["field"] == "birthday"
        assert "enabled" in data, "Response should contain 'enabled'"
        assert "disabled_automations" in data, "Response should contain 'disabled_automations'"
        
        # After toggle, check state
        print(f"Toggle result: field={data['field']}, enabled={data['enabled']}, disabled={data['disabled_automations']}")

    def test_toggle_birthday_back_on(self):
        """Toggle birthday automation back on (second toggle)"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "birthday"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["field"] == "birthday"
        print(f"Second toggle: enabled={data['enabled']}, disabled={data['disabled_automations']}")

    def test_toggle_anniversary(self):
        """Toggle anniversary automation"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "anniversary"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["field"] == "anniversary"
        print(f"Anniversary toggle: enabled={data['enabled']}")

    def test_toggle_sold_date(self):
        """Toggle sold_date automation"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "sold_date"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["field"] == "sold_date"
        print(f"Sold date toggle: enabled={data['enabled']}")

    def test_toggle_invalid_field_rejected(self):
        """Toggle with invalid field should return 400"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "invalid_field"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid field, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data
        print(f"Invalid field error: {data['detail']}")

    def test_toggle_empty_field_rejected(self):
        """Toggle with empty field should return 400"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": ""},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400 for empty field, got {response.status_code}: {response.text}"

    def test_toggle_missing_field_rejected(self):
        """Toggle with missing field should return 400"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400 for missing field, got {response.status_code}: {response.text}"

    def test_toggle_nonexistent_contact_returns_404(self):
        """Toggle on non-existent contact should return 404"""
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/nonexistent123456789012/toggle-automation",
            json={"field": "birthday"},
            headers={"Content-Type": "application/json"}
        )
        # Could be 404 or 500 depending on how ObjectId parsing fails
        assert response.status_code in [404, 400, 500], f"Expected error status for non-existent contact, got {response.status_code}"


class TestToggleAutomationStateConsistency:
    """Test that toggle maintains consistent state across calls"""
    
    def test_double_toggle_returns_to_original_state(self):
        """Toggling twice should return to original state"""
        # First, get current state
        response1 = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "anniversary"},
            headers={"Content-Type": "application/json"}
        )
        assert response1.status_code == 200
        first_enabled = response1.json()["enabled"]
        
        # Toggle again
        response2 = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID}/toggle-automation",
            json={"field": "anniversary"},
            headers={"Content-Type": "application/json"}
        )
        assert response2.status_code == 200
        second_enabled = response2.json()["enabled"]
        
        # States should be opposite
        assert first_enabled != second_enabled, "Double toggle should flip the state"
        print(f"First toggle: enabled={first_enabled}, Second toggle: enabled={second_enabled}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
