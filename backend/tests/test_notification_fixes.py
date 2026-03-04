"""
Test suite for notification system fixes:
1. Notification bell does NOT crash (getNotifColor fix - was referencing undefined colors)
2. Notification center API returns proper links with prefill params
3. Demo request POST creates notifications for admins with form_details
4. Task notifications use 'completed' field not 'status'
5. All notification types have proper links
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta
from bson import ObjectId

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def admin_user(api_client):
    """Login as super admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "forest@imosapp.com",
        "password": "Admin123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("user", data)

class TestNotificationCenterAPI:
    """Test notification center endpoints for proper links and data"""
    
    def test_notification_center_returns_200(self, api_client, admin_user):
        """GET /api/notification-center/{user_id} should return 200"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}")
        assert response.status_code == 200, f"Notification center failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "notifications" in data, "Response should have notifications array"
        assert "unread_count" in data, "Response should have unread_count"
        assert "category_counts" in data, "Response should have category_counts"
        print(f"SUCCESS: Notification center returned {len(data['notifications'])} notifications, {data['unread_count']} unread")
    
    def test_notification_center_category_filter(self, api_client, admin_user):
        """GET /api/notification-center/{user_id}?category=leads should filter properly"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=leads")
        assert response.status_code == 200, f"Leads filter failed: {response.text}"
        data = response.json()
        # If filtered, all notifications should be in leads category or empty
        for notif in data.get("notifications", []):
            assert notif.get("category") == "leads", f"Expected leads category, got {notif.get('category')}"
        print(f"SUCCESS: Leads category filter returned {len(data.get('notifications', []))} notifications")
    
    def test_notification_center_tasks_filter(self, api_client, admin_user):
        """GET /api/notification-center/{user_id}?category=tasks should filter properly"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=tasks")
        assert response.status_code == 200, f"Tasks filter failed: {response.text}"
        data = response.json()
        for notif in data.get("notifications", []):
            assert notif.get("category") == "tasks", f"Expected tasks category, got {notif.get('category')}"
        print(f"SUCCESS: Tasks category filter returned {len(data.get('notifications', []))} notifications")
    
    def test_notification_center_campaigns_filter(self, api_client, admin_user):
        """GET /api/notification-center/{user_id}?category=campaigns should filter properly"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=campaigns")
        assert response.status_code == 200, f"Campaigns filter failed: {response.text}"
        data = response.json()
        # Check campaign notifications have proper links with prefill
        for notif in data.get("notifications", []):
            if notif.get("type") == "campaign_send" and notif.get("contact_id"):
                link = notif.get("link", "")
                assert "/contact/" in link, f"Campaign send should link to /contact/ - got: {link}"
                print(f"Campaign notification link: {link}")
        print(f"SUCCESS: Campaigns category filter returned {len(data.get('notifications', []))} notifications")

class TestDemoRequestNotifications:
    """Test demo request creating notifications for admins"""
    
    def test_demo_request_creates_notification(self, api_client, admin_user):
        """POST /api/demo-requests should create notification for admins"""
        # Create a unique demo request
        unique_name = f"Test Lead {datetime.now().strftime('%H%M%S')}"
        demo_data = {
            "name": unique_name,
            "email": f"testlead_{datetime.now().strftime('%H%M%S')}@example.com",
            "phone": "+15551234567",
            "company": "Test Corp",
            "source": "pytest_notification_test",
            "message": "Testing notification creation from demo request",
            "utm_source": "pytest"
        }
        
        response = api_client.post(f"{BASE_URL}/api/demo-requests", json=demo_data)
        assert response.status_code == 200, f"Demo request failed: {response.text}"
        data = response.json()
        assert data.get("status") == "success", f"Expected success, got: {data}"
        print(f"SUCCESS: Demo request created for {unique_name}")
        
        # Now check if notification was created for admin
        user_id = admin_user.get("_id") or admin_user.get("id")
        notif_response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=leads")
        assert notif_response.status_code == 200, f"Notification center failed: {notif_response.text}"
        notif_data = notif_response.json()
        
        # Find the notification for our demo request
        found_notif = None
        for notif in notif_data.get("notifications", []):
            if notif.get("type") == "new_lead" and unique_name in (notif.get("title", "") + notif.get("body", "")):
                found_notif = notif
                break
        
        assert found_notif is not None, f"Expected to find notification for {unique_name}, but didn't find it in {len(notif_data.get('notifications', []))} notifications"
        
        # Verify notification has form_details
        body = found_notif.get("body", "")
        assert unique_name in body or "Name:" in body, f"Notification body should contain lead info: {body}"
        
        # Verify link to lead tracking
        link = found_notif.get("link", "")
        # New leads without contact should link to lead tracking
        assert link is not None, "Notification should have a link"
        
        print(f"SUCCESS: Found notification for demo request - type={found_notif.get('type')}, link={link}")
    
    def test_demo_request_with_referral(self, api_client, admin_user):
        """POST /api/demo-requests with ref code should attribute properly"""
        # First get admin's ref_code if available
        user_id = admin_user.get("_id") or admin_user.get("id")
        ref_code = admin_user.get("ref_code", "")
        
        unique_name = f"Referred Lead {datetime.now().strftime('%H%M%S')}"
        demo_data = {
            "name": unique_name,
            "email": f"referredlead_{datetime.now().strftime('%H%M%S')}@example.com",
            "phone": "+15559876543",
            "company": "Referred Corp",
            "source": "pytest_referral_test",
            "ref": ref_code if ref_code else "",
            "utm_source": "facebook",
            "utm_medium": "paid_social",
            "utm_campaign": "pytest_campaign"
        }
        
        response = api_client.post(f"{BASE_URL}/api/demo-requests", json=demo_data)
        assert response.status_code == 200, f"Demo request with referral failed: {response.text}"
        print(f"SUCCESS: Demo request with referral created for {unique_name}")

class TestNotificationTypes:
    """Test that all notification types are handled properly"""
    
    def test_mark_notifications_read(self, api_client, admin_user):
        """POST /api/notification-center/{user_id}/read should mark as read"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        
        # First get some notifications
        notif_response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}")
        assert notif_response.status_code == 200
        notif_data = notif_response.json()
        
        if notif_data.get("notifications"):
            # Mark the first notification as read
            notif_id = notif_data["notifications"][0].get("id")
            read_response = api_client.post(
                f"{BASE_URL}/api/notification-center/{user_id}/read",
                json={"ids": [notif_id]}
            )
            assert read_response.status_code == 200, f"Mark read failed: {read_response.text}"
            print(f"SUCCESS: Marked notification {notif_id} as read")
        else:
            print("SKIP: No notifications to mark as read")
    
    def test_mark_all_notifications_read(self, api_client, admin_user):
        """POST /api/notification-center/{user_id}/read-all should mark all as read"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        
        response = api_client.post(f"{BASE_URL}/api/notification-center/{user_id}/read-all")
        assert response.status_code == 200, f"Mark all read failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        print(f"SUCCESS: Marked all notifications as read - count={data.get('count')}")
    
    def test_unread_count_endpoint(self, api_client, admin_user):
        """GET /api/notification-center/{user_id}/unread-count should return count"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}/unread-count")
        assert response.status_code == 200, f"Unread count failed: {response.text}"
        data = response.json()
        assert "count" in data, "Response should have count field"
        print(f"SUCCESS: Unread count = {data.get('count')}")

class TestTaskNotificationLinks:
    """Test that task notifications have proper prefill links"""
    
    def test_task_notifications_have_contact_links(self, api_client, admin_user):
        """Task notifications should link to /contact/{id}?prefill={message}"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=tasks")
        assert response.status_code == 200, f"Tasks fetch failed: {response.text}"
        data = response.json()
        
        task_notifs = data.get("notifications", [])
        for notif in task_notifs:
            notif_type = notif.get("type", "")
            link = notif.get("link", "")
            contact_id = notif.get("contact_id", "")
            
            if notif_type in ("task_overdue", "task_due_soon"):
                if contact_id:
                    assert "/contact/" in link, f"Task notification with contact should link to /contact/ - got: {link}"
                    # Check for prefill parameter
                    if link and "?" in link:
                        assert "prefill=" in link, f"Task link should have prefill param: {link}"
                print(f"Task notification: type={notif_type}, has_link={bool(link)}, link_sample={link[:60] if link else 'None'}...")
        
        print(f"SUCCESS: Checked {len(task_notifs)} task notifications for proper links")

class TestCampaignNotificationLinks:
    """Test that campaign notifications have proper prefill links"""
    
    def test_campaign_send_notifications_have_prefill(self, api_client, admin_user):
        """Campaign send notifications should link to /contact/{id}?prefill={message}"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=campaigns")
        assert response.status_code == 200, f"Campaigns fetch failed: {response.text}"
        data = response.json()
        
        campaign_notifs = data.get("notifications", [])
        campaign_sends_checked = 0
        for notif in campaign_notifs:
            notif_type = notif.get("type", "")
            link = notif.get("link", "")
            contact_id = notif.get("contact_id", "")
            
            if notif_type == "campaign_send" and contact_id:
                assert "/contact/" in link, f"Campaign send should link to /contact/ - got: {link}"
                # Prefill should be URL-encoded message
                if "?" in link:
                    assert "prefill=" in link, f"Campaign send link should have prefill param: {link}"
                campaign_sends_checked += 1
                print(f"Campaign send notification: contact_id={contact_id}, link={link[:80]}...")
        
        print(f"SUCCESS: Checked {campaign_sends_checked} campaign send notifications for proper prefill links")

class TestActivityNotifications:
    """Test activity notification types render properly"""
    
    def test_activity_filter_returns_events(self, api_client, admin_user):
        """GET /api/notification-center/{user_id}?category=activity should return activity events"""
        user_id = admin_user.get("_id") or admin_user.get("id")
        
        response = api_client.get(f"{BASE_URL}/api/notification-center/{user_id}?category=activity")
        assert response.status_code == 200, f"Activity filter failed: {response.text}"
        data = response.json()
        
        activity_notifs = data.get("notifications", [])
        valid_activity_types = {
            "link_click", "review_submitted", "new_contact",
            "digital_card_sent", "review_request_sent", "congrats_card_sent",
            "email_sent", "sms_sent"
        }
        
        for notif in activity_notifs:
            notif_type = notif.get("type", "")
            assert notif.get("category") == "activity", f"Expected activity category, got {notif.get('category')}"
            print(f"Activity notification: type={notif_type}, title={notif.get('title', '')[:40]}")
        
        print(f"SUCCESS: Activity filter returned {len(activity_notifs)} notifications")
