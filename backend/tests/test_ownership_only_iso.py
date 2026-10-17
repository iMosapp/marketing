# Isolated "ownership-only" hotfix build: contact ownership / two-tier isolation API workflow checks (B1-B8)
import base64
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

WALT = "6ad2d5f0aed6a4c303816547"
THREAD = "6ad2d5f0aed6a4c30381654f"
A_ID = "6ad2d5efaed6a4c303816544"
A2_ID = "6ad2d5efaed6a4c303816545"
M_ID = "6ad2d5f0aed6a4c303816546"

CREDS = {
    "a": ("qa-sameorg-a@invalid.imonsocial.test", "SameOrgIso123!"),
    "a2": ("qa-sameorg-a2@invalid.imonsocial.test", "SameOrgIso123!"),
    "m": ("qa-sameorg-m@invalid.imonsocial.test", "SameOrgIso123!"),
    "rep": ("activation-tester@invalid.imonsocial.test", "NewPass123!"),
    "admin": ("forest@imosapp.com", "Admin123!"),
}
_cache = {}
CREATED = {}


def login(key):
    if key in _cache:
        return _cache[key]
    email, pw = CREDS[key]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login {key} failed {r.status_code} {r.text[:200]}")
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    user = d.get("user") or {}
    uid = str(user.get("_id") or user.get("id"))
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    _cache[key] = (s, uid)
    return _cache[key]


# Health / build label
def test_health_build():
    r = requests.get(f"{API}/health", timeout=20)
    assert r.status_code == 200
    assert r.json()["build"] == "2026-10-17.ownership-only"


# B1 contact create + edit
def test_b1_contact_create_edit():
    s, uid = login("rep")
    r = s.post(f"{API}/contacts/{uid}", json={"first_name": "TEST_Iso", "last_name": "Api", "phone": "+15005550182", "source": "manual"})
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    cid = str(d.get("_id") or d.get("id"))
    assert cid and cid != "None"
    CREATED["contact"] = cid
    r = s.put(f"{API}/contacts/{uid}/{cid}", json={"first_name": "TEST_Iso", "last_name": "Api", "phone": "+15005550182", "notes": "TEST_iso note updated"})
    assert r.status_code == 200, r.text[:300]
    g = s.get(f"{API}/contacts/{uid}/{cid}")
    assert g.status_code == 200
    assert g.json().get("notes") == "TEST_iso note updated"


# B2 tasks on own contact ok; A2 on Walt -> 404
def test_b2_task_own_contact():
    s, uid = login("rep")
    cid = CREATED.get("contact") or pytest.skip("no contact")
    r = s.post(f"{API}/tasks/{uid}", json={"contact_id": cid, "title": "TEST_iso task", "type": "manual"})
    assert r.status_code in (200, 201), r.text[:300]
    d = r.json()
    CREATED["task"] = str(d.get("_id") or d.get("id") or d)


def test_b2_task_on_walt_blocked():
    s, uid = login("a2")
    assert uid == A2_ID
    title = f"TEST_iso_blocked_{uuid.uuid4().hex[:6]}"
    r = s.post(f"{API}/tasks/{uid}", json={"contact_id": WALT, "title": title, "type": "manual"})
    assert r.status_code == 404, f"{r.status_code} {r.text[:300]}"
    lst = s.get(f"{API}/tasks/{uid}")
    if lst.status_code == 200:
        assert title not in lst.text


# B3 attachments
def _chunk(s, uid, cid):
    body = {"upload_id": f"TEST{uuid.uuid4().hex[:10]}", "index": 0, "total": 1, "contact_id": cid,
            "name": "TEST_note.pdf", "content_type": "application/pdf", "data": base64.b64encode(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n").decode()}
    return s.post(f"{API}/contact-files/{uid}/chunk", json=body)


def test_b3_attachment_own():
    s, uid = login("rep")
    cid = CREATED.get("contact") or pytest.skip("no contact")
    r = _chunk(s, uid, cid)
    assert r.status_code == 200, r.text[:300]
    CREATED["file"] = r.json()
    assert "file" in r.text or "id" in r.text


def test_b3_attachment_walt_blocked():
    s, uid = login("a2")
    r = _chunk(s, uid, WALT)
    assert r.status_code == 404, f"{r.status_code} {r.text[:300]}"


# B4 private reads on Walt by A2 -> 404; A and M -> 200
@pytest.mark.parametrize("path", [
    "/contacts/{u}/{w}", "/contacts/{u}/{w}/personal-details", "/voice-notes/{u}/{w}"])
def test_b4_a2_reads_404(path):
    s, uid = login("a2")
    r = s.get(API + path.format(u=uid, w=WALT))
    assert r.status_code == 404, f"{path} {r.status_code} {r.text[:200]}"
    assert "Harley" not in r.text


def test_b4_a2_contact_ask_404():
    s, uid = login("a2")
    r = s.post(f"{API}/contact-ask/{WALT}/ask", json={"question": "What does he ride?"}, timeout=60)
    assert r.status_code == 404, f"{r.status_code} {r.text[:200]}"
    g = s.get(f"{API}/contact-ask/{WALT}")
    assert g.status_code == 404


@pytest.mark.parametrize("key", ["a", "m"])
def test_b4_owner_manager_200(key):
    s, uid = login(key)
    r = s.get(f"{API}/contacts/{uid}/{WALT}")
    assert r.status_code == 200, r.text[:200]
    assert "Harley" in r.text


# B5 shared inbox
def test_b5_a2_cannot_claim_or_assign():
    s, uid = login("a2")
    r = s.post(f"{API}/inboxes/conversations/{THREAD}/claim")
    assert r.status_code in (403, 404), f"claim {r.status_code} {r.text[:200]}"
    r = s.post(f"{API}/inboxes/conversations/{THREAD}/assign", json={"user_id": A2_ID})
    assert r.status_code in (403, 404), f"assign {r.status_code} {r.text[:200]}"


def test_b5_a2_thread_messages_open():
    s, uid = login("a2")
    r = s.get(f"{API}/messages/thread/{THREAD}")
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    assert "truck still there" in r.text
    for w in ("Harley", "NADA", "three dealerships"):
        assert w not in r.text, w


# B6 campaign enrollment
def test_b6_enroll_own():
    s, uid = login("rep")
    cid = CREATED.get("contact") or pytest.skip("no contact")
    r = s.get(f"{API}/campaigns/{uid}")
    if r.status_code != 200 or not r.json():
        pytest.skip(f"rep has no campaigns ({r.status_code})")
    camps = r.json() if isinstance(r.json(), list) else r.json().get("campaigns", [])
    if not camps:
        pytest.skip("rep has no campaigns")
    camp = str(camps[0].get("_id") or camps[0].get("id"))
    CREATED["campaign"] = camp
    e = s.post(f"{API}/campaigns/{uid}/{camp}/enroll/{cid}")
    assert e.status_code in (200, 201), f"{e.status_code} {e.text[:300]}"
    CREATED["enroll"] = e.text[:200]


def test_b6_enroll_walt_by_a2_refused():
    s, uid = login("a2")
    r = s.get(f"{API}/campaigns/{uid}")
    camps = []
    if r.status_code == 200:
        j = r.json()
        camps = j if isinstance(j, list) else j.get("campaigns", [])
    camp = str(camps[0].get("_id") or camps[0].get("id")) if camps else "6ad2d5f0aed6a4c300000000"
    e = s.post(f"{API}/campaigns/{uid}/{camp}/enroll/{WALT}")
    assert e.status_code in (403, 404), f"{e.status_code} {e.text[:300]}"


# B7 super admin audit endpoints
def test_b7_admin_audit():
    s, _ = login("admin")
    r = s.get(f"{API}/admin/contact-access-audit")
    assert r.status_code == 200, r.text[:200]
    rows = r.json()["rows"]
    assert isinstance(rows, list)
    for row in rows[:50]:
        for k in ("first_name", "last_name", "notes", "name", "phone", "email"):
            assert k not in row, f"leaks {k}: {row}"
    CREATED["audit_keys"] = sorted(rows[0].keys()) if rows else []


def test_b7_merge_assessment_no_confirm_400():
    s, _ = login("admin")
    r = s.get(f"{API}/admin/contact-merge-assessment")
    assert r.status_code == 400


def test_b7_non_admin_403():
    s, _ = login("rep")
    assert s.get(f"{API}/admin/contact-access-audit").status_code == 403
    assert s.get(f"{API}/admin/contact-merge-assessment").status_code == 403


# B8 cross-org
def test_b8_cross_org_404():
    s, uid = login("rep")
    r = s.get(f"{API}/contacts/{uid}/{WALT}")
    assert r.status_code == 404
    assert "Harley" not in r.text


def test_zz_print_created():
    print("CREATED:", CREATED)
