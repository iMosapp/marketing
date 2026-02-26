"""
Test Social Links Feature for Digital Card
Tests:
1. Profile API stores just usernames (not full URLs)
2. Card data API returns social_links
3. @ symbol handling in usernames
4. Backwards compatibility with existing data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID
USER_ID = "699907444a076891982fab35"


class TestSocialLinksProfile:
    """Tests for social links in profile API"""
    
    def test_get_profile_returns_social_links(self):
        """GET /api/profile/{user_id} should return social_links"""
        response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        assert "social_links" in data["user"]
        print(f"Profile social_links: {data['user']['social_links']}")
    
    def test_update_social_links_with_username_only(self):
        """PUT /api/profile/{user_id} should store just username, not full URL"""
        test_links = {
            "facebook": "testuser123",
            "instagram": "testhandle",
            "linkedin": "testprofile",
            "twitter": "testtwitterhandle",
            "tiktok": "testtiktokuser",
            "youtube": "testyoutubechannel"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"social_links": test_links}
        )
        assert response.status_code == 200
        assert response.json()["success"] == True
        
        # Verify the data was saved correctly
        get_response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        assert get_response.status_code == 200
        
        saved_links = get_response.json()["user"]["social_links"]
        
        # Verify usernames are stored as-is (not full URLs)
        assert saved_links.get("facebook") == "testuser123", "Facebook username not saved correctly"
        assert saved_links.get("instagram") == "testhandle", "Instagram username not saved correctly"
        assert saved_links.get("linkedin") == "testprofile", "LinkedIn username not saved correctly"
        assert saved_links.get("twitter") == "testtwitterhandle", "Twitter username not saved correctly"
        assert saved_links.get("tiktok") == "testtiktokuser", "TikTok username not saved correctly"
        assert saved_links.get("youtube") == "testyoutubechannel", "YouTube username not saved correctly"
        
        print(f"All usernames saved correctly: {saved_links}")
    
    def test_at_symbol_in_username_storage(self):
        """Backend should store username as-is (frontend strips @)"""
        # Test that backend accepts username with @ if client sends it
        test_links = {
            "instagram": "@handlewithat",
            "twitter": "@twitterwithat"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"social_links": test_links}
        )
        assert response.status_code == 200
        
        # Verify backend stores exactly what was sent
        get_response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        saved_links = get_response.json()["user"]["social_links"]
        
        # Backend stores what frontend sends - frontend should strip @
        print(f"Stored with @: {saved_links}")
        assert saved_links.get("instagram") == "@handlewithat"
        assert saved_links.get("twitter") == "@twitterwithat"
    
    def test_empty_social_links(self):
        """Empty social links should be stored correctly"""
        test_links = {
            "facebook": "",
            "instagram": "",
            "linkedin": ""
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"social_links": test_links}
        )
        assert response.status_code == 200
        
        get_response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        saved_links = get_response.json()["user"]["social_links"]
        
        assert saved_links.get("facebook") == ""
        assert saved_links.get("instagram") == ""
        assert saved_links.get("linkedin") == ""
        print("Empty social links stored correctly")


class TestSocialLinksCardData:
    """Tests for social links in card data API"""
    
    def test_card_data_returns_social_links(self):
        """GET /api/card/data/{user_id} should return social_links"""
        response = requests.get(f"{BASE_URL}/api/card/data/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        assert "social_links" in data["user"]
        print(f"Card data social_links: {data['user']['social_links']}")
    
    def test_card_data_matches_profile_social_links(self):
        """Card data social_links should match profile social_links"""
        # First set specific social links via profile API
        test_links = {
            "facebook": "its4est",
            "instagram": "im4est",
            "linkedin": "forestward"
        }
        
        requests.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"social_links": test_links}
        )
        
        # Get profile data
        profile_response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        profile_links = profile_response.json()["user"]["social_links"]
        
        # Get card data
        card_response = requests.get(f"{BASE_URL}/api/card/data/{USER_ID}")
        card_links = card_response.json()["user"]["social_links"]
        
        # Verify they match
        assert profile_links.get("facebook") == card_links.get("facebook")
        assert profile_links.get("instagram") == card_links.get("instagram")
        assert profile_links.get("linkedin") == card_links.get("linkedin")
        print(f"Profile and card social_links match: {card_links}")


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with existing social link data"""
    
    def test_restore_original_data(self):
        """Restore original test data for frontend testing"""
        original_links = {
            "facebook": "its4est",
            "instagram": "@im4est",  # With @ to test stripping
            "linkedin": "forestward"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"social_links": original_links}
        )
        assert response.status_code == 200
        
        # Verify
        get_response = requests.get(f"{BASE_URL}/api/profile/{USER_ID}")
        saved_links = get_response.json()["user"]["social_links"]
        
        print(f"Restored original data: {saved_links}")
        assert saved_links.get("facebook") == "its4est"
        assert saved_links.get("instagram") == "@im4est"
        assert saved_links.get("linkedin") == "forestward"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
