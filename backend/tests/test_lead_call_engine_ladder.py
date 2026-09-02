"""
Lead Call Engine (CallDrip-style ladder) + marketing form -> Lead Source workflow.

Sequential suite (module state shared). Run with -p no:randomly and no xdist:
    pytest /app/backend/tests/test_lead_call_engine_ladder.py -v -s

SAFETY: only user 6a978d68b8673c29063aa8b9 (+15005550006 Twilio test number) is ever
put on a ladder, and only 500-555-01xx customer phones are used.
"""
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

fe = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
be = dotenv_values("/app/backend/.env")
_mc = MongoClient(be["MONGO_URL"])
db = _mc[be["DB_NAME"]]

WEBSITE = "69a787ca70ae63ea0ac69251"
REFERRAL = "69a787ca70ae63ea0ac69252"
TESTER = "6a978d68b8673c29063aa8b9"
OTHER_USER = "69c75782e051d06491e6fa9f"
ADMIN_ID = "69a0b7095fddcede09591667"
STORE = "69a0b7095fddcede09591668"
ORIGIN = "https://imonsocial.com"

STATE = {}
LADDER = [{"user_ids": [TESTER], "delay_seconds": 0}, {"user_ids": [TESTER], "delay_seconds": 60}]
BASE_WF = {
    # NOTE: hydrate_intake_text only supports {{field}} (double brace) placeholders.
    "intake_text": "Hi {{first_name}}, thanks for booking a demo!",
    "workflow_user_ids": [TESTER],
    "contact_mode": "text_and_call",
    "call_attempts": LADDER,
    "website_default": True,
    "website_pages": ["pricing"],
    "va_enabled": False,
}


TEST_EMAILS = [f"ladder-qa{n}@invalid.imonsocial.test" for n in ["", "2", "3", "4"]]
TEST_PHONES = ["+15005550166", "+15005550167", "+15005550168", "+15005550169", "+15005550170"]


def purge():
    """Remove anything this suite created (demo requests / convs / contacts / msgs / jobs)."""
    conv_ids, contact_ids = set(), set()
    for d in db.demo_requests.find({"email": {"$in": TEST_EMAILS}}):
        if d.get("conversation_id"):
            conv_ids.add(d["conversation_id"])
    for c in db.contacts.find({"$or": [{"email": {"$in": TEST_EMAILS}}, {"phone": {"$in": TEST_PHONES}}]}):
        contact_ids.add(str(c["_id"]))
    for cv in db.conversations.find({"contact_id": {"$in": list(contact_ids)}}):
        conv_ids.add(str(cv["_id"]))
    db.messages.delete_many({"conversation_id": {"$in": list(conv_ids)}})
    db.lead_call_jobs.delete_many({"$or": [{"conversation_id": {"$in": list(conv_ids)}},
                                           {"customer_phone": {"$in": TEST_PHONES}}]})
    db.conversations.delete_many({"_id": {"$in": [ObjectId(c) for c in conv_ids]}})
    db.contacts.delete_many({"_id": {"$in": [ObjectId(c) for c in contact_ids]}})
    db.demo_requests.delete_many({"email": {"$in": TEST_EMAILS}})
    db.inbound_leads.delete_many({"$or": [{"email": {"$in": TEST_EMAILS}}, {"phone": {"$in": TEST_PHONES}}]})
    db.notifications.delete_many({"conversation_id": {"$in": list(conv_ids)}})
    return len(conv_ids), len(contact_ids)


@pytest.fixture(scope="module", autouse=True)
def clean_slate():
    print("purge before:", purge())
    yield
    if os.environ.get("LADDER_QA_KEEP") != "1":
        print("purge after:", purge())


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE_URL}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:300]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    sess.headers.update({"Authorization": f"Bearer {tok}", "X-User-ID": ADMIN_ID})
    return sess


def _put_wf(s, source_id, cfg):
    return s.put(f"{BASE_URL}/api/lead-sources/{source_id}/workflow", json=cfg, timeout=30)


def _wait(fn, timeout=30, interval=2):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(interval)
    return fn()


# ── 1. Workflow config round-trip ────────────────────────────────────────────
class TestWorkflowConfig:
    def test_put_and_get_workflow(self, s):
        r = _put_wf(s, WEBSITE, BASE_WF)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("success") is True

        g = s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}/workflow", timeout=30)
        assert g.status_code == 200, g.text[:300]
        w = g.json()
        assert w["intake_text"] == BASE_WF["intake_text"]
        assert w["workflow_user_ids"] == [TESTER]
        assert w["contact_mode"] == "text_and_call"
        assert w["website_default"] is True
        assert w["website_pages"] == ["pricing"]
        assert w["va_enabled"] is False
        assert len(w["call_attempts"]) == 2
        assert w["call_attempts"][0]["user_ids"] == [TESTER]
        assert w["call_attempts"][0]["delay_seconds"] == 30  # server clamps to a 30s minimum
        assert w["call_attempts"][1]["delay_seconds"] == 60

    def test_website_pages_listing(self, s):
        r = s.get(f"{BASE_URL}/api/lead-sources/website-pages", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d.get("pages"), list) and len(d["pages"]) > 0
        routed = d.get("routed") or {}
        assert routed.get("pricing", {}).get("id") == WEBSITE
        assert routed["pricing"]["name"] == "Website"
        assert routed.get("__default__", {}).get("id") == WEBSITE
        assert routed["__default__"]["name"] == "Website"

    def test_call_attempts_clamped_to_four(self, s):
        cfg = dict(BASE_WF, call_attempts=[{"user_ids": [TESTER], "delay_seconds": i * 30} for i in range(6)])
        r = _put_wf(s, WEBSITE, cfg)
        assert r.status_code == 200, r.text[:300]
        got = s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}/workflow", timeout=30).json()["call_attempts"]
        assert len(got) == 4, f"expected clamp to 4, got {len(got)}"
        # restore the 2-attempt ladder
        assert _put_wf(s, WEBSITE, BASE_WF).status_code == 200
        assert len(s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}/workflow", timeout=30).json()["call_attempts"]) == 2

    def test_single_website_default(self, s):
        ref = {"intake_text": "", "workflow_user_ids": [], "contact_mode": "text_only",
               "call_attempts": [], "website_default": True, "website_pages": [], "va_enabled": False}
        assert _put_wf(s, REFERRAL, ref).status_code == 200
        assert s.get(f"{BASE_URL}/api/lead-sources/{REFERRAL}/workflow", timeout=30).json()["website_default"] is True
        assert s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}/workflow", timeout=30).json()["website_default"] is False, \
            "Website catch-all should have been cleared"
        # restore
        assert _put_wf(s, REFERRAL, dict(ref, website_default=False)).status_code == 200
        assert _put_wf(s, WEBSITE, BASE_WF).status_code == 200
        assert s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}/workflow", timeout=30).json()["website_default"] is True


# ── 2. Marketing form -> lead source pipeline ────────────────────────────────
class TestFormPipeline:
    def test_demo_request_routes_and_creates_job(self, s):
        body = {"name": "Ladder QA", "email": "ladder-qa@invalid.imonsocial.test", "phone": "(500) 555-0166",
                "company": "QA Motors", "business_type": "Auto dealer", "message": "lose leads on weekends",
                "source": "relationship_os_hero", "utm_source": "facebook", "utm_medium": "cpc"}
        r = requests.post(f"{BASE_URL}/api/demo-requests", json=body, headers={"Origin": ORIGIN}, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"

        demo = _wait(lambda: db.demo_requests.find_one({"email": body["email"], "lead_source_id": {"$ne": None}}), 20)
        assert demo, "demo_requests doc not created/routed"
        STATE["demo_id"] = demo["_id"]
        assert demo.get("lead_source_id") == WEBSITE, demo.get("lead_source_id")
        conv_id = demo.get("conversation_id")
        assert conv_id, "conversation_id not set on demo_requests doc"
        STATE["conv_id"] = conv_id

        conv = db.conversations.find_one({"_id": ObjectId(conv_id)})
        assert conv, "conversation missing"
        STATE["contact_id"] = str(conv.get("contact_id")) if conv.get("contact_id") else None
        assert conv.get("lead_source_name") == "Website", conv.get("lead_source_name")
        attr = conv.get("attribution") or {}
        assert attr.get("kind") == "website_form"
        assert attr.get("page") == "relationship_os", attr
        assert attr.get("position") == "hero", attr
        assert attr.get("channel") == "paid_social", attr
        assert attr.get("utm_source") == "facebook"
        assert attr.get("source_label") == "the Relationship OS page", attr.get("source_label")

        msgs = _wait(lambda: list(db.messages.find({"conversation_id": conv_id, "is_intake_text": True})), 15, 2)
        assert len(msgs) == 1, f"expected 1 intake text, got {len(msgs)}"
        assert msgs[0].get("content") == "Hi Ladder, thanks for booking a demo!", msgs[0].get("content")

        job = _wait(lambda: db.lead_call_jobs.find_one({"conversation_id": conv_id}), 20)
        assert job, "lead_call_jobs doc not created"
        STATE["job"] = job
        assert job["status"] in ("active", "exhausted", "claimed")
        assert len(job["attempts"]) == 2, job["attempts"]
        assert job["customer_phone"] == "+15005550166", job["customer_phone"]
        assert job["lead"]["name"] == "Ladder QA"
        assert job["lead"]["industry"] == "Auto dealer"
        assert job["lead"]["comments"], job["lead"]
        assert job["lead"]["source_label"] == "the Relationship OS page"

    def test_scheduler_fires_attempt_one(self):
        jid = STATE["job"]["_id"]
        job = _wait(lambda: db.lead_call_jobs.find_one({"_id": jid, "attempt_index": {"$gte": 1}}), 30, 3)
        assert job, "scheduler never fired attempt 1 (attempt_index still 0)"
        assert job["attempt_index"] == 1
        calls = [c for c in job.get("calls", []) if c.get("user_id") == TESTER]
        assert calls, f"no call entry for tester rep: {job.get('calls')}"
        assert calls[0]["status"] in ("ringing", "failed", "queued", "completed", "no-answer"), calls[0]
        STATE["job"] = job
        print("attempt1 call entries:", [(c["user_id"], c["status"], c.get("error", "")[:80]) for c in job["calls"]])

    def test_page_specific_route_text_only_no_job(self, s):
        ref = {"intake_text": "", "workflow_user_ids": [], "contact_mode": "text_only", "call_attempts": [],
               "website_default": False, "website_pages": ["relationship_os"], "va_enabled": False}
        assert _put_wf(s, REFERRAL, ref).status_code == 200
        try:
            body = {"name": "Ladder QA3", "email": "ladder-qa3@invalid.imonsocial.test", "phone": "(500) 555-0170",
                    "company": "QA Motors", "business_type": "Auto dealer", "message": "page route test",
                    "source": "relationship_os_cta"}
            r = requests.post(f"{BASE_URL}/api/demo-requests", json=body, headers={"Origin": ORIGIN}, timeout=60)
            assert r.status_code == 200, r.text[:300]
            demo = _wait(lambda: db.demo_requests.find_one({"email": body["email"], "lead_source_id": {"$ne": None}}), 20)
            assert demo, "page-specific demo not routed"
            assert demo["lead_source_id"] == REFERRAL, demo["lead_source_id"]
            conv_id = demo.get("conversation_id")
            assert conv_id
            time.sleep(3)
            assert db.lead_call_jobs.find_one({"conversation_id": conv_id}) is None, \
                "text_only source must not create a lead_call_job"
        finally:
            assert _put_wf(s, REFERRAL, dict(ref, website_pages=[])).status_code == 200


# ── 3. Voice webhooks (simulated Twilio) ─────────────────────────────────────
class TestVoiceWebhooks:
    @staticmethod
    def _qs(uid=None, token=None):
        job = STATE["job"]
        return f"job={job['_id']}&u={uid or TESTER}&t={token if token is not None else job['token']}"

    def test_answer_prompts_press_one(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/answer?{self._qs()}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert "<Gather" in r.text and "/lead-call/claim?" in r.text, r.text[:500]
        assert "Press 1 to claim this lead" in r.text, r.text[:500]

    def test_answer_wrong_token(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/answer?{self._qs(token='bogus')}", timeout=30)
        assert r.status_code == 200
        assert "no longer available" in r.text, r.text[:300]

    def test_claim_digit_two_passes(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/claim?{self._qs()}",
                          data={"Digits": "2"}, timeout=30)
        assert r.status_code == 200
        assert "passing on this lead" in r.text, r.text[:300]
        job = db.lead_call_jobs.find_one({"_id": STATE["job"]["_id"]})
        assert job.get("claimed_by") is None, "pass should not claim the job"

    def test_claim_digit_one_whispers_and_bridges(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/claim?{self._qs()}",
                          data={"Digits": "1"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        xml = r.text
        for token in ["You got it", "Ladder QA", "Relationship OS", "QA Motors",
                      "Industry: Auto dealer", "lose leads on weekends"]:
            assert token in xml, f"missing '{token}' in whisper: {xml[:800]}"
        assert 'callerId="+1' in xml and "<Dial" in xml and 'timeout="30"' in xml, xml[:600]
        assert "+15005550166</Dial>" in xml, xml[:600]

    def test_claim_persisted(self):
        job = db.lead_call_jobs.find_one({"_id": STATE["job"]["_id"]})
        assert job["status"] == "claimed", job["status"]
        assert job["claimed_by"] == TESTER
        assert job["claimed_via"] == "phone"
        conv = db.conversations.find_one({"_id": ObjectId(STATE["conv_id"])})
        assert conv.get("claimed") is True
        assert conv.get("claimed_by") == TESTER
        assert conv.get("assigned_to") == TESTER
        assert conv.get("user_id") == TESTER
        assert conv.get("claim_source") == "phone"
        if STATE.get("contact_id"):
            contact = db.contacts.find_one({"_id": ObjectId(STATE["contact_id"])})
            assert contact.get("user_id") == TESTER, contact.get("user_id")

    def test_second_claim_already_claimed(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/claim?{self._qs(uid=OTHER_USER)}",
                          data={"Digits": "1"}, timeout=30)
        assert r.status_code == 200
        assert "already" in r.text and "claimed this lead" in r.text, r.text[:300]

    def test_answer_after_claim(self):
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/answer?{self._qs(uid=OTHER_USER)}", timeout=30)
        assert r.status_code == 200
        assert "claimed this lead" in r.text, r.text[:300]

    def test_status_callback_records(self):
        job = db.lead_call_jobs.find_one({"_id": STATE["job"]["_id"]})
        sid = next((c.get("call_sid") for c in job.get("calls", []) if c.get("call_sid")), None)
        if not sid:
            pytest.skip("no call_sid on job.calls (Twilio call was not placed in preview)")
        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/status?{self._qs()}",
                          data={"CallSid": sid, "CallStatus": "completed"}, timeout=30)
        assert r.status_code == 204, r.status_code
        job = db.lead_call_jobs.find_one({"_id": STATE["job"]["_id"]})
        entry = next(c for c in job["calls"] if c.get("call_sid") == sid)
        assert entry["status"] == "completed", entry


# ── 4. In-app claim stops dialing ────────────────────────────────────────────
class TestInAppClaim:
    def test_in_app_claim_stops_ladder(self, s):
        body = {"name": "Ladder QA2", "email": "ladder-qa2@invalid.imonsocial.test", "phone": "(500) 555-0167",
                "company": "QA Motors", "business_type": "Auto dealer", "message": "in app claim test",
                "source": "pricing_hero"}
        r = requests.post(f"{BASE_URL}/api/demo-requests", json=body, headers={"Origin": ORIGIN}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        demo = _wait(lambda: db.demo_requests.find_one({"email": body["email"], "conversation_id": {"$ne": None}}), 20)
        assert demo and demo.get("lead_source_id") == WEBSITE, demo
        conv_id = demo["conversation_id"]
        job = _wait(lambda: db.lead_call_jobs.find_one({"conversation_id": conv_id}), 20)
        assert job, "job not created for pricing_hero lead"
        STATE["job2"] = job

        c = s.post(f"{BASE_URL}/api/lead-sources/claim/{conv_id}?user_id={OTHER_USER}", timeout=30)
        assert c.status_code == 200, f"{c.status_code} {c.text[:300]}"
        assert c.json().get("success") is True

        job = _wait(lambda: db.lead_call_jobs.find_one({"_id": job["_id"], "status": "claimed"}), 10, 1)
        assert job, "job status not claimed after in-app claim"
        assert job["claimed_via"] == "app", job["claimed_via"]
        assert job["claimed_by"] == OTHER_USER

        r = requests.post(f"{BASE_URL}/api/webhooks/twilio/lead-call/answer?job={job['_id']}&u={TESTER}&t={job['token']}", timeout=30)
        assert "claimed this lead" in r.text, r.text[:300]


# ── 5. Exhaustion ────────────────────────────────────────────────────────────
class TestExhaustion:
    def test_single_attempt_ladder_exhausts(self):
        now = datetime.now(timezone.utc)
        doc = {"token": "qa-token", "conversation_id": STATE["conv_id"], "contact_id": None,
               "lead_source_id": WEBSITE, "source_name": "Website", "customer_phone": "+15005550168",
               "lead": {"name": "Exhaust QA", "source_label": "the Pricing page"},
               "attempts": [{"user_ids": [TESTER], "delay_seconds": 0}], "attempt_index": 0,
               "next_attempt_at": now - timedelta(minutes=1), "status": "active", "claimed_by": None,
               "calls": [], "created_at": now, "updated_at": now}
        jid = db.lead_call_jobs.insert_one(doc).inserted_id
        STATE["job3_id"] = jid
        job = _wait(lambda: db.lead_call_jobs.find_one({"_id": jid, "status": {"$ne": "active"}}), 35, 3)
        assert job, "job never processed"
        assert job["status"] == "exhausted", job["status"]
        assert job.get("calls"), "calls should be populated on the exhausted attempt"
        assert job["attempt_index"] == 1


# ── 6. Regression ────────────────────────────────────────────────────────────
class TestRegression:
    def test_get_lead_source_not_shadowed(self, s):
        r = s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("success") is True
        assert (d.get("lead_source") or d.get("source") or {}).get("name") == "Website" or d.get("name") == "Website"

    def test_list_lead_sources(self, s):
        r = s.get(f"{BASE_URL}/api/lead-sources?store_id={STORE}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json().get("lead_sources", r.json().get("sources")), list)

    def test_legacy_demo_without_lead_source(self, s):
        assert _put_wf(s, WEBSITE, dict(BASE_WF, website_default=False, website_pages=[])).status_code == 200
        try:
            body = {"name": "Ladder QA4", "email": "ladder-qa4@invalid.imonsocial.test", "phone": "(500) 555-0169",
                    "company": "QA Motors", "business_type": "Auto dealer", "message": "legacy path",
                    "source": "features_cta"}
            r = requests.post(f"{BASE_URL}/api/demo-requests", json=body, headers={"Origin": ORIGIN}, timeout=60)
            assert r.status_code == 200, r.text[:300]
            demo = _wait(lambda: db.demo_requests.find_one({"email": body["email"]}), 20)
            assert demo, "legacy demo request not stored"
            assert not demo.get("lead_source_id"), f"unexpected routing: {demo.get('lead_source_id')}"
            time.sleep(2)
            assert db.lead_call_jobs.find_one({"customer_phone": "+15005550169"}) is None
        finally:
            assert _put_wf(s, WEBSITE, BASE_WF).status_code == 200
            w = s.get(f"{BASE_URL}/api/lead-sources/{WEBSITE}/workflow", timeout=30).json()
            assert w["website_default"] is True and w["website_pages"] == ["pricing"]
            assert w["contact_mode"] == "text_and_call" and len(w["call_attempts"]) == 2
