"""
Test Profile API - My Profile page features
Tests: GET profile, PUT profile, POST generate-bio
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://birthday-campaigns.preview.emergentagent.com")
TEST_USER_ID = "69963e636d8473ba25695a34"


class TestProfileGet:
    """Test GET /api/profile/{user_id} endpoint"""
    
    def test_get_profile_success(self):
        """Test getting profile data successfully"""
        response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "user" in data
        assert "store" in data
        assert "testimonials" in data
        assert "all_reviews" in data
        
        user = data["user"]
        # Verify user fields
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "phone" in user
        assert "title" in user
        assert "bio" in user
        assert "hobbies" in user
        assert "family_info" in user
        assert "hometown" in user
        assert "years_experience" in user
        assert "fun_facts" in user
        assert "personal_motto" in user
        assert "social_links" in user
        
        # Verify specific values
        assert user["id"] == TEST_USER_ID
        assert user["email"] == "superadmin@mvpline.com"
        assert isinstance(user["hobbies"], list)
        assert isinstance(user["fun_facts"], list)
        assert isinstance(user["social_links"], dict)
        
        print(f"Profile GET successful - Name: {user['name']}, Bio length: {len(user.get('bio', ''))}")
    
    def test_get_profile_invalid_id(self):
        """Test getting profile with invalid user ID"""
        response = requests.get(f"{BASE_URL}/api/profile/invalid_id_123")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print("Invalid ID returns 404 as expected")
    
    def test_get_profile_nonexistent_user(self):
        """Test getting profile for non-existent user"""
        response = requests.get(f"{BASE_URL}/api/profile/000000000000000000000000")
        
        assert response.status_code == 404
        print("Non-existent user returns 404 as expected")


class TestProfileUpdate:
    """Test PUT /api/profile/{user_id} endpoint"""
    
    def test_update_basic_info(self):
        """Test updating basic profile info (name, phone, title)"""
        # Get current profile
        get_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        original_data = get_response.json()["user"]
        
        # Update basic fields
        update_data = {
            "name": "John Smith",
            "phone": "(801) 555-7890",
            "title": "Senior Sales Consultant"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify changes persisted
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        updated_user = verify_response.json()["user"]
        
        assert updated_user["name"] == update_data["name"]
        assert updated_user["phone"] == update_data["phone"]
        assert updated_user["title"] == update_data["title"]
        
        print(f"Basic info update successful - Name: {updated_user['name']}")
    
    def test_update_years_experience(self):
        """Test updating years of experience"""
        update_data = {
            "years_experience": "8 years"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        user = verify_response.json()["user"]
        assert user["years_experience"] == "8 years"
        
        print("Years experience update verified")
    
    def test_update_personal_story(self):
        """Test updating personal story fields (hometown, family, motto)"""
        update_data = {
            "hometown": "Salt Lake City, Utah",
            "family_info": "Married with two kids",
            "personal_motto": "Treat every customer like family"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        user = verify_response.json()["user"]
        
        assert user["hometown"] == update_data["hometown"]
        assert user["family_info"] == update_data["family_info"]
        assert user["personal_motto"] == update_data["personal_motto"]
        
        print("Personal story fields update verified")
    
    def test_update_hobbies(self):
        """Test updating hobbies list"""
        update_data = {
            "hobbies": ["golf", "BBQ", "fishing"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        user = verify_response.json()["user"]
        
        assert isinstance(user["hobbies"], list)
        assert "golf" in user["hobbies"]
        assert "BBQ" in user["hobbies"]
        assert "fishing" in user["hobbies"]
        
        print(f"Hobbies update verified - {user['hobbies']}")
    
    def test_update_fun_facts(self):
        """Test updating fun facts list"""
        update_data = {
            "fun_facts": ["Can name every Honda model since 1990"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        user = verify_response.json()["user"]
        
        assert isinstance(user["fun_facts"], list)
        assert len(user["fun_facts"]) >= 1
        
        print(f"Fun facts update verified - {user['fun_facts']}")
    
    def test_update_social_links(self):
        """Test updating social media links"""
        update_data = {
            "social_links": {
                "facebook": "https://facebook.com/johnsmith",
                "instagram": "https://instagram.com/johnsmith_sales",
                "linkedin": "https://linkedin.com/in/johnsmith"
            }
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        user = verify_response.json()["user"]
        
        assert isinstance(user["social_links"], dict)
        assert user["social_links"].get("facebook") == "https://facebook.com/johnsmith"
        assert user["social_links"].get("instagram") == "https://instagram.com/johnsmith_sales"
        
        print(f"Social links update verified - {list(user['social_links'].keys())}")
    
    def test_update_bio_directly(self):
        """Test updating bio text directly"""
        test_bio = "Test bio text for verification"
        update_data = {
            "bio": test_bio
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
        user = verify_response.json()["user"]
        
        assert user["bio"] == test_bio
        
        print("Direct bio update verified")


class TestAIBioGeneration:
    """Test POST /api/profile/{user_id}/generate-bio endpoint"""
    
    def test_generate_bio_success(self):
        """Test AI bio generation with full profile data"""
        bio_data = {
            "name": "John Smith",
            "title": "Senior Sales Consultant",
            "hobbies": ["golf", "BBQ", "fishing"],
            "family_info": "Married with two kids",
            "hometown": "Salt Lake City, Utah",
            "years_experience": "8 years",
            "fun_facts": ["Can name every Honda model since 1990"],
            "personal_motto": "Treat every customer like family"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}/generate-bio",
            json=bio_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "bio" in data
        assert len(data["bio"]) > 50  # Bio should be substantial
        
        # Check that bio mentions key details
        bio_lower = data["bio"].lower()
        # At least some of these should be mentioned
        mentions_count = sum([
            "john" in bio_lower,
            "salt lake" in bio_lower or "utah" in bio_lower,
            "8 year" in bio_lower or "eight year" in bio_lower,
            "golf" in bio_lower or "bbq" in bio_lower or "fishing" in bio_lower,
            "family" in bio_lower or "kids" in bio_lower
        ])
        
        assert mentions_count >= 2, f"Bio should mention personal details. Got: {data['bio']}"
        
        print(f"AI bio generated successfully: {data['bio'][:100]}...")
    
    def test_generate_bio_minimal_info(self):
        """Test AI bio generation with minimal info"""
        bio_data = {
            "name": "John Smith",
            "years_experience": "8 years"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}/generate-bio",
            json=bio_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "bio" in data
        assert len(data["bio"]) > 20
        
        print(f"Bio with minimal info: {data['bio']}")
    
    def test_generate_bio_empty_data_uses_db(self):
        """Test that bio generation falls back to user data from DB when no personal info provided"""
        bio_data = {}
        
        response = requests.post(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}/generate-bio",
            json=bio_data
        )
        
        # API fetches user data from DB and uses that for bio generation
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "bio" in data
        assert len(data["bio"]) > 20  # Should still generate a bio
        
        print(f"Empty data correctly uses DB user info: {data['bio'][:50]}...")
    
    def test_generate_bio_invalid_user(self):
        """Test bio generation for non-existent user"""
        bio_data = {
            "name": "Test User",
            "years_experience": "5 years"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/profile/000000000000000000000000/generate-bio",
            json=bio_data
        )
        
        assert response.status_code == 404
        print("Non-existent user returns 404 as expected")


class TestDigitalCardIntegration:
    """Test that profile data flows to digital card correctly"""
    
    def test_card_shows_bio(self):
        """Test that digital card endpoint shows bio from profile"""
        # First, ensure we have a bio
        bio_data = {
            "name": "John Smith",
            "title": "Senior Sales Consultant",
            "hobbies": ["golf"],
            "hometown": "Salt Lake City"
        }
        
        gen_response = requests.post(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}/generate-bio",
            json=bio_data
        )
        
        assert gen_response.status_code == 200
        generated_bio = gen_response.json()["bio"]
        
        # Now save the bio
        save_response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json={"bio": generated_bio}
        )
        assert save_response.status_code == 200
        
        # Check card data endpoint
        card_response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        
        assert card_response.status_code == 200
        card_data = card_response.json()
        
        # Verify bio is in card data
        assert "user" in card_data
        assert "bio" in card_data["user"]
        assert card_data["user"]["bio"] == generated_bio
        
        print(f"Card shows bio correctly: {card_data['user']['bio'][:50]}...")
    
    def test_card_shows_social_links(self):
        """Test that digital card shows social links from profile"""
        # Update social links
        social_links = {
            "facebook": "https://facebook.com/test",
            "instagram": "https://instagram.com/test"
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/profile/{TEST_USER_ID}",
            json={"social_links": social_links}
        )
        assert update_response.status_code == 200
        
        # Check card data
        card_response = requests.get(f"{BASE_URL}/api/card/data/{TEST_USER_ID}")
        card_data = card_response.json()
        
        assert "social_links" in card_data["user"]
        assert card_data["user"]["social_links"]["facebook"] == "https://facebook.com/test"
        
        print("Card shows social links correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
