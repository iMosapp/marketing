"""Tests for GET /api/admin/search (global 'Find anything' endpoint)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
SEARCH = f"{BASE_URL}/api/admin/search"
LOGIN = f"{BASE_URL}/api/auth/login"

FOREST_ID = "69a0b7095fddcede09591667"
QA_MGR_ID = "6a9b2b82cc6e7504dafc33f2"


def _login(email, password):
    r = requests.post(LOGIN, json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()


@pytest.fixture(scope="module")
def activation_id():
    try:
        data = _login("activation-tester@invalid.imonsocial.test", "NewPass123!")
        u = data.get("user", {})
        return u.get("id") or u.get("_id") or data.get("user_id")
    except Exception:
        pytest.skip("activation-tester login failed")


# ---------- 401 / 403 auth guards ----------

def test_missing_user_id_returns_401():
    r = requests.get(SEARCH, params={"q": "emerald"}, timeout=15)
    assert r.status_code == 401, r.text


def test_plain_user_forbidden(activation_id):
    r = requests.get(SEARCH, params={"q": "emerald"}, headers={"X-User-ID": activation_id}, timeout=15)
    assert r.status_code == 403, r.text


# ---------- super admin (forest) ----------

def _h(uid):
    return {"X-User-ID": uid}


def test_forest_short_query_returns_empty_groups():
    r = requests.get(SEARCH, params={"q": "a"}, headers=_h(FOREST_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("organizations", "stores", "users", "widgets", "lead_sources"):
        assert d[k] == [], f"{k} should be [] for short q, got {d[k]}"


def test_forest_emerald_returns_orgs_and_stores():
    r = requests.get(SEARCH, params={"q": "emerald"}, headers=_h(FOREST_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert len(d["organizations"]) > 0, "expected organizations for 'emerald'"
    assert len(d["stores"]) > 0, "expected stores for 'emerald'"
    # rows should have id + name
    for row in d["organizations"] + d["stores"]:
        assert row.get("id") and row.get("name") is not None


def test_forest_phone_digits_matches_users():
    r = requests.get(SEARCH, params={"q": "9122"}, headers=_h(FOREST_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    names = " ".join((u.get("name") or "") for u in d["users"]).lower()
    assert "forest" in names, f"expected a Forest user for phone digits 9122, got {d['users']}"


def test_forest_social_returns_multiple_groups():
    r = requests.get(SEARCH, params={"q": "social"}, headers=_h(FOREST_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    # per problem statement stores, users, widgets, lead_sources should be non-empty
    assert len(d["stores"]) > 0, "expected stores for 'social'"
    assert len(d["users"]) > 0, "expected users for 'social'"
    assert len(d["widgets"]) > 0, "expected widgets for 'social'"
    assert len(d["lead_sources"]) > 0, "expected lead_sources for 'social'"


def test_group_limit_is_8():
    r = requests.get(SEARCH, params={"q": "a"*2}, headers=_h(FOREST_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("organizations", "stores", "users", "widgets", "lead_sources"):
        assert len(d[k]) <= 8


# ---------- store manager (qa-manager) ----------

def test_qa_manager_qa_scoped_to_store():
    r = requests.get(SEARCH, params={"q": "qa"}, headers=_h(QA_MGR_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    # store managers should never see organizations group
    assert d["organizations"] == []
    user_names = " ".join((u.get("name") or "") for u in d["users"]).lower()
    assert "qa manager" in user_names, f"expected QA Manager in users, got {d['users']}"


def test_qa_manager_emerald_out_of_scope():
    r = requests.get(SEARCH, params={"q": "emerald"}, headers=_h(QA_MGR_ID), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["organizations"] == []
    assert d["stores"] == []
    # users/widgets/lead_sources should also be empty (Emerald is a different org)
    # allow empty; assert nothing leaks
    for k in ("stores", "users", "widgets", "lead_sources"):
        assert d[k] == [], f"qa-manager should not see 'emerald' {k}: {d[k]}"
