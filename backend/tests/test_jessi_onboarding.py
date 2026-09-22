"""Jessi new-user onboarding, end to end without a real phone.
Case 1 (in-process, fake texts + fake call): admin creates a user with the toggle -> intro / vCard / explain / invite -> CALL rings them ->
call built -> "here's what I learned" -> YEP -> photo ask -> MMS photo saved -> login email asked -> email texted -> activation link ->
link swapped for a code + password set through the real API -> ACCOUNT_ACTIVATED -> login -> welcome summary -> first success.
Case 2 (real API): POST /admin/users/create with jessi_onboarding, admin list / detail / pause / message / resend, public call page + vCard.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_jessi_onboarding.py -q"""
import asyncio
import io
import os
import time

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image

from services import jessi_onboarding as jo

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
ADMIN = ("forest@imosapp.com", "Admin123!")
PHONE = "+15005550077"
PHONE_API = "+15005550078"


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


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return r.json()["token"], r.json()["user"]


async def _wipe(db, phone):
    async for u in db.users.find({"phone": phone}, {"_id": 1}):
        uid = str(u["_id"])
        await db.user_onboarding.delete_many({"user_id": uid})
        await db.password_reset_tokens.delete_many({"user_id": uid})
        await db.contacts.delete_many({"phone": phone})
        await db.users.delete_one({"_id": u["_id"]})
    await db.user_onboarding.delete_many({"phone": phone})


class Sent:
    def __init__(self):
        self.lines = []

    async def say(self, db, doc, body, media=None, kind="jessi"):
        self.lines.append({"kind": kind, "body": body, "media": media or []})
        await db[jo.COLL].update_one({"_id": doc["_id"]}, {"$push": {"thread": {"role": "jessi", "text": body, "at": jo._now(), "ok": True, "kind": kind}}, "$set": {"last_outbound_at": jo._now()}})
        return {"success": True, "message_sid": f"SMfake{len(self.lines)}"}

    def kinds(self):
        return [l["kind"] for l in self.lines]


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (240, 320), (180, 120, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def test_state_machine_end_to_end(monkeypatch):
    db = _db()
    sent = Sent()
    monkeypatch.setattr(jo, "_say", sent.say)
    monkeypatch.setattr(jo, "config", _fast_config)
    from services import interview as iv
    fake_session = {"_id": ObjectId(), "status": "dialing"}

    async def fake_iv_start(db_, me, dry_run=False):
        assert me["phone"] == PHONE and me["twilio_number"] == "+14352203414"
        await db_.interview_sessions.insert_one({**fake_session, "user_id": me["_id"] if isinstance(me["_id"], str) else str(me["_id"]), "dry_run": False})
        return {"id": str(fake_session["_id"]), "status": "dialing"}
    monkeypatch.setattr(iv, "start", fake_iv_start)

    async def fake_llm(system, user, timeout=75):
        if "3 to 4 sentence text message" in system:
            return {"summary": "You have sold trucks for 12 years in St. George and you like to keep it plain and friendly."}
        if "correcting the profile" in system:
            return {"hometown": "Cedar City"}
        return {"reply": "Good question. It helps you keep up with your customers by text. Ready for the setup call?", "intent": "none", "email": None}
    monkeypatch.setattr(jo, "_llm_json", fake_llm)

    async def fake_download(url, ctype=""):
        return _jpeg(), "image/jpeg"
    from services import photo_request
    monkeypatch.setattr(photo_request, "download", fake_download)

    async def flow():
        await _wipe(db, PHONE)
        admin = await db.users.find_one({"email": ADMIN[0]}, {"_id": 1})
        res = await db.users.insert_one({"first_name": "Quinn", "last_name": "QA-Onboard", "name": "Quinn QA-Onboard", "phone": PHONE, "email": "", "role": "user", "is_active": True,
                                         "activation_pending": True, "needs_password_change": True, "jessi_onboarding": True, "password": "x", "created_at": jo._now()})
        uid = str(res.inserted_id)
        doc = await jo.start(db, uid, str(admin["_id"]))
        assert doc["state"] == "NOT_STARTED" and doc["from_number"] == "+14352203414" and doc["phone"] == PHONE
        # kickoff runs as a task with our zero gaps
        for _ in range(60):
            await asyncio.sleep(0.2)
            d = await jo.get(db, uid)
            if d["state"] == "INTERVIEW_INVITED":
                break
        d = await jo.get(db, uid)
        assert d["state"] == "INTERVIEW_INVITED", d["state"]
        assert sent.kinds() == ["intro", "vcf", "explain", "invite"], sent.kinds()
        assert sent.lines[1]["media"] == [jo.vcf_url()]
        assert jo.call_link(d) in sent.lines[3]["body"] and "(500) 555-0077" in sent.lines[3]["body"]
        assert jo.waiting_on(d) == "them"

        # an off-topic question gets an answer and no state change
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "what does this app even do?", [], [], "SM1") is True
        d = await jo.get(db, uid)
        assert d["state"] == "INTERVIEW_INVITED" and sent.kinds()[-1] == "chat"
        # the same Twilio SID again is ignored
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "what does this app even do?", [], [], "SM1") is True
        assert sent.kinds()[-1] == "chat" and len(sent.lines) == 5
        # a stranger's text on the same number is not ours
        assert await jo.handle_inbound(db, "+14352203414", "+15005550099", "hi", [], [], "SM2") is False

        # CALL -> the interview engine rings them from the onboarding number
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "CALL", [], [], "SM3") is True
        d = await jo.get(db, uid)
        assert d["state"] == "INTERVIEW_STARTED" and d["interview_session_id"] == str(fake_session["_id"]) and sent.kinds()[-1] == "calling"
        assert jo.waiting_on(d) == "jessi"

        # the call got built -> summary text
        session = {"_id": fake_session["_id"], "dry_run": False, "extracted": {"bio": "I sell trucks.", "tone": "friendly", "humor_level": "light", "emoji_usage": "rare"}, "highlights": ["12 years selling trucks", "From St. George"]}
        await jo.on_interview_built(db, d, session)
        d = await jo.get(db, uid)
        assert d["state"] == "INTERVIEW_COMPLETE" and "12 years" in d["summary_text"] and sent.kinds()[-1] == "summary"

        # a correction patches the persona, then the photo ask goes out
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"persona": {"bio": "I sell trucks.", "hometown": "St. George"}}})
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "Actually I'm from Cedar City, not St. George", [], [], "SM4") is True
        u = await db.users.find_one({"_id": ObjectId(uid)})
        assert u["persona"]["hometown"] == "Cedar City"
        d = await jo.get(db, uid)
        assert d["state"] == "PHOTO_REQUESTED" and d["summary_confirmed"] is True and sent.kinds()[-2:] == ["summary_fixed", "photo_ask"]

        # a non-image file, then the photo
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "", ["https://x/y.pdf"], ["application/pdf"], "SM5") is True
        assert sent.kinds()[-1] == "photo_not_image"
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "", ["https://example.com/photo.jpg"], ["image/jpeg"], "SM6") is True
        d = await jo.get(db, uid)
        u = await db.users.find_one({"_id": ObjectId(uid)})
        assert u.get("photo_url"), "photo not saved"
        # no email on file -> she asks for it instead of sending the link
        assert d["state"] == "PROFILE_COMPLETE" and d["awaiting_email"] is True and sent.kinds()[-2:] == ["photo_done", "email_ask"]
        assert (d["steps"].get("PHOTO_RECEIVED") and d["steps"].get("PROFILE_COMPLETE"))

        # email by text -> saved -> activation link
        assert await jo.handle_inbound(db, "+14352203414", PHONE, "quinn.qa@invalid.imonsocial.test", [], [], "SM7") is True
        d = await jo.get(db, uid)
        u = await db.users.find_one({"_id": ObjectId(uid)})
        assert u["email"] == "quinn.qa@invalid.imonsocial.test"
        assert d["state"] == "ACTIVATION_SENT" and d["activation_url"] and sent.kinds()[-2:] == ["email_saved", "activation"]
        assert d["activation_url"] in sent.lines[-1]["body"]
        link = await db.password_reset_tokens.find_one({"user_id": uid, "purpose": "activate_link", "used": False})
        assert link and link["source"] == "jessi_onboarding"

        # the link -> code swap -> set password (real API, this is what the /auth/activate?token= page does)
        r = requests.post(f"{API}/auth/activate/link", json={"token": link["token"]}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["identifier"] == PHONE and len(j["code"]) == 6 and j["needs_email"] is False and j["first_name"] == "Quinn"
        r = requests.post(f"{API}/auth/activate/complete", json={"phone": j["identifier"], "code": j["code"], "new_password": "Quinn123!"}, timeout=30)
        assert r.status_code == 200, r.text
        # a used link cannot be reused
        r = requests.post(f"{API}/auth/activate/link", json={"token": link["token"]}, timeout=30)
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            assert r.json().get("already_active") is True
        for _ in range(30):
            await asyncio.sleep(0.3)
            d = await jo.get(db, uid)
            if d["state"] == "ACCOUNT_ACTIVATED":
                break
        assert d["state"] == "ACCOUNT_ACTIVATED", d["state"]
        u = await db.users.find_one({"_id": ObjectId(uid)})
        assert u["jessi_welcome_pending"] is True and u["onboarding_complete"] is True and u["activation_pending"] is False

        # first login -> welcome summary -> first success
        token, user = _login("quinn.qa@invalid.imonsocial.test", "Quinn123!")
        assert user.get("jessi_welcome_pending") is True
        for _ in range(30):
            await asyncio.sleep(0.3)
            d = await jo.get(db, uid)
            if d["state"] == "FIRST_LOGIN":
                break
        assert d["state"] == "FIRST_LOGIN", d["state"]
        r = requests.get(f"{API}/onboarding-jessi/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["onboarded_by_jessi"] and me["welcome_pending"] and me["first_name"] == "Quinn" and me["photo_url"] and me["first_win"]["route"] == "/quick-send/digitalcard"
        r = requests.post(f"{API}/onboarding-jessi/me/first-success", json={"which": "card"}, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200 and r.json()["state"] == "ONBOARDING_COMPLETE", r.text
        d = await jo.get(db, uid)
        assert d["steps"].get("FIRST_SUCCESS") and d["completed_at"] and jo.waiting_on(d) == "done"
        u = await db.users.find_one({"_id": ObjectId(uid)})
        assert u["jessi_welcome_pending"] is False
        # the scheduler leaves a finished user alone
        out = await jo.run_job(db)
        assert isinstance(out, dict)
        await _wipe(db, PHONE)

    _run(flow())


async def _fast_config(db):
    return {**jo.DEFAULT_CFG, "kickoff_gaps_s": [0, 0, 0], "quiet_start": 24, "quiet_end": 0}


def test_admin_api_and_public_pages():
    _run(_wipe(_db(), PHONE_API))
    token, admin = _login(*ADMIN)
    H = {"Authorization": f"Bearer {token}", "X-User-Id": admin["_id"]}
    cfg = requests.get(f"{API}/admin/onboarding-jessi/config", headers=H, timeout=30).json()
    assert cfg["available"] is True and cfg["sender"]["number"] == "+14352203414"

    r = requests.post(f"{API}/admin/users/create", json={"first_name": "Riley", "last_name": "QA-Api", "phone": PHONE_API, "role": "user", "jessi_onboarding": True}, headers=H, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    uid = j["user_id"]
    assert j["jessi_onboarding"] is True and j["temp_password"] is None and j["invite_sent"] is False
    try:
        lst = requests.get(f"{API}/admin/onboarding-jessi", headers=H, timeout=30).json()
        row = next(x for x in lst["rows"] if x["user_id"] == uid)
        assert row["phone"] == PHONE_API and row["from_number"] == "+14352203414" and row["waiting_on"] in ("jessi", "them") and "email" in row
        assert lst["counts"]
        det = requests.get(f"{API}/admin/onboarding-jessi/{uid}", headers=H, timeout=30).json()
        assert det["user"]["name"] == "Riley QA-Api" and det["call_link"].endswith(f"/jessi-call/{det['call_link'].split('/')[-1]}")
        tok = det["call_link"].split("/")[-1]
        # public call page (no auth)
        p = requests.get(f"{API}/onboarding-jessi/call/{tok}", timeout=30)
        assert p.status_code == 200 and p.json()["first_name"] == "Riley" and p.json()["can_call"] is True and p.json()["phone"] == "(500) 555-0078"
        assert requests.get(f"{API}/onboarding-jessi/call/nope", timeout=30).status_code == 404
        v = requests.get(f"{API}/onboarding-jessi/jessi.vcf", timeout=30)
        assert v.status_code == 200 and "BEGIN:VCARD" in v.text and "+14352203414" in v.text and "text/vcard" in v.headers["content-type"]
        # pause / resume / message
        assert requests.post(f"{API}/admin/onboarding-jessi/{uid}/pause", headers=H, timeout=30).json()["paused"] is True
        assert requests.post(f"{API}/admin/onboarding-jessi/{uid}/pause?resume=true", headers=H, timeout=30).json()["paused"] is False
        m = requests.post(f"{API}/admin/onboarding-jessi/{uid}/message", json={"text": "QA admin note"}, headers=H, timeout=30)
        assert m.status_code == 200
        det = requests.get(f"{API}/admin/onboarding-jessi/{uid}", headers=H, timeout=30).json()
        assert any(t.get("text") == "QA admin note" for t in det["thread"]) and any(e["type"] == "ADMIN_MESSAGE" for e in det["events"])
        # mark a step by hand
        mk = requests.post(f"{API}/admin/onboarding-jessi/{uid}/mark/INTERVIEW_INVITED", headers=H, timeout=30)
        assert mk.status_code == 200 and mk.json()["state_index"] >= jo.ORDER["INTERVIEW_INVITED"]
        # a rep cannot see the admin list
        rep_tok, _ = _login("activation-tester@invalid.imonsocial.test", "NewPass123!")
        assert requests.get(f"{API}/admin/onboarding-jessi", headers={"Authorization": f"Bearer {rep_tok}"}, timeout=30).status_code == 403
        # duplicate mobile is refused
        r2 = requests.post(f"{API}/admin/users/create", json={"first_name": "Riley", "last_name": "Again", "phone": PHONE_API, "role": "user", "jessi_onboarding": True}, headers=H, timeout=60)
        assert r2.status_code == 400 and "mobile" in r2.json()["detail"].lower()
        # no email and no toggle is still refused
        r3 = requests.post(f"{API}/admin/users/create", json={"first_name": "No", "last_name": "Email", "phone": "+15005550079", "role": "user"}, headers=H, timeout=60)
        assert r3.status_code == 400
    finally:
        time.sleep(1)
        _run(_wipe(_db(), PHONE_API))
