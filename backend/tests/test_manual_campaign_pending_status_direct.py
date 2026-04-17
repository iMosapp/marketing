"""
Test: Manual Campaign Pending Status Fix - Database Direct Testing

This test directly manipulates the database to ensure reliable testing
of the manual campaign pending status fix.

Bug Fix Verification:
- For MANUAL campaigns, scheduler should mark messages_sent with status='pending' (not 'sent')
- last_sent_at should NOT be set for manual mode enrollments
- Campaign task should have status='pending' and completed=false
- When task is completed via PATCH, messages_sent should update to status='sent'
- Campaign Journey API should return 'pending_send' for pending manual steps

Endpoints tested:
- POST /api/campaigns/scheduler/trigger - Process enrollments
- GET /api/contacts/{user_id}/{contact_id}/campaign-journey - Get journey with statuses
- GET /api/tasks/{user_id} - Get tasks for user
- PATCH /api/tasks/{user_id}/{task_id} - Complete task
"""

import os
import pytest
import requests
import os
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

# Use motor for async MongoDB operations
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    pytest.skip("motor not installed", allow_module_level=True)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "imos-admin-test_database"

# Test credentials
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


def get_event_loop():
    """Get or create an event loop for async operations."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


class TestManualCampaignPendingStatusDirect:
    """Direct database tests for manual campaign pending status fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and initialize database connection"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get user_id
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        user = login_resp.json().get("user", {})
        self.user_id = user.get("id") or user.get("_id")
        assert self.user_id, f"Failed to get user_id from login"
        
        # Initialize MongoDB client
        self.loop = get_event_loop()
        self.mongo_client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.mongo_client[DB_NAME]
        
        # Test data storage
        self.test_campaign_id = None
        self.test_contact_id = None
        self.test_enrollment_id = None
        
        yield
        
        # Cleanup
        self._cleanup()
    
    def _cleanup(self):
        """Cleanup test data"""
        async def do_cleanup():
            try:
                if self.test_campaign_id:
                    await self.db.campaigns.delete_one({"_id": ObjectId(self.test_campaign_id)})
                if self.test_contact_id:
                    await self.db.contacts.delete_one({"_id": ObjectId(self.test_contact_id)})
                if self.test_enrollment_id:
                    await self.db.campaign_enrollments.delete_one({"_id": ObjectId(self.test_enrollment_id)})
                if self.test_campaign_id:
                    await self.db.tasks.delete_many({"campaign_id": self.test_campaign_id})
                    await self.db.campaign_pending_sends.delete_many({"campaign_id": self.test_campaign_id})
                    await self.db.notifications.delete_many({"campaign_id": self.test_campaign_id})
            except Exception as e:
                print(f"Cleanup error (non-fatal): {e}")
        
        try:
            self.loop.run_until_complete(do_cleanup())
        except:
            pass
    
    def test_manual_campaign_pending_status_full_flow(self):
        """
        Full end-to-end test of manual campaign pending status fix.
        
        This test directly creates campaign, contact, and enrollment in the database
        with a past next_send_at to ensure the scheduler will process it.
        """
        async def run_test():
            now = datetime.now(timezone.utc)
            past = now - timedelta(minutes=5)  # 5 minutes in the past
            
            # Step 1: Create a manual campaign
            print("\n[1] Creating manual campaign...")
            campaign_data = {
                "name": "TEST_Pending_Status_Direct",
                "type": "custom",
                "trigger_tag": "test_pending_direct",
                "active": True,
                "delivery_mode": "manual",
                "ai_enabled": False,
                "user_id": self.user_id,
                "created_at": now,
                "sequences": [
                    {
                        "step": 1,
                        "delay_hours": 0,
                        "delay_days": 0,
                        "delay_months": 0,
                        "channel": "sms",
                        "message_template": "Step 1: Immediate!",
                        "action_type": "message"
                    },
                    {
                        "step": 2,
                        "delay_hours": 0,
                        "delay_days": 1,
                        "delay_months": 0,
                        "channel": "sms",
                        "message_template": "Step 2: Follow-up!",
                        "action_type": "message"
                    }
                ]
            }
            result = await self.db.campaigns.insert_one(campaign_data)
            self.test_campaign_id = str(result.inserted_id)
            print(f"    Campaign ID: {self.test_campaign_id}")
            
            # Step 2: Create a test contact
            print("\n[2] Creating test contact...")
            contact_data = {
                "first_name": "TEST_Direct",
                "last_name": "Pending",
                "phone": "+15557778888",
                "email": "test_direct_pending@test.com",
                "user_id": self.user_id,
                "original_user_id": self.user_id,
                "created_at": now,
                "tags": []
            }
            result = await self.db.contacts.insert_one(contact_data)
            self.test_contact_id = str(result.inserted_id)
            print(f"    Contact ID: {self.test_contact_id}")
            
            # Step 3: Create enrollment with next_send_at in the PAST
            print("\n[3] Creating enrollment with past next_send_at...")
            enrollment_data = {
                "user_id": self.user_id,
                "campaign_id": self.test_campaign_id,
                "campaign_name": "TEST_Pending_Status_Direct",
                "contact_id": self.test_contact_id,
                "contact_name": "TEST_Direct Pending",
                "contact_phone": "+15557778888",
                "current_step": 1,
                "total_steps": 2,
                "status": "active",
                "enrolled_at": past,
                "next_send_at": past,  # In the past so scheduler will process
                "messages_sent": []
            }
            result = await self.db.campaign_enrollments.insert_one(enrollment_data)
            self.test_enrollment_id = str(result.inserted_id)
            print(f"    Enrollment ID: {self.test_enrollment_id}")
            print(f"    next_send_at: {past}")
            
            # Step 4: Trigger the scheduler
            print("\n[4] Triggering scheduler...")
            resp = self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
            assert resp.status_code == 200, f"Scheduler failed: {resp.text}"
            sched_result = resp.json()
            print(f"    Scheduler: {sched_result}")
            
            # Verify scheduler processed our enrollment
            assert sched_result.get("processed", 0) >= 1, \
                f"Scheduler didn't process enrollment: {sched_result}"
            
            # Step 5: Check enrollment after scheduler
            print("\n[5] Checking enrollment after scheduler...")
            enrollment = await self.db.campaign_enrollments.find_one(
                {"_id": ObjectId(self.test_enrollment_id)}
            )
            assert enrollment, "Enrollment not found after scheduler"
            
            print(f"    current_step: {enrollment.get('current_step')}")
            print(f"    last_sent_at: {enrollment.get('last_sent_at')}")
            
            # Check messages_sent
            messages_sent = enrollment.get("messages_sent", [])
            assert len(messages_sent) > 0, "No messages_sent entries after scheduler"
            
            step1_msg = messages_sent[0]
            print(f"\n    messages_sent[0]:")
            print(f"      step: {step1_msg.get('step')}")
            print(f"      status: {step1_msg.get('status')}")
            print(f"      queued_at: {step1_msg.get('queued_at')}")
            print(f"      sent_at: {step1_msg.get('sent_at')}")
            
            # KEY ASSERTION 1: status should be 'pending' for manual mode
            assert step1_msg.get('status') == 'pending', \
                f"Expected status='pending', got '{step1_msg.get('status')}'"
            print("    ✅ messages_sent status is 'pending' (correct)")
            
            # KEY ASSERTION 2: sent_at should NOT be set
            assert step1_msg.get('sent_at') is None, \
                f"sent_at should be None for pending, got {step1_msg.get('sent_at')}"
            print("    ✅ sent_at is not set (correct)")
            
            # KEY ASSERTION 3: queued_at SHOULD be set
            assert step1_msg.get('queued_at') is not None, \
                "queued_at should be set for pending"
            print("    ✅ queued_at is set (correct)")
            
            # KEY ASSERTION 4: last_sent_at should NOT be set for manual mode
            assert enrollment.get('last_sent_at') is None, \
                f"last_sent_at should be None for manual mode, got {enrollment.get('last_sent_at')}"
            print("    ✅ last_sent_at is not set (correct for manual mode)")
            
            # Step 6: Check Campaign Journey API
            print("\n[6] Checking Campaign Journey API...")
            resp = self.session.get(
                f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}/campaign-journey"
            )
            assert resp.status_code == 200, f"Journey API failed: {resp.text}"
            journeys = resp.json()
            
            test_journey = None
            for j in journeys:
                if "TEST_Pending_Status_Direct" in j.get("campaign_name", ""):
                    test_journey = j
                    break
            
            assert test_journey, f"Test journey not found in {journeys}"
            
            step1 = test_journey["steps"][0]
            print(f"    Step 1 status: {step1.get('status')}")
            
            # KEY ASSERTION 5: Journey should show 'pending_send'
            assert step1.get('status') == 'pending_send', \
                f"Expected journey status='pending_send', got '{step1.get('status')}'"
            print("    ✅ Journey shows 'pending_send' (correct)")
            
            # Step 7: Check task creation
            print("\n[7] Checking task creation...")
            task = await self.db.tasks.find_one({
                "campaign_id": self.test_campaign_id,
                "contact_id": self.test_contact_id,
                "type": "campaign_send"
            })
            assert task, "Task not created for campaign step"
            
            print(f"    Task title: {task.get('title')}")
            print(f"    Task status: {task.get('status')}")
            print(f"    Task completed: {task.get('completed')}")
            
            # KEY ASSERTION 6: Task should be pending
            assert task.get('status') == 'pending', \
                f"Expected task status='pending', got '{task.get('status')}'"
            assert task.get('completed') == False, \
                f"Expected completed=False, got {task.get('completed')}"
            print("    ✅ Task is pending and not completed (correct)")
            
            # Step 8: Complete the task
            print("\n[8] Completing the task...")
            task_id = str(task["_id"])
            resp = self.session.patch(
                f"{BASE_URL}/api/tasks/{self.user_id}/{task_id}",
                json={"action": "complete"}
            )
            assert resp.status_code == 200, f"Task completion failed: {resp.text}"
            print("    Task completed successfully")
            
            # Step 9: Check enrollment after task completion
            print("\n[9] Checking enrollment after task completion...")
            enrollment = await self.db.campaign_enrollments.find_one(
                {"_id": ObjectId(self.test_enrollment_id)}
            )
            messages_sent = enrollment.get("messages_sent", [])
            step1_msg = messages_sent[0]
            
            print(f"    messages_sent[0] status: {step1_msg.get('status')}")
            print(f"    messages_sent[0] sent_at: {step1_msg.get('sent_at')}")
            
            # KEY ASSERTION 7: After completion, status should be 'sent'
            assert step1_msg.get('status') == 'sent', \
                f"After completion, expected status='sent', got '{step1_msg.get('status')}'"
            print("    ✅ After completion, status is 'sent' (correct)")
            
            # KEY ASSERTION 8: sent_at should now be set
            assert step1_msg.get('sent_at') is not None, \
                "After completion, sent_at should be set"
            print("    ✅ sent_at is now set (correct)")
            
            # Step 10: Check Journey after completion
            print("\n[10] Checking Journey API after task completion...")
            resp = self.session.get(
                f"{BASE_URL}/api/contacts/{self.user_id}/{self.test_contact_id}/campaign-journey"
            )
            journeys = resp.json()
            test_journey = None
            for j in journeys:
                if "TEST_Pending_Status_Direct" in j.get("campaign_name", ""):
                    test_journey = j
                    break
            
            step1 = test_journey["steps"][0]
            print(f"    Step 1 status after completion: {step1.get('status')}")
            
            # KEY ASSERTION 9: Journey should now show 'sent'
            assert step1.get('status') == 'sent', \
                f"After completion, expected journey status='sent', got '{step1.get('status')}'"
            print("    ✅ Journey now shows 'sent' (correct)")
            
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED - Manual Campaign Pending Status Fix Verified")
            print("=" * 60)
        
        self.loop.run_until_complete(run_test())
    
    def test_automated_campaign_comparison(self):
        """
        Compare behavior: automated campaigns should set status='sent' immediately.
        """
        async def run_test():
            now = datetime.now(timezone.utc)
            past = now - timedelta(minutes=5)
            
            # Create an AUTOMATED campaign
            print("\n[1] Creating automated campaign...")
            campaign_data = {
                "name": "TEST_Automated_Comparison",
                "type": "custom",
                "trigger_tag": "test_automated_comp",
                "active": True,
                "delivery_mode": "automated",  # AUTOMATED mode
                "ai_enabled": False,
                "user_id": self.user_id,
                "created_at": now,
                "sequences": [
                    {
                        "step": 1,
                        "delay_hours": 0,
                        "delay_days": 0,
                        "delay_months": 0,
                        "channel": "sms",
                        "message_template": "Automated step!",
                        "action_type": "message"
                    }
                ]
            }
            result = await self.db.campaigns.insert_one(campaign_data)
            self.test_campaign_id = str(result.inserted_id)
            
            # Create contact
            contact_data = {
                "first_name": "TEST_Auto",
                "last_name": "Comparison",
                "phone": "+15556667777",
                "user_id": self.user_id,
                "original_user_id": self.user_id,
                "created_at": now,
                "tags": []
            }
            result = await self.db.contacts.insert_one(contact_data)
            self.test_contact_id = str(result.inserted_id)
            
            # Create enrollment
            enrollment_data = {
                "user_id": self.user_id,
                "campaign_id": self.test_campaign_id,
                "campaign_name": "TEST_Automated_Comparison",
                "contact_id": self.test_contact_id,
                "contact_name": "TEST_Auto Comparison",
                "contact_phone": "+15556667777",
                "current_step": 1,
                "status": "active",
                "enrolled_at": past,
                "next_send_at": past,
                "messages_sent": []
            }
            result = await self.db.campaign_enrollments.insert_one(enrollment_data)
            self.test_enrollment_id = str(result.inserted_id)
            
            # Trigger scheduler
            print("\n[2] Triggering scheduler...")
            resp = self.session.post(f"{BASE_URL}/api/campaigns/scheduler/trigger")
            assert resp.status_code == 200
            print(f"    Scheduler: {resp.json()}")
            
            # Check enrollment
            print("\n[3] Checking automated enrollment...")
            enrollment = await self.db.campaign_enrollments.find_one(
                {"_id": ObjectId(self.test_enrollment_id)}
            )
            
            messages_sent = enrollment.get("messages_sent", [])
            if messages_sent:
                step1_msg = messages_sent[0]
                print(f"    status: {step1_msg.get('status')}")
                print(f"    sent_at: {step1_msg.get('sent_at')}")
                
                # For automated mode: status should be 'sent' immediately
                assert step1_msg.get('status') == 'sent', \
                    f"Automated should have status='sent', got '{step1_msg.get('status')}'"
                print("    ✅ Automated campaign correctly has status='sent'")
                
                # sent_at should be set
                assert step1_msg.get('sent_at') is not None, \
                    "Automated should have sent_at set"
                print("    ✅ sent_at is set for automated campaign")
            
            # last_sent_at SHOULD be set for automated mode
            assert enrollment.get('last_sent_at') is not None, \
                "Automated should have last_sent_at set"
            print("    ✅ last_sent_at is set for automated campaign")
        
        self.loop.run_until_complete(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
