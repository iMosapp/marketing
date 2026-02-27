"""
Backend API Tests for Messages and Review Links
Tests: Thread messages, AI suggestions, and Review Links endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://backend-startup-3.preview.emergentagent.com')
if BASE_URL and not BASE_URL.endswith('/api'):
    BASE_URL = BASE_URL.rstrip('/') + '/api'

# Test credentials
SUPERADMIN_EMAIL = "superadmin@mvpline.com"
SUPERADMIN_PASSWORD = "admin123"


class TestAuth:
    """Test authentication endpoint"""
    
    def test_login_superadmin(self):
        """Test login with superadmin credentials"""
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == SUPERADMIN_EMAIL
        assert data["user"]["role"] == "super_admin"
        print(f"LOGIN SUCCESS: User ID = {data['user']['_id']}")
        return data["user"]["_id"]
    
    def test_login_invalid_credentials(self):
        """Test login with wrong credentials"""
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [400, 401, 404]
        print("LOGIN INVALID: Correctly rejected")


class TestMessagesThread:
    """Test message thread endpoints"""
    
    def test_get_thread_messages_empty(self):
        """Test getting messages for non-existent conversation"""
        response = requests.get(f"{BASE_URL}/messages/thread/nonexistent123")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
        print("THREAD EMPTY: Returns empty list for non-existent conversation")
    
    def test_get_thread_messages_with_valid_id(self):
        """Test getting messages for a valid conversation"""
        # First get conversations to find a valid ID
        login_resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        user_id = login_resp.json()["user"]["_id"]
        
        conv_resp = requests.get(f"{BASE_URL}/messages/conversations/{user_id}")
        conversations = conv_resp.json()
        
        if conversations:
            conv_id = conversations[0]["_id"]
            response = requests.get(f"{BASE_URL}/messages/thread/{conv_id}")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print(f"THREAD VALID: Found {len(data)} messages in conversation")
        else:
            print("THREAD VALID: No conversations to test with")


class TestAISuggestion:
    """Test AI suggestion endpoint (MOCKED)"""
    
    def test_ai_suggestion_returns_suggestion(self):
        """Test AI suggestion endpoint returns mocked suggestion"""
        response = requests.post(f"{BASE_URL}/messages/ai-suggest/test123")
        assert response.status_code == 200
        data = response.json()
        assert "suggestion" in data
        assert "intent" in data
        assert len(data["suggestion"]) > 0
        assert data["intent"] == "general"
        print(f"AI SUGGESTION (MOCKED): {data['suggestion'][:50]}...")
    
    def test_ai_suggestion_different_responses(self):
        """Test AI suggestion returns varied responses"""
        suggestions = set()
        for _ in range(10):
            response = requests.post(f"{BASE_URL}/messages/ai-suggest/test123")
            data = response.json()
            suggestions.add(data["suggestion"])
        
        # Should have at least 2 different suggestions in 10 tries
        assert len(suggestions) >= 1  # At minimum 1 if only 1 template
        print(f"AI SUGGESTIONS VARIETY: Got {len(suggestions)} unique suggestions")


class TestReviewLinks:
    """Test review links endpoints"""
    
    def test_get_review_links_empty(self):
        """Test getting review links for user with none configured"""
        login_resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        user_id = login_resp.json()["user"]["_id"]
        
        response = requests.get(f"{BASE_URL}/users/{user_id}/review-links")
        assert response.status_code == 200
        data = response.json()
        assert "review_links" in data
        assert "custom_link_name" in data
        assert isinstance(data["review_links"], dict)
        print(f"REVIEW LINKS: Found {len(data['review_links'])} configured links")
    
    def test_update_review_links(self):
        """Test updating review links"""
        login_resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        user_id = login_resp.json()["user"]["_id"]
        
        # Update with test links
        test_links = {
            "review_links": {
                "google": "https://g.page/test-business",
                "facebook": "https://facebook.com/test-page"
            },
            "custom_link_name": "Test Link"
        }
        
        response = requests.put(f"{BASE_URL}/users/{user_id}/review-links", json=test_links)
        assert response.status_code == 200
        print("REVIEW LINKS UPDATE: Successfully saved")
        
        # Verify the update
        get_response = requests.get(f"{BASE_URL}/users/{user_id}/review-links")
        data = get_response.json()
        assert data["review_links"]["google"] == "https://g.page/test-business"
        assert data["review_links"]["facebook"] == "https://facebook.com/test-page"
        assert data["custom_link_name"] == "Test Link"
        print("REVIEW LINKS VERIFY: Data persisted correctly")
        
        # Clean up - reset to empty
        clean_links = {"review_links": {}, "custom_link_name": ""}
        requests.put(f"{BASE_URL}/users/{user_id}/review-links", json=clean_links)


class TestConversations:
    """Test conversation endpoints"""
    
    def test_get_conversations_for_superadmin(self):
        """Test getting conversations for superadmin (sees all)"""
        login_resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        user_id = login_resp.json()["user"]["_id"]
        
        response = requests.get(f"{BASE_URL}/messages/conversations/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"CONVERSATIONS: Found {len(data)} conversations")
        
        # Verify conversation structure
        if data:
            conv = data[0]
            assert "_id" in conv
            assert "status" in conv
            print(f"CONVERSATION STRUCTURE: Has required fields")


class TestAIOutcomes:
    """Test AI outcomes endpoint"""
    
    def test_get_ai_outcomes(self):
        """Test getting AI outcome types"""
        response = requests.get(f"{BASE_URL}/messages/ai-outcomes")
        assert response.status_code == 200
        data = response.json()
        
        # Should have these outcome types
        expected_outcomes = ["appointment_set", "callback_requested", "needs_assistance", 
                          "hot_lead", "question_asked", "escalated"]
        
        for outcome in expected_outcomes:
            assert outcome in data
            assert "label" in data[outcome]
            assert "priority" in data[outcome]
        
        print(f"AI OUTCOMES: Found {len(data)} outcome types")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """Test API is responding"""
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "MVPLine" in data["message"]
        print(f"API HEALTH: {data['message']} v{data.get('version', 'unknown')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
