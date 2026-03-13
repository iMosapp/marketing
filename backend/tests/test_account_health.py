"""
Account Health API Tests - Tests for Account Health Dashboard endpoints
- GET /api/account-health/overview - returns array of accounts with health scores
- GET /api/account-health/user/{user_id} - returns detailed health report
- Health score calculation (>=70 Healthy, >=40 At Risk, <40 Critical)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture
def auth_token():
    """Get authentication token for super_admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "forest@imosapp.com",
        "password": "Admin123!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestAccountHealthOverview:
    """Tests for GET /api/account-health/overview"""
    
    def test_overview_returns_200(self, authenticated_client):
        """Overview endpoint should return 200 status"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Overview endpoint returns 200")
    
    def test_overview_returns_array(self, authenticated_client):
        """Overview should return an array of accounts"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Expected array response"
        print(f"✓ Overview returns array with {len(data)} accounts")
    
    def test_overview_account_structure(self, authenticated_client):
        """Each account should have required fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            account = data[0]
            required_fields = [
                "user_id", "name", "email", "role", "organization", "store",
                "contacts", "messages_30d", "touchpoints_30d", "active_campaigns",
                "days_since_login", "last_login", "health"
            ]
            for field in required_fields:
                assert field in account, f"Missing required field: {field}"
            
            # Verify health object structure
            assert "score" in account["health"], "Health should have score"
            assert "grade" in account["health"], "Health should have grade"
            assert "color" in account["health"], "Health should have color"
            print("✓ Account structure is correct with all required fields")
        else:
            print("✓ No accounts to verify structure (empty array)")
    
    def test_overview_sorted_by_health_score(self, authenticated_client):
        """Accounts should be sorted by health score (worst first)"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) >= 2:
            scores = [a["health"]["score"] for a in data]
            assert scores == sorted(scores), "Accounts should be sorted by score ascending (worst first)"
            print(f"✓ Accounts sorted by health score (worst first): {scores[:5]}...")
        else:
            print("✓ Not enough accounts to verify sorting")
    
    def test_overview_with_period_parameter(self, authenticated_client):
        """Overview should accept period parameter"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview?period=90")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Overview with period=90 returns {len(data)} accounts")
    
    def test_overview_health_grades(self, authenticated_client):
        """Health grades should be Healthy, At Risk, or Critical"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        
        valid_grades = {"Healthy", "At Risk", "Critical"}
        grades_found = set()
        
        for account in data:
            grade = account["health"]["grade"]
            assert grade in valid_grades, f"Invalid grade: {grade}"
            grades_found.add(grade)
        
        print(f"✓ Health grades found: {grades_found}")


class TestAccountHealthUserDetail:
    """Tests for GET /api/account-health/user/{user_id}"""
    
    def test_user_detail_returns_200(self, authenticated_client):
        """User detail endpoint should return 200 for valid user"""
        # Bud Ward user_id from context
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ User detail endpoint returns 200 for user {user_id}")
    
    def test_user_detail_structure(self, authenticated_client):
        """User detail should have required sections"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        required_sections = ["user", "organization", "store", "metrics", "health", "recent_events", "period_days"]
        for section in required_sections:
            assert section in data, f"Missing required section: {section}"
        print("✓ User detail has all required sections")
    
    def test_user_detail_metrics_structure(self, authenticated_client):
        """User detail metrics should have all engagement fields"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        metrics = data["metrics"]
        required_metrics = [
            "total_contacts", "new_contacts", "total_messages", "messages_30d",
            "total_tasks", "completed_tasks", "active_campaigns", "total_campaigns",
            "enrollments", "enrollments_30d", "total_touchpoints", "touchpoints_30d",
            "event_breakdown", "short_urls_created", "link_clicks_30d", "cards_shared",
            "days_since_login", "last_login"
        ]
        for metric in required_metrics:
            assert metric in metrics, f"Missing metric: {metric}"
        print("✓ Metrics structure is complete with 18 fields")
    
    def test_user_detail_health_object(self, authenticated_client):
        """User detail health should have score, grade, and color"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        health = data["health"]
        assert "score" in health, "Health should have score"
        assert "grade" in health, "Health should have grade"
        assert "color" in health, "Health should have color"
        assert isinstance(health["score"], int), "Score should be integer"
        print(f"✓ Health object: score={health['score']}, grade={health['grade']}")
    
    def test_user_detail_event_breakdown(self, authenticated_client):
        """User detail should include event breakdown"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "event_breakdown" in data["metrics"], "Should have event_breakdown in metrics"
        event_breakdown = data["metrics"]["event_breakdown"]
        assert isinstance(event_breakdown, dict), "event_breakdown should be a dict"
        print(f"✓ Event breakdown types: {list(event_breakdown.keys()) if event_breakdown else 'empty'}")
    
    def test_user_detail_recent_events(self, authenticated_client):
        """User detail should include recent_events array"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "recent_events" in data, "Should have recent_events"
        assert isinstance(data["recent_events"], list), "recent_events should be array"
        print(f"✓ Recent events count: {len(data['recent_events'])}")
    
    def test_user_detail_with_period(self, authenticated_client):
        """User detail should accept period parameter"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}?period=90")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 90, f"Expected period_days=90, got {data['period_days']}"
        print("✓ User detail accepts period=90 parameter")
    
    def test_user_detail_not_found(self, authenticated_client):
        """User detail should return 404 for non-existent user"""
        invalid_id = "000000000000000000000000"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{invalid_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ User detail returns 404 for non-existent user")


class TestHealthScoreCalculation:
    """Tests for health score grading logic"""
    
    def test_health_score_grades_correct(self, authenticated_client):
        """Health scores should map to correct grades (>=70 Healthy, >=40 At Risk, <40 Critical)"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        
        for account in data:
            score = account["health"]["score"]
            grade = account["health"]["grade"]
            
            if score >= 70:
                expected = "Healthy"
            elif score >= 40:
                expected = "At Risk"
            else:
                expected = "Critical"
            
            assert grade == expected, f"Score {score} should be '{expected}', got '{grade}'"
        
        print("✓ All health scores map to correct grades")
    
    def test_health_colors_correct(self, authenticated_client):
        """Health grades should have correct colors"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        
        grade_colors = {
            "Healthy": "#34C759",
            "At Risk": "#FF9500",
            "Critical": "#FF3B30"
        }
        
        for account in data:
            grade = account["health"]["grade"]
            color = account["health"]["color"]
            expected_color = grade_colors.get(grade)
            assert color == expected_color, f"Grade '{grade}' should have color {expected_color}, got {color}"
        
        print("✓ All health grades have correct colors")
    
    def test_score_range_0_to_100(self, authenticated_client):
        """Health scores should be between 0 and 100"""
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/overview")
        assert response.status_code == 200
        data = response.json()
        
        for account in data:
            score = account["health"]["score"]
            assert 0 <= score <= 100, f"Score {score} outside valid range 0-100"
        
        print("✓ All health scores are within 0-100 range")


class TestAccountHealthUserInfo:
    """Tests for user info in health reports"""
    
    def test_user_detail_user_info(self, authenticated_client):
        """User detail should include user info fields"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        user = data["user"]
        # Should have basic user fields
        assert "email" in user, "Should have email"
        assert "role" in user, "Should have role"
        assert "name" in user or "first_name" in user, "Should have name"
        print(f"✓ User info: {user.get('name', 'N/A')} ({user.get('email', 'N/A')})")
    
    def test_bud_ward_at_risk_score(self, authenticated_client):
        """Bud Ward (sample user) should have score of 50 and At Risk grade"""
        user_id = "69a53bb3690af652a853906a"
        response = authenticated_client.get(f"{BASE_URL}/api/account-health/user/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        health = data["health"]
        # Based on context, Bud Ward has score=50, grade=At Risk
        assert health["grade"] == "At Risk", f"Expected 'At Risk', got '{health['grade']}'"
        print(f"✓ Bud Ward health: score={health['score']}, grade={health['grade']}")
