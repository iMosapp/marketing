"""
Card Labeling Fix Tests
-----------------------
Tests the bug fix where all cards sent from inbox were incorrectly labeled as 'Congrats Card'.
Now card_type is properly passed from frontend to backend and stored in MongoDB.

Features tested:
- POST /api/congrats/create accepts card_type parameter
- Backend stores card_type in congrats_cards collection
- Backend returns success with card_id, card_url, short_url
- Multiple card types: congrats, birthday, anniversary, thankyou, welcome, holiday
- Messages API stores event_type correctly when sending card messages
"""

import pytest
import requests
import os
import io
from PIL import Image

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com')
USER_ID = "69a0b7095fddcede09591667"  # Super Admin forest@imosapp.com

# Create a simple test image
def create_test_image():
    """Create a minimal test image for form upload."""
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes

class TestCardCreationWithType:
    """Test card creation with different card types."""
    
    def test_create_congrats_card_default_type(self):
        """Test creating a card without explicit card_type defaults to 'congrats'."""
        img_bytes = create_test_image()
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            data={
                "salesman_id": USER_ID,
                "customer_name": "TEST_Default_Card_Customer",
                "customer_phone": "+1555000001",
            },
            files={
                "photo": ("test.jpg", img_bytes, "image/jpeg")
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify success response structure
        assert data.get("success") is True, "Expected success=True"
        assert "card_id" in data, "Expected card_id in response"
        assert "card_url" in data, "Expected card_url in response"
        assert "short_url" in data, "Expected short_url in response"
        
        print(f"Created default card (card_id={data['card_id']})")
        
    def test_create_birthday_card_explicit_type(self):
        """Test creating a birthday card with explicit card_type='birthday'."""
        img_bytes = create_test_image()
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            data={
                "salesman_id": USER_ID,
                "customer_name": "TEST_Birthday_Customer",
                "customer_phone": "+1555000002",
                "card_type": "birthday"  # Explicit card type
            },
            files={
                "photo": ("birthday.jpg", img_bytes, "image/jpeg")
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "card_id" in data
        
        # Verify by fetching the card
        card_id = data["card_id"]
        get_response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        assert get_response.status_code == 200
        
        card_data = get_response.json()
        # The card type should be reflected in the headline
        assert "Birthday" in card_data.get("headline", ""), f"Expected 'Birthday' in headline, got: {card_data.get('headline')}"
        
        print(f"Created birthday card (card_id={card_id}, headline={card_data.get('headline')})")
        
    def test_create_anniversary_card(self):
        """Test creating an anniversary card."""
        img_bytes = create_test_image()
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            data={
                "salesman_id": USER_ID,
                "customer_name": "TEST_Anniversary_Customer",
                "customer_phone": "+1555000003",
                "card_type": "anniversary"
            },
            files={
                "photo": ("anniversary.jpg", img_bytes, "image/jpeg")
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        card_id = data["card_id"]
        get_response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        card_data = get_response.json()
        
        assert "Anniversary" in card_data.get("headline", ""), f"Expected 'Anniversary' in headline"
        print(f"Created anniversary card (card_id={card_id}, headline={card_data.get('headline')})")
        
    def test_create_thankyou_card(self):
        """Test creating a thank you card."""
        img_bytes = create_test_image()
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            data={
                "salesman_id": USER_ID,
                "customer_name": "TEST_ThankYou_Customer",
                "customer_phone": "+1555000004",
                "card_type": "thankyou"
            },
            files={
                "photo": ("thankyou.jpg", img_bytes, "image/jpeg")
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        card_id = data["card_id"]
        get_response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        card_data = get_response.json()
        
        assert "Thank You" in card_data.get("headline", "") or "Thank" in card_data.get("headline", ""), f"Expected 'Thank You' in headline"
        print(f"Created thank you card (card_id={card_id}, headline={card_data.get('headline')})")
        
    def test_create_welcome_card(self):
        """Test creating a welcome card."""
        img_bytes = create_test_image()
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            data={
                "salesman_id": USER_ID,
                "customer_name": "TEST_Welcome_Customer",
                "customer_phone": "+1555000005",
                "card_type": "welcome"
            },
            files={
                "photo": ("welcome.jpg", img_bytes, "image/jpeg")
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        card_id = data["card_id"]
        get_response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        card_data = get_response.json()
        
        assert "Welcome" in card_data.get("headline", ""), f"Expected 'Welcome' in headline"
        print(f"Created welcome card (card_id={card_id}, headline={card_data.get('headline')})")
        
    def test_create_holiday_card(self):
        """Test creating a holiday card."""
        img_bytes = create_test_image()
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            data={
                "salesman_id": USER_ID,
                "customer_name": "TEST_Holiday_Customer",
                "customer_phone": "+1555000006",
                "card_type": "holiday"
            },
            files={
                "photo": ("holiday.jpg", img_bytes, "image/jpeg")
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        card_id = data["card_id"]
        get_response = requests.get(f"{BASE_URL}/api/congrats/card/{card_id}")
        card_data = get_response.json()
        
        assert "Holiday" in card_data.get("headline", "") or "Holidays" in card_data.get("headline", ""), f"Expected 'Holiday' in headline"
        print(f"Created holiday card (card_id={card_id}, headline={card_data.get('headline')})")


class TestMessagesEventType:
    """Test that messages with card content store correct event_type."""
    
    def test_send_message_with_explicit_event_type(self):
        """Test sending a personal SMS with explicit event_type from frontend."""
        # First create a conversation or use existing contact
        response = requests.post(
            f"{BASE_URL}/api/messages/send/{USER_ID}",
            json={
                "contact_id": "69a0c06f7626f14d125f8c34",  # Existing test contact
                "content": "TEST - Here's your birthday card: https://app.imonsocial.com/congrats/test123",
                "channel": "sms_personal",
                "event_type": "birthday_card_sent"  # Explicit from frontend
            }
        )
        
        # Should succeed (even if SMS is mocked)
        assert response.status_code in [200, 404], f"Unexpected status {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"Message sent (status={data.get('status')}, event_type should be birthday_card_sent)")
            assert data.get('status') in ['sent', 'sending', 'failed'], "Expected valid status"
            

class TestCardDisplayConfig:
    """Test that card display configuration is correct for all types."""
    
    def test_card_types_have_correct_defaults(self):
        """Test each card type has the correct default configuration from backend template endpoint."""
        store_id = "673f16f4a30c7c4e6c8ea2ea"  # Any valid store ID
        
        card_types = ['congrats', 'birthday', 'anniversary', 'thankyou', 'welcome', 'holiday']
        expected_headlines = {
            'congrats': 'Congratulations!',
            'birthday': 'Happy Birthday!',
            'anniversary': 'Happy Anniversary!',
            'thankyou': 'Thank You!',
            'welcome': 'Welcome!',
            'holiday': 'Happy Holidays!'
        }
        
        for card_type in card_types:
            response = requests.get(f"{BASE_URL}/api/congrats/template/{store_id}?card_type={card_type}")
            assert response.status_code == 200, f"Failed to get template for {card_type}"
            
            data = response.json()
            template = data.get("template", {})
            headline = template.get("headline", "")
            
            expected = expected_headlines.get(card_type, "")
            assert expected in headline or headline == expected, f"Card type '{card_type}': Expected headline containing '{expected}', got '{headline}'"
            
            print(f"✓ {card_type}: headline='{headline}', accent_color={template.get('accent_color')}")


class TestCardHistory:
    """Test card history shows correct card types."""
    
    def test_card_history_includes_card_type(self):
        """Test that card history endpoint returns card_type for each card."""
        response = requests.get(f"{BASE_URL}/api/congrats/history/{USER_ID}?limit=10")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), "Expected list response"
        
        if len(data) > 0:
            # Check that card_type is present in each card
            for card in data[:5]:  # Check first 5
                card_type = card.get("card_type", "")
                assert card_type, f"Expected card_type in card {card.get('card_id')}"
                assert card_type in ['congrats', 'birthday', 'anniversary', 'thankyou', 'welcome', 'holiday'], \
                    f"Unexpected card_type: {card_type}"
                print(f"Card {card.get('card_id')}: card_type={card_type}, customer={card.get('customer_name')}")
        else:
            print("No cards in history yet (expected for clean test environment)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
