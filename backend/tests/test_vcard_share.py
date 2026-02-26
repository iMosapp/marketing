"""
Test vCard endpoint for digital business card sharing
Tests:
- GET /api/card/vcard/{user_id} - returns proper vCard file
- vCard content validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://chat-web-ui.preview.emergentagent.com')


class TestVCardEndpoint:
    """Tests for vCard download endpoint"""
    
    # Test user ID from provided credentials
    TEST_USER_ID = "69975a8b6ff748b1f9da6b57"
    
    def test_vcard_returns_200(self):
        """Test GET /api/card/vcard/{user_id} returns 200"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{self.TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ vCard endpoint returns 200 for user {self.TEST_USER_ID}")
    
    def test_vcard_content_type(self):
        """Test vCard endpoint returns correct content-type"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{self.TEST_USER_ID}")
        content_type = response.headers.get('Content-Type', '')
        assert 'text/vcard' in content_type, f"Expected text/vcard, got {content_type}"
        print(f"✓ Content-Type is text/vcard: {content_type}")
    
    def test_vcard_content_disposition(self):
        """Test vCard endpoint returns Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{self.TEST_USER_ID}")
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition, f"Expected attachment, got {content_disposition}"
        assert '.vcf' in content_disposition, f"Expected .vcf filename, got {content_disposition}"
        print(f"✓ Content-Disposition is correct: {content_disposition}")
    
    def test_vcard_contains_required_fields(self):
        """Test vCard contains all required vCard fields"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{self.TEST_USER_ID}")
        content = response.text
        
        # vCard must have these fields
        required_fields = ['BEGIN:VCARD', 'VERSION:', 'FN:', 'END:VCARD']
        for field in required_fields:
            assert field in content, f"vCard missing required field: {field}"
        print("✓ vCard contains all required fields (BEGIN, VERSION, FN, END)")
    
    def test_vcard_contains_contact_info(self):
        """Test vCard contains contact information"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/{self.TEST_USER_ID}")
        content = response.text
        
        # Check for phone and email
        has_phone = 'TEL' in content
        has_email = 'EMAIL' in content
        
        print(f"  Has phone: {has_phone}")
        print(f"  Has email: {has_email}")
        
        assert has_phone or has_email, "vCard should have at least phone or email"
        print("✓ vCard contains contact information (phone/email)")
    
    def test_vcard_invalid_user_returns_404(self):
        """Test vCard endpoint returns 404 for invalid user"""
        response = requests.get(f"{BASE_URL}/api/card/vcard/invalid_id_12345")
        assert response.status_code == 404, f"Expected 404 for invalid user, got {response.status_code}"
        print("✓ Invalid user returns 404")
    
    def test_campaigns_endpoint(self):
        """Test GET /api/card/campaigns/{user_id} returns list"""
        response = requests.get(f"{BASE_URL}/api/card/campaigns/{self.TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Campaigns endpoint returns list with {len(data)} campaigns")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
