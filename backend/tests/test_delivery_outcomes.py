"""Delivery outcomes: SENT / FAILED / UNKNOWN are told apart and no outcome is ever re-sent automatically under the same key.
In-process against preview Mongo with a fake Twilio client: nothing reaches Twilio."""
import asyncio
import secrets

import pytest
import requests
from twilio.base.exceptions import TwilioRestException

from services import send_ledger, twilio_service as ts

loop = asyncio.get_event_loop_policy().get_event_loop()  # shared with the other launch suites: get_db() caches one Motor client per process
if loop.is_closed():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


class _Msg:
    sid, status, num_segments = "SMqa" + secrets.token_hex(4), "queued", 1


class _Client:
    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, 0
        self.messages = self

    def create(self, **params):
        self.calls += 1
        if isinstance(self.behaviour, BaseException):
            raise self.behaviour
        return _Msg()


@pytest.fixture
def provider(monkeypatch):
    """Route _deliver to a fake client (preview guard and mock mode off, usage recording stubbed)."""
    def use(behaviour):
        client = _Client(behaviour)
        monkeypatch.setattr(ts, "_held_by_preview_guard", lambda to: False)
        monkeypatch.setattr(ts, "TWILIO_ENABLED", True)
        monkeypatch.setattr(ts, "twilio_client", client)

        async def _sender(_):
            return client

        async def _usage(*a, **k):
            return None
        monkeypatch.setattr(ts, "_client_for_sender", _sender)
        monkeypatch.setattr(ts, "_record_usage", _usage)
        monkeypatch.setattr(ts, "_status_callback_url", lambda: None)
        return client
    return use


@pytest.mark.parametrize("behaviour,outcome", [
    (None, "sent"),
    (TwilioRestException(400, "/Messages", "Invalid 'To' number", code=21211), "failed"),
    (TwilioRestException(503, "/Messages", "Service unavailable", code=20503), "unknown_outcome"),
    (requests.exceptions.ReadTimeout("read timed out"), "unknown_outcome"),
    (ConnectionResetError("connection reset by peer"), "unknown_outcome"),
])
def test_provider_answer_maps_to_ledger_outcome(provider, behaviour, outcome):
    provider(behaviour)
    res = run(ts._deliver("+15005550006", "QA outcome", None, "+15005550099", None, None))
    assert send_ledger.outcome(res) == outcome, res


def test_failure_before_the_provider_call_is_failed_not_unknown(provider, monkeypatch):
    provider(None)

    async def _boom(_):
        raise RuntimeError("could not build the subaccount client")
    monkeypatch.setattr(ts, "_client_for_sender", _boom)
    res = run(ts._deliver("+15005550006", "QA outcome", None, "+15005550099", None, None))
    assert send_ledger.outcome(res) == "failed"


@pytest.mark.parametrize("behaviour,ledger", [
    (None, "sent"),
    (TwilioRestException(400, "/Messages", "Invalid 'To' number", code=21211), "failed"),
    (requests.exceptions.ReadTimeout("read timed out"), "unknown_outcome"),
])
def test_same_key_is_never_sent_twice_whatever_the_outcome(provider, monkeypatch, behaviour, ledger):
    """send_sms with an idempotency key: the first call records the outcome; a retry (scheduler retry, second replica) makes no provider call."""
    from services import outbound_gate
    client = provider(behaviour)

    async def _allow(db, **kw):
        return {"allowed": True, "code": "ok", "shadow": [], "purpose": kw.get("purpose") or "transactional", "org_id": None, "user_id": None}

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(outbound_gate, "evaluate", _allow)
    monkeypatch.setattr(outbound_gate, "log", _noop)
    monkeypatch.setattr(ts, "_disclosure_plan", _noop)
    key = f"qa-outcome:{secrets.token_hex(4)}"
    db = adb()
    try:
        first = run(ts.send_sms("+15005550006", "QA outcome", purpose="transactional", idempotency_key=key))
        assert run(send_ledger.status(db, key)) == ledger, first
        second = run(ts.send_sms("+15005550006", "QA outcome", purpose="transactional", idempotency_key=key))
        assert second["duplicate"] and second["ledger_status"] == ledger and client.calls == 1
    finally:
        run(db.send_ledger.delete_one({"_id": key}))


def test_crashed_send_is_swept_to_unknown_and_stays_unsendable():
    from datetime import datetime, timedelta, timezone
    db = adb()
    key = f"qa-outcome:crash:{secrets.token_hex(4)}"
    assert run(send_ledger.claim(db, key, to="+15005550006"))
    run(db.send_ledger.update_one({"_id": key}, {"$set": {"claimed_at": datetime.now(timezone.utc) - timedelta(seconds=send_ledger.STALE_S + 30)}}))
    try:
        run(send_ledger.sweep(db))
        assert run(send_ledger.status(db, key)) == "unknown_outcome"
        assert not run(send_ledger.claim(db, key, to="+15005550006"))
    finally:
        run(db.send_ledger.delete_one({"_id": key}))
