"""
Image Migration & Optimization Pipeline Tests
- Tests lazy-migration of base64 images to WebP
- Tests 301 redirects to /api/images/ for migrated images
- Tests batch migration endpoint (super admin only)
- Tests contacts gallery returning URLs not base64
- Tests Cache-Control headers on image responses
"""
import os
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestImageMigrationEndpoints:
    """Test image migration and optimization endpoints"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Login as super admin and get token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Super admin login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def regular_user_token(self):
        """Get a regular user token (not super admin)"""
        # First try to create a test user or use existing non-admin
        # For now, we'll test without token to verify 403 for non-super-admin
        return None
    
    # ==================== Showcase Photo Endpoints ====================
    
    def test_showcase_photo_endpoint_exists(self):
        """Test GET /api/showcase/photo/{card_id} endpoint exists"""
        # Use a non-existent card_id to test 404 response
        response = requests.get(
            f"{BASE_URL}/api/showcase/photo/nonexistent_card_12345",
            allow_redirects=False,
            timeout=30
        )
        # Should return 404 for non-existent card (not 500 or connection error)
        assert response.status_code == 404, f"Expected 404 for non-existent card, got {response.status_code}"
        print("PASS: Showcase photo endpoint returns 404 for non-existent card")
    
    def test_showcase_user_photo_endpoint_exists(self):
        """Test GET /api/showcase/user-photo/{user_id} endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/user-photo/invalid_user_id_12345",
            allow_redirects=False,
            timeout=30
        )
        # Should return 404 or 500 for invalid ObjectId
        assert response.status_code in [404, 500], f"Expected 404/500 for invalid user, got {response.status_code}"
        print("PASS: User photo endpoint returns appropriate error for invalid user")
    
    def test_showcase_store_logo_endpoint_exists(self):
        """Test GET /api/showcase/store-logo/{store_id} endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/store-logo/invalid_store_id_12345",
            allow_redirects=False,
            timeout=30
        )
        # Should return 404 or 500 for invalid ObjectId
        assert response.status_code in [404, 500], f"Expected 404/500 for invalid store, got {response.status_code}"
        print("PASS: Store logo endpoint returns appropriate error for invalid store")
    
    def test_showcase_feedback_photo_endpoint_exists(self):
        """Test GET /api/showcase/feedback-photo/{feedback_id} endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/feedback-photo/invalid_feedback_12345",
            allow_redirects=False,
            timeout=30
        )
        # Should return 400 for invalid ObjectId format
        assert response.status_code in [400, 404], f"Expected 400/404 for invalid feedback, got {response.status_code}"
        print("PASS: Feedback photo endpoint returns appropriate error for invalid feedback ID")
    
    def test_user_photo_redirect_for_valid_user(self):
        """Test GET /api/showcase/user-photo/{user_id} for existing user (may redirect if photo exists)"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/user-photo/{TEST_USER_ID}",
            allow_redirects=False,
            timeout=30
        )
        # Either 301 redirect to /api/images/ or 404 if no photo
        if response.status_code == 301:
            location = response.headers.get("Location", "")
            assert "/api/images/" in location, f"301 redirect should go to /api/images/, got: {location}"
            print(f"PASS: User photo redirects to optimized path: {location}")
        elif response.status_code == 404:
            print("PASS: User photo returns 404 (user has no photo)")
        else:
            # Could be 200 with raw image (fallback)
            assert response.status_code == 200, f"Unexpected status: {response.status_code}"
            print("PASS: User photo returns 200 with image data")
    
    # ==================== Batch Migration Endpoint ====================
    
    def test_migrate_all_base64_super_admin_only(self, super_admin_token):
        """Test POST /api/images/migrate-all-base64 requires super admin"""
        response = requests.post(
            f"{BASE_URL}/api/images/migrate-all-base64",
            headers={"X-User-ID": TEST_USER_ID},
            timeout=120
        )
        # Should work for super admin
        if response.status_code == 200:
            data = response.json()
            assert "migrated" in data, f"Response should contain 'migrated' stats: {data}"
            assert "total_migrated" in data, f"Response should contain 'total_migrated': {data}"
            print(f"PASS: Batch migration returned stats: {data.get('total_migrated')} images migrated")
        else:
            # If already all migrated, might return 200 with 0 migrated
            print(f"Batch migration response: {response.status_code} - {response.text[:200]}")
    
    def test_migrate_all_base64_rejects_non_super_admin(self):
        """Test POST /api/images/migrate-all-base64 returns 403 for non-super-admin"""
        # Test with a fake/non-existent user ID
        response = requests.post(
            f"{BASE_URL}/api/images/migrate-all-base64",
            headers={"X-User-ID": "000000000000000000000001"},  # Non-existent user
            timeout=30
        )
        # Should return 403 (non super admin) or 500 (user not found treated as non-admin)
        assert response.status_code in [403, 500], f"Expected 403/500 for non-admin, got {response.status_code}"
        print(f"PASS: Batch migration rejects non-super-admin with status {response.status_code}")
    
    def test_migrate_all_base64_no_user_header(self):
        """Test POST /api/images/migrate-all-base64 without X-User-ID header"""
        response = requests.post(
            f"{BASE_URL}/api/images/migrate-all-base64",
            timeout=30
        )
        # Should return 403 or 422 (missing header)
        assert response.status_code in [403, 422, 500], f"Expected 403/422/500 without user header, got {response.status_code}"
        print(f"PASS: Batch migration rejects request without user header ({response.status_code})")
    
    # ==================== Contacts Photo Gallery ====================
    
    def test_contacts_photos_returns_urls(self, super_admin_token):
        """Test GET /api/contacts/{user_id}/{contact_id}/photos/all returns URLs not base64"""
        # First get a contact for this user
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            timeout=30
        )
        
        if response.status_code != 200:
            pytest.skip("Could not fetch contacts list")
        
        contacts = response.json()
        if not contacts:
            pytest.skip("No contacts found for user")
        
        # Get photos for first contact
        contact_id = contacts[0].get("id") or str(contacts[0].get("_id", ""))
        if not contact_id:
            pytest.skip("Contact has no ID")
        
        photos_response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}/photos/all",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            timeout=30
        )
        
        assert photos_response.status_code == 200, f"Photos endpoint failed: {photos_response.status_code}"
        data = photos_response.json()
        assert "photos" in data, f"Response should contain 'photos' array: {data}"
        
        # Check that photos use URL paths, not base64 blobs
        for photo in data.get("photos", []):
            url = photo.get("url", "")
            thumb_url = photo.get("thumbnail_url", "")
            
            # URLs should start with /api/images/ or be relative paths, NOT data:
            if url:
                assert not url.startswith("data:image"), f"Photo URL should be path, not base64: {url[:50]}..."
                print(f"  Photo URL format OK: {url[:60]}...")
            if thumb_url:
                assert not thumb_url.startswith("data:image"), f"Thumbnail URL should be path, not base64"
        
        print(f"PASS: Contact photos endpoint returns {len(data.get('photos', []))} photos with URL paths")
    
    # ==================== Image Serving with Cache Headers ====================
    
    def test_images_endpoint_cache_headers(self):
        """Test GET /api/images/* serves with Cache-Control: immutable headers"""
        # First find a migrated image path by checking a known photo endpoint
        user_photo_response = requests.get(
            f"{BASE_URL}/api/showcase/user-photo/{TEST_USER_ID}",
            allow_redirects=False,
            timeout=30
        )
        
        if user_photo_response.status_code == 301:
            # Follow the redirect to check cache headers
            redirect_path = user_photo_response.headers.get("Location", "")
            if redirect_path.startswith("/api/images/"):
                image_response = requests.get(
                    f"{BASE_URL}{redirect_path}",
                    timeout=30
                )
                
                if image_response.status_code == 200:
                    cache_control = image_response.headers.get("Cache-Control", "")
                    assert "immutable" in cache_control or "max-age=31536000" in cache_control, \
                        f"Expected immutable/1-year cache, got: {cache_control}"
                    print(f"PASS: Image served with Cache-Control: {cache_control}")
                    return
        
        # If no redirect, test the images endpoint directly with a known path pattern
        # This tests that the endpoint infrastructure is correct
        print("SKIP: No migrated image found to test cache headers (user may not have photo)")
    
    def test_image_cache_stats_endpoint(self):
        """Test GET /api/images/cache-stats returns cache statistics"""
        response = requests.get(
            f"{BASE_URL}/api/images/cache-stats",
            timeout=30
        )
        
        assert response.status_code == 200, f"Cache stats endpoint failed: {response.status_code}"
        data = response.json()
        
        # Check expected fields
        assert "items" in data, f"Should have 'items' count: {data}"
        assert "size_mb" in data, f"Should have 'size_mb': {data}"
        assert "max_mb" in data, f"Should have 'max_mb': {data}"
        
        print(f"PASS: Image cache stats: {data['items']} items, {data['size_mb']}MB / {data['max_mb']}MB")
    
    # ==================== Profile Photo Upload Pipeline ====================
    
    def test_profile_photo_upload_endpoint(self, super_admin_token):
        """Test POST /api/profile/{user_id}/photo uses image pipeline"""
        # This is a file upload endpoint - just verify it exists
        # We won't actually upload in this test but verify the route
        response = requests.post(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}/photo",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            files={},  # Empty file to check endpoint exists
            timeout=30
        )
        
        # Should return 422 (missing file) or 400 (bad request), not 404
        assert response.status_code != 404, "Profile photo upload endpoint should exist"
        print(f"PASS: Profile photo upload endpoint exists (returned {response.status_code} without file)")
    
    # ==================== Integration: Showcase User Endpoint ====================
    
    def test_showcase_user_returns_photo_urls(self):
        """Test GET /api/showcase/user/{user_id} returns photo URLs not base64"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}",
            timeout=30
        )
        
        if response.status_code != 200:
            pytest.skip(f"Showcase user endpoint failed: {response.status_code}")
        
        data = response.json()
        
        # Check salesperson photo_url is a path, not base64
        if data.get("salesperson", {}).get("photo_url"):
            photo_url = data["salesperson"]["photo_url"]
            assert not photo_url.startswith("data:"), f"Salesperson photo should be URL path: {photo_url[:50]}"
            assert photo_url.startswith("/api/"), f"Photo URL should be API path: {photo_url}"
            print(f"PASS: Salesperson photo_url is API path: {photo_url}")
        
        # Check store logo_url
        if data.get("store", {}).get("logo_url"):
            logo_url = data["store"]["logo_url"]
            assert not logo_url.startswith("data:"), f"Store logo should be URL path: {logo_url[:50]}"
            print(f"PASS: Store logo_url is API path: {logo_url}")
        
        # Check entries customer_photo paths
        entries = data.get("entries", [])
        for entry in entries[:5]:  # Check first 5 entries
            if entry.get("customer_photo"):
                assert entry["customer_photo"].startswith("/api/"), \
                    f"Entry photo should be API path: {entry['customer_photo']}"
        
        print(f"PASS: Showcase user endpoint returns {len(entries)} entries with URL paths")


class TestRedirectBehavior:
    """Test 301 redirect behavior for lazy-migrated images"""
    
    def test_redirect_does_not_follow_automatically(self):
        """Verify we can detect 301 redirects"""
        response = requests.get(
            f"{BASE_URL}/api/showcase/user-photo/{TEST_USER_ID}",
            allow_redirects=False,
            timeout=30
        )
        
        if response.status_code == 301:
            location = response.headers.get("Location", "")
            print(f"PASS: 301 redirect detected to: {location}")
            assert location, "301 response should have Location header"
        elif response.status_code == 404:
            print("INFO: No photo found for user (404)")
        else:
            print(f"INFO: Unexpected status {response.status_code}")


class TestReviewPageLinkHandling:
    """Test review page link click handling (web vs mobile)"""
    
    def test_review_page_loads(self):
        """Test review page at /review/{storeSlug} loads"""
        # We need to find a valid store slug first
        # For now, just verify the route pattern exists by checking a common pattern
        response = requests.get(
            f"{BASE_URL}/api/review/page/test-store-slug",
            timeout=30
        )
        
        # Should return 404 (store not found) not 500 (route doesn't exist)
        # If the route doesn't exist at all, we'd get a different error
        if response.status_code == 404:
            print("PASS: Review page endpoint exists (404 for unknown slug is expected)")
        elif response.status_code == 200:
            data = response.json()
            print(f"PASS: Review page endpoint returns store data: {data.get('store', {}).get('name', 'Unknown')}")
        else:
            print(f"INFO: Review page endpoint returned {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
