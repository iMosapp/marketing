"""Duplicate cleanup (service + live Jessi tools) and the GPT-Live shopper audition (browser session, no OpenAI: fake httpx).
The brain probes at the end run the real LLM (Emergent key)."""
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import duplicates as dups  # noqa: E402
from services import live_shops as ls  # noqa: E402
from services import live_voice as lv  # noqa: E402

TESTER_EMAIL = "activation-tester@invalid.imonsocial.test"
pytestmark = pytest.mark.asyncio


async def _tester(db):
    return await db.users.find_one({"email": TESTER_EMAIL})


def _c(uid, first, last, phone="", email="", days_ago=0, **extra):
    at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"_id": ObjectId(), "user_id": uid, "first_name": first, "last_name": last, "phone": phone, "email": email, "status": "active", "tags": ["QA Dup"],
            "created_at": at, "updated_at": at, "last_activity_at": at, **extra}


async def _seed(db, uid):
    rows = [_c(uid, "Tod", "Berry", "+15005550401", vehicle="2024 Tahoe"), _c(uid, "Todd", "Berry", "+15005550402", days_ago=30),
            _c(uid, "Sarah", "Same", "+15005550411"), _c(uid, "Sarah", "Same", "(500) 555-0411", days_ago=3),
            _c(uid, "Emil", "Twin", "+15005550421", email="twin@invalid.imonsocial.test"), _c(uid, "E.", "Twin", "+15005550422", email="Twin@invalid.imonsocial.test"),
            _c(uid, "Mike", "Solo", "+15005550431"), _c(uid, "Mike", "Snow", "+15005550432")]
    await db.contacts.insert_many(rows)
    return rows


async def _wipe(db, rows):
    ids = [r["_id"] for r in rows]
    await db.contacts.delete_many({"_id": {"$in": ids}})
    for col in dups.MIGRATE:
        await db[col].delete_many({"contact_id": {"$in": [str(i) for i in ids]}})


async def test_find_sets_phone_email_and_sounds_alike():
    db = get_db()
    user = await _tester(db)
    rows = await _seed(db, str(user["_id"]))
    try:
        sets = await dups.find_sets(db, str(user["_id"]))
        mine = [s for s in sets if all(any(c["id"] == str(r["_id"]) for r in rows) for c in s["contacts"])]
        by_reason = {s["reason"]: s for s in mine}
        assert set(by_reason) == {"phone", "email", "name"}, [(s["reason"], s["name"]) for s in mine]
        assert by_reason["phone"]["name"] == "Sarah Same" and len(by_reason["phone"]["contacts"]) == 2
        assert by_reason["email"]["reason_label"] == "Same email" and {c["last_name"] for c in by_reason["email"]["contacts"]} == {"Twin"}
        assert by_reason["name"]["reason_label"].startswith("Sounds alike") and "Tod Berry" in by_reason["name"]["reason_label"] and "Todd Berry" in by_reason["name"]["reason_label"]
        assert by_reason["name"]["contacts"][0]["first_name"] == "Tod", "most recently active record leads the set"
        assert not any("Solo" in s["name"] or "Snow" in s["name"] for s in mine), "Mike Solo / Mike Snow are different people"
        pub = dups.public(sets)
        assert all("_rows" not in s for s in pub)
    finally:
        await _wipe(db, rows)


async def test_merge_set_moves_records():
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    rows = await _seed(db, uid)
    tod, todd = rows[0], rows[1]
    await db.tasks.insert_one({"contact_id": str(todd["_id"]), "user_id": uid, "title": "QA Dup task", "status": "pending", "created_at": datetime.now(timezone.utc)})
    await db.messages.insert_one({"contact_id": str(todd["_id"]), "user_id": uid, "content": "QA dup msg", "created_at": datetime.now(timezone.utc)})
    try:
        r = await dups.merge_set(db, uid, [str(tod["_id"]), str(todd["_id"])])
        assert r["primary_id"] == str(tod["_id"]) and r["merged"] == 1 and r["records_migrated"] == 2
        assert (await db.contacts.find_one({"_id": todd["_id"]}))["status"] == "merged"
        assert await db.tasks.count_documents({"contact_id": str(tod["_id"]), "title": "QA Dup task"}) == 1
        sets = await dups.find_sets(db, uid)
        assert not any("Berry" in s["name"] for s in sets), "merged records leave the duplicate list"
        with pytest.raises(ValueError):
            await dups.merge(db, uid, str(tod["_id"]), str(tod["_id"]))
        with pytest.raises(LookupError):
            await dups.merge(db, uid, str(tod["_id"]), str(ObjectId()))
    finally:
        await _wipe(db, rows)
        await db.tasks.delete_many({"title": "QA Dup task"})
        await db.messages.delete_many({"content": "QA dup msg"})


async def test_jessi_duplicate_tools_without_llm():
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    rows = await _seed(db, uid)
    live = {"_id": ObjectId(), "live_id": "qa-dup", "user_id": uid, "mode": "assistant"}
    await db[lv.COLL].insert_one({**live, "status": "open", "transcript": [], "delegations": [], "pending": None, "started_at": datetime.now(timezone.utc)})
    try:
        said, opened = await lv._find_duplicates(db, user, live)
        assert "set" in said and "Sarah Same (2 records)" in said and opened == {"kind": "duplicates"}
        said, pending, opened = await lv._merge_duplicates(db, user, {"name": "Tod Berry"}, live)
        assert pending and pending["type"] == "merge" and len(pending["ids"]) == 2 and pending["ids"][0] == str(rows[0]["_id"])
        assert "2 records for Tod Berry" in said and "Say yes" in said and opened["kind"] == "contact" and opened["id"] == str(rows[0]["_id"])
        said, opened = await lv._merge_now(db, user, pending)
        assert said.startswith("Done. Tod Berry is one record now") and opened["id"] == str(rows[0]["_id"])
        assert (await db.contacts.find_one({"_id": rows[1]["_id"]}))["status"] == "merged"
        said, pending, _ = await lv._merge_duplicates(db, user, {"name": "Mike Solo"}, live)
        assert pending is None and "do not see duplicate records for Mike Solo" in said
        # "merge them" right after Jessi used one of two Sarah Same records
        live["last_choices"] = [str(rows[2]["_id"]), str(rows[3]["_id"])]
        said, pending, _ = await lv._merge_duplicates(db, user, {"name": ""}, live)
        assert pending and set(pending["ids"]) == {str(rows[2]["_id"]), str(rows[3]["_id"])}
    finally:
        await _wipe(db, rows)
        await db[lv.COLL].delete_one({"_id": live["_id"]})


async def test_brain_picks_duplicate_tools():
    """Real LLM: the planner maps the spoken asks onto find_duplicates / merge_duplicates / confirm."""
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    rows = await _seed(db, uid)
    live = {"_id": ObjectId(), "live_id": "qa-dup-brain", "user_id": uid, "mode": "assistant", "pending": None}
    await db[lv.COLL].insert_one({**live, "status": "open", "transcript": [], "delegations": [], "started_at": datetime.now(timezone.utc)})
    try:
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Hey, do I have any duplicate contacts in my book?"}], "d1")
        assert r["tool"] == "find_duplicates" and r["open"] == {"kind": "duplicates"}, r
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "do I have duplicates?"}, {"role": "assistant", "text": r["content"]}, {"role": "rep", "text": "Merge Tod Berry for me"}], "d2")
        assert r["tool"] == "merge_duplicates" and r["pending"] is True, r
        live["pending"] = (await db[lv.COLL].find_one({"_id": live["_id"]}))["pending"]
        r = await lv.delegate(db, live, user, [{"role": "assistant", "text": "I found 2 records for Tod Berry. Say yes to merge them."}, {"role": "rep", "text": "Yes, go ahead"}], "d3")
        assert r["tool"] == "confirm" and r["content"].startswith("Done. Tod Berry is one record now"), r
        assert (await db.contacts.find_one({"_id": rows[1]["_id"]}))["status"] == "merged"
    finally:
        await _wipe(db, rows)
        await db[lv.COLL].delete_one({"_id": live["_id"]})


async def test_shopper_audition_session(monkeypatch):
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    captured = {}

    class FakeResp:
        status_code = 201
        text = ""

        def json(self):
            return {"session": {"id": "live_shop1"}, "transport": {"type": "webrtc", "sdp": "v=0 answer"}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured.update({"body": json})
            return FakeResp()

    monkeypatch.setattr(lv.httpx, "AsyncClient", FakeClient)
    shop = await ls.audition(db, forest, {"industry": "automotive", "department": "sales", "direction": "inbound", "voice": "cinder", "store_name": "LHM Jeep", "offering": "2024 Wrangler"})
    assert shop["voice"] == "cinder" and shop["meta"]["department"] == "sales" and shop["meta"]["persona_name"]
    assert shop["meta"]["persona_name"] in shop["instructions"] and "browser audition" in shop["instructions"] and "LHM Jeep" in shop["instructions"]
    assert "Wait for them to pick up" in shop["greet_instruction"] and shop["meta"]["opening_line"] in shop["greet_instruction"]
    out_dir = await ls.audition(db, forest, {"industry": "automotive", "department": "sales", "direction": "outbound"})
    assert out_dir["greet_instruction"].startswith("The rep just called you back") and out_dir["voice"] in (*ls.FEMININE, *ls.MASCULINE)
    with pytest.raises(ValueError):
        await ls.audition(db, forest, {"industry": "automotive", "department": "no_such_department"})

    out = await lv.create_session(db, forest, "shopper", "v=0 offer", {"industry": "automotive", "department": "sales", "direction": "inbound", "voice": "gleam"})
    try:
        assert out["voice"] == "gleam" and out["idle_close_s"] == lv.SHOPPER_IDLE_S and out["cap_left_s"] is None and out["shopper"]["persona_name"]
        assert out["greet_instruction"].startswith("You placed this call")
        body = captured["body"]["session"]
        assert body["audio"]["output"]["voice"] == "gleam" and body["delegation"] == {"type": "client"} and "never admit you are an AI" in body["instructions"]
        assert "Home screen" not in body["input"][0]["content"][0]["text"]
        live = await lv.get_live(db, out["live_id"])
        assert live["mode"] == "shopper" and live["shopper"]["script_id"]
        r = await lv.delegate(db, live, forest, [{"role": "assistant", "text": "Hi, I'm calling about the Wrangler."}, {"role": "rep", "text": "Sure, what can I help with?"}], "d1")
        assert r["tool"] == "stay_in_character" and r["kind"] == "thinking" and r["end"] is False
        r = await lv.delegate(db, live, forest, [{"role": "rep", "text": "Saturday at 10 works, see you then."}, {"role": "assistant", "text": "Perfect, Saturday at 10. Thanks so much, bye!"}], "d2")
        assert r["tool"] == "hang_up" and r["end"] is True and "disconnecting" in r["content"]
        assert lv.serialize(await lv.get_live(db, out["live_id"]))["shopper"]["department"] == "sales"
    finally:
        await db[lv.COLL].delete_one({"live_id": out["live_id"]})
