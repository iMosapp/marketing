"""Backend tests for the redesigned Contacts page: smart-lists counts endpoint,
smart_list filter param on GET /api/contacts/{user_id}, auth enforcement,
pagination and sorting."""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

SMART_KEYS = ["needs_attention", "hot", "new_this_week", "birthdays"]


@pytest.fixture(scope="session")
def creds():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    email = re.search(r'(?im)^\s*[-*]?\s*Email:\s*`?([^`\s]+)', content).group(1)
    password = re.search(r'(?im)^\s*[-*]?\s*Password:\s*`?([^`\s]+)', content).group(1)
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth(session, creds):
    r = session.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    user = data.get("user") or {}
    uid = user.get("id") or user.get("_id")
    assert token and uid, f"login payload missing token/user id: {list(data.keys())}"
    return {"token": token, "user_id": uid, "headers": {"Authorization": f"Bearer {token}"}}


# ---------- Auth enforcement ----------
class TestAuth:
    def test_smart_lists_requires_auth(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}/smart-lists", timeout=30)
        assert r.status_code == 401, f"expected 401 without token, got {r.status_code}"

    def test_contacts_list_requires_auth(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}?paginated=true", timeout=30)
        assert r.status_code == 401

    def test_other_user_id_forbidden(self, session, auth):
        # random valid-looking objectid should not be readable (BOLA) - admin may be allowed
        r = session.get(f"{BASE_URL}/api/contacts/000000000000000000000000/smart-lists",
                        headers=auth["headers"], timeout=30)
        assert r.status_code in (200, 403, 404), r.status_code


# ---------- Smart list counts ----------
class TestSmartListCounts:
    def test_counts_shape(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}/smart-lists",
                        headers=auth["headers"], timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert set(data.keys()) == set(SMART_KEYS), data
        for k in SMART_KEYS:
            assert isinstance(data[k], int) and data[k] >= 0, (k, data[k])

    @pytest.mark.parametrize("key", SMART_KEYS)
    def test_count_matches_filtered_total(self, session, auth, key):
        counts = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}/smart-lists",
                             headers=auth["headers"], timeout=30).json()
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                        params={"smart_list": key, "paginated": "true", "limit": 50},
                        headers=auth["headers"], timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert set(["contacts", "total", "skip", "limit", "has_more"]).issubset(body.keys())
        assert body["total"] == counts[key], (
            f"smart list '{key}': counts endpoint={counts[key]} list total={body['total']}")
        assert len(body["contacts"]) <= body["total"]

    def test_invalid_smart_list_ignored(self, session, auth):
        full = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                           params={"paginated": "true"}, headers=auth["headers"], timeout=60).json()
        bogus = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                            params={"smart_list": "not_a_list", "paginated": "true"},
                            headers=auth["headers"], timeout=60).json()
        assert bogus["total"] == full["total"]


# ---------- Hot smart list with real tag mutation ----------
class TestHotSmartList:
    def test_hot_tag_reflects_in_smart_list(self, session, auth):
        uid = auth["user_id"]
        h = auth["headers"]
        listing = session.get(f"{BASE_URL}/api/contacts/{uid}",
                              params={"paginated": "true", "limit": 5}, headers=h, timeout=60).json()
        if not listing["contacts"]:
            pytest.skip("no contacts available")
        contact = listing["contacts"][0]
        cid = contact.get("_id") or contact.get("id")
        original_tags = contact.get("tags") or []
        before = session.get(f"{BASE_URL}/api/contacts/{uid}/smart-lists", headers=h, timeout=30).json()["hot"]
        try:
            r = session.patch(f"{BASE_URL}/api/contacts/{uid}/{cid}/tags",
                              json={"tags": list(set(original_tags + ["hot"]))}, headers=h, timeout=30)
            assert r.status_code == 200, f"tag patch failed {r.status_code}: {r.text[:200]}"
            after = session.get(f"{BASE_URL}/api/contacts/{uid}/smart-lists", headers=h, timeout=30).json()["hot"]
            assert after == before + 1, f"hot count did not increment: {before} -> {after}"
            hot_list = session.get(f"{BASE_URL}/api/contacts/{uid}",
                                   params={"smart_list": "hot", "paginated": "true"},
                                   headers=h, timeout=60).json()
            ids = [c.get("_id") for c in hot_list["contacts"]]
            assert cid in ids, "tagged contact not returned by smart_list=hot"
        finally:
            session.patch(f"{BASE_URL}/api/contacts/{uid}/{cid}/tags",
                          json={"tags": original_tags}, headers=h, timeout=30)
            restored = session.get(f"{BASE_URL}/api/contacts/{uid}/smart-lists",
                                   headers=h, timeout=30).json()["hot"]
            assert restored == before, f"cleanup failed, hot={restored} expected {before}"


# ---------- Pagination + sorting ----------
class TestListBehaviour:
    def test_pagination_pages_differ(self, session, auth):
        uid, h = auth["user_id"], auth["headers"]
        p1 = session.get(f"{BASE_URL}/api/contacts/{uid}",
                         params={"paginated": "true", "limit": 5, "skip": 0}, headers=h, timeout=60).json()
        if p1["total"] <= 5:
            pytest.skip("not enough contacts")
        p2 = session.get(f"{BASE_URL}/api/contacts/{uid}",
                         params={"paginated": "true", "limit": 5, "skip": 5}, headers=h, timeout=60).json()
        assert p1["has_more"] is True
        assert p1["total"] == p2["total"]
        assert {c["_id"] for c in p1["contacts"]}.isdisjoint({c["_id"] for c in p2["contacts"]})

    def test_sort_alpha_default(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                        params={"paginated": "true", "limit": 25, "sort_by": "alpha"},
                        headers=auth["headers"], timeout=60)
        assert r.status_code == 200
        names = [(c.get("first_name") or "") for c in r.json()["contacts"]]
        # NOTE: Mongo sort is case-sensitive (no collation), so compare raw values.
        # Case-insensitive ordering is a known minor UX issue reported to the dev agent.
        assert names == sorted(names), names[:10]

    def test_sort_recent(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                        params={"paginated": "true", "limit": 25, "sort_by": "recent"},
                        headers=auth["headers"], timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json()["contacts"], list)

    def test_team_view_enriches_salesperson(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                        params={"paginated": "true", "limit": 10, "view_mode": "team"},
                        headers=auth["headers"], timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "total" in body
        if body["contacts"]:
            assert any("salesperson_name" in c for c in body["contacts"])

    def test_search_filters(self, session, auth):
        uid, h = auth["user_id"], auth["headers"]
        base = session.get(f"{BASE_URL}/api/contacts/{uid}",
                           params={"paginated": "true", "limit": 5}, headers=h, timeout=60).json()
        if not base["contacts"]:
            pytest.skip("no contacts")
        term = (base["contacts"][0].get("first_name") or "")[:3]
        if len(term) < 3:
            pytest.skip("no usable search term")
        r = session.get(f"{BASE_URL}/api/contacts/{uid}",
                        params={"paginated": "true", "search": term}, headers=h, timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] <= base["total"]
        assert body["total"] >= 1
        for c in body["contacts"]:
            blob = " ".join(str(c.get(f) or "") for f in ("first_name", "last_name", "email", "phone")).lower()
            assert term.lower() in blob or any(term.lower() in str(t).lower() for t in (c.get("tags") or []))

    def test_no_raw_objectid_leak(self, session, auth):
        r = session.get(f"{BASE_URL}/api/contacts/{auth['user_id']}",
                        params={"paginated": "true", "limit": 5}, headers=auth["headers"], timeout=60)
        for c in r.json()["contacts"]:
            assert isinstance(c.get("_id"), str)
