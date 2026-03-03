"""
Test App Directory API endpoints for page sharing functionality.
- Share via Email (Resend)
- Share via SMS (Twilio - real in this environment)
- Copy Link logging
- Admin-only access controls
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imonsocial.com"
TEST_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def auth_session():
    """Get authenticated session with user ID"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login to get user ID
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} - {response.text}")
    
    data = response.json()
    user_id = data.get("user", {}).get("_id")
    
    if not user_id:
        pytest.skip("Could not get user ID from login response")
    
    session.headers.update({"X-User-ID": user_id})
    return session, user_id


class TestAppDirectoryShareEmail:
    """Test App Directory Share via Email endpoint"""
    
    def test_share_via_email_success(self, auth_session):
        """Test sharing a page via email works"""
        session, user_id = auth_session
        
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Login",
            "page_path": "/auth/login",
            "recipient_email": "test@example.com",
            "channel": "email",
            "custom_message": "Check out this page from i'M On Social!"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("channel") == "email"
        assert "test@example.com" in data.get("message", "")
    
    def test_share_via_email_with_recipient_name(self, auth_session):
        """Test sharing with recipient name included"""
        session, user_id = auth_session
        
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Analytics",
            "page_path": "/analytics",
            "recipient_name": "John Smith",
            "recipient_email": "john@example.com",
            "channel": "email",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
    
    def test_share_email_missing_email(self, auth_session):
        """Test email share fails without email address"""
        session, user_id = auth_session
        
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Login",
            "page_path": "/auth/login",
            "channel": "email"
        })
        
        assert response.status_code == 400
        assert "email" in response.json().get("detail", "").lower()


class TestAppDirectoryShareSMS:
    """Test App Directory Share via SMS endpoint (Twilio - real in this env)"""
    
    def test_share_via_sms_success(self, auth_session):
        """Test sharing a page via SMS works"""
        session, user_id = auth_session
        
        # Using a valid-looking number format
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Training Hub",
            "page_path": "/training-hub",
            "recipient_phone": "+18015550199",
            "channel": "sms",
            "custom_message": "Check out this training!"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("channel") == "sms"
    
    def test_share_sms_missing_phone(self, auth_session):
        """Test SMS share fails without phone number"""
        session, user_id = auth_session
        
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Login",
            "page_path": "/auth/login",
            "channel": "sms"
        })
        
        assert response.status_code == 400
        assert "phone" in response.json().get("detail", "").lower()


class TestAppDirectoryCopyLink:
    """Test App Directory Copy Link logging endpoint"""
    
    def test_copy_link_success(self, auth_session):
        """Test copy link logging works"""
        session, user_id = auth_session
        
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share/copy-link", json={
            "page_name": "Admin Dashboard",
            "page_path": "/admin"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True


class TestAppDirectoryAuth:
    """Test App Directory authentication and authorization"""
    
    def test_share_requires_auth(self):
        """Test share endpoint requires authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # No X-User-ID header
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Login",
            "page_path": "/auth/login",
            "recipient_email": "test@example.com",
            "channel": "email"
        })
        
        assert response.status_code == 401
        assert "not authenticated" in response.json().get("detail", "").lower()
    
    def test_copy_link_requires_auth(self):
        """Test copy link endpoint requires authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # No X-User-ID header
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share/copy-link", json={
            "page_name": "Admin Dashboard",
            "page_path": "/admin"
        })
        
        assert response.status_code == 401


class TestAppDirectoryInvalidChannel:
    """Test invalid channel handling"""
    
    def test_invalid_channel_rejected(self, auth_session):
        """Test that invalid channel is rejected"""
        session, user_id = auth_session
        
        response = session.post(f"{BASE_URL}/api/admin/app-directory/share", json={
            "page_name": "Login",
            "page_path": "/auth/login",
            "recipient_email": "test@example.com",
            "channel": "invalid_channel"
        })
        
        assert response.status_code == 400
        assert "channel" in response.json().get("detail", "").lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
