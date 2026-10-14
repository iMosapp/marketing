"""Founder Voice Pilot controls (own account only): enrol with 2 min GPT-Live / 10 min Mini / $20 hard cap, super admin capped like everyone,
usage + spend + open sessions + hand-offs in one status call, kill switch (refuses new sessions, hangs up open ones), total $ hard cap
enforced server side, leave -> legacy. Live preview API + Mongo, zero OpenAI spend (fake provider). Runs as forest on forest's own org and
cleans every row it created; forest's account is left NOT enrolled (the other suites rely on that)."""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from tests import qa_creds

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from services import voice_controls as vc  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
FOREST = {"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": qa_creds.password_for("activation-tester@invalid.imonsocial.test")}
pytestmark = pytest.mark.asyncio
S = {}


def api(method, path, tok=None, **kw):
    r = requests.request(method, f"{BASE}/api{path}", headers={"Authorization": f"Bearer {tok}"} if tok else {}, timeout=40, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def _token(creds):
    st, b = api("POST", "/auth/login", json=creds)
    assert st == 200, b
    return b["token"]


def start(tok, device="iphone-forest", resume_from=None, reason=None):
    return api("POST", "/live-voice/session", tok, json={"mode": "assistant", "sdp": "v=0 offer", "overrides": {"fake_provider": True}, "device_id": device, "resume_from": resume_from, "reason": reason})


def events(tok, live_id, evs):
    return api("POST", f"/live-voice/{live_id}/events", tok, json={"events": evs})


def backdate(live_id, seconds):
    S["mongo"].live_sessions.update_one({"live_id": live_id}, {"$set": {"started_at": datetime.now(timezone.utc) - timedelta(seconds=seconds - 0.5)}})


def seg_of(live_id):
    return S["mongo"][vc.LEDGER_COLL].find_one({"live_id": live_id, "kind": "segment"})


@pytest.fixture(scope="module", autouse=True)
def qa():
    m = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    S["mongo"] = m
    S["t0"] = datetime.now(timezone.utc) - timedelta(seconds=5)
    S["forest"] = _token(FOREST)
    st, status = api("GET", "/voice-controls/pilot", S["forest"])
    assert st == 200, status
    S["org"] = status["org_id"]
    S["uid"] = status["me"]["user_id"]
    S["prev_policy"] = m[vc.POLICY_COLL].find_one({"org_id": S["org"]})
    assert not (S["prev_policy"] or {}).get("enabled"), "forest's account must start un-enrolled"
    # a manual UI session (enrol, talk, leave) leaves today's usage and open fake sessions behind: start from a clean pool
    for coll in (vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL):
        m[coll].delete_many({"org_id": S["org"]})
    m[vc.LEDGER_COLL].update_many({"org_id": S["org"], "kind": "segment", "status": "open", "fake_provider": True}, {"$set": {"status": "closed", "stop_reason": "test_reset"}})
    m.live_sessions.update_many({"user_id": S["uid"], "fake_provider": True, "ended_at": None}, {"$set": {"ended_at": datetime.now(timezone.utc), "stop_reason": "test_reset"}})
    yield S
    org, uid, t0 = S["org"], S["uid"], S["t0"]
    m[vc.POLICY_COLL].delete_one({"org_id": org})
    if S["prev_policy"]:
        m[vc.POLICY_COLL].insert_one(S["prev_policy"])
    for coll in (vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL):
        m[coll].delete_many({"org_id": org})
    m[vc.LEDGER_COLL].delete_many({"org_id": org, "kind": "segment", "user_id": uid, "started_at": {"$gte": t0}})
    m[vc.LEDGER_COLL].delete_many({"org_id": org, "kind": {"$ne": "segment"}, "at": {"$gte": t0}})
    m.live_sessions.delete_many({"user_id": uid, "fake_provider": True, "started_at": {"$gte": t0 - timedelta(minutes=10)}})


# ── 1. status before, enrol my own account, super admin is capped like everyone ──────────────────────────────────────────
async def test_enroll_own_account_only():
    tok = S["forest"]
    st, before = api("GET", "/voice-controls/pilot", tok)
    assert before["enrolled"] is False and before["allowance"] is None and before["defaults"] == {"premium_min": 2, "backup_min": 10, "hard_usd": 20.0}
    assert set(before["env"]) == {"fake_provider_allowed", "openai_configured", "openai_reason", "build"} and before["env"]["fake_provider_allowed"] is True, "preview has the fake provider on"
    assert isinstance(before["other_enrolled_org_ids"], list) and S["org"] not in before["other_enrolled_org_ids"]
    others_before = len(before["other_enrolled_org_ids"])
    assert api("GET", "/voice-controls/pilot", _token(REP))[0] == 403, "reps cannot see or use the pilot controls"
    assert api("POST", "/voice-controls/pilot/enroll", tok, json={"premium_min": 0})[0] == 400
    assert api("POST", "/voice-controls/pilot/enroll", tok, json={"hard_usd": 0})[0] == 400
    st, s = api("POST", "/voice-controls/pilot/enroll", tok, json={"premium_min": 2, "backup_min": 10, "hard_usd": 20})
    assert st == 200 and s["enrolled"] is True and s["org_id"] == S["org"]
    p = s["policy"]
    assert p["enabled"] is True and p["cap_super_admins"] is True and p["killed"] is False and p["per_user_daily_premium_min"] == 2 and p["per_user_daily_backup_min"] == 10 and p["account_monthly_hard_usd"] == 20.0
    assert len(s["other_enrolled_org_ids"]) == others_before, "no other account changed"
    a = s["allowance"]
    assert a["premium_allowance_s"] == 120 and a["backup_allowance_s"] == 600 and a["premium_left_s"] == 120 and a["backup_left_s"] == 600 and a["next_engine"] == "live"
    assert "account_hard_cap" in a["limits"] and "super_admin_uncapped" not in a["limits"], "the founder is capped like a rep inside the pilot"
    assert s["month"]["cap_usd"] == 20.0 and s["month"]["cap_left_usd"] == 20.0 and s["active"] == [] and s["handoffs"] == []
    st, me = api("GET", "/voice-controls/me", tok)
    assert me["enrolled"] is True and me["premium_allowance_s"] == 120 and me["next_engine"] == "live"
    st, cfg = api("GET", "/live-voice/config", tok)
    assert cfg["usage"]["unlimited"] is False and cfg["usage"]["cap_s"] == 720 and cfg["controls"]["killed"] is False
    assert S["mongo"][vc.LEDGER_COLL].count_documents({"org_id": S["org"], "kind": "admin_policy_change", "at": {"$gte": S["t0"]}}) >= 1, "audit row"


# ── 1b. founder engine test: Realtime Mini only, premium pool untouched, back to live-first ───────────────────────────────
async def test_engine_mode_mini_only():
    tok = S["forest"]
    assert api("POST", "/voice-controls/pilot/engine-mode", tok, json={"mode": "turbo"})[0] == 400
    assert api("POST", "/voice-controls/pilot/engine-mode", _token(REP), json={"mode": "mini_only"})[0] == 403
    st, s = api("POST", "/voice-controls/pilot/engine-mode", tok, json={"mode": "mini_only"})
    assert st == 200 and s["policy"]["engine_mode"] == "mini_only" and s["allowance"]["next_engine"] == "mini" and s["allowance"]["premium_left_s"] == 120
    st, sess = start(tok, "iphone-mini-only")
    assert st == 200 and sess["engine"] == "mini" and sess["meter"]["role"] == "backup" and sess["meter"]["fallback_reason"] == "mini_only" and sess["resumed_from"] is None
    st, status = api("GET", "/voice-controls/pilot", tok)
    assert status["today"]["premium_reserved_s"] == 0 and status["today"]["backup_reserved_s"] == 60 and status["allowance"]["premium_left_s"] == 120, "GPT-Live minutes untouched"
    ev = events(tok, sess["live_id"], [{"type": "usage", "seconds": 0}])[1]
    assert ev.get("stop") is None and ev.get("fallback_engine") is None, "no hand-off target on a mini-only session"
    events(tok, sess["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 0}])
    st, s = api("POST", "/voice-controls/pilot/engine-mode", tok, json={"mode": "live_first"})
    assert st == 200 and s["policy"]["engine_mode"] == "live_first" and s["allowance"]["next_engine"] == "live" and s["active"] == []
    assert seg_of(sess["live_id"])["fallback_reason"] == "mini_only"


# ── 2. the pilot conversation: 2 premium minutes -> hand-off to Mini, visible in the status ──────────────────────────────
async def test_handoff_shows_up_in_status():
    tok = S["forest"]
    st, s1 = start(tok)
    assert st == 200 and s1["engine"] == "live" and s1["cap_left_s"] == 120 and s1["meter"]["role"] == "premium"
    st, status = api("GET", "/voice-controls/pilot", tok)
    assert len(status["active"]) == 1 and status["active"][0]["live_id"] == s1["live_id"] and status["active"][0]["reserved_s"] == 60 and status["today"]["premium_reserved_s"] == 60
    assert status["allowance"]["premium_left_s"] == 60, "the open session holds one slice"
    backdate(s1["live_id"], 130)
    st, ev = events(tok, s1["live_id"], [{"type": "usage", "seconds": 130}])
    assert ev["stop"] == "premium_cap" and ev["fallback_engine"] == "mini", ev
    events(tok, s1["live_id"], [{"type": "closed", "reason": "premium_cap", "seconds": 130}])
    st, s2 = start(tok, resume_from=s1["live_id"], reason="premium_cap")
    assert st == 200 and s2["engine"] == "mini" and s2["resumed_from"] == s1["live_id"] and s2["meter"]["fallback_reason"] == "premium_cap"
    backdate(s2["live_id"], 30)
    st, ev = events(tok, s2["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 30}])
    assert ev["status"] == "closed"
    st, status = api("GET", "/voice-controls/pilot", tok)
    assert status["active"] == [] and status["today"]["premium_used_s"] == 130 and status["today"]["backup_used_s"] == 30 and status["today"]["premium_reserved_s"] == 0 and status["today"]["backup_reserved_s"] == 0
    h = status["handoffs"][0]
    assert h["from_live_id"] == s1["live_id"] and h["to_live_id"] == s2["live_id"] and h["from_engine"] == "live" and h["to_engine"] == "mini" and h["reason"] == "premium_cap" and h["from_billable_s"] == 130 and h["to_billable_s"] == 30
    assert status["recent"][0]["live_id"] == s2["live_id"] and status["recent"][1]["live_id"] == s1["live_id"] and status["recent"][1]["stop_reason"] == "premium_cap"
    m = status["month"]
    assert m["premium_s"] == 130 and m["backup_s"] == 30 and m["premium_cost_usd"] == vc.live_cost(130) and m["backup_cost_usd"] == vc.mini_cost(None, 30) and m["est_cost_usd"] == round(vc.live_cost(130) + vc.mini_cost(None, 30), 4)
    assert m["cap_left_usd"] == round(20 - m["est_cost_usd"], 4)
    assert status["allowance"]["premium_left_s"] == 0 and status["allowance"]["next_engine"] == "mini"
    S["spent"] = m["est_cost_usd"]


# ── 3. kill switch: open session is hung up and finalized, new sessions refused, resume brings it back ─────────────────────
async def test_kill_switch():
    tok = S["forest"]
    st, s = start(tok, "ipad-forest")
    assert st == 200 and s["engine"] == "mini"
    st, out = api("POST", "/voice-controls/pilot/kill", tok)
    assert st == 200 and out["killed"] == 1 and out["policy"]["killed"] is True and out["active"] == []
    seg = seg_of(s["live_id"])
    assert seg["status"] == "closed" and seg["stop_reason"] == "killed" and seg["kill_attempts"] == 1 and seg["kill_result"]["basis"] == "fake" and seg["released_s"] == 60
    live = S["mongo"].live_sessions.find_one({"live_id": s["live_id"]})
    assert live["status"] == "closed" and live["close_reason"] == "killed"
    assert out["today"]["backup_reserved_s"] == 0 and out["today"]["premium_reserved_s"] == 0, "reservations given back"
    assert out["allowance"]["premium_left_s"] == 0 and out["allowance"]["backup_left_s"] == 0 and out["allowance"]["next_engine"] is None and "killed" in out["allowance"]["limits"]
    st, body = start(tok)
    assert st == 429 and "paused" in body["detail"], body
    assert events(tok, s["live_id"], [{"type": "usage", "seconds": 500}])[1]["stop"] is None and seg_of(s["live_id"])["billable_s"] == seg["billable_s"], "late events on a killed session change nothing"
    st, cfg = api("GET", "/live-voice/config", tok)
    assert cfg["controls"]["killed"] is True and cfg["usage"]["left_s"] == 0
    # a session that was open before the kill (simulated: reopen the row) is told to stop on its next heartbeat with no fallback
    S["mongo"].live_sessions.update_one({"live_id": s["live_id"]}, {"$set": {"status": "open", "seconds": 0}})
    S["mongo"][vc.LEDGER_COLL].update_one({"_id": seg["_id"]}, {"$set": {"status": "open", "stop_reason": None, "stop_requested_at": None}})
    st, ev = events(tok, s["live_id"], [{"type": "usage", "seconds": 1}])
    assert ev["stop"] == "killed" and ev["fallback_engine"] is None and "paused" in ev["message"]
    events(tok, s["live_id"], [{"type": "closed", "reason": "killed", "seconds": 1}])
    assert seg_of(s["live_id"])["status"] == "closed" and seg_of(s["live_id"])["unconfirmed"] is False
    st, out = api("POST", "/voice-controls/pilot/resume", tok)
    assert st == 200 and out["policy"]["killed"] is False and out["allowance"]["next_engine"] == "mini"
    st, s = start(tok)
    assert st == 200 and s["engine"] == "mini"
    events(tok, s["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 0}])


# ── 4. the $ hard cap: total spend this month, both engines, enforced before and during a session ────────────────────────
async def test_total_hard_cap_enforced():
    tok = S["forest"]
    st, status = api("GET", "/voice-controls/pilot", tok)
    spent = status["month"]["est_cost_usd"]
    cap = round(spent + 0.02, 2)
    st, s = api("POST", "/voice-controls/pilot/enroll", tok, json={"premium_min": 2, "backup_min": 10, "hard_usd": cap})
    assert st == 200 and s["policy"]["account_monthly_hard_usd"] == cap
    left_usd = round(cap - spent, 4)
    expect_back = int(left_usd / 0.015 * 60)
    assert s["allowance"]["backup_left_s"] == expect_back and s["allowance"]["premium_left_s"] == 0 and "account_hard_cap" in s["allowance"]["limits"], s["allowance"]
    assert 20 <= expect_back <= 120
    st, sess = start(tok)
    assert st == 200 and sess["engine"] == "mini" and sess["cap_left_s"] == expect_back
    backdate(sess["live_id"], expect_back + 15)
    st, ev = events(tok, sess["live_id"], [{"type": "usage", "seconds": expect_back + 15}])
    assert ev["stop"] == "backup_cap" and ev["fallback_engine"] is None, ev
    events(tok, sess["live_id"], [{"type": "closed", "reason": "backup_cap", "seconds": expect_back + 15}])
    st, status = api("GET", "/voice-controls/pilot", tok)
    assert status["month"]["cap_left_usd"] == 0 and status["allowance"]["next_engine"] is None and status["allowance"]["backup_left_s"] == 0
    assert start(tok)[0] == 429, "nothing can start once the account's monthly cap is spent"
    st, s = api("POST", "/voice-controls/pilot/enroll", tok, json={"premium_min": 2, "backup_min": 10, "hard_usd": 20})
    assert s["allowance"]["next_engine"] == "mini" and s["allowance"]["backup_left_s"] == 600 - status["month"]["backup_s"]


# ── 5. leave: back to legacy for the whole account, open sessions ended ───────────────────────────────────────────────────
async def test_leave_returns_to_legacy():
    tok = S["forest"]
    st, s = start(tok)
    assert st == 200 and s["meter"]["policy_mode"] == "controls"
    st, out = api("POST", "/voice-controls/pilot/leave", tok)
    assert st == 200 and out["killed"] == 1 and out["enrolled"] is False and out["policy"]["enabled"] is False and out["policy"]["cap_super_admins"] is False and out["allowance"] is None
    st, me = api("GET", "/voice-controls/me", tok)
    assert me["enrolled"] is False and me["policy_mode"] == "legacy"
    st, cfg = api("GET", "/live-voice/config", tok)
    assert cfg["usage"]["unlimited"] is True and cfg["controls"] is None
    st, s = start(tok)
    assert st == 200 and s["meter"]["policy_mode"] == "legacy" and s["cap_left_s"] == 24 * 3600
    events(tok, s["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 1}])
    assert S["mongo"][vc.RES_COLL].count_documents({"org_id": S["org"], "_id": {"$regex": f":{S['uid']}:"}}) >= 1, "history kept"
    assert ObjectId.is_valid(S["uid"])
