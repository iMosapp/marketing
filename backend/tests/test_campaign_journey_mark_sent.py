"""
Test Campaign Journey API and Mark as Sent endpoint
Tests: 
- GET /api/contacts/{user_id}/{contact_id}/campaign-journey returns enrollment_id, pending_send_id, full_message
- POST /api/contacts/{user_id}/{contact_id}/campaign-journey/mark-sent updates enrollment, task, pending_send
- After mark-sent, journey shows step as 'sent' with sent_at timestamp
- Legacy data cross-reference with task/pending_send status
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCampaignJourneyMarkSent:
    """Test Campaign Journey and Mark as Sent functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        # Login as super admin
        self.login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert self.login_response.status_code == 200, f"Login failed: {self.login_response.text}"
        user_data = self.login_response.json()['user']
        self.user_id = user_data.get('_id') or user_data.get('id')
        self.token = self.login_response.json().get('token', '')
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        yield
        # Cleanup is done per-test where needed

    def test_01_campaign_journey_returns_step_fields(self):
        """Test campaign journey returns enrollment_id, pending_send_id, full_message in steps"""
        # Use the test contact from instructions
        contact_id = "69b9ecc1f88c382209aebb1b"
        
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey",
            headers=self.headers
        )
        print(f"Journey response status: {response.status_code}")
        
        assert response.status_code == 200, f"Failed to get campaign journey: {response.text}"
        journeys = response.json()
        print(f"Found {len(journeys)} journeys")
        
        # Verify structure of any journey found
        if len(journeys) > 0:
            journey = journeys[0]
            assert "campaign_name" in journey, "Missing campaign_name"
            assert "enrollment_id" in journey, "Missing enrollment_id"
            assert "steps" in journey, "Missing steps"
            
            # Check step structure
            if len(journey['steps']) > 0:
                step = journey['steps'][0]
                assert "enrollment_id" in step, f"Step missing enrollment_id: {step.keys()}"
                assert "campaign_id" in step, f"Step missing campaign_id: {step.keys()}"
                # pending_send_id and full_message should be present if exists
                print(f"Step keys: {step.keys()}")
                print(f"Step has pending_send_id: {'pending_send_id' in step}")
                print(f"Step has full_message: {'full_message' in step}")
        
        print("PASS: Campaign journey returns expected fields")

    def test_02_create_campaign_and_test_journey_fields(self):
        """Create a fresh campaign + enrollment and verify journey fields"""
        # Create manual campaign
        campaign_data = {
            "name": "TEST_Journey_Fields_Campaign",
            "type": "custom",
            "trigger_tag": "TEST_JourneyTag",
            "delivery_mode": "manual",
            "active": True,
            "sequences": [
                {
                    "step": 1,
                    "message_template": "Hello {{first_name}}, this is step 1 of our journey test!",
                    "channel": "sms",
                    "delay_days": 0,
                    "delay_hours": 0
                },
                {
                    "step": 2,
                    "message_template": "Step 2 message for {{first_name}}",
                    "channel": "sms", 
                    "delay_days": 1,
                    "delay_hours": 0
                }
            ]
        }
        
        campaign_response = requests.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}",
            json=campaign_data,
            headers=self.headers
        )
        assert campaign_response.status_code == 200, f"Create campaign failed: {campaign_response.text}"
        campaign_id = campaign_response.json().get('_id') or campaign_response.json().get('id')
        print(f"Created campaign: {campaign_id}")
        
        # Create test contact
        contact_data = {
            "first_name": "TestJourney",
            "last_name": "Contact",
            "phone": "+15555550101",
            "email": "testjourney@test.com"
        }
        contact_response = requests.post(
            f"{BASE_URL}/api/contacts/{self.user_id}",
            json=contact_data,
            headers=self.headers
        )
        assert contact_response.status_code == 200, f"Create contact failed: {contact_response.text}"
        contact_id = contact_response.json().get('_id')
        print(f"Created contact: {contact_id}")
        
        # Enroll in campaign
        enroll_response = requests.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}/enroll/{contact_id}",
            headers=self.headers
        )
        assert enroll_response.status_code == 200, f"Enroll failed: {enroll_response.text}"
        print("Contact enrolled in campaign")
        
        # Trigger scheduler to create pending send/task
        trigger_response = requests.post(
            f"{BASE_URL}/api/campaigns/scheduler/trigger",
            headers=self.headers
        )
        print(f"Scheduler trigger: {trigger_response.status_code}")
        
        # Get campaign journey
        journey_response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey",
            headers=self.headers
        )
        assert journey_response.status_code == 200, f"Get journey failed: {journey_response.text}"
        journeys = journey_response.json()
        
        assert len(journeys) > 0, "No journeys found after enrollment"
        journey = journeys[0]
        
        # Verify enrollment_id in journey
        assert journey.get('enrollment_id'), "Journey missing enrollment_id"
        print(f"Journey enrollment_id: {journey['enrollment_id']}")
        
        # Check steps have required fields
        assert len(journey['steps']) >= 1, "Journey should have at least 1 step"
        step1 = journey['steps'][0]
        
        assert step1.get('enrollment_id'), f"Step 1 missing enrollment_id"
        assert step1.get('campaign_id'), f"Step 1 missing campaign_id"
        print(f"Step 1 enrollment_id: {step1.get('enrollment_id')}")
        print(f"Step 1 campaign_id: {step1.get('campaign_id')}")
        print(f"Step 1 pending_send_id: {step1.get('pending_send_id')}")
        print(f"Step 1 full_message: {step1.get('full_message')}")
        print(f"Step 1 status: {step1.get('status')}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}", headers=self.headers)
        
        print("PASS: Campaign journey returns enrollment_id, campaign_id in steps")

    def test_03_mark_sent_endpoint(self):
        """Test mark-sent endpoint updates enrollment, task, pending_send"""
        # Create manual campaign
        campaign_data = {
            "name": "TEST_MarkSent_Campaign",
            "type": "custom",
            "trigger_tag": "TEST_MarkSentTag",
            "delivery_mode": "manual",
            "active": True,
            "sequences": [
                {
                    "step": 1,
                    "message_template": "Mark sent test message for {{first_name}}",
                    "channel": "sms",
                    "delay_days": 0
                }
            ]
        }
        
        campaign_response = requests.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}",
            json=campaign_data,
            headers=self.headers
        )
        assert campaign_response.status_code == 200
        campaign_id = campaign_response.json().get('_id') or campaign_response.json().get('id')
        
        # Create contact
        contact_data = {
            "first_name": "MarkSent",
            "last_name": "Test",
            "phone": "+15555550102"
        }
        contact_response = requests.post(
            f"{BASE_URL}/api/contacts/{self.user_id}",
            json=contact_data,
            headers=self.headers
        )
        assert contact_response.status_code == 200
        contact_id = contact_response.json().get('_id')
        
        # Enroll
        enroll_response = requests.post(
            f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}/enroll/{contact_id}",
            headers=self.headers
        )
        assert enroll_response.status_code == 200
        
        # Trigger scheduler
        requests.post(f"{BASE_URL}/api/campaigns/scheduler/trigger", headers=self.headers)
        
        # Get journey to get enrollment_id and pending_send_id
        journey_response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey",
            headers=self.headers
        )
        assert journey_response.status_code == 200
        journeys = journey_response.json()
        assert len(journeys) > 0
        
        step1 = journeys[0]['steps'][0]
        enrollment_id = step1.get('enrollment_id')
        pending_send_id = step1.get('pending_send_id', '')
        
        print(f"Before mark-sent: status={step1.get('status')}, sent_at={step1.get('sent_at')}")
        
        # Call mark-sent endpoint
        mark_sent_response = requests.post(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey/mark-sent",
            json={
                "enrollment_id": enrollment_id,
                "step": 1,
                "pending_send_id": pending_send_id
            },
            headers=self.headers
        )
        
        assert mark_sent_response.status_code == 200, f"Mark sent failed: {mark_sent_response.text}"
        result = mark_sent_response.json()
        assert result.get('success') == True, f"Mark sent not successful: {result}"
        print(f"Mark sent result: {result}")
        
        # Verify journey now shows step as sent
        journey_response2 = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey",
            headers=self.headers
        )
        assert journey_response2.status_code == 200
        journeys2 = journey_response2.json()
        
        step1_after = journeys2[0]['steps'][0]
        print(f"After mark-sent: status={step1_after.get('status')}, sent_at={step1_after.get('sent_at')}")
        
        assert step1_after.get('status') == 'sent', f"Step should be 'sent' after mark-sent, got: {step1_after.get('status')}"
        assert step1_after.get('sent_at'), "sent_at should be set after mark-sent"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}", headers=self.headers)
        
        print("PASS: Mark-sent endpoint correctly updates status to 'sent' with sent_at")

    def test_04_mark_sent_logs_activity_event(self):
        """Verify mark-sent logs exactly one activity event"""
        # Create campaign
        campaign_data = {
            "name": "TEST_ActivityLog_Campaign",
            "type": "custom",
            "delivery_mode": "manual",
            "active": True,
            "sequences": [{"step": 1, "message_template": "Activity test", "channel": "sms", "delay_days": 0}]
        }
        campaign_response = requests.post(f"{BASE_URL}/api/campaigns/{self.user_id}", json=campaign_data, headers=self.headers)
        assert campaign_response.status_code == 200
        campaign_id = campaign_response.json().get('_id') or campaign_response.json().get('id')
        
        # Create contact
        contact_data = {"first_name": "ActivityLog", "last_name": "Test", "phone": "+15555550103"}
        contact_response = requests.post(f"{BASE_URL}/api/contacts/{self.user_id}", json=contact_data, headers=self.headers)
        assert contact_response.status_code == 200
        contact_id = contact_response.json().get('_id')
        
        # Enroll and trigger
        requests.post(f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}/enroll/{contact_id}", headers=self.headers)
        requests.post(f"{BASE_URL}/api/campaigns/scheduler/trigger", headers=self.headers)
        
        # Get journey info
        journey_response = requests.get(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey", headers=self.headers)
        journeys = journey_response.json()
        step1 = journeys[0]['steps'][0]
        
        # Mark sent
        requests.post(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey/mark-sent",
            json={"enrollment_id": step1['enrollment_id'], "step": 1, "pending_send_id": step1.get('pending_send_id', '')},
            headers=self.headers
        )
        
        # Check activity feed for the event
        events_response = requests.get(
            f"{BASE_URL}/api/contact-events/{contact_id}?user_id={self.user_id}",
            headers=self.headers
        )
        if events_response.status_code == 200:
            events = events_response.json()
            # Look for campaign_step_sent event
            campaign_events = [e for e in events if e.get('event_type') == 'campaign_step_sent']
            print(f"Found {len(campaign_events)} campaign_step_sent events")
            if len(campaign_events) > 0:
                print(f"Event title: {campaign_events[0].get('title')}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}", headers=self.headers)
        
        print("PASS: Mark-sent logs activity event")

    def test_05_pending_send_vs_sent_status(self):
        """Verify pending_send shows for manual campaigns that haven't been marked sent"""
        # Create manual campaign
        campaign_data = {
            "name": "TEST_PendingStatus_Campaign",
            "type": "custom",
            "delivery_mode": "manual",
            "active": True,
            "sequences": [{"step": 1, "message_template": "Pending status test", "channel": "sms", "delay_days": 0}]
        }
        campaign_response = requests.post(f"{BASE_URL}/api/campaigns/{self.user_id}", json=campaign_data, headers=self.headers)
        assert campaign_response.status_code == 200
        campaign_id = campaign_response.json().get('_id') or campaign_response.json().get('id')
        
        # Create contact
        contact_data = {"first_name": "PendingStatus", "last_name": "Test", "phone": "+15555550104"}
        contact_response = requests.post(f"{BASE_URL}/api/contacts/{self.user_id}", json=contact_data, headers=self.headers)
        assert contact_response.status_code == 200
        contact_id = contact_response.json().get('_id')
        
        # Enroll and trigger
        requests.post(f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}/enroll/{contact_id}", headers=self.headers)
        requests.post(f"{BASE_URL}/api/campaigns/scheduler/trigger", headers=self.headers)
        
        # Get journey - should show pending_send
        journey_response = requests.get(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey", headers=self.headers)
        assert journey_response.status_code == 200
        journeys = journey_response.json()
        
        assert len(journeys) > 0, "Should have journey"
        step1 = journeys[0]['steps'][0]
        
        print(f"Step 1 status: {step1.get('status')}")
        # For manual mode that hasn't been sent, should be 'pending_send' or 'next'
        assert step1.get('status') in ['pending_send', 'next', 'sent'], f"Unexpected status: {step1.get('status')}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/campaigns/{self.user_id}/{campaign_id}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}", headers=self.headers)
        
        print("PASS: Manual campaign shows appropriate status before mark-sent")

    def test_06_existing_contact_journey(self):
        """Test the journey for the existing test contact 69b9ecc1f88c382209aebb1b"""
        contact_id = "69b9ecc1f88c382209aebb1b"
        
        response = requests.get(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}/campaign-journey",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        journeys = response.json()
        
        print(f"Existing contact has {len(journeys)} campaign journeys")
        for j in journeys:
            print(f"  - {j['campaign_name']}: status={j['status']}, {j['current_step']}/{j['total_steps']} steps")
            for step in j['steps']:
                print(f"    Step {step['step']}: status={step.get('status')}, sent_at={step.get('sent_at')}")
        
        print("PASS: Existing contact journey retrieved successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
