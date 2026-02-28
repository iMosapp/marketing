"""
Test Notifications Center and Analytics Dashboard APIs
Tests:
- GET /api/notification-center/{user_id} - aggregated notifications
- GET /api/notification-center/{user_id}?category=activity - category filtering
- GET /api/notification-center/{user_id}/unread-count - badge count
- POST /api/notification-center/{user_id}/read - mark specific as read
- POST /api/notification-center/{user_id}/read-all - mark all as read
- GET /api/reports/dashboard/{user_id}?days=30 - analytics dashboard
- GET /api/reports/dashboard/{user_id}?days=7 - different period
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestNotificationCenterAPI:
    """Notification Center endpoint tests"""
    
    def test_get_notifications_returns_data(self):
        """GET /api/notification-center/{user_id} returns notifications structure"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "notifications" in data
        assert "unread_count" in data
        assert "total" in data
        assert "category_counts" in data
        
        # Check notification structure if any exist
        if len(data["notifications"]) > 0:
            notif = data["notifications"][0]
            assert "id" in notif
            assert "type" in notif
            assert "category" in notif
            assert "title" in notif
            assert "timestamp" in notif
            assert "read" in notif
            
    def test_get_notifications_filter_by_category(self):
        """GET /api/notification-center/{user_id}?category=activity filters correctly"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}?category=activity")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        # All returned notifications should be 'activity' category
        for notif in data.get("notifications", []):
            assert notif["category"] == "activity", f"Expected activity, got {notif['category']}"
            
    def test_get_notifications_filter_by_leads(self):
        """GET /api/notification-center/{user_id}?category=leads filters correctly"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}?category=leads")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        # All returned notifications should be 'leads' category  
        for notif in data.get("notifications", []):
            assert notif["category"] == "leads"
            
    def test_get_notifications_filter_by_tasks(self):
        """GET /api/notification-center/{user_id}?category=tasks filters correctly"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}?category=tasks")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        for notif in data.get("notifications", []):
            assert notif["category"] == "tasks"

    def test_get_unread_count(self):
        """GET /api/notification-center/{user_id}/unread-count returns count"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}/unread-count")
        assert response.status_code == 200
        
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
        
    def test_mark_notifications_read(self):
        """POST /api/notification-center/{user_id}/read marks as read"""
        # First get some notification IDs
        get_response = requests.get(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}")
        notifs = get_response.json().get("notifications", [])
        
        if len(notifs) > 0:
            test_ids = [notifs[0]["id"]]
            
            response = requests.post(
                f"{BASE_URL}/api/notification-center/{TEST_USER_ID}/read",
                json={"ids": test_ids}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data.get("success") == True
            assert "message" in data
        else:
            # No notifications to test, skip
            pytest.skip("No notifications available to test mark read")
    
    def test_mark_all_read(self):
        """POST /api/notification-center/{user_id}/read-all marks all as read"""
        response = requests.post(f"{BASE_URL}/api/notification-center/{TEST_USER_ID}/read-all")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        assert "count" in data
        assert isinstance(data["count"], int)


class TestAnalyticsDashboardAPI:
    """Reports Dashboard endpoint tests"""
    
    def test_dashboard_30_days(self):
        """GET /api/reports/dashboard/{user_id}?days=30 returns comprehensive data"""
        response = requests.get(f"{BASE_URL}/api/reports/dashboard/{TEST_USER_ID}?days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        assert "scope" in data
        assert "period_days" in data
        assert data["period_days"] == 30
        assert "start_date" in data
        assert "end_date" in data
        
        # Check KPIs structure
        assert "kpis" in data
        kpis = data["kpis"]
        assert "total_touchpoints" in kpis
        assert "trend_pct" in kpis
        assert "sms_sent" in kpis
        assert "emails_sent" in kpis
        assert "digital_cards" in kpis
        assert "review_invites" in kpis
        assert "new_contacts" in kpis
        assert "total_contacts" in kpis
        
        # Check daily_trend structure
        assert "daily_trend" in data
        assert isinstance(data["daily_trend"], list)
        if len(data["daily_trend"]) > 0:
            day = data["daily_trend"][0]
            assert "date" in day
            assert "sms" in day
            assert "email" in day
            assert "total" in day
            
        # Check channel_breakdown structure
        assert "channel_breakdown" in data
        channel = data["channel_breakdown"]
        assert "sms" in channel
        assert "email" in channel
        
        # Check team_size and store_comparison for admin
        assert "team_size" in data
        if data["scope"] == "organization":
            assert "store_comparison" in data
    
    def test_dashboard_7_days(self):
        """GET /api/reports/dashboard/{user_id}?days=7 works with different period"""
        response = requests.get(f"{BASE_URL}/api/reports/dashboard/{TEST_USER_ID}?days=7")
        assert response.status_code == 200
        
        data = response.json()
        assert data["period_days"] == 7
        assert "kpis" in data
        assert "daily_trend" in data
        assert len(data["daily_trend"]) == 8  # days + 1 for range
        
    def test_dashboard_90_days(self):
        """GET /api/reports/dashboard/{user_id}?days=90 works for longer period"""
        response = requests.get(f"{BASE_URL}/api/reports/dashboard/{TEST_USER_ID}?days=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data["period_days"] == 90
        assert "kpis" in data
        assert "daily_trend" in data
        
    def test_dashboard_invalid_user(self):
        """GET /api/reports/dashboard/{user_id} with invalid user returns 404"""
        response = requests.get(f"{BASE_URL}/api/reports/dashboard/000000000000000000000000?days=30")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
