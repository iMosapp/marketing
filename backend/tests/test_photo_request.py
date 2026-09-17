"""Photo request after the interview: the text goes out from the rep's work number, a reply with a picture becomes the card
photo, plain replies get a nudge (twice), STOP passes through, expired/done requests are ignored. Last case goes through the
real /webhooks/twilio/incoming endpoint with a public image URL.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_photo_request.py -q"""
import asyncio
import io
import os
from datetime import timedelta

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image

from services import photo_request as pr

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
TESTER = "activation-tester@invalid.imonsocial.test"
PHOTO_FIELDS = ["photo_url", "photo_path", "photo_thumb_path", "photo_avatar_path", "onboarding_complete", "og_image_path", "photo_storage_fallback", "updated_at"]


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


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (240, 320), (180, 120, 60)).save(buf, format="JPEG")
    return buf.getvalue()


async def _snapshot(db):
    u = await db.users.find_one({"email": TESTER})
    return u, {k: u.get(k) for k in PHOTO_FIELDS if k in u}


async def _restore(db, user, snap):
    unset = {k: "" for k in PHOTO_FIELDS if k not in snap}
    ops = {"$set": snap}
    if unset:
        ops["$unset"] = unset
    await db.users.update_one({"_id": user["_id"]}, ops)
    await db.photo_requests.delete_many({"user_id": str(user["_id"])})


def _session(user, **kw):
    return {"_id": ObjectId(), "user_id": str(user["_id"]), "rep_phone": user["phone"], "from_number": os.environ.get("TWILIO_PHONE_NUMBER", "+14352203414"), "locale": "en-US", **kw}


def test_ask_nudge_photo_and_expiry(monkeypatch):
    sent = []

    async def fake_send(to, body, media_urls=None, from_phone=None):
        sent.append({"to": to, "body": body, "from": from_phone})
        return {"success": True, "message_sid": f"SM{len(sent)}"}

    async def fake_download(url, content_type=""):
        return _jpeg(), "image/jpeg"

    import services.twilio_service as ts
    monkeypatch.setattr(ts, "send_sms", fake_send)
    monkeypatch.setattr(pr, "download", fake_download)

    async def go():
        db = _db()
        user, snap = await _snapshot(db)
        try:
            await db.users.update_one({"_id": user["_id"]}, {"$unset": {"photo_url": "", "photo_path": ""}})
            req = await pr.ask(db, _session(user))
            assert req["status"] == "open" and req["had_photo"] is False and req["to_phone"] == "+15005550006" and req["sms"]["ok"]
            assert "reply to this text with a photo" in sent[-1]["body"] and sent[-1]["from"] == req["from_number"] and sent[-1]["to"] == "+15005550006"
            frm, cell = req["from_number"], req["to_phone"]
            # a text without a picture: nudge (twice at most), never a contact
            assert await pr.handle_inbound(db, frm, cell, "ok one sec", [], [], "SM_a")
            assert "Just the photo" in sent[-1]["body"]
            assert await pr.handle_inbound(db, frm, cell, "", ["https://api.twilio.com/x.mp4"], ["video/mp4"], "SM_b")
            assert "not a picture" in sent[-1]["body"]
            n = len(sent)
            assert await pr.handle_inbound(db, frm, cell, "hello?", [], [], "SM_c")
            assert len(sent) == n, "third plain reply is swallowed quietly"
            # STOP is never ours
            assert await pr.handle_inbound(db, frm, cell, "STOP", [], [], "SM_d") is False
            # someone else texting that number is not ours either
            assert await pr.handle_inbound(db, frm, "+15005550099", "hi", [], [], "SM_e") is False
            # the photo
            assert await pr.handle_inbound(db, frm, cell, "", ["https://api.twilio.com/2010-04-01/Accounts/AC/Messages/MM/Media/ME"], ["image/jpeg"], "SM_f")
            u = await db.users.find_one({"_id": user["_id"]})
            assert u.get("photo_url") and (u["photo_url"].startswith("/api/images/") or u["photo_url"].startswith("data:"))
            assert u.get("onboarding_complete") is True, "bio + photo = onboarding done"
            req = await db.photo_requests.find_one({"_id": req["_id"]})
            assert req["status"] == "done" and req["photo_url"] == u["photo_url"] and req["message_sid"] == "SM_f"
            assert sent[-1]["body"].startswith("Got it, Activation") and "card" in sent[-1]["body"]
            s = await pr.summary(db, str(user["_id"]))
            assert s["status"] == "done" and s["photo_saved_at"]
            # done: further texts fall through to normal routing
            assert await pr.handle_inbound(db, frm, cell, "thanks", [], [], "SM_g") is False
            # replace flow + expiry
            req2 = await pr.ask(db, _session(user, locale="nl-NL"))
            assert req2["had_photo"] is True and "nieuwe foto" in sent[-1]["body"]
            assert (await pr.summary(db, str(user["_id"])))["status"] == "open"
            await db.photo_requests.update_one({"_id": req2["_id"]}, {"$set": {"expires_at": pr._now() - timedelta(minutes=1)}})
            assert await pr.handle_inbound(db, frm, cell, "", ["https://api.twilio.com/m"], ["image/jpeg"], "SM_h") is False
            assert (await pr.summary(db, str(user["_id"])))["status"] == "expired"
            # a bad image: retry text, request stays open
            async def bad_download(url, content_type=""):
                return b"not an image at all, definitely more than one hundred bytes of nothing useful........................", "image/jpeg"
            monkeypatch.setattr(pr, "download", bad_download)
            req3 = await pr.ask(db, _session(user))
            assert await pr.handle_inbound(db, frm, cell, "", ["https://api.twilio.com/m2"], ["image/jpeg"], "SM_i")
            assert "didn't come through" in sent[-1]["body"]
            assert (await db.photo_requests.find_one({"_id": req3["_id"]}))["status"] == "open"
        finally:
            await _restore(db, user, snap)
    _run(go())


def test_webhook_e2e():
    """Real server: an MMS from the tester's cell to the number that asked lands as their card photo."""
    async def setup():
        db = _db()
        user, snap = await _snapshot(db)
        req = await pr.ask(db, _session(user))
        return user, snap, req
    user, snap, req = _run(setup())
    try:
        r = requests.post(f"{API}/webhooks/twilio/incoming", data={"From": req["to_phone"], "To": req["from_number"], "Body": "", "MessageSid": f"MM_photo_{req['_id']}", "NumMedia": "1",
                                                                 "MediaUrl0": f"{API}/public/shop-contact/logo.png", "MediaContentType0": "image/png"}, timeout=60)
        assert r.status_code == 200 and "<Response>" in r.text

        async def check():
            db = _db()
            doc = await db.photo_requests.find_one({"_id": req["_id"]})
            u = await db.users.find_one({"_id": user["_id"]}, {"photo_url": 1})
            junk = await db.contacts.count_documents({"user_id": str(user["_id"]), "phone": {"$regex": "5550006"}})
            return doc, u, junk
        doc, u, junk = _run(check())
        assert doc["status"] == "done", doc
        assert u.get("photo_url") and u["photo_url"] == doc["photo_url"]
        assert doc["replies"] and "card" in doc["replies"][-1]["body"]
        assert junk == 0, "never became a contact or a thread for the rep"
    finally:
        async def cl():
            await _restore(_db(), user, snap)
        _run(cl())
