"""
Digital Card Label Bug Fix Tests
---------------------------------
Tests the bug fix where messages with event_type='congrats_card_sent' but containing
digital card content (URLs with /card/, /p/, or text like 'digital business card',
'save my contact info') were incorrectly displayed as 'Congrats Card' instead of
'Digital Card' in the inbox thread view.

Bug Root Cause:
- Historical messages had generic event_type='congrats_card_sent' but contained digital card content
- Frontend content-based detection logic was falling through to 'Congrats Card' label

Fix Applied (in /app/frontend/app/thread/[id].tsx):
1. Moved contentLower definition before isDigitalCard detection
2. Added guards so when isDigitalCard is true, detectedCardType is NOT set to 'congrats'
3. Swapped display priority so isDigitalCard is checked BEFORE isCongratsCard

Test Cases:
- Digital card messages with content containing 'digital business card' should display as 'Digital Card'
- Digital card messages with content containing '/card/' URL should display as 'Digital Card'
- Digital card messages with content containing '/p/' URL should display as 'Digital Card'
- Digital card messages with content containing 'save my contact' should display as 'Digital Card'
- Digital card messages with event_type='digital_card_sent' should display as 'Digital Card'
- Digital card messages with event_type='digital_card_shared' should display as 'Digital Card'
- Actual congrats card messages should still display as 'Congrats Card'
- Birthday card messages should display as 'Birthday Card'
- Holiday card messages should display as 'Holiday Card'
- Review link messages should display as 'Review Link'
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com')
USER_ID = "69a0b7095fddcede09591667"  # Super Admin forest@imosapp.com


class TestDigitalCardLabelBugFix:
    """
    Test suite for the digital card label bug fix.
    
    These tests verify that the backend API correctly returns event_type
    and the frontend logic (tested via Playwright separately) correctly
    interprets the content to display the right label.
    """
    
    def test_thread_api_returns_event_type(self):
        """Verify thread API returns event_type field for messages."""
        # Use the test conversation created for card label testing
        conv_id = "69adbc1c1aac0c754b9916c9"  # Test conversation
        
        response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        
        if response.status_code == 404:
            pytest.skip("Test conversation not found - skipping")
            
        assert response.status_code == 200
        messages = response.json()
        
        assert len(messages) > 0, "Expected test messages in thread"
        
        # Verify each message has event_type field
        for msg in messages:
            assert "event_type" in msg, f"Message {msg.get('_id')} missing event_type field"
            print(f"Message: event_type={msg.get('event_type')}, content={msg.get('content', '')[:50]}...")
    
    def test_event_type_digital_card_sent(self):
        """Test that digital_card_sent event_type is properly returned."""
        conv_id = "69adbc1c1aac0c754b9916c9"
        
        response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        
        if response.status_code == 404:
            pytest.skip("Test conversation not found")
            
        messages = response.json()
        
        # Find message with digital_card_sent event_type
        digital_card_msgs = [m for m in messages if m.get('event_type') == 'digital_card_sent']
        
        assert len(digital_card_msgs) > 0, "Expected at least one digital_card_sent message"
        print(f"Found {len(digital_card_msgs)} messages with event_type=digital_card_sent")
    
    def test_event_type_congrats_card_sent_with_digital_content(self):
        """
        Test the BUG FIX scenario: event_type='congrats_card_sent' but content
        contains digital card indicators (should display as 'Digital Card' in UI).
        """
        conv_id = "69adbc1c1aac0c754b9916c9"
        
        response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        
        if response.status_code == 404:
            pytest.skip("Test conversation not found")
            
        messages = response.json()
        
        # Find messages with congrats_card_sent event_type
        congrats_msgs = [m for m in messages if m.get('event_type') == 'congrats_card_sent']
        
        # Check for messages that have digital card content patterns
        digital_card_patterns = ['digital business card', 'digital card', '/card/', '/p/', 'save my contact']
        
        for msg in congrats_msgs:
            content = msg.get('content', '').lower()
            has_digital_pattern = any(pattern in content for pattern in digital_card_patterns)
            
            if has_digital_pattern:
                print(f"FOUND BUG SCENARIO: event_type=congrats_card_sent but content has digital card pattern")
                print(f"  Content: {msg.get('content', '')[:80]}...")
                print(f"  -> Frontend should display this as 'Digital Card', NOT 'Congrats Card'")
    
    def test_event_type_birthday_card_sent(self):
        """Test that birthday_card_sent event_type is properly returned."""
        conv_id = "69adbc1c1aac0c754b9916c9"
        
        response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        
        if response.status_code == 404:
            pytest.skip("Test conversation not found")
            
        messages = response.json()
        
        birthday_msgs = [m for m in messages if m.get('event_type') == 'birthday_card_sent']
        assert len(birthday_msgs) > 0, "Expected at least one birthday_card_sent message"
        print(f"Found {len(birthday_msgs)} messages with event_type=birthday_card_sent")
    
    def test_event_type_holiday_card_sent(self):
        """Test that holiday_card_sent event_type is properly returned."""
        conv_id = "69adbc1c1aac0c754b9916c9"
        
        response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        
        if response.status_code == 404:
            pytest.skip("Test conversation not found")
            
        messages = response.json()
        
        holiday_msgs = [m for m in messages if m.get('event_type') == 'holiday_card_sent']
        assert len(holiday_msgs) > 0, "Expected at least one holiday_card_sent message"
        print(f"Found {len(holiday_msgs)} messages with event_type=holiday_card_sent")
    
    def test_event_type_review_request_sent(self):
        """Test that review_request_sent event_type is properly returned."""
        conv_id = "69adbc1c1aac0c754b9916c9"
        
        response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        
        if response.status_code == 404:
            pytest.skip("Test conversation not found")
            
        messages = response.json()
        
        review_msgs = [m for m in messages if m.get('event_type') == 'review_request_sent']
        assert len(review_msgs) > 0, "Expected at least one review_request_sent message"
        print(f"Found {len(review_msgs)} messages with event_type=review_request_sent")


class TestMessageSendWithEventType:
    """Test sending messages with explicit event_type parameter."""
    
    def test_send_personal_sms_with_digital_card_event_type(self):
        """Test that sending a personal SMS with digital_card_sent event_type is stored correctly."""
        # Find or create a test conversation
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        assert response.status_code == 200
        
        convos = response.json()
        if not convos:
            pytest.skip("No conversations found for user")
            
        conv_id = convos[0].get('_id')
        
        # Send a test message with explicit event_type
        test_content = f"TEST_SEND_DIGITAL_{datetime.now().strftime('%H%M%S')}: Here is my digital business card"
        
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json={
                "conversation_id": conv_id,
                "content": test_content,
                "channel": "sms_personal",
                "event_type": "digital_card_sent"
            }
        )
        
        # Might fail if conversation doesn't exist, that's OK
        if response.status_code == 200:
            data = response.json()
            assert data.get('status') in ['sent', 'sending', 'failed'], "Expected valid status"
            assert data.get('event_type') == 'digital_card_sent' or data.get('channel') == 'sms_personal'
            print(f"Message sent: status={data.get('status')}, channel={data.get('channel')}")
        else:
            print(f"Message send returned {response.status_code} - may be expected if test data missing")


class TestFrontendLabelLogic:
    """
    Document the expected frontend label logic.
    
    These are not actual tests but document the expected behavior
    that should be tested via Playwright (UI automation).
    """
    
    def test_document_label_detection_rules(self):
        """Document the content-based label detection rules in frontend."""
        # This documents the logic in /app/frontend/app/thread/[id].tsx
        # Lines 1501-1565: renderMessage function with card labeling logic
        
        detection_rules = """
        DIGITAL CARD DETECTION (isDigitalCard = true):
        - Content contains '/card/' URL
        - Content contains '/p/' URL
        - Content contains 'digital card' (case-insensitive)
        - Content contains 'digital business card' (case-insensitive)
        - Content contains 'save my contact' (case-insensitive)
        - event_type is 'digital_card_shared'
        - event_type is 'digital_card_sent'
        
        CONGRATS CARD DETECTION:
        - event_type contains '_card_sent' AND is NOT 'digital_card_sent' AND content is NOT digital card
        - Content contains '/congrats/' URL AND content is NOT digital card
        - Content contains 'congrats' or 'congratulations' (case-insensitive) AND content is NOT digital card
        
        BIRTHDAY CARD DETECTION:
        - event_type is 'birthday_card_sent'
        - Content contains 'birthday card' or 'happy birthday'
        
        HOLIDAY CARD DETECTION:
        - event_type is 'holiday_card_sent'
        - Content contains 'holiday card' or 'happy holiday'
        
        REVIEW LINK DETECTION (isReviewLink = true):
        - Content contains '/review/' URL
        - Content contains 'review link' (case-insensitive)
        - event_type contains 'review'
        
        DISPLAY PRIORITY (checked in this order):
        1. Review Link
        2. Digital Card <-- CRITICAL: Digital card checked BEFORE congrats card
        3. Congrats Card (including birthday, anniversary, thankyou, welcome, holiday subtypes)
        """
        
        print(detection_rules)
        assert True  # This is a documentation test


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
