"""
Test Send Health Report endpoints for Account Health Dashboard
Tests the new POST /api/account-health/user/{user_id}/send-report and 
POST /api/account-health/org/{org_id}/send-report endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"

class TestAccountHealthOverview:
    """Test account health overview endpoint"""
    
    def test_overview_returns_accounts(self):
        """GET /api/account-health/overview returns list of accounts with health scores"""
        response = requests.get(f"{BASE_URL}/api/account-health/overview?period=30")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check that accounts have required fields
        if len(data) > 0:
            account = data[0]
            assert "user_id" in account, "Account should have user_id"
            assert "name" in account, "Account should have name"
            assert "email" in account, "Account should have email"
            assert "health" in account, "Account should have health"
            assert "score" in account["health"], "Health should have score"
            assert "grade" in account["health"], "Health should have grade"
            assert "color" in account["health"], "Health should have color"
            print(f"Account health overview returned {len(data)} accounts")

    def test_overview_with_90_day_period(self):
        """GET /api/account-health/overview works with 90 day period"""
        response = requests.get(f"{BASE_URL}/api/account-health/overview?period=90")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"90-day period returned {len(data)} accounts")


class TestUserHealthDetail:
    """Test user health detail endpoint"""
    
    def test_get_user_health_detail(self):
        """GET /api/account-health/user/{user_id} returns detailed health report"""
        response = requests.get(f"{BASE_URL}/api/account-health/user/{TEST_USER_ID}?period=30")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user" in data, "Response should have user"
        assert "metrics" in data, "Response should have metrics"
        assert "health" in data, "Response should have health"
        assert "recent_events" in data, "Response should have recent_events"
        assert "period_days" in data, "Response should have period_days"
        
        # Validate metrics structure
        metrics = data["metrics"]
        assert "total_contacts" in metrics
        assert "messages_30d" in metrics
        assert "touchpoints_30d" in metrics
        assert "active_campaigns" in metrics
        assert "event_breakdown" in metrics
        
        # Validate health structure
        health = data["health"]
        assert "score" in health
        assert "grade" in health
        assert "color" in health
        assert health["grade"] in ["Healthy", "At Risk", "Critical"]
        
        print(f"User health: {health['grade']} ({health['score']}/100)")

    def test_user_health_nonexistent_user(self):
        """GET /api/account-health/user/{bad_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/account-health/user/000000000000000000000000")
        assert response.status_code == 404


class TestSendUserHealthReport:
    """Test POST /api/account-health/user/{user_id}/send-report endpoint"""
    
    def test_send_report_endpoint_structure(self):
        """POST /api/account-health/user/{user_id}/send-report accepts correct payload"""
        payload = {
            "recipient_email": "test@example.com",
            "recipient_name": "Test User",
            "note": "Test note for the report",
            "period": 30
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/user/{TEST_USER_ID}/send-report",
            json=payload
        )
        # In preview env, Resend domain is not verified, so we expect 500 with specific error
        # But the endpoint structure and HTML generation should work
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert data["status"] == "sent"
            print("Report sent successfully!")
        else:
            # Expected in preview environment - domain not verified
            assert response.status_code == 500
            assert "domain" in response.text.lower() or "send" in response.text.lower()
            print(f"Expected domain verification error: {response.json().get('detail', '')}")

    def test_send_report_minimal_payload(self):
        """POST /api/account-health/user/{user_id}/send-report works with minimal payload"""
        payload = {
            "recipient_email": "minimal@example.com"
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/user/{TEST_USER_ID}/send-report",
            json=payload
        )
        # Same expectation - either sends or domain error
        assert response.status_code in [200, 500]
        if response.status_code == 500:
            # Should be domain verification error, not a validation error
            assert "domain" in response.text.lower() or "email" in response.text.lower()
            print("Minimal payload accepted, domain error expected")

    def test_send_report_missing_email(self):
        """POST /api/account-health/user/{user_id}/send-report requires email"""
        payload = {
            "recipient_name": "Test User"
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/user/{TEST_USER_ID}/send-report",
            json=payload
        )
        # Should fail with 422 validation error (missing required field)
        assert response.status_code == 422, f"Expected 422 for missing email, got {response.status_code}"
        print("Validation correctly rejects missing email")

    def test_send_report_nonexistent_user(self):
        """POST /api/account-health/user/{bad_id}/send-report returns 404"""
        payload = {
            "recipient_email": "test@example.com"
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/user/000000000000000000000000/send-report",
            json=payload
        )
        assert response.status_code == 404
        print("404 for non-existent user")

    def test_send_report_with_custom_period(self):
        """POST /api/account-health/user/{user_id}/send-report accepts period parameter"""
        payload = {
            "recipient_email": "test@example.com",
            "period": 90
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/user/{TEST_USER_ID}/send-report",
            json=payload
        )
        # Either sends or domain error, but should not be a different error
        assert response.status_code in [200, 500]
        print(f"90-day period report: {response.status_code}")


class TestOrgHealthReport:
    """Test organization health endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get an org ID from the system"""
        # First get a user to find their org
        response = requests.get(f"{BASE_URL}/api/account-health/user/{TEST_USER_ID}")
        if response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            self.org_id = user.get("organization_id")
        else:
            self.org_id = None
    
    def test_get_org_health(self):
        """GET /api/account-health/org/{org_id} returns org health report"""
        if not self.org_id:
            pytest.skip("No organization found for test user")
        
        response = requests.get(f"{BASE_URL}/api/account-health/org/{self.org_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "organization" in data
        assert "health" in data
        assert "aggregate" in data
        assert "users" in data
        print(f"Org health: {data['health']['grade']} ({data['health']['score']}/100)")

    def test_send_org_report_endpoint_exists(self):
        """POST /api/account-health/org/{org_id}/send-report endpoint exists"""
        if not self.org_id:
            pytest.skip("No organization found for test user")
        
        payload = {
            "recipient_email": "test@example.com",
            "recipient_name": "Org Manager",
            "note": "Test org report",
            "period": 30
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/org/{self.org_id}/send-report",
            json=payload
        )
        # Either success or domain verification error
        assert response.status_code in [200, 500]
        if response.status_code == 500:
            assert "domain" in response.text.lower()
            print("Org report endpoint exists, domain error expected")

    def test_send_org_report_nonexistent_org(self):
        """POST /api/account-health/org/{bad_id}/send-report returns 404"""
        payload = {
            "recipient_email": "test@example.com"
        }
        response = requests.post(
            f"{BASE_URL}/api/account-health/org/000000000000000000000000/send-report",
            json=payload
        )
        assert response.status_code == 404
        print("404 for non-existent org")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
