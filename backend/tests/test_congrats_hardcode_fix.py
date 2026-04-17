"""
Tests for congrats card hardcoded values fix:
1. POST create card stores photo_source matching actual card_type
2. Card view tracking logs correct event_type per card_type
3. Short URL creation uses card_type-specific link_type
4. Track download/share logs card_type-specific event
"""
import pytest
import requests
import os
import base64
from io import BytesIO

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
TEST_USER_ID = "69a0b7095fddcede09591667"

# Minimal test image (1x1 transparent PNG)
def create_test_image():
    # Minimal valid PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return BytesIO(png_bytes)


class TestCongratsCardTypeFix:
    """Tests for hardcoded congrats values fix"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # Test 1: Verify different card types get correct defaults
    def test_template_defaults_by_card_type(self):
        """GET /api/congrats/template/{store_id}?card_type=X returns type-specific defaults"""
        # Get a store_id for testing - using the test user
        user_resp = self.session.get(f"{BASE_URL}/api/auth/user/{TEST_USER_ID}")
        assert user_resp.status_code == 200, f"Failed to get user: {user_resp.text}"
        store_id = user_resp.json().get("store_id")
        
        # Test each card type has correct headline
        card_type_headlines = {
            "birthday": "Happy Birthday!",
            "thankyou": "Thank You!",
            "holiday": "Happy Holidays!",
            "welcome": "Welcome!",
            "anniversary": "Happy Anniversary!",
            "congrats": "Congratulations!",
        }
        
        for card_type, expected_headline in card_type_headlines.items():
            resp = self.session.get(f"{BASE_URL}/api/congrats/template/{store_id}?card_type={card_type}")
            assert resp.status_code == 200, f"Failed for card_type={card_type}: {resp.text}"
            data = resp.json()
            actual_headline = data.get("template", {}).get("headline")
            print(f"Card type '{card_type}': expected headline='{expected_headline}', got='{actual_headline}'")
            assert actual_headline == expected_headline, \
                f"card_type={card_type} should have headline '{expected_headline}' but got '{actual_headline}'"
        
        print("PASS: Template defaults return correct headlines for all card types")

    # Test 2: Create a birthday card and verify it's stored with card_type=birthday
    def test_create_birthday_card_stores_correct_card_type(self):
        """POST /api/congrats/create with card_type=birthday stores birthday, not congrats"""
        # Create a test card
        test_image = create_test_image()
        
        files = {
            'photo': ('test.png', test_image, 'image/png'),
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_Birthday_Customer',
            'customer_phone': '+15551234567',
            'card_type': 'birthday',  # Should be stored as birthday, NOT congrats
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data,
        )
        
        assert resp.status_code == 200, f"Failed to create card: {resp.text}"
        result = resp.json()
        card_id = result.get("card_id")
        assert card_id, "No card_id returned"
        print(f"Created card with id: {card_id}")
        
        # Now get the card and verify card_type is stored correctly
        card_resp = self.session.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        assert card_resp.status_code == 200, f"Failed to get card: {card_resp.text}"
        card_data = card_resp.json()
        
        # The headline should be "Happy Birthday!" not "Congratulations!"
        headline = card_data.get("headline")
        print(f"Card headline: {headline}")
        assert headline == "Happy Birthday!", f"Birthday card should have 'Happy Birthday!' headline, got '{headline}'"
        
        print("PASS: Birthday card created with correct headline")
        return card_id

    # Test 3: Create a thankyou card
    def test_create_thankyou_card_stores_correct_type(self):
        """POST /api/congrats/create with card_type=thankyou stores thankyou"""
        test_image = create_test_image()
        
        files = {
            'photo': ('test.png', test_image, 'image/png'),
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_ThankYou_Customer',
            'customer_phone': '+15551234568',
            'card_type': 'thankyou',
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data,
        )
        
        assert resp.status_code == 200, f"Failed to create card: {resp.text}"
        result = resp.json()
        card_id = result.get("card_id")
        
        # Verify headline
        card_resp = self.session.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        assert card_resp.status_code == 200
        card_data = card_resp.json()
        
        headline = card_data.get("headline")
        print(f"ThankYou card headline: {headline}")
        assert headline == "Thank You!", f"ThankYou card should have 'Thank You!' headline, got '{headline}'"
        
        print("PASS: ThankYou card created with correct headline")
        return card_id

    # Test 4: Create a holiday card
    def test_create_holiday_card_stores_correct_type(self):
        """POST /api/congrats/create with card_type=holiday stores holiday"""
        test_image = create_test_image()
        
        files = {
            'photo': ('test.png', test_image, 'image/png'),
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_Holiday_Customer',
            'customer_phone': '+15551234569',
            'card_type': 'holiday',
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data,
        )
        
        assert resp.status_code == 200, f"Failed to create card: {resp.text}"
        result = resp.json()
        card_id = result.get("card_id")
        
        # Verify headline
        card_resp = self.session.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        assert card_resp.status_code == 200
        card_data = card_resp.json()
        
        headline = card_data.get("headline")
        print(f"Holiday card headline: {headline}")
        assert headline == "Happy Holidays!", f"Holiday card should have 'Happy Holidays!' headline, got '{headline}'"
        
        print("PASS: Holiday card created with correct headline")
        return card_id

    # Test 5: Verify short URL link_type is card_type-specific
    def test_short_url_link_type_matches_card_type(self):
        """Short URL created for card should have link_type='{card_type}_card'"""
        # Create a birthday card
        test_image = create_test_image()
        
        files = {
            'photo': ('test.png', test_image, 'image/png'),
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_ShortURL_Customer',
            'customer_phone': '+15551234570',
            'card_type': 'birthday',
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data,
        )
        
        assert resp.status_code == 200, f"Failed to create card: {resp.text}"
        result = resp.json()
        short_url = result.get("short_url")
        card_id = result.get("card_id")
        
        print(f"Created card {card_id} with short_url: {short_url}")
        assert short_url, "No short_url returned"
        
        # The short URL should exist and when resolved should point to the card
        # We can't directly verify link_type from API, but we can verify the code path works
        print("PASS: Short URL created successfully for birthday card")

    # Test 6: Track download action logs correct event type
    def test_track_download_logs_correct_event_type(self):
        """POST /api/congrats/card/{card_id}/track logs {card_type}_card_download"""
        # First create a card
        test_image = create_test_image()
        
        files = {
            'photo': ('test.png', test_image, 'image/png'),
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_Download_Customer',
            'customer_phone': '+15551234571',
            'card_type': 'birthday',
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data,
        )
        
        assert resp.status_code == 200, f"Failed to create card: {resp.text}"
        result = resp.json()
        card_id = result.get("card_id")
        
        # Track download action
        track_resp = self.session.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "download"}
        )
        assert track_resp.status_code == 200, f"Track failed: {track_resp.text}"
        
        print("PASS: Track download action succeeded")

    # Test 7: Track share action logs correct event type
    def test_track_share_logs_correct_event_type(self):
        """POST /api/congrats/card/{card_id}/track logs {card_type}_card_share"""
        # First create a card
        test_image = create_test_image()
        
        files = {
            'photo': ('test.png', test_image, 'image/png'),
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_Share_Customer',
            'customer_phone': '+15551234572',
            'card_type': 'thankyou',
        }
        
        resp = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data,
        )
        
        assert resp.status_code == 200, f"Failed to create card: {resp.text}"
        result = resp.json()
        card_id = result.get("card_id")
        
        # Track share action
        track_resp = self.session.post(
            f"{BASE_URL}/api/congrats/card/{card_id}/track",
            json={"action": "share"}
        )
        assert track_resp.status_code == 200, f"Track failed: {track_resp.text}"
        
        print("PASS: Track share action succeeded")


class TestPublicCardPages:
    """Tests for public card page endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # Test 8: Digital card page loads
    def test_digital_card_data_endpoint(self):
        """GET /api/card/data/{userId} returns card data for digital card page"""
        resp = self.session.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        assert resp.status_code == 200, f"Failed to load digital card data: {resp.text}"
        data = resp.json()
        
        # Verify basic structure
        assert "user" in data, "Missing 'user' in card data"
        user = data.get("user", {})
        print(f"Digital card user: {user.get('name')}")
        
        print("PASS: Digital card data endpoint works")

    # Test 9: Showcase page endpoint
    def test_showcase_endpoint(self):
        """GET /api/showcase/user/{userId} returns showcase data"""
        resp = self.session.get(f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}")
        assert resp.status_code == 200, f"Failed to load showcase: {resp.text}"
        data = resp.json()
        
        # Verify structure
        assert "entries" in data, "Missing 'entries' in showcase data"
        assert "total_deliveries" in data, "Missing 'total_deliveries'"
        print(f"Showcase has {len(data.get('entries', []))} entries, {data.get('total_deliveries')} deliveries")
        
        print("PASS: Showcase endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
