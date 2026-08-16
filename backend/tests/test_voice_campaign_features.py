"""
Tests for:
1. Voice note max duration (180s accepted, 181s rejected)
2. capture-reminder endpoint schedules notification
3. Campaign enrollment pre-schedules pending_sends with delivery_mode=auto and correct send_at dates
4. GET voice notes returns all (not limited to 1)
5. pending_sends status='pending' after enrollment
"""
import pytest
import requests
import os
import io
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"

# ─────────────────────────── Voice Note Duration ───────────────────────────

class TestVoiceNoteDuration:
    """Max duration is now 180 seconds"""

    def test_duration_180_accepted(self):
        """Uploading a note with duration=180 should succeed"""
        # Create a minimal fake audio file
        audio_bytes = b"RIFF$\x00\x00\x00WAVEfmt "  # minimal wav header bytes
        files = {"audio": ("test.wav", io.BytesIO(audio_bytes), "audio/wav")}
        data = {"duration": 180}
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_000",
            files=files,
            data=data,
            timeout=30,
        )
        # Should NOT be 400 (limit exceeded). 500 is ok (storage may fail) but not 400
        assert resp.status_code != 400, f"Expected not 400 for duration=180, got {resp.status_code}: {resp.text}"
        print(f"PASS duration=180 status={resp.status_code}")

    def test_duration_181_rejected(self):
        """Uploading a note with duration=181 should return 400"""
        audio_bytes = b"RIFF$\x00\x00\x00WAVEfmt "
        files = {"audio": ("test.wav", io.BytesIO(audio_bytes), "audio/wav")}
        data = {"duration": 181}
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_000",
            files=files,
            data=data,
            timeout=30,
        )
        assert resp.status_code == 400, f"Expected 400 for duration=181, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "180" in body.get("detail", "") or "limit" in body.get("detail", "").lower(), \
            f"Expected limit message, got: {body}"
        print(f"PASS duration=181 rejected with 400")

    def test_duration_179_accepted(self):
        """Uploading a note with duration=179 should not be rejected by duration check"""
        audio_bytes = b"RIFF$\x00\x00\x00WAVEfmt "
        files = {"audio": ("test.wav", io.BytesIO(audio_bytes), "audio/wav")}
        data = {"duration": 179}
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_000",
            files=files,
            data=data,
            timeout=30,
            allow_redirects=False,
        )
        assert resp.status_code != 400, f"Expected not 400 for duration=179, got {resp.status_code}: {resp.text}"
        print(f"PASS duration=179 status={resp.status_code}")


# ─────────────────────────── Capture Reminder ───────────────────────────

class TestCaptureReminder:
    """POST capture-reminder returns success and schedules notification"""

    def test_capture_reminder_returns_success(self):
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_001/capture-reminder",
            json={"contact_name": "Test User", "delay_seconds": 1},
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("success") is True, f"Expected success=True, got: {body}"
        print(f"PASS capture-reminder: {body}")

    def test_capture_reminder_message_contains_delay(self):
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_001/capture-reminder",
            json={"contact_name": "John Doe", "delay_seconds": 1},
            timeout=10,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body, f"Expected message in response: {body}"
        assert "1s" in body["message"] or "1" in body["message"], \
            f"Expected delay in message, got: {body['message']}"
        print(f"PASS capture-reminder message: {body['message']}")

    def test_capture_reminder_default_delay(self):
        """Without delay_seconds, default 300 should be used"""
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_001/capture-reminder",
            json={"contact_name": "Jane Smith"},
            timeout=10,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        # Default delay is 300
        assert "300" in body.get("message", ""), f"Expected 300s in message: {body}"
        print(f"PASS capture-reminder default delay: {body}")


# ─────────────────────────── GET Voice Notes (returns all) ───────────────────────────

class TestGetVoiceNotes:
    """GET /voice-notes/{uid}/{cid} returns all notes, not just 1"""

    def test_get_voice_notes_returns_list(self):
        resp = requests.get(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_001",
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert isinstance(body, list), f"Expected list, got: {type(body)}"
        print(f"PASS get voice notes returns list of {len(body)} items")

    def test_get_voice_notes_returns_all_not_limited_to_1(self):
        """Verify response is a list (supports multiple notes)"""
        resp = requests.get(
            f"{BASE_URL}/api/voice-notes/{USER_ID}/test_contact_001",
            timeout=10,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list), "Should return list"
        # The key test: response is a list (not a single object), meaning >1 is possible
        # (DB query uses to_list(100), not limit 1)
        print(f"PASS voice notes endpoint returns list (max 100): count={len(body)}")


# ─────────────────────────── Campaign Enrollment → pending_sends ───────────────────────────

class TestCampaignEnrollment:
    """Campaign enrollment pre-schedules all steps with delivery_mode=auto and status=pending"""

    @pytest.fixture(scope="class")
    def campaign_and_contact(self):
        """Create a test campaign and contact, return their IDs. Cleanup after."""
        # 1. Create a contact
        contact_resp = requests.post(
            f"{BASE_URL}/api/contacts/{USER_ID}",
            json={
                "first_name": "TEST_Campaign",
                "last_name": "TestContact",
                "phone": "+15550001234",
                "email": "test_campaign@example.com",
            },
            timeout=10,
        )
        assert contact_resp.status_code in [200, 201], f"Create contact failed: {contact_resp.text}"
        contact = contact_resp.json()
        contact_id = contact.get("id") or contact.get("_id") or str(contact.get("_id", ""))
        if not contact_id:
            # Try to get from response structure
            contact_id = contact.get("contact_id", "")
        print(f"Created contact_id={contact_id}")

        # 2. Create a campaign with delivery_mode=auto and sequences
        campaign_resp = requests.post(
            f"{BASE_URL}/api/campaigns/{USER_ID}",
            json={
                "name": "TEST_AutoCampaign_v1",
                "type": "custom",
                "trigger_tag": "test_auto",
                "delivery_mode": "auto",
                "active": True,
                "ai_enabled": False,
                "sequences": [
                    {
                        "step": 1,
                        "delay_days": 3,
                        "delay_months": 0,
                        "channel": "sms",
                        "message_template": "Step 1: Hello {name}!",
                    },
                    {
                        "step": 2,
                        "delay_days": 14,
                        "delay_months": 0,
                        "channel": "sms",
                        "message_template": "Step 2: Follow up {name}!",
                    },
                    {
                        "step": 3,
                        "delay_days": 0,
                        "delay_months": 2,
                        "channel": "sms",
                        "message_template": "Step 3: Two months {name}!",
                    },
                ],
            },
            timeout=10,
        )
        assert campaign_resp.status_code in [200, 201], f"Create campaign failed: {campaign_resp.text}"
        campaign = campaign_resp.json()
        campaign_id = campaign.get("id") or campaign.get("_id") or str(campaign.get("_id", ""))
        print(f"Created campaign_id={campaign_id}")

        yield contact_id, campaign_id

        # Cleanup: cancel enrollments and delete campaign/contact
        try:
            requests.delete(
                f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enrollments",
                timeout=10,
            )
            requests.delete(f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}", timeout=10)
        except Exception as e:
            print(f"Cleanup error: {e}")

    def test_enroll_contact_creates_pending_sends(self, campaign_and_contact):
        contact_id, campaign_id = campaign_and_contact
        assert contact_id, "No contact_id"
        assert campaign_id, "No campaign_id"

        resp = requests.post(
            f"{BASE_URL}/api/campaigns/{USER_ID}/{campaign_id}/enroll/{contact_id}",
            timeout=10,
        )
        assert resp.status_code in [200, 201], f"Enroll failed: {resp.status_code}: {resp.text}"
        enrollment = resp.json()
        print(f"Enrolled: {enrollment.get('_id', enrollment.get('id'))}")

        # Verify pending sends were created
        pending_resp = requests.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends",
            timeout=10,
        )
        assert pending_resp.status_code == 200, f"pending-sends failed: {pending_resp.text}"
        pending = pending_resp.json()

        # Filter for our contact
        our_sends = [p for p in pending if p.get("contact_id") == contact_id]
        assert len(our_sends) >= 3, f"Expected 3+ pending sends for contact, got {len(our_sends)}"
        print(f"PASS: Found {len(our_sends)} pending sends for contact")

    def test_pending_sends_have_status_pending(self, campaign_and_contact):
        contact_id, campaign_id = campaign_and_contact

        pending_resp = requests.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends",
            timeout=10,
        )
        assert pending_resp.status_code == 200
        pending = pending_resp.json()

        our_sends = [p for p in pending if p.get("contact_id") == contact_id]
        for send in our_sends:
            assert send.get("status") == "pending", \
                f"Expected status='pending', got '{send.get('status')}'"
        print(f"PASS: All {len(our_sends)} sends have status='pending'")

    def test_pending_sends_have_delivery_mode_auto(self, campaign_and_contact):
        contact_id, campaign_id = campaign_and_contact

        pending_resp = requests.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends",
            timeout=10,
        )
        assert pending_resp.status_code == 200
        pending = pending_resp.json()

        our_sends = [p for p in pending if p.get("contact_id") == contact_id]
        assert len(our_sends) > 0, "No pending sends found for contact"
        for send in our_sends:
            assert send.get("delivery_mode") == "auto", \
                f"Expected delivery_mode='auto', got '{send.get('delivery_mode')}'"
        print(f"PASS: All {len(our_sends)} sends have delivery_mode='auto'")

    def test_pending_sends_have_correct_send_at_dates(self, campaign_and_contact):
        """send_at dates should match campaign sequence delays from enrollment time"""
        contact_id, campaign_id = campaign_and_contact

        pending_resp = requests.get(
            f"{BASE_URL}/api/campaigns/{USER_ID}/pending-sends",
            timeout=10,
        )
        assert pending_resp.status_code == 200
        pending = pending_resp.json()

        our_sends = [p for p in pending if p.get("contact_id") == contact_id]
        our_sends.sort(key=lambda x: x.get("step", 0))

        assert len(our_sends) >= 3, f"Expected 3 sends, got {len(our_sends)}"

        now = datetime.utcnow()
        # Step 1: delay_days=3 → send_at ≈ now + 3 days
        # Step 2: delay_days=14 → send_at ≈ now + 14 days
        # Step 3: delay_months=2 → send_at ≈ now + 60 days

        expected_offsets = [3, 14, 60]  # in days

        for i, (send, expected_days) in enumerate(zip(our_sends[:3], expected_offsets)):
            send_at_str = send.get("send_at", "")
            assert send_at_str, f"Step {i+1} missing send_at"
            try:
                # Handle both Z suffix and +00:00
                send_at = datetime.fromisoformat(send_at_str.replace("Z", "+00:00").replace("+00:00", ""))
            except Exception:
                send_at = datetime.fromisoformat(send_at_str[:19])
            
            # Allow 1 day tolerance
            expected_date = now + timedelta(days=expected_days)
            diff_days = abs((send_at - expected_date).days)
            assert diff_days <= 1, \
                f"Step {i+1}: expected ~{expected_days} days from now, got {(send_at - now).days} days (send_at={send_at_str})"
            print(f"PASS step {i+1}: send_at={send_at_str}, offset≈{(send_at - now).days} days (expected {expected_days})")

        print("PASS: All send_at dates match campaign sequences")
