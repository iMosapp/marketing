"""
UI/UX Audit Backend Tests - Iteration 58
Tests for: user-activity endpoint with all_time period, conversation archive/restore APIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestUserActivityAllTime:
    """Test user activity endpoint with all_time period"""
    
    def test_user_activity_all_time_returns_valid_data(self):
        """Verify /api/reports/user-activity/{user_id}?period=all_time returns valid data"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{TEST_USER_ID}?period=all_time")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify period is correctly set
        assert data.get("period") == "all_time", f"Expected period=all_time, got {data.get('period')}"
        
        # Verify start_date is a very old date (2020-01-01)
        assert "2020-01-01" in data.get("start_date", ""), "Start date should be 2020-01-01 for all_time"
        
        # Verify summary contains required fields
        assert "summary" in data
        assert "total_touchpoints" in data["summary"]
        
        # Verify communication stats
        assert "communication" in data
        comm = data["communication"]
        assert "texts_sent" in comm
        assert "emails_sent" in comm
        assert "calls_placed" in comm
        
        # Verify sharing stats
        assert "sharing" in data
        sharing = data["sharing"]
        assert "digital_cards" in sharing
        assert "review_links" in sharing
        assert "congrats_cards" in sharing
        
        print(f"✓ All Time activity: {data['summary']['total_touchpoints']} touchpoints")
    
    def test_user_activity_today_period(self):
        """Verify today period works"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{TEST_USER_ID}?period=today")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("period") == "today"
        print(f"✓ Today activity: {data['summary']['total_touchpoints']} touchpoints")
    
    def test_user_activity_week_period(self):
        """Verify week period works"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{TEST_USER_ID}?period=week")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("period") == "week"
        print(f"✓ Week activity: {data['summary']['total_touchpoints']} touchpoints")
    
    def test_user_activity_month_period(self):
        """Verify month period works"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{TEST_USER_ID}?period=month")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("period") == "month"
        print(f"✓ Month activity: {data['summary']['total_touchpoints']} touchpoints")
    
    def test_user_activity_year_period(self):
        """Verify year period works"""
        response = requests.get(f"{BASE_URL}/api/reports/user-activity/{TEST_USER_ID}?period=year")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("period") == "year"
        print(f"✓ Year activity: {data['summary']['total_touchpoints']} touchpoints")
    
    def test_user_activity_custom_period(self):
        """Verify custom date range works"""
        response = requests.get(
            f"{BASE_URL}/api/reports/user-activity/{TEST_USER_ID}",
            params={
                "period": "custom",
                "start_date": "2024-01-01",
                "end_date": "2025-12-31"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("period") == "custom"
        assert "2024-01-01" in data.get("start_date", "")
        assert "2025-12-31" in data.get("end_date", "")
        print(f"✓ Custom range activity: {data['summary']['total_touchpoints']} touchpoints")


class TestConversationArchive:
    """Test conversation archive and restore functionality"""
    
    def test_get_conversations(self):
        """Get active conversations for user"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Expected list of conversations"
        print(f"✓ Found {len(data)} conversations")
        return data
    
    def test_archive_conversation(self):
        """Test archiving a conversation"""
        # First get a conversation
        conversations = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}?limit=1").json()
        if not conversations:
            pytest.skip("No conversations to archive")
        
        conv_id = conversations[0]["_id"]
        
        # Archive it
        response = requests.put(f"{BASE_URL}/api/messages/conversation/{conv_id}/archive")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("message") == "Conversation archived"
        print(f"✓ Archived conversation {conv_id}")
        
        # Restore it back
        restore_response = requests.put(f"{BASE_URL}/api/messages/conversation/{conv_id}/restore")
        assert restore_response.status_code == 200
        print(f"✓ Restored conversation {conv_id}")
    
    def test_restore_conversation(self):
        """Test restoring an archived conversation"""
        # First get and archive a conversation
        conversations = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}?limit=1").json()
        if not conversations:
            pytest.skip("No conversations to test")
        
        conv_id = conversations[0]["_id"]
        
        # Archive first
        requests.put(f"{BASE_URL}/api/messages/conversation/{conv_id}/archive")
        
        # Now restore
        response = requests.put(f"{BASE_URL}/api/messages/conversation/{conv_id}/restore")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("message") == "Conversation restored"
        print(f"✓ Restore endpoint working correctly")


class TestCompanyDocs:
    """Test Company Docs listing endpoint"""
    
    def test_docs_list_endpoint_exists(self):
        """Verify docs list endpoint exists (requires auth)"""
        response = requests.get(f"{BASE_URL}/api/docs/")
        # Should return 401 (auth required) since we're not authenticated
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "Authentication required" in data.get("detail", "")
        print(f"✓ Docs list endpoint correctly requires authentication")


class TestHealthAndBasicEndpoints:
    """Basic health checks"""
    
    def test_health_endpoint(self):
        """Verify health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health endpoint OK")
    
    def test_backend_accessible(self):
        """Verify backend is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code in [200, 404]  # Root may or may not exist
        print("✓ Backend accessible")
