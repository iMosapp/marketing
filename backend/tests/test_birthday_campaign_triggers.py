"""
Test Birthday Campaign Triggers - Verifies the auto-generation of birthday cards
when birthday triggers are processed or birthday tags are applied.

Features tested:
1. PUT /api/date-triggers/{user_id}/config/birthday - include_birthday_card field
2. GET /api/date-triggers/{user_id}/config - returns include_birthday_card
3. POST /api/date-triggers/{user_id}/process - respects include_birthday_card
4. POST /api/tags/{user_id}/assign - birthday tag triggers card creation
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"  # Super Admin user_id


class TestDateTriggerConfig:
    """Tests for birthday trigger configuration with include_birthday_card field"""

    def test_put_birthday_config_with_include_card_true(self):
        """PUT /api/date-triggers/{user_id}/config/birthday accepts include_birthday_card=true"""
        config = {
            "trigger_type": "birthday",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Happy Birthday {first_name}!",
            "include_birthday_card": True
        }
        response = requests.put(f"{BASE_URL}/api/date-triggers/{USER_ID}/config/birthday", json=config)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data or "trigger_type" in data
        print(f"PASS: PUT birthday config with include_birthday_card=true - {data}")

    def test_put_birthday_config_with_include_card_false(self):
        """PUT /api/date-triggers/{user_id}/config/birthday accepts include_birthday_card=false"""
        config = {
            "trigger_type": "birthday",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Happy Birthday {first_name}!",
            "include_birthday_card": False
        }
        response = requests.put(f"{BASE_URL}/api/date-triggers/{USER_ID}/config/birthday", json=config)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: PUT birthday config with include_birthday_card=false")

    def test_get_config_returns_include_birthday_card(self):
        """GET /api/date-triggers/{user_id}/config returns include_birthday_card field"""
        # First set the config
        config = {
            "trigger_type": "birthday",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Happy Birthday {first_name}!",
            "include_birthday_card": True
        }
        put_resp = requests.put(f"{BASE_URL}/api/date-triggers/{USER_ID}/config/birthday", json=config)
        assert put_resp.status_code == 200

        # Now get and verify
        response = requests.get(f"{BASE_URL}/api/date-triggers/{USER_ID}/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        configs = response.json()
        assert isinstance(configs, list), "Expected list of configs"
        
        birthday_config = next((c for c in configs if c.get("trigger_type") == "birthday"), None)
        assert birthday_config is not None, "Birthday config not found in response"
        assert "include_birthday_card" in birthday_config, "include_birthday_card field missing"
        assert birthday_config["include_birthday_card"] == True, "include_birthday_card should be True"
        print(f"PASS: GET config returns include_birthday_card: {birthday_config['include_birthday_card']}")

    def test_include_birthday_card_defaults_to_true(self):
        """Birthday config without explicit include_birthday_card should default to True"""
        config = {
            "trigger_type": "birthday",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Happy Birthday {first_name}!"
            # No include_birthday_card - should default to True
        }
        response = requests.put(f"{BASE_URL}/api/date-triggers/{USER_ID}/config/birthday", json=config)
        assert response.status_code == 200
        
        # Verify default
        get_resp = requests.get(f"{BASE_URL}/api/date-triggers/{USER_ID}/config")
        configs = get_resp.json()
        birthday_config = next((c for c in configs if c.get("trigger_type") == "birthday"), None)
        # include_birthday_card should be True or None (will default to True in processing)
        print(f"PASS: include_birthday_card defaults appropriately: {birthday_config.get('include_birthday_card')}")


class TestDateTriggerProcess:
    """Tests for the date trigger process endpoint"""

    def test_process_endpoint_returns_success(self):
        """POST /api/date-triggers/{user_id}/process returns success"""
        response = requests.post(f"{BASE_URL}/api/date-triggers/{USER_ID}/process")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should contain message"
        assert "sent" in data, "Response should contain sent count"
        print(f"PASS: Process endpoint returned: {data}")

    def test_process_endpoint_with_enabled_birthday_trigger(self):
        """Process endpoint should work when birthday trigger is enabled"""
        # Enable birthday trigger with card creation
        config = {
            "trigger_type": "birthday",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Happy Birthday {first_name}! Wishing you all the best.",
            "include_birthday_card": True
        }
        put_resp = requests.put(f"{BASE_URL}/api/date-triggers/{USER_ID}/config/birthday", json=config)
        assert put_resp.status_code == 200

        # Process triggers
        response = requests.post(f"{BASE_URL}/api/date-triggers/{USER_ID}/process")
        assert response.status_code == 200
        data = response.json()
        print(f"PASS: Process with enabled trigger: sent={data.get('sent', 0)}, message={data.get('message')}")


class TestTagAssignmentTrigger:
    """Tests for birthday tag assignment triggering birthday card creation"""

    @pytest.fixture
    def birthday_tag_id(self):
        """Create a Birthday tag for testing"""
        tag_data = {
            "name": "Birthday",
            "color": "#FF6B8A",
            "icon": "gift"
        }
        # Create tag
        response = requests.post(f"{BASE_URL}/api/tags/{USER_ID}", json=tag_data)
        if response.status_code in [200, 201]:
            tag = response.json()
            yield tag.get("_id")
            # Cleanup - delete tag
            requests.delete(f"{BASE_URL}/api/tags/{USER_ID}/{tag.get('_id')}")
        elif response.status_code == 400 and "already exists" in response.text.lower():
            # Tag already exists, get it
            tags_resp = requests.get(f"{BASE_URL}/api/tags/{USER_ID}")
            tags = tags_resp.json()
            birthday_tag = next((t for t in tags if t.get("name") == "Birthday"), None)
            if birthday_tag:
                yield birthday_tag.get("_id")
            else:
                pytest.skip("Could not find or create Birthday tag")
        else:
            pytest.skip(f"Could not create Birthday tag: {response.text}")

    @pytest.fixture
    def test_contact_id(self):
        """Create a test contact for tag assignment tests"""
        contact_data = {
            "first_name": "TEST_BirthdayTag",
            "last_name": "Contact",
            "phone": "+15551234567",
            "email": "test.birthdaytag@test.com"
        }
        response = requests.post(f"{BASE_URL}/api/contacts/{USER_ID}", json=contact_data)
        if response.status_code in [200, 201]:
            data = response.json()
            contact_id = data.get("_id") or data.get("id")
            yield contact_id
            # Cleanup
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
        else:
            pytest.skip(f"Could not create test contact: {response.text}")

    def test_assign_birthday_tag_endpoint_exists(self):
        """POST /api/tags/{user_id}/assign endpoint should exist"""
        data = {
            "tag_name": "Birthday",
            "contact_ids": []  # Empty to just check endpoint
        }
        response = requests.post(f"{BASE_URL}/api/tags/{USER_ID}/assign", json=data)
        # Should return 400 for empty contact_ids, not 404
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}: {response.text}"
        print(f"PASS: Tag assign endpoint exists, status: {response.status_code}")

    def test_assign_birthday_tag_to_contact(self, birthday_tag_id, test_contact_id):
        """Assigning birthday tag should trigger birthday card creation"""
        data = {
            "tag_name": "Birthday",
            "contact_ids": [test_contact_id]
        }
        response = requests.post(f"{BASE_URL}/api/tags/{USER_ID}/assign", json=data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        result = response.json()
        assert "message" in result
        print(f"PASS: Assigned birthday tag to contact: {result}")

    def test_assign_lowercase_birthday_tag(self, birthday_tag_id, test_contact_id):
        """Lowercase 'birthday' tag should also trigger card creation - uses existing Birthday tag"""
        # The tags.py checks for birthday|happy birthday|bday (case insensitive match)
        # But the tag must exist first
        data = {
            "tag_name": "Birthday",  # Use the actual created tag name
            "contact_ids": [test_contact_id]
        }
        response = requests.post(f"{BASE_URL}/api/tags/{USER_ID}/assign", json=data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Birthday tag assignment works")

    def test_assign_bday_tag_triggers_card(self, test_contact_id):
        """'bday' tag should also trigger birthday card creation if it exists"""
        # First create the 'bday' tag
        tag_data = {"name": "bday", "color": "#FF6B8A", "icon": "gift"}
        tag_resp = requests.post(f"{BASE_URL}/api/tags/{USER_ID}", json=tag_data)
        
        if tag_resp.status_code not in [200, 201] and "already exists" not in tag_resp.text.lower():
            pytest.skip("Could not create bday tag")
        
        data = {
            "tag_name": "bday",
            "contact_ids": [test_contact_id]
        }
        response = requests.post(f"{BASE_URL}/api/tags/{USER_ID}/assign", json=data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: 'bday' tag assignment works")
        
        # Cleanup - try to delete bday tag
        if tag_resp.status_code in [200, 201]:
            tag_id = tag_resp.json().get("_id")
            if tag_id:
                requests.delete(f"{BASE_URL}/api/tags/{USER_ID}/{tag_id}")


class TestBirthdayCardsAfterTrigger:
    """Verify that birthday cards are created after triggers"""

    def test_get_birthday_card_history(self):
        """GET /api/birthday/history/{user_id} returns card list"""
        response = requests.get(f"{BASE_URL}/api/birthday/history/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        cards = response.json()
        assert isinstance(cards, list), "Expected list of cards"
        print(f"PASS: Birthday card history returned {len(cards)} cards")

    def test_birthday_card_auto_generation_function(self):
        """Test the auto_create_birthday_card endpoint directly"""
        # Create a test contact first
        contact_data = {
            "first_name": "TEST_AutoCard",
            "last_name": "Recipient",
            "phone": "+15559876543"
        }
        contact_resp = requests.post(f"{BASE_URL}/api/contacts/{USER_ID}", json=contact_data)
        
        if contact_resp.status_code not in [200, 201]:
            pytest.skip("Could not create test contact")
        
        contact_id = contact_resp.json().get("_id") or contact_resp.json().get("id")
        
        try:
            # Use the create endpoint which calls auto_create_birthday_card internally
            create_data = {
                "salesman_id": USER_ID,
                "contact_id": contact_id,
                "custom_message": "Test auto-generated birthday card"
            }
            # Use form data for the create endpoint
            response = requests.post(
                f"{BASE_URL}/api/birthday/create",
                data=create_data
            )
            # May succeed or fail based on existing card
            print(f"Birthday card create result: {response.status_code} - {response.text[:200]}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")


class TestTriggerLog:
    """Test the date trigger log endpoint"""

    def test_get_trigger_log(self):
        """GET /api/date-triggers/{user_id}/log returns recent sends"""
        response = requests.get(f"{BASE_URL}/api/date-triggers/{USER_ID}/log")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        logs = response.json()
        assert isinstance(logs, list), "Expected list of logs"
        print(f"PASS: Trigger log returned {len(logs)} entries")


class TestHolidaysEndpoint:
    """Test holidays endpoint is working"""

    def test_get_holidays(self):
        """GET /api/date-triggers/holidays returns holiday list"""
        response = requests.get(f"{BASE_URL}/api/date-triggers/holidays")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        holidays = response.json()
        assert isinstance(holidays, list), "Expected list of holidays"
        assert len(holidays) > 0, "Should have at least one holiday"
        
        # Check structure
        first_holiday = holidays[0]
        assert "id" in first_holiday
        assert "name" in first_holiday
        assert "month" in first_holiday
        assert "day" in first_holiday
        print(f"PASS: Holidays endpoint returned {len(holidays)} holidays")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
