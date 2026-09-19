"""Review-request integration tests for per-store Twilio compliance admin API.

Runs against the preview backend URL (REACT_APP_BACKEND_URL). Uses the seeded QA store
69a0b7095fddcede09591668. Leaves state clean: mode dry_run, notify_email '', QA store stage draft.
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
QA_STORE = "69a0b7095fddcede09591668"

SUPER = {"email": "forest@imosapp.com", "password": "Admin123!"}
USER = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}
MGR = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}


def _login(creds):
    r = requests.post(f"{BASE}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin():
    return _login(SUPER)


@pytest.fixture(scope="module")
def user():
    return _login(USER)


@pytest.fixture(scope="module")
def manager():
    try:
        return _login(MGR)
    except AssertionError:
        pytest.skip("qa-manager not seeded")


@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin):
    yield
    # Restore mode + notify email + QA store to draft
    requests.put(f"{BASE}/admin/compliance/settings", json={"mode": "dry_run", "notify_email": ""}, headers=admin, timeout=20)
    requests.post(f"{BASE}/admin/compliance/{QA_STORE}/reset", headers=admin, timeout=20)


# ── overview & settings ────────────────────────────────────────────────────
def test_overview_super_admin(admin):
    r = requests.get(f"{BASE}/admin/compliance", headers=admin, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "settings" in d and "stores" in d and "stages" in d and "stage_labels" in d
    assert "mode" in d["settings"] and "notify_email" in d["settings"]
    assert any(s["store_id"] == QA_STORE for s in d["stores"]), "QA store must be in overview"
    # only US/blank-country
    countries = {(s.get("country") or "") for s in d["stores"]}
    assert countries.issubset({"US", "USA", "", None}), f"non-US countries surfaced: {countries}"


def test_overview_forbidden_for_user(user):
    r = requests.get(f"{BASE}/admin/compliance", headers=user, timeout=20)
    assert r.status_code == 403


def test_settings_forbidden_for_user(user):
    r = requests.put(f"{BASE}/admin/compliance/settings", json={"mode": "mock"}, headers=user, timeout=20)
    assert r.status_code == 403


def test_settings_switch_mode_and_restore(admin):
    r = requests.put(f"{BASE}/admin/compliance/settings", json={"mode": "mock"}, headers=admin, timeout=20)
    assert r.status_code == 200 and r.json()["mode"] == "mock"
    r = requests.put(f"{BASE}/admin/compliance/settings", json={"mode": "dry_run"}, headers=admin, timeout=20)
    assert r.status_code == 200 and r.json()["mode"] == "dry_run"


def test_settings_invalid_mode(admin):
    r = requests.put(f"{BASE}/admin/compliance/settings", json={"mode": "bogus"}, headers=admin, timeout=20)
    assert r.status_code == 400


def test_options_endpoint(admin):
    r = requests.get(f"{BASE}/admin/compliance/options", headers=admin, timeout=20)
    assert r.status_code == 200
    d = r.json()
    for k in ("business_types", "job_positions", "use_cases", "modes"):
        assert k in d, f"missing {k}"
    assert "LOW_VOLUME" in d["use_cases"]
    assert "dry_run" in d["modes"]


# ── store record ───────────────────────────────────────────────────────────
def test_get_store_record(admin):
    r = requests.get(f"{BASE}/admin/compliance/{QA_STORE}", headers=admin, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["store"]["id"] == QA_STORE
    b = d["record"]["business"]
    assert b["ein"] == "", "EIN must never be echoed"
    assert "ein_masked" in b and "has_ein" in b
    assert isinstance(d["missing"], list)
    assert "summary" in d and "settings" in d


def test_get_unknown_store_404(admin):
    r = requests.get(f"{BASE}/admin/compliance/000000000000000000000000", headers=admin, timeout=20)
    assert r.status_code == 404
    r = requests.get(f"{BASE}/admin/compliance/notavalidid", headers=admin, timeout=20)
    assert r.status_code == 404


def test_put_record_fills_missing_and_normalizes_cnam(admin):
    payload = {
        "business": {
            "legal_name": "i'M On social",
            "ein": "12-3456789",
            "business_type": "Limited Liability Corporation",
            "website": "https://qamotors.example",
            "street": "12 Main St",
            "city": "Ogden",
            "state": "UT",
            "postal_code": "84401",
        },
        "rep": {
            "first_name": "Pat",
            "last_name": "Owner",
            "email": "qa@invalid.imonsocial.test",
            "phone": "+15005550100",
            "title": "General Manager",
            "job_position": "GM",
        },
        "campaign": {
            "use_case": "LOW_VOLUME",
            "description": "Sales and service reps text customers who bought a vehicle from them or asked to be contacted with follow-ups and reminders.",
            "message_flow": "Customers give their mobile number to their rep in person or on the website contact form and consent to receive texts. Every message includes STOP opt-out.",
            "samples": [
                "Hi Jordan, this is Sam at QA Motors. Your Tahoe is ready any time after 3. Reply STOP to opt out.",
                "Hey Jordan, Sam at QA Motors: still thinking about the Wrangler? I can hold it. Reply STOP to opt out.",
            ],
            "privacy_url": "https://qamotors.example/privacy",
            "terms_url": "https://qamotors.example/terms",
        },
        "cnam": {"display_name": "qa motors test long name", "enabled": True},
    }
    r = requests.put(f"{BASE}/admin/compliance/{QA_STORE}", json=payload, headers=admin, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["missing"] == [], f"still missing: {d['missing']}"
    assert d["record"]["business"]["ein"] == "", "EIN should never round-trip"
    assert d["record"]["business"]["ein_masked"] == "**-***6789"
    assert d["record"]["business"]["has_ein"] is True
    cnam = d["record"]["cnam"]["display_name"]
    assert len(cnam) <= 15 and cnam == cnam.upper(), f"cnam not normalized: {cnam!r}"
    assert all(ch.isalnum() or ch == " " for ch in cnam)


def test_put_blank_ein_keeps_prior(admin):
    r = requests.put(f"{BASE}/admin/compliance/{QA_STORE}", json={"business": {"ein": ""}}, headers=admin, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["record"]["business"]["has_ein"] is True
    assert d["record"]["business"]["ein_masked"] == "**-***6789"


# ── lifecycle ──────────────────────────────────────────────────────────────
def test_dry_run_lifecycle(admin):
    # Submit is gated on pre-flight + team review now; the super admin can force it
    r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/submit", headers=admin, timeout=30)
    assert r.status_code == 400 and "pre-flight" in r.text.lower()
    r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/submit?force=true", headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["summary"]["stage"] == "profile"
    assert d["record"]["sids"]["customer_profile"].startswith("BU")

    # Check advances profile -> a2p -> brand -> campaign -> complete
    last = d
    for _ in range(8):
        r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/check", headers=admin, timeout=30)
        assert r.status_code == 200, r.text
        last = r.json()
        if last["summary"]["stage"] == "complete":
            break
    assert last["summary"]["stage"] == "complete"
    assert last["summary"]["status"] == "approved"


def test_reset_forbidden_for_user(user):
    r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/reset", headers=user, timeout=20)
    assert r.status_code == 403


def test_reset_forbidden_for_manager(manager):
    # Managers are role store_manager (not super_admin/org_admin) -> should be 403
    r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/reset", headers=manager, timeout=20)
    assert r.status_code == 403


def test_reset_by_super_admin(admin):
    r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/reset", headers=admin, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["record"]["stage"] == "draft"
    assert d["record"]["status"] == "not_started"
    assert d["record"]["sids"] == {}
    # Business/rep/campaign form data survives
    assert d["record"]["business"]["legal_name"]


def test_submit_missing_fields_on_draft(admin):
    # After reset, the store still has all fields filled by prior test.
    # Wipe a required field to force 400.
    requests.put(f"{BASE}/admin/compliance/{QA_STORE}", json={"business": {"legal_name": ""}}, headers=admin, timeout=20)
    r = requests.post(f"{BASE}/admin/compliance/{QA_STORE}/submit?force=true", headers=admin, timeout=20)
    assert r.status_code == 400
    assert "Missing" in r.json().get("detail", "")
    # Restore
    requests.put(f"{BASE}/admin/compliance/{QA_STORE}", json={"business": {"legal_name": "i'M On social"}}, headers=admin, timeout=20)


# ── webhook ────────────────────────────────────────────────────────────────
def test_trusthub_webhook_unsigned():
    r = requests.post(f"{BASE}/webhooks/twilio/trusthub-status",
                      data={"BundleSid": "BUdoesnotexist", "Status": "twilio-approved"}, timeout=20)
    # With TWILIO_AUTH_TOKEN set in preview an unsigned request may be 403; without it 200.
    assert r.status_code in (200, 403), r.text
    print(f"[webhook] unsigned response = {r.status_code} {r.text[:80]}")


# ── scheduler job in-process ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scheduler_poll_all_runs():
    """Same coroutine the APScheduler job uses; must run without raising."""
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.twilio_compliance import poll_all
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    try:
        n = await poll_all(db)
        assert isinstance(n, int) and n >= 0
    finally:
        client.close()
