"""Recording Highlights: a recorded conversation's commitments become tasks (deduped) and show on the voice note.
Run: cd /app/backend && python -m pytest tests/test_recording_highlights.py -q"""
import asyncio
import os
import sys
from datetime import datetime, timezone

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
