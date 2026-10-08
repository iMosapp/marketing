"""One phone = one person. Registering a device token binds it to the caller and unbinds it from everyone else; a super-admin 'view as'
session never binds the admin's phone to the viewed user; sign-out unbinds; startup dedupe keeps only the newest owner of a device."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import API, call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
REP_ID = "6a978d68b8673c29063aa8b9"
OTHER_ID = "000000000000000000000abc"
TOKEN = "ExponentPushToken[qa-one-device-one-person]"
UA = {"User-Agent": "Mozilla/5.0"}


def _db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _owners():
    async def go():
        db = _db()
        return sorted([d["user_id"] async for d in db.expo_push_tokens.find({"expo_push_token": TOKEN})])
    return asyncio.run(go())


def _cleanup():
    async def go():
        db = _db()
        await db.expo_push_tokens.delete_many({"expo_push_token": {"$regex": "^ExponentPushToken\\[qa-"}})
        await db.push_subscriptions.delete_many({"endpoint": {"$regex": "^https://qa-push"}})
        await db.impersonation_sessions.delete_many({"token": {"$regex": "^impersonate_qa"}})
    asyncio.run(go())


def test_register_moves_the_device_to_the_caller_and_signout_unbinds():
    _cleanup()
    rep = auth(*login(*REP))
    try:
        # the device was (wrongly) bound to someone else first
        async def seed():
            await _db().expo_push_tokens.insert_one({"user_id": OTHER_ID, "expo_push_token": TOKEN, "platform": "ios", "updated_at": datetime.now(timezone.utc)})
        asyncio.run(seed())
        assert _owners() == [OTHER_ID]
        st, b = call("POST", f"/api/push/subscribe-native/{REP_ID}", {"expo_push_token": TOKEN, "platform": "ios"}, rep)
        assert st == 200 and b["registered"] is True
        assert _owners() == [REP_ID], "registering must unbind the device from the other user"
        # registering again is idempotent
        st, b = call("POST", f"/api/push/subscribe-native/{REP_ID}", {"expo_push_token": TOKEN, "platform": "ios"}, rep)
        assert st == 200 and _owners() == [REP_ID]
        # sign-out unbinds
        r = requests.delete(f"{API}/api/push/unsubscribe-native/{REP_ID}", json={"expo_push_token": TOKEN}, headers={**rep, **UA})
        assert r.status_code == 200 and r.json()["removed"] == 1
        assert _owners() == []
        r = requests.delete(f"{API}/api/push/unsubscribe-native/{REP_ID}", json={}, headers={**rep, **UA})
        assert r.status_code == 400
    finally:
        _cleanup()


def test_view_as_session_never_binds_the_admins_phone_to_the_viewed_user():
    _cleanup()
    try:
        async def seed():
            db = _db()
            await db.impersonation_sessions.insert_one({"token": "impersonate_qa0000000000", "impersonated_user_id": REP_ID, "admin_user_id": OTHER_ID,
                                                        "created_at": datetime.now(timezone.utc), "expires_at": datetime.utcnow() + timedelta(hours=1)})
            # a stale binding from before the fix
            await db.expo_push_tokens.insert_one({"user_id": REP_ID, "expo_push_token": TOKEN, "platform": "ios", "updated_at": datetime.now(timezone.utc)})
        asyncio.run(seed())
        imp = {"Authorization": "Bearer impersonate_qa0000000000", "X-User-ID": REP_ID}
        st, b = call("POST", f"/api/push/subscribe-native/{REP_ID}", {"expo_push_token": TOKEN, "platform": "ios"}, imp)
        assert st == 200 and b["registered"] is False and b["reason"] == "impersonating"
        assert _owners() == [], "the stale binding to the viewed user is removed, nothing new is written"
        # web push endpoint follows the same rule
        sub = {"endpoint": "https://qa-push.example/ep1", "keys": {"p256dh": "x", "auth": "y"}}
        st, b = call("POST", f"/api/push/subscribe/{REP_ID}", {"subscription": sub}, imp)
        assert st == 200 and b["status"] == "skipped"
    finally:
        _cleanup()


def test_web_endpoint_moves_to_the_caller():
    _cleanup()
    rep = auth(*login(*REP))
    try:
        sub = {"endpoint": "https://qa-push.example/ep2", "keys": {"p256dh": "x", "auth": "y"}}
        async def seed():
            await _db().push_subscriptions.insert_one({"user_id": OTHER_ID, "endpoint": sub["endpoint"], "subscription": sub, "updated_at": datetime.now(timezone.utc)})
        asyncio.run(seed())
        st, b = call("POST", f"/api/push/subscribe/{REP_ID}", {"subscription": sub}, rep)
        assert st == 200 and b["status"] == "subscribed"
        async def owners():
            return sorted([d["user_id"] async for d in _db().push_subscriptions.find({"endpoint": sub["endpoint"]})])
        assert asyncio.run(owners()) == [REP_ID]
    finally:
        _cleanup()


def test_startup_dedupe_keeps_the_newest_owner():
    _cleanup()
    try:
        async def go():
            db = _db()
            now = datetime.now(timezone.utc)
            t2 = "ExponentPushToken[qa-dedupe]"
            await db.expo_push_tokens.insert_many([
                {"user_id": OTHER_ID, "expo_push_token": t2, "platform": "ios", "updated_at": now - timedelta(days=3)},
                {"user_id": REP_ID, "expo_push_token": t2, "platform": "ios", "updated_at": now},
                {"user_id": "000000000000000000000def", "expo_push_token": t2, "platform": "ios", "updated_at": now - timedelta(days=1)},
            ])
            from routers.push_notifications import dedupe_push_devices
            r = await dedupe_push_devices()
            left = [d["user_id"] async for d in db.expo_push_tokens.find({"expo_push_token": t2})]
            return r, left
        r, left = asyncio.run(go())
        assert r["expo_removed"] >= 2 and left == [REP_ID], (r, left)
    finally:
        _cleanup()
