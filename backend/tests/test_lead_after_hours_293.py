"""
Iteration 293 - After-hours rule / Send Test Lead / Attempt timeline.

Covers:
  * GET+PUT /api/lead-sources/{id}/workflow (after_hours_mode, text_window_*, store_hours, validation, partial save)
  * POST /api/lead-sources/{id}/test-lead (validation, auth, real pipeline side effects)
  * After-hours + texting-window deferral, stagger, store-closed Jessi hand-off
  * process_lead_deferred_actions / process_lead_call_jobs release + cancel paths
  * Twilio lead-call webhooks (answer / claim / status) -> GET /api/lead-sources/call-timeline/{conv}

SAFETY: customer phones are Twilio test-range 500-555-01xx only; the only rep on the ladder is
Activation Tester (+15005550006). Store/lead-source config is restored in teardown.
"""
import asyncio
import os
import re
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import dotenv_values, load_dotenv

load_dotenv("/app/backend/.env")
FE = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FE.get("REACT_APP_BACKEND_URL") or FE.get("EXPO_PUBLIC_BACKEND_URL")).rstrip("/")
LOCAL = "http://localhost:8001"

SRC_ID = "69a787ca70ae63ea0ac69251"          # Website lead source
STORE_ID = "69a0b7095fddcede09591668"
TESTER_ID = "6a978d68b8673c29063aa8b9"       # Activation Tester, +15005550006
ADMIN = {"email": "forest@imosapp.com", "password": "Admin123!"}
NONMGR = {"email": "mjeast1985@gmail.com", "password": "NavyBean1!"}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


def run(coro):
    return LOOP.run_until_complete(coro)


def get_db():
    from routers.database import get_db as _g
    return LOOP.run_until_complete(_mk(_g))


async def _mk(fn):
    return fn()


def api(method, path, token=None, json=None, base=BASE_URL, expect=None):
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = requests.request(method, f"{base}{path}", headers=h, json=json, timeout=90)
    if expect is not None:
        assert r.status_code == expect, f"{method} {path} -> {r.status_code}: {r.text[:400]}"
    return r


def login(creds):
    r = api("POST", "/api/auth/login", json=creds, expect=200)
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login response: {r.text[:300]}"
    return tok


@pytest.fixture(scope="session")
def admin_token():
    return login(ADMIN)


@pytest.fixture(scope="session")
def user_token():
    return login(NONMGR)


@pytest.fixture(scope="session", autouse=True)
def snapshot_and_restore():
    """Snapshot the Website source workflow + store hours, restore no matter what."""
    from bson import ObjectId
    db = get_db()
    src = run(db.lead_sources.find_one({"_id": ObjectId(SRC_ID)}))
    store = run(db.stores.find_one({"_id": ObjectId(STORE_ID)}, {"business_hours": 1}))
    assert src, "Website lead source missing"
    keep = {k: src.get(k) for k in ("text_window_start", "text_window_end", "after_hours_mode",
                                    "contact_mode", "website_default", "intake_text", "call_attempts",
                                    "workflow_user_ids", "va_enabled")}
    yield
    run(db.lead_sources.update_one({"_id": ObjectId(SRC_ID)}, {"$set": {
        "text_window_start": keep.get("text_window_start") or "09:00",
        "text_window_end": keep.get("text_window_end") or "20:00",
        "after_hours_mode": keep.get("after_hours_mode") or "text_and_ai",
        "contact_mode": keep.get("contact_mode") or "text_and_call",
        "website_default": keep.get("website_default", True),
        "intake_text": keep.get("intake_text") or "",
        "call_attempts": keep.get("call_attempts") or [],
        "workflow_user_ids": keep.get("workflow_user_ids") or [],
    }}))
    run(db.stores.update_one({"_id": ObjectId(STORE_ID)}, {"$set": {"business_hours": (store or {}).get("business_hours") or {}}}))
    print("\n[teardown] Website source workflow + store business_hours restored")


STATE = {}


# ── Workflow config: GET ───────────────────────────────────────────────────────
def test_01_workflow_get_shape(admin_token):
    cfg = api("GET", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, expect=200).json()
    for k in ("after_hours_mode", "text_window_start", "text_window_end", "store_hours"):
        assert k in cfg, f"missing {k} in workflow config: {list(cfg)}"
    assert cfg["after_hours_mode"] in ("text_and_ai", "ring_anyway")
    assert re.match(r"^\d{2}:\d{2}$", cfg["text_window_start"])
    sh = cfg["store_hours"]
    for k in ("timezone", "configured", "open_now", "opens_at", "hours"):
        assert k in sh, f"missing store_hours.{k}: {sh}"
    assert sh["timezone"] == "America/Denver", sh["timezone"]
    assert sh["configured"] is True
    assert isinstance(sh["hours"], dict) and sh["hours"], "store hours not returned"
    STATE["cfg0"] = cfg
    print(f"workflow GET ok: window {cfg['text_window_start']}-{cfg['text_window_end']} mode={cfg['after_hours_mode']} open_now={sh['open_now']}")


# ── Workflow config: PUT validation + persistence + partial save ───────────────
@pytest.mark.parametrize("bad", ["25:99", "9:00", "abc", ""])
def test_02_workflow_put_bad_time_400(admin_token, bad):
    r = api("PUT", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, json={"text_window_start": bad})
    assert r.status_code == 400, f"'{bad}' accepted -> {r.status_code} {r.text[:200]}"


def test_03_workflow_put_auth(user_token):
    assert api("PUT", f"/api/lead-sources/{SRC_ID}/workflow", None, json={"after_hours_mode": "text_and_ai"}).status_code == 401
    assert api("PUT", f"/api/lead-sources/{SRC_ID}/workflow", user_token, json={"after_hours_mode": "text_and_ai"}).status_code == 403


def test_04_workflow_put_valid_persists(admin_token):
    api("PUT", f"/api/lead-sources/{SRC_ID}/workflow", admin_token,
        json={"text_window_start": "08:00", "text_window_end": "21:00"}, expect=200)
    cfg = api("GET", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, expect=200).json()
    assert (cfg["text_window_start"], cfg["text_window_end"]) == ("08:00", "21:00"), cfg


def test_05_partial_put_does_not_reset(admin_token):
    api("PUT", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, json={"after_hours_mode": "ring_anyway"}, expect=200)
    cfg = api("GET", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, expect=200).json()
    assert cfg["after_hours_mode"] == "ring_anyway"
    assert (cfg["text_window_start"], cfg["text_window_end"]) == ("08:00", "21:00"), f"partial PUT reset window: {cfg}"
    assert cfg.get("call_attempts") == STATE["cfg0"].get("call_attempts"), "partial PUT wiped the call ladder"
    assert cfg.get("intake_text") == STATE["cfg0"].get("intake_text"), "partial PUT wiped intake_text"
    # restore
    api("PUT", f"/api/lead-sources/{SRC_ID}/workflow", admin_token,
        json={"text_window_start": "09:00", "text_window_end": "20:00", "after_hours_mode": "text_and_ai"}, expect=200)
    cfg = api("GET", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, expect=200).json()
    assert (cfg["text_window_start"], cfg["text_window_end"], cfg["after_hours_mode"]) == ("09:00", "20:00", "text_and_ai")


# ── test-lead: validation + auth ───────────────────────────────────────────────
@pytest.mark.parametrize("phone", ["123", "abc", "", "500555018"])
def test_06_test_lead_bad_phone_400(admin_token, phone):
    r = api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", admin_token,
            json={"phone": phone, "first_name": "TEST", "last_name": "Bad", "include_ladder": False})
    assert r.status_code == 400, f"phone '{phone}' accepted -> {r.status_code} {r.text[:300]}"


def test_07_test_lead_auth(user_token):
    body = {"phone": "5005550190", "include_ladder": False}
    assert api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", None, json=body).status_code == 401
    assert api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", user_token, json=body).status_code == 403


def test_08_test_lead_bad_source_404(admin_token):
    r = api("POST", "/api/lead-sources/69a787ca70ae63ea0ac69999/test-lead", admin_token,
            json={"phone": "5005550190", "include_ladder": False})
    assert r.status_code == 404, f"unknown source -> {r.status_code} {r.text[:200]}"


# ── test-lead in hours: full pipeline side effects ─────────────────────────────
def test_09_test_lead_in_hours(admin_token):
    from bson import ObjectId
    db = get_db()
    r = api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", admin_token,
            json={"phone": "5005550182", "first_name": "TEST", "last_name": "InHours", "include_ladder": False}, expect=200)
    d = r.json()
    assert d["success"] is True
    conv_id, contact_id = d["conversation_id"], d["contact_id"]
    assert conv_id and contact_id
    plan = d["plan"]
    for k in ("intake_deferred", "ladder_deferred", "jessi_on", "after_hours", "window", "store"):
        assert k in plan, f"plan missing {k}: {plan}"
    assert plan["intake_deferred"] is False, f"in-hours lead was deferred: {plan}"
    assert plan["after_hours"] is False, f"store reported closed: {plan['store']}"
    STATE["conv_in_hours"] = conv_id
    run(asyncio.sleep(3))

    conv = run(db.conversations.find_one({"_id": ObjectId(conv_id)}))
    assert conv["is_internet_lead"] is True
    assert conv["is_test"] is True
    assert conv.get("routing_plan"), "routing_plan not stored on conversation"
    assert (conv.get("sms_consent") or {}).get("opted_in") is True, conv.get("sms_consent")
    STATE["rep_phone_set"] = bool(conv.get("rep_phone"))
    assert conv.get("rep_phone"), "rep_phone (intake sender number) not set on lead conversation"

    contact = run(db.contacts.find_one({"_id": ObjectId(contact_id)}))
    assert "Test Lead" in (contact.get("tags") or []), contact.get("tags")
    assert contact.get("sms_consent") is True

    lead = run(db.inbound_leads.find_one({"conversation_id": conv_id}))
    assert lead, "inbound_leads doc not created"
    assert lead["status"] == "skipped", f"legacy AI first message status={lead['status']} (expected 'skipped')"

    msg = run(db.messages.find_one({"conversation_id": conv_id, "is_intake_text": True}))
    assert msg, "intake text message not logged"
    print(f"in-hours test lead ok conv={conv_id}")


# ── window closed -> intake deferred to tomorrow 09:00 + 1/min stagger ─────────
def test_10_window_closed_defers_and_staggers(admin_token):
    from bson import ObjectId
    from zoneinfo import ZoneInfo
    db = get_db()
    den = ZoneInfo("America/Denver")
    now_local = datetime.now(timezone.utc).astimezone(den)
    passed = (now_local - timedelta(hours=1)).strftime("%H:00")
    run(db.lead_release_slots.delete_many({}))  # deterministic stagger counter
    run(db.lead_sources.update_one({"_id": ObjectId(SRC_ID)}, {"$set": {"text_window_end": passed}}))
    try:
        r1 = api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", admin_token,
                 json={"phone": "5005550182", "first_name": "TEST", "last_name": "Night", "include_ladder": True}, expect=200).json()
        r2 = api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", admin_token,
                 json={"phone": "5005550183", "first_name": "TEST", "last_name": "Night2", "include_ladder": True}, expect=200).json()
    finally:
        run(db.lead_sources.update_one({"_id": ObjectId(SRC_ID)}, {"$set": {"text_window_end": "20:00"}}))

    p1, p2 = r1["plan"], r2["plan"]
    assert p1["intake_deferred"] is True and p1["intake_reason"] == "texting_window", p1
    assert p1["ladder_deferred"] is True and p1["ladder_reasons"] == ["texting_window"], p1["ladder_reasons"]
    i1 = datetime.fromisoformat(p1["intake_at"]).astimezone(den)
    tomorrow = (now_local + timedelta(days=1)).date()
    assert (i1.date(), i1.hour, i1.minute) == (tomorrow, 9, 0), f"intake_at={i1.isoformat()} expected tomorrow 09:00 Denver"
    i2 = datetime.fromisoformat(p2["intake_at"]).astimezone(den)
    assert (i2 - i1) == timedelta(minutes=1), f"stagger broken: {i1} -> {i2}"
    l1 = datetime.fromisoformat(p1["ladder_at"])
    assert (l1 - datetime.fromisoformat(p1["intake_at"])) == timedelta(seconds=60), "ladder not intake+60s"

    run(asyncio.sleep(2))
    act = run(db.lead_deferred_actions.find_one({"conversation_id": r1["conversation_id"], "kind": "intake_text"}))
    assert act, "no lead_deferred_actions doc"
    assert act["status"] == "pending"
    assert abs((act["run_at"].replace(tzinfo=timezone.utc) - datetime.fromisoformat(p1["intake_at"])).total_seconds()) < 2, act["run_at"]
    assert not run(db.messages.find_one({"conversation_id": r1["conversation_id"], "is_intake_text": True})), "intake text sent despite deferral"
    job = run(db.lead_call_jobs.find_one({"conversation_id": r1["conversation_id"]}))
    assert job and job.get("deferred") is True, job
    assert job.get("deferred_reasons") == ["texting_window"], job.get("deferred_reasons")
    STATE["deferred_conv"] = r1["conversation_id"]
    STATE["deferred_conv2"] = r2["conversation_id"]
    print(f"window-closed deferral ok: intake {i1.strftime('%m-%d %H:%M')} / stagger {i2.strftime('%H:%M')}")


# ── store closed, window open -> intake now, Jessi on, ladder at opening ──────
def test_11_store_closed_jessi_takes_over(admin_token):
    from bson import ObjectId
    from zoneinfo import ZoneInfo
    db = get_db()
    den = ZoneInfo("America/Denver")
    store = run(db.stores.find_one({"_id": ObjectId(STORE_ID)}, {"business_hours": 1}))
    bh = dict(store.get("business_hours") or {})
    today_key = DAYS[datetime.now(timezone.utc).astimezone(den).weekday()]
    original_today = bh.get(today_key)
    bh[today_key] = {"open": "06:00", "close": "07:00"}
    run(db.stores.update_one({"_id": ObjectId(STORE_ID)}, {"$set": {"business_hours": bh}}))
    try:
        cfg = api("GET", f"/api/lead-sources/{SRC_ID}/workflow", admin_token, expect=200).json()
        assert cfg["store_hours"]["open_now"] is False, "store_hours.open_now still true while closed"
        r = api("POST", f"/api/lead-sources/{SRC_ID}/test-lead", admin_token,
                json={"phone": "5005550184", "first_name": "TEST", "last_name": "Closed", "include_ladder": True}, expect=200).json()
    finally:
        bh[today_key] = original_today
        run(db.stores.update_one({"_id": ObjectId(STORE_ID)}, {"$set": {"business_hours": bh}}))
    plan = r["plan"]
    assert plan["after_hours"] is True, plan["store"]
    assert plan["intake_deferred"] is False, "intake wrongly deferred while window open"
    assert plan["ladder_deferred"] is True and plan["ladder_reasons"] == ["store_closed"], plan["ladder_reasons"]
    assert plan["jessi_on"] is True
    run(asyncio.sleep(3))
    conv = run(db.conversations.find_one({"_id": ObjectId(r["conversation_id"])}))
    assert conv.get("ai_mode") == "auto_reply", conv.get("ai_mode")
    assert conv.get("ai_enabled") is True
    assert conv.get("after_hours_lead") is True
    assert run(db.messages.find_one({"conversation_id": r["conversation_id"], "is_intake_text": True})), "intake text not sent immediately"
    job = run(db.lead_call_jobs.find_one({"conversation_id": r["conversation_id"]}))
    assert job and job.get("deferred") is True and job.get("deferred_reasons") == ["store_closed"], job
    nxt = job["next_attempt_at"].replace(tzinfo=timezone.utc).astimezone(den)
    assert (nxt.hour, nxt.minute) == (9, 5), f"next_attempt_at={nxt.isoformat()} expected 09:05 local"
    # store hours restored
    after = run(db.stores.find_one({"_id": ObjectId(STORE_ID)}, {"business_hours": 1}))
    assert after["business_hours"][today_key] == original_today
    print(f"store-closed path ok, ladder at {nxt.strftime('%a %H:%M')}")


# ── morning release ───────────────────────────────────────────────────────────
def test_12_deferred_action_release_sends(admin_token):
    db = get_db()
    conv_id = STATE.get("deferred_conv")
    assert conv_id, "test_10 must run first"
    from routers.lead_intake import process_lead_deferred_actions
    run(db.lead_deferred_actions.update_one({"conversation_id": conv_id, "kind": "intake_text"},
                                            {"$set": {"run_at": datetime.now(timezone.utc) - timedelta(seconds=5)}}))
    run(process_lead_deferred_actions())
    act = run(db.lead_deferred_actions.find_one({"conversation_id": conv_id, "kind": "intake_text"}))
    assert act["status"] == "sent", f"status={act['status']} error={act.get('error')}"
    assert run(db.messages.find_one({"conversation_id": conv_id, "is_intake_text": True})), "released intake text not logged"


def test_13_deferred_action_cancelled_when_rep_replied():
    from bson import ObjectId
    db = get_db()
    conv_id = STATE.get("deferred_conv2")
    assert conv_id, "test_10 must run first"
    run(db.messages.insert_one({"conversation_id": conv_id, "sender": "user", "direction": "outbound",
                                "content": "TEST_rep manual reply", "timestamp": datetime.now(timezone.utc)}))
    run(db.lead_deferred_actions.update_one({"conversation_id": conv_id, "kind": "intake_text"},
                                            {"$set": {"run_at": datetime.now(timezone.utc) - timedelta(seconds=5)}}))
    from routers.lead_intake import process_lead_deferred_actions
    run(process_lead_deferred_actions())
    act = run(db.lead_deferred_actions.find_one({"conversation_id": conv_id, "kind": "intake_text"}))
    assert act["status"] == "cancelled" and act.get("reason") == "rep_replied", act
    job = run(db.lead_call_jobs.find_one({"conversation_id": conv_id}))
    run(db.lead_call_jobs.update_one({"_id": job["_id"]}, {"$set": {"next_attempt_at": datetime.now(timezone.utc) - timedelta(seconds=5)}}))
    from services.lead_call_engine import process_lead_call_jobs
    run(process_lead_call_jobs())
    job = run(db.lead_call_jobs.find_one({"_id": job["_id"]}))
    assert job["status"] == "handled" and job.get("handled_reason") == "rep_replied", (job["status"], job.get("handled_reason"))
    print("deferred action cancelled + job handled on rep engagement")


# ── ladder fires + timeline via simulated Twilio webhooks ─────────────────────
def test_14_deferred_job_fires_and_timeline(admin_token):
    from bson import ObjectId
    db = get_db()
    conv_id = STATE.get("deferred_conv")
    job = run(db.lead_call_jobs.find_one({"conversation_id": conv_id}))
    assert job, "no ladder job for deferred conversation"
    ladder_uids = {u for a in job.get("attempts", []) for u in a.get("user_ids", [])}
    assert ladder_uids <= {TESTER_ID}, f"UNSAFE ladder contains non-tester users: {ladder_uids}"
    run(db.lead_call_jobs.update_one({"_id": job["_id"]}, {"$set": {"next_attempt_at": datetime.now(timezone.utc) - timedelta(seconds=5),
                                                                    "deferred": True}}))
    from services.lead_call_engine import process_lead_call_jobs
    run(process_lead_call_jobs())
    job = run(db.lead_call_jobs.find_one({"_id": job["_id"]}))
    print(f"job after release: status={job['status']} deferred={job.get('deferred')} calls={len(job.get('calls') or [])} attempt={job.get('attempt_index')}")
    if job.get("deferred") is True:
        print("WARNING: job.deferred stays true after the attempt actually fired (stale flag surfaced in timeline)")
    calls = job.get("calls") or []
    assert calls, f"no call rows recorded after release (job status={job['status']}, error={job.get('last_error')})"
    STATE["job_id"] = str(job["_id"])
    STATE["job_token"] = job["token"]
    STATE["timeline_conv"] = conv_id

    # simulate Twilio voice webhooks (localhost, real answer/claim payload shape)
    sid1 = calls[0]["call_sid"]
    q = f"job={STATE['job_id']}&u={TESTER_ID}&t={STATE['job_token']}"
    # spoof guard: wrong token must not mutate the job
    bad = requests.post(f"{LOCAL}/api/webhooks/twilio/lead-call/answer?job={STATE['job_id']}&u={TESTER_ID}&t=bogus",
                        data={"CallSid": sid1}, timeout=30)
    assert bad.status_code == 200 and "no longer available" in bad.text, bad.text[:200]
    r = requests.post(f"{LOCAL}/api/webhooks/twilio/lead-call/answer?{q}", data={"CallSid": sid1}, timeout=30)
    assert r.status_code == 200 and "<Response>" in r.text, r.text[:200]
    r = requests.post(f"{LOCAL}/api/webhooks/twilio/lead-call/claim?{q}", data={"CallSid": sid1, "Digits": "2"}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    job = run(db.lead_call_jobs.find_one({"_id": ObjectId(STATE["job_id"])}))
    entry = next((c for c in job["calls"] if c.get("call_sid") == sid1), None)
    assert entry, f"answer webhook did not attach to a call row: {job['calls']}"
    assert entry.get("answered_at"), "answered_at not recorded"
    assert entry.get("passed") is True and entry.get("status") == "passed", entry

    # second attempt -> press 1 -> claimed
    sid2 = "CA_TEST_293_B"
    run(db.lead_call_jobs.update_one({"_id": ObjectId(STATE["job_id"])},
                                     {"$push": {"calls": {"call_sid": sid2, "user_id": TESTER_ID, "attempt": 2,
                                                          "status": "ringing", "started_at": datetime.now(timezone.utc)}}}))
    r = requests.post(f"{LOCAL}/api/webhooks/twilio/lead-call/answer?{q}", data={"CallSid": sid2}, timeout=30)
    assert r.status_code == 200
    r = requests.post(f"{LOCAL}/api/webhooks/twilio/lead-call/claim?{q}", data={"CallSid": sid2, "Digits": "1"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    r = requests.post(f"{LOCAL}/api/webhooks/twilio/lead-call/status?{q}", data={"CallSid": sid2, "CallStatus": "completed"}, timeout=30)
    assert r.status_code in (200, 204), r.status_code

    conv = run(db.conversations.find_one({"_id": ObjectId(conv_id)}))
    assert conv.get("claimed_by") == TESTER_ID, conv.get("claimed_by")
    assert conv.get("claim_source") == "phone", conv.get("claim_source")

    tl = api("GET", f"/api/lead-sources/call-timeline/{conv_id}", admin_token, expect=200).json()
    assert tl["conversation_id"] == conv_id
    assert tl["is_test"] is True
    outcomes = [c.get("outcome") for c in tl["job"]["calls"]]
    assert "passed" in outcomes and "claimed" in outcomes, outcomes
    assert tl["claimed_by_name"] == "Activation Tester", tl.get("claimed_by_name")
    assert isinstance(tl["job"].get("time_to_claim_seconds"), int), tl["job"].get("time_to_claim_seconds")
    assert tl["intake"]["sent_at"], tl["intake"]
    print(f"timeline ok outcomes={outcomes} ttc={tl['job']['time_to_claim_seconds']}s")


def test_15_timeline_auth(admin_token, user_token):
    conv_id = STATE.get("timeline_conv") or STATE.get("conv_in_hours")
    assert api("GET", f"/api/lead-sources/call-timeline/{conv_id}").status_code == 401
    r = api("GET", f"/api/lead-sources/call-timeline/{conv_id}", user_token)
    assert r.status_code == 403, f"non-manager, non-ladder user got {r.status_code}"
    assert api("GET", "/api/lead-sources/call-timeline/not-an-objectid", admin_token).status_code == 404
    assert api("GET", "/api/lead-sources/call-timeline/69a787ca70ae63ea0ac69999", admin_token).status_code == 404


# ── pure timing rules (no Twilio, injected clock) ─────────────────────────────
class TestTimingRules:
    SRC = {"text_window_start": "09:00", "text_window_end": "20:00", "store_id": "TEST_scope", "va_enabled": True}
    STORE = {"timezone": "America/Denver", "business_hours": {d: {"open": "09:00", "close": "18:00"} for d in DAYS}}

    def _plan(self, source_over, when_local, phone="+15005550111"):
        from zoneinfo import ZoneInfo
        from services.lead_timing import build_contact_plan
        db = get_db()
        run(db.lead_release_slots.delete_many({"key": {"$regex": "^TEST_scope"}}))
        now = when_local.replace(tzinfo=ZoneInfo("America/Denver")).astimezone(timezone.utc)
        return run(build_contact_plan(db, {**self.SRC, **source_over}, self.STORE, phone, now))

    def test_ring_anyway_ignores_store_closed(self):
        # 7 PM: store closed, window open, mode ring_anyway -> nothing deferred
        p = self._plan({"after_hours_mode": "ring_anyway"}, datetime.now().replace(hour=19, minute=0, second=0, microsecond=0))
        assert p["after_hours"] is True, p["store"]
        assert p["intake_deferred"] is False
        assert p["ladder_deferred"] is False and p["ladder_reasons"] == [], p["ladder_reasons"]

    def test_text_and_ai_defers_ladder_only(self):
        p = self._plan({"after_hours_mode": "text_and_ai"}, datetime.now().replace(hour=19, minute=0, second=0, microsecond=0))
        assert p["intake_deferred"] is False
        assert p["ladder_reasons"] == ["store_closed"], p["ladder_reasons"]
        assert p["jessi_on"] is True

    def test_both_gates_closed_at_3am(self):
        p = self._plan({"after_hours_mode": "text_and_ai"}, datetime.now().replace(hour=3, minute=0, second=0, microsecond=0))
        assert p["intake_deferred"] is True and p["intake_reason"] == "texting_window"
        assert set(p["ladder_reasons"]) == {"texting_window", "store_closed"}, p["ladder_reasons"]
        intake = datetime.fromisoformat(p["intake_at"])
        ladder = datetime.fromisoformat(p["ladder_at"])
        assert ladder >= intake, "ladder must not ring before the intake text"

    def test_customer_timezone_from_area_code(self):
        from services.lead_timing import customer_timezone
        assert customer_timezone("+12125550123", "America/Denver") == "America/New_York"
        assert customer_timezone("+15005550111", "America/Denver") == "America/Denver"  # test range falls back

    def test_window_uses_customer_local_time(self):
        # 7 PM Denver = 9 PM New York -> outside the window for an NY customer
        p = self._plan({}, datetime.now().replace(hour=19, minute=0, second=0, microsecond=0), phone="+12125550123")
        assert p["customer_tz"] == "America/New_York"
        assert p["intake_deferred"] is True, p["window"]
