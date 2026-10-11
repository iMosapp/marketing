"""
Test Suite: New Account Onboarding (POST /api/setup-wizard/new-account)
Tests the streamlined onboarding flow that creates org, store, user, and tracking record.
"""
import pytest
import requests
import os
import time

from tests.live_auth import SUPER_ADMIN, Session

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
_ADMIN = None
RUN_TAG = str(int(time.time()))


def _admin_headers():
    """Real Bearer JWT for the super admin (only super admins and partner admins may create accounts)."""
    global _ADMIN
    if _ADMIN is None:
        _ADMIN = Session(*SUPER_ADMIN)
    return {"Content-Type": "application/json", **_ADMIN.headers}


@pytest.fixture(scope="module", autouse=True)
def _remove_everything_this_module_created():
    """Every account these tests create is named TEST_*_{RUN_TAG}; remove orgs, stores, users, seeds and tracking rows afterwards."""
    yield
    from pymongo import MongoClient
    from bson import ObjectId
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    name_re = {"$regex": f"^TEST_.*_{RUN_TAG}"}
    org_ids = [str(o["_id"]) for o in db.organizations.find({"name": name_re}, {"_id": 1})]
    store_ids = [str(st["_id"]) for st in db.stores.find({"$or": [{"name": name_re}, {"organization_id": {"$in": org_ids}}]}, {"_id": 1})]
    user_ids = [str(u["_id"]) for u in db.users.find({"organization_id": {"$in": org_ids}}, {"_id": 1})]
    for coll in ("campaigns", "date_trigger_configs", "email_templates", "review_response_templates", "social_templates", "tags", "templates", "notifications"):
        db[coll].delete_many({"user_id": {"$in": user_ids}})
    for coll in ("tags", "lead_sources", "compliance_onboarding", "setup_wizard_progress"):
        db[coll].delete_many({"store_id": {"$in": store_ids}})
    db.onboarding_clients.delete_many({"organization_id": {"$in": org_ids}})
    db.users.delete_many({"_id": {"$in": [ObjectId(i) for i in user_ids]}})
    db.stores.delete_many({"_id": {"$in": [ObjectId(i) for i in store_ids]}})
    db.organizations.delete_many({"_id": {"$in": [ObjectId(i) for i in org_ids]}})

class TestNewAccountOnboarding:
    """Tests for POST /api/setup-wizard/new-account endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.headers = _admin_headers()
        self.timestamp = RUN_TAG
    
    def test_successful_account_creation(self):
        """Test successful creation of org, store, and user"""
        payload = {
            "business_name": f"TEST_Successful_Biz_{self.timestamp}",
            "contact_name": "John Doe",
            "contact_phone": "5005554567",
            "contact_email": f"test_success_{self.timestamp}@example.com",
            "address": "123 Main St",
            "city": "Denver",
            "state": "CO",
            "zip": "80202",
            "industry": "Automotive / Dealership",
            "plan": "pro"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert "organization_id" in data
        assert "store_id" in data
        assert "user_id" in data
        assert "temp_password" in data
        assert len(data["temp_password"]) > 0
        assert data["business_name"] == f"TEST_Successful_Biz_{self.timestamp}"
        assert data["contact_name"] == "John Doe"
        assert data["contact_email"] == f"test_success_{self.timestamp}@example.com"
        
    def test_duplicate_email_returns_409(self):
        """Test that duplicate email returns 409 Conflict"""
        unique_email = f"test_dup_{self.timestamp}@example.com"
        
        # First creation - should succeed
        payload = {
            "business_name": f"TEST_First_Biz_{self.timestamp}",
            "contact_name": "First User",
            "contact_phone": "5005551111",
            "contact_email": unique_email,
            "plan": "starter"
        }
        
        response1 = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        assert response1.status_code == 200, f"First creation failed: {response1.text}"
        
        # Second creation with same email - should return 409
        payload2 = {
            "business_name": f"TEST_Second_Biz_{self.timestamp}",
            "contact_name": "Second User",
            "contact_phone": "5005552222",
            "contact_email": unique_email,
            "plan": "pro"
        }
        
        response2 = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload2,
            headers=self.headers
        )
        
        assert response2.status_code == 409, f"Expected 409, got {response2.status_code}"
        assert "already exists" in response2.json().get("detail", "").lower()
        
    def test_missing_business_name_returns_400(self):
        """Test that missing business_name returns 400"""
        payload = {
            "business_name": "",
            "contact_name": "Test User",
            "contact_phone": "5005553333"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "business name" in response.json().get("detail", "").lower()
        
    def test_missing_contact_name_returns_400(self):
        """Test that missing contact_name returns 400"""
        payload = {
            "business_name": f"TEST_NoContact_{self.timestamp}",
            "contact_name": "",
            "contact_phone": "5005554444"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "contact name" in response.json().get("detail", "").lower()
        
    def test_missing_contact_phone_returns_400(self):
        """Test that missing contact_phone returns 400"""
        payload = {
            "business_name": f"TEST_NoPhone_{self.timestamp}",
            "contact_name": "Test User",
            "contact_phone": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "contact phone" in response.json().get("detail", "").lower()
        
    def test_phone_normalization_10_digit(self):
        """Test 10-digit phone is normalized to E.164 (+1...)"""
        payload = {
            "business_name": f"TEST_PhoneNorm10_{self.timestamp}",
            "contact_name": "Phone Test",
            "contact_phone": "5005556543",  # 10 digits, Twilio test range
            "contact_email": f"test_phone10_{self.timestamp}@example.com",
            "plan": "pro"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        user_id = response.json()["user_id"]
        
        # Verify user phone is E.164
        user_response = requests.get(
            f"{BASE_URL}/api/admin/users/{user_id}",
            headers=self.headers
        )
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert user_data["phone"] == "+15005556543", f"Expected +15005556543, got {user_data['phone']}"
        
    def test_phone_normalization_with_formatting(self):
        """Test phone with formatting chars is normalized to E.164"""
        payload = {
            "business_name": f"TEST_PhoneFormat_{self.timestamp}",
            "contact_name": "Phone Format Test",
            "contact_phone": "(500) 555-4567",  # With formatting, Twilio test range
            "contact_email": f"test_phoneformat_{self.timestamp}@example.com",
            "plan": "pro"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        user_id = response.json()["user_id"]
        
        # Verify user phone is E.164
        user_response = requests.get(
            f"{BASE_URL}/api/admin/users/{user_id}",
            headers=self.headers
        )
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert user_data["phone"] == "+15005554567", f"Expected +15005554567, got {user_data['phone']}"
        
    def test_created_user_has_correct_role(self):
        """Test created user has role=store_manager"""
        payload = {
            "business_name": f"TEST_RoleCheck_{self.timestamp}",
            "contact_name": "Role Test",
            "contact_phone": "5005551111",
            "contact_email": f"test_role_{self.timestamp}@example.com",
            "plan": "enterprise"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        user_id = response.json()["user_id"]
        
        # Verify user role
        user_response = requests.get(
            f"{BASE_URL}/api/admin/users/{user_id}",
            headers=self.headers
        )
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert user_data["role"] == "store_manager", f"Expected store_manager, got {user_data['role']}"
        
    def test_created_user_needs_password_change(self):
        """Test created user has needs_password_change=True"""
        payload = {
            "business_name": f"TEST_PasswordChange_{self.timestamp}",
            "contact_name": "Password Test",
            "contact_phone": "5005552222",
            "contact_email": f"test_pwd_{self.timestamp}@example.com",
            "plan": "pro"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        user_id = response.json()["user_id"]
        
        # Verify needs_password_change
        user_response = requests.get(
            f"{BASE_URL}/api/admin/users/{user_id}",
            headers=self.headers
        )
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert user_data.get("needs_password_change") is True, f"Expected needs_password_change=True, got {user_data.get('needs_password_change')}"
        
    def test_created_user_linked_to_org_and_store(self):
        """Test created user is properly linked to org and store"""
        payload = {
            "business_name": f"TEST_Links_{self.timestamp}",
            "contact_name": "Link Test",
            "contact_phone": "5005553333",
            "contact_email": f"test_links_{self.timestamp}@example.com",
            "plan": "pro"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        org_id = data["organization_id"]
        store_id = data["store_id"]
        user_id = data["user_id"]
        
        # Verify user links
        user_response = requests.get(
            f"{BASE_URL}/api/admin/users/{user_id}",
            headers=self.headers
        )
        assert user_response.status_code == 200
        user_data = user_response.json()
        
        assert user_data["organization_id"] == org_id, f"User org_id mismatch"
        assert user_data["store_id"] == store_id, f"User store_id mismatch"
        assert store_id in user_data.get("store_ids", []), f"store_id not in user's store_ids"
        
    def test_optional_email_creates_placeholder(self):
        """Test account can be created without email (uses placeholder)"""
        payload = {
            "business_name": f"TEST_NoEmail_{self.timestamp}",
            "contact_name": "No Email Test",
            "contact_phone": "5005554444",
            "plan": "starter"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        # Email should be empty or placeholder
        assert data.get("contact_email") == "" or "placeholder" in data.get("contact_email", "").lower()
        
    def test_plan_selection(self):
        """Test different plans are saved correctly"""
        for plan in ["starter", "pro", "enterprise"]:
            payload = {
                "business_name": f"TEST_Plan_{plan}_{self.timestamp}",
                "contact_name": f"Plan {plan} Test",
                "contact_phone": "5005555555",
                "contact_email": f"test_plan_{plan}_{self.timestamp}@example.com",
                "plan": plan
            }
            
            response = requests.post(
                f"{BASE_URL}/api/setup-wizard/new-account",
                json=payload,
                headers=self.headers
            )
            
            assert response.status_code == 200, f"Plan {plan} failed: {response.text}"
            user_id = response.json()["user_id"]
            
            # Verify plan on user
            user_response = requests.get(
                f"{BASE_URL}/api/admin/users/{user_id}",
                headers=self.headers
            )
            assert user_response.status_code == 200
            user_data = user_response.json()
            assert user_data.get("plan") == plan, f"Expected plan={plan}, got {user_data.get('plan')}"


class TestTrackingRecordCreation:
    """Tests for onboarding_clients tracking record creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = _admin_headers()
        self.timestamp = RUN_TAG
        
    def test_tracking_record_created(self):
        """Test that a tracking record is created in onboarding_clients"""
        payload = {
            "business_name": f"TEST_Tracking_{self.timestamp}",
            "contact_name": "Tracking Test",
            "contact_phone": "5005556666",
            "contact_email": f"test_tracking_{self.timestamp}@example.com",
            "industry": "Real Estate",
            "plan": "pro"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/setup-wizard/new-account",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tracking record via clients list
        clients_response = requests.get(
            f"{BASE_URL}/api/setup-wizard/clients",
            headers=self.headers
        )
        
        assert clients_response.status_code == 200
        clients = clients_response.json()
        
        # Find our client
        our_client = None
        for client in clients:
            if client.get("client_name") == f"TEST_Tracking_{self.timestamp}":
                our_client = client
                break
                
        assert our_client is not None, "Tracking record not found in clients list"
        assert our_client.get("contact_email") == f"test_tracking_{self.timestamp}@example.com"
        assert our_client.get("industry") == "Real Estate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
