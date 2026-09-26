"""Website Widget per-door stats (Doors tab card).

    cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_widget_door_stats.py -q
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
STORE = "69a0b7095fddcede09591668"
LOOP = asyncio.new_event_loop()


def run(coro):
    return LOOP.run_until_complete(coro)


def _db():
    from routers.database import get_db
    return get_db()


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture(scope="module")
def mgr():
    return _login("qa-manager@invalid.imonsocial.test", "Manager123!")


@pytest.fixture(scope="module")
def widget(mgr):
    r = requests.post(f"{BASE}/api/widgets", json={"store_id": STORE}, headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["widget"]


def test_page_path():
    from services.widgets import page_path
    assert page_path("https://www.dealer.com/inventory/new?x=1#top") == "/inventory/new"
    assert page_path("https://dealer.com") == "/"
    assert page_path("") == "/"


def test_event_endpoint_accepts_door_and_rejects_bad_door(widget):
    key = widget["key"]
    ok = requests.post(f"{BASE}/api/w/{key}/event", json={"kind": "door", "door": "text", "page": "https://qa.example.com/specials"}, timeout=30).json()
    assert ok == {"ok": True}
    bad = requests.post(f"{BASE}/api/w/{key}/event", json={"kind": "door", "door": "bogus", "page": "https://qa.example.com/"}, timeout=30).json()
    assert bad == {"ok": False}
    async def check():
        db = _db()
        ev = await db.widget_events.find_one({"widget_id": widget["id"], "kind": "door"}, sort=[("at", -1)])
        assert ev and ev["door"] == "text" and ev["page"].endswith("/specials")
        await db.widget_events.delete_many({"widget_id": widget["id"], "kind": "door"})
    run(check())


def test_door_stats_windows_and_pages(mgr, widget):
    from bson import ObjectId
    from services import widgets as W
    fake = {"_id": ObjectId(), "key": "qadoor"}
    wid = str(fake["_id"])
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=12)
    events = [
        {"kind": "door", "door": "text", "page": "https://qa.example.com/inventory", "at": now},
        {"kind": "door", "door": "text", "page": "https://qa.example.com/inventory", "at": now},
        {"kind": "lead", "door": "text", "page": "https://qa.example.com/inventory", "at": now},
        {"kind": "door", "door": "call", "page": "https://qa.example.com/specials?x=1", "at": now},
        {"kind": "lead", "door": "call", "page": "https://qa.example.com/specials?x=1", "at": now},
        {"kind": "lead", "door": "call", "page": "https://qa.example.com/service", "at": now},
        {"kind": "lead", "door": "call", "page": "https://qa.example.com/specials", "at": now},
        {"kind": "door", "door": "chat", "page": "https://qa.example.com/", "at": now},
        {"kind": "open", "door": None, "page": "https://qa.example.com/", "at": now},
        {"kind": "lead", "door": "text", "page": "https://qa.example.com/old", "at": old},
        {"kind": "door", "door": "text", "page": "https://qa.example.com/old", "at": old},
    ]
    calls = [
        {"widget_id": wid, "status": "connected", "seconds_to_connect": 12, "created_at": now, "name": "QA Door", "phone": "+15005550999"},
        {"widget_id": wid, "status": "missed", "created_at": now, "name": "QA Door", "phone": "+15005550999"},
        {"widget_id": wid, "status": "after_hours", "created_at": old, "name": "QA Door", "phone": "+15005550999"},
    ]
    chats = [
        {"widget_id": wid, "sid": "qa_doorstats_1", "key": "qadoor", "status": "handed_off", "contact_id": "x", "booking": {"kind": "test_drive"}, "rep_user_id": None, "created_at": now, "messages": []},
        {"widget_id": wid, "sid": "qa_doorstats_2", "key": "qadoor", "status": "open", "rep_user_id": "someone", "created_at": now, "messages": []},
        {"widget_id": wid, "sid": "qa_doorstats_3", "key": "qadoor", "status": "closed", "created_at": old, "messages": []},
    ]

    async def flow():
        db = _db()
        await db.widget_events.insert_many([{**e, "widget_id": wid, "key": "qadoor", "visitor": "qa_doorstats"} for e in events])
        await db.widget_call_requests.insert_many(calls)
        await db.widget_chats.insert_many(chats)
        try:
            s = await W.door_stats(db, fake, 7)
            assert s["days"] == 7 and s["total_leads"] == 4 and s["busiest"] == "call"
            t, c, ch = s["doors"]["text"], s["doors"]["call"], s["doors"]["chat"]
            assert t["views"] == 2 and t["leads"] == 1 and t["rate"] == 50 and t["pages"] == [{"path": "/inventory", "n": 1}]
            assert c["views"] == 1 and c["leads"] == 2 and c["requests"] == 2 and c["connected"] == 1 and c["missed"] == 1 and c["after_hours"] == 0 and c["avg_seconds"] == 12
            assert c["pages"][0] == {"path": "/specials", "n": 2} and c["pages"][1] == {"path": "/service", "n": 1}
            assert ch["views"] == 1 and ch["chats"] == 2 and ch["handed_off"] == 1 and ch["leads"] == 1 and ch["bookings"] == 1 and ch["taken_over"] == 1

            a = await W.door_stats(db, fake, 0)
            assert a["days"] == 0 and a["total_leads"] == 6 and a["doors"]["text"]["views"] == 3 and a["doors"]["call"]["after_hours"] == 1 and a["doors"]["chat"]["chats"] == 3
            assert a["doors"]["text"]["pages"] == [{"path": "/inventory", "n": 1}, {"path": "/old", "n": 1}]

            empty = await W.door_stats(db, {"_id": ObjectId()}, 30)
            assert empty["total_leads"] == 0 and empty["busiest"] is None and empty["doors"]["text"]["rate"] is None and empty["doors"]["call"]["avg_seconds"] is None
        finally:
            await db.widget_events.delete_many({"widget_id": wid})
            await db.widget_call_requests.delete_many({"widget_id": wid})
            await db.widget_chats.delete_many({"widget_id": wid})
    run(flow())

    # API: shape, window fallback, detail payload, auth
    real = widget["id"]
    r = requests.get(f"{BASE}/api/widgets/{real}/door-stats", params={"days": 30}, headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["days"] == 30 and set(body["doors"]) == {"text", "call", "chat"} and "requests" in body["doors"]["call"] and "bookings" in body["doors"]["chat"]
    assert requests.get(f"{BASE}/api/widgets/{real}/door-stats", params={"days": 3}, headers=mgr, timeout=30).json()["days"] == 7
    d = requests.get(f"{BASE}/api/widgets/{real}", headers=mgr, timeout=30).json()
    assert d["door_stats"]["days"] == 7 and "doors" in d["door_stats"]
    rep = _login("activation-tester@invalid.imonsocial.test", "NewPass123!")
    assert requests.get(f"{BASE}/api/widgets/{real}/door-stats", headers=rep, timeout=30).status_code == 200
    assert requests.get(f"{BASE}/api/widgets/{real}/door-stats", timeout=30).status_code in (401, 403)


def test_widget_js_tracks_door(widget):
    js = requests.get(f"{BASE}/api/w/{widget['key']}.js", timeout=30).text
    assert "track('door', { door: d })" in js
