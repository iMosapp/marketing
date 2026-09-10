"""Backend tests for Campaigns redesign - iteration 306."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_USER_ID = "69a0b7095fddcede09591667"
SOLD_CAMPAIGN_ID = "69d172b9276decacd8e16eaa"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------- LIST + PERMISSIONS + TEMPLATES ----------------

def test_list_campaigns_has_sent_this_week(headers):
    r = requests.get(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    required = {"sent_this_week", "enrollments_active", "sequences", "ai_assist_mode",
                "ai_enabled", "delivery_mode", "scope"}
    missing_summary = []
    for c in data:
        missing = required - set(c.keys())
        if missing:
            missing_summary.append((c.get("name"), list(missing)))
        else:
            assert isinstance(c["sent_this_week"], int)
    assert not missing_summary, f"Campaigns missing fields: {missing_summary[:5]}"


def test_permissions_allowed(headers):
    r = requests.get(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/permissions", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("allowed") is True, data


def test_prebuilt_templates_returns_8(headers):
    r = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # Might be list or dict
    templates = data if isinstance(data, list) else data.get("templates", [])
    assert len(templates) == 8, f"Expected 8 templates got {len(templates)}"
    for t in templates:
        assert "step_count" in t, f"Missing step_count in {t.get('id') or t.get('name')}"
        assert "total_duration" in t, f"Missing total_duration in {t.get('id') or t.get('name')}"


def test_prebuilt_template_sold_followup(headers):
    r = requests.get(f"{BASE_URL}/api/campaigns/templates/prebuilt/sold_followup", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    seqs = data.get("sequences") or data.get("template", {}).get("sequences")
    assert seqs and isinstance(seqs, list) and len(seqs) > 0, f"No sequences in sold_followup: {data}"


# ---------------- CRUD + ENROLLMENTS + DUPLICATE ----------------

def test_full_crud_and_enrollments(headers):
    ts = int(time.time())
    name = f"QA Redesign Plan {ts}"
    create_body = {
        "name": name,
        "type": "custom",
        "trigger_tag": "qa_redesign",
        "sequences": [],
        "active": False,
        "delivery_mode": "auto",
        "ai_enabled": True,
        "ai_assist_mode": "auto_reply",
        "scope": "personal",
        "ownership_level": "user",
    }
    r = requests.post(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}", headers=headers, json=create_body, timeout=30)
    assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
    created = r.json()
    cid = created.get("_id") or created.get("id")
    assert cid, f"No id in create response: {created}"

    try:
        # PUT update
        update_body = {
            "name": name,
            "trigger_tag": "qa_redesign",
            "type": "custom",
            "date_type": "",
            "active": False,
            "ai_assist_mode": "draft_only",
            "escalation_threshold": 3,
            "escalation_timeout_minutes": 20,
            "ai_enabled": False,
            "delivery_mode": "manual",
            "sequences": [
                {"step": 1, "action_type": "message", "card_type": "",
                 "message_template": "Hey {first_name}, QA test",
                 "delay_hours": 0, "delay_days": 1, "delay_months": 0, "delay_minutes": 0,
                 "media_urls": [], "channel": "sms", "ai_generated": False, "step_context": ""},
                {"step": 2, "action_type": "send_card", "card_type": "thankyou",
                 "message_template": "", "delay_hours": 0, "delay_days": 7,
                 "delay_months": 0, "delay_minutes": 0, "media_urls": [], "channel": "sms",
                 "ai_generated": False, "step_context": ""},
            ],
        }
        r = requests.put(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{cid}", headers=headers,
                         json=update_body, timeout=30)
        assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"

        # GET verify
        r = requests.get(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{cid}", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["ai_assist_mode"] == "draft_only", got.get("ai_assist_mode")
        assert got["delivery_mode"] == "manual", got.get("delivery_mode")
        assert len(got.get("sequences", [])) == 2, f"seq count = {len(got.get('sequences', []))}"
        s2 = got["sequences"][1]
        assert s2.get("action_type") == "send_card", s2
        assert s2.get("card_type") == "thankyou", s2

        # Enrollments
        r = requests.get(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{cid}/enrollments",
                         headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        enrolls = r.json()
        assert isinstance(enrolls, list), f"enrollments should be list: {enrolls}"

        # Duplicate
        r = requests.post(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{cid}/duplicate",
                          headers=headers, timeout=30)
        assert r.status_code in (200, 201), f"Duplicate failed: {r.status_code} {r.text}"
        dup = r.json()
        dup_id = dup.get("_id") or dup.get("id")
        assert dup_id, dup
        assert "(Copy)" in (dup.get("name") or ""), dup.get("name")
        assert dup.get("active") in (False, None), dup.get("active")

        # Delete copy
        r = requests.delete(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{dup_id}",
                            headers=headers, timeout=30)
        assert r.status_code in (200, 204), r.text
        r = requests.get(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{dup_id}",
                         headers=headers, timeout=30)
        assert r.status_code == 404, f"Copy still present: {r.status_code}"

    finally:
        # Cleanup original
        requests.delete(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{cid}",
                        headers=headers, timeout=30)


def test_sold_campaign_enrollments_enriched(headers):
    r = requests.get(f"{BASE_URL}/api/campaigns/{ADMIN_USER_ID}/{SOLD_CAMPAIGN_ID}/enrollments",
                     headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    if data:
        sample = data[0]
        assert "contact_name" in sample, f"Missing contact_name: {sample.keys()}"
        assert "total_steps" in sample, f"Missing total_steps: {sample.keys()}"
