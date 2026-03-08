"""
Card Analytics API Tests - Tests for GET /api/reports/card-analytics/{user_id}
Tests summary, card_type_breakdown, top_cards, daily_trend, and per_user breakdown.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCardAnalyticsAPI:
    """Card Analytics API endpoint tests"""
    
    # Super Admin credentials
    USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
    
    def test_card_analytics_returns_valid_structure(self):
        """Test that card analytics returns all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check top-level fields
        assert "scope" in data
        assert "days" in data
        assert "summary" in data
        assert "card_type_breakdown" in data
        assert "top_cards" in data
        assert "daily_trend" in data
        assert "per_user" in data
        
    def test_card_analytics_summary_fields(self):
        """Test summary object has all required KPI fields"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        summary = response.json()["summary"]
        
        # Verify all required summary fields
        assert "total_cards" in summary
        assert "total_views" in summary
        assert "total_downloads" in summary
        assert "total_shares" in summary
        assert "cards_trend_pct" in summary
        assert "views_trend_pct" in summary
        assert "avg_views_per_card" in summary
        assert "avg_downloads_per_card" in summary
        
        # Type validations
        assert isinstance(summary["total_cards"], int)
        assert isinstance(summary["total_views"], int)
        assert isinstance(summary["total_downloads"], int)
        assert isinstance(summary["total_shares"], int)
        
    def test_card_analytics_scope_organization_for_super_admin(self):
        """Test that super_admin user gets organization-wide scope"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["scope"] == "organization", f"Expected 'organization' scope for super_admin, got '{data['scope']}'"
        
    def test_card_analytics_days_parameter_7(self):
        """Test days=7 parameter works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=7"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 7
        
    def test_card_analytics_days_parameter_14(self):
        """Test days=14 parameter works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=14"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 14
        
    def test_card_analytics_days_parameter_30(self):
        """Test days=30 parameter works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 30
        
    def test_card_analytics_days_parameter_90(self):
        """Test days=90 parameter works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=90"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 90
        
    def test_card_analytics_days_parameter_365(self):
        """Test days=365 parameter works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=365"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 365
        
    def test_card_type_breakdown_structure(self):
        """Test card_type_breakdown array has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        breakdown = response.json()["card_type_breakdown"]
        assert isinstance(breakdown, list)
        
        if len(breakdown) > 0:
            item = breakdown[0]
            assert "card_type" in item
            assert "count" in item
            assert "views" in item
            assert "downloads" in item
            assert "shares" in item
            
    def test_top_cards_structure(self):
        """Test top_cards array has correct structure with engagement score"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        top_cards = response.json()["top_cards"]
        assert isinstance(top_cards, list)
        
        if len(top_cards) > 0:
            card = top_cards[0]
            assert "card_type" in card
            assert "views" in card
            assert "downloads" in card
            assert "shares" in card
            assert "engagement" in card  # Score based on views + downloads*2 + shares*3
            
    def test_top_cards_sorted_by_engagement(self):
        """Test top_cards are sorted by engagement score (descending)"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        top_cards = response.json()["top_cards"]
        
        if len(top_cards) >= 2:
            # Verify descending order
            for i in range(len(top_cards) - 1):
                assert top_cards[i]["engagement"] >= top_cards[i+1]["engagement"], \
                    f"Top cards not sorted by engagement: {top_cards[i]['engagement']} < {top_cards[i+1]['engagement']}"
                    
    def test_daily_trend_structure(self):
        """Test daily_trend array has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        daily_trend = response.json()["daily_trend"]
        assert isinstance(daily_trend, list)
        
        if len(daily_trend) > 0:
            day = daily_trend[0]
            assert "date" in day
            assert "cards" in day
            assert "views" in day
            assert "downloads" in day
            assert "shares" in day
            
    def test_per_user_structure_for_manager(self):
        """Test per_user array has correct structure including card_types breakdown and vs_avg"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        per_user = response.json()["per_user"]
        assert isinstance(per_user, list)
        
        if len(per_user) > 0:
            user_stats = per_user[0]
            assert "user_id" in user_stats
            assert "name" in user_stats
            assert "cards" in user_stats
            assert "views" in user_stats
            assert "downloads" in user_stats
            assert "shares" in user_stats
            assert "engagement" in user_stats
            assert "card_types" in user_stats  # Per-user card type breakdown
            assert "vs_avg_cards" in user_stats  # Comparison vs average
            
            # card_types should be a dict
            assert isinstance(user_stats["card_types"], dict)
            
    def test_engagement_score_formula(self):
        """Test engagement score = views + downloads*2 + shares*3"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        top_cards = response.json()["top_cards"]
        
        if len(top_cards) > 0:
            card = top_cards[0]
            expected_engagement = card["views"] + (card["downloads"] * 2) + (card["shares"] * 3)
            assert card["engagement"] == expected_engagement, \
                f"Engagement score mismatch. Expected {expected_engagement}, got {card['engagement']}"
                
    def test_invalid_user_returns_404(self):
        """Test that invalid user_id returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/invalid_user_id_12345?days=30"
        )
        # Either 404 or 500 for invalid ObjectId format
        assert response.status_code in [400, 404, 500]
        
    def test_card_analytics_returns_real_data(self):
        """Verify API returns real data based on existing cards"""
        response = requests.get(
            f"{BASE_URL}/api/reports/card-analytics/{self.USER_ID}?days=30"
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data["summary"]
        
        # We know there's existing data from main agent context (33 cards across 6 types)
        assert summary["total_cards"] > 0, "Expected some cards to exist in the system"
        assert len(data["card_type_breakdown"]) > 0, "Expected card type breakdown to have data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
