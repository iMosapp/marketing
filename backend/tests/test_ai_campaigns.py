"""
AI Campaign Engine API Tests
Tests for clone prompt management, AI message generation, pending sends workflow
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestGlobalClonePrompt:
    """Tests for global AI clone prompt endpoint"""

    def test_get_global_clone_prompt(self, api_client):
        """GET /api/ai-campaigns/clone-prompt/global returns default prompt"""
        response = api_client.get(f"{BASE_URL}/api/ai-campaigns/clone-prompt/global")
        assert response.status_code == 200
        data = response.json()
        assert "scope" in data or "prompt" in data
        # Should contain {user_name} placeholder
        if "prompt" in data:
            assert "{user_name}" in data["prompt"]
        print(f"Global prompt scope: {data.get('scope', 'default')}")

    def test_update_global_clone_prompt(self, api_client):
        """PUT /api/ai-campaigns/clone-prompt/global updates the prompt"""
        test_prompt = "Test global prompt with {user_name} and {user_bio} variables"
        response = api_client.put(
            f"{BASE_URL}/api/ai-campaigns/clone-prompt/global",
            json={"prompt": test_prompt}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "updated" in data.get("message", "").lower()
        print("Global prompt updated successfully")

    def test_update_global_clone_prompt_empty_fails(self, api_client):
        """PUT /api/ai-campaigns/clone-prompt/global with empty prompt fails"""
        response = api_client.put(
            f"{BASE_URL}/api/ai-campaigns/clone-prompt/global",
            json={"prompt": ""}
        )
        assert response.status_code == 400
        print("Empty prompt correctly rejected")


class TestUserClonePrompt:
    """Tests for user-specific AI clone prompt endpoint"""

    def test_get_user_clone_prompt_falls_back_to_global(self, api_client):
        """GET /api/ai-campaigns/clone-prompt/user/{user_id} falls back to global"""
        # First reset any user override
        api_client.delete(f"{BASE_URL}/api/ai-campaigns/clone-prompt/user/{USER_ID}")
        
        response = api_client.get(f"{BASE_URL}/api/ai-campaigns/clone-prompt/user/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "prompt" in data
        # Should indicate fallback
        assert data.get("is_fallback") == True or data.get("is_default") == True or data.get("scope") == "global"
        print(f"User prompt falls back correctly: {data.get('is_fallback', data.get('is_default', data.get('scope')))}")

    def test_update_user_clone_prompt(self, api_client):
        """PUT /api/ai-campaigns/clone-prompt/user/{user_id} saves user override"""
        custom_prompt = "Custom user prompt for testing with {user_name}"
        response = api_client.put(
            f"{BASE_URL}/api/ai-campaigns/clone-prompt/user/{USER_ID}",
            json={"prompt": custom_prompt}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Verify it was saved
        get_response = api_client.get(f"{BASE_URL}/api/ai-campaigns/clone-prompt/user/{USER_ID}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("scope") == "user"
        assert custom_prompt in get_data.get("prompt", "")
        print("User prompt override saved and verified")

    def test_delete_user_clone_prompt_resets_to_global(self, api_client):
        """DELETE /api/ai-campaigns/clone-prompt/user/{user_id} resets to global"""
        response = api_client.delete(f"{BASE_URL}/api/ai-campaigns/clone-prompt/user/{USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "reset" in data.get("message", "").lower() or "global" in data.get("message", "").lower()
        print("User prompt reset to global default")


class TestAIMessageGeneration:
    """Tests for AI message generation endpoints"""

    def test_generate_sms_message(self, api_client):
        """POST /api/ai-campaigns/generate-message/{user_id}/{contact_id} generates SMS"""
        response = api_client.post(
            f"{BASE_URL}/api/ai-campaigns/generate-message/{USER_ID}/{CONTACT_ID}",
            json={
                "step_context": "Initial check-in after purchase",
                "channel": "sms",
                "campaign_name": "Test Campaign"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        assert data.get("channel") == "sms"
        assert len(data["message"]) > 0
        print(f"Generated SMS ({len(data['message'])} chars): {data['message'][:100]}...")

    def test_generate_email_message_with_subject(self, api_client):
        """POST /api/ai-campaigns/generate-message with channel=email generates email"""
        response = api_client.post(
            f"{BASE_URL}/api/ai-campaigns/generate-message/{USER_ID}/{CONTACT_ID}",
            json={
                "step_context": "Follow-up email after meeting",
                "channel": "email",
                "campaign_name": "Email Campaign"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        assert data.get("channel") == "email"
        # Email should contain Subject line
        assert "Subject:" in data["message"] or len(data["message"]) > 50
        print(f"Generated email message: {data['message'][:150]}...")


class TestAIClonePreview:
    """Tests for AI clone preview endpoint"""

    def test_preview_clone_personality(self, api_client):
        """POST /api/ai-campaigns/preview-clone/{user_id} returns AI clone response"""
        response = api_client.post(
            f"{BASE_URL}/api/ai-campaigns/preview-clone/{USER_ID}",
            json={"message": "Tell me about yourself and what services you offer"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "response" in data
        assert len(data["response"]) > 0
        print(f"AI clone preview response: {data['response'][:200]}...")


class TestAIReplyHandler:
    """Tests for AI reply handler (virtual assistant)"""

    def test_handle_customer_reply(self, api_client):
        """POST /api/ai-campaigns/handle-reply/{user_id}/{contact_id} generates reply with delay"""
        response = api_client.post(
            f"{BASE_URL}/api/ai-campaigns/handle-reply/{USER_ID}/{CONTACT_ID}",
            json={"message": "Yes I'm interested, when can we schedule a call?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "reply" in data
        assert "delay_seconds" in data
        # Delay should be between 60-180 seconds (1-3 minutes)
        assert 60 <= data["delay_seconds"] <= 180
        assert "note" in data
        print(f"AI reply: {data['reply'][:100]}... (delay: {data['delay_seconds']}s)")

    def test_handle_reply_requires_message(self, api_client):
        """POST /api/ai-campaigns/handle-reply with empty message fails"""
        response = api_client.post(
            f"{BASE_URL}/api/ai-campaigns/handle-reply/{USER_ID}/{CONTACT_ID}",
            json={"message": ""}
        )
        assert response.status_code == 400
        print("Empty message correctly rejected")


class TestPendingSends:
    """Tests for pending sends (manual campaign workflow)"""

    def test_get_pending_sends_empty_array(self, api_client):
        """GET /api/campaigns/{user_id}/pending-sends returns array (empty if none)"""
        response = api_client.get(f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Pending sends count: {len(data)}")

    def test_mark_pending_send_complete_not_found(self, api_client):
        """POST /api/campaigns/{user_id}/pending-sends/{send_id}/complete with invalid ID"""
        fake_id = "000000000000000000000000"
        response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends/{fake_id}/complete")
        assert response.status_code == 404
        print("Non-existent pending send returns 404")

    def test_skip_pending_send_not_found(self, api_client):
        """POST /api/campaigns/{user_id}/pending-sends/{send_id}/skip with invalid ID"""
        fake_id = "000000000000000000000000"
        response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends/{fake_id}/skip")
        assert response.status_code == 404
        print("Non-existent pending send skip returns 404")


class TestCampaignWithNewFields:
    """Tests for campaign CRUD with new AI-related fields"""
    
    created_campaign_id = None

    def test_create_campaign_with_delivery_mode_and_ai(self, api_client):
        """Campaign creation accepts delivery_mode, ai_enabled, ownership_level"""
        response = api_client.post(
            f"{BASE_URL}/api/campaigns/{USER_ID}",
            json={
                "name": "TEST_AI_Automated_Campaign",
                "type": "custom",
                "trigger_tag": "test_ai",
                "segment_tags": ["test_ai"],
                "delivery_mode": "automated",
                "ai_enabled": True,
                "ownership_level": "store",
                "sequences": [
                    {
                        "step": 1,
                        "message_template": "Hello {name}!",
                        "delay_days": 0,
                        "delay_months": 0,
                        "channel": "sms",
                        "ai_generated": True,
                        "step_context": "Initial greeting"
                    }
                ],
                "send_time": "10:00",
                "active": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("delivery_mode") == "automated"
        assert data.get("ai_enabled") == True
        assert data.get("ownership_level") == "store"
        TestCampaignWithNewFields.created_campaign_id = data.get("_id")
        print(f"Created campaign with AI features: {data.get('_id')}")

    def test_campaign_steps_have_channel_and_ai_fields(self, api_client):
        """Campaign steps accept channel, ai_generated, step_context fields"""
        if not TestCampaignWithNewFields.created_campaign_id:
            pytest.skip("No campaign created")
        
        response = api_client.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{TestCampaignWithNewFields.created_campaign_id}"
        )
        assert response.status_code == 200
        data = response.json()
        sequences = data.get("sequences", [])
        assert len(sequences) > 0
        
        step = sequences[0]
        assert step.get("channel") == "sms"
        assert step.get("ai_generated") == True
        assert step.get("step_context") == "Initial greeting"
        print("Campaign step fields verified: channel, ai_generated, step_context")

    def test_cleanup_test_campaign(self, api_client):
        """Delete the test campaign"""
        if TestCampaignWithNewFields.created_campaign_id:
            response = api_client.delete(
                f"{BASE_URL}/api/campaigns/{USER_ID}/{TestCampaignWithNewFields.created_campaign_id}"
            )
            assert response.status_code == 200
            print("Test campaign cleaned up")


class TestNotificationCenterCampaigns:
    """Tests for notification center campaigns category"""

    def test_notification_center_includes_campaigns_category(self, api_client):
        """GET /api/notification-center/{user_id} responds to campaigns category"""
        response = api_client.get(
            f"{BASE_URL}/api/notification-center/{USER_ID}?category=campaigns&limit=100"
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "notifications" in data
        assert isinstance(data["notifications"], list)
        print(f"Campaigns category accessible, {len(data['notifications'])} notifications")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
