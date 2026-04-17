"""
Test file for Quotes and Partner Agreements management
Testing: CRUD operations, send/resend endpoints, delete functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imonsocial.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")

# Test IDs provided
TEST_QUOTE_ID = "699d7cff29a059c2cc904e96"
TEST_AGREEMENT_ID = "699cd851459dfed21094c6d6"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("access_token") or data.get("token")
        assert token, "No token in response"
        return token
    
    @pytest.fixture(scope="class") 
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data or "access_token" in data, "No token in response"
        assert "user" in data
        print(f"✓ Login successful, user role: {data['user'].get('role')}")


class TestQuotesAPI:
    """Tests for Quotes API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_list_quotes(self, auth_headers):
        """Test GET /api/subscriptions/quotes - list all quotes"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes", headers=auth_headers)
        assert response.status_code == 200, f"Failed to list quotes: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of quotes"
        print(f"✓ Listed {len(data)} quotes")
        
        # Check quote structure if any exist
        if len(data) > 0:
            quote = data[0]
            assert "_id" in quote, "Quote missing _id"
            assert "quote_number" in quote, "Quote missing quote_number"
            assert "status" in quote, "Quote missing status"
            print(f"  Sample quote: {quote.get('quote_number')} - Status: {quote.get('status')}")
    
    def test_get_specific_quote(self, auth_headers):
        """Test GET /api/subscriptions/quotes/{id} - get specific quote"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes/{TEST_QUOTE_ID}", headers=auth_headers)
        assert response.status_code in [200, 404], f"Unexpected response: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "_id" in data, "Quote missing _id"
            assert "quote_number" in data, "Quote missing quote_number"
            assert "customer" in data, "Quote missing customer info"
            assert "pricing" in data, "Quote missing pricing info"
            print(f"✓ Retrieved quote: {data.get('quote_number')} - Status: {data.get('status')}")
        else:
            print(f"⚠ Quote {TEST_QUOTE_ID} not found - may have been deleted")
    
    def test_patch_quote_update(self, auth_headers):
        """Test PATCH /api/subscriptions/quotes/{id} - update quote notes"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes/{TEST_QUOTE_ID}", headers=auth_headers)
        
        if response.status_code != 200:
            pytest.skip(f"Quote {TEST_QUOTE_ID} not found")
        
        # Try updating notes
        update_data = {"notes": f"Test note updated at {os.popen('date').read().strip()}"}
        patch_response = requests.patch(
            f"{BASE_URL}/api/subscriptions/quotes/{TEST_QUOTE_ID}",
            json=update_data,
            headers=auth_headers
        )
        assert patch_response.status_code == 200, f"Failed to update quote: {patch_response.text}"
        print("✓ Quote PATCH endpoint works for updating notes")
    
    def test_send_quote_endpoint(self, auth_headers):
        """Test POST /api/subscriptions/quotes/{id}/send - send/resend quote"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes/{TEST_QUOTE_ID}", headers=auth_headers)
        
        if response.status_code != 200:
            pytest.skip(f"Quote {TEST_QUOTE_ID} not found")
        
        # Try sending/resending the quote
        send_response = requests.post(
            f"{BASE_URL}/api/subscriptions/quotes/{TEST_QUOTE_ID}/send",
            headers=auth_headers
        )
        # Should succeed or fail with 400 if no email
        assert send_response.status_code in [200, 400], f"Unexpected response: {send_response.text}"
        
        if send_response.status_code == 200:
            data = send_response.json()
            print(f"✓ Quote send endpoint works - sent to: {data.get('sent_to')}")
        else:
            print(f"⚠ Quote send returned 400 (likely no customer email): {send_response.json().get('detail')}")
    
    def test_delete_quote_endpoint_exists(self, auth_headers):
        """Test that DELETE /api/subscriptions/quotes/{id} endpoint exists"""
        # We won't actually delete the test quote, just verify endpoint exists
        # Try with a fake ID
        response = requests.delete(
            f"{BASE_URL}/api/subscriptions/quotes/000000000000000000000000",
            headers=auth_headers
        )
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code in [404, 400], f"DELETE endpoint may not exist: {response.status_code}"
        print("✓ DELETE endpoint exists (returned 404 for non-existent quote)")


class TestPartnerAgreementsAPI:
    """Tests for Partner Agreements API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_list_agreements(self, auth_headers):
        """Test GET /api/partners/agreements - list all agreements"""
        response = requests.get(f"{BASE_URL}/api/partners/agreements", headers=auth_headers)
        assert response.status_code == 200, f"Failed to list agreements: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of agreements"
        print(f"✓ Listed {len(data)} agreements")
        
        # Check agreement structure if any exist
        if len(data) > 0:
            agreement = data[0]
            assert "id" in agreement, "Agreement missing id"
            assert "template_name" in agreement, "Agreement missing template_name"
            assert "status" in agreement, "Agreement missing status"
            assert "created_at" in agreement, "Agreement missing created_at"
            print(f"  Sample agreement: {agreement.get('template_name')} - Status: {agreement.get('status')}")
    
    def test_get_specific_agreement(self, auth_headers):
        """Test GET /api/partners/agreements/{id} - get specific agreement"""
        response = requests.get(f"{BASE_URL}/api/partners/agreements/{TEST_AGREEMENT_ID}", headers=auth_headers)
        assert response.status_code in [200, 404], f"Unexpected response: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data, "Agreement missing id"
            assert "template_name" in data, "Agreement missing template_name"
            assert "status" in data, "Agreement missing status"
            # Check for required fields
            assert "created_at" in data or data.get("created_at") is not None, "Agreement missing created_at"
            print(f"✓ Retrieved agreement: {data.get('template_name')} - Status: {data.get('status')}")
            print(f"  created_at: {data.get('created_at')}")
            print(f"  sent_at: {data.get('sent_at')}")
        else:
            print(f"⚠ Agreement {TEST_AGREEMENT_ID} not found")
    
    def test_update_agreement(self, auth_headers):
        """Test PUT /api/partners/agreements/{id} - update agreement"""
        response = requests.get(f"{BASE_URL}/api/partners/agreements/{TEST_AGREEMENT_ID}", headers=auth_headers)
        
        if response.status_code != 200:
            pytest.skip(f"Agreement {TEST_AGREEMENT_ID} not found")
        
        # Try updating partner name
        update_data = {"partner_name": "Test Partner Updated"}
        put_response = requests.put(
            f"{BASE_URL}/api/partners/agreements/{TEST_AGREEMENT_ID}",
            json=update_data,
            headers=auth_headers
        )
        assert put_response.status_code == 200, f"Failed to update agreement: {put_response.text}"
        print("✓ Agreement PUT endpoint works for updating partner info")
    
    def test_send_agreement_endpoint(self, auth_headers):
        """Test POST /api/partners/agreements/{id}/send - send agreement"""
        response = requests.get(f"{BASE_URL}/api/partners/agreements/{TEST_AGREEMENT_ID}", headers=auth_headers)
        
        if response.status_code != 200:
            pytest.skip(f"Agreement {TEST_AGREEMENT_ID} not found")
        
        # Try sending the agreement
        send_response = requests.post(
            f"{BASE_URL}/api/partners/agreements/{TEST_AGREEMENT_ID}/send",
            headers=auth_headers
        )
        # Should succeed or fail with 400 if no email
        assert send_response.status_code in [200, 400], f"Unexpected response: {send_response.text}"
        
        if send_response.status_code == 200:
            data = send_response.json()
            print(f"✓ Agreement send endpoint works - sent to: {data.get('sent_to')}")
        else:
            print(f"⚠ Agreement send returned 400 (likely no partner email): {send_response.json().get('detail')}")
    
    def test_delete_agreement_endpoint_exists(self, auth_headers):
        """Test that DELETE /api/partners/agreements/{id} endpoint exists"""
        # We won't actually delete the test agreement, just verify endpoint exists
        # Try with a fake ID
        response = requests.delete(
            f"{BASE_URL}/api/partners/agreements/000000000000000000000000",
            headers=auth_headers
        )
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code in [404, 400], f"DELETE endpoint may not exist: {response.status_code}"
        print("✓ DELETE endpoint exists (returned 404 for non-existent agreement)")
    
    def test_list_templates(self, auth_headers):
        """Test GET /api/partners/templates - list agreement templates"""
        response = requests.get(f"{BASE_URL}/api/partners/templates", headers=auth_headers)
        assert response.status_code == 200, f"Failed to list templates: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of templates"
        print(f"✓ Listed {len(data)} templates")
        
        if len(data) > 0:
            template = data[0]
            assert "id" in template, "Template missing id"
            assert "name" in template, "Template missing name"
            assert "commission_tiers" in template, "Template missing commission_tiers"
            print(f"  Sample template: {template.get('name')} - Type: {template.get('type')}")


class TestCreateAndDeleteQuote:
    """Test creating and deleting a draft quote"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_create_and_delete_quote(self, auth_headers):
        """Test full flow: create quote -> verify -> delete"""
        # 1. Create a new draft quote
        quote_data = {
            "plan_type": "individual",
            "plan_id": "monthly",
            "email": "test_delete@example.com",
            "name": "Test Delete User",
            "phone": "555-0100",
            "notes": "This is a test quote for deletion testing"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/subscriptions/quotes",
            json=quote_data,
            headers=auth_headers
        )
        assert create_response.status_code == 200, f"Failed to create quote: {create_response.text}"
        created_quote = create_response.json()
        quote_id = created_quote.get("_id")
        assert quote_id, "No _id in created quote"
        print(f"✓ Created quote: {created_quote.get('quote_number')} - ID: {quote_id}")
        
        # 2. Verify quote was created
        get_response = requests.get(
            f"{BASE_URL}/api/subscriptions/quotes/{quote_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "draft"
        print("✓ Verified quote exists with status 'draft'")
        
        # 3. Delete the quote
        delete_response = requests.delete(
            f"{BASE_URL}/api/subscriptions/quotes/{quote_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200, f"Failed to delete quote: {delete_response.text}"
        print("✓ Successfully deleted quote")
        
        # 4. Verify quote no longer exists
        verify_response = requests.get(
            f"{BASE_URL}/api/subscriptions/quotes/{quote_id}",
            headers=auth_headers
        )
        assert verify_response.status_code == 404, "Quote should be deleted but still exists"
        print("✓ Verified quote no longer exists (404)")


class TestCreateAndDeleteAgreement:
    """Test creating and deleting a draft agreement"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_create_and_delete_agreement(self, auth_headers):
        """Test full flow: create agreement -> verify -> delete"""
        # 1. Get a template first
        templates_response = requests.get(f"{BASE_URL}/api/partners/templates", headers=auth_headers)
        assert templates_response.status_code == 200
        templates = templates_response.json()
        assert len(templates) > 0, "No templates available"
        template_id = templates[0]["id"]
        
        # 2. Create a new draft agreement
        agreement_data = {
            "template_id": template_id,
            "partner_email": "test_delete_agreement@example.com",
            "partner_name": "Test Delete Partner",
            "commission_tier": {"name": "Bronze", "percentage": 10.0}
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/partners/agreements",
            json=agreement_data,
            headers=auth_headers
        )
        assert create_response.status_code == 200, f"Failed to create agreement: {create_response.text}"
        created_agreement = create_response.json()
        agreement_id = created_agreement.get("id")
        assert agreement_id, "No id in created agreement"
        print(f"✓ Created agreement - ID: {agreement_id}")
        
        # 3. Verify agreement was created
        get_response = requests.get(
            f"{BASE_URL}/api/partners/agreements/{agreement_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["status"] in ["draft", "viewed"]  # Might become viewed on access
        print(f"✓ Verified agreement exists with status '{get_response.json()['status']}'")
        
        # 4. Delete the agreement
        delete_response = requests.delete(
            f"{BASE_URL}/api/partners/agreements/{agreement_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200, f"Failed to delete agreement: {delete_response.text}"
        print("✓ Successfully deleted agreement")
        
        # 5. Verify agreement no longer exists
        verify_response = requests.get(
            f"{BASE_URL}/api/partners/agreements/{agreement_id}",
            headers=auth_headers
        )
        assert verify_response.status_code == 404, "Agreement should be deleted but still exists"
        print("✓ Verified agreement no longer exists (404)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
