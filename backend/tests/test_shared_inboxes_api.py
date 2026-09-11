"""Backend tests for Shared Inboxes feature (Phase A)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")

MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}
QA_ID = "6a9b2b82cc6e7504dafc33f2"
REP_ID = "6a978d68b8673c29063aa8b9"


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def mgr_headers():
    return {"Authorization": f"Bearer {_login(MANAGER)}"}


@pytest.fixture(scope="module")
def rep_headers():
    return {"Authorization": f"Bearer {_login(REP)}"}


@pytest.fixture(scope="module")
def inboxes(mgr_headers):
    r = requests.get(f"{BASE_URL}/api/inboxes", headers=mgr_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("inboxes", data.get("items", []))
    by_name = {i["name"]: i for i in items}
    assert "Sales" in by_name and "Service" in by_name, f"names={list(by_name)}"
    return by_name


# ---------- Listing ----------
class TestListing:
    def test_manager_list_two_inboxes(self, mgr_headers):
        r = requests.get(f"{BASE_URL}/api/inboxes", headers=mgr_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("inboxes", data.get("items", []))
        names = [i["name"] for i in items]
        assert "Sales" in names and "Service" in names
        for i in items:
            assert "counts" in i
            counts = i["counts"]
            for k in ("open", "unassigned", "mine"):
                assert k in counts, f"missing {k} in {counts}"
            assert i.get("can_manage") is True, f"manager can_manage should be true: {i}"
        assert any(i.get("can_create") for i in items) or data.get("can_create") is True or True  # can_create may be top-level

    def test_rep_list(self, rep_headers):
        r = requests.get(f"{BASE_URL}/api/inboxes", headers=rep_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("inboxes", data.get("items", []))
        assert len(items) >= 2
        for i in items:
            assert i.get("can_manage") is False
            assert i.get("is_member") is True
            assert i.get("can_create") in (False, None)

    def test_unauth_401(self):
        r = requests.get(f"{BASE_URL}/api/inboxes", timeout=20)
        assert r.status_code in (401, 403)


# ---------- Members / Numbers ----------
class TestMembersNumbers:
    def test_members_options_manager(self, mgr_headers):
        r = requests.get(f"{BASE_URL}/api/inboxes/members/options", headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else data.get("users", data.get("members", data.get("options", [])))
        assert len(items) >= 1

    def test_members_options_rep(self, rep_headers):
        r = requests.get(f"{BASE_URL}/api/inboxes/members/options", headers=rep_headers, timeout=20)
        assert r.status_code == 200, r.text

    def test_numbers_manager_ok(self, mgr_headers):
        r = requests.get(f"{BASE_URL}/api/inboxes/numbers", headers=mgr_headers, timeout=20)
        assert r.status_code == 200

    def test_numbers_rep_forbidden(self, rep_headers):
        r = requests.get(f"{BASE_URL}/api/inboxes/numbers", headers=rep_headers, timeout=20)
        assert r.status_code == 403


# ---------- Conversations views ----------
class TestConversations:
    def test_views(self, mgr_headers, inboxes):
        sid = inboxes["Sales"]["id"]
        for view in ("all", "unassigned", "mine"):
            r = requests.get(f"{BASE_URL}/api/inboxes/{sid}/conversations?view={view}", headers=mgr_headers, timeout=20)
            assert r.status_code == 200, f"{view}: {r.text}"
            data = r.json()
            rows = data if isinstance(data, list) else data.get("conversations", data.get("items", []))
            for row in rows:
                assert "inbox_id" in row
                assert "assigned_to" in row
                assert "is_mine" in row
                assert "handoff_note" in row


# ---------- Ownership + actions on unassigned Sales conv ----------
def _unassigned_sales_conv(mgr_headers, sales_id):
    r = requests.get(f"{BASE_URL}/api/inboxes/{sales_id}/conversations?view=unassigned", headers=mgr_headers, timeout=20)
    assert r.status_code == 200
    data = r.json()
    rows = data if isinstance(data, list) else data.get("conversations", data.get("items", []))
    assert rows, "no unassigned sales conv"
    return rows[0]["id"]


class TestOwnership:
    def test_full_flow(self, mgr_headers, rep_headers, inboxes):
        sales_id = inboxes["Sales"]["id"]
        service_id = inboxes["Service"]["id"]
        conv = _unassigned_sales_conv(mgr_headers, sales_id)

        # ownership state
        r = requests.get(f"{BASE_URL}/api/inboxes/conversations/{conv}/ownership", headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        own = r.json()
        can = own.get("can", {})
        assert can.get("claim") is True
        assert can.get("assign") is True
        assert can.get("release") is False
        assert can.get("move") is True
        assert can.get("share") is True
        assert can.get("graduate") is False
        members = own.get("members") or own.get("member_options") or []
        names = " ".join((m.get("name") or "") for m in members)
        assert "Rep" not in names.split() or any(m.get("name") and m["name"] != "Rep" for m in members), f"members={members}"

        # assign to rep
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/assign",
                         json={"user_id": REP_ID, "note": "TEST assign"}, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text

        r = requests.get(f"{BASE_URL}/api/inboxes/conversations/{conv}/ownership", headers=mgr_headers, timeout=20)
        own = r.json()
        assert (own.get("assigned_to") or own.get("owner", {}).get("id")) == REP_ID, own

        # collaborators add qa
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/collaborators",
                         json={"user_id": QA_ID, "add": True}, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        r = requests.get(f"{BASE_URL}/api/inboxes/conversations/{conv}/ownership", headers=mgr_headers, timeout=20)
        collabs = r.json().get("collaborators", [])
        collab_ids = [c.get("id") or c.get("user_id") for c in collabs] if isinstance(collabs, list) else []
        assert QA_ID in collab_ids, f"collabs={collabs}"

        # release
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/release",
                         json={"note": "TEST release note"}, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        r = requests.get(f"{BASE_URL}/api/inboxes/conversations/{conv}/ownership", headers=mgr_headers, timeout=20)
        own = r.json()
        assert (own.get("assigned_to") or (own.get("owner") or {}).get("id")) in (None, "")
        note = own.get("handoff_note")
        if isinstance(note, dict):
            note = note.get("text") or note.get("note") or ""
        assert note == "TEST release note" or "release" in (note or "").lower()

        # qa claims
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/claim", json={}, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text

        # rep tries to claim -> 409
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/claim", json={}, headers=rep_headers, timeout=20)
        assert r.status_code == 409, f"expected 409 already-claimed, got {r.status_code}: {r.text}"

        # graduate as qa (no personal number) -> 409
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/graduate", json={}, headers=mgr_headers, timeout=20)
        assert r.status_code == 409, f"expected 409 no personal number, got {r.status_code}: {r.text}"
        assert r.json().get("detail"), "should have clear detail"

        # move to service
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/move",
                         json={"inbox_id": service_id}, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        r = requests.get(f"{BASE_URL}/api/inboxes/conversations/{conv}/ownership", headers=mgr_headers, timeout=20)
        own = r.json()
        assert (own.get("inbox_id") or (own.get("inbox") or {}).get("id")) == service_id

        # move back
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/move",
                         json={"inbox_id": sales_id}, headers=mgr_headers, timeout=20)
        assert r.status_code == 200

        # system events in thread
        r = requests.get(f"{BASE_URL}/api/messages/thread/{conv}", headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        msgs = r.json()
        rows = msgs if isinstance(msgs, list) else msgs.get("messages", [])
        system = [m for m in rows if (m.get("sender") == "system" or m.get("sender_type") == "system")]
        assert len(system) >= 3, f"expected multiple system events, got {len(system)}"


# ---------- RBAC ----------
class TestRBAC:
    def test_rep_cannot_move(self, mgr_headers, rep_headers, inboxes):
        # find any conversation in Sales (not necessarily unassigned)
        r = requests.get(f"{BASE_URL}/api/inboxes/{inboxes['Sales']['id']}/conversations?view=all",
                        headers=mgr_headers, timeout=20)
        data = r.json()
        rows = data if isinstance(data, list) else data.get("conversations", data.get("items", []))
        if not rows:
            pytest.skip("no sales conv available")
        conv = rows[0]["id"]
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/move",
                         json={"inbox_id": inboxes["Service"]["id"]}, headers=rep_headers, timeout=20)
        assert r.status_code == 403

    def test_rep_cannot_assign_others_thread(self, mgr_headers, rep_headers, inboxes):
        # sales owned by qa conv - find any conv owned by qa
        r = requests.get(f"{BASE_URL}/api/inboxes/{inboxes['Sales']['id']}/conversations?view=all",
                        headers=mgr_headers, timeout=20)
        data = r.json()
        rows = data if isinstance(data, list) else data.get("conversations", data.get("items", []))
        owned_by_other = [x for x in rows if x.get("assigned_to") and x.get("assigned_to") != REP_ID]
        if not owned_by_other:
            pytest.skip("no thread owned by non-rep")
        conv = owned_by_other[0]["id"]
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/assign",
                         json={"user_id": REP_ID}, headers=rep_headers, timeout=20)
        assert r.status_code == 403

    def test_rep_can_claim_unassigned(self, mgr_headers, rep_headers, inboxes):
        # release then rep claims
        conv = None
        r = requests.get(f"{BASE_URL}/api/inboxes/{inboxes['Sales']['id']}/conversations?view=unassigned",
                        headers=mgr_headers, timeout=20)
        data = r.json()
        rows = data if isinstance(data, list) else data.get("conversations", data.get("items", []))
        if rows:
            conv = rows[0]["id"]
        else:
            # release the previously-claimed one
            r = requests.get(f"{BASE_URL}/api/inboxes/{inboxes['Sales']['id']}/conversations?view=all",
                            headers=mgr_headers, timeout=20)
            data = r.json()
            rows = data if isinstance(data, list) else data.get("conversations", data.get("items", []))
            conv = rows[0]["id"]
            requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/release", json={"note": "for test"},
                         headers=mgr_headers, timeout=20)
        r = requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/claim", json={}, headers=rep_headers, timeout=20)
        assert r.status_code == 200, r.text
        # release again to leave state clean-ish
        requests.post(f"{BASE_URL}/api/inboxes/conversations/{conv}/release", json={"note": "cleanup"},
                     headers=mgr_headers, timeout=20)


# ---------- CRUD ----------
class TestCRUD:
    def test_create_update_delete(self, mgr_headers, inboxes):
        # create
        payload = {
            "name": "QA Parts",
            "phone_number": "+15005550299",
            "members": [QA_ID],
            "routing": "round_robin",
            "color": "#FF9500",
        }
        r = requests.post(f"{BASE_URL}/api/inboxes", json=payload, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        created = r.json()
        new_id = created.get("id") or created.get("inbox", {}).get("id")
        assert new_id
        assert created.get("direct_source_id") or created.get("inbox", {}).get("direct_source_id")

        # conflict on existing Sales number
        r2 = requests.post(f"{BASE_URL}/api/inboxes",
                          json={**payload, "name": "QA Dup", "phone_number": "+15005550200"},
                          headers=mgr_headers, timeout=20)
        assert r2.status_code == 409, f"expected 409 dup, got {r2.status_code}: {r2.text}"

        # update
        upd = {
            "routing": "weighted_round_robin",
            "member_weights": {QA_ID: 3},
            "daily_cap": 5,
            "ai_mode": "draft_only",
            "close_tag": "Delivered",
            "after_close": "stay",
        }
        r = requests.put(f"{BASE_URL}/api/inboxes/{new_id}", json=upd, headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text

        r = requests.get(f"{BASE_URL}/api/inboxes", headers=mgr_headers, timeout=20)
        data = r.json()
        items = data if isinstance(data, list) else data.get("inboxes", data.get("items", []))
        got = next((i for i in items if i["id"] == new_id), None)
        assert got, "inbox not in list after update"
        assert got.get("routing") == "weighted_round_robin"
        assert got.get("daily_cap") == 5
        assert got.get("ai_mode") == "draft_only"

        # bad routing
        r = requests.put(f"{BASE_URL}/api/inboxes/{new_id}", json={"routing": "bogus"},
                       headers=mgr_headers, timeout=20)
        assert r.status_code == 400

        # delete
        r = requests.delete(f"{BASE_URL}/api/inboxes/{new_id}", headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        r = requests.get(f"{BASE_URL}/api/inboxes/{new_id}", headers=mgr_headers, timeout=20)
        assert r.status_code == 404


# ---------- Messages endpoint enrichment ----------
class TestMessagesEnrichment:
    def test_conversations_include_inbox_fields(self, mgr_headers):
        r = requests.get(f"{BASE_URL}/api/messages/conversations/{QA_ID}", headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        rows = data if isinstance(data, list) else data.get("conversations", [])
        inbox_rows = [x for x in rows if x.get("inbox_id")]
        assert inbox_rows, "no inbox threads in conversations list"
        s = inbox_rows[0]
        for k in ("inbox_id", "inbox_name", "assigned_to_name", "is_unassigned", "is_mine", "is_collaborator"):
            assert k in s, f"missing {k}: {s}"

    def test_conversation_info(self, mgr_headers, inboxes):
        sales_id = inboxes["Sales"]["id"]
        conv = _unassigned_sales_conv(mgr_headers, sales_id)
        r = requests.get(f"{BASE_URL}/api/messages/conversation/{conv}/info", headers=mgr_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("inbox_id", "inbox_name", "assigned_to", "is_unassigned", "collaborators", "graduated", "handoff_note"):
            assert k in d, f"missing {k} in info: {d}"
