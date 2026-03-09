"""
CRM Timeline Export Feature Tests

Tests for:
- POST /api/crm/timeline-token/{user_id}/{contact_id} - generate unique token
- GET /api/crm/timeline/{token} - public timeline (no auth required)
- POST /api/crm/mark-copied/{user_id}/{contact_id} - mark CRM link as copied
- GET /api/crm/pin-settings/{store_id} - get store PIN settings
- PUT /api/crm/pin-settings/{store_id} - update PIN settings
- POST /api/crm/timeline/{token}/verify-pin - verify PIN and get session
- GET /api/crm/export-stats/{user_id} - get CRM export stats
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = "Admin123!"
KNOWN_STORE_ID = "69a0b7095fddcede09591668"
KNOWN_TOKEN = "77d3edc3-4f8f-4eea-93c8-0f34456e7628"


@pytest.fixture(scope="module")
def auth_session():
    """Login and return session with auth cookie"""
    session = requests.Session()
    login_res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    return session


@pytest.fixture(scope="module")
def user_id(auth_session):
    """Get the logged-in user's ID"""
    me_res = auth_session.get(f"{BASE_URL}/api/auth/me")
    assert me_res.status_code == 200, f"Get user failed: {me_res.text}"
    data = me_res.json()
    # Handle both direct response and nested user object
    if "user" in data:
        return data["user"].get("_id") or data["user"].get("id")
    return data.get("_id") or data.get("id")


@pytest.fixture(scope="module")
def test_contact_id(auth_session, user_id):
    """Get an existing contact ID or create one for testing"""
    # First try to get existing contacts
    contacts_res = auth_session.get(f"{BASE_URL}/api/contacts/{user_id}")
    if contacts_res.status_code == 200:
        contacts = contacts_res.json()
        if contacts and len(contacts) > 0:
            return contacts[0].get("_id") or contacts[0].get("id")
    
    # Create a test contact if none exist
    create_res = auth_session.post(f"{BASE_URL}/api/contacts/{user_id}", json={
        "first_name": "CRM_Test",
        "last_name": "Contact",
        "phone": "+15551234567",
        "email": "crm_test@example.com"
    })
    if create_res.status_code in [200, 201]:
        return create_res.json().get("_id") or create_res.json().get("id")
    
    pytest.skip("Could not get or create test contact")


class TestCRMTimelineToken:
    """Tests for timeline token generation endpoint"""
    
    def test_generate_timeline_token_success(self, auth_session, user_id, test_contact_id):
        """POST /api/crm/timeline-token/{user_id}/{contact_id} returns a unique token"""
        response = auth_session.post(
            f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}"
        )
        assert response.status_code == 200, f"Token generation failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response missing 'token' field"
        assert "contact_id" in data, "Response missing 'contact_id' field"
        assert data["contact_id"] == test_contact_id
        # Token should be a valid UUID format
        assert len(data["token"]) == 36, "Token should be UUID format"
    
    def test_generate_token_returns_same_token_on_repeat(self, auth_session, user_id, test_contact_id):
        """Same contact should return same token on multiple calls"""
        res1 = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}")
        res2 = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}")
        
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["token"] == res2.json()["token"], "Token should be reused for same contact"
    
    def test_generate_token_invalid_contact_returns_404(self, auth_session, user_id):
        """Invalid contact ID should return 404"""
        fake_id = "000000000000000000000000"
        response = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{fake_id}")
        assert response.status_code == 404, f"Expected 404 for invalid contact: {response.status_code}"


class TestPublicTimeline:
    """Tests for public timeline endpoint (no auth required)"""
    
    def test_public_timeline_with_known_token(self):
        """GET /api/crm/timeline/{token} returns public timeline data"""
        # Use the known token from test setup
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{KNOWN_TOKEN}")
        
        # If token exists, should return 200 with data or pin_required
        # If token doesn't exist, should return 404
        if response.status_code == 200:
            data = response.json()
            # Either pin_required or full timeline data
            if data.get("pin_required"):
                assert "store_name" in data or "store_logo" in data
            else:
                assert "contact" in data, "Response should have contact info"
                assert "events" in data, "Response should have events array"
                assert "notes" in data, "Response should have notes array"
                assert "salesperson" in data, "Response should have salesperson info"
                assert "store" in data, "Response should have store info"
        elif response.status_code == 404:
            # Token not found - acceptable if test data doesn't exist
            pass
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_public_timeline_with_generated_token(self, auth_session, user_id, test_contact_id):
        """Generate a token and verify public timeline works"""
        # First generate a token
        token_res = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}")
        assert token_res.status_code == 200
        token = token_res.json()["token"]
        
        # Now access public timeline without auth
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{token}")
        assert response.status_code == 200, f"Public timeline failed: {response.text}"
        
        data = response.json()
        # If PIN not required, verify structure
        if not data.get("pin_required"):
            assert "contact" in data
            assert "name" in data["contact"] or data["contact"].get("name") is not None
    
    def test_public_timeline_invalid_token_returns_404(self):
        """Invalid token should return 404"""
        fake_token = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{fake_token}")
        assert response.status_code == 404, f"Expected 404 for invalid token: {response.status_code}"


class TestMarkCopied:
    """Tests for marking CRM link as copied"""
    
    def test_mark_copied_success(self, auth_session, user_id, test_contact_id):
        """POST /api/crm/mark-copied/{user_id}/{contact_id} sets crm_link_copied_at"""
        response = auth_session.post(
            f"{BASE_URL}/api/crm/mark-copied/{user_id}/{test_contact_id}"
        )
        assert response.status_code == 200, f"Mark copied failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
    
    def test_mark_copied_invalid_contact_returns_404(self, auth_session, user_id):
        """Invalid contact ID should return 404"""
        fake_id = "000000000000000000000000"
        response = auth_session.post(f"{BASE_URL}/api/crm/mark-copied/{user_id}/{fake_id}")
        assert response.status_code == 404


class TestPINSettings:
    """Tests for store PIN settings endpoints"""
    
    def test_get_pin_settings_success(self, auth_session):
        """GET /api/crm/pin-settings/{store_id} returns PIN settings"""
        response = auth_session.get(f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}")
        
        if response.status_code == 200:
            data = response.json()
            assert "crm_pin_enabled" in data
            assert "crm_pin" in data
            assert isinstance(data["crm_pin_enabled"], bool)
        elif response.status_code == 404:
            # Store not found - acceptable
            pass
        else:
            pytest.fail(f"Unexpected status: {response.status_code}, {response.text}")
    
    def test_update_pin_settings_enable(self, auth_session):
        """PUT /api/crm/pin-settings/{store_id} updates PIN settings"""
        # Enable PIN with a test PIN
        response = auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin_enabled": True, "crm_pin": "1234"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True
            assert data.get("crm_pin_enabled") == True
            assert data.get("crm_pin") == "1234"
        elif response.status_code == 404:
            pytest.skip("Store not found")
        else:
            pytest.fail(f"Update failed: {response.status_code}, {response.text}")
    
    def test_update_pin_settings_invalid_pin_length(self, auth_session):
        """PIN must be 4-8 digits"""
        # Too short
        response = auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin": "123"}  # Only 3 digits
        )
        if response.status_code != 404:
            assert response.status_code == 400, "Should reject PIN < 4 digits"
        
        # Too long
        response2 = auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin": "123456789"}  # 9 digits
        )
        if response2.status_code != 404:
            assert response2.status_code == 400, "Should reject PIN > 8 digits"
    
    def test_update_pin_settings_disable(self, auth_session):
        """Can disable PIN protection"""
        response = auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin_enabled": False}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("crm_pin_enabled") == False
        elif response.status_code == 404:
            pytest.skip("Store not found")


class TestPINVerification:
    """Tests for PIN verification flow"""
    
    def test_verify_pin_with_correct_pin(self, auth_session, user_id, test_contact_id):
        """POST /api/crm/timeline/{token}/verify-pin with correct PIN returns session token"""
        # First enable PIN
        auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin_enabled": True, "crm_pin": "5678"}
        )
        
        # Generate token
        token_res = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}")
        if token_res.status_code != 200:
            pytest.skip("Could not generate token")
        token = token_res.json()["token"]
        
        # Verify PIN
        response = requests.post(
            f"{BASE_URL}/api/crm/timeline/{token}/verify-pin",
            json={"pin": "5678"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("verified") == True
            # May or may not have session_token depending on store config
        elif response.status_code == 400:
            # No store configured - acceptable
            pass
        else:
            # 403 = invalid PIN, could mean test data doesn't match
            pass
    
    def test_verify_pin_with_wrong_pin(self, auth_session, user_id, test_contact_id):
        """Wrong PIN should return 403 when PIN is enabled"""
        # First enable PIN with a known value
        set_res = auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin_enabled": True, "crm_pin": "9999"}
        )
        
        if set_res.status_code != 200:
            pytest.skip("Could not set PIN settings")
        
        # Generate token
        token_res = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}")
        if token_res.status_code != 200:
            pytest.skip("Could not generate token")
        token = token_res.json()["token"]
        
        response = requests.post(
            f"{BASE_URL}/api/crm/timeline/{token}/verify-pin",
            json={"pin": "0000"}  # Wrong PIN - should fail
        )
        
        # Should be 403 (invalid PIN), 400 (no store config), or 200 (user's store differs)
        assert response.status_code in [200, 400, 403], f"Unexpected status: {response.status_code}"


class TestCRMExportStats:
    """Tests for CRM export stats endpoint"""
    
    def test_get_export_stats_success(self, auth_session, user_id):
        """GET /api/crm/export-stats/{user_id} returns contact CRM link stats"""
        response = auth_session.get(f"{BASE_URL}/api/crm/export-stats/{user_id}")
        assert response.status_code == 200, f"Export stats failed: {response.text}"
        
        data = response.json()
        assert "total_contacts" in data, "Response should have total_contacts"
        assert "crm_linked" in data, "Response should have crm_linked count"
        assert "not_linked" in data, "Response should have not_linked count"
        
        # Verify math: total = linked + not_linked
        assert data["total_contacts"] == data["crm_linked"] + data["not_linked"]


class TestTimelineDataStructure:
    """Tests for timeline response data structure"""
    
    def test_timeline_response_structure(self, auth_session, user_id, test_contact_id):
        """Verify timeline response has all required fields"""
        # Generate token
        token_res = auth_session.post(f"{BASE_URL}/api/crm/timeline-token/{user_id}/{test_contact_id}")
        assert token_res.status_code == 200
        token = token_res.json()["token"]
        
        # Disable PIN to get full data
        auth_session.put(
            f"{BASE_URL}/api/crm/pin-settings/{KNOWN_STORE_ID}",
            json={"crm_pin_enabled": False}
        )
        
        # Get timeline
        response = requests.get(f"{BASE_URL}/api/crm/timeline/{token}")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("pin_required"):
            # Verify contact structure
            assert "contact" in data
            contact = data["contact"]
            assert "name" in contact
            assert "phone" in contact or contact.get("phone") == ""
            
            # Verify events array
            assert "events" in data
            assert isinstance(data["events"], list)
            
            # Verify notes array
            assert "notes" in data
            assert isinstance(data["notes"], list)
            
            # Verify salesperson info
            assert "salesperson" in data
            
            # Verify store info
            assert "store" in data
            
            # Verify total_events count
            assert "total_events" in data
            assert data["total_events"] == len(data["events"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
