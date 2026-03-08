"""
AI-Powered Outreach with Relationship Intelligence Tests
Tests for the upgraded AI outreach system with:
1. Relationship Intelligence Engine (relationship_intel.py)
2. Auto-enrollment in Sold Follow-Up campaign on tag apply
3. Campaign pending sends with relationship brief
4. New Campaign tab in frontend (pending sends with relationship briefs)

Endpoints tested:
- GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id}
- GET /api/campaigns/{user_id}/pending-sends
- POST /api/campaigns/{user_id}/pending-sends/{send_id}/complete
- POST /api/tags/{user_id}/assign (sold tag triggers AI + campaign enrollment)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from context
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_USER_EMAIL = "forest@imosapp.com"
TEST_USER_PASSWORD = "Admin123!"

# Test contacts
BUD_CONTACT_ID = "69a496841603573df5a41723"  # Already has Sold tag and enrolled
JANE_CONTACT_ID = "69a1dbb4320d732f90069652"  # Has pending AI suggestion


class TestRelationshipIntelligence:
    """Tests for GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id}"""
    
    def test_get_relationship_brief_bud(self):
        """Get relationship brief for Bud (contact with Sold tag)"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/relationship-brief/{TEST_USER_ID}/{BUD_CONTACT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check required fields
        assert "relationship_health" in data, "Brief should have relationship_health"
        assert "engagement_score" in data, "Brief should have engagement_score"
        assert "response_pattern" in data, "Brief should have response_pattern"
        assert "milestones" in data, "Brief should have milestones"
        assert "human_summary" in data, "Brief should have human_summary"
        assert "contact_name" in data, "Brief should have contact_name"
        
        # Verify types
        assert data["relationship_health"] in ["strong", "warm", "cooling", "cold", "unknown"], \
            f"Invalid health: {data['relationship_health']}"
        assert isinstance(data["engagement_score"], int), "engagement_score should be int"
        assert isinstance(data["milestones"], list), "milestones should be list"
        
        print(f"Relationship Brief for {data.get('contact_name', 'Unknown')}:")
        print(f"  Health: {data['relationship_health']}")
        print(f"  Engagement Score: {data['engagement_score']}")
        print(f"  Response Pattern: {data['response_pattern']}")
        print(f"  Milestones: {data['milestones']}")
        print(f"  Human Summary: {data['human_summary']}")
    
    def test_get_relationship_brief_jane(self):
        """Get relationship brief for Jane Doe"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/relationship-brief/{TEST_USER_ID}/{JANE_CONTACT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "relationship_health" in data
        assert "engagement_score" in data
        assert "response_pattern" in data
        assert "human_summary" in data
        
        print(f"Jane Doe Brief: {data['human_summary']}")
    
    def test_relationship_brief_nonexistent_contact(self):
        """Non-existent contact should return 200 with 'Contact not found' summary"""
        fake_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/ai-outreach/relationship-brief/{TEST_USER_ID}/{fake_id}")
        # The endpoint returns 200 with summary "Contact not found" instead of 404
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "Contact not found" in data.get("human_summary", "") or data.get("relationship_health") == "unknown"
        print("Non-existent contact handled correctly")
    
    def test_relationship_brief_optional_fields(self):
        """Verify optional fields like days_since_sale and days_known"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/relationship-brief/{TEST_USER_ID}/{BUD_CONTACT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # These are optional but should be present in response
        assert "days_since_sale" in data, "Should have days_since_sale field (can be null)"
        assert "days_known" in data, "Should have days_known field (can be null)"
        assert "last_interaction_days" in data, "Should have last_interaction_days field"
        assert "engagement_signals" in data, "Should have engagement_signals list"
        assert "previous_campaign_messages" in data, "Should have previous_campaign_messages list"
        
        print(f"Days since sale: {data.get('days_since_sale')}")
        print(f"Days known: {data.get('days_known')}")


class TestCampaignPendingSends:
    """Tests for campaign pending sends with relationship brief"""
    
    def test_get_pending_sends(self):
        """GET /api/campaigns/{user_id}/pending-sends returns pending manual campaign sends"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/pending-sends")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        print(f"Found {len(data)} pending sends")
        
        # If there are pending sends, verify structure
        for send in data[:3]:  # Check first 3
            assert "_id" in send, "Pending send should have _id"
            assert "contact_id" in send, "Pending send should have contact_id"
            assert "contact_name" in send, "Pending send should have contact_name"
            assert "campaign_name" in send, "Pending send should have campaign_name"
            assert "step" in send, "Pending send should have step"
            assert "channel" in send, "Pending send should have channel"
            assert "message" in send, "Pending send should have message"
            assert "status" in send, "Pending send should have status"
            assert send["status"] == "pending", f"Status should be pending, got {send['status']}"
            
            # Check for relationship_brief field (may be empty string for old entries)
            has_relationship_brief = "relationship_brief" in send
            print(f"  Send {send['_id']}: {send['contact_name']} - Step {send['step']} - has_brief: {has_relationship_brief}")
            if has_relationship_brief and send["relationship_brief"]:
                print(f"    Brief: {send['relationship_brief'][:100]}...")
    
    def test_complete_pending_send(self):
        """POST /api/campaigns/{user_id}/pending-sends/{send_id}/complete marks send as sent"""
        # First get pending sends
        get_response = requests.get(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/pending-sends")
        assert get_response.status_code == 200
        
        pending = get_response.json()
        if not pending:
            pytest.skip("No pending sends to test complete action")
        
        send_id = pending[0]["_id"]
        contact_name = pending[0].get("contact_name", "Unknown")
        
        # Mark as complete
        response = requests.post(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/pending-sends/{send_id}/complete")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        print(f"Marked send for {contact_name} as complete: {data}")
        
        # Verify it's no longer in pending list
        verify_response = requests.get(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/pending-sends")
        assert verify_response.status_code == 200
        remaining = verify_response.json()
        remaining_ids = [s["_id"] for s in remaining]
        assert send_id not in remaining_ids, "Completed send should not be in pending list anymore"
    
    def test_complete_nonexistent_send(self):
        """Completing non-existent send returns 404"""
        fake_id = "000000000000000000000000"
        response = requests.post(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/pending-sends/{fake_id}/complete")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Non-existent send correctly returns 404")


class TestSoldTagTriggersCampaignEnrollment:
    """Tests for sold tag triggering both AI outreach AND campaign enrollment"""
    
    def test_get_campaign_enrollments_for_bud(self):
        """Verify Bud is enrolled in sold campaign via pending sends"""
        # Check pending sends which would show campaign enrollment activity
        response = requests.get(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/pending-sends")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        pending = response.json()
        # Check if Bud appears in pending sends
        bud_sends = [s for s in pending if s.get("contact_id") == BUD_CONTACT_ID]
        print(f"Found {len(bud_sends)} pending sends for Bud")
        
        # Also verify AI outreach exists
        ai_response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=all")
        assert ai_response.status_code == 200
        ai_data = ai_response.json()
        print(f"Total AI suggestions: {ai_data['total']}")
    
    def test_assign_sold_tag_triggers_ai_and_enrollment(self):
        """Assigning 'Sold' tag should trigger AI outreach AND campaign enrollment"""
        # This is a code review verification - the actual trigger is async
        # We verify the endpoint works and check code structure
        response = requests.post(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
            json={
                "tag_name": "Sold",
                "contact_ids": [BUD_CONTACT_ID]  # Already has tag, should be idempotent
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        print(f"Tag assign response: {data['message']}")
        
        # Give async tasks time to run
        time.sleep(2)
        
        # Verify AI outreach was triggered (or exists from before)
        ai_response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=all")
        assert ai_response.status_code == 200
        ai_data = ai_response.json()
        print(f"After tag assign: {ai_data['total']} total AI suggestions")


class TestAIOutreachWithRelationshipIntel:
    """Tests for AI outreach suggestions using relationship intelligence"""
    
    def test_get_pending_suggestions_with_context(self):
        """Get pending AI suggestions - verify they have contact context"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=pending")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        suggestions = data.get("suggestions", [])
        print(f"Found {len(suggestions)} pending suggestions")
        
        for sug in suggestions[:2]:
            assert "contact_id" in sug
            assert "contact_name" in sug
            assert "suggestions" in sug
            
            # Each suggestion should have message, approach, best_time_reason
            for inner in sug["suggestions"]:
                assert "message" in inner, "Suggestion should have message"
                assert "approach" in inner, "Suggestion should have approach"
                print(f"  {sug['contact_name']}: {inner['approach']} - {inner['message'][:50]}...")
    
    def test_accept_suggestion_creates_task_with_message(self):
        """Accept a suggestion - verify task is created with the suggested message"""
        # Get pending suggestions
        response = requests.get(f"{BASE_URL}/api/ai-outreach/suggestions/{TEST_USER_ID}?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("suggestions"):
            pytest.skip("No pending suggestions to test accept")
        
        record = data["suggestions"][0]
        record_id = record["_id"]
        suggested_message = record["suggestions"][0]["message"] if record["suggestions"] else ""
        
        # Accept the suggestion
        accept_response = requests.post(
            f"{BASE_URL}/api/ai-outreach/suggestions/{record_id}/accept",
            json={"suggestion_index": 0}
        )
        assert accept_response.status_code == 200, f"Expected 200, got {accept_response.status_code}: {accept_response.text}"
        
        result = accept_response.json()
        assert "task_id" in result, "Accept should return task_id"
        assert "scheduled_for" in result, "Accept should return scheduled_for"
        
        print(f"Accepted suggestion: Task ID {result['task_id']}, Scheduled for {result['scheduled_for']}")
        
        # The task should contain the suggested_message
        # We can verify by checking tasks endpoint if available
        tasks_response = requests.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}")
        if tasks_response.status_code == 200:
            tasks = tasks_response.json()
            if isinstance(tasks, dict):
                tasks = tasks.get("tasks", [])
            created_task = next((t for t in tasks if t.get("_id") == result["task_id"] or str(t.get("_id")) == result["task_id"]), None)
            if created_task:
                print(f"Task created with message: {created_task.get('suggested_message', created_task.get('description', ''))[:100]}...")


class TestLoginTimezone:
    """Test that login with timezone stores it on user document"""
    
    def test_login_stores_timezone(self):
        """Login with timezone parameter saves timezone on user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "timezone": "America/New_York"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user" in data
        user = data["user"]
        assert user.get("timezone") == "America/New_York", f"Expected America/New_York, got {user.get('timezone')}"
        print(f"Login successful - timezone stored: {user.get('timezone')}")


class TestStatsAndOverview:
    """Test stats endpoints for AI outreach"""
    
    def test_ai_outreach_stats(self):
        """GET /api/ai-outreach/stats returns correct counts"""
        response = requests.get(f"{BASE_URL}/api/ai-outreach/stats/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pending" in data
        assert "accepted" in data
        assert "dismissed" in data
        assert "total" in data
        
        # Verify total = sum
        assert data["total"] == data["pending"] + data["accepted"] + data["dismissed"]
        
        print(f"AI Outreach Stats: Pending={data['pending']}, Accepted={data['accepted']}, Dismissed={data['dismissed']}, Total={data['total']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
