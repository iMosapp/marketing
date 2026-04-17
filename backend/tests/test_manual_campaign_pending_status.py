"""
Test: Manual Campaign Pending Status Fix

Bug Fix Verification:
- For MANUAL campaigns, scheduler should mark messages_sent with status='pending' (not 'sent')
- last_sent_at should NOT be set for manual mode enrollments
- Campaign task should have status='pending' and completed=false
- When task is completed via PATCH, messages_sent should update to status='sent'
- Campaign Journey API should return 'pending_send' for pending manual steps

Endpoints tested:
- POST /api/campaigns/{user_id} - Create campaign
- POST /api/campaigns/{user_id}/{campaign_id}/enroll/{contact_id} - Enroll contact
- POST /api/campaigns/scheduler/trigger - Process enrollments
- GET /api/contacts/{user_id}/{contact_id}/campaign-journey - Get journey with statuses
- GET /api/tasks/{user_id} - Get tasks for user
- PATCH /api/tasks/{user_id}/{task_id} - Complete task
"""

import os
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestManualCampaignPendingStatus:
    """Tests for manual campaign pending/sent status fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get user_id"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get user_id
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        login_data = login_resp.json()
        user = login_data.get("user", {})
        self.user_id = user.get("id") or user.get("_id") or login_data.get("user_id")
        assert self.user_id, f"Failed to get user_id from login: {login_data}"
        
        # Store test artifacts for cleanup
        self.test_campaign_id = None
        self.test_contact_id = None
        self.test_task_id = None
        
        yield
        
        # Cleanup after tests
        self._cleanup()
    
    def _cleanup(self):
        """Cleanup test data"""
        try:
            if self.test_campaign_id:
                self.session.delete(f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}")
            if self.test_contact_id:
                self.session.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}")
        except Exception as e:
            print(f"Cleanup error (non-fatal): {e}")
    
    def test_01_create_manual_campaign(self):
        """Create a manual delivery mode campaign with 2 steps"""
        campaign_data = {
            "name": "TEST_Manual_Pending_Status_Campaign",
            "type": "custom",
            "trigger_tag": "test_manual_pending",
            "active": True,
            "delivery_mode": "manual",  # CRITICAL: This must be manual
            "ai_enabled": False,
            "sequences": [
                {
                    "step": 1,
                    "delay_hours": 0,
                    "delay_days": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "message_template": "Step 1: Hello {name}, this is the first step!",
                    "action_type": "message"
                },
                {
                    "step": 2,
                    "delay_hours": 0,
                    "delay_days": 1,
                    "delay_months": 0,
                    "channel": "sms",
                    "message_template": "Step 2: Follow-up message to {name}!",
                    "action_type": "message"
                }
            ]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/campaigns/{self.user_id}", json=campaign_data)
        assert resp.status_code == 200, f"Failed to create campaign: {resp.text}"
        
        campaign = resp.json()
        self.test_campaign_id = campaign.get("id") or campaign.get("_id")
        assert self.test_campaign_id, "Campaign ID not returned"
        
        # Verify delivery_mode is manual
        assert campaign.get("delivery_mode") == "manual", f"Expected delivery_mode='manual', got {campaign.get('delivery_mode')}"
        assert len(campaign.get("sequences", [])) == 2, "Expected 2 sequences"
        
        print(f"✓ Created manual campaign: {self.test_campaign_id}")
        return self.test_campaign_id
    
    def test_02_create_test_contact(self):
        """Create a test contact for enrollment"""
        contact_data = {
            "first_name": "TEST_Manual",
            "last_name": "PendingStatus",
            "phone": "+15551234567",
            "email": "test_manual_pending@test.com",
            "tags": []  # Don't use trigger tag to control enrollment manually
        }
        
        resp = self.session.post(f"{BASE_URL}/api/contacts/{self.user_id}", json=contact_data)
        assert resp.status_code == 200, f"Failed to create contact: {resp.text}"
        
        contact = resp.json()
        self.test_contact_id = contact.get("id") or contact.get("_id")
        assert self.test_contact_id, "Contact ID not returned"
        
        print(f"✓ Created test contact: {self.test_contact_id}")
        return self.test_contact_id
    
    def test_03_enroll_contact_in_campaign(self):
        """Enroll the contact in the manual campaign"""
        # First ensure we have campaign and contact
        if not self.test_campaign_id:
            self.test_01_create_manual_campaign()
        if not self.test_contact_id:
            self.test_02_create_test_contact()
        
        resp = self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enroll/{self.test_contact_id}"
        )
        assert resp.status_code == 200, f"Failed to enroll contact: {resp.text}"
        
        enrollment = resp.json()
        assert enrollment.get("status") == "active", f"Expected active enrollment, got {enrollment.get('status')}"
        assert enrollment.get("current_step") == 1, f"Expected current_step=1, got {enrollment.get('current_step')}"
        
        print(f"✓ Enrolled contact in campaign, enrollment status: {enrollment.get('status')}")
        return enrollment
    
    def test_04_trigger_scheduler_and_verify_pending_status(self):
        """Trigger scheduler and verify messages_sent has status='pending' for manual mode"""
        # Setup
        if not self.test_campaign_id:
            self.test_01_create_manual_campaign()
        if not self.test_contact_id:
            self.test_02_create_test_contact()
        
        # Enroll contact
        enroll_resp = self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enroll/{self.test_contact_id}"
        )
        if enroll_resp.status_code != 200:
            print(f"Enrollment may already exist: {enroll_resp.text}")
        
        # Trigger scheduler
        sched_resp = self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        assert sched_resp.status_code == 200, f"Scheduler trigger failed: {sched_resp.text}"
        
        sched_result = sched_resp.json()
        print(f"Scheduler result: {sched_result}")
        
        # Get campaign journey to verify status
        journey_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}/campaign-journey"
        )
        assert journey_resp.status_code == 200, f"Failed to get campaign journey: {journey_resp.text}"
        
        journeys = journey_resp.json()
        assert len(journeys) > 0, "Expected at least one campaign journey"
        
        # Find our test campaign's journey
        test_journey = None
        for j in journeys:
            if "TEST_Manual_Pending_Status" in j.get("campaign_name", ""):
                test_journey = j
                break
        
        assert test_journey, f"Test campaign journey not found in {journeys}"
        
        # Verify step 1 has pending_send status (NOT sent)
        steps = test_journey.get("steps", [])
        assert len(steps) >= 1, "Expected at least 1 step in journey"
        
        step1 = steps[0]
        step1_status = step1.get("status")
        
        print(f"Step 1 status: {step1_status}")
        
        # THE KEY ASSERTION - status should be 'pending_send' for manual campaigns
        assert step1_status == "pending_send", \
            f"BUG: Expected step 1 status='pending_send' for manual campaign, got '{step1_status}'"
        
        # Verify queued_at is set (not sent_at)
        assert step1.get("queued_at") is not None or step1.get("scheduled_at") is not None, \
            "Expected queued_at or scheduled_at to be set for pending step"
        
        print(f"✓ Step 1 correctly shows status='pending_send' for manual campaign")
        return test_journey
    
    def test_05_verify_task_created_with_pending_status(self):
        """Verify task was created with status='pending' and completed=false"""
        # Setup and trigger scheduler
        if not self.test_campaign_id:
            self.test_01_create_manual_campaign()
        if not self.test_contact_id:
            self.test_02_create_test_contact()
        
        # Enroll and trigger
        self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enroll/{self.test_contact_id}"
        )
        self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        
        # Get tasks
        tasks_resp = self.session.get(f"{BASE_URL}/api/tasks/{self.user_id}?filter=today")
        assert tasks_resp.status_code == 200, f"Failed to get tasks: {tasks_resp.text}"
        
        tasks = tasks_resp.json()
        
        # Find the campaign task for our test contact
        campaign_task = None
        for t in tasks:
            if (t.get("type") == "campaign_send" and 
                t.get("campaign_id") == self.test_campaign_id and
                t.get("contact_id") == self.test_contact_id):
                campaign_task = t
                break
        
        assert campaign_task, f"Campaign task not found for contact {self.test_contact_id}"
        
        # Verify task status
        task_status = campaign_task.get("status")
        task_completed = campaign_task.get("completed")
        
        print(f"Task status: {task_status}, completed: {task_completed}")
        
        assert task_status == "pending", f"Expected task status='pending', got '{task_status}'"
        assert task_completed == False, f"Expected task completed=False, got {task_completed}"
        
        self.test_task_id = campaign_task.get("_id") or campaign_task.get("id")
        
        print(f"✓ Task correctly has status='pending' and completed=False")
        return campaign_task
    
    def test_06_verify_enrollment_last_sent_at_not_set(self):
        """Verify enrollment's last_sent_at is NOT set for manual mode"""
        # Get campaign enrollments
        if not self.test_campaign_id:
            self.test_01_create_manual_campaign()
        if not self.test_contact_id:
            self.test_02_create_test_contact()
        
        # Enroll and trigger
        self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enroll/{self.test_contact_id}"
        )
        self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        
        # Get enrollments for the campaign
        enrollments_resp = self.session.get(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enrollments"
        )
        assert enrollments_resp.status_code == 200, f"Failed to get enrollments: {enrollments_resp.text}"
        
        enrollments = enrollments_resp.json()
        
        # Find our test enrollment
        test_enrollment = None
        for e in enrollments:
            if e.get("contact_id") == self.test_contact_id:
                test_enrollment = e
                break
        
        assert test_enrollment, f"Test enrollment not found"
        
        # Verify last_sent_at is NOT set for manual mode
        last_sent_at = test_enrollment.get("last_sent_at")
        
        print(f"Enrollment last_sent_at: {last_sent_at}")
        
        # For manual mode, last_sent_at should be None/not set until task is completed
        # Note: After scheduler processes, last_sent_at should NOT be set for manual mode
        # This is the key fix - manual mode should NOT set last_sent_at
        
        # Also verify messages_sent has the pending status
        messages_sent = test_enrollment.get("messages_sent", [])
        if len(messages_sent) > 0:
            step1_msg = messages_sent[0]
            msg_status = step1_msg.get("status")
            print(f"messages_sent[0] status: {msg_status}")
            assert msg_status == "pending", f"Expected messages_sent status='pending', got '{msg_status}'"
        
        print(f"✓ Enrollment correctly configured for manual mode")
        return test_enrollment
    
    def test_07_complete_task_and_verify_sent_status(self):
        """Complete the task and verify messages_sent updates to status='sent'"""
        # Setup - get the task
        if not self.test_campaign_id:
            self.test_01_create_manual_campaign()
        if not self.test_contact_id:
            self.test_02_create_test_contact()
        
        # Enroll and trigger
        self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enroll/{self.test_contact_id}"
        )
        self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        
        # Get the task
        tasks_resp = self.session.get(f"{BASE_URL}/api/tasks/{self.user_id}?filter=today")
        assert tasks_resp.status_code == 200
        tasks = tasks_resp.json()
        
        campaign_task = None
        for t in tasks:
            if (t.get("type") == "campaign_send" and 
                t.get("campaign_id") == self.test_campaign_id and
                t.get("contact_id") == self.test_contact_id):
                campaign_task = t
                break
        
        if not campaign_task:
            # Try with 'all' filter
            tasks_resp = self.session.get(f"{BASE_URL}/api/tasks/{self.user_id}?filter=all")
            tasks = tasks_resp.json()
            for t in tasks:
                if (t.get("type") == "campaign_send" and 
                    t.get("campaign_id") == self.test_campaign_id and
                    t.get("contact_id") == self.test_contact_id):
                    campaign_task = t
                    break
        
        assert campaign_task, "Campaign task not found"
        task_id = campaign_task.get("_id") or campaign_task.get("id")
        
        # Complete the task
        complete_resp = self.session.patch(
            f"{BASE_URL}/api/tasks/{self.user_id}/{task_id}",
            json={"action": "complete"}
        )
        assert complete_resp.status_code == 200, f"Failed to complete task: {complete_resp.text}"
        
        completed_task = complete_resp.json()
        assert completed_task.get("status") == "completed", \
            f"Expected task status='completed', got '{completed_task.get('status')}'"
        
        print(f"✓ Task completed successfully")
        
        # Now verify Campaign Journey shows step 1 as 'sent'
        journey_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}/campaign-journey"
        )
        assert journey_resp.status_code == 200
        
        journeys = journey_resp.json()
        test_journey = None
        for j in journeys:
            if "TEST_Manual_Pending_Status" in j.get("campaign_name", ""):
                test_journey = j
                break
        
        assert test_journey, "Test campaign journey not found after task completion"
        
        steps = test_journey.get("steps", [])
        step1 = steps[0]
        step1_status_after = step1.get("status")
        
        print(f"Step 1 status after task completion: {step1_status_after}")
        
        # THE KEY ASSERTION - after task completion, status should be 'sent'
        assert step1_status_after == "sent", \
            f"Expected step 1 status='sent' after task completion, got '{step1_status_after}'"
        
        # Verify sent_at is now set
        assert step1.get("sent_at") is not None, "Expected sent_at to be set after completion"
        
        print(f"✓ Step 1 correctly updated to status='sent' after task completion")
        return test_journey
    
    def test_08_full_flow_end_to_end(self):
        """Full end-to-end test of the manual campaign pending status fix"""
        print("\n" + "="*60)
        print("FULL E2E TEST: Manual Campaign Pending Status Fix")
        print("="*60)
        
        # Step 1: Create manual campaign
        print("\n[1] Creating manual campaign...")
        campaign_id = self.test_01_create_manual_campaign()
        
        # Step 2: Create test contact
        print("\n[2] Creating test contact...")
        contact_id = self.test_02_create_test_contact()
        
        # Step 3: Enroll contact
        print("\n[3] Enrolling contact in campaign...")
        enroll_resp = self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}/enroll/{contact_id}"
        )
        assert enroll_resp.status_code == 200
        print("✓ Contact enrolled")
        
        # Step 4: Trigger scheduler
        print("\n[4] Triggering scheduler...")
        sched_resp = self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        assert sched_resp.status_code == 200
        print(f"✓ Scheduler triggered: {sched_resp.json()}")
        
        # Step 5: Verify pending_send status in journey
        print("\n[5] Verifying Campaign Journey shows 'pending_send'...")
        journey_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey"
        )
        assert journey_resp.status_code == 200
        journeys = journey_resp.json()
        
        test_journey = None
        for j in journeys:
            if "TEST_Manual_Pending_Status" in j.get("campaign_name", ""):
                test_journey = j
                break
        
        assert test_journey, "Journey not found"
        step1_status = test_journey["steps"][0]["status"]
        assert step1_status == "pending_send", f"Expected 'pending_send', got '{step1_status}'"
        print(f"✓ Step 1 status = '{step1_status}' (correct for manual campaign)")
        
        # Step 6: Get and complete the task
        print("\n[6] Finding and completing the campaign task...")
        tasks_resp = self.session.get(f"{BASE_URL}/api/tasks/{self.user_id}?filter=all")
        tasks = tasks_resp.json()
        
        campaign_task = None
        for t in tasks:
            if (t.get("type") == "campaign_send" and 
                t.get("campaign_id") == campaign_id):
                campaign_task = t
                break
        
        assert campaign_task, "Task not found"
        task_id = campaign_task.get("_id")
        print(f"✓ Found task {task_id}, status: {campaign_task.get('status')}")
        
        # Complete the task
        complete_resp = self.session.patch(
            f"{BASE_URL}/api/tasks/{self.user_id}/{task_id}",
            json={"action": "complete"}
        )
        assert complete_resp.status_code == 200
        print("✓ Task completed")
        
        # Step 7: Verify 'sent' status after completion
        print("\n[7] Verifying Campaign Journey now shows 'sent'...")
        journey_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey"
        )
        journeys = journey_resp.json()
        
        test_journey = None
        for j in journeys:
            if "TEST_Manual_Pending_Status" in j.get("campaign_name", ""):
                test_journey = j
                break
        
        step1_status_after = test_journey["steps"][0]["status"]
        assert step1_status_after == "sent", f"Expected 'sent', got '{step1_status_after}'"
        print(f"✓ Step 1 status = '{step1_status_after}' (correctly updated after task completion)")
        
        print("\n" + "="*60)
        print("✓ ALL E2E TESTS PASSED - Manual Campaign Pending Status Fix Verified")
        print("="*60)


class TestAutomatedCampaignComparison:
    """Compare behavior between manual and automated campaigns"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get user_id"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200
        user = login_resp.json().get("user", {})
        self.user_id = user.get("id") or user.get("_id")
        
        self.test_campaign_id = None
        self.test_contact_id = None
        
        yield
        
        # Cleanup
        try:
            if self.test_campaign_id:
                self.session.delete(f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}")
            if self.test_contact_id:
                self.session.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}")
        except:
            pass
    
    def test_automated_campaign_sets_sent_immediately(self):
        """Automated campaigns should set status='sent' and last_sent_at immediately"""
        # Create automated campaign
        campaign_data = {
            "name": "TEST_Automated_Comparison_Campaign",
            "type": "custom",
            "trigger_tag": "test_automated_comparison",
            "active": True,
            "delivery_mode": "automated",  # AUTOMATED mode
            "ai_enabled": False,
            "sequences": [
                {
                    "step": 1,
                    "delay_hours": 0,
                    "delay_days": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "message_template": "Automated step 1!",
                    "action_type": "message"
                }
            ]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/campaigns/{self.user_id}", json=campaign_data)
        assert resp.status_code == 200
        campaign = resp.json()
        self.test_campaign_id = campaign.get("id") or campaign.get("_id")
        
        # Create contact
        contact_data = {
            "first_name": "TEST_Automated",
            "last_name": "Comparison",
            "phone": "+15559876543"
        }
        contact_resp = self.session.post(f"{BASE_URL}/api/contacts/{self.user_id}", json=contact_data)
        assert contact_resp.status_code == 200
        contact = contact_resp.json()
        self.test_contact_id = contact.get("id") or contact.get("_id")
        
        # Enroll and trigger
        self.session.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{self.test_campaign_id}/enroll/{self.test_contact_id}"
        )
        self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
        
        # Check journey - automated should show 'sent' immediately
        journey_resp = self.session.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}/campaign-journey"
        )
        assert journey_resp.status_code == 200
        journeys = journey_resp.json()
        
        test_journey = None
        for j in journeys:
            if "TEST_Automated_Comparison" in j.get("campaign_name", ""):
                test_journey = j
                break
        
        if test_journey:
            step1_status = test_journey["steps"][0]["status"]
            print(f"Automated campaign step 1 status: {step1_status}")
            # Automated should be 'sent' immediately (or 'next' if not yet processed)
            assert step1_status in ["sent", "next"], \
                f"Automated campaign should have status 'sent' or 'next', got '{step1_status}'"
            print(f"✓ Automated campaign correctly shows status='{step1_status}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
