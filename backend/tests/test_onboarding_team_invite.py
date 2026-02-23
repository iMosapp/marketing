"""
Tests for Onboarding Settings and Team Invite APIs
Tests Phase 1 (Admin Branding Center) and Phase 3 (Team Member Flow)
"""
import pytest
import requests
import os
import secrets

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://crm-webhooks.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_STORE_ID = "699637981b07c23426a5324a"
TEST_USER_ID = "6995b8bf6f535e1cec4e4ad4"
TEST_INVITE_CODE = "xah25yz9"

class TestOnboardingSettings:
    """Tests for /api/onboarding-settings endpoints"""
    
    def test_get_global_settings_returns_defaults(self):
        """GET /api/onboarding-settings/global returns default settings"""
        response = requests.get(f"{BASE_URL}/api/onboarding-settings/global")
        assert response.status_code == 200
        
        data = response.json()
        # Check required fields exist
        assert "messages" in data
        assert "app_links" in data
        assert "branding" in data
        assert "training_required" in data or data.get("training_required") == False  # Can be false after PUT
        assert "auto_send_welcome_sms" in data
        assert "auto_send_team_invite" in data
        
        # Check messages structure
        assert "welcome_sms" in data["messages"]
        assert "training_complete_sms" in data["messages"]
        assert "team_invite_sms" in data["messages"]
        assert "team_welcome_sms" in data["messages"]
        
        # Check branding is a dict (may have partial data after updates)
        assert isinstance(data["branding"], dict)
        
        print(f"GET /api/onboarding-settings/global: PASS - returned {len(data)} keys")
    
    def test_put_global_settings_updates(self):
        """PUT /api/onboarding-settings/global updates settings"""
        update_data = {
            "branding": {
                "company_name": f"TEST_Company_{secrets.token_hex(4)}"
            },
            "training_required": False
        }
        
        response = requests.put(
            f"{BASE_URL}/api/onboarding-settings/global",
            json=update_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["branding"]["company_name"] == update_data["branding"]["company_name"]
        assert data["training_required"] == False
        assert "_id" in data  # Should have persisted
        
        print(f"PUT /api/onboarding-settings/global: PASS - updated company_name")
        
        # Verify GET returns updated data
        get_response = requests.get(f"{BASE_URL}/api/onboarding-settings/global")
        get_data = get_response.json()
        assert get_data["branding"]["company_name"] == update_data["branding"]["company_name"]
        print(f"GET after PUT: PASS - verified persistence")
    
    def test_get_placeholders_returns_list(self):
        """GET /api/onboarding-settings/placeholders returns placeholder list"""
        response = requests.get(f"{BASE_URL}/api/onboarding-settings/placeholders")
        assert response.status_code == 200
        
        data = response.json()
        assert "placeholders" in data
        assert isinstance(data["placeholders"], list)
        assert len(data["placeholders"]) > 0
        
        # Check placeholder structure
        for placeholder in data["placeholders"]:
            assert "key" in placeholder
            assert "description" in placeholder
            assert placeholder["key"].startswith("{")
            assert placeholder["key"].endswith("}")
        
        print(f"GET /api/onboarding-settings/placeholders: PASS - returned {len(data['placeholders'])} placeholders")
    
    def test_preview_message(self):
        """POST /api/onboarding-settings/preview-message returns filled placeholders"""
        response = requests.post(
            f"{BASE_URL}/api/onboarding-settings/preview-message",
            json={"template": "Welcome {user_name}! Visit {training_link}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "original" in data
        assert "preview" in data
        assert "placeholders_used" in data
        assert "{user_name}" not in data["preview"]  # Should be replaced
        assert "{training_link}" not in data["preview"]  # Should be replaced
        
        print(f"POST /api/onboarding-settings/preview-message: PASS")


class TestTeamInvite:
    """Tests for /api/team-invite endpoints"""
    
    def test_validate_existing_invite_code(self):
        """GET /api/team-invite/validate/{code} validates invite and returns store info"""
        response = requests.get(f"{BASE_URL}/api/team-invite/validate/{TEST_INVITE_CODE}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["valid"] == True
        assert "store_id" in data
        assert "store_name" in data
        assert data["store_id"] == TEST_STORE_ID
        
        print(f"GET /api/team-invite/validate/{TEST_INVITE_CODE}: PASS - store: {data['store_name']}")
    
    def test_validate_invalid_invite_code(self):
        """GET /api/team-invite/validate/{code} returns 404 for invalid code"""
        response = requests.get(f"{BASE_URL}/api/team-invite/validate/invalid123")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        
        print(f"GET /api/team-invite/validate/invalid123: PASS - returns 404")
    
    def test_create_team_invite(self):
        """POST /api/team-invite/create creates team invite with invite_code and invite_url"""
        response = requests.post(
            f"{BASE_URL}/api/team-invite/create",
            json={
                "store_id": TEST_STORE_ID,
                "created_by": TEST_USER_ID,
                "expires_days": 30
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "invite_code" in data
        assert "invite_url" in data
        assert "store_name" in data
        assert "expires_at" in data
        assert len(data["invite_code"]) == 8
        assert "/join/" in data["invite_url"]
        
        print(f"POST /api/team-invite/create: PASS - code: {data['invite_code']}")
        
        # Store for join test
        TestTeamInvite.created_invite_code = data["invite_code"]
    
    def test_join_team_creates_user(self):
        """POST /api/team-invite/join creates new user account from invite"""
        # Generate unique email/phone
        random_suffix = secrets.token_hex(4)
        test_email = f"test_join_{random_suffix}@test.com"
        test_phone = f"555{secrets.randbelow(9000000) + 1000000}"
        
        # First create a fresh invite
        create_response = requests.post(
            f"{BASE_URL}/api/team-invite/create",
            json={
                "store_id": TEST_STORE_ID,
                "created_by": TEST_USER_ID,
                "expires_days": 30
            }
        )
        invite_code = create_response.json()["invite_code"]
        
        # Join with the new invite
        response = requests.post(
            f"{BASE_URL}/api/team-invite/join",
            json={
                "invite_code": invite_code,
                "name": f"TEST_JoinUser_{random_suffix}",
                "phone": test_phone,
                "email": test_email
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "user" in data
        assert "training_link" in data
        assert "store_name" in data
        
        # Verify user data
        user = data["user"]
        assert user["email"] == test_email.lower()
        assert user["store_id"] == TEST_STORE_ID
        assert user["onboarding_complete"] == False
        assert "_id" in user
        
        print(f"POST /api/team-invite/join: PASS - created user: {user['_id']}")
    
    def test_join_duplicate_email_fails(self):
        """POST /api/team-invite/join rejects duplicate email"""
        response = requests.post(
            f"{BASE_URL}/api/team-invite/join",
            json={
                "invite_code": TEST_INVITE_CODE,
                "name": "Duplicate Test",
                "phone": "5559999999",
                "email": "forest@mvpline.com"  # Existing email
            }
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "email" in data["detail"].lower()
        
        print(f"POST /api/team-invite/join (duplicate email): PASS - rejected")
    
    def test_get_store_invites(self):
        """GET /api/team-invite/store/{store_id} returns active invites"""
        response = requests.get(f"{BASE_URL}/api/team-invite/store/{TEST_STORE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            invite = data[0]
            assert "invite_code" in invite
            assert "invite_url" in invite
            assert "created_at" in invite
            assert "expires_at" in invite
        
        print(f"GET /api/team-invite/store/{TEST_STORE_ID}: PASS - {len(data)} invites")
    
    def test_get_user_share_link(self):
        """GET /api/team-invite/user/{user_id}/invite-link returns personal invite"""
        response = requests.get(f"{BASE_URL}/api/team-invite/user/{TEST_USER_ID}/invite-link")
        assert response.status_code == 200
        
        data = response.json()
        assert "invite_code" in data
        assert "invite_url" in data
        assert "expires_at" in data
        
        print(f"GET /api/team-invite/user/{TEST_USER_ID}/invite-link: PASS")


class TestStoreAndOrgSettings:
    """Tests for store/org level onboarding settings"""
    
    def test_get_store_settings_returns_defaults(self):
        """GET /api/onboarding-settings/store/{store_id} returns settings"""
        response = requests.get(f"{BASE_URL}/api/onboarding-settings/store/{TEST_STORE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        assert "store_id" in data or "inherited_from" in data
        
        print(f"GET /api/onboarding-settings/store/{TEST_STORE_ID}: PASS")
    
    def test_get_invalid_store_returns_404(self):
        """GET /api/onboarding-settings/store/{invalid} returns 404"""
        response = requests.get(f"{BASE_URL}/api/onboarding-settings/store/000000000000000000000000")
        assert response.status_code == 404
        
        print(f"GET /api/onboarding-settings/store/invalid: PASS - returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
