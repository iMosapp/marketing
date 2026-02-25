"""
Date Triggers API Tests
Tests: GET holidays, PUT/GET configs for birthday/anniversary/sold_date triggers,
       bulk holiday updates, and contact auto-tagging on date field save
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "699907444a076891982fab35"

class TestDateTriggersAPI:
    """Date Triggers endpoint tests"""
    
    def test_get_holidays_returns_14_us_holidays(self):
        """GET /api/date-triggers/holidays returns list of 14 US holidays"""
        response = requests.get(f"{BASE_URL}/api/date-triggers/holidays")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        holidays = response.json()
        assert isinstance(holidays, list), "Response should be a list"
        assert len(holidays) == 14, f"Expected 14 holidays, got {len(holidays)}"
        
        # Verify some expected holidays exist
        holiday_names = [h['name'] for h in holidays]
        assert "New Year's Day" in holiday_names
        assert "Valentine's Day" in holiday_names
        assert "Christmas Day" in holiday_names
        assert "Independence Day" in holiday_names
        assert "Thanksgiving" in holiday_names
        
        # Verify structure
        for h in holidays:
            assert 'id' in h, "Holiday should have id"
            assert 'name' in h, "Holiday should have name"
            assert 'month' in h, "Holiday should have month"
            assert 'day' in h, "Holiday should have day"
        print(f"✓ GET /api/date-triggers/holidays returned {len(holidays)} US holidays")
    
    def test_put_birthday_trigger_config(self):
        """PUT /api/date-triggers/{user_id}/config/birthday saves birthday trigger config"""
        payload = {
            "trigger_type": "birthday",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Happy Birthday, {first_name}! Wishing you an amazing day!"
        }
        response = requests.put(
            f"{BASE_URL}/api/date-triggers/{USER_ID}/config/birthday",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Configuration saved"
        assert data.get("trigger_type") == "birthday"
        print("✓ PUT birthday config saved successfully")
    
    def test_put_anniversary_trigger_config(self):
        """PUT /api/date-triggers/{user_id}/config/anniversary saves anniversary trigger config"""
        payload = {
            "trigger_type": "anniversary",
            "enabled": True,
            "delivery_method": "email",
            "message_template": "Happy Anniversary, {first_name}! Congratulations!"
        }
        response = requests.put(
            f"{BASE_URL}/api/date-triggers/{USER_ID}/config/anniversary",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Configuration saved"
        assert data.get("trigger_type") == "anniversary"
        print("✓ PUT anniversary config saved successfully")
    
    def test_put_sold_date_trigger_config(self):
        """PUT /api/date-triggers/{user_id}/config/sold_date saves sold_date trigger config"""
        payload = {
            "trigger_type": "sold_date",
            "enabled": False,
            "delivery_method": "both",
            "message_template": "Hi {first_name}, it's your vehicle anniversary!"
        }
        response = requests.put(
            f"{BASE_URL}/api/date-triggers/{USER_ID}/config/sold_date",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Configuration saved"
        assert data.get("trigger_type") == "sold_date"
        print("✓ PUT sold_date config saved successfully")
    
    def test_get_date_trigger_configs(self):
        """GET /api/date-triggers/{user_id}/config returns saved configs"""
        response = requests.get(f"{BASE_URL}/api/date-triggers/{USER_ID}/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        configs = response.json()
        assert isinstance(configs, list), "Response should be a list"
        
        # Should contain at least birthday, anniversary, sold_date from previous tests
        trigger_types = [c['trigger_type'] for c in configs]
        assert "birthday" in trigger_types, "Should have birthday config"
        assert "anniversary" in trigger_types, "Should have anniversary config"
        assert "sold_date" in trigger_types, "Should have sold_date config"
        
        # Verify config structure
        for config in configs:
            assert 'user_id' in config
            assert 'trigger_type' in config
            assert 'enabled' in config
            assert 'delivery_method' in config
            assert 'message_template' in config
        print(f"✓ GET /api/date-triggers/{USER_ID}/config returned {len(configs)} configs")
    
    def test_put_holiday_configs_bulk(self):
        """PUT /api/date-triggers/{user_id}/holidays saves selected holiday configs"""
        payload = [
            {"id": "christmas", "enabled": True, "delivery_method": "sms", "message_template": "Merry Christmas!"},
            {"id": "new_years", "enabled": True, "delivery_method": "sms", "message_template": "Happy New Year!"},
            {"id": "thanksgiving", "enabled": False}  # Not enabled
        ]
        response = requests.put(
            f"{BASE_URL}/api/date-triggers/{USER_ID}/holidays",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "Holiday configs updated" in data.get("message", "")
        # 2 are enabled (christmas, new_years)
        assert data.get("count") == 2, f"Expected 2 enabled holidays, got {data.get('count')}"
        print("✓ PUT holidays bulk update saved successfully with 2 enabled holidays")
    
    def test_invalid_trigger_type_returns_400(self):
        """PUT with invalid trigger type returns 400"""
        payload = {
            "trigger_type": "invalid_type",
            "enabled": True,
            "delivery_method": "sms",
            "message_template": "Test"
        }
        response = requests.put(
            f"{BASE_URL}/api/date-triggers/{USER_ID}/config/invalid_type",
            json=payload
        )
        assert response.status_code == 400, f"Expected 400 for invalid type, got {response.status_code}"
        print("✓ Invalid trigger type correctly returns 400")


class TestContactAutoTagging:
    """Contact auto-tagging tests - when date fields are saved, tags are auto-applied"""
    
    def test_create_contact_with_birthday_auto_tags(self):
        """POST /api/contacts/{user_id} with birthday field auto-applies 'Birthday' tag"""
        payload = {
            "first_name": "TEST_Birthday",
            "last_name": "AutoTag",
            "phone": f"+1555{datetime.now().strftime('%H%M%S')}01",
            "birthday": "1990-05-15T00:00:00",
            "tags": []
        }
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "Birthday" in data.get("tags", []), f"Expected 'Birthday' tag, got tags: {data.get('tags')}"
        print(f"✓ Contact with birthday auto-tagged: {data.get('tags')}")
        return data
    
    def test_create_contact_with_anniversary_auto_tags(self):
        """POST /api/contacts/{user_id} with anniversary field auto-applies 'Anniversary' tag"""
        payload = {
            "first_name": "TEST_Anniversary",
            "last_name": "AutoTag",
            "phone": f"+1555{datetime.now().strftime('%H%M%S')}02",
            "anniversary": "2020-06-20T00:00:00",
            "tags": []
        }
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "Anniversary" in data.get("tags", []), f"Expected 'Anniversary' tag, got tags: {data.get('tags')}"
        print(f"✓ Contact with anniversary auto-tagged: {data.get('tags')}")
        return data
    
    def test_create_contact_with_sold_date_auto_tags(self):
        """POST /api/contacts/{user_id} with date_sold field auto-applies 'Sold Date' tag"""
        payload = {
            "first_name": "TEST_SoldDate",
            "last_name": "AutoTag",
            "phone": f"+1555{datetime.now().strftime('%H%M%S')}03",
            "date_sold": "2023-01-10T00:00:00",
            "tags": []
        }
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "Sold Date" in data.get("tags", []), f"Expected 'Sold Date' tag, got tags: {data.get('tags')}"
        print(f"✓ Contact with date_sold auto-tagged: {data.get('tags')}")
        return data
    
    def test_create_contact_with_multiple_dates_auto_tags_all(self):
        """POST with multiple date fields auto-applies all relevant tags"""
        payload = {
            "first_name": "TEST_MultiDate",
            "last_name": "AutoTag",
            "phone": f"+1555{datetime.now().strftime('%H%M%S')}04",
            "birthday": "1985-12-25T00:00:00",
            "anniversary": "2015-07-04T00:00:00",
            "date_sold": "2022-09-15T00:00:00",
            "tags": ["VIP"]  # Existing tag should be preserved
        }
        response = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        tags = data.get("tags", [])
        assert "Birthday" in tags, f"Expected 'Birthday' tag in {tags}"
        assert "Anniversary" in tags, f"Expected 'Anniversary' tag in {tags}"
        assert "Sold Date" in tags, f"Expected 'Sold Date' tag in {tags}"
        assert "VIP" in tags, f"Existing 'VIP' tag should be preserved in {tags}"
        print(f"✓ Contact with multiple dates auto-tagged: {tags}")
        return data


class TestBrandingLogo:
    """Branding/logo endpoint test"""
    
    def test_get_branding_logo(self):
        """GET /api/branding/logo returns 200 with image/png"""
        response = requests.get(f"{BASE_URL}/api/branding/logo")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get('Content-Type', '')
        assert 'image/png' in content_type, f"Expected image/png, got {content_type}"
        assert len(response.content) > 0, "Logo should have content"
        print(f"✓ GET /api/branding/logo returns 200 with image/png ({len(response.content)} bytes)")


class TestContactsPerformance:
    """Contacts API performance test"""
    
    def test_contacts_list_loads(self):
        """GET /api/contacts/{user_id} loads properly"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        assert isinstance(contacts, list), "Response should be a list"
        print(f"✓ GET /api/contacts/{USER_ID} returned {len(contacts)} contacts")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
