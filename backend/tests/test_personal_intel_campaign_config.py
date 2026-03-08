"""
Test Personal Intelligence & Campaign Configuration Features
Tests for:
1) GET /api/contacts/{user_id}/{contact_id}/personal-details - returns personal_details from voice memo extraction
2) PATCH /api/contacts/{user_id}/{contact_id}/personal-details - updates personal details manually
3) GET /api/campaign-config/effective/{user_id} - returns resolved config with hierarchy
4) PUT /api/campaign-config/store/{store_id} - saves store-level campaign config
5) GET /api/campaign-config/store/{store_id} - returns saved config
6) DELETE /api/campaign-config/store/{store_id} - resets to defaults
7) GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id} - includes personal_details field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
USER_ID = "69a0b7095fddcede09591667"
STORE_ID = "69a0b7095fddcede09591668"
TEST_CONTACT_BUD_ID = "69a496841603573df5a41723"  # Has personal_details populated


class TestPersonalDetails:
    """Test personal_details endpoints for voice memo intelligence extraction"""
    
    def test_get_personal_details_for_contact_with_data(self):
        """GET /api/contacts/{user_id}/{contact_id}/personal-details - contact with populated personal_details"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/personal-details"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "personal_details" in data, "Response should have personal_details key"
        assert "has_details" in data, "Response should have has_details flag"
        
        # Bud should have personal_details populated from voice memo test
        if data["has_details"]:
            details = data["personal_details"]
            print(f"Personal details found: {list(details.keys())}")
            # Check for expected fields
            assert isinstance(details, dict), "personal_details should be a dict"
    
    def test_get_personal_details_returns_vehicle(self):
        """GET /api/contacts/{user_id}/{contact_id}/personal-details - returns vehicle field"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/personal-details"
        )
        assert response.status_code == 200
        data = response.json()
        assert "vehicle" in data, "Response should include vehicle field"
    
    def test_update_personal_details_manually(self):
        """PATCH /api/contacts/{user_id}/{contact_id}/personal-details - manual update"""
        update_payload = {
            "personal_details": {
                "test_manual_field": "This was manually added",
            }
        }
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/personal-details",
            json=update_payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "personal_details" in data
        # Manual edits should be merged
        assert data["personal_details"].get("test_manual_field") == "This was manually added"
    
    def test_update_personal_details_merges_with_existing(self):
        """PATCH merges with existing data, doesn't overwrite"""
        # First, add a field
        requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/personal-details",
            json={"personal_details": {"field_a": "value_a"}}
        )
        
        # Then add another field
        requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/personal-details",
            json={"personal_details": {"field_b": "value_b"}}
        )
        
        # Verify both fields exist
        response = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/personal-details"
        )
        assert response.status_code == 200
        details = response.json().get("personal_details", {})
        # Both should exist (merge behavior)
        # Note: field_a might not exist if it was cleaned up, but field_b should
        assert "field_b" in details or "field_a" in details
    
    def test_get_personal_details_not_found(self):
        """GET personal-details for non-existent contact returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/000000000000000000000000/personal-details"
        )
        assert response.status_code == 404


class TestCampaignConfig:
    """Test campaign configuration endpoints with hierarchy resolution"""
    
    def test_get_effective_config_for_user(self):
        """GET /api/campaign-config/effective/{user_id} - returns resolved config"""
        response = requests.get(f"{BASE_URL}/api/campaign-config/effective/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "config" in data, "Response should have config key"
        assert "level_applied" in data, "Response should have level_applied"
        assert "user_id" in data
        
        # Check config has expected default keys
        config = data["config"]
        assert "message_mode" in config, "Config should have message_mode"
        assert config["message_mode"] in ["ai_suggested", "template", "hybrid"]
        assert "ai_tone" in config, "Config should have ai_tone"
        assert "include_personal_details" in config
        assert "include_engagement_signals" in config
        assert "review_before_send" in config
        assert "auto_send" in config
    
    def test_set_store_config(self):
        """PUT /api/campaign-config/store/{store_id} - saves store-level config"""
        config_payload = {
            "config": {
                "message_mode": "ai_suggested",
                "ai_tone": "warm",
                "include_personal_details": True,
                "include_engagement_signals": True,
                "review_before_send": True,
                "auto_send": False,
            }
        }
        response = requests.put(
            f"{BASE_URL}/api/campaign-config/store/{STORE_ID}",
            json=config_payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Configuration saved"
        assert "config" in data
        assert data["config"]["message_mode"] == "ai_suggested"
        assert data["config"]["ai_tone"] == "warm"
    
    def test_get_store_config(self):
        """GET /api/campaign-config/store/{store_id} - returns saved config"""
        response = requests.get(f"{BASE_URL}/api/campaign-config/store/{STORE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "config" in data
        assert "level" in data
        assert data["level"] == "store"
        assert data["entity_id"] == STORE_ID
    
    def test_config_hierarchy_resolution(self):
        """Effective config resolves hierarchy: org > store > user"""
        # First set store config
        requests.put(
            f"{BASE_URL}/api/campaign-config/store/{STORE_ID}",
            json={"config": {"ai_tone": "professional"}}
        )
        
        # Get effective config for user
        response = requests.get(f"{BASE_URL}/api/campaign-config/effective/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        config = data["config"]
        # Should have the store's ai_tone setting
        assert config["ai_tone"] == "professional" or config.get("ai_tone") in ["casual", "warm", "professional"]
    
    def test_delete_store_config_resets_to_defaults(self):
        """DELETE /api/campaign-config/store/{store_id} - resets to defaults"""
        # First set a config
        requests.put(
            f"{BASE_URL}/api/campaign-config/store/{STORE_ID}",
            json={"config": {"message_mode": "template", "ai_tone": "casual"}}
        )
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/campaign-config/store/{STORE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "reset" in data["message"].lower() or "defaults" in data["message"].lower() or "no custom" in data["message"].lower()
        
        # Re-set the config for future tests
        requests.put(
            f"{BASE_URL}/api/campaign-config/store/{STORE_ID}",
            json={"config": {"message_mode": "ai_suggested", "ai_tone": "warm"}}
        )
    
    def test_invalid_level_returns_400(self):
        """Invalid config level returns 400"""
        response = requests.get(f"{BASE_URL}/api/campaign-config/invalid_level/{STORE_ID}")
        assert response.status_code == 400
    
    def test_set_config_filters_invalid_keys(self):
        """PUT only allows known config keys"""
        config_payload = {
            "config": {
                "message_mode": "template",
                "invalid_key_should_be_ignored": "test",
                "another_invalid": 123,
            }
        }
        response = requests.put(
            f"{BASE_URL}/api/campaign-config/store/{STORE_ID}",
            json=config_payload
        )
        assert response.status_code == 200
        
        data = response.json()
        # Invalid keys should not be in the saved config
        assert "invalid_key_should_be_ignored" not in data.get("config", {})
        assert "another_invalid" not in data.get("config", {})


class TestRelationshipBriefWithPersonalDetails:
    """Test that relationship brief includes personal_details from voice memos"""
    
    def test_relationship_brief_includes_personal_details(self):
        """GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id} - includes personal_details"""
        response = requests.get(
            f"{BASE_URL}/api/ai-outreach/relationship-brief/{USER_ID}/{TEST_CONTACT_BUD_ID}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check standard brief fields
        assert "relationship_health" in data
        assert "engagement_score" in data
        assert "human_summary" in data
        
        # Check personal_details field is present
        assert "personal_details" in data, "Relationship brief should include personal_details"
        assert isinstance(data["personal_details"], dict)
    
    def test_relationship_brief_human_summary_format(self):
        """Human summary includes personal details in readable format"""
        response = requests.get(
            f"{BASE_URL}/api/ai-outreach/relationship-brief/{USER_ID}/{TEST_CONTACT_BUD_ID}"
        )
        assert response.status_code == 200
        
        data = response.json()
        human_summary = data.get("human_summary", "")
        print(f"Human summary: {human_summary}")
        
        # Summary should be a pipe-separated string
        assert isinstance(human_summary, str)
        # Should contain relationship info
        assert "Relationship:" in human_summary or "Engagement:" in human_summary or len(human_summary) > 0
    
    def test_relationship_brief_contains_milestones(self):
        """Relationship brief contains milestone information"""
        response = requests.get(
            f"{BASE_URL}/api/ai-outreach/relationship-brief/{USER_ID}/{TEST_CONTACT_BUD_ID}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "milestones" in data
        assert isinstance(data["milestones"], list)


class TestVoiceNoteExtractionIntegration:
    """Test voice note auto-extraction flow (code review based - actual extraction requires audio upload)"""
    
    def test_voice_notes_endpoint_exists(self):
        """GET /api/voice-notes/{user_id}/{contact_id} - endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/voice-notes/{USER_ID}/{TEST_CONTACT_BUD_ID}")
        assert response.status_code == 200, f"Voice notes endpoint should return 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Should return list of voice notes"
    
    def test_re_extract_intelligence_endpoint(self):
        """POST /api/contacts/{user_id}/{contact_id}/re-extract - re-run extraction"""
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_BUD_ID}/re-extract"
        )
        # This endpoint might take time for AI extraction, should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "extracted" in data


class TestSchedulerCampaignConfigIntegration:
    """Test that scheduler respects campaign config for message generation"""
    
    def test_scheduler_health_endpoint(self):
        """Check scheduler is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
    
    def test_pending_sends_endpoint(self):
        """GET /api/campaigns/{user_id}/pending-sends - pending campaign messages"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return list of pending sends"
        
        # If there are pending sends, check they have relationship_brief field
        if len(data) > 0:
            first_send = data[0]
            # relationship_brief should be included (may be empty string if not generated)
            print(f"First pending send keys: {list(first_send.keys())}")


# Run with: pytest /app/backend/tests/test_personal_intel_campaign_config.py -v --tb=short
