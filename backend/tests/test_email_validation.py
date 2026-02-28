"""
Tests for email validation fix in messages.py
- _clean_email() should reject 'None', 'null', empty strings as invalid
- Valid emails like 'user@example.com' should pass validation
- Email sending should fail gracefully with 'No email address for contact'
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"


class TestEmailValidationLogic:
    """Test _clean_email() validation logic via API behavior"""
    
    def test_send_email_to_contact_without_email_fails(self):
        """Sending email to contact with no email should fail with appropriate error"""
        # First, create a contact WITHOUT an email
        create_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "NoEmail",
                "last_name": "Test",
                "phone": "+15551234999",
                "email": ""  # No email
            }
        )
        assert create_resp.status_code == 201 or create_resp.status_code == 200
        contact = create_resp.json()
        contact_id = contact.get("id") or contact.get("_id")
        
        try:
            # Try to send email to this contact
            send_resp = requests.post(
                f"{BASE_URL}/api/messages/send/{USER_ID}",
                json={
                    "contact_id": contact_id,
                    "content": "Test email",
                    "channel": "email"
                }
            )
            
            # Should succeed but message status should be 'failed'
            if send_resp.status_code == 200:
                data = send_resp.json()
                assert data.get("status") == "failed", "Status should be 'failed' for no email"
                assert "No email address" in (data.get("error") or ""), f"Error should mention 'No email address', got: {data.get('error')}"
                print(f"✓ Email to contact without email fails correctly: {data.get('error')}")
            else:
                # Some implementations might return 400
                print(f"✓ Request rejected with status {send_resp.status_code}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
    
    def test_send_email_to_contact_with_none_string_email_fails(self):
        """Contact with email='None' should be treated as having no email"""
        # Create contact with email='None' (the string)
        create_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "NoneEmail",
                "last_name": "Test",
                "phone": "+15551234998",
                "email": "None"  # String 'None'
            }
        )
        assert create_resp.status_code in [200, 201]
        contact = create_resp.json()
        contact_id = contact.get("id") or contact.get("_id")
        
        try:
            # Try to send email
            send_resp = requests.post(
                f"{BASE_URL}/api/messages/send/{USER_ID}",
                json={
                    "contact_id": contact_id,
                    "content": "Test email to None",
                    "channel": "email"
                }
            )
            
            if send_resp.status_code == 200:
                data = send_resp.json()
                # The _clean_email should sanitize 'None' to empty string
                assert data.get("status") == "failed", "Status should be 'failed' for email='None'"
                print(f"✓ Email='None' correctly rejected: {data.get('error')}")
            else:
                print(f"✓ Request rejected with status {send_resp.status_code}")
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
    
    def test_send_email_to_contact_with_null_string_email_fails(self):
        """Contact with email='null' should be treated as having no email"""
        create_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "NullEmail",
                "last_name": "Test",
                "phone": "+15551234997",
                "email": "null"
            }
        )
        assert create_resp.status_code in [200, 201]
        contact = create_resp.json()
        contact_id = contact.get("id") or contact.get("_id")
        
        try:
            send_resp = requests.post(
                f"{BASE_URL}/api/messages/send/{USER_ID}",
                json={
                    "contact_id": contact_id,
                    "content": "Test email to null",
                    "channel": "email"
                }
            )
            
            if send_resp.status_code == 200:
                data = send_resp.json()
                assert data.get("status") == "failed", "Status should be 'failed' for email='null'"
                print(f"✓ Email='null' correctly rejected: {data.get('error')}")
            else:
                print(f"✓ Request rejected with status {send_resp.status_code}")
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
    
    def test_send_email_to_contact_with_valid_email_succeeds(self):
        """Contact with valid email should attempt to send (may fail if Resend quota but validates email)"""
        create_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "ValidEmail",
                "last_name": "Test",
                "phone": "+15551234996",
                "email": "test-valid@example.com"
            }
        )
        assert create_resp.status_code in [200, 201]
        contact = create_resp.json()
        contact_id = contact.get("id") or contact.get("_id")
        
        try:
            send_resp = requests.post(
                f"{BASE_URL}/api/messages/send/{USER_ID}",
                json={
                    "contact_id": contact_id,
                    "content": "Test email with valid address",
                    "channel": "email"
                }
            )
            
            data = send_resp.json()
            # If RESEND_API_KEY is configured and valid, status should be 'sent'
            # Otherwise could be 'failed' due to API key issues
            if data.get("status") == "sent":
                print(f"✓ Valid email sent successfully")
            elif data.get("status") == "failed":
                # Check it's not because email was invalid
                error = data.get("error") or ""
                assert "No email address" not in error, f"Should not fail due to 'No email address': {error}"
                print(f"✓ Valid email passed validation (send failed due to: {error})")
            else:
                print(f"✓ Response: {data}")
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
    
    def test_send_email_to_contact_with_undefined_string_email_fails(self):
        """Contact with email='undefined' should be treated as having no email"""
        create_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "UndefinedEmail",
                "last_name": "Test",
                "phone": "+15551234995",
                "email": "undefined"
            }
        )
        assert create_resp.status_code in [200, 201]
        contact = create_resp.json()
        contact_id = contact.get("id") or contact.get("_id")
        
        try:
            send_resp = requests.post(
                f"{BASE_URL}/api/messages/send/{USER_ID}",
                json={
                    "contact_id": contact_id,
                    "content": "Test email to undefined",
                    "channel": "email"
                }
            )
            
            if send_resp.status_code == 200:
                data = send_resp.json()
                assert data.get("status") == "failed", "Status should be 'failed' for email='undefined'"
                print(f"✓ Email='undefined' correctly rejected: {data.get('error')}")
            else:
                print(f"✓ Request rejected with status {send_resp.status_code}")
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")


class TestEmailValidationInConversationInfo:
    """Test _get_contact_email in conversation info endpoint"""
    
    def test_conversation_info_sanitizes_email(self):
        """Conversation info should not return 'None' or 'null' as email"""
        # Create contact with email='None'
        create_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "ConvInfo",
                "last_name": "Test",
                "phone": "+15551234994",
                "email": "None"
            }
        )
        assert create_resp.status_code in [200, 201]
        contact = create_resp.json()
        contact_id = contact.get("id") or contact.get("_id")
        
        try:
            # Create conversation
            conv_resp = requests.post(
                f"{BASE_URL}/api/messages/conversations/{USER_ID}",
                json={"contact_id": contact_id, "contact_phone": "+15551234994"}
            )
            assert conv_resp.status_code in [200, 201]
            conv = conv_resp.json()
            conv_id = conv.get("_id")
            
            # Get conversation info
            info_resp = requests.get(f"{BASE_URL}/api/messages/conversation/{conv_id}/info")
            assert info_resp.status_code == 200
            info = info_resp.json()
            
            # contact_email should be sanitized (empty/null, not 'None')
            contact_email = info.get("contact_email")
            assert contact_email not in ("None", "null", "undefined"), f"contact_email should be sanitized, got: {contact_email}"
            print(f"✓ Conversation info correctly sanitizes email: contact_email={contact_email}")
            
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
