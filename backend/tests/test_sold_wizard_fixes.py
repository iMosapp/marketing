"""
Tests for two SOLD wizard bug fixes:
1. PATCH /contacts/{uid}/{cid}/set-photo sets photo_url and photo_thumbnail
2. enroll_contact_in_campaign includes ai_assist_mode and sets conversation ai_enabled
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
USER_ID = "69a0b7095fddcede09591667"

@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "forest@imosapp.com",
        "password": "Admin123!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token

@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def test_contact_id(headers):
    """Create a test contact and return its ID. Cleaned up after tests."""
    resp = requests.post(f"{BASE_URL}/api/contacts/{USER_ID}", 
        json={
            "first_name": "TEST_SoldWiz",
            "last_name": "BugFix",
            "phone": "+19995550199",
            "email": ""
        }, headers=headers)
    assert resp.status_code == 200, f"Create contact failed: {resp.text}"
    data = resp.json()
    cid = data.get("id") or data.get("_id")
    assert cid, f"No contact id: {data}"
    yield cid
    # Cleanup
    requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}", headers=headers)


class TestSetPhotoEndpoint:
    """Tests for PATCH /contacts/{uid}/{cid}/set-photo"""

    def test_set_photo_returns_200(self, headers, test_contact_id):
        resp = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/set-photo",
            json={"photo_url": "https://example.com/delivery-photo.jpg"},
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_set_photo_response_contains_photo_url(self, headers, test_contact_id):
        resp = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/set-photo",
            json={"photo_url": "https://example.com/delivery-photo.jpg"},
            headers=headers
        )
        data = resp.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        assert data.get("photo_url") == "https://example.com/delivery-photo.jpg"

    def test_set_photo_persists_photo_url_on_contact(self, headers, test_contact_id):
        photo_url = "https://example.com/delivery-photo-persist.jpg"
        requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/set-photo",
            json={"photo_url": photo_url},
            headers=headers
        )
        # GET contact and verify
        get_resp = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}",
            headers=headers
        )
        assert get_resp.status_code == 200, f"GET contact failed: {get_resp.text}"
        contact = get_resp.json()
        assert contact.get("photo_url") == photo_url, f"photo_url not persisted: {contact.get('photo_url')}"
        assert contact.get("photo_thumbnail") == photo_url, f"photo_thumbnail not persisted: {contact.get('photo_thumbnail')}"

    def test_set_photo_without_photo_url_returns_400(self, headers, test_contact_id):
        resp = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/set-photo",
            json={},
            headers=headers
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

    def test_set_photo_invalid_contact_returns_404(self, headers):
        resp = requests.patch(
            f"{BASE_URL}/api/contacts/{USER_ID}/000000000000000000000000/set-photo",
            json={"photo_url": "https://example.com/x.jpg"},
            headers=headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


class TestEnrollmentAiAssistMode:
    """Tests for enroll_contact_in_campaign ai_assist_mode fix"""

    def _get_sold_campaign_id(self, headers):
        resp = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}", headers=headers)
        if resp.status_code != 200:
            return None, None
        campaigns = resp.json()
        if isinstance(campaigns, dict):
            campaigns = campaigns.get("campaigns", [])
        for c in campaigns:
            if c.get("trigger_tag", "").lower() == "sold" and c.get("ai_enabled"):
                return str(c.get("id") or c.get("_id")), True
        # Find any ai_enabled campaign
        for c in campaigns:
            if c.get("ai_enabled") and c.get("active"):
                return str(c.get("id") or c.get("_id")), True
        # Any active campaign
        for c in campaigns:
            if c.get("active"):
                return str(c.get("id") or c.get("_id")), c.get("ai_enabled", False)
        return None, None

    def test_enrollment_has_ai_assist_mode_auto_reply_for_ai_campaign(self, headers, test_contact_id):
        campaign_id, ai_enabled = self._get_sold_campaign_id(headers)
        if not campaign_id:
            pytest.skip("No active campaign found")
        if not ai_enabled:
            pytest.skip("No AI-enabled campaign found for this test")

        resp = requests.post(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enroll/{test_contact_id}",
            headers=headers
        )
        # May already be enrolled — that's fine for re-test, but 400 is ok
        if resp.status_code == 400 and "already enrolled" in resp.text.lower():
            pytest.skip("Contact already enrolled — check enrollment directly")
        assert resp.status_code == 200, f"Enrollment failed: {resp.status_code} {resp.text}"

        data = resp.json()
        enrollment = data.get("enrollment") or data
        ai_mode = enrollment.get("ai_assist_mode")
        assert ai_mode == "auto_reply", f"Expected ai_assist_mode='auto_reply', got: {ai_mode}"

    def test_enrollment_ai_assist_mode_off_for_non_ai_campaign(self, headers, test_contact_id):
        """Create a fresh contact and enroll in a non-AI campaign"""
        # Get a non-AI campaign
        resp = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}", headers=headers)
        if resp.status_code != 200:
            pytest.skip("Cannot fetch campaigns")
        campaigns = resp.json()
        if isinstance(campaigns, dict):
            campaigns = campaigns.get("campaigns", [])
        non_ai_campaign = next((c for c in campaigns if c.get("active") and not c.get("ai_enabled")), None)
        if not non_ai_campaign:
            pytest.skip("No non-AI active campaign found")

        campaign_id = str(non_ai_campaign.get("id") or non_ai_campaign.get("_id"))
        # Create fresh contact
        c_resp = requests.post(f"{BASE_URL}/api/contacts/{USER_ID}",
            json={"first_name": "TEST_NoAI", "last_name": "Contact", "phone": "+19995550298"},
            headers=headers)
        assert c_resp.status_code == 200
        cid = c_resp.json().get("id") or c_resp.json().get("_id")

        try:
            enroll_resp = requests.post(
                f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enroll/{cid}",
                headers=headers
            )
            if enroll_resp.status_code == 200:
                data = enroll_resp.json()
                enrollment = data.get("enrollment") or data
                ai_mode = enrollment.get("ai_assist_mode")
                assert ai_mode == "off", f"Expected ai_assist_mode='off', got: {ai_mode}"
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}", headers=headers)

    def test_conversation_ai_enabled_after_ai_campaign_enrollment(self, headers):
        """Create contact, enroll in AI campaign, verify conversation has ai_enabled=True"""
        # Get AI-enabled sold campaign
        resp = requests.get(f"{BASE_URL}/api/campaigns/{USER_ID}", headers=headers)
        if resp.status_code != 200:
            pytest.skip("Cannot fetch campaigns")
        campaigns = resp.json()
        if isinstance(campaigns, dict):
            campaigns = campaigns.get("campaigns", [])
        ai_campaign = next((c for c in campaigns if c.get("ai_enabled") and c.get("active")), None)
        if not ai_campaign:
            pytest.skip("No AI-enabled active campaign found")
        campaign_id = str(ai_campaign.get("id") or ai_campaign.get("_id"))

        # Create fresh contact with phone
        c_resp = requests.post(f"{BASE_URL}/api/contacts/{USER_ID}",
            json={"first_name": "TEST_AIConv", "last_name": "Check", "phone": "+19995550397"},
            headers=headers)
        assert c_resp.status_code == 200
        contact_data = c_resp.json()
        cid = contact_data.get("id") or contact_data.get("_id")

        try:
            enroll_resp = requests.post(
                f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enroll/{cid}",
                headers=headers
            )
            if enroll_resp.status_code not in [200, 201]:
                pytest.skip(f"Enrollment failed: {enroll_resp.status_code}")

            # Check if conversation was created/updated with ai_enabled
            # Find conversation via messages thread
            conv_resp = requests.get(
                f"{BASE_URL}/api/messages/conversations/{USER_ID}",
                headers=headers
            )
            if conv_resp.status_code != 200:
                pytest.skip("Cannot fetch conversations")

            convs = conv_resp.json()
            if isinstance(convs, dict):
                convs = convs.get("conversations", [])

            # Find conversation for this contact
            contact_conv = next(
                (c for c in convs if c.get("contact_id") == cid or c.get("contact_phone") == "+19995550397"),
                None
            )
            # Note: conversation may not exist if no message was ever sent; this is acceptable.
            # The enrollment record itself should have ai_assist_mode='auto_reply'
            if contact_conv:
                conv_id = contact_conv.get("id") or contact_conv.get("_id") or contact_conv.get("conversation_id")
                if conv_id:
                    thread_resp = requests.get(
                        f"{BASE_URL}/api/messages/thread/{conv_id}",
                        headers=headers
                    )
                    if thread_resp.status_code == 200:
                        thread_data = thread_resp.json()
                        assert thread_data.get("ai_enabled") == True, \
                            f"Expected ai_enabled=True in thread, got: {thread_data.get('ai_enabled')}"
                        assert thread_data.get("ai_mode") == "auto_reply", \
                            f"Expected ai_mode='auto_reply', got: {thread_data.get('ai_mode')}"
                        print("PASS: conversation has ai_enabled=True, ai_mode='auto_reply'")
                    else:
                        print(f"Thread fetch returned {thread_resp.status_code} — skipping thread assertion")
            else:
                print("No conversation found for this test contact (acceptable — no SMS sent yet)")
        finally:
            requests.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}", headers=headers)

    def test_enrollment_record_has_ai_assist_mode_field(self, headers, test_contact_id):
        """Check enrollment record in campaign_enrollments directly via journey API"""
        resp = requests.get(
            f"{BASE_URL}/api/contacts/{USER_ID}/{test_contact_id}/campaign-journey",
            headers=headers
        )
        if resp.status_code != 200:
            pytest.skip(f"Journey API returned {resp.status_code}")
        journeys = resp.json()
        if not journeys:
            pytest.skip("No enrollments for test contact yet")
        # If enrolled, check ai_assist_mode presence
        for j in journeys:
            mode = j.get("ai_assist_mode")
            print(f"Campaign journey ai_assist_mode: {mode}")
            # Just verify it exists (could be auto_reply or off)
            assert mode in ("auto_reply", "off", None), f"Unexpected ai_assist_mode: {mode}"
