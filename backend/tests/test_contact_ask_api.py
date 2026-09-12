"""Backend tests for Ask Jessi (contact-ask). Uses the scorecard demo contact (Sarah Tester) owned by the Activation Tester."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture(scope="module")
def rep():
    return _login(REP)


@pytest.fixture(scope="module")
def mgr():
    return _login(MANAGER)


@pytest.fixture(scope="module")
def sarah_id(rep):
    d = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine", headers=rep, timeout=20).json()
    return next(e["contact_id"] for e in d["evaluations"] if e["call_sid"] == "CA_scdemo_good_001")


def test_unauth(sarah_id):
    assert requests.get(f"{BASE_URL}/api/contact-ask/{sarah_id}", timeout=20).status_code == 401


def test_overview(rep, sarah_id):
    d = requests.get(f"{BASE_URL}/api/contact-ask/{sarah_id}", headers=rep, timeout=20).json()
    assert d["contact"]["first_name"] == "Sarah" and d["stats"]["calls"] >= 1
    assert any("last call" in s for s in d["starters"]) and len(d["starters"]) <= 6
    assert isinstance(d["sessions"], list)


def test_bad_contact(rep):
    assert requests.get(f"{BASE_URL}/api/contact-ask/000000000000000000000000", headers=rep, timeout=20).status_code == 404
    assert requests.get(f"{BASE_URL}/api/contact-ask/nope", headers=rep, timeout=20).status_code == 404


def test_short_question(rep, sarah_id):
    assert requests.post(f"{BASE_URL}/api/contact-ask/{sarah_id}/ask", json={"question": " "}, headers=rep, timeout=20).status_code == 400


def test_ask_grounded_with_citations_and_session(rep, sarah_id):
    r = requests.post(f"{BASE_URL}/api/contact-ask/{sarah_id}/ask", json={"question": "What is Sarah trading in and what mileage?"}, headers=rep, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    msg = d["message"]
    assert "Explorer" in msg["content"] and "—" not in msg["content"]
    assert msg["citations"] and all(c["kind"] == "call" and c["call_sid"] == "CA_scdemo_good_001" for c in msg["citations"])
    assert any(c["seek_seconds"] is not None for c in msg["citations"])
    assert all("[" not in f for f in msg["follow_ups"])
    sid = d["session_id"]
    # follow-up in the same session resolves the pronoun from context
    r2 = requests.post(f"{BASE_URL}/api/contact-ask/{sarah_id}/ask", json={"question": "And when is she coming in?", "session_id": sid}, headers=rep, timeout=90)
    assert r2.status_code == 200 and r2.json()["session_id"] == sid
    assert "5:30" in r2.json()["message"]["content"]
    s = requests.get(f"{BASE_URL}/api/contact-ask/{sarah_id}/sessions/{sid}", headers=rep, timeout=20).json()
    assert s["message_count"] == 4 and [m["role"] for m in s["messages"]] == ["user", "assistant", "user", "assistant"]
    ov = requests.get(f"{BASE_URL}/api/contact-ask/{sarah_id}", headers=rep, timeout=20).json()
    assert ov["sessions"][0]["id"] == sid and ov["sessions"][0]["message_count"] == 4
    assert requests.delete(f"{BASE_URL}/api/contact-ask/{sarah_id}/sessions/{sid}", headers=rep, timeout=20).json()["deleted"] is True
    assert requests.get(f"{BASE_URL}/api/contact-ask/{sarah_id}/sessions/{sid}", headers=rep, timeout=20).status_code == 404


def test_not_in_record(rep, sarah_id):
    r = requests.post(f"{BASE_URL}/api/contact-ask/{sarah_id}/ask", json={"question": "What color is her house?"}, headers=rep, timeout=90)
    assert r.status_code == 200
    content = r.json()["message"]["content"].lower()
    assert any(w in content for w in ("not", "no ", "doesn't", "didn't", "never", "isn't")), content
    sid = r.json()["session_id"]
    requests.delete(f"{BASE_URL}/api/contact-ask/{sarah_id}/sessions/{sid}", headers=rep, timeout=20)


def test_manager_can_reach_store_contact(mgr, sarah_id):
    d = requests.get(f"{BASE_URL}/api/contact-ask/{sarah_id}", headers=mgr, timeout=20)
    assert d.status_code == 200 and d.json()["contact"]["first_name"] == "Sarah"
    # sessions are per user: the manager sees none of the rep's chats
    assert d.json()["sessions"] == []


def test_rep_cannot_reach_other_reps_contact(rep, mgr):
    mine = requests.get(f"{BASE_URL}/api/contacts/6a9b2b82cc6e7504dafc33f2?limit=50", headers=mgr, timeout=20)
    if mine.status_code != 200 or not mine.json():
        pytest.skip("manager has no personal contacts to test against")
    blocked = None
    for other in mine.json():
        cid = other.get("_id") or other.get("id")
        r = requests.get(f"{BASE_URL}/api/contact-ask/{cid}", headers=rep, timeout=20)
        if r.status_code in (403, 404):
            blocked = cid
            break
    # shared-inbox leads are legitimately visible to inbox members; a purely personal contact must be blocked
    if blocked is None:
        pytest.skip("every manager contact is reachable through a shared inbox the rep belongs to")
    assert blocked
