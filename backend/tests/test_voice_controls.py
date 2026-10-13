"""Voice AI usage controls (P2 allowances + P4 ledger/reservations), live preview API + Mongo, zero OpenAI spend:
sessions are opened with the fake provider (VOICE_FAKE_PROVIDER_ALLOWED=1 in preview backend/.env, @invalid.imonsocial.test accounts).
Creates and wipes "QA Voice Controls Org" + qa-voice-rep-* users; flips the Test Lab flag jessi_live_voice to live for the run and restores it."""
import asyncio
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
from services import voice_controls as vc  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
FOREST = {"email": "forest@imosapp.com", "password": "Admin123!"}
ORG_ADMIN_B = {"email": "qa-orgadmin@invalid.imonsocial.test", "password": "OrgAdmin123!"}
ORG_B = "69a907033b77512d1d8d8a08"
PW = "VoiceRep123!"
REPS = {"a": "qa-voice-rep-a@invalid.imonsocial.test", "b": "qa-voice-rep-b@invalid.imonsocial.test", "c": "qa-voice-rep-c@invalid.imonsocial.test"}
pytestmark = pytest.mark.asyncio
S = {}  # module state shared between the ordered tests


def _token(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def api(method, path, tok=None, **kw):
    r = requests.request(method, f"{BASE}/api{path}", headers=_h(tok) if tok else {}, timeout=40, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def start(tok, device="dev-1"):
    return api("POST", "/live-voice/session", tok, json={"mode": "assistant", "sdp": "v=0 offer", "overrides": {"fake_provider": True}, "device_id": device})


def events(tok, live_id, evs):
    return api("POST", f"/live-voice/{live_id}/events", tok, json={"events": evs})


def backdate(live_id, seconds):
    """Pretend the session started `seconds` ago (the server meters on its own clock; the half second absorbs request latency up to 1.5 s)."""
    S["mongo"].live_sessions.update_one({"live_id": live_id}, {"$set": {"started_at": datetime.now(timezone.utc) - timedelta(seconds=seconds - 0.5)}})


def res_doc(uid):
    return S["mongo"][vc.RES_COLL].find_one({"_id": f"{S['org']}:{uid}:{S['day']}"}) or {}


def seg_of(live_id):
    return S["mongo"][vc.LEDGER_COLL].find_one({"live_id": live_id, "kind": "segment"})


@pytest.fixture(scope="module", autouse=True)
def qa():
    m = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    S["mongo"] = m
    forest = _token(FOREST)
    S["forest"] = forest
    # Test Lab flag: assistant mode needs jessi_live_voice live for non-super-admins
    st, feats = api("GET", "/lab/features", forest)
    prev = next((f.get("status") for f in (feats.get("features") if isinstance(feats, dict) else feats) if f.get("key") == "jessi_live_voice"), "lab")
    api("PUT", "/lab/features/jessi_live_voice", forest, json={"status": "live"})
    org = m.organizations.insert_one({"name": "QA Voice Controls Org", "timezone": "America/Denver", "qa_voice": True, "active": True, "created_at": datetime.now(timezone.utc)}).inserted_id
    S["org"] = str(org)
    now = datetime.now(timezone.utc)
    uids = {}
    for key, email in REPS.items():
        uid = m.users.insert_one({"name": f"Voice Rep {key.upper()}", "email": email, "password": hash_password(PW), "role": "user", "organization_id": str(org), "store_id": None,
                                  "phone": f"+1500555090{ord(key) - 96}", "is_active": True, "status": "active", "onboarding_complete": True, "phone_verified": True, "timezone": "America/Denver",
                                  "qa_voice": True, "created_at": now, "updated_at": now}).inserted_id
        uids[key] = str(uid)
    S["uid"] = uids
    S["tok"] = {k: _token({"email": e, "password": PW}) for k, e in REPS.items()}
    S["day"] = datetime.now(ZoneInfo("America/Denver")).strftime("%Y-%m-%d")
    yield S
    api("PUT", "/lab/features/jessi_live_voice", forest, json={"status": prev})
    ids = list(uids.values())
    m.live_sessions.delete_many({"user_id": {"$in": ids}})
    m.live_sessions.delete_many({"fake_provider": True, "user_id": str(m.users.find_one({"email": FOREST["email"]})["_id"]), "started_at": {"$gte": now - timedelta(hours=1)}})
    for coll in (vc.LEDGER_COLL, vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL, vc.POLICY_COLL, vc.OVERRIDE_COLL):
        m[coll].delete_many({"org_id": {"$regex": f"^({S['org']}|qa-voice-)"}})
    m[vc.LEDGER_COLL].delete_many({"user_id": {"$in": ids}})
    m.users.delete_many({"_id": {"$in": [ObjectId(x) for x in ids]}})
    m.organizations.delete_one({"_id": org})


# ── 1. policy + access control ────────────────────────────────────────────────
async def test_policy_roundtrip_and_access():
    org, forest = S["org"], S["forest"]
    st, body = api("GET", f"/voice-controls/accounts/{org}", forest)
    assert st == 200 and body["policy"]["exists"] is False and body["policy"]["enabled"] is False and body["name"] == "QA Voice Controls Org"
    st, body = api("PUT", f"/voice-controls/accounts/{org}", forest, json={"enabled": True, "per_user_daily_premium_min": 15, "per_user_daily_backup_min": 60, "timezone": "America/Denver", "notes": "QA policy"})
    assert st == 200 and body["policy"]["enabled"] is True and body["policy"]["per_user_daily_premium_min"] == 15 and body["policy"]["timezone"] == "America/Denver" and body["policy"]["updated_by"] == FOREST["email"]
    assert api("PUT", f"/voice-controls/accounts/{org}", forest, json={"premium_engine": "elevenlabs"})[0] == 400
    assert api("PUT", f"/voice-controls/accounts/{org}", forest, json={"timezone": "Mars/Olympus"})[1]["policy"]["timezone"] == "America/Denver", "bad tz ignored"
    # reps and other org admins are kept out; an org admin reads their own account only
    rep = S["tok"]["a"]
    assert api("GET", "/voice-controls/global", rep)[0] == 403
    assert api("PUT", f"/voice-controls/accounts/{org}", rep, json={"enabled": False})[0] == 403
    assert api("GET", f"/voice-controls/accounts/{org}", rep)[0] == 403
    assert api("GET", f"/voice-controls/accounts/{org}")[0] == 401
    ob = _token(ORG_ADMIN_B)
    assert api("GET", f"/voice-controls/accounts/{org}", ob)[0] == 403
    st, body = api("GET", f"/voice-controls/accounts/{ORG_B}", ob)
    assert st == 200 and body["org_id"] == ORG_B and body["policy"]["enabled"] is False  # ORG_B is forest's org: a left (disabled) pilot row may exist
    assert api("PUT", f"/voice-controls/accounts/{ORG_B}", ob, json={"enabled": True})[0] == 403
    # the rep sees their effective allowance
    st, me = api("GET", "/voice-controls/me", rep)
    assert st == 200 and me["enrolled"] and me["premium_allowance_s"] == 900 and me["backup_allowance_s"] == 3600 and me["premium_left_s"] == 900 and me["next_engine"] == "live" and me["timezone"] == "America/Denver"
    assert S["mongo"][vc.LEDGER_COLL].count_documents({"org_id": org, "kind": "admin_policy_change"}) >= 1


# ── 2. precedence: global safety -> account caps/budget -> override -> default ───
async def test_resolve_precedence_and_hard_caps():
    db = get_db()
    org = "qa-voice-prec-" + ObjectId().__str__()[-8:]
    user = {"_id": ObjectId(), "role": "user", "organization_id": org, "timezone": "America/Denver"}
    base = {**vc.DEFAULT_POLICY, "org_id": org, "enabled": True, "timezone": "America/Denver"}
    try:
        eff = await vc.resolve(db, user, base)
        assert eff["premium_allowance_s"] == 900 and eff["backup_allowance_s"] == 3600 and eff["premium_left_s"] == 900 and vc.pick_engine(base, eff) == "live"
        # user override beats the account default, the global ceiling beats the override unless super-admin authorized
        await vc.save_override(db, org, str(user["_id"]), {"daily_premium_min": 30}, {"email": "qa"}, True)
        eff = await vc.resolve(db, user, base)
        assert eff["premium_allowance_s"] == 1800 and "user_override" in eff["limits"]
        await vc.save_override(db, org, str(user["_id"]), {"daily_premium_min": 500}, {"email": "qa"}, True)
        eff = await vc.resolve(db, user, base)
        assert eff["premium_allowance_s"] == 240 * 60 and "global_max_premium" in eff["limits"]
        await vc.save_override(db, org, str(user["_id"]), {"super_admin_authorized": True}, {"email": "qa"}, True)
        eff = await vc.resolve(db, user, base)
        assert eff["premium_allowance_s"] == 500 * 60
        # shared account daily cap wins over the user allowance (unless authorized), the hard $ cap binds everyone
        await vc.save_override(db, org, str(user["_id"]), {"daily_premium_min": 30, "super_admin_authorized": False}, {"email": "qa"}, True)
        shared = {**base, "account_daily_premium_min": 10}
        eff = await vc.resolve(db, user, shared)
        assert eff["premium_left_s"] == 600 and "account_daily_premium" in eff["limits"] and eff["account"]["premium_left_s"] == 600
        await vc.save_override(db, org, str(user["_id"]), {"super_admin_authorized": True}, {"email": "qa"}, True)
        eff = await vc.resolve(db, user, shared)
        assert eff["premium_left_s"] == 1800, "authorized override bypasses the shared minute cap"
        hard = {**shared, "hard_premium_cap_usd": 0.05}
        eff = await vc.resolve(db, user, hard)
        assert eff["premium_left_s"] == 60 and eff["account"]["hard_left_s"] == 60, "hard $ cap binds an authorized override"
        sup = {"_id": ObjectId(), "role": "super_admin", "organization_id": org}
        eff = await vc.resolve(db, sup, hard)
        assert eff["premium_left_s"] == 60 and "super_admin_uncapped" in eff["limits"], "hard $ cap binds a super admin too"
        eff = await vc.resolve(db, sup, shared)
        assert eff["premium_left_s"] == 24 * 3600 and eff["backup_left_s"] == 24 * 3600
        # monthly budget converts to premium seconds; premium disabled -> backup; nothing enabled -> no engine
        budget = {**base, "monthly_budget_usd": 1.0}
        eff = await vc.resolve(db, user, budget)
        assert eff["premium_left_s"] == 1800, "an authorized override bypasses the soft monthly budget"
        await vc.save_override(db, org, str(user["_id"]), {"super_admin_authorized": False}, {"email": "qa"}, True)
        eff = await vc.resolve(db, user, budget)
        assert eff["premium_left_s"] == 1200 and "monthly_budget" in eff["limits"]
        await vc.save_override(db, org, str(user["_id"]), {"premium_disabled": True}, {"email": "qa"}, True)
        eff = await vc.resolve(db, user, base)
        assert eff["premium_left_s"] == 0 and "premium_disabled" in eff["limits"] and vc.pick_engine(base, eff) == "mini"
        off = {**base, "backup_enabled": False}
        eff = await vc.resolve(db, user, off)
        assert vc.pick_engine(off, eff) is None
        with pytest.raises(vc.NoAllowance):
            await vc.start(db, user, off)
        # cost helpers: GPT-Live 15 s minimum, mini by tokens else by minute
        assert vc.live_cost(5) == round(15 * 0.05 / 60, 4) and vc.live_cost(120) == 0.1 and vc.live_cost(0) == 0.0
        assert vc.mini_cost({"audio_out": 1_000_000}, 0) == 20.0 and vc.mini_cost(None, 120) == 0.03
    finally:
        for coll in (vc.OVERRIDE_COLL, vc.LEDGER_COLL, vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL):
            await db[coll].delete_many({"org_id": org})


# ── 3. midnight reset in the account's time zone ──────────────────────────────
async def test_day_boundary_follows_account_timezone():
    db = get_db()
    org = "qa-voice-tz-" + ObjectId().__str__()[-8:]
    user = {"_id": ObjectId(), "role": "user", "organization_id": org, "timezone": "America/New_York"}
    try:
        for tz in ("Pacific/Kiritimati", "Etc/GMT+12", "America/Denver"):
            policy = {**vc.DEFAULT_POLICY, "org_id": org, "enabled": True, "timezone": tz}
            eff = await vc.resolve(db, user, policy)
            local = datetime.now(ZoneInfo(tz))
            assert eff["day"] == local.strftime("%Y-%m-%d") and eff["timezone"] == tz
            reset = datetime.fromisoformat(eff["reset_at"])
            assert reset.hour == 0 and reset.minute == 0 and reset.date() == (local + timedelta(days=1)).date() and reset.utcoffset() == local.utcoffset()
        # yesterday's spend never counts today: a full day of usage keyed on yesterday leaves today's pool untouched
        policy = {**vc.DEFAULT_POLICY, "org_id": org, "enabled": True, "timezone": "America/Denver"}
        yesterday = (datetime.now(ZoneInfo("America/Denver")) - timedelta(days=1)).strftime("%Y-%m-%d")
        await db[vc.RES_COLL].insert_one({"_id": f"{org}:{user['_id']}:{yesterday}", "org_id": org, "user_id": str(user["_id"]), "day": yesterday, "premium_used_s": 900, "premium_reserved_s": 0, "backup_used_s": 3600, "backup_reserved_s": 0})
        eff = await vc.resolve(db, user, policy)
        assert eff["premium_used_s"] == 0 and eff["premium_left_s"] == 900 and eff["backup_left_s"] == 3600
        # when the policy has no tz the organization's tz is used, then the user's chain
        org_doc = await db.organizations.insert_one({"_id": ObjectId(), "name": "QA tz org", "timezone": "Europe/Dublin", "qa_voice": True})
        eff = await vc.resolve(db, {**user, "organization_id": str(org_doc.inserted_id)}, {**policy, "org_id": str(org_doc.inserted_id), "timezone": None})
        assert eff["timezone"] == "Europe/Dublin"
        await db.organizations.delete_one({"_id": org_doc.inserted_id})
    finally:
        for coll in (vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL, vc.LEDGER_COLL):
            await db[coll].delete_many({"org_id": org})


# ── 4. one session: premium runs out -> stop + fallback engine, ledger + reservation accounting ───
async def test_premium_cap_stops_and_backup_takes_over():
    org, forest, tok, uid = S["org"], S["forest"], S["tok"]["a"], S["uid"]["a"]
    st, body = api("PUT", f"/voice-controls/accounts/{org}/users/{uid}", forest, json={"daily_premium_min": 1, "notes": "QA: one premium minute"})
    assert st == 200 and body["override"]["daily_premium_min"] == 1
    assert api("PUT", f"/voice-controls/accounts/{org}/users/{S['mongo'].users.find_one({'email': ORG_ADMIN_B['email']})['_id']}", forest, json={"daily_premium_min": 1})[0] == 404, "user from another account"
    st, s1 = start(tok, "phone-a")
    assert st == 200, s1
    assert s1["engine"] == "live" and s1["model"] == "gpt-live-1" and s1["cap_left_s"] == 60 and s1["meter"] == {"policy_mode": "controls", "role": "premium", "fallback_reason": None, "left_s": 60, "reset_at": s1["meter"]["reset_at"], "fake_provider": True}
    assert s1["session_id"].startswith("fake_") and "fake-provider" in s1["sdp"]
    live_id = s1["live_id"]
    r = res_doc(uid)
    assert r["premium_reserved_s"] == 60 and r["premium_used_s"] == 0
    seg = seg_of(live_id)
    assert seg["policy_mode"] == "controls" and seg["reserved_s"] == 60 and seg["engine"] == "live" and seg["cost_basis"] == "server_clock" and seg["device_id"] == "phone-a" and seg["org_id"] == org and seg["day"] == S["day"]
    st, me = api("GET", "/voice-controls/me", tok)
    assert me["premium_left_s"] == 0 and me["premium_reserved_s"] == 60 and me["next_engine"] == "mini", "the whole minute is held by the open session"
    # 40 s in: settled 40, 20 s headroom, no more slices available -> warning, no stop
    backdate(live_id, 40)
    st, ev = events(tok, live_id, [{"type": "transcript", "role": "rep", "text": "Who should I call today?"}, {"type": "usage", "seconds": 40}])
    assert st == 200 and ev["stop"] is None and ev["left_s"] == 20 and ev["seconds"] == 40, ev
    seg = seg_of(live_id)
    assert seg["settled_s"] == 40 and seg["billable_s"] == 40 and seg["client_s"] == 40 and seg.get("cap_warning") is True and "premium_100" in seg["thresholds_hit"] and "premium_80" in seg["thresholds_hit"]
    r = res_doc(uid)
    assert r["premium_used_s"] == 40 and r["premium_reserved_s"] == 20
    # 70 s in: the reservation is exhausted and nothing is left -> stop premium_cap, backup offered, overrun counted
    backdate(live_id, 70)
    st, ev = events(tok, live_id, [{"type": "usage", "seconds": 70}])
    assert st == 200 and ev["stop"] == "premium_cap" and ev["fallback_engine"] == "mini" and "premium Jessi minutes" in ev["message"] and ev["left_s"] == 0, ev
    seg = seg_of(live_id)
    assert seg["settled_s"] == 70 and seg["overrun_s"] == 10 and seg["stop_reason"] == "premium_cap" and seg["status"] == "open"
    r = res_doc(uid)
    assert r["premium_used_s"] == 70 and r["premium_reserved_s"] == 0
    live = S["mongo"].live_sessions.find_one({"live_id": live_id})
    assert live["meter"]["stop_reason"] == "premium_cap" and live["meter"]["fallback_engine"] == "mini" and live["status"] == "open"
    # the app closes: final seconds, cost, confirmed
    backdate(live_id, 72)
    st, ev = events(tok, live_id, [{"type": "closed", "reason": "premium_cap", "seconds": 72}])
    assert st == 200 and ev["status"] == "closed"
    seg = seg_of(live_id)
    assert seg["status"] == "closed" and seg["billable_s"] == 72 and seg["est_cost_usd"] == round(72 * 0.05 / 60, 4) and seg["unconfirmed"] is False and seg["released_s"] == 0 and seg["stop_reason"] == "premium_cap"
    r = res_doc(uid)
    assert r["premium_used_s"] == 72 and r["premium_reserved_s"] == 0
    live = S["mongo"].live_sessions.find_one({"live_id": live_id})
    assert live["status"] == "closed" and live["close_reason"] == "premium_cap" and live["meter"]["billable_s"] == 72
    # premium gone -> the next session starts on the backup engine with the reason attached
    st, s2 = start(tok, "phone-a")
    assert st == 200 and s2["engine"] == "mini" and s2["model"] == "gpt-realtime-2.1-mini" and s2["meter"]["fallback_reason"] == "premium_cap" and s2["meter"]["role"] == "backup" and s2["cap_left_s"] == 3600
    r = res_doc(uid)
    assert r["backup_reserved_s"] == 60 and r["premium_reserved_s"] == 0
    backdate(s2["live_id"], 10)
    st, ev = events(tok, s2["live_id"], [{"type": "usage", "seconds": 10, "tokens": {"audio_in": 1000, "audio_in_cached": 0, "text_in": 0, "text_in_cached": 0, "audio_out": 2000, "text_out": 0}},
                                         {"type": "closed", "reason": "close_requested", "seconds": 10, "tokens": {"audio_in": 1000, "audio_in_cached": 0, "text_in": 0, "text_in_cached": 0, "audio_out": 2000, "text_out": 0}}])
    assert st == 200 and ev["status"] == "closed"
    seg2 = seg_of(s2["live_id"])
    assert seg2["status"] == "closed" and seg2["billable_s"] == 10 and seg2["released_s"] == 50 and seg2["cost_basis"] == "client_report" and seg2["est_cost_usd"] == round((1000 * 10 + 2000 * 20) / 1_000_000, 4)
    r = res_doc(uid)
    assert r["backup_used_s"] == 10 and r["backup_reserved_s"] == 0
    S["a_sessions"] = [live_id, s2["live_id"]]
    # account roll-up and month ledger
    st, acct = api("GET", f"/voice-controls/accounts/{org}", forest, params={"range": "today"})
    row = next(u for u in acct["users"] if u["user_id"] == uid)
    assert row["premium_s"] == 72 and row["backup_s"] == 10 and row["sessions"] == 2 and row["cap_hits"] == 1 and row["email"] == REPS["a"]
    assert acct["today"]["premium_used_s"] == 72 and acct["today"]["premium_reserved_s"] == 0 and acct["today"]["backup_used_s"] == 10 and acct["today"]["sessions"] >= 2
    assert acct["month"]["premium_s"] == 72 and acct["month"]["premium_cost_usd"] == round(72 * 0.05 / 60, 4) and acct["month"]["backup_s"] == 10 and acct["month"]["est_cost_usd"] == round(acct["month"]["premium_cost_usd"] + acct["month"]["backup_cost_usd"], 4)
    assert any(o["user_id"] == uid and o["daily_premium_min"] == 1 for o in acct["overrides"])
    st, detail = api("GET", f"/voice-controls/accounts/{org}/users/{uid}", forest)
    assert st == 200 and detail["allowance"]["premium_left_s"] == 0 and detail["allowance"]["backup_left_s"] == 3590 and len(detail["segments"]) == 2 and detail["segments"][0]["live_id"] == s2["live_id"]
    # a grant tops the day up; the hard stop is gone until it is spent
    st, g = api("POST", f"/voice-controls/accounts/{org}/users/{uid}/grant", forest, json={"minutes": 5, "reason": "QA demo day"})
    assert st == 200 and g["override"]["grants"][0]["minutes"] == 5 and g["override"]["grants"][0]["day"] == S["day"]
    st, me = api("GET", "/voice-controls/me", tok)
    assert me["premium_allowance_s"] == 360 and me["premium_left_s"] == 288 and me["grants_min_today"] == 5 and me["next_engine"] == "live"
    assert api("POST", f"/voice-controls/accounts/{org}/users/{uid}/grant", forest, json={"minutes": 0})[0] == 400


# ── 5. two devices share one pool; the pool can never be jointly exceeded ──────
async def test_two_devices_share_one_pool():
    org, forest, tok, uid = S["org"], S["forest"], S["tok"]["b"], S["uid"]["b"]
    api("PUT", f"/voice-controls/accounts/{org}/users/{uid}", forest, json={"daily_premium_min": 2})
    st, d1 = start(tok, "phone-b")
    st2, d2 = start(tok, "laptop-b")
    assert st == 200 and st2 == 200 and d1["engine"] == "live" and d2["engine"] == "live"
    assert d1["cap_left_s"] == 120 and d2["cap_left_s"] == 60, "the second device only sees what the first one left"
    r = res_doc(uid)
    assert r["premium_reserved_s"] == 120 and r["premium_used_s"] == 0
    st, d3 = start(tok, "tablet-b")
    assert st == 200 and d3["engine"] == "mini" and d3["meter"]["fallback_reason"] == "premium_cap", "a third device gets the backup engine, not a third premium minute"
    events(tok, d3["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 0}])
    # device 1 talks 50 s: it cannot top up (device 2 holds the rest) -> warning; at 65 s it is stopped with the overrun on the books
    backdate(d1["live_id"], 50)
    st, ev = events(tok, d1["live_id"], [{"type": "usage", "seconds": 50}])
    assert ev["stop"] is None and ev["left_s"] == 10 and seg_of(d1["live_id"]).get("cap_warning") is True
    backdate(d1["live_id"], 65)
    st, ev = events(tok, d1["live_id"], [{"type": "usage", "seconds": 65}])
    assert ev["stop"] == "premium_cap" and ev["fallback_engine"] == "mini"
    r = res_doc(uid)
    assert r["premium_used_s"] == 65 and r["premium_reserved_s"] == 60, r
    # device 2 hangs up after 30 s: its unused 30 s go back to the pool, so the next premium start is possible again (25 s >= MIN_START_S)
    backdate(d2["live_id"], 30)
    st, ev = events(tok, d2["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 30}])
    r = res_doc(uid)
    assert r["premium_used_s"] == 95 and r["premium_reserved_s"] == 0
    events(tok, d1["live_id"], [{"type": "closed", "reason": "premium_cap", "seconds": 65}])
    st, me = api("GET", "/voice-controls/me", tok)
    assert me["premium_used_s"] == 95 and me["premium_left_s"] == 25 and me["next_engine"] == "live"
    # the reservation itself is atomic: eight racing devices on a one-minute pool -> exactly one wins the slice
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(S["uid"]["c"])})
    policy = await vc.get_policy(db, org)
    await vc.save_override(db, org, S["uid"]["c"], {"daily_premium_min": 1}, {"email": "qa"}, True)
    eff = await vc.resolve(db, user, policy)
    got = await asyncio.gather(*[vc.reserve(db, eff, "live", 60) for _ in range(8)])
    assert sorted(got) == [0] * 7 + [60], got
    r = res_doc(S["uid"]["c"])
    assert r["premium_reserved_s"] == 60
    await vc.release(db, org, S["uid"]["c"], S["day"], "live", 60)
    assert res_doc(S["uid"]["c"])["premium_reserved_s"] == 0
    # the shared account pool is atomic too: account cap 1 minute/day, two users racing for it
    await vc.save_policy(db, org, {"account_daily_premium_min": 3}, {"email": "qa"})  # 180 s; 95 s already used by rep b today, 72 by rep a -> 13 s left
    policy = await vc.get_policy(db, org)
    eff_c = await vc.resolve(db, user, policy)
    assert eff_c["premium_left_s"] == 13 and eff_c["account"]["premium_left_s"] == 13
    assert vc.pick_engine(policy, eff_c) == "mini", "below MIN_START_S premium falls straight to backup"
    await vc.save_policy(db, org, {"clear": ["account_daily_premium_min"], "account_daily_premium_min": None}, {"email": "qa"})
    policy = await vc.get_policy(db, org)
    assert policy["account_daily_premium_min"] is None


# ── 6. watchdog finalizes a session that stopped reporting ────────────────────
async def test_watchdog_finalizes_stale_sessions():
    org, forest, tok, uid = S["org"], S["forest"], S["tok"]["c"], S["uid"]["c"]
    st, s = start(tok, "phone-c")
    assert st == 200 and s["engine"] == "live" and s["cap_left_s"] == 60
    assert res_doc(uid)["premium_reserved_s"] == 60
    assert api("POST", "/voice-controls/watchdog", forest)[1]["finalized"] == 0, "fresh sessions are left alone"
    stale = datetime.now(timezone.utc) - timedelta(seconds=vc.HEARTBEAT_STALE_S + 60)
    S["mongo"][vc.LEDGER_COLL].update_one({"live_id": s["live_id"]}, {"$set": {"heartbeat_at": stale, "started_at": stale}})
    S["mongo"].live_sessions.update_one({"live_id": s["live_id"]}, {"$set": {"started_at": stale}})
    st, out = api("POST", "/voice-controls/watchdog", forest)
    assert st == 200 and out["finalized"] == 1
    seg = seg_of(s["live_id"])
    assert seg["status"] == "closed" and seg["stop_reason"] == "stale_meter" and seg["billable_s"] == vc.GRACE_S and seg["unconfirmed"] is True and seg["settled_s"] == vc.GRACE_S and seg["released_s"] == 60 - vc.GRACE_S
    r = res_doc(uid)
    assert r["premium_used_s"] == vc.GRACE_S and r["premium_reserved_s"] == 0
    live = S["mongo"].live_sessions.find_one({"live_id": s["live_id"]})
    assert live["status"] == "closed" and live["close_reason"] == "stale_meter" and live["seconds"] == vc.GRACE_S
    assert events(tok, s["live_id"], [{"type": "usage", "seconds": 500}])[1]["stop"] is None, "late events on a finalized session change nothing"
    assert seg_of(s["live_id"])["billable_s"] == vc.GRACE_S
    rows = api("GET", "/voice-controls/ledger", forest, params={"org_id": org, "limit": 20})[1]["segments"]
    assert any(x["live_id"] == s["live_id"] and x["stop_reason"] == "stale_meter" for x in rows) and all(x["org_id"] == org for x in rows)


# ── 7. accounts not enrolled keep today's behaviour (and still get a legacy ledger row) ───
async def test_non_enrolled_account_unchanged():
    forest = S["forest"]
    st, cfg = api("GET", "/live-voice/config", forest)
    assert st == 200 and set(cfg["usage"]) == {"used_s", "cap_s", "left_s", "unlimited", "reset_at", "engine"} and cfg["usage"]["unlimited"] is True
    st, me = api("GET", "/voice-controls/me", forest)
    assert me == {"enrolled": False, "policy_mode": "legacy", "org_id": ORG_B}
    st, s = start(forest, "forest-web")
    assert st == 200 and s["engine"] == cfg["engine"] and s["cap_left_s"] == 24 * 3600 and s["meter"]["policy_mode"] == "legacy" and s["meter"]["left_s"] is None and s["meter"]["fallback_reason"] is None
    seg = seg_of(s["live_id"])
    assert seg["policy_mode"] == "legacy" and seg["org_id"] == ORG_B and seg["reserved_s"] == 0 and seg["day"] is None
    assert S["mongo"][vc.RES_COLL].find_one({"org_id": ORG_B}) is None, "no reservations for legacy accounts"
    backdate(s["live_id"], 20)
    st, ev = events(forest, s["live_id"], [{"type": "usage", "seconds": 20}])
    assert ev["stop"] is None and ev["left_s"] is None and ev["fallback_engine"] is None
    st, ev = events(forest, s["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 21}])
    assert ev["status"] == "closed"
    seg = seg_of(s["live_id"])
    assert seg["status"] == "closed" and seg["billable_s"] == 21 and seg["stop_reason"] == "close_requested"
    live = S["mongo"].live_sessions.find_one({"live_id": s["live_id"]})
    assert live["status"] == "closed" and live["seconds"] == 21 and live["close_reason"] == "close_requested" and live["fake_provider"] is True
    S["mongo"].live_sessions.delete_one({"live_id": s["live_id"]})
    S["mongo"][vc.LEDGER_COLL].delete_one({"live_id": s["live_id"]})
    # the fake provider is refused for accounts outside the test suffix / super admins, and when the switch is off
    assert vc.fake_provider_allowed({"role": "user", "email": "someone@dealer.com"}) is False
    assert vc.fake_provider_allowed({"role": "user", "email": REPS["a"]}) is True
    os.environ["VOICE_FAKE_PROVIDER_ALLOWED"] = "0"
    try:
        assert vc.fake_provider_allowed({"role": "super_admin", "email": FOREST["email"]}) is False
    finally:
        os.environ["VOICE_FAKE_PROVIDER_ALLOWED"] = "1"
    # the overview lists the QA account with its usage and enrolment
    st, ov = api("GET", "/voice-controls/accounts", forest, params={"range": "today"})
    row = next(r for r in ov["accounts"] if r["org_id"] == S["org"])
    assert row["enabled"] is True and row["name"] == "QA Voice Controls Org" and row["premium_s"] >= 72 + 65 + 30 and row["active_users"] == 3 and row["cap_hits"] >= 2
    # switching the account off returns every rep to the legacy path at the next session start
    api("PUT", f"/voice-controls/accounts/{S['org']}", forest, json={"enabled": False})
    st, me = api("GET", "/voice-controls/me", S["tok"]["a"])
    assert me["enrolled"] is False
    st, s = start(S["tok"]["a"], "phone-a")
    assert st == 200 and s["meter"]["policy_mode"] == "legacy" and s["engine"] == cfg["engine"]
    events(S["tok"]["a"], s["live_id"], [{"type": "closed", "reason": "close_requested", "seconds": 1}])
