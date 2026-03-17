"""
Test Partner Orgs Page Fix - Tests for the new partner-orgs.tsx page functionality

Tests:
1. White Label Partners list endpoint returns Calendar Systems and Test Partner
2. GET /api/admin/partners/{id}/orgs returns linked orgs for a partner
3. POST /api/admin/partners/{id}/assign-org/{org_id} links an org to a partner
4. POST /api/admin/partners/{id}/unassign-org/{org_id} unlinks an org from a partner
5. POST /api/admin/stores with partner_id creates store with partner association
6. GET /api/admin/stores?organization_id={id} returns stores under an org
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com')

# Test data from the review request
TEST_PARTNER_ID = "69b9dd5cb27dd76126c289cd"
CALENDAR_SYSTEMS_PARTNER_ID = "69a10678b8e991776ed5df19"
TEST_ORG_ID = "69a907033b77512d1d8d8a08"
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"


class TestPartnersList:
    """Tests for /api/admin/partners endpoint"""
    
    def test_list_partners_returns_data(self):
        """Test that partners list returns Calendar Systems and Test Partner"""
        response = requests.get(f"{BASE_URL}/api/admin/partners")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        partners = response.json()
        assert isinstance(partners, list), "Response should be a list"
        assert len(partners) >= 2, f"Expected at least 2 partners, got {len(partners)}"
        
        # Check for required partners
        partner_names = [p.get('name') for p in partners]
        assert "Calendar Systems" in partner_names, "Calendar Systems partner not found"
        assert "Test Partner" in partner_names, "Test Partner not found"
        print(f"PASS: Found {len(partners)} partners including Calendar Systems and Test Partner")
    
    def test_partner_has_required_fields(self):
        """Test that partner objects have required fields for the UI"""
        response = requests.get(f"{BASE_URL}/api/admin/partners")
        assert response.status_code == 200
        
        partners = response.json()
        for partner in partners:
            assert "_id" in partner, f"Partner missing _id: {partner}"
            assert "name" in partner, f"Partner missing name: {partner}"
            assert "slug" in partner, f"Partner missing slug: {partner}"
        print("PASS: All partners have required fields (_id, name, slug)")


class TestPartnerOrgs:
    """Tests for /api/admin/partners/{id}/orgs endpoint"""
    
    def test_get_partner_orgs_for_test_partner(self):
        """Test that Test Partner has linked organization"""
        response = requests.get(f"{BASE_URL}/api/admin/partners/{TEST_PARTNER_ID}/orgs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        orgs = response.json()
        assert isinstance(orgs, list), "Response should be a list"
        assert len(orgs) >= 1, f"Expected at least 1 org linked, got {len(orgs)}"
        
        # Check that the test org is linked
        org_ids = [o.get('_id') for o in orgs]
        assert TEST_ORG_ID in org_ids, f"Test org {TEST_ORG_ID} not found in linked orgs: {org_ids}"
        print(f"PASS: Test Partner has {len(orgs)} linked org(s), including {TEST_ORG_ID}")
    
    def test_get_partner_orgs_returns_org_fields(self):
        """Test that org objects have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/partners/{TEST_PARTNER_ID}/orgs")
        assert response.status_code == 200
        
        orgs = response.json()
        for org in orgs:
            assert "_id" in org, f"Org missing _id: {org}"
            assert "name" in org, f"Org missing name: {org}"
        print("PASS: All linked orgs have required fields (_id, name)")
    
    def test_get_partner_orgs_for_calendar_systems(self):
        """Test Calendar Systems partner orgs (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/admin/partners/{CALENDAR_SYSTEMS_PARTNER_ID}/orgs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        orgs = response.json()
        assert isinstance(orgs, list), "Response should be a list"
        print(f"PASS: Calendar Systems has {len(orgs)} linked org(s)")


class TestStoreCreation:
    """Tests for POST /api/admin/stores with partner_id"""
    
    def test_create_store_with_partner_id(self):
        """Test creating a store with partner_id field"""
        unique_name = f"TEST_Store_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        payload = {
            "name": unique_name,
            "organization_id": TEST_ORG_ID,
            "partner_id": TEST_PARTNER_ID,
            "city": "Test City",
            "state": "UT"
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/stores", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        store = response.json()
        assert store.get("name") == unique_name, f"Store name mismatch: {store.get('name')}"
        assert store.get("organization_id") == TEST_ORG_ID, f"Org ID mismatch: {store.get('organization_id')}"
        assert store.get("partner_id") == TEST_PARTNER_ID, f"Partner ID mismatch: {store.get('partner_id')}"
        assert "_id" in store, "Store should have _id"
        
        print(f"PASS: Created store {unique_name} with partner_id={TEST_PARTNER_ID}")
        
        # Cleanup - delete the store
        store_id = store.get("_id")
        if store_id:
            cleanup_response = requests.delete(f"{BASE_URL}/api/admin/stores/{store_id}")
            print(f"Cleanup: Deleted test store {store_id}")
    
    def test_create_store_without_partner_id(self):
        """Test creating a store without partner_id still works"""
        unique_name = f"TEST_Store_NoPartner_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        payload = {
            "name": unique_name,
            "organization_id": TEST_ORG_ID,
            "city": "Another City",
            "state": "CA"
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/stores", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        store = response.json()
        assert store.get("name") == unique_name
        # partner_id should be None or not present
        assert store.get("partner_id") is None, f"Expected partner_id to be None, got {store.get('partner_id')}"
        
        print(f"PASS: Created store without partner_id")
        
        # Cleanup
        store_id = store.get("_id")
        if store_id:
            requests.delete(f"{BASE_URL}/api/admin/stores/{store_id}")


class TestStoresByOrganization:
    """Tests for GET /api/admin/stores?organization_id={id}"""
    
    def test_get_stores_by_organization(self):
        """Test getting stores for a specific organization"""
        response = requests.get(f"{BASE_URL}/api/admin/stores", params={"organization_id": TEST_ORG_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        stores = response.json()
        assert isinstance(stores, list), "Response should be a list"
        assert len(stores) >= 1, f"Expected at least 1 store, got {len(stores)}"
        
        # Verify all stores belong to the org
        for store in stores:
            assert store.get("organization_id") == TEST_ORG_ID, f"Store has wrong org_id: {store}"
        
        print(f"PASS: Found {len(stores)} stores for organization {TEST_ORG_ID}")


class TestAssignUnassignOrg:
    """Tests for assign and unassign org endpoints"""
    
    def test_assign_org_to_partner(self):
        """Test assigning an org to a partner (if org not already assigned)"""
        # First check current linked orgs
        response = requests.get(f"{BASE_URL}/api/admin/partners/{TEST_PARTNER_ID}/orgs")
        current_orgs = response.json()
        current_org_ids = [o.get('_id') for o in current_orgs]
        
        # If test org is already linked, this test still validates the endpoint works
        response = requests.post(f"{BASE_URL}/api/admin/partners/{TEST_PARTNER_ID}/assign-org/{TEST_ORG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get("status") == "assigned", f"Expected status 'assigned', got {result}"
        print("PASS: assign-org endpoint works correctly")
    
    def test_assign_org_invalid_partner(self):
        """Test assigning org to non-existent partner returns 404"""
        fake_partner_id = "000000000000000000000000"
        response = requests.post(f"{BASE_URL}/api/admin/partners/{fake_partner_id}/assign-org/{TEST_ORG_ID}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: assign-org returns 404 for invalid partner")


class TestPartnerDetail:
    """Tests for GET /api/admin/partners/{id}"""
    
    def test_get_partner_detail(self):
        """Test getting full partner details"""
        response = requests.get(f"{BASE_URL}/api/admin/partners/{TEST_PARTNER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        partner = response.json()
        assert partner.get("_id") == TEST_PARTNER_ID
        assert partner.get("name") == "Test Partner"
        assert partner.get("slug") == "test-partner"
        print(f"PASS: Got partner detail for Test Partner")
    
    def test_get_partner_detail_invalid_id(self):
        """Test getting partner with invalid ID returns 404"""
        fake_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/admin/partners/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Get partner returns 404 for invalid ID")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
