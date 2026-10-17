"""Iteration 401 (testing agent): Scan with Jessi Phase C - documents (quote/service) doc_type, key dates, suggested rep reminders
(scan sheet save + contact Files reminders endpoint), company matches, sensitive docs, and 'use a Files photo as profile photo'
(+ photos/all Files section). Cleans up every QA contact / task / file it makes."""
import base64
import os
import sys
import uuid
from datetime import date

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) QA-iter401"}
FIX = "/app/backend/tests/fixtures/scan"
FOREST = "69a0b7095fddcede09591667"
S = {"contacts": [], "files": []}


@pytest.fixture(scope="module")
def mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def forest():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, headers=UA, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    s = requests.Session()
    s.headers.update({**UA, "Authorization": f"Bearer {d.get('token') or d.get('access_token')}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    yield
    for cid in S["contacts"]:
        mongo.contacts.delete_one({"_id": ObjectId(cid)})
        mongo.contact_events.delete_many({"contact_id": cid})
        mongo.contact_files.delete_many({"contact_id": cid})
        mongo.tasks.delete_many({"contact_id": cid})
    for fid in S["files"]:
        mongo.contact_files.delete_one({"_id": ObjectId(fid)})


def _b64(name):
    with open(f"{FIX}/{name}", "rb") as f:
        return base64.b64encode(f.read()).decode()


def _contact(s, **kw):
    r = s.post(f"{API}/contacts/{FOREST}", json=kw, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json().get("_id") or r.json().get("id")
    S["contacts"].append(cid)
    return cid


def _scan(s, name, mode="document"):
    r = s.post(f"{API}/scan/{FOREST}/chunk", json={"upload_id": "qa401" + uuid.uuid4().hex[:10], "index": 0, "total": 1, "data": _b64(name),
                                                    "name": name, "content_type": "image/png", "capture": "library", "mode": mode}, timeout=150)
    assert r.status_code == 200, r.text
    S["files"].append(r.json()["scan"]["id"])
    return r.json()


def _file(s, cid, name, hint="document"):
    r = s.post(f"{API}/contact-files/{FOREST}/chunk", json={"upload_id": "qa401f" + uuid.uuid4().hex[:8], "index": 0, "total": 1, "data": _b64(name),
                                                             "name": name, "content_type": "image/png", "contact_id": cid, "hint": hint}, timeout=150)
    assert r.status_code == 200, r.text
    return r.json()["file"]


# --- scan sheet: document mode on a quote ---
def test_quote_document_scan_and_company_match(forest):
    co = _contact(forest, first_name="QA", last_name="CoMatch401", phone="+15005550911", employer="Hutchins Ag Supply")
    d = _scan(forest, "quote.png")
    sc = d["scan"]
    assert sc["is_card"] is False and sc["doc_type"] == "quote" and sc["doc_label"] == "Quote", sc
    assert any(x["what"] == "expires" and x["date"] == "2026-11-13" for x in sc["dates"]), sc["dates"]
    rem = {r["key"]: r for r in sc["reminders"]}
    assert "expires_2026-11-13" in rem, sc["reminders"]
    assert rem["expires_2026-11-13"]["due"] == "2026-11-10"
    assert rem["expires_2026-11-13"]["title"] == "Follow up before the quote expires Nov 13"
    m = [x for x in d["matches"] if x["id"] == co]
    assert m and "same company" in m[0]["why"], d["matches"]
    S["quote"] = sc


def test_card_mode_still_reads_cards(forest):
    sc = _scan(forest, "card_new.png", mode="card")["scan"]
    assert sc["is_card"] is True and sc["scan_type"] == "business_card" and sc["fields"].get("phone")


def test_save_quote_with_reminders_creates_tasks_idempotent(forest, mongo):
    sc = S["quote"]
    cid = _contact(forest, first_name="QA", last_name="Quote401", phone="+15005550912")
    r = forest.post(f"{API}/scan/{FOREST}/{sc['id']}/save", json={"contact_id": cid, "fields": [], "values": {}, "reminders": ["expires_2026-11-13", "bogus_2026-01-01"]})
    assert r.status_code == 200, r.text
    rems = r.json()["reminders"]
    assert len(rems) == 1 and rems[0]["key"] == "expires_2026-11-13" and rems[0]["status"] == "created"
    tasks = list(mongo.tasks.find({"contact_id": cid}))
    assert len(tasks) == 1
    t = tasks[0]
    assert t["source"] == "jessi_scan" and t["type"] == "follow_up" and t["user_id"] == FOREST and t["has_time"] is False
    assert t["due_date"].strftime("%Y-%m-%d %H:%M") == "2026-11-10 15:00"
    assert mongo.contact_events.find_one({"contact_id": cid, "event_type": "task_created"})
    assert mongo.contact_events.find_one({"contact_id": cid, "event_type": "file_added", "title": "Quote scanned with Jessi"})
    r2 = forest.post(f"{API}/scan/{FOREST}/{sc['id']}/save", json={"contact_id": cid, "fields": [], "reminders": ["expires_2026-11-13"]})
    assert r2.status_code == 200 and r2.json().get("already_saved") is True
    assert mongo.tasks.count_documents({"contact_id": cid}) == 1


def test_private_scan_has_no_matches_or_reminders(forest, mongo):
    d = _scan(forest, "quote.png")
    sid = d["scan"]["id"]
    mongo.contact_files.update_one({"_id": ObjectId(sid)}, {"$set": {"sensitive": True}})
    g = forest.get(f"{API}/scan/{FOREST}/{sid}").json()
    assert g["matches"] == [] and g["scan"]["reminders"] == [] and g["scan"]["dates"] == [] and g["scan"]["summary"] == ""


# --- contact Files: service paper + reminders endpoint ---
def test_files_service_doc_and_reminder_create_idempotent(forest, mongo):
    cid = _contact(forest, first_name="QA", last_name="Service401", phone="+15005550913")
    f = _file(forest, cid, "service.png")
    assert f["doc_type"] == "service", f
    assert [(x["what"], x["date"]) for x in f["dates"]] == [("appointment", "2026-11-05")], f["dates"]
    assert [(x["key"], x["due"]) for x in f["reminders"]] == [("appointment_2026-11-05", "2026-11-05")]
    u = f"{API}/contact-files/{FOREST}/{f['id']}/reminders"
    r1 = forest.post(u, json={"key": "appointment_2026-11-05"})
    assert r1.status_code == 200, r1.text
    tid = r1.json()["reminder"]["task_id"]
    assert tid and r1.json()["file"]["reminders"][0]["status"] == "created"
    r2 = forest.post(u, json={"key": "appointment_2026-11-05"})
    assert r2.status_code == 200 and r2.json()["reminder"]["task_id"] == tid
    assert mongo.tasks.count_documents({"contact_id": cid, "source": "jessi_scan"}) == 1
    r3 = forest.post(u, json={"key": "nope_2026-11-05"})
    assert r3.status_code == 400 and r3.json()["detail"] == "That reminder is no longer available"
    S["svc"] = (cid, f)


def test_files_reminder_dismiss_hides_for_good(forest, mongo):
    cid = _contact(forest, first_name="QA", last_name="Dismiss401", phone="+15005550914")
    f = _file(forest, cid, "quote.png")
    assert any(x["key"] == "expires_2026-11-13" for x in f["reminders"]), f["reminders"]
    r = forest.post(f"{API}/contact-files/{FOREST}/{f['id']}/reminders", json={"key": "expires_2026-11-13", "decision": "dismiss"})
    assert r.status_code == 200 and r.json()["reminder"]["status"] == "dismissed"
    assert not any(x["key"] == "expires_2026-11-13" for x in r.json()["file"]["reminders"])
    g = forest.get(f"{API}/contact-files/{FOREST}/{f['id']}").json()
    assert not any(x["key"] == "expires_2026-11-13" for x in g["reminders"])
    assert forest.post(f"{API}/contact-files/{FOREST}/{f['id']}/reminders", json={"key": "expires_2026-11-13"}).status_code == 400
    assert mongo.tasks.count_documents({"contact_id": cid}) == 0
    S["dismiss"] = (cid, f)


def test_past_dates_not_suggested_unit():
    sys.path.insert(0, "/app/backend")
    from services import doc_reminders as dr
    doc = {"doc_type": "quote", "dates": [{"what": "expires", "date": "2026-10-01", "label": "Expires"},
                                          {"what": "expires", "date": "2026-10-17", "label": "Expires"}]}
    out = dr.suggest(doc, today=date(2026, 10, 16))
    assert [o["key"] for o in out] == ["expires_2026-10-17"] and out[0]["due"] == "2026-10-16"
    assert dr.suggest({**doc, "sensitive": True}, today=date(2026, 10, 16)) == []


def test_sensitive_file_public_has_no_dates_or_reminders(forest):
    cid, f = S["dismiss"]
    r = forest.patch(f"{API}/contact-files/{FOREST}/{f['id']}", json={"sensitive": True})
    assert r.status_code == 200, r.text
    assert r.json()["dates"] == [] and r.json()["reminders"] == []


# --- profile photo from Files + gallery ---
def test_use_files_photo_as_profile_and_gallery(forest, mongo):
    cid, f = S["svc"]
    r = forest.patch(f"{API}/contacts/{FOREST}/{cid}/profile-photo", json={"photo_url": f["url"]})
    assert r.status_code == 200, r.text
    c = mongo.contacts.find_one({"_id": ObjectId(cid)})
    assert c.get("photo_path") and c.get("photo_thumb_path") and c.get("photo_avatar_path"), c
    assert c["photo_thumbnail"].startswith("/api/images/") and c["photo_thumbnail"].endswith(".webp"), c["photo_thumbnail"]
    g = forest.get(f"{API}/contacts/{FOREST}/{cid}/photos/all")
    assert g.status_code == 200
    body = g.json()
    photos = body.get("photos") if isinstance(body, dict) else body
    assert any(p.get("type") == "file" and f["url"].split("?")[0] in (p.get("url") or "") for p in photos), photos


def test_profile_photo_refuses_sensitive_deleted_other(forest, mongo):
    cid, f = S["svc"]
    dcid, df = S["dismiss"]   # now sensitive
    sens_path = mongo.contact_files.find_one({"_id": ObjectId(df["id"])})["path"]
    r = forest.patch(f"{API}/contacts/{FOREST}/{dcid}/profile-photo", json={"photo_url": f"/api/images/{sens_path}"})
    assert r.status_code == 400, r.text
    # file of another contact
    r = forest.patch(f"{API}/contacts/{FOREST}/{dcid}/profile-photo", json={"photo_url": f["url"]})
    assert r.status_code == 400, r.text
    # deleted file
    mongo.contact_files.update_one({"_id": ObjectId(f["id"])}, {"$set": {"deleted": True}})
    try:
        r = forest.patch(f"{API}/contacts/{FOREST}/{cid}/profile-photo", json={"photo_url": f["url"]})
        assert r.status_code == 400, r.text
        photos = forest.get(f"{API}/contacts/{FOREST}/{cid}/photos/all").json()
        photos = photos.get("photos") if isinstance(photos, dict) else photos
        assert not any(p.get("type") == "file" for p in photos)
    finally:
        mongo.contact_files.update_one({"_id": ObjectId(f["id"])}, {"$unset": {"deleted": ""}})
    # sensitive file never in gallery
    photos = forest.get(f"{API}/contacts/{FOREST}/{dcid}/photos/all").json()
    photos = photos.get("photos") if isinstance(photos, dict) else photos
    assert not any(p.get("type") == "file" for p in photos)
