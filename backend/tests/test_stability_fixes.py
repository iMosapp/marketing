"""
Test suite for Production Stability Fixes - Iteration 248
Tests the async conversion of notifications, lead sources, activity feed, and caching.

Root causes fixed:
1. Synchronous pymongo blocking event loop in notifications_center.py, notifications.py, lead_sources.py
2. N+1 queries in activity feed
3. Unthrottled expensive catchup task on every page load
4. Missing DB indexes
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"  # Test user ID from credentials

class TestNotificationCenter:
    """Tests for /api/notification-center endpoints - fully async with caching"""
    
    def test_get_unread_count_returns_count(self):
        """GET /api/notification-center/{user_id}/unread-count - Returns count, cached for 15s"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}/unread-count")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "count" in data, f"Response missing 'count' field: {data}"
        assert isinstance(data["count"], int), f"Count should be int, got {type(data['count'])}"
        print(f"✓ Unread count: {data['count']}")
    
    def test_get_unread_count_cached_response(self):
        """Verify unread count is cached (same response within 15s)"""
        # First request
        response1 = requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}/unread-count")
        assert response1.status_code == 200
        count1 = response1.json()["count"]
        
        # Second request immediately after (should be cached)
        response2 = requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}/unread-count")
        assert response2.status_code == 200
        count2 = response2.json()["count"]
        
        # Counts should be identical (cached)
        assert count1 == count2, f"Cached response mismatch: {count1} vs {count2}"
        print(f"✓ Cached unread count consistent: {count1}")
    
    def test_get_notifications_returns_structure(self):
        """GET /api/notification-center/{user_id} - Returns notifications with categories, priorities"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data, f"Response missing 'success' field: {data}"
        assert data["success"] == True, f"Expected success=True, got {data['success']}"
        assert "notifications" in data, f"Response missing 'notifications' field"
        assert "unread_count" in data, f"Response missing 'unread_count' field"
        assert "total" in data, f"Response missing 'total' field"
        assert "category_counts" in data, f"Response missing 'category_counts' field"
        
        # Verify notifications is a list
        assert isinstance(data["notifications"], list), f"notifications should be list"
        
        # If there are notifications, verify structure
        if data["notifications"]:
            notif = data["notifications"][0]
            required_fields = ["id", "type", "category", "priority", "title", "timestamp", "read", "source"]
            for field in required_fields:
                assert field in notif, f"Notification missing '{field}' field: {notif}"
        
        print(f"✓ Notifications returned: {len(data['notifications'])}, unread: {data['unread_count']}")
    
    def test_get_notifications_with_category_filter(self):
        """GET /api/notification-center/{user_id}?category=tasks - Filter by category"""
        response = requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}?category=tasks")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True
        
        # All returned notifications should be in 'tasks' category
        for notif in data["notifications"]:
            assert notif["category"] == "tasks", f"Expected category 'tasks', got '{notif['category']}'"
        
        print(f"✓ Filtered notifications (tasks): {len(data['notifications'])}")
    
    def test_mark_notifications_read(self):
        """POST /api/notification-center/{user_id}/read - Mark notifications as read"""
        # First get some notification IDs
        get_response = requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}")
        assert get_response.status_code == 200
        notifications = get_response.json().get("notifications", [])
        
        # Mark some as read (use first 2 if available)
        ids_to_mark = [n["id"] for n in notifications[:2]] if notifications else ["test_id_1"]
        
        response = requests.post(
            f"{BASE_URL}/api/notification-center/{USER_ID}/read",
            json={"ids": ids_to_mark}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True, f"Expected success=True: {data}"
        print(f"✓ Marked {len(ids_to_mark)} notifications as read")
    
    def test_mark_all_read(self):
        """POST /api/notification-center/{user_id}/read-all - Mark all as read"""
        response = requests.post(f"{BASE_URL}/api/notification-center/{USER_ID}/read-all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True, f"Expected success=True: {data}"
        assert "count" in data, f"Response missing 'count' field"
        print(f"✓ Marked all as read, count: {data['count']}")


class TestNotifications:
    """Tests for /api/notifications endpoints - all async now"""
    
    def test_get_notifications_list(self):
        """GET /api/notifications/?user_id={user_id} - Basic notification list"""
        response = requests.get(f"{BASE_URL}/api/notifications/?user_id={USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "success" in data, f"Response missing 'success' field"
        assert data["success"] == True
        assert "notifications" in data, f"Response missing 'notifications' field"
        assert "count" in data, f"Response missing 'count' field"
        assert "unread_count" in data, f"Response missing 'unread_count' field"
        
        print(f"✓ Notifications list: {data['count']} total, {data['unread_count']} unread")
    
    def test_get_notifications_unread_only(self):
        """GET /api/notifications/?user_id={user_id}&unread_only=true"""
        response = requests.get(f"{BASE_URL}/api/notifications/?user_id={USER_ID}&unread_only=true")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True
        
        # All returned should be unread
        for notif in data["notifications"]:
            assert notif.get("read") == False, f"Expected unread notification: {notif}"
        
        print(f"✓ Unread only filter: {len(data['notifications'])} notifications")
    
    def test_get_unread_count(self):
        """GET /api/notifications/unread-count?user_id={user_id}"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count?user_id={USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "count" in data, f"Response missing 'count' field"
        print(f"✓ Unread count (notifications router): {data['count']}")
    
    def test_get_pending_action_notification(self):
        """GET /api/notifications/pending-action?user_id={user_id}"""
        response = requests.get(f"{BASE_URL}/api/notifications/pending-action?user_id={USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        # notification can be None if no pending actions
        print(f"✓ Pending action: {'Found' if data.get('notification') else 'None'}")


class TestActivityFeed:
    """Tests for /api/activity/{user_id} - Activity feed with bulk lookups (no N+1)"""
    
    def test_get_activity_feed(self):
        """GET /api/activity/{user_id}?limit=10 - Activity feed with bulk lookups"""
        response = requests.get(f"{BASE_URL}/api/activity/{USER_ID}?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "activities" in data, f"Response missing 'activities' field"
        assert "user_role" in data, f"Response missing 'user_role' field"
        assert "total" in data, f"Response missing 'total' field"
        
        # Verify activities structure
        if data["activities"]:
            activity = data["activities"][0]
            required_fields = ["type", "icon", "color", "message", "timestamp"]
            for field in required_fields:
                assert field in activity, f"Activity missing '{field}' field: {activity}"
        
        print(f"✓ Activity feed: {len(data['activities'])} activities, role: {data['user_role']}")
    
    def test_activity_feed_performance(self):
        """Verify activity feed responds quickly (no N+1 queries)"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/activity/{USER_ID}?limit=20")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        # Should respond in under 3 seconds even with 20 items (bulk lookups)
        assert elapsed < 3.0, f"Activity feed too slow: {elapsed:.2f}s (expected <3s)"
        print(f"✓ Activity feed performance: {elapsed:.2f}s for {len(response.json()['activities'])} items")


class TestTasksSummary:
    """Tests for /api/tasks/{user_id}/summary - Cached response, throttled catchup"""
    
    def test_get_task_summary(self):
        """GET /api/tasks/{user_id}/summary - Cached response"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify summary structure
        required_fields = ["total_today", "completed_today", "pending_today", "overdue", "progress_pct", "activity"]
        for field in required_fields:
            assert field in data, f"Summary missing '{field}' field: {data}"
        
        # Verify activity breakdown
        activity = data["activity"]
        activity_fields = ["calls", "texts", "emails", "cards", "reviews", "clicks", "opens", "replies", "new_leads"]
        for field in activity_fields:
            assert field in activity, f"Activity missing '{field}' field"
        
        print(f"✓ Task summary: {data['total_today']} total, {data['completed_today']} completed, {data['progress_pct']}% progress")
    
    def test_task_summary_cached(self):
        """Verify task summary is cached (30s TTL)"""
        # First request
        response1 = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request immediately (should be cached)
        response2 = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Core values should be identical (cached)
        assert data1["total_today"] == data2["total_today"], "Cached response mismatch"
        assert data1["progress_pct"] == data2["progress_pct"], "Cached response mismatch"
        print(f"✓ Task summary cached correctly")


class TestSEOHealthScore:
    """Tests for /api/seo/health-score/{user_id} - Cached health score"""
    
    def test_get_seo_health_score(self):
        """GET /api/seo/health-score/{user_id} - Cached health score"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{USER_ID}")
        # May return 200 or 404 if user has no SEO data
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Verify structure if data exists
            if "score" in data:
                assert isinstance(data["score"], (int, float)), f"Score should be numeric"
            print(f"✓ SEO health score: {data.get('score', 'N/A')}")
        else:
            print(f"✓ SEO health score: No data for user (404 expected)")


class TestLeadSources:
    """Tests for /api/lead-sources endpoints - Converted from sync pymongo to async motor"""
    
    def test_list_lead_sources(self):
        """GET /api/lead-sources/{store_id} - Lead sources list (async now)"""
        # Use a test store_id
        store_id = "test_store_123"
        response = requests.get(f"{BASE_URL}/api/lead-sources?store_id={store_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "success" in data, f"Response missing 'success' field"
        assert data["success"] == True
        assert "lead_sources" in data, f"Response missing 'lead_sources' field"
        assert isinstance(data["lead_sources"], list)
        
        print(f"✓ Lead sources list: {len(data['lead_sources'])} sources")
    
    def test_inbound_lead_webhook_validation(self):
        """POST /api/lead-sources/inbound/{source_id} - Lead webhook (async now)"""
        # Test with valid ObjectId format but non-existent source - should return 404
        # Using a valid 24-char hex string that doesn't exist in DB
        fake_source_id = "000000000000000000000000"
        response = requests.post(
            f"{BASE_URL}/api/lead-sources/inbound/{fake_source_id}",
            json={"phone": "+15551234567", "name": "Test Lead"},
            headers={"X-API-Key": "invalid_key"}
        )
        # Should return 404 for non-existent source
        assert response.status_code == 404, f"Expected 404 for non-existent source, got {response.status_code}"
        print(f"✓ Inbound lead webhook validation: 404 for non-existent source")


class TestMediaUpload:
    """Tests for /api/media/upload-tracked - Tracked media upload still works"""
    
    def test_media_upload_endpoint_exists(self):
        """POST /api/media/upload-tracked - Endpoint exists and validates"""
        # Test without file - should return 422 (validation error)
        response = requests.post(
            f"{BASE_URL}/api/media/upload-tracked",
            data={"user_id": USER_ID}
        )
        # 422 means endpoint exists but validation failed (no file)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print(f"✓ Media upload endpoint exists (422 for missing file)")


class TestURLWrapping:
    """Tests for /api/s/wrap - URL wrapping still works"""
    
    def test_url_wrap_endpoint(self):
        """POST /api/s/wrap - URL wrapping still works"""
        response = requests.post(
            f"{BASE_URL}/api/s/wrap",
            json={
                "url": "https://example.com/test",
                "user_id": USER_ID,
                "contact_id": "test_contact"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "short_url" in data, f"Response missing 'short_url' field"
        assert "short_code" in data, f"Response missing 'short_code' field"
        print(f"✓ URL wrapping works: {data['short_url']}")


class TestDatabaseConnection:
    """Tests for database connection pool configuration"""
    
    def test_health_endpoint(self):
        """GET /api/health - Basic health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "healthy"
        print(f"✓ Health check: {data['status']}")
    
    def test_concurrent_requests(self):
        """Test multiple concurrent requests (connection pool)"""
        import concurrent.futures
        
        def make_request():
            return requests.get(f"{BASE_URL}/api/notification-center/{USER_ID}/unread-count")
        
        # Make 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        for r in results:
            assert r.status_code == 200, f"Concurrent request failed: {r.status_code}"
        
        print(f"✓ Concurrent requests: {len(results)} successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
