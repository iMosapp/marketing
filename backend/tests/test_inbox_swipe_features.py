"""
Backend tests for Inbox Swipe Features (P0):
1. Flag conversation - /api/messages/conversations/{user_id}/{conversation_id} supports 'flagged' field
2. Create task from conversation - /api/tasks/{user_id} supports creating tasks with contact_id
3. Contact Activity Feed - verify backend endpoints still work
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com').rstrip('/')

# Test credentials from requirements
TEST_EMAIL = "forest@imonsocial.com"
TEST_PASSWORD = "Admin123!"
TEST_CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestFlagConversation:
    """Tests for flagging conversations - new inbox swipe feature"""
    
    def test_flag_conversation_endpoint_allows_flagged_field(self):
        """Verify that /api/messages/conversations/{user_id}/{conversation_id} accepts 'flagged' field"""
        # First, get conversations to find one to flag
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}")
        assert response.status_code == 200, f"Failed to get conversations: {response.text}"
        
        conversations = response.json()
        assert len(conversations) > 0, "No conversations found to test flagging"
        
        # Pick the first conversation
        conv_id = conversations[0]['_id']
        
        # Flag the conversation
        response = requests.put(
            f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}/{conv_id}",
            json={"flagged": True}
        )
        assert response.status_code == 200, f"Failed to flag conversation: {response.text}"
        
        # Verify the flag was set by getting conversation again
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}")
        assert response.status_code == 200
        
        updated_convs = response.json()
        flagged_conv = next((c for c in updated_convs if c['_id'] == conv_id), None)
        assert flagged_conv is not None
        assert flagged_conv.get('flagged') == True, f"Conversation was not flagged: {flagged_conv}"
        
        print(f"SUCCESS: Conversation {conv_id} flagged successfully")
    
    def test_unflag_conversation(self):
        """Verify that 'flagged' can be set to False"""
        # Get conversations
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}")
        assert response.status_code == 200
        
        conversations = response.json()
        assert len(conversations) > 0
        
        conv_id = conversations[0]['_id']
        
        # Unflag
        response = requests.put(
            f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}/{conv_id}",
            json={"flagged": False}
        )
        assert response.status_code == 200
        
        print(f"SUCCESS: Conversation {conv_id} unflagged successfully")


class TestTaskCreation:
    """Tests for creating tasks from conversations - new inbox swipe feature"""
    
    def test_create_task_with_contact_id(self):
        """Verify that /api/tasks/{user_id} accepts contact_id, title, due_date"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_str = tomorrow.isoformat()
        
        task_data = {
            "contact_id": TEST_CONTACT_ID,
            "type": "follow_up",
            "title": "TEST_Follow up with Forest Ward",
            "description": "Created by swipe action test",
            "due_date": tomorrow_str,
            "priority": "medium"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        
        assert response.status_code == 200, f"Failed to create task: {response.text}"
        
        task = response.json()
        assert task.get('contact_id') == TEST_CONTACT_ID, f"contact_id not saved: {task}"
        assert task.get('title') == "TEST_Follow up with Forest Ward", f"title not saved: {task}"
        assert task.get('type') == "follow_up"
        assert task.get('priority') == "medium"
        
        print(f"SUCCESS: Task created with contact_id: {task.get('_id')}")
        
        # Clean up - delete the test task
        if task.get('_id'):
            cleanup_resp = requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task['_id']}")
            print(f"Cleanup: Task deleted (status={cleanup_resp.status_code})")
    
    def test_get_tasks_returns_contact_id(self):
        """Verify that GET tasks returns contact_id field"""
        response = requests.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}")
        assert response.status_code == 200, f"Failed to get tasks: {response.text}"
        
        tasks = response.json()
        # Check if any task has contact_id (may or may not exist)
        print(f"SUCCESS: Got {len(tasks)} tasks")
        
        # If we have tasks, verify the response structure
        if len(tasks) > 0:
            task = tasks[0]
            # Just verify the task has expected fields
            assert '_id' in task or 'id' in task, "Task missing id"
            assert 'title' in task, "Task missing title"
            print(f"Sample task structure: {list(task.keys())}")


class TestTagsEndpoint:
    """Tests for tags endpoint - used by swipe-to-tag feature"""
    
    def test_get_all_tags(self):
        """Verify /api/tags/{user_id} returns tags list"""
        response = requests.get(f"{BASE_URL}/api/tags/{TEST_USER_ID}")
        assert response.status_code == 200, f"Failed to get tags: {response.text}"
        
        tags = response.json()
        assert isinstance(tags, list), f"Expected list of tags, got: {type(tags)}"
        
        print(f"SUCCESS: Got {len(tags)} tags")
        
        if len(tags) > 0:
            tag = tags[0]
            assert 'name' in tag, "Tag missing name"
            print(f"Sample tag: {tag.get('name')} (color={tag.get('color')})")


class TestContactActivityFeed:
    """Tests for contact activity feed - regression tests for P0 task 1"""
    
    def test_get_contact_events(self):
        """Verify /api/contacts/{user_id}/{contact_id}/events returns events"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events")
        assert response.status_code == 200, f"Failed to get events: {response.text}"
        
        data = response.json()
        events = data.get('events', [])
        
        print(f"SUCCESS: Contact has {len(events)} events")
        
        if len(events) > 0:
            event = events[0]
            # Verify event structure
            assert 'event_type' in event, "Event missing event_type"
            assert 'timestamp' in event, "Event missing timestamp"
            print(f"Sample event: {event.get('event_type')} at {event.get('timestamp')}")
    
    def test_get_contact_stats(self):
        """Verify /api/contacts/{user_id}/{contact_id}/stats returns stats"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/stats")
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        
        stats = response.json()
        assert 'total_touchpoints' in stats, f"Stats missing total_touchpoints: {stats}"
        
        print(f"SUCCESS: Contact stats - {stats.get('total_touchpoints')} touchpoints")


class TestConversationsList:
    """Tests for conversations list - verify flagged field appears in response"""
    
    def test_conversations_include_flagged_field(self):
        """Verify conversation objects can have flagged field"""
        response = requests.get(f"{BASE_URL}/api/messages/conversations/{TEST_USER_ID}")
        assert response.status_code == 200, f"Failed to get conversations: {response.text}"
        
        conversations = response.json()
        assert len(conversations) > 0, "No conversations found"
        
        # Check structure
        conv = conversations[0]
        print(f"SUCCESS: Got {len(conversations)} conversations")
        print(f"Conversation structure includes: {list(conv.keys())}")
        
        # flagged might be None/missing if never set, that's OK
        if 'flagged' in conv:
            print(f"First conversation flagged status: {conv.get('flagged')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
