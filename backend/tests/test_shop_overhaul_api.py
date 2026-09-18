"""API tests for Mystery Shop overhaul: difficulty, direction_mix, retry, night_guard, people prefs, demo challenges."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
CLIENT_ID = "6aa6d7dfb4c41decb2734ec4"
ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASS = "Admin123!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_client_has_new_fields(auth):
    r = requests.get(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    client = data["client"]
    assert "difficulty" in client
    assert "direction_mix" in client
    assert "retry" in client and "tries" in client["retry"] and "spacing" in client["retry"]
    assert "night_guard" in client
    assert client["night_guard"].get("start") == "08:00"
    assert client["night_guard"].get("end") == "20:00"
    assert "reissue_unreachable" in client
    # people month
    people = data.get("people", [])
    if people:
        p0 = people[0]
        assert "month" in p0
        m = p0["month"]
        for k in ("planned", "completed", "scheduled", "unreachable", "inbound", "outbound", "avg_score", "quota", "next_at"):
            assert k in m, f"missing {k} in month"
    # grading
    grading = data.get("grading", {})
    assert "sales" in grading
    sales = grading["sales"]
    assert "inbound" in sales and sales["inbound"].get("name") == "Sales Phone-Up"
    assert "outbound" in sales and sales["outbound"].get("name") == "Internet Sales Call"
    assert "service" in grading


def test_put_client_valid(auth):
    payload = {
        "difficulty": "hard",
        "direction_mix": "outbound",
        "retry": {"tries": 2, "spacing": "same_day", "by_dept": {"service": {"tries": 4}}},
        "reissue_unreachable": False,
        "scorecards": {"sales:outbound": None},
    }
    r = requests.put(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    g = requests.get(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, timeout=20).json()["client"]
    assert g["difficulty"] == "hard"
    assert g["direction_mix"] == "outbound"
    assert g["retry"]["tries"] == 2
    assert g["retry"]["spacing"] == "same_day"
    by_dept = g.get("retry_by_dept") or g["retry"].get("by_dept") or {}
    assert by_dept.get("service", {}).get("tries") == 4
    assert g["reissue_unreachable"] is False


def test_put_client_invalid_coerced(auth):
    payload = {
        "difficulty": "insane",
        "direction_mix": "sideways",
        "retry": {"tries": 99, "spacing": "whenever"},
    }
    r = requests.put(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    g = requests.get(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, timeout=20).json()["client"]
    assert g["difficulty"] == "medium"
    assert g["direction_mix"] == "mixed"
    assert g["retry"]["tries"] == 5


def test_put_client_restore(auth):
    payload = {
        "difficulty": "medium",
        "direction_mix": "mixed",
        "retry": {"tries": 3, "spacing": "next_day", "by_dept": {}},
        "reissue_unreachable": True,
    }
    r = requests.put(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, json=payload, timeout=20)
    assert r.status_code == 200
    g = requests.get(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}", headers=auth, timeout=20).json()["client"]
    assert g["difficulty"] == "medium"
    assert g["direction_mix"] == "mixed"
    assert g["retry"]["tries"] == 3
    assert g["retry"]["spacing"] == "next_day"
    assert g["reissue_unreachable"] is True


def test_people_prefs_flow(auth):
    # Create
    payload = {
        "name": "QA Sched Tester",
        "phone": "5005559301",
        "department": "sales",
        "hours": {"start": "10:00", "end": "16:00", "days": [1, 2, 3]},
        "timezone": "America/Chicago",
        "difficulty": "easy",
        "monthly_quota": 7,
    }
    r = requests.post(f"{BASE_URL}/api/shop-clients/{CLIENT_ID}/people", headers=auth, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    person = r.json()
    pid = person.get("id") or person.get("_id")
    assert pid, person
    assert person.get("timezone") == "America/Chicago"
    assert person.get("difficulty") == "easy"
    assert person.get("monthly_quota") == 7
    assert person.get("hours", {}).get("start") == "10:00"

    try:
        # Invalid timezone
        r = requests.put(f"{BASE_URL}/api/shop-clients/people/{pid}", headers=auth,
                         json={"timezone": "Mars/Olympus"}, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

        # Clear
        r = requests.put(f"{BASE_URL}/api/shop-clients/people/{pid}", headers=auth,
                         json={"hours": {}, "timezone": "", "difficulty": "", "monthly_quota": -1}, timeout=20)
        assert r.status_code == 200, r.text
        p = r.json()
        assert not p.get("timezone")
        assert not p.get("difficulty")
        assert not p.get("monthly_quota")
        hrs = p.get("hours") or {}
        assert not hrs or not hrs.get("start")
    finally:
        d = requests.delete(f"{BASE_URL}/api/shop-clients/people/{pid}", headers=auth, timeout=20)
        assert d.status_code in (200, 204)


def test_demo_challenges_direction_filter(auth):
    r = requests.get(f"{BASE_URL}/api/shop-clients/demo/challenges?industry=automotive&direction=outbound",
                     headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    challenges = data if isinstance(data, list) else data.get("challenges", [])
    sales_out = [c for c in challenges if (c.get("direction") == "outbound")]
    assert len(sales_out) == len(challenges), f"non-outbound leaked: {challenges}"
    sales_dept_out = [c for c in challenges if c.get("direction") == "outbound" and c.get("department") == "sales"]
    assert len(sales_dept_out) >= 2, f"expected >=2 outbound sales, got {len(sales_dept_out)}"

    r = requests.get(f"{BASE_URL}/api/shop-clients/demo/challenges?industry=automotive&direction=inbound",
                     headers=auth, timeout=20)
    assert r.status_code == 200
    data = r.json()
    challenges = data if isinstance(data, list) else data.get("challenges", [])
    assert all(c.get("direction") == "inbound" for c in challenges)
