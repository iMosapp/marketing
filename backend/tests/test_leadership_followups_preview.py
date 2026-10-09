"""AI Leadership Team Phase 1 FOLLOW-UPS preview smoke (Memory Lane / Export / Morning brief / Cron).

Low-cost: no real LLM calls, no new roundtables. Uses existing DECIDED roundtable
6ac92360a9cf5a18a65339cf and the existing roster. The ONE allowed real send
(POST /morning-brief/send) is NOT invoked here on purpose; it is exercised by
the main agent / interactive flow.

Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_leadership_followups_preview.py -q
"""
import os
import re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
OWNER = {"email": "forest@imosapp.com", "password": "Admin123!"}
NONOWNER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
WEBHOOK_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")
DECIDED_RT = "6ac92360a9cf5a18a65339cf"


def _login(c):
    r = requests.post(f"{BASE}/api/auth/login", json=c, timeout=20)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    assert tok
    return tok, j.get("user", {})


@pytest.fixture(scope="module")
def owner():
    tok, user = _login(OWNER)
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {tok}"
    s.headers["Content-Type"] = "application/json"
    return s, user


@pytest.fixture(scope="module")
def nonowner():
    tok, _ = _login(NONOWNER)
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {tok}"
    s.headers["Content-Type"] = "application/json"
    return s


# --- Non-owner 403 on new routes ---------------------------------------
NEW_ROUTES = [
    ("GET", f"/api/command-center/team/roster/cfo/history"),
    ("GET", f"/api/command-center/team/roundtables/{DECIDED_RT}/export.md"),
    ("GET", f"/api/command-center/team/roundtables/{DECIDED_RT}/export.pdf"),
    ("GET", f"/api/command-center/team/morning-brief"),
]


@pytest.mark.parametrize("method,path", NEW_ROUTES)
def test_nonowner_forbidden(nonowner, method, path):
    r = nonowner.request(method, f"{BASE}{path}", timeout=20)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text[:120]}"


def test_nonowner_put_morning_brief_forbidden(nonowner):
    r = nonowner.put(f"{BASE}/api/command-center/team/morning-brief", json={"hour": 7}, timeout=20)
    assert r.status_code == 403


# --- Roster memory + morning_brief block --------------------------------
def test_roster_has_memory_and_morning_brief(owner):
    s, _ = owner
    r = s.get(f"{BASE}/api/command-center/team/roster", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "morning_brief" in data
    mb = data["morning_brief"]
    assert "enabled" in mb and "hour" in mb
    execs = {e["key"]: e for e in data.get("executives", [])}
    for key in ("cfo", "cto", "strategic_advisor", "cpo", "cro", "coo", "chief_of_staff"):
        assert key in execs, f"missing exec {key}"
        mem = execs[key].get("memory")
        assert mem is not None, f"{key} missing memory"
        for f in ("roundtables", "dissents", "open_dissents", "devil_advocate",
                  "approved", "rejected", "deferred", "pending", "high_confidence",
                  "threads", "last_at"):
            assert f in mem, f"{key}.memory missing {f}"
    # chief_of_staff is all zeros
    cos = execs["chief_of_staff"]["memory"]
    for f in ("roundtables", "dissents", "open_dissents", "devil_advocate",
              "approved", "rejected", "deferred", "pending", "high_confidence", "threads"):
        assert cos[f] == 0, f"CoS memory.{f} = {cos[f]} expected 0"


# --- History endpoint ---------------------------------------------------
@pytest.mark.parametrize("key", ["cfo", "cto", "strategic_advisor"])
def test_roster_history(owner, key):
    s, _ = owner
    r = s.get(f"{BASE}/api/command-center/team/roster/{key}/history?limit=50", timeout=30)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    execv = data.get("executive")
    exec_key = execv.get("key") if isinstance(execv, dict) else execv
    assert exec_key == key
    assert "summary" in data
    entries = data.get("entries", [])
    assert isinstance(entries, list)
    for e in entries:
        for f in ("roundtable_id", "title", "status", "at", "devil_advocate",
                  "position", "confidence", "position_change", "challenges_raised",
                  "challenged_on", "dissents", "brief_recommendation", "decision"):
            assert f in e, f"entry missing {f}"
        assert isinstance(e["dissents"], list)
        for d in e["dissents"]:
            for df in ("id", "issue", "position", "resolved", "needs_founder", "raised"):
                assert df in d, f"dissent missing {df}"


def test_history_unknown_key_404(owner):
    s, _ = owner
    r = s.get(f"{BASE}/api/command-center/team/roster/bogus_exec/history", timeout=20)
    assert r.status_code == 404


def test_history_limit_clamp(owner):
    s, _ = owner
    # Over 100 should still 200 and clamp
    r = s.get(f"{BASE}/api/command-center/team/roster/cfo/history?limit=5000", timeout=20)
    assert r.status_code == 200
    # Below 1 should error or clamp - API spec says 1..100 capped
    r2 = s.get(f"{BASE}/api/command-center/team/roster/cfo/history?limit=0", timeout=20)
    assert r2.status_code in (200, 400, 422)


def test_history_cross_check_vs_roundtable(owner):
    s, _ = owner
    hist = s.get(f"{BASE}/api/command-center/team/roster/cfo/history?limit=100", timeout=20).json()
    entries = hist.get("entries", [])
    if not entries:
        pytest.skip("No cfo entries to cross-check")
    e = entries[0]
    rid = e["roundtable_id"]
    r = s.get(f"{BASE}/api/command-center/team/roundtables/{rid}", timeout=20)
    assert r.status_code == 200
    rt = r.json()
    assessments = rt.get("assessments", {})
    cfo_a = assessments.get("cfo") or {}
    rec = (cfo_a.get("data") or {}).get("recommendation")
    if rec and e.get("position"):
        assert rec == e["position"], f"cfo recommendation {rec!r} != history position {e['position']!r}"


# --- Export markdown / PDF ----------------------------------------------
def test_export_markdown(owner):
    s, _ = owner
    r = s.get(f"{BASE}/api/command-center/team/roundtables/{DECIDED_RT}/export.md", timeout=30)
    assert r.status_code == 200
    assert "text/markdown" in r.headers.get("Content-Type", "")
    cd = r.headers.get("Content-Disposition", "")
    assert "attachment" in cd
    assert re.search(r"roundtable-.*-5339cf\.md", cd), cd
    body = r.text
    assert body.startswith("# ")
    for section in ("## The question", "## Decision", "## The room",
                    "## Executive brief", "## Dissent register",
                    "## Independent assessments", "## Challenge round", "## Record"):
        assert section in body, f"missing section {section}"
    assert "**Approved** by Forest" in body


def test_export_pdf(owner):
    s, _ = owner
    r = s.get(f"{BASE}/api/command-center/team/roundtables/{DECIDED_RT}/export.pdf", timeout=60)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("Content-Type", "")
    assert r.content.startswith(b"%PDF-")
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) > 1, f"only {len(reader.pages)} page(s)"
    except ImportError:
        pass


def test_export_unknown_rid_404(owner):
    s, _ = owner
    r = s.get(f"{BASE}/api/command-center/team/roundtables/deadbeefdeadbeefdeadbeef/export.md", timeout=20)
    assert r.status_code == 404


def test_export_writes_audit(owner):
    s, _ = owner
    # trigger export
    s.get(f"{BASE}/api/command-center/team/roundtables/{DECIDED_RT}/export.md", timeout=30)
    r = s.get(f"{BASE}/api/command-center/team/audit?limit=50", timeout=20)
    assert r.status_code == 200
    items = r.json().get("entries") or r.json().get("items") or r.json()
    if isinstance(items, dict):
        items = items.get("entries") or items.get("items", [])
    actions = [i.get("action") for i in items]
    assert "roundtable_exported" in actions, f"audit missing roundtable_exported: {actions[:10]}"


# --- Morning brief settings ---------------------------------------------
def test_morning_brief_get_and_put(owner):
    s, user = owner
    r = s.get(f"{BASE}/api/command-center/team/morning-brief", timeout=20)
    assert r.status_code == 200
    # Starting state not asserted (prior runs may have left changes); we restore at end

    # Valid PUT -> enable + NYC 8am
    r = s.put(f"{BASE}/api/command-center/team/morning-brief",
              json={"enabled": True, "hour": 8, "timezone": "America/New_York"}, timeout=20)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert j.get("enabled") is True
    assert j.get("hour") == 8
    assert j.get("timezone") == "America/New_York"
    assert j.get("user_name") == "Forest" or (j.get("user_name") or "").lower().startswith("forest")
    assert j.get("user_id")
    ns = j.get("next_send")
    assert ns and "T" in ns, f"next_send not ISO: {ns}"
    # 08:05 NY local in UTC: NY is UTC-5 (standard) or UTC-4 (DST) -> UTC 12:05 or 13:05
    assert ":05:" in ns

    # Bad hour
    r = s.put(f"{BASE}/api/command-center/team/morning-brief", json={"hour": 25}, timeout=20)
    assert r.status_code == 400

    # Bad tz
    r = s.put(f"{BASE}/api/command-center/team/morning-brief", json={"timezone": "Mars/Olympus"}, timeout=20)
    assert r.status_code == 400

    # Restore to disabled first, then validate PUT {} -> 400 on disabled state
    s.put(f"{BASE}/api/command-center/team/morning-brief",
          json={"enabled": False, "hour": 7, "timezone": "America/Denver"}, timeout=20)
    r = s.put(f"{BASE}/api/command-center/team/morning-brief", json={}, timeout=20)
    assert r.status_code == 400, f"PUT {{}} should be 400, got {r.status_code}: {r.text[:120]}"
    assert "nothing to change" in r.text.lower()

    # Audit entry
    r = s.get(f"{BASE}/api/command-center/team/audit?limit=50", timeout=20)
    items = r.json().get("entries") or r.json().get("items") or []
    assert "morning_brief_updated" in [i.get("action") for i in items]

    # Restore
    r = s.put(f"{BASE}/api/command-center/team/morning-brief",
              json={"enabled": False, "hour": 7, "timezone": "America/Denver"}, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("enabled") is False and j.get("hour") == 7 and j.get("timezone") == "America/Denver"


# --- Cron webhook -------------------------------------------------------
CRON_URL = "/api/cron/leadership-morning-brief"


def test_cron_no_auth():
    r = requests.post(f"{BASE}{CRON_URL}", json={}, timeout=20)
    assert r.status_code == 401


def test_cron_wrong_bearer():
    r = requests.post(f"{BASE}{CRON_URL}", headers={"Authorization": "Bearer nope"}, json={}, timeout=20)
    assert r.status_code == 401


def test_cron_correct_bearer_bad_body():
    assert WEBHOOK_SECRET, "WEBHOOK_CRON_SECRET not set in env"
    r = requests.post(f"{BASE}{CRON_URL}",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}", "Content-Type": "application/json"},
                      data="not json", timeout=20)
    assert r.status_code == 400


def test_cron_correct_bearer_ok_and_duplicate():
    import uuid
    assert WEBHOOK_SECRET
    run_id = f"qa-run-{uuid.uuid4().hex[:8]}"
    headers = {
        "Authorization": f"Bearer {WEBHOOK_SECRET}",
        "Content-Type": "application/json",
        "X-Webhook-Id": run_id,
    }
    payload = {"event": "schedule.triggered", "run_id": run_id}
    r1 = requests.post(f"{BASE}{CRON_URL}", headers=headers, json=payload, timeout=30)
    assert r1.status_code == 200, r1.text[:200]
    j1 = r1.json()
    assert j1.get("ok") is True
    assert not j1.get("duplicate"), f"first call should not be duplicate: {j1}"

    r2 = requests.post(f"{BASE}{CRON_URL}", headers=headers, json=payload, timeout=30)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("duplicate") is True

    # Cleanup cron_runs doc
    try:
        from pymongo import MongoClient
        mc = MongoClient(os.environ["MONGO_URL"])
        db = mc[os.environ["DB_NAME"]]
        db["cron_runs"].delete_one({"_id": f"lt-morning-brief:{run_id}"})
        mc.close()
    except Exception:
        pass


# --- Hard rule: Command Center fingerprint stable -----------------------
def _cc_fingerprint(s):
    import hashlib, json as _json
    collections = ["blueprint", "priorities", "roadmap", "ideas", "notes"]
    out = {}
    for c in collections:
        r = s.get(f"{BASE}/api/command-center/{c}", timeout=20)
        if r.status_code == 200:
            out[c] = r.json()
    serialized = _json.dumps(out, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest(), out


def test_cc_fingerprint_stable(owner):
    s, _ = owner
    h1, _ = _cc_fingerprint(s)
    # Trigger follow-ups side-effects
    s.get(f"{BASE}/api/command-center/team/roster", timeout=20)
    s.get(f"{BASE}/api/command-center/team/roundtables/{DECIDED_RT}/export.md", timeout=30)
    s.put(f"{BASE}/api/command-center/team/morning-brief",
          json={"enabled": False, "hour": 7, "timezone": "America/Denver"}, timeout=20)
    h2, _ = _cc_fingerprint(s)
    assert h1 == h2, "Command Center collections changed by leadership follow-up operations"
