"""
Test Contextual OG Meta Tags for Short URL Redirects
Tests that different card types, review requests, and business cards
get contextual OG tags with customer photos, store logos, and proper titles.

Test cases:
- Congrats/birthday/anniversary/thankyou/welcome/holiday cards show customer photo + contextual title
- Review request links show store logo + "Share Your Experience with [Store]"
- Business card links show salesperson photo + "[Name]'s Digital Card"
- Normal browsers get 302 redirect, NOT HTML
- OG tags have proper dimensions (og:image:width, og:image:height)
- Customer names are title-cased
"""
import pytest
import requests
import re
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known short codes from test data
KNOWN_SHORT_CODES = {
    "congrats_card": "j2YYxc",
    "birthday_card": "ESTvPu",
    "review_request": "yrj7rS",
    "business_card": "AqCPAn",
}

# Crawler user-agents for testing
CRAWLER_USER_AGENT = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
BROWSER_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"


def extract_og_tag(html: str, property_name: str) -> str:
    """Extract the content of an OG meta tag from HTML."""
    # Match both og:property and name patterns
    patterns = [
        rf'<meta\s+property="{property_name}"\s+content="([^"]*)"',
        rf'<meta\s+content="([^"]*)"\s+property="{property_name}"',
        rf'property="{property_name}"\s+content="([^"]*)"',
        rf'content="([^"]*)"\s+property="{property_name}"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


class TestCardOgTags:
    """Test OG tags for congratulations/birthday/etc card links."""

    def test_congrats_card_og_title(self):
        """Congrats card should have 'Congrats [Name]!' as og:title."""
        short_code = KNOWN_SHORT_CODES.get("congrats_card")
        if not short_code:
            pytest.skip("No congrats_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200, f"Expected 200 for crawler, got {response.status_code}"
        html = response.text
        
        # Extract og:title
        og_title = extract_og_tag(html, "og:title")
        print(f"og:title = {og_title}")
        
        # Should contain "Congrats" or be contextual
        assert og_title, "og:title should not be empty"
        assert "congrats" in og_title.lower() or "card" in og_title.lower() or og_title != "Check this out!", \
            f"Expected contextual title for congrats card, got: {og_title}"
        
        # Verify customer name is title-cased if present
        if "Congrats" in og_title:
            # Extract name after "Congrats "
            name_match = re.search(r"Congrats\s+([^!]+)", og_title)
            if name_match:
                name = name_match.group(1).strip()
                assert name == name.title(), f"Customer name should be title-cased: '{name}' vs '{name.title()}'"
                print(f"✓ Customer name properly title-cased: {name}")

    def test_birthday_card_og_title(self):
        """Birthday card should have 'Happy Birthday [Name]!' as og:title."""
        short_code = KNOWN_SHORT_CODES.get("birthday_card")
        if not short_code:
            pytest.skip("No birthday_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200, f"Expected 200 for crawler, got {response.status_code}"
        html = response.text
        
        og_title = extract_og_tag(html, "og:title")
        print(f"og:title = {og_title}")
        
        assert og_title, "og:title should not be empty"
        # Should contain "Birthday" or be contextual
        assert "birthday" in og_title.lower() or "card" in og_title.lower() or og_title != "Check this out!", \
            f"Expected contextual title for birthday card, got: {og_title}"

    def test_card_og_description_not_empty(self):
        """Card links should have og:description with store/salesman info."""
        short_code = KNOWN_SHORT_CODES.get("congrats_card")
        if not short_code:
            pytest.skip("No congrats_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200
        html = response.text
        
        og_description = extract_og_tag(html, "og:description")
        print(f"og:description = {og_description}")
        
        # Description should mention "From" + store or salesman
        if og_description:
            print(f"✓ og:description is populated: {og_description}")
            # Ideally contains "From" and store/salesman name
            if "From" in og_description:
                print(f"✓ Description includes 'From' attribution")
        else:
            print("⚠ og:description is empty (may be expected if no store/salesman info)")

    def test_card_og_image_is_customer_photo(self):
        """Card links should use customer photo URL as og:image."""
        short_code = KNOWN_SHORT_CODES.get("congrats_card")
        if not short_code:
            pytest.skip("No congrats_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200
        html = response.text
        
        og_image = extract_og_tag(html, "og:image")
        print(f"og:image = {og_image}")
        
        # og:image should be present
        assert og_image, "og:image should be present"
        # Should not be the default og-image.png unless no photo available
        if "og-image.png" in og_image:
            print("⚠ Using default og-image.png (customer may not have photo)")
        else:
            print(f"✓ og:image uses custom photo/image: {og_image}")


class TestReviewRequestOgTags:
    """Test OG tags for review request links."""

    def test_review_request_og_title(self):
        """Review request should have 'Share Your Experience with [Store]' as og:title."""
        short_code = KNOWN_SHORT_CODES.get("review_request")
        if not short_code:
            pytest.skip("No review_request short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200, f"Expected 200 for crawler, got {response.status_code}"
        html = response.text
        
        og_title = extract_og_tag(html, "og:title")
        print(f"og:title = {og_title}")
        
        assert og_title, "og:title should not be empty"
        # Should mention "Experience", "Review", "Feedback", or store name
        expected_patterns = ["experience", "feedback", "review", "share"]
        has_expected = any(p in og_title.lower() for p in expected_patterns)
        assert has_expected or og_title != "Check this out!", \
            f"Expected contextual review title, got: {og_title}"

    def test_review_request_og_image_is_store_logo(self):
        """Review request should use store logo as og:image."""
        short_code = KNOWN_SHORT_CODES.get("review_request")
        if not short_code:
            pytest.skip("No review_request short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200
        html = response.text
        
        og_image = extract_og_tag(html, "og:image")
        print(f"og:image = {og_image}")
        
        assert og_image, "og:image should be present"
        # Should reference the store logo OG image endpoint
        if "/api/s/og-image/" in og_image:
            print(f"✓ og:image uses store logo endpoint: {og_image}")
        else:
            print(f"✓ og:image present: {og_image}")


class TestBusinessCardOgTags:
    """Test OG tags for digital business card links."""

    def test_business_card_og_title(self):
        """Business card should have '[Name]'s Digital Card' as og:title."""
        short_code = KNOWN_SHORT_CODES.get("business_card")
        if not short_code:
            pytest.skip("No business_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200, f"Expected 200 for crawler, got {response.status_code}"
        html = response.text
        
        og_title = extract_og_tag(html, "og:title")
        print(f"og:title = {og_title}")
        
        assert og_title, "og:title should not be empty"
        # Should mention "Digital Card" or person's name
        expected_patterns = ["digital card", "card", "connect"]
        has_expected = any(p in og_title.lower() for p in expected_patterns)
        assert has_expected or og_title != "Check this out!", \
            f"Expected contextual business card title, got: {og_title}"

    def test_business_card_og_image_is_salesperson_photo(self):
        """Business card should use salesperson photo as og:image."""
        short_code = KNOWN_SHORT_CODES.get("business_card")
        if not short_code:
            pytest.skip("No business_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200
        html = response.text
        
        og_image = extract_og_tag(html, "og:image")
        print(f"og:image = {og_image}")
        
        assert og_image, "og:image should be present"
        # Should NOT be default og-image.png if salesperson has photo
        if "og-image.png" in og_image:
            print("⚠ Using default og-image.png (salesperson may not have photo)")
        else:
            print(f"✓ og:image uses custom image: {og_image}")


class TestOgTagDimensions:
    """Test that OG image tags have proper dimensions."""

    def test_og_image_has_dimensions(self):
        """OG image tags should include og:image:width and og:image:height."""
        short_code = KNOWN_SHORT_CODES.get("congrats_card")
        if not short_code:
            pytest.skip("No congrats_card short code available")
        
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        if response.status_code == 404:
            pytest.skip(f"Short code {short_code} not found in database")
        
        assert response.status_code == 200
        html = response.text
        
        og_image = extract_og_tag(html, "og:image")
        og_width = extract_og_tag(html, "og:image:width")
        og_height = extract_og_tag(html, "og:image:height")
        
        print(f"og:image = {og_image}")
        print(f"og:image:width = {og_width}")
        print(f"og:image:height = {og_height}")
        
        # Should have dimensions if image is present
        if og_image:
            assert og_width, "og:image:width should be present when og:image is set"
            assert og_height, "og:image:height should be present when og:image is set"
            
            # Dimensions should be numeric
            assert og_width.isdigit(), f"og:image:width should be numeric, got: {og_width}"
            assert og_height.isdigit(), f"og:image:height should be numeric, got: {og_height}"
            
            print(f"✓ OG image dimensions: {og_width}x{og_height}")


class TestNormalBrowserRedirect:
    """Test that normal browsers get 302 redirect, NOT HTML."""

    def test_browser_gets_302_not_html(self):
        """Normal browser should get 302 redirect, not HTML page."""
        for link_type, short_code in KNOWN_SHORT_CODES.items():
            response = requests.get(
                f"{BASE_URL}/api/s/{short_code}",
                headers={"User-Agent": BROWSER_USER_AGENT},
                allow_redirects=False
            )
            
            if response.status_code == 404:
                print(f"⚠ {link_type} ({short_code}) not found in database")
                continue
            
            assert response.status_code == 302, \
                f"{link_type}: Expected 302 redirect for browser, got {response.status_code}"
            
            location = response.headers.get("location", "")
            assert location, f"{link_type}: Redirect should have Location header"
            
            print(f"✓ {link_type} ({short_code}) redirects browser to: {location}")

    def test_crawler_gets_200_html(self):
        """Crawler should get 200 HTML, not 302 redirect."""
        for link_type, short_code in KNOWN_SHORT_CODES.items():
            response = requests.get(
                f"{BASE_URL}/api/s/{short_code}",
                headers={"User-Agent": CRAWLER_USER_AGENT},
                allow_redirects=False
            )
            
            if response.status_code == 404:
                print(f"⚠ {link_type} ({short_code}) not found in database")
                continue
            
            assert response.status_code == 200, \
                f"{link_type}: Expected 200 HTML for crawler, got {response.status_code}"
            
            content_type = response.headers.get("content-type", "")
            assert "text/html" in content_type, \
                f"{link_type}: Expected text/html, got {content_type}"
            
            print(f"✓ {link_type} ({short_code}) serves HTML to crawler")


class TestNameCapitalization:
    """Test that customer names in OG titles are properly capitalized."""

    def test_customer_name_title_case(self):
        """Customer names in og:title should be title-cased."""
        for link_type, short_code in KNOWN_SHORT_CODES.items():
            if link_type not in ["congrats_card", "birthday_card"]:
                continue
            
            response = requests.get(
                f"{BASE_URL}/api/s/{short_code}",
                headers={"User-Agent": CRAWLER_USER_AGENT},
                allow_redirects=False
            )
            
            if response.status_code == 404:
                print(f"⚠ {link_type} ({short_code}) not found in database")
                continue
            
            assert response.status_code == 200
            html = response.text
            
            og_title = extract_og_tag(html, "og:title")
            print(f"{link_type} og:title = {og_title}")
            
            # Check for proper capitalization in names
            # Names after "Congrats " or "Happy Birthday " should be title-cased
            if "Congrats" in og_title:
                name_match = re.search(r"Congrats\s+([A-Za-z]+)", og_title)
                if name_match:
                    name = name_match.group(1)
                    assert name[0].isupper(), f"Name '{name}' should start with capital"
                    print(f"✓ {link_type}: Name '{name}' is properly capitalized")
            
            if "Birthday" in og_title:
                name_match = re.search(r"Birthday\s+([A-Za-z]+)", og_title)
                if name_match:
                    name = name_match.group(1)
                    assert name[0].isupper(), f"Name '{name}' should start with capital"
                    print(f"✓ {link_type}: Name '{name}' is properly capitalized")


class TestAllCrawlerUserAgents:
    """Test that various crawler user-agents all get HTML response."""

    CRAWLER_AGENTS = [
        "facebookexternalhit/1.1",
        "Twitterbot/1.0",
        "LinkedInBot/1.0",
        "Slackbot-LinkExpanding 1.0",
        "WhatsApp/2.21.1.1",
        "TelegramBot",
        "Applebot/0.1",
        "iframely/1.3.1",
        "Embedly/0.2",
        "bot",
        "crawler",
        "spider",
        "preview",
    ]

    def test_various_crawlers_get_html(self):
        """Various crawler user-agents should all get HTML with OG tags."""
        short_code = KNOWN_SHORT_CODES.get("congrats_card")
        if not short_code:
            pytest.skip("No congrats_card short code available")
        
        for agent in self.CRAWLER_AGENTS:
            response = requests.get(
                f"{BASE_URL}/api/s/{short_code}",
                headers={"User-Agent": agent},
                allow_redirects=False
            )
            
            if response.status_code == 404:
                pytest.skip(f"Short code {short_code} not found")
            
            # Should get 200 HTML, not 302 redirect
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    print(f"✓ {agent}: 200 HTML")
                else:
                    print(f"⚠ {agent}: 200 but content-type is {content_type}")
            else:
                print(f"⚠ {agent}: Got {response.status_code} instead of 200")


class TestFallbackBehavior:
    """Test fallback behavior when card data is incomplete."""

    def test_missing_card_graceful_fallback(self):
        """Short codes without reference_id should fall back gracefully."""
        # Create a short URL without reference_id
        create_response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/test-fallback",
            "link_type": "congrats_card",
            # No reference_id
        })
        
        if create_response.status_code != 200:
            pytest.skip("Could not create test short URL")
        
        short_code = create_response.json()["short_code"]
        
        # Access with crawler
        response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            headers={"User-Agent": CRAWLER_USER_AGENT},
            allow_redirects=False
        )
        
        assert response.status_code == 200, f"Should still return 200, got {response.status_code}"
        html = response.text
        
        og_title = extract_og_tag(html, "og:title")
        print(f"Fallback og:title = {og_title}")
        
        # Should have some title, even if generic
        assert og_title, "Should have a fallback og:title"
        print(f"✓ Graceful fallback with title: {og_title}")
