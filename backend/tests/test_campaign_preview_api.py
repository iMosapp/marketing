"""Customer Preview Trio API: /api/campaign-preview candidates + preview (REAL LLM). Nothing must be saved or sent."""
import os
import re

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ALEX = ("alex@summitpartners.example", "DemoShots123!")
ALEX_ID = "6ad142f76ea24cad00bf0502"
CHECKIN = "6ad142f76ea24cad00bf056a"
BDAY = "6ad142f76ea24cad00bf0551"
ANNIV = "6ad142f76ea24cad00bf0560"
QA = ("qa-manager@invalid.imonsocial.test", "Manager123!")
QA_ID = "6a9b2b82cc6e7504dafc33f2"
QA_CAMP = "6ad088461aa1deaf729e0441"
LLM_TIMEOUT = 180

mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": creds[0], "password": creds[1]}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {creds[0]}: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def alex():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login(ALEX)}"})
    return s


@pytest.fixture(scope="module")
def trio(alex):
    r = alex.get(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}/candidates", timeout=60)
    assert r.status_code == 200, r.text
    return r.json()["contacts"]


# ── candidates ──
def test_candidates_three_distinct_with_why(trio):
    assert len(trio) == 3
    assert len({c["id"] for c in trio}) == 3
    assert [c["why"] for c in trio] == ["Most history", "A different situation", "Little history"]
    for c in trio:
        assert isinstance(c["name"], str) and c["name"]
        assert {"vehicle", "memos", "messages", "details"} <= set(c)


@pytest.mark.parametrize("camp", [BDAY, ANNIV])
def test_candidates_other_summit_campaigns(alex, camp):
    r = alex.get(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{camp}/candidates", timeout=60)
    assert r.status_code == 200 and len(r.json()["contacts"]) == 3


def test_candidates_401_without_token():
    r = requests.get(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}/candidates", timeout=30)
    assert r.status_code == 401


@pytest.mark.parametrize("camp", ["notanid", str(ObjectId()), QA_CAMP])
def test_candidates_404_invalid_or_other_users_campaign(alex, camp):
    r = alex.get(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{camp}/candidates", timeout=30)
    assert r.status_code == 404, r.text


def test_candidates_other_user_path_forbidden(alex):
    r = alex.get(f"{BASE_URL}/api/campaign-preview/{QA_ID}/{QA_CAMP}/candidates", timeout=30)
    assert r.status_code in (403, 404), r.text


def test_preview_401_without_token():
    r = requests.post(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}", json={"contact_ids": ["x"]}, timeout=30)
    assert r.status_code == 401


# ── preview ──
def test_preview_empty_ids_400(alex):
    r = alex.post(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}", json={"contact_ids": []}, timeout=30)
    assert r.status_code == 400


def test_preview_404_other_campaign(alex):
    r = alex.post(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{QA_CAMP}", json={"contact_ids": ["a"]}, timeout=30)
    assert r.status_code == 404


def test_preview_template_mode_resolves_variables(alex, trio):
    body = {"contact_ids": [c["id"] for c in trio], "message_template": "Hi {first_name}, checking in!", "channel": "sms", "ai_enabled": False}
    r = alex.post(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}", json=body, timeout=60)
    assert r.status_code == 200, r.text
    rows = r.json()["previews"]
    assert len(rows) == 3
    for row, c in zip(rows, trio):
        assert not row["error"] and "{" not in row["message"]
        assert row["message"].startswith("Hi ") and row["message"].endswith("checking in!")
        assert row["name"].split()[0] in row["message"]


def test_preview_not_owned_contact_row_error(alex, trio):
    other = mdb.contacts.find_one({"user_id": QA_ID}, {"_id": 1}) or mdb.contacts.find_one({"user_id": {"$nin": [ALEX_ID]}}, {"_id": 1})
    body = {"contact_ids": [str(other["_id"]), "garbage", trio[0]["id"]], "message_template": "Hi {first_name}", "ai_enabled": False}
    r = alex.post(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}", json=body, timeout=60)
    assert r.status_code == 200, r.text
    rows = r.json()["previews"]
    assert rows[0]["error"] == "Not one of your customers"
    assert rows[1]["error"] == "Not one of your customers"
    assert not rows[2]["error"] and rows[2]["message"]


def test_preview_real_ai_three_different_messages_nothing_saved(alex, trio):
    before = (mdb.campaign_pending_sends.count_documents({}), mdb.messages.count_documents({}), mdb.tasks.count_documents({}))
    body = {"contact_ids": [c["id"] for c in trio], "step_context": "90-day check-in: see how they are enjoying their purchase",
            "message_template": "Hi {first_name}, it's been 90 days - how's everything going?", "channel": "sms", "ai_enabled": True}
    r = alex.post(f"{BASE_URL}/api/campaign-preview/{ALEX_ID}/{CHECKIN}", json=body, timeout=LLM_TIMEOUT)
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data["previews"]
    print("\n".join(f"{x['name']}: {x['message']!r} used={x['used']} knew={x['knew']} err={x['error']}" for x in rows))
    assert data["ai"] is True and len(rows) == 3
    msgs = [x["message"] for x in rows]
    assert all(m.strip() for m in msgs), rows
    assert len(set(msgs)) == 3
    for x in rows:
        assert not x["error"]
        assert not re.search(r"\{[a-z_]+\}", x["message"]), x["message"]
        assert isinstance(x["knew"], list) and x["knew"]
        assert set(x["used"]) <= set(x["knew"])
    after = (mdb.campaign_pending_sends.count_documents({}), mdb.messages.count_documents({}), mdb.tasks.count_documents({}))
    assert after == before, f"preview wrote data: before={before} after={after}"
