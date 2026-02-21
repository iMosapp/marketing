"""
Backend Tests for MVPLine - Auth, Tasks CRUD, and Password Reset
Tests: Signup, Login, Logout flow, Tasks CRUD, Forgot Password flow
"""
import pytest
import requests
import os
import random
import string

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://imos-auth-ui.preview.emergentagent.com')
if BASE_URL and not BASE_URL.startswith('http'):
    BASE_URL = f"https://{BASE_URL}"

print(f"Testing against BASE_URL: {BASE_URL}")


def generate_test_email():
    """Generate unique test email"""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"TEST_user_{random_str}@test.com"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_root(self, api_client):
        """Test API root endpoint is accessible"""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "MVPLine API"
        print(f"✓ API root accessible: {data}")


class TestAuthFlow:
    """Authentication flow tests - Signup, Login, Logout"""
    
    def test_signup_new_user(self, api_client):
        """Test user signup - CREATE"""
        test_email = generate_test_email()
        signup_data = {
            "email": test_email,
            "password": "testpassword123",
            "name": "TEST User",
            "phone": "+15551234567",
            "mode": "solo"
        }
        
        response = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response.status_code == 200, f"Signup failed: {response.text}"
        
        data = response.json()
        assert "email" in data
        assert data["email"] == test_email
        assert "mvpline_number" in data
        assert "_id" in data
        print(f"✓ User signup successful: {data['email']}, ID: {data['_id']}")
        
        return data
    
    def test_signup_duplicate_email_fails(self, api_client):
        """Test that duplicate email signup fails"""
        test_email = generate_test_email()
        signup_data = {
            "email": test_email,
            "password": "testpassword123",
            "name": "TEST User 1",
            "phone": "+15551234567"
        }
        
        # First signup
        response1 = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response1.status_code == 200
        
        # Second signup with same email should fail
        signup_data["name"] = "TEST User 2"
        response2 = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert response2.status_code == 400, "Duplicate email should fail"
        
        data = response2.json()
        assert "Email already registered" in data.get("detail", "")
        print(f"✓ Duplicate email correctly rejected")
    
    def test_login_success(self, api_client):
        """Test user login with valid credentials"""
        test_email = generate_test_email()
        password = "testpassword123"
        
        # First create the user
        signup_data = {
            "email": test_email,
            "password": password,
            "name": "TEST Login User",
            "phone": "+15551234568"
        }
        signup_response = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200, f"Signup failed: {signup_response.text}"
        
        # Now login
        login_data = {"email": test_email, "password": password}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        assert "user" in data
        assert "token" in data
        assert data["user"]["email"] == test_email
        assert len(data["token"]) > 0
        print(f"✓ Login successful: {data['user']['email']}, Token: {data['token'][:20]}...")
        
        return data
    
    def test_login_invalid_credentials(self, api_client):
        """Test login with wrong password fails"""
        # Try to login with non-existent email
        login_data = {"email": "nonexistent@test.com", "password": "wrongpassword"}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid credentials" in data.get("detail", "")
        print(f"✓ Invalid credentials correctly rejected")
    
    def test_login_missing_fields(self, api_client):
        """Test login with missing fields fails"""
        # Missing password
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": "test@test.com"})
        assert response.status_code == 400
        print(f"✓ Missing fields correctly rejected")


class TestForgotPasswordFlow:
    """Forgot Password flow tests - 3 step process"""
    
    def test_forgot_password_request_code(self, api_client):
        """Test requesting a password reset code"""
        test_email = generate_test_email()
        
        # First create the user
        signup_data = {
            "email": test_email,
            "password": "oldpassword123",
            "name": "TEST Reset User",
            "phone": "+15551234569"
        }
        signup_response = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        
        # Request reset code
        response = api_client.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": test_email})
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        # In dev mode, dev_code should be returned
        assert "dev_code" in data, "Dev code should be returned in dev mode"
        assert len(data["dev_code"]) == 6
        print(f"✓ Password reset code requested: {data['dev_code']}")
        
        return {"email": test_email, "code": data["dev_code"]}
    
    def test_forgot_password_nonexistent_email(self, api_client):
        """Test forgot password with non-existent email (should not reveal info)"""
        response = api_client.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "nonexistent@test.com"})
        # Should return success even for non-existent email (security)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ Non-existent email handled securely")
    
    def test_verify_reset_code_valid(self, api_client):
        """Test verifying a valid reset code"""
        # Create user and request code
        test_email = generate_test_email()
        signup_data = {
            "email": test_email,
            "password": "oldpassword123",
            "name": "TEST Verify Code User",
            "phone": "+15551234570"
        }
        api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        
        forgot_response = api_client.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": test_email})
        code = forgot_response.json()["dev_code"]
        
        # Verify the code
        response = api_client.post(f"{BASE_URL}/api/auth/verify-reset-code", json={
            "email": test_email,
            "code": code
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") == True
        print(f"✓ Code verification successful")
    
    def test_verify_reset_code_invalid(self, api_client):
        """Test verifying an invalid reset code"""
        test_email = generate_test_email()
        signup_data = {
            "email": test_email,
            "password": "oldpassword123",
            "name": "TEST Invalid Code User",
            "phone": "+15551234571"
        }
        api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        api_client.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": test_email})
        
        # Try invalid code
        response = api_client.post(f"{BASE_URL}/api/auth/verify-reset-code", json={
            "email": test_email,
            "code": "000000"  # Invalid code
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid or expired" in data.get("detail", "")
        print(f"✓ Invalid code correctly rejected")
    
    def test_full_password_reset_flow(self, api_client):
        """Test complete password reset flow: Request -> Verify -> Reset -> Login"""
        test_email = generate_test_email()
        old_password = "oldpassword123"
        new_password = "newpassword456"
        
        # Step 1: Create user
        signup_data = {
            "email": test_email,
            "password": old_password,
            "name": "TEST Full Reset User",
            "phone": "+15551234572"
        }
        signup_response = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        print(f"  Step 1: User created")
        
        # Step 2: Request reset code
        forgot_response = api_client.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": test_email})
        assert forgot_response.status_code == 200
        code = forgot_response.json()["dev_code"]
        print(f"  Step 2: Reset code obtained: {code}")
        
        # Step 3: Verify the code
        verify_response = api_client.post(f"{BASE_URL}/api/auth/verify-reset-code", json={
            "email": test_email,
            "code": code
        })
        assert verify_response.status_code == 200
        print(f"  Step 3: Code verified")
        
        # Step 4: Reset password
        reset_response = api_client.post(f"{BASE_URL}/api/auth/reset-password", json={
            "email": test_email,
            "code": code,
            "new_password": new_password
        })
        assert reset_response.status_code == 200
        print(f"  Step 4: Password reset")
        
        # Step 5: Login with NEW password
        login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": new_password
        })
        assert login_response.status_code == 200
        print(f"  Step 5: Login with new password successful")
        
        # Step 6: OLD password should fail
        old_login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": old_password
        })
        assert old_login_response.status_code == 401
        print(f"  Step 6: Old password correctly rejected")
        
        print(f"✓ Full password reset flow completed successfully!")


class TestTasksCRUD:
    """Tasks CRUD tests - Create, Read, Update, Delete"""
    
    @pytest.fixture
    def auth_user(self, api_client):
        """Create and login a test user, return user data"""
        test_email = generate_test_email()
        signup_data = {
            "email": test_email,
            "password": "tasktest123",
            "name": "TEST Task User",
            "phone": "+15551234573"
        }
        signup_response = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        assert signup_response.status_code == 200
        
        login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": "tasktest123"
        })
        assert login_response.status_code == 200
        return login_response.json()["user"]
    
    def test_create_task(self, api_client, auth_user):
        """Test creating a new task"""
        user_id = auth_user["_id"]
        task_data = {
            "type": "callback",
            "title": "TEST Call John",
            "description": "Follow up about test drive",
            "priority": "high",
            "due_date": "2025-02-20T10:00:00",
            "completed": False
        }
        
        response = api_client.post(f"{BASE_URL}/api/tasks/{user_id}", json=task_data)
        assert response.status_code == 200, f"Create task failed: {response.text}"
        
        data = response.json()
        assert "_id" in data
        assert data["title"] == task_data["title"]
        assert data["type"] == task_data["type"]
        assert data["priority"] == task_data["priority"]
        assert data["completed"] == False
        print(f"✓ Task created: {data['_id']}")
        
        return data
    
    def test_get_tasks_list(self, api_client, auth_user):
        """Test getting all tasks for a user"""
        user_id = auth_user["_id"]
        
        # Create a couple of tasks first
        for i in range(2):
            task_data = {
                "type": "follow_up",
                "title": f"TEST Task {i+1}",
                "priority": "medium",
                "due_date": "2025-02-21T10:00:00",
                "completed": False
            }
            api_client.post(f"{BASE_URL}/api/tasks/{user_id}", json=task_data)
        
        # Get all tasks
        response = api_client.get(f"{BASE_URL}/api/tasks/{user_id}")
        assert response.status_code == 200
        
        tasks = response.json()
        assert isinstance(tasks, list)
        assert len(tasks) >= 2
        print(f"✓ Got {len(tasks)} tasks")
        
        return tasks
    
    def test_update_task_toggle_completion(self, api_client, auth_user):
        """Test updating task - toggle completion status"""
        user_id = auth_user["_id"]
        
        # Create a task
        task_data = {
            "type": "appointment",
            "title": "TEST Complete Me",
            "priority": "low",
            "due_date": "2025-02-22T10:00:00",
            "completed": False
        }
        create_response = api_client.post(f"{BASE_URL}/api/tasks/{user_id}", json=task_data)
        task_id = create_response.json()["_id"]
        
        # Update to completed
        update_response = api_client.put(f"{BASE_URL}/api/tasks/{user_id}/{task_id}", json={
            "completed": True
        })
        assert update_response.status_code == 200
        print(f"  Task marked as completed")
        
        # Verify update persisted via GET
        get_response = api_client.get(f"{BASE_URL}/api/tasks/{user_id}")
        assert get_response.status_code == 200
        
        tasks = get_response.json()
        updated_task = next((t for t in tasks if t["_id"] == task_id), None)
        assert updated_task is not None
        assert updated_task["completed"] == True
        print(f"✓ Task completion toggle verified")
    
    def test_delete_task(self, api_client, auth_user):
        """Test deleting a task"""
        user_id = auth_user["_id"]
        
        # Create a task to delete
        task_data = {
            "type": "other",
            "title": "TEST Delete Me",
            "priority": "medium",
            "due_date": "2025-02-23T10:00:00",
            "completed": False
        }
        create_response = api_client.post(f"{BASE_URL}/api/tasks/{user_id}", json=task_data)
        task_id = create_response.json()["_id"]
        print(f"  Task created: {task_id}")
        
        # Delete the task
        delete_response = api_client.delete(f"{BASE_URL}/api/tasks/{user_id}/{task_id}")
        assert delete_response.status_code == 200
        print(f"  Task deleted")
        
        # Verify task is gone via GET
        get_response = api_client.get(f"{BASE_URL}/api/tasks/{user_id}")
        tasks = get_response.json()
        deleted_task = next((t for t in tasks if t["_id"] == task_id), None)
        assert deleted_task is None, "Task should not exist after deletion"
        print(f"✓ Task deletion verified")
    
    def test_delete_nonexistent_task(self, api_client, auth_user):
        """Test deleting a non-existent task returns 404"""
        user_id = auth_user["_id"]
        fake_task_id = "507f1f77bcf86cd799439011"  # Valid MongoDB ObjectId format
        
        response = api_client.delete(f"{BASE_URL}/api/tasks/{user_id}/{fake_task_id}")
        assert response.status_code == 404
        print(f"✓ Non-existent task delete correctly returns 404")
    
    def test_get_active_tasks_filter(self, api_client, auth_user):
        """Test filtering tasks by completion status"""
        user_id = auth_user["_id"]
        
        # Create completed and incomplete tasks
        api_client.post(f"{BASE_URL}/api/tasks/{user_id}", json={
            "type": "callback", "title": "TEST Active Task", "priority": "high",
            "due_date": "2025-02-24T10:00:00", "completed": False
        })
        
        task2_response = api_client.post(f"{BASE_URL}/api/tasks/{user_id}", json={
            "type": "callback", "title": "TEST Done Task", "priority": "high",
            "due_date": "2025-02-24T11:00:00", "completed": False
        })
        task2_id = task2_response.json()["_id"]
        
        # Mark second as complete
        api_client.put(f"{BASE_URL}/api/tasks/{user_id}/{task2_id}", json={"completed": True})
        
        # Get only active tasks
        response = api_client.get(f"{BASE_URL}/api/tasks/{user_id}", params={"completed": False})
        assert response.status_code == 200
        tasks = response.json()
        
        for task in tasks:
            assert task.get("completed") == False
        print(f"✓ Active tasks filter working: {len(tasks)} active tasks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
