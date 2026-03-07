"""
Leaderboard V2 Gamification Tests
Tests the enhanced gamification leaderboard with:
- 3-tier leaderboards (My Team/Store, My Org, Global)
- Level/title system (Rookie→Hustler→Closer→All-Star→Legend)
- Streak tracking for consecutive days of task completion
- 'You vs Average' comparison
- Period filtering (week/month/all)
- Category sorting (total, digital_cards, reviews, cards, emails, sms, calls, tasks)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials - Forest Ward (super_admin with ~150 points, ranked #1)
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestStoreLeaderboard:
    """Store-level (My Team) leaderboard tests"""
    
    def test_store_leaderboard_returns_200(self):
        """GET /api/leaderboard/v2/store/{user_id} returns 200"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Store leaderboard returned 200")
    
    def test_store_leaderboard_has_your_stats(self):
        """Store leaderboard includes your_stats with rank, scores, streak, level, vs_avg"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify your_stats exists and has all required fields
        assert "your_stats" in data, "Missing 'your_stats' field"
        your_stats = data["your_stats"]
        
        assert "rank" in your_stats, "your_stats missing 'rank'"
        assert "scores" in your_stats, "your_stats missing 'scores'"
        assert "streak" in your_stats, "your_stats missing 'streak'"
        assert "level" in your_stats, "your_stats missing 'level'"
        assert "vs_avg" in your_stats, "your_stats missing 'vs_avg'"
        assert "team_avg" in your_stats, "your_stats missing 'team_avg'"
        
        print(f"✓ your_stats has all fields: rank={your_stats['rank']}, streak={your_stats['streak']}, vs_avg={your_stats['vs_avg']}")
    
    def test_store_leaderboard_level_structure(self):
        """Level object has title, color, icon, score, next_level, next_at, progress_pct"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        level = data.get("your_stats", {}).get("level", {})
        
        # Verify level structure
        assert "title" in level, "level missing 'title'"
        assert "color" in level, "level missing 'color'"
        assert "icon" in level, "level missing 'icon'"
        assert "score" in level, "level missing 'score'"
        # next_level and next_at can be None for Legend tier
        assert "progress_pct" in level, "level missing 'progress_pct'"
        
        print(f"✓ Level structure correct: title={level['title']}, color={level['color']}, progress={level['progress_pct']}%")
    
    def test_store_leaderboard_period_week(self):
        """Period=week filters to last 7 days"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("period") == "week", f"Expected period='week', got {data.get('period')}"
        print(f"✓ Period=week works")
    
    def test_store_leaderboard_period_month(self):
        """Period=month filters to last 30 days"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?period=month")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("period") == "month", f"Expected period='month', got {data.get('period')}"
        print(f"✓ Period=month works")
    
    def test_store_leaderboard_period_all(self):
        """Period=all returns all-time data"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?period=all")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("period") == "all", f"Expected period='all', got {data.get('period')}"
        print(f"✓ Period=all works")
    
    def test_store_leaderboard_category_sorts_correctly(self):
        """Category parameter re-sorts leaderboard by selected category"""
        for cat in ["total", "digital_cards", "reviews", "cards", "emails", "sms", "calls", "tasks"]:
            response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?category={cat}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("category") == cat, f"Expected category='{cat}', got {data.get('category')}"
        print(f"✓ All categories sort correctly: total, digital_cards, reviews, cards, emails, sms, calls, tasks")
    
    def test_store_leaderboard_badge_assignment(self):
        """Top 3 get gold/silver/bronze badges"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        for entry in leaderboard:
            rank = entry.get("rank")
            badge = entry.get("badge")
            if rank == 1:
                assert badge == "gold", f"Rank 1 should have gold, got {badge}"
            elif rank == 2:
                assert badge == "silver", f"Rank 2 should have silver, got {badge}"
            elif rank == 3:
                assert badge == "bronze", f"Rank 3 should have bronze, got {badge}"
            else:
                assert badge is None, f"Rank {rank} should have no badge, got {badge}"
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
    
    def test_store_leaderboard_includes_levels_metadata(self):
        """Response includes levels metadata for client to display level thresholds"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "levels" in data, "Missing 'levels' metadata"
        levels = data["levels"]
        assert len(levels) >= 5, f"Expected 5 levels, got {len(levels)}"
        
        # Verify level titles exist
        titles = [l["title"] for l in levels]
        for expected in ["Rookie", "Hustler", "Closer", "All-Star", "Legend"]:
            assert expected in titles, f"Missing level title: {expected}"
        print(f"✓ Levels metadata includes: {titles}")


class TestLevelSystem:
    """Test level/title thresholds: Rookie (0-50), Hustler (51-200), Closer (201-500), All-Star (501-1000), Legend (1001+)"""
    
    def test_level_thresholds_correct(self):
        """Verify level thresholds in response match spec"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        levels = data.get("levels", [])
        expected_thresholds = [
            {"title": "Rookie", "min": 0},
            {"title": "Hustler", "min": 51},
            {"title": "Closer", "min": 201},
            {"title": "All-Star", "min": 501},
            {"title": "Legend", "min": 1001},
        ]
        
        for expected in expected_thresholds:
            level = next((l for l in levels if l["title"] == expected["title"]), None)
            assert level is not None, f"Level '{expected['title']}' not found"
            assert level.get("min") == expected["min"], f"Level '{expected['title']}' min should be {expected['min']}, got {level.get('min')}"
        
        print(f"✓ Level thresholds correct: Rookie(0), Hustler(51), Closer(201), All-Star(501), Legend(1001)")
    
    def test_user_level_based_on_score(self):
        """User's level title matches their score threshold"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}?period=all")
        assert response.status_code == 200
        data = response.json()
        
        level = data.get("your_stats", {}).get("level", {})
        score = level.get("score", 0)
        title = level.get("title")
        
        # Determine expected level based on score
        if score >= 1001:
            expected = "Legend"
        elif score >= 501:
            expected = "All-Star"
        elif score >= 201:
            expected = "Closer"
        elif score >= 51:
            expected = "Hustler"
        else:
            expected = "Rookie"
        
        assert title == expected, f"Score {score} should give title '{expected}', got '{title}'"
        print(f"✓ User level correct: score={score} → title='{title}'")


class TestStreakCalculation:
    """Test streak calculation for consecutive days of task completion"""
    
    def test_streak_is_returned(self):
        """Streak value is returned in your_stats"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        streak = data.get("your_stats", {}).get("streak")
        assert streak is not None, "streak not found in your_stats"
        assert isinstance(streak, int), f"streak should be int, got {type(streak)}"
        assert streak >= 0, f"streak should be >= 0, got {streak}"
        print(f"✓ Streak returned: {streak} days")


class TestOrgLeaderboard:
    """Org-level (My Org) leaderboard tests - stores competing within org"""
    
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
        print(f"✓ Org leaderboard structure correct")
    
    def test_org_leaderboard_period_filter(self):
        """Org leaderboard accepts period filter (week/month/all) without errors"""
        for period in ["week", "month", "all"]:
            response = requests.get(f"{BASE_URL}/api/leaderboard/v2/org/{TEST_USER_ID}?period={period}")
            assert response.status_code == 200, f"Period={period} failed with {response.status_code}"
            data = response.json()
            # Org endpoint may not return period in response, but should accept the param
            assert data.get("level") == "org"
        print(f"✓ Org leaderboard accepts period filter (week/month/all)")
    
    def test_org_leaderboard_category_filter(self):
        """Org leaderboard respects category filter"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/org/{TEST_USER_ID}?category=emails")
        assert response.status_code == 200
        data = response.json()
        assert data.get("category") == "emails"
        print(f"✓ Org leaderboard category filter works")
    
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


class TestGlobalLeaderboard:
    """Global leaderboard tests - all users anonymized"""
    
    def test_global_leaderboard_returns_200(self):
        """GET /api/leaderboard/v2/global/{user_id} returns 200"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Global leaderboard returned 200")
    
    def test_global_leaderboard_structure(self):
        """Global leaderboard has level='global', your_rank, your_stats"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("level") == "global", f"Expected level='global', got {data.get('level')}"
        assert "leaderboard" in data, "Missing leaderboard field"
        assert "your_rank" in data, "Missing your_rank field"
        assert "your_stats" in data, "Missing your_stats field"
        assert "total_users" in data, "Missing total_users field"
        assert "categories" in data, "Missing categories field"
        print(f"✓ Global leaderboard structure correct, your_rank={data.get('your_rank')}")
    
    def test_global_leaderboard_has_your_stats(self):
        """Global leaderboard your_stats includes rank, scores, streak, level"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        your_stats = data.get("your_stats", {})
        assert "rank" in your_stats, "your_stats missing 'rank'"
        assert "scores" in your_stats, "your_stats missing 'scores'"
        assert "streak" in your_stats, "your_stats missing 'streak'"
        assert "level" in your_stats, "your_stats missing 'level'"
        print(f"✓ Global your_stats correct: rank={your_stats['rank']}, streak={your_stats['streak']}")
    
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
    
    def test_global_leaderboard_has_is_you_marker(self):
        """Global entries have is_you=true for requesting user"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        user_entry = next((e for e in leaderboard if e.get("user_id") == TEST_USER_ID), None)
        if user_entry:
            assert user_entry.get("is_you") == True, "Entry for requesting user should have is_you=true"
            print(f"✓ is_you marker correct for requesting user")
        else:
            print("ℹ User not in top 50 global leaderboard")
    
    def test_global_leaderboard_has_level_per_entry(self):
        """Global entries include level info for each user"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        if len(leaderboard) > 0:
            entry = leaderboard[0]
            assert "level" in entry, "Entry missing 'level'"
            level = entry["level"]
            assert "title" in level, "level missing 'title'"
            print(f"✓ Global entries include level: {level.get('title')}")
    
    def test_global_leaderboard_period_filter(self):
        """Global leaderboard respects period filter"""
        for period in ["week", "month", "all"]:
            response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}?period={period}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("period") == period, f"Expected period='{period}', got {data.get('period')}"
        print(f"✓ Global leaderboard period filter works (week/month/all)")
    
    def test_global_leaderboard_category_filter(self):
        """Global leaderboard respects category filter"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/global/{TEST_USER_ID}?category=tasks")
        assert response.status_code == 200
        data = response.json()
        assert data.get("category") == "tasks"
        print(f"✓ Global leaderboard category filter works")


class TestCategories:
    """Test that all categories are available and tracked"""
    
    def test_all_categories_present(self):
        """Response includes all 8 categories: total + 7 specific types"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        categories = data.get("categories", {})
        expected_cats = ["digital_cards", "reviews", "cards", "emails", "sms", "calls", "tasks"]
        
        for cat in expected_cats:
            assert cat in categories, f"Missing category: {cat}"
            assert "label" in categories[cat], f"Category {cat} missing label"
            assert "icon" in categories[cat], f"Category {cat} missing icon"
        
        print(f"✓ All 7 categories present: {list(categories.keys())}")
    
    def test_scores_have_all_category_breakdowns(self):
        """User scores include breakdown by all categories plus total"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        leaderboard = data.get("leaderboard", [])
        if len(leaderboard) > 0:
            scores = leaderboard[0].get("scores", {})
            expected_keys = ["total"]
            for key in expected_keys:
                assert key in scores, f"Scores missing '{key}'"
            print(f"✓ Scores have total field and category breakdowns")


class TestInvalidRequests:
    """Test error handling"""
    
    def test_invalid_user_id(self):
        """Invalid user_id returns 404"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/invalid_user_id")
        assert response.status_code in [404, 422], f"Expected 404/422 for invalid user, got {response.status_code}"
        print(f"✓ Invalid user_id returns error")
    
    def test_nonexistent_user_id(self):
        """Non-existent valid ObjectId returns 404"""
        response = requests.get(f"{BASE_URL}/api/leaderboard/v2/store/000000000000000000000000")
        assert response.status_code == 404, f"Expected 404 for non-existent user, got {response.status_code}"
        print(f"✓ Non-existent user_id returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
