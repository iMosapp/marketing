"""
Test Help Center AI API - Tests the POST /api/help-center/ask endpoint
which uses GPT-5.2 via EMERGENT_LLM_KEY to answer user questions about iMOs.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHelpCenterAPI:
    """Help Center AI endpoint tests"""
    
    def test_help_center_ask_broadcast_question(self):
        """Test asking how to send a broadcast"""
        response = requests.post(
            f"{BASE_URL}/api/help-center/ask",
            json={"question": "How do I send a broadcast?"},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "answer" in data, "Response should contain 'answer' field"
        assert "source" in data, "Response should contain 'source' field"
        assert data["source"] == "ai", f"Expected source='ai', got {data['source']}"
        assert len(data["answer"]) > 50, "AI answer should be substantive"
        # The answer should mention broadcast-related steps
        answer_lower = data["answer"].lower()
        assert "broadcast" in answer_lower or "campaign" in answer_lower, "Answer should be relevant to broadcast"
    
    def test_help_center_ask_branding_question(self):
        """Test asking about branding/logo"""
        response = requests.post(
            f"{BASE_URL}/api/help-center/ask",
            json={"question": "How do I change my store logo?"},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data
        assert data["source"] == "ai"
        # Answer should mention store profile or logo
        answer_lower = data["answer"].lower()
        assert "logo" in answer_lower or "store profile" in answer_lower or "branding" in answer_lower
    
    def test_help_center_ask_campaign_question(self):
        """Test asking about campaigns"""
        response = requests.post(
            f"{BASE_URL}/api/help-center/ask",
            json={"question": "How do I create an SMS campaign?"},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data
        assert data["source"] == "ai"
        answer_lower = data["answer"].lower()
        assert "campaign" in answer_lower or "sms" in answer_lower
    
    def test_help_center_ask_with_user_id(self):
        """Test asking with a user_id for session tracking"""
        response = requests.post(
            f"{BASE_URL}/api/help-center/ask",
            json={
                "question": "What is the leaderboard?",
                "user_id": "test_user_123"
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data
        assert data["source"] == "ai"
    
    def test_help_center_ask_empty_question(self):
        """Test with empty question - should still return a response"""
        response = requests.post(
            f"{BASE_URL}/api/help-center/ask",
            json={"question": ""},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        # API should handle gracefully
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
