"""Jessi walks the rep's day: services/day_agenda.py + the walkthrough wiring in live_voice (fake OpenAI via httpx; the brain probe at the end is the real LLM)."""
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import day_agenda as da  # noqa: E402
from services import live_voice as lv  # noqa: E402

TESTER_EMAIL = "activation-tester@invalid.imonsocial.test"
pytestmark = pytest.mark.asyncio
TAG = "QA Walk"


async def _tester(db):
    return await db.users.find_one({"email": TESTER_EMAIL})


def _c(uid, first, last, phone):
    now = datetime.now(timezone.utc)
    return {"_id": ObjectId(), "user_id": uid, "first_name": first, "last_name": last, "phone": phone, "status": "active", "tags": [TAG], "created_at": now, "updated_at": now}


async def _seed(db, uid):
    now = datetime.now(timezone.utc)
    jeremy, jay, marcus = _c(uid, "Jeremy", "QA-Cole", "+15005550501"), _c(uid, "Jay", "QA-Spencer", "+15005550502"), _c(uid, "Marcus", "QA-Hill", "+15005550503")
    await db.contacts.insert_many([jeremy, jay, marcus])
    conv_j = {"_id": ObjectId(), "user_id": uid, "contact_id": str(jeremy["_id"]), "channel": "sms", "hot_opportunity": True, "intent_signals": ["Asked about availability"], "last_message_at": now - timedelta(hours=2), "created_at": now, "updated_at": now}
    conv_m = {"_id": ObjectId(), "user_id": uid, "contact_id": str(marcus["_id"]), "channel": "sms", "hot_opportunity": True, "intent_signals": ["Viewed your card 3 times today"], "last_message_at": now - timedelta(hours=1), "created_at": now, "updated_at": now}
    await db.conversations.insert_many([conv_j, conv_m])
    msgs = [
        {"_id": ObjectId(), "conversation_id": str(conv_j["_id"]), "contact_id": str(jeremy["_id"]), "user_id": uid, "sender": "user", "direction": "outbound", "content": "Hey Jeremy, the Gladiator you asked about is here.", "timestamp": now - timedelta(hours=3), "channel": "sms"},
        {"_id": ObjectId(), "conversation_id": str(conv_j["_id"]), "contact_id": str(jeremy["_id"]), "user_id": uid, "sender": "contact", "direction": "inbound", "content": "Is the Gladiator still available? Could come by Saturday.", "timestamp": now - timedelta(hours=2), "channel": "sms"},
        {"_id": ObjectId(), "conversation_id": str(conv_m["_id"]), "contact_id": str(marcus["_id"]), "user_id": uid, "sender": "contact", "direction": "inbound", "content": "What's the price on the Grand Cherokee?", "timestamp": now - timedelta(hours=2), "channel": "sms"},
        {"_id": ObjectId(), "conversation_id": str(conv_m["_id"]), "contact_id": str(marcus["_id"]), "user_id": uid, "sender": "user", "direction": "outbound", "content": "Marcus, 48,900 and I can hold it for you.", "timestamp": now - timedelta(hours=1), "channel": "sms"},
    ]
    await db.messages.insert_many(msgs)
    task = {"_id": ObjectId(), "user_id": uid, "contact_id": str(jay["_id"]), "title": "Trade appraisal follow-up", "status": "pending", "due_date": now - timedelta(days=2), "created_at": now - timedelta(days=3), "action_type": "call"}
    await db.tasks.insert_one(task)
    return {"contacts": [jeremy, jay, marcus], "convs": [conv_j, conv_m], "task": task}


async def _wipe(db, uid, s):
    ids = [c["_id"] for c in s["contacts"]]
    await db.contacts.delete_many({"_id": {"$in": ids}})
    await db.conversations.delete_many({"_id": {"$in": [c["_id"] for c in s["convs"]]}})
    await db.messages.delete_many({"conversation_id": {"$in": [str(c["_id"]) for c in s["convs"]]}})
    await db.tasks.delete_one({"_id": s["task"]["_id"]})
    await db.home_action_state.delete_many({"user_id": uid, "key": {"$in": [f"hot:{c['_id']}" for c in s["convs"]] + [str(i) for i in ids]}})
    await db.home_action_state.delete_many({"user_id": uid, "source": "jessi_walkthrough"})


async def test_agenda_order_and_lines():
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    s = await _seed(db, uid)
    try:
        stops = await da.build(db, uid)
        mine = [x for x in stops if (x.get("contact_id") in {str(c["_id"]) for c in s["contacts"]})]
        kinds = [x["kind"] for x in mine]
        assert kinds[0] == "reply" and mine[0]["first"] == "Jeremy" and mine[0]["hot"] is True, mine
        assert "Is the Gladiator still available?" in mine[0]["say"] and "hasn't heard back" in mine[0]["say"] and mine[0]["key"] == f"hot:{s['convs'][0]['_id']}"
        assert stops[0]["kind"] == "reply", "replies waiting come before everything else"
        jay = next(x for x in mine if x["kind"] == "task")
        assert jay["task_id"] == str(s["task"]["_id"]) and "Trade appraisal follow-up" in jay["say"] and "Overdue touchpoint with Jay QA-Spencer" in jay["say"]
        assert kinds[-1] == "hot" and mine[-1]["first"] == "Marcus" and "Viewed your card 3 times today" in mine[-1]["say"], "answered hot threads close the day"
        assert stops.index(mine[-1]) > stops.index(jay)
        assert all(stops[i]["n"] == i + 1 for i in range(len(stops)))
        text = da.intro(user, stops)
        assert text.startswith("Hey ") and f"{len(stops)} stop" in text and "reply to Jeremy" in text and "First up: Reply to Jeremy QA-Cole" in text
        assert da.open_target(mine[0]) == {"kind": "thread", "id": str(s["contacts"][0]["_id"]), "name": "Jeremy QA-Cole", "first": "Jeremy"}
        assert da.open_target(jay)["kind"] == "task" and da.open_target(None) == {"kind": "home"}
        assert "caught up" in da.intro(user, [])
        assert da.outro(2, 1, 4) == "That's your day. 2 handled, 1 skipped, 1 still open on Home. Go get 'em."
    finally:
        await _wipe(db, uid, s)


async def test_walkthrough_session_and_advance(monkeypatch):
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    s = await _seed(db, uid)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    captured = {}

    class FakeResp:
        status_code = 201
        text = ""

        def json(self):
            return {"session": {"id": "live_walk1"}, "transport": {"type": "webrtc", "sdp": "v=0 answer"}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured.update(json)
            return FakeResp()

    monkeypatch.setattr(lv.httpx, "AsyncClient", FakeClient)
    out = await lv.create_session(db, user, "assistant", "v=0 offer", {"walkthrough": True})
    try:
        assert out["open"] == {"kind": "thread", "id": str(s["contacts"][0]["_id"]), "name": "Jeremy QA-Cole", "first": "Jeremy"}
        assert out["greet_instruction"].startswith("Open with this") and "First up: Reply to Jeremy" in out["greet_instruction"]
        assert out["agenda"][0]["kind"] == "reply" and out["contact_name"] == "Jeremy QA-Cole"
        assert "WALKTHROUGH OF THE REP'S DAY" in captured["session"]["instructions"] and "DAY WALKTHROUGH, the stops in order" in captured["session"]["input"][0]["content"][0]["text"]
        live = await lv.get_live(db, out["live_id"])
        assert live["agenda_pos"] == 0 and live["contact_id"] == str(s["contacts"][0]["_id"])
        assert lv._walkthrough_line(live).startswith("DAY WALKTHROUGH: stop 1 of")
        n = len(live["agenda"])

        # "done" on Jeremy: Home hides that hot thread for today, focus moves to the next stop
        said, opened = await lv._advance(db, user, live, "done")
        assert said.startswith("Done. Next up: ") and live["agenda_pos"] == 1 and opened is not None
        st = await db.home_action_state.find_one({"user_id": uid, "key": f"hot:{s['convs'][0]['_id']}"})
        assert st and st["status"] == "dismissed" and st["source"] == "jessi_walkthrough"
        fresh = await lv.get_live(db, out["live_id"])
        assert fresh["agenda_pos"] == 1 and fresh["agenda_done"] == [f"hot:{s['convs'][0]['_id']}"] and fresh["contact_id"] == live["agenda"][1]["contact_id"]

        # walk to the task and finish it: the task itself gets completed
        while lv._current_stop(live) and lv._current_stop(live)["kind"] != "task":
            await lv._advance(db, user, live, "skip")
        cur = lv._current_stop(live)
        assert cur and cur["task_id"] == str(s["task"]["_id"])
        said, opened = await lv._advance(db, user, live, "done")
        t = await db.tasks.find_one({"_id": s["task"]["_id"]})
        assert t["status"] == "completed" and t["completed_via"] == "jessi_walkthrough"

        # a sent text for the current stop ticks it off and moves on (confirm path, brain stubbed)
        cur = lv._current_stop(live)
        if cur and cur.get("contact_id"):
            from services import scripts as scr
            async def fake_plan(*a, **k):
                return {"tool": "confirm", "args": {}}
            monkeypatch.setattr(scr, "_llm_json", fake_plan)
            async def fake_send(db_, user_, pending):
                return f"Sent to {pending['name']}."
            monkeypatch.setattr(lv, "_send_now", fake_send)
            live_doc = await lv.get_live(db, out["live_id"])
            live_doc["pending"] = {"type": "send_text", "contact_id": cur["contact_id"], "name": cur["name"], "content": "hi", "at": "x"}
            r = await lv.delegate(db, live_doc, user, [{"role": "assistant", "text": "Say yes and I will send it."}, {"role": "rep", "text": "yes"}], "d1")
            assert r["tool"] == "confirm" and r["content"].startswith(f"Sent to {cur['name']}. Done. ") or r["content"].startswith(f"Sent to {cur['name']}. That's your day"), r
            live = await lv.get_live(db, out["live_id"])
            assert cur["key"] in live["agenda_done"]

        # run out the rest
        while lv._current_stop(live):
            said, opened = await lv._advance(db, user, live, "next")
        said, opened = await lv._advance(db, user, live, "next")
        assert said.startswith("That's your day.") and opened == {"kind": "home"}
        ser = lv.serialize(await lv.get_live(db, out["live_id"]))
        assert ser["walkthrough"]["stops"] == n and ser["walkthrough"]["done"] >= 2
    finally:
        await db[lv.COLL].delete_one({"live_id": out["live_id"]})
        await _wipe(db, uid, s)


async def test_brain_moves_the_walkthrough():
    """Real LLM: next / skip / done / draft it are read against the DAY WALKTHROUGH line."""
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    s = await _seed(db, uid)
    agenda = await da.build(db, uid)
    live = {"_id": ObjectId(), "live_id": "qa-walk-brain", "user_id": uid, "mode": "assistant", "pending": None, "agenda": agenda, "agenda_pos": 0, "agenda_done": [], "agenda_skipped": [],
            "contact_id": agenda[0]["contact_id"], "contact_name": agenda[0]["name"]}
    await db[lv.COLL].insert_one({**live, "status": "open", "transcript": [], "delegations": [], "started_at": datetime.now(timezone.utc)})
    try:
        opener = "Hey. First up: reply to Jeremy QA-Cole, he asked if the Gladiator is still available and hasn't heard back. Want me to draft the reply?"
        r = await lv.delegate(db, live, user, [{"role": "assistant", "text": opener}, {"role": "rep", "text": "Skip him for now"}], "d1")
        assert r["tool"] == "next_stop" and r["content"].startswith("Skipped. Next up:"), r
        live = await lv.get_live(db, "qa-walk-brain")
        r = await lv.delegate(db, live, user, [{"role": "assistant", "text": r["content"]}, {"role": "rep", "text": "Already did that one, what's next"}], "d2")
        assert r["tool"] == "next_stop" and r["content"].startswith("Done. Next up:") or r["content"].startswith("Next up:"), r
        live = await lv.get_live(db, "qa-walk-brain")
        cur = lv._current_stop(live)
        if cur and cur.get("contact_id"):
            r = await lv.delegate(db, live, user, [{"role": "assistant", "text": r["content"]}, {"role": "rep", "text": "Yeah, draft it"}], "d3")
            assert r["tool"] in ("send_text", "draft_message") and cur["first"] in r["content"], r
    finally:
        await db[lv.COLL].delete_one({"live_id": "qa-walk-brain"})
        await _wipe(db, uid, s)
