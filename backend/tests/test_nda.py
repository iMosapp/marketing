"""
NDA Router Tests - Digital Non-Disclosure Agreements with signature collection
Tests: Create, List, Get, Verify, Sign, Send, Delete flows
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNDAEndpoints:
    """NDA CRUD and signing flow tests"""
    
    # Track created NDA for cleanup
    created_nda_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_01_create_nda(self):
        """POST /api/nda/agreements - Create new NDA"""
        payload = {
            "sender_name": "Test Admin",
            "sender_title": "Test Manager",
            "sender_signature": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "signature_type": "drawn",
            "recipient_name": "Test Recipient",
            "recipient_email": "testrecp@example.com",
            "recipient_phone": "5551112222"
        }
        
        response = self.session.post(f"{BASE_URL}/api/nda/agreements", json=payload)
        
        assert response.status_code == 200, f"Create NDA failed: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain NDA id"
        assert "link" in data, "Response should contain shareable link"
        assert data["status"] == "pending", "New NDA should be pending"
        assert "message" in data, "Response should contain success message"
        
        # Store ID for subsequent tests
        TestNDAEndpoints.created_nda_id = data["id"]
        print(f"Created NDA with ID: {data['id']}")
    
    def test_02_list_ndas(self):
        """GET /api/nda/agreements - List all NDAs"""
        response = self.session.get(f"{BASE_URL}/api/nda/agreements")
        
        assert response.status_code == 200, f"List NDAs failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check if our created NDA is in the list
        if TestNDAEndpoints.created_nda_id:
            nda_ids = [n["id"] for n in data]
            assert TestNDAEndpoints.created_nda_id in nda_ids, "Created NDA should be in list"
        
        # Verify structure of NDA items
        if len(data) > 0:
            nda = data[0]
            assert "id" in nda
            assert "recipient_name" in nda
            assert "recipient_email" in nda
            assert "sender_name" in nda
            assert "status" in nda
            assert "created_at" in nda
        
        print(f"Found {len(data)} NDAs in list")
    
    def test_03_get_nda_detail(self):
        """GET /api/nda/agreements/{id} - Get full NDA details"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to get details")
        
        nda_id = TestNDAEndpoints.created_nda_id
        response = self.session.get(f"{BASE_URL}/api/nda/agreements/{nda_id}")
        
        assert response.status_code == 200, f"Get NDA detail failed: {response.text}"
        
        data = response.json()
        assert data["id"] == nda_id
        assert "sender" in data
        assert "recipient" in data
        assert "content" in data
        assert "status" in data
        
        # Verify sender info
        assert data["sender"]["name"] == "Test Admin"
        assert data["sender"]["title"] == "Test Manager"
        
        # Verify recipient info
        assert data["recipient"]["name"] == "Test Recipient"
        assert data["recipient"]["email"] == "testrecp@example.com"
        
        # Verify NDA content structure
        content = data["content"]
        assert "title" in content
        assert "sections" in content
        assert len(content["sections"]) > 0
        
        print(f"Got NDA detail: status={data['status']}, sections={len(content['sections'])}")
    
    def test_04_public_nda_info(self):
        """GET /api/nda/sign/{id} - Public endpoint for NDA info (no auth)"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test public endpoint")
        
        nda_id = TestNDAEndpoints.created_nda_id
        response = self.session.get(f"{BASE_URL}/api/nda/sign/{nda_id}")
        
        assert response.status_code == 200, f"Get public NDA info failed: {response.text}"
        
        data = response.json()
        assert data["id"] == nda_id
        assert "sender_name" in data
        assert "recipient_name" in data
        assert "status" in data
        
        # Should NOT include full content or sensitive info
        assert "content" not in data, "Public endpoint should not expose full content"
        
        print(f"Public NDA info: sender={data['sender_name']}, recipient={data['recipient_name']}")
    
    def test_05_verify_with_wrong_credentials(self):
        """POST /api/nda/sign/{id}/verify - Should fail with wrong credentials"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test verification")
        
        nda_id = TestNDAEndpoints.created_nda_id
        payload = {
            "email": "wrong@email.com",
            "phone": "1234567890"
        }
        
        response = self.session.post(f"{BASE_URL}/api/nda/sign/{nda_id}/verify", json=payload)
        
        assert response.status_code == 403, f"Expected 403 for wrong credentials, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"Verification failed as expected: {data['detail']}")
    
    def test_06_verify_with_correct_credentials(self):
        """POST /api/nda/sign/{id}/verify - Should succeed with correct credentials"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test verification")
        
        nda_id = TestNDAEndpoints.created_nda_id
        payload = {
            "email": "testrecp@example.com",
            "phone": "5551112222"
        }
        
        response = self.session.post(f"{BASE_URL}/api/nda/sign/{nda_id}/verify", json=payload)
        
        assert response.status_code == 200, f"Verification failed: {response.text}"
        
        data = response.json()
        assert data["verified"] == True
        assert "sender" in data
        assert "recipient" in data
        assert "content" in data
        
        # Verify full content is now accessible
        assert len(data["content"]["sections"]) > 0
        
        # Verify sender signature info is included
        assert "signature" in data["sender"]
        
        print(f"Verification succeeded, status={data['status']}")
    
    def test_07_send_nda_email(self):
        """POST /api/nda/agreements/{id}/send - Send NDA via email"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test email sending")
        
        nda_id = TestNDAEndpoints.created_nda_id
        response = self.session.post(f"{BASE_URL}/api/nda/agreements/{nda_id}/send")
        
        assert response.status_code == 200, f"Send NDA email failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert "link" in data
        assert "message" in data
        
        print(f"NDA email sent: {data['message']}")
    
    def test_08_submit_signature(self):
        """POST /api/nda/sign/{id}/submit - Recipient signs the NDA"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test signature submission")
        
        nda_id = TestNDAEndpoints.created_nda_id
        payload = {
            "name": "Test Recipient",
            "title": "Developer",
            "company": "Test Company Inc",
            "email": "testrecp@example.com",
            "signature": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "signature_type": "drawn"
        }
        
        response = self.session.post(f"{BASE_URL}/api/nda/sign/{nda_id}/submit", json=payload)
        
        assert response.status_code == 200, f"Submit signature failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert "message" in data
        
        print(f"Signature submitted: {data['message']}")
    
    def test_09_verify_signed_status(self):
        """GET /api/nda/agreements/{id} - Verify NDA is now signed"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to verify status")
        
        nda_id = TestNDAEndpoints.created_nda_id
        response = self.session.get(f"{BASE_URL}/api/nda/agreements/{nda_id}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "signed", f"Expected status 'signed', got '{data['status']}'"
        assert data["signed_recipient"] is not None
        assert data["signed_recipient"]["name"] == "Test Recipient"
        assert data["signed_recipient"]["company"] == "Test Company Inc"
        assert data["signed_at"] is not None
        
        print(f"NDA verified as signed, signed_at={data['signed_at']}")
    
    def test_10_cannot_delete_signed_nda(self):
        """DELETE /api/nda/agreements/{id} - Should fail for signed NDA"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test delete")
        
        nda_id = TestNDAEndpoints.created_nda_id
        response = self.session.delete(f"{BASE_URL}/api/nda/agreements/{nda_id}")
        
        assert response.status_code == 400, f"Expected 400 for signed NDA delete, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"Cannot delete signed NDA: {data['detail']}")
    
    def test_11_cannot_sign_already_signed_nda(self):
        """POST /api/nda/sign/{id}/submit - Should fail for already signed NDA"""
        if not TestNDAEndpoints.created_nda_id:
            pytest.skip("No NDA created to test re-sign")
        
        nda_id = TestNDAEndpoints.created_nda_id
        payload = {
            "name": "Another Person",
            "title": "Other Title",
            "company": "Other Company",
            "email": "other@example.com",
            "signature": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "signature_type": "drawn"
        }
        
        response = self.session.post(f"{BASE_URL}/api/nda/sign/{nda_id}/submit", json=payload)
        
        assert response.status_code == 400, f"Expected 400 for re-signing, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"Cannot re-sign: {data['detail']}")


class TestNDADeleteUnsigned:
    """Test deleting unsigned NDA"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_create_and_delete_unsigned_nda(self):
        """Create NDA then delete it (should work for unsigned)"""
        # Create
        payload = {
            "sender_name": "Delete Test",
            "sender_title": "Tester",
            "sender_signature": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "signature_type": "drawn",
            "recipient_name": "Delete Recipient",
            "recipient_email": "delete@example.com",
            "recipient_phone": "5559998888"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/nda/agreements", json=payload)
        assert create_response.status_code == 200
        
        nda_id = create_response.json()["id"]
        print(f"Created NDA for delete test: {nda_id}")
        
        # Verify it exists
        get_response = self.session.get(f"{BASE_URL}/api/nda/agreements/{nda_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "pending"
        
        # Delete
        delete_response = self.session.delete(f"{BASE_URL}/api/nda/agreements/{nda_id}")
        assert delete_response.status_code == 200
        
        data = delete_response.json()
        assert data["success"] == True
        print(f"Successfully deleted unsigned NDA")
        
        # Verify it's gone
        get_response = self.session.get(f"{BASE_URL}/api/nda/agreements/{nda_id}")
        assert get_response.status_code == 404


class TestNDANotFound:
    """Test NDA 404 cases"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_get_nonexistent_nda(self):
        """GET /api/nda/agreements/{id} - Should return 404"""
        fake_id = "000000000000000000000000"  # Valid ObjectId format but doesn't exist
        response = self.session.get(f"{BASE_URL}/api/nda/agreements/{fake_id}")
        
        assert response.status_code == 404
        print("Correctly returned 404 for nonexistent NDA")
    
    def test_public_nonexistent_nda(self):
        """GET /api/nda/sign/{id} - Should return 404"""
        fake_id = "000000000000000000000000"
        response = self.session.get(f"{BASE_URL}/api/nda/sign/{fake_id}")
        
        assert response.status_code == 404
        print("Correctly returned 404 for public nonexistent NDA")


class TestExistingNDAs:
    """Test with existing NDAs mentioned in context"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_verify_existing_signed_nda(self):
        """Verify existing signed NDA (John Smith) credentials work"""
        # First, get list and find the signed NDA
        response = self.session.get(f"{BASE_URL}/api/nda/agreements")
        assert response.status_code == 200
        
        ndas = response.json()
        signed_nda = None
        for nda in ndas:
            if nda.get("status") == "signed" and "john" in nda.get("recipient_email", "").lower():
                signed_nda = nda
                break
        
        if not signed_nda:
            pytest.skip("No existing signed NDA with john@example.com found")
        
        # Verify credentials
        nda_id = signed_nda["id"]
        payload = {
            "email": "john@example.com",
            "phone": "8015551234"
        }
        
        verify_response = self.session.post(f"{BASE_URL}/api/nda/sign/{nda_id}/verify", json=payload)
        assert verify_response.status_code == 200
        
        data = verify_response.json()
        assert data["verified"] == True
        print(f"Verified existing signed NDA for John Smith")
    
    def test_verify_existing_viewed_nda(self):
        """Verify existing viewed NDA (Jane Doe) credentials work"""
        # First, get list and find the viewed NDA
        response = self.session.get(f"{BASE_URL}/api/nda/agreements")
        assert response.status_code == 200
        
        ndas = response.json()
        viewed_nda = None
        for nda in ndas:
            if nda.get("status") == "viewed" and "jane" in nda.get("recipient_email", "").lower():
                viewed_nda = nda
                break
        
        if not viewed_nda:
            pytest.skip("No existing viewed NDA with jane@test.com found")
        
        # Verify credentials
        nda_id = viewed_nda["id"]
        payload = {
            "email": "jane@test.com",
            "phone": "5551234567"
        }
        
        verify_response = self.session.post(f"{BASE_URL}/api/nda/sign/{nda_id}/verify", json=payload)
        assert verify_response.status_code == 200
        
        data = verify_response.json()
        assert data["verified"] == True
        print(f"Verified existing viewed NDA for Jane Doe")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
