"""
Test Legal API endpoints - Terms of Service, Privacy Policy
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://reports-analytics-1.preview.emergentagent.com')


class TestLegalEndpoints:
    """Test legal document endpoints"""

    def test_get_terms_of_service(self):
        """Test GET /api/legal/terms returns TOS content"""
        response = requests.get(f"{BASE_URL}/api/legal/terms")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "title" in data, "Response missing 'title' field"
        assert "last_updated" in data, "Response missing 'last_updated' field"
        assert "content" in data, "Response missing 'content' field"
        
        assert data["title"] == "Terms of Service"
        assert "February 19, 2026" in data["last_updated"]
        assert len(data["content"]) > 1000, "TOS content should be comprehensive"
        assert "MVPLine" in data["content"], "TOS should mention company name"
        assert "Terms of Service" in data["content"]
        print(f"✓ TOS endpoint returns {len(data['content'])} characters")

    def test_get_privacy_policy(self):
        """Test GET /api/legal/privacy returns Privacy Policy content"""
        response = requests.get(f"{BASE_URL}/api/legal/privacy")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "title" in data, "Response missing 'title' field"
        assert "last_updated" in data, "Response missing 'last_updated' field"
        assert "content" in data, "Response missing 'content' field"
        
        assert data["title"] == "Privacy Policy"
        assert "February 19, 2026" in data["last_updated"]
        assert len(data["content"]) > 1000, "Privacy policy content should be comprehensive"
        assert "MVPLine" in data["content"], "Privacy policy should mention company name"
        assert "Privacy Policy" in data["content"]
        print(f"✓ Privacy Policy endpoint returns {len(data['content'])} characters")

    def test_get_customer_terms(self):
        """Test GET /api/legal/customer-terms returns Customer Terms content"""
        response = requests.get(f"{BASE_URL}/api/legal/customer-terms")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "title" in data
        assert "last_updated" in data
        assert "content" in data
        
        assert data["title"] == "Customer Terms of Use"
        assert len(data["content"]) > 500, "Customer terms should have content"
        print(f"✓ Customer Terms endpoint returns {len(data['content'])} characters")

    def test_get_all_legal_documents(self):
        """Test GET /api/legal/all returns all legal documents"""
        response = requests.get(f"{BASE_URL}/api/legal/all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "terms_of_service" in data
        assert "privacy_policy" in data
        assert "customer_terms" in data
        
        # Validate each document structure
        for doc_type, doc in data.items():
            assert "title" in doc, f"{doc_type} missing title"
            assert "last_updated" in doc, f"{doc_type} missing last_updated"
            assert "content" in doc, f"{doc_type} missing content"
        
        print("✓ All legal documents endpoint returns complete data")

    def test_terms_content_sections(self):
        """Test that TOS contains required legal sections"""
        response = requests.get(f"{BASE_URL}/api/legal/terms")
        data = response.json()
        content = data["content"]
        
        required_sections = [
            "Acceptance of Terms",
            "Description of Service",
            "Account Registration",
            "Acceptable Use Policy",
            "SMS/MMS Messaging Terms",
            "Data and Privacy",
            "Intellectual Property",
            "Payment Terms",
            "Disclaimer",
            "Limitation of Liability",
            "Termination",
            "Dispute Resolution",
            "Contact Information"
        ]
        
        for section in required_sections:
            assert section in content, f"TOS missing section: {section}"
        
        print(f"✓ TOS contains all {len(required_sections)} required sections")

    def test_privacy_content_sections(self):
        """Test that Privacy Policy contains required sections"""
        response = requests.get(f"{BASE_URL}/api/legal/privacy")
        data = response.json()
        content = data["content"]
        
        required_sections = [
            "Information We Collect",
            "How We Use Your Information",
            "How We Share Your Information",
            "Data Security",
            "Data Retention",
            "Your Rights and Choices",
            "Children's Privacy",
            "California Privacy Rights",
            "GDPR Rights",
            "Cookies Policy",
            "Contact Us"
        ]
        
        for section in required_sections:
            assert section in content, f"Privacy Policy missing section: {section}"
        
        print(f"✓ Privacy Policy contains all {len(required_sections)} required sections")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
