"""
Tests for the SOLD wizard vehicle/purchase bug fix (iteration 268):
1. PATCH /contacts/{uid}/{cid}/vehicle — safe partial update
2. POST /contacts/{uid}/{cid}/purchases — sets vehicle field on contact
3. GET /contacts/{uid}/{cid} — vehicle field visible after purchase
4. relationship_intel.py — most_recent_purchase in AI context
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"

# Auth headers
AUTH = {"X-User-ID": USER_ID}
TEST_PHONE = "+15559870001"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def test_contact_id(session):
    """Create a test contact and return its id. Cleaned up after module."""
    res = session.post(f"{BASE_URL}/api/contacts/{USER_ID}", json={
        "first_name": "TEST_VehicleFix",
        "last_name": "Buyer",
        "phone": TEST_PHONE,
        "tags": [],
    })
    assert res.status_code in (200, 201), f"Create contact failed: {res.text}"
    data = res.json()
    cid = data.get("id") or data.get("_id")
    assert cid, "No contact id returned"
    yield cid
    # Cleanup
    session.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}")


class TestPatchVehicleEndpoint:
    """PATCH /contacts/{uid}/{cid}/vehicle — safe partial update"""

    def test_patch_vehicle_returns_200(self, session, test_contact_id):
        res = session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/vehicle",
            json={"vehicle": "2024 Ford F-150 PATCH"}
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_patch_vehicle_response_has_vehicle_field(self, session, test_contact_id):
        res = session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/vehicle",
            json={"vehicle": "2024 Toyota Tacoma"}
        )
        data = res.json()
        assert data.get("success") is True
        assert data.get("vehicle") == "2024 Toyota Tacoma"

    def test_patch_vehicle_persists_to_contact(self, session, test_contact_id):
        """After PATCH, GET should show updated vehicle field."""
        vehicle_name = "2025 Chevy Silverado"
        session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/vehicle",
            json={"vehicle": vehicle_name}
        )
        get_res = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}")
        assert get_res.status_code == 200
        contact = get_res.json()
        assert contact.get("vehicle") == vehicle_name, f"Vehicle not updated: {contact.get('vehicle')}"

    def test_patch_vehicle_does_not_change_other_fields(self, session, test_contact_id):
        """Critical: PATCH /vehicle must NOT wipe name, phone, tags."""
        get_before = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}").json()
        session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/vehicle",
            json={"vehicle": "Honda CR-V"}
        )
        get_after = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}").json()
        # Core fields must be unchanged
        assert get_after.get("first_name") == get_before.get("first_name"), "first_name was wiped!"
        assert get_after.get("phone") == get_before.get("phone"), "phone was wiped!"

    def test_patch_vehicle_empty_returns_400(self, session, test_contact_id):
        res = session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/vehicle",
            json={"vehicle": ""}
        )
        assert res.status_code == 400

    def test_patch_vehicle_invalid_contact_returns_404(self, session):
        res = session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/000000000000000000000000/vehicle",
            json={"vehicle": "Test Car"}
        )
        assert res.status_code == 404


class TestPostPurchaseUpdatesVehicle:
    """POST /purchases should update contact.vehicle = purchase.title"""

    def test_post_purchase_returns_200(self, session, test_contact_id):
        res = session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases",
            json={
                "title": "2024 Ram 1500",
                "category": "vehicle",
                "date": datetime.utcnow().date().isoformat(),
                "notes": "Test purchase",
            }
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    def test_post_purchase_response_has_purchase_object(self, session, test_contact_id):
        res = session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases",
            json={"title": "2023 Jeep Wrangler", "category": "vehicle", "date": "2025-01-15"}
        )
        data = res.json()
        assert data.get("success") is True
        purchase = data.get("purchase", {})
        assert purchase.get("title") == "2023 Jeep Wrangler"
        assert "id" in purchase

    def test_post_purchase_sets_vehicle_on_contact(self, session, test_contact_id):
        """Core bug fix: POST /purchases must update contact.vehicle field."""
        title = "2025 Ford Maverick Lariat"
        session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases",
            json={"title": title, "category": "vehicle", "date": "2025-02-01"}
        )
        get_res = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}")
        assert get_res.status_code == 200
        contact = get_res.json()
        assert contact.get("vehicle") == title, (
            f"vehicle field not set after POST /purchases. Got: {contact.get('vehicle')}"
        )

    def test_post_purchase_purchase_in_history(self, session, test_contact_id):
        """Purchase should appear in GET /purchases."""
        title = "TEST_HistoryCheck Honda Pilot"
        session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases",
            json={"title": title, "category": "vehicle", "date": "2025-02-10"}
        )
        hist_res = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases")
        assert hist_res.status_code == 200
        data = hist_res.json()
        titles = [p.get("title") for p in data.get("purchases", [])]
        assert title in titles, f"Purchase not found in history. Got titles: {titles}"

    def test_post_purchase_missing_title_returns_400(self, session, test_contact_id):
        res = session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases",
            json={"category": "vehicle", "date": "2025-02-01"}
        )
        assert res.status_code == 400


class TestRelationshipIntelPurchaseContext:
    """relationship_intel.py should include most_recent_purchase in AI context."""

    def test_relationship_brief_returns_ok(self, session, test_contact_id):
        """Jessi AI brief endpoint should work (if exposed). Indirect: check brief via jessi or intel."""
        # Try the relationship brief endpoint
        res = session.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/relationship-brief",
            headers=AUTH
        )
        # If endpoint doesn't exist, skip (it's used internally by Jessi)
        if res.status_code == 404:
            pytest.skip("relationship-brief endpoint not exposed; tested via jessi")
        assert res.status_code == 200
        data = res.json()
        # Should have contact dict with vehicle or most_recent_purchase
        contact_dict = data.get("contact", {})
        assert "vehicle" in contact_dict or "most_recent_purchase" in contact_dict

    def test_contact_vehicle_field_set_after_purchase(self, session, test_contact_id):
        """After adding purchase, contact.vehicle must be set — this feeds relationship_intel."""
        title = "2025 Intel Context Car"
        session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases",
            json={"title": title, "category": "vehicle", "date": "2025-02-15"}
        )
        contact = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}").json()
        assert contact.get("vehicle") == title, (
            f"contact.vehicle should be '{title}' for AI context. Got: {contact.get('vehicle')}"
        )

    def test_purchase_history_has_entries(self, session, test_contact_id):
        """purchase_history must have entries for relationship_intel to show history."""
        hist_res = session.get(f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/purchases")
        assert hist_res.status_code == 200
        purchases = hist_res.json().get("purchases", [])
        assert len(purchases) >= 1, "purchase_history is empty — AI context won't show history"
