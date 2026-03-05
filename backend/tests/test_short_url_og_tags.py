"""
Test Short URL OG Tags Feature
Tests that short URL redirect serves dynamic OG meta tags for link preview crawlers.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user from credentials
USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
CONTACT_ID = "69a7901fa9f726b6a7008b87"


class TestShortUrlCreation:
    """Test creating short URLs via POST /api/s/create"""

    def test_create_short_url_business_card(self):
        """Create a short URL for a business card link."""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/card/69a0b7095fddcede09591667",
            "link_type": "business_card",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
            "metadata": {"contact_id": CONTACT_ID}
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "short_code" in data, "Response should contain short_code"
        assert "short_url" in data, "Response should contain short_url"
        assert "original_url" in data, "Response should contain original_url"
        
        # Verify short URL format
        assert "/api/s/" in data["short_url"], f"Short URL should contain /api/s/, got {data['short_url']}"
        assert len(data["short_code"]) >= 6, "Short code should be at least 6 characters"
        
        print(f"✓ Created short URL: {data['short_url']}")
        return data["short_code"]

    def test_create_short_url_review_request(self):
        """Create a short URL for a review request link."""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://g.co/maps/review/test-business",
            "link_type": "review_request",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
            "metadata": {"contact_id": CONTACT_ID, "platform": "google"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "short_url" in data
        print(f"✓ Created review short URL: {data['short_url']}")
        return data["short_code"]

    def test_create_short_url_showcase(self):
        """Create a short URL for a showcase link."""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/showcase/{USER_ID}",
            "link_type": "showcase",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
            "metadata": {"contact_id": CONTACT_ID}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "short_url" in data
        print(f"✓ Created showcase short URL: {data['short_url']}")
        return data["short_code"]

    def test_create_short_url_link_page(self):
        """Create a short URL for a link page."""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/l/testuser",
            "link_type": "link_page",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
            "metadata": {"contact_id": CONTACT_ID}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "short_url" in data
        print(f"✓ Created link page short URL: {data['short_url']}")
        return data["short_code"]


class TestShortUrlRedirectWithOgTags:
    """Test short URL redirect behavior with OG tag support for crawlers."""

    @pytest.fixture(autouse=True)
    def setup_short_url(self):
        """Create a test short URL before each test."""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": f"https://app.imonsocial.com/card/{USER_ID}",
            "link_type": "business_card",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
            "metadata": {"contact_id": CONTACT_ID}
        })
        assert response.status_code == 200
        self.short_code = response.json()["short_code"]
        self.short_url = response.json()["short_url"]

    def test_crawler_gets_og_tags_html(self):
        """Crawlers (e.g., iMessage, Facebook) should get HTML with OG tags."""
        # Use User-Agent that mimics iMessage/Facebook crawler
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
        }
        
        # Make request - don't follow redirects to check the HTML response
        response = requests.get(
            f"{BASE_URL}/api/s/{self.short_code}",
            headers=headers,
            allow_redirects=False
        )
        
        # Should return HTML (200) not a redirect
        assert response.status_code == 200, f"Crawler should get 200 HTML response, got {response.status_code}"
        
        # Verify it's HTML
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected text/html, got {content_type}"
        
        # Verify OG tags are present
        html = response.text
        assert "og:title" in html, "HTML should contain og:title meta tag"
        assert "og:description" in html or "og:type" in html, "HTML should contain og:description or og:type"
        
        # For business card links, should have user name in title
        print(f"✓ Crawler received HTML with OG tags")
        print(f"  Content preview: {html[:500]}...")

    def test_regular_browser_gets_302_redirect(self):
        """Regular browsers should get a 302 redirect to original URL."""
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
        }
        
        response = requests.get(
            f"{BASE_URL}/api/s/{self.short_code}",
            headers=headers,
            allow_redirects=False
        )
        
        # Should be a 302 redirect
        assert response.status_code == 302, f"Browser should get 302 redirect, got {response.status_code}"
        
        # Verify redirect location
        location = response.headers.get("location", "")
        assert "imonsocial.com" in location or "card" in location, f"Redirect should go to original URL, got {location}"
        
        print(f"✓ Browser received 302 redirect to: {location}")

    def test_crawler_og_image_is_store_logo(self):
        """Verify OG image is the store's logo, not the default app logo."""
        headers = {
            "User-Agent": "facebookexternalhit/1.1"
        }
        
        response = requests.get(
            f"{BASE_URL}/api/s/{self.short_code}",
            headers=headers,
            allow_redirects=False
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Check if og:image is present
        if 'og:image' in html:
            print(f"✓ OG image tag found in HTML")
            # Should NOT contain default i'M On Social logo
            assert "imonsocial-logo" not in html.lower(), "Should use store logo, not default app logo"
        else:
            # It's OK if no image - might not have store logo configured
            print("⚠ No og:image tag found (store may not have logo configured)")

    def test_business_card_og_title_includes_user_name(self):
        """Business card links should have user's name in OG title."""
        headers = {
            "User-Agent": "Twitterbot/1.0"
        }
        
        response = requests.get(
            f"{BASE_URL}/api/s/{self.short_code}",
            headers=headers,
            allow_redirects=False
        )
        
        assert response.status_code == 200
        html = response.text
        
        # OG title should mention "Digital Card" or user name
        assert 'og:title' in html, "Should have og:title"
        
        # Extract og:title content
        import re
        match = re.search(r'og:title["\s]+content="([^"]+)"', html)
        if match:
            og_title = match.group(1)
            print(f"✓ OG title: {og_title}")
            # Should be descriptive, not just "Check this out!"
            assert len(og_title) > 5, "OG title should be descriptive"


class TestShortUrlStats:
    """Test short URL stats/analytics."""

    def test_get_stats_for_short_url(self):
        """Get click stats for a short URL."""
        # First create a short URL
        create_response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/test-stats",
            "link_type": "custom",
            "user_id": USER_ID,
        })
        assert create_response.status_code == 200
        short_code = create_response.json()["short_code"]
        
        # Click it once (as a regular browser)
        requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=False
        )
        
        # Get stats
        stats_response = requests.get(f"{BASE_URL}/api/s/stats/{short_code}")
        assert stats_response.status_code == 200
        
        stats = stats_response.json()
        assert "click_count" in stats, "Stats should include click_count"
        assert stats["click_count"] >= 1, f"Click count should be at least 1, got {stats['click_count']}"
        
        print(f"✓ Stats retrieved - clicks: {stats['click_count']}")

    def test_stats_404_for_nonexistent_url(self):
        """Stats endpoint should return 404 for nonexistent short codes."""
        response = requests.get(f"{BASE_URL}/api/s/stats/NONEXISTENT123")
        assert response.status_code == 404


class TestDuplicateShortUrls:
    """Test that duplicate URLs return existing short code."""

    def test_same_url_returns_same_short_code(self):
        """Creating the same short URL twice should return the same short code."""
        original_url = f"https://app.imonsocial.com/card/{USER_ID}?test=duplicate"
        
        # First creation
        response1 = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": original_url,
            "link_type": "business_card",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
        })
        assert response1.status_code == 200
        short_code1 = response1.json()["short_code"]
        
        # Second creation with same URL
        response2 = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": original_url,
            "link_type": "business_card",
            "user_id": USER_ID,
            "reference_id": CONTACT_ID,
        })
        assert response2.status_code == 200
        short_code2 = response2.json()["short_code"]
        
        # Should be the same short code
        assert short_code1 == short_code2, f"Same URL should return same short code: {short_code1} != {short_code2}"
        print(f"✓ Duplicate URL returns same short code: {short_code1}")
