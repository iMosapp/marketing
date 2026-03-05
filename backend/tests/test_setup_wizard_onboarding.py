"""
Setup Wizard Onboarding Tests - Tests the 8-step admin onboarding wizard flow
Tests: Organization creation, Store creation, User creation with name field, User profile update
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://engagement-hub-69.preview.emergentagent.com")
# Super admin credentials for testing
SUPER_ADMIN_USER_ID = "69a0b7095fddcede09591667"

class TestSetupWizardAPIs:
    """Test the admin APIs used by the setup wizard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.headers = {
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_USER_ID
        }
        self.test_org_id = None
        self.test_store_id = None
        self.test_user_id = None
        yield
        # Cleanup created test data
        self.cleanup()
    
    def cleanup(self):
        """Clean up test data"""
        try:
            if self.test_user_id:
                requests.delete(f"{BASE_URL}/api/admin/users/{self.test_user_id}", headers=self.headers)
            if self.test_store_id:
                requests.delete(f"{BASE_URL}/api/admin/stores/{self.test_store_id}", headers=self.headers)
            if self.test_org_id:
                requests.delete(f"{BASE_URL}/api/admin/organizations/{self.test_org_id}", headers=self.headers)
        except Exception as e:
            print(f"Cleanup error: {e}")

    # ======== Step 1: Organization & Store Tests ========
    def test_create_organization(self):
        """Step 1: POST /api/admin/organizations - Create organization"""
        org_data = {
            "name": "TEST_WizardOrg_" + str(int(time.time())),
            "admin_email": "test@example.com",
            "admin_phone": "555-123-4567",
            "city": "Austin",
            "state": "TX",
            "account_type": "organization"
        }
        response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        
        # Verify status
        assert response.status_code == 200, f"Failed to create org: {response.text}"
        
        # Verify data
        data = response.json()
        assert "_id" in data or "id" in data, "Organization ID not returned"
        assert data.get("name") == org_data["name"], "Org name mismatch"
        
        self.test_org_id = data.get("_id") or data.get("id")
        print(f"Created organization: {self.test_org_id}")
    
    def test_create_store(self):
        """Step 1: POST /api/admin/stores - Create store linked to organization"""
        # First create an org
        org_data = {
            "name": "TEST_WizardOrg_Store_" + str(int(time.time())),
            "admin_email": "test@example.com",
            "city": "Austin",
            "state": "TX",
            "account_type": "organization"
        }
        org_response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        assert org_response.status_code == 200, f"Failed to create org: {org_response.text}"
        self.test_org_id = org_response.json().get("_id") or org_response.json().get("id")
        
        # Now create store
        store_data = {
            "organization_id": self.test_org_id,
            "name": "TEST_WizardStore_" + str(int(time.time())),
            "phone": "555-987-6543",
            "city": "Austin",
            "state": "TX",
            "website": "https://test.com",
            "industry": "Automotive / Dealership"
        }
        response = requests.post(f"{BASE_URL}/api/admin/stores", json=store_data, headers=self.headers)
        
        # Verify status
        assert response.status_code == 200, f"Failed to create store: {response.text}"
        
        # Verify data
        data = response.json()
        assert "_id" in data or "id" in data, "Store ID not returned"
        assert data.get("name") == store_data["name"], "Store name mismatch"
        assert data.get("organization_id") == self.test_org_id, "Store org_id mismatch"
        
        self.test_store_id = data.get("_id") or data.get("id")
        print(f"Created store: {self.test_store_id}")
    
    # ======== Step 3: Create User Tests ========
    def test_create_user_with_name_field(self):
        """Step 3: POST /api/admin/users - Create user with 'name' field (full name)"""
        # First create org and store
        org_data = {"name": "TEST_UserOrg_" + str(int(time.time())), "admin_email": "t@t.com", "city": "Austin", "state": "TX", "account_type": "organization"}
        org_response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        self.test_org_id = org_response.json().get("_id") or org_response.json().get("id")
        
        store_data = {"organization_id": self.test_org_id, "name": "TEST_UserStore", "city": "Austin", "state": "TX"}
        store_response = requests.post(f"{BASE_URL}/api/admin/stores", json=store_data, headers=self.headers)
        self.test_store_id = store_response.json().get("_id") or store_response.json().get("id")
        
        # Create user with 'name' field (full name combining first+last)
        unique_email = f"test_wizard_{int(time.time())}@example.com"
        user_data = {
            "name": "John Doe",  # Full name as frontend sends
            "email": unique_email,
            "phone": "555-111-2222",
            "password": "Welcome1234!",
            "role": "user",
            "store_id": self.test_store_id,
            "organization_id": self.test_org_id  # Frontend sends organization_id (not org_id)
        }
        response = requests.post(f"{BASE_URL}/api/admin/users", json=user_data, headers=self.headers)
        
        # Verify status
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        
        # Verify data
        data = response.json()
        assert "_id" in data or "id" in data, "User ID not returned"
        assert data.get("name") == "John Doe", f"User name mismatch: got {data.get('name')}"
        assert data.get("email") == unique_email, "User email mismatch"
        assert data.get("organization_id") == self.test_org_id, f"User org_id mismatch: got {data.get('organization_id')}"
        
        self.test_user_id = data.get("_id") or data.get("id")
        print(f"Created user: {self.test_user_id}")
        
        # GET user to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/admin/users/{self.test_user_id}", headers=self.headers)
        assert get_response.status_code == 200, f"Failed to get user: {get_response.text}"
        fetched_user = get_response.json()
        assert fetched_user.get("name") == "John Doe", f"User name not persisted: {fetched_user.get('name')}"
    
    # ======== Step 4: User Profile Update Tests ========
    def test_update_user_profile_fields(self):
        """Step 4: PUT /api/admin/users/{id} - Update user with title, bio, social_links"""
        # First create org, store, user
        org_data = {"name": "TEST_ProfileOrg_" + str(int(time.time())), "admin_email": "t@t.com", "city": "Austin", "state": "TX", "account_type": "organization"}
        org_response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        self.test_org_id = org_response.json().get("_id") or org_response.json().get("id")
        
        store_data = {"organization_id": self.test_org_id, "name": "TEST_ProfileStore", "city": "Austin", "state": "TX"}
        store_response = requests.post(f"{BASE_URL}/api/admin/stores", json=store_data, headers=self.headers)
        self.test_store_id = store_response.json().get("_id") or store_response.json().get("id")
        
        unique_email = f"test_profile_{int(time.time())}@example.com"
        user_data = {"name": "Jane Smith", "email": unique_email, "password": "Welcome1234!", "role": "user", "store_id": self.test_store_id, "organization_id": self.test_org_id}
        user_response = requests.post(f"{BASE_URL}/api/admin/users", json=user_data, headers=self.headers)
        self.test_user_id = user_response.json().get("_id") or user_response.json().get("id")
        
        # Update user profile with title, bio, social links
        profile_update = {
            "title": "Sales Manager",
            "bio": "Experienced sales professional with 10 years in automotive industry",
            "social_instagram": "@janesmith",
            "social_facebook": "https://facebook.com/janesmith",
            "social_linkedin": "https://linkedin.com/in/janesmith"
        }
        response = requests.put(f"{BASE_URL}/api/admin/users/{self.test_user_id}", json=profile_update, headers=self.headers)
        
        # Verify status
        assert response.status_code == 200, f"Failed to update user profile: {response.text}"
        
        # GET user to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/admin/users/{self.test_user_id}", headers=self.headers)
        assert get_response.status_code == 200, f"Failed to get user: {get_response.text}"
        fetched_user = get_response.json()
        
        # Verify profile fields were saved
        assert fetched_user.get("title") == "Sales Manager", f"Title not saved: {fetched_user.get('title')}"
        assert fetched_user.get("bio") == profile_update["bio"], f"Bio not saved: {fetched_user.get('bio')}"
        assert fetched_user.get("social_instagram") == "@janesmith", f"Instagram not saved: {fetched_user.get('social_instagram')}"
        print(f"Profile fields verified: title={fetched_user.get('title')}, bio length={len(fetched_user.get('bio', ''))}")
    
    # ======== Step 2: Store Branding Update Tests ========
    def test_update_store_branding(self):
        """Step 2: PUT /api/admin/stores/{id} - Update store with email_footer and industry"""
        # Create org and store
        org_data = {"name": "TEST_BrandingOrg_" + str(int(time.time())), "admin_email": "t@t.com", "city": "Austin", "state": "TX", "account_type": "organization"}
        org_response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        self.test_org_id = org_response.json().get("_id") or org_response.json().get("id")
        
        store_data = {"organization_id": self.test_org_id, "name": "TEST_BrandingStore", "city": "Austin", "state": "TX"}
        store_response = requests.post(f"{BASE_URL}/api/admin/stores", json=store_data, headers=self.headers)
        self.test_store_id = store_response.json().get("_id") or store_response.json().get("id")
        
        # Update store with branding fields
        branding_update = {
            "primary_color": "#007AFF",
            "email_footer": "Powered by Rev1 Auto Group",
            "industry": "Automotive / Dealership"
        }
        response = requests.put(f"{BASE_URL}/api/admin/stores/{self.test_store_id}", json=branding_update, headers=self.headers)
        
        # Verify status
        assert response.status_code == 200, f"Failed to update store branding: {response.text}"
        
        # GET store to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/admin/stores/{self.test_store_id}", headers=self.headers)
        assert get_response.status_code == 200, f"Failed to get store: {get_response.text}"
        fetched_store = get_response.json()
        
        # Verify branding fields
        assert fetched_store.get("primary_color") == "#007AFF", f"Primary color not saved: {fetched_store.get('primary_color')}"
        assert fetched_store.get("email_footer") == "Powered by Rev1 Auto Group", f"Email footer not saved: {fetched_store.get('email_footer')}"
        assert fetched_store.get("industry") == "Automotive / Dealership", f"Industry not saved: {fetched_store.get('industry')}"
        print(f"Store branding verified: color={fetched_store.get('primary_color')}, industry={fetched_store.get('industry')}")
    
    # ======== Step 5: Review Links Tests ========
    def test_update_store_review_links(self):
        """Step 5: PUT /api/admin/stores/{id}/review-links - Update store review links"""
        # Create org and store
        org_data = {"name": "TEST_ReviewOrg_" + str(int(time.time())), "admin_email": "t@t.com", "city": "Austin", "state": "TX", "account_type": "organization"}
        org_response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        self.test_org_id = org_response.json().get("_id") or org_response.json().get("id")
        
        store_data = {"organization_id": self.test_org_id, "name": "TEST_ReviewStore", "city": "Austin", "state": "TX"}
        store_response = requests.post(f"{BASE_URL}/api/admin/stores", json=store_data, headers=self.headers)
        self.test_store_id = store_response.json().get("_id") or store_response.json().get("id")
        
        # Update review links
        review_links = {
            "google": "https://g.page/r/example",
            "facebook": "https://facebook.com/example/reviews",
            "yelp": "https://yelp.com/biz/example"
        }
        response = requests.put(f"{BASE_URL}/api/admin/stores/{self.test_store_id}/review-links", json=review_links, headers=self.headers)
        
        # Verify status
        assert response.status_code == 200, f"Failed to update review links: {response.text}"
        
        # GET review links to verify
        get_response = requests.get(f"{BASE_URL}/api/admin/stores/{self.test_store_id}/review-links", headers=self.headers)
        assert get_response.status_code == 200, f"Failed to get review links: {get_response.text}"
        fetched_links = get_response.json()
        
        assert fetched_links.get("google") == review_links["google"], f"Google link not saved: {fetched_links.get('google')}"
        print(f"Review links verified: google={fetched_links.get('google')}")
    
    # ======== Full Wizard Flow Test ========
    def test_full_wizard_flow(self):
        """Full wizard flow: Org -> Store -> User -> Profile -> Review Links"""
        # Step 1: Create Organization
        org_data = {
            "name": "TEST_FullWizardOrg_" + str(int(time.time())),
            "admin_email": "admin@example.com",
            "city": "Austin",
            "state": "TX",
            "account_type": "organization"
        }
        org_response = requests.post(f"{BASE_URL}/api/admin/organizations", json=org_data, headers=self.headers)
        assert org_response.status_code == 200, f"Step 1 Failed - Create Org: {org_response.text}"
        self.test_org_id = org_response.json().get("_id") or org_response.json().get("id")
        print(f"Step 1 PASS: Created org {self.test_org_id}")
        
        # Step 1: Create Store
        store_data = {
            "organization_id": self.test_org_id,
            "name": "TEST_FullWizardStore",
            "phone": "555-111-2222",
            "city": "Austin",
            "state": "TX",
            "industry": "Real Estate"
        }
        store_response = requests.post(f"{BASE_URL}/api/admin/stores", json=store_data, headers=self.headers)
        assert store_response.status_code == 200, f"Step 1 Failed - Create Store: {store_response.text}"
        self.test_store_id = store_response.json().get("_id") or store_response.json().get("id")
        print(f"Step 1 PASS: Created store {self.test_store_id}")
        
        # Step 2: Update Store Branding
        branding_update = {"primary_color": "#34C759", "email_footer": "Real Estate Experts"}
        branding_response = requests.put(f"{BASE_URL}/api/admin/stores/{self.test_store_id}", json=branding_update, headers=self.headers)
        assert branding_response.status_code == 200, f"Step 2 Failed - Store Branding: {branding_response.text}"
        print(f"Step 2 PASS: Updated store branding")
        
        # Step 3: Create User
        unique_email = f"test_fullwizard_{int(time.time())}@example.com"
        user_data = {
            "name": "Todd Berry",
            "email": unique_email,
            "phone": "555-333-4444",
            "password": "Welcome5678!",
            "role": "user",
            "store_id": self.test_store_id,
            "organization_id": self.test_org_id
        }
        user_response = requests.post(f"{BASE_URL}/api/admin/users", json=user_data, headers=self.headers)
        assert user_response.status_code == 200, f"Step 3 Failed - Create User: {user_response.text}"
        self.test_user_id = user_response.json().get("_id") or user_response.json().get("id")
        print(f"Step 3 PASS: Created user {self.test_user_id}")
        
        # Step 4: Update User Profile
        profile_update = {
            "title": "Real Estate Agent",
            "bio": "Helping families find their dream homes for 15 years",
            "social_instagram": "@toddberry"
        }
        profile_response = requests.put(f"{BASE_URL}/api/admin/users/{self.test_user_id}", json=profile_update, headers=self.headers)
        assert profile_response.status_code == 200, f"Step 4 Failed - User Profile: {profile_response.text}"
        print(f"Step 4 PASS: Updated user profile")
        
        # Step 5: Update Review Links
        review_links = {"google": "https://g.page/r/toddberry"}
        review_response = requests.put(f"{BASE_URL}/api/admin/stores/{self.test_store_id}/review-links", json=review_links, headers=self.headers)
        assert review_response.status_code == 200, f"Step 5 Failed - Review Links: {review_response.text}"
        print(f"Step 5 PASS: Updated review links")
        
        # Verify all data persisted
        final_user = requests.get(f"{BASE_URL}/api/admin/users/{self.test_user_id}", headers=self.headers).json()
        assert final_user.get("name") == "Todd Berry", f"Final check failed: name={final_user.get('name')}"
        assert final_user.get("title") == "Real Estate Agent", f"Final check failed: title={final_user.get('title')}"
        assert final_user.get("organization_id") == self.test_org_id, f"Final check failed: org_id mismatch"
        
        final_store = requests.get(f"{BASE_URL}/api/admin/stores/{self.test_store_id}", headers=self.headers).json()
        assert final_store.get("primary_color") == "#34C759", f"Final check failed: color={final_store.get('primary_color')}"
        
        print("FULL WIZARD FLOW TEST PASSED")


class TestSetupWizardProgressAPI:
    """Test the setup wizard progress tracking API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-User-ID": SUPER_ADMIN_USER_ID
        }
        self.test_org_id = "test_progress_org_" + str(int(time.time()))
    
    def test_get_wizard_progress_new_org(self):
        """GET /api/setup-wizard/progress/{org_id} - Returns empty progress for new org"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/progress/{self.test_org_id}", headers=self.headers)
        
        assert response.status_code == 200, f"Failed to get progress: {response.text}"
        data = response.json()
        assert data.get("current_step") == 1, f"Expected current_step=1, got {data.get('current_step')}"
        assert data.get("completed_steps") == [], f"Expected empty completed_steps"
        print(f"Progress for new org: {data}")
    
    def test_save_wizard_progress(self):
        """POST /api/setup-wizard/progress/{org_id} - Save progress"""
        progress_data = {
            "store_id": "test_store_123",
            "current_step": 3,
            "completed_steps": [1, 2],
            "completed_step_ids": ["org", "branding"],
            "completed": False
        }
        response = requests.post(f"{BASE_URL}/api/setup-wizard/progress/{self.test_org_id}", json=progress_data, headers=self.headers)
        
        assert response.status_code == 200, f"Failed to save progress: {response.text}"
        
        # Verify saved
        get_response = requests.get(f"{BASE_URL}/api/setup-wizard/progress/{self.test_org_id}", headers=self.headers)
        fetched = get_response.json()
        assert fetched.get("current_step") == 3, f"Progress not saved: {fetched}"
        print(f"Progress saved and verified: {fetched}")
    
    def test_mark_wizard_complete(self):
        """POST /api/setup-wizard/complete/{org_id} - Mark wizard complete"""
        response = requests.post(f"{BASE_URL}/api/setup-wizard/complete/{self.test_org_id}", headers=self.headers)
        
        assert response.status_code == 200, f"Failed to complete wizard: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Completion not successful: {data}"
        print(f"Wizard marked complete: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
