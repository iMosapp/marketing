"""
Partner Monthly Invoice System Tests
Tests for waivers, store rates, invoice generation, PDF, and status management.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
SUPER_ADMIN_USER_ID = "69a0b7095fddcede09591667"
PARTNER_ID = "69a10678b8e991776ed5df19"  # Calendar Systems
STORE_ID_1 = "69a0b7095fddcede09591668"  # i'M On social
STORE_ID_2 = "69ba837cb3de690afb973612"  # CalSys Denver Store

# Use a future period to avoid conflicts with existing invoices
TEST_PERIOD = "2026-05"


class TestPartnerInvoiceWaivers:
    """Tests for billing waiver CRUD operations"""
    
    created_waiver_id = None
    
    def test_list_waivers_requires_auth(self):
        """GET /api/admin/partner-invoices/waivers/{partner_id} - requires X-User-ID header"""
        response = requests.get(f"{BASE_URL}/api/admin/partner-invoices/waivers/{PARTNER_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: List waivers requires authentication")
    
    def test_list_waivers_success(self):
        """GET /api/admin/partner-invoices/waivers/{partner_id} - returns waiver list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/waivers/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: List waivers returned {len(data)} waivers")
        
        # Check waiver structure if any exist
        if data:
            waiver = data[0]
            assert "_id" in waiver, "Waiver should have _id"
            assert "partner_id" in waiver, "Waiver should have partner_id"
            assert "store_id" in waiver, "Waiver should have store_id"
            assert "expired" in waiver, "Waiver should have expired flag"
            print(f"PASS: Waiver structure validated - store: {waiver.get('store_name')}, expired: {waiver.get('expired')}")
    
    def test_create_waiver_success(self):
        """POST /api/admin/partner-invoices/waivers - creates a new waiver"""
        payload = {
            "partner_id": PARTNER_ID,
            "store_id": STORE_ID_2,  # CalSys Denver Store
            "store_name": "CalSys Denver Store",
            "waived_until": "2026-12-31T23:59:59",
            "reason": "TEST_waiver - promotional period"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/partner-invoices/waivers",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "_id" in data, "Response should have _id"
        assert data["partner_id"] == PARTNER_ID, "Partner ID should match"
        assert data["store_id"] == STORE_ID_2, "Store ID should match"
        assert data["reason"] == "TEST_waiver - promotional period", "Reason should match"
        
        TestPartnerInvoiceWaivers.created_waiver_id = data["_id"]
        print(f"PASS: Created waiver {data['_id']} for store {data.get('store_name')}")
    
    def test_create_waiver_indefinite(self):
        """POST /api/admin/partner-invoices/waivers - creates waiver without expiry (indefinite)"""
        payload = {
            "partner_id": PARTNER_ID,
            "store_id": STORE_ID_2,
            "store_name": "CalSys Denver Store",
            "waived_until": None,  # Indefinite
            "reason": "TEST_indefinite_waiver"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/partner-invoices/waivers",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("waived_until") is None, "Indefinite waiver should have null waived_until"
        print(f"PASS: Created indefinite waiver {data['_id']}")
        
        # Clean up
        if data.get("_id"):
            requests.delete(
                f"{BASE_URL}/api/admin/partner-invoices/waivers/{data['_id']}",
                headers={"X-User-ID": SUPER_ADMIN_USER_ID}
            )
    
    def test_delete_waiver_success(self):
        """DELETE /api/admin/partner-invoices/waivers/{waiver_id} - removes waiver"""
        if not TestPartnerInvoiceWaivers.created_waiver_id:
            pytest.skip("No waiver created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/admin/partner-invoices/waivers/{TestPartnerInvoiceWaivers.created_waiver_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        print(f"PASS: Deleted waiver {TestPartnerInvoiceWaivers.created_waiver_id}")
        
        # Verify deletion
        list_response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/waivers/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        waivers = list_response.json()
        waiver_ids = [w["_id"] for w in waivers]
        assert TestPartnerInvoiceWaivers.created_waiver_id not in waiver_ids, "Deleted waiver should not appear in list"
        print("PASS: Verified waiver no longer in list")
    
    def test_delete_waiver_not_found(self):
        """DELETE /api/admin/partner-invoices/waivers/{waiver_id} - returns 404 for invalid ID"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/partner-invoices/waivers/000000000000000000000000",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Delete non-existent waiver returns 404")


class TestPartnerInvoiceStoreRates:
    """Tests for per-store billing rate management"""
    
    def test_get_store_rates_requires_auth(self):
        """GET /api/admin/partner-invoices/store-rates/{partner_id} - requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/partner-invoices/store-rates/{PARTNER_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Get store rates requires authentication")
    
    def test_get_store_rates_success(self):
        """GET /api/admin/partner-invoices/store-rates/{partner_id} - returns store list with rates"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/store-rates/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: Get store rates returned {len(data)} stores")
        
        # Check store structure
        if data:
            store = data[0]
            assert "_id" in store, "Store should have _id"
            assert "name" in store, "Store should have name"
            # billing_rate and billing_package may be null
            print(f"PASS: Store structure validated - {store.get('name')}, rate: {store.get('billing_rate')}")
    
    def test_set_store_rate_success(self):
        """PUT /api/admin/partner-invoices/store-rate/{store_id} - sets per-store rate override"""
        payload = {
            "billing_rate": 175.00,
            "billing_package": "TEST_Gold"
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/partner-invoices/store-rate/{STORE_ID_2}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        print(f"PASS: Set store rate to $175.00 with package TEST_Gold")
        
        # Verify the rate was set
        rates_response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/store-rates/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        stores = rates_response.json()
        store = next((s for s in stores if s["_id"] == STORE_ID_2), None)
        if store:
            assert store.get("billing_rate") == 175.00, f"Rate should be 175.00, got {store.get('billing_rate')}"
            assert store.get("billing_package") == "TEST_Gold", f"Package should be TEST_Gold, got {store.get('billing_package')}"
            print("PASS: Verified store rate was persisted")
    
    def test_set_store_rate_clear_override(self):
        """PUT /api/admin/partner-invoices/store-rate/{store_id} - clears rate override with null"""
        payload = {
            "billing_rate": None,
            "billing_package": ""
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/partner-invoices/store-rate/{STORE_ID_2}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Cleared store rate override")
    
    def test_set_store_rate_no_fields(self):
        """PUT /api/admin/partner-invoices/store-rate/{store_id} - returns 400 with empty body"""
        response = requests.put(
            f"{BASE_URL}/api/admin/partner-invoices/store-rate/{STORE_ID_2}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Empty update body returns 400")
    
    def test_set_store_rate_not_found(self):
        """PUT /api/admin/partner-invoices/store-rate/{store_id} - returns 404 for invalid store"""
        payload = {"billing_rate": 100}
        response = requests.put(
            f"{BASE_URL}/api/admin/partner-invoices/store-rate/000000000000000000000000",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Set rate for non-existent store returns 404")


class TestPartnerInvoiceGeneration:
    """Tests for invoice generation, listing, and PDF"""
    
    generated_invoice_id = None
    
    def test_generate_invoice_requires_auth(self):
        """POST /api/admin/partner-invoices/generate/{partner_id} - requires auth"""
        response = requests.post(f"{BASE_URL}/api/admin/partner-invoices/generate/{PARTNER_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Generate invoice requires authentication")
    
    def test_generate_invoice_success(self):
        """POST /api/admin/partner-invoices/generate/{partner_id} - generates invoice with line items"""
        payload = {"period": TEST_PERIOD}
        response = requests.post(
            f"{BASE_URL}/api/admin/partner-invoices/generate/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate invoice structure
        assert "_id" in data, "Invoice should have _id"
        assert "invoice_number" in data, "Invoice should have invoice_number"
        assert "period" in data, "Invoice should have period"
        assert data["period"] == TEST_PERIOD, f"Period should be {TEST_PERIOD}"
        assert "line_items" in data, "Invoice should have line_items"
        assert isinstance(data["line_items"], list), "line_items should be a list"
        assert "total" in data, "Invoice should have total"
        assert "status" in data, "Invoice should have status"
        assert data["status"] == "draft", "New invoice should be draft status"
        assert "pdf_path" in data, "Invoice should have pdf_path"
        
        TestPartnerInvoiceGeneration.generated_invoice_id = data["_id"]
        print(f"PASS: Generated invoice {data['invoice_number']} for period {TEST_PERIOD}")
        print(f"  - Total: ${data['total']}")
        print(f"  - Line items: {len(data['line_items'])}")
        print(f"  - PDF path: {data.get('pdf_path')}")
        
        # Check line item structure
        if data["line_items"]:
            item = data["line_items"][0]
            assert "store_id" in item, "Line item should have store_id"
            assert "store_name" in item, "Line item should have store_name"
            assert "rate" in item, "Line item should have rate"
            assert "amount" in item, "Line item should have amount"
            assert "waived" in item, "Line item should have waived flag"
            print(f"  - Sample line item: {item['store_name']}, rate=${item['rate']}, amount=${item['amount']}, waived={item['waived']}")
    
    def test_generate_invoice_duplicate_prevention(self):
        """POST /api/admin/partner-invoices/generate/{partner_id} - returns 409 for duplicate period"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to test duplicate")
        
        payload = {"period": TEST_PERIOD}
        response = requests.post(
            f"{BASE_URL}/api/admin/partner-invoices/generate/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 409, f"Expected 409 for duplicate, got {response.status_code}: {response.text}"
        print(f"PASS: Duplicate invoice for {TEST_PERIOD} correctly returns 409")
    
    def test_list_invoices_success(self):
        """GET /api/admin/partner-invoices/list/{partner_id} - returns invoice list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/list/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: List invoices returned {len(data)} invoices")
        
        # Check invoice list structure
        if data:
            inv = data[0]
            assert "_id" in inv, "Invoice should have _id"
            assert "invoice_number" in inv, "Invoice should have invoice_number"
            assert "period" in inv, "Invoice should have period"
            assert "total" in inv, "Invoice should have total"
            assert "status" in inv, "Invoice should have status"
            assert "line_item_count" in inv, "Invoice should have line_item_count"
            print(f"  - Latest: {inv['invoice_number']}, period={inv['period']}, total=${inv['total']}, status={inv['status']}")
    
    def test_get_invoice_detail_success(self):
        """GET /api/admin/partner-invoices/detail/{invoice_id} - returns full invoice"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to get detail")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/detail/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["_id"] == TestPartnerInvoiceGeneration.generated_invoice_id, "Invoice ID should match"
        assert "line_items" in data, "Detail should include line_items"
        assert "partner_name" in data, "Detail should include partner_name"
        assert "partner_email" in data, "Detail should include partner_email"
        assert "due_date" in data, "Detail should include due_date"
        print(f"PASS: Got invoice detail for {data['invoice_number']}")
        print(f"  - Partner: {data.get('partner_name')}")
        print(f"  - Due date: {data.get('due_date')}")
    
    def test_get_invoice_detail_not_found(self):
        """GET /api/admin/partner-invoices/detail/{invoice_id} - returns 404 for invalid ID"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/detail/000000000000000000000000",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Get detail for non-existent invoice returns 404")
    
    def test_download_pdf_success(self):
        """GET /api/admin/partner-invoices/pdf/{invoice_id} - returns PDF file"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to download PDF")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/pdf/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF should have content"
        print(f"PASS: Downloaded PDF ({len(response.content)} bytes)")
    
    def test_download_pdf_not_found(self):
        """GET /api/admin/partner-invoices/pdf/{invoice_id} - returns 404 for invalid ID"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/pdf/000000000000000000000000",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Download PDF for non-existent invoice returns 404")


class TestPartnerInvoiceStatus:
    """Tests for invoice status management"""
    
    def test_update_status_to_sent(self):
        """PATCH /api/admin/partner-invoices/status/{invoice_id} - marks invoice as sent"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to update status")
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={"status": "sent"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert data.get("status") == "sent", "Status should be sent"
        print("PASS: Updated invoice status to 'sent'")
        
        # Verify status was updated
        detail_response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/detail/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        detail = detail_response.json()
        assert detail.get("status") == "sent", f"Status should be sent, got {detail.get('status')}"
        assert detail.get("sent_at") is not None, "sent_at should be set"
        print("PASS: Verified status persisted as 'sent' with sent_at timestamp")
    
    def test_update_status_to_paid(self):
        """PATCH /api/admin/partner-invoices/status/{invoice_id} - marks invoice as paid"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to update status")
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={"status": "paid"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "paid", "Status should be paid"
        print("PASS: Updated invoice status to 'paid'")
        
        # Verify paid_at was set
        detail_response = requests.get(
            f"{BASE_URL}/api/admin/partner-invoices/detail/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        detail = detail_response.json()
        assert detail.get("paid_at") is not None, "paid_at should be set"
        print("PASS: Verified paid_at timestamp was set")
    
    def test_update_status_to_overdue(self):
        """PATCH /api/admin/partner-invoices/status/{invoice_id} - marks invoice as overdue"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to update status")
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={"status": "overdue"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Updated invoice status to 'overdue'")
    
    def test_update_status_to_cancelled(self):
        """PATCH /api/admin/partner-invoices/status/{invoice_id} - marks invoice as cancelled"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to update status")
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={"status": "cancelled"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Updated invoice status to 'cancelled'")
    
    def test_update_status_invalid(self):
        """PATCH /api/admin/partner-invoices/status/{invoice_id} - returns 400 for invalid status"""
        if not TestPartnerInvoiceGeneration.generated_invoice_id:
            pytest.skip("No invoice generated to update status")
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceGeneration.generated_invoice_id}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={"status": "invalid_status"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Invalid status returns 400")
    
    def test_update_status_not_found(self):
        """PATCH /api/admin/partner-invoices/status/{invoice_id} - returns 404 for invalid ID"""
        response = requests.patch(
            f"{BASE_URL}/api/admin/partner-invoices/status/000000000000000000000000",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json={"status": "paid"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Update status for non-existent invoice returns 404")


class TestPartnerInvoiceWaiverLogic:
    """Tests for waiver logic in invoice generation - waived stores show $0"""
    
    test_waiver_id = None
    test_invoice_id = None
    
    def test_waiver_zeroes_line_item(self):
        """Verify waived store shows $0 amount but still appears in invoice"""
        # First, create a waiver for STORE_ID_1
        waiver_payload = {
            "partner_id": PARTNER_ID,
            "store_id": STORE_ID_1,
            "store_name": "i'M On social",
            "waived_until": "2027-12-31T23:59:59",
            "reason": "TEST_waiver_logic_test"
        }
        waiver_response = requests.post(
            f"{BASE_URL}/api/admin/partner-invoices/waivers",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=waiver_payload
        )
        assert waiver_response.status_code == 200, f"Failed to create waiver: {waiver_response.text}"
        TestPartnerInvoiceWaiverLogic.test_waiver_id = waiver_response.json()["_id"]
        print(f"Created test waiver: {TestPartnerInvoiceWaiverLogic.test_waiver_id}")
        
        # Generate invoice for a different period
        test_period = "2026-06"
        invoice_payload = {"period": test_period}
        invoice_response = requests.post(
            f"{BASE_URL}/api/admin/partner-invoices/generate/{PARTNER_ID}",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
            json=invoice_payload
        )
        
        if invoice_response.status_code == 409:
            # Invoice already exists, get it from list
            list_response = requests.get(
                f"{BASE_URL}/api/admin/partner-invoices/list/{PARTNER_ID}",
                headers={"X-User-ID": SUPER_ADMIN_USER_ID}
            )
            invoices = list_response.json()
            existing = next((i for i in invoices if i["period"] == test_period), None)
            if existing:
                TestPartnerInvoiceWaiverLogic.test_invoice_id = existing["_id"]
                # Get full detail
                detail_response = requests.get(
                    f"{BASE_URL}/api/admin/partner-invoices/detail/{existing['_id']}",
                    headers={"X-User-ID": SUPER_ADMIN_USER_ID}
                )
                invoice = detail_response.json()
            else:
                pytest.skip("Could not find or create invoice for waiver test")
        else:
            assert invoice_response.status_code == 200, f"Failed to generate invoice: {invoice_response.text}"
            invoice = invoice_response.json()
            TestPartnerInvoiceWaiverLogic.test_invoice_id = invoice["_id"]
        
        # Find the waived store in line items
        line_items = invoice.get("line_items", [])
        waived_item = next((item for item in line_items if item["store_id"] == STORE_ID_1), None)
        
        if waived_item:
            assert waived_item["waived"] == True, "Waived store should have waived=True"
            assert waived_item["amount"] == 0.0, f"Waived store amount should be $0, got ${waived_item['amount']}"
            assert waived_item["rate"] > 0, "Waived store should still show the rate"
            print(f"PASS: Waived store '{waived_item['store_name']}' shows rate=${waived_item['rate']} but amount=$0")
            print(f"  - waiver_reason: {waived_item.get('waiver_reason')}")
        else:
            print(f"Note: Store {STORE_ID_1} not found in line items (may not be active for this partner)")
        
        # Clean up waiver
        if TestPartnerInvoiceWaiverLogic.test_waiver_id:
            requests.delete(
                f"{BASE_URL}/api/admin/partner-invoices/waivers/{TestPartnerInvoiceWaiverLogic.test_waiver_id}",
                headers={"X-User-ID": SUPER_ADMIN_USER_ID}
            )
            print("Cleaned up test waiver")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_invoice(self):
        """Clean up test invoice by marking as cancelled"""
        if TestPartnerInvoiceGeneration.generated_invoice_id:
            # Mark as cancelled (can't delete, but can cancel)
            response = requests.patch(
                f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceGeneration.generated_invoice_id}",
                headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
                json={"status": "cancelled"}
            )
            print(f"Marked test invoice {TestPartnerInvoiceGeneration.generated_invoice_id} as cancelled")
        
        if TestPartnerInvoiceWaiverLogic.test_invoice_id:
            response = requests.patch(
                f"{BASE_URL}/api/admin/partner-invoices/status/{TestPartnerInvoiceWaiverLogic.test_invoice_id}",
                headers={"X-User-ID": SUPER_ADMIN_USER_ID, "Content-Type": "application/json"},
                json={"status": "cancelled"}
            )
            print(f"Marked waiver test invoice {TestPartnerInvoiceWaiverLogic.test_invoice_id} as cancelled")
        
        print("PASS: Cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
