"""Iteration 337: 'Jessi hosts your calls' preview-only fallback tests.

Preview has NO OPENAI_API_KEY, so every host gate must degrade to the classic
<Say>/<Gather> path (never 5xx). We insert throwaway pending_calls and
roleplay_sessions docs directly in Mongo (tagged qa_test: true / rep_name QA Host)
and clean them up at the end. We NEVER place a real call.
"""
import os
import asyncio
import httpx
import pytest
import pytest_asyncio
from bson import ObjectId
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import lab, live_shops as ls, live_host as lh, mystery_shops as ms  # noqa: E402

pytestmark = pytest.mark.asyncio

BACKEND = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
if not BACKEND.startswith("http"):
    BACKEND = "http://localhost:8001"
API = f"{BACKEND}/api"
LOCAL_API = "http://localhost:8001/api"  # webhook posts are internal

SUPER_EMAIL = "forest@imosapp.com"
SUPER_PASS = "Admin123!"
REP_EMAIL = "activation-tester@invalid.imonsocial.test"


async def _login(email: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    assert tok, f"no token in login response: {list(j.keys())}"
    return tok


@pytest_asyncio.fixture(scope="module")
async def super_token():
    return await _login(SUPER_EMAIL, SUPER_PASS)


@pytest_asyncio.fixture(scope="module")
async def rep_user():
    db = get_db()
    u = await db.users.find_one({"email": REP_EMAIL}, {"_id": 1, "twilio_number": 1})
    assert u, "activation tester missing"
    return u


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _cleanup():
    yield
    db = get_db()
    await db.pending_calls.delete_many({"qa_test": True})
    await db.roleplay_sessions.delete_many({"rep_name": "QA Host"})


# ── 1. Test Lab feature registration ─────────────────────────────────────────
async def test_lab_features_lists_live_host(super_token):
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API}/lab/features", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200, r.text
    features = r.json().get("features") or []
    live_host_feat = next((f for f in features if f["key"] == "live_host"), None)
    assert live_host_feat, f"live_host missing from features: {[f['key'] for f in features]}"
    assert live_host_feat.get("status") == "live", f"default status should be live, got {live_host_feat.get('status')}"
    needs = live_host_feat.get("needs") or ""
    assert "OPENAI_API_KEY" in needs, f"needs should mention OPENAI_API_KEY, got {needs!r}"


async def test_lab_features_toggle_live_host(super_token):
    hdr = {"Authorization": f"Bearer {super_token}"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.put(f"{API}/lab/features/live_host", headers=hdr, json={"status": "lab"})
        assert r.status_code == 200, r.text
        # flip back to live (must be left live per instructions)
        r2 = await c.put(f"{API}/lab/features/live_host", headers=hdr, json={"status": "live"})
        assert r2.status_code == 200, r2.text
        # confirm
        r3 = await c.get(f"{API}/lab/features", headers=hdr)
    feat = next(f for f in r3.json()["features"] if f["key"] == "live_host")
    assert feat["status"] == "live"


# ── 2. /call-bridge falls back to classic <Gather> in preview (no key) ───────
async def test_call_bridge_falls_back_to_classic_gate(rep_user):
    db = get_db()
    pid = ObjectId()
    call_sid = f"CA_qa_iter337_{pid}"
    pending = {
        "_id": pid,
        "call_sid": call_sid,
        "customer_phone": "+15005550077",
        "rep_twilio_number": "+15005550001",
        "rep_user_id": str(rep_user["_id"]),
        "contact_id": None,
        "token": "qa1",
        "qa_test": True,
        "created_at": datetime.now(timezone.utc),
    }
    await db.pending_calls.insert_one(pending)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/webhooks/twilio/call-bridge", data={"CallSid": call_sid})
    assert r.status_code == 200, r.text
    body = r.text
    assert "<Gather" in body and "Press 1" in body, body
    assert "call-bridge-connect" in body
    assert "<Dial" not in body
    row = await db.pending_calls.find_one({"_id": pid})
    host = row.get("host") or {}
    assert host.get("transport") == "say", host
    assert host.get("skip_reason"), host
    # The skip_reason should be the no-key reason
    assert host["skip_reason"] == ls.NO_KEY, host["skip_reason"]


# ── 3. /call-bridge-host-after: all decision branches ────────────────────────
@pytest.mark.parametrize("decision,via,expect_dial,expect_hangup,expect_say,expect_gather", [
    ("go", "speech", True, False, False, False),
    ("later", "dtmf", False, True, False, False),
    ("none", "silence", False, True, True, False),
    ("none", "timeout", False, True, True, False),
])
async def test_call_bridge_host_after_decisions(rep_user, decision, via, expect_dial, expect_hangup, expect_say, expect_gather):
    db = get_db()
    pid = ObjectId()
    pending = {
        "_id": pid, "call_sid": f"CA_qa_ha_{pid}", "customer_phone": "+15005550077",
        "rep_twilio_number": "+15005550001", "rep_user_id": str(rep_user["_id"]),
        "contact_id": None, "token": "hatok", "qa_test": True,
        "host": {"decision": decision, "via": via},
        "created_at": datetime.now(timezone.utc),
    }
    await db.pending_calls.insert_one(pending)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/webhooks/twilio/call-bridge-host-after",
                         params={"pid": str(pid), "t": "hatok"}, data={})
    assert r.status_code == 200, r.text
    body = r.text
    if expect_dial:
        assert "<Dial" in body and "<Number>+15005550077</Number>" in body
        assert 'callerId="+15005550001"' in body
        assert "<Say>" not in body, f"go should have NO <Say>: {body}"
    else:
        assert "<Dial" not in body, body
    if expect_hangup:
        assert "<Hangup" in body, body
    if expect_say:
        assert "<Say>" in body and "No input received" in body, body
    if expect_gather:
        assert "<Gather" in body, body


async def test_call_bridge_host_after_missing_decision_falls_back(rep_user):
    """host missing / decision None → classic <Gather> + stamps host.transport 'say' + skip_reason 'never got on the line'"""
    db = get_db()
    pid = ObjectId()
    pending = {
        "_id": pid, "call_sid": f"CA_qa_none_{pid}", "customer_phone": "+15005550077",
        "rep_twilio_number": "+15005550001", "rep_user_id": str(rep_user["_id"]),
        "contact_id": None, "token": "notok", "qa_test": True,
        "created_at": datetime.now(timezone.utc),
        # no host key
    }
    await db.pending_calls.insert_one(pending)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/webhooks/twilio/call-bridge-host-after",
                         params={"pid": str(pid), "t": "notok"}, data={})
    assert r.status_code == 200, r.text
    body = r.text
    assert "<Gather" in body and "call-bridge-connect" in body, body
    assert "<Dial" not in body
    row = await db.pending_calls.find_one({"_id": pid})
    h = row["host"]
    assert h.get("transport") == "say"
    assert "never got on the line" in (h.get("skip_reason") or ""), h


async def test_call_bridge_host_after_wrong_token_and_unknown_pid(rep_user):
    db = get_db()
    pid = ObjectId()
    pending = {
        "_id": pid, "call_sid": f"CA_qa_wt_{pid}", "customer_phone": "+15005550077",
        "rep_twilio_number": "+15005550001", "rep_user_id": str(rep_user["_id"]),
        "contact_id": None, "token": "realtok", "qa_test": True,
        "host": {"decision": "go", "via": "speech"},
        "created_at": datetime.now(timezone.utc),
    }
    await db.pending_calls.insert_one(pending)
    async with httpx.AsyncClient(timeout=20) as c:
        # wrong token
        r1 = await c.post(f"{LOCAL_API}/webhooks/twilio/call-bridge-host-after",
                          params={"pid": str(pid), "t": "WRONG"}, data={})
        # unknown pid
        r2 = await c.post(f"{LOCAL_API}/webhooks/twilio/call-bridge-host-after",
                          params={"pid": str(ObjectId()), "t": "anything"}, data={})
    for r in (r1, r2):
        assert r.status_code == 200, r.text
        assert "<Say>" in r.text and "<Hangup" in r.text, r.text
        assert "<Dial" not in r.text, r.text


# ── 4. Mystery shop /twiml classic <Gather>, English + Dutch skip reasons ────
async def _insert_shop(locale="en-US", **extra):
    db = get_db()
    s = {
        "_id": ObjectId(),
        "token": "shoptok" + str(ObjectId())[-6:],
        "mode": "phone",
        "kind": "mystery_shop",
        "status": "dialing",
        "direction": "inbound",
        "locale": locale,
        "client_id": str(ObjectId()),
        "script_id": str(ObjectId()),
        "rep_name": "QA Host",
        "store_name": "QA",
        "department": "sales",
        "manual": True,
        "persona": {"name": "Casey Morgan", "voice": "female", "opening_line": "Hi"},
        "turns": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        **extra,
    }
    await db.roleplay_sessions.insert_one(s)
    return s


async def test_roleplay_twiml_english_shop_classic_gather():
    s = await _insert_shop(locale="en-US")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/twiml/{s['_id']}", params={"t": s["token"]}, data={})
    assert r.status_code == 200, r.text
    body = r.text
    assert "<Gather" in body, body
    assert "<Stream" not in body, "no key -> no GPT-Live stream"
    row = await get_db().roleplay_sessions.find_one({"_id": s["_id"]})
    host = row.get("host") or {}
    assert host.get("transport") == "say"
    assert host.get("skip_reason") == ls.NO_KEY, host


async def test_roleplay_twiml_dutch_shop_skip_reason_mentions_dutch():
    s = await _insert_shop(locale="nl-NL")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/twiml/{s['_id']}", params={"t": s["token"]}, data={})
    assert r.status_code == 200, r.text
    assert "<Stream" not in r.text
    row = await get_db().roleplay_sessions.find_one({"_id": s["_id"]})
    host = row.get("host") or {}
    assert host.get("transport") == "say"
    assert "Dutch" in (host.get("skip_reason") or ""), host


async def test_roleplay_twiml_practice_session_unaffected():
    """Practice (kind != mystery_shop) never goes through the host branch."""
    db = get_db()
    s = {
        "_id": ObjectId(), "token": "practok" + str(ObjectId())[-6:],
        "mode": "phone", "kind": "practice", "status": "dialing", "locale": "en-US",
        "client_id": str(ObjectId()), "script_id": str(ObjectId()),
        "rep_name": "QA Host", "store_name": "QA", "department": "sales", "manual": True,
        "persona": {"name": "Casey", "voice": "female", "opening_line": "Hi"},
        "turns": [],
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    }
    await db.roleplay_sessions.insert_one(s)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/twiml/{s['_id']}", params={"t": s["token"]}, data={})
    assert r.status_code == 200
    row = await db.roleplay_sessions.find_one({"_id": s["_id"]})
    # Practice never stamps host.transport
    assert (row.get("host") or {}).get("transport") is None, row.get("host")


# ── 5. /host-after for shops ─────────────────────────────────────────────────
async def test_shop_host_after_go_rings_shopper_no_here_it_comes():
    s = await _insert_shop(locale="en-US", host={"decision": "go", "via": "speech"})
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/host-after/{s['_id']}",
                         params={"t": s["token"]}, data={})
    assert r.status_code == 200, r.text
    body = r.text
    assert "ring.wav" in body, body
    assert "Here it comes" not in body, "Jessi already said it — no duplicate heads-up"
    row = await get_db().roleplay_sessions.find_one({"_id": s["_id"]})
    assert row.get("gate_via") == "host:speech"
    assert row.get("gate_passed_at") is not None


async def test_shop_host_after_later_manual_hangup_and_postpones():
    s = await _insert_shop(locale="en-US", host={"decision": "later", "via": "dtmf"})
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/host-after/{s['_id']}",
                         params={"t": s["token"]}, data={})
    assert r.status_code == 200, r.text
    body = r.text.strip()
    assert body.endswith("<Hangup/></Response>"), body
    assert "<Say" not in body, "manual shop 'later' via host = bare hangup"
    row = await get_db().roleplay_sessions.find_one({"_id": s["_id"]})
    assert row.get("status") == "unreachable"
    assert row.get("outcome") == "postponed"


async def test_shop_host_after_no_decision_falls_back_to_classic():
    s = await _insert_shop(locale="en-US")  # no host key
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/host-after/{s['_id']}",
                         params={"t": s["token"]}, data={"StreamError": "boom"})
    assert r.status_code == 200, r.text
    assert "<Gather" in r.text, r.text
    row = await get_db().roleplay_sessions.find_one({"_id": s["_id"]})
    h = row.get("host") or {}
    assert h.get("transport") == "say"
    assert "boom" in (h.get("skip_reason") or "") or "never got on the line" in (h.get("skip_reason") or ""), h


async def test_shop_host_after_wrong_token_returns_404():
    s = await _insert_shop(locale="en-US", host={"decision": "go", "via": "speech"})
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{LOCAL_API}/scripts/roleplay/host-after/{s['_id']}",
                         params={"t": "WRONG"}, data={})
    assert r.status_code == 404, r.text


# ── 6. serialize_call surfaces host object ───────────────────────────────────
async def test_serialize_call_host_object():
    doc_with_host = {
        "_id": ObjectId(), "status": "graded", "kind": "mystery_shop",
        "host": {"transport": "gpt-live", "decision": "go", "via": "speech",
                 "skip_reason": None, "seconds": 23, "voice": "gleam"},
    }
    out = ms.serialize_call(doc_with_host)
    assert "host" in out, out
    assert out["host"] is not None
    assert out["host"]["decision"] == "go"
    assert out["host"]["transport"] == "gpt-live"
    assert out["host"]["seconds"] == 23
    # doc without host
    doc_no_host = {"_id": ObjectId(), "status": "graded", "kind": "mystery_shop"}
    out2 = ms.serialize_call(doc_no_host)
    assert out2.get("host") is None
