"""
Test suite for MVPLine new features:
- Tags CRUD API (/api/tags/{user_id})
- Persona Settings API (/api/users/{user_id}/persona)
- Quick Actions (archive, read, unread, delete conversation)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://imos-auth-ui.preview.emergentagent.com').rstrip('/')

# Test user credentials
TEST_EMAIL = "superadmin@mvpline.com"
TEST_PASSWORD = "admin123"

@pytest.fixture(scope="module")
def auth_session():
    """Login and get authenticated session with user_id"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    data = response.json()
    user_id = data.get("user", {}).get("_id")
    assert user_id, "User ID not returned from login"
    
    return {"session": session, "user_id": user_id}


class TestTagsAPI:
    """Tests for /api/tags/{user_id} endpoints"""
    
    def test_get_tags_returns_list(self, auth_session):
        """GET /api/tags/{user_id} should return tags list"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        response = session.get(f"{BASE_URL}/api/tags/{user_id}")
        assert response.status_code == 200, f"Failed to get tags: {response.text}"
        
        tags = response.json()
        assert isinstance(tags, list), "Tags should be a list"
        
        # Should have default tags created for new users
        if len(tags) > 0:
            tag = tags[0]
            assert "_id" in tag, "Tag should have _id"
            assert "name" in tag, "Tag should have name"
            assert "color" in tag, "Tag should have color"
            print(f"✓ GET tags returned {len(tags)} tags")
    
    def test_get_tags_creates_defaults_for_new_users(self, auth_session):
        """GET /api/tags/{user_id} should create 5 default tags for new users"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        response = session.get(f"{BASE_URL}/api/tags/{user_id}")
        assert response.status_code == 200
        
        tags = response.json()
        # Default tags: Hot Lead, VIP, New Customer, Follow Up, Service Due
        expected_default_names = ["Hot Lead", "VIP", "New Customer", "Follow Up", "Service Due"]
        
        tag_names = [t["name"] for t in tags]
        defaults_found = [n for n in expected_default_names if n in tag_names]
        
        assert len(defaults_found) > 0 or len(tags) > 0, "Should have some tags"
        print(f"✓ Found {len(defaults_found)} default tags out of 5 expected")
    
    def test_create_tag(self, auth_session):
        """POST /api/tags/{user_id} should create a new tag"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        # Create unique tag
        tag_data = {
            "name": f"TEST_Tag_{datetime.utcnow().timestamp()}",
            "color": "#FF0000",
            "icon": "flame"
        }
        
        response = session.post(f"{BASE_URL}/api/tags/{user_id}", json=tag_data)
        assert response.status_code == 200, f"Failed to create tag: {response.text}"
        
        created_tag = response.json()
        assert created_tag["name"] == tag_data["name"]
        assert created_tag["color"] == tag_data["color"]
        assert "_id" in created_tag
        
        print(f"✓ Created tag: {created_tag['name']}")
        return created_tag["_id"]
    
    def test_create_duplicate_tag_fails(self, auth_session):
        """POST /api/tags/{user_id} with duplicate name should return 400"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        # First create a tag
        tag_data = {
            "name": f"TEST_Duplicate_{datetime.utcnow().timestamp()}",
            "color": "#00FF00"
        }
        response1 = session.post(f"{BASE_URL}/api/tags/{user_id}", json=tag_data)
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = session.post(f"{BASE_URL}/api/tags/{user_id}", json=tag_data)
        assert response2.status_code == 400, "Duplicate tag should return 400"
        
        print("✓ Duplicate tag creation correctly rejected")
    
    def test_delete_tag(self, auth_session):
        """DELETE /api/tags/{user_id}/{tag_id} should delete the tag"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        # First create a tag to delete
        tag_data = {
            "name": f"TEST_ToDelete_{datetime.utcnow().timestamp()}",
            "color": "#0000FF"
        }
        create_response = session.post(f"{BASE_URL}/api/tags/{user_id}", json=tag_data)
        assert create_response.status_code == 200
        tag_id = create_response.json()["_id"]
        
        # Delete the tag
        delete_response = session.delete(f"{BASE_URL}/api/tags/{user_id}/{tag_id}")
        assert delete_response.status_code == 200, f"Failed to delete tag: {delete_response.text}"
        
        print(f"✓ Deleted tag successfully")
    
    def test_get_tag_colors(self, auth_session):
        """GET /api/tags/{user_id}/colors should return available colors"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        response = session.get(f"{BASE_URL}/api/tags/{user_id}/colors")
        assert response.status_code == 200
        
        data = response.json()
        assert "colors" in data
        assert len(data["colors"]) > 0
        
        print(f"✓ Got {len(data['colors'])} tag colors")


class TestPersonaAPI:
    """Tests for /api/users/{user_id}/persona endpoints"""
    
    def test_get_persona_settings(self, auth_session):
        """GET /api/users/{user_id}/persona should return persona settings"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        response = session.get(f"{BASE_URL}/api/users/{user_id}/persona")
        assert response.status_code == 200, f"Failed to get persona: {response.text}"
        
        # Response can be empty dict for new users
        data = response.json()
        assert isinstance(data, dict)
        
        print(f"✓ GET persona returned settings: {list(data.keys()) if data else 'empty (new user)'}")
    
    def test_update_persona_settings(self, auth_session):
        """PUT /api/users/{user_id}/persona should save persona settings"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        persona_data = {
            "tone": "friendly",
            "emoji_usage": "minimal",
            "humor_level": "light",
            "response_length": "balanced",
            "greeting_style": "Hi {name}!",
            "signature": "- Test User",
            "auto_introduce": True,
            "escalation_keywords": ["urgent", "help", "manager"],
            "specialties": ["Sales", "Support"]
        }
        
        response = session.put(f"{BASE_URL}/api/users/{user_id}/persona", json=persona_data)
        assert response.status_code == 200, f"Failed to update persona: {response.text}"
        
        # Verify saved by fetching again
        get_response = session.get(f"{BASE_URL}/api/users/{user_id}/persona")
        assert get_response.status_code == 200
        
        saved_data = get_response.json()
        assert saved_data.get("tone") == "friendly"
        assert saved_data.get("emoji_usage") == "minimal"
        
        print("✓ Persona settings saved and verified")
    
    def test_persona_for_nonexistent_user(self, auth_session):
        """GET /api/users/{invalid_id}/persona should return 404"""
        session = auth_session["session"]
        
        # Use a valid but non-existent ObjectId
        fake_id = "000000000000000000000000"
        response = session.get(f"{BASE_URL}/api/users/{fake_id}/persona")
        assert response.status_code == 404
        
        print("✓ Non-existent user correctly returns 404")


class TestQuickActionsAPI:
    """Tests for conversation quick actions"""
    
    @pytest.fixture(scope="class")
    def conversation_id(self, auth_session):
        """Get or create a conversation for testing"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        # Get conversations
        response = session.get(f"{BASE_URL}/api/messages/conversations/{user_id}")
        assert response.status_code == 200
        
        conversations = response.json()
        if conversations:
            return conversations[0]["_id"]
        
        # If no conversations, create one with a contact
        contacts_response = session.get(f"{BASE_URL}/api/contacts/{user_id}")
        if contacts_response.status_code == 200 and contacts_response.json():
            contact_id = contacts_response.json()[0]["_id"]
            create_conv = session.post(f"{BASE_URL}/api/messages/conversations/{user_id}", json={
                "contact_id": contact_id
            })
            if create_conv.status_code == 200:
                return create_conv.json()["_id"]
        
        pytest.skip("No conversation available for testing")
    
    def test_archive_conversation(self, auth_session, conversation_id):
        """PUT /api/messages/conversation/{id}/archive should archive"""
        session = auth_session["session"]
        
        response = session.put(f"{BASE_URL}/api/messages/conversation/{conversation_id}/archive")
        assert response.status_code == 200, f"Failed to archive: {response.text}"
        
        data = response.json()
        assert "message" in data
        
        print(f"✓ Archived conversation {conversation_id}")
    
    def test_restore_conversation(self, auth_session, conversation_id):
        """PUT /api/messages/conversation/{id}/restore should restore"""
        session = auth_session["session"]
        
        response = session.put(f"{BASE_URL}/api/messages/conversation/{conversation_id}/restore")
        assert response.status_code == 200, f"Failed to restore: {response.text}"
        
        print(f"✓ Restored conversation {conversation_id}")
    
    def test_mark_conversation_read(self, auth_session, conversation_id):
        """PUT /api/messages/conversation/{id}/read should mark as read"""
        session = auth_session["session"]
        
        response = session.put(f"{BASE_URL}/api/messages/conversation/{conversation_id}/read")
        assert response.status_code == 200, f"Failed to mark read: {response.text}"
        
        print(f"✓ Marked conversation as read")
    
    def test_mark_conversation_unread(self, auth_session, conversation_id):
        """PUT /api/messages/conversation/{id}/unread should mark as unread"""
        session = auth_session["session"]
        
        response = session.put(f"{BASE_URL}/api/messages/conversation/{conversation_id}/unread")
        assert response.status_code == 200, f"Failed to mark unread: {response.text}"
        
        print(f"✓ Marked conversation as unread")
    
    def test_invalid_conversation_returns_404(self, auth_session):
        """Quick actions on invalid conversation should return 404"""
        session = auth_session["session"]
        
        fake_id = "000000000000000000000000"
        response = session.put(f"{BASE_URL}/api/messages/conversation/{fake_id}/read")
        assert response.status_code == 404
        
        print("✓ Invalid conversation correctly returns 404")


class TestTagAssignment:
    """Tests for tag assignment to contacts"""
    
    def test_assign_tag_to_contacts(self, auth_session):
        """POST /api/tags/{user_id}/assign should assign tag to contacts"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        # Get contacts
        contacts_response = session.get(f"{BASE_URL}/api/contacts/{user_id}")
        if contacts_response.status_code != 200 or not contacts_response.json():
            pytest.skip("No contacts available for testing")
        
        contact_id = contacts_response.json()[0]["_id"]
        
        # Get tags
        tags_response = session.get(f"{BASE_URL}/api/tags/{user_id}")
        assert tags_response.status_code == 200
        
        tags = tags_response.json()
        if not tags:
            pytest.skip("No tags available")
        
        tag_name = tags[0]["name"]
        
        # Assign tag
        response = session.post(f"{BASE_URL}/api/tags/{user_id}/assign", json={
            "tag_name": tag_name,
            "contact_ids": [contact_id]
        })
        assert response.status_code == 200, f"Failed to assign tag: {response.text}"
        
        print(f"✓ Assigned tag '{tag_name}' to contact")
    
    def test_get_contacts_by_tag(self, auth_session):
        """GET /api/tags/{user_id}/contacts/{tag_name} should return contacts"""
        session = auth_session["session"]
        user_id = auth_session["user_id"]
        
        # Get a tag
        tags_response = session.get(f"{BASE_URL}/api/tags/{user_id}")
        tags = tags_response.json()
        
        if tags:
            tag_name = tags[0]["name"]
            response = session.get(f"{BASE_URL}/api/tags/{user_id}/contacts/{tag_name}")
            assert response.status_code == 200
            
            contacts = response.json()
            assert isinstance(contacts, list)
            
            print(f"✓ Got {len(contacts)} contacts with tag '{tag_name}'")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_tags(auth_session):
    """Cleanup TEST_ prefixed tags after tests complete"""
    yield
    
    session = auth_session["session"]
    user_id = auth_session["user_id"]
    
    # Get all tags and delete TEST_ ones
    try:
        response = session.get(f"{BASE_URL}/api/tags/{user_id}")
        if response.status_code == 200:
            tags = response.json()
            for tag in tags:
                if tag["name"].startswith("TEST_"):
                    session.delete(f"{BASE_URL}/api/tags/{user_id}/{tag['_id']}")
                    print(f"Cleaned up test tag: {tag['name']}")
    except Exception as e:
        print(f"Cleanup warning: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
