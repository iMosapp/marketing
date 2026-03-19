"""
Tests for Campaign Scheduler Bug Fixes - Iteration 227

Tests verify:
1. GET /api/campaigns/scheduler/pending - returns pending/upcoming counts
2. POST /api/campaigns/scheduler/process - returns sent/completed/pending_found
3. GET /api/campaigns/{user_id} - returns list of campaigns (not 500)
4. GET /api/campaigns/templates/prebuilt - returns templates including cold_outreach_text
5. GET /api/campaigns/templates/prebuilt/{template_id} - returns template with sequences
6. POST /api/campaigns/scheduler/trigger - original endpoint still works
7. GET /api/campaigns/{user_id}/{campaign_id}/enrollments - returns enrollments
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"
CAMPAIGN_ID = "69aee1e38ef616daeb09143f"


class TestCampaignSchedulerEndpoints:
    """Test scheduler/pending and scheduler/process endpoints"""
    
    def test_scheduler_pending_returns_counts(self):
        """GET /api/campaigns/scheduler/pending should return pending and upcoming counts"""
        response = requests.get(f"{BASE_URL}/api/campaigns/scheduler/pending")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "pending" in data, "Response should have 'pending' field"
        assert "upcoming" in data, "Response should have 'upcoming' field"
        assert isinstance(data["pending"], int), "'pending' should be an integer"
        assert isinstance(data["upcoming"], int), "'upcoming' should be an integer"
        print(f"PASS: scheduler/pending returns pending={data['pending']}, upcoming={data['upcoming']}")
    
    def test_scheduler_process_returns_results(self):
        """POST /api/campaigns/scheduler/process should return sent/completed/pending_found"""
        response = requests.post(f"{BASE_URL}/api/campaigns/scheduler/process")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "sent" in data, "Response should have 'sent' field"
        assert "completed" in data, "Response should have 'completed' field"
        assert "pending_found" in data, "Response should have 'pending_found' field"
        print(f"PASS: scheduler/process returns sent={data['sent']}, completed={data['completed']}, pending_found={data['pending_found']}")
    
    def test_scheduler_trigger_still_works(self):
        """POST /api/campaigns/scheduler/trigger (original endpoint) should still work"""
        response = requests.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data or "processed" in data, "Response should have 'message' or 'processed'"
        print(f"PASS: scheduler/trigger still works")


class TestCampaignUserEndpoints:
    """Test campaigns/{user_id} endpoint (the main bug fix)"""
    
    def test_get_campaigns_returns_list(self):
        """GET /api/campaigns/{user_id} should return a list of campaigns (not 500)"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}")
        print(f"Status: {response.status_code}")
        print(f"Response length: {len(response.text)} chars")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. This was the main bug!"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of campaigns"
        print(f"PASS: campaigns/{USER_ID} returns {len(data)} campaigns")
        
        # Verify campaign structure if data exists
        if len(data) > 0:
            campaign = data[0]
            assert "_id" in campaign or "id" in campaign, "Campaign should have an ID"
            assert "name" in campaign, "Campaign should have a name"
            print(f"First campaign: {campaign.get('name', 'Unknown')}")
    
    def test_get_campaign_enrollments(self):
        """GET /api/campaigns/{user_id}/{campaign_id}/enrollments should return enrollments"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}/{CAMPAIGN_ID}/enrollments")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: enrollments endpoint returns {len(data)} enrollments")


class TestPrebuiltTemplates:
    """Test prebuilt campaign templates endpoints"""
    
    def test_get_prebuilt_templates(self):
        """GET /api/campaigns/templates/prebuilt should return list of templates"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        print(f"Status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one template"
        
        # Check for specific templates
        template_ids = [t["id"] for t in data]
        assert "cold_outreach_text" in template_ids, "Should have cold_outreach_text template"
        assert "cold_outreach_email" in template_ids, "Should have cold_outreach_email template"
        print(f"PASS: prebuilt templates returns {len(data)} templates including cold_outreach_text and cold_outreach_email")
    
    def test_get_cold_outreach_text_template(self):
        """GET /api/campaigns/templates/prebuilt/cold_outreach_text should return template with 3 sequences"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/cold_outreach_text")
        print(f"Status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "cold_outreach_text"
        assert "sequences" in data, "Template should have sequences"
        assert len(data["sequences"]) == 3, f"Should have 3 sequences, got {len(data['sequences'])}"
        print(f"PASS: cold_outreach_text template has {len(data['sequences'])} sequences")
    
    def test_get_cold_outreach_email_template(self):
        """GET /api/campaigns/templates/prebuilt/cold_outreach_email should return template"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/cold_outreach_email")
        print(f"Status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "cold_outreach_email"
        assert "sequences" in data
        print(f"PASS: cold_outreach_email template works")


class TestCampaignSequenceStepFix:
    """Test that CampaignSequenceStep.step defaults properly"""
    
    def test_campaigns_with_missing_step_field(self):
        """Campaigns should load even if DB records lack 'step' field (auto-assigns)"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            for campaign in data:
                sequences = campaign.get("sequences", [])
                for i, seq in enumerate(sequences):
                    # Auto-assigned step numbers should be present
                    step_num = seq.get("step", 0)
                    # Either 0 (default) or i+1 (auto-assigned)
                    assert step_num >= 0, f"Step number should be >= 0, got {step_num}"
        print(f"PASS: Campaigns load with step numbers properly handled")


class TestRouteOrdering:
    """Test that static routes work before parameterized routes"""
    
    def test_scheduler_pending_before_user_id(self):
        """Verify /scheduler/pending is not confused with /{user_id}"""
        # This was the key bug - 'scheduler' was being treated as a user_id
        response = requests.get(f"{BASE_URL}/api/campaigns/scheduler/pending")
        assert response.status_code == 200, "scheduler/pending should NOT 500 with ObjectId error"
        
        data = response.json()
        # Should return counts, not campaigns
        assert "pending" in data, "Should return pending count, not campaign list"
        print("PASS: scheduler/pending route works (not confused with user_id)")
    
    def test_scheduler_process_before_user_id(self):
        """Verify /scheduler/process is not confused with /{user_id}"""
        response = requests.post(f"{BASE_URL}/api/campaigns/scheduler/process")
        assert response.status_code == 200, "scheduler/process should NOT 500"
        print("PASS: scheduler/process route works")
    
    def test_templates_prebuilt_before_user_id(self):
        """Verify /templates/prebuilt is not confused with /{user_id}"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200, "templates/prebuilt should NOT 500"
        
        data = response.json()
        assert isinstance(data, list), "Should return list of templates"
        print("PASS: templates/prebuilt route works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
