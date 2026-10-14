"""Phase 1B validation tests for Living Customer Intelligence."""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from datetime import datetime, timezone
from tests import qa_creds

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "imos-admin-test_database")

SARAH_ID = "6aa413008f0d53e3f2261853"
STORE_ID = "69a0b7095fddcede09591668"
REP_ID = "6a978d68b8673c29063aa8b9"
LEAD_SOURCE_WEBHOOK = "69a787ca70ae63ea0ac69251"

CREDS = {
    "forest": ("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com")),
    "manager": ("qa-manager@invalid.imonsocial.test", qa_creds.password_for("qa-manager@invalid.imonsocial.test")),
    "rep": ("activation-tester@invalid.imonsocial.test", qa_creds.password_for("activation-tester@invalid.imonsocial.test")),
    "orgadmin": ("qa-orgadmin@invalid.imonsocial.test", qa_creds.password_for("qa-orgadmin@invalid.imonsocial.test")),
}

_tokens = {}


def login(role):
    if role in _tokens:
        return _tokens[role]
    email, password = CREDS[role]
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {role}: {r.status_code} {r.text}"
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    assert tok, f"no token for {role}: {d}"
    _tokens[role] = tok
    return tok


def H(role):
    return {"Authorization": f"Bearer {login(role)}"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


# ---- 1. config
def test_1_config_forest():
    r = requests.get(f"{BASE}/api/intel/config", headers=H("forest"), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    print("config:", d)
    flags = d.get("flags", {})
    assert flags.get("ingest") is True
    assert flags.get("legacy_projection") is True
    assert flags.get("backfill_execute") is True
    assert d.get("phase") in ("1A", "1B")
    assert d.get("settings", {}).get("intent_window_days") == 45


# ---- 2. Sarah facts/state/brief
def test_2_sarah_facts_rep():
    r = requests.get(f"{BASE}/api/intel/contacts/{SARAH_ID}/facts", headers=H("rep"), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("can_verify") is True
    facts = d.get("facts", [])
    assert len(facts) > 0
    required = {"id", "key", "layer", "status", "statement", "value", "occurred_at", "source", "confidence", "confirmations"}
    missing = required - set(facts[0].keys())
    assert not missing, f"fact missing keys: {missing}; got {facts[0]}"


def test_2_sarah_state():
    r = requests.get(f"{BASE}/api/intel/contacts/{SARAH_ID}/state", headers=H("rep"), timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ("identity", "current_state", "history", "active_intent", "driving", "needs_verification", "counts"):
        assert k in d, f"state missing {k}"


def test_2_sarah_brief():
    r = requests.get(f"{BASE}/api/intel/contacts/{SARAH_ID}/brief", headers=H("rep"), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    who = d.get("who", {})
    owns = who.get("owns", [])
    assert len(owns) > 0
    # Sarah is shared QA data (appraisal suites trade / add her vehicles); assert the invariant, not one specific truck
    verified_owned = [o for o in owns if (o.get("confirmations", 0) or 0) >= 1]
    appraisal_unconfirmed = [o for o in owns if "per appraisal" in (o.get("statement", "") or "").lower() and (o.get("confirmations", 0) or 0) == 0]
    assert verified_owned, f"missing a verified ownership fact; owns={[o.get('statement') for o in owns]}"
    assert appraisal_unconfirmed, f"missing appraisal unconfirmed; owns={owns}"
    # history is not in who.*
    for section in ("owns", "drives", "wants"):
        for item in who.get(section, []) or []:
            assert item.get("status") != "historical", f"historical in who.{section}"
    verify = d.get("verify", [])
    assert any(v.get("unverified") is True for v in verify), "verify missing unverified items"
    assert d.get("discuss", {}).get("topic") is not None
    assert d.get("discuss", {}).get("opening") is not None
    assert d.get("next", {}).get("action") is not None
    assert "evidence" in d


# ---- 3. Permissions
def test_3_manager_can_access_sarah():
    for ep in (f"/api/intel/contacts/{SARAH_ID}/facts", f"/api/intel/contacts/{SARAH_ID}/state", f"/api/intel/contacts/{SARAH_ID}/brief"):
        r = requests.get(f"{BASE}{ep}", headers=H("manager"), timeout=30)
        assert r.status_code == 200, f"{ep}: {r.status_code} {r.text}"


def test_3_orgadmin_cannot_see_sarah():
    for ep in (f"/api/intel/contacts/{SARAH_ID}/facts", f"/api/intel/contacts/{SARAH_ID}/state", f"/api/intel/contacts/{SARAH_ID}/brief"):
        r = requests.get(f"{BASE}{ep}", headers=H("orgadmin"), timeout=30)
        assert r.status_code == 404, f"{ep} expected 404 got {r.status_code} {r.text}"


def test_3_backfill_dryrun_orgadmin():
    r = requests.get(f"{BASE}/api/intel/backfill/dry-run", headers=H("orgadmin"), timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    print("orgadmin dry-run:", d)
    assert d.get("contacts_scanned", -1) == 0


def test_3_backfill_dryrun_manager():
    r = requests.get(f"{BASE}/api/intel/backfill/dry-run", headers=H("manager"), timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    print("manager dry-run:", d)
    cs = d.get("contacts_scanned", 0)
    assert 20 <= cs <= 50, f"contacts_scanned={cs}"
    assert "flags" in d


def test_3_backfill_dryrun_rep_forbidden():
    r = requests.get(f"{BASE}/api/intel/backfill/dry-run", headers=H("rep"), timeout=30)
    assert r.status_code == 403, r.text


def test_3_backfill_runs_rep_forbidden():
    r = requests.get(f"{BASE}/api/intel/backfill/runs", headers=H("rep"), timeout=30)
    assert r.status_code == 403


def test_3_backfill_runs_manager():
    r = requests.get(f"{BASE}/api/intel/backfill/runs", headers=H("manager"), timeout=30)
    assert r.status_code == 200
    d = r.json()
    runs = d.get("runs", [])
    assert isinstance(runs, list)
    for run in runs:
        assert "mode" in run and "started_at" in run


def test_3_projection_snapshots_manager():
    r = requests.get(f"{BASE}/api/intel/projection/snapshots", headers=H("manager"), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("contacts_projected", 0) >= 8
    assert "flags" in d


# ---- 4. Backfill execute guards + idempotency
def test_4_backfill_execute_rep_forbidden():
    r = requests.post(f"{BASE}/api/intel/backfill/execute", headers=H("rep"), json={"confirm": "EXECUTE"}, timeout=30)
    assert r.status_code == 403


def test_4_backfill_execute_manager_forbidden():
    r = requests.post(f"{BASE}/api/intel/backfill/execute", headers=H("manager"), json={"confirm": "EXECUTE"}, timeout=30)
    assert r.status_code == 403, r.text


def test_4_backfill_execute_forest_bad_confirm():
    r = requests.post(f"{BASE}/api/intel/backfill/execute", headers=H("forest"), json={"confirm": "nope"}, timeout=30)
    assert r.status_code == 403, r.text
    assert "EXECUTE" in r.text


def test_4_backfill_execute_idempotent():
    # count before
    r_pre = requests.get(f"{BASE}/api/intel/contacts/{SARAH_ID}/facts", headers=H("rep"), timeout=30)
    pre_count = len(r_pre.json().get("facts", []))

    r = requests.post(f"{BASE}/api/intel/backfill/execute", headers=H("forest"),
                      json={"confirm": "EXECUTE", "batch": 1000}, timeout=180)
    assert r.status_code == 200, r.text
    d = r.json()
    print("backfill execute:", d)
    assert d.get("facts_written_total", -1) == 0, f"expected 0 facts_written_total got {d}"
    assert d.get("reaffirmed_total", -1) == 0
    assert d.get("duplicates_total", 0) > 100
    assert d.get("done") is True
    assert d.get("projection") is True

    r_post = requests.get(f"{BASE}/api/intel/contacts/{SARAH_ID}/facts", headers=H("rep"), timeout=30)
    post_count = len(r_post.json().get("facts", []))
    assert pre_count == post_count, f"Sarah fact count changed {pre_count} -> {post_count}"


# ---- 5. Rollback guards
def test_5_rollback_manager_forbidden():
    r = requests.post(f"{BASE}/api/intel/projection/rollback", headers=H("manager"), json={"confirm": "ROLLBACK"}, timeout=30)
    assert r.status_code == 403


def test_5_rollback_forest_bad_confirm():
    r = requests.post(f"{BASE}/api/intel/projection/rollback", headers=H("forest"), json={"confirm": "nope"}, timeout=30)
    assert r.status_code == 400, r.text
    assert "ROLLBACK" in r.text


# ---- 6. Live event e2e
@pytest.fixture(scope="module")
def throwaway_contact(db):
    from bson import ObjectId
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "first_name": "Quinn",
        "last_name": "QA-IntelTest",
        "phone": "+15005550791",
        "email": "quinn.intel@invalid.imonsocial.test",
        "user_id": REP_ID,
        "store_id": STORE_ID,
        "status": "active",
        "tags": ["QA Intel Test"],
        "personal_details": {},
        "purchase_history": [],
        "created_at": now,
        "updated_at": now,
    }
    db.contacts.insert_one(doc)
    cid = str(doc["_id"])
    print(f"Created throwaway contact {cid}")
    yield cid
    # cleanup
    created_ids = set()
    created_ids.add(cid)
    for c in db.contacts.find({"tags": "QA Intel Test"}):
        created_ids.add(str(c["_id"]))
    for cc in created_ids:
        db.contacts.delete_many({"_id": ObjectId(cc)})
        db.contact_facts.delete_many({"contact_id": cc})
        db.contact_fact_events.delete_many({"contact_id": cc})
        db.intel_legacy_snapshots.delete_many({"contact_id": cc})
        db.inbound_leads.delete_many({"contact_id": cc})
        db.conversations.delete_many({"contact_id": cc})
        db.messages.delete_many({"contact_id": cc})
        db.contact_events.delete_many({"contact_id": cc})
        db.tasks.delete_many({"contact_id": cc})
        db.notifications.delete_many({"contact_id": cc})
    print(f"Cleaned up {len(created_ids)} contacts")


def test_6a_lead_webhook_ingest(throwaway_contact, db):
    from bson import ObjectId
    cid = throwaway_contact
    body = {
        "first_name": "Quinn", "last_name": "QA-IntelTest",
        "phone": "+15005550791", "email": "quinn.intel@invalid.imonsocial.test",
        "comments": "Pricing on the Tundra please",
        "vehicle_interest": "2025 Toyota Tundra",
        "make": "Toyota", "model": "Tundra", "year": 2025,
    }
    r = requests.post(f"{BASE}/api/leads/webhook/{LEAD_SOURCE_WEBHOOK}", json=body, timeout=60)
    assert r.status_code == 200, r.text
    print("webhook1:", r.json())
    time.sleep(3)
    # Check which contact got it
    matched_cid = cid
    doc = db.contacts.find_one({"_id": ObjectId(cid)})
    vi = (doc or {}).get("vehicle_interest", "")
    if "Tundra" not in str(vi):
        # maybe webhook created a new one
        new_c = db.contacts.find_one({"phone": "+15005550791", "_id": {"$ne": ObjectId(cid)}}, sort=[("created_at", -1)])
        if new_c:
            matched_cid = str(new_c["_id"])
            new_c.setdefault("tags", [])
            if "QA Intel Test" not in new_c["tags"]:
                db.contacts.update_one({"_id": new_c["_id"]}, {"$addToSet": {"tags": "QA Intel Test"}})
            print(f"WEBHOOK CREATED NEW CONTACT: {matched_cid} (expected to match {cid})")
            doc = new_c
    assert doc, "no contact doc"
    assert "Tundra" in str(doc.get("vehicle_interest", "")), f"vehicle_interest={doc.get('vehicle_interest')}"
    assert doc.get("intel_projected_at") is not None, "intel_projected_at not set"

    r2 = requests.get(f"{BASE}/api/intel/contacts/{matched_cid}/brief", headers=H("rep"), timeout=30)
    assert r2.status_code == 200, r2.text
    brief = r2.json()
    driving = brief.get("now", {}).get("driving") or {}
    assert "Tundra" in str(driving.get("label", "")), f"driving={driving}"
    src = driving.get("source") or {}
    assert src.get("kind") == "lead_form", f"source={src}"
    opening = brief.get("discuss", {}).get("opening", "")
    assert "Tundra" in str(opening), f"opening={opening}"
    # stash matched_cid for later tests
    pytest.matched_contact_id = matched_cid


def test_6b_personal_details_edit(db):
    from bson import ObjectId
    cid = getattr(pytest, "matched_contact_id", None)
    assert cid, "no matched contact id"
    body = {"personal_details": {"spouse_name": "Avery", "interests": ["hiking", "golf"]}}
    r = requests.patch(f"{BASE}/api/contacts/{REP_ID}/{cid}/personal-details",
                       headers=H("rep"), json=body, timeout=30)
    assert r.status_code == 200, r.text
    time.sleep(2)
    r2 = requests.get(f"{BASE}/api/intel/contacts/{cid}/facts", headers=H("rep"), timeout=30)
    facts = r2.json().get("facts", [])
    spouse = [f for f in facts if f.get("key") == "family.spouse"]
    assert spouse, f"no family.spouse fact; facts keys={[f.get('key') for f in facts]}"
    sv = spouse[0]
    val = sv.get("value") or {}
    assert "Avery" in str(val) or "Avery" in str(sv.get("statement", "")), f"spouse fact={sv}"
    assert (sv.get("source") or {}).get("kind") == "rep", f"spouse source={sv.get('source')}"
    assert sv.get("status") == "current"
    assert (sv.get("confirmations") or 0) >= 1
    interests = [f for f in facts if f.get("key") == "preference.interest"]
    assert len(interests) >= 2, f"interests count {len(interests)}"
    # contact doc shape
    doc = db.contacts.find_one({"_id": ObjectId(cid)})
    pd = doc.get("personal_details") or {}
    assert pd.get("spouse_name") == "Avery", pd
    pd_interests = pd.get("interests") or []
    assert all(isinstance(x, str) for x in pd_interests), f"interests not strings: {pd_interests}"
    assert set(pd_interests) >= {"hiking", "golf"}, pd_interests


def test_6c_suggest_employer(db):
    from bson import ObjectId
    cid = getattr(pytest, "matched_contact_id", None)
    assert cid
    body = {"key": "work.employer", "statement": "Employer: Acme Tools",
            "value": {"label": "Acme Tools"}, "layer": "state", "domain": "work"}
    r = requests.post(f"{BASE}/api/intel/contacts/{cid}/facts/suggest",
                      headers=H("rep"), json=body, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    print("suggest:", d)
    assert d.get("action") == "created"
    assert d.get("as_verifier") is True
    fact = d.get("fact") or {}
    assert fact.get("status") == "current"
    pytest.employer_fact_id = fact.get("id")
    time.sleep(1)
    doc = db.contacts.find_one({"_id": ObjectId(cid)})
    assert (doc.get("personal_details") or {}).get("employer") == "Acme Tools", doc.get("personal_details")


def test_6d_suggest_as_orgadmin_forbidden():
    cid = getattr(pytest, "matched_contact_id", None)
    assert cid
    body = {"key": "work.employer", "statement": "Employer: Wrong Corp",
            "value": {"label": "Wrong Corp"}, "layer": "state", "domain": "work"}
    r = requests.post(f"{BASE}/api/intel/contacts/{cid}/facts/suggest",
                      headers=H("orgadmin"), json=body, timeout=30)
    assert r.status_code == 404, f"got {r.status_code}: {r.text}"


def test_6e_dispute_and_events_and_confirm():
    fid = getattr(pytest, "employer_fact_id", None)
    assert fid
    r = requests.post(f"{BASE}/api/intel/facts/{fid}/dispute", headers=H("rep"),
                      json={"note": "wrong company"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("fact", {}).get("status") == "disputed"
    r2 = requests.get(f"{BASE}/api/intel/facts/{fid}/events", headers=H("rep"), timeout=30)
    assert r2.status_code == 200
    events = r2.json().get("events", [])
    actions = [e.get("action") for e in events]
    assert "created" in actions, f"actions={actions}"
    assert "status_disputed" in actions, f"actions={actions}"
    for e in events:
        assert e.get("actor") or e.get("actor_name") or e.get("actor_id"), f"event missing actor: {e}"
    r3 = requests.post(f"{BASE}/api/intel/facts/{fid}/confirm", headers=H("manager"), json={}, timeout=30)
    assert r3.status_code == 200, r3.text
    fact = r3.json().get("fact", {})
    assert fact.get("status") == "current"
    assert fact.get("confidence") == "high"


def test_6f_duplicate_webhook_no_new_fact(db):
    cid = getattr(pytest, "matched_contact_id", None)
    assert cid
    r_pre = requests.get(f"{BASE}/api/intel/contacts/{cid}/facts", headers=H("rep"), timeout=30)
    pre_vi = [f for f in r_pre.json().get("facts", []) if f.get("key") == "vehicle.interest"]
    pre_count = len(pre_vi)
    body = {
        "first_name": "Quinn", "last_name": "QA-IntelTest",
        "phone": "+15005550791", "email": "quinn.intel@invalid.imonsocial.test",
        "comments": "Pricing on the Tundra please",
        "vehicle_interest": "2025 Toyota Tundra",
        "make": "Toyota", "model": "Tundra", "year": 2025,
    }
    r = requests.post(f"{BASE}/api/leads/webhook/{LEAD_SOURCE_WEBHOOK}", json=body, timeout=60)
    assert r.status_code == 200, r.text
    time.sleep(3)
    r_post = requests.get(f"{BASE}/api/intel/contacts/{cid}/facts", headers=H("rep"), timeout=30)
    post_vi = [f for f in r_post.json().get("facts", []) if f.get("key") == "vehicle.interest"]
    post_count = len(post_vi)
    assert post_count == pre_count, f"vehicle.interest facts increased {pre_count} -> {post_count}"


# ---- 7. Legacy regression
def test_7_legacy_contact_shape():
    r = requests.get(f"{BASE}/api/contacts/{REP_ID}/{SARAH_ID}", headers=H("rep"), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("first_name") == "Sarah"
    pd = d.get("personal_details") or {}
    assert pd.get("occupation") == "Fleet Sales Manager", pd
    assert pd.get("employer") == "Rocky Mountain Kubota", pd
    assert pd.get("vehicle_purchased"), pd  # projected from a confirmed ownership fact (never blanked)
    interests = pd.get("interests") or []
    assert all(isinstance(x, str) for x in interests), interests
    # the legacy contact response keeps its exact shape on purpose (no new keys); the marker lives in Mongo only


def test_7_legacy_personal_details_endpoint():
    r = requests.get(f"{BASE}/api/contacts/{REP_ID}/{SARAH_ID}/personal-details", headers=H("rep"), timeout=30)
    assert r.status_code == 200, r.text
