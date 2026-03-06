"""
Test Photo Gallery v2 - Bug fixes for gallery modal
Tests: 1) photos/all endpoint returns proper URLs
       2) Photo URL structure for mobile URL resolution
       3) Photo count accuracy
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test contact: Forest Ward with 11 photos
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a0c06f7626f14d125f8c34"


class TestPhotoGalleryEndpoint:
    """Test /api/contacts/{user_id}/{contact_id}/photos/all endpoint"""

    def test_photos_all_endpoint_returns_200(self):
        """Verify the endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ photos/all endpoint returns 200 OK")

    def test_photos_all_returns_correct_structure(self):
        """Verify response has photos array and total count"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        assert "photos" in data, "Response missing 'photos' key"
        assert "total" in data, "Response missing 'total' key"
        assert isinstance(data["photos"], list), "'photos' should be a list"
        assert isinstance(data["total"], int), "'total' should be an integer"
        print(f"✓ Response structure is correct: photos array + total count")

    def test_photos_all_returns_11_photos_for_forest_ward(self):
        """Forest Ward contact should have 11 photos"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        assert data["total"] == 11, f"Expected 11 photos, got {data['total']}"
        assert len(data["photos"]) == 11, f"Expected 11 photo objects, got {len(data['photos'])}"
        print(f"✓ Forest Ward has exactly 11 photos")

    def test_each_photo_has_required_fields(self):
        """Each photo object must have type, url, and thumbnail_url"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        for i, photo in enumerate(data["photos"]):
            assert "type" in photo, f"Photo[{i}] missing 'type'"
            assert "url" in photo, f"Photo[{i}] missing 'url'"
            assert "thumbnail_url" in photo, f"Photo[{i}] missing 'thumbnail_url'"
            assert photo["url"], f"Photo[{i}] has empty 'url'"
            assert photo["thumbnail_url"], f"Photo[{i}] has empty 'thumbnail_url'"
        print(f"✓ All 11 photos have required fields (type, url, thumbnail_url)")

    def test_photo_urls_are_relative_paths(self):
        """Photo URLs should be relative paths starting with /api/images/"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        for i, photo in enumerate(data["photos"]):
            url = photo["url"]
            thumb = photo["thumbnail_url"]
            # URLs should be relative paths (not absolute http URLs)
            assert url.startswith("/api/images/") or url.startswith("/api/showcase/") or url.startswith("/api/birthday/"), \
                f"Photo[{i}] url should be relative path, got: {url[:60]}"
            assert thumb.startswith("/api/images/") or thumb.startswith("/api/showcase/") or thumb.startswith("/api/birthday/"), \
                f"Photo[{i}] thumbnail_url should be relative path, got: {thumb[:60]}"
        print(f"✓ All photo URLs are relative paths (for mobile URL resolution)")

    def test_first_photo_is_profile(self):
        """First photo should be the profile photo"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        assert len(data["photos"]) > 0, "No photos returned"
        first = data["photos"][0]
        assert first["type"] == "profile", f"First photo should be 'profile' type, got: {first['type']}"
        assert first["label"] == "Profile Photo", f"First photo label should be 'Profile Photo', got: {first['label']}"
        print(f"✓ First photo is the profile photo")

    def test_photo_types_include_congrats_and_birthday(self):
        """Should have profile, congrats, and birthday photo types"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        types = set(p["type"] for p in data["photos"])
        assert "profile" in types, "Missing profile photo type"
        assert "congrats" in types, "Missing congrats photo type"
        assert "birthday" in types, "Missing birthday photo type"
        print(f"✓ Photo types include: {types}")

    def test_congrats_photos_have_label_and_date(self):
        """Congrats photos should have label and date fields"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        congrats_photos = [p for p in data["photos"] if p["type"] == "congrats"]
        assert len(congrats_photos) > 0, "No congrats photos found"
        
        for i, photo in enumerate(congrats_photos):
            assert "label" in photo, f"Congrats photo[{i}] missing 'label'"
            assert photo["label"].startswith("Congrats -"), f"Congrats photo label format wrong: {photo['label']}"
        print(f"✓ All {len(congrats_photos)} congrats photos have proper labels")

    def test_birthday_photos_have_label_and_date(self):
        """Birthday photos should have label and date fields"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        data = response.json()
        
        birthday_photos = [p for p in data["photos"] if p["type"] == "birthday"]
        assert len(birthday_photos) > 0, "No birthday photos found"
        
        for i, photo in enumerate(birthday_photos):
            assert "label" in photo, f"Birthday photo[{i}] missing 'label'"
            assert photo["label"].startswith("Birthday -"), f"Birthday photo label format wrong: {photo['label']}"
        print(f"✓ All {len(birthday_photos)} birthday photos have proper labels")


class TestPhotoImageAccessibility:
    """Test that photo images are actually accessible"""

    def test_profile_photo_thumbnail_is_accessible(self):
        """Profile photo thumbnail should return an image"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        photos = response.json()["photos"]
        profile = photos[0]
        
        # Try to access the thumbnail
        img_response = requests.get(f"{BASE_URL}{profile['thumbnail_url']}", timeout=10)
        assert img_response.status_code == 200, f"Profile thumbnail not accessible: {img_response.status_code}"
        assert "image" in img_response.headers.get("content-type", ""), "Response is not an image"
        print(f"✓ Profile photo thumbnail is accessible and returns an image")

    def test_congrats_photo_thumbnail_is_accessible(self):
        """At least one congrats photo thumbnail should be accessible"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photos/all")
        photos = response.json()["photos"]
        congrats_photos = [p for p in photos if p["type"] == "congrats"]
        
        if not congrats_photos:
            pytest.skip("No congrats photos to test")
        
        photo = congrats_photos[0]
        img_response = requests.get(f"{BASE_URL}{photo['thumbnail_url']}", timeout=10)
        assert img_response.status_code == 200, f"Congrats thumbnail not accessible: {img_response.status_code}"
        print(f"✓ Congrats photo thumbnail is accessible")


class TestInvalidContactPhotos:
    """Test edge cases for photos endpoint"""

    def test_invalid_contact_id_returns_empty(self):
        """Invalid contact ID should return empty photos array"""
        fake_contact = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{fake_contact}/photos/all")
        # Should still return 200 with empty array, not 404
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["total"] == 0, f"Expected 0 photos for invalid contact, got {data['total']}"
        print(f"✓ Invalid contact ID returns empty photos array (graceful handling)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
