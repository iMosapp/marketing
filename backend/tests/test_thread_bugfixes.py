"""
Test thread page bug fixes:
1. /api/messages/conversation/{id}/info returns contact_id field
2. Contact navigation uses contact_id not conversation_id
3. Intel refresh scroll to top (frontend only - verified via code review)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConversationInfoEndpoint:
    """Test the conversation info endpoint returns contact_id"""
    
    # Known test data from main agent context
    CONVERSATION_ID = "69a15f29957bacd218fed55d"
    EXPECTED_CONTACT_ID = "69a0c06f7626f14d125f8c34"
    EXPECTED_CONTACT_NAME = "Forest Ward"
    
    def test_conversation_info_returns_contact_id(self):
        """Bug 1: Verify contact_id is returned in conversation info"""
        response = requests.get(f"{BASE_URL}/api/messages/conversation/{self.CONVERSATION_ID}/info")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Data assertions
        data = response.json()
        
        # Verify contact_id field exists and has correct value
        assert "contact_id" in data, "contact_id field missing from response"
        assert data["contact_id"] == self.EXPECTED_CONTACT_ID, \
            f"Expected contact_id {self.EXPECTED_CONTACT_ID}, got {data.get('contact_id')}"
        
        # Verify contact_id is different from conversation _id (this was the bug)
        assert data["contact_id"] != data["_id"], \
            "Bug not fixed: contact_id should be different from conversation _id"
        
        print(f"PASS: contact_id ({data['contact_id']}) is correctly different from conversation _id ({data['_id']})")
    
    def test_conversation_info_has_all_fields(self):
        """Verify all expected fields are present in conversation info"""
        response = requests.get(f"{BASE_URL}/api/messages/conversation/{self.CONVERSATION_ID}/info")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields
        required_fields = ["_id", "contact_name", "contact_phone", "status", "contact_id"]
        for field in required_fields:
            assert field in data, f"Required field '{field}' missing from response"
        
        # Verify contact name is correct
        assert data["contact_name"] == self.EXPECTED_CONTACT_NAME, \
            f"Expected contact_name '{self.EXPECTED_CONTACT_NAME}', got '{data.get('contact_name')}'"
        
        print(f"PASS: All required fields present: {required_fields}")
    
    def test_nonexistent_conversation_returns_404(self):
        """Verify 404 for non-existent conversation"""
        fake_id = "000000000000000000000000"
        response = requests.get(f"{BASE_URL}/api/messages/conversation/{fake_id}/info")
        
        assert response.status_code == 404, f"Expected 404 for non-existent conversation, got {response.status_code}"
        print("PASS: Non-existent conversation returns 404")


class TestThreadPageCodeReview:
    """Code review tests - verify the frontend code changes are correct"""
    
    def test_contact_id_state_variable_exists(self):
        """Verify contactIdForNav state variable exists in thread page"""
        thread_file = "/app/frontend/app/thread/[id].tsx"
        
        with open(thread_file, 'r') as f:
            content = f.read()
        
        # Line 520: contactIdForNav state
        assert "contactIdForNav" in content, "contactIdForNav state variable not found"
        assert "useState<string | null>(null)" in content, "contactIdForNav not properly typed"
        
        print("PASS: contactIdForNav state variable exists and is properly typed")
    
    def test_contact_id_set_from_api(self):
        """Verify contactIdForNav is set from API response"""
        thread_file = "/app/frontend/app/thread/[id].tsx"
        
        with open(thread_file, 'r') as f:
            content = f.read()
        
        # Line 536: setContactIdForNav from API
        assert "setContactIdForNav(response.data.contact_id)" in content, \
            "contactIdForNav not being set from API response"
        
        print("PASS: contactIdForNav is set from API response.data.contact_id")
    
    def test_navigation_uses_contact_id(self):
        """Verify navigation uses contactIdForNav instead of conversation id"""
        thread_file = "/app/frontend/app/thread/[id].tsx"
        
        with open(thread_file, 'r') as f:
            content = f.read()
        
        # Line 1666: Navigation uses contactIdForNav || id
        # Must use contactIdForNav first, fall back to id
        assert "contactIdForNav || id" in content, \
            "Navigation should use contactIdForNav || id pattern"
        assert "/contact/${contactIdForNav || id}" in content or \
               '`/contact/${contactIdForNav || id}`' in content, \
            "Contact navigation not using contactIdForNav"
        
        print("PASS: Navigation uses contactIdForNav with fallback to id")
    
    def test_data_testid_exists(self):
        """Verify thread-contact-name-link data-testid exists"""
        thread_file = "/app/frontend/app/thread/[id].tsx"
        
        with open(thread_file, 'r') as f:
            content = f.read()
        
        assert 'data-testid="thread-contact-name-link"' in content, \
            "thread-contact-name-link data-testid not found"
        
        print("PASS: thread-contact-name-link data-testid exists")
    
    def test_scroll_to_top_in_generate_intel(self):
        """Bug 3: Verify window.scrollTo is called after generateIntel"""
        thread_file = "/app/frontend/app/thread/[id].tsx"
        
        with open(thread_file, 'r') as f:
            content = f.read()
        
        # Look for scrollTo in generateIntel function context
        assert "window.scrollTo({ top: 0, behavior: 'smooth' })" in content or \
               "window.scrollTo({top: 0, behavior: 'smooth'})" in content, \
            "window.scrollTo call not found for intel refresh"
        
        # Verify it's in generateIntel context (look for nearby function name)
        generate_intel_start = content.find("const generateIntel = async")
        if generate_intel_start != -1:
            # Find next function or end of generateIntel
            generate_intel_section = content[generate_intel_start:generate_intel_start + 2000]
            assert "scrollTo" in generate_intel_section, \
                "scrollTo not found within generateIntel function"
        
        print("PASS: window.scrollTo is called in generateIntel function")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
