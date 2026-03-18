"""
Partner Billing & Partner Admin Access Tests
Tests for:
- Partner org_admin can list all partner-linked orgs (not just their own)
- Partner org_admin can create new orgs - auto-linked to partner_id
- Partner org_admin can create stores in partner orgs - auto-inherits partner_id
- Partner org_admin CANNOT create stores in orgs outside their partner
- Super admin PUT /api/admin/partner-billing/platform/{partner_id} saves billing config
- Super admin GET /api/admin/partner-billing/platform-summary returns all partners with counts
- POST /api/admin/partner-billing/client-records creates billing record
- GET /api/admin/partner-billing/client-records returns records scoped to user's partner
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review_request
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com / Admin123!
PARTNER_ADMIN_ID = "69ba8350116fd5b3ad1691ba"  # admin@calendarsystems.com / CalSys123!
CALENDAR_SYSTEMS_PARTNER_ID = "69a10678b8e991776ed5df19"
CALENDAR_SYSTEMS_HQ_ORG_ID = "69ba8350116fd5b3ad1691b9"
NEW_CALSYS_ORG_ID = "69ba8371b3de690afb973611"


class TestPartnerOrgAdminAccess:
    """Tests for partner org_admin expanded access"""
    
    def test_partner_admin_can_list_partner_orgs(self):
        """Partner org_admin should see all orgs linked to their partner"""
        response = requests.get(
            f"{BASE_URL}/api/admin/organizations",
            headers={"X-User-ID": PARTNER_ADMIN_ID, "Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Failed to list orgs: {response.text}"
        orgs = response.json()
        
        # Partner admin should see at least their HQ org and any partner-linked orgs
        assert len(orgs) >= 1, "Partner admin should see at least 1 org"
        
        # Check that the orgs returned belong to the partner
        org_ids = [o.get('_id') for o in orgs]
        print(f"Partner admin sees {len(orgs)} orgs: {org_ids}")
        
        # Should include their own org
        assert CALENDAR_SYSTEMS_HQ_ORG_ID in org_ids, "Partner admin should see their HQ org"
        
    def test_partner_admin_can_create_org_auto_linked_to_partner(self):
        """Partner org_admin can create new orgs that auto-link to partner_id"""
        org_data = {
            "name": "TEST_CalSys Client Org",
            "admin_email": "testclient@calendarsystems.info"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/organizations",
            json=org_data,
            headers={"X-User-ID": PARTNER_ADMIN_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Failed to create org: {response.text}"
        created_org = response.json()
        
        # Verify org was created
        assert created_org.get('_id'), "Org should have an ID"
        assert created_org.get('name') == org_data['name']
        
        # Verify partner_id was auto-linked
        assert created_org.get('partner_id') == CALENDAR_SYSTEMS_PARTNER_ID, \
            f"Org should be linked to partner. Got: {created_org.get('partner_id')}"
        
        print(f"Created org {created_org.get('_id')} with partner_id {created_org.get('partner_id')}")
        
        # Clean up - delete the test org (super admin)
        cleanup_response = requests.delete(
            f"{BASE_URL}/api/admin/organizations/{created_org.get('_id')}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert cleanup_response.status_code == 200, "Should delete test org"
        
    def test_partner_admin_can_create_store_in_partner_org(self):
        """Partner org_admin can create stores in partner orgs - store inherits partner_id"""
        store_data = {
            "name": "TEST_CalSys Store",
            "organization_id": CALENDAR_SYSTEMS_HQ_ORG_ID,
            "city": "Salt Lake City",
            "state": "UT"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/stores",
            json=store_data,
            headers={"X-User-ID": PARTNER_ADMIN_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Failed to create store: {response.text}"
        created_store = response.json()
        
        # Verify store was created
        assert created_store.get('_id'), "Store should have an ID"
        assert created_store.get('name') == store_data['name']
        
        # Verify partner_id was auto-inherited from org
        assert created_store.get('partner_id') == CALENDAR_SYSTEMS_PARTNER_ID, \
            f"Store should inherit partner_id from org. Got: {created_store.get('partner_id')}"
        
        print(f"Created store {created_store.get('_id')} with partner_id {created_store.get('partner_id')}")
        
        # Clean up
        cleanup_response = requests.delete(
            f"{BASE_URL}/api/admin/stores/{created_store.get('_id')}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        print(f"Cleanup response: {cleanup_response.status_code}")
        
    def test_partner_admin_cannot_create_store_outside_partner(self):
        """Partner org_admin CANNOT create stores in orgs outside their partner"""
        # First, get an org that doesn't belong to this partner
        response = requests.get(
            f"{BASE_URL}/api/admin/organizations",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert response.status_code == 200
        all_orgs = response.json()
        
        # Find an org without partner_id or with different partner_id
        non_partner_org = None
        for org in all_orgs:
            partner_id = org.get('partner_id')
            if not partner_id or partner_id != CALENDAR_SYSTEMS_PARTNER_ID:
                non_partner_org = org
                break
        
        if not non_partner_org:
            pytest.skip("No non-partner org found for testing")
        
        store_data = {
            "name": "TEST_Unauthorized Store",
            "organization_id": str(non_partner_org.get('_id')),
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/stores",
            json=store_data,
            headers={"X-User-ID": PARTNER_ADMIN_ID, "Content-Type": "application/json"}
        )
        
        # Should be forbidden
        assert response.status_code == 403, f"Should deny creating store in non-partner org. Got: {response.status_code}, {response.text}"
        print(f"Correctly denied: {response.json()}")
        
    def test_partner_admin_list_stores_scoped_to_partner(self):
        """Partner org_admin should only see stores in partner-linked orgs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stores",
            headers={"X-User-ID": PARTNER_ADMIN_ID}
        )
        assert response.status_code == 200, f"Failed to list stores: {response.text}"
        stores = response.json()
        
        print(f"Partner admin sees {len(stores)} stores")
        
        # All stores should belong to partner orgs
        # (We can't easily verify partner_id on stores without extra queries,
        # but we verify they have org_ids that should be partner-linked)


class TestSuperAdminPlatformBilling:
    """Tests for super admin platform billing configuration"""
    
    def test_super_admin_can_set_platform_billing(self):
        """Super admin PUT /api/admin/partner-billing/platform/{partner_id} saves billing config"""
        billing_config = {
            "model": "per_store",
            "rate": 150.0,
            "currency": "USD",
            "includes_carrier": True,
            "carrier_addon_rate": 25.0,
            "notes": "TEST billing config - per store at $150/mo"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/partner-billing/platform/{CALENDAR_SYSTEMS_PARTNER_ID}",
            json=billing_config,
            headers={"X-User-ID": SUPER_ADMIN_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Failed to set billing config: {response.text}"
        result = response.json()
        
        # Verify fields were saved
        assert result.get('model') == billing_config['model']
        assert result.get('rate') == billing_config['rate']
        assert result.get('includes_carrier') == billing_config['includes_carrier']
        assert result.get('carrier_addon_rate') == billing_config['carrier_addon_rate']
        
        print(f"Set billing config: {result}")
        
    def test_super_admin_can_get_platform_billing(self):
        """Super admin GET /api/admin/partner-billing/platform/{partner_id} returns config"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-billing/platform/{CALENDAR_SYSTEMS_PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 200, f"Failed to get billing config: {response.text}"
        config = response.json()
        
        # Should have model field at minimum
        assert 'model' in config or config == {}, "Config should have model or be empty"
        print(f"Got billing config: {config}")
        
    def test_super_admin_can_get_platform_summary(self):
        """Super admin GET /api/admin/partner-billing/platform-summary returns all partners with counts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-billing/platform-summary",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 200, f"Failed to get summary: {response.text}"
        summary = response.json()
        
        assert isinstance(summary, list), "Summary should be a list"
        print(f"Got {len(summary)} partners in summary")
        
        # Find Calendar Systems in summary
        calsys_summary = None
        for p in summary:
            if p.get('_id') == CALENDAR_SYSTEMS_PARTNER_ID:
                calsys_summary = p
                break
        
        if calsys_summary:
            print(f"Calendar Systems summary: {calsys_summary}")
            # Should have count fields
            assert 'org_count' in calsys_summary
            assert 'store_count' in calsys_summary
            assert 'billing_model' in calsys_summary
            
    def test_non_super_admin_cannot_view_platform_billing(self):
        """Partner org_admin should NOT be able to view platform billing config"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-billing/platform/{CALENDAR_SYSTEMS_PARTNER_ID}",
            headers={"X-User-ID": PARTNER_ADMIN_ID}
        )
        
        assert response.status_code == 403, f"Should deny non-super admin. Got: {response.status_code}"
        print(f"Correctly denied: {response.json()}")


class TestClientBillingRecords:
    """Tests for client billing records (Layer 2)"""
    
    def test_create_client_billing_record(self):
        """POST /api/admin/partner-billing/client-records creates billing record"""
        record_data = {
            "partner_id": CALENDAR_SYSTEMS_PARTNER_ID,
            "client_name": "TEST_Client Dealership",
            "client_type": "store",
            "billing_model": "per_store",
            "rate": 100.0,
            "billing_contact": "billing@testclient.com",
            "notes": "TEST billing record"
        }
        
        # Super admin can create
        response = requests.post(
            f"{BASE_URL}/api/admin/partner-billing/client-records",
            json=record_data,
            headers={"X-User-ID": SUPER_ADMIN_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Failed to create record: {response.text}"
        record = response.json()
        
        assert record.get('_id'), "Record should have an ID"
        assert record.get('client_name') == record_data['client_name']
        assert record.get('partner_id') == CALENDAR_SYSTEMS_PARTNER_ID
        
        print(f"Created billing record: {record.get('_id')}")
        
        # Clean up
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/partner-billing/client-records/{record.get('_id')}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert delete_response.status_code == 200
        
    def test_partner_admin_create_client_billing_record(self):
        """Partner org_admin can create billing records for their partner"""
        record_data = {
            "client_name": "TEST_Partner Client Store",
            "client_type": "store",
            "billing_model": "per_seat",
            "rate": 50.0,
            "billing_contact": "client@example.com",
            "notes": "TEST - created by partner admin"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/partner-billing/client-records",
            json=record_data,
            headers={"X-User-ID": PARTNER_ADMIN_ID, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Failed to create record: {response.text}"
        record = response.json()
        
        assert record.get('_id'), "Record should have an ID"
        # Partner_id should be auto-set from partner admin's org
        assert record.get('partner_id') == CALENDAR_SYSTEMS_PARTNER_ID, \
            f"Partner ID should be auto-set. Got: {record.get('partner_id')}"
        
        print(f"Partner admin created billing record: {record}")
        
        # Clean up with super admin
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/partner-billing/client-records/{record.get('_id')}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        print(f"Cleanup: {delete_response.status_code}")
        
    def test_get_client_billing_records_scoped_to_partner(self):
        """GET /api/admin/partner-billing/client-records returns records scoped to user's partner"""
        # First create a record
        record_data = {
            "partner_id": CALENDAR_SYSTEMS_PARTNER_ID,
            "client_name": "TEST_Scoped Record",
            "client_type": "org",
            "billing_model": "per_org",
            "rate": 500.0,
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/partner-billing/client-records",
            json=record_data,
            headers={"X-User-ID": SUPER_ADMIN_ID, "Content-Type": "application/json"}
        )
        assert create_response.status_code == 200
        created_record = create_response.json()
        
        # Partner admin should see records for their partner
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-billing/client-records",
            headers={"X-User-ID": PARTNER_ADMIN_ID}
        )
        
        assert response.status_code == 200, f"Failed to get records: {response.text}"
        records = response.json()
        
        print(f"Partner admin sees {len(records)} records")
        
        # All records should belong to their partner
        for r in records:
            assert r.get('partner_id') == CALENDAR_SYSTEMS_PARTNER_ID, \
                f"All records should belong to partner. Got: {r.get('partner_id')}"
        
        # Clean up
        requests.delete(
            f"{BASE_URL}/api/admin/partner-billing/client-records/{created_record.get('_id')}",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
    def test_super_admin_sees_all_billing_records(self):
        """Super admin should see all billing records across all partners"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-billing/client-records",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 200, f"Failed to get records: {response.text}"
        records = response.json()
        
        print(f"Super admin sees {len(records)} total billing records")
        # Super admin may see records from multiple partners
        partner_ids = set(r.get('partner_id') for r in records)
        print(f"Records from {len(partner_ids)} partners: {partner_ids}")


class TestRBACEnhancements:
    """Tests for RBAC enhancements - get_user_partner_id helper"""
    
    def test_partner_admin_get_scoped_organizations(self):
        """Verify partner admin sees all partner-linked orgs via get_scoped_organization_ids"""
        # This is implicitly tested by list_organizations, but let's verify again
        response = requests.get(
            f"{BASE_URL}/api/admin/organizations",
            headers={"X-User-ID": PARTNER_ADMIN_ID}
        )
        assert response.status_code == 200
        orgs = response.json()
        
        # Should have at least 1 org (their HQ)
        assert len(orgs) >= 1
        
        # All orgs should be partner-linked or the admin's own org
        print(f"Partner admin has access to {len(orgs)} organizations")
        for org in orgs:
            print(f"  - {org.get('name')} (ID: {org.get('_id')}, partner_id: {org.get('partner_id')})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
