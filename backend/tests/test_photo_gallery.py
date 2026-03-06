"""
Photo Gallery API Tests
Tests for the redesigned Facebook-style photo reel feature
- /api/contacts/{user_id}/{contact_id}/photos/all endpoint
- Set as Profile Photo functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from problem statement
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID_WITH_PHOTOS = "69a0c06f7626f14d125f8c34"  # Forest Ward contact with 11 photos


class TestPhotoGalleryAPI:
    """Tests for the photo gallery endpoint"""
    
    def test_photos_all_endpoint_returns_data(self):
        """Test that /photos/all endpoint returns photos with thumbnail_url"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "photos" in data, "Response should contain 'photos' key"
        assert "total" in data, "Response should contain 'total' key"
        print(f"SUCCESS: photos/all returned {data['total']} photos")
    
    def test_photos_have_url_and_thumbnail_url(self):
        """Test that each photo has both url and thumbnail_url fields"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        assert len(photos) > 0, "Should have at least one photo"
        
        for idx, photo in enumerate(photos):
            assert "url" in photo, f"Photo {idx} missing 'url' field"
            assert "thumbnail_url" in photo, f"Photo {idx} missing 'thumbnail_url' field"
            assert photo["url"], f"Photo {idx} has empty 'url'"
            assert photo["thumbnail_url"], f"Photo {idx} has empty 'thumbnail_url'"
        
        print(f"SUCCESS: All {len(photos)} photos have url and thumbnail_url fields")
    
    def test_photos_have_type_badges(self):
        """Test that photos have type field for badges (PROFILE, CONGRATS, BIRTHDAY, etc)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        
        photo_types = set()
        for photo in photos:
            assert "type" in photo, f"Photo missing 'type' field: {photo}"
            photo_types.add(photo["type"])
        
        # Should have multiple types based on test data
        print(f"SUCCESS: Found photo types: {photo_types}")
        assert len(photo_types) >= 1, "Should have at least one photo type"
    
    def test_photos_total_count(self):
        """Test that the total count matches number of photos"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        total = data.get("total", 0)
        
        assert total == len(photos), f"Total ({total}) should match photo count ({len(photos)})"
        assert total >= 10, f"Expected at least 10 photos, got {total}"  # Contact should have 11 photos
        print(f"SUCCESS: Photo count {total} matches array length")
    
    def test_profile_photo_first(self):
        """Test that profile photo appears first in the list"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        
        if photos:
            first_photo = photos[0]
            assert first_photo.get("type") == "profile", f"First photo should be profile, got: {first_photo.get('type')}"
            print("SUCCESS: Profile photo appears first in gallery")
    
    def test_thumbnail_urls_are_webp(self):
        """Test that thumbnail URLs point to optimized WebP format"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        
        webp_count = 0
        for photo in photos:
            thumb_url = photo.get("thumbnail_url", "")
            if "_thumb.webp" in thumb_url or thumb_url.endswith(".webp"):
                webp_count += 1
        
        # Most thumbnails should be WebP (except profile photo which may be legacy)
        total_non_profile = len([p for p in photos if p.get("type") != "profile"])
        assert webp_count >= total_non_profile - 1, f"Expected most thumbnails to be WebP, got {webp_count} out of {len(photos)}"
        print(f"SUCCESS: {webp_count}/{len(photos)} photos have WebP thumbnails")


class TestSetProfilePhoto:
    """Tests for Set as Profile Photo functionality"""
    
    def test_set_profile_photo_endpoint_exists(self):
        """Test that PATCH /profile-photo endpoint exists"""
        # This should fail with 400 since we're not sending photo_url
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/profile-photo",
            json={}
        )
        
        # Should get 400 (missing photo_url) not 404 (endpoint not found)
        assert response.status_code in [400, 422], f"Expected 400 or 422 for missing photo_url, got {response.status_code}"
        print("SUCCESS: profile-photo endpoint exists and validates input")
    
    def test_set_profile_photo_with_valid_url(self):
        """Test setting profile photo with a valid URL"""
        # Get existing photos to use one as the profile photo
        photos_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/photos/all")
        assert photos_response.status_code == 200
        
        photos = photos_response.json().get("photos", [])
        # Find a non-profile photo to set as profile
        non_profile = [p for p in photos if p.get("type") != "profile"]
        
        if not non_profile:
            pytest.skip("No non-profile photos available to test with")
        
        test_photo_url = non_profile[0]["url"]
        
        response = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}/profile-photo",
            json={"photo_url": test_photo_url}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"SUCCESS: Set profile photo to {test_photo_url}")


class TestContactWithPhotos:
    """Tests for contact data including photo fields"""
    
    def test_contact_has_photo_data(self):
        """Test that contact endpoint returns photo fields"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}")
        assert response.status_code == 200
        
        data = response.json()
        assert "first_name" in data
        assert data["first_name"], "Contact should have first_name"
        
        # Contact should have some photo data
        has_photo = data.get("photo") or data.get("photo_url") or data.get("photo_thumbnail")
        assert has_photo, "Contact should have photo data"
        print(f"SUCCESS: Contact {data.get('first_name')} has photo data")
    
    def test_contact_name_is_forest_ward(self):
        """Verify we're testing with the correct contact (Forest Ward)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_ID_WITH_PHOTOS}")
        assert response.status_code == 200
        
        data = response.json()
        first_name = data.get("first_name", "").lower()
        last_name = data.get("last_name", "").lower()
        
        # Should be Forest Ward contact
        assert "forest" in first_name or "ward" in last_name, f"Expected Forest Ward, got {data.get('first_name')} {data.get('last_name')}"
        print(f"SUCCESS: Confirmed testing with {data.get('first_name')} {data.get('last_name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
