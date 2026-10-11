"""Sharing the digital card with someone new creates the contact and, a minute later, nudges the rep to record a voice memo.
Runs against the live preview API (REACT_APP_BACKEND_URL) and checks the Alerts mirror of the push in Mongo."""
import asyncio
import os
import random
import time

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from tests._http import auth, call, login

LOOP = asyncio.new_event_loop()
MONGO = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=LOOP)
DB = MONGO[os.environ["DB_NAME"]]


def run(coro):
    return LOOP.run_until_complete(coro)


@pytest.fixture(scope="module")
def rep():
    tok, uid = login("forest@imosapp.com", "Admin123!")
    return tok, uid


def _share(rep, event_type, phone, name):
    tok, uid = rep
    st, body = call("POST", f"/api/contacts/{uid}/find-or-create-and-log",
                    {"phone": phone, "name": name, "event_type": event_type, "event_title": "Digital card", "event_channel": "sms"},
                    auth(tok, uid))
    assert st == 200, (st, body)
    return body


def _cleanup(uid, contact_id):
    run(DB.contacts.delete_one({"_id": ObjectId(contact_id)}))
    run(DB.contact_events.delete_many({"contact_id": contact_id}))
    run(DB.notifications.delete_many({"user_id": uid, "link": f"/contact/{contact_id}?capture=true"}))


def test_card_share_creates_contact_and_nudges_memo(rep):
    tok, uid = rep
    phone = f"500555{random.randint(1000, 9999)}"
    first = f"Card{random.randint(100, 999)}"
    body = _share(rep, "digital_card_shared", phone, f"{first} Nudge Tester")
    cid = body["contact_id"]
    try:
        assert body["contact_created"] is True
        doc = run(DB.contacts.find_one({"_id": ObjectId(cid)}))
        assert doc["source"] == "digital_card"

        deadline = time.time() + 90
        note = None
        while time.time() < deadline and not note:
            note = run(DB.notifications.find_one({"user_id": uid, "link": f"/contact/{cid}?capture=true"}))
            if not note:
                time.sleep(3)
        assert note, "no memo nudge landed in Alerts within 90s"
        assert first in note["title"]
        assert note["icon"] == "mic"
    finally:
        _cleanup(uid, cid)


def test_existing_contact_and_non_card_events_do_not_nudge(rep):
    tok, uid = rep
    phone = f"500555{random.randint(1000, 9999)}"
    first = _share(rep, "link_shared", phone, "Plain Share Tester")
    cid = first["contact_id"]
    try:
        assert first["contact_created"] is True
        doc = run(DB.contacts.find_one({"_id": ObjectId(cid)}))
        assert doc["source"] == "manual"
        again = _share(rep, "digital_card_shared", phone, "Plain Share Tester")
        assert again["contact_id"] == cid and again["contact_created"] is False
        time.sleep(70)
        assert run(DB.notifications.find_one({"user_id": uid, "link": f"/contact/{cid}?capture=true"})) is None
    finally:
        _cleanup(uid, cid)
