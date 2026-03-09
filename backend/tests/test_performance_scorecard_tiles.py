"""
Test Performance Scorecard and Clickable Tiles - Iteration 167
Tests: Daily Scorecard, Showcase sharing, New Leads, Click-through detail categories
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"

class TestPerformanceScorecard:
    """Tests for the new daily scorecard feature"""
    
    def test_performance_returns_scorecard(self):
        """Performance endpoint includes scorecard object with today, yesterday, diff"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        assert response.status_code == 200
        data = response.json()
        
        # Scorecard object must exist
        assert "scorecard" in data, "Response missing 'scorecard' field"
        sc = data["scorecard"]
        
        # Scorecard fields
        assert "today" in sc, "Scorecard missing 'today'"
        assert "yesterday" in sc, "Scorecard missing 'yesterday'"
        assert "diff" in sc, "Scorecard missing 'diff'"
        
        # diff = today - yesterday
        assert sc["diff"] == sc["today"] - sc["yesterday"], "Scorecard diff calculation incorrect"
        
        # Values should be integers
        assert isinstance(sc["today"], int)
        assert isinstance(sc["yesterday"], int)
        assert isinstance(sc["diff"], int)
        print(f"PASSED: Scorecard - today={sc['today']}, yesterday={sc['yesterday']}, diff={sc['diff']}")

    def test_performance_scorecard_regardless_of_period(self):
        """Scorecard always shows today vs yesterday regardless of period filter"""
        # Test with different periods
        for period in ["today", "week", "month"]:
            response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period={period}")
            assert response.status_code == 200
            data = response.json()
            assert "scorecard" in data, f"Scorecard missing for period={period}"
        print("PASSED: Scorecard present for all periods")


class TestShowcaseSharing:
    """Tests for the new Showcase sharing category"""
    
    def test_performance_includes_showcase_in_sharing(self):
        """Performance endpoint includes sharing.showcase field counting showroom_shared events"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "sharing" in data, "Response missing 'sharing' field"
        assert "showcase" in data["sharing"], "sharing missing 'showcase' field"
        assert isinstance(data["sharing"]["showcase"], int)
        print(f"PASSED: sharing.showcase = {data['sharing']['showcase']}")

    def test_detail_showcase_returns_showroom_shared_events(self):
        """Detail endpoint for showcase returns showroom_shared events"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=showcase&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data, "Response missing 'events' field"
        assert "count" in data, "Response missing 'count' field"
        
        # If events exist, verify structure
        if data["events"]:
            event = data["events"][0]
            assert "event_type" in event
            assert event["event_type"] == "showroom_shared", f"Expected showroom_shared, got {event['event_type']}"
            assert "contact_name" in event
            assert "timestamp" in event
        print(f"PASSED: showcase detail returns {data['count']} events")


class TestNewLeadsDetail:
    """Tests for the New Leads clickable category"""
    
    def test_detail_new_leads_returns_contacts(self):
        """Detail endpoint for new_leads returns recently created contacts"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=new_leads&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        # If contacts exist, verify structure
        if data["events"]:
            event = data["events"][0]
            assert event["event_type"] == "new_lead", f"Expected new_lead, got {event['event_type']}"
            assert "contact_name" in event
            assert "contact_id" in event
            assert "content" in event  # Added via source info
            assert "timestamp" in event
        print(f"PASSED: new_leads detail returns {data['count']} contacts")


class TestClickThroughDetails:
    """Tests for click-through breakdown detail categories"""
    
    def test_detail_digital_card_views(self):
        """Detail endpoint for digital_card_views returns card_viewed and digital_card_viewed events"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=digital_card_views&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        if data["events"]:
            event = data["events"][0]
            assert event["event_type"] in ["card_viewed", "digital_card_viewed"], f"Unexpected event_type: {event['event_type']}"
        print(f"PASSED: digital_card_views detail returns {data['count']} events")

    def test_detail_review_link_clicks(self):
        """Detail endpoint for review_link_clicks returns review click events"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=review_link_clicks&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        if data["events"]:
            event = data["events"][0]
            assert "review_link_clicked" in event["event_type"].lower() or event["event_type"] == "review_link_clicked"
        print(f"PASSED: review_link_clicks detail returns {data['count']} events")

    def test_detail_showcase_views(self):
        """Detail endpoint for showcase_views returns showcase view events"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=showcase_views&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        if data["events"]:
            event = data["events"][0]
            assert event["event_type"] in ["showcase_viewed", "showroom_viewed"], f"Unexpected event_type: {event['event_type']}"
        print(f"PASSED: showcase_views detail returns {data['count']} events")

    def test_detail_link_page_visits(self):
        """Detail endpoint for link_page_visits returns link page view events"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=link_page_visits&period=week")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        if data["events"]:
            event = data["events"][0]
            assert event["event_type"] == "link_page_viewed"
        print(f"PASSED: link_page_visits detail returns {data['count']} events")


class TestExistingDetailCategories:
    """Verify existing detail categories still work"""
    
    def test_detail_texts(self):
        """Texts detail endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=texts&period=week")
        assert response.status_code == 200
        print(f"PASSED: texts detail returns {response.json().get('count', 0)} events")

    def test_detail_emails(self):
        """Emails detail endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=emails&period=week")
        assert response.status_code == 200
        print(f"PASSED: emails detail returns {response.json().get('count', 0)} events")

    def test_detail_calls(self):
        """Calls detail endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=calls&period=week")
        assert response.status_code == 200
        print(f"PASSED: calls detail returns {response.json().get('count', 0)} events")

    def test_detail_my_card(self):
        """My Card detail endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=my_card&period=week")
        assert response.status_code == 200
        print(f"PASSED: my_card detail returns {response.json().get('count', 0)} events")

    def test_detail_reviews(self):
        """Reviews detail endpoint works"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance/detail?category=reviews&period=week")
        assert response.status_code == 200
        print(f"PASSED: reviews detail returns {response.json().get('count', 0)} events")


class TestPerformanceResponseStructure:
    """Test full response structure"""
    
    def test_full_performance_structure(self):
        """Verify all expected fields in performance response"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        assert response.status_code == 200
        data = response.json()
        
        # Top-level fields
        assert "total_touchpoints" in data
        assert "trend_pct" in data
        assert "scorecard" in data
        assert "communication" in data
        assert "sharing" in data
        assert "engagement" in data
        assert "click_through" in data
        
        # Communication fields
        comm = data["communication"]
        assert "texts" in comm
        assert "emails" in comm
        assert "calls" in comm
        
        # Sharing fields
        sharing = data["sharing"]
        assert "my_card" in sharing
        assert "reviews" in sharing
        assert "card_shares" in sharing
        assert "showcase" in sharing  # NEW
        
        # Engagement fields
        eng = data["engagement"]
        assert "link_clicks" in eng
        assert "email_opens" in eng
        assert "replies" in eng
        assert "new_leads" in eng
        
        # Click-through fields
        ctr = data["click_through"]
        assert "digital_card_views" in ctr
        assert "review_link_clicks" in ctr
        assert "showcase_views" in ctr
        assert "link_page_visits" in ctr
        
        print("PASSED: Full performance response structure verified")
