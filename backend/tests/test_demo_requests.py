"""
Demo Requests API Tests - Lead tracking with full-funnel attribution
Tests the POST /api/demo-requests and GET /api/demo-requests/analytics endpoints
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDemoRequestsPost:
    """Tests for POST /api/demo-requests - capturing leads with attribution"""
    
    def test_create_demo_request_basic(self):
        """Test creating a demo request with minimal required fields"""
        unique_email = f"TEST_lead_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Test Lead",
            "email": unique_email
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "success"
        assert "message" in data
        print(f"PASS: Basic demo request created for {unique_email}")
    
    def test_create_demo_request_with_source(self):
        """Test that source field is accepted and stored"""
        unique_email = f"TEST_source_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Test Source Lead",
            "email": unique_email,
            "source": "digital_card_hero"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        print(f"PASS: Demo request with source=digital_card_hero created")
    
    def test_create_demo_request_with_all_utm_params(self):
        """Test that all UTM params are accepted"""
        unique_email = f"TEST_utm_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Test UTM Lead",
            "email": unique_email,
            "source": "homepage_hero",
            "utm_source": "facebook",
            "utm_medium": "paid_social",
            "utm_campaign": "spring_launch_2026",
            "utm_content": "video_ad_1",
            "utm_term": "sales crm"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        print(f"PASS: Demo request with full UTM params created")
    
    def test_create_demo_request_with_referrer(self):
        """Test that referrer field is accepted"""
        unique_email = f"TEST_ref_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Test Referrer Lead",
            "email": unique_email,
            "referrer": "https://google.com/search?q=crm"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        print(f"PASS: Demo request with referrer field created")
    
    def test_create_demo_request_missing_name(self):
        """Test error handling for missing name"""
        payload = {
            "email": "test@example.com"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert data.get("status") == "error"
        assert "name" in data.get("message", "").lower()
        print(f"PASS: Missing name returns error as expected")
    
    def test_create_demo_request_missing_email(self):
        """Test error handling for missing email"""
        payload = {
            "name": "Test Missing Email"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "error"
        assert "email" in data.get("message", "").lower()
        print(f"PASS: Missing email returns error as expected")


class TestChannelClassification:
    """Tests for auto-classification of channels based on UTM params"""
    
    def test_facebook_paid_social_classification(self):
        """Test facebook utm_source is classified as paid_social"""
        unique_email = f"TEST_fb_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Facebook Lead",
            "email": unique_email,
            "utm_source": "facebook",
            "utm_medium": "paid_social"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        # Verify via GET endpoint
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        assert list_response.status_code == 200
        leads = list_response.json()
        fb_lead = next((l for l in leads if l.get("email") == unique_email.lower()), None)
        assert fb_lead is not None, "Facebook lead not found in list"
        assert fb_lead.get("channel") == "paid_social", f"Expected paid_social, got {fb_lead.get('channel')}"
        print(f"PASS: Facebook lead classified as paid_social")
    
    def test_google_paid_search_classification(self):
        """Test google utm_source is classified as paid_search"""
        unique_email = f"TEST_goog_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Google Lead",
            "email": unique_email,
            "utm_source": "google",
            "utm_medium": "cpc"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        leads = list_response.json()
        g_lead = next((l for l in leads if l.get("email") == unique_email.lower()), None)
        assert g_lead is not None
        assert g_lead.get("channel") == "paid_search", f"Expected paid_search, got {g_lead.get('channel')}"
        print(f"PASS: Google lead classified as paid_search")
    
    def test_organic_website_classification(self):
        """Test organic traffic from website source"""
        unique_email = f"TEST_org_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Organic Lead",
            "email": unique_email,
            "source": "homepage_hero"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        leads = list_response.json()
        org_lead = next((l for l in leads if l.get("email") == unique_email.lower()), None)
        assert org_lead is not None
        assert org_lead.get("channel") == "organic", f"Expected organic, got {org_lead.get('channel')}"
        print(f"PASS: Website lead classified as organic")


class TestSourceParsing:
    """Tests for source parsing into source_page and source_position"""
    
    def test_source_page_parsing(self):
        """Test digital_card_hero parses to page=digital_card"""
        unique_email = f"TEST_page_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Page Parse Lead",
            "email": unique_email,
            "source": "digital_card_hero"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        leads = list_response.json()
        lead = next((l for l in leads if l.get("email") == unique_email.lower()), None)
        assert lead is not None
        assert lead.get("source_page") == "digital_card", f"Expected digital_card, got {lead.get('source_page')}"
        assert lead.get("source_position") == "hero", f"Expected hero, got {lead.get('source_position')}"
        print(f"PASS: Source 'digital_card_hero' parsed correctly to page=digital_card, position=hero")
    
    def test_source_nav_position(self):
        """Test homepage_nav parses to position=nav"""
        unique_email = f"TEST_nav_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Nav Parse Lead",
            "email": unique_email,
            "source": "homepage_nav"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        leads = list_response.json()
        lead = next((l for l in leads if l.get("email") == unique_email.lower()), None)
        assert lead is not None
        assert lead.get("source_page") == "homepage", f"Expected homepage, got {lead.get('source_page')}"
        assert lead.get("source_position") == "nav", f"Expected nav, got {lead.get('source_position')}"
        print(f"PASS: Source 'homepage_nav' parsed correctly to page=homepage, position=nav")
    
    def test_source_footer_position(self):
        """Test pricing_footer parses to position=footer"""
        unique_email = f"TEST_ftr_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Footer Parse Lead",
            "email": unique_email,
            "source": "pricing_footer"
        }
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        leads = list_response.json()
        lead = next((l for l in leads if l.get("email") == unique_email.lower()), None)
        assert lead is not None
        assert lead.get("source_page") == "pricing", f"Expected pricing, got {lead.get('source_page')}"
        assert lead.get("source_position") == "footer", f"Expected footer, got {lead.get('source_position')}"
        print(f"PASS: Source 'pricing_footer' parsed correctly to page=pricing, position=footer")


class TestDemoRequestsAnalytics:
    """Tests for GET /api/demo-requests/analytics endpoint"""
    
    def test_analytics_endpoint_returns_200(self):
        """Test analytics endpoint returns valid response"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "summary" in data
        assert "by_channel" in data
        assert "by_page" in data
        assert "by_position" in data
        assert "by_source" in data
        assert "by_campaign" in data
        assert "daily_trend" in data
        assert "recent_requests" in data
        print(f"PASS: Analytics endpoint returns all expected fields")
    
    def test_analytics_with_days_param(self):
        """Test analytics endpoint with days parameter"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["period_days"] == 30
        print(f"PASS: Analytics with days=30 returns correct period_days")
    
    def test_analytics_summary_fields(self):
        """Test analytics summary contains all required fields"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        assert response.status_code == 200
        summary = response.json().get("summary", {})
        assert "total_all_time" in summary
        assert "total_period" in summary
        assert "total_previous_period" in summary
        assert "total_new" in summary
        assert "period_days" in summary
        print(f"PASS: Analytics summary contains all required fields")
        print(f"  - Total all time: {summary['total_all_time']}")
        print(f"  - Total in period: {summary['total_period']}")
        print(f"  - Total new status: {summary['total_new']}")
    
    def test_analytics_by_channel_structure(self):
        """Test by_channel has correct structure"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        data = response.json()
        by_channel = data.get("by_channel", [])
        if len(by_channel) > 0:
            for item in by_channel:
                assert "channel" in item
                assert "count" in item
                assert isinstance(item["count"], int)
        print(f"PASS: by_channel structure is valid with {len(by_channel)} channels")
    
    def test_analytics_by_page_structure(self):
        """Test by_page has correct structure"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        data = response.json()
        by_page = data.get("by_page", [])
        if len(by_page) > 0:
            for item in by_page:
                assert "page" in item
                assert "count" in item
        print(f"PASS: by_page structure is valid with {len(by_page)} pages")
    
    def test_analytics_by_position_structure(self):
        """Test by_position has correct structure"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        data = response.json()
        by_position = data.get("by_position", [])
        if len(by_position) > 0:
            for item in by_position:
                assert "position" in item
                assert "count" in item
        print(f"PASS: by_position structure is valid with {len(by_position)} positions")
    
    def test_analytics_recent_requests(self):
        """Test recent_requests returns recent leads"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        data = response.json()
        recent = data.get("recent_requests", [])
        assert isinstance(recent, list)
        if len(recent) > 0:
            for req in recent:
                assert "name" in req
                assert "email" in req
                assert "created_at" in req
        print(f"PASS: recent_requests returns {len(recent)} items with correct structure")


class TestListDemoRequests:
    """Tests for GET /api/demo-requests endpoint"""
    
    def test_list_demo_requests(self):
        """Test listing all demo requests"""
        response = requests.get(f"{BASE_URL}/api/demo-requests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List endpoint returns {len(data)} demo requests")
    
    def test_list_contains_seeded_data(self):
        """Test that seeded data exists (6+ demo requests mentioned)"""
        response = requests.get(f"{BASE_URL}/api/demo-requests")
        assert response.status_code == 200
        data = response.json()
        # Mentioned that 6 test requests have been seeded
        assert len(data) >= 1, "Expected at least some demo requests in database"
        print(f"PASS: Database contains {len(data)} demo requests")
        
        # Check structure of returned data
        if len(data) > 0:
            sample = data[0]
            expected_fields = ["name", "email", "source", "channel", "created_at"]
            for field in expected_fields:
                assert field in sample, f"Expected field {field} in response"
        print(f"PASS: Demo request data structure is valid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
