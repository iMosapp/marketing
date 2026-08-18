"""
Tests for forgot-password SMS reset flow (MongoDB-backed):
- /api/auth/forgot-password/request
- /api/auth/forgot-password/verify
- /api/auth/forgot-password/reset
"""
import pytest
import requests
import os
from datetime import datetime
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "")

TEST_EMAIL = "forest@imosapp.com"
TEST_USER_ID = "69a0b7095fddcede09591667"


@pytest.fixture(scope="module")
def mongo_db():
    """Direct MongoDB connection to read tokens"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(autouse=True)
def cleanup_tokens(mongo_db):
    """Clean up test tokens before each test"""
    mongo_db.password_reset_tokens.delete_many({"user_id": TEST_USER_ID, "email": TEST_EMAIL})
    yield
    # cleanup after
    mongo_db.password_reset_tokens.delete_many({"user_id": TEST_USER_ID, "email": TEST_EMAIL})


# ── Request endpoint ──────────────────────────────────────────────────────────

def test_request_with_email_returns_safe_message(session):
    """Request with valid email returns safe (no-enumeration) message"""
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "reset code" in data["message"].lower() or "sent" in data["message"].lower()
    print(f"PASS: request returns safe message: {data['message']}")


def test_request_stores_token_in_mongodb(session, mongo_db):
    """Token is stored in password_reset_tokens collection"""
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    assert resp.status_code == 200

    token = mongo_db.password_reset_tokens.find_one({"user_id": TEST_USER_ID})
    assert token is not None, "Token not found in MongoDB"
    assert "code" in token
    assert len(str(token["code"])) == 6
    assert token["used"] is False
    assert token["attempts"] == 0
    assert "expires_at" in token
    assert "created_at" in token
    print(f"PASS: Token stored in MongoDB, code={token['code']}, expires_at={token['expires_at']}")


def test_request_with_unknown_identifier_returns_safe_message(session):
    """Unknown identifier returns same safe message (no user enumeration)"""
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": "no-such-user@example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    print(f"PASS: Unknown email returns safe message: {data['message']}")


def test_request_missing_identifier_returns_400(session):
    """Request with no identifier returns 400"""
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={})
    assert resp.status_code == 400
    print("PASS: Missing identifier returns 400")


# ── Verify endpoint ───────────────────────────────────────────────────────────

def test_verify_correct_code_returns_verified_true(session, mongo_db):
    """Correct code returns verified:true"""
    session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    token = mongo_db.password_reset_tokens.find_one({"user_id": TEST_USER_ID})
    assert token, "No token in DB after request"

    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/verify", json={
        "email": TEST_EMAIL,
        "code": token["code"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("verified") is True
    assert "user_id" in data
    print(f"PASS: Correct code verified, user_id={data['user_id']}")


def test_verify_wrong_code_increments_attempts(session, mongo_db):
    """Wrong code increments attempts counter"""
    session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    token = mongo_db.password_reset_tokens.find_one({"user_id": TEST_USER_ID})
    assert token

    wrong_code = "000000" if token["code"] != "000000" else "111111"
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/verify", json={
        "email": TEST_EMAIL,
        "code": wrong_code
    })
    assert resp.status_code == 400

    updated = mongo_db.password_reset_tokens.find_one({"_id": token["_id"]})
    assert updated["attempts"] == 1
    print(f"PASS: Wrong code incremented attempts to {updated['attempts']}")


def test_verify_lockout_after_5_wrong_attempts(session, mongo_db):
    """After 5 wrong attempts, 429 is returned"""
    session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    token = mongo_db.password_reset_tokens.find_one({"user_id": TEST_USER_ID})
    assert token

    wrong_code = "000000" if token["code"] != "000000" else "111111"

    # Make 5 wrong attempts
    for i in range(5):
        resp = session.post(f"{BASE_URL}/api/auth/forgot-password/verify", json={
            "email": TEST_EMAIL,
            "code": wrong_code
        })
        print(f"  attempt {i+1}: status={resp.status_code}")

    # 6th attempt should be 429
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/verify", json={
        "email": TEST_EMAIL,
        "code": wrong_code
    })
    assert resp.status_code == 429, f"Expected 429 after lockout, got {resp.status_code}: {resp.text}"
    print("PASS: 429 returned after 5 wrong attempts")


# ── Reset endpoint ────────────────────────────────────────────────────────────

def test_reset_with_correct_code_updates_password_and_marks_used(session, mongo_db):
    """Reset with valid code updates password and marks token used"""
    session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    token = mongo_db.password_reset_tokens.find_one({"user_id": TEST_USER_ID})
    assert token

    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/reset", json={
        "email": TEST_EMAIL,
        "code": token["code"],
        "new_password": "Admin123!"  # reset back to original
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "success" in data["message"].lower() or "updated" in data["message"].lower()

    # Verify token is marked used
    updated_token = mongo_db.password_reset_tokens.find_one({"_id": token["_id"]})
    assert updated_token["used"] is True
    print(f"PASS: Password reset, token marked as used")


def test_reset_with_already_used_token_returns_400(session, mongo_db):
    """Using an already-used token returns 400"""
    session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    token = mongo_db.password_reset_tokens.find_one({"user_id": TEST_USER_ID})
    assert token

    # First reset
    session.post(f"{BASE_URL}/api/auth/forgot-password/reset", json={
        "email": TEST_EMAIL,
        "code": token["code"],
        "new_password": "Admin123!"
    })

    # Second reset with same code
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/reset", json={
        "email": TEST_EMAIL,
        "code": token["code"],
        "new_password": "Admin123!"
    })
    assert resp.status_code == 400, f"Expected 400 for used token, got {resp.status_code}: {resp.text}"
    print("PASS: Used token returns 400")


# ── Rate limiting ─────────────────────────────────────────────────────────────

def test_rate_limit_4th_request_in_10_minutes_returns_429(session, mongo_db):
    """4th request within 10 minutes returns 429"""
    # cleanup first
    mongo_db.password_reset_tokens.delete_many({"user_id": TEST_USER_ID})

    for i in range(3):
        resp = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
        assert resp.status_code == 200, f"Request {i+1} failed: {resp.status_code}"
        print(f"  request {i+1}: 200 OK")

    # 4th request should be 429
    resp = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": TEST_EMAIL})
    assert resp.status_code == 429, f"Expected 429 on 4th request, got {resp.status_code}: {resp.text}"
    print("PASS: 429 returned on 4th request within 10 minutes")
