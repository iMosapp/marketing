"""Delivery details + resend-as-text (Sep 27 2026): auth binding, explanation mapping, vCard -> link conversion."""
import asyncio
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from _http import call, login, auth  # noqa: E402


@pytest.fixture(scope="module")
def who():
    return {"sa": login("forest@imosapp.com", "Admin123!"), "us": login("mjeast1985@gmail.com", "NavyBean1!")}


@pytest.fixture(scope="module")
def message_id():
    from dotenv import load_dotenv
    from motor.motor_asyncio import AsyncIOMotorClient
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

    async def pick():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        m = await db.messages.find_one({"direction": "outbound", "twilio_sid": {"$regex": "^SM|^MM"}}, sort=[("timestamp", -1)])
        return str(m["_id"]) if m else None

    mid = asyncio.run(pick())
    if not mid:
        pytest.skip("no outbound Twilio message in preview db")
    return mid


def test_delivery_requires_login(message_id):
    assert call("GET", f"/api/messages/{message_id}/delivery")[0] == 401


def test_delivery_forbidden_for_other_rep(who, message_id):
    tok, uid = who["us"]
    assert call("GET", f"/api/messages/{message_id}/delivery", headers=auth(tok, uid))[0] == 403


def test_delivery_for_super_admin(who, message_id):
    tok, uid = who["sa"]
    st, b = call("GET", f"/api/messages/{message_id}/delivery", headers=auth(tok, uid))
    assert st == 200, b
    for k in ("status", "twilio_sid", "explanation", "can_resend_text", "media_kinds", "live_checked"):
        assert k in b
    assert b["explanation"]["title"] and b["explanation"]["tone"] in ("good", "bad", "warn", "muted")


def test_twilio_send_cannot_impersonate_another_rep(who):
    us_tok, us_id = who["us"]
    sa_id = who["sa"][1]
    st, _ = call("POST", "/api/messages/twilio-send", {"user_id": sa_id, "to": "5005550006", "body": "x"}, headers=auth(us_tok, us_id))
    assert st == 403


def test_admin_data_messages_expose_delivery(who):
    tok, uid = who["sa"]
    st, rows = call("GET", "/api/admin/data/messages?limit=20", headers=auth(tok, uid))
    assert st == 200 and isinstance(rows, list)
    for r in rows:
        assert set(("twilio_sid", "error_code", "delivery", "has_media")) <= set(r)


def test_explain_mapping():
    from services.twilio_errors import explain
    assert explain({"status": "failed", "error_code": "30007"})["title"] == "Filtered by the carrier"
    assert explain({"status": "failed", "error_code": "30034"})["tone"] == "bad"
    assert explain({"status": "delivered"})["tone"] == "good"
    assert explain({"status": "sent", "timestamp": datetime.utcnow()})["title"] == "Sent"
    stale = explain({"status": "sent", "has_media": True, "media_urls": ["x.vcf"], "timestamp": datetime.utcnow() - timedelta(hours=1)})
    assert stale["title"] == "Accepted, never confirmed" and "Contact-card" in stale["detail"]


def test_vcard_attachment_becomes_link():
    from services.twilio_errors import vcard_media_to_link
    body, media = vcard_media_to_link("Hi! tap to save my number.", ["https://x/api/profile/1/vcard.vcf", "https://x/api/images/a.jpg"])
    assert body.endswith("https://x/api/profile/1/vcard.vcf") and media == ["https://x/api/images/a.jpg"]
    body2, media2 = vcard_media_to_link("Save me: https://x/api/profile/1/vcard.vcf", ["https://x/api/profile/1/vcard.vcf"])
    assert body2 == "Save me: https://x/api/profile/1/vcard.vcf" and media2 == []
