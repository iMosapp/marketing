"""
Test Link Page API - Social Links Rewrite
Tests the new social_links structure: {platform: {username, visible}}
Tests built_social_links and contact_links for public pages
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_USERNAME = "forestward"

# Expected social platforms
EXPECTED_PLATFORMS = ["facebook", "instagram", "linkedin", "twitter", "tiktok", "youtube"]


class TestSocialLinksUserEndpoint:
    """Tests for GET /api/linkpage/user/{user_id} - social_links structure"""

    def test_get_user_link_page_has_social_links(self):
        """Test that social_links dict exists with all 6 platforms"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "social_links" in data, "Response should have social_links"
        
        social_links = data["social_links"]
        assert isinstance(social_links, dict), "social_links should be a dict"
        
        # Check all 6 platforms exist
        for platform in EXPECTED_PLATFORMS:
            assert platform in social_links, f"Missing platform: {platform}"
            entry = social_links[platform]
            assert "username" in entry, f"{platform} should have 'username' field"
            assert "visible" in entry, f"{platform} should have 'visible' field"
            assert isinstance(entry["username"], str), f"{platform}.username should be string"
            assert isinstance(entry["visible"], bool), f"{platform}.visible should be boolean"
        
        print(f"PASS: social_links contains all 6 platforms with correct structure")

    def test_social_links_expected_values(self):
        """Test that Facebook/Instagram/LinkedIn have expected values"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        social_links = data["social_links"]
        
        # Test expected values from the context
        assert social_links["facebook"]["username"] == "forestward", "Facebook username should be forestward"
        assert social_links["facebook"]["visible"] == True, "Facebook should be visible"
        
        assert social_links["instagram"]["username"] == "forestward_sales", "Instagram username should be forestward_sales"
        assert social_links["instagram"]["visible"] == True, "Instagram should be visible"
        
        assert social_links["linkedin"]["username"] == "forestward", "LinkedIn username should be forestward"
        assert social_links["linkedin"]["visible"] == True, "LinkedIn should be visible"
        
        # Twitter/TikTok/YouTube should be empty and hidden
        for platform in ["twitter", "tiktok", "youtube"]:
            assert social_links[platform]["username"] == "", f"{platform} username should be empty"
            assert social_links[platform]["visible"] == False, f"{platform} should be hidden"
        
        print("PASS: Social links have expected values")


class TestSocialLinksUpdate:
    """Tests for PUT /api/linkpage/user/{user_id} - updating social_links"""

    def test_update_social_links(self):
        """Test PUT /api/linkpage/user/{user_id} updates social_links"""
        # Get current state
        get_response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        assert get_response.status_code == 200
        original_data = get_response.json()
        original_social_links = original_data.get("social_links", {})
        
        # Update Twitter username
        new_social_links = {
            **original_social_links,
            "twitter": {"username": "test_twitter_update", "visible": True}
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}",
            json={"social_links": new_social_links}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update
        verify_response = requests.get(f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}")
        verify_data = verify_response.json()
        assert verify_data["social_links"]["twitter"]["username"] == "test_twitter_update"
        assert verify_data["social_links"]["twitter"]["visible"] == True
        
        # Restore original state
        requests.put(
            f"{BASE_URL}/api/linkpage/user/{TEST_USER_ID}",
            json={"social_links": original_social_links}
        )
        
        print("PASS: Social links update works correctly")


class TestPublicPageBuiltSocialLinks:
    """Tests for GET /api/linkpage/public/{username} - built_social_links"""

    def test_public_page_has_built_social_links(self):
        """Test that public page returns built_social_links array"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        assert "built_social_links" in data, "Public page should have built_social_links"
        
        built_links = data["built_social_links"]
        assert isinstance(built_links, list), "built_social_links should be a list"
        
        print(f"PASS: Public page has built_social_links with {len(built_links)} links")

    def test_built_social_links_have_full_urls(self):
        """Test that built_social_links contain full URLs"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        built_links = data["built_social_links"]
        
        # Expected URLs for visible platforms
        expected_urls = {
            "facebook": "https://facebook.com/forestward",
            "instagram": "https://instagram.com/forestward_sales",
            "linkedin": "https://linkedin.com/in/forestward"
        }
        
        for link in built_links:
            assert "id" in link, "Link should have id"
            assert "url" in link, "Link should have url"
            assert "label" in link, "Link should have label"
            assert "icon" in link, "Link should have icon"
            assert "color" in link, "Link should have color"
            
            platform_id = link["id"]
            if platform_id in expected_urls:
                assert link["url"] == expected_urls[platform_id], f"Wrong URL for {platform_id}: {link['url']}"
        
        print("PASS: built_social_links have correct full URLs")

    def test_built_social_links_only_visible(self):
        """Test that only visible links with non-empty usernames are in built_social_links"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        built_links = data["built_social_links"]
        
        # Should only have 3 links (facebook, instagram, linkedin)
        assert len(built_links) == 3, f"Expected 3 built social links, got {len(built_links)}"
        
        visible_ids = [link["id"] for link in built_links]
        assert "facebook" in visible_ids
        assert "instagram" in visible_ids
        assert "linkedin" in visible_ids
        assert "twitter" not in visible_ids, "Twitter should not be in built_social_links (hidden)"
        assert "tiktok" not in visible_ids, "TikTok should not be in built_social_links (hidden)"
        assert "youtube" not in visible_ids, "YouTube should not be in built_social_links (hidden)"
        
        print("PASS: Only visible social links with usernames are returned")


class TestPublicPageContactLinks:
    """Tests for GET /api/linkpage/public/{username} - contact_links"""

    def test_public_page_has_contact_links(self):
        """Test that public page returns contact_links array"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        assert "contact_links" in data, "Public page should have contact_links"
        
        contact_links = data["contact_links"]
        assert isinstance(contact_links, list), "contact_links should be a list"
        
        print(f"PASS: Public page has contact_links with {len(contact_links)} links")

    def test_contact_links_structure(self):
        """Test contact_links have correct structure"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        contact_links = data["contact_links"]
        
        expected_contact_ids = ["phone", "email", "digital_card", "google_review"]
        
        for link in contact_links:
            assert "id" in link
            assert "label" in link
            assert "url" in link
            assert "icon" in link
            assert "color" in link
            assert "visible" in link
        
        contact_ids = [link["id"] for link in contact_links]
        for expected_id in expected_contact_ids:
            assert expected_id in contact_ids, f"Missing contact link: {expected_id}"
        
        print("PASS: contact_links have correct structure")

    def test_contact_links_expected_values(self):
        """Test contact links have expected labels and URLs"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        contact_links = data["contact_links"]
        
        # Create lookup by id
        links_by_id = {link["id"]: link for link in contact_links}
        
        # Test phone link
        assert links_by_id["phone"]["label"] == "Call Me"
        assert "tel:" in links_by_id["phone"]["url"]
        
        # Test email link
        assert links_by_id["email"]["label"] == "Email Me"
        assert "mailto:" in links_by_id["email"]["url"]
        
        # Test digital card link
        assert links_by_id["digital_card"]["label"] == "My Digital Card"
        assert "/card/" in links_by_id["digital_card"]["url"]
        
        # Test review link
        assert links_by_id["google_review"]["label"] == "Leave a Review"
        
        print("PASS: contact_links have expected values")


class TestLinkPageBackwardCompatibility:
    """Tests for backward compatibility"""

    def test_public_page_still_has_links_array(self):
        """Test that public page still has links array for backward compat"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{TEST_USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        assert "links" in data, "Public page should still have links array"
        assert isinstance(data["links"], list), "links should be a list"
        
        print("PASS: Public page maintains backward compatibility with links array")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
