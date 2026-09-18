"""Jessi hosts the rep's line on GPT-Live: the click-to-call briefing and the mystery-shop announcement, with a fake Twilio socket and a fake
GPT-Live upstream (no OpenAI, no Twilio calls, real Mongo). The /host-after webhooks are hit on the running backend (localhost:8001)."""
import asyncio
import os
import httpx
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import lab  # noqa: E402
from services import live_host as lh  # noqa: E402
from services import live_shops as ls  # noqa: E402

pytestmark = pytest.mark.asyncio
BASE = "http://localhost:8001/api"


def _shop(direction="inbound", locale="en-US", **extra):
    return {"_id": ObjectId(), "token": "tok" + ObjectId().__str__()[-6:], "mode": "phone", "kind": "mystery_shop", "status": "dialing", "direction": direction,
            "locale": locale, "client_id": str(ObjectId()), "script_id": str(ObjectId()), "rep_name": "Sam Seller", "store_name": "QA Jeep", "department": "sales", "manual": True,
            "persona": {"name": "Casey Morgan", "voice": "female", "opening_line": "Hi, I'm calling about the Wrangler you have online.", "vehicle": "a Wrangler"},
            "turns": [], "attempts": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc), **extra}


class FakeUpstream:
    def __init__(self):
        self.sent = []
        self.q: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send(self, ev):
        self.sent.append(ev)
        if ev.get("type") == "session.close":
            await self.q.put({"type": "session.closed", "reason": "close_requested", "usage": {"seconds": 23}})

    def __aiter__(self):
        return self

    async def __anext__(self):
        ev = await self.q.get()
        if ev is None:
            raise StopAsyncIteration
        return ev

    async def close(self):
        self.closed = True
        await self.q.put(None)

    def types(self):
        return [e.get("type") for e in self.sent]

    def texts(self):
        return " | ".join(str(e.get("content") or e.get("session", {}).get("instructions", ""))[:400] for e in self.sent)


async def _ret(x):
    return x


async def _wait(cond, timeout=8.0):
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if cond():
            return True
        await asyncio.sleep(0.05)
    return False


async def _rep():
    db = get_db()
    u = await db.users.find_one({"email": "activation-tester@invalid.imonsocial.test"}, {"_id": 1, "name": 1})
    assert u, "activation tester missing"
    return u


@pytest.fixture(autouse=True)
def _no_twilio_rest(monkeypatch):
    """Never touch Twilio's REST API from tests; the WebSocket-close handoff is the default path here."""
    calls: list = []

    async def fake_redirect(call_sid, url):
        calls.append((call_sid, url))
        return False
    monkeypatch.setattr(lh, "redirect_call", fake_redirect)
    lh._test_redirects = calls  # type: ignore[attr-defined]
    yield calls


async def _seed_customer(uid: str) -> dict:
    """Bud Ward: drives a Tahoe, texted yesterday, a voice memo two days ago, an overdue task, tagged hot + Harley riders."""
    db = get_db()
    now = datetime.now(timezone.utc)
    cid = (await db.contacts.insert_one({"user_id": uid, "first_name": "Bud", "last_name": "QA-Host", "name": "Bud QA-Host", "phone": "+15005550077", "vehicle": "2024 Chevy Tahoe",
                                         "tags": ["Harley riders", "hot", "QA Host"], "status": "active", "created_at": now, "updated_at": now})).inserted_id
    conv = (await db.conversations.insert_one({"user_id": uid, "contact_id": str(cid), "created_at": now, "updated_at": now, "qa_host": True})).inserted_id
    await db.messages.insert_one({"conversation_id": str(conv), "contact_id": str(cid), "sender": "contact", "direction": "inbound", "content": "Can you do 450 a month on the Tahoe? Saturday works for me.",
                                  "timestamp": now - timedelta(days=1), "created_at": now - timedelta(days=1), "qa_host": True})
    await db.voice_notes.insert_one({"user_id": uid, "contact_id": str(cid), "summary": "Wants the black one, trading a 2018 Silverado.", "transcript": "", "created_at": now - timedelta(days=2), "kind": "memo", "qa_host": True})
    await db.tasks.insert_one({"user_id": uid, "contact_id": str(cid), "title": "Send Bud the out-the-door numbers", "status": "pending", "due_date": now - timedelta(days=1), "created_at": now, "qa_host": True})
    return {"cid": str(cid), "conv": str(conv)}


async def _wipe_customer(cid: str):
    db = get_db()
    await db.contacts.delete_one({"_id": ObjectId(cid)})
    for coll in ("conversations", "messages", "voice_notes", "tasks"):
        await db[coll].delete_many({"qa_host": True})
    await db.pending_calls.delete_many({"qa_host": True})


async def test_intent_table():
    cases = {"yes": "go", "connect": "go", "yeah go ahead": "go", "put him through": "go", "do it": "go", "I'm good, dial": "go", "uh yes": "go",
             "okay": "other", "hello?": "other", "hello this is sam": "other",
             "not now": "later", "no": "later", "nope": "later", "cancel": "later", "skip it": "later", "not right now, busy": "later",
             "okay, what did he text?": "question", "what did he say about the price": "question", "remind me what he drives": "question",
             "sure, what's his budget": "question", "can you repeat that": "question", "no wait, what did he text": "question"}
    bad = {t: lh.intent(t) for t, want in cases.items() if lh.intent(t) != want}
    assert not bad, bad


async def test_decide_twiml_and_fallback(monkeypatch):
    db = get_db()
    assert lab._default(lh.LAB_KEY) == "live"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    s = _shop()
    on, why = await lh.decide(db, "shop", s)
    assert on is True and why == "Jessi hosts the line"
    on, why = await lh.decide(db, "shop", {**s, "locale": "nl-NL"})
    assert on is False and "Dutch" in why
    pending = {"_id": ObjectId(), "token": "abc123"}
    on, _ = await lh.decide(db, "call", pending)
    assert on is True
    xml = lh.shop_twiml(s)
    assert f'/api/scripts/roleplay/host/{s["_id"]}/{s["token"]}" />' in xml and f'/api/scripts/roleplay/host-after/{s["_id"]}?t={s["token"]}' in xml
    assert xml.count(f'host-after/{s["_id"]}?t={s["token"]}') == 2 and "<Redirect method=\"POST\">" in xml, "action + Redirect fallback both point at host-after"
    xml = lh.call_twiml(pending)
    assert f'/api/webhooks/twilio/call-host/{pending["_id"]}/abc123" />' in xml and f'call-bridge-host-after?pid={pending["_id"]}&amp;t=abc123' in xml
    assert xml.index("</Connect>") < xml.index("<Redirect")
    assert lh.after_url("call", pending) == f'{lh.scr._app_url()}/api/webhooks/twilio/call-bridge-host-after?pid={pending["_id"]}&t=abc123'
    assert lh.said_line("Alright. Connecting you now!", lh.CONNECT_LINE) and not lh.said_line("Ready to connect?", lh.CONNECT_LINE) and not lh.said_line("", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    on, why = await lh.decide(db, "call", pending)
    assert on is False and why == ls.NO_KEY


async def test_call_brief_facts():
    db = get_db()
    rep = await _rep()
    seeded = await _seed_customer(str(rep["_id"]))
    try:
        pending = {"_id": ObjectId(), "token": "t", "rep_user_id": str(rep["_id"]), "contact_id": seeded["cid"], "customer_phone": "+15005550077", "rep_twilio_number": "+15005550001"}
        b = await lh.call_brief(db, pending)
        text = " ".join(b["facts"])
        assert b["who"] == "Bud QA-Host" and b["customer_first"] == "Bud"
        assert "Drives 2024 Chevy Tahoe" in text
        assert "Yesterday Bud texted" in text and "450 a month" in text, text
        assert "You owe them: Send Bud the out-the-door numbers, overdue" in text
        assert "Tagged hot, Harley riders" in text, text
        assert b["opener"].startswith("Hey ") and "2024 Chevy Tahoe" in b["opener"] and "Say connect when you're ready" in b["opener"]
        assert "\u2014" not in b["opener"]
        ins = lh.instructions("call", b, {})
        assert lh.CONNECT_LINE in ins and lh.CANCEL_LINE in ins and "never will be while you are" in ins
        # no contact on file -> still a usable opener
        b2 = await lh.call_brief(db, {**pending, "contact_id": None})
        assert "ending in 0077" in b2["opener"]
    finally:
        await _wipe_customer(seeded["cid"])


async def test_click_to_call_host_connects(monkeypatch):
    """Rep picks up, Jessi briefs, rep says 'yes connect', Jessi says the connect line and delegates -> stream closes with decision go -> /call-bridge-host-after dials the customer."""
    db = get_db()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    rep = await _rep()
    seeded = await _seed_customer(str(rep["_id"]))
    pending = {"_id": ObjectId(), "token": "hosttok1", "rep_user_id": str(rep["_id"]), "contact_id": seeded["cid"], "customer_phone": "+15005550077", "rep_twilio_number": "+15005550001",
               "rep_name": "Tester", "call_sid": "CA_qa_host_1", "created_at": datetime.now(timezone.utc), "qa_host": True}
    await db.pending_calls.insert_one(pending)
    up, out, closed = FakeUpstream(), [], {"v": False}

    async def send(m):
        out.append(m)

    async def close():
        closed["v"] = True
    try:
        bridge = lh.HostBridge(db, pending, "call", send, close, connect=lambda: _ret(up))
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZ1", "callSid": "CA_qa_host_1"}})
        assert up.types()[0] == "session.start"
        start = up.sent[0]["session"]
        assert start["model"] == "gpt-live-1" and start["audio"]["format"]["type"] == "audio/pcmu" and "2024 Chevy Tahoe" in start["instructions"]
        row = await db.pending_calls.find_one({"_id": pending["_id"]})
        assert row["host"]["transport"] == "gpt-live" and row["host"]["voice"] == start["audio"]["output"]["voice"] and "Tahoe" in row["host"]["opener"]
        await up.q.put({"type": "session.started", "session": {"id": "sess_1"}})
        assert await _wait(lambda: "session.commentary.append" in up.types())
        assert any(e.get("type") == "session.instructions.append" and "Speak first" in e["content"] for e in up.sent)
        # Jessi speaks the brief, the rep answers
        await up.q.put({"type": "session.output_audio.delta", "delta": "AAAA"})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Hey Tester, calling Bud about the Tahoe.", "start_ms": 0, "end_ms": 4000})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "Yes, connect.", "start_ms": 6000, "end_ms": 7000})
        await up.q.put({"type": "session.output_transcript.delta", "delta": lh.CONNECT_LINE, "start_ms": 8000, "end_ms": 9000})
        assert await _wait(lambda: bridge.decision == "go"), "the rep's 'yes, connect' should decide go"
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "d1", "target": "client"}})
        assert await _wait(lambda: closed["v"], timeout=10), "the stream should close after the delegation"
        await asyncio.wait_for(bridge.done.wait(), 5)
        assert bridge.reason == "go"
        row = await db.pending_calls.find_one({"_id": pending["_id"]})
        h = row["host"]
        assert h["decision"] == "go" and h["via"] == "speech" and h["end_reason"] == "go" and h["seconds"] == 23
        assert h["handoff"] == "ws_close" and h["call_sid"] == "CA_qa_host_1"
        assert lh._test_redirects == [("CA_qa_host_1", lh.after_url("call", pending))], "the REST redirect is always tried first"
        roles = [t["role"] for t in h["turns"]]
        assert roles == ["jessi", "rep", "jessi"], roles
        assert any("disconnecting" in str(e.get("content")) for e in up.sent if e.get("type") == "session.thinking.append")
        assert lh.describe(row)["decision"] == "go"
        # Twilio hits the action URL -> the customer is dialed, no second "connecting" line
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge-host-after", params={"pid": str(pending["_id"]), "t": "hosttok1"}, data={"CallSid": "CA_qa_host_1"})
        assert r.status_code == 200 and "<Dial" in r.text and "<Number>+15005550077</Number>" in r.text and 'callerId="+15005550001"' in r.text and "<Say>" not in r.text, r.text
        row = await db.pending_calls.find_one({"_id": pending["_id"]})
        assert row["host"]["after_hits"] == 1
        # a wrong token never dials
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge-host-after", params={"pid": str(pending["_id"]), "t": "nope"}, data={})
        assert "<Dial" not in r.text and "<Hangup/>" in r.text
    finally:
        await _wipe_customer(seeded["cid"])


async def test_click_to_call_rest_handoff_and_jessi_line(monkeypatch):
    """Production path: the rep's transcript is late or garbled, but Jessi says 'Connecting you now' -> decision go from her own line;
    the handoff goes through Twilio's REST redirect (no reliance on the WebSocket close), Twilio then stops the stream itself."""
    db = get_db()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    moved: list = []

    async def fake_redirect(call_sid, url):
        moved.append((call_sid, url))
        return True
    monkeypatch.setattr(lh, "redirect_call", fake_redirect)
    monkeypatch.setattr(lh, "CLOSE_AFTER_REDIRECT_S", 2)
    rep = await _rep()
    pending = {"_id": ObjectId(), "token": "hosttok5", "rep_user_id": str(rep["_id"]), "contact_id": None, "customer_phone": "+15005550077", "rep_twilio_number": "+15005550001",
               "rep_name": "Tester", "call_sid": "CA_qa_host_5", "created_at": datetime.now(timezone.utc), "qa_host": True}
    await db.pending_calls.insert_one(pending)
    up, closed = FakeUpstream(), {"v": False}

    async def send(m):
        pass

    async def close():
        closed["v"] = True
    try:
        bridge = lh.HostBridge(db, pending, "call", send, close, connect=lambda: _ret(up))
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZ5", "callSid": "CA_qa_host_5"}})
        await up.q.put({"type": "session.started", "session": {"id": "sess_5"}})
        assert await _wait(lambda: bridge.ready)
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Hey Tester, calling the number ending in 0077.", "start_ms": 0, "end_ms": 3000})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "[unintelligible]", "start_ms": 4000, "end_ms": 4400})
        await up.q.put({"type": "session.output_audio.delta", "delta": "AAAA"})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Got it. Connecting you now!", "start_ms": 5000, "end_ms": 6000})
        # her line is only flushed when the next turn starts or on delegation; the model delegates right after speaking it
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "d5", "target": "client"}})
        assert await _wait(lambda: bridge.decision == "go"), "Jessi's own 'Connecting you now' decides go"
        assert await _wait(lambda: bridge.handed_off, timeout=8)
        assert moved == [("CA_qa_host_5", lh.after_url("call", pending))]

        async def _row():
            return await db.pending_calls.find_one({"_id": pending["_id"]})
        for _ in range(40):
            row = await _row()
            if (row["host"] or {}).get("handoff"):
                break
            await asyncio.sleep(0.05)
        assert row["host"]["decision"] == "go" and row["host"]["via"] == "jessi" and row["host"]["handoff"] == "rest"
        assert not closed["v"] and not bridge.closed, "after a successful redirect we wait for Twilio to stop the stream"
        # Twilio moved the call to host-after and tore the stream down
        await bridge.on_twilio({"event": "stop"})
        assert bridge.closed and bridge.reason == "twilio_stop" and closed["v"]
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge-host-after", params={"pid": str(pending["_id"]), "t": "hosttok5"}, data={"CallSid": "CA_qa_host_5"})
        assert "<Dial" in r.text and "<Number>+15005550077</Number>" in r.text
        # no delegation at all: the watchdog hands off DECIDED_CLOSE_S after the decision
        monkeypatch.setattr(lh, "DECIDED_CLOSE_S", 0.6)
        pending2 = {**pending, "_id": ObjectId(), "token": "hosttok6", "call_sid": "CA_qa_host_6"}
        await db.pending_calls.insert_one(pending2)
        up2, closed2 = FakeUpstream(), {"v": False}

        async def close2():
            closed2["v"] = True
        b2 = lh.HostBridge(db, pending2, "call", send, close2, connect=lambda: _ret(up2))
        await b2.on_twilio({"event": "start", "start": {"streamSid": "MZ6", "callSid": "CA_qa_host_6"}})
        await up2.q.put({"type": "session.started", "session": {"id": "sess_6"}})
        assert await _wait(lambda: b2.ready)
        await b2.on_twilio({"event": "dtmf", "dtmf": {"digit": "1"}})
        assert b2.decision == "go"
        assert await _wait(lambda: b2.handed_off, timeout=5), "pressed 1, Jessi never delegated -> handoff anyway"
        assert moved[-1][0] == "CA_qa_host_6"
    finally:
        await db.pending_calls.delete_many({"qa_host": True})


async def test_click_to_call_question_then_silence(monkeypatch):
    """Rep asks a question -> Jessi delegates -> backend whispers an answer; then nobody talks -> nudge -> 'none' by silence -> host-after cancels, customer NOT dialed."""
    db = get_db()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    monkeypatch.setattr(lh, "NUDGE_S", 0.6)
    monkeypatch.setattr(lh, "MAX_QUIET_S", 1.6)

    async def fake_answer(db_, brief, q):
        return f"Backend says: he asked about {q}"
    monkeypatch.setattr(lh, "answer_question", fake_answer)
    rep = await _rep()
    seeded = await _seed_customer(str(rep["_id"]))
    pending = {"_id": ObjectId(), "token": "hosttok2", "rep_user_id": str(rep["_id"]), "contact_id": seeded["cid"], "customer_phone": "+15005550077", "rep_twilio_number": "+15005550001",
               "rep_name": "Tester", "call_sid": "CA_qa_host_2", "created_at": datetime.now(timezone.utc), "qa_host": True}
    await db.pending_calls.insert_one(pending)
    up, closed = FakeUpstream(), {"v": False}

    async def send(m):
        pass

    async def close():
        closed["v"] = True
    try:
        bridge = lh.HostBridge(db, pending, "call", send, close, connect=lambda: _ret(up))
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZ2", "callSid": "CA_qa_host_2"}})
        await up.q.put({"type": "session.started", "session": {"id": "sess_2"}})
        assert await _wait(lambda: bridge.ready)
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Hey Tester, calling Bud.", "start_ms": 0, "end_ms": 2000})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "What did he text me?", "start_ms": 3000, "end_ms": 4000})
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "dq", "target": "client"}})
        assert await _wait(lambda: any(e.get("type") == "session.thinking.append" and "Backend says" in str(e.get("content")) for e in up.sent)), up.texts()
        assert bridge.decision is None
        await up.q.put({"type": "session.output_audio.delta", "delta": "AAAA"})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "He asked about the payment. Ready to connect?", "start_ms": 5000, "end_ms": 7000})
        assert await _wait(lambda: any(e.get("event_id") == "nudge_1" for e in up.sent), timeout=5), "quiet rep -> one nudge"
        assert await _wait(lambda: closed["v"], timeout=6), "still quiet -> closed"
        await asyncio.wait_for(bridge.done.wait(), 5)
        row = await db.pending_calls.find_one({"_id": pending["_id"]})
        assert row["host"]["decision"] == "none" and row["host"]["via"] == "silence"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge-host-after", params={"pid": str(pending["_id"]), "t": "hosttok2"}, data={})
        assert "<Dial" not in r.text and "Call cancelled" in r.text and "<Hangup/>" in r.text
        # DTMF 2 on a fresh bridge = not now
        pending2 = {**pending, "_id": ObjectId(), "token": "hosttok3", "call_sid": "CA_qa_host_3"}
        await db.pending_calls.insert_one(pending2)
        up2, closed2 = FakeUpstream(), {"v": False}

        async def close2():
            closed2["v"] = True
        b2 = lh.HostBridge(db, pending2, "call", send, close2, connect=lambda: _ret(up2))
        await b2.on_twilio({"event": "start", "start": {"streamSid": "MZ3", "callSid": "CA_qa_host_3"}})
        await up2.q.put({"type": "session.started", "session": {"id": "sess_3"}})
        assert await _wait(lambda: b2.ready)
        await b2.on_twilio({"event": "dtmf", "dtmf": {"digit": "2"}})
        assert b2.decision == "later" and any(e.get("event_id") == "dtmf_later" and lh.CANCEL_LINE in e["content"] for e in up2.sent)
        await up2.q.put({"type": "session.delegation.created", "delegation": {"id": "d2", "target": "client"}})
        assert await _wait(lambda: closed2["v"], timeout=10)
        await asyncio.wait_for(b2.done.wait(), 5)
        row = await db.pending_calls.find_one({"_id": pending2["_id"]})
        assert row["host"]["decision"] == "later" and row["host"]["via"] == "dtmf"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge-host-after", params={"pid": str(pending2["_id"]), "t": "hosttok3"}, data={})
        assert r.text.strip().endswith("<Hangup/></Response>") and "<Dial" not in r.text
    finally:
        await _wipe_customer(seeded["cid"])


async def test_host_after_falls_back_when_jessi_never_spoke():
    """GPT-Live unreachable (decision none via upstream_failed) -> the spoken press-1 gate, so the call still works."""
    db = get_db()
    rep = await _rep()
    pending = {"_id": ObjectId(), "token": "hosttok4", "rep_user_id": str(rep["_id"]), "contact_id": None, "customer_phone": "+15005550077", "rep_twilio_number": "+15005550001",
               "rep_name": "Tester", "call_sid": "CA_qa_host_4", "created_at": datetime.now(timezone.utc), "qa_host": True, "host": {"transport": "gpt-live", "decision": "none", "via": "upstream_failed"}}
    await db.pending_calls.insert_one(pending)
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge-host-after", params={"pid": str(pending["_id"]), "t": "hosttok4"}, data={"StreamError": "x"})
        assert "<Gather" in r.text and "call-bridge-connect" in r.text and "Press 1" in r.text and "<Dial" not in r.text
        row = await db.pending_calls.find_one({"_id": pending["_id"]})
        assert row["host"]["transport"] == "say" and "never got on the line" in row["host"]["skip_reason"]
        # no key on the preview server: /call-bridge itself answers with the spoken gate and stamps why
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/call-bridge", data={"CallSid": "CA_qa_host_4"})
        assert "<Gather" in r.text and "Calling the customer" in r.text
        row = await db.pending_calls.find_one({"_id": pending["_id"]})
        assert row["host"]["transport"] == "say" and row["host"]["skip_reason"] == ls.NO_KEY
    finally:
        await db.pending_calls.delete_many({"qa_host": True})


async def test_shop_announcement_hosted(monkeypatch):
    """Mystery shop: Jessi announces on GPT-Live, keeps the shopper secret, rep says ready -> host-after rings the shopper in with no second heads-up; press 2 -> parked."""
    db = get_db()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    s = _shop(direction="inbound")
    await db.roleplay_sessions.insert_one(s)
    up, closed = FakeUpstream(), {"v": False}

    async def send(m):
        pass

    async def close():
        closed["v"] = True
    try:
        b = lh.shop_brief(s)
        assert b["rep_first"] == "Sam" and "practice call" in b["opener"] and b["go_line"] == "Here it comes." and "try another time" in b["later_line"]
        ins = lh.instructions("shop", b, {})
        assert "Never reveal who the customer will be" in ins and "Casey" not in ins and "Wrangler" not in ins
        bridge = lh.HostBridge(db, s, "shop", send, close, connect=lambda: _ret(up))
        assert bridge.COLL == "roleplay_sessions" and bridge.TURNS_FIELD == "host.turns"
        await bridge.on_twilio({"event": "start", "start": {"streamSid": "MZ9", "callSid": "CA_qa_shop_host"}})
        row = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert row["status"] == "dialing", "the host never changes the shop status"
        assert row["host"]["transport"] == "gpt-live" and row["host"]["voice"]
        host_voice = row["host"]["voice"]
        assert ls.voice_for(row) != host_voice, "the shopper never reuses Jessi's voice"
        await up.q.put({"type": "session.started", "session": {"id": "sess_s"}})
        assert await _wait(lambda: bridge.ready)
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Hi Sam, this is your practice call.", "start_ms": 0, "end_ms": 3000})
        await up.q.put({"type": "session.input_transcript.delta", "delta": "Ready.", "start_ms": 4000, "end_ms": 4500})
        await up.q.put({"type": "session.output_transcript.delta", "delta": "Here it comes.", "start_ms": 5000, "end_ms": 5600})
        assert await _wait(lambda: bridge.decision == "go")
        await up.q.put({"type": "session.delegation.created", "delegation": {"id": "ds", "target": "client"}})
        assert await _wait(lambda: closed["v"], timeout=10)
        await asyncio.wait_for(bridge.done.wait(), 5)
        row = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert row["host"]["decision"] == "go" and row["status"] == "dialing" and row.get("turns") == [], "host turns never land in the graded transcript"
        assert [t["role"] for t in row["host"]["turns"]] == ["jessi", "rep", "jessi"]
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/scripts/roleplay/host-after/{s['_id']}", params={"t": s["token"]}, data={"CallSid": "CA_qa_shop_host"})
        assert r.status_code == 200 and "ring.wav" in r.text and "Here it comes" not in r.text, r.text
        row = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert row["gate_via"] == "host:speech" and row.get("gate_passed_at")
        assert row["live_transport"] == "relay" and row["live_skip_reason"] == ls.NO_KEY, "no key on the preview server -> relay shopper"
        from services import mystery_shops as ms
        assert ms.serialize_call(row)["host"]["decision"] == "go"
        # press 2 on another shop -> parked, bare hangup (Jessi already said the line)
        s2 = _shop(direction="outbound")
        await db.roleplay_sessions.insert_one(s2)
        up2, closed2 = FakeUpstream(), {"v": False}

        async def close2():
            closed2["v"] = True
        b2 = lh.HostBridge(db, s2, "shop", send, close2, connect=lambda: _ret(up2))
        await b2.on_twilio({"event": "start", "start": {"streamSid": "MZ10", "callSid": "CA_qa_shop_host2"}})
        await up2.q.put({"type": "session.started", "session": {"id": "sess_s2"}})
        assert await _wait(lambda: b2.ready)
        await b2.on_twilio({"event": "dtmf", "dtmf": {"digit": "2"}})
        await up2.q.put({"type": "session.delegation.created", "delegation": {"id": "ds2", "target": "client"}})
        assert await _wait(lambda: closed2["v"], timeout=10)
        await asyncio.wait_for(b2.done.wait(), 5)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/scripts/roleplay/host-after/{s2['_id']}", params={"t": s2["token"]}, data={})
        assert r.text.strip().endswith("<Hangup/></Response>") and "<Say" not in r.text
        row2 = await db.roleplay_sessions.find_one({"_id": s2["_id"]})
        assert row2["status"] == "unreachable" and row2["outcome"] == "postponed"
        # Jessi never got on (no decision) -> classic spoken announcement
        s3 = _shop()
        await db.roleplay_sessions.insert_one(s3)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/scripts/roleplay/host-after/{s3['_id']}", params={"t": s3["token"]}, data={"StreamError": "boom"})
        assert "<Gather" in r.text and "practice call from I'm On Social" in r.text
        row3 = await db.roleplay_sessions.find_one({"_id": s3["_id"]})
        assert row3["host"]["transport"] == "say" and "boom" in row3["host"]["skip_reason"]
        # /twiml on the preview server (no key) -> classic announcement, reason stamped
        s4 = _shop()
        await db.roleplay_sessions.insert_one(s4)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/scripts/roleplay/twiml/{s4['_id']}", params={"t": s4["token"]}, data={})
        assert "<Gather" in r.text and "<Stream" not in r.text
        row4 = await db.roleplay_sessions.find_one({"_id": s4["_id"]})
        assert row4["host"] == {"transport": "say", "skip_reason": ls.NO_KEY}
    finally:
        await db.roleplay_sessions.delete_many({"rep_name": "Sam Seller", "store_name": "QA Jeep", "kind": "mystery_shop", "manual": True, "persona.name": "Casey Morgan"})
