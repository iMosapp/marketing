"""
Test seed_defaults functionality for new user provisioning.
Tests: signup auto-seeding, backfill endpoint, review/social templates CRUD,
date trigger format, campaign sequences, and store defaults.
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")

# Test user prefix for cleanup
TEST_PREFIX = "TEST_SEED_"


class TestSeedDefaults:
    """Tests for default package auto-provisioning on signup"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create requests session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def admin_login(self, session):
        """Login as super admin and get user info"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        return data["user"]
    
    @pytest.fixture(scope="class")
    def test_user(self, session):
        """Create a test user via signup and return user_id"""
        timestamp = int(time.time())
        test_email = f"{TEST_PREFIX}user_{timestamp}@test.com"
        
        response = session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": f"{TEST_PREFIX}User {timestamp}",
            "phone": "+15551234567",
            "account_type": "independent"  # Gets active status immediately
        })
        assert response.status_code == 200, f"Signup failed: {response.text}"
        data = response.json()
        user_id = data.get("_id")
        assert user_id, "No user_id returned from signup"
        
        yield user_id
        
        # Cleanup: Delete test user and their seeded data
        try:
            session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
        except Exception:
            pass
    
    # ==================== Test 1: Signup creates default data ====================
    
    def test_signup_creates_sms_templates(self, session, test_user):
        """Verify signup creates 12 SMS templates for new user"""
        response = session.get(f"{BASE_URL}/api/templates/{test_user}")
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        templates = response.json()
        
        # Filter to only default templates (is_default=True)
        default_templates = [t for t in templates if t.get("is_default")]
        
        assert len(default_templates) == 12, f"Expected 12 SMS templates, got {len(default_templates)}: {[t.get('name') for t in default_templates]}"
        
        # Verify expected template names
        expected_names = ["Welcome", "Add Socials Nudge", "Review Ask", "Review Follow-Up", 
                         "Referral Ask", "Check-In", "Birthday", "Anniversary", 
                         "Congrats / Sold", "Reactivation", "Winback After Feedback", "Just Because"]
        actual_names = [t.get("name") for t in default_templates]
        for name in expected_names:
            assert name in actual_names, f"Missing SMS template: {name}"
        print(f"✓ 12 SMS templates created: {actual_names}")
    
    def test_signup_creates_email_templates(self, session, test_user):
        """Verify signup creates 8 email templates for new user"""
        response = session.get(f"{BASE_URL}/api/email/templates/{test_user}")
        assert response.status_code == 200, f"Failed to get email templates: {response.text}"
        templates = response.json()
        
        # Filter to only default templates
        default_templates = [t for t in templates if t.get("is_default")]
        
        assert len(default_templates) == 8, f"Expected 8 email templates, got {len(default_templates)}"
        
        # Verify expected template names
        expected_names = ["Welcome + Card Setup", "Digital Business Card", "Review Request",
                         "Follow-Up / Check-In", "Referral Request", "Congrats / Purchase",
                         "Reputation Rescue", "Reactivation"]
        actual_names = [t.get("name") for t in default_templates]
        for name in expected_names:
            assert name in actual_names, f"Missing email template: {name}"
        print(f"✓ 8 email templates created: {actual_names}")
    
    def test_signup_creates_campaigns(self, session, test_user):
        """Verify signup creates 6 campaigns for new user"""
        response = session.get(f"{BASE_URL}/api/campaigns/{test_user}")
        assert response.status_code == 200, f"Failed to get campaigns: {response.text}"
        campaigns = response.json()
        
        assert len(campaigns) >= 6, f"Expected at least 6 campaigns, got {len(campaigns)}"
        
        # Verify expected campaign names
        expected_names = ["New Account Onboarding", "First 10 Reviews Sprint", 
                         "Ongoing Relationship Touches", "Post-Purchase Follow-Up",
                         "Reputation Rescue", "Social Growth Loop"]
        actual_names = [c.get("name") for c in campaigns]
        for name in expected_names:
            assert name in actual_names, f"Missing campaign: {name}"
        print(f"✓ 6 campaigns created: {actual_names}")
    
    def test_signup_creates_date_triggers(self, session, test_user):
        """Verify signup creates 6 date triggers for new user"""
        response = session.get(f"{BASE_URL}/api/date-triggers/{test_user}/config")
        assert response.status_code == 200, f"Failed to get date triggers: {response.text}"
        triggers = response.json()
        
        assert len(triggers) >= 6, f"Expected at least 6 date triggers, got {len(triggers)}"
        
        # Verify expected trigger types with correct format
        expected_types = ["birthday", "anniversary", "sold_date", 
                         "holiday_thanksgiving", "holiday_christmas", "holiday_new_years"]
        actual_types = [t.get("trigger_type") for t in triggers]
        for trigger_type in expected_types:
            assert trigger_type in actual_types, f"Missing date trigger: {trigger_type}"
        print(f"✓ 6 date triggers created: {actual_types}")
    
    def test_signup_creates_review_templates(self, session, test_user):
        """Verify signup creates 3 review response templates"""
        response = session.get(f"{BASE_URL}/api/review-templates/{test_user}")
        assert response.status_code == 200, f"Failed to get review templates: {response.text}"
        templates = response.json()
        
        # Filter to defaults
        default_templates = [t for t in templates if t.get("is_default")]
        
        assert len(default_templates) == 3, f"Expected 3 review templates, got {len(default_templates)}"
        
        # Verify rating ranges
        expected_ranges = ["5", "3-4", "1-2"]
        actual_ranges = [t.get("rating_range") for t in default_templates]
        for rating in expected_ranges:
            assert rating in actual_ranges, f"Missing review template for rating: {rating}"
        print(f"✓ 3 review response templates created: {[t.get('name') for t in default_templates]}")
    
    def test_signup_creates_social_templates(self, session, test_user):
        """Verify signup creates 5 social content templates"""
        response = session.get(f"{BASE_URL}/api/social-templates/{test_user}")
        assert response.status_code == 200, f"Failed to get social templates: {response.text}"
        templates = response.json()
        
        # Filter to defaults
        default_templates = [t for t in templates if t.get("is_default")]
        
        assert len(default_templates) == 5, f"Expected 5 social templates, got {len(default_templates)}"
        
        # Verify expected categories
        expected_categories = ["intro", "value", "proof", "community", "offer"]
        actual_categories = [t.get("category") for t in default_templates]
        for cat in expected_categories:
            assert cat in actual_categories, f"Missing social template category: {cat}"
        print(f"✓ 5 social templates created: {[t.get('name') for t in default_templates]}")
    
    # ==================== Test 2: Backfill endpoint ====================
    
    def test_backfill_endpoint_works(self, session, admin_login):
        """Test POST /api/admin/seed/backfill-all endpoint"""
        session.headers.update({"X-User-ID": admin_login["_id"]})
        response = session.post(f"{BASE_URL}/api/admin/seed/backfill-all")
        assert response.status_code == 200, f"Backfill failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "success", f"Backfill status not success: {data}"
        assert "users" in data, "Backfill should return users count"
        print(f"✓ Backfill endpoint returned: {data}")
    
    def test_backfill_is_idempotent(self, session, admin_login):
        """Verify running backfill twice doesn't create duplicates"""
        session.headers.update({"X-User-ID": admin_login["_id"]})
        
        # First run
        response1 = session.post(f"{BASE_URL}/api/admin/seed/backfill-all")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second run - should not add new data
        response2 = session.post(f"{BASE_URL}/api/admin/seed/backfill-all")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Counts for sms_templates, email_templates, campaigns, etc should be 0 on second run
        # because data already exists
        assert data2.get("sms_templates", 0) == 0, f"Backfill created duplicates: {data2}"
        assert data2.get("email_templates", 0) == 0, f"Backfill created duplicates: {data2}"
        print(f"✓ Backfill is idempotent - second run created 0 new records")
    
    # ==================== Test 3: Review templates CRUD ====================
    
    def test_review_templates_crud_create(self, session, test_user):
        """Test POST /api/review-templates/{user_id}"""
        response = session.post(f"{BASE_URL}/api/review-templates/{test_user}", json={
            "name": "Custom 5-Star Reply",
            "rating_range": "5",
            "content": "Thank you so much for the amazing review!"
        })
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert data.get("_id"), "Should return created template with _id"
        assert data.get("name") == "Custom 5-Star Reply"
        print(f"✓ Created review template: {data.get('_id')}")
        return data.get("_id")
    
    def test_review_templates_crud_read(self, session, test_user):
        """Test GET /api/review-templates/{user_id}"""
        response = session.get(f"{BASE_URL}/api/review-templates/{test_user}")
        assert response.status_code == 200, f"Read failed: {response.text}"
        templates = response.json()
        assert isinstance(templates, list), "Should return list"
        print(f"✓ Read review templates: {len(templates)} found")
    
    def test_review_templates_crud_update(self, session, test_user):
        """Test PUT /api/review-templates/{user_id}/{id}"""
        # First get existing template
        response = session.get(f"{BASE_URL}/api/review-templates/{test_user}")
        templates = response.json()
        if not templates:
            pytest.skip("No templates to update")
        
        template_id = templates[0]["_id"]
        response = session.put(f"{BASE_URL}/api/review-templates/{test_user}/{template_id}", json={
            "content": "Updated content for review response"
        })
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data.get("content") == "Updated content for review response"
        print(f"✓ Updated review template: {template_id}")
    
    def test_review_templates_crud_delete(self, session, test_user):
        """Test DELETE /api/review-templates/{user_id}/{id}"""
        # Create one to delete
        create_resp = session.post(f"{BASE_URL}/api/review-templates/{test_user}", json={
            "name": "To Delete",
            "rating_range": "3",
            "content": "Will be deleted"
        })
        template_id = create_resp.json().get("_id")
        
        response = session.delete(f"{BASE_URL}/api/review-templates/{test_user}/{template_id}")
        assert response.status_code == 200, f"Delete failed: {response.text}"
        
        # Verify deleted
        get_resp = session.get(f"{BASE_URL}/api/review-templates/{test_user}/{template_id}")
        assert get_resp.status_code == 404, "Template should be deleted"
        print(f"✓ Deleted review template: {template_id}")
    
    # ==================== Test 4: Social templates CRUD ====================
    
    def test_social_templates_crud_create(self, session, test_user):
        """Test POST /api/social-templates/{user_id}"""
        response = session.post(f"{BASE_URL}/api/social-templates/{test_user}", json={
            "name": "Custom Promo Post",
            "category": "promo",
            "content": "Check out our latest offer!"
        })
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert data.get("_id"), "Should return created template with _id"
        print(f"✓ Created social template: {data.get('_id')}")
    
    def test_social_templates_crud_read(self, session, test_user):
        """Test GET /api/social-templates/{user_id}"""
        response = session.get(f"{BASE_URL}/api/social-templates/{test_user}")
        assert response.status_code == 200, f"Read failed: {response.text}"
        templates = response.json()
        assert isinstance(templates, list), "Should return list"
        print(f"✓ Read social templates: {len(templates)} found")
    
    def test_social_templates_crud_update(self, session, test_user):
        """Test PUT /api/social-templates/{user_id}/{id}"""
        response = session.get(f"{BASE_URL}/api/social-templates/{test_user}")
        templates = response.json()
        if not templates:
            pytest.skip("No templates to update")
        
        template_id = templates[0]["_id"]
        response = session.put(f"{BASE_URL}/api/social-templates/{test_user}/{template_id}", json={
            "content": "Updated social post content"
        })
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data.get("content") == "Updated social post content"
        print(f"✓ Updated social template: {template_id}")
    
    def test_social_templates_crud_delete(self, session, test_user):
        """Test DELETE /api/social-templates/{user_id}/{id}"""
        create_resp = session.post(f"{BASE_URL}/api/social-templates/{test_user}", json={
            "name": "To Delete Social",
            "category": "test",
            "content": "Will be deleted"
        })
        template_id = create_resp.json().get("_id")
        
        response = session.delete(f"{BASE_URL}/api/social-templates/{test_user}/{template_id}")
        assert response.status_code == 200, f"Delete failed: {response.text}"
        print(f"✓ Deleted social template: {template_id}")
    
    # ==================== Test 5: Date trigger format ====================
    
    def test_date_trigger_format_holidays(self, session, test_user):
        """Verify holiday triggers use correct format: holiday_thanksgiving, holiday_christmas, holiday_new_years"""
        response = session.get(f"{BASE_URL}/api/date-triggers/{test_user}/config")
        assert response.status_code == 200
        triggers = response.json()
        
        # Check that holiday triggers have the correct format
        holiday_triggers = [t for t in triggers if t.get("trigger_type", "").startswith("holiday_")]
        
        assert len(holiday_triggers) >= 3, f"Expected at least 3 holiday triggers, got {len(holiday_triggers)}"
        
        # Verify no generic "holiday" trigger type (should be holiday_<id>)
        for trigger in triggers:
            if "holiday" in trigger.get("trigger_type", "").lower():
                assert trigger["trigger_type"].startswith("holiday_"), \
                    f"Holiday trigger should be holiday_<id>, got: {trigger['trigger_type']}"
        
        # Verify specific holiday IDs
        trigger_types = [t.get("trigger_type") for t in triggers]
        assert "holiday_thanksgiving" in trigger_types, "Missing holiday_thanksgiving"
        assert "holiday_christmas" in trigger_types, "Missing holiday_christmas"
        assert "holiday_new_years" in trigger_types, "Missing holiday_new_years"
        print(f"✓ Holiday triggers use correct format: {[t for t in trigger_types if 'holiday' in t]}")
    
    # ==================== Test 6: Campaign sequences ====================
    
    def test_campaign_sequences_have_correct_fields(self, session, test_user):
        """Verify campaigns have multi-step sequences with delay_days, delay_months, action_type"""
        response = session.get(f"{BASE_URL}/api/campaigns/{test_user}")
        assert response.status_code == 200
        campaigns = response.json()
        
        # Check each campaign has sequences with required fields
        for campaign in campaigns:
            sequences = campaign.get("sequences", [])
            assert len(sequences) > 0, f"Campaign '{campaign.get('name')}' has no sequences"
            
            for seq in sequences:
                assert "step" in seq, f"Sequence missing 'step' field: {seq}"
                assert "action_type" in seq, f"Sequence missing 'action_type' field: {seq}"
                assert "delay_days" in seq, f"Sequence missing 'delay_days' field: {seq}"
                assert "delay_months" in seq, f"Sequence missing 'delay_months' field: {seq}"
        
        # Specifically check Ongoing Relationship Touches uses delay_months
        relationship_campaign = next((c for c in campaigns if c.get("name") == "Ongoing Relationship Touches"), None)
        if relationship_campaign:
            has_monthly_delays = any(
                seq.get("delay_months", 0) > 0 
                for seq in relationship_campaign.get("sequences", [])
            )
            assert has_monthly_delays, "Ongoing Relationship Touches should use delay_months"
            print(f"✓ Ongoing Relationship Touches has {len(relationship_campaign.get('sequences', []))} steps with monthly delays")
        
        print(f"✓ All {len(campaigns)} campaigns have proper sequence fields")
    
    def test_campaign_send_card_action_type(self, session, test_user):
        """Verify Post-Purchase Follow-Up has send_card action type"""
        response = session.get(f"{BASE_URL}/api/campaigns/{test_user}")
        campaigns = response.json()
        
        post_purchase = next((c for c in campaigns if c.get("name") == "Post-Purchase Follow-Up"), None)
        if post_purchase:
            sequences = post_purchase.get("sequences", [])
            has_send_card = any(seq.get("action_type") == "send_card" for seq in sequences)
            assert has_send_card, "Post-Purchase should have send_card action"
            
            send_card_seq = next((s for s in sequences if s.get("action_type") == "send_card"), None)
            assert send_card_seq.get("card_type") == "congrats", "send_card should be congrats type"
            print(f"✓ Post-Purchase Follow-Up has send_card action with card_type=congrats")
        else:
            print("⚠ Post-Purchase Follow-Up campaign not found")


class TestAdminDataCreation:
    """Test admin-created users also get seeded data"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def admin_login(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["user"]
    
    def test_admin_created_user_gets_defaults(self, session, admin_login):
        """Verify users created via /api/admin/users also get seeded defaults"""
        timestamp = int(time.time())
        
        session.headers.update({"X-User-ID": admin_login["_id"]})
        response = session.post(f"{BASE_URL}/api/admin/users", json={
            "email": f"{TEST_PREFIX}admin_user_{timestamp}@test.com",
            "password": "TestPass123!",
            "name": f"{TEST_PREFIX}Admin Created User",
            "role": "user"
        })
        assert response.status_code == 200, f"Admin user creation failed: {response.text}"
        user_id = response.json().get("_id")
        
        # Verify SMS templates were created
        templates_resp = session.get(f"{BASE_URL}/api/templates/{user_id}")
        assert templates_resp.status_code == 200
        templates = templates_resp.json()
        default_templates = [t for t in templates if t.get("is_default")]
        assert len(default_templates) == 12, f"Admin-created user should have 12 SMS templates, got {len(default_templates)}"
        
        # Verify campaigns were created
        campaigns_resp = session.get(f"{BASE_URL}/api/campaigns/{user_id}")
        assert campaigns_resp.status_code == 200
        campaigns = campaigns_resp.json()
        assert len(campaigns) >= 6, f"Admin-created user should have 6 campaigns, got {len(campaigns)}"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
        
        print(f"✓ Admin-created user got all defaults: {len(default_templates)} SMS templates, {len(campaigns)} campaigns")


class TestStoreDefaults:
    """Test store-level defaults (tags, lead sources)"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def admin_login(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["user"]
    
    def test_store_defaults_defined(self):
        """Verify DEFAULT_TAGS and DEFAULT_LEAD_SOURCES exist in seed_defaults.py"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.seed_defaults import DEFAULT_TAGS, DEFAULT_LEAD_SOURCES
        
        assert len(DEFAULT_TAGS) == 8, f"Expected 8 default tags, got {len(DEFAULT_TAGS)}"
        assert len(DEFAULT_LEAD_SOURCES) == 8, f"Expected 8 default lead sources, got {len(DEFAULT_LEAD_SOURCES)}"
        
        # Verify tag fields
        for tag in DEFAULT_TAGS:
            assert "name" in tag, f"Tag missing name: {tag}"
            assert "color" in tag, f"Tag missing color: {tag}"
        
        # Verify lead source fields
        for source in DEFAULT_LEAD_SOURCES:
            assert "name" in source, f"Lead source missing name: {source}"
            assert "type" in source, f"Lead source missing type: {source}"
        
        print(f"✓ Store defaults defined: {len(DEFAULT_TAGS)} tags, {len(DEFAULT_LEAD_SOURCES)} lead sources")


class TestHealthCheck:
    """Basic health check to ensure API is running"""
    
    def test_api_health(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ API is healthy: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
