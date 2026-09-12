"""Ask Jessi extensions: team ask (managers), draft-from-answer, inbound email webhook, recorded-conversation upload caps.
Run: cd /app/backend && python -m pytest tests/test_ask_extensions_api.py -q
Needs the scorecard demo seed (Sarah Tester for Activation Tester) and the QA manager."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def rep():
    return _login(REP)


@pytest.fixture(scope="module")
def mgr():
    return _login(MANAGER)


@pytest.fixture(scope="module")
def rep_id():
    return requests.post(f"{BASE_URL}/api/auth/login", json=REP, timeout=20).json()["user"]["_id"]


@pytest.fixture(scope="module")
def sarah_id(rep):
    d = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine", headers=rep, timeout=20).json()
    return next(e["contact_id"] for e in d["evaluations"] if e["call_sid"] == "CA_scdemo_good_001")


# ---------------------------------------------------------------- team ask
def test_team_overview_rbac(rep):
    assert requests.get(f"{BASE_URL}/api/contact-ask/team/overview", timeout=20).status_code == 401
    assert requests.get(f"{BASE_URL}/api/contact-ask/team/overview", headers=rep, timeout=20).status_code == 403
    assert requests.post(f"{BASE_URL}/api/contact-ask/team/ask", json={"question": "who is waiting?"}, headers=rep, timeout=20).status_code == 403


def test_team_overview_manager(mgr, rep_id):
    d = requests.get(f"{BASE_URL}/api/contact-ask/team/overview?days=30", headers=mgr, timeout=30).json()
    assert d["stats"]["days"] == 30 and d["stats"]["reps"] >= 1 and d["stats"]["calls"] >= 3
    assert any(r["id"] == rep_id for r in d["reps"]) and 3 <= len(d["starters"]) <= 6
    one = requests.get(f"{BASE_URL}/api/contact-ask/team/overview?days=99&rep_id={rep_id}", headers=mgr, timeout=30).json()
    assert one["stats"]["days"] == 30 and one["stats"]["reps"] == 1
    assert any("Activation" in s for s in one["starters"])


def test_team_ask_validation(mgr):
    assert requests.post(f"{BASE_URL}/api/contact-ask/team/ask", json={"question": " "}, headers=mgr, timeout=20).status_code == 400
    assert requests.post(f"{BASE_URL}/api/contact-ask/team/ask", json={"question": "who is waiting?", "rep_id": "000000000000000000000000"}, headers=mgr, timeout=20).status_code == 404
    assert requests.get(f"{BASE_URL}/api/contact-ask/team/sessions/nope", headers=mgr, timeout=20).status_code == 404


def test_team_ask_grounded_session(mgr, rep_id):
    r = requests.post(f"{BASE_URL}/api/contact-ask/team/ask", json={"question": "Summarize the recorded calls: what went well and what was missed?", "rep_id": rep_id, "days": 30}, headers=mgr, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    msg = d["message"]
    assert msg["content"] and "—" not in msg["content"]
    assert msg["citations"], "expected [P]/[C] citations"
    assert all(c["kind"] in ("thread", "call") and c["token"] for c in msg["citations"])
    assert any(c["kind"] == "call" and c["call_sid"].startswith("CA_scdemo") and "has_recording" in c for c in msg["citations"])
    assert 1 <= len(msg["follow_ups"]) <= 3 and not any("[" in f for f in msg["follow_ups"])
    sid = d["session_id"]
    s = requests.get(f"{BASE_URL}/api/contact-ask/team/sessions/{sid}", headers=mgr, timeout=20).json()
    assert len(s["messages"]) == 2 and s["messages"][0]["role"] == "user"
    ov = requests.get(f"{BASE_URL}/api/contact-ask/team/overview?days=30&rep_id={rep_id}", headers=mgr, timeout=30).json()
    assert any(x["id"] == sid for x in ov["sessions"])
    # scoped sessions do not leak into the whole-team list
    ov_all = requests.get(f"{BASE_URL}/api/contact-ask/team/overview?days=30", headers=mgr, timeout=30).json()
    assert not any(x["id"] == sid for x in ov_all["sessions"])


# ---------------------------------------------------------------- draft from answer
def test_draft_from_answer(rep, sarah_id):
    assert requests.post(f"{BASE_URL}/api/contact-ask/{sarah_id}/draft", json={"answer": "hi"}, headers=rep, timeout=20).status_code == 400
    r = requests.post(f"{BASE_URL}/api/contact-ask/{sarah_id}/draft",
                      json={"answer": "Sarah is trading in a 2019 Explorer with about 62,000 miles [C1@0:40]. She wants to come in Saturday morning [C1@1:10].", "question": "What is Sarah trading in?"},
                      headers=rep, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 10 < len(d["text"]) <= 600 and "—" not in d["text"] and "[C1" not in d["text"]
    assert "conversation_id" in d


# ---------------------------------------------------------------- recorded conversation upload caps
def test_conversation_chunk_caps(rep, rep_id, sarah_id):
    url = f"{BASE_URL}/api/voice-notes/{rep_id}/{sarah_id}/chunk"
    base = {"upload_id": f"t{uuid.uuid4().hex[:8]}", "index": 0, "total": 2, "data": "AAAA", "content_type": "audio/mp4"}
    assert requests.post(url, json={**base, "duration": 60}, timeout=20).status_code == 401
    # a 30-minute memo is rejected, the same length as a recorded conversation is accepted (first of two pieces, nothing processed yet)
    assert requests.post(url, json={**base, "duration": 1800, "kind": "memo"}, headers=rep, timeout=20).status_code == 400
    r = requests.post(url, json={**base, "duration": 1800, "kind": "conversation"}, headers=rep, timeout=20)
    assert r.status_code == 200 and r.json() == {"success": True, "received": 1, "total": 2}
    assert requests.post(url, json={**base, "duration": 46 * 60, "kind": "conversation"}, headers=rep, timeout=20).status_code == 400
    assert requests.post(url, json={**base, "total": 0, "duration": 60}, headers=rep, timeout=20).status_code == 400

    async def cleanup():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        await db.voice_upload_chunks.delete_many({"upload_id": base["upload_id"]})
    _run(cleanup())


# ---------------------------------------------------------------- inbound email webhook
def test_webhook_http_guards():
    url = f"{BASE_URL}/api/webhooks/resend/inbound"
    assert requests.post(url, data="not json", headers={"Content-Type": "application/json"}, timeout=20).status_code == 400
    assert requests.post(url, json={"type": "email.sent", "data": {}}, timeout=20).json() == {"ignored": "email.sent"}
    assert requests.post(url, json={"type": "email.received", "data": {}}, timeout=20).status_code == 400


def test_clean_reply():
    from routers.resend_webhooks import clean_reply, _strip_html
    raw = "Yes, Saturday at 10 works for me!\n\nThanks,\nSarah\n\nOn Tue, Jun 2, 2026 at 9:14 AM Forest Ward <forest@x.com> wrote:\n> Hi Sarah, does Saturday work?\n> Forest"
    assert clean_reply(raw) == "Yes, Saturday at 10 works for me!\n\nThanks,\nSarah"
    assert clean_reply("Sounds good\nSent from my iPhone") == "Sounds good"
    assert clean_reply("> quoted only") == ""
    assert _strip_html("<p>Hello <b>there</b></p><div>bye</div>").split() == ["Hello", "there", "bye"]


def test_webhook_signature():
    import base64, hmac, hashlib, json
    from routers.resend_webhooks import _verify_svix
    secret_raw = b"0123456789abcdef0123456789abcdef"
    os.environ["RESEND_WEBHOOK_SECRET"] = "whsec_" + base64.b64encode(secret_raw).decode()
    try:
        body = json.dumps({"type": "email.received"}).encode()
        ts = str(int(datetime.now(timezone.utc).timestamp()))
        sig = base64.b64encode(hmac.new(secret_raw, f"msg_1.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
        good = {"svix-id": "msg_1", "svix-timestamp": ts, "svix-signature": f"v1,{sig}"}
        assert _verify_svix(good, body) is True
        assert _verify_svix({**good, "svix-signature": "v1,bogus"}, body) is False
        assert _verify_svix({**good, "svix-timestamp": str(int(ts) - 900)}, body) is False
        assert _verify_svix({}, body) is False
    finally:
        os.environ.pop("RESEND_WEBHOOK_SECRET", None)
    assert _verify_svix({}, b"x") is True  # no secret configured = accept


def test_ingest_email_into_thread(rep_id, sarah_id):
    from routers.resend_webhooks import ingest_received_email

    async def run():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        now = datetime.now(timezone.utc)
        conv = await db.conversations.insert_one({"user_id": rep_id, "contact_id": sarah_id, "contact_name": "Sarah Tester", "contact_phone": "+15005550041", "rep_phone": "+15005550006",
                                                  "status": "active", "unread": False, "unread_count": 0, "created_at": now, "last_message_at": now, "is_test": True, "ask_ext_test": True})
        cid = str(conv.inserted_id)
        eid = f"em_{uuid.uuid4().hex[:10]}"
        email = {"from": "Sarah Tester <sarah.tester@example.com>", "to": [f"reply+{cid}@reply.imonsocial.com"], "subject": "Re: Saturday",
                 "text": "Saturday at 10 works!\n\nOn Tue, Jun 2, 2026 Forest wrote:\n> does Saturday work?"}
        try:
            out = await ingest_received_email(db, email, eid)
            assert out["status"] == "ok" and out["conversation_id"] == cid
            msg = await db.messages.find_one({"_id": ObjectId(out["message_id"])})
            assert msg["content"] == "Saturday at 10 works!" and msg["channel"] == "email" and msg["sender"] == "contact"
            assert msg["subject"] == "Re: Saturday" and msg["email_from"] == "sarah.tester@example.com" and msg["user_id"] == rep_id
            c = await db.conversations.find_one({"_id": conv.inserted_id})
            assert c["unread"] is True and c["unread_count"] == 1 and c["last_channel"] == "email" and c["needs_assistance"] is True
            assert await db.contact_events.count_documents({"message_id": out["message_id"], "event_type": "email_received"}) == 1
            assert await db.notifications.count_documents({"conversation_id": cid, "type": "new_message"}) == 1
            # replay of the same Resend email is a no-op
            assert (await ingest_received_email(db, email, eid))["status"] == "duplicate"
            assert await db.messages.count_documents({"conversation_id": cid}) == 1
            # no reply+ address: route by the sender's email on a contact; unknown sender -> unmatched queue
            await db.contacts.update_one({"_id": ObjectId(sarah_id)}, {"$set": {"work_email": "sarah.tester@example.com"}})
            out2 = await ingest_received_email(db, {"from": "sarah.tester@example.com", "to": ["sales@imonsocial.com"], "subject": "", "html": "<p>Also, can I bring my <b>trade</b>?</p>"}, eid + "b")
            assert out2["status"] == "ok" and out2["conversation_id"] == cid
            msg2 = await db.messages.find_one({"_id": ObjectId(out2["message_id"])})
            assert msg2["content"].split() == ["Also,", "can", "I", "bring", "my", "trade?"]
            out3 = await ingest_received_email(db, {"from": "nobody@nowhere.example", "to": ["sales@imonsocial.com"], "subject": "Hi", "text": "hello"}, eid + "c")
            assert out3["status"] == "unmatched"
            assert await db.inbound_email_unmatched.count_documents({"email_id": eid + "c"}) == 1
            # the thread API shows the email like any inbound message
            r = requests.get(f"{BASE_URL}/api/messages/thread/{cid}", timeout=20)
            assert r.status_code == 200
            body = r.json()
            items = body if isinstance(body, list) else body.get("messages", [])
            mine = [m for m in items if m.get("channel") == "email"]
            assert len(mine) == 2 and mine[0]["sender"] == "contact" and mine[0].get("subject") == "Re: Saturday"
        finally:
            await db.messages.delete_many({"conversation_id": cid})
            await db.contact_events.delete_many({"conversation_id": cid})
            await db.notifications.delete_many({"conversation_id": cid})
            await db.conversations.delete_one({"_id": conv.inserted_id})
            await db.inbound_email_unmatched.delete_many({"email_id": {"$regex": f"^{eid}"}})
            await db.contacts.update_one({"_id": ObjectId(sarah_id)}, {"$unset": {"work_email": ""}})
    _run(run())
