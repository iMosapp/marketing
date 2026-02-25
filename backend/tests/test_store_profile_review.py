"""
Store Profile and Public Review Page API Tests
Tests for:
- GET /admin/stores/{store_id} - Get store profile
- PUT /admin/stores/{store_id} - Update store profile with business hours
- GET /review/page/{store_slug} - Public review page data
- POST /review/submit/{store_slug} - Feedback submission
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://cascading-invites.preview.emergentagent.com')

# Test data
TEST_STORE_ID = "699637981b07c23426a5324a"
TEST_STORE_SLUG = "ken-garff-honda-downtown"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestStoreProfile:
    """Store Profile API Tests"""
    
    def test_get_store_profile_success(self, api_client):
        """GET /admin/stores/{store_id} - Success"""
        response = api_client.get(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate store data structure
        assert "_id" in data
        assert data["_id"] == TEST_STORE_ID
        assert "name" in data
        assert data["name"] == "Ken Garff Honda Downtown"
        assert "slug" in data
        assert data["slug"] == TEST_STORE_SLUG
        
        # Validate business hours structure
        assert "business_hours" in data
        hours = data["business_hours"]
        assert "monday" in hours
        assert "saturday" in hours
        assert "sunday" in hours
        
        # Validate Monday hours
        if hours.get("monday"):
            assert "open" in hours["monday"]
            assert "close" in hours["monday"]
        
        # Validate Sunday is closed (null)
        assert hours.get("sunday") is None
        
        print(f"Store profile loaded successfully: {data['name']}")
    
    def test_get_store_profile_not_found(self, api_client):
        """GET /admin/stores/{store_id} - Not Found"""
        fake_id = "000000000000000000000000"
        response = api_client.get(f"{BASE_URL}/api/admin/stores/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"Store not found handled correctly: {data['detail']}")
    
    def test_update_store_business_hours(self, api_client):
        """PUT /admin/stores/{store_id} - Update business hours"""
        update_data = {
            "business_hours": {
                "monday": {"open": "08:00", "close": "19:00"},
                "tuesday": {"open": "08:00", "close": "19:00"},
                "wednesday": {"open": "08:00", "close": "19:00"},
                "thursday": {"open": "08:00", "close": "19:00"},
                "friday": {"open": "08:00", "close": "19:00"},
                "saturday": {"open": "09:00", "close": "18:00"},
                "sunday": None
            }
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Store updated"
        
        # Verify update persisted by fetching store
        get_response = api_client.get(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}")
        assert get_response.status_code == 200
        store_data = get_response.json()
        
        # Verify Monday hours updated
        assert store_data["business_hours"]["monday"]["open"] == "08:00"
        assert store_data["business_hours"]["monday"]["close"] == "19:00"
        
        print("Business hours updated and verified successfully")
        
        # Restore original hours
        restore_data = {
            "business_hours": {
                "monday": {"open": "09:00", "close": "18:00"},
                "tuesday": {"open": "09:00", "close": "18:00"},
                "wednesday": {"open": "09:00", "close": "18:00"},
                "thursday": {"open": "09:00", "close": "18:00"},
                "friday": {"open": "09:00", "close": "18:00"},
                "saturday": {"open": "10:00", "close": "17:00"},
                "sunday": None
            }
        }
        api_client.put(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}", json=restore_data)
    
    def test_update_store_social_links(self, api_client):
        """PUT /admin/stores/{store_id} - Update social links"""
        update_data = {
            "social_links": {
                "facebook": "https://facebook.com/teststore",
                "instagram": "https://instagram.com/teststore",
                "twitter": "https://twitter.com/teststore"
            }
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}",
            json=update_data
        )
        
        assert response.status_code == 200
        
        # Verify update
        get_response = api_client.get(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}")
        assert get_response.status_code == 200
        store_data = get_response.json()
        
        assert store_data["social_links"]["twitter"] == "https://twitter.com/teststore"
        
        print("Social links updated successfully")
        
        # Restore original social links
        restore_data = {
            "social_links": {
                "facebook": "https://facebook.com/kengarffhonda",
                "instagram": "https://instagram.com/kengarffhonda"
            }
        }
        api_client.put(f"{BASE_URL}/api/admin/stores/{TEST_STORE_ID}", json=restore_data)


class TestPublicReviewPage:
    """Public Review Page API Tests"""
    
    def test_get_review_page_data_success(self, api_client):
        """GET /review/page/{store_slug} - Success"""
        response = api_client.get(f"{BASE_URL}/api/review/page/{TEST_STORE_SLUG}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate store data
        assert "store" in data
        store = data["store"]
        assert "id" in store
        assert "name" in store
        assert store["name"] == "Ken Garff Honda Downtown"
        assert "phone" in store
        assert "address" in store
        assert "city" in store
        assert "business_hours" in store
        assert "timezone" in store
        
        # Validate review links
        assert "review_links" in data
        review_links = data["review_links"]
        assert "google" in review_links
        assert "yelp" in review_links
        
        # Validate social links
        assert "social_links" in data
        social_links = data["social_links"]
        assert "facebook" in social_links
        assert "instagram" in social_links
        
        # Validate salesperson is null when not provided
        assert data.get("salesperson") is None
        
        print(f"Review page data loaded for: {store['name']}")
    
    def test_get_review_page_not_found(self, api_client):
        """GET /review/page/{store_slug} - Not Found"""
        response = api_client.get(f"{BASE_URL}/api/review/page/non-existent-store")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"Store not found handled correctly: {data['detail']}")
    
    def test_get_review_page_with_salesperson(self, api_client):
        """GET /review/page/{store_slug}?sp={salesperson_id} - With salesperson"""
        # Using a dummy salesperson ID (won't match actual user but should not error)
        response = api_client.get(f"{BASE_URL}/api/review/page/{TEST_STORE_SLUG}?sp=699637981b07c23426a5324a")
        
        assert response.status_code == 200
        data = response.json()
        
        # Salesperson info should be included (but name may be empty if not found)
        assert "salesperson" in data
        if data["salesperson"]:
            assert "id" in data["salesperson"]
        
        print("Review page with salesperson param works correctly")


class TestFeedbackSubmission:
    """Feedback Submission API Tests"""
    
    def test_submit_feedback_success(self, api_client):
        """POST /review/submit/{store_slug} - Success"""
        unique_name = f"Test Customer {uuid.uuid4().hex[:8]}"
        feedback_data = {
            "customer_name": unique_name,
            "customer_email": "test@example.com",
            "rating": 5,
            "text_review": "Excellent service! Very professional and helpful.",
            "photo_consent": True
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/review/submit/{TEST_STORE_SLUG}",
            json=feedback_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "feedback_id" in data
        assert "message" in data
        assert data["message"] == "Thank you for your feedback!"
        
        print(f"Feedback submitted successfully, ID: {data['feedback_id']}")
    
    def test_submit_feedback_minimal(self, api_client):
        """POST /review/submit/{store_slug} - Minimal data"""
        feedback_data = {
            "customer_name": "Anonymous Customer",
            "rating": 4
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/review/submit/{TEST_STORE_SLUG}",
            json=feedback_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        print("Minimal feedback submitted successfully")
    
    def test_submit_feedback_with_platform_clicked(self, api_client):
        """POST /review/submit/{store_slug} - Track platform click"""
        feedback_data = {
            "customer_name": "Link Click",
            "platform_clicked": "google"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/review/submit/{TEST_STORE_SLUG}",
            json=feedback_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        print("Platform click tracked successfully")
    
    def test_submit_feedback_store_not_found(self, api_client):
        """POST /review/submit/{store_slug} - Store not found"""
        feedback_data = {
            "customer_name": "Test",
            "rating": 5
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/review/submit/non-existent-store",
            json=feedback_data
        )
        
        assert response.status_code == 404
        print("Store not found handled correctly for feedback submission")


class TestBusinessHoursCheck:
    """Business Hours Check API Tests"""
    
    def test_check_hours_success(self, api_client):
        """GET /review/check-hours/{store_slug} - Success"""
        response = api_client.get(f"{BASE_URL}/api/review/check-hours/{TEST_STORE_SLUG}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "is_open" in data
        assert isinstance(data["is_open"], bool)
        assert "day" in data
        assert "timezone" in data
        
        if data.get("today_hours"):
            assert "open" in data["today_hours"]
            assert "close" in data["today_hours"]
        
        print(f"Store is {'open' if data['is_open'] else 'closed'} - Day: {data['day']}")
    
    def test_check_hours_not_found(self, api_client):
        """GET /review/check-hours/{store_slug} - Not Found"""
        response = api_client.get(f"{BASE_URL}/api/review/check-hours/non-existent-store")
        
        assert response.status_code == 404
        print("Store not found handled correctly for hours check")


class TestStoreFeedbackAdmin:
    """Store Feedback Admin API Tests"""
    
    def test_get_store_feedback(self, api_client):
        """GET /review/feedback/{store_id} - Get all feedback for a store"""
        response = api_client.get(f"{BASE_URL}/api/review/feedback/{TEST_STORE_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return an array
        assert isinstance(data, list)
        
        # If there's feedback, validate structure
        if len(data) > 0:
            feedback = data[0]
            assert "_id" in feedback
            assert "store_id" in feedback
            assert "customer_name" in feedback
            assert "created_at" in feedback
        
        print(f"Retrieved {len(data)} feedback entries for store")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
