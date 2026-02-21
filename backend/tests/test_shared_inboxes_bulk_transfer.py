"""
Test Shared Inboxes and Bulk Customer Transfer APIs
These features allow:
1. Shared Inboxes - Multiple users assigned to a single phone number/inbox
2. Bulk Customer Transfers - Transfer all contacts/conversations from one user to another
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

# Test credentials from provided data
TEST_USER_ID = "69963e636d8473ba25695a34"
TEST_EMAIL = "superadmin@mvpline.com"
TEST_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for superadmin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    if auth_token:
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestSharedInboxesAPI:
    """Test Shared Inboxes CRUD operations"""
    
    created_inbox_id = None
    
    def test_list_shared_inboxes(self, authenticated_client):
        """GET /api/admin/team/shared-inboxes - List all shared inboxes"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={TEST_USER_ID}"
        )
        print(f"List shared inboxes: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of inboxes"
        print(f"Found {len(data)} shared inboxes")
    
    def test_create_shared_inbox(self, authenticated_client):
        """POST /api/admin/team/shared-inboxes - Create a new shared inbox"""
        inbox_data = {
            "name": "TEST_Support Team Inbox",
            "phone_number": "+1555TEST123",
            "description": "Test inbox for support team"
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={TEST_USER_ID}",
            json=inbox_data
        )
        print(f"Create shared inbox: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data, "Expected 'id' in response"
        assert "message" in data, "Expected 'message' in response"
        TestSharedInboxesAPI.created_inbox_id = data["id"]
        print(f"Created inbox ID: {TestSharedInboxesAPI.created_inbox_id}")
    
    def test_create_inbox_duplicate_phone_number(self, authenticated_client):
        """POST /api/admin/team/shared-inboxes - Should fail for duplicate phone number"""
        inbox_data = {
            "name": "TEST_Duplicate Inbox",
            "phone_number": "+1555TEST123",  # Same phone number as above
            "description": "This should fail"
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/admin/team/shared-inboxes?user_id={TEST_USER_ID}",
            json=inbox_data
        )
        print(f"Create duplicate inbox: {response.status_code}")
        
        assert response.status_code == 400, f"Expected 400 for duplicate phone, got {response.status_code}"
    
    def test_get_shared_inbox_details(self, authenticated_client):
        """GET /api/admin/team/shared-inboxes/{id} - Get inbox details"""
        if not TestSharedInboxesAPI.created_inbox_id:
            pytest.skip("No inbox was created")
        
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{TestSharedInboxesAPI.created_inbox_id}?user_id={TEST_USER_ID}"
        )
        print(f"Get inbox details: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["id"] == TestSharedInboxesAPI.created_inbox_id
        assert data["name"] == "TEST_Support Team Inbox"
        assert "assigned_users" in data
        print(f"Inbox has {len(data['assigned_users'])} assigned users")


class TestUserAssignment:
    """Test user assignment to shared inboxes"""
    
    target_user_id = None
    
    def test_list_users_for_assignment(self, authenticated_client):
        """GET /api/admin/team/users - List available users"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/users?user_id={TEST_USER_ID}"
        )
        print(f"List users: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of users"
        print(f"Found {len(data)} users available for assignment")
        
        # Save a user ID for assignment tests
        if len(data) > 0:
            TestUserAssignment.target_user_id = data[0]["id"]
            print(f"Will use user {data[0]['name']} ({TestUserAssignment.target_user_id}) for assignment tests")
    
    def test_assign_user_to_inbox(self, authenticated_client):
        """POST /api/admin/team/shared-inboxes/{id}/assign - Assign user to inbox"""
        if not TestSharedInboxesAPI.created_inbox_id:
            pytest.skip("No inbox was created")
        if not TestUserAssignment.target_user_id:
            pytest.skip("No target user available")
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{TestSharedInboxesAPI.created_inbox_id}/assign"
            f"?target_user_id={TestUserAssignment.target_user_id}&user_id={TEST_USER_ID}"
        )
        print(f"Assign user: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data
        print(f"Assignment result: {data['message']}")
    
    def test_verify_user_assigned(self, authenticated_client):
        """Verify user was assigned to inbox"""
        if not TestSharedInboxesAPI.created_inbox_id:
            pytest.skip("No inbox was created")
        
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{TestSharedInboxesAPI.created_inbox_id}?user_id={TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        
        assigned_ids = [u["id"] for u in data["assigned_users"]]
        assert TestUserAssignment.target_user_id in assigned_ids, "User should be assigned"
        print(f"Verified: User {TestUserAssignment.target_user_id} is assigned to inbox")
    
    def test_unassign_user_from_inbox(self, authenticated_client):
        """POST /api/admin/team/shared-inboxes/{id}/unassign - Remove user from inbox"""
        if not TestSharedInboxesAPI.created_inbox_id:
            pytest.skip("No inbox was created")
        if not TestUserAssignment.target_user_id:
            pytest.skip("No target user available")
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{TestSharedInboxesAPI.created_inbox_id}/unassign"
            f"?target_user_id={TestUserAssignment.target_user_id}&user_id={TEST_USER_ID}"
        )
        print(f"Unassign user: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data
        print(f"Unassign result: {data['message']}")
    
    def test_verify_user_unassigned(self, authenticated_client):
        """Verify user was removed from inbox"""
        if not TestSharedInboxesAPI.created_inbox_id:
            pytest.skip("No inbox was created")
        
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{TestSharedInboxesAPI.created_inbox_id}?user_id={TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        
        assigned_ids = [u["id"] for u in data["assigned_users"]]
        assert TestUserAssignment.target_user_id not in assigned_ids, "User should be unassigned"
        print(f"Verified: User {TestUserAssignment.target_user_id} is no longer assigned")


class TestBulkTransferAPI:
    """Test Bulk Customer Transfer operations"""
    
    def test_get_transfer_preview(self, authenticated_client):
        """GET /api/admin/team/bulk-transfer/preview - Preview transfer for a user"""
        # Get a user to preview transfer for
        users_response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/users?user_id={TEST_USER_ID}"
        )
        if users_response.status_code != 200 or not users_response.json():
            pytest.skip("No users available for preview test")
        
        preview_user_id = users_response.json()[0]["id"]
        
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/bulk-transfer/preview"
            f"?from_user_id={preview_user_id}&user_id={TEST_USER_ID}"
        )
        print(f"Transfer preview: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate response structure
        assert "from_user" in data, "Expected 'from_user' in preview"
        assert "items_to_transfer" in data, "Expected 'items_to_transfer' in preview"
        assert "total" in data, "Expected 'total' count in preview"
        
        items = data["items_to_transfer"]
        assert "contacts" in items
        assert "conversations" in items
        assert "tasks" in items
        assert "campaign_enrollments" in items
        
        print(f"Preview: {data['total']} total items for user {data['from_user']['name']}")
        print(f"  - Contacts: {items['contacts']}")
        print(f"  - Conversations: {items['conversations']}")
        print(f"  - Tasks: {items['tasks']}")
        print(f"  - Campaigns: {items['campaign_enrollments']}")
    
    def test_get_transfer_preview_invalid_user(self, authenticated_client):
        """GET /api/admin/team/bulk-transfer/preview - Should fail for invalid user"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/bulk-transfer/preview"
            f"?from_user_id=invaliduserid123&user_id={TEST_USER_ID}"
        )
        print(f"Transfer preview invalid user: {response.status_code}")
        
        # Could be 400 or 404 depending on implementation
        assert response.status_code in [400, 404, 422], f"Expected error status, got {response.status_code}"
    
    def test_get_transfer_history(self, authenticated_client):
        """GET /api/admin/team/bulk-transfer/history - Get transfer history"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/bulk-transfer/history?user_id={TEST_USER_ID}"
        )
        print(f"Transfer history: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of transfers"
        print(f"Found {len(data)} historical transfers")
        
        if len(data) > 0:
            first = data[0]
            assert "from_user" in first
            assert "to_user" in first
            assert "status" in first
            print(f"Latest transfer: {first['from_user']} -> {first['to_user']} ({first['status']})")
    
    def test_execute_bulk_transfer(self, authenticated_client):
        """POST /api/admin/team/bulk-transfer - Execute a bulk transfer"""
        # Get two users for transfer
        users_response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/users?user_id={TEST_USER_ID}"
        )
        if users_response.status_code != 200:
            pytest.skip("Cannot get users list")
        
        users = users_response.json()
        if len(users) < 2:
            pytest.skip("Need at least 2 users for transfer test")
        
        from_user = users[0]
        to_user = users[1]
        
        transfer_data = {
            "from_user_id": from_user["id"],
            "to_user_id": to_user["id"],
            "transfer_contacts": True,
            "transfer_conversations": True,
            "transfer_tasks": True,
            "transfer_campaigns": True,
            "reason": "TEST_Bulk transfer initiated from pytest"
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/admin/team/bulk-transfer?user_id={TEST_USER_ID}",
            json=transfer_data
        )
        print(f"Execute transfer: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "message" in data
        assert "details" in data
        print(f"Transfer result: {data['message']}")
        print(f"Details: {data['details']}")
    
    def test_bulk_transfer_invalid_from_user(self, authenticated_client):
        """POST /api/admin/team/bulk-transfer - Should fail for invalid source user"""
        users_response = authenticated_client.get(
            f"{BASE_URL}/api/admin/team/users?user_id={TEST_USER_ID}"
        )
        if users_response.status_code != 200 or not users_response.json():
            pytest.skip("Cannot get users list")
        
        to_user = users_response.json()[0]
        
        transfer_data = {
            "from_user_id": "invaliduserid123",
            "to_user_id": to_user["id"],
            "transfer_contacts": True
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/admin/team/bulk-transfer?user_id={TEST_USER_ID}",
            json=transfer_data
        )
        print(f"Transfer invalid from_user: {response.status_code}")
        
        assert response.status_code in [400, 404, 422], f"Expected error status, got {response.status_code}"


class TestSharedInboxCleanup:
    """Cleanup test data"""
    
    def test_delete_shared_inbox(self, authenticated_client):
        """DELETE /api/admin/team/shared-inboxes/{id} - Delete the test inbox"""
        if not TestSharedInboxesAPI.created_inbox_id:
            pytest.skip("No inbox was created to delete")
        
        response = authenticated_client.delete(
            f"{BASE_URL}/api/admin/team/shared-inboxes/{TestSharedInboxesAPI.created_inbox_id}?user_id={TEST_USER_ID}"
        )
        print(f"Delete inbox: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data
        print(f"Delete result: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
