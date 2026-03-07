"""
Test Suite for Company Docs PDF Export & Email Features
Tests:
1. POST /api/docs/seed-project-scope - Updates operations manual (super admin only)
2. GET /api/docs/{id}/export-pdf - PDF generation (super admin only)
3. POST /api/docs/{id}/email-pdf - Email PDF (super admin only)
4. Non-super-admin 403 access denied tests
5. Operations manual has v3.0 with 26 slides
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SUPER_ADMIN_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
OPERATIONS_MANUAL_DOC_ID = "69a2296073da8ea96c918d75"

# Non-super-admin user ID (regular user for access control tests)
NON_SUPER_ADMIN_ID = "69a5303dbd4ef63b7ef776d4"  # Test User with role=user


class TestDocsPdfExport:
    """Tests for PDF export and email features"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.headers_super_admin = {"X-User-ID": SUPER_ADMIN_ID}

    def test_health_check(self):
        """Test backend is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Backend health check passed")

    def test_get_operations_manual(self):
        """Verify operations manual exists and has correct metadata"""
        response = requests.get(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}",
            headers=self.headers_super_admin
        )
        assert response.status_code == 200, f"Failed to get doc: {response.text}"
        
        data = response.json()
        assert data.get("title") == "i'M On Social Platform - Complete Operations Manual"
        assert data.get("version") == "3.0"
        assert data.get("slug") == "imos-operations-manual"
        
        slides = data.get("slides", [])
        assert len(slides) == 26, f"Expected 26 slides, got {len(slides)}"
        
        print(f"✓ Operations manual found: {data['title']}")
        print(f"✓ Version: {data['version']}")
        print(f"✓ Slides: {len(slides)}")

    def test_seed_project_scope_super_admin(self):
        """POST /api/docs/seed-project-scope should work for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/docs/seed-project-scope",
            headers=self.headers_super_admin
        )
        assert response.status_code == 200, f"Seed failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "id" in data
        print(f"✓ Seed project scope: {data['message']}")

    def test_export_pdf_super_admin(self):
        """GET /api/docs/{id}/export-pdf should return a valid PDF for super admin"""
        response = requests.get(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}/export-pdf",
            headers=self.headers_super_admin
        )
        assert response.status_code == 200, f"PDF export failed: {response.text}"
        
        # Verify response headers
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Wrong content type: {content_type}"
        
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Missing attachment header: {content_disp}"
        assert "imos-operations-manual.pdf" in content_disp, f"Wrong filename: {content_disp}"
        
        # Verify PDF content (PDF starts with %PDF-)
        assert response.content[:5] == b"%PDF-", "Response is not a valid PDF"
        
        # Check PDF size (should be substantial with 26 slides)
        pdf_size = len(response.content)
        assert pdf_size > 10000, f"PDF too small ({pdf_size} bytes), might be incomplete"
        
        print(f"✓ PDF exported successfully: {pdf_size} bytes")
        print(f"✓ Content-Type: {content_type}")
        print(f"✓ Content-Disposition: {content_disp}")

    def test_email_pdf_super_admin(self):
        """POST /api/docs/{id}/email-pdf should attempt to send email for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}/email-pdf",
            headers=self.headers_super_admin
        )
        
        # Note: Email may fail in preview env due to Resend domain verification
        # But we should get either 200 (success) or 500 with domain error, not 403
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is True
            assert "message" in data
            print(f"✓ Email sent: {data['message']}")
        elif response.status_code == 500:
            # Expected in preview environment (domain not verified)
            data = response.json()
            detail = data.get("detail", "")
            print(f"⚠ Email failed (expected in preview): {detail}")
            # This is acceptable - we verified auth works, email service just isn't configured
            assert "domain" in detail.lower() or "send email" in detail.lower() or "validation" in detail.lower(), f"Unexpected error: {detail}"
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text}")


class TestDocsPdfAccessControl:
    """Tests for 403 access denied for non-super-admin users"""

    def test_seed_project_scope_non_super_admin_403(self):
        """POST /api/docs/seed-project-scope should return 403 for non-super-admin"""
        response = requests.post(
            f"{BASE_URL}/api/docs/seed-project-scope",
            headers={"X-User-ID": NON_SUPER_ADMIN_ID}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Seed project scope correctly denied to non-super-admin (403)")

    def test_export_pdf_non_super_admin_403(self):
        """GET /api/docs/{id}/export-pdf should return 403 for non-super-admin"""
        response = requests.get(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}/export-pdf",
            headers={"X-User-ID": NON_SUPER_ADMIN_ID}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ PDF export correctly denied to non-super-admin (403)")

    def test_email_pdf_non_super_admin_403(self):
        """POST /api/docs/{id}/email-pdf should return 403 for non-super-admin"""
        response = requests.post(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}/email-pdf",
            headers={"X-User-ID": NON_SUPER_ADMIN_ID}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Email PDF correctly denied to non-super-admin (403)")

    def test_export_pdf_no_auth_401(self):
        """GET /api/docs/{id}/export-pdf should return 401 with no user ID"""
        response = requests.get(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}/export-pdf"
        )
        # Could be 401 (no auth) or 403 (insufficient permissions)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ PDF export correctly denied without auth ({response.status_code})")

    def test_email_pdf_no_auth_401(self):
        """POST /api/docs/{id}/email-pdf should return 401 with no user ID"""
        response = requests.post(
            f"{BASE_URL}/api/docs/{OPERATIONS_MANUAL_DOC_ID}/email-pdf"
        )
        # Could be 401 (no auth) or 403 (insufficient permissions)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Email PDF correctly denied without auth ({response.status_code})")


class TestDocsPdfEdgeCases:
    """Edge case tests for PDF export"""

    def test_export_pdf_invalid_doc_id_404(self):
        """GET /api/docs/{invalid_id}/export-pdf should return 404"""
        response = requests.get(
            f"{BASE_URL}/api/docs/000000000000000000000000/export-pdf",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ PDF export returns 404 for invalid doc ID")

    def test_email_pdf_invalid_doc_id_404(self):
        """POST /api/docs/{invalid_id}/email-pdf should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/docs/000000000000000000000000/email-pdf",
            headers={"X-User-ID": SUPER_ADMIN_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Email PDF returns 404 for invalid doc ID")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
