"""Memo nudge: adding a contact or sharing the digital card schedules one push (~90 s) asking the rep to record a voice memo.
Runs against the live preview API (REACT_APP_BACKEND_URL); the claim (`contacts.memo_nudge_at`) is checked right away, the real push
(Alerts mirror in Mongo) once. Cleans up after itself."""
import asyncio
import os
import random
import time

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from tests._http import auth, call, login
from tests import qa_creds

LOOP = asyncio.new_event_loop()
MONGO = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=LOOP)
DB = MONGO[os.environ["DB_NAME"]]


def run(coro):
    return LOOP.run_until_complete(coro)


@pytest.fixture(scope="module")
def rep():
    tok, uid = login("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com"))
    return tok, uid


def _share(rep, event_type, phone, name):
    tok, uid = rep
    st, body = call("POST", f"/api/contacts/{uid}/find-or-create-and-log",
                    {"phone": phone, "name": name, "event_type": event_type, "event_title": "Digital card", "event_channel": "sms"},
                    auth(tok, uid))
    assert st == 200, (st, body)
    return body


def _create(rep, first, source=None):
    tok, uid = rep
    body = {"first_name": first, "last_name": "Nudge", "phone": f"500555{random.randint(1000, 9999)}"}
    if source:
        body["source"] = source
    st, res = call("POST", f"/api/contacts/{uid}", body, auth(tok, uid))
    assert st == 200, (st, res)
    return res.get("_id") or res.get("id")


def _claim(cid, wait_s=6):
    deadline = time.time() + wait_s
    while time.time() < deadline:
        doc = run(DB.contacts.find_one({"_id": ObjectId(cid)}, {"memo_nudge_at": 1, "memo_nudge_reason": 1}))
        if doc and doc.get("memo_nudge_at"):
            return doc
        time.sleep(0.5)
    return doc or {}


def _cleanup(uid, contact_id):
    run(DB.contacts.delete_one({"_id": ObjectId(contact_id)}))
    run(DB.contact_events.delete_many({"contact_id": contact_id}))
    run(DB.notifications.delete_many({"user_id": uid, "link": f"/contact/{contact_id}?capture=true"}))


def test_manual_add_schedules_nudge_and_push_lands(rep):
    tok, uid = rep
    first = f"Added{random.randint(100, 999)}"
    cid = _create(rep, first)
    try:
        claim = _claim(cid)
        assert claim.get("memo_nudge_reason") == "new_contact", claim
        deadline = time.time() + 150
        note = None
        while time.time() < deadline and not note:
            note = run(DB.notifications.find_one({"user_id": uid, "link": f"/contact/{cid}?capture=true"}))
            if not note:
                time.sleep(3)
        assert note, "no memo nudge landed in Alerts within 150s"
        assert note["title"] == f"You just added {first}. Tell me about them"
        assert note["icon"] == "mic"
    finally:
        _cleanup(uid, cid)


def test_card_share_to_existing_contact_nudges_once_per_day(rep):
    tok, uid = rep
    phone = f"500555{random.randint(1000, 9999)}"
    first = _share(rep, "link_shared", phone, "Plain Share Tester")
    cid = first["contact_id"]
    try:
        assert first["contact_created"] is True
        assert not _claim(cid, wait_s=3).get("memo_nudge_at"), "a plain link share must not nudge"
        again = _share(rep, "digital_card_shared", phone, "Plain Share Tester")
        assert again["contact_id"] == cid and again["contact_created"] is False
        claim = _claim(cid)
        assert claim.get("memo_nudge_reason") == "card", claim
        st, _ = call("POST", f"/api/contacts/{uid}/{cid}/events", {"event_type": "digital_card_shared", "title": "Digital Business Card", "channel": "sms"}, auth(tok, uid))
        assert st == 200
        time.sleep(1.5)
        assert _claim(cid, wait_s=1).get("memo_nudge_at") == claim["memo_nudge_at"], "second share within 24h must not re-claim"
    finally:
        _cleanup(uid, cid)


def test_card_share_creating_contact_claims_new_contact_nudge(rep):
    tok, uid = rep
    phone = f"500555{random.randint(1000, 9999)}"
    body = _share(rep, "digital_card_shared", phone, f"Card{random.randint(100, 999)} Nudge Tester")
    cid = body["contact_id"]
    try:
        assert body["contact_created"] is True
        assert _claim(cid).get("memo_nudge_reason") == "new_contact"
    finally:
        _cleanup(uid, cid)


def test_imports_and_non_card_events_do_not_nudge(rep):
    tok, uid = rep
    cid = _create(rep, f"Imported{random.randint(100, 999)}", source="phone_import")
    try:
        assert not _claim(cid, wait_s=3).get("memo_nudge_at"), "phone imports must not nudge"
        st, _ = call("POST", f"/api/contacts/{uid}/{cid}/events", {"event_type": "note_added", "title": "Note"}, auth(tok, uid))
        assert st == 200
        assert not _claim(cid, wait_s=2).get("memo_nudge_at")
    finally:
        _cleanup(uid, cid)
