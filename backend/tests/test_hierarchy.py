"""
Test Hierarchy Management APIs - Organizations -> Stores -> Users
Tests all hierarchy endpoints for the MVPLine CRM admin panel.
"""
import pytest
import requests
import os
import random
import string

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://email-invite-patch.preview.emergentagent.com')

# Test data constants
TEST_ORG_ID = "699637971b07c23426a53249"  # Ken Garff Auto Group
TEST_STORE_ID = "699637981b07c23426a5324a"  # Ken Garff Honda Downtown
TEST_USER_ID = "6995b8bf6f535e1cec4e4ad4"  # John Doe

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHierarchyOverview:
    """Test /api/admin/hierarchy/overview endpoint"""
    
    def test_hierarchy_overview_returns_organizations(self, api_client):
        """Test that overview returns all organizations with counts"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Validate response structure
        assert "organizations" in data
        assert "unassigned_users" in data
        assert "total_organizations" in data
        assert "total_stores" in data
        assert "total_users" in data
        
        # Validate organizations array
        assert isinstance(data["organizations"], list)
        assert len(data["organizations"]) > 0
        
        # Validate organization structure
        org = data["organizations"][0]
        assert "_id" in org
        assert "name" in org
        assert "store_count" in org
        assert "user_count" in org
        assert "admin_count" in org
        
        print(f"SUCCESS: Found {data['total_organizations']} organizations, {data['total_stores']} stores, {data['total_users']} users")
    
    def test_hierarchy_overview_counts_match(self, api_client):
        """Verify the counts are accurate"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/overview")
        data = response.json()
        
        # Total organizations should match array length
        assert data["total_organizations"] == len(data["organizations"])
        
        # Sum of org store counts should be reasonable (may have independent stores)
        total_counted_stores = sum(org["store_count"] for org in data["organizations"])
        assert total_counted_stores <= data["total_stores"]
        
        print(f"SUCCESS: Counts validated - {data['unassigned_users']} unassigned users")


class TestOrganizationHierarchy:
    """Test /api/admin/hierarchy/organization/{org_id} endpoint"""
    
    def test_organization_hierarchy_returns_full_data(self, api_client):
        """Test that organization hierarchy returns stores and users"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/organization/{TEST_ORG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Validate response structure
        assert "organization" in data
        assert "admins" in data
        assert "stores" in data
        assert "unassigned_users" in data
        assert "stats" in data
        
        # Validate organization details
        org = data["organization"]
        assert org["_id"] == TEST_ORG_ID
        assert "name" in org
        assert "active" in org
        
        # Validate stats
        stats = data["stats"]
        assert "total_stores" in stats
        assert "total_users" in stats
        assert "total_admins" in stats
        assert "unassigned_count" in stats
        
        print(f"SUCCESS: Org '{org['name']}' has {stats['total_stores']} stores, {stats['total_users']} users")
    
    def test_organization_hierarchy_includes_store_users(self, api_client):
        """Test that stores include their assigned users"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/organization/{TEST_ORG_ID}")
        data = response.json()
        
        # Find a store with users
        stores_with_users = [s for s in data["stores"] if s["user_count"] > 0]
        
        if stores_with_users:
            store = stores_with_users[0]
            assert "users" in store
            assert len(store["users"]) == store["user_count"]
            
            # Validate user structure
            user = store["users"][0]
            assert "_id" in user
            assert "name" in user
            assert "email" in user
            assert "role" in user
            assert "is_active" in user
            
            print(f"SUCCESS: Store '{store['name']}' has {store['user_count']} users with full details")
        else:
            print("WARNING: No stores with users found to validate")
    
    def test_organization_not_found_returns_404(self, api_client):
        """Test that invalid org ID returns 404"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/organization/000000000000000000000000")
        assert response.status_code == 404
        
        print("SUCCESS: 404 returned for non-existent organization")


class TestStoreHierarchy:
    """Test /api/admin/hierarchy/store/{store_id} endpoint"""
    
    def test_store_hierarchy_returns_users(self, api_client):
        """Test that store hierarchy returns all users"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Validate response structure
        assert "store" in data
        assert "organization" in data
        assert "users" in data
        assert "available_users" in data
        assert "user_count" in data
        
        # Validate store details
        store = data["store"]
        assert store["_id"] == TEST_STORE_ID
        assert "name" in store
        assert "active" in store
        
        # Validate user count matches
        assert data["user_count"] == len(data["users"])
        
        print(f"SUCCESS: Store '{store['name']}' has {data['user_count']} users")
    
    def test_store_hierarchy_includes_store_ids(self, api_client):
        """Test that users include their store_ids array"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/store/{TEST_STORE_ID}")
        data = response.json()
        
        if data["users"]:
            user = data["users"][0]
            assert "store_ids" in user
            assert isinstance(user["store_ids"], list)
            
            print(f"SUCCESS: User '{user['name']}' has store_ids: {user['store_ids']}")
        else:
            print("WARNING: No users in store to validate")
    
    def test_store_not_found_returns_404(self, api_client):
        """Test that invalid store ID returns 404"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/store/000000000000000000000000")
        assert response.status_code == 404
        
        print("SUCCESS: 404 returned for non-existent store")


class TestUsersHierarchy:
    """Test /api/admin/hierarchy/users endpoint with filters"""
    
    def test_users_hierarchy_all_users(self, api_client):
        """Test getting all users without filter"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users")
        assert response.status_code == 200
        
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] == len(data["users"])
        
        print(f"SUCCESS: Found {data['total']} users")
    
    def test_users_hierarchy_unassigned_filter(self, api_client):
        """Test filtering for unassigned users"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users?filter=unassigned")
        assert response.status_code == 200
        
        data = response.json()
        # All returned users should have no org
        for user in data["users"]:
            assert user["organization_id"] is None or user["organization_id"] == ""
        
        print(f"SUCCESS: Found {data['total']} unassigned users")
    
    def test_users_hierarchy_org_admins_filter(self, api_client):
        """Test filtering for org admins"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users?filter=org_admins")
        assert response.status_code == 200
        
        data = response.json()
        # All returned users should be org_admin role
        for user in data["users"]:
            assert user["role"] == "org_admin"
        
        print(f"SUCCESS: Found {data['total']} org admins")
    
    def test_users_hierarchy_by_organization(self, api_client):
        """Test filtering by organization_id"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users?organization_id={TEST_ORG_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # All returned users should belong to the org
        for user in data["users"]:
            assert user["organization_id"] == TEST_ORG_ID
        
        print(f"SUCCESS: Found {data['total']} users in organization")
    
    def test_users_hierarchy_includes_store_names(self, api_client):
        """Test that users include their store names"""
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users")
        data = response.json()
        
        # Find a user with stores
        users_with_stores = [u for u in data["users"] if u.get("stores")]
        
        if users_with_stores:
            user = users_with_stores[0]
            store = user["stores"][0]
            assert "id" in store
            assert "name" in store
            
            print(f"SUCCESS: User '{user['name']}' assigned to store '{store['name']}'")
        else:
            print("WARNING: No users with store assignments found")


class TestAssignUserToOrganization:
    """Test /api/admin/hierarchy/users/{user_id}/assign-org endpoint"""
    
    def test_assign_user_to_organization(self, api_client):
        """Test assigning a user to an organization"""
        # First, find an unassigned user
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users?filter=unassigned")
        data = response.json()
        
        if not data["users"]:
            pytest.skip("No unassigned users available for testing")
        
        test_user_id = data["users"][0]["_id"]
        
        # Assign to organization
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-org",
            json={"organization_id": TEST_ORG_ID, "role": "user"}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["organization_id"] == TEST_ORG_ID
        assert result["role"] == "user"
        
        # Verify GET shows updated data
        verify = api_client.get(f"{BASE_URL}/api/admin/users/{test_user_id}")
        assert verify.json()["organization_id"] == TEST_ORG_ID
        
        # Clean up - remove from org
        api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-org",
            json={"organization_id": None, "role": "user"}
        )
        
        print(f"SUCCESS: Assigned and unassigned user from organization")
    
    def test_assign_to_invalid_org_returns_404(self, api_client):
        """Test that assigning to invalid org returns 404"""
        # Find a user
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/users?filter=unassigned")
        data = response.json()
        
        if not data["users"]:
            pytest.skip("No unassigned users available for testing")
        
        test_user_id = data["users"][0]["_id"]
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-org",
            json={"organization_id": "000000000000000000000000", "role": "user"}
        )
        assert response.status_code == 404
        
        print("SUCCESS: 404 returned for invalid organization")


class TestAssignUserToStore:
    """Test /api/admin/hierarchy/users/{user_id}/assign-store endpoint"""
    
    def test_assign_user_to_store(self, api_client):
        """Test adding a user to a store"""
        # Use a user already in the org
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/organization/{TEST_ORG_ID}")
        data = response.json()
        
        # Find an unassigned user in the org
        if not data["unassigned_users"]:
            # Find an org user not in the test store
            test_user_id = None
            for admin in data["admins"]:
                test_user_id = admin["_id"]
                break
            if not test_user_id:
                pytest.skip("No users available for store assignment testing")
        else:
            test_user_id = data["unassigned_users"][0]["_id"]
        
        # Assign to store
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-store",
            json={"store_id": TEST_STORE_ID}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert TEST_STORE_ID in result["store_ids"]
        
        print(f"SUCCESS: Assigned user to store")
        
        # Clean up
        api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/remove-store",
            json={"store_id": TEST_STORE_ID}
        )
    
    def test_assign_to_invalid_store_returns_404(self, api_client):
        """Test that assigning to invalid store returns 404"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{TEST_USER_ID}/assign-store",
            json={"store_id": "000000000000000000000000"}
        )
        assert response.status_code == 404
        
        print("SUCCESS: 404 returned for invalid store")
    
    def test_assign_store_requires_store_id(self, api_client):
        """Test that store_id is required"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{TEST_USER_ID}/assign-store",
            json={}
        )
        assert response.status_code == 400
        
        print("SUCCESS: 400 returned when store_id is missing")


class TestRemoveUserFromStore:
    """Test /api/admin/hierarchy/users/{user_id}/remove-store endpoint"""
    
    def test_remove_user_from_store(self, api_client):
        """Test removing a user from a store"""
        # First, add a user to a store
        response = api_client.get(f"{BASE_URL}/api/admin/hierarchy/organization/{TEST_ORG_ID}")
        data = response.json()
        
        # Find a user to test with
        test_user_id = None
        if data["admins"]:
            test_user_id = data["admins"][0]["_id"]
        elif data["unassigned_users"]:
            test_user_id = data["unassigned_users"][0]["_id"]
        else:
            pytest.skip("No users available for removal testing")
        
        # Add to store first
        api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/assign-store",
            json={"store_id": TEST_STORE_ID}
        )
        
        # Now remove
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{test_user_id}/remove-store",
            json={"store_id": TEST_STORE_ID}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert TEST_STORE_ID not in result["store_ids"]
        
        print(f"SUCCESS: Removed user from store")
    
    def test_remove_store_requires_store_id(self, api_client):
        """Test that store_id is required"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{TEST_USER_ID}/remove-store",
            json={}
        )
        assert response.status_code == 400
        
        print("SUCCESS: 400 returned when store_id is missing")


class TestUpdateUserRole:
    """Test /api/admin/hierarchy/users/{user_id}/role endpoint"""
    
    def test_update_user_role(self, api_client):
        """Test updating a user's role"""
        # Get a test user
        response = api_client.get(f"{BASE_URL}/api/admin/users/{TEST_USER_ID}")
        original_role = response.json()["role"]
        
        # Update to a different role
        new_role = "store_manager" if original_role != "store_manager" else "user"
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{TEST_USER_ID}/role",
            json={"role": new_role}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["role"] == new_role
        
        # Verify GET shows updated role
        verify = api_client.get(f"{BASE_URL}/api/admin/users/{TEST_USER_ID}")
        assert verify.json()["role"] == new_role
        
        # Restore original role
        api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{TEST_USER_ID}/role",
            json={"role": original_role}
        )
        
        print(f"SUCCESS: Changed role from {original_role} to {new_role} and back")
    
    def test_update_role_validates_input(self, api_client):
        """Test that invalid role returns 400"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/{TEST_USER_ID}/role",
            json={"role": "invalid_role"}
        )
        assert response.status_code == 400
        
        print("SUCCESS: 400 returned for invalid role")
    
    def test_update_role_user_not_found(self, api_client):
        """Test that invalid user returns 404"""
        response = api_client.put(
            f"{BASE_URL}/api/admin/hierarchy/users/000000000000000000000000/role",
            json={"role": "user"}
        )
        assert response.status_code == 404
        
        print("SUCCESS: 404 returned for non-existent user")


class TestGetRoles:
    """Test /api/admin/roles endpoint"""
    
    def test_get_available_roles(self, api_client):
        """Test getting available roles"""
        response = api_client.get(f"{BASE_URL}/api/admin/roles")
        assert response.status_code == 200
        
        data = response.json()
        assert "roles" in data
        assert len(data["roles"]) == 4  # super_admin, org_admin, store_manager, user
        
        # Validate role structure
        for role in data["roles"]:
            assert "id" in role
            assert "label" in role
            assert "description" in role
            assert "color" in role
        
        role_ids = [r["id"] for r in data["roles"]]
        assert "super_admin" in role_ids
        assert "org_admin" in role_ids
        assert "store_manager" in role_ids
        assert "user" in role_ids
        
        print(f"SUCCESS: Found {len(data['roles'])} roles")


class TestUserToggleStatus:
    """Test user activation/deactivation via /api/admin/users/{user_id}"""
    
    def test_toggle_user_active_status(self, api_client):
        """Test toggling user is_active status"""
        # Get current status
        response = api_client.get(f"{BASE_URL}/api/admin/users/{TEST_USER_ID}")
        current_status = response.json().get("is_active", True)
        
        # Toggle status
        new_status = not current_status
        response = api_client.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}",
            json={"is_active": new_status}
        )
        assert response.status_code == 200
        
        # Verify change
        verify = api_client.get(f"{BASE_URL}/api/admin/users/{TEST_USER_ID}")
        assert verify.json()["is_active"] == new_status
        
        # Restore original status
        api_client.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}",
            json={"is_active": current_status}
        )
        
        print(f"SUCCESS: Toggled user active status from {current_status} to {new_status} and back")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
