"""Native Messages handoff (POST /api/messages/native-authorize, services/native_handoff.py): the server authorizes the exact recipient
before the app may open the phone's Messages app. Live preview API; QA contacts on Twilio test-range numbers, deleted at the end."""
import os
import secrets
from datetime import timedelta

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

from tests import qa_creds

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
AUTH = f"{BASE}/api/messages/native-authorize"


def login(email):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": qa_creds.password_for(email)}, headers=UA, timeout=30)
    assert r.status_code == 200, r.text[:200]
    b = r.json()
    return {"Authorization": "Bearer " + b["token"], **UA}, b["user"]["_id"]


def fresh_phone(db, scope):
    while True:
        p = f"+1500555{secrets.randbelow(9000) + 1000}"
        if not db.consent_state.find_one({"phone": p}) and not db.contacts.find_one({"phone": p}) and not db.sms_inbound_index.find_one({"phone": p}):
            return p


@pytest.fixture(scope="module")
def world():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    mgr_h, mgr_id = login("qa-manager@invalid.imonsocial.test")    # no texting number: "text from my phone" = native handoff
    oa_h, oa_id = login("qa-orgadmin@invalid.imonsocial.test")     # another organization
    scope = f"user:{mgr_id}"
    phones, ids = [], []

    def contact(owner, **kw):
        p = fresh_phone(db, scope)
        phones.append(p)
        cid = db.contacts.insert_one({"user_id": owner, "first_name": "QA Native", "last_name": secrets.token_hex(3), "phone": p, **kw}).inserted_id
        ids.append(cid)
        return str(cid), p

    w = {"db": db, "mgr": (mgr_h, mgr_id), "oa": (oa_h, oa_id), "mine": contact(mgr_id), "stopped": contact(mgr_id, opted_out=True),
         "theirs": contact(oa_id)}
    yield w
    db.contacts.delete_many({"_id": {"$in": ids}, "first_name": "QA Native"})
    for coll in ("consent_state", "consent_records", "native_handoff_authorizations", "sms_send_log", "sms_disclosure_state"):
        db[coll].delete_many({"phone": {"$in": phones}})
    db.contact_events.delete_many({"contact_id": {"$in": [str(i) for i in ids]}})


def post(h, body):
    return requests.post(AUTH, json=body, headers=h, timeout=30)


def test_requires_sign_in():
    assert requests.post(AUTH, json={"phone": "+15005550052"}, headers=UA, timeout=30).status_code == 401


@pytest.mark.parametrize("bad", ["0", "undefined", "abc", "null"])
def test_malformed_contact_id_is_400(world, bad):
    r = post(world["mgr"][0], {"contact_id": bad})
    assert r.status_code == 400 and r.json()["detail"] == "Invalid contact id"


def test_unknown_contact_is_404(world):
    assert post(world["mgr"][0], {"contact_id": "0123456789abcdef01234567"}).status_code == 404


def test_another_organizations_contact_is_403(world):
    cid, _ = world["theirs"]
    assert post(world["mgr"][0], {"contact_id": cid}).status_code == 403


def test_number_must_belong_to_the_contact(world):
    cid, _ = world["mine"]
    _, other = world["stopped"]
    r = post(world["mgr"][0], {"contact_id": cid, "phone": other})
    assert r.status_code == 400 and "not this contact's number" in r.json()["detail"]


def test_bad_phone_is_400(world):
    assert post(world["mgr"][0], {"phone": "123"}).status_code == 400


def test_unknown_purpose_is_refused(world):
    cid, _ = world["mine"]
    r = post(world["mgr"][0], {"contact_id": cid, "purpose": "bogus"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bad_purpose"


def test_opted_out_contact_is_refused(world):
    cid, _ = world["stopped"]
    r = post(world["mgr"][0], {"contact_id": cid})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "opted_out"


@pytest.mark.skipif((os.environ.get("CONSENT_MODE") or "").lower() == "shadow", reason="consent enforce only")
def test_no_consent_is_refused_then_allowed_after_consent(world):
    h, _ = world["mgr"]
    cid, phone = world["mine"]
    r = post(h, {"contact_id": cid})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "consent_required" and r.json()["detail"]["needs"]
    rec = requests.post(f"{BASE}/api/consent/contact/{cid}", json={"scopes": ["requested_info"], "method": "verbal_in_person"}, headers=h, timeout=30)
    assert rec.status_code == 200, rec.text[:200]
    r = post(h, {"contact_id": cid})
    assert r.status_code == 200, r.text[:200]
    b = r.json()
    assert b["authorized"] is True and b["phone"] == phone and b["purpose"] == "conversational" and b["ttl_s"] == 120
    doc = world["db"].native_handoff_authorizations.find_one({"_id": b["token"]})
    assert doc and doc["contact_id"] == cid and doc["phone"] == phone and doc["expires_at"] - doc["issued_at"] == timedelta(seconds=120)


def test_marketing_needs_written_opt_in(world):
    cid, _ = world["mine"]
    r = post(world["mgr"][0], {"contact_id": cid, "purpose": "marketing"})
    assert r.status_code == 409 and r.json()["detail"]["code"] in ("marketing_consent_required",)


def test_thank_you_text_without_a_business_number_returns_its_authorization(world):
    h, me = world["mgr"]
    cid, phone = world["mine"]
    r = requests.post(f"{BASE}/api/relationship-health/{me}/advocates/{cid}/thank", json={"mode": "text"}, headers=h, timeout=30)
    assert r.status_code == 200, r.text[:200]
    b = r.json()
    assert b["via"] == "native" and b["native_authorization"]["phone"] == phone == b["phone"]


def test_thank_you_text_to_an_opted_out_contact_is_refused_and_not_logged(world):
    h, me = world["mgr"]
    cid, _ = world["stopped"]
    r = requests.post(f"{BASE}/api/relationship-health/{me}/advocates/{cid}/thank", json={"mode": "text"}, headers=h, timeout=30)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "opted_out"
    assert not world["db"].contacts.find_one({"_id": ObjectId(cid)}).get("last_thanked_at")


def test_thank_preview_no_longer_writes_an_authorization(world):
    h, me = world["mgr"]
    cid, phone = world["stopped"]
    r = requests.get(f"{BASE}/api/relationship-health/{me}/advocates/{cid}/thank", headers=h, timeout=30)
    assert r.status_code == 200 and not world["db"].native_handoff_authorizations.find_one({"phone": phone})
