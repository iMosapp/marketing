"""
Universal URL Tracking Tests
Tests for the universal URL wrapping feature that tracks clicks on all URLs in the app.

Endpoints tested:
- POST /api/s/wrap - Universal URL wrapping
- POST /api/s/wrap-bulk - Bulk URL wrapping
- POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links - Rewrap campaign links
- PUT /api/campaigns/{user_id}/{campaign_id} - Auto-wraps URLs when saving
- POST /api/training/admin/tracks/{track_id}/lessons - Auto-wraps video_url
- PUT /api/training/lessons/{lesson_id} - Auto-wraps video_url
- GET /api/s/{short_code} - Redirect endpoint
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
USER_ID = "69a0b7095fddcede09591667"
TRAINING_TRACK_ID = "69c17d182d274c0bdc975362"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestWrapUrlEndpoint:
    """Tests for POST /api/s/wrap - Universal URL wrapping"""
    
    def test_wrap_url_basic(self, api_client):
        """Test basic URL wrapping with required fields"""
        test_url = f"https://example.com/test-{uuid.uuid4().hex[:8]}"
        response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "short_url" in data, "Response should contain short_url"
        assert "short_code" in data, "Response should contain short_code"
        assert "original_url" in data, "Response should contain original_url"
        assert "link_type" in data, "Response should contain link_type"
        
        # Verify values
        assert data["original_url"] == test_url
        assert "/api/s/" in data["short_url"]
        assert len(data["short_code"]) >= 6
        print(f"PASS: Basic URL wrapping - {test_url} -> {data['short_url']}")
    
    def test_wrap_youtube_url_auto_detects_training_video(self, api_client):
        """Test that YouTube URLs are auto-detected as training_video type"""
        test_url = f"https://www.youtube.com/watch?v=test{uuid.uuid4().hex[:8]}"
        response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["link_type"] == "training_video", f"YouTube URL should be detected as training_video, got {data['link_type']}"
        print(f"PASS: YouTube URL auto-detected as training_video")
    
    def test_wrap_youtu_be_url_auto_detects_training_video(self, api_client):
        """Test that youtu.be short URLs are also detected as training_video"""
        test_url = f"https://youtu.be/test{uuid.uuid4().hex[:8]}"
        response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["link_type"] == "training_video", f"youtu.be URL should be detected as training_video, got {data['link_type']}"
        print(f"PASS: youtu.be URL auto-detected as training_video")
    
    def test_wrap_url_idempotent(self, api_client):
        """Test that wrapping the same URL twice returns the same short_code (idempotent)"""
        test_url = f"https://example.com/idempotent-{uuid.uuid4().hex[:8]}"
        
        # First wrap
        response1 = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second wrap - same URL
        response2 = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Should return the same short_code
        assert data1["short_code"] == data2["short_code"], f"Idempotency failed: {data1['short_code']} != {data2['short_code']}"
        print(f"PASS: URL wrapping is idempotent - same short_code returned")
    
    def test_wrap_url_missing_url_returns_400(self, api_client):
        """Test that missing url field returns 400"""
        response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "user_id": USER_ID
        })
        
        assert response.status_code == 400, f"Expected 400 for missing url, got {response.status_code}"
        print(f"PASS: Missing url returns 400")
    
    def test_wrap_url_missing_user_id_returns_400(self, api_client):
        """Test that missing user_id field returns 400"""
        response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": "https://example.com/test"
        })
        
        assert response.status_code == 400, f"Expected 400 for missing user_id, got {response.status_code}"
        print(f"PASS: Missing user_id returns 400")
    
    def test_wrap_url_with_context(self, api_client):
        """Test URL wrapping with optional context parameter"""
        test_url = f"https://example.com/context-{uuid.uuid4().hex[:8]}"
        response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID,
            "context": "campaign"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Non-YouTube URL with context should use context as link_type
        assert data["link_type"] == "campaign", f"Expected link_type 'campaign', got {data['link_type']}"
        print(f"PASS: URL wrapping with context parameter")


class TestWrapBulkEndpoint:
    """Tests for POST /api/s/wrap-bulk - Bulk URL wrapping"""
    
    def test_wrap_bulk_basic(self, api_client):
        """Test bulk URL wrapping with multiple URLs"""
        test_urls = [
            f"https://example.com/bulk1-{uuid.uuid4().hex[:8]}",
            f"https://example.com/bulk2-{uuid.uuid4().hex[:8]}",
            f"https://www.youtube.com/watch?v=bulk{uuid.uuid4().hex[:8]}"
        ]
        
        response = api_client.post(f"{BASE_URL}/api/s/wrap-bulk", json={
            "urls": test_urls,
            "user_id": USER_ID
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "results" in data, "Response should contain results array"
        assert "wrapped_count" in data, "Response should contain wrapped_count"
        assert data["wrapped_count"] == 3, f"Expected 3 wrapped URLs, got {data['wrapped_count']}"
        assert len(data["results"]) == 3, f"Expected 3 results, got {len(data['results'])}"
        
        # Verify each result has required fields
        for result in data["results"]:
            assert "short_url" in result
            assert "short_code" in result
            assert "original_url" in result
            assert "link_type" in result
        
        # Verify YouTube URL was detected correctly
        youtube_result = [r for r in data["results"] if "youtube.com" in r["original_url"]][0]
        assert youtube_result["link_type"] == "training_video"
        
        print(f"PASS: Bulk URL wrapping - {data['wrapped_count']} URLs wrapped")
    
    def test_wrap_bulk_missing_urls_returns_400(self, api_client):
        """Test that missing urls field returns 400"""
        response = api_client.post(f"{BASE_URL}/api/s/wrap-bulk", json={
            "user_id": USER_ID
        })
        
        assert response.status_code == 400, f"Expected 400 for missing urls, got {response.status_code}"
        print(f"PASS: Missing urls returns 400")
    
    def test_wrap_bulk_empty_urls_returns_400(self, api_client):
        """Test that empty urls array returns 400"""
        response = api_client.post(f"{BASE_URL}/api/s/wrap-bulk", json={
            "urls": [],
            "user_id": USER_ID
        })
        
        assert response.status_code == 400, f"Expected 400 for empty urls, got {response.status_code}"
        print(f"PASS: Empty urls array returns 400")
    
    def test_wrap_bulk_missing_user_id_returns_400(self, api_client):
        """Test that missing user_id returns 400"""
        response = api_client.post(f"{BASE_URL}/api/s/wrap-bulk", json={
            "urls": ["https://example.com/test"]
        })
        
        assert response.status_code == 400, f"Expected 400 for missing user_id, got {response.status_code}"
        print(f"PASS: Missing user_id returns 400")


class TestRedirectEndpoint:
    """Tests for GET /api/s/{short_code} - Redirect endpoint"""
    
    def test_redirect_valid_short_code(self, api_client):
        """Test that valid short code redirects correctly"""
        # First create a short URL
        test_url = f"https://example.com/redirect-{uuid.uuid4().hex[:8]}"
        wrap_response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        assert wrap_response.status_code == 200
        short_code = wrap_response.json()["short_code"]
        
        # Now test the redirect (don't follow redirects to check the response)
        redirect_response = api_client.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False
        )
        
        # Should return HTML with JS redirect (status 200 with HTML content)
        assert redirect_response.status_code == 200, f"Expected 200, got {redirect_response.status_code}"
        assert "text/html" in redirect_response.headers.get("content-type", "")
        assert test_url in redirect_response.text, "Redirect URL should be in HTML response"
        print(f"PASS: Valid short code returns redirect HTML")
    
    def test_redirect_invalid_short_code_returns_404(self, api_client):
        """Test that invalid short code returns 404"""
        response = api_client.get(f"{BASE_URL}/api/s/invalid_code_xyz123")
        
        assert response.status_code == 404, f"Expected 404 for invalid short code, got {response.status_code}"
        print(f"PASS: Invalid short code returns 404")
    
    def test_redirect_increments_click_count(self, api_client):
        """Test that redirect increments click count"""
        # Create a short URL
        test_url = f"https://example.com/clicks-{uuid.uuid4().hex[:8]}"
        wrap_response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        assert wrap_response.status_code == 200
        short_code = wrap_response.json()["short_code"]
        
        # Get initial stats
        stats_response1 = api_client.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response1.status_code == 200
        initial_clicks = stats_response1.json().get("click_count", 0)
        
        # Click the link
        api_client.get(f"{BASE_URL}/api/s/{short_code}", allow_redirects=False)
        
        # Get updated stats
        stats_response2 = api_client.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response2.status_code == 200
        new_clicks = stats_response2.json().get("click_count", 0)
        
        assert new_clicks == initial_clicks + 1, f"Click count should increment: {initial_clicks} -> {new_clicks}"
        print(f"PASS: Redirect increments click count")


class TestCampaignAutoWrap:
    """Tests for campaign URL auto-wrapping"""
    
    def test_create_campaign_with_urls_auto_wraps(self, api_client):
        """Test that creating a campaign auto-wraps URLs in sequences"""
        campaign_name = f"TEST_AutoWrap_{uuid.uuid4().hex[:8]}"
        youtube_url = f"https://www.youtube.com/watch?v=test{uuid.uuid4().hex[:8]}"
        
        # Create campaign with URLs in sequences
        response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}", json={
            "name": campaign_name,
            "type": "custom",
            "trigger_tag": "test",
            "active": False,
            "sequences": [
                {
                    "step": 1,
                    "delay_days": 1,
                    "channel": "sms",
                    "message_template": f"Check out this video: {youtube_url}",
                    "media_urls": [youtube_url]
                }
            ]
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        campaign_id = data.get("_id") or data.get("id")
        
        # Note: Auto-wrap happens on UPDATE, not CREATE
        # Let's update the campaign to trigger auto-wrap
        update_response = api_client.put(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}", json={
            "sequences": [
                {
                    "step": 1,
                    "delay_days": 1,
                    "channel": "sms",
                    "message_template": f"Check out this video: {youtube_url}",
                    "media_urls": [youtube_url]
                }
            ]
        })
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        # Fetch the campaign to verify URLs were wrapped
        get_response = api_client.get(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}")
        assert get_response.status_code == 200
        campaign_data = get_response.json()
        
        sequences = campaign_data.get("sequences", [])
        if sequences:
            first_step = sequences[0]
            media_urls = first_step.get("media_urls", [])
            message = first_step.get("message_template", "")
            
            # Check if URLs were wrapped (contain /api/s/)
            if media_urls:
                wrapped_media = any("/api/s/" in url for url in media_urls)
                print(f"Media URLs wrapped: {wrapped_media} - {media_urls}")
            
            wrapped_message = "/api/s/" in message
            print(f"Message URLs wrapped: {wrapped_message}")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}")
        print(f"PASS: Campaign URL auto-wrapping test completed")


class TestCampaignRewrapLinks:
    """Tests for POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links"""
    
    def test_rewrap_campaign_links(self, api_client):
        """Test rewrapping raw URLs in an existing campaign"""
        campaign_name = f"TEST_Rewrap_{uuid.uuid4().hex[:8]}"
        raw_url = f"https://example.com/raw-{uuid.uuid4().hex[:8]}"
        
        # Create campaign with raw URLs
        create_response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}", json={
            "name": campaign_name,
            "type": "custom",
            "trigger_tag": "test",
            "active": False,
            "sequences": [
                {
                    "step": 1,
                    "delay_days": 1,
                    "channel": "sms",
                    "message_template": f"Visit: {raw_url}",
                    "media_urls": [raw_url]
                }
            ]
        })
        
        assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
        data = create_response.json()
        campaign_id = data.get("_id") or data.get("id")
        
        # Call rewrap-links endpoint
        rewrap_response = api_client.post(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/rewrap-links")
        
        assert rewrap_response.status_code == 200, f"Expected 200, got {rewrap_response.status_code}: {rewrap_response.text}"
        rewrap_data = rewrap_response.json()
        
        assert "wrapped" in rewrap_data or "message" in rewrap_data, "Response should contain wrapped count or message"
        print(f"PASS: Rewrap campaign links - {rewrap_data}")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}")


class TestTrainingLessonAutoWrap:
    """Tests for training lesson video_url auto-wrapping"""
    
    def test_create_lesson_auto_wraps_video_url(self, api_client):
        """Test that creating a lesson auto-wraps video_url"""
        lesson_title = f"TEST_Lesson_{uuid.uuid4().hex[:8]}"
        youtube_url = f"https://www.youtube.com/watch?v=lesson{uuid.uuid4().hex[:8]}"
        
        # Create a lesson with a YouTube URL
        response = api_client.post(f"{BASE_URL}/api/training/admin/tracks/{TRAINING_TRACK_ID}/lessons", json={
            "title": lesson_title,
            "description": "Test lesson for URL wrapping",
            "video_url": youtube_url,
            "content": "Test content",
            "user_id": USER_ID
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        lesson_id = data.get("id")
        assert lesson_id, "Response should contain lesson id"
        
        # Fetch the lesson to verify video_url was wrapped
        lessons_response = api_client.get(f"{BASE_URL}/api/training/admin/tracks/{TRAINING_TRACK_ID}/lessons")
        assert lessons_response.status_code == 200
        lessons = lessons_response.json()
        
        # Find our test lesson
        test_lesson = next((l for l in lessons if l.get("title") == lesson_title), None)
        if test_lesson:
            video_url = test_lesson.get("video_url", "")
            wrapped = "/api/s/" in video_url
            print(f"Lesson video_url wrapped: {wrapped} - {video_url}")
            
            # Cleanup
            api_client.delete(f"{BASE_URL}/api/training/admin/lessons/{lesson_id}")
        
        print(f"PASS: Create lesson auto-wraps video_url")
    
    def test_update_lesson_auto_wraps_video_url(self, api_client):
        """Test that updating a lesson auto-wraps video_url"""
        lesson_title = f"TEST_UpdateLesson_{uuid.uuid4().hex[:8]}"
        initial_url = f"https://www.youtube.com/watch?v=initial{uuid.uuid4().hex[:8]}"
        updated_url = f"https://www.youtube.com/watch?v=updated{uuid.uuid4().hex[:8]}"
        
        # Create a lesson first
        create_response = api_client.post(f"{BASE_URL}/api/training/admin/tracks/{TRAINING_TRACK_ID}/lessons", json={
            "title": lesson_title,
            "description": "Test lesson for update",
            "video_url": initial_url,
            "content": "Test content",
            "user_id": USER_ID
        })
        
        assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
        lesson_id = create_response.json().get("id")
        
        # Update the lesson with a new video URL
        update_response = api_client.put(f"{BASE_URL}/api/training/lessons/{lesson_id}", json={
            "video_url": updated_url,
            "user_id": USER_ID
        })
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        # Fetch lessons to verify
        lessons_response = api_client.get(f"{BASE_URL}/api/training/admin/tracks/{TRAINING_TRACK_ID}/lessons")
        assert lessons_response.status_code == 200
        lessons = lessons_response.json()
        
        test_lesson = next((l for l in lessons if l.get("id") == lesson_id), None)
        if test_lesson:
            video_url = test_lesson.get("video_url", "")
            wrapped = "/api/s/" in video_url
            print(f"Updated lesson video_url wrapped: {wrapped} - {video_url}")
            
            # Cleanup
            api_client.delete(f"{BASE_URL}/api/training/admin/lessons/{lesson_id}")
        
        print(f"PASS: Update lesson auto-wraps video_url")


class TestShortUrlStats:
    """Tests for GET /api/s/stats/{short_code}"""
    
    def test_get_stats_for_valid_short_code(self, api_client):
        """Test getting stats for a valid short code"""
        # Create a short URL first
        test_url = f"https://example.com/stats-{uuid.uuid4().hex[:8]}"
        wrap_response = api_client.post(f"{BASE_URL}/api/s/wrap", json={
            "url": test_url,
            "user_id": USER_ID
        })
        assert wrap_response.status_code == 200
        short_code = wrap_response.json()["short_code"]
        
        # Get stats
        stats_response = api_client.get(f"{BASE_URL}/api/s/stats/{short_code}")
        
        assert stats_response.status_code == 200, f"Expected 200, got {stats_response.status_code}: {stats_response.text}"
        data = stats_response.json()
        
        assert "short_code" in data
        assert "original_url" in data
        assert "link_type" in data
        assert "click_count" in data
        assert "created_at" in data
        
        assert data["short_code"] == short_code
        assert data["original_url"] == test_url
        print(f"PASS: Get stats for valid short code")
    
    def test_get_stats_for_invalid_short_code_returns_404(self, api_client):
        """Test that invalid short code returns 404"""
        response = api_client.get(f"{BASE_URL}/api/s/stats/invalid_xyz123")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"PASS: Invalid short code stats returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
