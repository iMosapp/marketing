"""
Tests for Jessi AI vehicle reference fix:
- build_relationship_brief() uses most recent purchase_history entry, NOT stale personal_details.vehicle_purchased
- POST /purchases with category='vehicle' syncs personal_details.vehicle_purchased
- Legacy contacts (no purchase_history) still show vehicle_details from personal_details
"""
import pytest
import requests
import os
import sys
import asyncio


def _init():
    """Load backend .env and frontend .env, set env vars, return BASE_URL."""
    backend_env = "/app/backend/.env"
    if os.path.exists(backend_env):
        with open(backend_env) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"')

    url = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not url:
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.strip().split("=", 1)[1]

    sys.path.insert(0, "/app/backend")
    return url.rstrip("/")


BASE_URL = _init()
USER_ID = "69a0b7095fddcede09591667"
HEADERS = None


def get_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "forest@imosapp.com", "password": "Admin123!"})
    if r.status_code == 200:
        token = r.json().get("token") or r.json().get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def setup_headers():
    global HEADERS
    HEADERS = get_headers()


def create_test_contact(suffix="270"):
    payload = {
        "first_name": "TEST_Jessi",
        "last_name": f"VehicleFix{suffix}",
        "phone": f"555{suffix[:7].zfill(7)}",
        "personal_details": {
            "vehicle_purchased": "Mojave",
            "vehicle_details": "Black, 2023, with chrome package",
            "vehicle_color": "Black"
        }
    }
    r = requests.post(f"{BASE_URL}/api/contacts/{USER_ID}", json=payload, headers=HEADERS)
    assert r.status_code in (200, 201), f"Contact creation failed: {r.text}"
    data = r.json()
    cid = data.get("id") or data.get("_id") or data.get("contact_id")
    assert cid, f"No contact id in response: {data}"
    return cid


def delete_contact(contact_id):
    if contact_id:
        requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}", headers=HEADERS)


def get_ai_context(contact_id):
    """Get ai_context via direct Python import (HTTP endpoint strips it)."""
    # Reset DB singleton so Motor re-initializes with each new event loop
    import routers.database as db_module
    db_module._client = None
    db_module._db = None

    from services.relationship_intel import build_relationship_brief

    async def run():
        return await build_relationship_brief(USER_ID, contact_id)

    brief = asyncio.run(run())
    return brief.get("ai_context", "")


# ─── Test 1: POST /purchases syncs personal_details ───────────────────────────

class TestAddPurchaseSyncsVehicle:
    contact_id = None

    def test_create_contact(self):
        TestAddPurchaseSyncsVehicle.contact_id = create_test_contact("0001270a")

    def test_add_vehicle_purchase_returns_success(self):
        cid = TestAddPurchaseSyncsVehicle.contact_id
        r = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{cid}/purchases",
            json={"title": "Road Glide", "category": "vehicle", "date": "2024-06-01"},
            headers=HEADERS
        )
        assert r.status_code in (200, 201), f"Add purchase failed: {r.text}"

    def test_personal_details_vehicle_purchased_updated(self):
        cid = TestAddPurchaseSyncsVehicle.contact_id
        r = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}", headers=HEADERS)
        assert r.status_code == 200
        personal = r.json().get("personal_details", {})
        vp = personal.get("vehicle_purchased", "")
        assert vp == "Road Glide", f"vehicle_purchased not synced, got: '{vp}'"
        print(f"PASS: personal_details.vehicle_purchased = '{vp}'")

    def test_personal_details_vehicle_details_cleared(self):
        cid = TestAddPurchaseSyncsVehicle.contact_id
        r = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}", headers=HEADERS)
        assert r.status_code == 200
        personal = r.json().get("personal_details", {})
        vd = personal.get("vehicle_details", "NOT_PRESENT")
        # Should be cleared to "" or absent
        assert vd in ("", None, "NOT_PRESENT"), \
            f"vehicle_details should be cleared, got: '{vd}'"
        print(f"PASS: personal_details.vehicle_details = '{vd}' (cleared/absent)")

    def test_purchase_history_has_road_glide(self):
        cid = TestAddPurchaseSyncsVehicle.contact_id
        r = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}/purchases", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        # Response format: {"success": True, "purchases": [...]}
        purchases = data.get("purchases") if isinstance(data, dict) else data
        titles = [p.get("title") for p in purchases if isinstance(p, dict)]
        assert "Road Glide" in titles, f"Road Glide missing from purchase_history, got: {titles}"
        print(f"PASS: purchase_history contains Road Glide")

    def test_cleanup(self):
        delete_contact(TestAddPurchaseSyncsVehicle.contact_id)


# ─── Test 2: ai_context uses most recent purchase, not stale Mojave ───────────

class TestAiContextVehicle:
    contact_id = None

    def test_create_contact_with_old_vehicle(self):
        TestAiContextVehicle.contact_id = create_test_contact("0001270b")

    def test_add_road_glide_purchase(self):
        cid = TestAiContextVehicle.contact_id
        r = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{cid}/purchases",
            json={"title": "Road Glide", "category": "vehicle", "date": "2024-06-15"},
            headers=HEADERS
        )
        assert r.status_code in (200, 201), f"Failed: {r.text}"

    def test_ai_context_most_recent_is_road_glide(self):
        """Most recent purchase line should say Road Glide, not Mojave."""
        cid = TestAiContextVehicle.contact_id
        ai_context = get_ai_context(cid)
        print(f"\n--- AI Context ---\n{ai_context[:600]}\n---")
        assert "Road Glide" in ai_context, \
            f"Road Glide missing from ai_context. Context: {ai_context[:300]}"
        print("PASS: Road Glide present in ai_context")

    def test_ai_context_mojave_not_as_recent_purchase(self):
        """Mojave should NOT appear in 'Most recent purchase' line."""
        cid = TestAiContextVehicle.contact_id
        ai_context = get_ai_context(cid)
        for line in ai_context.split("\n"):
            if "Most recent purchase" in line:
                assert "Mojave" not in line, \
                    f"Mojave in 'Most recent purchase' line: '{line}'"
                print(f"PASS: most-recent-purchase line = '{line}'")
        print("PASS: Mojave not as most recent purchase")

    def test_stale_vehicle_details_not_in_ai_context(self):
        """vehicle_details for old Mojave should be cleared and not appear."""
        cid = TestAiContextVehicle.contact_id
        ai_context = get_ai_context(cid)
        assert "Black, 2023, with chrome package" not in ai_context, \
            "Stale Mojave vehicle_details still showing in AI context!"
        print("PASS: Stale vehicle_details not in AI context")

    def test_cleanup(self):
        delete_contact(TestAiContextVehicle.contact_id)


# ─── Test 3: Legacy contact (no purchase_history) still shows vehicle_details ─

class TestLegacyContactVehicleDetails:
    contact_id = None

    def test_create_legacy_contact(self):
        """Create a contact then set personal_details with old vehicle (no purchase_history)."""
        cid = create_test_contact("0001270d")
        # Set personal_details via the dedicated endpoint
        r = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{cid}/personal-details",
            json={"personal_details": {
                "vehicle_purchased": "Mojave",
                "vehicle_details": "Black, 2023, with chrome package",
                "vehicle_color": "Black"
            }},
            headers=HEADERS
        )
        assert r.status_code == 200, f"Failed to set personal_details: {r.text}"
        TestLegacyContactVehicleDetails.contact_id = cid

    def test_legacy_ai_context_shows_vehicle_details(self):
        """For legacy contacts (no purchase_history), vehicle_details should appear in ai_context."""
        cid = TestLegacyContactVehicleDetails.contact_id
        ai_context = get_ai_context(cid)
        print(f"Legacy AI context: {ai_context[:500]}")
        assert "Black, 2023, with chrome package" in ai_context, \
            f"vehicle_details missing from legacy contact ai_context. Context: {ai_context[:400]}"
        print("PASS: Legacy contact shows vehicle_details")

    def test_cleanup(self):
        delete_contact(TestLegacyContactVehicleDetails.contact_id)
