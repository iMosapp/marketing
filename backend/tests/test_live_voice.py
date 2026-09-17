"""Live Jessi (GPT-Live-1) brain + API. No OpenAI Live session is opened: the session doc is seeded directly and
`create_session` is exercised against a fake httpx client. The brain itself runs the real LLM (Emergent key)."""
import os
import pytest
import requests
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import live_voice as lv  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
FOREST = {"email": "forest@imosapp.com", "password": "Admin123!"}
TESTER = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}
pytestmark = pytest.mark.asyncio


def _token(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def forest_h():
    return {"Authorization": f"Bearer {_token(FOREST)}"}


@pytest.fixture(scope="module")
def tester_h():
    return {"Authorization": f"Bearer {_token(TESTER)}"}


async def _tester(db):
    return await db.users.find_one({"email": TESTER["email"]})


async def _seed_live(db, user, mode="assistant"):
    live_id = "test" + ObjectId().__str__()[-8:]
    doc = {"live_id": live_id, "user_id": str(user["_id"]), "user_name": user.get("name"), "mode": mode, "openai_session_id": "live_fake", "voice": "gleam",
           "config": dict(lv.DEFAULTS), "status": "open", "started_at": datetime.now(timezone.utc), "ended_at": None, "seconds": 0, "cost_usd": 0.0, "close_reason": None,
           "transcript": [], "delegations": [], "pending": None, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
    await db[lv.COLL].insert_one(doc)
    return doc


async def test_config_and_prompt():
    cfg = lv.clean_config({"voice": "vesper", "energy": 9, "pacing": 0, "brevity": "x", "greeting": "  Yo {first}  ", "daily_cap_min": 1000})
    assert cfg["voice"] == "vesper" and cfg["energy"] == 5 and cfg["pacing"] == 1 and cfg["brevity"] == 4 and cfg["greeting"] == "Yo {first}" and cfg["daily_cap_min"] == 240
    assert lv.clean_config({"voice": "nope"})["voice"] == "gleam"
    text = lv.assistant_instructions(cfg, {"name": "Forest Ward", "role": "super_admin"})
    assert "high-energy" in text and "Delegate to the backend when" in text and "Forest" in text
    assert lv.greeting_text(cfg, {"name": "Forest Ward"}) == "Yo Forest"
    assert len(lv.VOICES) == 13 and len(lv.VOICE_IDS) == 13


async def test_create_session_with_fake_openai(monkeypatch):
    db = get_db()
    user = await _tester(db)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    captured = {}

    class FakeResp:
        status_code = 201
        text = ""

        def json(self):
            return {"session": {"id": "live_abc123"}, "transport": {"type": "webrtc", "sdp": "v=0 answer"}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured.update({"url": url, "body": json, "headers": headers})
            return FakeResp()

    monkeypatch.setattr(lv.httpx, "AsyncClient", FakeClient)
    out = await lv.create_session(db, user, "assistant", "v=0 offer")
    try:
        assert out["sdp"] == "v=0 answer" and out["session_id"] == "live_abc123" and out["voice"] == "gleam" and out["cap_left_s"] == 900
        assert "Activation" in out["greeting"]
        body = captured["body"]
        assert captured["url"] == lv.LIVE_URL and captured["headers"]["Authorization"] == "Bearer sk-test-fake"
        assert body["transport"] == {"type": "webrtc", "sdp": "v=0 offer"}
        assert body["session"]["model"] == "gpt-live-1" and body["session"]["delegation"] == {"type": "client"} and body["session"]["audio"]["output"]["voice"] == "gleam"
        assert body["session"]["input"][0]["role"] == "developer"
        live = await lv.get_live(db, out["live_id"])
        assert live and live["status"] == "open" and live["openai_session_id"] == "live_abc123"
    finally:
        await db[lv.COLL].delete_one({"live_id": out["live_id"]})


async def test_brain_who_today_recall_text_confirm_reminder():
    db = get_db()
    user = await _tester(db)
    live = await _seed_live(db, user)
    created_tasks_before = {t["_id"] async for t in db.tasks.find({"user_id": str(user["_id"])}, {"_id": 1})}
    try:
        # 1. who today
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Who should I talk to today?"}], "item_1")
        assert r["tool"] == "who_today" and r["content"]
        # 2. recall a real contact
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Tell me about Sarah Tester."}], "item_2")
        assert r["tool"] in ("recall_person", "find_person") and "Sarah" in r["content"] or r["content"]
        # 3. text -> pending, then confirm -> send attempt (500-555 number, Twilio rejects harmlessly)
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Text Mike Tester and tell him his part came in."}], "item_3")
        assert r["tool"] == "send_text" and r["pending"] is True and "Mike" in r["content"]
        live = await lv.get_live(db, live["live_id"])
        assert live["pending"] and live["pending"]["contact_id"] == "6aa413008f0d53e3f2261854" and live["pending"]["content"]
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Text Mike Tester and tell him his part came in."}, {"role": "assistant", "text": r["content"]}, {"role": "rep", "text": "Yes, send it."}], "item_4")
        assert r["tool"] == "confirm" and r["pending"] is False and ("Sent to" in r["content"] or "did not go out" in r["content"])
        # 4. reminder
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Remind me to call Dana Tester Friday at 2 pm."}], "item_5")
        assert r["tool"] == "set_reminder" and "Reminder set" in r["content"] and "Dana" in r["content"] and "Friday" in r["content"]
        live = await lv.get_live(db, live["live_id"])
        assert len(live["delegations"]) == 5 and live["delegations"][0]["tool"] == "who_today"
        # 5. unknown person
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Pull up Zebulon Quixote."}], "item_6")
        assert "could not find" in r["content"].lower() or "no one named" in r["content"].lower()
    finally:
        await db[lv.COLL].delete_one({"live_id": live["live_id"]})
        await db.tasks.delete_many({"user_id": str(user["_id"]), "_id": {"$nin": list(created_tasks_before)}})
        await db.messages.delete_many({"conversation_id": {"$in": [str(c["_id"]) async for c in db.conversations.find({"user_id": str(user["_id"]), "contact_id": "6aa413008f0d53e3f2261854"})]}, "created_at": {"$gte": live["started_at"]}})


async def test_fuzzy_name_resolution():
    """Todd Berry spoken -> Tod Berry (one D) found, not Todd Snow; 'Todd' alone asks; spelled letters win; Jesse/Jessie handled."""
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    extra = [{"first_name": "Todd", "last_name": "Snow", "phone": "+15005550301"}, {"first_name": "Tod", "last_name": "Berry", "phone": "+15005550302", "vehicle": "2024 Tahoe"},
             {"first_name": "Jesse", "last_name": "Pinkman", "phone": "+15005550303"}, {"first_name": "Jessie", "last_name": "Walters", "phone": "+15005550304"}]
    ids = [(await db.contacts.insert_one({**c, "user_id": uid, "created_at": datetime.now(timezone.utc)})).inserted_id for c in extra]
    try:
        c, err = await lv._resolve(db, uid, "Todd Berry")
        assert c and c["last_name"] == "Berry" and c["first_name"] == "Tod" and err is None
        c, err = await lv._resolve(db, uid, "Todd Barry")
        assert c and c["last_name"] == "Berry"
        c, err = await lv._resolve(db, uid, "Todd")
        assert c is None and "Todd Snow (T-O-D-D)" in err and "Tod Berry (T-O-D)" in err and "Which one" in err
        c, err = await lv._resolve(db, uid, "Tod, T-O-D")
        assert c and c["last_name"] == "Berry", "spelling it out settles it"
        c, err = await lv._resolve(db, uid, "Jesse")
        assert c is None and "Jesse Pinkman" in err and "Jessie Walters" in err
        c, err = await lv._resolve(db, uid, "Jesse Walters")
        assert c and c["first_name"] == "Jessie"
        c, err = await lv._resolve(db, uid, "Sara Tester")
        assert c and c["first_name"] == "Sarah"
        c, err = await lv._resolve(db, uid, "Zebulon Quixote")
        assert c is None and "spell it" in err
        focus = await db.contacts.find_one({"_id": ids[0]})
        c, err = await lv._resolve(db, uid, "Todd Berry", focus)
        assert c and c["last_name"] == "Berry", "a different last name beats the focus contact"
        c, err = await lv._resolve(db, uid, "Todd", focus)
        assert c and c["last_name"] == "Snow", "first name alone stays with the focus contact"
        rows = await lv._find(db, uid, "Todd Berry")
        assert rows[0]["_score"] >= 0.9 and all("_score" in r for r in rows)
    finally:
        await db.contacts.delete_many({"_id": {"$in": ids}})


async def test_duplicates_never_loop():
    """Two 'Tod Berry' records: no question, the most active one is used with a 'say the other one' note; hints pick; exact clones collapse;
    a name that was already asked about is not asked again."""
    db = get_db()
    user = await _tester(db)
    uid = str(user["_id"])
    live = await _seed_live(db, user)
    now = datetime.now(timezone.utc)
    extra = [{"first_name": "Tod", "last_name": "Berry", "phone": "+15005550401", "vehicle": "2024 Tahoe", "last_activity_at": now},
             {"first_name": "Tod", "last_name": "Berry", "phone": "+15005550402", "vehicle": "2019 Silverado", "last_activity_at": now - timedelta(days=40)},
             {"first_name": "Jesse", "last_name": "Pinkman", "phone": "+15005550403", "last_activity_at": now},
             {"first_name": "Jesse", "last_name": "Pinkman", "phone": "(500) 555-0403", "last_activity_at": now - timedelta(days=3)},
             {"first_name": "Jessie", "last_name": "Walters", "phone": "+15005550404"}]
    ids = [(await db.contacts.insert_one({**c, "user_id": uid, "created_at": now})).inserted_id for c in extra]
    try:
        c, err = await lv._resolve(db, uid, "Tod Berry", live=live)
        assert c and str(c["_id"]) == str(ids[0]) and err is None, "most recently active duplicate wins, no question"
        assert "you have 2 records for Tod Berry" in c["_note"] and "2024 Tahoe" in c["_note"] and "Say 'the other one'" in c["_note"]
        assert live["last_pick"] == str(ids[0]) and live["last_choices"] == [str(ids[0]), str(ids[1])]
        c, err = await lv._resolve(db, uid, "Tod Berry", hint="the other one", live=live)
        assert c and str(c["_id"]) == str(ids[1]), "'the other one' switches to the record not used"
        c, err = await lv._resolve(db, uid, "Tod Berry", hint="the one with the Tahoe", live=live)
        assert c and str(c["_id"]) == str(ids[0])
        c, err = await lv._resolve(db, uid, "Tod Berry", hint="ending in 0402", live=live)
        assert c and str(c["_id"]) == str(ids[1])
        # exact clones (same name, same phone) are one person: silent
        c, err = await lv._resolve(db, uid, "Jesse Pinkman", live=live)
        assert c and c["last_name"] == "Pinkman" and not c.get("_note") and err is None
        # different people: asked once, ordinal pick works, and repeating the bare name is not asked again
        c, err = await lv._resolve(db, uid, "Jesse", live=live)
        assert c is None and "Which one" in err and "the first one" in err
        assert live["last_question_name"] == "jesse" and len(live["last_choices"]) == 2
        c, err = await lv._resolve(db, uid, "Jesse", hint="the second one", live=live)
        assert c and str(c["_id"]) == live["last_choices"][1] and err is None
        c, err = await lv._resolve(db, uid, "Jesse", live=live)
        assert c is None and "Which one" in err, "a fresh ask after a pick is fine"
        c, err = await lv._resolve(db, uid, "Jesse", live=live)
        assert c and err is None and "I went with" in c["_note"], "asked twice in a row -> go with the best and say so"
        # the delegation log carries the pick through find_person with a hint (faked brain not needed: direct call)
        stored = await lv.get_live(db, live["live_id"])
        assert stored["last_pick"] == str(c["_id"])
    finally:
        await db.contacts.delete_many({"_id": {"$in": ids}})
        await db[lv.COLL].delete_one({"live_id": live["live_id"]})


async def test_open_targets_for_the_screen(monkeypatch):
    """Every tool that touches a person tells the app what to put on screen; open_screen does it on request. Brain + recall LLM are faked."""
    import services.scripts as scr
    db = get_db()
    user = await _tester(db)
    live = await _seed_live(db, user)
    plans = []

    async def fake_plan(system, prompt, timeout=30):
        return plans.pop(0)

    async def fake_llm(system, prompt, timeout=40):
        return "She bought a 2024 Tahoe last spring and asked about a hitch."

    monkeypatch.setattr(scr, "_llm_json", fake_plan)
    monkeypatch.setattr(scr, "_llm", fake_llm)
    created_tasks_before = {t["_id"] async for t in db.tasks.find({"user_id": str(user["_id"])}, {"_id": 1})}
    try:
        plans.append({"tool": "open_screen", "args": {"what": "contact", "name": "Sarah Tester"}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Pull up Sarah Tester."}], "o1")
        assert r["tool"] == "open_screen" and r["open"]["kind"] == "contact" and r["open"]["name"] == "Sarah Tester" and r["open"]["first"] == "Sarah"
        assert ObjectId.is_valid(r["open"]["id"]) and "up on your screen" in r["content"]
        plans.append({"tool": "open_screen", "args": {"what": "thread", "name": "Sarah Tester"}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Open her text thread."}], "o2")
        assert r["open"]["kind"] == "thread" and "thread" in r["content"]
        plans.append({"tool": "open_screen", "args": {"what": "tasks", "name": ""}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Show me my tasks."}], "o3")
        assert r["open"] == {"kind": "tasks"} and "tasks" in r["content"].lower()
        plans.append({"tool": "open_screen", "args": {"what": "contact", "name": "Zebulon Quixote"}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Pull up Zebulon Quixote."}], "o4")
        assert r["open"] is None and "could not find" in r["content"].lower()
        plans.append({"tool": "recall_person", "args": {"name": "Mike Tester"}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "What did Mike Tester buy?"}], "o5")
        assert r["open"]["kind"] == "contact" and r["open"]["id"] == "6aa413008f0d53e3f2261854" and "Tahoe" in r["content"]
        plans.append({"tool": "send_text", "args": {"name": "Sarah Tester", "message": "Hey Sarah, quick check-in on the Tahoe. Any questions?", "intent": "check in"}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Text Sarah Tester: hey Sarah, quick check-in on the Tahoe, any questions?"}], "o6")
        assert r["open"]["kind"] == "thread" and r["pending"] is True
        plans.append({"tool": "set_reminder", "args": {"name": "Dana Tester", "when_iso": "2030-01-04T14:00:00", "note": "Call Dana about the trade-in", "action": "call"}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Remind me to call Dana Tester Friday at 2."}], "o7")
        assert r["open"]["kind"] == "task" and ObjectId.is_valid(r["open"]["id"]) and r["open"]["name"].startswith("Call Dana")
        assert await db.tasks.find_one({"_id": ObjectId(r["open"]["id"])})
        plans.append({"tool": "who_today", "args": {}})
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Who is up today?"}], "o8")
        assert r["open"] is None
        live = await lv.get_live(db, live["live_id"])
        assert live["delegations"][0]["open"]["kind"] == "contact" and live["delegations"][2]["open"] == {"kind": "tasks"}
        assert "open_screen" in lv.BRAIN_SYSTEM and "Open on screen" in lv.assistant_instructions(lv.DEFAULTS, user)
    finally:
        await db[lv.COLL].delete_one({"live_id": live["live_id"]})
        await db.tasks.delete_many({"user_id": str(user["_id"]), "_id": {"$nin": list(created_tasks_before)}})


async def test_events_and_admin_api(forest_h, tester_h):
    db = get_db()
    user = await _tester(db)
    live = await _seed_live(db, user, mode="lab")
    try:
        # events by the owner
        r = requests.post(f"{BASE}/api/live-voice/{live['live_id']}/events", headers=tester_h, timeout=30,
                          json={"events": [{"type": "transcript", "role": "assistant", "text": "Hey Activation, it's Jessi.", "start_ms": 0, "end_ms": 1800},
                                           {"type": "transcript", "role": "rep", "text": "Who should I call today?", "start_ms": 2500, "end_ms": 4000},
                                           {"type": "usage", "seconds": 42}]})
        assert r.status_code == 200 and r.json()["seconds"] == 42
        # someone else cannot touch it
        other = {"Authorization": f"Bearer {_token({'email': 'qa-manager@invalid.imonsocial.test', 'password': 'Manager123!'})}"}
        assert requests.post(f"{BASE}/api/live-voice/{live['live_id']}/events", headers=other, json={"events": []}, timeout=30).status_code == 404
        # close
        r = requests.post(f"{BASE}/api/live-voice/{live['live_id']}/events", headers=tester_h, json={"events": [{"type": "closed", "reason": "idle", "seconds": 90}]}, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "closed"
        doc = await lv.get_live(db, live["live_id"])
        assert doc["status"] == "closed" and doc["seconds"] == 90 and doc["cost_usd"] == 0.075 and doc["close_reason"] == "idle" and len(doc["transcript"]) == 2
        # delegate on a closed session
        assert requests.post(f"{BASE}/api/live-voice/{live['live_id']}/delegate", headers=tester_h, json={"transcript": [], "delegation_id": "x"}, timeout=30).status_code == 409
        # owner detail
        r = requests.get(f"{BASE}/api/live-voice/{live['live_id']}", headers=tester_h, timeout=30)
        assert r.status_code == 200 and r.json()["transcript"][1]["text"] == "Who should I call today?"
        # admin views
        assert requests.get(f"{BASE}/api/live-voice/admin/config", headers=tester_h, timeout=30).status_code == 403
        r = requests.get(f"{BASE}/api/live-voice/admin/sessions", headers=forest_h, timeout=30)
        assert r.status_code == 200 and any(s["live_id"] == live["live_id"] for s in r.json()["sessions"]) and "today" in r.json()["stats"]
        r = requests.get(f"{BASE}/api/live-voice/admin/sessions/{live['live_id']}", headers=forest_h, timeout=30)
        assert r.status_code == 200 and r.json()["mode"] == "lab" and r.json()["cost_usd"] == 0.075
        # config save round trip + preview
        before = requests.get(f"{BASE}/api/live-voice/admin/config", headers=forest_h, timeout=30).json()["config"]
        r = requests.put(f"{BASE}/api/live-voice/admin/config", headers=forest_h, json={"voice": "willow", "energy": 2, "notes": "Loves a quick car joke."}, timeout=30)
        assert r.status_code == 200 and r.json()["config"]["voice"] == "willow" and r.json()["config"]["energy"] == 2 and r.json()["config"]["updated_by"] == FOREST["email"]
        assert requests.put(f"{BASE}/api/live-voice/admin/config", headers=forest_h, json={"voice": "nope"}, timeout=30).status_code == 400
        r = requests.get(f"{BASE}/api/live-voice/admin/preview", headers=forest_h, params={"energy": 5, "playful": 5}, timeout=30)
        assert r.status_code == 200 and "high-energy" in r.json()["personality"] and "quick with a one-liner" in r.json()["personality"] and "car joke" in r.json()["personality"]
        cfg = requests.get(f"{BASE}/api/live-voice/config", headers=tester_h, timeout=30).json()
        assert cfg["voice"] == "willow" and cfg["available"] is False and cfg["is_super_admin"] is False
        # session start guards
        assert requests.post(f"{BASE}/api/live-voice/session", headers=tester_h, json={"mode": "lab", "sdp": "v=0"}, timeout=30).status_code == 403
        assert requests.post(f"{BASE}/api/live-voice/session", headers=tester_h, json={"mode": "assistant", "sdp": "v=0"}, timeout=30).status_code == 403
        assert requests.post(f"{BASE}/api/live-voice/session", headers=forest_h, json={"mode": "assistant", "sdp": ""}, timeout=30).status_code == 400
        r = requests.post(f"{BASE}/api/live-voice/session", headers=forest_h, json={"mode": "lab", "sdp": "v=0"}, timeout=30)
        assert r.status_code in (503, 201, 200)  # 503 without OPENAI_API_KEY
        # restore config
        requests.put(f"{BASE}/api/live-voice/admin/config", headers=forest_h, json={k: before[k] for k in lv.DEFAULTS}, timeout=30)
    finally:
        await db[lv.COLL].delete_one({"live_id": live["live_id"]})


async def test_focus_contact_from_ask_button(monkeypatch):
    """Opened from Sarah Tester's thread: pronouns and name-less requests resolve to her, other names still search."""
    db = get_db()
    user = await _tester(db)
    sarah = "6aa413008f0d53e3f2261853"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    captured = {}

    class FakeResp:
        status_code = 201
        text = ""

        def json(self):
            return {"session": {"id": "live_focus"}, "transport": {"type": "webrtc", "sdp": "v=0 answer"}}

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
    out = await lv.create_session(db, user, "assistant", "v=0 offer", None, sarah)
    live = await lv.get_live(db, out["live_id"])
    try:
        assert out["contact_name"] == "Sarah Tester" and "Sarah" in out["greeting"]
        assert "Sarah Tester is the person in focus" in captured["session"]["instructions"]
        assert "Sarah Tester's conversation" in captured["session"]["input"][0]["content"][0]["text"]
        assert live["contact_id"] == sarah and live["contact_name"] == "Sarah Tester"
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "What do we know about her?"}], "f1")
        assert r["tool"] in ("recall_person", "find_person") and r["content"]
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Text her that the paperwork is ready."}], "f2")
        assert r["tool"] == "send_text" and r["pending"]
        live = await lv.get_live(db, live["live_id"])
        assert live["pending"]["contact_id"] == sarah
        r = await lv.delegate(db, live, user, [{"role": "rep", "text": "Never mind. Pull up Mike Tester instead."}], "f3")
        assert "Mike" in r["content"]
        # unknown contact id -> plain session, no focus
        out2 = await lv.create_session(db, user, "assistant", "v=0 offer", None, "000000000000000000000000")
        assert out2["contact_name"] is None and "Home screen" in captured["session"]["input"][0]["content"][0]["text"]
        await db[lv.COLL].delete_one({"live_id": out2["live_id"]})
    finally:
        await db[lv.COLL].delete_one({"live_id": out["live_id"]})
