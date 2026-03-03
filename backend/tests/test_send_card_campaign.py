"""
Test suite for Send Card campaign feature
Tests: action_type and card_type fields in campaigns, scheduler pending sends creation
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imonsocial.com"
TEST_PASSWORD = "Admin123!"
USER_ID = "69a0b7095fddcede09591667"
CAMPAIGN_ID = "69a27569d1bc10a69de0c9d6"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("token")


@pytest.fixture
def api_client(auth_token):
    """Session with auth headers"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestCampaignModelFields:
    """Verify CampaignSequenceStep model has action_type and card_type fields"""
    
    def test_get_campaign_has_sequences(self, api_client):
        """GET campaign and verify sequences structure"""
        response = api_client.get(f"{BASE_URL}/api/campaigns/{USER_ID}/{CAMPAIGN_ID}")
        assert response.status_code == 200, f"Failed to get campaign: {response.text}"
        
        data = response.json()
        assert "sequences" in data, "Campaign should have sequences field"
        assert isinstance(data["sequences"], list), "sequences should be a list"
        print(f"Campaign '{data.get('name')}' has {len(data['sequences'])} steps")
    
    def test_create_campaign_with_card_step(self, api_client):
        """Create a campaign with a send_card step and verify action_type and card_type are saved"""
        campaign_payload = {
            "name": "TEST_Card_Campaign_" + datetime.utcnow().strftime("%H%M%S"),
            "type": "custom",
            "trigger_tag": "test_card",
            "segment_tags": [],
            "send_time": "10:00",
            "active": True,
            "delivery_mode": "manual",
            "ai_enabled": False,
            "sequences": [
                {
                    "step": 1,
                    "action_type": "send_card",
                    "card_type": "birthday",
                    "message_template": "",
                    "delay_days": 0,
                    "delay_months": 0,
                    "media_urls": [],
                    "channel": "sms"
                },
                {
                    "step": 2,
                    "action_type": "message",
                    "card_type": "",
                    "message_template": "Follow-up message after the card",
                    "delay_days": 3,
                    "delay_months": 0,
                    "media_urls": [],
                    "channel": "sms"
                }
            ]
        }
        
        response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}", json=campaign_payload)
        assert response.status_code == 200 or response.status_code == 201, f"Failed to create campaign: {response.text}"
        
        data = response.json()
        assert "sequences" in data, "Created campaign should have sequences"
        assert len(data["sequences"]) == 2, "Should have 2 steps"
        
        # Verify step 1 is send_card with birthday
        step1 = data["sequences"][0]
        assert step1.get("action_type") == "send_card", f"Step 1 action_type should be 'send_card', got {step1.get('action_type')}"
        assert step1.get("card_type") == "birthday", f"Step 1 card_type should be 'birthday', got {step1.get('card_type')}"
        
        # Verify step 2 is message
        step2 = data["sequences"][1]
        assert step2.get("action_type") == "message", f"Step 2 action_type should be 'message', got {step2.get('action_type')}"
        
        print(f"Campaign created with card step: {data.get('name')}")
        
        # Clean up - delete the test campaign
        campaign_id = str(data.get("_id"))
        if campaign_id:
            api_client.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}")
    
    def test_update_campaign_with_card_step(self, api_client):
        """Update existing campaign to add action_type and card_type"""
        update_payload = {
            "name": "Updated Test Campaign with Card",
            "sequences": [
                {
                    "step": 1,
                    "action_type": "send_card",
                    "card_type": "congrats",
                    "message_template": "",
                    "delay_days": 0,
                    "delay_months": 0,
                    "media_urls": [],
                    "channel": "sms"
                },
                {
                    "step": 2,
                    "action_type": "send_card",
                    "card_type": "thankyou",
                    "message_template": "",
                    "delay_days": 7,
                    "delay_months": 0,
                    "media_urls": [],
                    "channel": "sms"
                }
            ]
        }
        
        response = api_client.put(f"{BASE_URL}/api/campaigns/{USER_ID}/{CAMPAIGN_ID}", json=update_payload)
        assert response.status_code == 200, f"Failed to update campaign: {response.text}"
        
        # Verify the update by fetching the campaign
        get_response = api_client.get(f"{BASE_URL}/api/campaigns/{USER_ID}/{CAMPAIGN_ID}")
        assert get_response.status_code == 200, f"Failed to get updated campaign: {get_response.text}"
        
        data = get_response.json()
        assert len(data["sequences"]) == 2, "Should have 2 steps"
        
        step1 = data["sequences"][0]
        assert step1.get("action_type") == "send_card", f"Step 1 action_type should be 'send_card'"
        assert step1.get("card_type") == "congrats", f"Step 1 card_type should be 'congrats'"
        
        step2 = data["sequences"][1]
        assert step2.get("action_type") == "send_card", f"Step 2 action_type should be 'send_card'"
        assert step2.get("card_type") == "thankyou", f"Step 2 card_type should be 'thankyou'"
        
        print("Campaign updated with card steps successfully")


class TestCardTypeVariants:
    """Test all 6 card type variants: congrats, birthday, anniversary, thankyou, welcome, holiday"""
    
    CARD_TYPES = ["congrats", "birthday", "anniversary", "thankyou", "welcome", "holiday"]
    
    def test_all_card_types_in_campaign(self, api_client):
        """Create campaign with all 6 card types to verify they are accepted"""
        sequences = []
        for idx, card_type in enumerate(self.CARD_TYPES):
            sequences.append({
                "step": idx + 1,
                "action_type": "send_card",
                "card_type": card_type,
                "message_template": "",
                "delay_days": idx * 7,
                "delay_months": 0,
                "media_urls": [],
                "channel": "sms"
            })
        
        campaign_payload = {
            "name": "TEST_All_Card_Types_" + datetime.utcnow().strftime("%H%M%S"),
            "type": "custom",
            "trigger_tag": "test_all_cards",
            "send_time": "10:00",
            "active": False,  # Keep inactive to not trigger
            "delivery_mode": "manual",
            "sequences": sequences
        }
        
        response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}", json=campaign_payload)
        assert response.status_code in [200, 201], f"Failed to create campaign: {response.text}"
        
        data = response.json()
        assert len(data["sequences"]) == 6, f"Should have 6 steps, got {len(data['sequences'])}"
        
        # Verify each card type is correctly saved
        for idx, card_type in enumerate(self.CARD_TYPES):
            step = data["sequences"][idx]
            assert step.get("card_type") == card_type, f"Step {idx+1} card_type should be '{card_type}'"
            print(f"✓ Card type '{card_type}' verified in step {idx+1}")
        
        # Clean up
        campaign_id = str(data.get("_id"))
        if campaign_id:
            api_client.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}")


class TestSchedulerTrigger:
    """Test scheduler creates pending sends with action_type and card_type for send_card steps"""
    
    def test_scheduler_trigger_endpoint(self, api_client):
        """Trigger scheduler and verify it processes enrollments"""
        response = api_client.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        assert response.status_code == 200, f"Scheduler trigger failed: {response.text}"
        
        data = response.json()
        assert "processed" in data, "Response should contain 'processed' field"
        assert "pending_found" in data, "Response should contain 'pending_found' field"
        print(f"Scheduler: processed {data.get('processed')}, found {data.get('pending_found')} pending")
    
    def test_pending_sends_endpoint(self, api_client):
        """Get pending sends and verify structure supports action_type and card_type"""
        response = api_client.get(f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends")
        assert response.status_code == 200, f"Failed to get pending sends: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Pending sends should be a list"
        
        # Log details about pending sends
        card_sends = [p for p in data if p.get("action_type") == "send_card"]
        message_sends = [p for p in data if p.get("action_type") != "send_card"]
        print(f"Pending sends: {len(data)} total, {len(card_sends)} card tasks, {len(message_sends)} message tasks")
        
        # If there are card sends, verify they have card_type
        for card_send in card_sends:
            assert "card_type" in card_send, f"Card send should have card_type field"
            print(f"  - Card send for '{card_send.get('contact_name')}': {card_send.get('card_type')} card")


class TestCampaignUpdatePayload:
    """Test that campaign update accepts action_type and card_type in sequences"""
    
    def test_update_with_mixed_steps(self, api_client):
        """Update campaign with both message and card steps"""
        update_payload = {
            "sequences": [
                {
                    "step": 1,
                    "action_type": "message",
                    "card_type": "",
                    "message_template": "Hello {name}! This is step 1.",
                    "delay_days": 0,
                    "delay_months": 0,
                    "media_urls": [],
                    "channel": "sms"
                },
                {
                    "step": 2,
                    "action_type": "send_card",
                    "card_type": "holiday",
                    "message_template": "",
                    "delay_days": 0,
                    "delay_months": 1,
                    "media_urls": [],
                    "channel": "sms"
                },
                {
                    "step": 3,
                    "action_type": "message",
                    "card_type": "",
                    "message_template": "Following up {name}...",
                    "delay_days": 7,
                    "delay_months": 1,
                    "media_urls": [],
                    "channel": "sms"
                }
            ]
        }
        
        response = api_client.put(f"{BASE_URL}/api/campaigns/{USER_ID}/{CAMPAIGN_ID}", json=update_payload)
        assert response.status_code == 200, f"Failed to update campaign: {response.text}"
        
        # Verify
        get_response = api_client.get(f"{BASE_URL}/api/campaigns/{USER_ID}/{CAMPAIGN_ID}")
        data = get_response.json()
        
        assert len(data["sequences"]) == 3, f"Should have 3 steps, got {len(data['sequences'])}"
        
        # Step 1 = message
        assert data["sequences"][0].get("action_type") == "message"
        # Step 2 = send_card with holiday
        assert data["sequences"][1].get("action_type") == "send_card"
        assert data["sequences"][1].get("card_type") == "holiday"
        # Step 3 = message
        assert data["sequences"][2].get("action_type") == "message"
        
        print("Campaign updated with mixed message and card steps successfully")


# No cleanup fixture needed - tests are independent
