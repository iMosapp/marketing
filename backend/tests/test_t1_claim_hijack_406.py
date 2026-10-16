"""T1 iteration 406 regression for the thread-claim hijack: a rep (same store OR another org) must not be able to POST
/api/inboxes/conversations/{conv}/claim on another rep's private 1:1 thread (no inbox, no assigned_to) - today it answers 200, rewrites
conversation.user_id AND moves the contact (contact.user_id) to the claimer, who then reads every private note / memo / fact.
Also: cross-org managers must not reassign another org's contact via POST /api/engagement/reassign-lead; POST /api/tasks/{me} must not
accept another rep's contact_id. Uses the same-org demo (tests/test_same_org_rep_isolation helpers) and restores it (collaborator scenario).
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_t1_claim_hijack_406.py -v"""
import os

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

from tests import test_same_org_rep_isolation as t

mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
API = t.BASE + "/api"


@pytest.fixture(scope="module", autouse=True)
def demo():
    t.run(t._wipe_leftovers())
    t.run(t._seed())
    for key in t.S["uid"]:
        r = requests.post(f"{API}/auth/login", json={"email": f"qa-sameorg-{key.lower()}@invalid.imonsocial.test", "password": t.PW}, timeout=30)
        assert r.status_code == 200, r.text
        t.S["tok"][key] = r.json()["token"]
    r = requests.post(f"{API}/auth/login", json={"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}, timeout=30)
    t.S["tok"]["X"], t.S["xid"] = r.json()["token"], str(r.json()["user"].get("_id") or r.json()["user"].get("id"))
    r = requests.post(f"{API}/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}, timeout=30)
    t.S["tok"]["XM"], t.S["xmid"] = r.json()["token"], str(r.json()["user"].get("_id") or r.json()["user"].get("id"))
    yield
    mdb.tasks.delete_many({"title": "TEST_T1 probe"})
    t.scenario("collaborator")   # leave the manual demo in place like tests/seed_same_org_demo.py


def _reset_owner():
    """Undo what a successful hijack moves (contact, open tasks, enrollments - see services/inboxes._move_book)."""
    a, c = t.S["uid"]["A"], t.S["ca"]
    mdb.contacts.update_one({"_id": ObjectId(c)}, {"$set": {"user_id": a}, "$unset": {"claimed_by": ""}})
    mdb.tasks.update_many({"contact_id": c, "title": {"$ne": "TEST_T1 probe"}}, {"$set": {"user_id": a}, "$unset": {"transferred_at": ""}})
    mdb.contact_events.delete_many({"contact_id": c, "event_type": {"$in": ["lead_claimed", "lead_reassigned"]}})


def h(who):
    return {"Authorization": f"Bearer {t.S['tok'][who]}"}


@pytest.mark.parametrize("who", ["A2", "X"])
def test_rep_cannot_claim_another_reps_private_thread(who):
    t.scenario("none")
    _reset_owner()
    r = requests.post(f"{API}/inboxes/conversations/{t.S['conv']}/claim", headers=h(who), json={}, timeout=30)
    owner = mdb.contacts.find_one({"_id": ObjectId(t.S["ca"])})["user_id"]
    conv = mdb.conversations.find_one({"_id": ObjectId(t.S["conv"])})
    _reset_owner()
    assert r.status_code in (403, 404), f"{who} claimed A's private thread: {r.status_code} {r.text[:150]}"
    assert owner == t.S["uid"]["A"] and conv.get("user_id") == t.S["uid"]["A"]


def test_cross_org_manager_cannot_reassign_lead():
    _reset_owner()
    r = requests.post(f"{API}/engagement/reassign-lead", headers=h("XM"), json={"contact_id": t.S["ca"], "new_user_id": t.S["xmid"]}, timeout=30)
    owner = mdb.contacts.find_one({"_id": ObjectId(t.S["ca"])})["user_id"]
    _reset_owner()
    mdb.contact_events.delete_many({"contact_id": t.S["ca"], "event_type": "lead_reassigned"})
    assert r.status_code in (403, 404) and owner == t.S["uid"]["A"], f"{r.status_code} {r.text[:150]}"


@pytest.mark.parametrize("who,uid_key", [("A2", "A2"), ("X", None)])
def test_task_create_refuses_foreign_contact(who, uid_key):
    t.scenario("none")
    uid = t.S["uid"]["A2"] if uid_key else t.S["xid"]
    r = requests.post(f"{API}/tasks/{uid}", headers=h(who), json={"title": "TEST_T1 probe", "contact_id": t.S["ca"], "type": "follow_up"}, timeout=30)
    mdb.tasks.delete_many({"title": "TEST_T1 probe"})
    assert r.status_code in (403, 404), f"{r.status_code} {r.text[:200]}"


def test_cross_org_manager_cannot_assign_foreign_conversation():
    t.scenario("none")
    _reset_owner()
    r = requests.post(f"{API}/inboxes/conversations/{t.S['conv']}/assign", headers=h("XM"), json={"user_id": t.S["xmid"]}, timeout=30)
    owner = mdb.contacts.find_one({"_id": ObjectId(t.S["ca"])})["user_id"]
    _reset_owner()
    assert r.status_code in (403, 404) and owner == t.S["uid"]["A"], f"{r.status_code} {r.text[:150]} owner_moved={owner != t.S['uid']['A']}"
