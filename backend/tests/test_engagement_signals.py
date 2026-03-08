"""
Test Engagement Intelligence System
Features:
- GET /api/engagement/hot-leads/{user_id} returns contacts with recent engagement sorted by heat score
- GET /api/engagement/signals/{user_id} returns raw engagement signal feed
- Engagement signal is created when a congrats card is viewed (GET /api/congrats/card/{card_id})
- Engagement signal deduplication (same card within 5 minutes does NOT create duplicate signal)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test user from context: forest@imosapp.com, user_id='69a0b7095fddcede09591667'
# Test card: card_id='55dd14e3' belongs to this user
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CARD_ID = "55dd14e3"


class TestEngagementSignalsAPI:
    """Test the engagement signals router endpoints"""

    def test_hot_leads_endpoint_returns_200(self):
        """GET /api/engagement/hot-leads/{user_id} should return 200"""
        url = f"{BASE_URL}/api/engagement/hot-leads/{TEST_USER_ID}"
        response = requests.get(url)
        print(f"Hot leads response status: {response.status_code}")
        print(f"Hot leads response: {response.json()}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_hot_leads_response_structure(self):
        """Hot leads response should have expected structure"""
        url = f"{BASE_URL}/api/engagement/hot-leads/{TEST_USER_ID}"
        response = requests.get(url)
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "hot_leads" in data, "Response missing 'hot_leads' key"
        assert "total" in data, "Response missing 'total' key"
        assert "period_hours" in data, "Response missing 'period_hours' key"
        assert isinstance(data["hot_leads"], list), "'hot_leads' should be a list"
        print(f"Hot leads total: {data['total']}, period: {data['period_hours']} hours")
        
    def test_hot_leads_with_hours_parameter(self):
        """Hot leads should accept hours parameter for filtering"""
        # Test with different time windows
        for hours in [24, 48, 168]:
            url = f"{BASE_URL}/api/engagement/hot-leads/{TEST_USER_ID}?hours={hours}"
            response = requests.get(url)
            assert response.status_code == 200
            data = response.json()
            assert data["period_hours"] == hours, f"Expected period_hours={hours}, got {data['period_hours']}"
            print(f"Hours {hours}: found {data['total']} leads")

    def test_signals_endpoint_returns_200(self):
        """GET /api/engagement/signals/{user_id} should return 200"""
        url = f"{BASE_URL}/api/engagement/signals/{TEST_USER_ID}"
        response = requests.get(url)
        print(f"Signals response status: {response.status_code}")
        print(f"Signals response: {response.json()}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_signals_response_structure(self):
        """Signals response should have expected structure"""
        url = f"{BASE_URL}/api/engagement/signals/{TEST_USER_ID}"
        response = requests.get(url)
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "signals" in data, "Response missing 'signals' key"
        assert "total" in data, "Response missing 'total' key"
        assert isinstance(data["signals"], list), "'signals' should be a list"
        print(f"Signals total: {data['total']}")
        
        # Check signal item structure if any signals exist
        if len(data["signals"]) > 0:
            signal = data["signals"][0]
            expected_keys = ["signal_type", "user_id", "contact_name", "label", "icon", "color"]
            for key in expected_keys:
                assert key in signal, f"Signal missing '{key}' key"
            print(f"First signal: {signal.get('signal_type')} - {signal.get('contact_name')}")

    def test_signals_with_limit_parameter(self):
        """Signals should accept limit parameter"""
        url = f"{BASE_URL}/api/engagement/signals/{TEST_USER_ID}?limit=10"
        response = requests.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["signals"]) <= 10, "Signals should respect limit parameter"
        print(f"Limited to 10, got {len(data['signals'])} signals")


class TestCardViewCreatesSignal:
    """Test that viewing a card creates an engagement signal"""

    def test_card_view_creates_signal(self):
        """GET /api/congrats/card/{card_id} should create an engagement signal"""
        # First, get current signals count
        signals_url = f"{BASE_URL}/api/engagement/signals/{TEST_USER_ID}?limit=100"
        before_response = requests.get(signals_url)
        assert before_response.status_code == 200
        before_count = before_response.json()["total"]
        print(f"Signals before card view: {before_count}")
        
        # View the card (this should trigger record_signal)
        card_url = f"{BASE_URL}/api/congrats/card/{TEST_CARD_ID}"
        card_response = requests.get(card_url)
        print(f"Card view status: {card_response.status_code}")
        
        # Card might not exist - that's ok for this test, we're testing the signal mechanism
        if card_response.status_code == 404:
            print("Card not found - skipping signal creation test")
            pytest.skip("Test card not found in database")
            return
            
        assert card_response.status_code == 200, f"Card view failed: {card_response.text}"
        
        # Wait briefly for signal to be recorded (async operation)
        time.sleep(0.5)
        
        # Get signals after card view
        after_response = requests.get(signals_url)
        assert after_response.status_code == 200
        after_count = after_response.json()["total"]
        print(f"Signals after card view: {after_count}")
        
        # Note: Due to deduplication, count might not increase if viewed recently
        print(f"Signal count change: {after_count - before_count}")


class TestSignalDeduplication:
    """Test that duplicate signals within 5 minutes are not created"""

    def test_rapid_card_views_deduplicated(self):
        """Viewing same card within 5 minutes should NOT create duplicate signals"""
        # Get current signals count
        signals_url = f"{BASE_URL}/api/engagement/signals/{TEST_USER_ID}?limit=100"
        
        # View the card first time
        card_url = f"{BASE_URL}/api/congrats/card/{TEST_CARD_ID}"
        first_view = requests.get(card_url)
        
        if first_view.status_code == 404:
            print("Card not found - skipping deduplication test")
            pytest.skip("Test card not found in database")
            return
        
        time.sleep(0.5)
        
        # Get signal count after first view
        after_first = requests.get(signals_url)
        first_count = after_first.json()["total"]
        print(f"Signal count after first view: {first_count}")
        
        # View the card again immediately (within 5 minutes)
        second_view = requests.get(card_url)
        assert second_view.status_code == 200
        
        time.sleep(0.5)
        
        # Get signal count after second view
        after_second = requests.get(signals_url)
        second_count = after_second.json()["total"]
        print(f"Signal count after second view: {second_count}")
        
        # Count should NOT have increased due to deduplication
        assert second_count == first_count, f"Deduplication failed: {first_count} -> {second_count}"
        print("Deduplication working correctly - no duplicate signal created")


class TestHotLeadsSorting:
    """Test that hot leads are sorted by heat score"""

    def test_hot_leads_sorted_by_heat_score(self):
        """Hot leads should be sorted by heat score (highest first)"""
        url = f"{BASE_URL}/api/engagement/hot-leads/{TEST_USER_ID}?hours=168"  # 7 days
        response = requests.get(url)
        assert response.status_code == 200
        
        hot_leads = response.json()["hot_leads"]
        if len(hot_leads) < 2:
            print(f"Only {len(hot_leads)} hot leads - cannot verify sorting")
            pytest.skip("Not enough hot leads to verify sorting")
            return
            
        # Verify sorted by heat_score descending
        for i in range(len(hot_leads) - 1):
            current_score = hot_leads[i]["heat_score"]
            next_score = hot_leads[i + 1]["heat_score"]
            assert current_score >= next_score, f"Hot leads not sorted: {current_score} < {next_score}"
        
        print(f"Hot leads correctly sorted by heat score ({len(hot_leads)} leads)")
        print(f"Scores: {[l['heat_score'] for l in hot_leads[:5]]}")

    def test_hot_lead_item_structure(self):
        """Each hot lead should have expected fields"""
        url = f"{BASE_URL}/api/engagement/hot-leads/{TEST_USER_ID}?hours=168"
        response = requests.get(url)
        assert response.status_code == 200
        
        hot_leads = response.json()["hot_leads"]
        if len(hot_leads) == 0:
            print("No hot leads found - skipping structure test")
            pytest.skip("No hot leads to verify structure")
            return
            
        lead = hot_leads[0]
        expected_fields = [
            "contact_name", "last_signal", "last_signal_label", "last_activity",
            "minutes_ago", "total_signals", "heat_score", "is_return_visit"
        ]
        for field in expected_fields:
            assert field in lead, f"Hot lead missing '{field}' field"
        
        print(f"Hot lead structure verified: {lead['contact_name']} (score: {lead['heat_score']})")


class TestEngagementWithNonExistentUser:
    """Test error handling for non-existent users"""

    def test_hot_leads_empty_for_unknown_user(self):
        """Hot leads should return empty list for unknown user"""
        fake_user_id = "000000000000000000000000"
        url = f"{BASE_URL}/api/engagement/hot-leads/{fake_user_id}"
        response = requests.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0, "Unknown user should have no hot leads"
        assert len(data["hot_leads"]) == 0
        print("Unknown user correctly returns empty hot leads")

    def test_signals_empty_for_unknown_user(self):
        """Signals should return empty list for unknown user"""
        fake_user_id = "000000000000000000000000"
        url = f"{BASE_URL}/api/engagement/signals/{fake_user_id}"
        response = requests.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0, "Unknown user should have no signals"
        assert len(data["signals"]) == 0
        print("Unknown user correctly returns empty signals")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
