"""
Comprehensive Sold Workflow Tests
Tests the white-label partner sold workflow system:
- PATCH /api/contacts/{user_id}/{contact_id}/tags with 'Sold' tag triggers workflow
- Validation of required fields returns missing_fields list
- POST /api/sold-workflow/revalidate/{contact_id} re-validates 
- GET /api/sold-workflow/contact/{contact_id} returns sold event history
- Idempotency - applying Sold tag twice does not create duplicates
- date_sold is auto-set only if empty when Sold tag applied
- Non-partner users are not affected (sold_workflow is null in response)
"""

import pytest
import requests
import os
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com').rstrip('/')

# MongoDB connection for test setup/cleanup
client = MongoClient("mongodb://localhost:27017")
db = client["imos-admin-test_database"]


class TestSoldWorkflowSetup:
    """Setup: Create test org/store linked to Calendar Systems partner for sold workflow testing"""
    
    @pytest.fixture(scope="class")
    def test_user_id(self):
        """Get super admin user ID"""
        user = db.users.find_one({"email": "forest@imosapp.com"})
        assert user is not None, "Super admin user not found"
        return str(user["_id"])
    
    @pytest.fixture(scope="class")
    def partner_data(self):
        """Get or verify Calendar Systems partner with sold workflow enabled"""
        partner = db.white_label_partners.find_one({"slug": "calendar-systems"})
        if not partner:
            pytest.skip("Calendar Systems partner not found - skipping sold workflow tests")
        return {
            "id": str(partner["_id"]),
            "name": partner.get("name"),
            "sold_workflow_enabled": partner.get("sold_workflow_enabled", False),
            "sold_required_fields": partner.get("sold_required_fields", [])
        }
    
    @pytest.fixture(scope="class")
    def setup_test_org_store(self, test_user_id, partner_data):
        """Create test org and store linked to Calendar Systems, assign user"""
        org_id = ObjectId()
        store_id = ObjectId()
        
        # Save original user store/org for cleanup
        original_user = db.users.find_one({"_id": ObjectId(test_user_id)})
        original_store_id = original_user.get("store_id")
        original_org_id = original_user.get("organization_id") or original_user.get("org_id")
        
        # Create test org linked to partner
        db.organizations.insert_one({
            "_id": org_id,
            "name": "TEST_SoldWorkflow_Org",
            "partner_id": partner_data["id"],
            "created_at": datetime.utcnow(),
        })
        
        # Create test store with external_account_id
        db.stores.insert_one({
            "_id": store_id,
            "name": "TEST_SoldWorkflow_Store",
            "organization_id": str(org_id),
            "partner_id": partner_data["id"],
            "external_account_id": "TEST-CS-ACCT-001",
            "deal_or_stock_mode": "stock_number",
            "created_at": datetime.utcnow(),
        })
        
        # Assign user to this store/org
        db.users.update_one(
            {"_id": ObjectId(test_user_id)},
            {"$set": {"store_id": str(store_id), "organization_id": str(org_id)}}
        )
        
        yield {
            "org_id": str(org_id),
            "store_id": str(store_id),
            "partner_id": partner_data["id"],
        }
        
        # Cleanup
        db.organizations.delete_one({"_id": org_id})
        db.stores.delete_one({"_id": store_id})
        # Restore user's original store/org
        if original_store_id or original_org_id:
            update = {}
            if original_store_id:
                update["store_id"] = original_store_id
            if original_org_id:
                update["organization_id"] = original_org_id
            db.users.update_one({"_id": ObjectId(test_user_id)}, {"$set": update})
        else:
            db.users.update_one(
                {"_id": ObjectId(test_user_id)},
                {"$unset": {"store_id": "", "organization_id": ""}}
            )


class TestSoldWorkflowAPI(TestSoldWorkflowSetup):
    """Test Sold Workflow API endpoints"""
    
    def test_1_apply_sold_tag_triggers_workflow(self, test_user_id, setup_test_org_store, partner_data):
        """PATCH /api/contacts/{user_id}/{contact_id}/tags with 'Sold' tag triggers sold workflow"""
        headers = {"X-User-ID": test_user_id, "Content-Type": "application/json"}
        
        # Create a contact without sold tag - missing required fields
        create_resp = requests.post(f"{BASE_URL}/api/contacts/{test_user_id}", json={
            "first_name": "TEST_SoldWorkflow",
            "last_name": "Contact1",
            "phone": "5551234567",
            "tags": ["New Customer"],
        }, headers=headers)
        
        assert create_resp.status_code in [200, 201], f"Failed to create contact: {create_resp.text}"
        contact = create_resp.json()
        contact_id = contact.get("_id")
        
        try:
            # Apply Sold tag via PATCH
            patch_resp = requests.patch(f"{BASE_URL}/api/contacts/{test_user_id}/{contact_id}/tags", json={
                "tags": ["New Customer", "Sold"],
            }, headers=headers)
            
            assert patch_resp.status_code == 200, f"PATCH tags failed: {patch_resp.text}"
            result = patch_resp.json()
            
            # Verify sold_workflow key is present (partner user)
            assert "sold_workflow" in result, f"sold_workflow key missing in response: {result}"
            sw = result["sold_workflow"]
            
            # Verify workflow status (should be validation_failed due to missing fields)
            assert sw.get("status") in ["validation_failed", "queued", "already_processed"], f"Unexpected status: {sw}"
            
            # If validation failed, check missing_fields
            if sw.get("status") == "validation_failed":
                assert "missing_fields" in sw, "missing_fields key missing in validation_failed response"
                assert len(sw["missing_fields"]) > 0, "Expected missing_fields to be non-empty"
                
            # Verify event_id was created
            assert "event_id" in sw, f"event_id missing in sold_workflow response: {sw}"
            
            print(f"✓ Sold workflow triggered: status={sw.get('status')}, missing_fields={sw.get('missing_fields', [])}")
            
        finally:
            # Cleanup
            db.contacts.delete_one({"_id": ObjectId(contact_id)})
            db.sold_event_logs.delete_many({"contact_id": contact_id})
    
    def test_2_date_sold_auto_set_when_sold_tag_applied(self, test_user_id, setup_test_org_store):
        """date_sold is auto-set only if empty when Sold tag applied"""
        headers = {"X-User-ID": test_user_id, "Content-Type": "application/json"}
        
        # Create contact without date_sold
        create_resp = requests.post(f"{BASE_URL}/api/contacts/{test_user_id}", json={
            "first_name": "TEST_DateSold",
            "last_name": "AutoSet",
            "phone": "5552223333",
            "tags": [],
        }, headers=headers)
        
        assert create_resp.status_code in [200, 201]
        contact = create_resp.json()
        contact_id = contact.get("_id")
        
        try:
            # Verify no date_sold initially
            contact_before = db.contacts.find_one({"_id": ObjectId(contact_id)})
            assert not contact_before.get("date_sold"), "Expected no date_sold initially"
            
            # Apply Sold tag
            requests.patch(f"{BASE_URL}/api/contacts/{test_user_id}/{contact_id}/tags", json={
                "tags": ["Sold"],
            }, headers=headers)
            
            # Check date_sold was auto-set
            contact_after = db.contacts.find_one({"_id": ObjectId(contact_id)})
            assert contact_after.get("date_sold") is not None, "date_sold should be auto-set when Sold tag applied"
            assert contact_after.get("sold_tag_applied_at") is not None, "sold_tag_applied_at should be set"
            
            print(f"✓ date_sold auto-set: {contact_after.get('date_sold')}")
            
        finally:
            db.contacts.delete_one({"_id": ObjectId(contact_id)})
            db.sold_event_logs.delete_many({"contact_id": contact_id})
    
    def test_3_idempotency_no_duplicate_events(self, test_user_id, setup_test_org_store):
        """Applying Sold tag twice does not create duplicate events"""
        headers = {"X-User-ID": test_user_id, "Content-Type": "application/json"}
        
        # Create contact and apply Sold tag
        create_resp = requests.post(f"{BASE_URL}/api/contacts/{test_user_id}", json={
            "first_name": "TEST_Idempotent",
            "last_name": "Check",
            "phone": "5553334444",
            "tags": ["Sold"],  # Apply Sold tag on creation
        }, headers=headers)
        
        contact = create_resp.json()
        contact_id = contact.get("_id")
        
        try:
            # Wait for event to be created
            import time
            time.sleep(0.5)
            
            # Count events after first application
            event_count_1 = db.sold_event_logs.count_documents({"contact_id": contact_id})
            
            # Apply Sold tag again via PATCH
            requests.patch(f"{BASE_URL}/api/contacts/{test_user_id}/{contact_id}/tags", json={
                "tags": ["Sold", "VIP"],  # Same Sold tag plus extra
            }, headers=headers)
            
            # Count events after second application
            event_count_2 = db.sold_event_logs.count_documents({"contact_id": contact_id})
            
            # Should not create duplicate (Sold was already present)
            assert event_count_2 == event_count_1, f"Duplicate event created: before={event_count_1}, after={event_count_2}"
            
            print(f"✓ Idempotency verified: events count={event_count_2}")
            
        finally:
            db.contacts.delete_one({"_id": ObjectId(contact_id)})
            db.sold_event_logs.delete_many({"contact_id": contact_id})
    
    def test_4_revalidate_endpoint(self, test_user_id, setup_test_org_store):
        """POST /api/sold-workflow/revalidate/{contact_id} re-validates after fields are fixed"""
        headers = {"X-User-ID": test_user_id, "Content-Type": "application/json"}
        
        # Create contact missing required fields
        create_resp = requests.post(f"{BASE_URL}/api/contacts/{test_user_id}", json={
            "first_name": "TEST_Revalidate",
            "last_name": "Test",
            "phone": "",  # Missing phone
            "tags": [],
        }, headers=headers)
        
        contact = create_resp.json()
        contact_id = contact.get("_id")
        
        try:
            # Apply Sold tag - should fail validation
            patch_resp = requests.patch(f"{BASE_URL}/api/contacts/{test_user_id}/{contact_id}/tags", json={
                "tags": ["Sold"],
            }, headers=headers)
            
            result = patch_resp.json()
            sw = result.get("sold_workflow", {})
            
            if sw.get("status") == "validation_failed":
                # Fix the missing fields directly in DB
                db.contacts.update_one(
                    {"_id": ObjectId(contact_id)},
                    {"$set": {
                        "phone": "5559998888",
                        "full_size_image_url": "https://example.com/test.jpg",
                        "stock_number": "TEST-STK-001",
                    }}
                )
                
                # Call revalidate endpoint
                revalidate_resp = requests.post(f"{BASE_URL}/api/sold-workflow/revalidate/{contact_id}", headers=headers)
                
                assert revalidate_resp.status_code == 200, f"Revalidate failed: {revalidate_resp.text}"
                revalidate_result = revalidate_resp.json()
                
                # Check if validation now passes or shows remaining missing fields
                assert "status" in revalidate_result, f"status key missing: {revalidate_result}"
                print(f"✓ Revalidate response: {revalidate_result}")
            else:
                print(f"⚠ Validation didn't fail initially, skipping revalidate test")
                
        finally:
            db.contacts.delete_one({"_id": ObjectId(contact_id)})
            db.sold_event_logs.delete_many({"contact_id": contact_id})
    
    def test_5_get_contact_sold_status(self, test_user_id, setup_test_org_store):
        """GET /api/sold-workflow/contact/{contact_id} returns sold event history"""
        headers = {"X-User-ID": test_user_id, "Content-Type": "application/json"}
        
        # Create contact and apply Sold tag
        create_resp = requests.post(f"{BASE_URL}/api/contacts/{test_user_id}", json={
            "first_name": "TEST_StatusCheck",
            "last_name": "History",
            "phone": "5551112222",
            "tags": ["Sold"],
        }, headers=headers)
        
        contact = create_resp.json()
        contact_id = contact.get("_id")
        
        try:
            # Get sold status
            status_resp = requests.get(f"{BASE_URL}/api/sold-workflow/contact/{contact_id}", headers=headers)
            
            assert status_resp.status_code == 200, f"Get status failed: {status_resp.text}"
            status_data = status_resp.json()
            
            # Verify response structure
            assert "events" in status_data, f"events key missing: {status_data}"
            assert "has_partner" in status_data, f"has_partner key missing: {status_data}"
            
            # Verify has_partner is True (user is linked to partner)
            assert status_data.get("has_partner") == True, f"Expected has_partner=True: {status_data}"
            
            # Check events array
            events = status_data.get("events", [])
            assert len(events) >= 1, f"Expected at least 1 event: {events}"
            
            # Verify event structure
            event = events[0]
            assert "validation_status" in event or "_id" in event, f"Event missing expected fields: {event}"
            
            print(f"✓ Contact sold status: has_partner={status_data.get('has_partner')}, events={len(events)}")
            
        finally:
            db.contacts.delete_one({"_id": ObjectId(contact_id)})
            db.sold_event_logs.delete_many({"contact_id": contact_id})


class TestNonPartnerUser:
    """Test that non-partner users are not affected by sold workflow"""
    
    @pytest.fixture
    def non_partner_user_id(self):
        """Get or create a test user NOT linked to any partner"""
        # Clear any partner linkage from the super admin for this test
        user = db.users.find_one({"email": "forest@imosapp.com"})
        user_id = str(user["_id"])
        
        # Save original values
        original = {
            "store_id": user.get("store_id"),
            "organization_id": user.get("organization_id"),
            "org_id": user.get("org_id")
        }
        
        # Unset store/org so user has no partner
        db.users.update_one(
            {"_id": user["_id"]},
            {"$unset": {"store_id": "", "organization_id": "", "org_id": ""}}
        )
        
        yield user_id
        
        # Restore
        restore_fields = {k: v for k, v in original.items() if v}
        if restore_fields:
            db.users.update_one({"_id": user["_id"]}, {"$set": restore_fields})
    
    def test_non_partner_user_no_sold_workflow(self, non_partner_user_id):
        """Non-partner users get NO sold_workflow key in tag PATCH response"""
        headers = {"X-User-ID": non_partner_user_id, "Content-Type": "application/json"}
        
        # Create contact
        create_resp = requests.post(f"{BASE_URL}/api/contacts/{non_partner_user_id}", json={
            "first_name": "TEST_NonPartner",
            "last_name": "User",
            "phone": "5556667777",
            "tags": [],
        }, headers=headers)
        
        contact = create_resp.json()
        contact_id = contact.get("_id")
        
        try:
            # Apply Sold tag
            patch_resp = requests.patch(f"{BASE_URL}/api/contacts/{non_partner_user_id}/{contact_id}/tags", json={
                "tags": ["Sold"],
            }, headers=headers)
            
            assert patch_resp.status_code == 200
            result = patch_resp.json()
            
            # For non-partner users, sold_workflow should NOT be in response
            # (or be None/empty)
            sw = result.get("sold_workflow")
            assert sw is None, f"Non-partner user should NOT get sold_workflow: {result}"
            
            print(f"✓ Non-partner user: sold_workflow is null (expected)")
            
        finally:
            db.contacts.delete_one({"_id": ObjectId(contact_id)})


class TestWhiteLabelPartnerAPI:
    """Test partner admin API endpoints for sold workflow config"""
    
    def test_list_partners_shows_sold_workflow_status(self):
        """GET /api/admin/partners should include sold_workflow_enabled field"""
        resp = requests.get(f"{BASE_URL}/api/admin/partners")
        assert resp.status_code == 200, f"List partners failed: {resp.text}"
        
        partners = resp.json()
        assert isinstance(partners, list), "Expected list of partners"
        
        # Check if any partner has sold_workflow_enabled field
        has_sold_workflow_field = any("sold_workflow_enabled" in p for p in partners)
        assert has_sold_workflow_field, "Partners should have sold_workflow_enabled field"
        
        # Check Calendar Systems specifically
        cs_partner = next((p for p in partners if p.get("slug") == "calendar-systems"), None)
        if cs_partner:
            assert "sold_workflow_enabled" in cs_partner, "Calendar Systems should have sold_workflow_enabled"
            print(f"✓ Calendar Systems sold_workflow_enabled: {cs_partner.get('sold_workflow_enabled')}")
    
    def test_get_partner_details_includes_sold_config(self):
        """GET /api/admin/partners/{id} should include full sold workflow config"""
        partner = db.white_label_partners.find_one({"slug": "calendar-systems"})
        if not partner:
            pytest.skip("Calendar Systems partner not found")
        
        partner_id = str(partner["_id"])
        resp = requests.get(f"{BASE_URL}/api/admin/partners/{partner_id}")
        
        assert resp.status_code == 200, f"Get partner failed: {resp.text}"
        data = resp.json()
        
        # Verify sold workflow fields
        expected_fields = ["sold_workflow_enabled", "sold_required_fields", "event_delivery"]
        for field in expected_fields:
            assert field in data, f"Partner missing {field} field: {data.keys()}"
        
        print(f"✓ Partner sold config: enabled={data.get('sold_workflow_enabled')}, fields={data.get('sold_required_fields')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
