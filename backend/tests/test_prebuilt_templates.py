"""
Pre-built Campaign Templates API Tests
Tests the GET /api/campaigns/templates/prebuilt endpoints
Verifies 5 templates: Sold Follow-Up, Be-Back, Service Reminder, Referral Thank You, VIP Customer
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPrebuiltTemplatesEndpoints:
    """Test suite for pre-built campaign templates API"""
    
    def test_get_all_prebuilt_templates(self):
        """GET /api/campaigns/templates/prebuilt returns all 5 templates with correct metadata"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert len(templates) == 5, f"Expected 5 templates, got {len(templates)}"
        
        # Verify expected template IDs exist
        template_ids = [t['id'] for t in templates]
        expected_ids = ['sold_followup', 'be_back_nurture', 'service_reminder', 'referral_thank_you', 'vip_customer_care']
        for eid in expected_ids:
            assert eid in template_ids, f"Missing template ID: {eid}"
        
        # Verify each template has required metadata fields
        for tpl in templates:
            assert 'id' in tpl
            assert 'name' in tpl
            assert 'description' in tpl
            assert 'step_count' in tpl
            assert 'trigger_tag' in tpl
            assert 'total_duration' in tpl
            assert 'ai_enabled' in tpl
            assert 'delivery_mode' in tpl
            assert tpl['ai_enabled'] == True, f"Template {tpl['id']} should have ai_enabled=True"
            assert tpl['delivery_mode'] == 'manual', f"Template {tpl['id']} should have delivery_mode=manual"


class TestSoldFollowUpTemplate:
    """Test Sold Follow-Up template (5 steps, 1 year)"""
    
    def test_get_sold_followup_summary(self):
        """Verify sold_followup appears in listing with correct step count"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200
        
        templates = response.json()
        sold = next((t for t in templates if t['id'] == 'sold_followup'), None)
        assert sold is not None, "sold_followup template not found"
        assert sold['step_count'] == 5, f"Expected 5 steps, got {sold['step_count']}"
        assert sold['trigger_tag'] == 'sold'
        assert 'year' in sold['total_duration'].lower() or '12 month' in sold['total_duration'].lower()
    
    def test_get_sold_followup_full_details(self):
        """GET /api/campaigns/templates/prebuilt/sold_followup returns full template with 5 steps"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/sold_followup")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        tpl = response.json()
        assert tpl['id'] == 'sold_followup'
        assert tpl['name'] == 'Sold - Complete Follow-Up'
        assert tpl['ai_enabled'] == True
        assert tpl['delivery_mode'] == 'manual'
        assert 'sequences' in tpl
        
        sequences = tpl['sequences']
        assert len(sequences) == 5, f"Expected 5 steps, got {len(sequences)}"
        
        # Verify step fields exist
        for step in sequences:
            assert 'channel' in step
            assert 'ai_generated' in step
            assert 'step_context' in step
            assert 'message_template' in step
            assert 'delay_days' in step or 'delay_months' in step
    
    def test_sold_followup_delay_progression(self):
        """Sold template steps have correct delay progression (3d, 14d, 2mo, 7mo, 12mo)"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/sold_followup")
        assert response.status_code == 200
        
        sequences = response.json()['sequences']
        
        # Step 1: 3 days
        assert sequences[0]['delay_days'] == 3
        assert sequences[0]['delay_months'] == 0
        
        # Step 2: 14 days
        assert sequences[1]['delay_days'] == 14
        assert sequences[1]['delay_months'] == 0
        
        # Step 3: 2 months
        assert sequences[2]['delay_days'] == 0
        assert sequences[2]['delay_months'] == 2
        
        # Step 4: 7 months
        assert sequences[3]['delay_days'] == 0
        assert sequences[3]['delay_months'] == 7
        
        # Step 5: 12 months
        assert sequences[4]['delay_days'] == 0
        assert sequences[4]['delay_months'] == 12


class TestBeBackNurtureTemplate:
    """Test Be-Back / Working Customer template (4 steps, 1 month)"""
    
    def test_get_be_back_summary(self):
        """Verify be_back_nurture appears with correct step count"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200
        
        templates = response.json()
        be_back = next((t for t in templates if t['id'] == 'be_back_nurture'), None)
        assert be_back is not None, "be_back_nurture template not found"
        assert be_back['step_count'] == 4, f"Expected 4 steps, got {be_back['step_count']}"
        assert be_back['trigger_tag'] == 'be_back'
    
    def test_get_be_back_full_details(self):
        """GET /api/campaigns/templates/prebuilt/be_back_nurture returns full template with 4 steps"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/be_back_nurture")
        assert response.status_code == 200
        
        tpl = response.json()
        assert tpl['id'] == 'be_back_nurture'
        assert tpl['ai_enabled'] == True
        assert tpl['delivery_mode'] == 'manual'
        
        sequences = tpl['sequences']
        assert len(sequences) == 4, f"Expected 4 steps, got {len(sequences)}"
        
        for step in sequences:
            assert 'channel' in step
            assert 'ai_generated' in step
            assert 'step_context' in step
            assert 'message_template' in step


class TestServiceReminderTemplate:
    """Test Service Reminder template (3 steps)"""
    
    def test_get_service_reminder_summary(self):
        """Verify service_reminder appears with correct step count"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200
        
        templates = response.json()
        service = next((t for t in templates if t['id'] == 'service_reminder'), None)
        assert service is not None, "service_reminder template not found"
        assert service['step_count'] == 3, f"Expected 3 steps, got {service['step_count']}"
        assert service['trigger_tag'] == 'service_due'
    
    def test_get_service_reminder_full_details(self):
        """GET /api/campaigns/templates/prebuilt/service_reminder returns full template with 3 steps"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/service_reminder")
        assert response.status_code == 200
        
        tpl = response.json()
        assert tpl['id'] == 'service_reminder'
        assert tpl['ai_enabled'] == True
        assert tpl['delivery_mode'] == 'manual'
        
        sequences = tpl['sequences']
        assert len(sequences) == 3, f"Expected 3 steps, got {len(sequences)}"


class TestReferralThankYouTemplate:
    """Test Referral Thank You & Nurture template (3 steps, 3 months)"""
    
    def test_get_referral_summary(self):
        """Verify referral_thank_you appears with correct step count"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200
        
        templates = response.json()
        referral = next((t for t in templates if t['id'] == 'referral_thank_you'), None)
        assert referral is not None, "referral_thank_you template not found"
        assert referral['step_count'] == 3, f"Expected 3 steps, got {referral['step_count']}"
        assert referral['trigger_tag'] == 'referral'
    
    def test_get_referral_full_details(self):
        """GET /api/campaigns/templates/prebuilt/referral_thank_you returns full template with 3 steps"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/referral_thank_you")
        assert response.status_code == 200
        
        tpl = response.json()
        assert tpl['id'] == 'referral_thank_you'
        assert tpl['ai_enabled'] == True
        assert tpl['delivery_mode'] == 'manual'
        
        sequences = tpl['sequences']
        assert len(sequences) == 3, f"Expected 3 steps, got {len(sequences)}"
        
        # Step 3 should be at 3 months
        assert sequences[2]['delay_months'] == 3


class TestVIPCustomerCareTemplate:
    """Test VIP Customer Experience template (4 steps, 10 months total - 0,1,3,6 mo)"""
    
    def test_get_vip_summary(self):
        """Verify vip_customer_care appears with correct step count"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt")
        assert response.status_code == 200
        
        templates = response.json()
        vip = next((t for t in templates if t['id'] == 'vip_customer_care'), None)
        assert vip is not None, "vip_customer_care template not found"
        assert vip['step_count'] == 4, f"Expected 4 steps, got {vip['step_count']}"
        assert vip['trigger_tag'] == 'vip'
    
    def test_get_vip_full_details(self):
        """GET /api/campaigns/templates/prebuilt/vip_customer_care returns full template with 4 steps"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/vip_customer_care")
        assert response.status_code == 200
        
        tpl = response.json()
        assert tpl['id'] == 'vip_customer_care'
        assert tpl['ai_enabled'] == True
        assert tpl['delivery_mode'] == 'manual'
        
        sequences = tpl['sequences']
        assert len(sequences) == 4, f"Expected 4 steps, got {len(sequences)}"
        
        # Check the VIP has an email step (step 3)
        assert sequences[2]['channel'] == 'email', f"VIP step 3 should be email, got {sequences[2]['channel']}"


class TestTemplateNotFound:
    """Test 404 for nonexistent template"""
    
    def test_nonexistent_template_returns_404(self):
        """GET /api/campaigns/templates/prebuilt/nonexistent returns 404"""
        response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/nonexistent")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestTemplateStepFields:
    """Verify all templates have required step fields"""
    
    def test_all_templates_have_step_fields(self):
        """Each template step has channel, ai_generated, step_context, message_template fields"""
        template_ids = ['sold_followup', 'be_back_nurture', 'service_reminder', 'referral_thank_you', 'vip_customer_care']
        
        for tpl_id in template_ids:
            response = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/{tpl_id}")
            assert response.status_code == 200, f"Failed to get {tpl_id}"
            
            tpl = response.json()
            for i, step in enumerate(tpl['sequences']):
                assert 'channel' in step, f"{tpl_id} step {i+1} missing 'channel'"
                assert 'ai_generated' in step, f"{tpl_id} step {i+1} missing 'ai_generated'"
                assert 'step_context' in step, f"{tpl_id} step {i+1} missing 'step_context'"
                assert 'message_template' in step, f"{tpl_id} step {i+1} missing 'message_template'"
                assert step['channel'] in ['sms', 'email'], f"{tpl_id} step {i+1} has invalid channel: {step['channel']}"
