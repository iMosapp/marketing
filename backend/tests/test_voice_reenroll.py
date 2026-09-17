"""Voice ID self-heal: a rep interviewed while PICOVOICE_ACCESS_KEY was missing on the server (voice_id.status not_configured,
recording kept in object storage) gets enrolled from that recording the next time /interview/status is fetched, no redo call.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_voice_reenroll.py -q   (TTS + Eagle, ~40 s)"""
import asyncio
import os
import uuid
from datetime import timedelta

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import interview as svc
from services import voice_id
from tests.voice_id_check import ENROLL, tts

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
TESTER = "activation-tester@invalid.imonsocial.test"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(asyncio.sleep(0.05))
        loop.close()


@pytest.mark.skipif(voice_id.available() is not None, reason="Eagle not available on this server")
def test_reenroll_from_kept_recording():
    async def setup():
        from utils.image_storage import put_object
        db = _db()
        user = await db.users.find_one({"email": TESTER})
        prev_voice = user.get("voice_id")
        audio = await tts(ENROLL, "nova")
        sid = ObjectId()
        path = f"interview/{sid}/rep.mp3"
        stored = (await asyncio.to_thread(put_object, path, audio, "audio/mpeg")).get("path") or path
        now = svc._now()
        await db[svc.COLL].insert_one({"_id": sid, "user_id": str(user["_id"]), "rep_name": user.get("name"), "status": "completed", "turns": [], "covered": [], "industry": "automotive", "token": uuid.uuid4().hex,
                                       "recording_url": f"/api/images/{stored}", "recording_seconds": 45, "voice": {"status": "not_configured", "error": "PICOVOICE_ACCESS_KEY is not set"}, "qa_reenroll": True,
                                       "started_at": now - timedelta(minutes=6), "ended_at": now - timedelta(minutes=1), "created_at": now, "updated_at": now})
        # what production wrote when the key was missing
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"voice_id": {"status": "not_configured", "attempted_at": now, "source": "interview", "error": "PICOVOICE_ACCESS_KEY is not set"}}})
        return user, prev_voice, sid
    user, prev_voice, sid = _run(setup())
    try:
        r = requests.post(f"{API}/auth/login", json={"email": TESTER, "password": "NewPass123!"}, timeout=30)
        r.raise_for_status()
        headers = {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}
        st = requests.get(f"{API}/interview/status", headers=headers, timeout=60).json()
        if st["voice"]["status"] == "not_configured":  # enrollment still running in the background: give it a moment
            import time
            time.sleep(15)
            st = requests.get(f"{API}/interview/status", headers=headers, timeout=60).json()
        assert st["voice"]["status"] == "enrolled" and st["voice"]["enrolled"] is True and st["voice"]["configured"] is True, st["voice"]

        async def check():
            db = _db()
            s = await db[svc.COLL].find_one({"_id": sid})
            u = await db.users.find_one({"_id": user["_id"]}, {"voice_id": 1})
            return s, u
        s, u = _run(check())
        assert s.get("voice_reenroll_at") and s["voice"]["status"] == "enrolled"
        assert u["voice_id"]["profile"] and u["voice_id"]["source"] == "interview"
        # second fetch is a no-op (stamped), stays enrolled
        st2 = requests.get(f"{API}/interview/status", headers=headers, timeout=60).json()
        assert st2["voice"]["status"] == "enrolled"
    finally:
        async def cleanup():
            db = _db()
            await db[svc.COLL].delete_many({"_id": sid})
            if prev_voice is None:
                await db.users.update_one({"_id": user["_id"]}, {"$unset": {"voice_id": ""}})
            else:
                await db.users.update_one({"_id": user["_id"]}, {"$set": {"voice_id": prev_voice}})
        _run(cleanup())
