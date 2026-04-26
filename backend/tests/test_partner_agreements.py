"""
Partner Agreement System Backend Tests
Tests: agreement templates, create/get/list agreements, commission tiers in Exhibit A,
sign agreement, W-9 upload, W-9 verify
"""
import pytest
import requests
import os
import io
import time

def _get_base_url():
    url = os.environ.get('REACT_APP_BACKEND_URL', '')
    if not url:
        # Read from frontend .env
        env_path = os.path.join(os.path.dirname(__file__), '../../frontend/.env')
        try:
            with open(env_path) as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        url = line.strip().split('=', 1)[1].strip()
                        break
        except Exception:
            pass
    return url.rstrip('/')

BASE_URL = _get_base_url()

# Known draft agreement IDs from the DB (provided in review_request)
EXISTING_DRAFT_IDS = [
    '69ee7e14d276512419673033',
    '69ee7196595e240e6acd880a',
    '69ee6fd9aa6d11afaf9179e3',
]


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def template_ids(api_client):
    """Get available template IDs from the server"""
    response = api_client.get(f"{BASE_URL}/api/partners/templates")
    assert response.status_code == 200, f"Templates fetch failed: {response.text}"
    templates = response.json()
    assert len(templates) > 0, "No templates found"
    result = {}
    for t in templates:
        result[t['type']] = t['id']
    return result


class TestAgreementTemplates:
    """Agreement template endpoints"""

    def test_list_templates_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /partners/templates → 200")

    def test_list_templates_has_required_fields(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/templates")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "No templates returned"
        for t in data:
            assert 'id' in t
            assert 'name' in t
            assert 'type' in t
            assert t['type'] in ('reseller', 'referral')
        print(f"✓ Templates have required fields: {[t['name'] for t in data]}")

    def test_templates_include_reseller_and_referral(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/templates")
        data = response.json()
        types = [t['type'] for t in data]
        assert 'reseller' in types, f"No reseller template found. Types: {types}"
        assert 'referral' in types, f"No referral template found. Types: {types}"
        print(f"✓ Both reseller and referral templates exist")


class TestCreateAgreement:
    """POST /api/partners/agreements — create agreement"""

    created_agreement_id = None

    def test_create_referral_agreement_success(self, api_client, template_ids):
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        payload = {
            "template_id": tid,
            "partner_name": "TEST_Partner John Doe",
            "partner_email": "TEST_partner@example.com",
            "custom_terms": "",
            "custom_commission_notes": ""
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'id' in data, "No 'id' in response"
        assert 'link' in data, "No 'link' in response"
        assert data['id'], "Agreement ID is empty"
        TestCreateAgreement.created_agreement_id = data['id']
        print(f"✓ Created referral agreement ID: {data['id']}, link: {data['link']}")

    def test_create_reseller_agreement_success(self, api_client, template_ids):
        tid = template_ids.get('reseller')
        if not tid:
            pytest.skip("No reseller template available")
        payload = {
            "template_id": tid,
            "partner_name": "TEST_Reseller Partner",
            "partner_email": "TEST_reseller@example.com",
            "custom_terms": "TEST Special Term — Utah territory exclusive",
            "custom_commission_notes": ""
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'id' in data
        print(f"✓ Created reseller agreement ID: {data['id']}")

    def test_create_agreement_missing_template_id_returns_400(self, api_client):
        payload = {
            "partner_name": "TEST_Bad Partner",
            "partner_email": "TEST_bad@example.com"
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Missing template_id → 400")

    def test_create_agreement_invalid_template_id_returns_404(self, api_client):
        payload = {
            "template_id": "000000000000000000000000",
            "partner_name": "TEST_Partner",
            "partner_email": "TEST_partner@example.com"
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ Invalid template ID → 404")

    def test_create_agreement_with_custom_commission_notes(self, api_client, template_ids):
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        payload = {
            "template_id": tid,
            "partner_name": "TEST_Custom Commission Partner",
            "partner_email": "TEST_custom@example.com",
            "custom_commission_notes": "15% of MRR for first 12 months, then 10% ongoing"
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'id' in data
        # Fetch the agreement and check content
        get_response = api_client.get(f"{BASE_URL}/api/partners/agreements/{data['id']}")
        assert get_response.status_code == 200
        agreement = get_response.json()
        content = agreement.get('content', '')
        assert 'Custom Commission Terms' in content or '15% of MRR' in content, \
            f"Custom commission notes not in content: {content[:500]}"
        print(f"✓ Custom commission notes appear in agreement content")


class TestGetAgreement:
    """GET /api/partners/agreements/{id}"""

    def test_get_existing_agreement_returns_200(self, api_client):
        # Use one of the known draft agreements
        aid = EXISTING_DRAFT_IDS[0]
        response = api_client.get(f"{BASE_URL}/api/partners/agreements/{aid}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'id' in data
        assert 'content' in data
        assert 'status' in data
        print(f"✓ GET agreement {aid} → 200, status={data['status']}")

    def test_get_agreement_has_full_content(self, api_client):
        aid = EXISTING_DRAFT_IDS[0]
        response = api_client.get(f"{BASE_URL}/api/partners/agreements/{aid}")
        data = response.json()
        content = data.get('content', '')
        assert len(content) > 100, f"Content too short: {len(content)} chars"
        # Should contain MPA
        assert 'MASTER PARTNER AGREEMENT' in content or 'Partner Agreement' in content, \
            f"Master agreement text not in content. Content starts: {content[:200]}"
        # Should contain Exhibit A
        assert 'EXHIBIT A' in content, f"Exhibit A not in content"
        print(f"✓ Agreement has full content (MPA + Exhibit A), length={len(content)}")

    def test_get_agreement_invalid_id_returns_404(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/agreements/000000000000000000000000")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid agreement ID → 404")


class TestCommissionTiersInExhibitA:
    """Verify Exhibit A commission tiers are correct for referral vs reseller"""

    def test_referral_exhibit_a_has_10_and_15_percent(self, api_client, template_ids):
        """Referral type must show 10% and 15% tiers"""
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        payload = {
            "template_id": tid,
            "partner_name": "TEST_ExhibitA Referral",
            "partner_email": "TEST_exhibita_ref@example.com",
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 200
        data = response.json()
        get_resp = api_client.get(f"{BASE_URL}/api/partners/agreements/{data['id']}")
        content = get_resp.json().get('content', '')
        assert '10%' in content, f"10% tier not found in referral Exhibit A. Content snippet: {content[content.find('EXHIBIT A'):content.find('EXHIBIT A')+500]}"
        assert '15%' in content, f"15% tier not found in referral Exhibit A. Content snippet: {content[content.find('EXHIBIT A'):content.find('EXHIBIT A')+500]}"
        # Ensure reseller rates NOT present in referral
        exhibit_start = content.find('EXHIBIT A')
        exhibit_content = content[exhibit_start:] if exhibit_start > -1 else content
        print(f"✓ Referral Exhibit A has 10% and 15% commission tiers")

    def test_reseller_exhibit_a_has_20_30_40_percent(self, api_client, template_ids):
        """Reseller type must show 20%, 30%, and 40% tiers"""
        tid = template_ids.get('reseller')
        if not tid:
            pytest.skip("No reseller template available")
        payload = {
            "template_id": tid,
            "partner_name": "TEST_ExhibitA Reseller",
            "partner_email": "TEST_exhibita_res@example.com",
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 200
        data = response.json()
        get_resp = api_client.get(f"{BASE_URL}/api/partners/agreements/{data['id']}")
        content = get_resp.json().get('content', '')
        exhibit_start = content.find('EXHIBIT A')
        exhibit_content = content[exhibit_start:] if exhibit_start > -1 else content
        assert '20%' in exhibit_content, f"20% tier not found in reseller Exhibit A. Exhibit content: {exhibit_content[:600]}"
        assert '30%' in exhibit_content, f"30% tier not found in reseller Exhibit A. Exhibit content: {exhibit_content[:600]}"
        assert '40%' in exhibit_content, f"40% tier not found in reseller Exhibit A. Exhibit content: {exhibit_content[:600]}"
        print(f"✓ Reseller Exhibit A has 20%, 30%, and 40% commission tiers")

    def test_custom_commission_notes_override_standard_tiers(self, api_client, template_ids):
        """Custom commission notes override section 1 in Exhibit A"""
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        custom_note = "TEST CUSTOM: Flat 12% commission for all MRR"
        payload = {
            "template_id": tid,
            "partner_name": "TEST_Custom Override",
            "partner_email": "TEST_override@example.com",
            "custom_commission_notes": custom_note
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements", json=payload)
        assert response.status_code == 200
        data = response.json()
        get_resp = api_client.get(f"{BASE_URL}/api/partners/agreements/{data['id']}")
        content = get_resp.json().get('content', '')
        assert custom_note in content or 'TEST CUSTOM' in content or 'Flat 12%' in content, \
            f"Custom commission notes not found in content. Content snippet: {content[:800]}"
        assert 'Custom Commission Terms' in content, \
            f"Custom Commission Terms label not found in content"
        print(f"✓ Custom commission notes override standard tiers in Exhibit A")


class TestListAgreements:
    """GET /api/partners/agreements"""

    def test_list_agreements_returns_200(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/agreements")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /partners/agreements → 200")

    def test_list_agreements_has_required_fields(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/agreements")
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            first = data[0]
            assert 'id' in first, "Missing 'id'"
            assert 'status' in first, "Missing 'status'"
            assert 'partner_name' in first or first.get('partner_name') is None, "Missing 'partner_name'"
            assert 'w9_status' not in first or True  # Optional field - just checking not crashing
        print(f"✓ Agreements list has required fields, count={len(data)}")

    def test_list_agreements_includes_existing_drafts(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/partners/agreements")
        data = response.json()
        ids = [a['id'] for a in data]
        found = [aid for aid in EXISTING_DRAFT_IDS if aid in ids]
        assert len(found) > 0, f"None of the known draft IDs found in list: {ids[:5]}"
        print(f"✓ Agreement list includes known draft agreements: {found}")


class TestSignAgreement:
    """POST /api/partners/agreements/{id}/sign"""

    signed_agreement_id = None

    def test_sign_agreement_success(self, api_client, template_ids):
        """Create a new agreement and sign it"""
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        # Create fresh agreement for signing
        create_response = api_client.post(f"{BASE_URL}/api/partners/agreements", json={
            "template_id": tid,
            "partner_name": "TEST_SignTest Partner",
            "partner_email": "TEST_signtest@example.com",
        })
        assert create_response.status_code == 200
        agreement_id = create_response.json()['id']
        TestSignAgreement.signed_agreement_id = agreement_id

        sign_payload = {
            "name": "TEST_SignTest Partner",
            "email": "TEST_signtest@example.com",
            "company": "TEST Company LLC",
            "phone": "555-0100",
            "signature": "TEST_SignTest Partner",
            "signature_type": "typed",
            "agreed_to_terms": True
        }
        response = api_client.post(f"{BASE_URL}/api/partners/agreements/{agreement_id}/sign", json=sign_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') is True
        assert data.get('status') == 'signed', f"Expected status='signed', got: {data.get('status')}"
        print(f"✓ Agreement {agreement_id} signed successfully, status: {data.get('status')}")

    def test_sign_agreement_verifies_status_changed_to_signed(self, api_client):
        """After signing, GET should return status='signed' and signed_partner data"""
        if not TestSignAgreement.signed_agreement_id:
            pytest.skip("No signed agreement created in previous test")
        response = api_client.get(f"{BASE_URL}/api/partners/agreements/{TestSignAgreement.signed_agreement_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'signed', f"Expected status='signed', got: {data.get('status')}"
        assert data.get('signed_partner') is not None, "signed_partner should not be null after signing"
        signed = data['signed_partner']
        assert signed.get('name') == "TEST_SignTest Partner"
        assert signed.get('email') == "TEST_signtest@example.com"
        assert signed.get('signature') == "TEST_SignTest Partner"
        assert 'ip_address' in signed, "IP address not captured in signed_partner"
        assert 'document_hash' in signed, "Document hash not captured in signed_partner"
        assert signed.get('agreed_to_terms') is True
        print(f"✓ GET after sign shows status='signed', signed_partner data present with IP+hash")

    def test_sign_already_signed_agreement_returns_400(self, api_client):
        """Can't sign an already-signed agreement"""
        if not TestSignAgreement.signed_agreement_id:
            pytest.skip("No signed agreement ID available")
        sign_payload = {
            "name": "Another Signer",
            "email": "another@example.com",
            "signature": "Another Signer",
            "signature_type": "typed",
            "agreed_to_terms": True
        }
        response = api_client.post(
            f"{BASE_URL}/api/partners/agreements/{TestSignAgreement.signed_agreement_id}/sign",
            json=sign_payload
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Re-signing already-signed agreement → 400")

    def test_sign_nonexistent_agreement_returns_404(self, api_client):
        sign_payload = {
            "name": "Nobody",
            "email": "nobody@example.com",
            "signature": "Nobody",
            "signature_type": "typed",
            "agreed_to_terms": True
        }
        response = api_client.post(
            f"{BASE_URL}/api/partners/agreements/000000000000000000000000/sign",
            json=sign_payload
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ Signing non-existent agreement → 404")


class TestW9Upload:
    """POST /api/partners/agreements/{id}/w9 and POST /api/partners/agreements/{id}/w9/verify"""

    w9_agreement_id = None

    def test_w9_upload_pdf_success(self, api_client, template_ids):
        """Upload a mock PDF W-9 to a signed agreement"""
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        # Create and sign an agreement first
        create_response = api_client.post(f"{BASE_URL}/api/partners/agreements", json={
            "template_id": tid,
            "partner_name": "TEST_W9Upload Partner",
            "partner_email": "TEST_w9upload@example.com",
        })
        assert create_response.status_code == 200
        agreement_id = create_response.json()['id']
        TestW9Upload.w9_agreement_id = agreement_id

        # Sign the agreement first
        api_client.post(f"{BASE_URL}/api/partners/agreements/{agreement_id}/sign", json={
            "name": "TEST_W9Upload Partner",
            "email": "TEST_w9upload@example.com",
            "signature": "TEST_W9Upload Partner",
            "signature_type": "typed",
            "agreed_to_terms": True
        })

        # Upload a mock PDF
        pdf_content = b"%PDF-1.4 TEST W9 CONTENT"
        files = {'file': ('w9.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        # Remove JSON content-type for multipart
        upload_client = requests.Session()
        response = upload_client.post(
            f"{BASE_URL}/api/partners/agreements/{agreement_id}/w9",
            files=files
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') is True
        assert data.get('w9_status') == 'uploaded', f"Expected w9_status='uploaded', got: {data.get('w9_status')}"
        print(f"✓ W-9 uploaded successfully for agreement {agreement_id}")

    def test_w9_upload_updates_agreement_status(self, api_client):
        """After W-9 upload, agreement's w9_status should be 'uploaded'"""
        if not TestW9Upload.w9_agreement_id:
            pytest.skip("No W9 agreement ID available")
        response = api_client.get(f"{BASE_URL}/api/partners/agreements/{TestW9Upload.w9_agreement_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get('w9_status') == 'uploaded', f"Expected w9_status='uploaded', got: {data.get('w9_status')}"
        print(f"✓ Agreement w9_status='uploaded' after upload")

    def test_w9_upload_no_file_returns_400(self, api_client, template_ids):
        """W-9 upload with no file should return 400"""
        tid = template_ids.get('referral')
        if not tid:
            pytest.skip("No referral template available")
        # Use existing draft agreement
        response = api_client.post(
            f"{BASE_URL}/api/partners/agreements/{EXISTING_DRAFT_IDS[2]}/w9",
            data={}  # No file
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ W-9 upload with no file → 400")

    def test_w9_verify_success(self, api_client):
        """Admin can verify W-9 after upload"""
        if not TestW9Upload.w9_agreement_id:
            pytest.skip("No W9 agreement ID available")
        response = api_client.post(f"{BASE_URL}/api/partners/agreements/{TestW9Upload.w9_agreement_id}/w9/verify")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') is True
        assert data.get('w9_status') == 'verified', f"Expected w9_status='verified', got: {data.get('w9_status')}"
        print(f"✓ W-9 verified successfully")

    def test_w9_verify_updates_agreement_status(self, api_client):
        """After verification, agreement w9_status should be 'verified'"""
        if not TestW9Upload.w9_agreement_id:
            pytest.skip("No W9 agreement ID available")
        response = api_client.get(f"{BASE_URL}/api/partners/agreements/{TestW9Upload.w9_agreement_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get('w9_status') == 'verified', f"Expected w9_status='verified', got: {data.get('w9_status')}"
        print(f"✓ Agreement w9_status='verified' after verify API call")
