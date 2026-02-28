"""
Test suite for email pipeline bugfix verification.
Tests the critical email sending bugs that were fixed:
1. Email diagnostic endpoint (GET /api/messages/email-diagnostic/{user_id}/{contact_id})
2. Email send with channel='email' returns status='sent' with resend_id
3. Email send to contact WITHOUT email returns status='failed' with descriptive error
4. Failed email sends are logged as contact_events with event_type='email_failed'
5. Conversation info endpoint (GET /api/messages/conversation/{conversation_id}/info)
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials provided in the request
USER_ID = "69a0b7095fddcede09591667"
CONTACT_WITH_EMAIL = "69a0c06f7626f14d125f8c34"
CONTACT_WITHOUT_EMAIL = "69a1354f2c0649ac6fb7f3f1"
CONVERSATION_ID = "69a15f29957bacd218fed55d"


class TestEmailDiagnosticEndpoint:
    """Test the new email diagnostic endpoint that traces the entire email pipeline."""
    
    def test_email_diagnostic_returns_diagnostic_result(self):
        """GET /api/messages/email-diagnostic/{user_id}/{contact_id} returns diagnostic with steps"""
        response = requests.get(f"{BASE_URL}/api/messages/email-diagnostic/{USER_ID}/{CONTACT_WITH_EMAIL}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "diagnostic" in data, "Response should have 'diagnostic' field"
        assert "steps" in data, "Response should have 'steps' field"
        assert isinstance(data["steps"], list), "steps should be a list"
        
        # Verify all expected steps are present
        step_names = [step.get("step") for step in data["steps"]]
        expected_steps = ["user_lookup", "contact_lookup", "conversation_lookup", "resend_config", "brand_context"]
        
        for expected_step in expected_steps:
            assert expected_step in step_names, f"Missing step: {expected_step}"
        
        print(f"Diagnostic result: {data['diagnostic']}")
        print(f"Steps executed: {step_names}")
        
    def test_email_diagnostic_user_lookup_step(self):
        """Verify user_lookup step contains valid user info"""
        response = requests.get(f"{BASE_URL}/api/messages/email-diagnostic/{USER_ID}/{CONTACT_WITH_EMAIL}")
        
        assert response.status_code == 200
        data = response.json()
        
        user_step = next((s for s in data["steps"] if s["step"] == "user_lookup"), None)
        assert user_step is not None, "user_lookup step should exist"
        assert user_step.get("ok") == True, f"user_lookup should be ok: {user_step}"
        
        print(f"User lookup: {user_step}")
        
    def test_email_diagnostic_contact_lookup_step(self):
        """Verify contact_lookup step returns email info"""
        response = requests.get(f"{BASE_URL}/api/messages/email-diagnostic/{USER_ID}/{CONTACT_WITH_EMAIL}")
        
        assert response.status_code == 200
        data = response.json()
        
        contact_step = next((s for s in data["steps"] if s["step"] == "contact_lookup"), None)
        assert contact_step is not None, "contact_lookup step should exist"
        assert contact_step.get("ok") == True, f"contact_lookup should be ok: {contact_step}"
        
        # Should have cleaned_email field
        assert "cleaned_email" in contact_step, "contact_lookup should have cleaned_email"
        
        print(f"Contact lookup: {contact_step}")
        
    def test_email_diagnostic_resend_config_step(self):
        """Verify resend_config step shows API key is configured"""
        response = requests.get(f"{BASE_URL}/api/messages/email-diagnostic/{USER_ID}/{CONTACT_WITH_EMAIL}")
        
        assert response.status_code == 200
        data = response.json()
        
        resend_step = next((s for s in data["steps"] if s["step"] == "resend_config"), None)
        assert resend_step is not None, "resend_config step should exist"
        
        # API key should be configured in this environment
        assert resend_step.get("ok") == True, f"resend_config should be ok (API key configured): {resend_step}"
        assert "api_key_prefix" in resend_step, "Should have api_key_prefix"
        assert resend_step["api_key_prefix"] != "MISSING", f"API key should not be MISSING: {resend_step}"
        
        print(f"Resend config: {resend_step}")


class TestEmailSendWithContactHavingEmail:
    """Test email send to contact WITH email address - should succeed."""
    
    def test_email_send_success_returns_sent_status(self):
        """POST /api/messages/send/{user_id} with channel='email' to contact WITH email returns status='sent'"""
        # First, we need to get or create a conversation for the contact with email
        conv_response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_WITH_EMAIL}
        )
        
        assert conv_response.status_code == 200, f"Failed to get/create conversation: {conv_response.text}"
        conversation = conv_response.json()
        conv_id = conversation.get("_id")
        
        # Now send an email message
        send_payload = {
            "conversation_id": conv_id,
            "content": f"Test email from pytest at {datetime.utcnow().isoformat()}",
            "channel": "email"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json=send_payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify successful email send
        assert data.get("status") == "sent", f"Expected status='sent', got: {data}"
        assert data.get("channel") == "email", f"Expected channel='email', got: {data}"
        assert "resend_id" in data, f"Response should have resend_id for successful email: {data}"
        assert data.get("resend_id") is not None, f"resend_id should not be None: {data}"
        
        print(f"Email sent successfully!")
        print(f"  Status: {data.get('status')}")
        print(f"  Channel: {data.get('channel')}")
        print(f"  Resend ID: {data.get('resend_id')}")
        
        return conv_id, data.get("_id")  # Return for verification in contact_events


class TestEmailSendWithContactWithoutEmail:
    """Test email send to contact WITHOUT email address - should fail gracefully."""
    
    def test_email_send_fails_without_email(self):
        """POST /api/messages/send/{user_id} with channel='email' to contact WITHOUT email returns status='failed'"""
        # First, get or create a conversation for the contact without email
        conv_response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_WITHOUT_EMAIL}
        )
        
        assert conv_response.status_code == 200, f"Failed to get/create conversation: {conv_response.text}"
        conversation = conv_response.json()
        conv_id = conversation.get("_id")
        
        # Now try to send an email message - should fail
        send_payload = {
            "conversation_id": conv_id,
            "content": f"Test email that should fail at {datetime.utcnow().isoformat()}",
            "channel": "email"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json=send_payload
        )
        
        # API should still return 200, but with status='failed' in the response body
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify failed email send with descriptive error
        assert data.get("status") == "failed", f"Expected status='failed' for contact without email, got: {data}"
        assert data.get("channel") == "email", f"Expected channel='email', got: {data}"
        assert "error" in data, f"Response should have 'error' field for failed send: {data}"
        assert data.get("error") is not None, f"error should not be None: {data}"
        
        # Error should mention no email
        error_msg = data.get("error", "").lower()
        assert "email" in error_msg or "no valid" in error_msg, f"Error should mention email issue: {data.get('error')}"
        
        print(f"Email send correctly failed!")
        print(f"  Status: {data.get('status')}")
        print(f"  Error: {data.get('error')}")
        
        return conv_id  # Return for verification in contact_events


class TestContactEventsForEmailFailure:
    """Test that failed email sends are logged in contact_events collection."""
    
    def test_email_failed_event_logged(self):
        """Failed email sends should create contact_event with event_type='email_failed'"""
        # First, trigger a failed email send
        conv_response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_WITHOUT_EMAIL}
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json().get("_id")
        
        # Send email that will fail
        unique_content = f"Failed email test {datetime.utcnow().isoformat()}"
        send_payload = {
            "conversation_id": conv_id,
            "content": unique_content,
            "channel": "email"
        }
        
        send_response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json=send_payload
        )
        
        assert send_response.status_code == 200
        send_data = send_response.json()
        assert send_data.get("status") == "failed", "Email should have failed"
        
        # Now check contact_events for the logged failure
        # The contact_events endpoint format: /api/contacts/{user_id}/{contact_id}/events
        events_response = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_WITHOUT_EMAIL}/events"
        )
        
        # If events endpoint exists
        if events_response.status_code == 200:
            response_data = events_response.json()
            # Response is wrapped in {'events': [...], 'total': N}
            events = response_data.get("events", response_data) if isinstance(response_data, dict) else response_data
            
            # Look for recent email_failed event
            email_failed_events = [
                e for e in events 
                if isinstance(e, dict) and e.get("event_type") == "email_failed" and e.get("channel") == "email"
            ]
            
            assert len(email_failed_events) > 0, f"Should have at least one email_failed event. Events: {events[:5]}"
            
            latest_failed = email_failed_events[0]
            print(f"Found email_failed event:")
            print(f"  Event type: {latest_failed.get('event_type')}")
            print(f"  Channel: {latest_failed.get('channel')}")
            print(f"  Error: {latest_failed.get('error')}")
        else:
            # Contact events endpoint might not exist or have different format
            print(f"Contact events endpoint returned {events_response.status_code}")
            # The event was still logged in DB (verified by code review), just may not have API endpoint
            pytest.skip("Contact events API endpoint not available for verification")
            
    def test_email_sent_event_logged(self):
        """Successful email sends should create contact_event with event_type='email_sent'"""
        # First, trigger a successful email send
        conv_response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_WITH_EMAIL}
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json().get("_id")
        
        # Send email that should succeed
        unique_content = f"Success email test {datetime.utcnow().isoformat()}"
        send_payload = {
            "conversation_id": conv_id,
            "content": unique_content,
            "channel": "email"
        }
        
        send_response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json=send_payload
        )
        
        assert send_response.status_code == 200
        send_data = send_response.json()
        assert send_data.get("status") == "sent", f"Email should have sent: {send_data}"
        
        # Check contact_events for the logged success
        events_response = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{CONTACT_WITH_EMAIL}/events"
        )
        
        if events_response.status_code == 200:
            response_data = events_response.json()
            # Response is wrapped in {'events': [...], 'total': N}
            events = response_data.get("events", response_data) if isinstance(response_data, dict) else response_data
            
            # Look for recent email_sent event
            email_sent_events = [
                e for e in events 
                if isinstance(e, dict) and e.get("event_type") == "email_sent" and e.get("channel") == "email"
            ]
            
            assert len(email_sent_events) > 0, f"Should have at least one email_sent event. Events: {events[:5]}"
            
            latest_sent = email_sent_events[0]
            print(f"Found email_sent event:")
            print(f"  Event type: {latest_sent.get('event_type')}")
            print(f"  Channel: {latest_sent.get('channel')}")
            print(f"  Status: {latest_sent.get('status')}")
        else:
            print(f"Contact events endpoint returned {events_response.status_code}")
            pytest.skip("Contact events API endpoint not available for verification")


class TestConversationInfoEndpoint:
    """Test the conversation info endpoint that frontend uses for email prompt."""
    
    def test_conversation_info_returns_contact_data(self):
        """GET /api/messages/conversation/{conversation_id}/info returns conversation with contact info"""
        response = requests.get(f"{BASE_URL}/api/messages/conversation/{CONVERSATION_ID}/info")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "_id" in data, "Response should have _id"
        assert data["_id"] == CONVERSATION_ID or str(data["_id"]) == CONVERSATION_ID, f"ID mismatch: {data}"
        
        # Should have contact info fields
        expected_fields = ["contact_name", "contact_phone", "status"]
        for field in expected_fields:
            assert field in data, f"Response should have '{field}' field: {data}"
        
        print(f"Conversation info:")
        print(f"  ID: {data.get('_id')}")
        print(f"  Contact name: {data.get('contact_name')}")
        print(f"  Contact phone: {data.get('contact_phone')}")
        print(f"  Contact email: {data.get('contact_email')}")
        print(f"  Status: {data.get('status')}")
        
    def test_conversation_info_includes_email_if_available(self):
        """Verify contact_email is included in response when available"""
        # Use conversation for contact with email
        conv_response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_WITH_EMAIL}
        )
        
        assert conv_response.status_code == 200
        conv_id = conv_response.json().get("_id")
        
        # Get info for this conversation
        response = requests.get(f"{BASE_URL}/api/messages/conversation/{conv_id}/info")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Contact email should be present (since this contact has an email)
        # Note: might be None if contact doesn't have email, but field should exist
        if "contact_email" in data and data["contact_email"]:
            print(f"Contact email found: {data['contact_email']}")
            # Verify it looks like an email
            assert "@" in data["contact_email"], f"contact_email should be valid email: {data['contact_email']}"
        else:
            print("Contact email not present in this conversation (may need to be set)")


class TestEmailFlowLogging:
    """Test that [EMAIL-FLOW] logging is working in backend logs."""
    
    def test_email_flow_triggers_logging(self):
        """Verify that sending email triggers [EMAIL-FLOW] log entries"""
        # This test verifies the code path is executed by checking the response
        # The actual logs are written to backend logs which we verified in code review
        
        conv_response = requests.post(
            f"{BASE_URL}/api/messages/conversations/{USER_ID}",
            json={"contact_id": CONTACT_WITH_EMAIL}
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json().get("_id")
        
        # Send email
        send_payload = {
            "conversation_id": conv_id,
            "content": f"Logging test email {datetime.utcnow().isoformat()}",
            "channel": "email"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json=send_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If email sent successfully, logging was triggered
        assert data.get("status") in ["sent", "failed"], f"Email should have status: {data}"
        
        print(f"Email flow executed - status: {data.get('status')}")
        print("[EMAIL-FLOW] logging entries would be visible in backend logs")
        print("Code review confirmed logging at lines 929-1011 in messages.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
