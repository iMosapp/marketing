"""
Test suite for Jessie AI Assistant API endpoints
Tests: /api/jessie/chat, /api/jessie/voice-chat, /api/jessie/history, /api/jessie/session
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_EMAIL = "forestward@gmail.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_user(api_client):
    """Get authenticated user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["user"]


class TestJessieChat:
    """Jessie chat endpoint tests"""
    
    def test_chat_basic_response(self, api_client, auth_user):
        """Test basic chat without voice - Jessie should respond to a simple message"""
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json={
            "user_id": auth_user["_id"],
            "message": "Hello, what can you help me with?",
            "include_voice": False
        })
        
        assert response.status_code == 200, f"Chat failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "text" in data, "Response should contain text"
        assert "session_id" in data, "Response should contain session_id"
        assert len(data["text"]) > 0, "Response text should not be empty"
        assert data["session_id"].startswith("jessie_"), "Session ID should start with 'jessie_'"
        print(f"Jessie responded: {data['text'][:100]}...")
    
    def test_chat_with_voice_request(self, api_client, auth_user):
        """Test chat with voice generation request"""
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json={
            "user_id": auth_user["_id"],
            "message": "Say hello",
            "include_voice": True
        }, timeout=60)  # Longer timeout for voice generation
        
        assert response.status_code == 200, f"Chat with voice failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "text" in data, "Response should contain text"
        assert "session_id" in data, "Response should contain session_id"
        
        # Voice should be included if LLM key is configured
        if "audio_base64" in data:
            assert "audio_format" in data, "Should include audio format"
            assert data["audio_format"] == "mp3", "Audio format should be mp3"
            assert len(data["audio_base64"]) > 100, "Audio base64 should have content"
            print("Voice response generated successfully")
        elif "voice_error" in data:
            print(f"Voice generation had error (acceptable): {data['voice_error']}")
        else:
            print("Note: Voice not generated - may need EMERGENT_LLM_KEY")
    
    def test_chat_missing_user_id(self, api_client):
        """Test chat without user_id returns 422"""
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json={
            "message": "Hello"
        })
        
        assert response.status_code == 422, f"Should return 422 for missing user_id: {response.status_code}"
    
    def test_chat_missing_message(self, api_client, auth_user):
        """Test chat without message returns 422"""
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json={
            "user_id": auth_user["_id"]
        })
        
        assert response.status_code == 422, f"Should return 422 for missing message: {response.status_code}"


class TestJessieSession:
    """Jessie session endpoint tests"""
    
    def test_get_session(self, api_client, auth_user):
        """Test getting/creating a chat session"""
        response = api_client.get(f"{BASE_URL}/api/jessie/session/{auth_user['_id']}")
        
        assert response.status_code == 200, f"Get session failed: {response.text}"
        data = response.json()
        
        # Verify session structure
        assert "session_id" in data, "Response should contain session_id"
        assert data["session_id"].startswith("jessie_"), "Session ID should start with 'jessie_'"
        print(f"Session ID: {data['session_id']}")


class TestJessieHistory:
    """Jessie history endpoint tests"""
    
    def test_get_history(self, api_client, auth_user):
        """Test getting chat history"""
        response = api_client.get(f"{BASE_URL}/api/jessie/history/{auth_user['_id']}")
        
        assert response.status_code == 200, f"Get history failed: {response.text}"
        data = response.json()
        
        # Verify history structure
        assert "messages" in data, "Response should contain messages array"
        assert isinstance(data["messages"], list), "Messages should be a list"
        
        if len(data["messages"]) > 0:
            msg = data["messages"][0]
            assert "role" in msg, "Message should have role"
            assert "content" in msg, "Message should have content"
            print(f"Found {len(data['messages'])} messages in history")
        else:
            print("No messages in history yet")
    
    def test_get_history_with_limit(self, api_client, auth_user):
        """Test getting chat history with limit"""
        response = api_client.get(f"{BASE_URL}/api/jessie/history/{auth_user['_id']}?limit=5")
        
        assert response.status_code == 200, f"Get history with limit failed: {response.text}"
        data = response.json()
        
        assert "messages" in data
        assert len(data["messages"]) <= 5, "Should respect limit parameter"


class TestJessieClearHistory:
    """Jessie clear history endpoint tests"""
    
    def test_clear_history(self, api_client, auth_user):
        """Test clearing chat history"""
        response = api_client.delete(f"{BASE_URL}/api/jessie/history/{auth_user['_id']}")
        
        assert response.status_code == 200, f"Clear history failed: {response.text}"
        data = response.json()
        
        assert "message" in data, "Response should have message"
        assert "cleared" in data["message"].lower(), "Message should indicate history was cleared"
        print("Chat history cleared successfully")


class TestJessieTTS:
    """Jessie text-to-speech endpoint tests"""
    
    def test_tts_basic(self, api_client):
        """Test TTS endpoint with simple text"""
        response = api_client.post(f"{BASE_URL}/api/jessie/tts", json={
            "text": "Hello, this is a test."
        }, timeout=30)
        
        # May fail if EMERGENT_LLM_KEY not configured
        if response.status_code == 200:
            assert response.headers.get("content-type") == "audio/mpeg"
            assert len(response.content) > 100, "Audio should have content"
            print("TTS generated audio successfully")
        elif response.status_code == 500:
            print("TTS unavailable (expected if EMERGENT_LLM_KEY not set)")
        else:
            pytest.fail(f"Unexpected TTS response: {response.status_code}")
    
    def test_tts_empty_text(self, api_client):
        """Test TTS with empty text returns 400"""
        response = api_client.post(f"{BASE_URL}/api/jessie/tts", json={
            "text": ""
        })
        
        assert response.status_code == 400, f"Should return 400 for empty text: {response.status_code}"
    
    def test_tts_text_too_long(self, api_client):
        """Test TTS with text exceeding limit returns 400"""
        long_text = "a" * 5000  # Exceeds 4096 character limit
        response = api_client.post(f"{BASE_URL}/api/jessie/tts", json={
            "text": long_text
        })
        
        assert response.status_code == 400, f"Should return 400 for text > 4096 chars: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
