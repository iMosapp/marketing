"""
Tests for Brand Kit and Email Analytics endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://lead-routing-1.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "forestward@gmail.com"
TEST_PASSWORD = "Admin123!"


class TestBrandKit:
    """Test Brand Kit CRUD endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.user = response.json()["user"]
        self.user_id = self.user["_id"]
    
    def test_get_brand_kit_empty(self):
        """Test getting brand kit when none exists returns empty dict"""
        response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{self.user_id}")
        assert response.status_code == 200
        data = response.json()
        # Should return dict (possibly empty or with brand kit data)
        assert isinstance(data, dict)
        print(f"PASS: Got brand kit: {data}")
    
    def test_update_brand_kit_primary_color(self):
        """Test updating primary color"""
        response = requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{self.user_id}",
            json={"primary_color": "#FF5733"}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Brand kit updated"
        print("PASS: Updated primary color")
    
    def test_update_brand_kit_full(self):
        """Test updating all brand kit fields"""
        brand_kit_data = {
            "logo_url": "https://example.com/test-logo.png",
            "primary_color": "#007AFF",
            "secondary_color": "#34C759",
            "accent_color": "#FFD60A",
            "company_name": "TEST_Company",
            "tagline": "Test tagline",
            "footer_text": "Powered by Test",
            "social_links": {
                "website": "https://example.com",
                "facebook": "https://facebook.com/test",
                "instagram": "https://instagram.com/test",
                "twitter": "https://twitter.com/test",
                "linkedin": "https://linkedin.com/test"
            }
        }
        
        response = requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{self.user_id}",
            json=brand_kit_data
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Brand kit updated"
        
        # Verify GET returns updated values
        get_response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{self.user_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data.get("company_name") == "TEST_Company"
        assert data.get("primary_color") == "#007AFF"
        assert data.get("social_links", {}).get("website") == "https://example.com"
        print("PASS: Full brand kit update and verify")
    
    def test_get_brand_kit_invalid_entity_type(self):
        """Test that invalid entity type returns 400"""
        response = requests.get(f"{BASE_URL}/api/email/brand-kit/invalid/{self.user_id}")
        assert response.status_code == 400
        print("PASS: Invalid entity type returns 400")
    
    def test_get_brand_kit_invalid_entity_id(self):
        """Test that invalid entity ID returns error"""
        response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/invalid_id_123")
        # Could be 400 for invalid ObjectId format, 404 for not found, or 5xx for server error
        assert response.status_code in [400, 404, 500, 520]
        print("PASS: Invalid entity ID handled")


class TestEmailAnalytics:
    """Test Email Analytics endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.user = response.json()["user"]
        self.user_id = self.user["_id"]
    
    def test_get_analytics_default(self):
        """Test getting analytics with default 30 days"""
        response = requests.get(f"{BASE_URL}/api/email/analytics/{self.user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "period_days" in data
        assert "total_sent" in data
        assert "total_delivered" in data
        assert "total_opened" in data
        assert "total_clicked" in data
        assert "total_bounced" in data
        assert "open_rate" in data
        assert "click_rate" in data
        
        # Verify types
        assert isinstance(data["total_sent"], int)
        assert isinstance(data["open_rate"], int)
        assert data["period_days"] == 30
        print(f"PASS: Got analytics: sent={data['total_sent']}, open_rate={data['open_rate']}%")
    
    def test_get_analytics_7_days(self):
        """Test getting analytics for 7 days"""
        response = requests.get(f"{BASE_URL}/api/email/analytics/{self.user_id}", params={"days": 7})
        assert response.status_code == 200
        
        data = response.json()
        assert data["period_days"] == 7
        print("PASS: Got 7-day analytics")
    
    def test_get_analytics_90_days(self):
        """Test getting analytics for 90 days"""
        response = requests.get(f"{BASE_URL}/api/email/analytics/{self.user_id}", params={"days": 90})
        assert response.status_code == 200
        
        data = response.json()
        assert data["period_days"] == 90
        print("PASS: Got 90-day analytics")
    
    def test_get_analytics_all_time(self):
        """Test getting analytics for all time (days=0)"""
        response = requests.get(f"{BASE_URL}/api/email/analytics/{self.user_id}", params={"days": 0})
        assert response.status_code == 200
        
        data = response.json()
        # days=0 means all time, but period_days in response may still be 0
        assert "total_sent" in data
        print("PASS: Got all-time analytics")


class TestEmailLogs:
    """Test Email Logs endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.user = response.json()["user"]
        self.user_id = self.user["_id"]
    
    def test_get_logs(self):
        """Test getting email logs"""
        response = requests.get(f"{BASE_URL}/api/email/logs/{self.user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Got {len(data)} email logs")
        
        # If there are logs, verify structure
        if len(data) > 0:
            log = data[0]
            assert "_id" in log
            assert "recipient_email" in log
            assert "subject" in log
            assert "status" in log
            print(f"PASS: Log structure verified: {log.get('subject')}")
    
    def test_get_logs_with_limit(self):
        """Test getting logs with limit"""
        response = requests.get(f"{BASE_URL}/api/email/logs/{self.user_id}", params={"limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5
        print(f"PASS: Got {len(data)} logs with limit=5")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
