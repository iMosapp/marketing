"""
Test campaign creation API endpoints
Tests POST /api/campaigns/{user_id} and GET /api/campaigns/{user_id}
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestCampaignCreationAPI:
    """Test campaign CRUD operations"""
    
    def test_create_campaign_with_valid_data(self):
        """Create a campaign with all required fields"""
        campaign_name = f"TEST_Campaign_{int(time.time())}"
        payload = {
            "name": campaign_name,
            "type": "tag",
            "trigger_tag": "Sold",
            "segment_tags": ["Sold"],
            "sequences": [
                {
                    "step": 1,
                    "message_template": "Hello {name}! This is a test message.",
                    "delay_days": 0,
                    "delay_hours": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "ai_generated": False
                }
            ],
            "send_time": "10:00",
            "active": True,
            "delivery_mode": "manual",
            "ai_enabled": False
        }
        
        response = requests.post(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == campaign_name
        assert data["type"] == "tag"
        assert data["trigger_tag"] == "Sold"
        assert data["user_id"] == TEST_USER_ID
        assert len(data["sequences"]) == 1
        assert "_id" in data
        print(f"Created campaign: {data['_id']}")
    
    def test_create_campaign_with_multiple_sequences(self):
        """Create a campaign with multiple message sequences"""
        campaign_name = f"TEST_MultiSeq_{int(time.time())}"
        payload = {
            "name": campaign_name,
            "type": "tag",
            "trigger_tag": "VIP",
            "segment_tags": ["VIP"],
            "sequences": [
                {
                    "step": 1,
                    "message_template": "Welcome {name}!",
                    "delay_days": 0,
                    "delay_hours": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "ai_generated": False
                },
                {
                    "step": 2,
                    "message_template": "Follow-up message for {name}",
                    "delay_days": 7,
                    "delay_hours": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "ai_generated": True,
                    "step_context": "Check in after 1 week"
                }
            ],
            "send_time": "09:00",
            "active": True,
            "delivery_mode": "manual",
            "ai_enabled": True
        }
        
        response = requests.post(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["sequences"]) == 2
        assert data["sequences"][0]["step"] == 1
        assert data["sequences"][1]["step"] == 2
        assert data["ai_enabled"] == True
        print(f"Created multi-sequence campaign: {data['_id']}")
    
    def test_get_campaign_list(self):
        """Get all campaigns for user"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} campaigns for user")
    
    def test_get_prebuilt_templates(self):
        """Get prebuilt campaign templates"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify "Sold - Complete Follow-Up" template exists
        sold_template = next((t for t in data if t["id"] == "sold_followup"), None)
        assert sold_template is not None, "Sold followup template not found"
        assert sold_template["trigger_tag"] == "sold"
        print(f"Found {len(data)} prebuilt templates")
    
    def test_get_specific_template(self):
        """Get a specific prebuilt template with full details"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/sold_followup")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Sold - Complete Follow-Up"
        assert data["trigger_tag"] == "sold"
        assert len(data["sequences"]) == 5  # 5 steps in this template
        print(f"Template has {len(data['sequences'])} sequences")
    
    def test_tags_api(self):
        """Test tags API returns tags for user"""
        response = requests.get(f"{BASE_URL}/api/tags/{TEST_USER_ID}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Check for common tags
        tag_names = [t.get("name", t) for t in data]
        assert len(tag_names) > 0, "No tags found"
        print(f"Found {len(tag_names)} tags: {tag_names[:5]}...")


class TestCampaignValidation:
    """Test campaign validation rules"""
    
    def test_create_campaign_duplicate_prevention(self):
        """Creating duplicate campaign should return existing"""
        campaign_name = f"TEST_Duplicate_{int(time.time())}"
        payload = {
            "name": campaign_name,
            "type": "tag",
            "trigger_tag": "Sold",
            "sequences": [{"step": 1, "message_template": "Test", "delay_days": 0}],
            "send_time": "10:00",
            "active": True
        }
        
        # First create
        response1 = requests.post(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}", json=payload)
        assert response1.status_code == 200
        campaign_id_1 = response1.json()["_id"]
        
        # Second create with same name+type should return existing
        response2 = requests.post(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}", json=payload)
        assert response2.status_code == 200
        campaign_id_2 = response2.json()["_id"]
        
        assert campaign_id_1 == campaign_id_2, "Duplicate campaign created instead of returning existing"
        print(f"Duplicate prevention working correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
