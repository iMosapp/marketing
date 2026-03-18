"""
SEO Health Score API Tests
Tests the SEO/AEO Health Score endpoints for individual users and team leaderboards
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSEOHealthScore:
    """Tests for GET /api/seo/health-score/{user_id}"""
    
    test_user_id = "69a0b7095fddcede09591667"  # Forest Ward - Super Admin
    
    def test_health_score_returns_valid_structure(self):
        """Test that health score endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required top-level fields
        assert "total_score" in data
        assert "grade" in data
        assert "grade_color" in data
        assert "factors" in data
        assert "tips" in data
        
        # Validate score is in valid range (0-100)
        assert 0 <= data["total_score"] <= 100
        
        # Validate grade is one of expected values
        valid_grades = ["Excellent", "Good", "Fair", "Needs Work", "Getting Started"]
        assert data["grade"] in valid_grades
        
        # Validate grade color is a hex color
        assert data["grade_color"].startswith("#")
        assert len(data["grade_color"]) == 7
        
    def test_health_score_factors_structure(self):
        """Test that all 5 factors are present with correct structure"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        factors = response.json()["factors"]
        
        # Check all 5 factors exist
        expected_factors = ["profile", "reviews", "distribution", "visibility", "freshness"]
        for factor_key in expected_factors:
            assert factor_key in factors, f"Missing factor: {factor_key}"
            
            factor = factors[factor_key]
            # Each factor should have score, max, and label
            assert "score" in factor
            assert "max" in factor
            assert "label" in factor
            assert factor["max"] == 20, f"Factor {factor_key} max should be 20"
            assert 0 <= factor["score"] <= 20
            
    def test_health_score_profile_checks(self):
        """Test that profile factor includes detailed checks"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        profile_factor = response.json()["factors"]["profile"]
        assert "checks" in profile_factor
        
        expected_checks = ["profile_photo", "bio", "phone", "title", "seo_slug", "social_links"]
        for check in expected_checks:
            assert check in profile_factor["checks"], f"Missing profile check: {check}"
            assert isinstance(profile_factor["checks"][check], bool)
            
    def test_health_score_reviews_details(self):
        """Test that reviews factor includes count and avg_rating"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        reviews_factor = response.json()["factors"]["reviews"]
        assert "details" in reviews_factor
        assert "count" in reviews_factor["details"]
        assert "avg_rating" in reviews_factor["details"]
        
    def test_health_score_tips_array(self):
        """Test that tips array contains valid tip objects"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        tips = response.json()["tips"]
        assert isinstance(tips, list)
        
        # Tips should be sorted by points (highest first)
        if len(tips) > 1:
            for i in range(len(tips) - 1):
                assert tips[i]["points"] >= tips[i+1]["points"], "Tips should be sorted by points descending"
        
        for tip in tips:
            assert "tip" in tip
            assert "points" in tip
            assert isinstance(tip["tip"], str)
            assert isinstance(tip["points"], int)
            
    def test_health_score_includes_user_name(self):
        """Test that response includes user_name field"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "user_name" in data
        assert data["user_name"] == "Forest Ward"
        
    def test_health_score_invalid_user_returns_error(self):
        """Test that invalid user ID returns error"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/invalid_user_id_123")
        # Should return 200 with error field or 404
        if response.status_code == 200:
            data = response.json()
            assert "error" in data
            
    def test_health_score_nonexistent_user(self):
        """Test that nonexistent user returns error"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/000000000000000000000000")
        # Should return 200 with error or 404
        if response.status_code == 200:
            data = response.json()
            assert "error" in data


class TestSEOTeamScores:
    """Tests for GET /api/seo/health-score/team/{store_id}"""
    
    test_store_id = "69a0b7095fddcede09591668"  # imos-demo store
    
    def test_team_scores_returns_team_array(self):
        """Test that team endpoint returns team array"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/{self.test_store_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "team" in data
        assert isinstance(data["team"], list)
        
    def test_team_scores_member_structure(self):
        """Test that each team member has correct fields"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/{self.test_store_id}")
        assert response.status_code == 200
        
        team = response.json()["team"]
        assert len(team) > 0, "Team should have at least one member"
        
        for member in team:
            assert "user_id" in member
            assert "name" in member
            assert "title" in member
            assert "score" in member
            assert "grade" in member
            assert "review_count" in member
            assert "card_visits" in member
            
            # Validate score range
            assert 0 <= member["score"] <= 100
            
            # Validate grade
            valid_grades = ["Excellent", "Good", "Fair", "Needs Work", "Getting Started"]
            assert member["grade"] in valid_grades
            
    def test_team_scores_sorted_by_score(self):
        """Test that team is sorted by score descending"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/{self.test_store_id}")
        assert response.status_code == 200
        
        team = response.json()["team"]
        if len(team) > 1:
            for i in range(len(team) - 1):
                assert team[i]["score"] >= team[i+1]["score"], "Team should be sorted by score descending"
                
    def test_team_scores_empty_store(self):
        """Test that nonexistent store returns empty team"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/000000000000000000000000")
        assert response.status_code == 200
        
        data = response.json()
        assert "team" in data
        assert isinstance(data["team"], list)
        assert len(data["team"]) == 0
        
    def test_team_scores_invalid_store_id(self):
        """Test that invalid store ID returns empty team or handles gracefully"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/team/invalid_store_id")
        # Should handle gracefully - either return empty team or error
        assert response.status_code in [200, 400, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "team" in data
            assert isinstance(data["team"], list)


class TestSEOHealthScoreCalculation:
    """Tests for score calculation accuracy"""
    
    test_user_id = "69a0b7095fddcede09591667"  # Forest Ward
    
    def test_total_score_equals_sum_of_factors(self):
        """Test that total_score is the sum of all factor scores"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        data = response.json()
        factors = data["factors"]
        
        calculated_total = sum(f["score"] for f in factors.values())
        # Total should be capped at 100
        expected_total = min(calculated_total, 100)
        assert data["total_score"] == expected_total
        
    def test_grade_matches_score_range(self):
        """Test that grade correctly matches score range"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        data = response.json()
        score = data["total_score"]
        grade = data["grade"]
        
        if score >= 80:
            assert grade == "Excellent"
        elif score >= 60:
            assert grade == "Good"
        elif score >= 40:
            assert grade == "Fair"
        elif score >= 20:
            assert grade == "Needs Work"
        else:
            assert grade == "Getting Started"
            
    def test_profile_check_consistency(self):
        """Test that profile checks reflect user data accurately"""
        response = requests.get(f"{BASE_URL}/api/seo/health-score/{self.test_user_id}")
        assert response.status_code == 200
        
        checks = response.json()["factors"]["profile"]["checks"]
        
        # For Forest Ward, we know:
        # - Has bio: true
        # - Has phone: true
        # - Has title: true
        # - Has seo_slug: true (from previous test)
        # - Has social_links: true (likely)
        # - profile_photo: could be true or false
        
        assert checks["bio"] == True, "Forest Ward should have bio"
        assert checks["phone"] == True, "Forest Ward should have phone"
        assert checks["title"] == True, "Forest Ward should have title"
        assert checks["seo_slug"] == True, "Forest Ward should have seo_slug"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
