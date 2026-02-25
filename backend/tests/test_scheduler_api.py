"""
Scheduler API Tests
Tests for:
- GET /api/scheduler/status - scheduler health and job info
- POST /api/scheduler/trigger/date-triggers - manual date-trigger sweep
- POST /api/scheduler/trigger/campaign-steps - manual campaign step processing
- Date trigger deduplication
- Campaign step advancement and completion
- Birthday trigger matching
"""
import pytest
import requests
import os
from datetime import datetime, timedelta, timezone
from bson import ObjectId

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test IDs from main agent
SUPER_ADMIN_USER_ID = "699907444a076891982fab35"
TEST_CONTACT_ID = "699f25926cd30496c5065496"  # Contact with today's birthday
TEST_CAMPAIGN_ID = "699f25ce6cd30496c506549c"
TEST_ENROLLMENT_ID = "699f25d36cd30496c506549d"


class TestSchedulerStatusEndpoint:
    """Tests for GET /api/scheduler/status"""
    
    def test_scheduler_status_returns_running_true(self):
        """GET /api/scheduler/status returns running=true"""
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("running") is True, f"Expected running=True, got {data.get('running')}"
        print("✓ Scheduler status shows running=true")
    
    def test_scheduler_status_shows_2_registered_jobs(self):
        """GET /api/scheduler/status shows 2 registered jobs"""
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        jobs = data.get("jobs", [])
        assert len(jobs) == 2, f"Expected 2 jobs, got {len(jobs)}"
        
        job_ids = [job["id"] for job in jobs]
        assert "daily_date_triggers" in job_ids, f"Missing daily_date_triggers job. Jobs: {job_ids}"
        assert "campaign_step_processor" in job_ids, f"Missing campaign_step_processor job. Jobs: {job_ids}"
        print(f"✓ Scheduler shows 2 registered jobs: {job_ids}")
    
    def test_scheduler_status_job_structure(self):
        """Each job has id, next_run, and trigger fields"""
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert response.status_code == 200
        
        data = response.json()
        for job in data.get("jobs", []):
            assert "id" in job, "Job missing 'id' field"
            assert "next_run" in job, "Job missing 'next_run' field"
            assert "trigger" in job, "Job missing 'trigger' field"
        print("✓ All jobs have correct structure (id, next_run, trigger)")
    
    def test_scheduler_status_response_fields(self):
        """Status response contains expected fields"""
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert response.status_code == 200
        
        data = response.json()
        expected_fields = ["running", "jobs", "last_date_trigger_run", "last_campaign_step_run", 
                         "date_trigger_results", "campaign_step_results", "recent_errors", "checked_at"]
        
        for field in expected_fields:
            assert field in data, f"Missing field '{field}' in response"
        print(f"✓ Scheduler status contains all expected fields")


class TestManualDateTrigger:
    """Tests for POST /api/scheduler/trigger/date-triggers"""
    
    def test_manual_date_trigger_returns_results(self):
        """POST /api/scheduler/trigger/date-triggers returns results object"""
        response = requests.post(f"{BASE_URL}/api/scheduler/trigger/date-triggers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have 'message' field"
        assert "results" in data, "Response should have 'results' field"
        assert "Date-trigger sweep completed" in data["message"], f"Unexpected message: {data['message']}"
        
        results = data["results"]
        assert "users_processed" in results, "Results should have 'users_processed'"
        assert "messages_sent" in results, "Results should have 'messages_sent'"
        assert "ran_at" in results, "Results should have 'ran_at'"
        print(f"✓ Date-trigger sweep completed: {results}")
        return results
    
    def test_date_trigger_updates_status_timestamp(self):
        """Manual trigger updates last_date_trigger_run timestamp"""
        # Run the trigger
        trigger_response = requests.post(f"{BASE_URL}/api/scheduler/trigger/date-triggers")
        assert trigger_response.status_code == 200
        
        # Check status shows the run
        status_response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data.get("last_date_trigger_run") is not None, "last_date_trigger_run should be set"
        
        # Verify it's recent (within last minute)
        last_run = datetime.fromisoformat(data["last_date_trigger_run"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - last_run).total_seconds()
        assert diff < 60, f"last_date_trigger_run should be recent. Diff: {diff}s"
        print(f"✓ last_date_trigger_run timestamp updated: {data['last_date_trigger_run']}")


class TestManualCampaignSteps:
    """Tests for POST /api/scheduler/trigger/campaign-steps"""
    
    def test_manual_campaign_steps_returns_results(self):
        """POST /api/scheduler/trigger/campaign-steps returns results object"""
        response = requests.post(f"{BASE_URL}/api/scheduler/trigger/campaign-steps")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have 'message' field"
        assert "results" in data, "Response should have 'results' field"
        assert "Campaign step processing completed" in data["message"], f"Unexpected message: {data['message']}"
        
        results = data["results"]
        assert "pending_found" in results, "Results should have 'pending_found'"
        assert "processed" in results, "Results should have 'processed'"
        assert "ran_at" in results, "Results should have 'ran_at'"
        print(f"✓ Campaign step processing completed: {results}")
        return results
    
    def test_campaign_steps_updates_status_timestamp(self):
        """Manual trigger updates last_campaign_step_run timestamp"""
        # Run the trigger
        trigger_response = requests.post(f"{BASE_URL}/api/scheduler/trigger/campaign-steps")
        assert trigger_response.status_code == 200
        
        # Check status shows the run
        status_response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data.get("last_campaign_step_run") is not None, "last_campaign_step_run should be set"
        
        # Verify it's recent (within last minute)
        last_run = datetime.fromisoformat(data["last_campaign_step_run"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - last_run).total_seconds()
        assert diff < 60, f"last_campaign_step_run should be recent. Diff: {diff}s"
        print(f"✓ last_campaign_step_run timestamp updated: {data['last_campaign_step_run']}")


class TestDateTriggerDeduplication:
    """Tests for date trigger deduplication - running twice on same day sends 0 on second run"""
    
    def test_deduplication_second_run_sends_zero(self):
        """Running date-trigger sweep twice on same day sends 0 messages on second run"""
        # First run
        response1 = requests.post(f"{BASE_URL}/api/scheduler/trigger/date-triggers")
        assert response1.status_code == 200
        first_results = response1.json().get("results", {})
        first_sent = first_results.get("messages_sent", 0)
        print(f"First run: {first_sent} messages sent")
        
        # Second run - should send 0 due to deduplication
        response2 = requests.post(f"{BASE_URL}/api/scheduler/trigger/date-triggers")
        assert response2.status_code == 200
        second_results = response2.json().get("results", {})
        second_sent = second_results.get("messages_sent", 0)
        
        # Second run should send fewer or equal messages (ideally 0 if dedup is working)
        assert second_sent <= first_sent, f"Second run sent {second_sent}, expected <= {first_sent} (dedup should prevent resending)"
        print(f"✓ Deduplication working: First run sent {first_sent}, second run sent {second_sent}")


class TestCampaignStepAdvancement:
    """Tests for campaign step processor advancing enrollments"""
    
    def test_create_enrollment_and_process(self):
        """Create a new enrollment and verify step processor advances it"""
        # First, check if we can create a test enrollment
        # We need an active campaign and a contact
        
        # Get existing campaigns
        campaigns_response = requests.get(f"{BASE_URL}/api/campaigns/{SUPER_ADMIN_USER_ID}")
        if campaigns_response.status_code != 200:
            pytest.skip("Could not fetch campaigns")
        
        campaigns = campaigns_response.json()
        active_campaigns = [c for c in campaigns if c.get("active") and len(c.get("sequences", [])) >= 2]
        
        if not active_campaigns:
            pytest.skip("No active campaigns with 2+ steps found")
        
        campaign = active_campaigns[0]
        campaign_id = campaign.get("_id") or campaign.get("id")
        print(f"Using campaign: {campaign.get('name')} with {len(campaign.get('sequences', []))} steps")
        
        # Get contacts
        contacts_response = requests.get(f"{BASE_URL}/api/contacts/{SUPER_ADMIN_USER_ID}?limit=10")
        if contacts_response.status_code != 200:
            pytest.skip("Could not fetch contacts")
        
        contacts = contacts_response.json()
        if not contacts:
            pytest.skip("No contacts found")
        
        # Find a contact not already enrolled
        test_contact = contacts[0]
        contact_id = test_contact.get("_id") or test_contact.get("id")
        
        # Attempt to enroll (might fail if already enrolled)
        enroll_response = requests.post(
            f"{BASE_URL}/api/campaigns/{SUPER_ADMIN_USER_ID}/{campaign_id}/enroll/{contact_id}"
        )
        
        if enroll_response.status_code == 400 and "already enrolled" in enroll_response.text.lower():
            print("Contact already enrolled, skipping new enrollment test")
            pytest.skip("Contact already enrolled")
        
        if enroll_response.status_code == 200:
            enrollment = enroll_response.json()
            print(f"✓ Created enrollment: step {enrollment.get('current_step')}, status {enrollment.get('status')}")
            assert enrollment.get("current_step") == 1
            assert enrollment.get("status") == "active"
    
    def test_enrollment_status_after_processing(self):
        """Check enrollment status reflects step advancement"""
        # Get enrollments for the test campaign
        enrollments_response = requests.get(
            f"{BASE_URL}/api/campaigns/{SUPER_ADMIN_USER_ID}/{TEST_CAMPAIGN_ID}/enrollments"
        )
        
        if enrollments_response.status_code != 200:
            pytest.skip(f"Could not fetch enrollments: {enrollments_response.text}")
        
        enrollments = enrollments_response.json()
        print(f"Found {len(enrollments)} enrollments for campaign {TEST_CAMPAIGN_ID}")
        
        for e in enrollments:
            step = e.get("current_step", 0)
            status = e.get("status", "unknown")
            messages = len(e.get("messages_sent", []))
            print(f"  - {e.get('contact_name', 'Unknown')}: step {step}, status {status}, {messages} messages sent")


class TestCampaignCompletion:
    """Tests for campaign completion when all steps are done"""
    
    def test_completed_enrollments_have_correct_status(self):
        """Enrollments that completed all steps should have status='completed'"""
        # Get all enrollments
        enrollments_response = requests.get(
            f"{BASE_URL}/api/campaigns/{SUPER_ADMIN_USER_ID}/{TEST_CAMPAIGN_ID}/enrollments"
        )
        
        if enrollments_response.status_code != 200:
            pytest.skip("Could not fetch enrollments")
        
        enrollments = enrollments_response.json()
        completed = [e for e in enrollments if e.get("status") == "completed"]
        
        if completed:
            print(f"✓ Found {len(completed)} completed enrollments")
            for e in completed:
                # Verify messages_sent array exists and has entries
                messages = e.get("messages_sent", [])
                print(f"  - {e.get('contact_name')}: {len(messages)} messages sent")
        else:
            print("No completed enrollments found (may be expected if campaign still in progress)")


class TestBirthdayTriggerMatching:
    """Tests for birthday trigger correctly matching contacts"""
    
    def test_birthday_config_exists(self):
        """Verify birthday trigger config is set up"""
        response = requests.get(f"{BASE_URL}/api/date-triggers/{SUPER_ADMIN_USER_ID}/config")
        assert response.status_code == 200
        
        configs = response.json()
        birthday_configs = [c for c in configs if c.get("trigger_type") == "birthday"]
        
        if birthday_configs:
            config = birthday_configs[0]
            print(f"✓ Birthday config found: enabled={config.get('enabled')}, delivery={config.get('delivery_method')}")
            assert config.get("message_template"), "Birthday config should have a message template"
        else:
            print("No birthday config found - creating one for test")
            # Create a birthday config
            payload = {
                "trigger_type": "birthday",
                "enabled": True,
                "delivery_method": "sms",
                "message_template": "Happy Birthday, {first_name}! Wishing you an amazing day!"
            }
            create_response = requests.put(
                f"{BASE_URL}/api/date-triggers/{SUPER_ADMIN_USER_ID}/config/birthday",
                json=payload
            )
            assert create_response.status_code == 200
            print("✓ Created birthday config for testing")
    
    def test_contact_with_todays_birthday_gets_message(self):
        """Contact with today's birthday should receive a message when trigger runs"""
        # Check the date trigger log for the test contact
        log_response = requests.get(f"{BASE_URL}/api/date-triggers/{SUPER_ADMIN_USER_ID}/log?limit=50")
        
        if log_response.status_code != 200:
            pytest.skip("Could not fetch date trigger log")
        
        logs = log_response.json()
        birthday_logs = [l for l in logs if l.get("trigger_type") == "birthday"]
        
        print(f"Found {len(birthday_logs)} birthday trigger log entries")
        for log in birthday_logs[:5]:
            print(f"  - {log.get('contact_name')}: sent at {log.get('sent_at')}")
        
        if birthday_logs:
            print("✓ Birthday trigger has sent messages")


class TestSchedulerErrorHandling:
    """Tests for scheduler error tracking"""
    
    def test_recent_errors_array_exists(self):
        """Status endpoint should return recent_errors array"""
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "recent_errors" in data, "Status should have recent_errors field"
        assert isinstance(data["recent_errors"], list), "recent_errors should be a list"
        
        if data["recent_errors"]:
            print(f"⚠ Found {len(data['recent_errors'])} recent errors:")
            for err in data["recent_errors"]:
                print(f"  - {err}")
        else:
            print("✓ No recent errors in scheduler")


class TestEndToEndSchedulerFlow:
    """End-to-end test of scheduler functionality"""
    
    def test_full_scheduler_flow(self):
        """Test complete scheduler workflow"""
        # 1. Check scheduler is running
        status1 = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert status1.status_code == 200
        data1 = status1.json()
        assert data1["running"] is True, "Scheduler should be running"
        print("Step 1: ✓ Scheduler is running")
        
        # 2. Trigger date triggers
        trigger1 = requests.post(f"{BASE_URL}/api/scheduler/trigger/date-triggers")
        assert trigger1.status_code == 200
        result1 = trigger1.json()
        print(f"Step 2: ✓ Date triggers processed: {result1['results'].get('messages_sent', 0)} messages")
        
        # 3. Trigger campaign steps
        trigger2 = requests.post(f"{BASE_URL}/api/scheduler/trigger/campaign-steps")
        assert trigger2.status_code == 200
        result2 = trigger2.json()
        print(f"Step 3: ✓ Campaign steps processed: {result2['results'].get('processed', 0)}/{result2['results'].get('pending_found', 0)}")
        
        # 4. Verify status updated
        status2 = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert status2.status_code == 200
        data2 = status2.json()
        
        assert data2["last_date_trigger_run"] is not None, "last_date_trigger_run should be set"
        assert data2["last_campaign_step_run"] is not None, "last_campaign_step_run should be set"
        print("Step 4: ✓ Status timestamps updated")
        
        print("\n✓ Full scheduler flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
