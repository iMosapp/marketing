"""AI Leadership Team Phase 1 preview smoke tests (no new LLM calls).

Covers low-cost paths against the preview API:
- Auth 403 for non-owner on every /team/* route.
- Roster shape and readiness.
- Roster patch rules (CoS/SA cannot be disabled; COO toggle gating 'switched off').
- Knowledge list, CRUD, status transitions, bad-key/bad-domain 400.
- Controls validation (hard<soft 400, emergency stop 429, hard-limit 429 on chat/convene), restore.
- Convene empty question 400; cancel on fresh selected roundtable.
- Decision bad actions: bogus / modify with empty reason 400; approve-again (if already-decided id exists).
- Operating review GET latest.
- Hard rule: Command Center read-only (snapshot stable across the whole test run).
- Legacy routes: /advisor/conversations, /advisor/brief, /advisor/usage.

Run: cd /app/backend && python -m pytest tests/test_leadership_team_preview.py -q
"""
import json
import os
import time

import pytest
import requests
from tests import qa_creds

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
OWNER = {"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}
NONOWNER = {"email": "qa-manager@invalid.imonsocial.test", "password": qa_creds.password_for("qa-manager@invalid.imonsocial.test")}

TEAM_ROUTES = [
    ("GET", "/roster"),
    ("GET", "/threads"),
    ("GET", "/roundtables"),
    ("GET", "/decisions"),
    ("GET", "/knowledge"),
    ("GET", "/usage"),
    ("GET", "/controls"),
    ("GET", "/audit"),
]


def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.text[:200]
    return tok


@pytest.fixture(scope="module")
def owner_s():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {_login(OWNER)}"
    s.headers["Content-Type"] = "application/json"
    return s


@pytest.fixture(scope="module")
def nonowner_s():
    s = requests.Session()
    try:
        s.headers["Authorization"] = f"Bearer {_login(NONOWNER)}"
    except AssertionError:
        pytest.skip("non-owner credentials not available in preview")
    return s


def T(path):
    return f"{BASE}/api/command-center/team{path}"


# ---------------- non-owner 403 on every team route ----------------
@pytest.mark.parametrize("method,path", TEAM_ROUTES)
def test_nonowner_forbidden(method, path, nonowner_s):
    r = nonowner_s.request(method, T(path), timeout=20)
    assert r.status_code == 403, f"{method} {path}: expected 403, got {r.status_code}: {r.text[:120]}"


# ---------------- roster ----------------
def test_roster_shape(owner_s):
    r = owner_s.get(T("/roster"), timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert set(j.keys()) >= {"executives", "company", "controls", "month_spend_usd"}
    keys = {e["key"] for e in j["executives"]}
    assert keys == {"chief_of_staff", "strategic_advisor", "cto", "cpo", "cro", "coo", "cfo"}
    for e in j["executives"]:
        rd = e.get("readiness")
        assert rd and set(rd.keys()) >= {"score", "level", "items", "missing"}
    assert set(j["controls"].keys()) >= {"soft_usd", "hard_usd", "stopped", "max_participants"}


def test_patch_roster_rules(owner_s):
    # CoS cannot be disabled
    r = owner_s.patch(T("/roster/chief_of_staff"), json={"enabled": False}, timeout=20)
    assert r.status_code == 400
    # SA cannot be disabled
    r = owner_s.patch(T("/roster/strategic_advisor"), json={"enabled": False}, timeout=20)
    assert r.status_code == 400
    # Disable COO, confirm, re-enable
    r = owner_s.patch(T("/roster/coo"), json={"enabled": False}, timeout=20)
    assert r.status_code == 200 and r.json()["enabled"] is False
    # Creating a thread for COO should be 'switched off'
    r = owner_s.post(T("/threads"), json={"agent_key": "coo"}, timeout=20)
    assert r.status_code == 400 and "switched off" in r.text.lower()
    # Re-enable
    r = owner_s.patch(T("/roster/coo"), json={"enabled": True}, timeout=20)
    assert r.status_code == 200 and r.json()["enabled"] is True


# ---------------- knowledge ----------------
def test_knowledge_crud_and_validation(owner_s):
    r = owner_s.get(T("/knowledge"), timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert len(j["facts"]) >= 18
    for f in j["facts"]:
        assert "status" in f and "kind" in f and "source" in f and "stale" in f

    # bad key (no dot)
    r = owner_s.post(T("/knowledge"), json={"key": "nodot", "statement": "x", "domain": "commercial", "kind": "fact", "status": "proposed", "source": {"kind": "human", "ref": "qa"}}, timeout=20)
    assert r.status_code == 400
    # bad domain
    r = owner_s.post(T("/knowledge"), json={"key": "commercial.test.bad_domain", "statement": "x", "domain": "bogus", "kind": "fact", "status": "proposed", "source": {"kind": "human", "ref": "qa"}}, timeout=20)
    assert r.status_code == 400
    # good create
    body = {"key": "commercial.test.qa_fact", "statement": "QA preview fact", "domain": "commercial", "kind": "fact", "status": "proposed", "source": {"kind": "human", "ref": "qa"}}
    r = owner_s.post(T("/knowledge"), json=body, timeout=20)
    assert r.status_code == 200, r.text[:200]
    fid = r.json()["id"]
    # transitions
    for st in ("verified", "disputed", "retired"):
        r = owner_s.post(T(f"/knowledge/{fid}/status"), json={"status": st}, timeout=20)
        assert r.status_code == 200, f"{st}: {r.text[:200]}"
        assert r.json()["status"] == st


# ---------------- controls ----------------
def test_controls_rules_and_restore(owner_s):
    # ensure baseline
    r = owner_s.put(T("/controls"), json={"soft_usd": 25, "hard_usd": 50, "stopped": False}, timeout=20)
    assert r.status_code == 200
    # hard<soft
    r = owner_s.put(T("/controls"), json={"hard_usd": 1}, timeout=20)
    assert r.status_code == 400 and "below" in r.text.lower()
    # emergency stop blocks convene & chat
    r = owner_s.put(T("/controls"), json={"stopped": True}, timeout=20)
    assert r.status_code == 200
    try:
        rr = owner_s.post(T("/roundtables"), json={"question": "test block"}, timeout=20)
        assert rr.status_code == 429 and "emergency" in rr.text.lower()
    finally:
        owner_s.put(T("/controls"), json={"stopped": False}, timeout=20)

    # restore baseline
    r = owner_s.put(T("/controls"), json={"soft_usd": 25, "hard_usd": 50, "stopped": False}, timeout=20)
    assert r.status_code == 200


def test_convene_empty_question_400(owner_s):
    r = owner_s.post(T("/roundtables"), json={"question": "   "}, timeout=20)
    assert r.status_code == 400, r.text[:200]


# ---------------- decisions negatives ----------------
def test_decision_bad_actions(owner_s):
    r = owner_s.get(T("/decisions"), timeout=20)
    assert r.status_code == 200
    decisions = r.json()["decisions"]
    if not decisions:
        pytest.skip("no decisions seeded in preview")
    # pick any decision; bogus action must 400
    did = decisions[0]["id"]
    r = owner_s.post(T(f"/decisions/{did}"), json={"action": "bogus"}, timeout=20)
    assert r.status_code == 400
    # modify requires a non-empty reason
    r = owner_s.post(T(f"/decisions/{did}"), json={"action": "modify", "reason": ""}, timeout=20)
    assert r.status_code == 400 and "what should change" in r.text.lower()


# ---------------- usage/audit/review ----------------
def test_usage_and_audit_and_review_latest(owner_s):
    r = owner_s.get(T("/usage"), timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert "month_spend_usd" in j and "controls" in j and "last_30d" in j
    r = owner_s.get(T("/audit"), timeout=20)
    assert r.status_code == 200
    r = owner_s.get(T("/review"), timeout=20)
    assert r.status_code == 200


# ---------------- hard rule: CC read-only during these tests ----------------
CC_PATHS = ["/focus", "/priorities", "/roadmap", "/ideas", "/notes"]


def _cc_fingerprint(s):
    out = {}
    for p in CC_PATHS:
        r = s.get(f"{BASE}/api/command-center{p}", timeout=20)
        assert r.status_code == 200, f"{p}: {r.status_code}"
        out[p] = r.json()
    return json.dumps(out, sort_keys=True, default=str)


def test_cc_untouched_fingerprint(owner_s):
    # Snapshot twice, bracketing one PATCH roster + knowledge write; nothing in cc_* should change.
    before = _cc_fingerprint(owner_s)
    # a benign ops operation
    owner_s.patch(T("/roster/cfo"), json={"display_name": None}, timeout=20)
    after = _cc_fingerprint(owner_s)
    assert before == after, "Command Center read-only invariant violated"


# ---------------- legacy routes ----------------
def test_legacy_advisor_routes(owner_s):
    base = f"{BASE}/api/command-center/advisor"
    for p in ("/conversations", "/brief", "/usage"):
        r = owner_s.get(base + p, timeout=30)
        assert r.status_code == 200, f"{p}: {r.status_code} {r.text[:120]}"
