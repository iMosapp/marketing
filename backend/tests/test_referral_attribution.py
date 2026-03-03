"""
Referral Attribution System Tests
Tests for ref code backfill, resolution, demo request attribution, and analytics
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRefCodeBackfill:
    """Test POST /api/auth/ref/backfill endpoint"""
    
    def test_backfill_ref_codes(self):
        """Backfill should succeed and return count of backfilled users"""
        response = requests.post(f"{BASE_URL}/api/auth/ref/backfill")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        assert "backfilled" in data
        print(f"Backfilled {data['backfilled']} users with ref codes")


class TestRefCodeResolution:
    """Test GET /api/auth/ref/{ref_code} endpoint"""
    
    def test_resolve_forest_ward_ref_code(self):
        """Forest Ward's ref code 34C53029 should resolve to user info"""
        ref_code = "34C53029"
        response = requests.get(f"{BASE_URL}/api/auth/ref/{ref_code}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("status") == "found", f"Expected 'found' but got {data}"
        assert "user_id" in data
        assert "name" in data
        # Should be Forest Ward
        print(f"Ref code {ref_code} resolved to: {data.get('name')} (role: {data.get('role')})")
    
    def test_resolve_invalid_ref_code(self):
        """Invalid ref code should return not_found status"""
        response = requests.get(f"{BASE_URL}/api/auth/ref/INVALID123")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "not_found"


class TestLoginRefCode:
    """Test that login returns ref_code for users"""
    
    def test_login_returns_ref_code(self):
        """Login for forest@imosapp.com should return ref_code 34C53029"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "user" in data
        user = data["user"]
        assert "ref_code" in user, "User should have ref_code field"
        print(f"User ref_code: {user.get('ref_code')}")
        # Forest Ward's ref code should be 34C53029
        assert user.get("ref_code") == "34C53029", f"Expected 34C53029 but got {user.get('ref_code')}"


class TestDemoRequestWithRef:
    """Test POST /api/demo-requests with ref parameter"""
    
    def test_create_demo_request_with_ref(self):
        """Demo request with ref param should store referred_by fields"""
        test_email = f"TEST_refattr_{datetime.now().strftime('%H%M%S')}@test.com"
        payload = {
            "name": "Test Referral User",
            "email": test_email,
            "company": "Test Company",
            "phone": "555-1234",
            "source": "digital_card_hero",
            "ref": "34C53029"  # Forest Ward's ref code
        }
        
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        
        # Verify the request was stored with referral info
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        assert list_response.status_code == 200
        requests_list = list_response.json()
        
        # Find our test request
        test_request = None
        for req in requests_list:
            # Backend stores email in lowercase
            if req.get("email") == test_email.lower():
                test_request = req
                break
        
        assert test_request is not None, "Test request not found in list"
        
        # Verify referral fields
        assert test_request.get("referred_by") == "34C53029", f"Expected ref code 34C53029, got {test_request.get('referred_by')}"
        assert test_request.get("referred_by_user_id") is not None, "referred_by_user_id should be set"
        assert test_request.get("referred_by_name") is not None, "referred_by_name should be set"
        assert test_request.get("referrer_type") is not None, "referrer_type should be set"
        
        print(f"Referral fields: referred_by={test_request.get('referred_by')}, "
              f"user_id={test_request.get('referred_by_user_id')}, "
              f"name={test_request.get('referred_by_name')}, "
              f"type={test_request.get('referrer_type')}")


class TestReferrerTypeClassification:
    """Test the referrer_type classification logic"""
    
    def test_internal_referrer_type_for_super_admin(self):
        """Super admin ref should classify as 'internal'"""
        # Forest Ward is a super_admin, so referrer_type should be 'internal'
        test_email = f"TEST_internal_{datetime.now().strftime('%H%M%S')}@test.com"
        payload = {
            "name": "Test Internal Referral",
            "email": test_email,
            "source": "test_source",
            "ref": "34C53029"  # Forest Ward (super_admin)
        }
        
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        # Get the request to verify referrer_type
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        requests_list = list_response.json()
        
        test_request = next((r for r in requests_list if r.get("email") == test_email.lower()), None)
        assert test_request is not None
        
        # Super admin should be classified as 'internal'
        assert test_request.get("referrer_type") == "internal", \
            f"Expected 'internal' for super_admin, got {test_request.get('referrer_type')}"


class TestAnalyticsWithReferrer:
    """Test GET /api/demo-requests/analytics includes by_referrer"""
    
    def test_analytics_includes_by_referrer(self):
        """Analytics endpoint should include by_referrer array"""
        response = requests.get(f"{BASE_URL}/api/demo-requests/analytics?days=30")
        assert response.status_code == 200
        data = response.json()
        
        # Verify standard analytics fields exist
        assert "summary" in data
        assert "by_channel" in data
        assert "by_page" in data
        assert "by_source" in data
        
        # Verify by_referrer exists in response
        assert "by_referrer" in data, "Analytics should include 'by_referrer' array"
        
        by_referrer = data.get("by_referrer", [])
        print(f"by_referrer has {len(by_referrer)} entries")
        
        # If there are referrals, verify structure
        if len(by_referrer) > 0:
            first_ref = by_referrer[0]
            assert "ref_code" in first_ref, "Referrer entry should have ref_code"
            assert "name" in first_ref, "Referrer entry should have name"
            assert "type" in first_ref, "Referrer entry should have type"
            assert "count" in first_ref, "Referrer entry should have count"
            print(f"First referrer: {first_ref}")


class TestDemoRequestSourceAndRef:
    """Test demo request with both source and ref parameters"""
    
    def test_create_with_source_and_ref(self):
        """Demo request should correctly store both source and ref"""
        test_email = f"TEST_sourceref_{datetime.now().strftime('%H%M%S')}@test.com"
        payload = {
            "name": "Test Source And Ref",
            "email": test_email,
            "company": "Test Corp",
            "source": "digital_card_hero",
            "ref": "34C53029"
        }
        
        response = requests.post(f"{BASE_URL}/api/demo-requests", json=payload)
        assert response.status_code == 200
        
        # Verify in list
        list_response = requests.get(f"{BASE_URL}/api/demo-requests")
        requests_list = list_response.json()
        
        test_request = next((r for r in requests_list if r.get("email") == test_email.lower()), None)
        assert test_request is not None
        
        # Both source and ref should be stored
        assert test_request.get("source") == "digital_card_hero"
        assert test_request.get("source_page") == "digital_card"
        assert test_request.get("source_position") == "hero"
        assert test_request.get("referred_by") == "34C53029"
        assert test_request.get("referred_by_name") is not None
        
        print(f"Request has source={test_request.get('source')} and ref={test_request.get('referred_by')}")


# Cleanup after tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed demo requests after tests"""
    yield
    # Note: In production, would delete TEST_ prefixed data
    # For this system, demo requests don't have a delete endpoint
    print("Test cleanup: TEST_ prefixed demo requests remain in database")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
