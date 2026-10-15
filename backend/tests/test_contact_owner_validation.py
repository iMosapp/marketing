"""Contact create / import / bulk writes must target a real account the caller may write for (services/route_guard.require_real_owner).
Live preview API. Every contact created here is a QA record on a Twilio test-range number and is deleted at the end."""
import os
import re
import secrets

import pytest
import requests
from pymongo import MongoClient

from tests import qa_creds

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
HEX24 = re.compile(r"^[0-9a-fA-F]{24}$")
BAD_IDS = ["0", "undefined", "null", "abc", "None", "1234"]
NONEXISTENT = "0123456789abcdef01234567"


def login(email):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": qa_creds.password_for(email)}, headers=UA, timeout=30)
    assert r.status_code == 200, r.text[:200]
    b = r.json()
    return {"Authorization": "Bearer " + b["token"], **UA}, b["user"]["_id"]


@pytest.fixture(scope="module")
def world():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rep_h, rep_id = login("qa-consent-rep@invalid.imonsocial.test")      # role user, store STORE_A, no organization
    mgr_h, mgr_id = login("qa-manager@invalid.imonsocial.test")          # store_manager on STORE_A
    oa_h, oa_id = login("qa-orgadmin@invalid.imonsocial.test")           # org_admin of another organization
    created = []
    w = {"db": db, "rep": (rep_h, rep_id), "mgr": (mgr_h, mgr_id), "oa": (oa_h, oa_id), "created": created,
         "orphans_before": db.contacts.count_documents({"user_id": {"$not": HEX24}})}
    yield w
    for cid in created:
        db.contacts.delete_one({"_id": __import__("bson").ObjectId(cid), "first_name": "QA Owner"})


def post(h, path, body=None):
    return requests.post(f"{BASE}{path}", json=body if body is not None else {}, headers=h, timeout=30)


def contact_body(**kw):
    return {"first_name": "QA Owner", "last_name": secrets.token_hex(3), "phone": f"+1500555{secrets.randbelow(9000) + 1000}", **kw}


@pytest.mark.parametrize("bad", BAD_IDS)
def test_create_under_malformed_user_id_is_rejected(world, bad):
    h, _ = world["rep"]
    r = post(h, f"/api/contacts/{bad}", contact_body())
    assert r.status_code == 400 and r.json()["detail"] == "Invalid user id", r.text[:200]


def test_create_under_nonexistent_user_is_404(world):
    h, _ = world["rep"]
    r = post(h, f"/api/contacts/{NONEXISTENT}", contact_body())
    assert r.status_code == 404, r.text[:200]


def test_create_for_self_ignores_user_id_in_body(world):
    h, me = world["rep"]
    _, other = world["mgr"]
    r = post(h, f"/api/contacts/{me}", contact_body(user_id=other))
    assert r.status_code == 200, r.text[:200]
    world["created"].append(r.json()["_id"])
    doc = world["db"].contacts.find_one({"_id": __import__("bson").ObjectId(r.json()["_id"])})
    assert doc["user_id"] == me and doc["original_user_id"] == me


def test_rep_cannot_write_for_their_manager(world):
    h, _ = world["rep"]
    _, mgr = world["mgr"]
    assert post(h, f"/api/contacts/{mgr}", contact_body()).status_code == 403


def test_manager_may_write_for_a_rep_in_their_store(world):
    h, _ = world["mgr"]
    _, rep = world["rep"]
    r = post(h, f"/api/contacts/{rep}", contact_body())
    assert r.status_code == 200, r.text[:200]
    world["created"].append(r.json()["_id"])
    assert world["db"].contacts.find_one({"_id": __import__("bson").ObjectId(r.json()["_id"])})["user_id"] == rep


def test_org_admin_of_another_org_cannot_write_for_the_rep(world):
    h, _ = world["oa"]
    _, rep = world["rep"]
    assert post(h, f"/api/contacts/{rep}", contact_body()).status_code == 403


@pytest.mark.parametrize("path,body", [
    ("/api/contacts/{u}/import", {"contacts": [{"first_name": "QA Owner", "phone": "+15005550901"}]}),
    ("/api/contacts/{u}/import-csv/confirm", {"contacts": [{"first_name": "QA Owner", "phone": "+15005550902"}]}),
    ("/api/contacts/{u}/bulk-delete", {"contact_ids": []}),
    ("/api/contacts/{u}/date-optins/bulk", {"contact_ids": [], "field": "birthday", "enabled": True}),
    ("/api/contacts/{u}/find-or-create-and-log", {"phone": "+15005550903", "name": "QA Owner", "event_type": "sms_sent"}),
    ("/api/tags/{u}/assign", {"tag_name": "QA", "contact_ids": []}),
])
@pytest.mark.parametrize("bad", ["0", "undefined"])
def test_import_and_bulk_routes_reject_malformed_user_id(world, path, body, bad):
    h, _ = world["rep"]
    r = post(h, path.format(u=bad), body)
    assert r.status_code == 400, f"{path} {r.status_code} {r.text[:160]}"


def test_import_routes_reject_other_orgs_user(world):
    h, _ = world["oa"]
    _, rep = world["rep"]
    assert post(h, f"/api/contacts/{rep}/import", {"contacts": [{"first_name": "QA Owner", "phone": "+15005550904"}]}).status_code == 403
    assert post(h, f"/api/contacts/{rep}/find-or-create-and-log", {"phone": "+15005550905", "name": "QA Owner"}).status_code == 403


def test_reads_are_unchanged_and_no_new_orphans(world):
    h, _ = world["rep"]
    assert requests.get(f"{BASE}/api/contacts/0", headers=h, timeout=30).status_code == 200  # reads keep answering (empty)
    assert world["db"].contacts.count_documents({"user_id": {"$not": HEX24}}) == world["orphans_before"]
