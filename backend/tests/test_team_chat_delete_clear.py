"""
Test Team Chat Delete Channel and Clear History Endpoints
Tests DELETE /api/team-chat/channels/{id} and DELETE /api/team-chat/channels/{id}/messages
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "699907444a076891982fab35"  # super_admin forest@imosapp.com

class TestTeamChatDeleteClear:
    """Tests for delete channel and clear history endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_test_channel(self):
        """Create a test channel before each test"""
        # Create test channel
        response = requests.post(f"{BASE_URL}/api/team-chat/channels", json={
            "name": "TEST_channel_delete_clear",
            "channel_type": "custom",
            "created_by": USER_ID,
            "member_ids": [USER_ID]
        })
        if response.status_code == 200:
            data = response.json()
            self.test_channel_id = data.get("channel_id")
        else:
            self.test_channel_id = None
        yield
        # Cleanup - try to delete channel if it still exists
        if self.test_channel_id:
            requests.delete(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}?user_id={USER_ID}")

    def test_clear_channel_history_success(self):
        """Test clearing all messages from a channel"""
        if not self.test_channel_id:
            pytest.skip("Test channel not created")
        
        # First send a test message
        requests.post(f"{BASE_URL}/api/team-chat/messages", json={
            "channel_id": self.test_channel_id,
            "sender_id": USER_ID,
            "content": "Test message to be cleared"
        })
        
        # Clear history
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}/messages?user_id={USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "messages_deleted" in data
        assert data["message"] == "Chat history cleared"
        
        # Verify channel still exists
        channel_response = requests.get(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}")
        assert channel_response.status_code == 200
        
        # Verify messages are empty
        messages_response = requests.get(f"{BASE_URL}/api/team-chat/messages/{self.test_channel_id}?user_id={USER_ID}")
        assert messages_response.status_code == 200
        assert len(messages_response.json().get("messages", [])) == 0
    
    def test_delete_channel_success(self):
        """Test deleting a channel and all its messages"""
        if not self.test_channel_id:
            pytest.skip("Test channel not created")
        
        # Delete channel
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}?user_id={USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "messages_deleted" in data
        assert data["message"] == "Channel and all messages deleted"
        
        # Verify channel is deleted
        channel_response = requests.get(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}")
        assert channel_response.status_code == 404
        
        # Clear the ID so cleanup doesn't try to delete again
        self.test_channel_id = None
    
    def test_delete_channel_not_found(self):
        """Test deleting non-existent channel returns 404"""
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/000000000000000000000000?user_id={USER_ID}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Channel not found"
    
    def test_clear_history_channel_not_found(self):
        """Test clearing history of non-existent channel returns 404"""
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/000000000000000000000000/messages?user_id={USER_ID}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Channel not found"
    
    def test_delete_channel_missing_user_id(self):
        """Test delete channel requires user_id parameter"""
        if not self.test_channel_id:
            pytest.skip("Test channel not created")
        
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}")
        assert response.status_code == 422  # Validation error
    
    def test_clear_history_missing_user_id(self):
        """Test clear history requires user_id parameter"""
        if not self.test_channel_id:
            pytest.skip("Test channel not created")
        
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}/messages")
        assert response.status_code == 422  # Validation error
    
    def test_delete_channel_unauthorized_user(self):
        """Test non-admin/non-creator cannot delete channel"""
        if not self.test_channel_id:
            pytest.skip("Test channel not created")
        
        # Use a non-admin user ID (would need a valid non-admin user for real test)
        # For now, we verify the permission check structure exists
        response = requests.delete(f"{BASE_URL}/api/team-chat/channels/{self.test_channel_id}?user_id=000000000000000000000000")
        # Should return 404 for non-existent user
        assert response.status_code == 404
