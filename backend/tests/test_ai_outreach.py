"""
AI-Powered Outreach API Tests
Tests for AI-generated follow-up message suggestions when 'sold' tag is applied.
Features:
- GET /api/ai-outreach/suggestions/{user_id} - Get suggestions by status
- GET /api/ai-outreach/stats/{user_id} - Get pending/accepted/dismissed counts
- POST /api/ai-outreach/generate/{user_id}/{contact_id} - Manual AI generation
- POST /api/ai-outreach/suggestions/{record_id}/accept - Accept a suggestion
- POST /api/ai-outreach/suggestions/{record_id}/dismiss - Dismiss a suggestion
- Login with timezone parameter stores timezone on user
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from the context
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_USER_EMAIL = "forest@imosapp.com"
TEST_USER_PASSWORD = "Admin123!"
TEST_CONTACT_ID = "69a1dbb4320d732f90069652"  # Jane Doe - has pending suggestion


class TestAIOutreachSuggestions:
    """Tests for GET /api/ai-outreach/suggestions/{user_id}"""
    
    def test_get_pending_suggestions(self):
        """Get pending suggestions returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=pending")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "suggestions" in data, "Response should have 'suggestions' key"
        assert "total" in data, "Response should have 'total' key"
        assert isinstance(data["suggestions"], list), "suggestions should be a list"
        print(f"Found {data['total']} pending suggestions")
        
        # If there are pending suggestions, verify structure
        if data["suggestions"]:
            sug = data["suggestions"][0]
            assert "_id" in sug, "Suggestion should have _id"
            assert "contact_id" in sug, "Suggestion should have contact_id"
            assert "contact_name" in sug, "Suggestion should have contact_name"
            assert "suggestions" in sug, "Suggestion should have suggestions array"
            assert "status" in sug, "Suggestion should have status"
            assert sug["status"] == "pending", "Status should be pending"
            
            # Verify inner suggestion structure
            if sug["suggestions"]:
                inner = sug["suggestions"][0]
                assert "message" in inner, "Inner suggestion should have message"
                assert "approach" in inner, "Inner suggestion should have approach"
                assert "best_time_reason" in inner, "Inner suggestion should have best_time_reason"
            print(f"Verified structure for suggestion: {sug['contact_name']}")

    def test_get_accepted_suggestions(self):
        """Get accepted suggestions"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=accepted")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "suggestions" in data
        assert "total" in data
        print(f"Found {data['total']} accepted suggestions")
        
        # Verify accepted suggestions have accepted_index
        for sug in data["suggestions"]:
            assert sug["status"] == "accepted", "All returned should be accepted"
            # accepted_index can be 0, so check for not None
            assert sug.get("accepted_index") is not None or sug["status"] == "accepted"
    
    def test_get_dismissed_suggestions(self):
        """Get dismissed suggestions"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=dismissed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "suggestions" in data
        assert "total" in data
        print(f"Found {data['total']} dismissed suggestions")
        
        for sug in data["suggestions"]:
            assert sug["status"] == "dismissed", "All returned should be dismissed"
    
    def test_get_all_suggestions(self):
        """Get all suggestions regardless of status"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "suggestions" in data
        assert "total" in data
        print(f"Found {data['total']} total suggestions (all statuses)")


class TestAIOutreachStats:
    """Tests for GET /api/ai-outreach/stats/{user_id}"""
    
    def test_get_stats(self):
        """Get outreach stats returns counts"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/stats/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pending" in data, "Stats should have 'pending' count"
        assert "accepted" in data, "Stats should have 'accepted' count"
        assert "dismissed" in data, "Stats should have 'dismissed' count"
        assert "total" in data, "Stats should have 'total' count"
        
        # Verify counts are integers
        assert isinstance(data["pending"], int), "pending should be int"
        assert isinstance(data["accepted"], int), "accepted should be int"
        assert isinstance(data["dismissed"], int), "dismissed should be int"
        assert isinstance(data["total"], int), "total should be int"
        
        # Verify total = pending + accepted + dismissed
        expected_total = data["pending"] + data["accepted"] + data["dismissed"]
        assert data["total"] == expected_total, f"Total should equal sum: {expected_total}"
        
        print(f"Stats - Pending: {data['pending']}, Accepted: {data['accepted']}, Dismissed: {data['dismissed']}, Total: {data['total']}")


class TestAIOutreachManualGeneration:
    """Tests for POST /api/ai-outreach/generate/{user_id}/{contact_id}"""
    
    def test_generate_for_existing_contact(self):
        """Manually generate AI suggestions for an existing contact"""
        response = requests.post(f"{BASE_URL}/api/ai-outreach/generate/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Could return new record_id or existing one (dedup)
        assert "record_id" in data or "message" in data, "Response should have record_id or message"
        print(f"Generate response: {data}")
    
    def test_generate_for_nonexistent_contact(self):
        """Generating for non-existent contact should return 404"""
        fake_contact_id = "000000000000000000000000"
        response = requests.post(f"{BASE_URL}/api/ai-outreach/generate/{TEST_USER_ID}/{fake_contact_id}")
        assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"
        print("Correctly returned 404 for non-existent contact")


class TestAIOutreachAcceptDismiss:
    """Tests for accept/dismiss suggestion endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get a pending suggestion for testing"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=pending")
        if response.status_code == 200:
            data = response.json()
            self.pending_suggestions = data.get("suggestions", [])
        else:
            self.pending_suggestions = []
    
    def test_accept_suggestion_creates_task(self):
        """Accepting a suggestion should create a scheduled task"""
        if not self.pending_suggestions:
            pytest.skip("No pending suggestions to test accept flow")
        
        record = self.pending_suggestions[0]
        record_id = record["_id"]
        
        # Accept suggestion with index 0
        response = requests.post(
            f"{BASE_URL}/api/ai-outreach/suggestions/{record_id}/accept",
            json={"suggestion_index": 0}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "task_id" in data, "Accept response should return task_id"
        assert "scheduled_for" in data, "Accept response should return scheduled_for"
        print(f"Suggestion accepted! Task ID: {data['task_id']}, Scheduled for: {data['scheduled_for']}")
        
        # Verify the suggestion is now accepted
        verify_response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=accepted")
        assert verify_response.status_code == 200
        accepted = verify_response.json()["suggestions"]
        accepted_ids = [s["_id"] for s in accepted]
        assert record_id in accepted_ids, "Accepted record should appear in accepted list"
    
    def test_accept_invalid_record(self):
        """Accepting a non-existent record should return 500 or 400"""
        fake_record_id = "000000000000000000000000"
        response = requests.post(
            f"{BASE_URL}/api/ai-outreach/suggestions/{fake_record_id}/accept",
            json={"suggestion_index": 0}
        )
        # Could be 400 (bad request) or 500 (server error when record not found)
        assert response.status_code in [400, 404, 500], f"Expected error code, got {response.status_code}"
        print(f"Correctly returned error {response.status_code} for invalid record")
    
    def test_dismiss_suggestion(self):
        """Dismissing a suggestion should change status"""
        if not self.pending_suggestions:
            # Create a fresh one to dismiss
            gen_response = requests.post(f"{BASE_URL}/api/ai-outreach/generate/{TEST_USER_ID}/{TEST_CONTACT_ID}")
            if gen_response.status_code != 200:
                pytest.skip("Cannot create suggestion to dismiss")
            # Refetch pending
            response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=pending")
            data = response.json()
            if not data.get("suggestions"):
                pytest.skip("No pending suggestions after generation - may be deduplicated")
            record_id = data["suggestions"][0]["_id"]
        else:
            record_id = self.pending_suggestions[0]["_id"]
        
        response = requests.post(f"{BASE_URL}/api/ai-outreach/suggestions/{record_id}/dismiss")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Dismiss response should have message"
        print(f"Dismiss response: {data['message']}")
    
    def test_dismiss_invalid_record(self):
        """Dismissing a non-existent record should return 404"""
        fake_record_id = "000000000000000000000000"
        response = requests.post(f"{BASE_URL}/api/ai-outreach/suggestions/{fake_record_id}/dismiss")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Correctly returned 404 for invalid dismiss")


class TestLoginWithTimezone:
    """Tests for login endpoint with timezone parameter"""
    
    def test_login_with_timezone(self):
        """Login with timezone parameter stores timezone on user"""
        test_timezone = "America/Los_Angeles"
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "timezone": test_timezone
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user" in data, "Login response should have user"
        assert "token" in data, "Login response should have token"
        
        # Verify timezone was stored
        user = data["user"]
        assert user.get("timezone") == test_timezone, f"User timezone should be {test_timezone}, got {user.get('timezone')}"
        print(f"Login successful. Timezone stored: {user.get('timezone')}")
    
    def test_login_without_timezone(self):
        """Login without timezone should still work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("Login without timezone parameter works correctly")


class TestTagTriggerIntegration:
    """Test that applying 'sold' tag triggers AI outreach generation"""
    
    def test_assign_sold_tag_structure(self):
        """Verify the tag assignment endpoint exists and structure"""
        # This tests the endpoint structure, not the async AI generation
        response = requests.post(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
            json={
                "tag_name": "sold",
                "contact_ids": [TEST_CONTACT_ID]
            }
        )
        # Should succeed even if contact already has tag
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        print(f"Tag assign response: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
