"""
Lead Sources API Tests
Tests for lead source CRUD operations, webhook endpoint, and routing logic
"""
import pytest
import requests
import os
import secrets

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://backend-startup-3.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "forestward@gmail.com"
TEST_PASSWORD = "Admin123!"

class TestLeadSourcesAPI:
    """Lead Sources endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get user info
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        self.user_id = data["user"]["_id"]
        self.store_id = data["user"].get("store_id", self.user_id)
        
        # Store created lead sources for cleanup
        self.created_source_ids = []
        
        yield
        
        # Cleanup: Delete test lead sources
        for source_id in self.created_source_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/lead-sources/{source_id}")
            except:
                pass
    
    # ============ GET /api/lead-sources ============
    
    def test_list_lead_sources_empty(self):
        """GET /api/lead-sources returns empty array for store with no sources"""
        response = self.session.get(f"{BASE_URL}/api/lead-sources?store_id={self.store_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "lead_sources" in data
        assert isinstance(data["lead_sources"], list)
        print(f"✓ GET /api/lead-sources returns {len(data['lead_sources'])} lead sources")
    
    def test_list_lead_sources_requires_store_id(self):
        """GET /api/lead-sources without store_id should fail"""
        response = self.session.get(f"{BASE_URL}/api/lead-sources")
        
        # Should return 422 (validation error) since store_id is required
        assert response.status_code == 422
        print("✓ GET /api/lead-sources requires store_id parameter")
    
    # ============ POST /api/lead-sources ============
    
    def test_create_lead_source_success(self):
        """POST /api/lead-sources creates a new lead source with webhook URL and API key"""
        payload = {
            "name": "TEST_Facebook Ads",
            "description": "Leads from Facebook advertising campaigns",
            "team_id": "test_team_123",  # Using test team ID
            "assignment_method": "jump_ball",
            "is_active": True
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json=payload
        )
        
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data["success"] == True
        assert "lead_source" in data
        
        source = data["lead_source"]
        self.created_source_ids.append(source["id"])
        
        # Verify all fields are present
        assert source["name"] == payload["name"]
        assert source["description"] == payload["description"]
        assert source["team_id"] == payload["team_id"]
        assert source["assignment_method"] == payload["assignment_method"]
        assert source["is_active"] == True
        
        # Verify webhook URL and API key are generated
        assert "webhook_url" in source
        assert source["webhook_url"].startswith("http")
        assert f"/api/lead-sources/inbound/{source['id']}" in source["webhook_url"]
        
        assert "api_key" in source
        assert len(source["api_key"]) > 20  # Should be a secure token
        
        print(f"✓ POST /api/lead-sources creates source with webhook: {source['webhook_url']}")
    
    def test_create_lead_source_jump_ball(self):
        """POST /api/lead-sources with jump_ball assignment method"""
        payload = {
            "name": "TEST_Jump Ball Source",
            "team_id": "test_team_456",
            "assignment_method": "jump_ball"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead_source"]["assignment_method"] == "jump_ball"
        self.created_source_ids.append(data["lead_source"]["id"])
        print("✓ Lead source created with jump_ball assignment method")
    
    def test_create_lead_source_round_robin(self):
        """POST /api/lead-sources with round_robin assignment method"""
        payload = {
            "name": "TEST_Round Robin Source",
            "team_id": "test_team_789",
            "assignment_method": "round_robin"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead_source"]["assignment_method"] == "round_robin"
        self.created_source_ids.append(data["lead_source"]["id"])
        print("✓ Lead source created with round_robin assignment method")
    
    def test_create_lead_source_weighted_round_robin(self):
        """POST /api/lead-sources with weighted_round_robin assignment method"""
        payload = {
            "name": "TEST_Weighted RR Source",
            "team_id": "test_team_101",
            "assignment_method": "weighted_round_robin"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead_source"]["assignment_method"] == "weighted_round_robin"
        self.created_source_ids.append(data["lead_source"]["id"])
        print("✓ Lead source created with weighted_round_robin assignment method")
    
    def test_create_lead_source_missing_name(self):
        """POST /api/lead-sources without name should fail"""
        payload = {
            "team_id": "test_team_123",
            "assignment_method": "jump_ball"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json=payload
        )
        
        assert response.status_code == 422  # Validation error
        print("✓ POST /api/lead-sources requires name field")
    
    def test_create_lead_source_missing_team_id(self):
        """POST /api/lead-sources without team_id should fail"""
        payload = {
            "name": "TEST_No Team Source",
            "assignment_method": "jump_ball"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json=payload
        )
        
        assert response.status_code == 422  # Validation error
        print("✓ POST /api/lead-sources requires team_id field")
    
    # ============ GET /api/lead-sources/{id} ============
    
    def test_get_lead_source_by_id(self):
        """GET /api/lead-sources/{id} returns specific lead source"""
        # First create a lead source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Get By ID Source",
                "team_id": "test_team_get",
                "assignment_method": "jump_ball"
            }
        )
        assert create_response.status_code == 200
        source_id = create_response.json()["lead_source"]["id"]
        self.created_source_ids.append(source_id)
        
        # Now retrieve it
        response = self.session.get(f"{BASE_URL}/api/lead-sources/{source_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["lead_source"]["id"] == source_id
        assert data["lead_source"]["name"] == "TEST_Get By ID Source"
        print(f"✓ GET /api/lead-sources/{source_id} returns correct source")
    
    def test_get_lead_source_not_found(self):
        """GET /api/lead-sources/{id} returns 404 for non-existent source"""
        fake_id = "000000000000000000000000"  # Valid ObjectId format but doesn't exist
        response = self.session.get(f"{BASE_URL}/api/lead-sources/{fake_id}")
        
        assert response.status_code == 404
        print("✓ GET /api/lead-sources returns 404 for non-existent source")
    
    # ============ PATCH /api/lead-sources/{id} ============
    
    def test_update_lead_source(self):
        """PATCH /api/lead-sources/{id} updates lead source"""
        # Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Update Source",
                "team_id": "test_team_update",
                "assignment_method": "jump_ball"
            }
        )
        source_id = create_response.json()["lead_source"]["id"]
        self.created_source_ids.append(source_id)
        
        # Update source
        update_payload = {
            "name": "TEST_Updated Source Name",
            "description": "Updated description",
            "assignment_method": "round_robin"
        }
        
        response = self.session.patch(
            f"{BASE_URL}/api/lead-sources/{source_id}",
            json=update_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["lead_source"]["name"] == "TEST_Updated Source Name"
        assert data["lead_source"]["description"] == "Updated description"
        assert data["lead_source"]["assignment_method"] == "round_robin"
        
        # Verify GET returns updated data
        get_response = self.session.get(f"{BASE_URL}/api/lead-sources/{source_id}")
        assert get_response.json()["lead_source"]["name"] == "TEST_Updated Source Name"
        print("✓ PATCH /api/lead-sources/{id} updates source correctly")
    
    def test_update_lead_source_toggle_active(self):
        """PATCH /api/lead-sources/{id} can toggle is_active status"""
        # Create active source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Toggle Active",
                "team_id": "test_team_toggle",
                "assignment_method": "jump_ball",
                "is_active": True
            }
        )
        source_id = create_response.json()["lead_source"]["id"]
        self.created_source_ids.append(source_id)
        
        # Deactivate
        response = self.session.patch(
            f"{BASE_URL}/api/lead-sources/{source_id}",
            json={"is_active": False}
        )
        
        assert response.status_code == 200
        assert response.json()["lead_source"]["is_active"] == False
        print("✓ PATCH /api/lead-sources can toggle is_active status")
    
    # ============ DELETE /api/lead-sources/{id} ============
    
    def test_delete_lead_source(self):
        """DELETE /api/lead-sources/{id} removes lead source"""
        # Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Delete Source",
                "team_id": "test_team_delete",
                "assignment_method": "jump_ball"
            }
        )
        source_id = create_response.json()["lead_source"]["id"]
        # Don't add to cleanup list since we're deleting it
        
        # Delete source
        response = self.session.delete(f"{BASE_URL}/api/lead-sources/{source_id}")
        
        assert response.status_code == 200
        assert response.json()["success"] == True
        
        # Verify it's gone
        get_response = self.session.get(f"{BASE_URL}/api/lead-sources/{source_id}")
        assert get_response.status_code == 404
        print("✓ DELETE /api/lead-sources/{id} removes source")
    
    # ============ POST /api/lead-sources/inbound/{id} ============
    
    def test_inbound_webhook_with_valid_api_key(self):
        """POST /api/lead-sources/inbound/{id} processes lead with valid API key"""
        # Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Webhook Source",
                "team_id": "test_team_webhook",
                "assignment_method": "jump_ball"
            }
        )
        source = create_response.json()["lead_source"]
        source_id = source["id"]
        api_key = source["api_key"]
        self.created_source_ids.append(source_id)
        
        # Send inbound lead
        lead_payload = {
            "name": "John Doe",
            "phone": "+15551234567",
            "email": "john@example.com",
            "notes": "Interested in SUV"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources/inbound/{source_id}",
            json=lead_payload,
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == 200, f"Webhook failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert "contact_id" in data
        assert "conversation_id" in data
        assert data["assignment_method"] == "jump_ball"
        print(f"✓ POST /api/lead-sources/inbound/{source_id} processes lead successfully")
    
    def test_inbound_webhook_invalid_api_key(self):
        """POST /api/lead-sources/inbound/{id} rejects invalid API key"""
        # Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Invalid API Key Source",
                "team_id": "test_team_invalid",
                "assignment_method": "jump_ball"
            }
        )
        source_id = create_response.json()["lead_source"]["id"]
        self.created_source_ids.append(source_id)
        
        # Send with wrong API key
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources/inbound/{source_id}",
            json={
                "name": "Test Lead",
                "phone": "+15559999999"
            },
            headers={"X-API-Key": "wrong_api_key"}
        )
        
        assert response.status_code == 401
        print("✓ POST /api/lead-sources/inbound rejects invalid API key")
    
    def test_inbound_webhook_no_api_key(self):
        """POST /api/lead-sources/inbound/{id} rejects requests without API key"""
        # Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_No API Key Source",
                "team_id": "test_team_no_key",
                "assignment_method": "jump_ball"
            }
        )
        source_id = create_response.json()["lead_source"]["id"]
        self.created_source_ids.append(source_id)
        
        # Send without API key header
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources/inbound/{source_id}",
            json={
                "name": "Test Lead",
                "phone": "+15558888888"
            }
        )
        
        assert response.status_code == 401
        print("✓ POST /api/lead-sources/inbound rejects requests without API key")
    
    def test_inbound_webhook_inactive_source(self):
        """POST /api/lead-sources/inbound/{id} rejects leads for inactive sources"""
        # Create and deactivate source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Inactive Source",
                "team_id": "test_team_inactive",
                "assignment_method": "jump_ball",
                "is_active": True
            }
        )
        source = create_response.json()["lead_source"]
        source_id = source["id"]
        api_key = source["api_key"]
        self.created_source_ids.append(source_id)
        
        # Deactivate source
        self.session.patch(
            f"{BASE_URL}/api/lead-sources/{source_id}",
            json={"is_active": False}
        )
        
        # Try to send lead
        response = self.session.post(
            f"{BASE_URL}/api/lead-sources/inbound/{source_id}",
            json={
                "name": "Test Lead",
                "phone": "+15557777777"
            },
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == 400
        print("✓ POST /api/lead-sources/inbound rejects leads for inactive sources")
    
    # ============ GET /api/lead-sources/stats/{id} ============
    
    def test_get_lead_source_stats(self):
        """GET /api/lead-sources/stats/{id} returns source statistics"""
        # Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Stats Source",
                "team_id": "test_team_stats",
                "assignment_method": "jump_ball"
            }
        )
        source_id = create_response.json()["lead_source"]["id"]
        self.created_source_ids.append(source_id)
        
        # Get stats
        response = self.session.get(f"{BASE_URL}/api/lead-sources/stats/{source_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "stats" in data
        assert "total_leads" in data["stats"]
        assert "assignment_method" in data["stats"]
        print(f"✓ GET /api/lead-sources/stats returns stats: {data['stats']}")
    
    # ============ Integration Tests ============
    
    def test_full_lead_source_workflow(self):
        """Test complete workflow: create source -> receive lead -> get stats"""
        # 1. Create source
        create_response = self.session.post(
            f"{BASE_URL}/api/lead-sources?store_id={self.store_id}",
            json={
                "name": "TEST_Full Workflow Source",
                "description": "Testing complete workflow",
                "team_id": "test_team_workflow",
                "assignment_method": "jump_ball"
            }
        )
        assert create_response.status_code == 200
        source = create_response.json()["lead_source"]
        source_id = source["id"]
        api_key = source["api_key"]
        self.created_source_ids.append(source_id)
        print("  1. Created lead source")
        
        # 2. Verify source is listed
        list_response = self.session.get(f"{BASE_URL}/api/lead-sources?store_id={self.store_id}")
        sources = list_response.json()["lead_sources"]
        assert any(s["id"] == source_id for s in sources)
        print("  2. Source appears in list")
        
        # 3. Send inbound lead
        lead_response = self.session.post(
            f"{BASE_URL}/api/lead-sources/inbound/{source_id}",
            json={
                "first_name": "Jane",
                "last_name": "Smith",
                "phone": "+15551112222",
                "email": "jane@test.com",
                "notes": "Test lead from workflow"
            },
            headers={"X-API-Key": api_key}
        )
        assert lead_response.status_code == 200
        lead_data = lead_response.json()
        assert lead_data["success"] == True
        print("  3. Inbound lead received successfully")
        
        # 4. Verify stats updated
        stats_response = self.session.get(f"{BASE_URL}/api/lead-sources/stats/{source_id}")
        assert stats_response.status_code == 200
        stats = stats_response.json()["stats"]
        assert stats["total_leads"] >= 1  # At least 1 lead
        print(f"  4. Stats show {stats['total_leads']} total leads")
        
        # 5. Verify source shows lead count updated
        get_response = self.session.get(f"{BASE_URL}/api/lead-sources/{source_id}")
        assert get_response.json()["lead_source"]["lead_count"] >= 1
        print("  5. Source lead_count updated")
        
        print("✓ Full workflow test passed!")


class TestLeadSourcesTeamInbox:
    """Team inbox endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        
        data = response.json()
        self.user_id = data["user"]["_id"]
        self.store_id = data["user"].get("store_id", self.user_id)
    
    def test_get_team_inbox(self):
        """GET /api/lead-sources/team-inbox/{team_id} returns team conversations"""
        team_id = "test_team_inbox"
        
        response = self.session.get(f"{BASE_URL}/api/lead-sources/team-inbox/{team_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "conversations" in data
        assert isinstance(data["conversations"], list)
        print(f"✓ GET /api/lead-sources/team-inbox returns {len(data['conversations'])} conversations")
    
    def test_get_team_inbox_include_claimed(self):
        """GET /api/lead-sources/team-inbox/{team_id}?include_claimed=true includes claimed leads"""
        team_id = "test_team_inbox_claimed"
        
        response = self.session.get(
            f"{BASE_URL}/api/lead-sources/team-inbox/{team_id}?include_claimed=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ GET /api/lead-sources/team-inbox with include_claimed=true works")
    
    def test_get_user_inbox(self):
        """GET /api/lead-sources/user-inbox/{user_id} returns user's assigned leads"""
        response = self.session.get(f"{BASE_URL}/api/lead-sources/user-inbox/{self.user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "conversations" in data
        print(f"✓ GET /api/lead-sources/user-inbox returns {len(data['conversations'])} conversations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
