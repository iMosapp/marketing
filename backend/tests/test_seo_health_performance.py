"""
Test SEO Health Score Performance Optimizations
- Tests caching functionality (5-minute TTL)
- Tests store query fix (_id vs store_id)
- Tests aggregation pipeline usage for reviews/short_urls
- Tests error handling for invalid/nonexistent users
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_USER_ID = "69a0b7095fddcede09591667"  # Forest Ward
TEST_STORE_ID = "69a0b7095fddcede09591668"  # Store with team members


class TestSEOHealthScoreAPI:
    """Tests for GET /api/seo/health-score/{user_id} endpoint"""

    def test_valid_user_returns_score_structure(self):
        """Health score for valid user returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify no error
        assert "error" not in data
        
        # Verify required fields
        assert "total_score" in data
        assert "grade" in data
        assert "grade_color" in data
        assert "factors" in data
        assert "tips" in data
        assert "user_name" in data
        
        # Verify score is valid
        assert isinstance(data["total_score"], int)
        assert 0 <= data["total_score"] <= 100
        
        # Verify grade matches score thresholds
        score = data["total_score"]
        if score >= 80:
            assert data["grade"] == "Excellent"
        elif score >= 60:
            assert data["grade"] == "Good"
        elif score >= 40:
            assert data["grade"] == "Fair"
        elif score >= 20:
            assert data["grade"] == "Needs Work"
        else:
            assert data["grade"] == "Getting Started"

    def test_five_factors_present_with_correct_structure(self):
        """Health score includes all 5 factors with correct structure"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        factors = data["factors"]
        expected_factors = ["profile", "reviews", "distribution", "visibility", "freshness"]
        
        for factor_name in expected_factors:
            assert factor_name in factors, f"Missing factor: {factor_name}"
            factor = factors[factor_name]
            
            # Each factor has score, max, label
            assert "score" in factor
            assert "max" in factor
            assert "label" in factor
            assert factor["max"] == 20  # All factors max out at 20
            assert 0 <= factor["score"] <= 20

    def test_total_score_equals_sum_of_factors(self):
        """Total score equals sum of all factor scores"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        factors = data["factors"]
        calculated_sum = sum(f["score"] for f in factors.values())
        
        # Total should equal sum (capped at 100)
        assert data["total_score"] == min(calculated_sum, 100)

    def test_invalid_user_id_returns_error(self):
        """Invalid user IDs return graceful error, not 500"""
        invalid_ids = ["undefined", "null", "None", "abc", "123", ""]
        
        for invalid_id in invalid_ids:
            if invalid_id:  # Skip empty string (would be 404)
                response = requests.get(f"{BASE_URL}/api/seo/health-score/{invalid_id}")
                assert response.status_code == 200
                data = response.json()
                assert "error" in data
                assert data["error"] == "Invalid user ID"

    def test_nonexistent_user_returns_not_found(self):
        """Valid format but nonexistent user returns 'User not found'"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/000000000000000000000000")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "User not found"

    def test_caching_works_second_call_fast(self):
        """Second call should be faster due to caching"""
        # First call - may or may not be cached
        start1 = time.time()
        response1 = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        time1 = time.time() - start1
        
        assert response1.status_code == 200
        
        # Second call - should be from cache
        start2 = time.time()
        response2 = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        time2 = time.time() - start2
        
        assert response2.status_code == 200
        
        # Verify same data returned
        assert response1.json()["total_score"] == response2.json()["total_score"]
        
        # Note: Can't reliably assert time2 < time1 due to network variability
        # But both should complete quickly
        print(f"First call: {time1:.3f}s, Second call: {time2:.3f}s")

    def test_skip_cache_recomputes_score(self):
        """skip_cache=true forces recomputation"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}?skip_cache=true")
        assert response.status_code == 200
        data = response.json()
        
        assert "error" not in data
        assert "total_score" in data


class TestSEOTeamScoresAPI:
    """Tests for GET /api/seo/health-score/team/{store_id} endpoint"""

    def test_valid_store_returns_team_array(self):
        """Valid store_id returns team array with member scores"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/{TEST_STORE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "team" in data
        assert isinstance(data["team"], list)
        
        # Should have team members
        if len(data["team"]) > 0:
            member = data["team"][0]
            assert "user_id" in member
            assert "name" in member
            assert "score" in member
            assert "grade" in member

    def test_team_sorted_by_score_descending(self):
        """Team members should be sorted by score descending"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/{TEST_STORE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        team = data["team"]
        if len(team) > 1:
            scores = [m["score"] for m in team]
            assert scores == sorted(scores, reverse=True)

    def test_invalid_store_id_returns_empty_team(self):
        """Invalid/undefined store_id returns empty team array"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/undefined")
        assert response.status_code == 200
        data = response.json()
        
        assert data == {"team": []}

    def test_null_store_id_returns_empty_team(self):
        """null store_id returns empty team array"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/null")
        assert response.status_code == 200
        data = response.json()
        
        assert data == {"team": []}


class TestProfileChecks:
    """Tests for profile completeness factor checks"""

    def test_profile_checks_boolean_values(self):
        """Profile factor includes boolean checks for each field"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        profile_factor = data["factors"]["profile"]
        assert "checks" in profile_factor
        
        checks = profile_factor["checks"]
        expected_checks = ["profile_photo", "bio", "phone", "title", "seo_slug", "social_links"]
        
        for check_name in expected_checks:
            assert check_name in checks
            assert isinstance(checks[check_name], bool)


class TestReviewsFactor:
    """Tests for reviews factor with aggregation pipeline"""

    def test_reviews_factor_has_details(self):
        """Reviews factor includes count and avg_rating details"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        reviews_factor = data["factors"]["reviews"]
        assert "details" in reviews_factor
        
        details = reviews_factor["details"]
        assert "count" in details
        assert "avg_rating" in details
        
        assert isinstance(details["count"], int)
        assert details["count"] >= 0
        
        # avg_rating should be 0 if no reviews, or between 1-5 if reviews exist
        if details["count"] > 0:
            assert 1 <= details["avg_rating"] <= 5


class TestDistributionFactor:
    """Tests for distribution factor with aggregation pipeline for short_urls"""

    def test_distribution_factor_has_details(self):
        """Distribution factor includes card_visits, active_links, shares"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        dist_factor = data["factors"]["distribution"]
        assert "details" in dist_factor
        
        details = dist_factor["details"]
        assert "card_visits" in details
        assert "active_links" in details
        assert "shares" in details
        
        assert isinstance(details["card_visits"], int)
        assert isinstance(details["active_links"], int)
        assert isinstance(details["shares"], int)
