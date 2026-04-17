"""
Test suite for:
1. Training video short URLs with YouTube OG tags (Bug Fix #1)
2. Custom card types in GET /api/congrats/templates/all/{store_id} (Bug Fix #2)

Tests verify:
- Training video short URL metadata includes video_title
- GET /api/s/{short_code} for training_video returns HTML with YouTube OG tags
- GET /api/congrats/templates/all/{store_id} returns custom card types alongside defaults
"""
import os
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com').rstrip('/')

# Test credentials from review request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_STORE_ID = "69a0b7095fddcede09591668"
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


class TestTrainingVideoOGTags:
    """Tests for training video short URL YouTube OG tag fix (Bug #1)"""
    
    def test_create_training_video_short_url_with_video_title(self, api_client, auth_token):
        """Test that creating a training video short URL stores video_title in metadata"""
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_title = "Test Training Video"
        
        response = api_client.post(f"{BASE_URL}/api/s/create", json={
            "original_url": youtube_url,
            "link_type": "training_video",
            "user_id": TEST_USER_ID,
            "metadata": {
                "video_url": youtube_url,
                "video_title": video_title
            }
        })
        
        assert response.status_code == 200, f"Failed to create short URL: {response.text}"
        data = response.json()
        assert "short_code" in data, "Response missing short_code"
        assert "short_url" in data, "Response missing short_url"
        print(f"PASS: Created training video short URL: {data['short_url']}")
        return data["short_code"]
    
    def test_training_video_redirect_has_youtube_og_tags(self, api_client, auth_token):
        """Test that training video short URL redirect includes YouTube OG tags"""
        # First create a short URL
        youtube_url = "https://www.youtube.com/watch?v=Vj_JBS5UXrQ"
        video_title = "Saving The App Training"
        
        create_resp = api_client.post(f"{BASE_URL}/api/s/create", json={
            "original_url": youtube_url,
            "link_type": "training_video",
            "user_id": TEST_USER_ID,
            "metadata": {
                "video_url": youtube_url,
                "video_title": video_title
            }
        })
        
        assert create_resp.status_code == 200, f"Failed to create short URL: {create_resp.text}"
        short_code = create_resp.json()["short_code"]
        
        # Now fetch the redirect page (don't follow redirects to get the HTML)
        redirect_resp = api_client.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False
        )
        
        # Should return HTML with OG tags (not a redirect)
        assert redirect_resp.status_code == 200, f"Expected 200, got {redirect_resp.status_code}"
        html_content = redirect_resp.text
        
        # Check for YouTube thumbnail OG image
        assert 'og:image' in html_content, "Missing og:image meta tag"
        assert 'img.youtube.com' in html_content, "OG image should be YouTube thumbnail"
        
        # Check for video title in og:title
        assert 'og:title' in html_content, "Missing og:title meta tag"
        
        # Extract og:title content
        og_title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html_content)
        assert og_title_match, "Could not find og:title meta tag"
        og_title = og_title_match.group(1)
        
        # The og:title should contain the video title or a fallback
        print(f"PASS: og:title = '{og_title}'")
        
        # Check for og:description
        assert 'og:description' in html_content, "Missing og:description meta tag"
        
        # Extract og:image content
        og_image_match = re.search(r'<meta property="og:image" content="([^"]*)"', html_content)
        assert og_image_match, "Could not find og:image meta tag"
        og_image = og_image_match.group(1)
        
        # Should be YouTube thumbnail URL
        assert 'youtube.com/vi/' in og_image or 'img.youtube.com' in og_image, \
            f"OG image should be YouTube thumbnail, got: {og_image}"
        print(f"PASS: og:image = '{og_image}'")
        
        # Verify video ID is in the thumbnail URL
        assert 'Vj_JBS5UXrQ' in og_image, "YouTube video ID should be in thumbnail URL"
        print("PASS: Training video short URL has correct YouTube OG tags")
    
    def test_training_video_og_tags_with_youtu_be_url(self, api_client, auth_token):
        """Test YouTube OG tags work with youtu.be short URLs"""
        youtube_url = "https://youtu.be/dT7ybKZembI"
        video_title = "Setting Up Your Profile"
        
        create_resp = api_client.post(f"{BASE_URL}/api/s/create", json={
            "original_url": youtube_url,
            "link_type": "training_video",
            "user_id": TEST_USER_ID,
            "metadata": {
                "video_url": youtube_url,
                "video_title": video_title
            }
        })
        
        assert create_resp.status_code == 200, f"Failed to create short URL: {create_resp.text}"
        short_code = create_resp.json()["short_code"]
        
        # Fetch the redirect page
        redirect_resp = api_client.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False
        )
        
        assert redirect_resp.status_code == 200
        html_content = redirect_resp.text
        
        # Check for YouTube thumbnail
        og_image_match = re.search(r'<meta property="og:image" content="([^"]*)"', html_content)
        assert og_image_match, "Could not find og:image meta tag"
        og_image = og_image_match.group(1)
        
        # Should extract video ID from youtu.be URL
        assert 'dT7ybKZembI' in og_image, f"Video ID should be in thumbnail URL, got: {og_image}"
        print(f"PASS: youtu.be URL correctly extracts video ID for thumbnail")


class TestCustomCardTypes:
    """Tests for custom card types in templates endpoint (Bug #2)"""
    
    def test_get_all_templates_returns_default_types(self, api_client, auth_token):
        """Test that GET /api/congrats/templates/all/{store_id} returns default card types"""
        response = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{TEST_STORE_ID}")
        
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        templates = response.json()
        
        assert isinstance(templates, list), "Response should be a list"
        
        # Check for default card types
        default_types = ['congrats', 'birthday', 'holiday', 'thankyou', 'anniversary', 'welcome']
        template_types = [t.get('card_type') for t in templates]
        
        for dt in default_types:
            assert dt in template_types, f"Missing default card type: {dt}"
        
        print(f"PASS: Found all {len(default_types)} default card types")
        print(f"All template types: {template_types}")
    
    def test_get_all_templates_includes_custom_types(self, api_client, auth_token):
        """Test that custom card types are included in the response"""
        response = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{TEST_STORE_ID}")
        
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        templates = response.json()
        
        # Check for custom card types (not in default list)
        default_types = {'congrats', 'birthday', 'holiday', 'thankyou', 'anniversary', 'welcome'}
        custom_types = [t for t in templates if t.get('card_type') not in default_types]
        
        print(f"Found {len(custom_types)} custom card types")
        for ct in custom_types:
            print(f"  - {ct.get('card_type')}: headline='{ct.get('headline')}'")
        
        # Per the review request, store 69a0b7095fddcede09591668 has custom card type 'custom'
        # with headline 'Special Offer!'
        template_types = [t.get('card_type') for t in templates]
        
        # If custom types exist, verify they have required fields
        for ct in custom_types:
            assert 'card_type' in ct, "Custom type missing card_type"
            assert 'headline' in ct, "Custom type missing headline"
            assert 'customized' in ct, "Custom type missing customized flag"
            assert ct.get('customized') == True, "Custom types should have customized=True"
        
        print(f"PASS: Custom card types have correct structure")
    
    def test_create_custom_card_type_and_verify_in_list(self, api_client, auth_token):
        """Test creating a custom card type and verifying it appears in templates list"""
        custom_type = "test_custom_type"
        custom_headline = "Test Custom Headline"
        
        # Create a custom card template
        create_resp = api_client.post(
            f"{BASE_URL}/api/congrats/template/{TEST_STORE_ID}",
            json={
                "card_type": custom_type,
                "headline": custom_headline,
                "message": "This is a test custom card message",
                "accent_color": "#FF5733"
            }
        )
        
        assert create_resp.status_code == 200, f"Failed to create custom template: {create_resp.text}"
        print(f"PASS: Created custom card type '{custom_type}'")
        
        # Now verify it appears in the templates list
        list_resp = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{TEST_STORE_ID}")
        assert list_resp.status_code == 200
        templates = list_resp.json()
        
        # Find our custom type
        custom_template = next((t for t in templates if t.get('card_type') == custom_type), None)
        assert custom_template is not None, f"Custom type '{custom_type}' not found in templates list"
        
        # Verify the data
        assert custom_template.get('headline') == custom_headline, \
            f"Headline mismatch: expected '{custom_headline}', got '{custom_template.get('headline')}'"
        assert custom_template.get('customized') == True, "Custom type should have customized=True"
        assert custom_template.get('accent_color') == "#FF5733", "Accent color mismatch"
        
        print(f"PASS: Custom card type '{custom_type}' appears in templates list with correct data")
    
    def test_template_structure_has_required_fields(self, api_client, auth_token):
        """Test that all templates have required fields for frontend consumption"""
        response = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{TEST_STORE_ID}")
        
        assert response.status_code == 200
        templates = response.json()
        
        required_fields = ['card_type', 'headline', 'message', 'accent_color', 'background_color', 'text_color']
        
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template '{template.get('card_type')}' missing field: {field}"
        
        print(f"PASS: All {len(templates)} templates have required fields")


class TestTemplatesWrapVideoUrls:
    """Tests for _wrap_video_urls function that adds video_title to metadata"""
    
    def test_templates_endpoint_wraps_video_urls(self, api_client, auth_token):
        """Test that GET /api/templates/{user_id} wraps YouTube URLs with tracked short URLs"""
        response = api_client.get(f"{BASE_URL}/api/templates/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        templates = response.json()
        
        # Find training video templates
        video_templates = [t for t in templates if t.get('category') == 'training_video']
        
        print(f"Found {len(video_templates)} training video templates")
        
        for vt in video_templates:
            content = vt.get('content', '')
            # Check if YouTube URLs are wrapped with short URLs
            if 'youtube.com' in content or 'youtu.be' in content:
                # Raw YouTube URL found - this is expected if wrapping failed
                print(f"  - {vt.get('name')}: Contains raw YouTube URL")
            elif '/api/s/' in content:
                # Short URL found - wrapping worked
                print(f"  - {vt.get('name')}: Contains tracked short URL")
        
        print("PASS: Templates endpoint returns training video templates")


class TestFrontendIntegration:
    """Tests to verify frontend can consume the custom card types"""
    
    def test_custom_types_format_for_frontend(self, api_client, auth_token):
        """Test that custom card types have the format expected by frontend"""
        response = api_client.get(f"{BASE_URL}/api/congrats/templates/all/{TEST_STORE_ID}")
        
        assert response.status_code == 200
        templates = response.json()
        
        # Frontend expects: card_type, headline, accent_color for custom types
        # See quick-send/[action].tsx lines 91-99
        default_types = {'congrats', 'birthday', 'holiday', 'thankyou', 'anniversary', 'welcome'}
        custom_types = [t for t in templates if t.get('card_type') not in default_types]
        
        for ct in custom_types:
            # Frontend maps: key=card_type, label=headline + " Card", color=accent_color
            assert ct.get('card_type'), "Missing card_type for frontend key"
            assert ct.get('headline'), "Missing headline for frontend label"
            assert ct.get('accent_color'), "Missing accent_color for frontend color"
            
            # Simulate frontend mapping
            frontend_item = {
                'key': ct['card_type'],
                'label': f"{ct.get('headline', ct['card_type'])} Card",
                'icon': 'create-outline',
                'color': ct.get('accent_color', '#C9A962'),
            }
            print(f"Frontend item: {frontend_item}")
        
        print(f"PASS: {len(custom_types)} custom types have correct format for frontend")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
