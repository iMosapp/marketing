"""Phase 3 Step 2: Jessi search v2. Covers unfiled voice memos (the searcher's own only, with a direct link), saved facts and personal details on
contacts the searcher may see, natural-language time frames, and isolation: a same-store teammate, the store manager and another org's rep
never get the owner's private details or unfiled memos.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_phase3_search_v2.py -q"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId

from routers.database import get_db
from services import date_window as dw
from services import memory_search as ms
from tests import test_same_org_rep_isolation as t

NOW = datetime.now(timezone.utc)
X = {}


def _fp():
    return "qa-p3-" + uuid.uuid4().hex


@pytest.fixture(scope="module", autouse=True)
def seeded():
    t.run(t._wipe_leftovers())
    t.run(t._seed())
    for key in t.S["uid"]:
        r = requests.post(f"{t.BASE}/api/auth/login", json={"email": f"qa-sameorg-{key.lower()}@invalid.imonsocial.test", "password": t.PW}, timeout=30)
        assert r.status_code == 200, r.text
        t.S["tok"][key] = r.json()["token"]
    t.scenario("collaborator")
    db, a, tag = get_db(), t.S["uid"]["A"], {"qa_same_org_iso": True}
    base = {"user_id": a, "store_id": t.S["store"], "organization_id": t.S["org"], "ownership_type": "org", "status": "active", "source": "manual", **tag}

    async def seed():
        await db.contacts.update_one({"_id": ObjectId(t.S["ca"])}, {"$set": {"personal_details.hobbies": ["fly fishing", "woodworking"]}})
        await db.contact_facts.insert_one({"contact_id": t.S["ca"], "owner_user_id": a, "store_id": t.S["store"], "layer": "identity", "key": "family.daughter",
                                           "statement": "Daughter Emma plays violin in the youth symphony", "status": "current", "occurred_at": NOW - timedelta(days=10),
                                           "recorded_at": NOW - timedelta(days=10), "fingerprint": _fp(), "created_at": NOW})
        await db.voice_notes.insert_one({"contact_id": t.S["ca"], "user_id": a, "recorded_by_id": a, "kind": "memo", "duration": 9, "audio_url": "qa/none.m4a",
                                         "transcript": "Walt wants a pontoon boat for the lake house", "created_at": NOW - timedelta(days=90)})
        X["unfiled"] = str((await db.voice_notes.insert_one({"contact_id": None, "unattached": True, "user_id": a, "kind": "memo", "duration": 30, "audio_url": "qa/none.m4a",
                                                             "title": "Dealer summit keynote", "transcript": "Notes from the Lamborghini dealer summit keynote, follow up on the fleet idea",
                                                             "summary": "Lamborghini dealer summit keynote", "created_at": NOW - timedelta(days=2)})).inserted_id)
        X["feb"] = str((await db.contacts.insert_one({**base, "first_name": "Febby", "last_name": "Qametfeb", "phone": "+15005550193",
                                                      "how_we_met": {"event": "Boat show", "date": f"{_last_feb()}-02", "summary": "At the Boat show, Feb", "source": "qa"},
                                                      "created_at": NOW - timedelta(days=3), "updated_at": NOW})).inserted_id)
        X["old"] = str((await db.contacts.insert_one({**base, "first_name": "Olden", "last_name": "Qaoldie", "phone": "+15005550194",
                                                      "created_at": NOW - timedelta(days=400), "updated_at": NOW - timedelta(days=400)})).inserted_id)
        t.S["cids"] += [X["feb"], X["old"]]
    t.run(seed())
    yield
    t.run(db.voice_notes.delete_one({"_id": ObjectId(X["unfiled"]), "user_id": a}))
    t.run(t._wipe())


def _last_feb() -> int:
    return NOW.year if NOW.month > 2 else NOW.year - 1


def _user(key: str) -> dict:
    return t.run(get_db().users.find_one({"_id": ObjectId(t.S["uid"][key])}))


def _other_org_user() -> dict:
    u = t.run(get_db().users.find_one({"email": "activation-tester@invalid.imonsocial.test"}))
    assert u and str(u.get("organization_id")) != t.S["org"]
    return u


def _ids(res: dict) -> set:
    return {r["contact_id"] for r in res.get("results") or []}


# ---- time frames (pure) ----
def test_date_window_phrases():
    now = datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)
    w = dw.parse("who did I meet last February", now)
    assert (w["start"].date().isoformat(), w["end"].date().isoformat(), dw.strip("who did I meet last February", w)) == ("2026-02-01", "2026-03-01", "who did I meet")
    w = dw.parse("the guy I talked to three months ago about a boat", now)
    assert w["start"] < datetime(2026, 7, 17, tzinfo=timezone.utc) < w["end"] and "boat" in dw.strip("the guy I talked to three months ago about a boat", w)
    w = dw.parse("people I met in October", now)
    assert w["start"].date().isoformat() == "2026-10-01" and w["end"] <= now
    assert dw.parse("who did I meet last October", now)["start"].year == 2025
    assert dw.parse("who did I meet in November", now)["start"].year == 2025
    assert dw.parse("in the past 3 months", now)["start"].date().isoformat() == "2026-07-17"
    assert dw.parse("last week", now)["start"].date().isoformat() == "2026-10-07" and dw.parse("last month", now)["start"].date().isoformat() == "2026-09-02"
    assert dw.parse("who is into Harleys", now) is None and dw.parse("who mentioned the Mustang Market", now) is None and dw.parse("who may want a truck", now) is None


# ---- personal facts and details ----
def test_owner_finds_saved_fact_and_personal_detail():
    a = _user("A")
    assert t.S["ca"] in {h["contact_id"] for h in t.run(ms.scan(get_db(), a, ["violin"])) if h["source"] == "fact"}
    assert t.S["ca"] in {h["contact_id"] for h in t.run(ms.scan(get_db(), a, ["fly fishing"])) if h["source"] == "fact"}
    assert t.S["ca"] in _ids(t.run(ms.search(get_db(), a, "the guy whose daughter plays violin")))


@pytest.mark.parametrize("key", ["A2", "M"])
def test_teammate_and_manager_get_no_private_details(key):
    u = _user(key)
    for terms in (["violin"], ["fly fishing"], ["pontoon"], [t.SECRET]):
        assert not [h for h in t.run(ms.scan(get_db(), u, terms)) if h["contact_id"] in t.S["cids"]], (key, terms)
    assert not _ids(t.run(ms.search(get_db(), u, "the guy whose daughter plays violin"))) & set(t.S["cids"])


def test_other_org_rep_gets_nothing():
    u = _other_org_user()
    for terms in (["violin"], ["fly fishing"], ["lamborghini"]):
        assert not [h for h in t.run(ms.scan(get_db(), u, terms)) if h["contact_id"] in t.S["cids"]]
        assert not [h for h in t.run(ms.unfiled(get_db(), u, terms)) if h["memo_id"] == X["unfiled"]]


# ---- unfiled voice memos ----
def test_owner_finds_unfiled_memo_with_direct_link():
    res = t.run(ms.search(get_db(), _user("A"), "the memo about the Lamborghini dealer summit"))
    m = next((m for m in res["memos"] if m["memo_id"] == X["unfiled"]), None)
    assert m and m["link"] == f"/voice-memos?memo={X['unfiled']}" and "Lamborghini" in m["quote"]
    assert "voice memo you have not filed" in ms.spoken(res)


@pytest.mark.parametrize("key", ["A2", "M"])
def test_unfiled_memos_stay_with_the_recorder(key):
    assert not t.run(ms.unfiled(get_db(), _user(key), ["lamborghini"]))
    assert not t.run(ms.unfiled(get_db(), _user(key), [], {"start": NOW - timedelta(days=7), "end": NOW + timedelta(minutes=1)}))


def test_unfiled_memo_api_owner_and_teammate():
    r = requests.post(f"{t.BASE}/api/memory/search", json={"query": "the memo about the Lamborghini dealer summit"}, headers={"Authorization": f"Bearer {t.S['tok']['A']}"}, timeout=90)
    assert r.status_code == 200 and X["unfiled"] in {m["memo_id"] for m in r.json().get("memos") or []}, r.text[:300]
    r = requests.post(f"{t.BASE}/api/memory/search", json={"query": "the memo about the Lamborghini dealer summit"}, headers={"Authorization": f"Bearer {t.S['tok']['A2']}"}, timeout=90)
    assert r.status_code == 200 and not r.json().get("memos") and not _ids(r.json()) & set(t.S["cids"])


# ---- time frames end to end ----
def test_who_did_i_meet_last_february():
    res = t.run(ms.search(get_db(), _user("A"), "who did I meet last February"))
    assert res["mode"] == "met" and X["feb"] in _ids(res) and X["old"] not in _ids(res) and t.S["ca"] not in _ids(res)


def test_people_i_met_in_this_month():
    month = NOW.strftime("%B")
    res = t.run(ms.search(get_db(), _user("A"), f"people I met in {month}"))
    assert res["mode"] == "met" and t.S["ca"] in _ids(res) and X["old"] not in _ids(res) and X["feb"] not in _ids(res)
    assert not _ids(t.run(ms.search(get_db(), _user("A2"), f"people I met in {month}"))) & set(t.S["cids"])


def test_topic_with_time_frame():
    a = _user("A")
    assert t.S["ca"] in _ids(t.run(ms.search(get_db(), a, "who mentioned a pontoon boat three months ago")))
    assert t.S["ca"] not in _ids(t.run(ms.search(get_db(), a, "who mentioned a pontoon boat last week")))


def test_memos_from_a_time_frame_include_unfiled():
    res = t.run(ms.search(get_db(), _user("A"), "memos from the past week"))
    assert res["mode"] == "memos" and X["unfiled"] in {m["memo_id"] for m in res["memos"]}
