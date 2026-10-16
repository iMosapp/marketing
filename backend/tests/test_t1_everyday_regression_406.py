"""T1 iteration 406: everyday-workflow regression after the contact-scope change (rep = activation-tester, manager = qa-manager,
super admin = forest). Self-cleaning (TEST_T1 contacts / campaigns / lead source). Texts go ONLY to +1500555XXXX numbers.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_t1_everyday_regression_406.py -v
"""
import base64
import json
import os
import struct
import uuid

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
S: dict = {"contacts": [], "campaigns": []}
STORE = "69a0b7095fddcede09591668"   # QA store (qa-manager, activation-tester)
_A = db.users.find_one({"email": "qa-sameorg-a@invalid.imonsocial.test"}, {"_id": 1})   # same-org demo (tests/seed_same_org_demo.py): rep A's Walt
WALT = str((db.contacts.find_one({"user_id": str(_A["_id"])}, {"_id": 1}) or {}).get("_id") or "") if _A else None


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {d['token']}"
    return s, str(d["user"].get("_id") or d["user"].get("id"))


@pytest.fixture(scope="module", autouse=True)
def accounts():
    S["rep"], S["rid"] = login("activation-tester@invalid.imonsocial.test", "NewPass123!")
    S["mgr"], S["mid"] = login("qa-manager@invalid.imonsocial.test", "Manager123!")
    S["adm"], S["aid"] = login("forest@imosapp.com", "Admin123!")
    yield
    for cid in S["campaigns"]:
        S["adm"].delete(f"{BASE}/campaigns/{S['mid']}/{cid}")
    if "camp_settings" in S:
        S["adm"].put(f"{BASE}/admin/stores/{STORE}/campaign-settings", json=S["camp_settings"])
    for coll in ("conversations", "messages", "voice_notes", "contact_events", "campaign_enrollments", "tasks", "contact_files"):
        db[coll].delete_many({"contact_id": {"$in": S["contacts"]}})
    db.contacts.delete_many({"_id": {"$in": [ObjectId(c) for c in S["contacts"] if ObjectId.is_valid(c)]}})
    db.contacts.delete_many({"first_name": {"$in": ["TEST_T1", "Pat"]}, "last_name": {"$in": ["Regression", "Testcase"]}})
    if S.get("src"):
        db.lead_sources.delete_one({"_id": ObjectId(S["src"])})


# --- contacts ---
def test_01_rep_creates_contact_and_reads_it():
    r = S["rep"].post(f"{BASE}/contacts/{S['rid']}", json={"first_name": "TEST_T1", "last_name": "Regression", "phone": "+15005550177", "notes": "T1 private note"})
    assert r.status_code == 200, r.text
    cid = r.json().get("_id") or r.json().get("id")
    S["contacts"].append(cid)
    S["cid"] = cid
    g = S["rep"].get(f"{BASE}/contacts/{S['rid']}/{cid}")
    assert g.status_code == 200 and g.json()["first_name"] == "TEST_T1" and "T1 private note" in str(g.json())


# --- voice note (chunked) ---
def _wav(seconds=1):
    n = 8000 * seconds
    return b"RIFF" + struct.pack("<I", 36 + n * 2) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16) + b"data" + struct.pack("<I", n * 2) + b"\x00\x00" * n


def test_02_voice_note_chunk_upload_and_list():
    data = base64.b64encode(_wav()).decode()
    r = S["rep"].post(f"{BASE}/voice-notes/{S['rid']}/{S['cid']}/chunk", json={"upload_id": "t1" + uuid.uuid4().hex[:8], "index": 0, "total": 1, "data": data,
                                                                                "content_type": "audio/wav", "duration": 1, "kind": "memo"}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    lst = S["rep"].get(f"{BASE}/voice-notes/{S['rid']}/{S['cid']}")
    assert lst.status_code == 200 and len(lst.json() if isinstance(lst.json(), list) else lst.json().get("notes", lst.json().get("voice_notes", []))) >= 1, lst.text[:300]


# --- scan with Jessi ---
def test_03_scan_with_jessi_status_and_upload():
    st = S["adm"].get(f"{BASE}/scan/{S['aid']}/status")
    assert st.status_code == 200, st.text
    assert st.json().get("enabled") is True, f"scan rollout disabled for forest: {st.json()}"
    data = base64.b64encode(open("/app/backend/tests/fixtures/scan/card_new.png", "rb").read()).decode()
    r = S["adm"].post(f"{BASE}/scan/{S['aid']}/chunk", json={"upload_id": "t1" + uuid.uuid4().hex[:8], "index": 0, "total": 1, "data": data, "name": "card_new.png",
                                                             "content_type": "image/png", "capture": "library"}, timeout=180)
    assert r.status_code == 200 and r.json()["scan"]["fields"].get("phone"), r.text[:300]
    sid = r.json()["scan"]["id"]
    assert S["adm"].get(f"{BASE}/scan/{S['aid']}/{sid}").status_code == 200
    S["adm"].delete(f"{BASE}/scan/{S['aid']}/{sid}")


# --- texting (500-555 only) ---
def test_04_conversation_and_send_text_to_test_number():
    r = S["rep"].post(f"{BASE}/messages/conversations/{S['rid']}", json={"contact_id": S["cid"]})
    assert r.status_code == 200, r.text[:300]
    conv = r.json().get("_id") or r.json().get("id")
    S["conv"] = conv
    cr = S["rep"].post(f"{BASE}/consent/contact/{S['cid']}", json={"scopes": ["requested_info", "transactional"], "method": "verbal_in_person"})
    assert cr.status_code == 200, cr.text[:300]
    m = S["rep"].post(f"{BASE}/messages/send/{S['rid']}/{conv}", json={"conversation_id": conv, "content": "T1 regression test text", "channel": "sms"}, timeout=60)
    # activation-tester has no organization in preview, so the sender policy (not the contact scope) refuses with 409 "unattributed"
    blocked_by_sender_policy = m.status_code == 409 and (m.json().get("detail") or {}).get("code") in ("unattributed", "no_number", "no_subaccount", "not_ready")
    assert m.status_code in (200, 201, 202) or blocked_by_sender_policy, m.text[:300]
    th = S["rep"].get(f"{BASE}/messages/thread/{conv}")
    assert th.status_code == 200 and (blocked_by_sender_policy or "T1 regression test text" in th.text)


# --- campaigns ---
def test_05_campaign_create_and_enroll_own_contact():
    # store managers need the store's managers_can_edit (off by default): switch it on for the QA store for this run, restored at teardown
    S["camp_settings"] = S["adm"].get(f"{BASE}/admin/stores/{STORE}/campaign-settings").json()
    assert S["adm"].put(f"{BASE}/admin/stores/{STORE}/campaign-settings", json={**S["camp_settings"], "managers_can_edit": True}).status_code == 200
    r = S["mgr"].post(f"{BASE}/campaigns/{S['mid']}", json={"name": "TEST_T1 Campaign", "type": "custom", "active": True,
                                                           "sequences": [{"step": 1, "delay_days": 1, "message_template": "Hi {first_name}", "channel": "sms"}]})
    assert r.status_code == 200, r.text[:300]
    camp = r.json().get("_id") or r.json().get("id")
    S["campaigns"].append(camp)
    own = S["mgr"].post(f"{BASE}/contacts/{S['mid']}", json={"first_name": "TEST_T1", "last_name": "Regression", "phone": "+15005550179"}).json()
    S["contacts"].append(own.get("_id") or own.get("id"))
    e = S["mgr"].post(f"{BASE}/campaigns/{S['mid']}/{camp}/enroll/{S['contacts'][-1]}")
    assert e.status_code == 200, e.text[:300]


def test_06_campaign_cannot_enroll_teammates_private_contact():
    if not WALT:
        pytest.skip("no same-org demo")
    camp = S["campaigns"][0]
    e = S["mgr"].post(f"{BASE}/campaigns/{S['mid']}/{camp}/enroll/{WALT}")
    assert e.status_code in (403, 404), e.text[:200]


# --- lead intake ---
def test_07_lead_intake_test_lead_creates_contact_and_conversation():
    store = STORE
    src = db.lead_sources.find_one({"store_id": store, "is_active": True})
    if not src:
        r = S["mgr"].post(f"{BASE}/lead-sources?store_id={store}", json={"name": "TEST_T1 Source", "team_id": store, "assignment_method": "jump_ball"})
        assert r.status_code == 200, f"cannot create lead source: {r.status_code} {r.text[:300]}"
        S["src"] = r.json().get("id") or r.json().get("_id") or (r.json().get("lead_source") or {}).get("id")
        src = {"_id": S["src"]}
    r = S["mgr"].post(f"{BASE}/lead-sources/{src['_id']}/test-lead", json={"phone": "5005550178", "first_name": "TEST_T1", "last_name": "Lead", "include_ladder": False}, timeout=90)
    assert r.status_code == 200, r.text[:400]
    c = db.contacts.find_one({"phone": {"$regex": "5005550178$"}}, sort=[("_id", -1)])
    assert c, "lead contact not created"
    S["contacts"].append(str(c["_id"]))
    assert db.conversations.find_one({"contact_id": str(c["_id"])}), "lead conversation not created"


# --- Jessi ---
def test_08_jessi_basic_and_contact_creation():
    r = S["rep"].post(f"{BASE}/jessie/chat", json={"user_id": S["rid"], "message": "What can you help me with today?", "include_voice": False}, timeout=120)
    assert r.status_code == 200 and (r.json().get("text") or r.json().get("response")), r.text[:300]
    r = S["rep"].post(f"{BASE}/jessie/chat", json={"user_id": S["rid"], "message": "add Pat Testcase, met him at NADA, his number is 500 555 0177", "include_voice": False}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    r = S["rep"].post(f"{BASE}/jessie/chat", json={"user_id": S["rid"], "message": "yes", "include_voice": False}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    c = db.contacts.find_one({"user_id": S["rid"], "first_name": "Pat", "last_name": "Testcase"})
    assert c, f"Jessi did not create Pat: {r.text[:300]}"
    S["contacts"].append(str(c["_id"]))
    assert "NADA" in json.dumps(c.get("how_we_met") or {}, default=str) + str(c.get("notes")), c.get("how_we_met")


# --- manager ---
def test_09_manager_team_view_and_rep_contact_voice_notes():
    tv = S["mgr"].get(f"{BASE}/team-view")
    assert tv.status_code == 200, tv.text[:300]
    g = S["mgr"].get(f"{BASE}/contacts/{S['rid']}/{S['cid']}")
    assert g.status_code == 200 and "T1 private note" in g.text, g.text[:200]
    v = S["mgr"].get(f"{BASE}/voice-notes/{S['rid']}/{S['cid']}")
    assert v.status_code == 200 and v.text not in ("[]", "{}"), v.text[:200]


def test_10_manager_bulk_transfer_preview_only():
    r = S["mgr"].get(f"{BASE}/admin/team/bulk-transfer/preview", params={"user_id": S["mid"], "from_user_id": S["rid"]})
    assert r.status_code == 200, r.text[:300]


# --- isolation spill-overs found by T1 ---
def test_11_cross_org_rep_cannot_create_task_on_foreign_contact():
    if not WALT:
        pytest.skip("no same-org demo")
    r = S["rep"].post(f"{BASE}/tasks/{S['rid']}", json={"title": "TEST_T1 probe", "contact_id": WALT, "type": "follow_up"})
    db.tasks.delete_many({"title": "TEST_T1 probe"})
    assert r.status_code in (403, 404), f"{r.status_code} {r.text[:200]}"


def test_12_merge_assessment_writes_nothing():
    before = [db[c].count_documents({}) for c in ("contacts", "conversations", "messages", "voice_notes")]
    r = S["adm"].get(f"{BASE}/admin/contact-merge-assessment", params={"confirm": "COUNTS_ONLY"}, timeout=120)
    assert r.status_code == 200
    assert before == [db[c].count_documents({}) for c in ("contacts", "conversations", "messages", "voice_notes")]
