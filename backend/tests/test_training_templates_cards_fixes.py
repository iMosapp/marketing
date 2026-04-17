"""
Test suite for bug fixes:
1. Training tracks auto-seeding (onboarding-videos with 8 lessons)
2. Templates with tracked short URLs for training_video category
3. Short URL stats showing link_type=training_video
4. Short URL redirect incrementing click_count
5. Custom card type saving and retrieval in card templates
"""
import os
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
USER_ID = "69a0b7095fddcede09591667"
STORE_ID = "69a0b7095fddcede09591668"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
        "X-User-ID": USER_ID
    })
    return session


class TestTrainingTracksAutoSeed:
    """Test training tracks auto-seeding with onboarding-videos track"""
    
    def test_get_tracks_returns_onboarding_videos(self, api_client):
        """GET /api/training/tracks?role=super_admin should return onboarding-videos track"""
        response = api_client.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        tracks = response.json()
        assert isinstance(tracks, list), "Response should be a list of tracks"
        
        # Find onboarding-videos track
        onboarding_track = None
        for track in tracks:
            if track.get("slug") == "onboarding-videos":
                onboarding_track = track
                break
        
        assert onboarding_track is not None, "onboarding-videos track should exist"
        print(f"Found onboarding-videos track: {onboarding_track.get('title')}")
        
    def test_onboarding_videos_has_8_lessons(self, api_client):
        """onboarding-videos track should have 8 lessons"""
        response = api_client.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        assert response.status_code == 200
        
        tracks = response.json()
        onboarding_track = next((t for t in tracks if t.get("slug") == "onboarding-videos"), None)
        
        assert onboarding_track is not None, "onboarding-videos track should exist"
        assert onboarding_track.get("lesson_count") == 8, f"Expected 8 lessons, got {onboarding_track.get('lesson_count')}"
        print(f"onboarding-videos has {onboarding_track.get('lesson_count')} lessons")
        
    def test_tracks_count_at_least_5(self, api_client):
        """Should have at least 5 tracks (all seed tracks)"""
        response = api_client.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        assert response.status_code == 200
        
        tracks = response.json()
        assert len(tracks) >= 5, f"Expected at least 5 tracks, got {len(tracks)}"
        
        track_slugs = [t.get("slug") for t in tracks]
        print(f"Found {len(tracks)} tracks: {track_slugs}")


class TestTemplatesWithTrackedShortURLs:
    """Test templates return tracked short URLs for training_video category"""
    
    def test_get_templates_returns_training_video_templates(self, api_client):
        """GET /api/templates/{user_id} should return training_video templates"""
        response = api_client.get(f"{BASE_URL}/api/templates/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list of templates"
        
        # Find training_video templates
        video_templates = [t for t in templates if t.get("category") == "training_video"]
        assert len(video_templates) > 0, "Should have training_video templates"
        print(f"Found {len(video_templates)} training_video templates")
        
    def test_training_video_templates_have_tracked_urls(self, api_client):
        """training_video templates should have tracked short URLs (containing /api/s/)"""
        response = api_client.get(f"{BASE_URL}/api/templates/{USER_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        video_templates = [t for t in templates if t.get("category") == "training_video"]
        
        assert len(video_templates) > 0, "Should have training_video templates"
        
        # Check that at least one template has a tracked URL
        tracked_count = 0
        for template in video_templates:
            content = template.get("content", "")
            if "/api/s/" in content:
                tracked_count += 1
                print(f"Template '{template.get('name')}' has tracked URL")
            elif "youtube.com" in content or "youtu.be" in content:
                print(f"WARNING: Template '{template.get('name')}' still has raw YouTube URL")
        
        assert tracked_count > 0, "At least one training_video template should have tracked short URL (/api/s/)"
        print(f"{tracked_count}/{len(video_templates)} templates have tracked URLs")
        
    def test_extract_short_code_from_template(self, api_client):
        """Extract a short code from a training_video template for further testing"""
        response = api_client.get(f"{BASE_URL}/api/templates/{USER_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        video_templates = [t for t in templates if t.get("category") == "training_video"]
        
        short_code = None
        for template in video_templates:
            content = template.get("content", "")
            # Extract short code from /api/s/{short_code}
            match = re.search(r'/api/s/([a-zA-Z0-9]+)', content)
            if match:
                short_code = match.group(1)
                print(f"Extracted short code: {short_code} from template '{template.get('name')}'")
                break
        
        assert short_code is not None, "Should be able to extract a short code from training_video template"
        return short_code


class TestShortURLStats:
    """Test short URL stats endpoint"""
    
    def test_get_short_url_stats_for_training_video(self, api_client):
        """GET /api/s/stats/{short_code} should show link_type=training_video"""
        # First get a short code from templates
        response = api_client.get(f"{BASE_URL}/api/templates/{USER_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        video_templates = [t for t in templates if t.get("category") == "training_video"]
        
        short_code = None
        for template in video_templates:
            content = template.get("content", "")
            match = re.search(r'/api/s/([a-zA-Z0-9]+)', content)
            if match:
                short_code = match.group(1)
                break
        
        if not short_code:
            pytest.skip("No short code found in training_video templates")
        
        # Get stats for the short code
        stats_response = api_client.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response.status_code == 200, f"Expected 200, got {stats_response.status_code}: {stats_response.text}"
        
        stats = stats_response.json()
        assert stats.get("link_type") == "training_video", f"Expected link_type=training_video, got {stats.get('link_type')}"
        assert "youtube.com" in stats.get("original_url", "") or "youtu.be" in stats.get("original_url", ""), "Original URL should be YouTube"
        print(f"Short URL stats: link_type={stats.get('link_type')}, click_count={stats.get('click_count')}")


class TestShortURLRedirect:
    """Test short URL redirect increments click_count"""
    
    def test_short_url_redirect_increments_click_count(self, api_client):
        """GET /api/s/{short_code} should redirect and increment click_count"""
        # First get a short code from templates
        response = api_client.get(f"{BASE_URL}/api/templates/{USER_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        video_templates = [t for t in templates if t.get("category") == "training_video"]
        
        short_code = None
        for template in video_templates:
            content = template.get("content", "")
            match = re.search(r'/api/s/([a-zA-Z0-9]+)', content)
            if match:
                short_code = match.group(1)
                break
        
        if not short_code:
            pytest.skip("No short code found in training_video templates")
        
        # Get initial click count
        stats_before = api_client.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_before.status_code == 200
        initial_clicks = stats_before.json().get("click_count", 0)
        
        # Access the short URL (don't follow redirects to avoid leaving the test)
        redirect_response = requests.get(f"{BASE_URL}/api/s/{short_code}", allow_redirects=False)
        # Should return HTML with redirect or 302
        assert redirect_response.status_code in [200, 302, 307], f"Expected redirect response, got {redirect_response.status_code}"
        
        # Get click count after
        stats_after = api_client.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_after.status_code == 200
        new_clicks = stats_after.json().get("click_count", 0)
        
        assert new_clicks > initial_clicks, f"Click count should have increased. Before: {initial_clicks}, After: {new_clicks}"
        print(f"Click count incremented: {initial_clicks} -> {new_clicks}")


class TestCustomCardTemplates:
    """Test custom card type saving and retrieval"""
    
    def test_save_custom_card_template(self, api_client):
        """POST /api/congrats/template/{store_id} with card_type='custom' should save successfully"""
        custom_template = {
            "card_type": "custom",
            "headline": "Test Custom Card",
            "message": "Hey {customer_name}, this is a custom test card!",
            "accent_color": "#FF5500",
            "footer_text": "Test footer"
        }
        
        response = api_client.post(f"{BASE_URL}/api/congrats/template/{STORE_ID}", json=custom_template)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get("success") == True, f"Expected success=True, got {result}"
        print(f"Custom card template saved: {result}")
        
    def test_get_all_templates_includes_custom(self, api_client):
        """GET /api/congrats/templates/all/{store_id} should include custom card_type"""
        response = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{STORE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list of templates"
        
        # Find custom card type
        custom_template = None
        for template in templates:
            if template.get("card_type") == "custom":
                custom_template = template
                break
        
        assert custom_template is not None, "custom card_type should be in the templates list"
        assert custom_template.get("headline") == "Test Custom Card", f"Expected headline 'Test Custom Card', got {custom_template.get('headline')}"
        print(f"Found custom template: {custom_template}")
        
    def test_standard_card_types_present(self, api_client):
        """Standard card types (congrats, birthday, etc.) should be present"""
        response = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{STORE_ID}")
        assert response.status_code == 200
        
        templates = response.json()
        card_types = [t.get("card_type") for t in templates]
        
        expected_types = ["congrats", "birthday", "anniversary", "thankyou", "welcome", "holiday"]
        for expected in expected_types:
            assert expected in card_types, f"Expected card_type '{expected}' to be present"
        
        print(f"All standard card types present: {expected_types}")


class TestTrainingHubIntegration:
    """Integration tests for training hub functionality"""
    
    def test_get_track_detail_with_lessons(self, api_client):
        """GET /api/training/tracks/{track_id} should return track with lessons"""
        # First get tracks to find onboarding-videos ID
        tracks_response = api_client.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        assert tracks_response.status_code == 200
        
        tracks = tracks_response.json()
        onboarding_track = next((t for t in tracks if t.get("slug") == "onboarding-videos"), None)
        
        if not onboarding_track:
            pytest.skip("onboarding-videos track not found")
        
        track_id = onboarding_track.get("id")
        
        # Get track detail
        detail_response = api_client.get(f"{BASE_URL}/api/training/tracks/{track_id}")
        assert detail_response.status_code == 200, f"Expected 200, got {detail_response.status_code}: {detail_response.text}"
        
        detail = detail_response.json()
        assert detail.get("slug") == "onboarding-videos"
        assert "lessons" in detail, "Track detail should include lessons"
        assert len(detail.get("lessons", [])) == 8, f"Expected 8 lessons, got {len(detail.get('lessons', []))}"
        
        # Check lessons have video URLs
        lessons_with_video = [l for l in detail.get("lessons", []) if l.get("video_url")]
        print(f"Track has {len(lessons_with_video)} lessons with video URLs")
        
        # Print lesson titles
        for lesson in detail.get("lessons", []):
            print(f"  - {lesson.get('title')}: {lesson.get('video_url', 'No video')[:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
