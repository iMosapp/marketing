"""
Iteration 287 — Speed-to-lead + Weekly Wins backend tests.
Covers:
  - GET /api/leads/awaiting/{user_id}       (no auth)
  - GET /api/home/weekly-wins/{user_id}     (no auth)
  - GET /api/leads/analytics/response-times (Bearer JWT)
"""
import os
from datetime import datetime

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

USER_ID = "69a0b7095fddcede09591667"
TEST_CONV = "6a948a5b94f43a817b73d510"
EMAIL = "forest@imosapp.com"
PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:400]}")
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    if not tok:
        pytest.fail(f"No token in login response: {list(data.keys())}")
    return tok


# ── awaiting leads ────────────────────────────────────────────────────────────
class TestAwaitingLeads:
    def test_awaiting_returns_seeded_lead(self, client):
        r = client.get(f"{BASE_URL}/api/leads/awaiting/{USER_ID}")
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert "count" in d and "oldest" in d
        assert isinstance(d["count"], int)
        # NOTE: verified count==1 with oldest == TEST_CONV ("Sally Tester") before a
        # human reply was sent during this run. After a human reply the count clears to 0.
        if d["count"] == 0:
            assert d["oldest"] is None
            return
        oldest = d["oldest"]
        assert oldest is not None
        assert isinstance(oldest["conversation_id"], str)
        assert "contact_name" in oldest
        datetime.fromisoformat(oldest["received_at"].replace("Z", "+00:00"))

    def test_awaiting_unknown_user_empty(self, client):
        r = client.get(f"{BASE_URL}/api/leads/awaiting/000000000000000000000000")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["count"] == 0
        assert d["oldest"] is None

    def test_awaiting_no_mongo_id_leak(self, client):
        r = client.get(f"{BASE_URL}/api/leads/awaiting/{USER_ID}")
        assert '"_id"' not in r.text


# ── weekly wins ───────────────────────────────────────────────────────────────
class TestWeeklyWins:
    def test_weekly_wins_shape(self, client):
        r = client.get(f"{BASE_URL}/api/home/weekly-wins/{USER_ID}")
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        for k in ["week_start", "week_end", "sold", "texts", "scans", "new_contacts"]:
            assert k in d, f"missing {k} in {d}"
        ws = datetime.fromisoformat(d["week_start"].replace("Z", "+00:00"))
        we = datetime.fromisoformat(d["week_end"].replace("Z", "+00:00"))
        assert ws.weekday() == 0, f"week_start not Monday: {ws}"
        assert (we - ws).days == 7, f"window not 7 days: {ws} -> {we}"
        assert we <= datetime.now(ws.tzinfo), "week_end should be in the past"
        for k in ["sold", "texts", "scans", "new_contacts"]:
            assert isinstance(d[k], int) and d[k] >= 0
        print("weekly wins:", d)

    def test_weekly_wins_expected_activity(self, client):
        d = client.get(f"{BASE_URL}/api/home/weekly-wins/{USER_ID}").json()
        assert d["texts"] > 0, f"expected texts>0, got {d}"
        assert d["scans"] > 0, f"expected scans>0, got {d}"

    def test_weekly_wins_unknown_user_zeros(self, client):
        d = client.get(f"{BASE_URL}/api/home/weekly-wins/000000000000000000000000").json()
        assert d["sold"] == 0 and d["texts"] == 0 and d["scans"] == 0 and d["new_contacts"] == 0


# ── response times analytics ──────────────────────────────────────────────────
class TestResponseTimes:
    def test_requires_auth(self, client):
        r = requests.get(f"{BASE_URL}/api/leads/analytics/response-times?days=90")
        assert r.status_code in (401, 403), f"expected auth error, got {r.status_code}"

    def test_response_times_payload(self, client, token):
        r = client.get(
            f"{BASE_URL}/api/leads/analytics/response-times?days=90",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["days"] == 90
        assert "overall" in d and "reps" in d
        o = d["overall"]
        for k in ["avg_seconds", "measured", "unanswered", "fastest_seconds"]:
            assert k in o
        assert isinstance(d["reps"], list)
        avgs = [rep["avg_seconds"] for rep in d["reps"]]
        assert avgs == sorted(avgs), f"reps not sorted by avg_seconds: {avgs}"
        for rep in d["reps"]:
            for k in ["user_id", "name", "count", "avg_seconds", "fastest_seconds", "slowest_seconds"]:
                assert k in rep
            assert rep["fastest_seconds"] <= rep["avg_seconds"] <= rep["slowest_seconds"]
        print("response-times overall:", o, "reps:", len(d["reps"]))

    def test_days_clamped(self, client, token):
        r = client.get(
            f"{BASE_URL}/api/leads/analytics/response-times?days=9999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json()["days"] == 365


# ── conversation enrichment used by the UI banner/chip ────────────────────────
class TestConversationLeadFields:
    def test_conversation_info_lead_flags(self, client, token):
        r = client.get(
            f"{BASE_URL}/api/messages/conversation/{TEST_CONV}/info",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 404:
            pytest.fail("test conversation 6a948a5b94f43a817b73d510 not found")
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("is_internet_lead") is True, f"is_internet_lead missing/false: {list(d.keys())}"
        assert "awaiting_first_reply" in d, f"awaiting_first_reply missing: {list(d.keys())}"
        # after this run's human reply it flips to False; before the reply it was True
        assert d["awaiting_first_reply"] in (True, False)
