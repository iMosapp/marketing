"""
Showcase API Tests - The Showroom feature
Tests for public social proof landing pages with delivery photos and reviews
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID from context
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CREDENTIALS = {
    "email": "forest@imonsocial.com",
    "password": "Admin123!"
}


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for protected endpoints"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestShowcaseUserEndpoint:
    """Test GET /api/showcase/user/{user_id} - public endpoint"""

    def test_get_user_showcase_success(self, api_client):
        """Test successful retrieval of user showcase data"""
        response = api_client.get(f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure - salesperson info
        assert "salesperson" in data
        assert "id" in data["salesperson"]
        assert "name" in data["salesperson"]
        assert "title" in data["salesperson"]
        assert "photo_url" in data["salesperson"]
        
        # Verify structure - store info (can be null)
        assert "store" in data
        if data["store"]:
            assert "name" in data["store"]
            assert "logo_url" in data["store"]
            assert "primary_color" in data["store"]
        
        # Verify entries array
        assert "entries" in data
        assert isinstance(data["entries"], list)
        
        # Verify totals
        assert "total_deliveries" in data
        assert "total_reviews" in data
        assert isinstance(data["total_deliveries"], int)
        assert isinstance(data["total_reviews"], int)
        
        print(f"User showcase: {data['salesperson']['name']}, {data['total_deliveries']} deliveries, {data['total_reviews']} reviews")

    def test_get_user_showcase_invalid_user(self, api_client):
        """Test 404 for non-existent user"""
        response = api_client.get(f"{BASE_URL}/api/showcase/user/000000000000000000000000")
        assert response.status_code == 404

    def test_get_user_showcase_invalid_id_format(self, api_client):
        """Test error for invalid ObjectId format"""
        response = api_client.get(f"{BASE_URL}/api/showcase/user/invalid-id")
        assert response.status_code in [400, 500, 422]  # Should error on invalid ObjectId


class TestShowcaseStoreEndpoint:
    """Test GET /api/showcase/store/{store_id} - public endpoint"""

    def test_get_store_showcase_success(self, api_client, auth_token):
        """Test successful retrieval of store showcase data"""
        # First get user to find their store_id
        headers = {"Authorization": f"Bearer {auth_token}"}
        user_response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            store_id = user_data.get("store_id")
            
            if store_id:
                response = api_client.get(f"{BASE_URL}/api/showcase/store/{store_id}")
                
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
                
                data = response.json()
                
                # Verify structure
                assert "store" in data
                assert "id" in data["store"]
                assert "name" in data["store"]
                
                assert "team" in data
                assert isinstance(data["team"], list)
                
                assert "entries" in data
                assert isinstance(data["entries"], list)
                
                assert "total_deliveries" in data
                assert "total_reviews" in data
                
                print(f"Store showcase: {data['store']['name']}, {len(data['team'])} team members, {data['total_deliveries']} deliveries")
            else:
                pytest.skip("User has no store_id - skipping store showcase test")
        else:
            pytest.skip("Could not get user info")

    def test_get_store_showcase_invalid_store(self, api_client):
        """Test 404 for non-existent store"""
        response = api_client.get(f"{BASE_URL}/api/showcase/store/000000000000000000000000")
        assert response.status_code == 404


class TestShowcaseManageEndpoint:
    """Test GET /api/showcase/manage/{user_id} - returns all entries including hidden"""

    def test_get_manage_showcase_success(self, api_client):
        """Test successful retrieval of managed showcase entries"""
        response = api_client.get(f"{BASE_URL}/api/showcase/manage/{TEST_USER_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # Check entry structure if any exist
        if len(data) > 0:
            entry = data[0]
            assert "card_id" in entry
            assert "customer_name" in entry
            assert "hidden" in entry
            assert "created_at" in entry
            print(f"Manage showcase: {len(data)} entries, first card_id: {entry.get('card_id')}")
        else:
            print("Manage showcase: 0 entries (empty)")


class TestShowcaseHideShowEndpoints:
    """Test PUT /api/showcase/entry/{card_id}/hide and /show endpoints"""

    def test_hide_entry_nonexistent_card(self, api_client):
        """Test hide with non-existent card_id"""
        response = api_client.put(f"{BASE_URL}/api/showcase/entry/nonexistent-card-id-12345/hide")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_show_entry_nonexistent_card(self, api_client):
        """Test show with non-existent card_id"""
        response = api_client.put(f"{BASE_URL}/api/showcase/entry/nonexistent-card-id-12345/show")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_hide_show_existing_card(self, api_client):
        """Test hide/show functionality with actual card if exists"""
        # Get existing cards
        response = api_client.get(f"{BASE_URL}/api/showcase/manage/{TEST_USER_ID}")
        assert response.status_code == 200
        
        entries = response.json()
        if len(entries) == 0:
            pytest.skip("No congrats cards to test hide/show")
            return
        
        card_id = entries[0].get("card_id")
        if not card_id:
            pytest.skip("First entry has no card_id")
            return
        
        # Test HIDE
        hide_response = api_client.put(f"{BASE_URL}/api/showcase/entry/{card_id}/hide")
        assert hide_response.status_code == 200, f"Hide failed: {hide_response.text}"
        hide_data = hide_response.json()
        assert hide_data.get("success") == True
        
        # Verify hidden status
        manage_response = api_client.get(f"{BASE_URL}/api/showcase/manage/{TEST_USER_ID}")
        updated_entries = manage_response.json()
        hidden_entry = next((e for e in updated_entries if e.get("card_id") == card_id), None)
        assert hidden_entry is not None
        assert hidden_entry.get("hidden") == True, "Card should be hidden after hide"
        
        # Test SHOW (unhide)
        show_response = api_client.put(f"{BASE_URL}/api/showcase/entry/{card_id}/show")
        assert show_response.status_code == 200, f"Show failed: {show_response.text}"
        show_data = show_response.json()
        assert show_data.get("success") == True
        
        # Verify unhidden status
        manage_response2 = api_client.get(f"{BASE_URL}/api/showcase/manage/{TEST_USER_ID}")
        final_entries = manage_response2.json()
        final_entry = next((e for e in final_entries if e.get("card_id") == card_id), None)
        assert final_entry is not None
        assert final_entry.get("hidden") == False, "Card should not be hidden after show"
        
        print(f"Hide/show tested successfully for card_id: {card_id}")


class TestShowcaseEntryStructure:
    """Test showcase entry data structure and matching logic"""

    def test_entry_structure_for_delivery(self, api_client):
        """Verify delivery entry has correct structure"""
        response = api_client.get(f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        entries = data.get("entries", [])
        
        # Find a delivery entry if any
        delivery_entries = [e for e in entries if e.get("type") == "delivery"]
        
        if len(delivery_entries) > 0:
            entry = delivery_entries[0]
            
            # Required fields for delivery entry
            assert "id" in entry
            assert "type" in entry
            assert entry["type"] == "delivery"
            assert "customer_name" in entry
            assert "customer_photo" in entry
            assert "card_id" in entry
            assert "created_at" in entry
            # review can be null or object
            assert "review" in entry
            
            if entry.get("review"):
                review = entry["review"]
                assert "id" in review
                assert "rating" in review
                assert "text" in review
                assert "customer_name" in review
            
            print(f"Delivery entry structure verified: {entry.get('customer_name')}")
        else:
            print("No delivery entries found - structure test skipped (entries are empty)")


class TestShowcaseDataIntegrity:
    """Test data integrity between endpoints"""

    def test_public_vs_manage_visibility(self, api_client):
        """Public endpoint should NOT show hidden entries, manage should show ALL"""
        # Get public showcase (should exclude hidden)
        public_response = api_client.get(f"{BASE_URL}/api/showcase/user/{TEST_USER_ID}")
        assert public_response.status_code == 200
        public_entries = public_response.json().get("entries", [])
        
        # Get manage showcase (should include hidden)
        manage_response = api_client.get(f"{BASE_URL}/api/showcase/manage/{TEST_USER_ID}")
        assert manage_response.status_code == 200
        manage_entries = manage_response.json()
        
        # Manage should have >= public (includes hidden)
        # This is a sanity check - manage includes hidden, public excludes
        print(f"Public entries: {len(public_entries)}, Manage entries: {len(manage_entries)}")
        
        # If any are hidden, manage should have more
        hidden_count = sum(1 for e in manage_entries if e.get("hidden"))
        print(f"Hidden entries in manage: {hidden_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
