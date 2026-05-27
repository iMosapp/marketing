"""
Backend tests for:
- Shared Inboxes CRUD (GET, POST, PUT, DELETE)
- Shared Inbox VA profile fields in list response
- Shared Inbox Webhook Info endpoint
- Lead Sources Workflow VA picker support
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_USER_ID = "69a0b7095fddcede09591667"

# Fixture: shared requests session
@pytest.fixture(scope="module")
def client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ─── Health Check ──────────────────────────────────────────────────────────────
class TestHealthCheck:
    """Backend health check"""

    def test_backend_healthy(self, client):
        res = client.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "healthy"
        print(f"PASS: Backend healthy - {data}")


# ─── Shared Inboxes List ────────────────────────────────────────────────────────
class TestSharedInboxesList:
    """GET /api/admin/team/shared-inboxes - list with va_profile_id fields"""

    def test_list_returns_200(self, client):
        res = client.get(f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={ADMIN_USER_ID}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert isinstance(data, list)
        print(f"PASS: GET shared-inboxes returned {len(data)} items")

    def test_list_items_have_va_fields(self, client):
        """Each item in list must include va_profile_id and va_prompt_override"""
        res = client.get(f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={ADMIN_USER_ID}")
        assert res.status_code == 200
        data = res.json()
        if len(data) == 0:
            pytest.skip("No inboxes exist yet - skipping field check")
        for inbox in data:
            assert "va_profile_id" in inbox, f"Missing va_profile_id in {inbox.get('id')}"
            assert "va_prompt_override" in inbox, f"Missing va_prompt_override in {inbox.get('id')}"
        print(f"PASS: All {len(data)} inboxes have va_profile_id and va_prompt_override")


# ─── Shared Inboxes CRUD ────────────────────────────────────────────────────────
class TestSharedInboxesCRUD:
    """Create, Update, Webhook, Delete for shared inboxes"""

    created_inbox_id = None

    def test_create_shared_inbox(self, client):
        payload = {
            "name": "TEST_Inbox_VA_Picker",
            "phone_number": "+18005550001",
            "description": "Test inbox for VA picker feature",
            "assigned_user_ids": []
        }
        res = client.post(
            f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={ADMIN_USER_ID}",
            json=payload
        )
        assert res.status_code == 200, f"Create failed: {res.status_code} {res.text}"
        data = res.json()
        assert "id" in data or "inbox_id" in data or "_id" in data or "message" in data
        print(f"PASS: Created shared inbox: {data}")

    def test_list_after_create(self, client):
        """After creating, list should include the new inbox"""
        res = client.get(f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={ADMIN_USER_ID}")
        assert res.status_code == 200
        data = res.json()
        found = [i for i in data if i.get("name") == "TEST_Inbox_VA_Picker"]
        assert len(found) >= 1, "Newly created inbox not in list"
        TestSharedInboxesCRUD.created_inbox_id = found[0]["id"]
        print(f"PASS: Inbox found in list, id={TestSharedInboxesCRUD.created_inbox_id}")

    def test_update_shared_inbox_with_va_fields(self, client):
        """PUT /api/admin/team/shared-inboxes/{id} - update name and va fields"""
        inbox_id = TestSharedInboxesCRUD.created_inbox_id
        if not inbox_id:
            pytest.skip("No inbox created - cannot test update")

        payload = {
            "name": "TEST_Inbox_VA_Updated",
            "va_profile_id": "test_va_profile_123",
            "va_prompt_override": "Be concise and helpful"
        }
        res = client.put(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{inbox_id}?user_id={ADMIN_USER_ID}",
            json=payload
        )
        assert res.status_code == 200, f"Update failed: {res.status_code} {res.text}"
        print(f"PASS: Updated inbox {inbox_id}: {res.json()}")

    def test_list_after_update_has_va_fields(self, client):
        """After update, list should reflect changes"""
        res = client.get(f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={ADMIN_USER_ID}")
        assert res.status_code == 200
        data = res.json()
        inbox_id = TestSharedInboxesCRUD.created_inbox_id
        if not inbox_id:
            pytest.skip("No inbox created")
        found = [i for i in data if i.get("id") == inbox_id]
        assert len(found) == 1, "Updated inbox not found in list"
        inbox = found[0]
        assert inbox.get("va_profile_id") == "test_va_profile_123", f"va_profile_id not persisted: {inbox}"
        assert inbox.get("va_prompt_override") == "Be concise and helpful", f"va_prompt_override not persisted: {inbox}"
        print(f"PASS: VA fields persisted in list after update")

    def test_webhook_info_endpoint(self, client):
        """GET /api/admin/team/shared-inboxes/{id}/webhook-info"""
        inbox_id = TestSharedInboxesCRUD.created_inbox_id
        if not inbox_id:
            pytest.skip("No inbox created - cannot test webhook info")

        res = client.get(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{inbox_id}/webhook-info?user_id={ADMIN_USER_ID}"
        )
        assert res.status_code == 200, f"Webhook info failed: {res.status_code} {res.text}"
        data = res.json()
        assert "webhook_url" in data, f"Missing webhook_url in response: {data}"
        assert "example_payload" in data, f"Missing example_payload in response: {data}"
        print(f"PASS: Webhook info returned: {data.get('webhook_url')}")

    def test_delete_shared_inbox(self, client):
        """DELETE /api/admin/team/shared-inboxes/{id}"""
        inbox_id = TestSharedInboxesCRUD.created_inbox_id
        if not inbox_id:
            pytest.skip("No inbox created - cannot test delete")

        res = client.delete(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{inbox_id}?user_id={ADMIN_USER_ID}"
        )
        assert res.status_code == 200, f"Delete failed: {res.status_code} {res.text}"
        data = res.json()
        assert "message" in data or "id" in data
        print(f"PASS: Deleted inbox {inbox_id}: {data}")

    def test_list_after_delete_not_found(self, client):
        """After delete, inbox should not appear in list"""
        inbox_id = TestSharedInboxesCRUD.created_inbox_id
        if not inbox_id:
            pytest.skip("No inbox created")

        res = client.get(f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={ADMIN_USER_ID}")
        assert res.status_code == 200
        data = res.json()
        found = [i for i in data if i.get("id") == inbox_id]
        assert len(found) == 0, f"Deleted inbox still in list: {found}"
        print(f"PASS: Deleted inbox not found in list (verified removal)")


# ─── Lead Sources Workflow VA Config ────────────────────────────────────────────
class TestLeadSourcesWorkflow:
    """Lead Sources: Verify workflow endpoint includes va_profile_id support"""

    lead_source_id = None

    def test_list_lead_sources(self, client):
        """GET /api/lead-sources - list all lead sources to find or create one"""
        res = client.get(
            f"{BASE_URL}/api/lead-sources?store_id=test_store",
            headers={"X-User-ID": ADMIN_USER_ID}
        )
        # Accept 200 or 404 (no lead sources)
        assert res.status_code in [200, 404], f"Unexpected status: {res.status_code}"
        if res.status_code == 200:
            data = res.json()
            sources = data if isinstance(data, list) else data.get("lead_sources", [])
            if len(sources) > 0:
                TestLeadSourcesWorkflow.lead_source_id = sources[0].get("id") or str(sources[0].get("_id", ""))
        print(f"PASS: Lead sources list returned: {res.status_code}")

    def test_get_workflow_endpoint(self, client):
        """GET /api/lead-sources/{id}/workflow - verify va_profile_id in response"""
        lead_id = TestLeadSourcesWorkflow.lead_source_id
        if not lead_id:
            pytest.skip("No lead source available - skipping workflow test")

        res = client.get(f"{BASE_URL}/api/lead-sources/{lead_id}/workflow")
        assert res.status_code in [200, 404], f"Unexpected: {res.status_code} {res.text}"
        if res.status_code == 200:
            data = res.json()
            # va_profile_id should be present (can be None)
            assert "va_profile_id" in data or "va_enabled" in data, f"Workflow fields missing: {data}"
            print(f"PASS: Workflow endpoint returned va fields: {data}")
        else:
            print(f"INFO: No workflow config yet for this lead source")


# ─── VA Profiles Check ─────────────────────────────────────────────────────────
class TestVAProfiles:
    """Check VA profiles endpoint (used by VA picker)"""

    def test_get_va_profiles(self, client):
        res = client.get(
            f"{BASE_URL}/api/va-profiles",
            headers={"X-User-ID": ADMIN_USER_ID}
        )
        assert res.status_code == 200, f"VA profiles failed: {res.status_code} {res.text}"
        data = res.json()
        profiles = data.get("profiles", [])
        assert isinstance(profiles, list)
        print(f"PASS: VA profiles returned {len(profiles)} profiles")
