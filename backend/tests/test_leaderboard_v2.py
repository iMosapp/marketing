"""
Leaderboard V2 API Tests
Tests the 3-level gamification leaderboard: Store, Org, and Global levels
Categories: digital_cards, reviews, congrats, emails, sms, voice_notes
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_USER_ID = "69a0b7095fddcede09591667"  # Forest Ward - super_admin

class TestLeaderboardV2Store:
    """Store-level leaderboard tests - users within same account"""
    
    def test_store_leaderboard_returns_200(self):
        """GET /api/leaderboard/v2/store/{user_id} returns 200"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Store leaderboard returned 200")
    
    def test_store_leaderboard_structure(self):
        """Store leaderboard has required fields: level, leaderboard, team_summary, categories"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "level" in data, "Missing 'level' field"
        assert data["level"] == "store", f"Expected level='store', got {data['level']}"
        assert "leaderboard" in data, "Missing 'leaderboard' field"
        assert "team_summary" in data, "Missing 'team_summary' field"
        assert "categories" in data, "Missing 'categories' field"
        assert "your_user_id" in data, "Missing 'your_user_id' field"
        assert data["your_user_id"] == TEST_USER_ID
        print(f"✓ Store leaderboard has correct structure")
    
    def test_store_leaderboard_entries_have_required_fields(self):
        """Each leaderboard entry has: user_id, name, rank, badge, scores"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        if len(leaderboard) > 0:
            entry = leaderboard[0]
            assert "user_id" in entry, "Entry missing user_id"
            assert "name" in entry, "Entry missing name"
            assert "rank" in entry, "Entry missing rank"
            assert "badge" in entry, "Entry missing badge field (can be null)"
            assert "scores" in entry, "Entry missing scores"
            # Verify scores has categories
            scores = entry["scores"]
            assert "total" in scores, "Scores missing 'total'"
            print(f"✓ Store leaderboard entries have correct fields")
        else:
            print("ℹ No leaderboard entries found (empty store)")
    
    def test_store_leaderboard_badge_assignment(self):
        """Rank 1=gold, rank 2=silver, rank 3=bronze"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        for entry in leaderboard[:3]:  # Only top 3 get badges
            rank = entry.get("rank")
            badge = entry.get("badge")
            if rank == 1:
                assert badge == "gold", f"Rank 1 should have gold badge, got {badge}"
            elif rank == 2:
                assert badge == "silver", f"Rank 2 should have silver badge, got {badge}"
            elif rank == 3:
                assert badge == "bronze", f"Rank 3 should have bronze badge, got {badge}"
        
        # Rank 4+ should have no badge
        for entry in leaderboard[3:]:
            assert entry.get("badge") is None, f"Rank {entry.get('rank')} should have no badge"
        print(f"✓ Badge assignment correct (gold/silver/bronze for top 3)")
    
    def test_store_leaderboard_team_summary(self):
        """Team summary has team_total, members, avg_score"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("team_summary", {})
        assert "team_total" in summary, "team_summary missing team_total"
        assert "members" in summary, "team_summary missing members"
        assert "avg_score" in summary, "team_summary missing avg_score"
        print(f"✓ Team summary: total={summary.get('team_total')}, members={summary.get('members')}, avg={summary.get('avg_score')}")
    
    def test_store_leaderboard_month_filter(self):
        """Month/year filtering works: ?month=2&year=2026 returns filtered data"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?month=2&year=2026")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("month") == 2, f"Expected month=2, got {data.get('month')}"
        assert data.get("year") == 2026, f"Expected year=2026, got {data.get('year')}"
        print(f"✓ Month/year filter works - Feb 2026 data")
    
    def test_store_leaderboard_category_filter(self):
        """Category filtering works: ?category=emails returns users ranked by emails"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?category=emails")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("category") == "emails", f"Expected category='emails', got {data.get('category')}"
        print(f"✓ Category filter works - emails category")
    
    def test_store_leaderboard_invalid_user(self):
        """Invalid user_id returns 404"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/invalid_user_id")
        assert response.status_code in [404, 422], f"Expected 404/422 for invalid user, got {response.status_code}"
        print(f"✓ Invalid user_id returns error")


class TestLeaderboardV2Org:
    """Org-level leaderboard tests - stores competing within org"""
    
    def test_org_leaderboard_returns_200(self):
        """GET /api/leaderboard/v2/org/{user_id} returns 200"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/org/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Org leaderboard returned 200")
    
    def test_org_leaderboard_structure(self):
        """Org leaderboard has level='org' and store rankings"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/org/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("level") == "org", f"Expected level='org', got {data.get('level')}"
        assert "leaderboard" in data, "Missing leaderboard field"
        assert "categories" in data, "Missing categories field"
        print(f"✓ Org leaderboard has correct structure")
    
    def test_org_leaderboard_store_entries(self):
        """Org leaderboard entries have store_id, store_name, members, scores"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/org/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        if len(leaderboard) > 0:
            entry = leaderboard[0]
            assert "store_id" in entry or "store_name" in entry, "Entry missing store identifier"
            assert "members" in entry, "Entry missing members count"
            assert "scores" in entry, "Entry missing scores"
            assert "rank" in entry, "Entry missing rank"
            print(f"✓ Org leaderboard entries have store info")
        else:
            print("ℹ No org leaderboard entries (no org or single store)")
    
    def test_org_leaderboard_month_filter(self):
        """Org leaderboard respects month/year filter"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/org/{TEST_USER_ID}?month=2&year=2026")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("month") == 2
        assert data.get("year") == 2026
        print(f"✓ Org leaderboard month filter works")


class TestLeaderboardV2Global:
    """Global leaderboard tests - all users anonymized"""
    
    def test_global_leaderboard_returns_200(self):
        """GET /api/leaderboard/v2/global/{user_id} returns 200"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Global leaderboard returned 200")
    
    def test_global_leaderboard_structure(self):
        """Global leaderboard has level='global', your_rank, anonymized entries"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("level") == "global", f"Expected level='global', got {data.get('level')}"
        assert "leaderboard" in data, "Missing leaderboard field"
        assert "your_rank" in data, "Missing your_rank field (shows requesting user's position)"
        assert "total_users" in data, "Missing total_users field"
        assert "categories" in data, "Missing categories field"
        print(f"✓ Global leaderboard structure correct, your_rank={data.get('your_rank')}")
    
    def test_global_leaderboard_anonymization(self):
        """Global entries have display_name (initials) instead of real names"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        if len(leaderboard) > 0:
            entry = leaderboard[0]
            assert "display_name" in entry, "Entry missing display_name for anonymization"
            display_name = entry.get("display_name", "")
            # Display name should be initials like "F. W." or "User #1"
            assert "." in display_name or "User #" in display_name, f"Display name not anonymized: {display_name}"
            print(f"✓ Global leaderboard uses anonymized display_name: '{display_name}'")
        else:
            print("ℹ No global leaderboard entries")
    
    def test_global_leaderboard_no_photos(self):
        """Global leaderboard entries have photo=None for anonymization"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        for entry in leaderboard:
            assert entry.get("photo") is None, f"Global entry should not have photo"
        print(f"✓ Global leaderboard has no photos (anonymized)")
    
    def test_global_leaderboard_your_rank_correct(self):
        """your_rank field shows requesting user's position"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        your_rank = data.get("your_rank")
        leaderboard = data.get("leaderboard", [])
        
        # Find the requesting user in leaderboard
        user_entry = next((e for e in leaderboard if e.get("user_id") == TEST_USER_ID), None)
        if user_entry:
            assert your_rank == user_entry.get("rank"), f"your_rank ({your_rank}) doesn't match entry rank ({user_entry.get('rank')})"
        print(f"✓ your_rank field correct: {your_rank}")
    
    def test_global_leaderboard_month_filter(self):
        """Global leaderboard respects month/year filter"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}?month=2&year=2026")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("month") == 2
        assert data.get("year") == 2026
        print(f"✓ Global leaderboard month filter works")
    
    def test_global_leaderboard_category_filter(self):
        """Global leaderboard respects category filter"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}?category=sms")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("category") == "sms"
        print(f"✓ Global leaderboard category filter works")


class TestLeaderboardV2Categories:
    """Test that all categories are available and tracked"""
    
    def test_categories_present_in_response(self):
        """Response includes category definitions with labels and icons"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        categories = data.get("categories", {})
        expected_cats = ["digital_cards", "reviews", "congrats", "emails", "sms", "voice_notes"]
        
        for cat in expected_cats:
            assert cat in categories, f"Missing category: {cat}"
            assert "label" in categories[cat], f"Category {cat} missing label"
            assert "icon" in categories[cat], f"Category {cat} missing icon"
        
        print(f"✓ All 6 categories present: {list(categories.keys())}")
    
    def test_scores_have_all_category_breakdowns(self):
        """User scores include breakdown by all categories"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        if len(leaderboard) > 0:
            scores = leaderboard[0].get("scores", {})
            expected_keys = ["total", "digital_cards", "reviews", "congrats", "emails", "sms", "voice_notes"]
            for key in expected_keys:
                assert key in scores, f"Scores missing '{key}'"
            print(f"✓ Scores have all category breakdowns: {list(scores.keys())}")
        else:
            print("ℹ No leaderboard entries to check scores")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
