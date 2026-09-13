"""Backend tests for Mystery Shops challenges - iteration 317.

Covers GET/POST /api/shop-clients/challenges, generate endpoint, PUT/DELETE.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
EMAIL = "forest@imosapp.com"
PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.json()
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_list_challenges_shape(auth_headers):
    r = requests.get(f"{BASE_URL}/api/shop-clients/challenges", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "challenges" in data
    assert "departments" in data
    depts = data["departments"]
    assert isinstance(depts, list) and len(depts) == 4
    keys = [d.get("key") for d in depts]
    assert set(keys) == {"sales", "service", "parts", "rental"}
    for d in depts:
        assert "label" in d and d["label"]
    curveballs = data.get("curveballs")
    assert isinstance(curveballs, dict)
    assert set(curveballs.keys()) >= {"sales", "service", "parts", "rental"}


def test_generate_short_scenario_400(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/shop-clients/challenges/generate",
        headers=auth_headers,
        json={"scenario": "too short", "department": "parts", "count": 1},
        timeout=30,
    )
    assert r.status_code == 400, r.text


def test_generate_bad_department_400(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/shop-clients/challenges/generate",
        headers=auth_headers,
        json={
            "scenario": "A shopper asks about warranty coverage on a specific part they need for their truck.",
            "department": "bodyshop",
            "count": 1,
        },
        timeout=30,
    )
    assert r.status_code == 400, r.text


def test_put_nonexistent_challenge_404(auth_headers):
    fake_id = "6aa5f046efccef2627dcedff"  # 24-hex, unlikely to exist
    r = requests.put(
        f"{BASE_URL}/api/shop-clients/challenges/{fake_id}",
        headers=auth_headers,
        json={"title": "x", "purpose": "y", "body": "z" * 50, "department": "parts"},
        timeout=30,
    )
    assert r.status_code == 404, f"{r.status_code}: {r.text}"


def test_create_parts_missing_opening_line_400(auth_headers):
    payload = {
        "title": "QA Missing Opening",
        "department": "parts",
        "purpose": "Test purpose here",
        "body": "This is a sufficiently long body for the challenge to pass length validation checks in the API." * 2,
        "graded_points": ["Greets caller", "Confirms part"],
        "curveballs": ["Wrong VIN"],
        "persona": {
            "name": "Alex Stone",
            "voice": "Casual",
            "summary": "Truck owner",
            # opening_line intentionally missing
        },
    }
    r = requests.post(
        f"{BASE_URL}/api/shop-clients/challenges",
        headers=auth_headers,
        json=payload,
        timeout=30,
    )
    assert r.status_code == 400, f"{r.status_code}: {r.text}"
    body = r.text.lower()
    assert "opening" in body or "name" in body
