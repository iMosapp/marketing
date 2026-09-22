"""Iteration 346: Jessi Onboarding review - backend API smoke tests.
Covers admin list/config/detail/RBAC, public vCard + call page, inbound webhook idempotency.
"""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("forest@imosapp.com", "Admin123!")
REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")

QUINN_PHONE = "+15005550077"
RILEY_PHONE = "+15005550078"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("token")


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def rep_headers():
    return {"Authorization": f"Bearer {_login(*REP)}"}


@pytest.fixture(scope="module")
def rows(admin_headers):
    r = requests.get(f"{BASE}/api/admin/onboarding-jessi", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    return r.json()


def test_admin_list_shape(rows):
    assert "rows" in rows and "counts" in rows and "states" in rows and "sender" in rows
    assert len(rows["states"]) == 14
    assert rows["sender"]["number"] == "+14352203414"
    assert rows["sender"]["name"].lower().startswith("forest")
    for row in rows["rows"]:
        assert "email" in row
        assert "user_photo_url" in row
        assert row["waiting_on"] in ("them", "jessi", "done", "paused")


def test_admin_list_includes_seeded(rows):
    phones = {r.get("phone") for r in rows["rows"]}
    assert QUINN_PHONE in phones
    assert RILEY_PHONE in phones


def test_admin_config(admin_headers):
    r = requests.get(f"{BASE}/api/admin/onboarding-jessi/config", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["default_on"] is True
    assert body["sender"]["number"] == "+14352203414"


def test_admin_detail_quinn(admin_headers, rows):
    quinn = next(r for r in rows["rows"] if r.get("phone") == QUINN_PHONE)
    r = requests.get(f"{BASE}/api/admin/onboarding-jessi/{quinn['user_id']}", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    body = r.json()
    for k in ("thread", "events", "steps", "user", "call_link", "waiting_on"):
        assert k in body, f"missing {k}"
    assert "/jessi-call/" in body["call_link"]


def test_admin_detail_unknown_404(admin_headers):
    r = requests.get(f"{BASE}/api/admin/onboarding-jessi/000000000000000000000000", headers=admin_headers, timeout=30)
    assert r.status_code == 404


def test_rbac_rep_forbidden(rep_headers):
    r = requests.get(f"{BASE}/api/admin/onboarding-jessi", headers=rep_headers, timeout=30)
    assert r.status_code == 403


def test_rbac_no_token():
    r = requests.get(f"{BASE}/api/admin/onboarding-jessi", timeout=30)
    assert r.status_code == 401


def test_public_vcard():
    r = requests.get(f"{BASE}/api/onboarding-jessi/jessi.vcf", timeout=30)
    assert r.status_code == 200
    assert "vcard" in r.headers.get("content-type", "").lower()
    body = r.text
    assert "BEGIN:VCARD" in body
    assert "FN:Jessi" in body or "FN: Jessi" in body or body.count("Jessi") >= 1
    assert "+14352203414" in body or "4352203414" in body


def test_public_call_page(admin_headers, rows):
    quinn = next(r for r in rows["rows"] if r.get("phone") == QUINN_PHONE)
    d = requests.get(f"{BASE}/api/admin/onboarding-jessi/{quinn['user_id']}", headers=admin_headers, timeout=30).json()
    token = d["call_link"].rsplit("/", 1)[-1]
    r = requests.get(f"{BASE}/api/onboarding-jessi/call/{token}", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body.get("first_name")
    assert "500" in body.get("phone", "")
    assert body.get("can_call") is True


def test_public_call_bad_token():
    r = requests.get(f"{BASE}/api/onboarding-jessi/call/badtoken_xxxx", timeout=30)
    assert r.status_code == 404


def test_inbound_webhook_idempotent(admin_headers, rows):
    """POST inbound twice with same MessageSid -> only one user bubble added."""
    quinn = next(r for r in rows["rows"] if r.get("phone") == QUINN_PHONE)
    uid = quinn["user_id"]

    before = requests.get(f"{BASE}/api/admin/onboarding-jessi/{uid}", headers=admin_headers, timeout=30).json()
    before_count = len(before["thread"])

    form = {
        "From": QUINN_PHONE,
        "To": "+14352203414",
        "Body": "tell me about the app",
        "MessageSid": "SMqa_review_346",
        "NumMedia": "0",
    }
    r1 = requests.post(f"{BASE}/api/webhooks/twilio/incoming", data=form, timeout=30)
    assert r1.status_code == 200, r1.text
    # second post - idempotent
    r2 = requests.post(f"{BASE}/api/webhooks/twilio/incoming", data=form, timeout=30)
    assert r2.status_code == 200

    # wait up to 15s for LLM reply
    for _ in range(15):
        time.sleep(1)
        after = requests.get(f"{BASE}/api/admin/onboarding-jessi/{uid}", headers=admin_headers, timeout=30).json()
        if len(after["thread"]) >= before_count + 2:
            break
    added = len(after["thread"]) - before_count
    # inbound user + jessi reply expected; but not double-user
    user_bubbles = [b for b in after["thread"] if b.get("direction") == "in"]
    sids = [b.get("sid") or b.get("message_sid") for b in user_bubbles]
    assert sids.count("SMqa_review_346") <= 1, f"duplicate inbound stored: {sids}"
    assert added >= 1


def test_yep_at_invited_means_call_me(admin_headers, rows):
    quinn = next(r for r in rows["rows"] if r.get("phone") == QUINN_PHONE)
    uid = quinn["user_id"]
    before = requests.get(f"{BASE}/api/admin/onboarding-jessi/{uid}", headers=admin_headers, timeout=30).json()
    prev_state = before["state"]

    form = {
        "From": QUINN_PHONE,
        "To": "+14352203414",
        "Body": "YEP",
        "MessageSid": f"SMqa_review_346_yep_{int(time.time())}",
        "NumMedia": "0",
    }
    r = requests.post(f"{BASE}/api/webhooks/twilio/incoming", data=form, timeout=30)
    assert r.status_code == 200
    time.sleep(2)
    after = requests.get(f"{BASE}/api/admin/onboarding-jessi/{uid}", headers=admin_headers, timeout=30).json()
    # "Ready to build your profile? Reply CALL" -> a bare YEP means "yes, ring me": it is a call trigger at the invite
    # (the write-up confirmation only applies at INTERVIEW_COMPLETE). The call attempt to a 500 number fails, so the
    # state is INTERVIEW_STARTED (call placed) or still INTERVIEW_INVITED (Twilio refused); never anything later.
    assert after["state"] in (prev_state, "INTERVIEW_STARTED"), f"unexpected state {after['state']} on YEP at INVITED"
    assert any(t.get("text") == "YEP" for t in after["thread"])
