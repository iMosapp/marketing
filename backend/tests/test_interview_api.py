"""Backend regression for the Onboarding Voice Interview endpoints.
Assumes tests/interview_sim.py --keep left a completed session for activation-tester."""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL") or [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("MONGO_URL=")][0]
DB_NAME = os.environ.get("DB_NAME") or [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("DB_NAME=")][0]

REP_EMAIL = "activation-tester@invalid.imonsocial.test"
REP_PASS = "NewPass123!"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": REP_EMAIL, "password": REP_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ---- status ----
def test_status_shape(auth_headers):
    r = requests.get(f"{BASE_URL}/api/interview/status", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "session" in d and "voice" in d and "phone" in d and "can_call" in d and "persona_filled" in d
    assert d["voice"]["configured"] is False
    assert d["voice"]["status"] == "not_configured"
    assert d["voice"]["enrolled"] is False
    assert d["phone"] == "(500) •••-0006"
    assert d["can_call"] is True
    assert 0 <= d["persona_filled"] <= 11
    # session should be either completed (sim --keep) or failed (from a start test earlier)
    if d["session"]:
        assert d["session"]["status"] in ("completed", "failed", "dialing", "live", "building", "abandoned"), d["session"]["status"]
        if d["session"]["status"] == "completed":
            assert d["session"]["extracted"]["bio"]
            assert isinstance(d["session"]["highlights"], list)
            assert isinstance(d["session"]["applied_fields"], list)
            assert isinstance(d["session"]["turns"], list)
            assert isinstance(d["session"]["labels"], dict)
            assert len(d["session"]["covered"]) == 17
            assert d["session"]["topics_total"] == 17


# ---- sessions/{sid} ----
def test_get_session_ok_and_auth(auth_headers, db):
    st = requests.get(f"{BASE_URL}/api/interview/status", headers=auth_headers, timeout=30).json()
    if not st.get("session"):
        pytest.skip("no session for tester")
    sid = st["session"]["id"]
    r = requests.get(f"{BASE_URL}/api/interview/sessions/{sid}", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    assert r.json()["id"] == sid
    # 401 without auth
    r2 = requests.get(f"{BASE_URL}/api/interview/sessions/{sid}", timeout=30)
    assert r2.status_code == 401
    # 404 for bad id
    r3 = requests.get(f"{BASE_URL}/api/interview/sessions/deadbeef", headers=auth_headers, timeout=30)
    assert r3.status_code == 404
    # 404 for another user's session
    other = db.interview_sessions.find_one({"user_id": {"$ne": str(db.users.find_one({"email": REP_EMAIL})["_id"])}})
    if other:
        r4 = requests.get(f"{BASE_URL}/api/interview/sessions/{other['_id']}", headers=auth_headers, timeout=30)
        assert r4.status_code == 404


# ---- rebuild ----
def test_rebuild_completed_session(auth_headers, db):
    st = requests.get(f"{BASE_URL}/api/interview/status", headers=auth_headers, timeout=30).json()
    if not st.get("session") or st["session"]["status"] != "completed":
        pytest.skip("no completed session; sim --keep required")
    sid = st["session"]["id"]
    r = requests.post(f"{BASE_URL}/api/interview/sessions/{sid}/rebuild", headers=auth_headers, timeout=200)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "completed"
    bio = d["extracted"]["bio"]
    assert bio and len(bio) > 20
    assert "\u2014" not in bio
    # verify persona.bio in Mongo
    rep = db.users.find_one({"email": REP_EMAIL})
    assert rep["persona"]["bio"] == bio
    assert rep.get("persona_interviewed_at") is not None


# ---- voice DELETE ----
def test_delete_voice_noop(auth_headers):
    r = requests.delete(f"{BASE_URL}/api/interview/voice", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["voice"]["status"] == "not_configured"


# ---- public twiml token gating ----
def test_public_twiml_bad_token(db):
    s = db.interview_sessions.find_one({"user_id": str(db.users.find_one({"email": REP_EMAIL})["_id"])}, sort=[("created_at", -1)])
    if not s:
        pytest.skip("no session")
    r = requests.post(f"{BASE_URL}/api/interview/call/twiml/{s['_id']}?t=WRONG", timeout=30)
    assert r.status_code == 404


def test_public_call_status_204(db):
    s = db.interview_sessions.find_one({"user_id": str(db.users.find_one({"email": REP_EMAIL})["_id"])}, sort=[("created_at", -1)])
    if not s or not s.get("token"):
        pytest.skip("no session token")
    r = requests.post(f"{BASE_URL}/api/interview/call/status/{s['_id']}?t={s['token']}", data={"CallStatus": "ringing"}, timeout=30)
    assert r.status_code == 204


# ---- regression: scripts endpoint ----
def test_scripts_regression(auth_headers):
    r = requests.get(f"{BASE_URL}/api/scripts", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    body = r.json()
    # accept either {scripts:[...]} or list
    scripts = body.get("scripts") if isinstance(body, dict) else body
    assert isinstance(scripts, list) and len(scripts) > 0
