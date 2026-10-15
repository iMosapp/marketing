"""Inbound call routing: a rep calling their own business number from their own cell goes straight to voicemail (dialing the same phone
can never connect); any other caller still rings the rep's cell. Calls the route with the signature dependency overridden; QA user wiped."""
import os

import pytest
from bson import ObjectId
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import server  # noqa: E402
from services.twilio_signature import require_signed_callback  # noqa: E402

BIZ = "+15005550188"
CELL = "+18015550188"
OTHER = "+18015550177"


@pytest.fixture(scope="module")
def client():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    uid = db.users.insert_one({"email": "qa-selfcall@invalid.imonsocial.test", "name": "QA Selfcall", "role": "user", "status": "active",
                               "twilio_number": BIZ, "phone": CELL}).inserted_id
    server.app.dependency_overrides[require_signed_callback] = lambda: None
    with TestClient(server.app) as c:
        yield c
    server.app.dependency_overrides.pop(require_signed_callback, None)
    db.users.delete_one({"_id": ObjectId(uid)})
    for coll in ("contact_events", "voicemail_inbox"):
        db[coll].delete_many({"call_sid": {"$in": ["CAqaself1", "CAqaother1"]}})


def test_calling_your_own_number_from_your_cell_goes_to_voicemail(client):
    r = client.post("/api/webhooks/twilio/voice", data={"To": BIZ, "From": CELL, "CallSid": "CAqaself1"})
    assert r.status_code == 200 and "<Record" in r.text and "<Dial" not in r.text


def test_anyone_else_still_rings_the_rep(client):
    r = client.post("/api/webhooks/twilio/voice", data={"To": BIZ, "From": OTHER, "CallSid": "CAqaother1"})
    assert r.status_code == 200 and "<Dial" in r.text and f">{CELL}</Number>" in r.text
