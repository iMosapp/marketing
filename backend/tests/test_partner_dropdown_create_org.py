"""
Partner Dropdown in Create Organization - Backend API Tests
Tests the new optional partner_id field in POST /api/admin/organizations
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com')

# Test credentials
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"
CALENDAR_SYSTEMS_PARTNER_ID = "69a10678b8e991776ed5df19"
TEST_PARTNER_ID = "69b9dd5cb27dd76126c289cd"


class TestPartnerDropdownBackend:
    """Tests for partner_id field in create organization endpoint"""
    
    def test_create_org_with_partner_id(self):
        """Create org with partner_id - should link org to partner"""
        test_name = f"TEST_PartnerOrg_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/admin/organizations",
            headers={"Content-Type": "application/json", "X-User-ID": SUPER_ADMIN_ID},
            json={
                "name": test_name,
                "admin_email": f"test{int(time.time())}@partner.com",
                "partner_id": CALENDAR_SYSTEMS_PARTNER_ID
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify partner_id is set in response
        assert data.get("partner_id") == CALENDAR_SYSTEMS_PARTNER_ID, \
            f"Expected partner_id {CALENDAR_SYSTEMS_PARTNER_ID}, got {data.get('partner_id')}"
        assert data.get("_id"), "Organization should have _id"
        assert data.get("name") == test_name
        
        print(f"Created org {data['_id']} with partner_id {data['partner_id']}")
        return data["_id"]
    
    def test_create_org_without_partner_id(self):
        """Create org without partner_id - should work normally"""
        test_name = f"TEST_NoPartnerOrg_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/admin/organizations",
            headers={"Content-Type": "application/json", "X-User-ID": SUPER_ADMIN_ID},
            json={
                "name": test_name,
                "admin_email": f"test{int(time.time())}@nopartner.com"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify no partner_id
        assert "partner_id" not in data or data.get("partner_id") is None, \
            f"Expected no partner_id, got {data.get('partner_id')}"
        assert data.get("_id"), "Organization should have _id"
        
        print(f"Created org {data['_id']} without partner_id")
        return data["_id"]
    
    def test_partner_org_ids_updated(self):
        """Verify partner's organization_ids list is updated when org created with partner_id"""
        # Get initial partner data
        response = requests.get(
            f"{BASE_URL}/api/admin/partners/{CALENDAR_SYSTEMS_PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert response.status_code == 200
        initial_orgs = response.json().get("organization_ids", [])
        initial_count = len(initial_orgs)
        
        # Create a new org with partner_id
        test_name = f"TEST_PartnerUpdate_{int(time.time())}"
        create_response = requests.post(
            f"{BASE_URL}/api/admin/organizations",
            headers={"Content-Type": "application/json", "X-User-ID": SUPER_ADMIN_ID},
            json={
                "name": test_name,
                "admin_email": f"test{int(time.time())}@update.com",
                "partner_id": CALENDAR_SYSTEMS_PARTNER_ID
            }
        )
        assert create_response.status_code == 200
        new_org_id = create_response.json().get("_id")
        
        # Check partner's organization_ids was updated
        response = requests.get(
            f"{BASE_URL}/api/admin/partners/{CALENDAR_SYSTEMS_PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert response.status_code == 200
        updated_orgs = response.json().get("organization_ids", [])
        
        assert new_org_id in updated_orgs, \
            f"New org {new_org_id} should be in partner's organization_ids"
        assert len(updated_orgs) > initial_count, \
            "Partner should have more orgs now"
        
        print(f"Partner organization_ids updated: {len(updated_orgs)} orgs (was {initial_count})")
    
    def test_list_partners_endpoint(self):
        """Verify GET /api/admin/partners returns partner list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partners",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 200
        partners = response.json()
        assert isinstance(partners, list)
        assert len(partners) >= 1, "Should have at least one partner"
        
        # Find Calendar Systems
        calendar_systems = next((p for p in partners if p.get("_id") == CALENDAR_SYSTEMS_PARTNER_ID), None)
        assert calendar_systems is not None, "Calendar Systems partner should exist"
        assert calendar_systems.get("name") == "Calendar Systems"
        
        print(f"Found {len(partners)} partners")
    
    def test_organization_create_model_includes_partner_id(self):
        """Verify OrganizationCreate model accepts partner_id field"""
        # This tests that the API accepts partner_id in the request body
        test_name = f"TEST_ModelCheck_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/admin/organizations",
            headers={"Content-Type": "application/json", "X-User-ID": SUPER_ADMIN_ID},
            json={
                "name": test_name,
                "admin_email": f"model{int(time.time())}@test.com",
                "account_type": "organization",
                "city": "Salt Lake City",
                "state": "UT",
                "partner_id": TEST_PARTNER_ID  # Optional partner_id
            }
        )
        
        assert response.status_code == 200, f"Model should accept partner_id: {response.text}"
        data = response.json()
        assert data.get("partner_id") == TEST_PARTNER_ID
        
        print(f"OrganizationCreate model correctly accepts partner_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
