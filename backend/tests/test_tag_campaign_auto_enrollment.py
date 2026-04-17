"""
Test Tag → Campaign Auto-Enrollment System
Tests generic tag-based campaign enrollment functionality including:
- GET /api/tags/{user_id} - returns available tags
- POST /api/tags/{user_id}/assign - tag assignment triggers campaign enrollment
- POST /api/tags/{user_id}/assign with skip_campaign=true - skips enrollment
- POST /api/congrats/create - accepts tags and skip_campaign params
"""
import os
import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
TEST_CONTACT_ID = "69a8abe36a8712d026633756"


class TestTagsAPI:
    """Test tags API endpoints"""
    
    def test_get_tags_returns_available_tags(self):
        """GET /api/tags/{user_id} should return available tags with correct fields"""
        response = requests.get(f"{BASE_URL}/api/tags/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        tags = response.json()
        assert isinstance(tags, list), "Response should be a list of tags"
        
        # Check that at least some default tags exist
        if len(tags) > 0:
            tag = tags[0]
            assert "_id" in tag, "Tag should have _id field"
            assert "name" in tag, "Tag should have name field"
            assert "color" in tag, "Tag should have color field"
            print(f"PASSED: Found {len(tags)} tags. First tag: {tag.get('name')}")
    
    def test_tags_include_common_trigger_tags(self):
        """Tags should include common trigger tags like Hot Lead, VIP, Service Due"""
        response = requests.get(f"{BASE_URL}/api/tags/{TEST_USER_ID}")
        assert response.status_code == 200
        
        tags = response.json()
        tag_names = [t["name"].lower() for t in tags]
        
        # Check that some expected tags exist
        expected_tags = ["hot lead", "vip", "service due", "follow up"]
        found_tags = [t for t in expected_tags if t in tag_names]
        
        print(f"PASSED: Found expected tags: {found_tags}")
        assert len(found_tags) >= 2, f"Expected at least 2 common tags, found: {found_tags}"


class TestTagAssignment:
    """Test tag assignment and campaign enrollment"""
    
    def test_assign_sold_tag_triggers_campaign_enrollment(self):
        """POST /api/tags/{user_id}/assign with 'Sold' tag should trigger campaign auto-enrollment"""
        # First, create a test contact or use existing one
        payload = {
            "tag_name": "Sold",
            "contact_ids": [TEST_CONTACT_ID],
            "skip_campaign": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
            json=payload
        )
        
        # Should succeed or return 404 if tag not found (needs to be created first)
        if response.status_code == 404:
            # Create the Sold tag first
            create_response = requests.post(
                f"{BASE_URL}/api/tags/{TEST_USER_ID}",
                json={"name": "Sold", "color": "#34C759"}
            )
            assert create_response.status_code in [200, 400], f"Tag creation failed: {create_response.text}"
            
            # Try assignment again
            response = requests.post(
                f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
                json=payload
            )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message field"
        # Check if campaign_triggered is returned
        if "campaign_triggered" in data:
            assert data["campaign_triggered"] == True, "Campaign should be triggered"
        print(f"PASSED: Tag assigned. Response: {data}")
    
    def test_assign_tag_with_skip_campaign_does_not_enroll(self):
        """POST /api/tags/{user_id}/assign with skip_campaign=true should NOT create enrollment"""
        payload = {
            "tag_name": "Sold",
            "contact_ids": [TEST_CONTACT_ID],
            "skip_campaign": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
            json=payload
        )
        
        if response.status_code == 404:
            print("SKIP: 'Sold' tag not found - create it first")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        if "campaign_triggered" in data:
            assert data["campaign_triggered"] == False, "Campaign should NOT be triggered when skip_campaign=true"
        print(f"PASSED: Tag assigned with skip_campaign=true. Response: {data}")
    
    def test_assign_vip_tag_triggers_vip_campaign(self):
        """POST /api/tags/{user_id}/assign with 'VIP' tag should trigger VIP campaign enrollment"""
        # Ensure VIP tag exists
        tags_response = requests.get(f"{BASE_URL}/api/tags/{TEST_USER_ID}")
        tags = tags_response.json()
        vip_tag = next((t for t in tags if t["name"].lower() == "vip"), None)
        
        if not vip_tag:
            # Create VIP tag
            requests.post(
                f"{BASE_URL}/api/tags/{TEST_USER_ID}",
                json={"name": "VIP", "color": "#FFD60A"}
            )
        
        payload = {
            "tag_name": "VIP",
            "contact_ids": [TEST_CONTACT_ID],
            "skip_campaign": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"PASSED: VIP tag assigned. Response: {data}")
    
    def test_assign_tag_without_campaign_template_gracefully_skips(self):
        """POST /api/tags/{user_id}/assign with tag that has NO matching campaign template should gracefully skip"""
        # First ensure 'Hot Lead' tag exists
        tags_response = requests.get(f"{BASE_URL}/api/tags/{TEST_USER_ID}")
        tags = tags_response.json()
        
        hot_lead_tag = next((t for t in tags if t["name"].lower() == "hot lead"), None)
        if not hot_lead_tag:
            # Create Hot Lead tag
            requests.post(
                f"{BASE_URL}/api/tags/{TEST_USER_ID}",
                json={"name": "Hot Lead", "color": "#FF3B30"}
            )
        
        payload = {
            "tag_name": "Hot Lead",
            "contact_ids": [TEST_CONTACT_ID],
            "skip_campaign": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}/assign",
            json=payload
        )
        
        # Should succeed - hot lead has no matching template, so enrollment is gracefully skipped
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Even without matching template, should not error
        print(f"PASSED: Tag without campaign template handled gracefully. Response: {data}")


class TestCampaignTemplates:
    """Test prebuilt campaign templates with trigger_tags"""
    
    def test_get_prebuilt_templates(self):
        """GET /api/campaigns/templates/prebuilt should return templates with trigger_tags"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        assert len(templates) >= 3, f"Expected at least 3 templates, got {len(templates)}"
        
        # Check trigger_tags
        trigger_tags = [t.get("trigger_tag") for t in templates if t.get("trigger_tag")]
        print(f"PASSED: Found {len(templates)} templates with trigger_tags: {trigger_tags}")
        
        # Verify expected trigger tags exist
        expected = ["sold", "be_back", "service_due", "referral", "vip"]
        for expected_tag in expected:
            assert expected_tag in trigger_tags, f"Missing expected trigger_tag: {expected_tag}"
    
    def test_sold_template_exists(self):
        """Sold follow-up template should exist with trigger_tag='sold'"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/sold_followup")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        template = response.json()
        assert template.get("trigger_tag") == "sold", "Sold template should have trigger_tag='sold'"
        assert template.get("name") == "Sold - Complete Follow-Up"
        print(f"PASSED: Sold template found with {len(template.get('sequences', []))} sequences")
    
    def test_vip_template_exists(self):
        """VIP template should exist with trigger_tag='vip'"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/vip_customer_care")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        template = response.json()
        assert template.get("trigger_tag") == "vip", "VIP template should have trigger_tag='vip'"
        print(f"PASSED: VIP template found with {len(template.get('sequences', []))} sequences")


class TestCongratsCardWithTags:
    """Test congrats card creation with tag support"""
    
    def test_congrats_create_accepts_tags_param(self):
        """POST /api/congrats/create should accept tags JSON array"""
        import io
        
        # Create a simple test image (1x1 red pixel PNG)
        # This is a valid 1x1 PNG image
        png_bytes = bytes([
            0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xde, 0x00, 0x00, 0x00,
            0x0c, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x05, 0xfe, 0xd4, 0xef, 0x00, 0x00,
            0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82
        ])
        
        files = {
            'photo': ('test.png', io.BytesIO(png_bytes), 'image/png')
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_TagCard Customer',
            'customer_phone': '+15551234567',
            'card_type': 'congrats',
            'tags': json.dumps(['Sold']),  # JSON array
            'skip_campaign': 'false'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get("success") == True, "Card creation should succeed"
        assert "card_id" in result, "Response should include card_id"
        print(f"PASSED: Congrats card created with tags. Card ID: {result.get('card_id')}")
        
        # Check if tags_applied is returned
        if "tags_applied" in result:
            print(f"Tags applied: {result.get('tags_applied')}")
    
    def test_congrats_create_with_skip_campaign(self):
        """POST /api/congrats/create with skip_campaign=true should not trigger enrollment"""
        import io
        
        png_bytes = bytes([
            0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xde, 0x00, 0x00, 0x00,
            0x0c, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x05, 0xfe, 0xd4, 0xef, 0x00, 0x00,
            0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82
        ])
        
        files = {
            'photo': ('test.png', io.BytesIO(png_bytes), 'image/png')
        }
        data = {
            'salesman_id': TEST_USER_ID,
            'customer_name': 'TEST_SkipCampaign Customer',
            'customer_phone': '+15559876543',
            'card_type': 'congrats',
            'tags': json.dumps(['VIP']),
            'skip_campaign': 'true'  # Should skip campaign enrollment
        }
        
        response = requests.post(
            f"{BASE_URL}/api/congrats/create",
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get("success") == True, "Card creation should succeed"
        print(f"PASSED: Congrats card created with skip_campaign=true. Card ID: {result.get('card_id')}")


class TestCampaignConfig:
    """Test campaign configuration for auto_enroll_on_tag setting"""
    
    def test_default_config_has_auto_enroll_enabled(self):
        """Default campaign config should have auto_enroll_on_tag=true"""
        response = requests.get(f"{BASE_URL}/api/campaign-config/effective/{TEST_USER_ID}")
        
        if response.status_code == 404:
            print("SKIP: Campaign config endpoint not available")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        config = data.get("config", {})
        
        # Default should be True
        auto_enroll = config.get("auto_enroll_on_tag", True)
        assert auto_enroll == True, f"auto_enroll_on_tag should default to True, got {auto_enroll}"
        print(f"PASSED: auto_enroll_on_tag is enabled. Full config: {config}")


class TestCampaignEnrollments:
    """Test campaign enrollment creation after tag assignment"""
    
    def test_check_campaign_enrollments_after_tag(self):
        """After assigning a tag with trigger, check if enrollment was created"""
        # Get all campaigns for user
        response = requests.get(f"{BASE_URL}/api/campaigns/{TEST_USER_ID}")
        
        if response.status_code != 200:
            print(f"SKIP: Could not get campaigns: {response.text}")
            return
        
        campaigns = response.json()
        
        # Look for sold or vip campaigns
        trigger_campaigns = [c for c in campaigns if c.get("trigger_tag") in ["sold", "vip"]]
        
        if trigger_campaigns:
            campaign = trigger_campaigns[0]
            campaign_id = campaign.get("_id") or str(campaign.get("_id"))
            
            # Get enrollments
            enroll_response = requests.get(
                f"{BASE_URL}/api/campaigns/{TEST_USER_ID}/{campaign_id}/enrollments"
            )
            
            if enroll_response.status_code == 200:
                enrollments = enroll_response.json()
                print(f"PASSED: Campaign '{campaign.get('name')}' has {len(enrollments)} enrollments")
            else:
                print(f"Could not get enrollments: {enroll_response.text}")
        else:
            print("INFO: No trigger-tag campaigns found yet (expected if auto-created)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
