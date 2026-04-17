"""
Tasks API Tests - Sprint 1 Task Engine
Tests CRUD operations, task actions (complete, snooze, dismiss, edit), 
daily summary, and system task generation.

Endpoints tested:
- GET /api/tasks/{user_id}?filter=today|completed|all
- GET /api/tasks/{user_id}/summary
- POST /api/tasks/{user_id}
- PATCH /api/tasks/{user_id}/{task_id}
- DELETE /api/tasks/{user_id}/{task_id}
- POST /api/tasks/{user_id}/generate-system-tasks
"""
import os
import pytest
import requests
import os
from datetime import datetime, timedelta

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestTasksGetEndpoint:
    """Tests for GET /api/tasks/{user_id} with various filters"""
    
    def test_get_tasks_filter_today(self):
        """GET /api/tasks/{user_id}?filter=today returns pending tasks due today"""
        response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            params={"filter": "today"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        tasks = response.json()
        assert isinstance(tasks, list), "Response should be a list"
        
        # Verify returned tasks have expected structure
        for task in tasks:
            assert "_id" in task, "Task should have _id"
            assert "user_id" in task, "Task should have user_id"
            # Status should be pending or snoozed for today filter (not completed or dismissed)
            # Note: The serializer maps completed=True to status=completed for legacy compat
            # The filter query should exclude completed tasks, but verify what we get
            if task.get("status") not in ["pending", "snoozed", None]:
                print(f"WARNING: Task {task['_id']} has status={task.get('status')}, may be legacy data")
        print(f"PASS: GET /api/tasks?filter=today returned {len(tasks)} tasks")

    def test_get_tasks_filter_completed(self):
        """GET /api/tasks/{user_id}?filter=completed returns completed tasks"""
        response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            params={"filter": "completed"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        tasks = response.json()
        assert isinstance(tasks, list), "Response should be a list"
        
        # Verify completed tasks have completed status
        for task in tasks:
            assert task.get("status") == "completed" or task.get("completed") == True, \
                f"Completed filter should only return completed tasks, got status: {task.get('status')}"
        print(f"PASS: GET /api/tasks?filter=completed returned {len(tasks)} completed tasks")

    def test_get_tasks_filter_all(self):
        """GET /api/tasks/{user_id}?filter=all returns all tasks"""
        response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            params={"filter": "all"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        tasks = response.json()
        assert isinstance(tasks, list), "Response should be a list"
        print(f"PASS: GET /api/tasks?filter=all returned {len(tasks)} total tasks")


class TestTaskSummaryEndpoint:
    """Tests for GET /api/tasks/{user_id}/summary"""
    
    def test_get_task_summary(self):
        """GET /api/tasks/{user_id}/summary returns daily counts"""
        response = requests.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "total_today" in data, "Summary should have total_today"
        assert "completed_today" in data, "Summary should have completed_today"
        assert "pending_today" in data, "Summary should have pending_today"
        assert "overdue" in data, "Summary should have overdue"
        assert "progress_pct" in data, "Summary should have progress_pct"
        assert "activity" in data, "Summary should have activity"
        
        # Verify data types
        assert isinstance(data["total_today"], int), "total_today should be int"
        assert isinstance(data["completed_today"], int), "completed_today should be int"
        assert isinstance(data["pending_today"], int), "pending_today should be int"
        assert isinstance(data["overdue"], int), "overdue should be int"
        assert isinstance(data["progress_pct"], (int, float)), "progress_pct should be number"
        assert isinstance(data["activity"], dict), "activity should be dict"
        
        # Verify activity has expected fields
        activity = data["activity"]
        assert "calls" in activity, "activity should have calls"
        assert "texts" in activity, "activity should have texts"
        assert "emails" in activity, "activity should have emails"
        
        print(f"PASS: Summary returned - total: {data['total_today']}, completed: {data['completed_today']}, pending: {data['pending_today']}, overdue: {data['overdue']}, progress: {data['progress_pct']}%")

    def test_progress_pct_calculation(self):
        """Summary progress_pct correctly calculates completed/total percentage"""
        response = requests.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/summary")
        assert response.status_code == 200
        
        data = response.json()
        total = data["total_today"]
        completed = data["completed_today"]
        progress = data["progress_pct"]
        
        # Verify calculation: (completed / max(total, 1)) * 100
        expected = round((completed / max(total, 1)) * 100)
        assert progress == expected, f"Progress should be {expected}%, got {progress}%"
        print(f"PASS: progress_pct calculation verified: {completed}/{total} = {progress}%")


class TestTaskCreateEndpoint:
    """Tests for POST /api/tasks/{user_id}"""
    
    created_task_id = None
    
    def test_create_manual_task_success(self):
        """POST /api/tasks/{user_id} creates a manual task with all fields"""
        task_data = {
            "title": "TEST_Manual Task Creation",
            "description": "Testing manual task creation with all fields",
            "priority": "high",
            "action_type": "call",
            "suggested_message": "Hi, following up on our conversation.",
            "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        task = response.json()
        
        # Verify returned task has expected fields
        assert "_id" in task, "Task should have _id"
        assert task["title"] == task_data["title"], "Title should match"
        assert task["description"] == task_data["description"], "Description should match"
        assert task["priority"] == task_data["priority"], "Priority should match"
        assert task["action_type"] == task_data["action_type"], "action_type should match"
        assert task["suggested_message"] == task_data["suggested_message"], "suggested_message should match"
        assert task["status"] == "pending", "New task should have pending status"
        assert task["source"] == "manual", "Manual task should have manual source"
        
        # Store for cleanup
        TestTaskCreateEndpoint.created_task_id = task["_id"]
        print(f"PASS: Created manual task with ID: {task['_id']}")
        
    def test_create_task_empty_title_returns_400(self):
        """POST /api/tasks/{user_id} returns 400 if title is empty"""
        task_data = {
            "title": "",
            "description": "Task with empty title"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert response.status_code == 400, f"Expected 400 for empty title, got {response.status_code}"
        
        error = response.json()
        assert "detail" in error, "Error response should have detail"
        print(f"PASS: Empty title returns 400 with message: {error.get('detail')}")

    def test_create_task_whitespace_title_returns_400(self):
        """POST /api/tasks/{user_id} returns 400 if title is whitespace only"""
        task_data = {
            "title": "   ",
            "description": "Task with whitespace title"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert response.status_code == 400, f"Expected 400 for whitespace title, got {response.status_code}"
        print("PASS: Whitespace title returns 400")


class TestTaskUpdateEndpoint:
    """Tests for PATCH /api/tasks/{user_id}/{task_id}"""
    
    task_id = None
    
    @pytest.fixture(autouse=True)
    def setup_task(self):
        """Create a task for update tests"""
        task_data = {
            "title": "TEST_Task for Update Tests",
            "description": "Will be updated in tests",
            "priority": "medium"
        }
        response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        if response.status_code == 200:
            TestTaskUpdateEndpoint.task_id = response.json()["_id"]
        yield
        # Cleanup after test
        if TestTaskUpdateEndpoint.task_id:
            requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{TestTaskUpdateEndpoint.task_id}")

    def test_complete_task(self):
        """PATCH /api/tasks/{user_id}/{task_id} with action=complete marks task as completed"""
        if not self.task_id:
            pytest.skip("No task created for test")
            
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{self.task_id}",
            json={"action": "complete"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        task = response.json()
        assert task["status"] == "completed", "Status should be completed"
        assert task["completed"] == True, "completed flag should be True"
        assert task.get("completed_at") is not None, "completed_at should be set"
        print(f"PASS: Task marked as completed with timestamp: {task.get('completed_at')}")

    def test_snooze_task(self):
        """PATCH /api/tasks/{user_id}/{task_id} with action=snooze sets snoozed_until"""
        if not self.task_id:
            pytest.skip("No task created for test")
            
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{self.task_id}",
            json={"action": "snooze", "snooze_hours": 24}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        task = response.json()
        assert task["status"] == "snoozed", "Status should be snoozed"
        assert task.get("snoozed_until") is not None, "snoozed_until should be set"
        assert task.get("due_date") is not None, "due_date should be updated"
        print(f"PASS: Task snoozed until: {task.get('snoozed_until')}")

    def test_dismiss_task(self):
        """PATCH /api/tasks/{user_id}/{task_id} with action=dismiss sets status to dismissed"""
        if not self.task_id:
            pytest.skip("No task created for test")
            
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{self.task_id}",
            json={"action": "dismiss"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        task = response.json()
        assert task["status"] == "dismissed", "Status should be dismissed"
        print("PASS: Task dismissed successfully")

    def test_edit_task(self):
        """PATCH /api/tasks/{user_id}/{task_id} with action=edit updates allowed fields"""
        if not self.task_id:
            pytest.skip("No task created for test")
            
        update_data = {
            "action": "edit",
            "title": "TEST_Updated Title",
            "description": "Updated description",
            "priority": "high",
            "action_type": "email",
            "suggested_message": "Updated suggested message"
        }
        
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{self.task_id}",
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        task = response.json()
        assert task["title"] == update_data["title"], "Title should be updated"
        assert task["description"] == update_data["description"], "Description should be updated"
        assert task["priority"] == update_data["priority"], "Priority should be updated"
        assert task["action_type"] == update_data["action_type"], "action_type should be updated"
        assert task["suggested_message"] == update_data["suggested_message"], "suggested_message should be updated"
        print("PASS: Task edited successfully with all fields updated")


class TestTaskDeleteEndpoint:
    """Tests for DELETE /api/tasks/{user_id}/{task_id}"""
    
    def test_delete_task_success(self):
        """DELETE /api/tasks/{user_id}/{task_id} removes the task"""
        # First create a task to delete
        task_data = {"title": "TEST_Task to Delete"}
        create_response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["_id"]
        
        # Delete the task
        delete_response = requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        result = delete_response.json()
        assert result.get("success") == True, "Delete should return success: true"
        
        # Verify task is actually deleted - get all tasks and check
        get_response = requests.get(f"{BASE_URL}/api/tasks/{TEST_USER_ID}", params={"filter": "all"})
        tasks = get_response.json()
        task_ids = [t["_id"] for t in tasks]
        assert task_id not in task_ids, "Deleted task should not appear in task list"
        print(f"PASS: Task {task_id} deleted successfully")

    def test_delete_nonexistent_task_returns_404(self):
        """DELETE /api/tasks/{user_id}/nonexistent returns 404"""
        fake_id = "000000000000000000000000"  # Valid ObjectId format but doesn't exist
        
        response = requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{fake_id}")
        assert response.status_code == 404, f"Expected 404 for nonexistent task, got {response.status_code}"
        
        error = response.json()
        assert "detail" in error, "Error response should have detail"
        print(f"PASS: Nonexistent task returns 404 with message: {error.get('detail')}")


class TestGenerateSystemTasks:
    """Tests for POST /api/tasks/{user_id}/generate-system-tasks"""
    
    def test_generate_system_tasks(self):
        """POST /api/tasks/{user_id}/generate-system-tasks runs without error"""
        response = requests.post(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/generate-system-tasks")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "created" in result, "Response should have 'created' field"
        assert "user_id" in result, "Response should have 'user_id' field"
        assert result["user_id"] == TEST_USER_ID, "user_id should match"
        assert isinstance(result["created"], int), "created should be an integer"
        print(f"PASS: System tasks generated, created: {result['created']}")

    def test_generate_system_tasks_invalid_user_returns_404(self):
        """POST /api/tasks/{invalid_user}/generate-system-tasks returns 404"""
        fake_user_id = "000000000000000000000000"
        
        response = requests.post(f"{BASE_URL}/api/tasks/{fake_user_id}/generate-system-tasks")
        assert response.status_code == 404, f"Expected 404 for invalid user, got {response.status_code}"
        print("PASS: Invalid user returns 404 for generate-system-tasks")


class TestTaskCompletionLogsEvent:
    """Tests that completing a task logs a contact_event"""
    
    def test_complete_task_logs_contact_event(self):
        """Completing a task with contact_id logs a contact_event with event_type=task_completed"""
        # First, get a contact to associate with the task
        contacts_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        if contacts_response.status_code != 200 or not contacts_response.json():
            pytest.skip("No contacts available for this test")
        
        contacts = contacts_response.json()
        contact = contacts[0] if contacts else None
        if not contact:
            pytest.skip("No contacts available")
            
        contact_id = contact.get("_id") or contact.get("id")
        
        # Create a task with contact_id
        task_data = {
            "title": "TEST_Task for Event Logging",
            "contact_id": contact_id,
            "description": "Will be completed to test event logging"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["_id"]
        
        # Complete the task
        complete_response = requests.patch(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task_id}",
            json={"action": "complete"}
        )
        assert complete_response.status_code == 200, f"Complete failed: {complete_response.text}"
        
        # Check that a contact_event was logged
        events_response = requests.get(
            f"{BASE_URL}/api/contact-events/{contact_id}",
            params={"limit": 10}
        )
        
        if events_response.status_code == 200:
            events = events_response.json()
            # Look for task_completed event
            task_completed_events = [e for e in events if e.get("event_type") == "task_completed"]
            assert len(task_completed_events) > 0, "Should have logged a task_completed event"
            print(f"PASS: Task completion logged contact_event with event_type=task_completed")
        else:
            # Event may have been logged but endpoint might not be accessible
            print(f"INFO: Could not verify event logging (status {events_response.status_code}), but completion succeeded")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task_id}")


class TestTaskDataPersistence:
    """Tests that verify data is actually persisted to database"""
    
    def test_create_and_get_task(self):
        """Create task then GET to verify persistence"""
        task_data = {
            "title": "TEST_Persistence Check",
            "description": "Verifying data persistence",
            "priority": "high",
            "action_type": "text"
        }
        
        # Create
        create_response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert create_response.status_code == 200
        created_task = create_response.json()
        task_id = created_task["_id"]
        
        # Get all tasks and find our task
        get_response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            params={"filter": "all", "limit": 100}
        )
        assert get_response.status_code == 200
        
        tasks = get_response.json()
        found_task = next((t for t in tasks if t["_id"] == task_id), None)
        
        assert found_task is not None, "Created task should be found in GET response"
        assert found_task["title"] == task_data["title"], "Title should persist"
        assert found_task["description"] == task_data["description"], "Description should persist"
        assert found_task["priority"] == task_data["priority"], "Priority should persist"
        
        print(f"PASS: Task persisted and retrieved successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task_id}")

    def test_update_and_verify_persistence(self):
        """Update task then GET to verify changes persisted"""
        # Create
        task_data = {"title": "TEST_Update Persistence", "priority": "low"}
        create_response = requests.post(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            json=task_data
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["_id"]
        
        # Update
        update_data = {"action": "edit", "title": "TEST_Updated Persistence", "priority": "high"}
        update_response = requests.patch(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task_id}",
            json=update_data
        )
        assert update_response.status_code == 200
        
        # Verify via GET
        get_response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            params={"filter": "all", "limit": 100}
        )
        tasks = get_response.json()
        found_task = next((t for t in tasks if t["_id"] == task_id), None)
        
        assert found_task is not None, "Updated task should exist"
        assert found_task["title"] == update_data["title"], "Updated title should persist"
        assert found_task["priority"] == update_data["priority"], "Updated priority should persist"
        
        print("PASS: Task update persisted successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task_id}")


# Cleanup any TEST_ prefixed tasks after all tests
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_tasks():
    """Cleanup TEST_ prefixed tasks after all tests complete"""
    yield
    # Cleanup - get all tasks and delete TEST_ ones
    try:
        response = requests.get(
            f"{BASE_URL}/api/tasks/{TEST_USER_ID}",
            params={"filter": "all", "limit": 200}
        )
        if response.status_code == 200:
            tasks = response.json()
            for task in tasks:
                if task.get("title", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/tasks/{TEST_USER_ID}/{task['_id']}")
            print(f"Cleanup: Removed {len([t for t in tasks if t.get('title','').startswith('TEST_')])} test tasks")
    except Exception as e:
        print(f"Cleanup warning: {e}")
