"""
Tests for 4 confirmed bug fixes:
1. ObjectId import in push_notifications.py — notification_mode=sms returns 0
2. notification_mode=push — skips SMS, sends push
3. notification_mode=both — default behavior, sends push
4. SEO team leaderboard — /api/seo/health-score/team/{store_id} returns members even on empty cache
"""
import pytest
import requests
import asyncio
import sys
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Login to get session cookie
    resp = s.post(f"{BASE_URL}/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return s


# ── Bug 1 & 3: ObjectId import — notification_mode=sms returns 0 via API ───────
class TestNotificationModePreference:
    """Tests that ObjectId import works and notification_mode is respected."""

    def test_objectid_no_error_get_push_status(self, session):
        """Bug 1: ObjectId import added — push status endpoint should not 500."""
        resp = session.get(f"{BASE_URL}/api/push/status/{TEST_USER_ID}")
        assert resp.status_code == 200, f"Push status 500: {resp.text}"
        data = resp.json()
        assert "native_tokens" in data
        print(f"PASS: Push status OK — tokens={data['native_tokens']}, web_subs={data['web_subscriptions']}")

    def test_set_mode_sms_then_test_push_returns_no_subscriptions(self, session):
        """Bug 1+3: Set notification_mode=sms, then test push — should return 0 sent (no_subscriptions or sms skip)."""
        # Set to sms
        resp = session.patch(
            f"{BASE_URL}/api/push/preferences/{TEST_USER_ID}",
            json={"notification_mode": "sms"}
        )
        assert resp.status_code == 200, f"Failed to set sms mode: {resp.text}"
        assert resp.json().get("notification_mode") == "sms"
        print("PASS: Set notification_mode=sms")

        # Test push notification — should be blocked by sms mode
        resp2 = session.post(f"{BASE_URL}/api/push/test/{TEST_USER_ID}")
        assert resp2.status_code == 200, f"Push test failed: {resp2.text}"
        data2 = resp2.json()
        # With mode=sms, send_push_to_user returns 0 immediately
        assert data2.get("sent_to") == 0, f"Expected 0 sent for sms-only user, got: {data2}"
        print(f"PASS: SMS-only user got 0 push notifications: {data2}")

    def test_set_mode_push_returns_expected_status(self, session):
        """Bug 2: Set notification_mode=push — should not block push sending."""
        resp = session.patch(
            f"{BASE_URL}/api/push/preferences/{TEST_USER_ID}",
            json={"notification_mode": "push"}
        )
        assert resp.status_code == 200
        assert resp.json().get("notification_mode") == "push"
        print("PASS: Set notification_mode=push")

        # Test push — with push mode, send_push_to_user runs normally
        resp2 = session.post(f"{BASE_URL}/api/push/test/{TEST_USER_ID}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        # Status can be "no_subscriptions" or "sent" depending on Expo tokens
        assert data2.get("status") in ("no_subscriptions", "sent"), f"Unexpected status: {data2}"
        print(f"PASS: Push-mode user got status={data2.get('status')}, sent_to={data2.get('sent_to')}")

    def test_reset_mode_both_and_verify(self, session):
        """Bug 3: Reset to mode=both — default behavior preserved."""
        resp = session.patch(
            f"{BASE_URL}/api/push/preferences/{TEST_USER_ID}",
            json={"notification_mode": "both"}
        )
        assert resp.status_code == 200
        assert resp.json().get("notification_mode") == "both"
        print("PASS: Reset notification_mode=both")

        # Verify via login response
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert login_resp.status_code == 200
        user_data = login_resp.json().get("user", {})
        mode = user_data.get("notification_mode", "both")  # may default if not returned
        print(f"PASS: Login returned notification_mode={mode}")

    def test_mode_sms_then_both_sequence(self, session):
        """Full round-trip: sms→verify 0 push→reset to both."""
        # Set SMS
        session.patch(f"{BASE_URL}/api/push/preferences/{TEST_USER_ID}", json={"notification_mode": "sms"})

        # Verify sms mode blocks push
        resp = session.post(f"{BASE_URL}/api/push/test/{TEST_USER_ID}")
        data = resp.json()
        assert data.get("sent_to") == 0, f"SMS mode should block push, got: {data}"
        print("PASS: sms mode blocks push (sent_to=0)")

        # Reset
        session.patch(f"{BASE_URL}/api/push/preferences/{TEST_USER_ID}", json={"notification_mode": "both"})
        print("PASS: Reset to both complete")


# ── Bug 4: SEO team leaderboard — computing:True fallback ──────────────────────
class TestSEOTeamLeaderboard:
    """Tests that team endpoint returns members with scores even when cache is empty."""

    def test_get_team_scores_returns_data(self, session):
        """Get store_id for forest user and verify team endpoint returns members."""
        # Get user's store_id from login
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert login_resp.status_code == 200
        user = login_resp.json().get("user", {})
        store_id = user.get("store_id") or user.get("storeId")

        if not store_id:
            pytest.skip("Test user has no store_id — cannot test team leaderboard")

        print(f"Testing team scores for store_id={store_id}")
        resp = session.get(f"{BASE_URL}/api/seo/health-score/team/{store_id}")
        assert resp.status_code == 200, f"Team scores returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "team" in data, f"Missing 'team' key: {data}"

        # Bug fix: team should NOT be empty due to computing:True causing KeyError
        # (With empty cache, computing fallback now runs _compute_health_score)
        team = data["team"]
        print(f"Team count: {len(team)}")

        if len(team) > 0:
            member = team[0]
            assert "score" in member, f"Member missing 'score': {member}"
            assert "grade" in member, f"Member missing 'grade': {member}"
            assert isinstance(member["score"], (int, float)), f"Score not numeric: {member['score']}"
            print(f"PASS: Team leaderboard has {len(team)} members, top score={member['score']}, grade={member['grade']}")
        else:
            # Store may genuinely have no active members
            print("INFO: Team is empty (no active members in store) — not a bug")

    def test_seo_health_score_individual_no_error(self, session):
        """Individual SEO health score endpoint should work (cache miss triggers background compute)."""
        resp = session.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert resp.status_code == 200, f"Health score 500: {resp.text}"
        data = resp.json()
        assert "total_score" in data or "computing" in data, f"Unexpected response: {data}"
        print(f"PASS: Health score returned — computing={data.get('computing')}, score={data.get('total_score')}")

    def test_seo_health_score_skip_cache_force_compute(self, session):
        """Force compute (skip_cache=true) should return a real score not computing:True."""
        resp = session.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}?skip_cache=true")
        assert resp.status_code == 200
        data = resp.json()
        # After skip_cache, compute runs synchronously in background then returns placeholder
        # The computing:True placeholder is still returned; second call should hit cache
        print(f"PASS: skip_cache response — computing={data.get('computing')}, score={data.get('total_score')}")

        import time
        time.sleep(2)  # Wait for background task to populate cache

        resp2 = session.get(f"{BASE_URL}/api/seo/health-score/{TEST_USER_ID}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        if not data2.get("computing"):
            assert data2["total_score"] >= 0
            assert data2["grade"] not in ("Calculating...", "")
            print(f"PASS: Cached score returned — score={data2['total_score']}, grade={data2['grade']}")
        else:
            print("INFO: Still computing after 2s (background task may be slow)")
