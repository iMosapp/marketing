"""
Test Messaging Channels API — Configures which share channels are available per organization.
Tests: GET /api/messaging-channels/available, GET/PUT /api/messaging-channels/org/{org_id}, GET /api/messaging-channels/user/{user_id}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_ORG_ID = "69a907033b77512d1d8d8a08"  # Valid org ID from test context
TEST_USER_ID = "69a0b7095fddcede09591667"  # Valid user ID from test context
INVALID_ORG_ID = "invalid_id_format"
INVALID_USER_ID = "invalid_user_id"
NONEXISTENT_ORG_ID = "000000000000000000000000"
NONEXISTENT_USER_ID = "000000000000000000000000"

# All 7 available channels
AVAILABLE_CHANNEL_IDS = ["sms", "whatsapp", "messenger", "telegram", "linkedin", "email", "clipboard"]


class TestMessagingChannelsAvailable:
    """Tests for GET /api/messaging-channels/available endpoint"""
    
    def test_get_available_channels_returns_all_7(self):
        """GET /api/messaging-channels/available returns all 7 channels"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/available")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 7, f"Expected 7 channels, got {len(data)}"
        
        # Verify all channel IDs are present
        channel_ids = [ch["id"] for ch in data]
        for expected_id in AVAILABLE_CHANNEL_IDS:
            assert expected_id in channel_ids, f"Missing channel: {expected_id}"
        
        print(f"PASS: All 7 channels returned: {channel_ids}")
    
    def test_available_channels_have_required_fields(self):
        """Each available channel has required fields: id, name, icon, color, description, url_scheme, requires_phone"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/available")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["id", "name", "icon", "color", "description", "url_scheme", "requires_phone"]
        for channel in data:
            for field in required_fields:
                assert field in channel, f"Channel {channel.get('id', 'unknown')} missing field: {field}"
        
        print(f"PASS: All channels have required fields")
    
    def test_sms_channel_metadata(self):
        """SMS/iMessage channel has correct metadata"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/available")
        
        assert response.status_code == 200
        data = response.json()
        
        sms_channel = next((ch for ch in data if ch["id"] == "sms"), None)
        assert sms_channel is not None, "SMS channel not found"
        assert sms_channel["name"] == "SMS / iMessage"
        assert sms_channel["color"] == "#34C759"
        assert sms_channel["requires_phone"] == True
        
        print(f"PASS: SMS channel metadata correct")
    
    def test_whatsapp_channel_metadata(self):
        """WhatsApp channel has correct metadata"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/available")
        
        assert response.status_code == 200
        data = response.json()
        
        whatsapp_channel = next((ch for ch in data if ch["id"] == "whatsapp"), None)
        assert whatsapp_channel is not None, "WhatsApp channel not found"
        assert whatsapp_channel["name"] == "WhatsApp"
        assert whatsapp_channel["color"] == "#25D366"
        assert whatsapp_channel["requires_phone"] == True
        assert "wa.me" in whatsapp_channel["url_scheme"]
        
        print(f"PASS: WhatsApp channel metadata correct")


class TestMessagingChannelsOrg:
    """Tests for GET/PUT /api/messaging-channels/org/{org_id} endpoints"""
    
    def test_get_org_channels_success(self):
        """GET /api/messaging-channels/org/{org_id} returns current org config"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "org_id" in data, "Response should include org_id"
        assert "enabled_channels" in data, "Response should include enabled_channels"
        assert "available" in data, "Response should include available channels"
        
        assert data["org_id"] == TEST_ORG_ID
        assert isinstance(data["enabled_channels"], list)
        assert len(data["available"]) == 7, "Should return all 7 available channels"
        
        print(f"PASS: Org channels returned - enabled: {data['enabled_channels']}")
    
    def test_get_org_channels_invalid_id(self):
        """GET /api/messaging-channels/org/{invalid_id} returns 400"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{INVALID_ORG_ID}")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"PASS: Invalid org ID returns 400")
    
    def test_get_org_channels_nonexistent(self):
        """GET /api/messaging-channels/org/{nonexistent_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{NONEXISTENT_ORG_ID}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"PASS: Nonexistent org ID returns 404")
    
    def test_update_org_channels_enable_whatsapp(self):
        """PUT /api/messaging-channels/org/{org_id} enables WhatsApp"""
        # First get current config
        get_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        original_channels = get_response.json().get("enabled_channels", ["sms"])
        
        # Enable SMS and WhatsApp
        new_channels = ["sms", "whatsapp"]
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": new_channels}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "updated"
        assert "sms" in data["enabled_channels"]
        assert "whatsapp" in data["enabled_channels"]
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        assert "whatsapp" in verify_response.json()["enabled_channels"]
        
        # Restore original channels
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": original_channels}
        )
        
        print(f"PASS: WhatsApp enabled and verified")
    
    def test_update_org_channels_multiple(self):
        """PUT /api/messaging-channels/org/{org_id} enables multiple channels"""
        # Get current config
        get_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        original_channels = get_response.json().get("enabled_channels", ["sms"])
        
        # Enable 4 channels
        new_channels = ["sms", "whatsapp", "email", "clipboard"]
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": new_channels}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["enabled_channels"]) == 4
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": original_channels}
        )
        
        print(f"PASS: Multiple channels updated")
    
    def test_update_org_channels_invalid_channel_id(self):
        """PUT /api/messaging-channels/org/{org_id} with invalid channel ID returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": ["sms", "invalid_channel_xyz"]}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "Invalid channel IDs" in response.json().get("detail", "")
        
        print(f"PASS: Invalid channel ID returns 400")
    
    def test_update_org_channels_invalid_org_id(self):
        """PUT /api/messaging-channels/org/{invalid_id} returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{INVALID_ORG_ID}",
            json={"channels": ["sms"]}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"PASS: Invalid org ID on PUT returns 400")
    
    def test_update_org_channels_nonexistent_org(self):
        """PUT /api/messaging-channels/org/{nonexistent_id} returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{NONEXISTENT_ORG_ID}",
            json={"channels": ["sms"]}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"PASS: Nonexistent org ID on PUT returns 404")


class TestMessagingChannelsUser:
    """Tests for GET /api/messaging-channels/user/{user_id} endpoint"""
    
    def test_get_user_channels_success(self):
        """GET /api/messaging-channels/user/{user_id} returns channels based on org config"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/user/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Response should include user_id"
        assert "enabled_channels" in data, "Response should include enabled_channels"
        assert "channels" in data, "Response should include channels with full metadata"
        
        assert data["user_id"] == TEST_USER_ID
        assert isinstance(data["enabled_channels"], list)
        assert isinstance(data["channels"], list)
        
        # Verify channels have metadata
        if data["channels"]:
            ch = data["channels"][0]
            assert "id" in ch
            assert "name" in ch
            assert "icon" in ch
            assert "color" in ch
        
        print(f"PASS: User channels returned - enabled: {data['enabled_channels']}")
    
    def test_get_user_channels_invalid_id(self):
        """GET /api/messaging-channels/user/{invalid_id} returns 400"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/user/{INVALID_USER_ID}")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"PASS: Invalid user ID returns 400")
    
    def test_get_user_channels_nonexistent(self):
        """GET /api/messaging-channels/user/{nonexistent_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/messaging-channels/user/{NONEXISTENT_USER_ID}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"PASS: Nonexistent user ID returns 404")
    
    def test_user_channels_reflect_org_config(self):
        """User channels reflect org config after org update"""
        # Enable WhatsApp for org
        original_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        original_channels = original_response.json().get("enabled_channels", ["sms"])
        
        # Update org to have SMS + WhatsApp
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": ["sms", "whatsapp"]}
        )
        
        # Check user channels reflect update
        user_response = requests.get(f"{BASE_URL}/api/messaging-channels/user/{TEST_USER_ID}")
        assert user_response.status_code == 200
        
        user_data = user_response.json()
        assert "sms" in user_data["enabled_channels"]
        assert "whatsapp" in user_data["enabled_channels"]
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": original_channels}
        )
        
        print(f"PASS: User channels reflect org config")


class TestMessagingChannelsEdgeCases:
    """Edge case tests for messaging channels API"""
    
    def test_enable_all_channels(self):
        """Can enable all 7 channels at once"""
        original_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        original_channels = original_response.json().get("enabled_channels", ["sms"])
        
        # Enable all channels
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": AVAILABLE_CHANNEL_IDS}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["enabled_channels"]) == 7
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": original_channels}
        )
        
        print(f"PASS: All 7 channels can be enabled")
    
    def test_enable_single_channel_only(self):
        """Can enable just one channel"""
        original_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        original_channels = original_response.json().get("enabled_channels", ["sms"])
        
        # Enable only clipboard
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": ["clipboard"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["enabled_channels"] == ["clipboard"]
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": original_channels}
        )
        
        print(f"PASS: Single channel can be enabled")
    
    def test_empty_channels_array(self):
        """Sending empty channels array is allowed (though UI prevents it)"""
        original_response = requests.get(f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}")
        original_channels = original_response.json().get("enabled_channels", ["sms"])
        
        # Try enabling empty channels
        response = requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": []}
        )
        
        # API allows empty, frontend prevents it
        assert response.status_code == 200
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/messaging-channels/org/{TEST_ORG_ID}",
            json={"channels": original_channels}
        )
        
        print(f"PASS: Empty channels array is accepted by API")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
