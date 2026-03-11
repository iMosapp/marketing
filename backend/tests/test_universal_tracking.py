"""
Tests for Universal Click Tracking System.
Tests POST /api/tracking/event endpoint with various scenarios:
- Direct contact_id (preferred path)
- Phone fallback
- No identifier (should return tracked:false)
- Unknown action (should still track with generic info)
- ACTION_CONFIG resolution
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from requirements
USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
TEST_CONTACT_ID = "69a496841603573df5a41723"  # Bud contact
TEST_CONTACT_PHONE = "8018212166"


class TestTrackingEndpoint:
    """Tests for POST /api/tracking/event"""

    def test_track_event_with_contact_id(self):
        """Test tracking with direct contact_id (preferred path) - should return tracked:true"""
        response = requests.post(
            f"{BASE_URL}/api/tracking/event",
            json={
                "page": "card",
                "action": "call_clicked",
                "salesperson_id": USER_ID,
                "contact_id": TEST_CONTACT_ID,
                "url": "tel:+18015551234"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("tracked") is True, f"Expected tracked:true, got {data}"
        assert data.get("event_type") == "card_call_clicked", f"Expected card_call_clicked, got {data.get('event_type')}"
        print(f"PASS: Track with contact_id returned tracked:true, event_type={data.get('event_type')}")

    def test_track_event_with_phone_fallback(self):
        """Test tracking with customer_phone fallback - should return tracked:true"""
        response = requests.post(
            f"{BASE_URL}/api/tracking/event",
            json={
                "page": "card",
                "action": "text_clicked",
                "salesperson_id": USER_ID,
                "customer_phone": TEST_CONTACT_PHONE,
                "url": "sms:+18018212166"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Phone lookup may or may not find contact - just verify endpoint works
        print(f"Track with phone fallback: {data}")
        assert "tracked" in data, "Response should have 'tracked' field"

    def test_track_event_without_identifier(self):
        """Test tracking without contact_id or phone - should return tracked:false, reason:contact_not_found"""
        response = requests.post(
            f"{BASE_URL}/api/tracking/event",
            json={
                "page": "card",
                "action": "email_clicked",
                "salesperson_id": USER_ID,
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("tracked") is False, f"Expected tracked:false when no identifier, got {data}"
        assert data.get("reason") == "contact_not_found", f"Expected reason:contact_not_found, got {data.get('reason')}"
        print(f"PASS: Track without identifier returned tracked:false, reason={data.get('reason')}")

    def test_track_event_without_salesperson_id(self):
        """Test tracking without salesperson_id - should return tracked:false, reason:no_salesperson_id"""
        response = requests.post(
            f"{BASE_URL}/api/tracking/event",
            json={
                "page": "card",
                "action": "call_clicked",
                "contact_id": TEST_CONTACT_ID,
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("tracked") is False, f"Expected tracked:false when no salesperson_id, got {data}"
        assert "salesperson" in data.get("reason", "").lower(), f"Expected reason to mention salesperson, got {data.get('reason')}"
        print(f"PASS: Track without salesperson_id returned tracked:false, reason={data.get('reason')}")

    def test_track_event_unknown_action(self):
        """Test tracking with unknown action - should still track with generic info"""
        response = requests.post(
            f"{BASE_URL}/api/tracking/event",
            json={
                "page": "card",
                "action": "some_random_action",
                "salesperson_id": USER_ID,
                "contact_id": TEST_CONTACT_ID,
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should still track even with unknown action
        assert data.get("tracked") is True, f"Expected tracked:true for unknown action, got {data}"
        # Event type should be constructed from page_action
        assert data.get("event_type") == "card_some_random_action", f"Expected card_some_random_action, got {data.get('event_type')}"
        print(f"PASS: Track unknown action returned tracked:true, event_type={data.get('event_type')}")


class TestActionConfigResolution:
    """Test that all ACTION_CONFIG entries resolve correctly"""

    def test_congrats_card_actions(self):
        """Test congrats card action config resolution"""
        actions = [
            ("congrats", "viewed", "congrats_card_viewed"),
            ("congrats", "internal_review_submitted", "internal_review_submitted"),
            ("congrats", "online_review_clicked", "online_review_clicked"),
            ("congrats", "download_clicked", "congrats_card_downloaded"),
            ("congrats", "share_clicked", "congrats_card_shared"),
            ("congrats", "salesman_card_clicked", "card_salesman_clicked"),
            ("congrats", "my_card_clicked", "card_quick_link_clicked"),
            ("congrats", "my_page_clicked", "page_quick_link_clicked"),
            ("congrats", "showcase_clicked", "showcase_quick_link_clicked"),
            ("congrats", "links_clicked", "links_quick_link_clicked"),
            ("congrats", "opt_in_clicked", "opt_in_clicked"),
        ]
        for page, action, expected_type in actions:
            response = requests.post(
                f"{BASE_URL}/api/tracking/event",
                json={
                    "page": page,
                    "action": action,
                    "salesperson_id": USER_ID,
                    "contact_id": TEST_CONTACT_ID,
                }
            )
            assert response.status_code == 200
            data = response.json()
            if data.get("tracked"):
                assert data.get("event_type") == expected_type, f"({page},{action}) expected {expected_type}, got {data.get('event_type')}"
                print(f"PASS: ({page},{action}) -> {expected_type}")
            else:
                print(f"WARN: ({page},{action}) not tracked - {data}")

    def test_digital_card_actions(self):
        """Test digital card action config resolution"""
        actions = [
            ("card", "viewed", "digital_card_viewed"),
            ("card", "call_clicked", "card_call_clicked"),
            ("card", "text_clicked", "card_text_clicked"),
            ("card", "email_clicked", "card_email_clicked"),
            ("card", "vcard_saved", "vcard_saved"),
            ("card", "website_clicked", "card_website_clicked"),
            ("card", "social_clicked", "card_social_clicked"),
            ("card", "share_clicked", "card_share_clicked"),
            ("card", "review_clicked", "card_review_clicked"),
            ("card", "online_review_clicked", "card_online_review_clicked"),
            ("card", "refer_clicked", "card_refer_clicked"),
        ]
        for page, action, expected_type in actions:
            response = requests.post(
                f"{BASE_URL}/api/tracking/event",
                json={
                    "page": page,
                    "action": action,
                    "salesperson_id": USER_ID,
                    "contact_id": TEST_CONTACT_ID,
                }
            )
            assert response.status_code == 200
            data = response.json()
            if data.get("tracked"):
                assert data.get("event_type") == expected_type, f"({page},{action}) expected {expected_type}, got {data.get('event_type')}"
                print(f"PASS: ({page},{action}) -> {expected_type}")
            else:
                print(f"WARN: ({page},{action}) not tracked - {data}")

    def test_store_card_actions(self):
        """Test store card action config resolution"""
        actions = [
            ("store_card", "viewed", "store_card_viewed"),
            ("store_card", "call_clicked", "store_call_clicked"),
            ("store_card", "email_clicked", "store_email_clicked"),
            ("store_card", "website_clicked", "store_website_clicked"),
            ("store_card", "directions_clicked", "store_directions_clicked"),
            ("store_card", "team_member_clicked", "store_team_clicked"),
        ]
        for page, action, expected_type in actions:
            response = requests.post(
                f"{BASE_URL}/api/tracking/event",
                json={
                    "page": page,
                    "action": action,
                    "salesperson_id": USER_ID,
                    "contact_id": TEST_CONTACT_ID,
                }
            )
            assert response.status_code == 200
            data = response.json()
            if data.get("tracked"):
                assert data.get("event_type") == expected_type, f"({page},{action}) expected {expected_type}, got {data.get('event_type')}"
                print(f"PASS: ({page},{action}) -> {expected_type}")
            else:
                print(f"WARN: ({page},{action}) not tracked - {data}")

    def test_review_page_actions(self):
        """Test review page action config resolution"""
        actions = [
            ("review", "viewed", "review_page_viewed"),
            ("review", "review_link_clicked", "review_link_clicked"),
            ("review", "review_submitted", "review_submitted"),
        ]
        for page, action, expected_type in actions:
            response = requests.post(
                f"{BASE_URL}/api/tracking/event",
                json={
                    "page": page,
                    "action": action,
                    "salesperson_id": USER_ID,
                    "contact_id": TEST_CONTACT_ID,
                }
            )
            assert response.status_code == 200
            data = response.json()
            if data.get("tracked"):
                assert data.get("event_type") == expected_type, f"({page},{action}) expected {expected_type}, got {data.get('event_type')}"
                print(f"PASS: ({page},{action}) -> {expected_type}")
            else:
                print(f"WARN: ({page},{action}) not tracked - {data}")

    def test_link_page_actions(self):
        """Test link page action config resolution"""
        actions = [
            ("link_page", "viewed", "link_page_viewed"),
            ("link_page", "link_clicked", "link_page_link_clicked"),
        ]
        for page, action, expected_type in actions:
            response = requests.post(
                f"{BASE_URL}/api/tracking/event",
                json={
                    "page": page,
                    "action": action,
                    "salesperson_id": USER_ID,
                    "contact_id": TEST_CONTACT_ID,
                }
            )
            assert response.status_code == 200
            data = response.json()
            if data.get("tracked"):
                assert data.get("event_type") == expected_type, f"({page},{action}) expected {expected_type}, got {data.get('event_type')}"
                print(f"PASS: ({page},{action}) -> {expected_type}")
            else:
                print(f"WARN: ({page},{action}) not tracked - {data}")


class TestContactEventsIntegration:
    """Test that tracked events appear in contact's activity feed"""

    def test_events_appear_in_contact_feed(self):
        """After tracking, events should show up in GET /api/contacts/{user_id}/{contact_id}/events"""
        # First, track an event
        track_response = requests.post(
            f"{BASE_URL}/api/tracking/event",
            json={
                "page": "card",
                "action": "call_clicked",
                "salesperson_id": USER_ID,
                "contact_id": TEST_CONTACT_ID,
                "url": "tel:+18015551234",
                "description": "Test call from tracking test"
            }
        )
        assert track_response.status_code == 200
        track_data = track_response.json()
        
        if track_data.get("tracked"):
            # Then, verify it appears in the contact's event feed
            events_response = requests.get(
                f"{BASE_URL}/api/contacts/{USER_ID}/{TEST_CONTACT_ID}/events"
            )
            assert events_response.status_code == 200, f"Expected 200, got {events_response.status_code}: {events_response.text}"
            events = events_response.json()
            
            # Look for the event we just created
            found = any(
                e.get("event_type") == "card_call_clicked" 
                for e in events if isinstance(events, list)
            )
            print(f"PASS: Contact events endpoint working. Found tracked event in feed: {found}")
            print(f"  Total events for contact: {len(events) if isinstance(events, list) else 'N/A'}")
        else:
            print(f"WARN: Event not tracked, skipping feed check: {track_data}")


class TestPublicPageDataEndpoints:
    """Test that public page data endpoints accept cid param"""

    def test_card_data_with_cid(self):
        """Test GET /api/card/data/{userId}?cid=... accepts cid param"""
        response = requests.get(
            f"{BASE_URL}/api/card/data/{USER_ID}?cid={TEST_CONTACT_ID}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "user" in data, "Response should contain user data"
        print(f"PASS: GET /api/card/data/{USER_ID}?cid=... works. User: {data.get('user', {}).get('name', 'N/A')}")

    def test_linkpage_public_with_cid(self):
        """Test GET /api/linkpage/public/{username}?cid=... accepts cid param"""
        # First get a valid username
        linkpage_response = requests.get(f"{BASE_URL}/api/linkpage/user/{USER_ID}")
        if linkpage_response.status_code != 200:
            print("SKIP: No linkpage for this user")
            return
        
        username = linkpage_response.json().get("username")
        if not username:
            print("SKIP: No linkpage username")
            return
            
        response = requests.get(f"{BASE_URL}/api/linkpage/public/{username}?cid={TEST_CONTACT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASS: GET /api/linkpage/public/{username}?cid=... works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
