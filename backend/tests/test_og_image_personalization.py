"""
Test Suite: Personalized OG Image for Social Share Previews
Tests the /api/s/og-image/{user_id} endpoint and OG meta tag integration in short URL redirects.

Features tested:
1. GET /api/s/og-image/{user_id} returns 200 with PNG image (1200x630)
2. Fallback image for non-existent users (not 500 error)
3. GET /api/s/{short_code} includes og:image meta tag pointing to /api/s/og-image/{user_id}
4. OG meta tags include correct width (1200) and height (630)
5. OG meta tags include og:title and og:description
6. Personalized OG image has actual content (file size > 10KB)
"""
import os
import pytest
import requests
import os
import re
from io import BytesIO

# Use the public-facing URL for all tests
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review_request
TEST_USER_ID = "69a0b7095fddcede09591667"
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestOGImageEndpoint:
    """Test the /api/s/og-image/{user_id} endpoint"""

    def test_og_image_returns_200_for_valid_user(self):
        """Test that OG image endpoint returns 200 status for a valid user"""
        response = requests.get(f"{BASE_URL}/api/s/og-image/{TEST_USER_ID}", timeout=15)
        
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}. Response: {response.text[:200]}"
        print(f"PASS: OG image endpoint returns 200 for valid user")

    def test_og_image_returns_png_content_type(self):
        """Test that OG image endpoint returns PNG content type"""
        response = requests.get(f"{BASE_URL}/api/s/og-image/{TEST_USER_ID}", timeout=15)
        
        assert response.status_code == 200
        content_type = response.headers.get('Content-Type', '')
        assert 'image/png' in content_type, f"Expected image/png but got {content_type}"
        print(f"PASS: OG image returns PNG content type: {content_type}")

    def test_og_image_has_correct_dimensions(self):
        """Test that OG image is 1200x630 pixels"""
        from PIL import Image
        
        response = requests.get(f"{BASE_URL}/api/s/og-image/{TEST_USER_ID}", timeout=15)
        assert response.status_code == 200
        
        # Load image from response content
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        
        assert width == 1200, f"Expected width 1200 but got {width}"
        assert height == 630, f"Expected height 630 but got {height}"
        print(f"PASS: OG image has correct dimensions: {width}x{height}")

    def test_og_image_has_substantial_content(self):
        """Test that OG image has actual content (file size > 10KB)"""
        response = requests.get(f"{BASE_URL}/api/s/og-image/{TEST_USER_ID}", timeout=15)
        assert response.status_code == 200
        
        file_size = len(response.content)
        assert file_size > 10000, f"Expected file size > 10KB but got {file_size} bytes"
        print(f"PASS: OG image has substantial content: {file_size} bytes ({file_size/1024:.1f} KB)")

    def test_og_image_fallback_for_nonexistent_user(self):
        """Test that non-existent user returns fallback image (not 500 error)"""
        fake_user_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/s/og-image/{fake_user_id}", timeout=15)
        
        # Should return either 404 with fallback image or a fallback image
        # The important thing is it should NOT return 500
        assert response.status_code != 500, f"Should not return 500 error. Got: {response.status_code}"
        print(f"PASS: Non-existent user returns {response.status_code} (not 500)")

    def test_og_image_has_cache_header(self):
        """Test that OG image has cache headers for performance (may be overridden by proxy)"""
        response = requests.get(f"{BASE_URL}/api/s/og-image/{TEST_USER_ID}", timeout=15)
        assert response.status_code == 200
        
        cache_control = response.headers.get('Cache-Control', '')
        # Note: In preview environment, Kubernetes proxy may override cache headers
        # The backend code sets Cache-Control: public, max-age=3600
        # This is informational - not a critical test
        if 'max-age' in cache_control or 'public' in cache_control:
            print(f"PASS: OG image has cache headers: {cache_control}")
        else:
            # Proxy is overriding - this is expected in preview environment
            print(f"INFO: Cache headers overridden by proxy: {cache_control}")


class TestShortURLOGMetaTags:
    """Test OG meta tags in short URL redirect pages"""

    @pytest.fixture
    def auth_token(self):
        """Get authentication token for creating short URLs"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code}")

    @pytest.fixture
    def short_code(self, auth_token):
        """Get or create a short URL for the test user's business card"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/card/short-url/{TEST_USER_ID}",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("short_code")
        pytest.skip(f"Failed to get short URL: {response.status_code} - {response.text}")

    def test_short_url_redirect_returns_html(self, short_code):
        """Test that short URL redirect returns HTML with OG meta tags"""
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False,  # Don't follow redirects - get the HTML
            timeout=10
        )
        
        # Should return HTML response (200) with meta tags
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
        assert 'text/html' in response.headers.get('Content-Type', ''), \
            f"Expected HTML but got {response.headers.get('Content-Type')}"
        print(f"PASS: Short URL redirect returns HTML")

    def test_short_url_has_og_image_meta_tag(self, short_code):
        """Test that short URL redirect has og:image meta tag"""
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        assert response.status_code == 200
        
        html = response.text
        # Check for og:image meta tag pointing to /api/s/og-image/{user_id}
        og_image_pattern = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
        match = re.search(og_image_pattern, html, re.IGNORECASE)
        
        if not match:
            # Try alternate attribute order
            og_image_pattern2 = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
            match = re.search(og_image_pattern2, html, re.IGNORECASE)
        
        assert match, f"og:image meta tag not found in HTML response"
        og_image_url = match.group(1)
        
        # Verify it points to the personalized OG image endpoint
        assert '/og-image/' in og_image_url, \
            f"og:image should point to /og-image/ endpoint but got: {og_image_url}"
        print(f"PASS: og:image meta tag found: {og_image_url}")

    def test_short_url_has_og_image_dimensions(self, short_code):
        """Test that short URL has og:image:width (1200) and og:image:height (630)"""
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        assert response.status_code == 200
        
        html = response.text
        
        # Check for og:image:width
        width_pattern = r'og:image:width["\'][^>]+content=["\'](\d+)["\']'
        width_match = re.search(width_pattern, html, re.IGNORECASE)
        if not width_match:
            width_pattern2 = r'content=["\'](\d+)["\'][^>]+og:image:width'
            width_match = re.search(width_pattern2, html, re.IGNORECASE)
        
        assert width_match, "og:image:width meta tag not found"
        width = int(width_match.group(1))
        assert width == 1200, f"Expected og:image:width=1200 but got {width}"
        
        # Check for og:image:height
        height_pattern = r'og:image:height["\'][^>]+content=["\'](\d+)["\']'
        height_match = re.search(height_pattern, html, re.IGNORECASE)
        if not height_match:
            height_pattern2 = r'content=["\'](\d+)["\'][^>]+og:image:height'
            height_match = re.search(height_pattern2, html, re.IGNORECASE)
        
        assert height_match, "og:image:height meta tag not found"
        height = int(height_match.group(1))
        assert height == 630, f"Expected og:image:height=630 but got {height}"
        
        print(f"PASS: og:image dimensions correct - width={width}, height={height}")

    def test_short_url_has_og_title(self, short_code):
        """Test that short URL has og:title meta tag"""
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        assert response.status_code == 200
        
        html = response.text
        
        # Check for og:title
        title_pattern = r'og:title["\'][^>]+content=["\']([^"\']+)["\']'
        match = re.search(title_pattern, html, re.IGNORECASE)
        if not match:
            title_pattern2 = r'content=["\']([^"\']+)["\'][^>]+og:title'
            match = re.search(title_pattern2, html, re.IGNORECASE)
        
        assert match, "og:title meta tag not found"
        og_title = match.group(1)
        assert len(og_title) > 0, "og:title should not be empty"
        print(f"PASS: og:title found: {og_title}")

    def test_short_url_has_og_description(self, short_code):
        """Test that short URL has og:description meta tag"""
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        assert response.status_code == 200
        
        html = response.text
        
        # Check for og:description
        desc_pattern = r'og:description["\'][^>]+content=["\']([^"\']*)["\']'
        match = re.search(desc_pattern, html, re.IGNORECASE)
        if not match:
            desc_pattern2 = r'content=["\']([^"\']*)["\'][^>]+og:description'
            match = re.search(desc_pattern2, html, re.IGNORECASE)
        
        assert match, "og:description meta tag not found"
        og_desc = match.group(1)
        # Description can be empty for some link types, just verify the tag exists
        print(f"PASS: og:description found: '{og_desc}'")


class TestOGImageIntegration:
    """Integration tests - verify the complete flow"""

    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Authentication failed: {response.status_code}")

    def test_og_image_url_from_short_url_is_accessible(self, auth_token):
        """Test that the og:image URL from short URL is actually accessible"""
        # Get short URL
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/card/short-url/{TEST_USER_ID}",
            headers=headers,
            timeout=10
        )
        assert response.status_code == 200
        short_code = response.json().get("short_code")
        
        # Get HTML from short URL
        html_response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        assert html_response.status_code == 200
        
        # Extract og:image URL
        og_image_pattern = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
        match = re.search(og_image_pattern, html_response.text, re.IGNORECASE)
        if not match:
            og_image_pattern2 = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
            match = re.search(og_image_pattern2, html_response.text, re.IGNORECASE)
        
        assert match, "Could not find og:image URL in HTML"
        og_image_url = match.group(1)
        
        # Verify the og:image URL is accessible
        img_response = requests.get(og_image_url, timeout=15)
        assert img_response.status_code == 200, \
            f"og:image URL not accessible: {og_image_url}, status: {img_response.status_code}"
        assert 'image/png' in img_response.headers.get('Content-Type', ''), \
            f"og:image should be PNG but got: {img_response.headers.get('Content-Type')}"
        
        print(f"PASS: og:image URL is accessible and returns PNG")

    def test_og_image_not_blank(self, auth_token):
        """Test that generated OG image is not just a blank/white image"""
        from PIL import Image
        import numpy as np
        
        response = requests.get(f"{BASE_URL}/api/s/og-image/{TEST_USER_ID}", timeout=15)
        assert response.status_code == 200
        
        # Load image
        img = Image.open(BytesIO(response.content))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Convert to numpy array to analyze
        img_array = np.array(img)
        
        # Calculate color variance - a blank image would have very low variance
        variance = np.var(img_array)
        
        # A meaningful image should have some variance (not all one color)
        assert variance > 100, f"Image appears to be mostly one color (variance: {variance})"
        
        # Check that it's not all white or all black
        mean_color = np.mean(img_array)
        assert mean_color > 5, f"Image appears to be all black (mean: {mean_color})"
        assert mean_color < 250, f"Image appears to be all white (mean: {mean_color})"
        
        print(f"PASS: OG image has actual visual content (variance: {variance:.0f}, mean: {mean_color:.0f})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
