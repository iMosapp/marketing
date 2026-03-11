"""
Tests for Customer Performance / Customer Rankings API
Tests the GET /api/tracking/customer-rankings/{user_id} endpoint
with various period and scope filters.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestCustomerRankings:
    """Tests for the customer rankings endpoint"""
    
    def test_rankings_all_period_user_scope(self):
        """Test rankings with period=all and scope=user"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "all", "scope": "user"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rankings" in data, "Response should contain rankings"
        assert "period" in data, "Response should contain period"
        assert "scope" in data, "Response should contain scope"
        assert data["period"] == "all", f"Period should be 'all', got {data['period']}"
        assert data["scope"] == "user", f"Scope should be 'user', got {data['scope']}"
        
        # Verify rankings is a list
        assert isinstance(data["rankings"], list), "Rankings should be a list"
        print(f"✓ Rankings with period=all, scope=user: {len(data['rankings'])} contacts returned")
    
    def test_rankings_today_period(self):
        """Test rankings with period=today"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "today"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rankings" in data
        assert data["period"] == "today"
        print(f"✓ Rankings with period=today: {len(data['rankings'])} contacts returned")
    
    def test_rankings_week_period(self):
        """Test rankings with period=week"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "week"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rankings" in data
        assert data["period"] == "week"
        print(f"✓ Rankings with period=week: {len(data['rankings'])} contacts returned")
    
    def test_rankings_month_period(self):
        """Test rankings with period=month"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "month"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rankings" in data
        assert data["period"] == "month"
        print(f"✓ Rankings with period=month: {len(data['rankings'])} contacts returned")
    
    def test_rankings_org_scope(self):
        """Test rankings with scope=org"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "month", "scope": "org"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rankings" in data
        assert data["scope"] == "org"
        print(f"✓ Rankings with scope=org: {len(data['rankings'])} contacts returned")
    
    def test_rankings_global_scope(self):
        """Test rankings with scope=global"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "month", "scope": "global"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rankings" in data
        assert data["scope"] == "global"
        print(f"✓ Rankings with scope=global: {len(data['rankings'])} contacts returned")
    
    def test_rankings_data_structure(self):
        """Test that rankings contain all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "all", "scope": "user"}
        )
        assert response.status_code == 200
        
        data = response.json()
        rankings = data.get("rankings", [])
        
        if len(rankings) > 0:
            contact = rankings[0]
            
            # Check required fields exist
            required_fields = ["contact_id", "name", "score", "event_count", "breakdown", "last_activity"]
            for field in required_fields:
                assert field in contact, f"Contact should have '{field}' field"
            
            # Verify data types
            assert isinstance(contact["contact_id"], str), "contact_id should be string"
            assert isinstance(contact["name"], str), "name should be string"
            assert isinstance(contact["score"], (int, float)), "score should be numeric"
            assert isinstance(contact["event_count"], int), "event_count should be int"
            assert isinstance(contact["breakdown"], dict), "breakdown should be dict"
            
            print(f"✓ Top contact: {contact['name']} with score {contact['score']}, {contact['event_count']} events")
            print(f"  Breakdown: {len(contact['breakdown'])} event types")
        else:
            print("✓ No rankings returned (empty data)")
    
    def test_rankings_are_sorted_by_score(self):
        """Test that rankings are sorted by score descending"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "all", "scope": "user"}
        )
        assert response.status_code == 200
        
        data = response.json()
        rankings = data.get("rankings", [])
        
        if len(rankings) > 1:
            scores = [r["score"] for r in rankings]
            assert scores == sorted(scores, reverse=True), "Rankings should be sorted by score descending"
            print(f"✓ Rankings are correctly sorted by score (top: {scores[0]}, bottom: {scores[-1]})")
        else:
            print("✓ Not enough rankings to verify sort order")
    
    def test_rankings_breakdown_contains_event_counts(self):
        """Test that breakdown contains event type counts"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "all", "scope": "user"}
        )
        assert response.status_code == 200
        
        data = response.json()
        rankings = data.get("rankings", [])
        
        if len(rankings) > 0:
            contact = rankings[0]
            breakdown = contact.get("breakdown", {})
            
            # Verify breakdown values are integers
            for event_type, count in breakdown.items():
                assert isinstance(count, int), f"Event count for '{event_type}' should be int"
                assert count > 0, f"Event count for '{event_type}' should be positive"
            
            print(f"✓ Breakdown contains {len(breakdown)} event types with valid counts")
            # Print a few sample event types
            sample_events = list(breakdown.items())[:3]
            for evt, cnt in sample_events:
                print(f"  - {evt}: {cnt}")
        else:
            print("✓ No rankings to verify breakdown structure")


class TestCustomerRankingsEdgeCases:
    """Edge case tests for customer rankings"""
    
    def test_rankings_invalid_user_id(self):
        """Test rankings with an invalid user_id (should return empty or 200)"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/invalid_user_id_12345",
            params={"period": "all", "scope": "user"}
        )
        # Should not crash, either returns 200 with empty or handles gracefully
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print(f"✓ Invalid user_id handled gracefully (status: {response.status_code})")
    
    def test_rankings_default_params(self):
        """Test rankings with default parameters (no params specified)"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}"
        )
        assert response.status_code == 200
        
        data = response.json()
        # Default should be period=month, scope=user
        assert data["period"] == "month", f"Default period should be 'month', got {data['period']}"
        assert data["scope"] == "user", f"Default scope should be 'user', got {data['scope']}"
        print("✓ Default params work correctly (period=month, scope=user)")
    
    def test_rankings_limit(self):
        """Test that rankings are limited to 50 results"""
        response = requests.get(
            f"{BASE_URL}/api/tracking/customer-rankings/{TEST_USER_ID}",
            params={"period": "all", "scope": "global"}  # Global scope to get max results
        )
        assert response.status_code == 200
        
        data = response.json()
        rankings = data.get("rankings", [])
        assert len(rankings) <= 50, f"Rankings should be limited to 50, got {len(rankings)}"
        print(f"✓ Rankings limited correctly: {len(rankings)} contacts (max 50)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
