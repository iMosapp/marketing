"""
Sprint 2 Touchpoints API Tests - Testing backend endpoints for Touchpoints feature.
Tests: GET tasks (filtered), summary, performance, PATCH (complete/snooze), POST create
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"


class TestTasksFilterEndpoints:
    """Test GET /api/tasks/{user_id} with various filters"""
    
    def test_get_tasks_filter_today(self):
        """GET /api/tasks/{user_id}?filter=today returns today's tasks"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}?filter=today&limit=100")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET tasks filter=today returned {len(data)} tasks")
        
        # Verify task structure
        if len(data) > 0:
            task = data[0]
            assert "_id" in task
            assert "user_id" in task
            assert "status" in task
            print(f"✓ Task structure valid: {task.get('title', 'N/A')[:50]}")
    
    def test_get_tasks_filter_overdue(self):
        """GET /api/tasks/{user_id}?filter=overdue returns overdue tasks"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}?filter=overdue&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET tasks filter=overdue returned {len(data)} tasks")
    
    def test_get_tasks_filter_completed(self):
        """GET /api/tasks/{user_id}?filter=completed returns completed tasks"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}?filter=completed&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET tasks filter=completed returned {len(data)} tasks")


class TestTasksSummaryEndpoint:
    """Test GET /api/tasks/{user_id}/summary endpoint"""
    
    def test_get_summary(self):
        """GET /api/tasks/{user_id}/summary returns daily scoreboard data"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total_today" in data
        assert "completed_today" in data
        assert "pending_today" in data
        assert "progress_pct" in data
        assert "activity" in data
        
        # Verify activity breakdown
        activity = data["activity"]
        assert "calls" in activity
        assert "texts" in activity
        assert "emails" in activity
        assert "cards" in activity
        assert "reviews" in activity
        
        print(f"✓ Summary: {data['completed_today']}/{data['total_today']} completed ({data['progress_pct']}%)")
        print(f"✓ Activity: calls={activity['calls']}, texts={activity['texts']}, emails={activity['emails']}, cards={activity['cards']}, reviews={activity['reviews']}")


class TestTasksPerformanceEndpoint:
    """Test GET /api/tasks/{user_id}/performance endpoint"""
    
    def test_get_performance_week(self):
        """GET /api/tasks/{user_id}/performance?period=week returns weekly stats"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=week")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total_touchpoints" in data
        assert "trend_pct" in data
        assert "communication" in data
        assert "sharing" in data
        assert "engagement" in data
        assert "click_through" in data
        
        # Verify communication breakdown
        comm = data["communication"]
        assert "texts" in comm
        assert "emails" in comm
        assert "calls" in comm
        
        # Verify sharing breakdown
        sharing = data["sharing"]
        assert "cards" in sharing
        assert "reviews" in sharing
        assert "congrats" in sharing
        
        # Verify engagement breakdown
        engagement = data["engagement"]
        assert "link_clicks" in engagement
        assert "email_opens" in engagement
        assert "replies" in engagement
        assert "new_leads" in engagement
        
        # Verify click-through breakdown
        ctr = data["click_through"]
        assert "digital_card_views" in ctr
        assert "review_link_clicks" in ctr
        assert "showcase_views" in ctr
        assert "link_page_visits" in ctr
        
        print(f"✓ Performance (week): {data['total_touchpoints']} touchpoints, trend={data['trend_pct']}%")
    
    def test_get_performance_today(self):
        """GET /api/tasks/{user_id}/performance?period=today returns daily stats"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=today")
        assert response.status_code == 200
        data = response.json()
        assert "total_touchpoints" in data
        print(f"✓ Performance (today): {data['total_touchpoints']} touchpoints")
    
    def test_get_performance_month(self):
        """GET /api/tasks/{user_id}/performance?period=month returns monthly stats"""
        response = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}/performance?period=month")
        assert response.status_code == 200
        data = response.json()
        assert "total_touchpoints" in data
        print(f"✓ Performance (month): {data['total_touchpoints']} touchpoints")


class TestTaskCreateEndpoint:
    """Test POST /api/tasks/{user_id} endpoint"""
    
    def test_create_task_success(self):
        """POST /api/tasks/{user_id} creates a new manual task"""
        payload = {
            "title": "TEST_Sprint2_Follow up call",
            "description": "Test task for Sprint 2 UI testing",
            "priority": "high",
            "action_type": "call",
            "type": "manual"
        }
        response = requests.post(f"{BASE_URL}/api/tasks/{USER_ID}", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify returned task
        assert "_id" in data
        assert data["title"] == payload["title"]
        assert data["priority"] == payload["priority"]
        assert data["action_type"] == payload["action_type"]
        assert data["status"] == "pending"
        
        print(f"✓ Created task: {data['_id']} - {data['title']}")
        
        # Clean up - delete the test task
        task_id = data["_id"]
        delete_response = requests.delete(f"{BASE_URL}/api/tasks/{USER_ID}/{task_id}")
        assert delete_response.status_code == 200
        print(f"✓ Cleaned up test task: {task_id}")
    
    def test_create_task_empty_title_fails(self):
        """POST /api/tasks/{user_id} with empty title returns 400"""
        payload = {"title": "   ", "description": "Should fail"}
        response = requests.post(f"{BASE_URL}/api/tasks/{USER_ID}", json=payload)
        assert response.status_code == 400
        print("✓ Empty title correctly rejected with 400")


class TestTaskPatchEndpoints:
    """Test PATCH /api/tasks/{user_id}/{task_id} endpoint for task actions"""
    
    @pytest.fixture(autouse=True)
    def setup_task(self):
        """Create a task for testing, clean up after"""
        payload = {
            "title": "TEST_Sprint2_PATCH_Test",
            "description": "Task for testing PATCH actions",
            "priority": "medium",
            "action_type": "text"
        }
        response = requests.post(f"{BASE_URL}/api/tasks/{USER_ID}", json=payload)
        assert response.status_code == 200
        self.task_id = response.json()["_id"]
        print(f"Setup: Created task {self.task_id}")
        
        yield
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tasks/{USER_ID}/{self.task_id}")
        print(f"Teardown: Deleted task {self.task_id}")
    
    def test_patch_complete_task(self):
        """PATCH with action=complete marks task as completed"""
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{USER_ID}/{self.task_id}",
            json={"action": "complete"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "completed"
        assert data["completed"] == True
        assert "completed_at" in data and data["completed_at"] is not None
        
        print(f"✓ Task completed: status={data['status']}, completed_at={data['completed_at']}")
    
    def test_patch_snooze_task(self):
        """PATCH with action=snooze snoozes task for 24 hours"""
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{USER_ID}/{self.task_id}",
            json={"action": "snooze", "snooze_hours": 24}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "snoozed"
        assert "snoozed_until" in data and data["snoozed_until"] is not None
        
        print(f"✓ Task snoozed: status={data['status']}, snoozed_until={data['snoozed_until']}")
    
    def test_patch_nonexistent_task(self):
        """PATCH nonexistent task returns 404"""
        response = requests.patch(
            f"{BASE_URL}/api/tasks/{USER_ID}/000000000000000000000000",
            json={"action": "complete"}
        )
        assert response.status_code == 404
        print("✓ Nonexistent task correctly returns 404")


class TestTasksIntegration:
    """Integration tests for full task workflow"""
    
    def test_full_task_lifecycle(self):
        """Test create -> read -> complete -> verify flow"""
        # 1. Create task
        payload = {
            "title": "TEST_Sprint2_Lifecycle",
            "description": "Full lifecycle test",
            "priority": "high",
            "action_type": "call"
        }
        create_resp = requests.post(f"{BASE_URL}/api/tasks/{USER_ID}", json=payload)
        assert create_resp.status_code == 200
        task_id = create_resp.json()["_id"]
        print(f"1. Created task: {task_id}")
        
        # 2. Verify task appears in today filter
        list_resp = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}?filter=today&limit=100")
        assert list_resp.status_code == 200
        tasks = list_resp.json()
        task_ids = [t["_id"] for t in tasks]
        assert task_id in task_ids, "Created task should appear in today's tasks"
        print(f"2. Task appears in today filter ✓")
        
        # 3. Complete the task
        complete_resp = requests.patch(
            f"{BASE_URL}/api/tasks/{USER_ID}/{task_id}",
            json={"action": "complete"}
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"
        print(f"3. Task completed ✓")
        
        # 4. Verify task no longer in today filter (pending)
        list_resp2 = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}?filter=today&limit=100")
        tasks2 = list_resp2.json()
        task_ids2 = [t["_id"] for t in tasks2]
        assert task_id not in task_ids2, "Completed task should not appear in today's pending tasks"
        print(f"4. Completed task removed from today filter ✓")
        
        # 5. Verify task appears in completed filter
        completed_resp = requests.get(f"{BASE_URL}/api/tasks/{USER_ID}?filter=completed&limit=100")
        completed_tasks = completed_resp.json()
        completed_ids = [t["_id"] for t in completed_tasks]
        assert task_id in completed_ids, "Completed task should appear in completed filter"
        print(f"5. Task in completed filter ✓")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tasks/{USER_ID}/{task_id}")
        print(f"6. Cleanup complete ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
