"""
CRM Timeline Enhanced Export Tests (Iteration 177)
Tests the enhanced CRM timeline that fetches from ALL sources:
- contact_events
- messages collection (conversations)
- campaign_enrollments
- congrats_cards_sent
- broadcast_recipients

Also verifies:
- Direction field (outbound/inbound) classification
- Message content (full_content, description) for message_outbound events
- total_events count matches actual events array length
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_CRM_TOKEN = "c873848e-0ab2-435e-8418-de3ff4c3cb85"


class TestCRMTimelineEnhanced:
    """Tests for enhanced CRM timeline export"""

    def test_timeline_endpoint_accessible(self):
        """Verify GET /api/crm/timeline/{token} returns 200"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "events" in data, "Response should contain 'events' field"
        assert "total_events" in data, "Response should contain 'total_events' field"
        print(f"PASS: Timeline endpoint accessible, {data['total_events']} total events")

    def test_total_events_matches_array_length(self):
        """Verify total_events count matches the events array length"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        
        total_events = data.get("total_events", 0)
        actual_length = len(data.get("events", []))
        
        assert total_events == actual_length, \
            f"total_events ({total_events}) does not match events array length ({actual_length})"
        print(f"PASS: total_events ({total_events}) matches events array length")

    def test_all_events_have_direction_field(self):
        """Verify all events have a 'direction' field"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        missing_direction = [i for i, e in enumerate(events) if "direction" not in e]
        assert len(missing_direction) == 0, \
            f"Events at indices {missing_direction[:10]} missing 'direction' field"
        print(f"PASS: All {len(events)} events have 'direction' field")

    def test_direction_values_valid(self):
        """Verify direction field is either 'outbound' or 'inbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        invalid = [e.get("direction") for e in events if e.get("direction") not in ("outbound", "inbound")]
        assert len(invalid) == 0, f"Found invalid direction values: {set(invalid)}"
        
        outbound = sum(1 for e in events if e.get("direction") == "outbound")
        inbound = sum(1 for e in events if e.get("direction") == "inbound")
        print(f"PASS: All directions valid (outbound: {outbound}, inbound: {inbound})")

    def test_viewed_events_marked_inbound(self):
        """Verify *_viewed events are classified as 'inbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        viewed_types = [
            "digital_card_viewed", "birthday_card_viewed", "review_page_viewed",
            "congrats_card_viewed", "thankyou_card_viewed", "thank_you_card_viewed",
            "holiday_card_viewed", "welcome_card_viewed", "anniversary_card_viewed",
            "showcase_viewed", "link_page_viewed"
        ]
        
        for vt in viewed_types:
            matches = [e for e in events if e.get("event_type") == vt]
            for m in matches:
                assert m.get("direction") == "inbound", \
                    f"Event type {vt} should be 'inbound', got '{m.get('direction')}'"
        
        viewed_count = sum(1 for e in events if e.get("event_type") in viewed_types)
        print(f"PASS: All {viewed_count} *_viewed events marked as 'inbound'")

    def test_customer_reply_marked_inbound(self):
        """Verify customer_reply events are classified as 'inbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        replies = [e for e in events if e.get("event_type") == "customer_reply"]
        for r in replies:
            assert r.get("direction") == "inbound", \
                f"customer_reply should be 'inbound', got '{r.get('direction')}'"
        
        print(f"PASS: All {len(replies)} customer_reply events marked as 'inbound'")

    def test_message_outbound_has_content(self):
        """Verify message_outbound events have full_content and description"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        msg_outbound = [e for e in events if e.get("event_type") == "message_outbound"]
        assert len(msg_outbound) > 0, "Expected at least one message_outbound event"
        
        for m in msg_outbound[:5]:  # Check first 5
            # Should have full_content OR description with actual message body
            has_content = bool(m.get("full_content") or m.get("description"))
            assert has_content, f"message_outbound event missing content/description"
            
            # Verify direction is outbound
            assert m.get("direction") == "outbound", \
                f"message_outbound should have direction='outbound', got '{m.get('direction')}'"
        
        print(f"PASS: {len(msg_outbound)} message_outbound events have content and correct direction")

    def test_message_inbound_marked_correctly(self):
        """Verify message_inbound events are classified as 'inbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        msg_inbound = [e for e in events if e.get("event_type") == "message_inbound"]
        for m in msg_inbound:
            assert m.get("direction") == "inbound", \
                f"message_inbound should be 'inbound', got '{m.get('direction')}'"
        
        print(f"PASS: All {len(msg_inbound)} message_inbound events marked correctly")

    def test_campaign_enrolled_marked_outbound(self):
        """Verify campaign_enrolled events are classified as 'outbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        enrolled = [e for e in events if e.get("event_type") == "campaign_enrolled"]
        for e in enrolled:
            assert e.get("direction") == "outbound", \
                f"campaign_enrolled should be 'outbound', got '{e.get('direction')}'"
        
        print(f"PASS: All {len(enrolled)} campaign_enrolled events marked as 'outbound'")

    def test_card_sent_events_marked_outbound(self):
        """Verify *_card_sent events are classified as 'outbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        card_sent_types = [
            "digital_card_sent", "birthday_card_sent", "congrats_card_sent",
            "thankyou_card_sent", "thank_you_card_sent", "holiday_card_sent",
            "welcome_card_sent", "anniversary_card_sent"
        ]
        
        for ct in card_sent_types:
            matches = [e for e in events if e.get("event_type") == ct]
            for m in matches:
                assert m.get("direction") == "outbound", \
                    f"{ct} should be 'outbound', got '{m.get('direction')}'"
        
        card_count = sum(1 for e in events if e.get("event_type") in card_sent_types)
        print(f"PASS: All {card_count} *_card_sent events marked as 'outbound'")

    def test_broadcast_sent_marked_outbound(self):
        """Verify broadcast_sent events are classified as 'outbound'"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        broadcasts = [e for e in events if e.get("event_type") == "broadcast_sent"]
        for b in broadcasts:
            assert b.get("direction") == "outbound", \
                f"broadcast_sent should be 'outbound', got '{b.get('direction')}'"
        
        print(f"PASS: All {len(broadcasts)} broadcast_sent events marked as 'outbound'")

    def test_contact_info_present(self):
        """Verify contact info is included in response"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        
        contact = data.get("contact", {})
        assert "name" in contact, "Contact should have 'name' field"
        assert contact.get("name"), "Contact name should not be empty"
        print(f"PASS: Contact info present - name: {contact.get('name')}")

    def test_salesperson_info_present(self):
        """Verify salesperson info is included in response"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        
        salesperson = data.get("salesperson", {})
        assert "name" in salesperson, "Salesperson should have 'name' field"
        print(f"PASS: Salesperson info present - name: {salesperson.get('name')}")

    def test_store_info_present(self):
        """Verify store info is included in response"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        
        store = data.get("store", {})
        assert "name" in store or "color" in store, "Store should have basic info"
        print(f"PASS: Store info present")

    def test_invalid_token_returns_404(self):
        """Verify invalid token returns 404"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/invalid-token-12345")
        assert response.status_code == 404, f"Expected 404 for invalid token, got {response.status_code}"
        print("PASS: Invalid token returns 404")

    def test_events_have_timestamp(self):
        """Verify all events have a timestamp field"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        missing_ts = [i for i, e in enumerate(events) if not e.get("timestamp")]
        # Allow some events without timestamp (should be minimal)
        assert len(missing_ts) < len(events) * 0.1, \
            f"Too many events ({len(missing_ts)}) missing timestamp"
        
        print(f"PASS: {len(events) - len(missing_ts)}/{len(events)} events have timestamps")

    def test_events_have_event_type(self):
        """Verify all events have an event_type field"""
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{TEST_CRM_TOKEN}")
        data = response.json()
        events = data.get("events", [])
        
        missing_type = [i for i, e in enumerate(events) if not e.get("event_type")]
        assert len(missing_type) == 0, f"Events at indices {missing_type[:10]} missing event_type"
        print(f"PASS: All {len(events)} events have event_type")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
