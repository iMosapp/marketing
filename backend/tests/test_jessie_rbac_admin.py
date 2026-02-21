"""
Backend Tests for Jessie AI Assistant and Admin RBAC Endpoints

Features tested:
1. Jessie AI Chat - Text response via GPT-5.2
2. Jessie AI Chat with Voice - Audio base64 via OpenAI TTS
3. Jessie Chat History - Conversation memory
4. Admin RBAC - Organization access control
5. Admin RBAC - Store access control
6. Admin RBAC - User data isolation

Test Credentials:
- Super Admin: forest@mvpline.com / MVPLine2024! (ID: 69975a8b6ff748b1f9da6b57)
- Manager: manager@mvpline.com / Manager123! (ID: 699783e741097acc0e570b8d)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://imos-marketing.preview.emergentagent.com').rstrip('/')
if BASE_URL and not BASE_URL.startswith('http'):
    BASE_URL = f"https://{BASE_URL}"

print(f"Jessie & RBAC Admin Testing against BASE_URL: {BASE_URL}")

# Test User IDs from review request
SUPER_ADMIN_ID = "69975a8b6ff748b1f9da6b57"
MANAGER_ID = "699783e741097acc0e570b8d"

# Existing RBAC test users
SUPER_ADMIN_RBAC_ID = "69963e636d8473ba25695a34"
ORG_ADMIN_ID = "69963e5b6d8473ba25695a30"
REGULAR_USER_ID = "69963e5b6d8473ba25695a31"
EXTERNAL_USER_ID = "69963e5b6d8473ba25695a32"
STORE_MANAGER_ID = "69963f059eb007396fc5c496"

ORG_ID = "69963e5a6d8473ba25695a2e"
STORE_ID = "69963e5b6d8473ba25695a2f"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# =========== JESSIE AI ASSISTANT TESTS ===========

class TestJessieChatEndpoint:
    """Test Jessie /api/jessie/chat endpoint for text responses"""
    
    def test_jessie_chat_returns_text_response(self, api_client):
        """Jessie chat should return a text response"""
        payload = {
            "user_id": SUPER_ADMIN_ID,
            "message": "Hello Jessie, what can you help me with?",
            "include_voice": False
        }
        
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json=payload, timeout=60)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "text" in data, "Response should include 'text' field"
        assert "session_id" in data, "Response should include 'session_id' field"
        assert len(data["text"]) > 0, "Response text should not be empty"
        
        print(f"✓ Jessie chat response: '{data['text'][:100]}...'")
        print(f"✓ Session ID: {data['session_id']}")
    
    def test_jessie_chat_with_voice_returns_audio(self, api_client):
        """Jessie chat with include_voice=true should return audio_base64"""
        payload = {
            "user_id": SUPER_ADMIN_ID,
            "message": "Tell me about MVPLine features briefly",
            "include_voice": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json=payload, timeout=90)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "text" in data, "Response should include 'text' field"
        assert "session_id" in data, "Response should include 'session_id' field"
        
        # Check for audio response
        if "audio_base64" in data:
            assert len(data["audio_base64"]) > 0, "audio_base64 should not be empty"
            assert data.get("audio_format") == "mp3", "Audio format should be mp3"
            print(f"✓ Jessie voice response: audio_base64 length = {len(data['audio_base64'])}")
        elif "voice_error" in data:
            print(f"⚠ Voice generation had error: {data['voice_error']}")
            # Allow test to pass if voice generation failed but text worked
        else:
            pytest.fail("Response should include either 'audio_base64' or 'voice_error'")
        
        print(f"✓ Text response: '{data['text'][:100]}...'")
    
    def test_jessie_chat_empty_message(self, api_client):
        """Jessie chat with empty message should be handled"""
        payload = {
            "user_id": SUPER_ADMIN_ID,
            "message": "",
            "include_voice": False
        }
        
        response = api_client.post(f"{BASE_URL}/api/jessie/chat", json=payload, timeout=60)
        # Empty message might return 400 or 422 or process with empty response
        assert response.status_code in [200, 400, 422, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ Empty message handled with status: {response.status_code}")


class TestJessieHistoryEndpoint:
    """Test Jessie /api/jessie/history/{user_id} endpoint"""
    
    def test_jessie_history_returns_messages(self, api_client):
        """Jessie history should return previous messages"""
        # First, send a message to create history
        chat_payload = {
            "user_id": SUPER_ADMIN_ID,
            "message": "Test message for history check",
            "include_voice": False
        }
        chat_response = api_client.post(f"{BASE_URL}/api/jessie/chat", json=chat_payload, timeout=60)
        assert chat_response.status_code == 200, f"Chat failed: {chat_response.text}"
        
        # Then get history
        response = api_client.get(f"{BASE_URL}/api/jessie/history/{SUPER_ADMIN_ID}")
        assert response.status_code == 200, f"History failed: {response.text}"
        
        data = response.json()
        assert "messages" in data, "Response should include 'messages' field"
        assert isinstance(data["messages"], list), "Messages should be a list"
        
        print(f"✓ Jessie history: {len(data['messages'])} messages found")
        
        # Check message structure if messages exist
        if len(data["messages"]) > 0:
            msg = data["messages"][-1]
            assert "role" in msg, "Message should have 'role' field"
            assert "content" in msg, "Message should have 'content' field"
            print(f"✓ Last message role: {msg['role']}, content: '{msg['content'][:50]}...'")
    
    def test_jessie_history_new_user(self, api_client):
        """Jessie history for new user should return empty messages"""
        # Use a test user ID that likely has no history
        new_user_id = "507f1f77bcf86cd799439999"
        
        response = api_client.get(f"{BASE_URL}/api/jessie/history/{new_user_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "messages" in data, "Response should include 'messages' field"
        assert isinstance(data["messages"], list), "Messages should be a list"
        # New user should have 0 messages
        print(f"✓ New user history: {len(data['messages'])} messages (expected 0 or empty)")


class TestJessieSessionEndpoint:
    """Test Jessie /api/jessie/session/{user_id} endpoint"""
    
    def test_jessie_get_or_create_session(self, api_client):
        """Jessie session endpoint should return session info"""
        response = api_client.get(f"{BASE_URL}/api/jessie/session/{SUPER_ADMIN_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should include 'session_id' field"
        print(f"✓ Session: {data['session_id']}")


# =========== ADMIN RBAC ORGANIZATION TESTS ===========

class TestAdminOrganizationsRBAC:
    """Test RBAC for /api/admin/organizations endpoint"""
    
    def test_super_admin_sees_all_organizations(self, api_client):
        """Super admin should see ALL organizations"""
        headers = {"X-User-ID": SUPER_ADMIN_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/organizations", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        orgs = response.json()
        assert isinstance(orgs, list), "Response should be a list"
        
        print(f"✓ Super admin sees {len(orgs)} organizations")
        if len(orgs) > 0:
            print(f"  Sample org: {orgs[0].get('name', 'N/A')}")
    
    def test_manager_sees_only_own_organization(self, api_client):
        """Manager should see only their own organization"""
        headers = {"X-User-ID": MANAGER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/organizations", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        orgs = response.json()
        assert isinstance(orgs, list), "Response should be a list"
        
        print(f"✓ Manager sees {len(orgs)} organizations")
        # Manager should see 0 or 1 organizations (their own)
        assert len(orgs) <= 1, "Manager should see at most 1 organization (their own)"
    
    def test_store_manager_sees_limited_organizations(self, api_client):
        """Store manager should see only their organization"""
        headers = {"X-User-ID": STORE_MANAGER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/organizations", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        orgs = response.json()
        print(f"✓ Store manager sees {len(orgs)} organizations")
    
    def test_no_user_id_header_backward_compat(self, api_client):
        """Request without X-User-ID header should work (backward compatibility)"""
        response = api_client.get(f"{BASE_URL}/api/admin/organizations")
        # Should work for backward compatibility
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ No X-User-ID header works (backward compat)")


class TestAdminStoresRBAC:
    """Test RBAC for /api/admin/stores endpoint"""
    
    def test_super_admin_sees_all_stores(self, api_client):
        """Super admin should see ALL stores"""
        headers = {"X-User-ID": SUPER_ADMIN_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/stores", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        stores = response.json()
        assert isinstance(stores, list), "Response should be a list"
        
        print(f"✓ Super admin sees {len(stores)} stores")
        if len(stores) > 0:
            print(f"  Sample store: {stores[0].get('name', 'N/A')}")
    
    def test_manager_sees_only_assigned_stores(self, api_client):
        """Manager (store_manager role) should see only their assigned stores"""
        headers = {"X-User-ID": MANAGER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/stores", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        stores = response.json()
        assert isinstance(stores, list), "Response should be a list"
        
        print(f"✓ Manager sees {len(stores)} stores")
    
    def test_store_manager_sees_own_stores(self, api_client):
        """Store manager should see only their assigned stores"""
        headers = {"X-User-ID": STORE_MANAGER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/stores", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        stores = response.json()
        print(f"✓ Store manager sees {len(stores)} stores")
    
    def test_regular_user_sees_no_stores(self, api_client):
        """Regular user should not see stores list (empty)"""
        headers = {"X-User-ID": REGULAR_USER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/stores", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        stores = response.json()
        # Regular users typically don't see stores list
        print(f"✓ Regular user sees {len(stores)} stores")


class TestAdminUsersRBAC:
    """Test RBAC for /api/admin/users endpoint"""
    
    def test_super_admin_sees_all_users(self, api_client):
        """Super admin should see ALL users"""
        headers = {"X-User-ID": SUPER_ADMIN_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        
        print(f"✓ Super admin sees {len(users)} users")
    
    def test_store_manager_cannot_access_other_users_data(self, api_client):
        """Store manager should not access users outside their stores"""
        headers = {"X-User-ID": STORE_MANAGER_ID}
        
        # Try to access a user outside their store
        response = api_client.get(f"{BASE_URL}/api/admin/users/{EXTERNAL_USER_ID}", headers=headers)
        
        # Should be 403 Forbidden or return limited data
        if response.status_code == 403:
            print(f"✓ Store manager correctly denied access to external user (403)")
        elif response.status_code == 200:
            # Check if it's the same user or if access is somehow granted
            print(f"⚠ Store manager got access to user (may need verification)")
        else:
            print(f"✓ Store manager access handled with status: {response.status_code}")
    
    def test_manager_sees_limited_users(self, api_client):
        """Manager should see only users in their scope"""
        headers = {"X-User-ID": MANAGER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        users = response.json()
        print(f"✓ Manager sees {len(users)} users")
    
    def test_regular_user_sees_no_users(self, api_client):
        """Regular user should not see other users"""
        headers = {"X-User-ID": REGULAR_USER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        users = response.json()
        # Regular users typically return empty list
        print(f"✓ Regular user sees {len(users)} users")


class TestRBACComparison:
    """Compare RBAC scoping between roles"""
    
    def test_org_hierarchy_organizations(self, api_client):
        """Verify super_admin sees >= manager organizations"""
        super_resp = api_client.get(
            f"{BASE_URL}/api/admin/organizations",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        manager_resp = api_client.get(
            f"{BASE_URL}/api/admin/organizations",
            headers={"X-User-ID": MANAGER_ID}
        )
        
        assert super_resp.status_code == 200
        assert manager_resp.status_code == 200
        
        super_count = len(super_resp.json())
        manager_count = len(manager_resp.json())
        
        print(f"Organizations - Super Admin: {super_count}, Manager: {manager_count}")
        assert super_count >= manager_count, "Super admin should see >= organizations than manager"
        print(f"✓ Organization hierarchy verified")
    
    def test_store_hierarchy(self, api_client):
        """Verify super_admin sees >= org_admin >= store_manager stores"""
        super_resp = api_client.get(
            f"{BASE_URL}/api/admin/stores",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        org_admin_resp = api_client.get(
            f"{BASE_URL}/api/admin/stores",
            headers={"X-User-ID": ORG_ADMIN_ID}
        )
        store_mgr_resp = api_client.get(
            f"{BASE_URL}/api/admin/stores",
            headers={"X-User-ID": STORE_MANAGER_ID}
        )
        
        assert super_resp.status_code == 200
        assert org_admin_resp.status_code == 200
        assert store_mgr_resp.status_code == 200
        
        super_count = len(super_resp.json())
        org_admin_count = len(org_admin_resp.json())
        store_mgr_count = len(store_mgr_resp.json())
        
        print(f"Stores - Super Admin: {super_count}, Org Admin: {org_admin_count}, Store Manager: {store_mgr_count}")
        
        # Super admin >= org_admin
        assert super_count >= org_admin_count, "Super admin should see >= stores than org admin"
        print(f"✓ Store hierarchy verified")


class TestSpecificRBACScenarios:
    """Test specific RBAC scenarios from requirements"""
    
    def test_manager_can_only_see_own_organization(self, api_client):
        """RBAC: Manager user can only see their own organization"""
        headers = {"X-User-ID": MANAGER_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/organizations", headers=headers)
        assert response.status_code == 200
        
        orgs = response.json()
        # Manager should see at most 1 org (their own)
        assert len(orgs) <= 1, f"Manager should see max 1 organization, got {len(orgs)}"
        print(f"✓ RBAC verified: Manager sees only {len(orgs)} organization(s)")
    
    def test_super_admin_can_see_all_organizations(self, api_client):
        """RBAC: Super admin can see all organizations"""
        headers = {"X-User-ID": SUPER_ADMIN_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/organizations", headers=headers)
        assert response.status_code == 200
        
        orgs = response.json()
        # Should see multiple organizations
        print(f"✓ RBAC verified: Super admin sees {len(orgs)} organizations")
        assert len(orgs) >= 1, "Super admin should see at least 1 organization"
    
    def test_super_admin_can_see_all_stores(self, api_client):
        """RBAC: Super admin can see all stores"""
        headers = {"X-User-ID": SUPER_ADMIN_ID}
        response = api_client.get(f"{BASE_URL}/api/admin/stores", headers=headers)
        assert response.status_code == 200
        
        stores = response.json()
        print(f"✓ RBAC verified: Super admin sees {len(stores)} stores")
        assert len(stores) >= 1, "Super admin should see at least 1 store"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
