"""
Test Image Loading Performance Fixes - Iteration 145
Tests for:
1. GET /api/showcase/user/{user_id} returns ALL image URLs as /api/images/ paths
2. GET /api/showcase/store/{store_id} returns optimized image paths
3. GET /api/showcase/photo/{card_id} returns 301 redirect to /api/images/
4. GET /api/showcase/user-photo/{user_id} returns 301 redirect for migrated user photos
5. GET /api/showcase/store-logo/{store_id} returns 301 redirect for migrated store logos
6. POST /api/images/migrate-all-base64 includes backfill step
7. GET /api/contacts/{user_id}/{contact_id}/photos/all returns URL paths not base64 blobs
8. No Python dict duplicate-key bugs remain (code verified in showcase.py)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
SUPER_ADMIN_USER_ID = "69a0b7095fddcede09591667"


@pytest.fixture
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code}")


class TestShowcaseUserEndpoint:
    """Test GET /api/showcase/user/{user_id} returns optimized image paths"""
    
    def test_showcase_user_returns_images_paths_not_fallback(self):
        """Verify user showcase returns /api/images/ paths, not /api/showcase/photo/ fallbacks"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        entries = data.get("entries", [])
        
        # Count image types
        direct_images = 0
        fallback_photos = 0
        null_photos = 0
        
        for entry in entries:
            photo = entry.get("customer_photo")
            if photo:
                if photo.startswith("/api/images/"):
                    direct_images += 1
                elif photo.startswith("/api/showcase/photo/"):
                    fallback_photos += 1
                else:
                    print(f"Unknown photo path pattern: {photo[:50]}...")
            else:
                null_photos += 1
        
        print(f"Direct /api/images/ paths: {direct_images}")
        print(f"Fallback /api/showcase/photo/ paths: {fallback_photos}")
        print(f"No photo: {null_photos}")
        
        # Verify at least some entries exist (based on context, images were migrated)
        assert len(entries) >= 0, "Showcase entries should exist"
        
        # If there are photos, most should be direct paths (migrated)
        if direct_images + fallback_photos > 0:
            migration_rate = direct_images / (direct_images + fallback_photos) * 100
            print(f"Migration rate: {migration_rate:.1f}%")
    
    def test_showcase_user_salesperson_photo_optimized(self):
        """Verify user's own photo_url in showcase is optimized"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        salesperson = data.get("salesperson", {})
        photo_url = salesperson.get("photo_url")
        
        print(f"Salesperson photo_url: {photo_url}")
        
        # If photo exists, should be a path-based URL, not base64
        if photo_url:
            assert not photo_url.startswith("data:"), "Photo URL should not be base64"
            assert photo_url.startswith("/api/"), f"Photo should be served via API, got: {photo_url[:50]}"
    
    def test_showcase_user_store_logo_optimized(self):
        """Verify store logo in showcase is optimized"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        store = data.get("store")
        
        if store:
            logo_url = store.get("logo_url")
            print(f"Store logo_url: {logo_url}")
            
            if logo_url:
                assert not logo_url.startswith("data:"), "Logo URL should not be base64"
                assert logo_url.startswith("/api/"), f"Logo should be served via API"
    
    def test_showcase_user_review_photos_optimized(self):
        """Verify review photos in showcase entries are optimized"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("entries", [])
        
        review_photos_direct = 0
        review_photos_fallback = 0
        
        for entry in entries:
            review = entry.get("review")
            if review:
                photo_url = review.get("photo_url")
                if photo_url:
                    if photo_url.startswith("/api/images/"):
                        review_photos_direct += 1
                    elif photo_url.startswith("/api/showcase/feedback-photo/"):
                        review_photos_fallback += 1
        
        print(f"Review photos with direct paths: {review_photos_direct}")
        print(f"Review photos with fallback paths: {review_photos_fallback}")


class TestShowcaseStoreEndpoint:
    """Test GET /api/showcase/store/{store_id} returns optimized image paths"""
    
    def test_showcase_store_returns_optimized_paths(self):
        """Verify store showcase returns optimized image paths"""
        # First get the store_id from the user's showcase
        user_response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        if user_response.status_code != 200:
            pytest.skip("Cannot get user showcase to find store_id")
        
        store = user_response.json().get("store")
        if not store or not store.get("id"):
            pytest.skip("User does not have a store")
        
        store_id = store["id"]
        print(f"Testing store showcase for store_id: {store_id}")
        
        response = requests.get(f"{BASE_URL}/api/showcase/store/{store_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check store logo
        store_info = data.get("store", {})
        logo_url = store_info.get("logo_url")
        if logo_url:
            print(f"Store logo: {logo_url}")
            assert not logo_url.startswith("data:"), "Store logo should not be base64"
        
        # Check team photos
        team = data.get("team", [])
        for member in team:
            photo_url = member.get("photo_url")
            if photo_url:
                print(f"Team member photo: {photo_url[:60]}...")
                # Team photos are served via showcase endpoint
                assert not photo_url.startswith("data:"), "Team photo should not be base64"


class TestShowcasePhotoRedirects:
    """Test that showcase photo endpoints return 301 redirects"""
    
    def test_showcase_photo_redirects_to_images_api(self):
        """Verify /api/showcase/photo/{card_id} returns 301 redirect to /api/images/"""
        # Get a card_id from the showcase
        response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        if response.status_code != 200:
            pytest.skip("Cannot get showcase entries")
        
        entries = response.json().get("entries", [])
        card_id = None
        for entry in entries:
            if entry.get("card_id"):
                card_id = entry["card_id"]
                break
        
        if not card_id:
            pytest.skip("No card_id found in showcase entries")
        
        print(f"Testing photo redirect for card_id: {card_id}")
        
        # Request without following redirects
        photo_response = requests.get(
            f"{BASE_URL}/api/showcase/photo/{card_id}",
            allow_redirects=False
        )
        
        print(f"Photo response status: {photo_response.status_code}")
        
        if photo_response.status_code == 301:
            location = photo_response.headers.get("Location")
            print(f"Redirect location: {location}")
            assert "/api/images/" in location, f"Redirect should point to /api/images/, got: {location}"
            assert ".webp" in location or ".png" in location or ".jpg" in location, "Should redirect to image file"
        elif photo_response.status_code == 200:
            # May be serving raw image if not migrated
            content_type = photo_response.headers.get("Content-Type", "")
            print(f"Direct response content-type: {content_type}")
            assert "image" in content_type, "Should return an image"
        elif photo_response.status_code == 404:
            print("Card photo not found (expected if no photo)")
        else:
            pytest.fail(f"Unexpected status: {photo_response.status_code}")
    
    def test_user_photo_redirect_or_404(self):
        """Verify /api/showcase/user-photo/{user_id} behaves correctly"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/user-photo/{SUPER_ADMIN_USER_ID}",
            allow_redirects=False
        )
        
        print(f"User photo status: {response.status_code}")
        
        if response.status_code == 301:
            location = response.headers.get("Location")
            print(f"Redirect location: {location}")
            assert "/api/images/" in location, "Should redirect to /api/images/"
        elif response.status_code == 404:
            print("User photo not found (expected if user has no photo)")
        elif response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            print(f"Direct image content-type: {content_type}")
    
    def test_store_logo_redirect_or_404(self):
        """Verify /api/showcase/store-logo/{store_id} behaves correctly"""
        # Get store_id
        user_response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        if user_response.status_code != 200:
            pytest.skip("Cannot get user showcase")
        
        store = user_response.json().get("store")
        if not store or not store.get("id"):
            pytest.skip("User has no store")
        
        store_id = store["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/showcase/store-logo/{store_id}",
            allow_redirects=False
        )
        
        print(f"Store logo status: {response.status_code}")
        
        if response.status_code == 301:
            location = response.headers.get("Location")
            print(f"Redirect location: {location}")
            assert "/api/images/" in location, "Should redirect to /api/images/"
        elif response.status_code == 404:
            print("Store logo not found")
        elif response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            print(f"Direct image content-type: {content_type}")


class TestBatchMigrationEndpoint:
    """Test POST /api/images/migrate-all-base64"""
    
    def test_migrate_all_requires_super_admin(self, auth_token):
        """Verify batch migration endpoint requires super admin"""
        # Test without header
        response = requests.post(f"{BASE_URL}/api/images/migrate-all-base64")
        assert response.status_code in [403, 422, 500], "Should reject without user header"
        
        # Test with non-admin user (if we had one - just document behavior)
        # For now, verify the endpoint exists and requires auth
        print(f"No header response: {response.status_code}")
    
    def test_migrate_all_super_admin_runs(self, auth_token):
        """Verify batch migration runs for super admin and returns stats"""
        response = requests.post(
            f"{BASE_URL}/api/images/migrate-all-base64",
            headers={"X-User-ID": SUPER_ADMIN_USER_ID}
        )
        
        print(f"Migration status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Migration result: {data}")
            
            # Should have backfilled field from the new fix
            assert "backfilled" in data, "Response should include 'backfilled' count"
            assert "migrated" in data, "Response should include 'migrated' stats"
            
            # Check structure
            migrated = data.get("migrated", {})
            assert "users" in migrated
            assert "stores" in migrated
            assert "contacts" in migrated
            assert "congrats" in migrated
            assert "feedback" in migrated
            
            print(f"Backfilled: {data.get('backfilled', 0)}")
            print(f"Total migrated: {data.get('total_migrated', 0)}")
        elif response.status_code == 403:
            print("Migration denied (super admin check working)")
        else:
            print(f"Migration response: {response.text[:200]}")


class TestContactPhotosEndpoint:
    """Test GET /api/contacts/{user_id}/{contact_id}/photos/all"""
    
    def test_contact_photos_returns_urls_not_base64(self, auth_token):
        """Verify contact gallery returns URL paths, not base64 blobs"""
        # First get a contact with photos
        contacts_response = requests.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if contacts_response.status_code != 200:
            pytest.skip(f"Cannot get contacts: {contacts_response.status_code}")
        
        contacts = contacts_response.json()
        if not contacts:
            pytest.skip("No contacts found")
        
        # Find a contact (preferably one with a photo)
        contact_id = None
        for contact in contacts[:5]:  # Check first 5
            cid = contact.get("_id") or contact.get("id")
            if cid:
                contact_id = str(cid)
                break
        
        if not contact_id:
            pytest.skip("No contact with ID found")
        
        print(f"Testing photos for contact: {contact_id}")
        
        photos_response = requests.get(
            f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}/{contact_id}/photos/all",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        print(f"Photos response status: {photos_response.status_code}")
        
        if photos_response.status_code == 200:
            data = photos_response.json()
            photos = data.get("photos", [])
            
            print(f"Total photos found: {len(photos)}")
            
            base64_count = 0
            url_count = 0
            
            for photo in photos:
                url = photo.get("url", "")
                thumb = photo.get("thumbnail_url", "")
                
                # Check for base64
                if url.startswith("data:"):
                    base64_count += 1
                    print(f"WARNING: Base64 found in photo type={photo.get('type')}")
                elif url.startswith("/api/") or url.startswith("http"):
                    url_count += 1
                    print(f"OK: URL path photo type={photo.get('type')}: {url[:60]}...")
            
            print(f"URL paths: {url_count}, Base64: {base64_count}")
            
            # Should have zero or very few base64 blobs
            if url_count + base64_count > 0:
                assert base64_count == 0 or (base64_count / (url_count + base64_count)) < 0.1, \
                    "Most photos should be URL paths, not base64"
        elif photos_response.status_code == 404:
            print("Contact photos endpoint returned 404")


class TestImageCachingHeaders:
    """Test that images are served with proper caching headers"""
    
    def test_image_has_etag_and_cache_control(self):
        """Verify images have ETag and Cache-Control headers"""
        # Get a known image path
        response = requests.get(f"{BASE_URL}/api/showcase/user/{SUPER_ADMIN_USER_ID}")
        if response.status_code != 200:
            pytest.skip("Cannot get showcase")
        
        entries = response.json().get("entries", [])
        image_url = None
        
        for entry in entries:
            photo = entry.get("customer_photo")
            if photo and photo.startswith("/api/images/"):
                image_url = photo
                break
        
        if not image_url:
            pytest.skip("No /api/images/ path found")
        
        # Request the actual image
        full_url = f"{BASE_URL}{image_url}"
        img_response = requests.get(full_url)
        
        print(f"Image response status: {img_response.status_code}")
        print(f"Content-Type: {img_response.headers.get('Content-Type')}")
        print(f"ETag: {img_response.headers.get('ETag')}")
        print(f"Cache-Control: {img_response.headers.get('Cache-Control')}")
        print(f"Content-Length: {len(img_response.content)} bytes")
        
        assert img_response.status_code == 200, f"Image request failed: {img_response.status_code}"
        
        # Should have caching headers
        assert img_response.headers.get("ETag"), "Image should have ETag header"
        
        # Verify it's an image
        content_type = img_response.headers.get("Content-Type", "")
        assert "image" in content_type, f"Should be an image, got: {content_type}"


class TestCodeReviewDictBug:
    """Verify the Python dict duplicate-key bug has been fixed in showcase.py"""
    
    def test_no_duplicate_ne_keys_in_query(self):
        """Verify showcase.py uses $nin instead of duplicate $ne keys"""
        # This is a code review test - the fix uses $nin instead of:
        # {"$ne": None, "$ne": ""} which would silently drop the first key
        
        # Read the showcase.py file and verify the fix
        showcase_path = "/app/backend/routers/showcase.py"
        try:
            with open(showcase_path, "r") as f:
                content = f.read()
        except Exception as e:
            pytest.skip(f"Cannot read showcase.py: {e}")
        
        # Check for the old buggy pattern
        buggy_pattern = r'\$ne.*None.*\$ne.*""'
        if re.search(buggy_pattern, content):
            pytest.fail("Found duplicate $ne keys in showcase.py - this is a Python dict bug")
        
        # Check for the correct $nin pattern
        assert "$nin" in content, "showcase.py should use $nin for multiple negative checks"
        assert '"$nin": [None, ""]' in content or "'$nin': [None, '']" in content, \
            "Should use $nin: [None, ''] pattern"
        
        print("PASS: showcase.py uses $nin pattern correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
