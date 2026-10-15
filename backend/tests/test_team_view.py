"""My Team (services/team_view.py): scope rules and the per-rep numbers, against preview Mongo with a disposable
"QA My Team *" organization (two stores, owner, store manager, three reps, one rep with a texting-ready number). Removed at the end."""
import asyncio
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from services import team_view

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
SUB = "AC" + "6" * 32
MS = "MG" + "8" * 32


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


@pytest.fixture(scope="module")
def world():
    db = adb()
    tag = secrets.token_hex(3)
    now = datetime.now(timezone.utc)
    org_id, other_org = ObjectId(), ObjectId()
    store_a, store_b = str(ObjectId()), str(ObjectId())
    oid = str(org_id)
    ids = {k: ObjectId() for k in ("owner", "mgr", "rep1", "rep2", "rep3", "outsider", "gone")}
    phone = f"+1500555{secrets.randbelow(9000) + 1000}"

    def user(k, role, store, **kw):
        return {"_id": ids[k], "name": f"QA {k} {tag}", "email": f"qa-myteam-{k}-{tag}@invalid.imonsocial.test", "role": role,
                "organization_id": oid, "store_id": store, "status": "active", "created_at": now, **kw}
    run(db.organizations.insert_many([
        {"_id": org_id, "name": f"QA My Team {tag}", "customer": {"billing_status": "active"},
         "twilio": {"subaccount_sid": SUB, "messaging_ready": True, "messaging_service_sid": MS}},
        {"_id": other_org, "name": f"QA My Team Other {tag}", "customer": {"billing_status": "active"}}]))
    run(db.users.insert_many([
        user("owner", "org_admin", store_a, last_login=now),
        user("mgr", "store_manager", store_a, last_login=now),
        user("rep1", "user", store_a, last_login=now - timedelta(hours=2), twilio_number=phone),
        user("rep2", "user", store_a, activation_pending=True),
        user("rep3", "user", store_b, last_login=now - timedelta(days=3)),
        user("gone", "user", store_a, status="deactivated"),
        {"_id": ids["outsider"], "name": "QA outsider", "email": f"qa-myteam-out-{tag}@invalid.imonsocial.test", "role": "org_admin",
         "organization_id": str(other_org), "status": "active", "created_at": now}]))
    r1 = str(ids["rep1"])
    run(db.phone_numbers.insert_one({"phone_number": phone, "organization_id": oid, "assigned_user_id": r1, "number_type": "USER",
                                     "twilio_account_sid": SUB, "messaging_service_sid": MS, "status": "ASSIGNED", "updated_at": now}))
    run(db.contacts.insert_many([{"user_id": r1, "first_name": f"QA c{i} {tag}", "source": "manual", "created_at": now - timedelta(days=d)} for i, d in enumerate((1, 2, 20))]))
    run(db.contact_events.insert_one({"user_id": r1, "event_type": "digital_card_shared", "timestamp": now - timedelta(hours=1)}))
    run(db.messages.insert_many([{"user_id": r1, "sender": "user", "direction": "outbound", "content": f"qa {tag}", "timestamp": now - timedelta(hours=h)} for h in (1, 2, 3)]))
    run(db.voice_notes.insert_one({"user_id": r1, "created_at": now - timedelta(hours=5)}))
    yield {"db": db, "oid": oid, "ids": ids, "users": {k: run(db.users.find_one({"_id": v})) for k, v in ids.items()}}
    uids = [str(v) for v in ids.values()]
    for c in ("contacts", "contact_events", "messages", "voice_notes", "phone_numbers"):
        run(db[c].delete_many({"user_id": {"$in": uids}}))
    run(db.phone_numbers.delete_many({"organization_id": oid}))
    run(db.users.delete_many({"_id": {"$in": list(ids.values())}}))
    run(db.organizations.delete_many({"_id": {"$in": [org_id, other_org]}}))


def names(res):
    return sorted(m["name"].split(" ")[1] for m in res["members"])


def test_owner_sees_whole_org_except_self_and_deactivated(world):
    res = run(team_view.team(world["db"], world["users"]["owner"]))
    assert res["scope"] == "organization" and names(res) == ["mgr", "rep1", "rep2", "rep3"]


def test_store_manager_sees_only_their_store(world):
    res = run(team_view.team(world["db"], world["users"]["mgr"]))
    assert res["scope"] == "store" and names(res) == ["owner", "rep1", "rep2"]


def test_rep_cannot_see_my_team(world):
    with pytest.raises(PermissionError):
        run(team_view.team(world["db"], world["users"]["rep1"]))


def test_other_org_admin_cannot_read_this_team(world):
    with pytest.raises(PermissionError):
        run(team_view.team(world["db"], world["users"]["outsider"], org_id=world["oid"]))
    res = run(team_view.team(world["db"], world["users"]["outsider"]))
    assert world["oid"] not in {m["id"] for m in res["members"]} and all(m["name"] != "QA rep1" for m in res["members"])


def test_super_admin_reads_by_org_id(world):
    res = run(team_view.team(world["db"], {"_id": ObjectId(), "role": "super_admin"}, org_id=world["oid"]))
    assert names(res) == ["mgr", "owner", "rep1", "rep2", "rep3"]


def test_rep_numbers_progress_and_activity(world):
    res = run(team_view.team(world["db"], world["users"]["owner"]))
    by = {m["name"].split(" ")[1]: m for m in res["members"]}
    r1, r2, r3 = by["rep1"], by["rep2"], by["rep3"]
    assert r1["week"] == {"contacts": 2, "cards_shared": 1, "texts_sent": 3}
    assert r1["setup"] == {"done": 3, "total": 5}
    assert r1["number"]["status"] == "ready" and r1["number"]["last4"]
    assert r1["activated"] and r1["last_activity"]
    assert r2["number"]["status"] == "none" and not r2["activated"] and r2["week"] == {"contacts": 0, "cards_shared": 0, "texts_sent": 0}
    assert r3["setup"]["done"] == 0 and r3["last_activity"]
    assert "content" not in str(res) or "qa " not in str(res)
