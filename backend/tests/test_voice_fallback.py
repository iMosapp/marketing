"""Phase 3: automatic voice model fallback (GPT-Live premium -> Realtime Mini backup), live preview API + Mongo, zero OpenAI spend
(fake provider). Creates and wipes "QA Voice Fallback Org" + qa-voice-fb-* users; flips Test Lab jessi_live_voice live for the run and restores it.
Covers: handoff with context + reservation accounting + audit trail, server-side resume of a still-open premium session, backup exhausted ->
text offer, bypass attempts (reconnect / second device / engine request / foreign session), kill switch, account-wide hard $ cap across users."""
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.auth import hash_password  # noqa: E402
from routers.database import get_db  # noqa: E402
from services import live_voice as lv  # noqa: E402
from services import voice_controls as vc  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
FOREST = {"email": "forest@imosapp.com", "password": "Admin123!"}
PW = "VoiceRep123!"
REPS = {"a": "qa-voice-fb-a@invalid.imonsocial.test", "b": "qa-voice-fb-b@invalid.imonsocial.test", "c": "qa-voice-fb-c@invalid.imonsocial.test", "d": "qa-voice-fb-d@invalid.imonsocial.test"}
pytestmark = pytest.mark.asyncio
S = {}


def _token(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def api(method, path, tok=None, **kw):
    r = requests.request(method, f"{BASE}/api{path}", headers={"Authorization": f"Bearer {tok}"} if tok else {}, timeout=40, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def start(tok, device="dev-1", resume_from=None, reason=None, overrides=None):
    return api("POST", "/live-voice/session", tok, json={"mode": "assistant", "sdp": "v=0 offer", "overrides": {"fake_provider": True, **(overrides or {})}, "device_id": device, "resume_from": resume_from, "reason": reason})


def events(tok, live_id, evs):
    return api("POST", f"/live-voice/{live_id}/events", tok, json={"events": evs})


def backdate(live_id, seconds):
    S["mongo"].live_sessions.update_one({"live_id": live_id}, {"$set": {"started_at": datetime.now(timezone.utc) - timedelta(seconds=seconds - 0.5)}})


def res_doc(uid):
    return S["mongo"][vc.RES_COLL].find_one({"_id": f"{S['org']}:{uid}:{S['day']}"}) or {}


def seg_of(live_id):
    return S["mongo"][vc.LEDGER_COLL].find_one({"live_id": live_id, "kind": "segment"})


def live_of(live_id):
    return S["mongo"].live_sessions.find_one({"live_id": live_id})


def override(uid, body):
    st, b = api("PUT", f"/voice-controls/accounts/{S['org']}/users/{uid}", S["forest"], json=body)
    assert st == 200, b


@pytest.fixture(scope="module", autouse=True)
def qa():
    m = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    S["mongo"] = m
    forest = _token(FOREST)
    S["forest"] = forest
    st, feats = api("GET", "/lab/features", forest)
    prev = next((f.get("status") for f in feats["features"] if f.get("key") == "jessi_live_voice"), "lab")
    api("PUT", "/lab/features/jessi_live_voice", forest, json={"status": "live"})
    org = m.organizations.insert_one({"name": "QA Voice Fallback Org", "timezone": "America/Denver", "qa_voice": True, "active": True, "created_at": datetime.now(timezone.utc)}).inserted_id
    S["org"] = str(org)
    now = datetime.now(timezone.utc)
    uids = {}
    for key, email in REPS.items():
        uid = m.users.insert_one({"name": f"Fallback Rep {key.upper()}", "email": email, "password": hash_password(PW), "role": "user", "organization_id": str(org), "store_id": None,
                                  "phone": f"+1500555091{ord(key) - 96}", "is_active": True, "status": "active", "onboarding_complete": True, "phone_verified": True, "timezone": "America/Denver",
                                  "qa_voice": True, "created_at": now, "updated_at": now}).inserted_id
        uids[key] = str(uid)
    S["uid"] = uids
    S["tok"] = {k: _token({"email": e, "password": PW}) for k, e in REPS.items()}
    S["day"] = datetime.now(ZoneInfo("America/Denver")).strftime("%Y-%m-%d")
    st, body = api("PUT", f"/voice-controls/accounts/{S['org']}", forest, json={"enabled": True, "per_user_daily_premium_min": 15, "per_user_daily_backup_min": 60, "timezone": "America/Denver"})
    assert st == 200 and body["policy"]["enabled"] is True
    yield S
    api("PUT", "/lab/features/jessi_live_voice", forest, json={"status": prev})
    ids = list(uids.values())
    m.live_sessions.delete_many({"user_id": {"$in": ids}})
    for coll in (vc.LEDGER_COLL, vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL, vc.POLICY_COLL, vc.OVERRIDE_COLL):
        m[coll].delete_many({"org_id": S["org"]})
    m[vc.LEDGER_COLL].delete_many({"user_id": {"$in": ids}})
    m.users.delete_many({"_id": {"$in": [ObjectId(x) for x in ids]}})
    m.organizations.delete_one({"_id": org})


# ── 1. the handoff: premium pool spent -> stop -> backup session seeded with the conversation ───────────────────────────────
async def test_premium_to_backup_handoff_with_context_and_trail():
    tok, uid, forest = S["tok"]["a"], S["uid"]["a"], S["forest"]
    override(uid, {"daily_premium_min": 1})
    st, s1 = start(tok, "phone-a")
    assert st == 200 and s1["engine"] == "live" and s1["meter"]["role"] == "premium" and s1["resumed_from"] is None and "Fallback" in s1["greeting"]
    # the conversation so far + a pending yes/no the brain is waiting on (what the handoff must carry)
    st, ev = events(tok, s1["live_id"], [{"type": "transcript", "role": "assistant", "text": "Hey Fallback, it's Jessi. Who are we talking about today?"},
                                         {"type": "transcript", "role": "rep", "text": "Text Mike Tester and tell him his part came in."},
                                         {"type": "transcript", "role": "assistant", "text": "Here is the text for Mike: Hey Mike, your part came in, swing by when you can. Send it?"},
                                         {"type": "usage", "seconds": 20}])
    assert st == 200 and ev["stop"] is None
    pending = {"type": "send_text", "contact_id": "6aa413008f0d53e3f2261854", "name": "Mike Tester", "content": "Hey Mike, your part came in, swing by when you can.", "at": datetime.now(timezone.utc).isoformat()}
    S["mongo"].live_sessions.update_one({"live_id": s1["live_id"]}, {"$set": {"pending": pending, "last_choices": ["6aa413008f0d53e3f2261854"], "last_pick": "6aa413008f0d53e3f2261854"}})
    # 70 s in: the server says stop, continue on mini
    backdate(s1["live_id"], 70)
    st, ev = events(tok, s1["live_id"], [{"type": "usage", "seconds": 70}])
    assert ev["stop"] == "premium_cap" and ev["fallback_engine"] == "mini", ev
    # the app: final close for the old session FIRST, then the resume (reservation released before the next one is taken)
    st, ev = events(tok, s1["live_id"], [{"type": "closed", "reason": "premium_cap", "seconds": 70}])
    assert ev["status"] == "closed"
    r = res_doc(uid)
    assert r["premium_used_s"] == 70 and r["premium_reserved_s"] == 0 and int(r.get("backup_reserved_s") or 0) == 0
    st, s2 = start(tok, "phone-a", resume_from=s1["live_id"], reason="premium_cap")
    assert st == 200, s2
    assert s2["engine"] == "mini" and s2["model"] == "gpt-realtime-2.1-mini" and s2["resumed_from"] == s1["live_id"] and s2["meter"]["role"] == "backup" and s2["meter"]["fallback_reason"] == "premium_cap"
    assert s2["greeting"] == "" and "still here" in s2["greet_instruction"] and "No greeting" in s2["greet_instruction"] and "pending yes or no" in s2["greet_instruction"]
    assert s2["cap_left_s"] == 3600 and s2["contact_name"] is None
    r = res_doc(uid)
    assert r["premium_reserved_s"] == 0 and r["backup_reserved_s"] == 60 and r["premium_used_s"] == 70, "no overlapping reservation across the switch"
    # continuity on the new session record and in the context handed to the engine
    new = live_of(s2["live_id"])
    old = live_of(s1["live_id"])
    assert new["resumed_from"] == s1["live_id"] and new["handoff_reason"] == "premium_cap" and new["meter"]["segment_no"] == 2 and new["meter"]["reconnect_of"] == s1["live_id"]
    assert new["pending"] == pending and new["last_pick"] == "6aa413008f0d53e3f2261854" and new["transcript"] == []
    assert old["handoff_to"] == s2["live_id"] and old["status"] == "closed" and old["close_reason"] == "premium_cap"
    ctx = new["handoff_context"]
    assert "THE VOICE LINE WAS JUST SWITCHED" in ctx and "Rep: Text Mike Tester" in ctx and "Jessi: Here is the text for Mike" in ctx and "PENDING: you read back 'Hey Mike, your part came in" in ctx and "Do not greet again" in ctx
    seg1, seg2 = seg_of(s1["live_id"]), seg_of(s2["live_id"])
    assert seg1["status"] == "closed" and seg1["stop_reason"] == "premium_cap" and seg1["billable_s"] == 70 and seg1["segment_no"] == 1 and seg1["role"] == "premium"
    assert seg2["status"] == "open" and seg2["reconnect_of"] == s1["live_id"] and seg2["segment_no"] == 2 and seg2["role"] == "backup" and seg2["fallback_reason"] == "premium_cap" and seg2["reserved_s"] == 60
    # the conversation on mini keeps metering and ends normally
    backdate(s2["live_id"], 30)
    st, ev = events(tok, s2["live_id"], [{"type": "transcript", "role": "assistant", "text": "Okay, still here. Want me to send that text to Mike?"}, {"type": "transcript", "role": "rep", "text": "Yes, send it."},
                                         {"type": "usage", "seconds": 30, "tokens": {"audio_in": 3000, "audio_in_cached": 0, "text_in": 500, "text_in_cached": 0, "audio_out": 4000, "text_out": 100}}])
    assert ev["stop"] is None and ev["left_s"] == 30 + 3540
    st, ev = events(tok, s2["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 30, "tokens": {"audio_in": 3000, "audio_in_cached": 0, "text_in": 500, "text_in_cached": 0, "audio_out": 4000, "text_out": 100}}])
    assert ev["status"] == "closed"
    r = res_doc(uid)
    assert r["backup_used_s"] == 30 and r["backup_reserved_s"] == 0
    # audit trail: both segments, which engine for how long, est. cost, basis, one handoff
    st, trail = api("GET", f"/live-voice/{s2['live_id']}/trail", tok)
    assert st == 200 and trail["conversation_id"] == s1["live_id"] and [x["live_id"] for x in trail["segments"]] == [s1["live_id"], s2["live_id"]]
    t = trail["totals"]
    mini_cost = round((3000 * 10 + 500 * 0.6 + 4000 * 20 + 100 * 2.4) / 1_000_000, 4)
    assert t["segments"] == 2 and t["premium_s"] == 70 and t["backup_s"] == 30 and t["total_s"] == 100 and t["handoffs"] == 1 and t["engines"] == ["live", "mini"] and t["open"] is False
    assert t["est_cost_usd"] == round(vc.live_cost(70) + mini_cost, 4) and set(t["cost_basis"]) == {"server_clock", "client_report"} and t["unconfirmed"] is False
    assert trail["segments"][0]["engine"] == "live" and trail["segments"][0]["billable_s"] == 70 and trail["segments"][1]["engine"] == "mini" and trail["segments"][1]["est_cost_usd"] == mini_cost
    st, same = api("GET", f"/live-voice/{s1['live_id']}/trail", tok)
    assert same["conversation_id"] == s1["live_id"] and len(same["segments"]) == 2, "the trail is the same from either end"
    assert api("GET", f"/live-voice/{s2['live_id']}/trail", S["tok"]["b"])[0] == 404, "someone else cannot read it"
    st, adm = api("GET", f"/live-voice/admin/sessions/{s2['live_id']}", forest)
    assert st == 200 and adm["trail"]["totals"]["handoffs"] == 1 and adm["meter"]["segment_no"] == 2 and adm["engine"] == "mini"
    st, adm2 = api("GET", f"/voice-controls/sessions/{s1['live_id']}/trail", forest)
    assert st == 200 and adm2["totals"]["total_s"] == 100
    assert api("GET", f"/voice-controls/sessions/{s1['live_id']}/trail", tok)[0] == 403
    S["a"] = (s1["live_id"], s2["live_id"])


# ── 2. the server settles a still-open premium session itself when the app resumes without closing it ────────────────────
async def test_resume_closes_open_premium_session_first():
    tok, uid = S["tok"]["b"], S["uid"]["b"]
    override(uid, {"daily_premium_min": 2})
    st, s1 = start(tok, "phone-b")
    assert st == 200 and s1["engine"] == "live"
    # no client report here: the server clock alone bills this segment (int() truncation, so aim at the middle of the 50th second)
    S["mongo"].live_sessions.update_one({"live_id": s1["live_id"]}, {"$set": {"started_at": datetime.now(timezone.utc) - timedelta(seconds=50.3)}})
    st, s2 = start(tok, "phone-b", resume_from=s1["live_id"], reason="connection_lost")
    assert st == 200 and s2["resumed_from"] == s1["live_id"]
    assert s2["engine"] == "live" and s2["meter"]["fallback_reason"] is None, "premium still has 70 s, so a plain reconnect stays on premium"
    seg1 = seg_of(s1["live_id"])
    assert seg1["status"] == "closed" and seg1["stop_reason"] == "handoff" and seg1["billable_s"] == 50 and seg1["released_s"] == 10 and seg1["unconfirmed"] is False
    old = live_of(s1["live_id"])
    assert old["status"] == "closed" and old["close_reason"] == "handoff" and old["handoff_to"] == s2["live_id"]
    r = res_doc(uid)
    assert r["premium_used_s"] == 50 and r["premium_reserved_s"] == 60, "exactly one live reservation after the switch"
    assert seg_of(s2["live_id"])["reconnect_of"] == s1["live_id"] and seg_of(s2["live_id"])["segment_no"] == 2
    events(tok, s2["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 5}])
    assert res_doc(uid)["premium_reserved_s"] == 0


# ── 3. backup exhausted too: stop with no fallback, every new start / resume refused -> the app offers typed Ask Jessi ──────
async def test_backup_exhausted_offers_text():
    tok, uid = S["tok"]["c"], S["uid"]["c"]
    override(uid, {"premium_disabled": True, "daily_backup_min": 1})
    st, s1 = start(tok, "phone-c")
    assert st == 200 and s1["engine"] == "mini" and s1["meter"]["fallback_reason"] == "premium_disabled" and s1["cap_left_s"] == 60
    backdate(s1["live_id"], 70)
    st, ev = events(tok, s1["live_id"], [{"type": "usage", "seconds": 70}])
    assert ev["stop"] == "backup_cap" and ev["fallback_engine"] is None and "resets at midnight" in ev["message"]
    st, ev = events(tok, s1["live_id"], [{"type": "closed", "reason": "voice_cap", "seconds": 70}])
    assert ev["status"] == "closed" and seg_of(s1["live_id"])["unconfirmed"] is False
    st, body = start(tok, "phone-c", resume_from=s1["live_id"], reason="backup_cap")
    assert st == 429 and "used today's Jessi voice minutes" in body["detail"]
    assert start(tok, "phone-c")[0] == 429
    st, cfg = api("GET", "/live-voice/config", tok)
    assert cfg["usage"]["left_s"] == 0 and cfg["controls"]["premium_left_s"] == 0 and cfg["controls"]["backup_left_s"] == 0 and cfg["controls"]["next_engine"] is None
    st, me = api("GET", "/voice-controls/me", tok)
    assert me["next_engine"] is None and me["backup_used_s"] == 70


# ── 4. no way around the caps: reconnects, a second device, asking for an engine, borrowing someone else's session ──────────
async def test_bypass_attempts_are_refused():
    tok, uid = S["tok"]["d"], S["uid"]["d"]
    override(uid, {"daily_premium_min": 1})
    # reconnect churn costs nothing and gains nothing: every open+close goes through the same pool
    for _ in range(5):
        st, s = start(tok, "phone-d")
        assert st == 200 and s["engine"] == "live"
        events(tok, s["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 0}])
    r = res_doc(uid)
    assert r["premium_used_s"] == 0 and r["premium_reserved_s"] == 0
    st, s = start(tok, "phone-d")
    backdate(s["live_id"], 70)
    events(tok, s["live_id"], [{"type": "usage", "seconds": 70}])
    events(tok, s["live_id"], [{"type": "closed", "reason": "premium_cap", "seconds": 70}])
    # reconnecting with a friendly reason, from another device, or asking for the premium engine: always the backup
    st, s2 = start(tok, "phone-d", resume_from=s["live_id"], reason="connection_lost")
    assert st == 200 and s2["engine"] == "mini" and s2["meter"]["fallback_reason"] == "premium_cap"
    st, s3 = start(tok, "laptop-d", overrides={"engine": "live", "walkthrough": False})
    assert st == 200 and s3["engine"] == "mini", "the engine is chosen by the server only"
    st, s4 = start(tok, "phone-d", resume_from=s2["live_id"], reason="premium_cap")
    assert st == 200 and s4["engine"] == "mini"
    for x in (s2, s3, s4):
        events(tok, x["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 1}])
    # another rep's session cannot be resumed; a lab session cannot be resumed as an assistant session
    assert start(tok, "phone-d", resume_from=S["a"][0], reason="premium_cap")[0] == 404
    assert start(tok, "phone-d", resume_from="nope12345678", reason="premium_cap")[0] == 404
    r = res_doc(uid)
    assert r["premium_used_s"] == 70 and r["premium_reserved_s"] == 0 and r["backup_reserved_s"] == 0
    # super admin can read the whole account's ledger; the rep still cannot change their own allowance
    assert api("PUT", f"/voice-controls/accounts/{S['org']}/users/{uid}", tok, json={"daily_premium_min": 500})[0] == 403
    assert api("POST", f"/voice-controls/accounts/{S['org']}/users/{uid}/grant", tok, json={"minutes": 60})[0] == 403


# ── 5. kill switch: a session that ignores the stop is closed by the server after STOP_GRACE_S ────────────────────────────
async def test_kill_switch_when_client_ignores_stop(monkeypatch):
    tok, uid, forest = S["tok"]["a"], S["uid"]["a"], S["forest"]
    api("POST", f"/voice-controls/accounts/{S['org']}/users/{uid}/grant", forest, json={"minutes": 1, "reason": "QA kill switch"})
    st, s = start(tok, "phone-a")
    assert st == 200 and s["engine"] == "live" and s["cap_left_s"] == 50, "the 70 s already spoken count against the 60 + 60 s"
    backdate(s["live_id"], 65)
    st, ev = events(tok, s["live_id"], [{"type": "usage", "seconds": 65}])
    assert ev["stop"] == "premium_cap"
    # the (modified) client keeps talking and keeps reporting: inside the grace period nothing is killed
    backdate(s["live_id"], 75)
    st, ev = events(tok, s["live_id"], [{"type": "usage", "seconds": 75}])
    assert ev["stop"] == "premium_cap", "the directive is repeated on every heartbeat"
    st, out = api("POST", "/voice-controls/watchdog", forest)
    assert out["killed"] == 0 and live_of(s["live_id"])["status"] == "open"
    S["mongo"][vc.LEDGER_COLL].update_one({"live_id": s["live_id"]}, {"$set": {"stop_requested_at": datetime.now(timezone.utc) - timedelta(seconds=vc.STOP_GRACE_S + 5)}})
    st, out = api("POST", "/voice-controls/watchdog", forest)
    assert out["killed"] == 1
    seg = seg_of(s["live_id"])
    assert seg["status"] == "closed" and seg["stop_reason"] == "server_kill" and seg["kill_attempts"] == 1 and seg["kill_result"]["ok"] is True and seg["kill_result"]["basis"] == "fake"
    assert seg["billable_s"] >= 75 and seg["unconfirmed"] is True
    live = live_of(s["live_id"])
    assert live["status"] == "closed" and live["close_reason"] == "server_kill" and live["meter"]["stop_reason"] == "server_kill"
    r = res_doc(uid)
    assert r["premium_reserved_s"] == 0 and r["premium_used_s"] >= 70 + 75
    assert events(tok, s["live_id"], [{"type": "usage", "seconds": 300}])[1]["stop"] is None and seg_of(s["live_id"])["billable_s"] == seg["billable_s"], "late heartbeats change nothing"
    st, again = start(tok, "phone-a")
    assert again["engine"] == "mini", "premium stays closed for the day"
    events(tok, again["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 0}])
    # provider_close against the real provider is never attempted without a key; with one it hits the documented endpoints (faked here)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert (await lv.provider_close({"engine": "mini", "openai_session_id": "rtc_x"}))["ok"] is False
    assert (await lv.provider_close({"engine": "live", "openai_session_id": "fake_abc", "fake_provider": True})) == {"ok": True, "basis": "fake", "provider_seconds": None}
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    calls = {}

    class FakeResp:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, **k):
            calls["url"], calls["headers"] = url, headers
            return FakeResp()

    monkeypatch.setattr(lv.httpx, "AsyncClient", FakeClient)
    out = await lv.provider_close({"engine": "mini", "openai_session_id": "rtc_abc123"})
    assert out["ok"] is True and calls["url"] == "https://api.openai.com/v1/realtime/calls/rtc_abc123/hangup" and calls["headers"]["Authorization"] == "Bearer sk-test-fake"

    import websockets
    sent = []
    msgs = [json.dumps({"type": "session.usage.updated", "usage": {"seconds": 88}}), json.dumps({"type": "session.closed", "reason": "close_requested", "usage": {"seconds": 91}})]

    class FakeWs:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def send(self, msg):
            sent.append(json.loads(msg))

        async def recv(self):
            return msgs.pop(0)

    monkeypatch.setattr(websockets, "connect", lambda url, **k: calls.update({"ws": url, "wsh": k.get("additional_headers")}) or FakeWs())
    out = await lv.provider_close({"engine": "live", "openai_session_id": "live_abc"})
    assert out == {"ok": True, "closed_event": True, "provider_seconds": 91, "reason": "close_requested"}
    assert sent == [{"type": "session.close"}] and calls["ws"] == "wss://api.openai.com/v1/live/sessions/live_abc/attach" and calls["wsh"]["Authorization"] == "Bearer sk-test-fake"


# ── 6. account-wide hard $ cap across users and concurrent sessions ─────────────────────────────────────────────────────────
async def test_account_hard_cap_across_users():
    forest, org = S["forest"], S["org"]
    db = get_db()
    override(S["uid"]["b"], {"clear": ["daily_premium_min"], "premium_disabled": False, "super_admin_authorized": False})
    override(S["uid"]["c"], {"clear": ["daily_premium_min", "daily_backup_min"], "premium_disabled": False})
    month = await db[vc.ACCT_MONTH_COLL].find_one({"org_id": org})
    spent = float((month or {}).get("premium_cost_usd") or 0)
    assert spent > 0.1, "the earlier tests spent premium minutes on this account"
    cap = round(spent + 70 * 0.05 / 60, 4)  # about 70 s of GPT-Live left for the WHOLE account
    api("PUT", f"/voice-controls/accounts/{org}", forest, json={"hard_premium_cap_usd": cap})
    st, me = api("GET", "/voice-controls/me", S["tok"]["b"])
    left_s = me["premium_left_s"]
    assert 60 <= left_s <= 76 and "hard_premium_cap" in me["limits"], me
    st1, s1 = start(S["tok"]["b"], "phone-b")
    st2, s2 = start(S["tok"]["c"], "phone-c")
    assert st1 == 200 and s1["engine"] == "live" and s1["cap_left_s"] == left_s
    assert st2 == 200 and s2["engine"] == "mini" and s2["meter"]["fallback_reason"] == "premium_cap", "the second rep cannot take premium the account no longer has (the first rep's reservation already counts)"
    day = await db[vc.ACCT_DAY_COLL].find_one({"_id": f"{org}:{S['day']}"})
    assert int(day["premium_reserved_s"]) == 60 <= left_s
    st, me_c = api("GET", "/voice-controls/me", S["tok"]["c"])
    assert me_c["premium_left_s"] == left_s - 60 and me_c["next_engine"] == "mini"
    # rep b talks past the account's last seconds: stopped, nothing more can be reserved by anyone
    backdate(s1["live_id"], left_s + 5)
    st, ev = events(S["tok"]["b"], s1["live_id"], [{"type": "usage", "seconds": left_s + 5}])
    assert ev["stop"] == "premium_cap" and ev["fallback_engine"] == "mini"
    for tok, x in ((S["tok"]["b"], s1), (S["tok"]["c"], s2)):
        events(tok, x["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 0}])
    st, me = api("GET", "/voice-controls/me", S["tok"]["b"])
    assert me["premium_left_s"] == 0 and me["next_engine"] == "mini"
    # binds even a super-admin-authorized override
    override(S["uid"]["b"], {"daily_premium_min": 60, "super_admin_authorized": True})
    st, me = api("GET", "/voice-controls/me", S["tok"]["b"])
    assert me["premium_left_s"] == 0 and "hard_premium_cap" in me["limits"]
    api("PUT", f"/voice-controls/accounts/{org}", forest, json={"clear": ["hard_premium_cap_usd"]})
    st, me = api("GET", "/voice-controls/me", S["tok"]["b"])
    assert me["premium_left_s"] == 3600 - me["premium_used_s"] and "hard_premium_cap" not in me["limits"] and me["next_engine"] == "live"
