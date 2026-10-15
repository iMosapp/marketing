"""End-to-end STOP suppression + send-block smoke (preview, mocks on).

Uses the real HTTP messages/send endpoint after calling services.suppression.on_inbound
in-process (as the launch tests do) to confirm every send path refuses while opted-out.
Does NOT touch Twilio (SMS_SEND_ONLY_TO guard returns mock sids).
"""
import asyncio
import os
import secrets
import sys

import pytest
import requests

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
QA_PHONE = "+15005550852"  # QA Text 396852
QA_CONTACT = "6ab749cde92af4ad95bbe576"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()


@pytest.fixture(scope="module")
def manager():
    return _login("qa-manager@invalid.imonsocial.test", "Manager123!")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.new_event_loop().run_until_complete(coro)


def _apply_stop(opt_out: bool):
    from services import suppression  # local
    db_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = db_client[os.environ["DB_NAME"]]

    async def go():
        body = "STOP" if opt_out else "START"
        await suppression.on_inbound(db, from_phone=QA_PHONE, to_phone="+15005550000", body=body, message_sid="SMqa" + secrets.token_hex(6))

    asyncio.new_event_loop().run_until_complete(go())
    db_client.close()


def test_stop_then_start_lifecycle(manager):
    try:
        # Opt out
        _apply_stop(opt_out=True)

        token = manager["token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Consent GET should show opted_out
        r = requests.get(f"{BASE}/api/consent/contact/{QA_CONTACT}", headers=headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("opted_out") is True, r.json()

        # Any send -> blocked
        user_id = manager["user"]["id"] if "id" in manager["user"] else manager["user"].get("_id")
        send_url = f"{BASE}/api/messages/send/{user_id}"
        resp = requests.post(send_url, headers=headers,
                             json={"contact_id": QA_CONTACT,
                                   "content": "QA opt-out test " + secrets.token_hex(3),
                                   "channel": "sms"}, timeout=30)
        body = {}
        try:
            body = resp.json()
        except Exception:
            pass
        # Accept the documented shapes: 409 opted_out OR 200 success:false blocked:true
        blocked = (
            resp.status_code == 409
            or body.get("blocked") is True
            or body.get("success") is False
            or body.get("error_code") == "opted_out"
            or "opted_out" in str(body).lower()
        )
        assert blocked, f"send not blocked opted-out: {resp.status_code} {body}"

        # Texting from the rep's own phone (sms_personal) is refused too, before anything is logged
        rp = requests.post(send_url, headers=headers, json={"contact_id": QA_CONTACT, "content": "QA personal opt-out " + secrets.token_hex(3),
                                                            "channel": "sms_personal"}, timeout=30)
        assert rp.status_code == 409 and rp.json()["detail"]["code"] == "opted_out", f"{rp.status_code} {rp.text[:200]}"

        # Opt-in link creation refused
        r2 = requests.post(f"{BASE}/api/consent/contact/{QA_CONTACT}/opt-in-link",
                           headers=headers, json={"scopes": ["marketing"]}, timeout=30)
        assert r2.status_code == 409, f"{r2.status_code} {r2.text[:200]}"

    finally:
        # Lift suppression so other tests / UI stay usable
        _apply_stop(opt_out=False)
        # Verify lifted
        token = manager["token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE}/api/consent/contact/{QA_CONTACT}", headers=headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("opted_out") in (False, None), r.json()
        user_id = manager["user"]["id"] if "id" in manager["user"] else manager["user"].get("_id")
        rp = requests.post(f"{BASE}/api/messages/send/{user_id}", headers={**headers, "Content-Type": "application/json"},
                           json={"contact_id": QA_CONTACT, "content": "QA personal after START", "channel": "sms_personal"}, timeout=30)
        assert rp.status_code == 200, f"{rp.status_code} {rp.text[:200]}"
