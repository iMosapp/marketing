"""
Test suite for Digital Business Card feature
Tests: card data, campaigns, vCard generation, save/enrollment tracking
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://agreements-mgmt.preview.emergentagent.com')

# Test data from review_request
TEST_USER_ID = "69963e636d8473ba25695a34"
TEST_CONTACT_ID = "6995b8fc39e855ab676230f5"
TEST_CAMPAIGN_ID = "69969344a6e392c2c80b40e1"
INVALID_USER_ID = "000000000000000000000000"


class TestCardDataAPI:
    """Tests for GET /api/card/data/{user_id}"""
    
    def test_get_card_data_success(self):
        """Test getting card data for valid user"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify user data structure
        assert "user" in data, "Response should contain user data"
        assert "store" in data, "Response should contain store data"
        assert "testimonials" in data, "Response should contain testimonials"
        
        # Verify user fields
        user = data["user"]
        assert user["id"] == TEST_USER_ID, "User ID should match"
        assert "name" in user, "User should have name"
        assert "email" in user, "User should have email"
        assert "title" in user, "User should have title"
        assert "social_links" in user, "User should have social_links"
        
        # Verify store fields when present
        if data["store"]:
            store = data["store"]
            assert "id" in store, "Store should have id"
            assert "name" in store, "Store should have name"
            assert "primary_color" in store, "Store should have primary_color"
        
        print(f"SUCCESS: Card data retrieved for user {user['name']}")
    
    def test_get_card_data_invalid_user(self):
        """Test getting card data for non-existent user"""
        response = requests.get(f"{BASE_URL}/api/card/data/{INVALID_USER_ID}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: 404 returned for invalid user ID")
    
    def test_get_card_data_invalid_id_format(self):
        """Test getting card data with invalid ID format"""
        response = requests.get(f"{BASE_URL}/api/card/data/invalid-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: 404 returned for invalid ID format")


class TestCampaignsAPI:
    """Tests for GET /api/card/campaigns/{user_id}"""
    
    def test_get_campaigns_success(self):
        """Test getting campaigns for valid user"""
        response = requests.get(f"{BASE_URL}/api/card/campaigns/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of campaigns"
        
        if len(data) > 0:
            campaign = data[0]
            assert "id" in campaign, "Campaign should have id"
            assert "name" in campaign, "Campaign should have name"
            assert "type" in campaign, "Campaign should have type"
            print(f"SUCCESS: Found {len(data)} campaigns for user")
        else:
            print("SUCCESS: Empty campaign list returned (user has no active campaigns)")
    
    def test_campaigns_contains_expected(self):
        """Test that expected test campaign is present"""
        response = requests.get(f"{BASE_URL}/api/card/campaigns/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        campaign_ids = [c["id"] for c in data]
        assert TEST_CAMPAIGN_ID in campaign_ids, f"Expected campaign {TEST_CAMPAIGN_ID} not found"
        print(f"SUCCESS: Test campaign 'Birthday Special' found in list")
    
    def test_get_campaigns_non_existent_user(self):
        """Test getting campaigns for non-existent user returns empty"""
        response = requests.get(f"{BASE_URL}/api/card/campaigns/{INVALID_USER_ID}")
        # Non-existent user should return empty list, not error
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 0, "Should return empty list for non-existent user"
        print("SUCCESS: Empty list returned for non-existent user")


class TestVCardAPI:
    """Tests for GET /api/card/vcard/{user_id}"""
    
    def test_generate_vcard_success(self):
        """Test vCard generation for valid user"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "vcard" in data, "Response should contain vcard data"
        assert "filename" in data, "Response should contain filename"
        
        # Verify vCard structure
        vcard = data["vcard"]
        assert vcard.startswith("BEGIN:VCARD"), "vCard should start with BEGIN:VCARD"
        assert "END:VCARD" in vcard, "vCard should end with END:VCARD"
        assert "VERSION:3.0" in vcard, "vCard should have VERSION:3.0"
        assert "FN:" in vcard, "vCard should have FN (full name)"
        
        # Verify filename
        filename = data["filename"]
        assert filename.endswith(".vcf"), "Filename should have .vcf extension"
        
        print(f"SUCCESS: vCard generated with filename: {filename}")
    
    def test_vcard_contains_contact_info(self):
        """Test that vCard contains expected contact info"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{TEST_USER_ID}")
        assert response.status_code == 200
        
        vcard = response.json()["vcard"]
        assert "EMAIL:superadmin@mvpline.com" in vcard, "vCard should contain email"
        assert "ORG:Ken Garff Honda Downtown" in vcard, "vCard should contain organization"
        print("SUCCESS: vCard contains expected contact info")
    
    def test_vcard_invalid_user(self):
        """Test vCard generation for non-existent user"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{INVALID_USER_ID}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: 404 returned for invalid user ID")


class TestCardSaveAPI:
    """Tests for POST /api/card/save/{user_id}"""
    
    def test_track_card_save_success(self):
        """Test tracking card save event"""
        response = requests.post(
            f"{BASE_URL}/api/card/save/{TEST_USER_ID}",
            json={"contact_id": TEST_CONTACT_ID, "campaign_id": TEST_CAMPAIGN_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Response should contain success field"
        assert data["success"] == True, "Success should be True"
        assert "enrolled" in data, "Response should contain enrolled field"
        print(f"SUCCESS: Card save tracked, enrolled: {data.get('enrolled')}")
    
    def test_track_card_save_without_campaign(self):
        """Test tracking card save without campaign enrollment"""
        response = requests.post(
            f"{BASE_URL}/api/card/save/{TEST_USER_ID}",
            json={"contact_id": TEST_CONTACT_ID}  # No campaign_id
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] == True, "Success should be True"
        assert data["enrolled"] == False, "Enrolled should be False without campaign"
        print("SUCCESS: Card save tracked without enrollment")
    
    def test_track_card_save_empty_body(self):
        """Test tracking card save with empty body"""
        response = requests.post(
            f"{BASE_URL}/api/card/save/{TEST_USER_ID}",
            json={}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] == True, "Success should be True even with empty body"
        print("SUCCESS: Card save tracked with empty body")
    
    def test_track_card_save_invalid_campaign(self):
        """Test enrollment with invalid campaign ID"""
        response = requests.post(
            f"{BASE_URL}/api/card/save/{TEST_USER_ID}",
            json={"contact_id": TEST_CONTACT_ID, "campaign_id": INVALID_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] == True, "Success should be True"
        assert data["enrolled"] == False, "Enrolled should be False for invalid campaign"
        assert "message" in data, "Should have message explaining failure"
        print(f"SUCCESS: Card save tracked, not enrolled: {data.get('message')}")
    
    def test_track_card_save_invalid_contact(self):
        """Test enrollment with invalid contact ID"""
        response = requests.post(
            f"{BASE_URL}/api/card/save/{TEST_USER_ID}",
            json={"contact_id": INVALID_USER_ID, "campaign_id": TEST_CAMPAIGN_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] == True, "Success should be True"
        assert data["enrolled"] == False, "Enrolled should be False for invalid contact"
        print(f"SUCCESS: Card save tracked, not enrolled: {data.get('message')}")


class TestCardAPIEdgeCases:
    """Edge case tests for Digital Card APIs"""
    
    def test_card_data_excludes_password(self):
        """Verify that password is excluded from card data response"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        user = data["user"]
        assert "password" not in user, "Password should not be in response"
        print("SUCCESS: Password correctly excluded from card data")
    
    def test_card_data_testimonials_structure(self):
        """Test testimonials structure in card data"""
        response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        testimonials = data["testimonials"]
        assert isinstance(testimonials, list), "Testimonials should be a list"
        
        if len(testimonials) > 0:
            t = testimonials[0]
            assert "id" in t, "Testimonial should have id"
            assert "customer_name" in t, "Testimonial should have customer_name"
            assert "rating" in t, "Testimonial should have rating"
            print(f"SUCCESS: Found {len(testimonials)} testimonials with correct structure")
        else:
            print("SUCCESS: Empty testimonials list (no 4+ star reviews with consent)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
