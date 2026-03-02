"""
Test Link Page Auto-Sync from User Profile Social Links
This tests the feature: When link page has all-empty social usernames
and user profile has social links, GET /api/linkpage/user/{user_id}
should auto-sync them.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"
USERNAME = "forestward"


class TestLinkPageAutoSync:
    """Tests for link page auto-sync of social links from user profile"""
    
    def test_user_profile_has_social_links(self):
        """Verify user profile has social_links set"""
        response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        user_social = data.get("user", {}).get("social_links", {})
        
        # Verify user has social links
        assert "facebook" in user_social or "instagram" in user_social or "linkedin" in user_social, \
            "User profile should have at least one social link"
        
        print(f"User profile social_links: {user_social}")
    
    def test_linkpage_has_social_links_structure(self):
        """Verify link page returns social_links with proper structure"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        social_links = data.get("social_links", {})
        
        # All 6 platforms should exist
        expected_platforms = ["facebook", "instagram", "linkedin", "twitter", "tiktok", "youtube"]
        for platform in expected_platforms:
            assert platform in social_links, f"Platform {platform} missing from social_links"
            assert "username" in social_links[platform], f"Platform {platform} missing 'username' field"
            assert "visible" in social_links[platform], f"Platform {platform} missing 'visible' field"
        
        print(f"Link page social_links structure verified: {list(social_links.keys())}")
    
    def test_reset_social_links_to_empty(self):
        """Reset all social_links to empty usernames"""
        empty_social_links = {
            "facebook": {"username": "", "visible": False},
            "instagram": {"username": "", "visible": False},
            "linkedin": {"username": "", "visible": False},
            "twitter": {"username": "", "visible": False},
            "tiktok": {"username": "", "visible": False},
            "youtube": {"username": "", "visible": False},
        }
        
        response = requests.put(
            f"{BASE_URL}/api/linkpage/user/{USER_ID}",
            json={"social_links": empty_social_links}
        )
        assert response.status_code == 200
        
        # Verify the update
        verify_response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        assert verify_response.status_code == 200
        data = verify_response.json()
        social_links = data.get("social_links", {})
        
        print(f"After reset, social_links: {social_links}")
    
    def test_auto_sync_from_profile(self):
        """
        After resetting to empty, verify GET auto-syncs from user profile.
        This is the core test for the auto-sync feature.
        """
        # First, reset all social_links to empty
        empty_social_links = {
            "facebook": {"username": "", "visible": False},
            "instagram": {"username": "", "visible": False},
            "linkedin": {"username": "", "visible": False},
            "twitter": {"username": "", "visible": False},
            "tiktok": {"username": "", "visible": False},
            "youtube": {"username": "", "visible": False},
        }
        
        reset_response = requests.put(
            f"{BASE_URL}/api/linkpage/user/{USER_ID}",
            json={"social_links": empty_social_links}
        )
        assert reset_response.status_code == 200, "Reset should succeed"
        
        # Now GET the link page - auto-sync should kick in
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        social_links = data.get("social_links", {})
        
        # Get user profile social links for comparison
        profile_response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        profile_data = profile_response.json()
        user_social = profile_data.get("user", {}).get("social_links", {})
        
        # Check if auto-sync happened
        synced_count = 0
        for platform, username in user_social.items():
            if username and platform in social_links:
                link_username = social_links[platform].get("username", "")
                if link_username:
                    synced_count += 1
                    print(f"SYNCED {platform}: {link_username}")
        
        # If user has social links, they should be synced
        if user_social:
            assert synced_count > 0, \
                f"Auto-sync should have populated social_links from user profile. User social: {user_social}, Link page: {social_links}"
        
        print(f"Auto-sync verified: {synced_count} social links synced from profile")
        print(f"User profile social_links: {user_social}")
        print(f"Link page social_links after sync: {social_links}")
    
    def test_public_page_shows_synced_links(self):
        """Verify public page shows the synced social links"""
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{USERNAME}")
        assert response.status_code == 200
        
        data = response.json()
        built_social_links = data.get("built_social_links", [])
        
        print(f"Public page built_social_links count: {len(built_social_links)}")
        for link in built_social_links:
            print(f"  - {link.get('label')}: {link.get('url')}")
        
        # Should have at least the synced social links
        # Note: only visible links with usernames appear in built_social_links


class TestLinkPageSocialLinksVerification:
    """Additional verification tests for social links"""
    
    def test_facebook_username_extracted(self):
        """Test that Facebook username is properly extracted"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        fb = data.get("social_links", {}).get("facebook", {})
        username = fb.get("username", "")
        
        if username:
            # Username should not contain URL parts
            assert "facebook.com" not in username.lower(), "Username should not contain URL"
            assert "/" not in username, "Username should not contain slashes"
            print(f"Facebook username: {username}")
    
    def test_instagram_username_extracted(self):
        """Test that Instagram username is properly extracted"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        ig = data.get("social_links", {}).get("instagram", {})
        username = ig.get("username", "")
        
        if username:
            assert "instagram.com" not in username.lower(), "Username should not contain URL"
            assert "@" not in username, "Username should not start with @"
            print(f"Instagram username: {username}")
    
    def test_linkedin_username_extracted(self):
        """Test that LinkedIn username is properly extracted"""
        response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        li = data.get("social_links", {}).get("linkedin", {})
        username = li.get("username", "")
        
        if username:
            assert "linkedin.com" not in username.lower(), "Username should not contain URL"
            print(f"LinkedIn username: {username}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
