"""Live Jessi (GPT-Live-1) brain + API. No OpenAI Live session is opened: the session doc is seeded directly and
`create_session` is exercised against a fake httpx client. The brain itself runs the real LLM (Emergent key)."""
import os
import pytest
import requests
from bson import ObjectId
from datetime import datetime, timezone

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
