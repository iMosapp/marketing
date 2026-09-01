"""
Iteration 289 — Broadcast pick-specific-contacts + CSV list_tag tagging.
Covers: GET /api/broadcast/preview (contact_ids union semantics),
POST /api/broadcast (draft create), DELETE /api/broadcast/{id},
POST /api/contacts/{user_id}/import-csv/confirm?list_tag=X
NOTE: never calls POST /api/broadcast/{id}/send (real Twilio SMS).
"""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

EMAIL = "forest@imosapp.com"
PASSWORD = "Admin123!"
USER_ID = "69a0b7095fddcede09591667"
TEST_TAG = "TEST_LIST_289"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def all_count(client):
    r = client.get(f"{BASE_URL}/api/broadcast/preview", params={"user_id": USER_ID}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()["count"]


@pytest.fixture(scope="module")
def sample_contact(client):
    r = client.get(f"{BASE_URL}/api/broadcast/preview", params={"user_id": USER_ID}, timeout=30)
    assert r.status_code == 200
    sample = r.json()["sample"]
    assert len(sample) > 0, "no contacts available for picking"
    return sample[0]


# ---------- Preview / union semantics ----------
class TestPreviewPickedContacts:
    def test_preview_all(self, all_count):
        assert all_count > 1

    def test_preview_picked_only_is_exactly_one(self, client, sample_contact, all_count):
        r = client.get(f"{BASE_URL}/api/broadcast/preview",
                       params={"user_id": USER_ID, "contact_ids": sample_contact["id"]}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["count"] == 1, f"picked-only should be 1, got {body['count']} (all={all_count})"
        assert body["sample"][0]["id"] == sample_contact["id"]

    def test_preview_tag_plus_outside_contact_is_union(self, client):
        tag_r = client.get(f"{BASE_URL}/api/broadcast/preview",
                           params={"user_id": USER_ID, "tags": "Sold"}, timeout=30)
        assert tag_r.status_code == 200, tag_r.text[:300]
        tag_count = tag_r.json()["count"]
        tag_ids = {c["id"] for c in tag_r.json()["sample"]}
        assert tag_count > 0, "tag 'Sold' matched 0 contacts — cannot test union"

        all_r = client.get(f"{BASE_URL}/api/broadcast/preview", params={"user_id": USER_ID}, timeout=30)
        outside = next((c for c in all_r.json()["sample"] if c["id"] not in tag_ids), None)
        assert outside, "no contact outside tag in sample"

        union_r = client.get(f"{BASE_URL}/api/broadcast/preview",
                             params={"user_id": USER_ID, "tags": "Sold", "contact_ids": outside["id"]}, timeout=30)
        assert union_r.status_code == 200
        assert union_r.json()["count"] == tag_count + 1, (
            f"expected union {tag_count + 1}, got {union_r.json()['count']}")

    def test_preview_invalid_contact_id_does_not_500(self, client):
        r = client.get(f"{BASE_URL}/api/broadcast/preview",
                       params={"user_id": USER_ID, "contact_ids": "not-an-objectid"}, timeout=30)
        assert r.status_code in (200, 400), r.text[:300]


# ---------- Draft creation with picked contact ----------
class TestDraftCreation:
    created = []

    def test_create_draft_with_picked_contact(self, client, sample_contact):
        payload = {
            "name": "TEST_289 Picked Draft",
            "message": "Hi {first_name}, TEST draft do not send.",
            "filters": {"tags": [], "exclude_tags": [], "contact_ids": [sample_contact["id"]]},
        }
        r = client.post(f"{BASE_URL}/api/broadcast", params={"user_id": USER_ID}, json=payload, timeout=30)
        assert r.status_code == 200, r.text[:400]
        b = r.json()["broadcast"]
        TestDraftCreation.created.append(b["id"])
        assert b["status"] == "draft"
        assert b["recipient_count"] == 1, f"recipient_count should be 1, got {b['recipient_count']}"
        assert b["recipients"] == [sample_contact["id"]]

        # GET verifies persistence
        g = client.get(f"{BASE_URL}/api/broadcast/{b['id']}", params={"user_id": USER_ID}, timeout=30)
        assert g.status_code == 200
        gb = g.json()["broadcast"]
        assert gb["recipient_count"] == 1
        assert gb["filters"].get("contact_ids") == [sample_contact["id"]]

        # appears in list
        lst = client.get(f"{BASE_URL}/api/broadcast", params={"user_id": USER_ID}, timeout=30)
        assert lst.status_code == 200
        assert any(x["id"] == b["id"] for x in lst.json()["broadcasts"])

    def test_delete_draft_and_verify_removal(self, client):
        assert TestDraftCreation.created, "no draft created"
        bid = TestDraftCreation.created.pop()
        d = client.delete(f"{BASE_URL}/api/broadcast/{bid}", params={"user_id": USER_ID}, timeout=30)
        assert d.status_code in (200, 204), d.text[:300]
        g = client.get(f"{BASE_URL}/api/broadcast/{bid}", params={"user_id": USER_ID}, timeout=30)
        assert g.status_code == 404


# ---------- CSV import with list_tag ----------
CSV_BODY = (
    "First Name,Last Name,Phone 1 - Label,Phone 1 - Value,E-mail 1 - Label,E-mail 1 - Value\n"
    "TESTCSV,Person289,Mobile,+15551230289,Personal,testcsv289@example.test\n"
)


class TestCsvListTag:
    def test_preview_then_confirm_with_list_tag(self, client):
        files = {"file": ("test289.csv", CSV_BODY, "text/csv")}
        s = requests.Session()
        s.headers.update({k: v for k, v in client.headers.items() if k.lower() == "authorization"})
        p = s.post(f"{BASE_URL}/api/contacts/{USER_ID}/import-csv/preview", files=files, timeout=60)
        assert p.status_code == 200, p.text[:400]
        pv = p.json()
        assert pv["total_parsed"] == 1, pv
        contacts = pv["contacts"]

        c = client.post(f"{BASE_URL}/api/contacts/{USER_ID}/import-csv/confirm",
                        params={"list_tag": TEST_TAG}, json=contacts, timeout=60)
        assert c.status_code == 200, c.text[:400]
        res = c.json()
        assert res["imported"] + res["skipped"] == 1

        # tag doc created and visible
        t = client.get(f"{BASE_URL}/api/tags/{USER_ID}", timeout=30)
        assert t.status_code == 200, t.text[:300]
        body = t.json()
        tags = body.get("tags", body) if isinstance(body, dict) else body
        names = [x.get("name") for x in tags]
        assert TEST_TAG in names, f"{TEST_TAG} not in tags: {names[:20]}"

        # contact tagged -> broadcast preview by that tag finds it
        pr = client.get(f"{BASE_URL}/api/broadcast/preview",
                        params={"user_id": USER_ID, "tags": TEST_TAG}, timeout=30)
        assert pr.status_code == 200
        assert pr.json()["count"] >= 1, "tagged contact not found via tag filter"

    def test_cleanup(self, client):
        # find + delete test contact
        s = client.get(f"{BASE_URL}/api/contacts/{USER_ID}", params={"search": "TESTCSV", "limit": 100}, timeout=30)
        deleted = 0
        assert s.status_code == 200, s.text[:300]
        body = s.json()
        items = body.get("contacts", []) if isinstance(body, dict) else body
        for c in items:
            if c.get("first_name") == "TESTCSV":
                cid = c.get("id") or c.get("_id")
                d = client.delete(f"{BASE_URL}/api/contacts/{USER_ID}/{cid}", timeout=30)
                if d.status_code in (200, 204):
                    deleted += 1
        assert deleted >= 1, f"cleanup failed, found {len(items)} contacts"
        print(f"cleanup: deleted {deleted} test contacts (search status {s.status_code})")


# ---------- Auth playbook spot-checks (non-destructive; no brute force to avoid locking admin) ----------
class TestAuthPlaybook:
    def test_login_sets_httponly_cookie(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        raw = r.headers.get("set-cookie", "")
        assert "HttpOnly" in raw or "httponly" in raw.lower(), f"no HttpOnly cookie on login: {raw[:200]}"
        body = r.json()
        assert body.get("token") or body.get("access_token"), "login response missing token"

    def test_login_wrong_password_rejected(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"email": "nobody_289@example.test", "password": "wrong-pass-289"}, timeout=30)
        assert r.status_code in (401, 403, 429), f"unexpected {r.status_code}: {r.text[:200]}"
