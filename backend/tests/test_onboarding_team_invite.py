"""Onboarding Settings + Team Invite APIs (repaired Oct 11 2026: real Bearer tokens, no hard-coded invite codes, self-cleaning)."""
import secrets

from tests.live_auth import STORE_A, anon

ZERO = "000000000000000000000000"


class TestOnboardingSettings:
    def test_get_global_settings_returns_defaults(self, super_admin):
        status, data = super_admin.get("/api/onboarding-settings/global")
        assert status == 200, data
        for key in ("messages", "app_links", "branding", "auto_send_welcome_sms", "auto_send_team_invite"):
            assert key in data
        for key in ("welcome_sms", "training_complete_sms", "team_invite_sms", "team_welcome_sms"):
            assert key in data["messages"]
        assert isinstance(data["branding"], dict)

    def test_put_global_settings_updates_and_is_restored(self, super_admin):
        _, before = super_admin.get("/api/onboarding-settings/global")
        previous = (before.get("branding") or {}).get("company_name")
        name = f"TEST_Company_{secrets.token_hex(4)}"
        try:
            status, data = super_admin.put("/api/onboarding-settings/global", {"branding": {"company_name": name}})
            assert status == 200 and data["branding"]["company_name"] == name, data
            _, after = super_admin.get("/api/onboarding-settings/global")
            assert after["branding"]["company_name"] == name
        finally:
            if previous is not None:
                super_admin.put("/api/onboarding-settings/global", {"branding": {"company_name": previous}})

    def test_global_settings_are_super_admin_only(self, store_manager, org_admin):
        assert anon("GET", "/api/onboarding-settings/global")[0] == 401
        assert store_manager.get("/api/onboarding-settings/global")[0] == 403
        assert org_admin.put("/api/onboarding-settings/global", {"training_required": False})[0] == 403

    def test_get_placeholders_returns_list(self, rep):
        status, data = rep.get("/api/onboarding-settings/placeholders")
        assert status == 200, data
        assert data["placeholders"] and all(p["key"].startswith("{") and p["key"].endswith("}") for p in data["placeholders"])

    def test_preview_message(self, store_manager, rep):
        status, data = store_manager.post("/api/onboarding-settings/preview-message", {"template": "Welcome {user_name}! Visit {training_link}"})
        assert status == 200, data
        assert "{user_name}" not in data["preview"] and "{training_link}" not in data["preview"]
        assert rep.post("/api/onboarding-settings/preview-message", {"template": "x"})[0] == 403


class TestTeamInvite:
    def test_create_validate_join_and_revoke(self, store_manager, mongo):
        status, inv = store_manager.post("/api/team-invite/create", {"store_id": STORE_A, "expires_days": 30})
        assert status == 200, inv
        code = inv["invite_code"]
        assert len(code) == 8 and code in inv["invite_url"] and inv["store_name"] and inv["expires_at"]
        created_user = None
        try:
            status, data = anon("GET", f"/api/team-invite/validate/{code}")
            assert status == 200 and data["valid"] is True and data["store_id"] == STORE_A

            suffix = secrets.token_hex(3)
            status, joined = anon("POST", "/api/team-invite/join", {
                "invite_code": code, "name": f"TEST_JoinUser_{suffix}", "phone": f"500555{secrets.randbelow(9000) + 1000}",
                "email": f"test-join-{suffix}@qa.imonsocial.com"})
            assert status == 200, joined
            created_user = joined["user"]["_id"]
            assert joined["user"]["store_id"] == STORE_A and joined["user"]["onboarding_complete"] is False
            assert "training_link" in joined and joined["store_name"]

            status, dup = anon("POST", "/api/team-invite/join", {"invite_code": code, "name": "Dup", "phone": "5005559999", "email": store_manager.email})
            assert status == 400 and "email" in str(dup).lower()

            invite_id = str(mongo.team_invites.find_one({"invite_code": code})["_id"])
            assert store_manager.delete(f"/api/team-invite/{invite_id}")[0] == 200
        finally:
            if created_user:
                mongo.users.delete_one({"_id": __import__("bson").ObjectId(created_user)})
            mongo.team_invites.delete_one({"invite_code": code})

    def test_validate_invalid_invite_code(self):
        status, data = anon("GET", "/api/team-invite/validate/invalid123")
        assert status == 404 and "detail" in str(data)

    def test_get_store_invites(self, store_manager, rep):
        status, data = store_manager.get(f"/api/team-invite/store/{STORE_A}")
        assert status == 200 and isinstance(data, list), data
        for invite in data[:1]:
            for key in ("invite_code", "invite_url", "created_at", "expires_at"):
                assert key in invite
        assert rep.get(f"/api/team-invite/store/{STORE_A}")[0] == 403

    def test_get_user_share_link(self, store_manager, mongo):
        status, data = store_manager.get(f"/api/team-invite/user/{store_manager.user_id}/invite-link")
        assert status == 200, data
        assert data["invite_code"] and data["invite_url"] and data["expires_at"]
        assert anon("GET", f"/api/team-invite/user/{store_manager.user_id}/invite-link")[0] == 401


class TestStoreAndOrgSettings:
    def test_get_store_settings_returns_defaults(self, store_manager):
        status, data = store_manager.get(f"/api/onboarding-settings/store/{STORE_A}")
        assert status == 200, data
        assert "messages" in data and ("store_id" in data or "inherited_from" in data)

    def test_get_invalid_store_returns_404(self, super_admin):
        assert super_admin.get(f"/api/onboarding-settings/store/{ZERO}")[0] == 404
