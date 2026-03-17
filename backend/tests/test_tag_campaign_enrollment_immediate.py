"""
Test campaign enrollment auto-trigger via tag application.
Tests the fix where applying a tag to a contact immediately enrolls them in 
matching campaigns AND creates a task/pending_send for step 1 if delay=0.

User story: User creates a campaign called 'Onboarding Videos' triggered by 'New Customer' tag.
When they apply the tag to a contact, the campaign should immediately enroll the contact
and create a touchpoint task in 'Today's Touchpoints' on the home screen.
"""
import pytest
import requests
import os
from datetime import datetime, timedelta
from bson import ObjectId

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"

class TestTagCampaignEnrollmentImmediate:
    """Test the immediate campaign enrollment + task creation when a tag is applied"""
    
    created_campaign_id = None
    created_contact_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Setup and teardown for each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
        # Cleanup will be done in teardown_class

    @classmethod
    def teardown_class(cls):
        """Cleanup all test data after tests complete"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Cleanup test campaign
        if cls.created_campaign_id:
            try:
                session.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{cls.created_campaign_id}")
                print(f"Cleaned up test campaign: {cls.created_campaign_id}")
            except:
                pass
        
        # Cleanup test contact
        if cls.created_contact_id:
            try:
                session.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{cls.created_contact_id}")
                print(f"Cleaned up test contact: {cls.created_contact_id}")
            except:
                pass
        
        # Cleanup any enrollments, pending_sends, tasks, notifications with "TestAutoTag" prefix
        # This will need MongoDB direct cleanup via a test cleanup endpoint or manual cleanup
        print("Note: Some test data (enrollments, pending_sends, tasks) may need manual cleanup")

    def test_01_create_campaign_with_immediate_trigger(self):
        """
        Create a campaign with:
        - trigger_tag='TestAutoTag'
        - 3 sequences: step 1 (delay_hours=0), step 2 (delay_hours=1), step 3 (delay_hours=1)
        - active=true
        - delivery_mode='manual'
        """
        campaign_data = {
            "name": "TEST_Immediate Enrollment Campaign",
            "type": "custom",
            "trigger_tag": "TestAutoTag",
            "active": True,
            "delivery_mode": "manual",
            "ai_enabled": False,
            "sequences": [
                {
                    "step": 1,
                    "delay_hours": 0,
                    "delay_days": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "action_type": "message",
                    "message_template": "Welcome! This is step 1 - immediate send."
                },
                {
                    "step": 2,
                    "delay_hours": 1,
                    "delay_days": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "action_type": "message",
                    "message_template": "This is step 2 - 1 hour delay."
                },
                {
                    "step": 3,
                    "delay_hours": 1,
                    "delay_days": 0,
                    "delay_months": 0,
                    "channel": "sms",
                    "action_type": "message",
                    "message_template": "This is step 3 - another 1 hour delay."
                }
            ]
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/campaigns/{USER_ID}",
            json=campaign_data
        )
        
        assert response.status_code in [200, 201], f"Failed to create campaign: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Campaign should have _id"
        assert data.get("name") == "TEST_Immediate Enrollment Campaign"
        assert data.get("trigger_tag") == "TestAutoTag"
        assert data.get("active") == True
        assert data.get("delivery_mode") == "manual"
        assert len(data.get("sequences", [])) == 3
        
        # Verify sequence delays
        sequences = data.get("sequences", [])
        assert sequences[0].get("delay_hours") == 0, "Step 1 should have delay_hours=0"
        assert sequences[1].get("delay_hours") == 1, "Step 2 should have delay_hours=1"
        assert sequences[2].get("delay_hours") == 1, "Step 3 should have delay_hours=1"
        
        TestTagCampaignEnrollmentImmediate.created_campaign_id = data["_id"]
        print(f"Created campaign with ID: {data['_id']}")
    
    def test_02_create_test_contact_without_tag(self):
        """Create a test contact without the trigger tag initially"""
        contact_data = {
            "first_name": "TEST_TagEnroll",
            "last_name": "AutoTest",
            "phone": "+15551234567",
            "email": "test_tagenroll@example.com",
            "tags": []  # No tags initially
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json=contact_data
        )
        
        assert response.status_code in [200, 201], f"Failed to create contact: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Contact should have _id"
        assert data.get("first_name") == "TEST_TagEnroll"
        
        TestTagCampaignEnrollmentImmediate.created_contact_id = data["_id"]
        print(f"Created contact with ID: {data['_id']}")
    
    def test_03_apply_tag_triggers_enrollment_and_task(self):
        """
        Apply 'TestAutoTag' tag to the contact.
        Verify:
        - Campaign enrollment is created
        - current_step=2 (step 1 already processed)
        - A task was created with type='campaign_send' and source='campaign'
        - A campaign_pending_sends document was created for step 1
        """
        contact_id = TestTagCampaignEnrollmentImmediate.created_contact_id
        assert contact_id, "Contact ID should be set from previous test"
        
        # Apply the tag using PATCH /api/contacts/{user_id}/{contact_id}/tags
        tag_data = {"tags": ["TestAutoTag"]}
        
        response = self.session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}/tags",
            json=tag_data
        )
        
        assert response.status_code == 200, f"Failed to apply tag: {response.text}"
        
        data = response.json()
        assert "TestAutoTag" in data.get("tags", []), "Tag should be applied to contact"
        print(f"Applied tag to contact: {data}")
    
    def test_04_verify_enrollment_created_with_step_2(self):
        """Verify campaign enrollment was created with current_step=2"""
        campaign_id = TestTagCampaignEnrollmentImmediate.created_campaign_id
        contact_id = TestTagCampaignEnrollmentImmediate.created_contact_id
        
        assert campaign_id, "Campaign ID should be set"
        assert contact_id, "Contact ID should be set"
        
        # Get enrollments for the campaign
        response = self.session.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enrollments"
        )
        
        assert response.status_code == 200, f"Failed to get enrollments: {response.text}"
        
        enrollments = response.json()
        
        # Find our enrollment
        matching_enrollment = None
        for enrollment in enrollments:
            if enrollment.get("contact_id") == contact_id:
                matching_enrollment = enrollment
                break
        
        assert matching_enrollment is not None, "Enrollment should exist for our contact"
        
        # Verify enrollment details
        assert matching_enrollment.get("status") == "active", "Enrollment should be active"
        assert matching_enrollment.get("current_step") == 2, \
            f"current_step should be 2 (step 1 already processed), got {matching_enrollment.get('current_step')}"
        assert matching_enrollment.get("trigger_type") == "tag", "trigger_type should be 'tag'"
        assert matching_enrollment.get("trigger_tag") == "TestAutoTag", "trigger_tag should be 'TestAutoTag'"
        
        # Verify messages_sent includes step 1
        messages_sent = matching_enrollment.get("messages_sent", [])
        assert len(messages_sent) >= 1, "Step 1 should be recorded in messages_sent"
        assert messages_sent[0].get("step") == 1, "First message_sent should be step 1"
        
        # Verify next_send_at is approximately 1 hour in the future (for step 2)
        next_send_at_str = matching_enrollment.get("next_send_at")
        if next_send_at_str:
            if isinstance(next_send_at_str, str):
                # Parse ISO format
                next_send_at = datetime.fromisoformat(next_send_at_str.replace('Z', '+00:00'))
            else:
                next_send_at = next_send_at_str
            
            now = datetime.utcnow()
            expected_min = now + timedelta(minutes=50)  # Allow some tolerance
            expected_max = now + timedelta(hours=1, minutes=10)
            
            # Convert to comparable format
            if next_send_at.tzinfo:
                next_send_at = next_send_at.replace(tzinfo=None)
            
            print(f"next_send_at: {next_send_at}, now: {now}")
            assert expected_min <= next_send_at <= expected_max, \
                f"next_send_at ({next_send_at}) should be ~1 hour from now"
        
        print(f"Enrollment verified: {matching_enrollment}")
    
    def test_05_verify_task_created_for_step_1(self):
        """Verify a task was created with type='campaign_send' and source='campaign' for step 1"""
        contact_id = TestTagCampaignEnrollmentImmediate.created_contact_id
        campaign_id = TestTagCampaignEnrollmentImmediate.created_campaign_id
        
        assert contact_id, "Contact ID should be set"
        assert campaign_id, "Campaign ID should be set"
        
        # Get today's tasks for the user
        response = self.session.get(
            f"{BASE_URL}/api/tasks/{USER_ID}?filter=today"
        )
        
        assert response.status_code == 200, f"Failed to get tasks: {response.text}"
        
        tasks = response.json()
        
        # Find our task
        matching_task = None
        for task in tasks:
            if (task.get("contact_id") == contact_id and 
                task.get("type") == "campaign_send" and 
                task.get("source") == "campaign" and
                task.get("campaign_id") == campaign_id):
                matching_task = task
                break
        
        assert matching_task is not None, \
            f"Task should exist for contact {contact_id} with type='campaign_send' and source='campaign'"
        
        # Verify task details
        assert matching_task.get("status") == "pending", "Task should be pending"
        assert matching_task.get("channel") == "sms", "Task channel should be sms"
        assert "pending_send_id" in matching_task, "Task should have pending_send_id"
        assert "TEST_TagEnroll" in matching_task.get("title", "") or "TEST_TagEnroll" in matching_task.get("contact_name", ""), \
            "Task should reference our test contact"
        
        print(f"Task verified: {matching_task}")
    
    def test_06_verify_pending_send_created_for_step_1(self):
        """Verify a campaign_pending_sends document was created for step 1"""
        # Get pending sends for the user
        response = self.session.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends"
        )
        
        assert response.status_code == 200, f"Failed to get pending sends: {response.text}"
        
        pending_sends = response.json()
        
        contact_id = TestTagCampaignEnrollmentImmediate.created_contact_id
        campaign_id = TestTagCampaignEnrollmentImmediate.created_campaign_id
        
        # Find our pending send
        matching_pending = None
        for pending in pending_sends:
            if (pending.get("contact_id") == contact_id and 
                pending.get("campaign_id") == campaign_id and
                pending.get("step") == 1):
                matching_pending = pending
                break
        
        assert matching_pending is not None, \
            f"Pending send should exist for contact {contact_id}, campaign {campaign_id}, step 1"
        
        # Verify pending send details
        assert matching_pending.get("status") == "pending", "Pending send should be pending"
        assert matching_pending.get("action_type") == "message", "Action type should be message"
        assert matching_pending.get("channel") == "sms", "Channel should be sms"
        assert "Welcome" in matching_pending.get("message", "") or "step 1" in matching_pending.get("message", "").lower(), \
            "Pending send should contain step 1 message"
        
        print(f"Pending send verified: {matching_pending}")
    
    def test_07_no_duplicate_enrollment_on_reapply_tag(self):
        """Verify no duplicate enrollment if the same tag is applied twice to the same contact"""
        contact_id = TestTagCampaignEnrollmentImmediate.created_contact_id
        campaign_id = TestTagCampaignEnrollmentImmediate.created_campaign_id
        
        assert contact_id, "Contact ID should be set"
        assert campaign_id, "Campaign ID should be set"
        
        # Get enrollment count before
        response_before = self.session.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enrollments"
        )
        enrollments_before = response_before.json()
        count_before = len([e for e in enrollments_before if e.get("contact_id") == contact_id])
        
        # Re-apply the same tag
        tag_data = {"tags": ["TestAutoTag", "AnotherTag"]}  # Re-applying with same tag plus another
        
        response = self.session.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}/tags",
            json=tag_data
        )
        
        assert response.status_code == 200, f"Failed to apply tag: {response.text}"
        
        # Get enrollment count after
        response_after = self.session.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enrollments"
        )
        enrollments_after = response_after.json()
        count_after = len([e for e in enrollments_after if e.get("contact_id") == contact_id])
        
        # Should be the same count - no duplicate enrollment
        assert count_after == count_before, \
            f"Should not create duplicate enrollment. Before: {count_before}, After: {count_after}"
        
        print(f"No duplicate enrollment confirmed. Count: {count_after}")
    
    def test_08_duplicate_campaign_still_works(self):
        """Verify POST /api/campaigns/{user_id}/{campaign_id}/duplicate works correctly"""
        campaign_id = TestTagCampaignEnrollmentImmediate.created_campaign_id
        
        assert campaign_id, "Campaign ID should be set"
        
        response = self.session.post(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/duplicate"
        )
        
        assert response.status_code in [200, 201], f"Failed to duplicate campaign: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Duplicated campaign should have _id"
        assert data.get("_id") != campaign_id, "Duplicated campaign should have different ID"
        assert "(Copy)" in data.get("name", ""), "Duplicated campaign name should contain '(Copy)'"
        assert data.get("active") == False, "Duplicated campaign should start paused"
        assert data.get("trigger_tag") == "TestAutoTag", "Duplicated campaign should keep trigger_tag"
        assert len(data.get("sequences", [])) == 3, "Duplicated campaign should keep all sequences"
        
        # Cleanup the duplicated campaign
        dup_id = data["_id"]
        try:
            self.session.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{dup_id}")
            print(f"Cleaned up duplicated campaign: {dup_id}")
        except:
            pass
        
        print(f"Duplicate campaign verified: {data['name']}")


class TestCleanup:
    """Cleanup any leftover test data"""
    
    def test_cleanup_test_campaigns_and_contacts(self):
        """Clean up any test data with TEST_ prefix"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Get and cleanup test campaigns
        try:
            response = session.get(f"{BASE_URL}/api/campaigns/{USER_ID}")
            if response.status_code == 200:
                campaigns = response.json()
                for campaign in campaigns:
                    if campaign.get("name", "").startswith("TEST_"):
                        try:
                            session.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign['_id']}")
                            print(f"Cleaned up campaign: {campaign['name']}")
                        except:
                            pass
        except:
            pass
        
        # Get and cleanup test contacts
        try:
            response = session.get(f"{BASE_URL}/api/contacts/{USER_ID}")
            if response.status_code == 200:
                contacts = response.json()
                for contact in contacts:
                    first_name = contact.get("first_name", "")
                    if first_name.startswith("TEST_"):
                        try:
                            session.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact['_id']}")
                            print(f"Cleaned up contact: {first_name}")
                        except:
                            pass
        except:
            pass
        
        print("Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
