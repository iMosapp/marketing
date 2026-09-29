"""Iter 353 - HTTP-level tests for weekly leaderboard, public leaderboard, public score history, guide editor."""
import os, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
CID = "6ab983f954b9cb9243f0ba00"
REPORT_TOKEN = "6c5cdb8560b14de2a86579da265b85b3"
SCORE_TOKEN = "e4792e3c7bef452eabec3b5066ba4dd2"

ADMIN = ("forest@imosapp.com", "Admin123!")
MGR = ("qa-manager@invalid.imonsocial.test", "Manager123!")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    uid = (j.get("user") or {}).get("id") or j.get("user_id")
    return {"Authorization": f"Bearer {tok}", "X-User-ID": uid}


@pytest.fixture(scope="module")
def admin_h():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def mgr_h():
    return _login(*MGR)


# ---------- Weekly leaderboard ----------
def test_leaderboard_admin_current(admin_h):
    r = requests.get(f"{BASE}/api/shop-clients/{CID}/leaderboard", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("label", "is_current", "completed", "people", "avg_score", "prev_avg_score", "boards", "movers"):
        assert k in j, f"missing key {k}"
    assert j["is_current"] is True
    assert isinstance(j["boards"], list)


def test_leaderboard_admin_last_week(admin_h):
    r = requests.get(f"{BASE}/api/shop-clients/{CID}/leaderboard?offset=-1", headers=admin_h, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j["is_current"] is False


def test_leaderboard_non_admin_forbidden(mgr_h):
    r = requests.get(f"{BASE}/api/shop-clients/{CID}/leaderboard", headers=mgr_h, timeout=20)
    assert r.status_code == 403, r.status_code


# ---------- Public leaderboard ----------
def test_public_leaderboard_no_auth():
    r = requests.get(f"{BASE}/api/public/shop-report/{REPORT_TOKEN}/leaderboard", timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "boards" in j


def test_public_leaderboard_bogus_token():
    r = requests.get(f"{BASE}/api/public/shop-report/notarealtoken/leaderboard", timeout=20)
    assert r.status_code == 404


# ---------- Public score history ----------
def test_public_score_has_history():
    r = requests.get(f"{BASE}/api/public/shop-score/{SCORE_TOKEN}", timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "history" in j
    hist = j["history"]
    assert isinstance(hist, list) and len(hist) >= 1
    currents = [h for h in hist if h.get("current")]
    assert len(currents) == 1, f"expected exactly 1 current, got {len(currents)}"
    ats = [h.get("at") for h in hist]
    assert ats == sorted(ats), "history should be oldest first"
    for k in ("score_pct", "at", "department_label", "channel", "current"):
        assert k in hist[0]


# ---------- Guide editor ----------
def _fetch_seed_parts(admin_h):
    r = requests.get(f"{BASE}/api/public/call-guide/equipment/eq_parts", timeout=20)
    r.raise_for_status()
    return r.json()


def test_guide_validation_empty_title(admin_h):
    seed = _fetch_seed_parts(admin_h)
    body = {"title": "", "chain": seed.get("chain", []), "note": seed.get("note", ""),
            "sections": seed["sections"], "scorecard": seed["scorecard"]}
    r = requests.put(f"{BASE}/api/shop-clients/guides/equipment/eq_parts", json=body, headers=admin_h, timeout=20)
    assert r.status_code == 400
    assert "title" in r.text.lower()


def test_guide_validation_empty_scorecard(admin_h):
    seed = _fetch_seed_parts(admin_h)
    body = {"title": seed["title"], "chain": seed.get("chain", []), "note": seed.get("note", ""),
            "sections": seed["sections"], "scorecard": []}
    r = requests.put(f"{BASE}/api/shop-clients/guides/equipment/eq_parts", json=body, headers=admin_h, timeout=20)
    assert r.status_code == 400


def test_guide_non_admin_forbidden(mgr_h):
    seed = requests.get(f"{BASE}/api/public/call-guide/equipment/eq_parts", timeout=20).json()
    body = {"title": "hack", "chain": seed.get("chain", []), "note": "",
            "sections": seed["sections"], "scorecard": seed["scorecard"]}
    r = requests.put(f"{BASE}/api/shop-clients/guides/equipment/eq_parts", json=body, headers=mgr_h, timeout=20)
    assert r.status_code == 403


def test_guide_unknown_department_404(admin_h):
    seed = _fetch_seed_parts(admin_h)
    body = {"title": "x", "chain": [], "note": "", "sections": seed["sections"], "scorecard": seed["scorecard"]}
    r = requests.put(f"{BASE}/api/shop-clients/guides/equipment/eq_bogus_dept", json=body, headers=admin_h, timeout=20)
    assert r.status_code == 404


def test_guide_save_then_reset(admin_h):
    seed = _fetch_seed_parts(admin_h)
    new_title = "Iter353 Edited Parts Guide"
    # tweak one block text and add a kpi to first section
    edited = {
        "title": new_title,
        "chain": seed.get("chain", []),
        "note": seed.get("note", ""),
        "sections": [dict(s) for s in seed["sections"]],
        "scorecard": seed["scorecard"],
    }
    if edited["sections"]:
        s0 = edited["sections"][0]
        s0["kpis"] = list(s0.get("kpis", [])) + ["Iter353 KPI Check"]
        if s0.get("blocks"):
            s0["blocks"] = list(s0["blocks"])
            b0 = dict(s0["blocks"][0])
            b0["text"] = "Iter353 edited block text"
            s0["blocks"][0] = b0
    try:
        r = requests.put(f"{BASE}/api/shop-clients/guides/equipment/eq_parts", json=edited, headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["source"] == "custom"
        assert j["title"] == new_title
        # public reads the edited title
        pub = requests.get(f"{BASE}/api/public/call-guide/equipment/eq_parts", timeout=20).json()
        assert pub["title"] == new_title
    finally:
        # always reset
        r = requests.post(f"{BASE}/api/shop-clients/guides/equipment/eq_parts/reset", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["source"] == "seed"
        assert j["title"] == "Kubota Parts Customer Engagement Standard"
        assert j["total"] == 100
