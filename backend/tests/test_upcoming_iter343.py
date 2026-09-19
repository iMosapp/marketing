"""Iter 343: Upcoming agenda backend tests (GET /api/upcoming, send-now, cancel)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

USER_ID = "6a978d68b8673c29063aa8b9"  # activation-tester
CONTACT_ID = "6aa413008f0d53e3f2261853"  # Sarah Tester

TESTER = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
OTHER = ("mjeast1985@gmail.com", "NavyBean1!")
ADMIN = ("forest@imosapp.com", "Admin123!")


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tester_token():
    return _login(*TESTER)


@pytest.fixture(scope="module")
def other_token():
    return _login(*OTHER)


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


# ── GET /upcoming shape ─────────────────────────────────────────────
def test_upcoming_shape_and_seed_data(tester_token):
    r = requests.get(f"{API}/upcoming/{USER_ID}?days=14", headers=_hdr(tester_token), timeout=30)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d["timezone"] == "America/Denver", d.get("timezone")
    assert d["days"] == 14
    assert "today" in d and len(d["today"]) == 10
    for k in ("you", "jessi", "dates", "total"):
        assert k in d["counts"]
    assert isinstance(d["groups"], list)
    # groups sorted
    dates = [g["date"] for g in d["groups"]]
    assert dates == sorted(dates)
    # no item today or earlier
    today = d["today"]
    for g in d["groups"]:
        assert g["date"] > today, f"Group {g['date']} not > today {today}"
        for it in g["items"]:
            for f in ("kind", "id", "at", "date", "owner", "title", "contact_id", "contact_name"):
                assert f in it, f"Missing field {f} in item: {it}"

    # Find seeded items
    all_items = [it for g in d["groups"] for it in g["items"]]
    titles = [it.get("title", "") for it in all_items]

    # 'QA_UP Test drive with Sarah' appointment
    testdrive = [it for it in all_items if "QA_UP Test drive" in it.get("title", "")]
    assert testdrive, f"Missing QA_UP Test drive; titles={titles}"
    assert testdrive[0]["kind"] == "appointment"
    assert testdrive[0]["owner"] == "you"

    # 'QA_UP Call about trade-in' task
    calltrade = [it for it in all_items if "QA_UP Call about trade-in" in it.get("title", "")]
    assert calltrade, f"Missing QA_UP Call about trade-in; titles={titles}"
    assert calltrade[0]["kind"] == "task"

    # Birthday (owner=you, not handled)
    birthdays = [it for it in all_items if it.get("kind") == "date" and it.get("contact_id") == CONTACT_ID and "birthday" in it.get("title", "").lower()]
    assert birthdays, f"Missing birthday for Sarah Tester; date items={[it for it in all_items if it['kind']=='date']}"
    assert birthdays[0]["owner"] == "you"

    # Sold anniversary
    sold = [it for it in all_items if it.get("kind") == "date" and "sold anniversary" in it.get("title", "").lower()]
    assert sold, f"Missing sold anniversary; date items={[it for it in all_items if it['kind']=='date']}"

    # Auto-text 'Review request' with body starting QA_UP Hey Sarah
    review = [it for it in all_items if it.get("kind") == "auto_text" and it.get("owner") == "jessi" and "review" in it.get("title", "").lower()]
    assert review, f"Missing review request auto_text; auto_text items={[it for it in all_items if it['kind']=='auto_text']}"
    body = review[0].get("body", "") or review[0].get("subtitle", "")
    assert "QA_UP Hey Sarah" in body, f"Body: {body!r}"

    # No unreplaced placeholders in any auto_text
    for it in all_items:
        if it.get("kind") in ("auto_text", "manual_text"):
            assert "{" not in (it.get("body") or ""), f"Unreplaced placeholder: {it.get('body')}"
            assert "{" not in (it.get("subtitle") or ""), f"Unreplaced placeholder subtitle: {it.get('subtitle')}"


# ── days clamping ───────────────────────────────────────────────────
def test_days_clamping(tester_token):
    r0 = requests.get(f"{API}/upcoming/{USER_ID}?days=0", headers=_hdr(tester_token), timeout=30)
    assert r0.status_code == 200 and r0.json()["days"] == 1
    r999 = requests.get(f"{API}/upcoming/{USER_ID}?days=999", headers=_hdr(tester_token), timeout=30)
    assert r999.status_code == 200 and r999.json()["days"] == 60


# ── auth ────────────────────────────────────────────────────────────
def test_auth_403_other_user(other_token):
    r = requests.get(f"{API}/upcoming/{USER_ID}?days=14", headers=_hdr(other_token), timeout=30)
    assert r.status_code == 403, r.text[:300]


def test_auth_401_no_token():
    r = requests.get(f"{API}/upcoming/{USER_ID}?days=14", timeout=30)
    assert r.status_code == 401, r.text[:300]


def test_auth_admin_can_read(admin_token):
    r = requests.get(f"{API}/upcoming/{USER_ID}?days=14", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 200


# ── send-now + cancel ──────────────────────────────────────────────
def _schedule_delayed(token, body, delay=3600):
    r = requests.post(
        f"{API}/messages/schedule-delayed",
        headers=_hdr(token),
        json={
            "user_id": USER_ID,
            "to": "+15005550042",
            "body": body,
            "delay_seconds": delay,
            "contact_id": CONTACT_ID,
            "contact_name": "Sarah Tester",
        },
        timeout=30,
    )
    assert r.status_code in (200, 201), f"schedule-delayed -> {r.status_code} {r.text[:300]}"
    j = r.json()
    return j.get("pending_send_id") or j.get("id") or j.get("_id")


def test_send_now_flow(tester_token):
    sid = _schedule_delayed(tester_token, "QA_UP2 sendnow", delay=3600)
    assert sid, "no pending_send_id returned"

    # Appears in upcoming
    r = requests.get(f"{API}/upcoming/{USER_ID}?days=14", headers=_hdr(tester_token), timeout=30)
    assert r.status_code == 200
    all_items = [it for g in r.json()["groups"] for it in g["items"]]
    ids = [it["id"] for it in all_items]
    assert sid in ids, f"sid {sid} not in upcoming ids {ids[:10]}"

    # send-now
    r2 = requests.post(f"{API}/upcoming/{USER_ID}/sends/{sid}/send-now", headers=_hdr(tester_token), timeout=30)
    assert r2.status_code == 200, r2.text[:300]
    assert r2.json().get("ok") is True

    # Cleanup: try cancel (harmless if already sent/failed)
    requests.post(f"{API}/upcoming/{USER_ID}/sends/{sid}/cancel", headers=_hdr(tester_token), timeout=30)


def test_cancel_flow_and_errors(tester_token, other_token):
    sid = _schedule_delayed(tester_token, "QA_UP2 cancelme", delay=3600)
    assert sid

    r = requests.post(f"{API}/upcoming/{USER_ID}/sends/{sid}/cancel", headers=_hdr(tester_token), timeout=30)
    assert r.status_code == 200 and r.json().get("ok") is True

    # 2nd cancel -> 409
    r2 = requests.post(f"{API}/upcoming/{USER_ID}/sends/{sid}/cancel", headers=_hdr(tester_token), timeout=30)
    assert r2.status_code == 409, r2.text[:200]

    # unknown id -> 404
    r3 = requests.post(f"{API}/upcoming/{USER_ID}/sends/507f1f77bcf86cd799439011/cancel", headers=_hdr(tester_token), timeout=30)
    assert r3.status_code == 404, r3.text[:200]

    # other user (against activation-tester's uid) -> 403
    sid2 = _schedule_delayed(tester_token, "QA_UP2 crossuser", delay=3600)
    r4 = requests.post(f"{API}/upcoming/{USER_ID}/sends/{sid2}/cancel", headers=_hdr(other_token), timeout=30)
    assert r4.status_code in (403, 404), r4.text[:200]
    # cleanup
    requests.post(f"{API}/upcoming/{USER_ID}/sends/{sid2}/cancel", headers=_hdr(tester_token), timeout=30)
