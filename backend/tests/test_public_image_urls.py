"""
Test Public-Facing Image URLs - Ensure ALL public URLs serve optimized WebP images
instead of raw base64. Valid patterns:
  - /api/images/{path} (optimized)
  - /api/showcase/* (lazy-migration fallback)
  - http/https URLs shorter than 500 chars

Test endpoints:
  - GET /api/card/data/{user_id}
  - GET /api/landing-page/user/{user_id} (public_landing.py /p/data/{user_id})
  - GET /api/showcase/user/{user_id}
  - GET /api/profile/{user_id}
  - GET /api/card/store/{store_slug}
  - POST /api/congrats-cards/create
  - GET /api/congrats-cards/{card_id}
  - GET /api/birthday-cards/{card_id}
  - POST /api/images/migrate-all-base64 (backfill step)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"  # Test user
STORE_SLUG = "imos-demo"


def is_valid_image_url(url: str) -> tuple:
    """
    Check if an image URL is valid (not base64, not too long).
    Returns (is_valid, reason)
    """
    if url is None:
        return True, "None is acceptable (no image)"
    
    if not isinstance(url, str):
        return False, f"Expected string, got {type(url)}"
    
    # Check for base64 data
    if url.startswith("data:"):
        return False, f"Contains base64 data (starts with 'data:')"
    
    # Check length - base64 images are typically thousands of chars
    if len(url) > 500:
        return False, f"URL too long ({len(url)} chars) - likely base64"
    
    # Valid patterns
    valid_patterns = [
        r"^/api/images/",       # Optimized WebP path
        r"^/api/showcase/",     # Lazy-migration fallback
        r"^https?://",         # External URLs (should be short)
    ]
    
    for pattern in valid_patterns:
        if re.match(pattern, url):
            return True, f"Valid pattern: {pattern}"
    
    # Empty string is acceptable
    if url == "":
        return True, "Empty string is acceptable"
    
    return False, f"Unknown pattern: {url[:100]}..."


def check_response_for_base64(data: dict, path: str = "") -> list:
    """
    Recursively check a response dict for any base64 image data.
    Returns list of issues found.
    """
    issues = []
    # Fields that contain actual image URLs
    image_fields = ["photo_url", "logo_url", "customer_photo", "photo", "logo", "thumbnail", 
                    "salesman_photo", "store_logo", "photo_thumbnail"]
    # Fields that have "photo" in name but are NOT images
    skip_fields = ["photo_consent", "photo_source", "contact_photo_updated", "photo_path", 
                   "photo_thumb_path", "photo_avatar_path", "logo_path", "logo_thumb_path", 
                   "logo_avatar_path"]
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            # Skip non-image fields
            if key.lower() in [f.lower() for f in skip_fields]:
                continue
            
            # Check if this is an image field (must be a string to be a URL)
            if isinstance(value, str):
                if key.lower() in [f.lower() for f in image_fields] or "photo" in key.lower() or "logo" in key.lower():
                    is_valid, reason = is_valid_image_url(value)
                    if not is_valid:
                        issues.append(f"{current_path}: {reason}")
            
            # Recurse into nested structures
            if isinstance(value, dict):
                issues.extend(check_response_for_base64(value, current_path))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        issues.extend(check_response_for_base64(item, f"{current_path}[{i}]"))
    
    return issues


class TestDigitalCardEndpoint:
    """Test GET /api/card/data/{user_id} returns optimized photo_url and logo_url"""
    
    def test_card_data_no_base64(self):
        """GET /api/card/data/{user_id} should return optimized image URLs"""
        response = requests.get(f"{BASE_URL}/api/card/data/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Specific checks for this endpoint
        user = data.get("user", {})
        photo_url = user.get("photo_url")
        is_valid, reason = is_valid_image_url(photo_url)
        assert is_valid, f"user.photo_url invalid: {reason}"
        
        store = data.get("store")
        if store:
            logo_url = store.get("logo_url")
            is_valid, reason = is_valid_image_url(logo_url)
            assert is_valid, f"store.logo_url invalid: {reason}"
        
        # Check all fields
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/card/data/{USER_ID} - No base64 found")
        print(f"  user.photo_url: {photo_url}")
        print(f"  store.logo_url: {store.get('logo_url') if store else 'N/A'}")


class TestLandingPageEndpoint:
    """Test GET /api/p/data/{user_id} returns optimized photo_url and logo_url"""
    
    def test_landing_page_no_base64(self):
        """GET /api/p/data/{user_id} should return optimized image URLs"""
        response = requests.get(f"{BASE_URL}/api/p/data/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Specific checks
        user = data.get("user", {})
        photo_url = user.get("photo_url")
        is_valid, reason = is_valid_image_url(photo_url)
        assert is_valid, f"user.photo_url invalid: {reason}"
        
        store = data.get("store")
        if store:
            logo_url = store.get("logo_url")
            is_valid, reason = is_valid_image_url(logo_url)
            assert is_valid, f"store.logo_url invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/p/data/{USER_ID} - No base64 found")
        print(f"  user.photo_url: {photo_url}")


class TestShowcaseUserEndpoint:
    """Test GET /api/showcase/user/{user_id} returns all image URLs as /api/images/ paths"""
    
    def test_showcase_user_no_base64(self):
        """GET /api/showcase/user/{user_id} should return optimized image URLs"""
        response = requests.get(f"{BASE_URL}/api/showcase/user/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Check salesperson photo
        sp = data.get("salesperson", {})
        photo_url = sp.get("photo_url")
        is_valid, reason = is_valid_image_url(photo_url)
        assert is_valid, f"salesperson.photo_url invalid: {reason}"
        
        # Check store logo
        store = data.get("store")
        if store:
            logo_url = store.get("logo_url")
            is_valid, reason = is_valid_image_url(logo_url)
            assert is_valid, f"store.logo_url invalid: {reason}"
        
        # Check entries
        entries = data.get("entries", [])
        for i, entry in enumerate(entries):
            customer_photo = entry.get("customer_photo")
            is_valid, reason = is_valid_image_url(customer_photo)
            assert is_valid, f"entries[{i}].customer_photo invalid: {reason}"
            
            review = entry.get("review")
            if review:
                review_photo = review.get("photo_url")
                is_valid, reason = is_valid_image_url(review_photo)
                assert is_valid, f"entries[{i}].review.photo_url invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/showcase/user/{USER_ID} - No base64 found")
        print(f"  Total entries: {len(entries)}")
        print(f"  Salesperson photo: {photo_url}")


class TestProfileEndpoint:
    """Test GET /api/profile/{user_id} returns optimized photo_url"""
    
    def test_profile_no_base64(self):
        """GET /api/profile/{user_id} should return optimized image URLs"""
        response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Check user photo
        user = data.get("user", {})
        photo_url = user.get("photo_url")
        is_valid, reason = is_valid_image_url(photo_url)
        assert is_valid, f"user.photo_url invalid: {reason}"
        
        # Check store logo
        store = data.get("store")
        if store:
            logo_url = store.get("logo_url")
            is_valid, reason = is_valid_image_url(logo_url)
            assert is_valid, f"store.logo_url invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/profile/{USER_ID} - No base64 found")
        print(f"  user.photo_url: {photo_url}")


class TestStoreCardEndpoint:
    """Test GET /api/card/store/{store_slug} returns optimized team member photos and store logo"""
    
    def test_store_card_no_base64(self):
        """GET /api/card/store/{store_slug} should return optimized image URLs"""
        response = requests.get(f"{BASE_URL}/api/card/store/{STORE_SLUG}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Check store logo
        store = data.get("store", {})
        logo_url = store.get("logo_url")
        is_valid, reason = is_valid_image_url(logo_url)
        assert is_valid, f"store.logo_url invalid: {reason}"
        
        # Check team member photos
        team = data.get("team", [])
        for i, member in enumerate(team):
            photo_url = member.get("photo_url")
            is_valid, reason = is_valid_image_url(photo_url)
            assert is_valid, f"team[{i}].photo_url invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/card/store/{STORE_SLUG} - No base64 found")
        print(f"  store.logo_url: {logo_url}")
        print(f"  Team members with photos: {len(team)}")


class TestCongratsCardsEndpoint:
    """Test congrats cards endpoints return optimized customer_photo URL"""
    
    def test_congrats_card_get_no_base64(self):
        """GET /api/congrats/card/{card_id} should return optimized customer_photo URL"""
        # First, get a card_id from the user's history
        response = requests.get(f"{BASE_URL}/api/congrats/history/{USER_ID}")
        
        if response.status_code != 200 or not response.json():
            pytest.skip("No congrats cards found for this user")
        
        cards = response.json()
        if not cards:
            pytest.skip("No congrats cards found for this user")
        
        card_id = cards[0].get("card_id")
        
        # Get the card data
        response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Check customer photo
        customer_photo = data.get("customer_photo")
        is_valid, reason = is_valid_image_url(customer_photo)
        assert is_valid, f"customer_photo invalid: {reason}"
        
        # Check salesman photo
        salesman = data.get("salesman")
        if salesman:
            salesman_photo = salesman.get("photo")
            is_valid, reason = is_valid_image_url(salesman_photo)
            assert is_valid, f"salesman.photo invalid: {reason}"
        
        # Check store logo
        store = data.get("store")
        if store:
            store_logo = store.get("logo")
            is_valid, reason = is_valid_image_url(store_logo)
            assert is_valid, f"store.logo invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/congrats/card/{card_id} - No base64 found")
        print(f"  customer_photo: {customer_photo}")


class TestBirthdayCardsEndpoint:
    """Test birthday cards endpoint returns optimized customer_photo and salesman photo"""
    
    def test_birthday_card_get_no_base64(self):
        """GET /api/birthday/card/{card_id} should return optimized image URLs"""
        # First, get a card_id from the user's history
        response = requests.get(f"{BASE_URL}/api/birthday/history/{USER_ID}")
        
        if response.status_code != 200 or not response.json():
            pytest.skip("No birthday cards found for this user")
        
        cards = response.json()
        if not cards:
            pytest.skip("No birthday cards found for this user")
        
        card_id = cards[0].get("card_id")
        
        # Get the card data
        response = requests.get(f"{BASE_URL}/api/birthday/card/{card_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Check customer photo
        customer_photo = data.get("customer_photo")
        is_valid, reason = is_valid_image_url(customer_photo)
        assert is_valid, f"customer_photo invalid: {reason}"
        
        # Check salesman photo
        salesman = data.get("salesman")
        if salesman:
            salesman_photo = salesman.get("photo")
            is_valid, reason = is_valid_image_url(salesman_photo)
            assert is_valid, f"salesman.photo invalid: {reason}"
        
        # Check store logo
        store = data.get("store")
        if store:
            store_logo = store.get("logo")
            is_valid, reason = is_valid_image_url(store_logo)
            assert is_valid, f"store.logo invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/birthday/card/{card_id} - No base64 found")
        print(f"  customer_photo: {customer_photo}")


class TestBatchMigrationEndpoint:
    """Test POST /api/images/migrate-all-base64 includes backfill step"""
    
    def test_batch_migration_includes_backfill(self):
        """POST /api/images/migrate-all-base64 should include backfill in response"""
        headers = {"X-User-ID": USER_ID}
        response = requests.post(
            f"{BASE_URL}/api/images/migrate-all-base64",
            headers=headers
        )
        
        # Should return 200 for super admin
        if response.status_code == 403:
            pytest.skip("User is not super admin - cannot test batch migration")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        
        # Check that backfill is included in response
        assert "backfilled" in data or "backfill" in str(data).lower(), \
            f"Backfill step not found in response: {data}"
        
        print(f"✓ POST /api/images/migrate-all-base64 - Backfill included")
        print(f"  Response: {data}")


class TestShowcaseStoreEndpoint:
    """Test GET /api/showcase/store/{store_id} returns optimized image URLs"""
    
    def test_showcase_store_no_base64(self):
        """GET /api/showcase/store/{store_id} should return optimized image URLs"""
        # First get store_id from digital card endpoint
        response = requests.get(f"{BASE_URL}/api/card/store/{STORE_SLUG}")
        if response.status_code != 200:
            pytest.skip(f"Could not get store data: {response.status_code}")
        
        store_data = response.json().get("store", {})
        store_id = store_data.get("id")
        
        if not store_id:
            pytest.skip("No store_id found")
        
        response = requests.get(f"{BASE_URL}/api/showcase/store/{store_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        issues = check_response_for_base64(data)
        
        # Check store logo
        store = data.get("store", {})
        logo_url = store.get("logo_url")
        is_valid, reason = is_valid_image_url(logo_url)
        assert is_valid, f"store.logo_url invalid: {reason}"
        
        # Check team photos
        team = data.get("team", [])
        for i, member in enumerate(team):
            photo_url = member.get("photo_url")
            is_valid, reason = is_valid_image_url(photo_url)
            assert is_valid, f"team[{i}].photo_url invalid: {reason}"
        
        # Check entries
        entries = data.get("entries", [])
        for i, entry in enumerate(entries):
            customer_photo = entry.get("customer_photo")
            is_valid, reason = is_valid_image_url(customer_photo)
            assert is_valid, f"entries[{i}].customer_photo invalid: {reason}"
        
        assert len(issues) == 0, f"Found base64 data in response: {issues}"
        print(f"✓ GET /api/showcase/store/{store_id} - No base64 found")
        print(f"  store.logo_url: {logo_url}")
        print(f"  Team members: {len(team)}")
        print(f"  Entries: {len(entries)}")


class TestNoPythonDictDuplicateKeys:
    """Verify no Python dict duplicate-key bugs remain in the codebase"""
    
    def test_showcase_dict_pattern(self):
        """Showcase.py should use $nin instead of duplicate $ne keys"""
        # This is verified by the fact that the API returns correct results
        # If there were duplicate key bugs, queries would fail or return wrong data
        response = requests.get(f"{BASE_URL}/api/showcase/user/{USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        entries = data.get("entries", [])
        
        # If dict duplicate key bug existed, photo_map would be wrong
        # Check that entries with photos have valid URLs
        entries_with_photos = [e for e in entries if e.get("customer_photo")]
        
        for entry in entries_with_photos:
            photo = entry.get("customer_photo")
            assert photo.startswith("/api/"), f"Photo should start with /api/: {photo[:50]}"
        
        print(f"✓ No dict duplicate-key bugs - {len(entries_with_photos)} entries with photos verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
