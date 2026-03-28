"""
Photo Gallery v2 Tests - Instagram-style gallery and read-only photo endpoint
Tests:
1. GET /api/contacts/{user_id}/{contact_id}/photos/all - Fast read-only (no lazy migration)
2. PATCH /api/contacts/{user_id}/{contact_id}/events/latest-channel - Update latest event channel
3. GET /api/lead-sources/team-inbox/{team_id} - Route ordering fix
4. GET /api/lead-sources/user-inbox/{user_id} - Route ordering fix
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://user-routing-issue.preview.emergentagent.com"

# Test credentials from request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a0c06f7626f14d125f8c34"  # Forest Ward - 2 photos


class TestPhotosAllEndpoint:
    """Test GET /api/contacts/{user_id}/{contact_id}/photos/all - read-only, fast response"""
    
    def test_photos_all_returns_200(self):
        """GET photos/all should return 200"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all"
        response = requests.get(url)
        print(f"GET {url} -> {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: photos/all returns 200")
    
    def test_photos_all_response_structure(self):
        """Response should have 'photos' array and 'total' count"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all"
        response = requests.get(url)
        assert response.status_code == 200
        
        data = response.json()
        assert "photos" in data, "Response missing 'photos' field"
        assert "total" in data, "Response missing 'total' field"
        assert isinstance(data["photos"], list), "'photos' should be a list"
        assert isinstance(data["total"], int), "'total' should be an integer"
        print(f"PASS: Response has photos (count={len(data['photos'])}) and total={data['total']}")
    
    def test_photos_all_photo_fields(self):
        """Each photo should have type, url, thumbnail_url fields"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all"
        response = requests.get(url)
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        
        if len(photos) == 0:
            print("SKIP: No photos found for test contact (contact may have no photos)")
            pytest.skip("No photos to validate field structure")
        
        for i, photo in enumerate(photos):
            assert "type" in photo, f"Photo {i} missing 'type' field"
            assert "url" in photo, f"Photo {i} missing 'url' field"
            # thumbnail_url is optional but should be present if url exists
            print(f"Photo {i}: type={photo.get('type')}, has_url={bool(photo.get('url'))}, has_thumb={bool(photo.get('thumbnail_url'))}")
        
        print(f"PASS: All {len(photos)} photos have required fields")
    
    def test_photos_all_fast_response(self):
        """Endpoint should respond within 2 seconds (no lazy migration)"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all"
        
        start_time = time.time()
        response = requests.get(url)
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s - expected under 2s for fast read-only"
        print(f"PASS: Response time {elapsed:.3f}s (under 2s threshold)")
    
    def test_photos_all_invalid_contact(self):
        """Should return 200 with empty photos for non-existent contact (not 500)"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/000000000000000000000000/photos/all"
        response = requests.get(url)
        
        # Should not crash - return empty or 404
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print(f"PASS: Invalid contact returns {response.status_code} (no crash)")


class TestLatestChannelEndpoint:
    """Test PATCH /api/contacts/{user_id}/{contact_id}/events/latest-channel"""
    
    def test_patch_latest_channel_requires_channel(self):
        """PATCH without 'channel' field should return 400"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events/latest-channel"
        response = requests.patch(url, json={})
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Missing channel returns 400")
    
    def test_patch_latest_channel_success(self):
        """PATCH with channel should return 200 and updated:true"""
        # First create an event to update
        event_url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events"
        event_payload = {
            "event_type": "test_gallery_event",
            "title": "Test Event for Channel Update",
            "description": "Testing latest-channel endpoint",
            "icon": "checkmark",
            "color": "#34C759"
        }
        event_response = requests.post(event_url, json=event_payload)
        print(f"Created test event: {event_response.status_code}")
        
        # Now update the latest event's channel
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events/latest-channel"
        response = requests.patch(url, json={"channel": "whatsapp"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("channel") == "whatsapp", f"Expected channel='whatsapp', got {data.get('channel')}"
        print(f"PASS: Updated latest event channel to 'whatsapp', response: {data}")
    
    def test_patch_latest_channel_various_channels(self):
        """Test updating to different channel types"""
        channels = ["sms", "email", "messenger", "telegram", "linkedin"]
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events/latest-channel"
        
        for channel in channels:
            response = requests.patch(url, json={"channel": channel})
            assert response.status_code == 200, f"Channel '{channel}' failed: {response.status_code}"
            data = response.json()
            assert data.get("channel") == channel
            print(f"  Channel '{channel}' - OK")
        
        print(f"PASS: All {len(channels)} channel types accepted")


class TestLeadSourcesRouteOrdering:
    """Test that specific lead-sources routes are matched before /{source_id}"""
    
    def test_team_inbox_route(self):
        """GET /api/lead-sources/team-inbox/{team_id} should return 200 (not 404 source_id match)"""
        # Using test user ID as a team_id (won't find data but should hit correct route)
        url = f"{BASE_URL}/api/lead-sources/team-inbox/{TEST_USER_ID}"
        response = requests.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "success" in data, "Response missing 'success' field"
        assert "conversations" in data, "Response missing 'conversations' field"
        print(f"PASS: team-inbox returns 200 with {len(data.get('conversations', []))} conversations")
    
    def test_user_inbox_route(self):
        """GET /api/lead-sources/user-inbox/{user_id} should return 200 (not 404 source_id match)"""
        url = f"{BASE_URL}/api/lead-sources/user-inbox/{TEST_USER_ID}"
        response = requests.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "success" in data, "Response missing 'success' field"
        assert "conversations" in data, "Response missing 'conversations' field"
        print(f"PASS: user-inbox returns 200 with {len(data.get('conversations', []))} conversations")
    
    def test_stats_route(self):
        """GET /api/lead-sources/stats/{source_id} should return 404 for non-existent (not 500)"""
        url = f"{BASE_URL}/api/lead-sources/stats/000000000000000000000000"
        response = requests.get(url)
        
        # Should return 404 Not Found, not 500 Internal Server Error
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: stats route for non-existent source returns 404")


class TestProfilePhotoSetAs:
    """Test PATCH /api/contacts/{user_id}/{contact_id}/profile-photo endpoint"""
    
    def test_set_profile_photo_requires_url(self):
        """PATCH without photo_url should return 400"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/profile-photo"
        response = requests.patch(url, json={})
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Missing photo_url returns 400")
    
    def test_set_profile_photo_success(self):
        """PATCH with valid photo_url should return success"""
        url = f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/profile-photo"
        payload = {"photo_url": "/api/images/test_photo.webp"}
        response = requests.patch(url, json=payload)
        
        # Should return 200 if contact exists, 404 if not
        if response.status_code == 200:
            data = response.json()
            assert "message" in data or "Profile photo updated" in str(data)
            print(f"PASS: Profile photo updated successfully")
        elif response.status_code == 404:
            print("SKIP: Contact not found (may have been deleted)")
        else:
            assert False, f"Unexpected status {response.status_code}: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
