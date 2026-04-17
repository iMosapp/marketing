"""
Test Campaign Journey API endpoint and Scheduler fixes
Tests:
1. Campaign Journey API returns correct data for contacts with enrollments
2. Campaign Journey API returns empty array for contacts without enrollments
3. Scheduler AI toggle fix - respects campaign ai_enabled=false
4. Scheduler hourly delay fix - no randomization for hourly campaigns
"""
import os
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCampaignJourneyAPI:
    """Tests for the new Campaign Journey endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get user credentials"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        login_data = login_response.json()
        # User object is nested under 'user' key
        self.user = login_data.get("user", login_data)
        self.user_id = self.user.get("_id") or self.user.get("id")
        assert self.user_id, "No user ID returned"
        
        # Test contact IDs from request
        self.contact_with_enrollment = "69a1354f2c0649ac6fb7f3f1"
        self.contact_without_enrollment = "69a0c06f7626f14d125f8c34"
    
    def test_campaign_journey_endpoint_exists(self):
        """Test that the campaign-journey endpoint exists and returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_with_enrollment}/campaign-journey"
        )
        assert response.status_code == 200, f"Endpoint returned {response.status_code}: {response.text}"
        print("SUCCESS: Campaign Journey endpoint exists and returns 200")
    
    def test_campaign_journey_returns_array(self):
        """Test that endpoint returns an array"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_with_enrollment}/campaign-journey"
        )
        data = response.json()
        assert isinstance(data, list), f"Expected array, got {type(data)}"
        print(f"SUCCESS: Returns array with {len(data)} journey(s)")
    
    def test_campaign_journey_structure_for_enrolled_contact(self):
        """Test journey data structure for contact with active enrollment"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_with_enrollment}/campaign-journey"
        )
        data = response.json()
        
        assert len(data) > 0, "Expected at least one journey for enrolled contact"
        
        journey = data[0]
        
        # Verify required fields
        required_fields = [
            "campaign_name", "campaign_type", "trigger_tag", "ai_enabled",
            "status", "current_step", "total_steps", "enrolled_at",
            "next_send_at", "steps"
        ]
        for field in required_fields:
            assert field in journey, f"Missing field: {field}"
        
        print(f"SUCCESS: Journey has all required fields")
        print(f"  Campaign: {journey['campaign_name']}")
        print(f"  Status: {journey['status']}")
        print(f"  Step: {journey['current_step']}/{journey['total_steps']}")
        print(f"  AI Enabled: {journey['ai_enabled']}")
    
    def test_campaign_journey_steps_structure(self):
        """Test that steps have correct structure and status values"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_with_enrollment}/campaign-journey"
        )
        data = response.json()
        
        assert len(data) > 0, "No journey data"
        
        steps = data[0].get("steps", [])
        assert len(steps) > 0, "No steps in journey"
        
        valid_statuses = ["sent", "next", "upcoming"]
        
        for i, step in enumerate(steps):
            # Check required step fields
            step_fields = ["step", "message", "channel", "status"]
            for field in step_fields:
                assert field in step, f"Step {i+1} missing field: {field}"
            
            # Validate status
            assert step["status"] in valid_statuses, f"Invalid status: {step['status']}"
            
            # Sent steps should have sent_at
            if step["status"] == "sent":
                assert "sent_at" in step and step["sent_at"], f"Sent step {i+1} missing sent_at"
            
            # Next step should have scheduled_at
            if step["status"] == "next":
                assert "scheduled_at" in step, f"Next step {i+1} missing scheduled_at"
        
        # Count statuses
        sent_count = sum(1 for s in steps if s["status"] == "sent")
        next_count = sum(1 for s in steps if s["status"] == "next")
        upcoming_count = sum(1 for s in steps if s["status"] == "upcoming")
        
        print(f"SUCCESS: {len(steps)} steps with valid structure")
        print(f"  Sent: {sent_count}, Next: {next_count}, Upcoming: {upcoming_count}")
    
    def test_campaign_journey_empty_for_unenrolled_contact(self):
        """Test that endpoint returns empty array for contact without enrollments"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.contact_without_enrollment}/campaign-journey"
        )
        data = response.json()
        
        assert isinstance(data, list), f"Expected array, got {type(data)}"
        assert len(data) == 0, f"Expected empty array for unenrolled contact, got {len(data)} items"
        
        print("SUCCESS: Returns empty array for contact without enrollment")


class TestSchedulerAIToggleFix:
    """
    Tests for scheduler AI toggle fix.
    The fix ensures campaign's ai_enabled toggle is respected:
    - When ai_enabled=false on campaign, scheduler should NOT use AI regardless of store config
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and setup"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        login_data = login_response.json()
        self.user = login_data.get("user", login_data)
        self.user_id = self.user.get("_id") or self.user.get("id")
    
    def test_scheduler_code_respects_ai_toggle(self):
        """
        Code review test: Verify scheduler.py has correct AI toggle logic.
        The fix at lines 397-422 should:
        1. Get campaign_ai_enabled from campaign.get("ai_enabled", False)
        2. Only use AI when campaign_ai_enabled AND ai_generated are both true
        """
        import os
        scheduler_path = "/app/backend/scheduler.py"
        
        with open(scheduler_path, 'r') as f:
            content = f.read()
        
        # Check for the fix pattern
        assert 'campaign_ai_enabled = campaign.get("ai_enabled", False)' in content, \
            "Missing: campaign_ai_enabled extraction"
        
        assert 'use_ai = campaign_ai_enabled and ai_generated' in content, \
            "Missing: AI toggle logic (use_ai = campaign_ai_enabled and ai_generated)"
        
        # Verify the logic is correct - campaign toggle is primary control
        assert 'if campaign_ai_enabled:' in content, \
            "Missing: campaign_ai_enabled check before store config lookup"
        
        print("SUCCESS: Scheduler AI toggle logic is correctly implemented")
        print("  - Campaign's ai_enabled is the primary control")
        print("  - Store config only checked when campaign has AI on")


class TestSchedulerHourlyDelayFix:
    """
    Tests for scheduler hourly delay fix.
    The fix prevents time randomization for hourly campaigns (delay_hours only).
    Randomization should only apply to daily+ delays (delay_days > 0 or delay_months > 0).
    """
    
    def test_scheduler_code_hourly_fix(self):
        """
        Code review test: Verify scheduler.py only randomizes daily+ delays.
        The fix at lines 555-590 should:
        1. Check step_delay_days and step_delay_months
        2. Only randomize if is_daily_or_longer (delay_days > 0 or delay_months > 0)
        """
        scheduler_path = "/app/backend/scheduler.py"
        
        with open(scheduler_path, 'r') as f:
            content = f.read()
        
        # Check for delay extraction
        assert "step_delay_hours = next_step.get('delay_hours', 0)" in content, \
            "Missing: step_delay_hours extraction"
        assert "step_delay_days = next_step.get('delay_days', 0)" in content, \
            "Missing: step_delay_days extraction"
        assert "step_delay_months = next_step.get('delay_months', 0)" in content, \
            "Missing: step_delay_months extraction"
        
        # Check for daily-or-longer condition
        assert "is_daily_or_longer = step_delay_days > 0 or step_delay_months > 0" in content, \
            "Missing: is_daily_or_longer condition"
        
        # Check that randomization is gated by is_daily_or_longer
        assert "if is_daily_or_longer:" in content, \
            "Missing: is_daily_or_longer gate for randomization"
        
        print("SUCCESS: Scheduler hourly delay fix is correctly implemented")
        print("  - Only daily+ delays get time randomization")
        print("  - Hourly campaigns advance without randomization")


class TestCampaignJourneyComponentIntegration:
    """
    Tests for verifying the Campaign Journey component integration
    in the contact detail page.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
        })
        self.user = login_response.json()
        self.user_id = self.user.get("_id") or self.user.get("id")
    
    def test_frontend_component_exists(self):
        """Verify CampaignJourney.tsx component file exists"""
        component_path = "/app/frontend/components/CampaignJourney.tsx"
        assert os.path.exists(component_path), f"Component not found: {component_path}"
        
        with open(component_path, 'r') as f:
            content = f.read()
        
        # Check for data-testid attributes
        assert 'data-testid="campaign-journey-section"' in content, \
            "Missing data-testid for main section"
        
        # Check for proper API call
        assert "/campaign-journey" in content, "Missing API endpoint call"
        
        # Check for status handling
        assert "'sent'" in content or '"sent"' in content, "Missing 'sent' status handling"
        assert "'next'" in content or '"next"' in content, "Missing 'next' status handling"
        assert "'upcoming'" in content or '"upcoming"' in content, "Missing 'upcoming' status handling"
        
        print("SUCCESS: CampaignJourney component properly implemented")
    
    def test_contact_page_imports_component(self):
        """Verify contact detail page imports CampaignJourney"""
        contact_page_path = "/app/frontend/app/contact/[id].tsx"
        
        with open(contact_page_path, 'r') as f:
            content = f.read()
        
        assert "CampaignJourney" in content, "CampaignJourney not imported in contact page"
        assert "<CampaignJourney" in content, "CampaignJourney component not used in JSX"
        
        print("SUCCESS: Contact page integrates CampaignJourney component")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
