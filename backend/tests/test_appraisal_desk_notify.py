"""Desk alerts on submit: every eligible manager is told (in-app + push) and the rep/desk can see who, and whether the push reached a phone.
Runs against the preview backend. Rep = activation-tester, manager = qa-manager (same store). A throwaway rep on a store with no manager proves the gap warning."""
import os
import sys
import uuid

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402
from routers.auth import hash_password  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
SARAH = "6aa413008f0d53e3f2261853"
OUTCOMES = {"sent", "no_device", "sms_only", "quiet_hours", "failed"}
CREATED, TEMP_USERS, TEMP_CONTACTS = [], [], []


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _submit(hdr, contact_id):
    st, b = call("POST", "/api/appraisals", {"contact_id": contact_id, "mode": "vehicle_here"}, hdr)
    assert st == 200, (st, b)
    aid = b["appraisal"]["id"]
    CREATED.append(aid)
    assert call("POST", f"/api/appraisals/{aid}/vehicle", {"manual": {"year": 2021, "make": "Jeep", "model": "Grand Cherokee", "trim": "Limited"}, "method": "manual_vehicle"}, hdr)[0] == 200
    assert call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 48200, "source": "manual"}, hdr)[0] == 200
    st, b = call("POST", f"/api/appraisals/{aid}/submit", None, hdr)
    assert st == 200, (st, b)
    return aid, b


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db = _db()
    for aid in CREATED:
        db.vehicle_appraisals.update_one({"_id": ObjectId(aid)}, {"$set": {"deleted": True}})
    if TEMP_USERS:
        db.users.delete_many({"_id": {"$in": TEMP_USERS}})
        db.notifications.delete_many({"user_id": {"$in": [str(u) for u in TEMP_USERS]}})
    if TEMP_CONTACTS:
        db.contacts.delete_many({"_id": {"$in": TEMP_CONTACTS}})


def test_submit_tells_every_store_manager_and_shows_who(rep, manager):
    aid, b = _submit(rep, SARAH)
    rows = b["notified_managers"]
    assert b["notified"] == len(rows) >= 1
    by_id = {r["user_id"]: r for r in rows}
    assert manager["X-User-ID"] in by_id, "the store manager of the rep's store must be on the list"
    for r in rows:
        assert r["push"] in OUTCOMES and r["push_label"] and r["name"]
        assert r["user_id"] != rep["X-User-ID"], "the submitter never alerts themself"
    # the rep's own view and the manager's desk both carry the same list
    st, mine = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200 and [r["user_id"] for r in mine["workflow"]["notified_managers"]] == list(by_id)
    st, desk = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
    assert st == 200 and [r["user_id"] for r in desk["notified_managers"]] == list(by_id)
    # the in-app alert exists and deep-links to the desk
    n = _db().notifications.find_one({"user_id": manager["X-User-ID"], "type": "appraisal_submitted", "link": f"/appraisal/desk/{aid}"})
    assert n and n["title"] == "Trade appraisal ready"


def test_store_without_a_manager_is_flagged_not_silent():
    db = _db()
    tag = uuid.uuid4().hex[:8]
    store_id = str(ObjectId())
    uid = db.users.insert_one({"email": f"cc-lonely-rep-{tag}@qa.test", "password": hash_password("Lonely123!"), "name": "Lonely Rep", "first_name": "Lonely", "last_name": "Rep",
                               "role": "user", "status": "active", "store_id": store_id, "onboarding_complete": True,
                               "feature_permissions": {"my_tools": {"_enabled": True, "trade_appraisal": True}}}).inserted_id
    TEMP_USERS.append(uid)
    cid = db.contacts.insert_one({"user_id": str(uid), "store_id": store_id, "first_name": "Nobody", "last_name": "Home", "name": "Nobody Home", "phone": "+15005550199"}).inserted_id
    TEMP_CONTACTS.append(cid)
    hdr = auth(*login(f"cc-lonely-rep-{tag}@qa.test", "Lonely123!"))
    aid, b = _submit(hdr, str(cid))
    assert b["appraisal"]["status"] == "submitted"
    assert b["notified"] == 0 and b["notified_managers"] == []
    st, mine = call("GET", f"/api/appraisals/{aid}", None, hdr)
    assert st == 200 and mine["workflow"]["notified_managers"] == [] and mine["workflow"]["notified_manager_ids"] == []
