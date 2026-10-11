"""Setup Wizard API (repaired Oct 11 2026: real Bearer tokens, self-cleaning data):
- GET/POST /api/setup-wizard/progress/{org_id}
- POST /api/setup-wizard/bulk-invite
- POST /api/setup-wizard/complete/{org_id}
"""
import secrets
import uuid

from tests.live_auth import STORE_A, anon

ZERO = "000000000000000000000000"


class TestSetupWizardProgress:
    def test_get_progress_unknown_org(self, super_admin):
        org_id = f"test_{uuid.uuid4().hex[:12]}"
        status, data = super_admin.get(f"/api/setup-wizard/progress/{org_id}")
        assert status == 200, data
        assert data["organization_id"] == org_id
        assert data["current_step"] == 1 and data["completed_steps"] == [] and data["completed"] is False

    def test_save_and_get_progress(self, super_admin, mongo):
        org_id = f"test_{uuid.uuid4().hex[:12]}"
        try:
            status, saved = super_admin.post(f"/api/setup-wizard/progress/{org_id}", {"store_id": STORE_A, "current_step": 3, "completed_steps": [1, 2], "completed": False})
            assert status == 200 and saved["success"] is True, saved
            status, data = super_admin.get(f"/api/setup-wizard/progress/{org_id}")
            assert status == 200
            assert data["current_step"] == 3 and data["completed_steps"] == [1, 2] and data["completed"] is False
        finally:
            mongo.setup_wizard_progress.delete_one({"organization_id": org_id})

    def test_progress_requires_auth_and_org_scope(self, store_manager):
        assert anon("GET", "/api/setup-wizard/progress/anything")[0] == 401
        assert store_manager.get("/api/setup-wizard/progress/anything")[0] == 403


class TestSetupWizardBulkInvite:
    def test_bulk_invite_creates_users(self, super_admin, mongo):
        uid = secrets.token_hex(3)
        members = [
            {"name": f"Test User {uid} A", "email": f"wizard-{uid}-a@qa.imonsocial.com", "phone": f"500555{secrets.randbelow(9000) + 1000}", "role": "user"},
            {"name": f"Test User {uid} B", "email": f"wizard-{uid}-b@qa.imonsocial.com", "phone": f"500555{secrets.randbelow(9000) + 1000}", "role": "store_manager"},
        ]
        try:
            status, data = super_admin.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": members})
            assert status == 200, data
            assert data["total"] == 2 and data["created"] == 2
            for r in data["results"]:
                assert r["status"] == "created" and r["temp_password"] and r["user_id"]
        finally:
            mongo.users.delete_many({"email": {"$in": [m["email"] for m in members]}})

    def test_bulk_invite_skip_existing_email(self, super_admin):
        members = [{"name": "Existing", "email": super_admin.email, "phone": "5005551111", "role": "user"}]
        status, data = super_admin.post("/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": members})
        assert status == 200, data
        assert data["results"][0]["status"] == "skipped"
        assert "already exists" in data["results"][0]["reason"].lower()

    def test_bulk_invite_requires_auth(self):
        assert anon("POST", "/api/setup-wizard/bulk-invite", {"store_id": STORE_A, "members": []})[0] == 401

    def test_bulk_invite_invalid_store(self, super_admin):
        status, body = super_admin.post("/api/setup-wizard/bulk-invite", {"store_id": ZERO, "members": [{"name": "T", "email": "t@qa.imonsocial.com", "role": "user"}]})
        assert status == 404, body


class TestSetupWizardComplete:
    def test_mark_wizard_complete(self, super_admin, mongo):
        org_id = f"test_{uuid.uuid4().hex[:12]}"
        try:
            status, data = super_admin.post(f"/api/setup-wizard/complete/{org_id}")
            assert status == 200 and data["success"] is True, data
            status, data = super_admin.get(f"/api/setup-wizard/progress/{org_id}")
            assert status == 200 and data["completed"] is True
        finally:
            mongo.setup_wizard_progress.delete_one({"organization_id": org_id})
