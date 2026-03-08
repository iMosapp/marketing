"""
Test Team Engagement Feature - Manager Hot Leads Dashboard
Tests:
1. GET /api/engagement/team-hot-leads/{manager_id} - Team hot leads for manager
2. GET /api/engagement/team-hot-leads/{manager_id}?hours=24 - Respects hours filter
3. POST /api/engagement/reassign-lead - Lead reassignment (manager only, org-owned only)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"


class TestTeamHotLeadsEndpoint:
    """Tests for GET /api/engagement/team-hot-leads/{manager_id}"""

    def test_get_team_hot_leads_returns_correct_structure(self):
        """Verify team hot leads endpoint returns expected data structure"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify top-level keys exist
        assert "hot_leads" in data, "Missing 'hot_leads' key"
        assert "team_stats" in data, "Missing 'team_stats' key"
        assert "alert_leads" in data, "Missing 'alert_leads' key"
        assert "total" in data, "Missing 'total' key"
        assert "period_hours" in data, "Missing 'period_hours' key"
        
        # Verify types
        assert isinstance(data["hot_leads"], list), "hot_leads should be a list"
        assert isinstance(data["team_stats"], list), "team_stats should be a list"
        assert isinstance(data["alert_leads"], list), "alert_leads should be a list"
        assert isinstance(data["total"], int), "total should be an integer"
        assert isinstance(data["period_hours"], int), "period_hours should be an integer"
        
        print(f"Team hot leads response: {len(data['hot_leads'])} leads, {len(data['team_stats'])} team members")

    def test_get_team_hot_leads_default_period_is_48_hours(self):
        """Default period should be 48 hours"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["period_hours"] == 48, f"Default period should be 48 hours, got {data['period_hours']}"

    def test_get_team_hot_leads_respects_hours_filter_24(self):
        """Verify hours=24 filter is respected"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}?hours=24")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["period_hours"] == 24, f"Expected period_hours=24, got {data['period_hours']}"

    def test_get_team_hot_leads_respects_hours_filter_168(self):
        """Verify hours=168 (7 days) filter is respected"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}?hours=168")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["period_hours"] == 168, f"Expected period_hours=168, got {data['period_hours']}"

    def test_lead_has_can_reassign_field(self):
        """Verify hot leads include can_reassign field"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["hot_leads"]) > 0:
            lead = data["hot_leads"][0]
            assert "can_reassign" in lead, "Lead should have 'can_reassign' field"
            assert isinstance(lead["can_reassign"], bool), "can_reassign should be boolean"
            # Verify other expected fields
            assert "contact_name" in lead
            assert "rep_name" in lead
            assert "heat_score" in lead
            print(f"First lead: {lead['contact_name']} (rep: {lead['rep_name']}, can_reassign: {lead['can_reassign']})")
        else:
            print("No hot leads to verify can_reassign field")

    def test_team_stats_structure(self):
        """Verify team_stats has correct structure"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["team_stats"]) > 0:
            stat = data["team_stats"][0]
            expected_fields = ["user_id", "name", "calls", "texts", "emails", "cards", "engagement_signals", "total_activity"]
            for field in expected_fields:
                assert field in stat, f"Team stat missing '{field}' field"
            print(f"Team stats sample: {stat['name']} - {stat['total_activity']} total activities")
        else:
            print("No team stats to verify")

    def test_alert_leads_have_3_plus_interactions(self):
        """Alert leads should be those with 3+ interactions"""
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/{SUPER_ADMIN_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Every alert lead should have total_signals >= 3
        for lead in data["alert_leads"]:
            assert lead.get("total_signals", 0) >= 3, \
                f"Alert lead {lead.get('contact_name')} has only {lead.get('total_signals')} signals"
        
        print(f"Alert leads count: {len(data['alert_leads'])}")

    def test_invalid_manager_id_returns_500(self):
        """Invalid (non-ObjectId) manager ID returns 500 - KNOWN BUG to report"""
        # This test documents current behavior - should ideally return 200 with empty results
        # or 400/404 for invalid ObjectId
        response = requests.get(f"{BASE_URL}/api/engagement/team-hot-leads/invalid_id_12345")
        
        # Currently returns 500 due to invalid ObjectId handling
        assert response.status_code == 500, f"Expected 500 for invalid manager id, got {response.status_code}"
        print("BUG: Invalid manager ID should return graceful error or empty results, not 500")


class TestReassignLeadEndpoint:
    """Tests for POST /api/engagement/reassign-lead"""

    def test_reassign_lead_requires_manager_role(self):
        """Non-managers (role=user) should get 403"""
        # First, get a regular user from the database
        # For this test, we'll need to find a user with role='user'
        # Using a fake user ID that doesn't exist should also fail
        response = requests.post(
            f"{BASE_URL}/api/engagement/reassign-lead",
            json={"contact_id": "507f1f77bcf86cd799439011", "new_user_id": SUPER_ADMIN_ID},
            headers={"X-User-ID": "507f1f77bcf86cd799439000"}  # Non-existent user
        )
        
        # Should fail because user doesn't exist or doesn't have manager role
        assert response.status_code in [403, 404], \
            f"Expected 403/404 for non-manager, got {response.status_code}: {response.text}"

    def test_reassign_lead_requires_contact_id(self):
        """Missing contact_id should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/engagement/reassign-lead",
            json={"new_user_id": SUPER_ADMIN_ID},
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 400, f"Expected 400 for missing contact_id, got {response.status_code}"

    def test_reassign_lead_requires_new_user_id(self):
        """Missing new_user_id should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/engagement/reassign-lead",
            json={"contact_id": "507f1f77bcf86cd799439011"},
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 400, f"Expected 400 for missing new_user_id, got {response.status_code}"

    def test_reassign_lead_contact_not_found(self):
        """Non-existent contact should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/engagement/reassign-lead",
            json={"contact_id": "507f1f77bcf86cd799439099", "new_user_id": SUPER_ADMIN_ID},
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent contact, got {response.status_code}"

    def test_reassign_personal_contact_blocked(self):
        """Personal contacts (ownership_type != 'org') should return 403"""
        # Use known personal contact: Jane Doe (ID: 69a1dbb4320d732f90069652, ownership_type=personal)
        personal_contact_id = "69a1dbb4320d732f90069652"
        
        response = requests.post(
            f"{BASE_URL}/api/engagement/reassign-lead",
            json={"contact_id": personal_contact_id, "new_user_id": SUPER_ADMIN_ID},
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        
        assert response.status_code == 403, \
            f"Expected 403 for personal contact reassign, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "organization-created" in data.get("detail", "").lower() or "org" in data.get("detail", "").lower(), \
            f"Expected error about org-owned leads, got: {data}"
        print("Verified: Personal contact correctly blocked from reassignment")


class TestIndividualHotLeadsEndpoint:
    """Test existing individual hot leads endpoint still works"""

    def test_individual_hot_leads_endpoint_works(self):
        """Verify the individual user hot leads endpoint"""
        response = requests.get(f"{BASE_URL}/api/engagement/hot-leads/{SUPER_ADMIN_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "hot_leads" in data
        assert "total" in data
        assert "period_hours" in data
        print(f"Individual hot leads: {data['total']} leads in {data['period_hours']} hours")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
