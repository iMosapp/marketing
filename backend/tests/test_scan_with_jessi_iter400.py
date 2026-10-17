"""Iteration 400 (testing agent): Scan with Jessi (Phase B business cards) API - status/rollout, chunk upload (single + multi-part),
same-image reuse (no second model call), matches, save (ticked-only, rep edits win, additive phone/email, 409 on 2nd contact),
discard, cross-user isolation, Pause All, and a contact-files chunk/apply regression. Restores db.settings jessi_mms_vision."""
import base64
import os
import time
import uuid

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) QA-iter400"}
FIX = "/app/backend/tests/fixtures/scan"
FOREST = "69a0b7095fddcede09591667"
KEY = "jessi_mms_vision"
RESTORE = {"intelligence": "test_orgs", "replies": "off", "paused": False, "test_org_ids": ["69a907033b77512d1d8d8a08"]}

STATE = {}


@pytest.fixture(scope="module")
def mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, headers=UA, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    s = requests.Session()
    s.headers.update({**UA, "Authorization": f"Bearer {d.get('token') or d.get('access_token')}"})
    return s, str((d.get("user") or {}).get("_id") or (d.get("user") or {}).get("id"))


@pytest.fixture(scope="module")
def forest():
    s, _ = _login("forest@imosapp.com", "Admin123!")
    return s


@pytest.fixture(scope="module")
def tester():
    return _login("activation-tester@invalid.imonsocial.test", "NewPass123!")


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    made_contacts, t0 = [], time.time()
    STATE["contacts"] = made_contacts
    STATE["files"] = []
    yield
    mongo.settings.update_one({"key": KEY}, {"$set": RESTORE})
    for cid in made_contacts:
        mongo.contacts.delete_one({"_id": ObjectId(cid)})
        mongo.contact_events.delete_many({"contact_id": cid})
        mongo.contact_files.delete_many({"contact_id": cid})
    for fid in STATE["files"]:
        mongo.contact_files.delete_one({"_id": ObjectId(fid)})


def _b64(name):
    with open(f"{FIX}/{name}", "rb") as f:
        return base64.b64encode(f.read()).decode()


def _upload(s, uid, name, parts=1, capture="library"):
    data = _b64(name)
    up = "qa400" + uuid.uuid4().hex[:10]
    size = -(-len(data) // parts)
    last = None
    for i in range(parts):
        last = s.post(f"{API}/scan/{uid}/chunk", json={"upload_id": up, "index": i, "total": parts, "data": data[i * size:(i + 1) * size],
                                                         "name": name, "content_type": "image/png", "capture": capture}, timeout=120)
        if i < parts - 1:
            assert last.status_code == 200 and last.json()["received"] == i + 1, last.text
    if last.status_code == 200 and last.json().get("scan"):
        STATE["files"].append(last.json()["scan"]["id"])
    return last


def _contact(s, **kw):
    r = s.post(f"{API}/contacts/{FOREST}", json=kw, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json().get("_id") or r.json().get("id")
    STATE["contacts"].append(cid)
    return cid


# --- status / rollout ---
def test_status_enabled_for_forest_disabled_for_tester(forest, tester):
    r = forest.get(f"{API}/scan/{FOREST}/status")
    assert r.status_code == 200 and r.json() == {"enabled": True, "paused": False}, r.text
    ts, tid = tester
    r = ts.get(f"{API}/scan/{tid}/status")
    assert r.status_code == 200 and r.json()["enabled"] is False
    assert ts.get(f"{API}/scan/{FOREST}/status").status_code == 403


def test_chunk_forbidden_when_disabled_or_not_owner(tester):
    ts, tid = tester
    body = {"upload_id": "qa400x", "index": 0, "total": 1, "data": "aGk=", "name": "x.png", "content_type": "image/png"}
    assert ts.post(f"{API}/scan/{tid}/chunk", json=body).status_code == 403
    assert ts.post(f"{API}/scan/{FOREST}/chunk", json=body).status_code == 403


# --- upload + read + save to a new contact ---
def test_upload_card_new_reads_fields(forest, mongo):
    r = _upload(forest, FOREST, "card_new.png", parts=1, capture="library")
    assert r.status_code == 200, r.text
    sc = r.json()["scan"]
    assert sc["is_card"] is True and sc["scan_type"] == "business_card"
    f = sc["fields"]
    for k in ("first_name", "last_name", "company", "title", "phone", "phone_office", "email", "website"):
        assert f.get(k), f"missing {k}: {f}"
    assert "0142" in f["phone"] and "0188" in f["phone_office"]
    assert sc["summary"] and sc["confidence"] > 0.6 and sc["contact_id"] == ""
    assert isinstance(r.json()["matches"], list)
    doc = mongo.contact_files.find_one({"_id": ObjectId(sc["id"])})
    assert doc["contact_id"] == "" and doc["source"] == "scan" and doc["capture"] == "library"
    u = mongo.vision_usage.find_one({"file_id": sc["id"]})
    assert u and u["source"] == "scan_library" and u.get("analyzed") is True
    STATE["scan_new"] = sc


def test_reupload_same_card_multi_chunk_is_reused(forest, mongo):
    r = _upload(forest, FOREST, "card_new.png", parts=3, capture="camera")
    assert r.status_code == 200, r.text
    sc = r.json()["scan"]
    assert sc["reused"] is True and sc["fields"]["phone"] == STATE["scan_new"]["fields"]["phone"]
    u = mongo.vision_usage.find_one({"file_id": sc["id"]})
    assert u and u.get("cached") is True and u.get("analyzed") is False and u["source"] == "scan_camera"
    STATE["scan_dup"] = sc


def test_save_to_new_contact_ticked_only_and_additive_phone(forest, mongo):
    sc = STATE["scan_new"]
    f = sc["fields"]
    cid = _contact(forest, first_name=f["first_name"], last_name="QA Scan Test", phone="+1" + "".join(c for c in f["phone"] if c.isdigit())[-10:])
    r = forest.post(f"{API}/scan/{FOREST}/{sc['id']}/save",
                    json={"contact_id": cid, "fields": ["phone", "phone_office", "title", "website"], "values": {"title": "QA Edited Title", "company": "NotTicked Co"}})
    assert r.status_code == 200, r.text
    ap = r.json()["applied"]
    assert "phone" not in ap and "phone_office" in ap and ap["title"] == "QA Edited Title" and "company" not in ap
    c = mongo.contacts.find_one({"_id": ObjectId(cid)})
    assert c["occupation"] == "QA Edited Title" and not c.get("employer")
    nums = [p["number"] for p in c.get("phones") or []]
    assert any("0188" in n for n in nums) and not any("0142" in n for n in nums)
    assert [p for p in c["phones"] if "0188" in p["number"]][0]["label"] == "work"
    assert (c.get("personal_details") or {}).get("website")
    files = forest.get(f"{API}/contact-files/{FOREST}/contact/{cid}").json()
    rows = files.get("files") if isinstance(files, dict) else files
    assert any(x["id"] == sc["id"] for x in rows), files
    ev = [e["event_type"] for e in mongo.contact_events.find({"contact_id": cid})]
    assert "file_added" in ev and "file_applied" in ev
    assert mongo.contact_events.find_one({"contact_id": cid, "title": "Business card scanned with Jessi"})
    STATE["new_cid"] = cid


def test_save_same_scan_to_other_contact_409_and_delete_after_save_409(forest):
    other = _contact(forest, first_name="QA", last_name="Other400", phone="+15005550999")
    r = forest.post(f"{API}/scan/{FOREST}/{STATE['scan_new']['id']}/save", json={"contact_id": other, "fields": [], "values": {}})
    assert r.status_code == 409
    assert forest.delete(f"{API}/scan/{FOREST}/{STATE['scan_new']['id']}").status_code == 409


def test_save_to_invisible_or_missing_contact_404(forest):
    sid = STATE["scan_dup"]["id"]
    assert forest.post(f"{API}/scan/{FOREST}/{sid}/save", json={"contact_id": str(ObjectId()), "fields": []}).status_code == 404
    assert forest.post(f"{API}/scan/{FOREST}/{sid}/save", json={"contact_id": "bad", "fields": []}).status_code == 404


def test_other_user_cannot_touch_scan(tester):
    ts, tid = tester
    sid = STATE["scan_dup"]["id"]
    assert ts.get(f"{API}/scan/{tid}/{sid}").status_code == 404
    assert ts.delete(f"{API}/scan/{tid}/{sid}").status_code == 404
    assert ts.post(f"{API}/scan/{tid}/{sid}/save", json={"contact_id": str(ObjectId()), "fields": []}).status_code == 404
    assert ts.get(f"{API}/scan/{FOREST}/{sid}").status_code == 403


def test_discard_pending_scan(forest):
    sid = STATE["scan_dup"]["id"]
    assert forest.get(f"{API}/scan/{FOREST}/{sid}").status_code == 200
    r = forest.delete(f"{API}/scan/{FOREST}/{sid}")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert forest.get(f"{API}/scan/{FOREST}/{sid}").status_code == 404


# --- existing contact: matches + replace rules + email additive ---
def test_existing_card_matches_and_no_silent_overwrite(forest, mongo):
    cid = _contact(forest, first_name="Dale", last_name="Hutchins", phone="+15005550163", employer="Old Employer LLC", address_city="Boise",
                   email="dale.old@invalid.imonsocial.test")
    mongo.contacts.update_one({"_id": ObjectId(cid)}, {"$set": {"email_work": "dale.work@invalid.imonsocial.test"}})
    r = _upload(forest, FOREST, "card_existing.png", parts=2)
    assert r.status_code == 200, r.text
    d = r.json()
    sc = d["scan"]
    assert "0163" in sc["fields"].get("phone", ""), sc["fields"]
    m = [x for x in d["matches"] if x["id"] == cid]
    assert m, d["matches"]
    assert "same phone" in m[0]["why"] and "same name" in m[0]["why"]
    assert m[0]["current"]["company"] == "Old Employer LLC" and m[0]["current"]["address_city"] == "Boise"
    r = forest.post(f"{API}/scan/{FOREST}/{sc['id']}/save", json={"contact_id": cid, "fields": ["title", "address_street", "email", "phone"], "values": {}})
    assert r.status_code == 200, r.text
    ap = r.json()["applied"]
    assert "phone" not in ap and "email" in ap
    c = mongo.contacts.find_one({"_id": ObjectId(cid)})
    assert c["employer"] == "Old Employer LLC" and c["address_city"] == "Boise"
    assert c["email"] == "dale.old@invalid.imonsocial.test" and c["email_work"] == "dale.work@invalid.imonsocial.test"
    assert any("hutchins" in (e.get("value") or "").lower() for e in c.get("emails") or [])
    assert c.get("occupation") and c.get("address_street")
    assert c["phone"] == "+15005550163" and not any("0163" in (p.get("number") or "") for p in c.get("phones") or [])
    STATE["dale"] = cid


# --- Pause All ---
def test_pause_all_blocks_scan(forest, mongo):
    mongo.settings.update_one({"key": KEY}, {"$set": {"paused": True}})
    try:
        st = forest.get(f"{API}/scan/{FOREST}/status").json()
        assert st == {"enabled": False, "paused": True}
        r = forest.post(f"{API}/scan/{FOREST}/chunk", json={"upload_id": "qa400p", "index": 0, "total": 1, "data": "aGk=", "name": "x.png", "content_type": "image/png"})
        assert r.status_code == 403
    finally:
        mongo.settings.update_one({"key": KEY}, {"$set": RESTORE})
    assert forest.get(f"{API}/scan/{FOREST}/status").json()["enabled"] is True


def test_bad_chunk_400(forest):
    r = forest.post(f"{API}/scan/{FOREST}/chunk", json={"upload_id": "qa400b", "index": 3, "total": 1, "data": "aGk=", "name": "x.png"})
    assert r.status_code == 400


# --- regression: contact-files chunk + apply ---
def test_contact_files_chunk_apply_regression(forest, mongo):
    cid = _contact(forest, first_name="QA", last_name="Files400", phone="+15005550998")
    data = _b64("card_existing.png")
    r = forest.post(f"{API}/contact-files/{FOREST}/chunk", json={"upload_id": "qa400f" + uuid.uuid4().hex[:6], "index": 0, "total": 1, "data": data,
                                                                  "name": "card.png", "content_type": "image/png", "contact_id": cid, "hint": "business_card"}, timeout=120)
    assert r.status_code == 200, r.text
    fobj = r.json().get("file") or r.json()
    fid = fobj["id"]
    r = forest.post(f"{API}/contact-files/{FOREST}/{fid}/apply", json={"fields": ["company", "title"]})
    assert r.status_code == 200, r.text
    c = mongo.contacts.find_one({"_id": ObjectId(cid)})
    assert c.get("employer") and c.get("occupation")
    assert mongo.contact_events.find_one({"contact_id": cid, "event_type": "file_applied"})
