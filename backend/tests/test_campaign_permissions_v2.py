"""
Tests for Campaign Permissions (store_manager role blocked) and Tag→Enrollment pipeline.

Covers:
- POST /api/campaigns/{user_id} returns 403 for store_manager role
- PUT /api/campaigns/{user_id}/{campaign_id} returns 403 for store_manager role
- POST /api/campaigns/{user_id} succeeds for super_admin
- GET /api/campaigns/{user_id}/permissions returns allowed:false for store_manager, allowed:true for super_admin
- Tag-triggered enrollment creates campaign_pending_sends
- Tag enrollment is idempotent
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"

# Store manager test user - will be created if not found
STORE_MANAGER_EMAIL = "TEST_mgr_campcheck@imonsocial.com"
STORE_MANAGER_PASSWORD = "TestPass123!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def super_admin(session):
    """Login as super_admin."""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Super admin login failed: {resp.text}"
    user = resp.json().get("user", {})
    assert user, "No user data returned"
    print(f"Super admin ID: {user.get('_id')}")
    return user


@pytest.fixture(scope="module")
def store_manager_user(session, super_admin):
    """
    Return a known store_manager user with a store_id (so permission checks apply).
    Uses a pre-existing test user in the DB: 69a5303dbd4ef63b7ef776d5
    """
    # Known store_manager user with store_id=69a0b7095fddcede09591668
    # Verified manually: store has no managers_can_edit setting → defaults to False
    return {
        "_id": "69a5303dbd4ef63b7ef776d5",
        "store_id": "69a0b7095fddcede09591668",
        "role": "store_manager"
    }


# =====================================================
# TEST: GET /api/campaigns/{user_id}/permissions
# =====================================================

class TestCampaignPermissions:
    """Test campaign permission endpoint."""

    def test_super_admin_permission_allowed(self, session, super_admin):
        """super_admin should always get allowed=True."""
        uid = super_admin.get("_id")
        resp = session.get(f"{BASE_URL}/api/campaigns/{uid}/permissions")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("allowed") == True, f"Expected allowed=True for super_admin, got: {data}"
        print(f"Super admin permission: {data}")

    def test_store_manager_permission_denied(self, session, store_manager_user):
        """store_manager with no store or default store settings should get allowed=False."""
        uid = store_manager_user.get("_id")
        resp = session.get(f"{BASE_URL}/api/campaigns/{uid}/permissions")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        # store_manager without store → "Manager default access" = True per current code
        # store_manager with store where managers_can_edit=False → allowed=False
        print(f"Store manager permission result: {data}")
        # Check if store assigned - if no store, the code returns allowed=True (fallback)
        store_id = store_manager_user.get("store_id")
        if store_id:
            assert data.get("allowed") == False, f"store_manager with store should be denied by default: {data}"
        else:
            print("NOTE: store_manager has no store assigned - defaults to allowed=True per code (line 474-475)")

    def test_invalid_user_permission_denied(self, session):
        """Non-existent user returns allowed=False."""
        resp = session.get(f"{BASE_URL}/api/campaigns/000000000000000000000000/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("allowed") == False, f"Expected allowed=False for invalid user: {data}"


# =====================================================
# TEST: POST /api/campaigns - Permission enforcement
# =====================================================

class TestCampaignCreatePermissions:
    """Test campaign creation blocked for store_manager."""

    def test_super_admin_can_create_campaign(self, session, super_admin):
        """super_admin should create campaign successfully."""
        uid = super_admin.get("_id")
        payload = {
            "name": "TEST_SuperAdmin_Campaign_v2",
            "type": "general",
            "active": False,
            "sequences": []
        }
        resp = session.post(f"{BASE_URL}/api/campaigns/{uid}", json=payload)
        assert resp.status_code in [200, 201], f"super_admin create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("name") == "TEST_SuperAdmin_Campaign_v2"
        campaign_id = data.get("_id") or data.get("id")
        print(f"Super admin created campaign: {campaign_id}")

        # Cleanup
        if campaign_id:
            session.delete(f"{BASE_URL}/api/campaigns/{uid}/{campaign_id}")

    def test_store_manager_create_campaign_blocked(self, session, store_manager_user):
        """store_manager with store should be denied campaign creation (403)."""
        uid = store_manager_user.get("_id")
        store_id = store_manager_user.get("store_id")

        if not store_id:
            pytest.skip("store_manager has no store_id — cannot test permission block (no-store fallback is allowed=True)")

        payload = {
            "name": "TEST_Manager_Campaign_BLOCKED",
            "type": "general",
            "active": False,
            "sequences": []
        }
        resp = session.post(f"{BASE_URL}/api/campaigns/{uid}", json=payload)
        assert resp.status_code == 403, f"Expected 403 for store_manager, got {resp.status_code}: {resp.text}"
        print(f"store_manager correctly blocked: {resp.json()}")

    def test_store_manager_edit_campaign_blocked(self, session, super_admin, store_manager_user):
        """store_manager cannot edit a campaign (403)."""
        store_id = store_manager_user.get("store_id")
        if not store_id:
            pytest.skip("store_manager has no store_id — cannot test permission block")

        # First create a campaign as super_admin
        admin_uid = super_admin.get("_id")
        mgr_uid = store_manager_user.get("_id")
        payload = {"name": "TEST_Campaign_For_Mgr_Edit", "type": "general", "active": False, "sequences": []}
        create_resp = session.post(f"{BASE_URL}/api/campaigns/{admin_uid}", json=payload)
        assert create_resp.status_code in [200, 201], f"Failed to create test campaign: {create_resp.text}"
        campaign_id = create_resp.json().get("_id") or create_resp.json().get("id")

        # Manager tries to edit
        edit_resp = session.put(f"{BASE_URL}/api/campaigns/{mgr_uid}/{campaign_id}", json={"name": "EDITED_NAME"})
        # Either 403 (permission denied) or 404 (no access to campaign) - both are valid blocks
        assert edit_resp.status_code in [403, 404], f"Expected 403/404, got {edit_resp.status_code}: {edit_resp.text}"
        print(f"store_manager edit blocked: {edit_resp.status_code}")

        # Cleanup
        session.delete(f"{BASE_URL}/api/campaigns/{admin_uid}/{campaign_id}")


# =====================================================
# TEST: Tag → Campaign Enrollment Pipeline
# =====================================================

class TestTagCampaignEnrollment:
    """Test that applying a tag triggers campaign auto-enrollment."""

    @pytest.fixture(scope="class")
    def test_campaign(self, session, super_admin):
        """Create an active campaign with a test trigger_tag."""
        uid = super_admin.get("_id")
        tag = "TEST_tag_trigger_v2"
        payload = {
            "name": "TEST_TagTrigger_Campaign_v2",
            "type": "custom",
            "trigger_tag": tag,
            "active": True,
            "delivery_mode": "manual",
            "sequences": [
                {
                    "step": 1,
                    "delay_days": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "message_template": "Hi {name}, test enrollment message!"
                }
            ]
        }
        resp = session.post(f"{BASE_URL}/api/campaigns/{uid}", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create test campaign: {resp.text}"
        campaign = resp.json()
        campaign_id = campaign.get("_id") or campaign.get("id")
        print(f"Created test campaign: {campaign_id}, trigger_tag={tag}")
        yield {"id": campaign_id, "tag": tag, "uid": uid}
        # Cleanup
        session.delete(f"{BASE_URL}/api/campaigns/{uid}/{campaign_id}")

    @pytest.fixture(scope="class")
    def test_contact(self, session, super_admin):
        """Create a test contact."""
        uid = super_admin.get("_id")
        payload = {
            "first_name": "TEST",
            "last_name": "TagEnrollContact",
            "phone": "+15550010001",
            "email": "TEST_tagenroll@test.com"
        }
        resp = session.post(f"{BASE_URL}/api/contacts/{uid}", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create contact: {resp.text}"
        contact = resp.json()
        contact_id = contact.get("_id") or contact.get("id")
        print(f"Created test contact: {contact_id}")
        yield {"id": contact_id, "uid": uid}
        # Cleanup
        session.delete(f"{BASE_URL}/api/contacts/{uid}/{contact_id}")

    def test_tag_application_triggers_enrollment(self, session, super_admin, test_campaign, test_contact):
        """Applying a trigger_tag to a contact should create pending_sends."""
        uid = super_admin.get("_id")
        contact_id = test_contact["id"]
        tag = test_campaign["tag"]
        campaign_id = test_campaign["id"]

        # Apply the tag via PATCH /api/contacts/{uid}/{contact_id}/tags
        tag_resp = session.patch(f"{BASE_URL}/api/contacts/{uid}/{contact_id}/tags", json={
            "tags": [tag]
        })
        assert tag_resp.status_code == 200, f"Tag apply failed: {tag_resp.status_code} {tag_resp.text}"
        print(f"Tag '{tag}' applied to contact {contact_id}")

        # Wait a moment for async enrollment
        time.sleep(1)

        # Check campaign_pending_sends via pending-sends endpoint
        pending_resp = session.get(f"{BASE_URL}/api/campaigns/{uid}/pending-sends")
        assert pending_resp.status_code == 200, f"Pending sends fetch failed: {pending_resp.text}"
        pending = pending_resp.json()
        matching = [p for p in pending if p.get("campaign_id") == campaign_id and p.get("contact_id") == contact_id]
        assert len(matching) >= 1, f"Expected at least 1 pending send for enrolled contact, got 0. All pending: {len(pending)}"
        print(f"Found {len(matching)} pending send(s) for tag-triggered enrollment")

    def test_tag_enrollment_idempotent(self, session, super_admin, test_campaign, test_contact):
        """Applying the same tag a second time should NOT create duplicate pending sends."""
        uid = super_admin.get("_id")
        contact_id = test_contact["id"]
        tag = test_campaign["tag"]
        campaign_id = test_campaign["id"]

        # Count current pending sends
        pending_resp1 = session.get(f"{BASE_URL}/api/campaigns/{uid}/pending-sends")
        count_before = len([p for p in pending_resp1.json()
                            if p.get("campaign_id") == campaign_id and p.get("contact_id") == contact_id])

        # Apply same tag again
        tag_resp = session.patch(f"{BASE_URL}/api/contacts/{uid}/{contact_id}/tags", json={
            "tags": [tag]
        })
        assert tag_resp.status_code == 200

        time.sleep(1)

        # Count again — should be same
        pending_resp2 = session.get(f"{BASE_URL}/api/campaigns/{uid}/pending-sends")
        count_after = len([p for p in pending_resp2.json()
                           if p.get("campaign_id") == campaign_id and p.get("contact_id") == contact_id])

        assert count_after == count_before, (
            f"Idempotency violation: applying same tag twice created duplicates "
            f"(before={count_before}, after={count_after})"
        )
        print(f"Idempotency check passed: {count_before} pending sends (no duplicates added)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
