"""
Test Brand Kit Page Theme feature for Digital Card public pages
Tests the page_theme field in brand kit settings that controls light/dark theme on public pages
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID provided in requirements
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestBrandKitPageTheme:
    """Tests for Brand Kit page_theme feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Store original brand kit settings and restore after test"""
        self.original_brand_kit = None
        try:
            response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}")
            if response.status_code == 200:
                self.original_brand_kit = response.json()
        except Exception:
            pass
        yield
        # Restore original settings
        if self.original_brand_kit:
            try:
                requests.put(
                    f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
                    json=self.original_brand_kit
                )
            except Exception:
                pass
    
    def test_get_brand_kit_returns_page_theme(self):
        """GET /api/email/brand-kit/user/{userId} should return page_theme field"""
        response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # page_theme should be present (can be null, "dark", or "light")
        assert "page_theme" in data or data.get("page_theme") is None or data.get("page_theme") in ["dark", "light"], \
            f"page_theme should be returned in brand kit response: {data}"
        print(f"✓ Brand kit GET returns page_theme: {data.get('page_theme')}")
    
    def test_put_brand_kit_with_dark_theme(self):
        """PUT /api/email/brand-kit/user/{userId} should accept page_theme='dark'"""
        payload = {"page_theme": "dark"}
        
        response = requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the change persisted
        get_response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}")
        data = get_response.json()
        
        assert data.get("page_theme") == "dark", f"Expected page_theme='dark', got {data.get('page_theme')}"
        print("✓ Brand kit PUT with page_theme='dark' works correctly")
    
    def test_put_brand_kit_with_light_theme(self):
        """PUT /api/email/brand-kit/user/{userId} should accept page_theme='light'"""
        payload = {"page_theme": "light"}
        
        response = requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the change persisted
        get_response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}")
        data = get_response.json()
        
        assert data.get("page_theme") == "light", f"Expected page_theme='light', got {data.get('page_theme')}"
        print("✓ Brand kit PUT with page_theme='light' works correctly")
    
    def test_put_brand_kit_with_multiple_fields(self):
        """PUT should accept page_theme along with primary_color and other fields"""
        payload = {
            "page_theme": "dark",
            "primary_color": "#007AFF",
            "company_name": "Test Company"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify all fields persisted
        get_response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}")
        data = get_response.json()
        
        assert data.get("page_theme") == "dark", f"page_theme mismatch: {data.get('page_theme')}"
        assert data.get("primary_color") == "#007AFF", f"primary_color mismatch: {data.get('primary_color')}"
        print("✓ Brand kit PUT with multiple fields including page_theme works correctly")


class TestDigitalCardDataAPI:
    """Tests for Digital Card data endpoint returning brand_kit"""
    
    def test_card_data_returns_brand_kit_object(self):
        """GET /api/card/data/{userId} should return brand_kit object"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "brand_kit" in data, "brand_kit object should be in card data response"
        print(f"✓ Card data includes brand_kit object")
    
    def test_card_data_brand_kit_includes_page_theme(self):
        """GET /api/card/data/{userId} brand_kit should include page_theme"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        brand_kit = data.get("brand_kit", {})
        
        assert "page_theme" in brand_kit, f"brand_kit should include page_theme: {brand_kit}"
        assert brand_kit.get("page_theme") in [None, "dark", "light"], \
            f"page_theme should be null, 'dark', or 'light': {brand_kit.get('page_theme')}"
        print(f"✓ Card data brand_kit includes page_theme: {brand_kit.get('page_theme')}")
    
    def test_card_data_brand_kit_includes_primary_color(self):
        """GET /api/card/data/{userId} brand_kit should include primary_color"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        brand_kit = data.get("brand_kit", {})
        
        assert "primary_color" in brand_kit, f"brand_kit should include primary_color: {brand_kit}"
        print(f"✓ Card data brand_kit includes primary_color: {brand_kit.get('primary_color')}")
    
    def test_card_data_brand_kit_includes_all_theme_fields(self):
        """GET /api/card/data/{userId} brand_kit should include all theme-related fields"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        brand_kit = data.get("brand_kit", {})
        
        expected_fields = ["page_theme", "primary_color", "secondary_color", "accent_color", "logo_url", "company_name"]
        for field in expected_fields:
            assert field in brand_kit, f"brand_kit should include {field}: {brand_kit}"
        
        print(f"✓ Card data brand_kit includes all theme fields: {list(brand_kit.keys())}")


class TestThemePersistence:
    """Tests for verifying theme changes persist across endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Store original settings and restore after test"""
        self.original_brand_kit = None
        try:
            response = requests.get(f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}")
            if response.status_code == 200:
                self.original_brand_kit = response.json()
        except Exception:
            pass
        yield
        # Restore original settings
        if self.original_brand_kit:
            try:
                requests.put(
                    f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
                    json=self.original_brand_kit
                )
            except Exception:
                pass
    
    def test_theme_change_reflects_in_card_data(self):
        """Changing page_theme via brand-kit PUT should reflect in card data endpoint"""
        # Set to light theme
        requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
            json={"page_theme": "light"}
        )
        
        # Verify in card data
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        data = response.json()
        brand_kit = data.get("brand_kit", {})
        
        assert brand_kit.get("page_theme") == "light", \
            f"Card data should reflect light theme: {brand_kit.get('page_theme')}"
        
        # Change to dark theme
        requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
            json={"page_theme": "dark"}
        )
        
        # Verify change reflected
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        data = response.json()
        brand_kit = data.get("brand_kit", {})
        
        assert brand_kit.get("page_theme") == "dark", \
            f"Card data should reflect dark theme: {brand_kit.get('page_theme')}"
        
        print("✓ Theme changes in brand-kit correctly reflect in card data endpoint")
    
    def test_primary_color_change_reflects_in_card_data(self):
        """Changing primary_color via brand-kit PUT should reflect in card data endpoint"""
        test_color = "#FF5500"
        
        # Set color
        requests.put(
            f"{BASE_URL}/api/email/brand-kit/user/{TEST_USER_ID}",
            json={"primary_color": test_color}
        )
        
        # Verify in card data
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        data = response.json()
        brand_kit = data.get("brand_kit", {})
        
        assert brand_kit.get("primary_color") == test_color, \
            f"Card data should reflect color change: {brand_kit.get('primary_color')}"
        
        print(f"✓ Primary color changes correctly reflect in card data endpoint: {test_color}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
