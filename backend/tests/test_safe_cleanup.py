"""The cleanup guard rails (tests/safe_cleanup.py) can't delete legitimate records. Runs in a THROWAWAY local database
(<DB_NAME>_cleanup_guard_test), never the preview data, and drops it at the end.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_safe_cleanup.py -q"""
import asyncio
import os

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from tests import safe_cleanup as sc

LOOP = asyncio.new_event_loop()
TEST_DB = os.environ["DB_NAME"] + "_cleanup_guard_test"


def run(coro):
    return LOOP.run_until_complete(coro)


@pytest.fixture()
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=LOOP)
    d = client[TEST_DB]
    yield d
    assert d.name.endswith("_cleanup_guard_test")
    run(client.drop_database(TEST_DB))


def _seed(db):
    test_user, real_user, contact = str(ObjectId()), str(ObjectId()), str(ObjectId())
    run(db.users.insert_many([{"email": "real@x.test"}, {"_id": ObjectId(test_user), "user_id": test_user}]))   # account docs have no user_id
    run(db.organizations.insert_one({"name": "Real Org"}))
    run(db.settings.insert_one({"key": "jessi_mms_vision"}))
    run(db.contacts.insert_many([{"user_id": test_user, "first_name": "Test"}, {"user_id": real_user, "first_name": "Real"},
                                 {"first_name": "No owner"}, {"user_id": None, "first_name": "Null owner"}]))
    run(db.messages.insert_many([{"contact_id": contact}, {"contact_id": str(ObjectId())}, {"body": "no contact"}]))
    return test_user, real_user, contact


def test_none_and_junk_ids_delete_nothing(db):
    _seed(db)
    before = {c: run(db[c].count_documents({})) for c in ("users", "organizations", "settings", "contacts", "messages")}
    assert run(sc.wipe_by_owner(db, [None, "", "None", "0", 123], [None, ""])) == {}
    assert {c: run(db[c].count_documents({})) for c in before} == before


def test_only_the_test_owner_rows_go_and_account_collections_are_never_touched(db):
    test_user, real_user, contact = _seed(db)
    removed = run(sc.wipe_by_owner(db, [test_user, None], [contact, ""]))
    assert removed == {"contacts": 1, "messages": 1}
    assert run(db.users.count_documents({})) == 2 and run(db.organizations.count_documents({})) == 1 and run(db.settings.count_documents({})) == 1
    assert {c["first_name"] for c in run(db.contacts.find({}).to_list(10))} == {"Real", "No owner", "Null owner"}
    assert run(db.messages.count_documents({})) == 2


def test_refuses_a_non_local_database(monkeypatch, db):
    for url in ("mongodb+srv://u:p@cluster0.example.mongodb.net/app", "mongodb://u:p@10.0.0.5:27017", "mongodb://db.internal:27017", ""):
        monkeypatch.setenv("MONGO_URL", url)
        with pytest.raises(sc.UnsafeCleanup):
            sc.require_preview_db()
        with pytest.raises(sc.UnsafeCleanup):
            run(sc.wipe_by_owner(db, [str(ObjectId())]))


def test_refuses_a_production_api_url(monkeypatch):
    monkeypatch.setenv("REACT_APP_BACKEND_URL", "https://app.imonsocial.com")
    with pytest.raises(sc.UnsafeCleanup):
        sc.require_preview_db()


def test_valid_ids_keeps_only_object_ids():
    oid = str(ObjectId())
    assert sc.valid_ids([oid, None, "", "abc", 7, oid.upper()]) == [oid]
