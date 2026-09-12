"""Recording Highlights: a recorded conversation's commitments become tasks (deduped) and show on the voice note.
Run: cd /app/backend && python -m pytest tests/test_recording_highlights.py -q"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}

TRANSCRIPT = (
    "Rep: Thanks for coming by, Sarah. So you liked the white Tahoe Z71 out front? "
    "Customer: I did, but I need to know what my Explorer is worth on trade, it has about sixty two thousand miles. "
    "Rep: I'll get you a firm trade number and the out-the-door price on the Tahoe texted over by tomorrow morning. "
    "Customer: Perfect. My husband wants to see it too, can we come back Saturday around ten? "
    "Rep: Saturday at ten works, I'll have it pulled up front and washed. "
    "Customer: Great. I also need to send you a copy of my insurance card and the payoff letter from my credit union. "
    "Rep: Sounds good, text those to me when you get home and I'll build the deal around them."
)


LOOP = asyncio.new_event_loop()  # one loop for the module: routers.database's Motor client binds to the first loop it sees


def _run(coro):
    return LOOP.run_until_complete(coro)


@pytest.fixture(scope="module")
def rep_login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=REP, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"Authorization": f"Bearer {d['token']}"}, d["user"]["_id"]


@pytest.fixture(scope="module")
def sarah_id(rep_login):
    hdr, _ = rep_login
    d = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine", headers=hdr, timeout=20).json()
    return next(e["contact_id"] for e in d["evaluations"] if e["call_sid"] == "CA_scdemo_good_001")


def test_due_fallbacks():
    from services.recording_highlights import _due, _json
    due, has_time = _due(None, True, "America/Denver")
    assert due > datetime.now(timezone.utc) and has_time is False
    due2, ht2 = _due("2099-06-05T10:00:00-06:00", True, "America/Denver")
    assert due2.isoformat().startswith("2099-06-05T16:00") and ht2 is True
    old, _ = _due("2020-01-01T10:00:00Z", True, "America/Denver")
    assert old > datetime.now(timezone.utc)
    assert _json('```json\n{"a": 1}\n```') == {"a": 1} and _json("junk {\"b\": 2} tail") == {"b": 2} and _json("nope") == {}


def test_highlights_create_tasks_and_dedupe(rep_login, sarah_id):
    from services.recording_highlights import process_recorded_conversation
    hdr, rep_id = rep_login

    async def run():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        now = datetime.now(timezone.utc)
        note = await db.voice_notes.insert_one({"contact_id": sarah_id, "user_id": rep_id, "audio_url": "/api/images/voice-notes/test/none.m4a", "audio_path": "voice-notes/test/none.m4a",
                                                "transcript": TRANSCRIPT, "summary": "", "kind": "conversation", "duration": 95.0, "created_at": now, "hl_test": True})
        note_id = str(note.inserted_id)
        try:
            out = await process_recorded_conversation(db, rep_id, sarah_id, note_id, TRANSCRIPT)
            assert out["summary"] and "—" not in out["summary"] and "–" not in out["summary"]
            assert 3 <= len(out["title"]) <= 40, out["title"]
            assert 2 <= len(out["tasks"]) <= 5, out
            titles = " | ".join(t["title"].lower() for t in out["tasks"])
            assert "trade" in titles or "price" in titles or "number" in titles, titles
            assert any(t["action"] == "appointment" for t in out["tasks"]), titles
            appt = next(t for t in out["tasks"] if t["action"] == "appointment")
            assert datetime.fromisoformat(appt["due_date"]).astimezone(timezone.utc) > now
            for t in out["tasks"]:
                doc = await db.tasks.find_one({"_id": ObjectId(t["id"])})
                assert doc and doc["user_id"] == rep_id and doc["contact_id"] == sarah_id and doc["status"] == "pending" and doc["completed"] is False
                assert doc["source"] == "recorded_conversation" and doc["auto_kind"] == "recording_highlight" and doc["voice_note_id"] == note_id
                assert doc["priority"] == "high" and doc["due_date"].replace(tzinfo=timezone.utc) > now - __import__("datetime").timedelta(hours=1)
                assert "—" not in doc["title"] and "—" not in doc["description"]
            saved = await db.voice_notes.find_one({"_id": note.inserted_id})
            assert saved["summary"] == out["summary"] and len(saved["highlights"]) == len(out["highlights"]) and all(h["task_id"] for h in saved["highlights"])
            assert await db.contact_events.count_documents({"event_type": "recording_highlights", "metadata.voice_note_id": note_id}) == 1

            # the contact's Up Next card and the voice-notes list see them
            open_tasks = requests.get(f"{BASE_URL}/api/tasks/{rep_id}/contact/{sarah_id}?limit=50", headers=hdr, timeout=20).json()
            open_ids = {t.get("_id") or t.get("id") for t in (open_tasks if isinstance(open_tasks, list) else open_tasks.get("tasks", []))}
            assert {t["id"] for t in out["tasks"]} <= open_ids
            notes = requests.get(f"{BASE_URL}/api/voice-notes/{rep_id}/{sarah_id}", headers=hdr, timeout=20).json()
            mine = next(n for n in notes if n["id"] == note_id)
            assert mine["kind"] == "conversation" and mine["summary"] and len(mine["highlights"]) == len(out["highlights"])
            assert all(isinstance(h["due_date"], str) for h in mine["highlights"])

            # second pass over the same recording adds no duplicate tasks
            before = await db.tasks.count_documents({"contact_id": sarah_id, "user_id": rep_id, "auto_kind": "recording_highlight"})
            out2 = await process_recorded_conversation(db, rep_id, sarah_id, note_id, TRANSCRIPT)
            after = await db.tasks.count_documents({"contact_id": sarah_id, "user_id": rep_id, "auto_kind": "recording_highlight"})
            assert after - before <= 2 and len(out2["tasks"]) <= 2  # model sees the open tasks; allow a rewording or two
            assert all(h["task_id"] for h in out2["highlights"])
        finally:
            await db.tasks.delete_many({"contact_id": sarah_id, "user_id": rep_id, "auto_kind": "recording_highlight"})
            await db.contact_events.delete_many({"metadata.voice_note_id": note_id})
            await db.voice_notes.delete_one({"_id": note.inserted_id})
    _run(run())


def test_rename_recording(rep_login, sarah_id):
    hdr, rep_id = rep_login

    async def run():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        note = await db.voice_notes.insert_one({"contact_id": sarah_id, "user_id": rep_id, "audio_url": "", "transcript": "x", "kind": "conversation", "duration": 6, "created_at": datetime.now(timezone.utc)})
        nid = str(note.inserted_id)
        try:
            url = f"{BASE_URL}/api/voice-notes/{rep_id}/{sarah_id}/{nid}"
            r = requests.patch(url, json={"title": "  Tahoe walk-around — trade talk  "}, headers=hdr, timeout=20)
            assert r.status_code == 200 and r.json()["title"] == "Tahoe walk-around, trade talk"
            listed = next(n for n in requests.get(f"{BASE_URL}/api/voice-notes/{rep_id}/{sarah_id}", headers=hdr, timeout=20).json() if n["id"] == nid)
            assert listed["title"] == "Tahoe walk-around, trade talk"
            assert requests.patch(url, json={"title": "x" * 100}, headers=hdr, timeout=20).json()["title"] == "x" * 60
            assert requests.patch(url, json={"title": ""}, headers=hdr, timeout=20).json()["title"] == ""
            assert requests.patch(f"{BASE_URL}/api/voice-notes/{rep_id}/{sarah_id}/000000000000000000000000", json={"title": "a"}, headers=hdr, timeout=20).status_code == 404
            assert requests.patch(f"{BASE_URL}/api/voice-notes/{rep_id}/{sarah_id}/nope", json={"title": "a"}, headers=hdr, timeout=20).status_code == 404
        finally:
            await db.voice_notes.delete_one({"_id": note.inserted_id})
    _run(run())


def test_highlight_nudge_flow(rep_login, sarah_id):
    """A recorded promise comes due -> one highlight_due alert with a draft + thread link carrying prefill/taskId; no double nudge; resolves when the task completes."""
    from services.recording_highlights import send_highlight_nudges, _fallback_draft
    from urllib.parse import urlparse, parse_qs
    hdr, rep_id = rep_login
    assert _fallback_draft("Sarah", "Text firm trade number", "text").startswith("Hi Sarah,") and "—" not in _fallback_draft("Sarah", "x", "appointment")

    async def run():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        now = datetime.now(timezone.utc)
        conv = await db.conversations.insert_one({"user_id": rep_id, "contact_id": sarah_id, "contact_name": "Sarah Tester", "status": "active", "created_at": now, "last_message_at": now, "is_test": True})
        task = await db.tasks.insert_one({"user_id": rep_id, "contact_id": sarah_id, "contact_name": "Sarah Tester", "type": "follow_up", "source": "recorded_conversation", "auto_kind": "recording_highlight",
                                          "voice_note_id": "vn_test", "title": "Text Sarah the firm trade number and OTD price on the Tahoe", "title_norm": "x",
                                          "description": "Promised in your recorded conversation on Sep 12: I'll get you a firm trade number and the out-the-door price texted over by tomorrow morning.",
                                          "action_type": "text", "priority": "high", "status": "pending", "completed": False, "due_date": now - timedelta(minutes=3), "has_time": False, "created_at": now})
        tid = str(task.inserted_id)
        try:
            assert await send_highlight_nudges(db) >= 1
            n = await db.notifications.find_one({"type": "highlight_due", "task_id": tid})
            assert n and n["user_id"] == rep_id and n["title"].startswith("Promised to Sarah:") and 15 < len(n["draft"]) <= 320 and "—" not in n["draft"] and "[" not in n["draft"]
            assert n["conversation_id"] == str(conv.inserted_id)
            u = urlparse(n["link"]); qs = parse_qs(u.query)
            assert u.path == f"/thread/{conv.inserted_id}" and qs["taskId"] == [tid] and qs["prefill"][0] == n["draft"]
            t = await db.tasks.find_one({"_id": task.inserted_id})
            assert t.get("nudged_at") and t.get("reminded_due") is True
            # second sweep is a no-op
            assert await db.notifications.count_documents({"type": "highlight_due", "task_id": tid}) == 1
            await send_highlight_nudges(db)
            assert await db.notifications.count_documents({"type": "highlight_due", "task_id": tid}) == 1
            # alerts feed: the nudge shows once with a Send text action and the task is not duplicated as a virtual overdue row
            def _items():
                feed = requests.get(f"{BASE_URL}/api/notification-center/{rep_id}", headers=hdr, timeout=30).json()
                items = feed.get("items") or feed.get("alerts") or feed
                return items if isinstance(items, list) else sum((v for v in items.values() if isinstance(v, list)), [])
            mine = []
            for _ in range(8):  # the server feed cache is 30s; the nudge itself invalidates it in-process
                items = _items()
                mine = [i for i in items if i.get("type") == "highlight_due" and i.get("id") == str(n["_id"])]
                if mine:
                    break
                await asyncio.sleep(5)
            assert mine and mine[0]["action"]["label"] == "Send text" and mine[0]["link"] == n["link"] and mine[0]["bucket"] == "now"
            assert not any(i.get("id") == f"task_{tid}" for i in items)
            # completing the task (what the thread does after the draft sends) auto-resolves the alert
            requests.patch(f"{BASE_URL}/api/tasks/{rep_id}/{tid}", json={"action": "complete"}, headers=hdr, timeout=20)
            items2 = _items()
            assert not any(i.get("id") == str(n["_id"]) for i in items2)
            assert (await db.notifications.find_one({"_id": n["_id"]}))["dismissed"] is True
        finally:
            await db.notifications.delete_many({"task_id": tid})
            await db.tasks.delete_one({"_id": task.inserted_id})
            await db.contact_events.delete_many({"task_id": tid})
            await db.conversations.delete_one({"_id": conv.inserted_id})
    _run(run())


def test_short_transcript_makes_no_tasks(rep_login, sarah_id):
    from services.recording_highlights import process_recorded_conversation
    _, rep_id = rep_login

    async def run():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        note = await db.voice_notes.insert_one({"contact_id": sarah_id, "user_id": rep_id, "audio_url": "", "transcript": "hi", "kind": "conversation", "duration": 6, "created_at": datetime.now(timezone.utc)})
        try:
            out = await process_recorded_conversation(db, rep_id, sarah_id, str(note.inserted_id), "hi")
            assert out == {"title": "", "summary": "", "highlights": [], "tasks": []}
        finally:
            await db.voice_notes.delete_one({"_id": note.inserted_id})
    _run(run())
