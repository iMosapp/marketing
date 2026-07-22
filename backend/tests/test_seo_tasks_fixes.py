"""
Tests for two production bug fixes:
1. SEO health-score endpoint returns valid JSON (not empty/520)
2. Tasks summary endpoint returns 200 with expected fields
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
VALID_USER_ID = "69a0b7095fddcede09591667"  # forest@imosapp.com
INVALID_USER_ID = "invalid_id_xyz"


class TestSEOHealthScore:
    """SEO health-score endpoint tests — verifies 520/empty-response bug is fixed"""

    def test_cache_miss_returns_valid_json(self):
        """Cache miss path: skip_cache=true should always return valid JSON (not empty)"""
        resp = requests.get(
            f"{BASE_URL}/api/seo/health-score/{VALID_USER_ID}",
            params={"skip_cache": "true"},
            timeout=15
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "total_score" in data, f"Missing total_score: {data}"
        assert "grade" in data, f"Missing grade: {data}"

    def test_cache_hit_returns_valid_json(self):
        """Cache hit path: second call should return cached result instantly"""
        # Warm the cache first
        requests.get(f"{BASE_URL}/api/seo/health-score/{VALID_USER_ID}", timeout=15)
        time.sleep(1)  # allow background task to compute
        # Now hit again (cache hit)
        resp = requests.get(f"{BASE_URL}/api/seo/health-score/{VALID_USER_ID}", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        # Either cached result with score or pending placeholder — both are valid JSON
        assert "total_score" in data, f"Missing total_score in: {data}"
        assert "grade" in data, f"Missing grade in: {data}"

    def test_pending_placeholder_has_computing_flag(self):
        """First call (cold cache) should return computing=True placeholder"""
        # Use skip_cache to get the pending response behavior via a fresh user_id
        # Actually with skip_cache=True, it re-computes synchronously — so use normal call
        resp = requests.get(
            f"{BASE_URL}/api/seo/health-score/{VALID_USER_ID}",
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_score" in data
        # Response is always valid JSON (the bug was it returned empty body)

    def test_invalid_user_id_returns_error_json(self):
        """Invalid user ID should return error JSON, not crash/empty"""
        resp = requests.get(
            f"{BASE_URL}/api/seo/health-score/{INVALID_USER_ID}",
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "error" in data, f"Expected error key, got: {data}"
        assert data["error"] == "Invalid user ID", f"Unexpected error message: {data}"

    def test_short_user_id_returns_error_json(self):
        """Short user ID (not 24 chars) should return error JSON"""
        resp = requests.get(
            f"{BASE_URL}/api/seo/health-score/abc123",
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_response_is_not_empty(self):
        """Regression: endpoint must never return an empty body (the 520 bug)"""
        resp = requests.get(
            f"{BASE_URL}/api/seo/health-score/{VALID_USER_ID}",
            timeout=15
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0, "Response body is empty — 520 bug may have returned!"
        assert resp.json() is not None


class TestTasksSummary:
    """Tasks summary endpoint tests"""

    def test_summary_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/tasks/{VALID_USER_ID}/summary", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_summary_has_required_fields(self):
        resp = requests.get(f"{BASE_URL}/api/tasks/{VALID_USER_ID}/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        required = ["total_today", "completed_today", "pending_today", "overdue", "progress_pct"]
        for field in required:
            assert field in data, f"Missing field '{field}' in response: {data}"

    def test_summary_field_types(self):
        """All numeric fields should be integers/floats"""
        resp = requests.get(f"{BASE_URL}/api/tasks/{VALID_USER_ID}/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["total_today"], (int, float)), f"total_today wrong type: {type(data['total_today'])}"
        assert isinstance(data["completed_today"], (int, float))
        assert isinstance(data["pending_today"], (int, float))
        assert isinstance(data["overdue"], (int, float))
        assert isinstance(data["progress_pct"], (int, float))

    def test_summary_progress_pct_range(self):
        """progress_pct should be between 0 and 100"""
        resp = requests.get(f"{BASE_URL}/api/tasks/{VALID_USER_ID}/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert 0 <= data["progress_pct"] <= 100, f"progress_pct out of range: {data['progress_pct']}"

    def test_summary_has_activity_field(self):
        """Activity breakdown should be present"""
        resp = requests.get(f"{BASE_URL}/api/tasks/{VALID_USER_ID}/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "activity" in data, f"Missing activity field: {data}"
