"""
Tests for Public Landing Page features
- Public landing page data API
- Review submission
- Review approval/rejection
- Referral submission
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://lead-routing-1.preview.emergentagent.com')

# Test user ID
TEST_USER_ID = "69975a8b6ff748b1f9da6b57"


class TestPublicLandingPage:
    """Tests for the public landing page API"""
    
    def test_get_landing_page_data(self):
        """Test fetching landing page data for a user"""
        response = requests.get(f"{BASE_URL}/api/p/data/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        assert "store" in data
        assert "testimonials" in data
        
        # Verify user data structure
        user = data["user"]
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "phone" in user
        assert "social_links" in user
        print(f"Landing page data loaded for user: {user['name']}")
    
    def test_get_landing_page_data_invalid_user(self):
        """Test fetching landing page data for invalid user returns 404"""
        response = requests.get(f"{BASE_URL}/api/p/data/invaliduserid123")
        assert response.status_code == 404
        print("Invalid user correctly returns 404")


class TestReviewSubmission:
    """Tests for review submission API"""
    
    def test_submit_review_minimal(self):
        """Test submitting a review with minimal required data"""
        form_data = {
            "customer_name": "TEST_Minimal Reviewer",
            "rating": "5"
        }
        response = requests.post(
            f"{BASE_URL}/api/p/review/{TEST_USER_ID}",
            data=form_data
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] == True
        assert "feedback_id" in result
        print(f"Review submitted with ID: {result['feedback_id']}")
        return result["feedback_id"]
    
    def test_submit_review_full(self):
        """Test submitting a review with all fields"""
        form_data = {
            "customer_name": "TEST_Full Reviewer",
            "rating": "4",
            "text_review": "Great service! Very professional and helpful.",
            "customer_phone": "+15559998888",
            "customer_email": "test_reviewer@example.com"
        }
        response = requests.post(
            f"{BASE_URL}/api/p/review/{TEST_USER_ID}",
            data=form_data
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] == True
        assert "feedback_id" in result
        print(f"Full review submitted with ID: {result['feedback_id']}")
        return result["feedback_id"]
    
    def test_submit_review_invalid_user(self):
        """Test submitting review for invalid user returns 404"""
        form_data = {
            "customer_name": "TEST_Invalid",
            "rating": "5"
        }
        response = requests.post(
            f"{BASE_URL}/api/p/review/invaliduserid123",
            data=form_data
        )
        assert response.status_code == 404
        print("Review submission for invalid user correctly returns 404")


class TestReviewApproval:
    """Tests for review approval workflow"""
    
    def test_get_pending_reviews(self):
        """Test fetching pending reviews for a user"""
        response = requests.get(f"{BASE_URL}/api/p/reviews/pending/{TEST_USER_ID}")
        assert response.status_code == 200
        
        reviews = response.json()
        assert isinstance(reviews, list)
        print(f"Found {len(reviews)} pending reviews")
    
    def test_approve_review_flow(self):
        """Test the full review approval flow"""
        # First submit a test review
        form_data = {
            "customer_name": "TEST_ApprovalFlow",
            "rating": "5",
            "text_review": "Testing approval flow"
        }
        submit_response = requests.post(
            f"{BASE_URL}/api/p/review/{TEST_USER_ID}",
            data=form_data
        )
        assert submit_response.status_code == 200
        review_id = submit_response.json()["feedback_id"]
        
        # Approve the review
        approve_response = requests.post(f"{BASE_URL}/api/p/reviews/approve/{review_id}")
        assert approve_response.status_code == 200
        
        result = approve_response.json()
        assert result["success"] == True
        print(f"Review {review_id} approved successfully")
    
    def test_reject_review_flow(self):
        """Test the full review rejection flow"""
        # First submit a test review
        form_data = {
            "customer_name": "TEST_RejectFlow",
            "rating": "3",
            "text_review": "Testing rejection flow"
        }
        submit_response = requests.post(
            f"{BASE_URL}/api/p/review/{TEST_USER_ID}",
            data=form_data
        )
        assert submit_response.status_code == 200
        review_id = submit_response.json()["feedback_id"]
        
        # Reject the review
        reject_response = requests.post(f"{BASE_URL}/api/p/reviews/reject/{review_id}")
        assert reject_response.status_code == 200
        
        result = reject_response.json()
        assert result["success"] == True
        print(f"Review {review_id} rejected successfully")
    
    def test_approve_invalid_review(self):
        """Test approving non-existent review returns 404"""
        response = requests.post(f"{BASE_URL}/api/p/reviews/approve/000000000000000000000000")
        assert response.status_code == 404
        print("Approve invalid review correctly returns 404")
    
    def test_reject_invalid_review(self):
        """Test rejecting non-existent review returns 404"""
        response = requests.post(f"{BASE_URL}/api/p/reviews/reject/000000000000000000000000")
        assert response.status_code == 404
        print("Reject invalid review correctly returns 404")


class TestReferralSubmission:
    """Tests for referral submission API"""
    
    def test_submit_referral(self):
        """Test submitting a referral"""
        payload = {
            "referrer_name": "TEST_John Referrer",
            "referrer_phone": "+15551234567",
            "referred_name": "TEST_Alice Friend",
            "referred_phone": "+15559876543",
            "referred_email": "alice_test@example.com",
            "notes": "Interested in new car"
        }
        response = requests.post(
            f"{BASE_URL}/api/p/refer/{TEST_USER_ID}",
            json=payload
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] == True
        assert "referral_id" in result
        print(f"Referral submitted with ID: {result['referral_id']}")
    
    def test_submit_referral_minimal(self):
        """Test submitting a referral with minimal data"""
        payload = {
            "referrer_name": "TEST_Min Referrer",
            "referred_name": "TEST_Min Friend"
        }
        response = requests.post(
            f"{BASE_URL}/api/p/refer/{TEST_USER_ID}",
            json=payload
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] == True
        print("Minimal referral submitted successfully")
    
    def test_submit_referral_invalid_user(self):
        """Test submitting referral for invalid user returns 404"""
        payload = {
            "referrer_name": "TEST_Invalid",
            "referred_name": "TEST_Friend"
        }
        response = requests.post(
            f"{BASE_URL}/api/p/refer/invaliduserid123",
            json=payload
        )
        assert response.status_code == 404
        print("Referral submission for invalid user correctly returns 404")
    
    def test_get_referrals(self):
        """Test fetching referrals for a user"""
        response = requests.get(f"{BASE_URL}/api/p/referrals/{TEST_USER_ID}")
        assert response.status_code == 200
        
        referrals = response.json()
        assert isinstance(referrals, list)
        print(f"Found {len(referrals)} referrals")
        
        if referrals:
            # Verify referral data structure
            ref = referrals[0]
            assert "id" in ref
            assert "referrer_name" in ref
            assert "referred_name" in ref


class TestApprovedReviewsDisplay:
    """Tests for approved reviews display on landing page"""
    
    def test_approved_reviews_appear_in_testimonials(self):
        """Verify approved reviews appear in landing page testimonials"""
        response = requests.get(f"{BASE_URL}/api/p/data/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        testimonials = data.get("testimonials", [])
        
        # Just verify structure - reviews need 4+ rating to appear
        for t in testimonials:
            assert "id" in t
            assert "customer_name" in t
            assert "rating" in t
            assert t["rating"] >= 4  # Only 4+ star reviews shown
        print(f"Found {len(testimonials)} approved testimonials with 4+ rating")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_reviews(self):
        """Clean up test reviews by rejecting them"""
        response = requests.get(f"{BASE_URL}/api/p/reviews/pending/{TEST_USER_ID}")
        reviews = response.json()
        
        cleaned = 0
        for review in reviews:
            if "TEST_" in review.get("customer_name", ""):
                reject_resp = requests.post(f"{BASE_URL}/api/p/reviews/reject/{review['id']}")
                if reject_resp.status_code == 200:
                    cleaned += 1
        
        print(f"Cleaned up {cleaned} test reviews")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
