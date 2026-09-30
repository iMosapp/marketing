"""Login must not 500 for a user who enrolled Voice ID (services/voice_id.py stores the Eagle profile as Binary on the user doc).
Reproduces the Sep 30 2026 production outage: fresh logins failed with TypeError bytes not JSON serializable."""
import asyncio
import os
import sys

import bcrypt
from bson import Binary
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests._http import call  # noqa: E402

EMAIL = "voiceid-login-probe@invalid.imonsocial.test"
PASS = "Probe-Only-Voice-9931!"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_login_me_refresh_work_with_a_binary_voice_id_profile():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    _run(db.users.delete_many({"email": EMAIL}))
    _run(db.users.insert_one({"email": EMAIL, "password": bcrypt.hashpw(PASS.encode(), bcrypt.gensalt()).decode(), "name": "VoiceId Probe", "role": "user",
                              "is_active": True, "voice_id": {"status": "enrolled", "profile": Binary(b"\x00\x01\x02\x03"), "percent": 100.0, "source": "interview"}}))
    try:
        st, body = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASS})
        assert st == 200, body
        u = body["user"]
        assert "profile" not in u["voice_id"] and u["voice_id"]["enrolled"] is True and u["voice_id"]["status"] == "enrolled"
        assert "password" not in u and body["token"]
        hdr = {"Authorization": "Bearer " + body["token"], "X-User-ID": u["_id"], "Cookie": f"imonsocial_session={u['_id']}"}
        st, me = call("GET", "/api/auth/me", headers=hdr)
        assert st == 200 and "profile" not in (me["user"].get("voice_id") or {}) and me["user"]["voice_id"]["enrolled"] is True, me
        st, ref = call("POST", "/api/auth/refresh", {}, headers=hdr)
        assert st == 200 and "profile" not in (ref["user"].get("voice_id") or {}), ref
    finally:
        _run(db.users.delete_many({"email": EMAIL}))
