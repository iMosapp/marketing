"""Batch 4 backend tests: /api/schedule/team name fallback + /api/leads em-dash strip."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "forest@imosapp.com"
PASSWORD = "Admin123!"
EM_DASH = "\u2014"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    d = r.json()
    token = d.get("access_token") or d.get("token")
    user = d.get("user") or {}
    uid = user.get("id") or user.get("_id") or d.get("user_id")
    assert token and uid, f"missing token/uid in {d}"
    return {"Authorization": f"Bearer {token}", "X-User-ID": str(uid), "Content-Type": "application/json"}


def test_schedule_team_no_unknown(auth):
    r = requests.get(f"{BASE_URL}/api/schedule/team", headers=auth, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    items = r.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("team") or items.get("data") or []
    assert isinstance(items, list), f"expected list, got {type(items)}: {str(items)[:200]}"
    print(f"schedule/team count={len(items)}")
    bad = [i for i in items if not i.get("name") or i.get("name") == "Unknown"]
    assert not bad, f"items with empty/'Unknown' name: {bad[:3]}"


def test_leads_no_em_dash(auth):
    r = requests.get(f"{BASE_URL}/api/leads/?limit=100", headers=auth, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    leads = data if isinstance(data, list) else (data.get("items") or data.get("leads") or data.get("data") or [])
    print(f"leads count={len(leads)}")
    bad = []
    for lead in leads:
        dm = lead.get("draft_message") or ""
        if EM_DASH in dm:
            bad.append({"id": lead.get("id") or lead.get("_id"), "snippet": dm[:80]})
    assert not bad, f"draft_message contains em-dash in {len(bad)} leads. first: {bad[:2]}"
