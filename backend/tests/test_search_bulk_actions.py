"""
Search and Bulk Actions API Tests
Testing: Global Search and Inbox Bulk Selection features for MVPLine

Features tested:
- Global Search API: /api/search/{user_id}?q=query
- Search filters by type (contacts, conversations, campaigns)
- Bulk action endpoints: archive, read, unread, delete
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://imos-admin.preview.emergentagent.com')
BASE_URL = BASE_URL.rstrip('/')

# Test credentials
USER_ID = "69963e636d8473ba25695a34"
TEST_EMAIL = "superadmin@mvpline.com"
TEST_PASSWORD = "admin123"


class TestSearchAPI:
    """Global Search endpoint tests"""
    
    def test_search_api_basic(self):
        """Test basic search returns results structure"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={"q": "test"})
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "query" in data, "Response missing 'query' field"
        assert "contacts" in data, "Response missing 'contacts' field"
        assert "conversations" in data, "Response missing 'conversations' field"
        assert "campaigns" in data, "Response missing 'campaigns' field"
        assert "total_count" in data, "Response missing 'total_count' field"
        print(f"PASS: Basic search returned {data['total_count']} total results")
    
    def test_search_contacts_filter(self):
        """Test search with contacts-only filter"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "Alice",
            "types": "contacts"
        })
        assert response.status_code == 200, f"Filtered search failed: {response.text}"
        
        data = response.json()
        # When filtering by contacts, conversations and campaigns should be empty
        assert isinstance(data["contacts"], list), "Contacts should be a list"
        print(f"PASS: Contacts filter returned {len(data['contacts'])} contacts")
    
    def test_search_conversations_filter(self):
        """Test search with conversations-only filter"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "a",  # Generic search term
            "types": "conversations"
        })
        assert response.status_code == 200, f"Conversations search failed: {response.text}"
        
        data = response.json()
        assert isinstance(data["conversations"], list), "Conversations should be a list"
        print(f"PASS: Conversations filter returned {len(data['conversations'])} conversations")
    
    def test_search_campaigns_filter(self):
        """Test search with campaigns-only filter"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "campaign",
            "types": "campaigns"
        })
        assert response.status_code == 200, f"Campaigns search failed: {response.text}"
        
        data = response.json()
        assert isinstance(data["campaigns"], list), "Campaigns should be a list"
        print(f"PASS: Campaigns filter returned {len(data['campaigns'])} campaigns")
    
    def test_search_all_types(self):
        """Test search returns all types by default"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "a"  # Generic search term to get results
        })
        assert response.status_code == 200, f"All types search failed: {response.text}"
        
        data = response.json()
        total = len(data["contacts"]) + len(data["conversations"]) + len(data["campaigns"])
        assert data["total_count"] == total, f"Total count mismatch: {data['total_count']} vs {total}"
        print(f"PASS: All types search returned {total} total (contacts: {len(data['contacts'])}, conversations: {len(data['conversations'])}, campaigns: {len(data['campaigns'])})")
    
    def test_search_limit_parameter(self):
        """Test search respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "a",
            "limit": 5
        })
        assert response.status_code == 200, f"Limited search failed: {response.text}"
        
        data = response.json()
        # Each type should respect the limit
        assert len(data["contacts"]) <= 5, f"Contacts exceeded limit: {len(data['contacts'])}"
        assert len(data["conversations"]) <= 5, f"Conversations exceeded limit: {len(data['conversations'])}"
        assert len(data["campaigns"]) <= 5, f"Campaigns exceeded limit: {len(data['campaigns'])}"
        print(f"PASS: Limit parameter respected")
    
    def test_search_empty_query_error(self):
        """Test search fails with empty query"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": ""
        })
        # Should return 422 validation error
        assert response.status_code == 422, f"Expected 422 for empty query, got {response.status_code}"
        print(f"PASS: Empty query correctly returns 422 validation error")
    
    def test_search_result_structure(self):
        """Test search result items have correct structure"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "a"  
        })
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        
        # Check contact result structure if any
        if data["contacts"]:
            contact = data["contacts"][0]
            assert "id" in contact, "Contact missing 'id'"
            assert "type" in contact and contact["type"] == "contact", "Contact missing/wrong 'type'"
            assert "title" in contact, "Contact missing 'title'"
            assert "subtitle" in contact, "Contact missing 'subtitle'"
            assert "icon" in contact, "Contact missing 'icon'"
            assert "color" in contact, "Contact missing 'color'"
            print(f"PASS: Contact result structure is valid")
        
        # Check conversation result structure if any
        if data["conversations"]:
            conv = data["conversations"][0]
            assert "id" in conv, "Conversation missing 'id'"
            assert "type" in conv and conv["type"] == "conversation", "Conversation missing/wrong 'type'"
            assert "title" in conv, "Conversation missing 'title'"
            assert "subtitle" in conv, "Conversation missing 'subtitle'"
            print(f"PASS: Conversation result structure is valid")
        
        print(f"PASS: Result structures verified")


class TestSearchSuggestions:
    """Search suggestions endpoint tests"""
    
    def test_suggestions_basic(self):
        """Test search suggestions endpoint"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}/suggestions", params={
            "q": "A"
        })
        assert response.status_code == 200, f"Suggestions failed: {response.text}"
        
        data = response.json()
        assert "suggestions" in data, "Response missing 'suggestions'"
        assert isinstance(data["suggestions"], list), "Suggestions should be a list"
        print(f"PASS: Suggestions returned {len(data['suggestions'])} items")
    
    def test_suggestions_limit(self):
        """Test suggestions respects limit"""
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}/suggestions", params={
            "q": "a",
            "limit": 3
        })
        assert response.status_code == 200, f"Suggestions failed: {response.text}"
        
        data = response.json()
        assert len(data["suggestions"]) <= 3, f"Suggestions exceeded limit: {len(data['suggestions'])}"
        print(f"PASS: Suggestions limit respected")


class TestBulkArchive:
    """Bulk archive endpoint tests"""
    
    @pytest.fixture
    def test_conversation_ids(self):
        """Get conversation IDs to test with"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        if response.status_code != 200:
            pytest.skip("Cannot load conversations for bulk testing")
        
        conversations = response.json()
        if len(conversations) < 2:
            pytest.skip("Not enough conversations for bulk testing")
        
        return [c["_id"] for c in conversations[:2]]
    
    def test_bulk_archive_success(self, test_conversation_ids):
        """Test bulk archive endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/archive",
            json={"conversation_ids": test_conversation_ids}
        )
        assert response.status_code == 200, f"Bulk archive failed: {response.text}"
        
        data = response.json()
        assert "modified_count" in data, "Response missing 'modified_count'"
        print(f"PASS: Bulk archive modified {data['modified_count']} conversations")
        
        # Restore them back for other tests
        requests.post(
            f"{BASE_URL}/api/messages/bulk/restore",
            json={"conversation_ids": test_conversation_ids}
        )
    
    def test_bulk_archive_empty_ids(self):
        """Test bulk archive fails with empty list"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/archive",
            json={"conversation_ids": []}
        )
        assert response.status_code == 400, f"Expected 400 for empty IDs, got {response.status_code}"
        print(f"PASS: Empty IDs correctly returns 400 error")


class TestBulkRestore:
    """Bulk restore endpoint tests"""
    
    @pytest.fixture
    def archived_conversation_ids(self):
        """Create archived conversations for testing"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        if response.status_code != 200:
            pytest.skip("Cannot load conversations for bulk testing")
        
        conversations = response.json()
        if len(conversations) < 2:
            pytest.skip("Not enough conversations for bulk testing")
        
        ids = [c["_id"] for c in conversations[:2]]
        
        # Archive them first
        requests.post(
            f"{BASE_URL}/api/messages/bulk/archive",
            json={"conversation_ids": ids}
        )
        
        return ids
    
    def test_bulk_restore_success(self, archived_conversation_ids):
        """Test bulk restore endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/restore",
            json={"conversation_ids": archived_conversation_ids}
        )
        assert response.status_code == 200, f"Bulk restore failed: {response.text}"
        
        data = response.json()
        assert "modified_count" in data, "Response missing 'modified_count'"
        print(f"PASS: Bulk restore modified {data['modified_count']} conversations")


class TestBulkRead:
    """Bulk mark as read endpoint tests"""
    
    @pytest.fixture
    def test_conversation_ids(self):
        """Get conversation IDs to test with"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        if response.status_code != 200:
            pytest.skip("Cannot load conversations for bulk testing")
        
        conversations = response.json()
        if len(conversations) < 2:
            pytest.skip("Not enough conversations for bulk testing")
        
        return [c["_id"] for c in conversations[:2]]
    
    def test_bulk_read_success(self, test_conversation_ids):
        """Test bulk mark as read endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/read",
            json={"conversation_ids": test_conversation_ids}
        )
        assert response.status_code == 200, f"Bulk read failed: {response.text}"
        
        data = response.json()
        assert "modified_count" in data, "Response missing 'modified_count'"
        print(f"PASS: Bulk mark read modified {data['modified_count']} conversations")
    
    def test_bulk_read_empty_ids(self):
        """Test bulk read fails with empty list"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/read",
            json={"conversation_ids": []}
        )
        assert response.status_code == 400, f"Expected 400 for empty IDs, got {response.status_code}"
        print(f"PASS: Empty IDs correctly returns 400 error")


class TestBulkUnread:
    """Bulk mark as unread endpoint tests"""
    
    @pytest.fixture
    def test_conversation_ids(self):
        """Get conversation IDs to test with"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{USER_ID}")
        if response.status_code != 200:
            pytest.skip("Cannot load conversations for bulk testing")
        
        conversations = response.json()
        if len(conversations) < 2:
            pytest.skip("Not enough conversations for bulk testing")
        
        return [c["_id"] for c in conversations[:2]]
    
    def test_bulk_unread_success(self, test_conversation_ids):
        """Test bulk mark as unread endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/unread",
            json={"conversation_ids": test_conversation_ids}
        )
        assert response.status_code == 200, f"Bulk unread failed: {response.text}"
        
        data = response.json()
        assert "modified_count" in data, "Response missing 'modified_count'"
        print(f"PASS: Bulk mark unread modified {data['modified_count']} conversations")


class TestBulkDelete:
    """Bulk delete endpoint tests - Non-destructive with verification"""
    
    def test_bulk_delete_empty_ids(self):
        """Test bulk delete fails with empty list"""
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/delete",
            json={"conversation_ids": []}
        )
        assert response.status_code == 400, f"Expected 400 for empty IDs, got {response.status_code}"
        print(f"PASS: Empty IDs correctly returns 400 error")
    
    def test_bulk_delete_invalid_ids(self):
        """Test bulk delete with invalid IDs doesn't error out"""
        # Use fake IDs that don't exist
        fake_ids = ["000000000000000000000001", "000000000000000000000002"]
        response = requests.post(
            f"{BASE_URL}/api/messages/bulk/delete",
            json={"conversation_ids": fake_ids}
        )
        assert response.status_code == 200, f"Bulk delete failed: {response.text}"
        
        data = response.json()
        assert "deleted_count" in data, "Response missing 'deleted_count'"
        assert data["deleted_count"] == 0, f"Should delete 0 with fake IDs, got {data['deleted_count']}"
        print(f"PASS: Bulk delete with invalid IDs returns 0 deleted")


class TestEndToEndSearchFlow:
    """End-to-end search flow tests"""
    
    def test_search_then_navigate_contact(self):
        """Test searching for a contact returns navigable result"""
        # Search for contacts
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "a",
            "types": "contacts",
            "limit": 1
        })
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        if not data["contacts"]:
            pytest.skip("No contacts found to verify")
        
        contact = data["contacts"][0]
        contact_id = contact["id"]
        
        # Verify we can get this contact directly
        contact_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/{contact_id}")
        assert contact_response.status_code == 200, f"Cannot fetch contact: {contact_response.text}"
        
        print(f"PASS: Search contact '{contact['title']}' is navigable")
    
    def test_search_then_navigate_conversation(self):
        """Test searching for a conversation returns navigable result"""
        # Search for conversations
        response = requests.get(f"{BASE_URL}/api/search/{USER_ID}", params={
            "q": "a",
            "types": "conversations",
            "limit": 1
        })
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        if not data["conversations"]:
            pytest.skip("No conversations found to verify")
        
        conv = data["conversations"][0]
        conv_id = conv["id"]
        
        # Verify we can get this conversation's thread
        thread_response = requests.get(f"{BASE_URL}/api/messages/thread/{conv_id}")
        assert thread_response.status_code == 200, f"Cannot fetch thread: {thread_response.text}"
        
        print(f"PASS: Search conversation '{conv['title']}' is navigable")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
